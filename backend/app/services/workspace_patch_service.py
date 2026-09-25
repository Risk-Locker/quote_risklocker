"""Write-side workspace optimistic patch mutation engine."""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select, delete
from sqlalchemy.orm import defer, load_only
from sqlalchemy.orm.attributes import flag_modified

from app.core.errors import AppError
from app.domain.benefits import (
    BenefitValue,
    CostStatus,
    MoneyAmount,
    ReviewedBenefitState,
    SourceLineDisposition,
)
from app.models.enums import RecordStatus, Role
from app.models.tables import (
    AuditEvent,
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    BenefitFacet,
    BenefitPackage,
    BenefitPackagePlan,
    BenefitPackagePlanItem,
    BenefitRelation,
    CatalogOffering,
    CompanyBenefitCondition,
    CompanyBenefitConfig,
    CorrectionMemory,
    DraftBenefitSelection,
    DraftSourceLineDecision,
    ExtractionBenefitLine,
    ExtractionRecord,
    GeneratedPdfVersion,
    InsuranceCompany,
    InsuranceProduct,
    InsuranceProductTier,
    OutputTemplateConfig,
    QuotationDraft,
    Session,
    TemplateRevision,
    UploadedFile,
    new_id,
)
from app.rendering.render_context import (
    RenderContextError,
    adjusted_total_text,
    build_extras,
    format_benefit_value,
    resolve_benefit_cards,
)
from app.services.catalog_review_service import _resolve_vehicle_category, auto_apply_extracted_benefits, initialize_catalog_review, pin_catalog_context, seed_base_benefits
from app.extraction.validators import normalize_date, normalize_money, normalize_valuation_type
from app.extraction.benefit_lines import is_spurious_benefit_line




from app.services.workspace_common import (
    SCALAR_DECISIONS, SELECTION_KEY_RE, _UUID_RE, BUSINESS_ROLES, PIN_SENSITIVE_FIELDS,
    MONEY_FIELDS, DATE_FIELDS, TOTAL_SOURCES,
    _utcnow, _require_business_user, _session_and_draft, _rows_for_draft,
    _template_for_draft, _field_summary, generation_blockers
)


__all__ = ['_locked_draft', '_validate_selection_key', '_selection_by_key', '_decision_by_line', '_line_belongs_to_draft', '_apply_scalar_decision', '_normalize_edited_value', '_recompute_total', '_draft_field_text', '_sync_detected_company', '_reset_catalog_pin', '_reset_draft_benefits_for_catalog', '_reconcile_catalog_pin', '_apply_pin_catalog', '_apply_select_package_tier', '_apply_reset_benefits', '_safe_concept_id', '_safe_source_line_id', '_safe_package_plan_id', '_apply_custom_benefit', '_draft_selections_with_pending', '_resolve_selection', '_apply_select_catalog_offering', '_apply_benefit_update', '_apply_revert_benefit', '_drop_plan_selection', '_apply_select_package_plan', '_apply_remove_package_plan', '_apply_source_disposition', '_apply_layout_override', '_apply_template_selection', 'apply_workspace_patch']


def _locked_draft(db, user, draft_id: str) -> QuotationDraft:
    _require_business_user(user)
    draft = db.scalar(
        select(QuotationDraft).where(QuotationDraft.id == draft_id).with_for_update()
    )
    if not draft or draft.id != draft_id or draft.deleted_at:
        raise AppError("Draft not found.", 404)
    return draft



def _validate_selection_key(value: Any) -> str:
    key = str(value or "").strip().lower()
    if not SELECTION_KEY_RE.fullmatch(key):
        raise AppError("Selection key must use lowercase letters, numbers, dots, colons, underscores, or dashes.", 422)
    return key



def _selection_by_key(db, draft_id: str, selection_key: str) -> DraftBenefitSelection | None:
    for selection in _rows_for_draft(db, DraftBenefitSelection, draft_id):
        if selection.selection_key == selection_key:
            return selection
    return None



def _decision_by_line(db, draft_id: str, source_line_id: str) -> DraftSourceLineDecision | None:
    for decision in _rows_for_draft(db, DraftSourceLineDecision, draft_id):
        if decision.source_line_id == source_line_id:
            return decision
    return None



def _line_belongs_to_draft(db, draft: QuotationDraft, source_line_id: str) -> ExtractionBenefitLine:
    line = db.get(ExtractionBenefitLine, source_line_id)
    if not line:
        raise AppError("Source benefit line not found.", 404)
    extraction = db.scalar(
        select(ExtractionRecord).where(ExtractionRecord.uploaded_file_id == draft.uploaded_file_id)
    )
    if not extraction or extraction.id != line.extraction_record_id:
        raise AppError("Source benefit line does not belong to this quotation.", 422)
    return line



def _apply_scalar_decision(db, draft: QuotationDraft, user, operation: dict) -> str:
    field_name = str(operation.get("field") or "").strip()
    decision = str(operation.get("decision") or "")
    current_fields = dict(draft.fields or {})
    if field_name not in current_fields:
        if re.match(r"^[a-zA-Z0-9_-]+$", field_name):
            current_fields[field_name] = {"value": None, "status": "ready", "message": ""}
            draft.fields = current_fields
        else:
            raise AppError("Scalar field was not found.", 422)
    if decision not in SCALAR_DECISIONS:
        raise AppError("Scalar decision is invalid.", 422)
    fields = draft.fields
    field = deepcopy(fields[field_name] if isinstance(fields[field_name], dict) else {"value": fields[field_name]})
    original = field.get("value")
    if "detected_value" not in field or field.get("detected_value") is None:
        field["detected_value"] = original
    if decision == "edit":
        if "value" not in operation:
            raise AppError("Edited fields require a value.", 422)
        field["value"] = _normalize_edited_value(field_name, operation.get("value"))
        field["status"] = "ready"
        field["message"] = ""
    elif decision == "clear":
        field["value"] = None
        field["status"] = "ready"
        field["message"] = ""
    elif decision == "confirm":
        if "value" in operation and operation.get("value") not in {None, ""}:
            field["value"] = _normalize_edited_value(field_name, operation.get("value"))
        if field.get("value") in {None, ""}:
            field["value"] = None
            decision = "clear"
        field["status"] = "ready"
        field["message"] = ""
    else:
        field["status"] = "check_needed"
        field["message"] = "Please check this value."
    fields[field_name] = field
    decisions = draft.scalar_decisions
    decisions[field_name] = {
        "decision": decision,
        "decided_by": user.id,
        "decided_at": _utcnow().isoformat(),
    }
    # // RL-DISABLED correction_memory — disabled 2026-09-08; restore when semantic provenance and context-aware learning are implemented
    if decision == "edit" and field_name in PIN_SENSITIVE_FIELDS:
        _reconcile_catalog_pin(db, draft, changed_field=field_name)
    if field_name in TOTAL_SOURCES:
        _recompute_total(fields, decisions, user, draft=draft)
    return f"fields.{field_name}"



