"""Canonical v7 quotation workspace snapshots and optimistic mutations."""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm.attributes import flag_modified

from app.core.errors import AppError
from app.domain.benefits import (
    BenefitValue,
    CostStatus,
    ReviewedBenefitState,
    SourceLineDisposition,
)
from app.models.enums import RecordStatus, Role
from app.models.tables import (
    AuditEvent,
    BenefitConcept,
    BenefitFacet,
    BenefitRelation,
    CatalogOffering,
    CorrectionMemory,
    DraftBenefitSelection,
    DraftSourceLineDecision,
    ExtractionBenefitLine,
    ExtractionRecord,
    GeneratedPdfVersion,
    InsuranceCompany,
    InsuranceProduct,
    InsuranceProductTier,
    QuotationDraft,
    Session,
    TemplateRevision,
    UploadedFile,
    new_id,
)
from app.rendering.render_context import RenderContextError, format_benefit_value, resolve_benefit_cards
from app.services.catalog_review_service import auto_apply_extracted_benefits, initialize_catalog_review
from app.extraction.validators import normalize_date, normalize_money


SCALAR_DECISIONS = frozenset({"confirm", "edit", "clear", "keep_check_needed"})
SELECTION_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,159}$")
BUSINESS_ROLES = frozenset({Role.STAFF.value, Role.ADMIN.value, Role.SUPER_ADMIN.value})
PIN_SENSITIVE_FIELDS = frozenset({"insurance_company", "product_name", "product", "tier_name", "product_tier", "plan_name"})
MONEY_FIELDS = frozenset({
    "coverage_amount", "market_value", "agreed_value", "excess_amount", "basic_premium_vehicle",
    "premium", "ncd_amount", "loading_amount", "all_riders_amount", "optional_cover_amount",
    "service_tax", "stamp_duty", "gross_premium", "roadtax", "service_fee", "total_amount",
})
DATE_FIELDS = frozenset({"issue_date", "valid_until", "cover_start_date", "cover_end_date"})
TOTAL_SOURCES = frozenset({"premium", "roadtax", "service_fee"})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def workspace_capabilities(user) -> dict[str, bool]:
    business = user.role in BUSINESS_ROLES
    security_admin = user.role in {Role.ADMIN.value, Role.SUPER_ADMIN.value}
    primary = user.role == Role.SUPER_ADMIN.value
    return {
        "can_edit_fields": business,
        "can_edit_selections": business,
        "can_edit_layout": business,
        "can_generate": business,
        "can_manage_catalogs": business,
        "can_manage_templates": business,
        "can_manage_assets": business,
        "can_view_all_records": business,
        "can_manage_users": security_admin,
        "can_manage_security": security_admin,
        "can_view_audit": security_admin,
        "can_manage_ip_controls": security_admin,
        "can_transfer_primary_admin": primary,
    }


def _require_business_user(user) -> None:
    if user.role not in BUSINESS_ROLES:
        raise AppError("You do not have permission to use quotation workspaces.", 403)


def _session_and_draft(db, user, session_id: str) -> tuple[Session, QuotationDraft]:
    _require_business_user(user)
    session = db.get(Session, session_id)
    if not session:
        raise AppError("Session not found.", 404)
    draft = db.get(QuotationDraft, session.draft_id)
    if not draft or draft.deleted_at:
        raise AppError("Draft not found.", 404)
    return session, draft


def _rows_for_draft(db, model, draft_id: str) -> list:
    rows = list(db.scalars(select(model).where(model.draft_id == draft_id)).all())
    # The explicit filter is redundant in SQL but keeps pure fake/test adapters
    # from accidentally returning another draft's rows.
    return [row for row in rows if row.draft_id == draft_id]


def _template_for_draft(db, draft: QuotationDraft) -> TemplateRevision | None:
    if draft.template_revision_id:
        rev = db.get(TemplateRevision, draft.template_revision_id)
        if rev:
            return rev
    return db.scalars(
        select(TemplateRevision)
        .where(TemplateRevision.state.in_(["published", "compatibility"]))
        .order_by(TemplateRevision.revision_number.desc())
    ).first()