def _normalize_edited_value(field_name: str, raw) -> str | None:
    if raw is None:
        return None
    if field_name in MONEY_FIELDS:
        normalized = normalize_money(str(raw))
        if normalized is None:
            raise AppError("Enter a valid RM amount.", 422)
        return normalized
    if field_name in DATE_FIELDS:
        normalized = normalize_date(str(raw))
        if normalized is None:
            raise AppError("Enter a valid date, for example 25/01/2026.", 422)
        return normalized
    if field_name in {"ncd_percent", "ncd_percentage"}:
        text = re.sub(r"[^0-9.]", "", str(raw))
        if not text or text.count(".") > 1:
            raise AppError("Enter NCD as a percentage number, for example 25.", 422)
        return text
    if field_name == "valuation_type":
        return normalize_valuation_type(str(raw))
    return str(raw)



def _recompute_total(fields: dict, decisions: dict, user, draft: QuotationDraft | None = None) -> None:
    sources = (
        ("premium", "coverage_premium", "basic_premium_vehicle"),
        ("roadtax", "road_tax_amount"),
        ("service_fee", "runner_fee"),
    )
    amounts: list[Decimal] = []
    for aliases in sources:
        found_val: Decimal | None = None
        for name in aliases:
            field = fields.get(name)
            value = field.get("value") if isinstance(field, dict) else field
            if value is not None and str(value).strip():
                try:
                    found_val = Decimal(str(value).replace(",", "").strip())
                    break
                except (InvalidOperation, TypeError, ValueError):
                    pass
        if found_val is None:
            fields["total_amount"] = {
                "value": None,
                "status": "check_needed",
                "message": "Add the premium, road tax, and runner fee to compute the total.",
            }
            decisions["total_amount"] = {
                "decision": "keep_check_needed",
                "decided_by": user.id,
                "decided_at": _utcnow().isoformat(),
            }
            return
        amounts.append(found_val)
    total = sum(amounts, Decimal("0"))
    round_tot = bool((getattr(draft, "display_options", None) or {}).get("round_total", False)) if draft else False
    if round_tot:
        total = Decimal(int(total.quantize(Decimal("1"), rounding="ROUND_HALF_UP")))
    fields["total_amount"] = {"value": f"{total:.2f}", "status": "ready", "message": ""}
    decisions["total_amount"] = {
        "decision": "edit",
        "decided_by": user.id,
        "decided_at": _utcnow().isoformat(),
    }



def _draft_field_text(draft: QuotationDraft, *names: str) -> str:
    for name in names:
        raw = (draft.fields or {}).get(name)
        value = raw.get("value") if isinstance(raw, dict) else raw
        if str(value or "").strip():
            return str(value).strip()
    return ""



def _sync_detected_company(db, draft: QuotationDraft) -> None:
    session = db.scalar(select(Session).where(Session.draft_id == draft.id))
    if session is None:
        return
    session.detected_company = _draft_field_text(draft, "insurance_company") or None



def _reset_catalog_pin(draft: QuotationDraft, *, clear_company: bool = True) -> None:
    if clear_company:
        draft.company_id = None
    draft.product_id = None
    draft.tier_id = None
    draft.package_id = None
    draft.catalog_revision_id = None



def _reset_draft_benefits_for_catalog(db, draft: QuotationDraft) -> None:
    if hasattr(db, "execute"):
        db.execute(delete(DraftSourceLineDecision).where(DraftSourceLineDecision.draft_id == draft.id))
        db.execute(delete(DraftBenefitSelection).where(DraftBenefitSelection.draft_id == draft.id))
    else:
        for d in _rows_for_draft(db, DraftSourceLineDecision, draft.id):
            db.delete(d)
        for s in _rows_for_draft(db, DraftBenefitSelection, draft.id):
            db.delete(s)
    if hasattr(db, "flush"):
        db.flush()

    rec = db.scalar(select(ExtractionRecord).options(load_only(ExtractionRecord.id)).where(ExtractionRecord.uploaded_file_id == draft.uploaded_file_id))
    if rec:
        lines = list(db.scalars(select(ExtractionBenefitLine).where(ExtractionBenefitLine.extraction_record_id == rec.id)).all())
        for line in lines:
            db.add(DraftSourceLineDecision(
                id=new_id(),
                draft_id=draft.id,
                source_line_id=line.id,
                disposition="unresolved",
            ))
        db.flush()
    initialize_catalog_review(db, draft)
    auto_apply_extracted_benefits(db, draft)
    db.flush()



def _reconcile_catalog_pin(db, draft: QuotationDraft, *, changed_field: str) -> None:
    """Re-resolve the pinned catalog after a staff edit; never guess ambiguous names."""
    prev_company_id = draft.company_id
    if changed_field == "insurance_company":
        name = _draft_field_text(draft, "insurance_company")
        if not name:
            _reset_catalog_pin(draft, clear_company=True)
        else:
            companies = db.scalars(select(InsuranceCompany).where(InsuranceCompany.status == "active")).all()
            matches = [item for item in companies if str(item.name or "").strip().casefold() == name.casefold()]
            if len(matches) == 1:
                if matches[0].id != draft.company_id:
                    draft.company_id = matches[0].id
                    _reset_catalog_pin(draft, clear_company=False)
            else:
                _reset_catalog_pin(draft, clear_company=True)
    elif changed_field in {"product_name", "product"}:
        _reset_catalog_pin(draft, clear_company=False)
    elif changed_field in {"tier_name", "product_tier", "plan_name", "vehicle_type", "vehicle_category", "car_model", "coverage_type", "coverage"}:
        draft.tier_id = None
        draft.package_id = None
        draft.catalog_revision_id = None

    if prev_company_id != draft.company_id:
        _reset_draft_benefits_for_catalog(db, draft)

    _sync_detected_company(db, draft)
    initialize_catalog_review(db, draft)
    auto_apply_extracted_benefits(db, draft)



def _apply_pin_catalog(db, draft: QuotationDraft, user, operation: dict) -> str:
    company_id = str(operation.get("company_id") or "").strip() or None
    product_id = str(operation.get("product_id") or "").strip() or None
    tier_id = str(operation.get("tier_id") or "").strip() or None
    catalog_id = str(operation.get("catalog_id") or "").strip() or None
    if not company_id:
        raise AppError("Choose the insurance company to pin its catalog.", 422)
    company = db.get(InsuranceCompany, company_id)
    if company is None or company.status != "active":
        raise AppError("That insurance company is not active.", 422)

    company_changed = draft.company_id != company.id
    if company_changed:
        _reset_draft_benefits_for_catalog(db, draft)

    draft.company_id = company.id
    draft.product_id = None
    draft.tier_id = None
    draft.package_id = None
    draft.catalog_revision_id = None
    if product_id:
        product = db.get(InsuranceProduct, product_id)
        if product is None or product.company_id != company.id or product.status != "active":
            raise AppError("That product does not belong to the pinned company.", 422)
        draft.product_id = product.id
    if tier_id:
        if not draft.product_id:
            raise AppError("Select the product before the tier.", 422)
        tier = db.get(InsuranceProductTier, tier_id)
        if tier is None or tier.product_id != draft.product_id or tier.status != "active":
            raise AppError("That tier does not belong to the pinned product.", 422)
        draft.tier_id = tier.id
    if catalog_id:
        # Direct catalog pin (package-tier switch): bypass ambiguous resolution.
        catalog = db.get(BenefitCatalog, catalog_id)
        if catalog is None or catalog.company_id != company.id or catalog.status not in {"active", "published"}:
            raise AppError("That catalog does not belong to the pinned company.", 422)
        if product_id and catalog.product_id and catalog.product_id != product_id:
            raise AppError("That catalog does not belong to the pinned product.", 422)
        if catalog.product_id:
            draft.product_id = catalog.product_id
        if catalog.tier_id:
            draft.tier_id = catalog.tier_id
        revisions = [
            item for item in db.scalars(select(BenefitCatalogRevision)).all()
            if item.catalog_id == catalog.id and item.state == "published"
        ]
        if not revisions:
            raise AppError("That catalog has no published revision.", 409)
        revision = max(revisions, key=lambda item: (int(item.revision_number), str(item.id)))
        draft.catalog_revision_id = revision.id
        seed_base_benefits(db, draft, revision)
    else:
        initialize_catalog_review(db, draft)
    auto_apply_extracted_benefits(db, draft)
    draft.fields["insurance_company"] = {"value": company.name, "status": "ready", "message": ""}
    draft.scalar_decisions["insurance_company"] = {
        "decision": "confirm",
        "decided_by": user.id,
        "decided_at": _utcnow().isoformat(),
    }
    _sync_detected_company(db, draft)
    return "catalog"



def _apply_select_package_tier(db, draft: QuotationDraft, user, operation: dict) -> str:
    if not draft.catalog_revision_id:
        raise AppError("No catalog revision is pinned for this quotation.", 422)
    package_id = str(operation.get("package_id") or "").strip() or None
    if not package_id:
        raise AppError("Choose a package tier to select.", 422)
    package = db.get(BenefitPackage, package_id)
    if package is None or package.package_kind != "comprehensive" or package.status != "active":
        raise AppError("That package tier does not exist or is inactive.", 422)

    # Check if package belongs to currently pinned revision or to a published revision of a sibling catalog
    if package.catalog_revision_id != draft.catalog_revision_id:
        target_rev = db.get(BenefitCatalogRevision, package.catalog_revision_id)
        if target_rev is None or target_rev.state != "published":
            raise AppError("That package tier does not belong to a published catalog revision.", 422)
        target_cat = db.get(BenefitCatalog, target_rev.catalog_id)
        if target_cat is None or target_cat.company_id != draft.company_id:
            raise AppError("That package tier does not belong to the draft's insurer.", 422)
        # Repin to the sibling catalog revision
        draft.catalog_revision_id = target_rev.id
        if target_cat.product_id:
            draft.product_id = target_cat.product_id

    if draft.package_id == package.id:
        return "package_tier"

    draft.package_id = package.id
    for s in _rows_for_draft(db, DraftBenefitSelection, draft.id):
        if s.item_kind == "catalog":
            db.delete(s)

    revision = db.get(BenefitCatalogRevision, draft.catalog_revision_id)
    if revision:
        seed_base_benefits(db, draft, revision)
    auto_apply_extracted_benefits(db, draft)
    return "package_tier"



def _apply_reset_benefits(db, draft: QuotationDraft, user, operation: dict) -> str:
    """Reset all benefit selections back to the clean catalog defaults and auto-applied detections.

    Preserves the draft's pinned insurance company, product, package tier, and template selection.
    """
    for s in _rows_for_draft(db, DraftBenefitSelection, draft.id):
        db.delete(s)
    for d in _rows_for_draft(db, DraftSourceLineDecision, draft.id):
        db.delete(d)

    revision = pin_catalog_context(db, draft)
    if revision:
        seed_base_benefits(db, draft, revision)
    elif draft.catalog_revision_id:
        rev = db.get(BenefitCatalogRevision, draft.catalog_revision_id)
        if rev:
            seed_base_benefits(db, draft, rev)

    auto_apply_extracted_benefits(db, draft)
    return "benefits"