def generation_blockers(
    draft: QuotationDraft,
    decisions: list[DraftSourceLineDecision],
    selections: list[DraftBenefitSelection],
    *,
    template_revision: TemplateRevision | None,
) -> list[dict]:
    blockers: list[dict] = []
    scalar_decisions = draft.scalar_decisions or {}
    for field_name, field in (draft.fields or {}).items():
        if not isinstance(field, dict):
            continue
        explicit = (scalar_decisions.get(field_name) or {}).get("decision")
        if explicit not in SCALAR_DECISIONS:
            blockers.append({
                "code": "scalar_check_needed",
                "path": f"fields.{field_name}",
                "message": f"Confirm or edit {field_name.replace('_', ' ')}.",
            })

    for decision in decisions:
        if decision.disposition == SourceLineDisposition.UNRESOLVED.value:
            blockers.append({
                "code": "unresolved_source_line",
                "path": f"source_lines.{decision.source_line_id}",
                "message": "Resolve this extracted benefit line.",
            })

    rendered_states = {ReviewedBenefitState.CURRENT.value, ReviewedBenefitState.AVAILABLE_ADDON.value}
    for selection in selections:
        if selection.state == ReviewedBenefitState.UNRESOLVED.value:
            blockers.append({
                "code": "unresolved_benefit",
                "path": f"benefits.{selection.id}",
                "message": "Resolve this quotation benefit.",
            })
            continue
        if selection.state not in rendered_states:
            continue
        if selection.cost_status == CostStatus.UNKNOWN.value:
            blockers.append({
                "code": "unknown_benefit_cost",
                "path": f"benefits.{selection.id}.cost_status",
                "message": "Set this benefit as included, paid, or FOC.",
            })
        value = selection.typed_value_override
        if selection.item_kind == "custom" and value is None:
            blockers.append({
                "code": "missing_benefit_value",
                "path": f"benefits.{selection.id}.typed_value",
                "message": "Enter a valid quotation-specific value.",
            })
        elif value is not None:
            try:
                BenefitValue.model_validate(value)
            except ValidationError:
                blockers.append({
                    "code": "invalid_benefit_value",
                    "path": f"benefits.{selection.id}.typed_value",
                    "message": "Correct the benefit value before generation.",
                })

    if not draft.catalog_revision_id:
        blockers.append({
            "code": "missing_catalog",
            "path": "catalog_revision_id",
            "message": "Choose a published catalog version.",
        })

    if template_revision is None or template_revision.state not in {"published", "compatibility"}:
        blockers.append({
            "code": "missing_template",
            "path": "template_revision_id",
            "message": "Choose a published master template.",
        })
    elif draft.layout_override is not None and (
        draft.layout_override_template_id != template_revision.template_id
        or draft.layout_override_template_revision_id != template_revision.id
        or draft.layout_override_base_hash != template_revision.config_hash
    ):
        blockers.append({
            "code": "stale_layout_override",
            "path": "layout_override",
            "message": "Reset or rebase the session layout for the selected template revision.",
        })
    return blockers


def _catalog_overview(db, draft: QuotationDraft) -> dict:
    if not draft.catalog_revision_id:
        return {"defaults": [], "addons": []}
    offerings = [
        item for item in db.scalars(select(CatalogOffering)).all()
        if item.catalog_revision_id == draft.catalog_revision_id
    ]
    concept_ids = {item.concept_id for item in offerings}
    concepts = {item.id: item for item in db.scalars(select(BenefitConcept)).all() if item.id in concept_ids}
    overview = {"defaults": [], "addons": []}
    for offering in sorted(offerings, key=lambda item: (int(item.sort_order or 0), item.offering_key)):
        concept = concepts.get(offering.concept_id)
        label = offering.label_override or (concept.label if concept else offering.offering_key)
        try:
            value = format_benefit_value(offering.typed_value)
        except RenderContextError:
            value = ""
        entry = {"offering_id": offering.id, "label": label, "value": value}
        if offering.offering_kind == "base":
            overview["defaults"].append(entry)
        elif offering.offering_kind in {"upgrade", "optional", "package_component"}:
            overview["addons"].append(entry)
    return overview