def _safe_concept_id(db, concept_id: str | None) -> str | None:
    if not concept_id:
        return None
    try:
        found = db.get(BenefitConcept, concept_id)
        if found:
            return str(found.id)
        if hasattr(db, "bind") and db.bind is not None:
            return None
    except Exception:
        pass
    return concept_id



def _safe_source_line_id(db, source_line_id: str | None) -> str | None:
    if not source_line_id:
        return None
    try:
        found = db.get(ExtractionBenefitLine, source_line_id)
        if found:
            return str(found.id)
        if hasattr(db, "bind") and db.bind is not None:
            return None
    except Exception:
        pass
    return source_line_id



def _safe_package_plan_id(db, plan_id: str | None) -> str | None:
    if not plan_id:
        return None
    try:
        found = db.get(BenefitPackagePlan, plan_id)
        if found:
            return str(found.id)
        if hasattr(db, "bind") and db.bind is not None:
            return None
    except Exception:
        pass
    return plan_id



def _apply_custom_benefit(db, draft: QuotationDraft, user, operation: dict) -> tuple[str, DraftBenefitSelection]:
    key = _validate_selection_key(operation.get("selection_key"))
    label = str(operation.get("label") or "").strip()
    if not label or len(label) > 255:
        raise AppError("Custom benefits require a label of at most 255 characters.", 422)
    try:
        raw_typed = operation.get("typed_value")
        typed_value = BenefitValue.model_validate(raw_typed).model_dump(mode="json", exclude_none=True) if raw_typed else None
        state = ReviewedBenefitState(str(operation.get("state") or "current")).value
        cost_status = CostStatus(str(operation.get("cost_status") or "unknown")).value
    except (ValidationError, ValueError) as exc:
        raise AppError("Custom benefit state, cost, or typed value is invalid.", 422) from exc
    price = operation.get("price")
    if price is not None:
        try:
            price = MoneyAmount.model_validate(price).model_dump(mode="json", exclude_none=True)
        except ValidationError as exc:
            raise AppError("Custom benefit price is invalid.", 422) from exc
    if state not in {ReviewedBenefitState.CURRENT.value, ReviewedBenefitState.AVAILABLE_ADDON.value}:
        raise AppError("A new custom benefit must be current or an available add-on.", 422)

    source_line_id = _safe_source_line_id(db, operation.get("source_line_id"))
    concept_id = operation.get("concept_id")
    if not concept_id and operation.get("concept_key"):
        matched_concept = db.scalar(select(BenefitConcept).where(BenefitConcept.concept_key == operation.get("concept_key")))
        if matched_concept:
            concept_id = matched_concept.id
    if not concept_id:
        matched_concept = db.scalar(select(BenefitConcept).where(func.lower(BenefitConcept.label) == label.lower()))
        if matched_concept:
            concept_id = matched_concept.id
    concept_id = _safe_concept_id(db, concept_id)

    existing = _selection_by_key(db, draft.id, key)
    if existing:
        existing.label_override = label
        existing.state = state
        existing.cost_status = cost_status
        existing.typed_value_override = typed_value
        existing.price = price
        existing.selected_by = user.id
        if concept_id:
            existing.concept_id = concept_id
        if source_line_id:
            existing.source_line_id = source_line_id
        return f"benefits.{existing.id}", existing

    selection = DraftBenefitSelection(
        id=new_id(),
        draft_id=draft.id,
        selection_key=key,
        source_line_id=source_line_id if source_line_id else None,
        concept_id=concept_id if concept_id else None,
        item_kind="custom",
        state=state,
        cost_status=cost_status,
        label_override=label,
        typed_value_override=typed_value,
        evidence_snapshot={},
        sort_order=int(operation.get("sort_order") or 0),
        selected_by=user.id,
        price=price,
    )
    db.add(selection)
    return f"benefits.{selection.id}", selection



def _draft_selections_with_pending(db, draft_id: str) -> list[DraftBenefitSelection]:
    rows = _rows_for_draft(db, DraftBenefitSelection, draft_id)
    for item in getattr(db, "added", []):
        if isinstance(item, DraftBenefitSelection) and item.draft_id == draft_id and item not in rows:
            rows.append(item)
    return rows



def _resolve_selection(db, draft: QuotationDraft, selection_id: str) -> DraftBenefitSelection | None:
    """Resolve a selection by UUID pk or by selection_key (handles pending:catalog:* IDs)."""
    if _UUID_RE.match(selection_id):
        sel = db.get(DraftBenefitSelection, selection_id)
        if sel and sel.draft_id == draft.id:
            return sel
        return None
    # Non-UUID: strip 'pending:' prefix and look up by id or selection_key
    lookup_key = selection_id.removeprefix("pending:")
    for item in _draft_selections_with_pending(db, draft.id):
        if item.id == selection_id or item.selection_key == selection_id or item.selection_key == lookup_key:
            return item
        if lookup_key.startswith("custom:") and item.id == lookup_key.removeprefix("custom:"):
            return item
        if item.selection_key in (lookup_key, f"addon:{lookup_key}", f"default:{lookup_key}"):
            return item
        if lookup_key.startswith("addon:") or lookup_key.startswith("default:") or lookup_key.startswith("concept:"):
            if item.selection_key == lookup_key:
                return item
    return None



def _apply_select_catalog_offering(db, draft: QuotationDraft, user, operation: dict) -> str:
    offering_id = str(operation.get("offering_id") or "")
    offering = db.get(CatalogOffering, offering_id)
    if not offering or offering.catalog_revision_id != draft.catalog_revision_id or offering.status not in {"active", "compatibility"}:
        raise AppError("Choose an available offering from this quotation's pinned catalog.", 422)
    selections = _draft_selections_with_pending(db, draft.id)

    desired_state = ReviewedBenefitState.CURRENT.value
    if "state" in operation and operation.get("state"):
        try:
            desired_state = ReviewedBenefitState(str(operation.get("state"))).value
        except ValueError as exc:
            raise AppError("Quotation benefit state is invalid.", 422) from exc

    current = [item for item in selections if item.concept_id == offering.concept_id and item.state == ReviewedBenefitState.CURRENT.value]
    if len(current) > 1:
        raise AppError("This benefit concept has conflicting current selections.", 409)

    if desired_state == ReviewedBenefitState.CURRENT.value:
        if current and current[0].catalog_offering_id != offering.id:
            valid_edge = any(
                relation.catalog_revision_id == draft.catalog_revision_id
                and relation.relation_kind == "replaces"
                and relation.from_offering_id == current[0].catalog_offering_id
                and relation.to_offering_id == offering.id
                for relation in db.scalars(select(BenefitRelation)).all()
            )
            same_concept_addon = (
                offering.concept_id
                and offering.concept_id == current[0].concept_id
                and (getattr(offering, "role", None) in {"addon_option", "bundle_component"} or offering.offering_kind in {"optional", "base"})
            )
            if not valid_edge and not same_concept_addon:
                raise AppError("That offering is not an explicit upgrade for the current benefit.", 422)
        elif not current and offering.offering_kind not in {"optional", "base"} and getattr(offering, "role", None) not in {"addon_option", "bundle_component", "included"}:
            raise AppError("An upgrade requires its explicit current benefit.", 422)

    try:
        cost_status = CostStatus(str(operation.get("cost_status") or ("included" if desired_state == "current" else "paid"))).value
    except ValueError as exc:
        raise AppError("Benefit cost must be included, paid, FOC, or unknown.", 422) from exc
    typed_override = None
    if "typed_value" in operation and operation.get("typed_value") is not None:
        try:
            typed_override = BenefitValue.model_validate(operation["typed_value"]).model_dump(mode="json", exclude_none=True)
        except ValidationError as exc:
            raise AppError("The quotation-specific benefit value is invalid.", 422) from exc

    price = operation.get("price")
    if "price" in operation and price is None:
        price = None
    elif price is None and offering.optional_price:
        price = deepcopy(offering.optional_price)
    elif price is not None:
        try:
            price = MoneyAmount.model_validate(price).model_dump(mode="json", exclude_none=True)
        except Exception:
            price = None

    valid_concept_id = _safe_concept_id(db, offering.concept_id)

    selected = next((item for item in selections if item.catalog_offering_id == offering.id), None)
    if selected is None:
        selected = DraftBenefitSelection(
            id=new_id(), draft_id=draft.id, selection_key=f"catalog:{offering.offering_key}"[:160],
            catalog_offering_id=offering.id, concept_id=valid_concept_id, item_kind="catalog",
            label_override=offering.label_override, evidence_snapshot={"catalog_revision_id": draft.catalog_revision_id},
            sort_order=int(offering.sort_order or 0),
        )
        db.add(selected)
    selected.state = desired_state
    selected.cost_status = cost_status
    selected.typed_value_override = typed_override
    selected.price = price
    if "label" in operation or "label_override" in operation:
        raw_lbl = operation.get("label") if "label" in operation else operation.get("label_override")
        if raw_lbl:
            selected.label_override = str(raw_lbl).strip()
    if "description" in operation or "description_override" in operation:
        raw_desc = operation.get("description") if "description" in operation else operation.get("description_override")
        if raw_desc:
            clean_desc = str(raw_desc).strip()
            curr_typed = dict(selected.typed_value_override or {})
            curr_typed["description"] = clean_desc
            if "type" not in curr_typed:
                curr_typed["type"] = "custom"
            selected.typed_value_override = curr_typed
    selected.selected_by = user.id
    if desired_state == ReviewedBenefitState.CURRENT.value and current and current[0].id != selected.id:
        current[0].state = ReviewedBenefitState.SUPERSEDED.value
        current[0].superseded_by_id = selected.id
    elif desired_state == ReviewedBenefitState.REMOVED.value and current and current[0].id != selected.id:
        current[0].state = ReviewedBenefitState.REMOVED.value
    return f"benefits.{selected.id}"



def _apply_benefit_update(db, draft: QuotationDraft, user, operation: dict) -> str:
    selection_id = str(operation.get("selection_id") or "")
    selection = _resolve_selection(db, draft, selection_id)
    if not selection:
        if str(operation.get("state")) == ReviewedBenefitState.REMOVED.value and (
            selection_id.startswith("pending:") or selection_id.startswith("custom:") or selection_id.startswith("addon:") or selection_id.startswith("default:")
        ):
            return f"benefits.{selection_id}"
        raise AppError("Quotation benefit not found.", 404)
    if "state" in operation:
        try:
            state = ReviewedBenefitState(str(operation.get("state"))).value
        except ValueError as exc:
            raise AppError("Quotation benefit state is invalid.", 422) from exc
        if state == ReviewedBenefitState.CURRENT.value and selection.concept_id:
            conflicts = [
                item for item in _draft_selections_with_pending(db, draft.id)
                if item.id != selection.id and item.concept_id and item.concept_id == selection.concept_id and item.state == ReviewedBenefitState.CURRENT.value
            ]
            for conflict in conflicts:
                conflict.state = ReviewedBenefitState.SUPERSEDED.value
                conflict.superseded_by_id = selection.id
        selection.state = state
        if state != ReviewedBenefitState.SUPERSEDED.value:
            selection.superseded_by_id = None
    if "cost_status" in operation:
        try:
            selection.cost_status = CostStatus(str(operation.get("cost_status"))).value
        except ValueError as exc:
            raise AppError("Benefit cost must be included, paid, FOC, or unknown.", 422) from exc
    if "price" in operation:
        raw_price = operation.get("price")
        if raw_price is None:
            selection.price = None
        else:
            try:
                selection.price = MoneyAmount.model_validate(raw_price).model_dump(mode="json", exclude_none=True)
            except Exception:
                selection.price = raw_price if isinstance(raw_price, dict) else None
    if "label" in operation or "label_override" in operation:
        raw_label = operation.get("label") if "label" in operation else operation.get("label_override")
        clean_lbl = str(raw_label or "").strip()
        selection.label_override = clean_lbl or None
    if "description" in operation or "description_override" in operation:
        raw_desc = operation.get("description") if "description" in operation else operation.get("description_override")
        clean_desc = str(raw_desc or "").strip()
        curr_typed = dict(selection.typed_value_override or {})
        if clean_desc:
            curr_typed["description"] = clean_desc
            if "type" not in curr_typed:
                curr_typed["type"] = "custom"
        else:
            curr_typed.pop("description", None)
        selection.typed_value_override = curr_typed or None
    if "typed_value" in operation or "typed_value_override" in operation:
        raw = operation.get("typed_value") if "typed_value" in operation else operation.get("typed_value_override")
        if raw is None:
            if selection.typed_value_override and "description" in selection.typed_value_override:
                selection.typed_value_override = {"type": "custom", "description": selection.typed_value_override["description"]}
            else:
                selection.typed_value_override = None
        else:
            try:
                validated = BenefitValue.model_validate(raw).model_dump(mode="json", exclude_none=True)
                if selection.typed_value_override and "description" in selection.typed_value_override and "description" not in validated:
                    validated["description"] = selection.typed_value_override["description"]
                selection.typed_value_override = validated
            except ValidationError as exc:
                raise AppError("The quotation-specific benefit value is invalid.", 422) from exc
    selection.selected_by = user.id
    return f"benefits.{selection.id}"