def _field_summary(draft: QuotationDraft) -> dict[str, dict]:
    output: dict[str, dict] = {}
    for name, value in (draft.fields or {}).items():
        field = value if isinstance(value, dict) else {"value": value}
        output[name] = {
            "value": field.get("value"),
            "status": field.get("status", "check_needed"),
            "message": field.get("message", ""),
            "decision": (draft.scalar_decisions or {}).get(name),
        }
    return output


def _selection_summary(selection: DraftBenefitSelection) -> dict:
    return {
        "id": selection.id,
        "selection_key": selection.selection_key,
        "item_kind": selection.item_kind,
        "catalog_offering_id": selection.catalog_offering_id,
        "concept_id": selection.concept_id,
        "source_line_id": selection.source_line_id,
        "state": selection.state,
        "cost_status": selection.cost_status,
        "label": selection.label_override,
        "typed_value": selection.typed_value_override,
        "sort_order": selection.sort_order,
        "superseded_by_id": selection.superseded_by_id,
    }


def _decision_summary(db, decision: DraftSourceLineDecision) -> dict:
    line = db.get(ExtractionBenefitLine, decision.source_line_id)
    return {
        "id": decision.id,
        "source_line_id": decision.source_line_id,
        "line_id": line.line_id if line else None,
        "raw_label": line.raw_label if line else "",
        "normalized_label": line.normalized_label if line else "",
        "page_number": line.page_number if line else None,
        "inclusion_state": line.inclusion_state if line else "unknown",
        "disposition": decision.disposition,
        "selection_id": decision.selection_id,
        "candidate_mappings": list(line.candidate_mappings or []) if line else [],
        "extracted_value": deepcopy(line.extracted_value) if line else None,
    }


def _workspace_benefit_cards(db, draft: QuotationDraft, selections: list[DraftBenefitSelection]) -> dict[str, list[dict]]:
    concepts = list(db.scalars(select(BenefitConcept)).all())
    if not draft.catalog_revision_id:
        offerings: list = []
        relations: list = []
        facets: list = []
        valid_selections = [s for s in selections if s.item_kind != "catalog"]
    else:
        offerings = [
            item for item in db.scalars(select(CatalogOffering)).all()
            if item.catalog_revision_id == draft.catalog_revision_id
        ]
        offering_ids = {item.id for item in offerings}
        concept_ids = {item.concept_id for item in offerings}
        relations = [
            item for item in db.scalars(select(BenefitRelation)).all()
            if item.catalog_revision_id == draft.catalog_revision_id
            and item.from_offering_id in offering_ids and item.to_offering_id in offering_ids
        ]
        facets = [item for item in db.scalars(select(BenefitFacet)).all() if item.parent_concept_id in concept_ids]
        valid_selections = [
            s for s in selections
            if s.item_kind != "catalog" or s.catalog_offering_id in offering_ids
        ]
    return resolve_benefit_cards(
        selections=valid_selections, offerings=offerings, concepts=concepts, relations=relations, facets=facets,
    )