def _apply_revert_benefit(db, draft: QuotationDraft, user, operation: dict) -> str:
    selection_id = str(operation.get("selection_id") or "")
    selection = _resolve_selection(db, draft, selection_id)
    if not selection:
        raise AppError("Quotation benefit not found.", 404)
    predecessors = [
        item for item in _draft_selections_with_pending(db, draft.id)
        if item.superseded_by_id == selection.id and item.state == ReviewedBenefitState.SUPERSEDED.value
    ]
    if len(predecessors) > 1:
        raise AppError("This upgrade history is ambiguous and must be reviewed manually.", 409)
    selection.state = ReviewedBenefitState.REMOVED.value
    selection.superseded_by_id = None
    selection.selected_by = user.id
    if predecessors:
        predecessors[0].state = ReviewedBenefitState.CURRENT.value
        predecessors[0].superseded_by_id = None
        predecessors[0].selected_by = user.id
    return f"benefits.{selection.id}"



def _drop_plan_selection(db, selections: list[DraftBenefitSelection], selection: DraftBenefitSelection, user) -> None:
    """Remove one plan member and restore its superseded default, if any.

    Selections the plan merely adopted (staff/AI custom values) are untagged
    and stay current; only selections created by the plan are removed.
    """
    source = str((selection.evidence_snapshot or {}).get("source") or "")
    if source != "package_plan":
        selection.package_plan_id = None
        return
    predecessors = [
        item for item in selections
        if item.superseded_by_id == selection.id and item.state == ReviewedBenefitState.SUPERSEDED.value
    ]
    if len(predecessors) > 1:
        raise AppError("This upgrade history is ambiguous and must be reviewed manually.", 409)
    selection.state = ReviewedBenefitState.REMOVED.value
    selection.superseded_by_id = None
    selection.package_plan_id = None
    selection.selected_by = user.id
    if predecessors:
        predecessors[0].state = ReviewedBenefitState.CURRENT.value
        predecessors[0].superseded_by_id = None
        predecessors[0].package_plan_id = None
        predecessors[0].selected_by = user.id



def _apply_select_package_plan(db, draft: QuotationDraft, user, operation: dict) -> str:
    """Atomically add (or switch) an add-on bundle plan.

    Plan members supersede untouched catalog defaults in place; a staff- or
    AI-customized value is preserved and only adopted into the group border.
    A previous plan of the same bundle is dropped first so ladder upgrades
    never create duplicate cards.
    """
    if not draft.catalog_revision_id:
        raise AppError("Pin the insurance catalog before adding a package plan.", 422)
    plan_id = str(operation.get("plan_id") or "")
    package_id = str(operation.get("package_id") or "")
    plan = db.get(BenefitPackagePlan, plan_id)
    if plan is None or plan.status != "active":
        raise AppError("Package plan not found.", 404)
    if package_id and str(plan.package_id) != package_id:
        raise AppError("That plan does not belong to the chosen package.", 422)
    package = db.get(BenefitPackage, plan.package_id)
    if package is None or package.catalog_revision_id != draft.catalog_revision_id or package.package_kind != "addon_bundle":
        raise AppError("Choose an add-on bundle plan from this quotation's pinned catalog.", 422)
    try:
        cost_status = CostStatus(str(operation.get("cost_status") or "paid")).value
    except ValueError as exc:
        raise AppError("Benefit cost must be included, paid, FOC, or unknown.", 422) from exc
    items = list(
        db.scalars(
            select(BenefitPackagePlanItem)
            .where(BenefitPackagePlanItem.plan_id == plan.id)
            .order_by(BenefitPackagePlanItem.sort_order)
        ).all()
    )
    selections = _draft_selections_with_pending(db, draft.id)

    # 1. Drop members of other plans of the same bundle (clean ladder switch).
    sibling_plan_ids = {
        str(item.id)
        for item in db.scalars(
            select(BenefitPackagePlan).where(BenefitPackagePlan.package_id == package.id)
        ).all()
    } - {str(plan.id)}
    for sel in [s for s in selections if s.package_plan_id and s.package_plan_id in sibling_plan_ids]:
        _drop_plan_selection(db, selections, sel, user)
    selections = _draft_selections_with_pending(db, draft.id)

    # 2. Apply each plan item against the single-current-per-concept rule.
    offerings_by_id = {
        str(item.id): item
        for item in db.scalars(
            select(CatalogOffering).where(CatalogOffering.catalog_revision_id == draft.catalog_revision_id)
        ).all()
    }
    for item in items:
        offering = offerings_by_id.get(str(item.offering_id))
        if offering is None or offering.status not in {"active", "compatibility"}:
            raise AppError("A plan item offering is unavailable from the pinned catalog revision.", 422)
        current = [
            s for s in selections
            if s.concept_id == offering.concept_id and s.state == ReviewedBenefitState.CURRENT.value
        ]
        if len(current) > 1:
            raise AppError("This benefit concept has conflicting current selections.", 409)
        if current:
            sel = current[0]
            if sel.package_plan_id and sel.package_plan_id == plan.id:
                continue
            if sel.typed_value_override is not None:
                # Custom value already reviewed: keep it, adopt the card into the group.
                sel.package_plan_id = plan.id
                continue
            selection_id = new_id()
            sel.state = ReviewedBenefitState.SUPERSEDED.value
            sel.superseded_by_id = selection_id
            replacement = DraftBenefitSelection(
                id=selection_id,
                draft_id=draft.id,
                selection_key=f"plan:{plan.plan_key}:{offering.offering_key}"[:160],
                catalog_offering_id=offering.id,
                concept_id=offering.concept_id,
                item_kind="catalog",
                state=ReviewedBenefitState.CURRENT.value,
                cost_status=cost_status,
                label_override=offering.label_override,
                typed_value_override=deepcopy(item.typed_value_override),
                evidence_snapshot={
                    "package_id": package.id,
                    "plan_id": plan.id,
                    "plan_key": plan.plan_key,
                    "source": "package_plan",
                },
                sort_order=int(item.sort_order or 0),
                package_plan_id=plan.id,
                selected_by=user.id,
            )
            db.add(replacement)
            selections.append(replacement)
        else:
            member = DraftBenefitSelection(
                id=new_id(),
                draft_id=draft.id,
                selection_key=f"plan:{plan.plan_key}:{offering.offering_key}"[:160],
                catalog_offering_id=offering.id,
                concept_id=offering.concept_id,
                item_kind="catalog",
                state=ReviewedBenefitState.CURRENT.value,
                cost_status=cost_status,
                label_override=offering.label_override,
                typed_value_override=deepcopy(item.typed_value_override),
                evidence_snapshot={
                    "package_id": package.id,
                    "plan_id": plan.id,
                    "plan_key": plan.plan_key,
                    "source": "package_plan",
                },
                sort_order=int(item.sort_order or 0),
                package_plan_id=plan.id,
                selected_by=user.id,
            )
            db.add(member)
            selections.append(member)
    return f"benefits.plan.{plan.id}"



def _apply_remove_package_plan(db, draft: QuotationDraft, user, operation: dict) -> str:
    plan_id = str(operation.get("plan_id") or "")
    if not plan_id:
        raise AppError("Choose the plan to remove.", 422)
    plan = db.get(BenefitPackagePlan, plan_id)
    if plan is None:
        raise AppError("Package plan not found.", 404)
    selections = _draft_selections_with_pending(db, draft.id)
    for sel in [s for s in selections if s.package_plan_id and s.package_plan_id == plan.id]:
        _drop_plan_selection(db, selections, sel, user)
    return f"benefits.plan.{plan.id}"



def _apply_source_disposition(db, draft: QuotationDraft, user, operation: dict) -> str:
    source_line_id = str(operation.get("source_line_id") or "")
    _line_belongs_to_draft(db, draft, source_line_id)
    try:
        disposition = SourceLineDisposition(str(operation.get("disposition") or "")).value
    except ValueError as exc:
        raise AppError("Source-line disposition is invalid.", 422) from exc
    decision = _decision_by_line(db, draft.id, source_line_id)
    if decision is None:
        if not db.get(ExtractionBenefitLine, source_line_id):
            return f"source_lines.{source_line_id}"
        decision = DraftSourceLineDecision(
            id=new_id(), draft_id=draft.id, source_line_id=source_line_id, disposition="unresolved"
        )
        db.add(decision)
    selection = None
    if disposition in {SourceLineDisposition.MAPPED.value, SourceLineDisposition.CUSTOM.value}:
        key = _validate_selection_key(operation.get("selection_key"))
        selection = _selection_by_key(db, draft.id, key)
        if selection is None:
            # A prior operation in the same patch may not yet be returned by a
            # fake adapter or an autoflush-disabled session; inspect pending rows.
            selection = next(
                (item for item in getattr(db, "added", []) if isinstance(item, DraftBenefitSelection) and item.draft_id == draft.id and item.selection_key == key),
                None,
            )
        if selection is None:
            raise AppError("Mapped/custom dispositions require a quotation benefit.", 422)
    decision.disposition = disposition
    decision.selection_id = selection.id if selection else None
    decision.decided_by = user.id
    decision.decided_at = _utcnow()
    return f"source_lines.{source_line_id}"



def _apply_layout_override(db, draft: QuotationDraft, operation: dict) -> str:
    revision_id = str(operation.get("template_revision_id") or "")
    template_id = str(operation.get("template_id") or "")
    base_hash = str(operation.get("base_hash") or "")
    revision = db.get(TemplateRevision, revision_id)
    if (
        not revision
        or draft.template_revision_id != revision.id
        or revision.template_id != template_id
        or revision.config_hash != base_hash
    ):
        raise AppError("The layout does not match the selected template revision.", 409)
    layout = operation.get("layout")
    if not isinstance(layout, dict):
        raise AppError("Layout override must be an object.", 422)
    draft.layout_override = deepcopy(layout)
    draft.layout_override_template_id = template_id
    draft.layout_override_template_revision_id = revision_id
    draft.layout_override_base_hash = base_hash
    return "layout_override"



def _apply_template_selection(db, draft: QuotationDraft, operation: dict) -> str:
    if operation.get("confirmed") is not True:
        raise AppError("Confirm the template impact before applying this change.", 422)
    revision_id = str(operation.get("template_revision_id") or "")
    revision = db.get(TemplateRevision, revision_id)
    if revision is None or revision.state != "published":
        raise AppError("Choose a published template revision.", 422)
    if draft.template_revision_id != revision.id:
        draft.template_revision_id = revision.id
        draft.layout_override = None
        draft.layout_override_template_id = None
        draft.layout_override_template_revision_id = None
        draft.layout_override_base_hash = None
    return "template_revision_id"