def build_workspace_snapshot(db, user, session_id: str) -> dict:
    session, draft = _session_and_draft(db, user, session_id)
    selections = _rows_for_draft(db, DraftBenefitSelection, draft.id)
    decisions = _rows_for_draft(db, DraftSourceLineDecision, draft.id)
    template_revision = _template_for_draft(db, draft)
    blockers = generation_blockers(draft, decisions, selections, template_revision=template_revision)
    try:
        benefit_cards = _workspace_benefit_cards(db, draft, selections)
    except RenderContextError:
        benefit_cards = {"current_benefits": [], "available_addons": []}
        blockers.append({
            "code": "invalid_benefit_graph",
            "path": "benefits",
            "message": "Resolve the conflicting or unavailable benefit catalog selections.",
        })
    versions = [
        version
        for version in db.scalars(
            select(GeneratedPdfVersion).where(GeneratedPdfVersion.draft_id == draft.id)
        ).all()
        if version.draft_id == draft.id
    ]
    versions.sort(key=lambda item: item.version_number)
    template = None
    if template_revision:
        template = {
            "id": template_revision.template_id,
            "revision_id": template_revision.id,
            "revision_number": template_revision.revision_number,
            "config_hash": template_revision.config_hash,
        }
    company = db.get(InsuranceCompany, draft.company_id) if draft.company_id else None
    product = db.get(InsuranceProduct, draft.product_id) if draft.product_id else None
    tier = db.get(InsuranceProductTier, draft.tier_id) if draft.tier_id else None
    catalog_overview = _catalog_overview(db, draft)
    return {
        "session_id": session.id,
        "draft_id": draft.id,
        "uploaded_file_id": draft.uploaded_file_id,
        "revision": draft.revision,
        "status": draft.status,
        "fields": _field_summary(draft),
        "benefits": [_selection_summary(item) for item in sorted(selections, key=lambda item: (item.sort_order, item.selection_key))],
        "benefit_cards": benefit_cards,
        "source_lines": [_decision_summary(db, item) for item in decisions],
        "pinned": {
            "company_id": draft.company_id,
            "product_id": draft.product_id,
            "tier_id": draft.tier_id,
            "catalog_revision_id": draft.catalog_revision_id,
            "template_revision_id": draft.template_revision_id,
        },
        "pinned_names": {
            "company_name": company.name if company else None,
            "product_name": product.name if product else None,
            "tier_name": tier.name if tier else None,
        },
        "catalog": catalog_overview,
        "template": template,
        "layout_override": draft.layout_override if (
            template_revision
            and draft.layout_override_template_id == template_revision.template_id
            and draft.layout_override_template_revision_id == template_revision.id
            and draft.layout_override_base_hash == template_revision.config_hash
        ) else None,
        "layout_binding": {
            "template_id": draft.layout_override_template_id,
            "template_revision_id": draft.layout_override_template_revision_id,
            "base_hash": draft.layout_override_base_hash,
        },
        "generation_blockers": blockers,
        "versions": [
            {
                "id": version.id,
                "version_number": version.version_number,
                "draft_revision": version.draft_revision,
                "stale": version.draft_revision != draft.revision,
                "generated_at": version.generated_at.isoformat(),
            }
            for version in versions
        ],
        "capabilities": workspace_capabilities(user),
    }


def _locked_draft(db, user, draft_id: str) -> QuotationDraft:
    _require_business_user(user)
    draft = db.scalar(
        select(QuotationDraft).where(QuotationDraft.id == draft_id).with_for_update()
    )
    if not draft or draft.id != draft_id or draft.deleted_at:
        raise AppError("Draft not found.", 404)
    return draft


def template_selection_impact(
    db,
    user,
    session_id: str,
    *,
    template_revision_id: str,
    base_revision: int,
) -> dict:
    """Preview the deterministic effects of pinning another master revision."""
    _session, draft = _session_and_draft(db, user, session_id)
    if draft.revision != base_revision:
        raise AppError("This quotation changed elsewhere. Reload before changing its template.", 409)
    target = db.get(TemplateRevision, template_revision_id)
    if target is None or target.state != "published":
        raise AppError("Choose a published template revision.", 422)
    changed = draft.template_revision_id != target.id
    resets_layout = changed and any((
        draft.layout_override is not None,
        draft.layout_override_template_id,
        draft.layout_override_template_revision_id,
        draft.layout_override_base_hash,
    ))
    return {
        "current_template_revision_id": draft.template_revision_id,
        "target": {
            "template_id": target.template_id,
            "template_revision_id": target.id,
            "revision_number": target.revision_number,
            "name": str((target.config or {}).get("template_name") or "Published template"),
            "config_hash": target.config_hash,
        },
        "will_reset_layout_override": bool(resets_layout),
        "requires_confirmation": bool(changed),
        "messages": [
            "The quotation-specific layout will reset because it belongs to another template revision."
        ] if resets_layout else [],
    }


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
    if field_name not in (draft.fields or {}):
        raise AppError("Scalar field was not found.", 422)
    if decision not in SCALAR_DECISIONS:
        raise AppError("Scalar decision is invalid.", 422)
    fields = draft.fields
    field = deepcopy(fields[field_name] if isinstance(fields[field_name], dict) else {"value": fields[field_name]})
    original = field.get("value")
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
        if field.get("value") in {None, ""}:
            raise AppError("An empty value must be cleared, not confirmed.", 422)
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
    if original != field.get("value"):
        db.add(CorrectionMemory(
            draft_id=draft.id,
            uploaded_file_id=draft.uploaded_file_id,
            field_name=field_name,
            original_value=original,
            corrected_value=field.get("value"),
            insurance_company_id=draft.company_id,
            corrected_by=user.id,
        ))
    if decision == "edit" and field_name in PIN_SENSITIVE_FIELDS:
        _reconcile_catalog_pin(db, draft, changed_field=field_name)
    if field_name in TOTAL_SOURCES:
        _recompute_total(fields, decisions, user)
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
    if field_name == "ncd_percent":
        text = re.sub(r"[^0-9.]", "", str(raw))
        if not text or text.count(".") > 1:
            raise AppError("Enter NCD as a percentage number, for example 25.", 422)
        return text
    return str(raw)


def _recompute_total(fields: dict, decisions: dict, user) -> None:
    amounts: list[Decimal] = []
    for name in ("premium", "roadtax", "service_fee"):
        field = fields.get(name)
        value = field.get("value") if isinstance(field, dict) else field
        try:
            amounts.append(Decimal(str(value)))
        except (InvalidOperation, TypeError, ValueError):
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
    total = sum(amounts, Decimal("0"))
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
    draft.catalog_revision_id = None


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
    elif changed_field in {"tier_name", "product_tier", "plan_name"}:
        draft.tier_id = None
        draft.catalog_revision_id = None

    if prev_company_id != draft.company_id:
        for s in _rows_for_draft(db, DraftBenefitSelection, draft.id):
            if s.item_kind == "catalog":
                db.delete(s)

    _sync_detected_company(db, draft)
    initialize_catalog_review(db, draft)
    auto_apply_extracted_benefits(db, draft)


def _apply_pin_catalog(db, draft: QuotationDraft, user, operation: dict) -> str:
    company_id = str(operation.get("company_id") or "").strip() or None
    product_id = str(operation.get("product_id") or "").strip() or None
    tier_id = str(operation.get("tier_id") or "").strip() or None
    if not company_id:
        raise AppError("Choose the insurance company to pin its catalog.", 422)
    company = db.get(InsuranceCompany, company_id)
    if company is None or company.status != "active":
        raise AppError("That insurance company is not active.", 422)

    company_changed = draft.company_id != company.id
    if company_changed:
        for s in _rows_for_draft(db, DraftBenefitSelection, draft.id):
            if s.item_kind == "catalog":
                db.delete(s)

    draft.company_id = company.id
    draft.product_id = None
    draft.tier_id = None
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


def _apply_reset_benefits(db, draft: QuotationDraft, user, operation: dict) -> str:
    """Reset all benefit selections back to the clean catalog defaults and auto-applied detections."""
    for s in _rows_for_draft(db, DraftBenefitSelection, draft.id):
        db.delete(s)
    for d in _rows_for_draft(db, DraftSourceLineDecision, draft.id):
        db.delete(d)
    initialize_catalog_review(db, draft)
    auto_apply_extracted_benefits(db, draft)
    return "benefits"