def apply_workspace_patch(
    db,
    user,
    draft_id: str,
    *,
    base_revision: int,
    operations: list[dict],
) -> dict:
    if not operations or len(operations) > 200:
        raise AppError("Submit between 1 and 200 dirty workspace operations.", 422)
    draft = _locked_draft(db, user, draft_id)
    if draft.revision != base_revision:
        raise AppError("This quotation changed elsewhere. Reload and compare before saving.", 409)

    # Copy mutable JSON before applying so a rejected operation cannot mutate
    # SQLAlchemy's live values in memory.
    draft.fields = deepcopy(draft.fields or {})
    draft.scalar_decisions = deepcopy(draft.scalar_decisions or {})
    changed_paths: list[str] = []
    operation_names: list[str] = []
    try:
        for operation in operations:
            if not isinstance(operation, dict):
                raise AppError("Workspace operations must be objects.", 422)
            operation_name = str(operation.get("op") or "")
            operation_names.append(operation_name)
            if operation_name == "scalar_decision":
                changed_paths.append(_apply_scalar_decision(db, draft, user, operation))
            elif operation_name == "create_custom_benefit":
                path, _selection = _apply_custom_benefit(db, draft, user, operation)
                changed_paths.append(path)
            elif operation_name == "update_display_options":
                options = operation.get("options")
                if isinstance(options, dict):
                    draft.display_options = {**(draft.display_options or {}), **options}
                    changed_paths.append("display_options")
                    if "round_total" in options:
                        _recompute_total(draft.fields or {}, draft.scalar_decisions or {}, user, draft=draft)
                        changed_paths.append("fields.total_amount")
            elif operation_name == "source_disposition":
                changed_paths.append(_apply_source_disposition(db, draft, user, operation))
            elif operation_name == "select_catalog_offering":
                changed_paths.append(_apply_select_catalog_offering(db, draft, user, operation))
            elif operation_name == "select_package_plan":
                changed_paths.append(_apply_select_package_plan(db, draft, user, operation))
            elif operation_name == "remove_package_plan":
                changed_paths.append(_apply_remove_package_plan(db, draft, user, operation))
            elif operation_name == "benefit_update":
                changed_paths.append(_apply_benefit_update(db, draft, user, operation))
            elif operation_name == "revert_benefit":
                changed_paths.append(_apply_revert_benefit(db, draft, user, operation))
            elif operation_name == "layout_override":
                changed_paths.append(_apply_layout_override(db, draft, operation))
            elif operation_name == "pin_catalog":
                changed_paths.append(_apply_pin_catalog(db, draft, user, operation))
            elif operation_name == "select_package_tier":
                changed_paths.append(_apply_select_package_tier(db, draft, user, operation))
            elif operation_name == "reset_benefits":
                changed_paths.append(_apply_reset_benefits(db, draft, user, operation))
            elif operation_name == "template_selection":
                changed_paths.append(_apply_template_selection(db, draft, operation))
            else:
                raise AppError(f"Unsupported workspace operation: {operation_name or 'missing'}.", 422)

        flag_modified(draft, "fields")
        flag_modified(draft, "scalar_decisions")
        if "layout_override" in changed_paths or "template_selection" in operation_names:
            flag_modified(draft, "layout_override")
        draft.revision += 1
        draft.reviewed_at = _utcnow()
        draft.reviewed_by = user.id
        decisions = _rows_for_draft(db, DraftSourceLineDecision, draft.id)
        selections = _rows_for_draft(db, DraftBenefitSelection, draft.id)
        # Include pending rows for adapters without autoflush/query visibility.
        for item in getattr(db, "added", []):
            if isinstance(item, DraftSourceLineDecision) and item.draft_id == draft.id and item not in decisions:
                decisions.append(item)
            if isinstance(item, DraftBenefitSelection) and item.draft_id == draft.id and item not in selections:
                selections.append(item)
        blockers = generation_blockers(
            draft, decisions, selections, template_revision=_template_for_draft(db, draft)
        )
        draft.status = RecordStatus.READY.value if not blockers else RecordStatus.CHECK_NEEDED.value
        uploaded = db.get(UploadedFile, draft.uploaded_file_id)
        if uploaded:
            uploaded.status = draft.status
        db.add(AuditEvent(
            actor_id=user.id,
            action="workspace.patch",
            entity_type="quotation_draft",
            entity_id=draft.id,
            details={
                "base_revision": base_revision,
                "new_revision": draft.revision,
                "operations": operation_names,
                "changed_paths": changed_paths,
            },
        ))
        session = db.scalar(select(Session).where(Session.draft_id == draft.id))
        if session:
            session.last_edited_by_id = user.id
            session.last_edited_at = _utcnow()
            if not getattr(session, "is_test", False):
                from app.services.quotation_activity_service import log_quotation_activity
                modified_topics = []
                for path in changed_paths:
                    if path.startswith("fields."):
                        field_name = path.replace("fields.", "")
                        if field_name in ("vehicle_no", "car_brand", "car_model"):
                            modified_topics.append("vehicle details")
                        elif field_name in ("customer_name", "ic_or_brn"):
                            modified_topics.append("client info")
                        elif field_name in ("total_amount", "premium", "gross_premium", "ncd_percent", "roadtax"):
                            modified_topics.append("pricing/premium")
                        elif field_name in ("insurance_company", "coverage_type"):
                            modified_topics.append("insurer/coverage")
                        else:
                            modified_topics.append("policy fields")
                    elif path.startswith("benefits"):
                        modified_topics.append("benefits & add-ons")
                    elif "options" in path:
                        modified_topics.append("display options")
                    elif "layout" in path or "template" in path:
                        modified_topics.append("template layout")

                unique_topics = list(dict.fromkeys(modified_topics))
                if unique_topics:
                    save_desc = f"Saved changes: {', '.join(unique_topics[:3])}"
                else:
                    save_desc = "Saved quotation draft updates"

                log_quotation_activity(
                    db=db,
                    session_id=session.id,
                    action_type="draft_saved",
                    user_id=user.id,
                    sent_to_client=False,
                    summary=save_desc,
                    status=session.quotation_status or "pending",
                )
        db.commit()
        db.refresh(draft)
    except AppError:
        db.rollback()
        raise
    session_ref = session.quotation_ref if session else None
    return {
        "draft_id": draft.id,
        "revision": draft.revision,
        "status": draft.status,
        "fields": _field_summary(draft, session_ref),
        "changed_paths": changed_paths,
        "generation_blockers": blockers,
    }