def _apply_custom_benefit(db, draft: QuotationDraft, user, operation: dict) -> tuple[str, DraftBenefitSelection]:
    key = _validate_selection_key(operation.get("selection_key"))
    if _selection_by_key(db, draft.id, key):
        raise AppError("A benefit with this selection key already exists.", 409)
    label = str(operation.get("label") or "").strip()
    if not label or len(label) > 255:
        raise AppError("Custom benefits require a label of at most 255 characters.", 422)
    try:
        typed_value = BenefitValue.model_validate(operation.get("typed_value")).model_dump(mode="json", exclude_none=True)
        state = ReviewedBenefitState(str(operation.get("state") or "current")).value
        cost_status = CostStatus(str(operation.get("cost_status") or "unknown")).value
    except (ValidationError, ValueError) as exc:
        raise AppError("Custom benefit state, cost, or typed value is invalid.", 422) from exc
    if state not in {ReviewedBenefitState.CURRENT.value, ReviewedBenefitState.AVAILABLE_ADDON.value}:
        raise AppError("A new custom benefit must be current or an available add-on.", 422)
    source_line_id = operation.get("source_line_id")
    if source_line_id:
        _line_belongs_to_draft(db, draft, str(source_line_id))
    concept_id = operation.get("concept_id")
    if not concept_id and operation.get("concept_key"):
        matched_concept = db.scalar(select(BenefitConcept).where(BenefitConcept.concept_key == operation.get("concept_key")))
        if matched_concept:
            concept_id = matched_concept.id
    if not concept_id:
        matched_concept = db.scalar(select(BenefitConcept).where(func.lower(BenefitConcept.label) == label.lower()))
        if matched_concept:
            concept_id = matched_concept.id

    selection = DraftBenefitSelection(
        id=new_id(),
        draft_id=draft.id,
        selection_key=key,
        source_line_id=str(source_line_id) if source_line_id else None,
        concept_id=str(concept_id) if concept_id else None,
        item_kind="custom",
        state=state,
        cost_status=cost_status,
        label_override=label,
        typed_value_override=typed_value,
        evidence_snapshot={},
        sort_order=int(operation.get("sort_order") or 0),
        selected_by=user.id,
    )
    db.add(selection)
    return f"benefits.{selection.id}", selection


def _draft_selections_with_pending(db, draft_id: str) -> list[DraftBenefitSelection]:
    rows = _rows_for_draft(db, DraftBenefitSelection, draft_id)
    for item in getattr(db, "added", []):
        if isinstance(item, DraftBenefitSelection) and item.draft_id == draft_id and item not in rows:
            rows.append(item)
    return rows


def _apply_select_catalog_offering(db, draft: QuotationDraft, user, operation: dict) -> str:
    offering_id = str(operation.get("offering_id") or "")
    offering = db.get(CatalogOffering, offering_id)
    if not offering or offering.catalog_revision_id != draft.catalog_revision_id or offering.status not in {"active", "compatibility"}:
        raise AppError("Choose an available offering from this quotation's pinned catalog.", 422)
    selections = _draft_selections_with_pending(db, draft.id)
    current = [item for item in selections if item.concept_id == offering.concept_id and item.state == ReviewedBenefitState.CURRENT.value]
    if len(current) > 1:
        raise AppError("This benefit concept has conflicting current selections.", 409)
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
        cost_status = CostStatus(str(operation.get("cost_status") or "unknown")).value
    except ValueError as exc:
        raise AppError("Benefit cost must be included, paid, FOC, or unknown.", 422) from exc
    typed_override = None
    if "typed_value" in operation and operation.get("typed_value") is not None:
        try:
            typed_override = BenefitValue.model_validate(operation["typed_value"]).model_dump(mode="json", exclude_none=True)
        except ValidationError as exc:
            raise AppError("The quotation-specific benefit value is invalid.", 422) from exc

    selected = next((item for item in selections if item.catalog_offering_id == offering.id), None)
    if selected is None:
        selected = DraftBenefitSelection(
            id=new_id(), draft_id=draft.id, selection_key=f"catalog:{offering.offering_key}"[:160],
            catalog_offering_id=offering.id, concept_id=offering.concept_id, item_kind="catalog",
            label_override=offering.label_override, evidence_snapshot={"catalog_revision_id": draft.catalog_revision_id},
            sort_order=int(offering.sort_order or 0),
        )
        db.add(selected)
    selected.state = ReviewedBenefitState.CURRENT.value
    selected.cost_status = cost_status
    selected.typed_value_override = typed_override
    selected.selected_by = user.id
    if current and current[0].id != selected.id:
        current[0].state = ReviewedBenefitState.SUPERSEDED.value
        current[0].superseded_by_id = selected.id
    return f"benefits.{selected.id}"


def _apply_benefit_update(db, draft: QuotationDraft, user, operation: dict) -> str:
    selection_id = str(operation.get("selection_id") or "")
    selection = db.get(DraftBenefitSelection, selection_id)
    if not selection or selection.draft_id != draft.id:
        raise AppError("Quotation benefit not found.", 404)
    if "state" in operation:
        try:
            state = ReviewedBenefitState(str(operation.get("state"))).value
        except ValueError as exc:
            raise AppError("Quotation benefit state is invalid.", 422) from exc
        if state == ReviewedBenefitState.CURRENT.value:
            conflicts = [
                item for item in _draft_selections_with_pending(db, draft.id)
                if item.id != selection.id and item.concept_id and item.concept_id == selection.concept_id and item.state == ReviewedBenefitState.CURRENT.value
            ]
            if conflicts:
                raise AppError("Replace the current benefit through an explicit catalog upgrade.", 409)
        selection.state = state
        if state != ReviewedBenefitState.SUPERSEDED.value:
            selection.superseded_by_id = None
    if "cost_status" in operation:
        try:
            selection.cost_status = CostStatus(str(operation.get("cost_status"))).value
        except ValueError as exc:
            raise AppError("Benefit cost must be included, paid, FOC, or unknown.", 422) from exc
    if "typed_value" in operation:
        raw = operation.get("typed_value")
        if raw is None:
            selection.typed_value_override = None
        else:
            try:
                selection.typed_value_override = BenefitValue.model_validate(raw).model_dump(mode="json", exclude_none=True)
            except ValidationError as exc:
                raise AppError("The quotation-specific benefit value is invalid.", 422) from exc
    selection.selected_by = user.id
    return f"benefits.{selection.id}"


def _apply_revert_benefit(db, draft: QuotationDraft, user, operation: dict) -> str:
    selection_id = str(operation.get("selection_id") or "")
    selection = db.get(DraftBenefitSelection, selection_id)
    if not selection or selection.draft_id != draft.id:
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


def _apply_source_disposition(db, draft: QuotationDraft, user, operation: dict) -> str:
    source_line_id = str(operation.get("source_line_id") or "")
    _line_belongs_to_draft(db, draft, source_line_id)
    try:
        disposition = SourceLineDisposition(str(operation.get("disposition") or "")).value
    except ValueError as exc:
        raise AppError("Source-line disposition is invalid.", 422) from exc
    decision = _decision_by_line(db, draft.id, source_line_id)
    if decision is None:
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
            elif operation_name == "source_disposition":
                changed_paths.append(_apply_source_disposition(db, draft, user, operation))
            elif operation_name == "select_catalog_offering":
                changed_paths.append(_apply_select_catalog_offering(db, draft, user, operation))
            elif operation_name == "benefit_update":
                changed_paths.append(_apply_benefit_update(db, draft, user, operation))
            elif operation_name == "revert_benefit":
                changed_paths.append(_apply_revert_benefit(db, draft, user, operation))
            elif operation_name == "layout_override":
                changed_paths.append(_apply_layout_override(db, draft, operation))
            elif operation_name == "pin_catalog":
                changed_paths.append(_apply_pin_catalog(db, draft, user, operation))
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
        db.commit()
        db.refresh(draft)
    except AppError:
        db.rollback()
        raise
    return {
        "draft_id": draft.id,
        "revision": draft.revision,
        "status": draft.status,
        "fields": _field_summary(draft),
        "changed_paths": changed_paths,
        "generation_blockers": blockers,
    }
