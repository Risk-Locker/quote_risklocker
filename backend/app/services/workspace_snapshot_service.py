"""Read-side workspace snapshot compilation."""

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


__all__ = ['workspace_capabilities', '_catalog_overview', '_selection_summary', '_decision_summary', '_workspace_benefit_cards', 'build_workspace_snapshot', '_workspace_extracted_benefits_section', '_workspace_packs', '_workspace_package_tiers', 'template_selection_impact']


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



def _catalog_overview(db, draft: QuotationDraft) -> dict:
    if not draft.catalog_revision_id:
        return {"defaults": [], "addons": []}
    offerings = list(
        db.scalars(
            select(CatalogOffering).where(CatalogOffering.catalog_revision_id == draft.catalog_revision_id)
        ).all()
    )
    concept_ids = {item.concept_id for item in offerings}
    concepts = (
        {item.id: item for item in db.scalars(select(BenefitConcept).where(BenefitConcept.id.in_(concept_ids))).all()}
        if concept_ids
        else {}
    )
    overview = {"defaults": [], "addons": []}
    for offering in sorted(offerings, key=lambda item: (int(item.sort_order or 0), item.offering_key)):
        concept = concepts.get(offering.concept_id)
        label = offering.label_override or (concept.label if concept else offering.offering_key)
        try:
            value = format_benefit_value(offering.typed_value)
        except RenderContextError:
            value = ""
        entry = {"offering_id": offering.id, "label": label, "value": value}
        role = offering.role
        is_default = role == "included" or (role is None and offering.offering_kind == "base")
        if is_default:
            overview["defaults"].append(entry)
        else:
            overview["addons"].append(entry)
    return overview



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
        "package_plan_id": selection.package_plan_id,
        "price": selection.price,
    }



def _decision_summary(db, decision: DraftSourceLineDecision, lines_by_id: dict | None = None) -> dict:
    if lines_by_id is not None:
        line = lines_by_id.get(decision.source_line_id)
    else:
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



def _workspace_benefit_cards(db, draft: QuotationDraft, selections: list[DraftBenefitSelection], decisions: list[DraftSourceLineDecision]) -> dict[str, list[dict]]:
    concepts = list(db.scalars(select(BenefitConcept)).all())
    if not draft.catalog_revision_id:
        offerings: list = []
        relations: list = []
        facets: list = []
        plans: list = []
        retired_concept_ids = {str(item.id) for item in concepts if getattr(item, "status", "active") == "retired"}
        valid_selections = [
            s for s in selections
            if s.item_kind != "catalog" and (s.concept_id or "") not in retired_concept_ids
        ]
    else:
        offerings = list(
            db.scalars(
                select(CatalogOffering).where(CatalogOffering.catalog_revision_id == draft.catalog_revision_id)
            ).all()
        )
        offering_ids = {item.id for item in offerings}
        concept_ids = {item.concept_id for item in offerings}
        relations = (
            list(
                db.scalars(
                    select(BenefitRelation).where(
                        BenefitRelation.catalog_revision_id == draft.catalog_revision_id,
                        BenefitRelation.from_offering_id.in_(offering_ids),
                        BenefitRelation.to_offering_id.in_(offering_ids),
                    )
                ).all()
            )
            if offering_ids
            else []
        )
        facets = (
            list(
                db.scalars(select(BenefitFacet).where(BenefitFacet.parent_concept_id.in_(concept_ids))).all()
            )
            if concept_ids
            else []
        )
        package_ids = {
            item.id
            for item in db.scalars(
                select(BenefitPackage).where(BenefitPackage.catalog_revision_id == draft.catalog_revision_id)
            ).all()
        }
        plans = (
            list(
                db.scalars(select(BenefitPackagePlan).where(BenefitPackagePlan.package_id.in_(package_ids))).all()
            )
            if package_ids
            else []
        )
        retired_concept_ids = {str(item.id) for item in concepts if getattr(item, "status", "active") == "retired"}
        offerings_by_concept = {str(item.concept_id): item for item in offerings if item.concept_id}
        valid_selections = []
        for s in selections:
            if (s.concept_id or "") in retired_concept_ids:
                continue
            if s.item_kind == "catalog":
                if s.catalog_offering_id not in offering_ids:
                    matched_off = offerings_by_concept.get(s.concept_id or "")
                    if matched_off:
                        s.catalog_offering_id = matched_off.id
                        valid_selections.append(s)
                else:
                    valid_selections.append(s)
            else:
                valid_selections.append(s)
    from app.services.formula_evaluator import extract_evaluation_context
    from app.services.benefit_catalog_matrix import get_catalog_for_product
    
    extras_section = _workspace_extracted_benefits_section(db, draft, decisions, selections)
    eval_context = extract_evaluation_context(draft.fields or {}, extras_section.get("extras", []))
    
    # Try to determine insurer_key and product_type
    draft_company = getattr(draft, "company", None)
    draft_product = getattr(draft, "product", None)
    insurer_key = str(getattr(draft_company, "company_key", "") or "etiqa") if draft_company else "etiqa"
    product_type = str(getattr(draft_product, "name", "private_car") or "private_car") if draft_product else "private_car"
    
    insurer_catalog = get_catalog_for_product(insurer_key, product_type)

    company_conditions = []
    company_configs = []
    if getattr(draft, "company_id", None):
        from app.services.business_setup_service import get_active_benefit_profile
        try:
            active_prof = get_active_benefit_profile(db)
            if active_prof:
                company_conditions = list(db.scalars(
                    select(CompanyBenefitCondition).where(
                        CompanyBenefitCondition.company_id == draft.company_id,
                        CompanyBenefitCondition.profile_id == active_prof.id,
                        CompanyBenefitCondition.is_active.is_(True),
                    )
                ).all())
                company_configs = list(db.scalars(
                    select(CompanyBenefitConfig).where(
                        CompanyBenefitConfig.company_id == draft.company_id,
                        CompanyBenefitConfig.profile_id == active_prof.id,
                    )
                ).all())
        except Exception:
            pass

    visual_profile_assets = None
    try:
        from app.services.global_benefit_profile_service import get_active_visual_profile_asset_map
        visual_profile_assets = get_active_visual_profile_asset_map(db)
    except Exception:
        pass

    return resolve_benefit_cards(
        selections=valid_selections, offerings=offerings, concepts=concepts, relations=relations, facets=facets,
        plans=plans, eval_context=eval_context, insurer_catalog=insurer_catalog,
        company_conditions=company_conditions, company_configs=company_configs,
        visual_profile_assets=visual_profile_assets,
    )



def build_workspace_snapshot(db, user, session_id: str) -> dict:
    session, draft = _session_and_draft(db, user, session_id)
    selections = _rows_for_draft(db, DraftBenefitSelection, draft.id)
    current_selections = [s for s in selections if s.state == "current"]
    catalog_rev = db.get(BenefitCatalogRevision, draft.catalog_revision_id) if draft.catalog_revision_id else None
    catalog = db.get(BenefitCatalog, catalog_rev.catalog_id) if catalog_rev else None
    if not draft.catalog_revision_id and not selections and (draft.company_id or session.detected_company):
        try:
            revision = pin_catalog_context(db, draft)
            if revision:
                seed_base_benefits(db, draft, revision)
            auto_apply_extracted_benefits(db, draft)
            db.commit()
            selections = _rows_for_draft(db, DraftBenefitSelection, draft.id)
            current_selections = [s for s in selections if s.state == "current"]
        except Exception:
            db.rollback()
            selections = _rows_for_draft(db, DraftBenefitSelection, draft.id)
    decisions = _rows_for_draft(db, DraftSourceLineDecision, draft.id)
    template_revision = _template_for_draft(db, draft)
    blockers = generation_blockers(draft, decisions, selections, template_revision=template_revision)
    try:
        benefit_cards = _workspace_benefit_cards(db, draft, selections, decisions)
    except Exception as e:
        import traceback
        traceback.print_exc()
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
    package = db.get(BenefitPackage, draft.package_id) if getattr(draft, "package_id", None) else None
    catalog_overview = _catalog_overview(db, draft)
    concepts = list(db.scalars(select(BenefitConcept)).all())
    offerings = (
        list(
            db.scalars(
                select(CatalogOffering).where(CatalogOffering.catalog_revision_id == draft.catalog_revision_id)
            ).all()
        )
        if draft.catalog_revision_id
        else []
    )
    extras = build_extras(selections, concepts, offerings)
    round_tot = bool((draft.display_options or {}).get("round_total", False))
    adjusted_total = adjusted_total_text(draft.fields or {}, extras, round_total=round_tot)
    
    # Extract car model string safely
    raw_car_model = (draft.fields or {}).get("car_model")
    car_model_str = raw_car_model.get("value") if isinstance(raw_car_model, dict) else (raw_car_model or "")

    if not draft.template_revision_id:
        tmpl_rev = _template_for_draft(db, draft)
        if tmpl_rev:
            draft.template_revision_id = tmpl_rev.id
            db.flush()
    
    line_ids = {item.source_line_id for item in decisions if item.source_line_id}
    lines_by_id = (
        {line.id: line for line in db.scalars(select(ExtractionBenefitLine).where(ExtractionBenefitLine.id.in_(line_ids))).all()}
        if line_ids
        else {}
    )

    return {
        "session_id": session.id,
        "draft_id": draft.id,
        "uploaded_file_id": draft.uploaded_file_id,
        "revision": draft.revision,
        "status": draft.status,
        "is_test": bool(getattr(session, "is_test", False)),
        "display_options": draft.display_options or {},
        "quotation_ref": session.quotation_ref,
        "fields": _field_summary(draft, session.quotation_ref),
        "benefits": [_selection_summary(item) for item in sorted(selections, key=lambda item: (item.sort_order, item.selection_key))],
        "benefit_cards": benefit_cards,
        "extras": extras,
        "total_premium_adjusted": adjusted_total,
        "packs": _workspace_packs(db, draft),
        "package_tiers": _workspace_package_tiers(db, draft),
        "source_lines": [_decision_summary(db, item, lines_by_id=lines_by_id) for item in decisions],
        "pinned": {
            "company_id": draft.company_id,
            "product_id": draft.product_id,
            "tier_id": draft.tier_id,
            "package_id": draft.package_id,
            "catalog_revision_id": draft.catalog_revision_id,
            "template_revision_id": draft.template_revision_id,
        },
        "pinned_names": {
            "company_name": company.name if company else None,
            "product_name": product.name if product else None,
            "tier_name": tier.name if tier else None,
            "package_name": package.name if package else None,
        },
        "hierarchy": {
            "company_name": company.name if company else (session.detected_company or "Insurance Company"),
            "product_name": product.name if product else "Comprehensive Motor",
            "vehicle_category": getattr(product, "vehicle_category_code", None) or "Private Passenger Car",
            "segment": getattr(product, "segment_code", None) or "Private",
            "coverage_type": getattr(product, "coverage_type_code", None) or "Comprehensive",
            "car_model": str(car_model_str or "Vehicle"),
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
        "extracted_benefits_section": _workspace_extracted_benefits_section(db, draft, decisions, selections),
        "capabilities": workspace_capabilities(user),
        "quotation_tracking": {
            "status": session.quotation_status or "pending",
            "closed_at": session.closed_at.isoformat() if session.closed_at else None,
            "miss_reason": session.miss_reason,
            "vehicle_no": session.tracked_vehicle.vehicle_no if getattr(session, "tracked_vehicle", None) else None,
            "owner_change_alert": (draft.display_options or {}).get("owner_change_alert"),
        },
    }



def _workspace_extracted_benefits_section(
    db,
    draft: QuotationDraft,
    decisions: list[DraftSourceLineDecision],
    selections: list[DraftBenefitSelection],
) -> dict:
    """Detailed summary of detected insurance packages, extra covers, and add-on costs from quotation PDF."""
    extraction = db.scalar(
        select(ExtractionRecord).where(ExtractionRecord.uploaded_file_id == draft.uploaded_file_id)
    )
    detected_package_name = ""
    detected_packs = []
    if extraction and extraction.candidates:
        tier_candidates = extraction.candidates.get("product_tier") or extraction.candidates.get("tier_name") or []
        if tier_candidates and isinstance(tier_candidates, list):
            detected_package_name = str(tier_candidates[0].get("value") or "")
        detected_packs = extraction.candidates.get("detected_packs") or []

    if not detected_package_name:
        prod_val = str((draft.fields or {}).get("product_name", {}).get("value") or "")
        if any(w in prod_val.lower() for w in ("auto365", "premier", "plus", "lite", "standard", "mymotor", "myclick")):
            detected_package_name = prod_val

    # Find matching package tier if any
    matched_tier_id = None
    pkg_tiers = _workspace_package_tiers(db, draft)
    if detected_package_name and pkg_tiers:
        norm_det = re.sub(r"[^a-z0-9]+", "", detected_package_name.lower())
        for pt in pkg_tiers:
            norm_pt = re.sub(r"[^a-z0-9]+", "", pt["name"].lower())
            if norm_pt in norm_det or norm_det in norm_pt:
                matched_tier_id = pt["package_id"]
                break

    raw_lines = extraction.benefit_lines if extraction and extraction.benefit_lines else []
    selection_concepts = {str(s.concept_id): s for s in selections if s.state == "current"}
    all_concepts = list(db.scalars(select(BenefitConcept)).all())
    concepts_by_id = {str(c.id): c for c in all_concepts}
    concepts_by_key = {c.concept_key: c for c in all_concepts}

    extras_list = []
    seen_labels = set()
    total_opt_cover = str((draft.fields or {}).get("optional_cover_amount", {}).get("value") or "")

    for idx, line in enumerate(raw_lines):
        if not isinstance(line, dict):
            continue
        label = line.get("raw_label") or line.get("raw_text") or ""
        if not label:
            continue
        norm_label = re.sub(r"\s+", " ", label).strip()
        if norm_label.lower() in seen_labels:
            continue
        # Reject pure amounts, totals, accounting calculation rows, or negative flags
        if re.match(r"^[:\-•*+~]?\s*(?:RM|MYR)?\s*[\d,]+(?:\.\d{1,2})?\s*%?\s*$", norm_label, re.IGNORECASE):
            continue
        if re.match(r"^(?:total|basic contribution|gross contribution|total contribution|takaful contribution|\+ additional|\- ncd|\+ service tax|\+ stamp duty|quotation type|agent code|takaful scheme|insurance scheme|agreed value|market value|acceptance of any|this quotation|endorsement attaching|cbc regulation)\b", norm_label, re.IGNORECASE):
            continue
        if re.search(r"[:=\-]?\s*(?:no|tidak|false)\b", norm_label, re.IGNORECASE):
            continue
        if line.get("line_kind") in {"narrative", "pds_narrative"} or line.get("source_scope") == "pds":
            continue
        if is_spurious_benefit_line(norm_label):
            continue

        seen_labels.add(norm_label.lower())

        raw_cov_limit = line.get("coverage_limit")
        cov_limit = ""
        if isinstance(raw_cov_limit, str) and raw_cov_limit.strip():
            cov_limit = raw_cov_limit.strip()
        elif isinstance(raw_cov_limit, (int, float)):
            cov_limit = f"{raw_cov_limit:,.2f}" if raw_cov_limit != int(raw_cov_limit) else f"{int(raw_cov_limit):,}"

        raw_cost = line.get("premium_cost")
        cost = ""
        if isinstance(raw_cost, str) and raw_cost.strip():
            cost = raw_cost.strip()
        elif isinstance(raw_cost, (int, float)):
            cost = f"{raw_cost:,.2f}" if raw_cost != int(raw_cost) else f"{int(raw_cost):,}"

        typed_val = line.get("extracted_value") or {}
        if not cost and isinstance(typed_val, dict) and typed_val.get("semantic_role") == "premium":
            cost = str(typed_val.get("value") or "")
        if not cov_limit and isinstance(typed_val, dict) and typed_val.get("semantic_role") in {"limit", "insured_limit"}:
            cov_limit = str(typed_val.get("value") or "")

        # Clean cost and limit to avoid showing false limit matching cost
        is_plan = bool(re.search(r"\b(plan|tier|level|package|option)\s*\d+\b", label + " " + cov_limit, re.I))
        clean_lim_str = re.sub(r"[^0-9.]", "", cov_limit)
        clean_cost_str = re.sub(r"[^0-9.]", "", cost)
        if clean_lim_str and clean_cost_str:
            try:
                l_n = float(clean_lim_str)
                c_n = float(clean_cost_str)
                if abs(l_n - c_n) <= 0.01 or l_n == 0:
                    cov_limit = ""
                elif is_plan and l_n < 100:
                    # Single-digit plan tier numbers (e.g. Plan 4) are not coverage sums insured
                    cov_limit = ""
            except Exception:
                pass
        elif is_plan and clean_lim_str:
            try:
                l_n = float(clean_lim_str)
                if l_n < 100:
                    cov_limit = ""
            except Exception:
                pass

        mappings = line.get("candidate_mappings") or []
        first_map = mappings[0] if mappings else {}
        concept_id = first_map.get("concept_id")
        concept_key = first_map.get("concept_key") or ""

        concept = concepts_by_id.get(str(concept_id)) if concept_id else concepts_by_key.get(concept_key)
        disp_ovr = (getattr(concept, "display_overrides", {}) or {}) if concept else {}
        show_cov = True
        if disp_ovr.get("enabled") and disp_ovr.get("showCoverage") is False:
            show_cov = False
        elif disp_ovr.get("showCoverage") is False:
            show_cov = False

        if not show_cov:
            cov_limit = ""
            label = re.sub(r"\s*\(RM\s*[\d,.]+\)", "", label, flags=re.I).strip()
        else:
            # Strip false (RM \d+) suffix if attached to a plan tier name (e.g. Plan 4 (RM 4))
            label = re.sub(r"(\bplan\s*\d+)\s*\(RM\s*[\d,.]+\)", r"\1", label, flags=re.I).strip()

        is_applied = False
        selection_id = None
        if concept_id and str(concept_id) in selection_concepts:
            is_applied = True
            selection_id = selection_concepts[str(concept_id)].id
        elif concept_id and bool(cost):
            # Known benefit concept with purchased extra cost
            is_applied = True

        is_optional = bool(line.get("is_optional_cover")) or line.get("section") == "Optional Covers" or bool(cost)

        extras_list.append({
            "id": line.get("line_id") or f"ext_{idx}",
            "label": label,
            "raw_text": line.get("raw_text") or label,
            "coverage_limit": cov_limit,
            "cost": cost,
            "is_optional_cover": is_optional,
            "concept_key": concept_key,
            "concept_id": concept_id,
            "is_applied": is_applied,
            "selection_id": selection_id,
            "display_overrides": disp_ovr,
            "show_coverage": show_cov,
            "source": "gemini_vision" if "gemini" in str(line.get("line_id", "")) else "native_pdf",
        })

    calc_extras_sum = 0.0
    for e in extras_list:
        c_str = re.sub(r"[^0-9.]", "", str(e.get("cost") or ""))
        if c_str:
            try:
                calc_extras_sum += float(c_str)
            except ValueError:
                pass

    if calc_extras_sum > 0:
        try:
            cur_tot = float(re.sub(r"[^0-9.]", "", total_opt_cover)) if total_opt_cover else 0.0
            if cur_tot == 0.0 or cur_tot > (calc_extras_sum * 5.0):
                total_opt_cover = f"{calc_extras_sum:,.2f}"
        except Exception:
            total_opt_cover = f"{calc_extras_sum:,.2f}"

    return {
        "detected_package": {
            "name": detected_package_name,
            "matching_package_id": matched_tier_id,
            "is_active_tier": any(pt.get("is_current") for pt in pkg_tiers if pt.get("package_id") == matched_tier_id) if matched_tier_id else False,
        },
        "total_optional_cover_amount": total_opt_cover,
        "extras": extras_list,
        "detected_packs": detected_packs,
    }



def _workspace_packs(db, draft: QuotationDraft) -> list[dict]:
    """Add-on bundles with their plan ladder, for the sessions add-ons manager."""
    if not draft.catalog_revision_id:
        return []
    packages = list(
        db.scalars(
            select(BenefitPackage).where(
                BenefitPackage.catalog_revision_id == draft.catalog_revision_id,
                BenefitPackage.package_kind == "addon_bundle",
                BenefitPackage.status == "active",
            )
        ).all()
    )
    package_ids = {item.id for item in packages}
    plans = (
        list(
            db.scalars(
                select(BenefitPackagePlan).where(
                    BenefitPackagePlan.package_id.in_(package_ids),
                    BenefitPackagePlan.status == "active",
                )
            ).all()
        )
        if package_ids
        else []
    )
    plan_ids = {item.id for item in plans}
    items = (
        list(
            db.scalars(
                select(BenefitPackagePlanItem).where(BenefitPackagePlanItem.plan_id.in_(plan_ids))
            ).all()
        )
        if plan_ids
        else []
    )
    offerings = {
        item.id: item
        for item in db.scalars(
            select(CatalogOffering).where(CatalogOffering.catalog_revision_id == draft.catalog_revision_id)
        ).all()
    }
    concepts = {item.id: item for item in db.scalars(select(BenefitConcept)).all()}
    result: list[dict] = []
    for package in sorted(packages, key=lambda item: (int(item.sort_order or 0), str(item.id))):
        plan_rows = []
        for plan in sorted(plans, key=lambda item: (int(item.sort_order or 0), str(item.id))):
            if plan.package_id != package.id:
                continue
            members = []
            for item in sorted(items, key=lambda row: (int(row.sort_order or 0), str(row.id))):
                if item.plan_id != plan.id:
                    continue
                offering = offerings.get(item.offering_id)
                label = None
                if offering:
                    concept = concepts.get(offering.concept_id) if offering.concept_id else None
                    label = offering.label_override or (concept.label if concept else None)
                members.append({
                    "offering_id": item.offering_id,
                    "label": label or "Benefit",
                    "typed_value_override": item.typed_value_override,
                })
            plan_rows.append({
                "plan_id": plan.id,
                "plan_key": plan.plan_key,
                "name": plan.name,
                "sort_order": plan.sort_order,
                "members": members,
            })
        result.append({
            "package_id": package.id,
            "package_key": package.package_key,
            "name": package.name,
            "plans": plan_rows,
        })
    return result



def _workspace_package_tiers(db, draft: QuotationDraft) -> list[dict]:
    """Comprehensive package tiers for the pinned catalog revision / company (AmAssurance-style).

    When a catalog revision is pinned on the draft, tiers are the active comprehensive
    packages belonging to that revision. When no revision is pinned yet, falls back
    to iterating company catalogs and picking their newest published revision.
    """
    if draft.catalog_revision_id:
        revision = db.get(BenefitCatalogRevision, draft.catalog_revision_id)
        if revision is not None:
            catalog = db.get(BenefitCatalog, revision.catalog_id)
            packages = [
                item for item in db.scalars(
                    select(BenefitPackage).where(
                        BenefitPackage.catalog_revision_id == revision.id,
                        BenefitPackage.package_kind == "comprehensive",
                        BenefitPackage.status == "active",
                    )
                ).all()
                if item.catalog_revision_id == revision.id
                and item.package_kind == "comprehensive"
                and item.status == "active"
            ]
            if packages:
                packages.sort(key=lambda item: (int(item.sort_order or 0), item.name.casefold()))
                valid_ids = {item.id for item in packages}
                current_pkg_id = None
                if getattr(draft, "package_id", None) and draft.package_id in valid_ids:
                    current_pkg_id = draft.package_id
                elif catalog and catalog.package_id and catalog.package_id in valid_ids:
                    current_pkg_id = catalog.package_id
                else:
                    current_pkg_id = packages[0].id

                # If this catalog revision has only 1 package, check if the insurer has sibling package catalogs
                # under the same vehicle category and engine type (e.g. AmAssurance Auto365 tiers: Lite, Plus, Premier, All-Inclusive)
                if len(packages) == 1 and catalog and catalog.company_id:
                    sibling_catalogs = [
                        item for item in db.scalars(
                            select(BenefitCatalog).where(
                                BenefitCatalog.company_id == catalog.company_id,
                                BenefitCatalog.status != "archived",
                                BenefitCatalog.id != catalog.id,
                            )
                        ).all()
                        if item.company_id == catalog.company_id
                        and item.status != "archived"
                        and item.package_id is not None
                        and (not catalog.vehicle_category_id or item.vehicle_category_id == catalog.vehicle_category_id)
                        and (item.engine_type or "ice") == (catalog.engine_type or "ice")
                        and (not catalog.coverage_type_id or item.coverage_type_id == catalog.coverage_type_id)
                    ]
                    if sibling_catalogs:
                        all_sibling_cats = [catalog] + sibling_catalogs
                        all_package_tiers: list[dict] = []
                        target_active_pkg_id = draft.package_id or catalog.package_id or packages[0].id
                        for sc in all_sibling_cats:
                            sc_rev = revision if sc.id == catalog.id else db.scalar(
                                select(BenefitCatalogRevision).where(
                                    BenefitCatalogRevision.catalog_id == sc.id,
                                    BenefitCatalogRevision.state == "published",
                                ).order_by(BenefitCatalogRevision.revision_number.desc())
                            )
                            if not sc_rev and sc.id != catalog.id:
                                sc_rev = db.scalar(
                                    select(BenefitCatalogRevision).where(
                                        BenefitCatalogRevision.catalog_id == sc.id,
                                        BenefitCatalogRevision.state != "archived",
                                    ).order_by(BenefitCatalogRevision.revision_number.desc())
                                )
                            if not sc_rev:
                                continue
                            sc_pkgs = [
                                p for p in db.scalars(
                                    select(BenefitPackage).where(
                                        BenefitPackage.catalog_revision_id == sc_rev.id,
                                        BenefitPackage.package_kind == "comprehensive",
                                        BenefitPackage.status == "active",
                                    )
                                ).all()
                                if p.catalog_revision_id == sc_rev.id
                                and p.package_kind == "comprehensive"
                                and p.status == "active"
                            ]
                            sc_offerings = [
                                o for o in db.scalars(
                                    select(CatalogOffering).where(
                                        CatalogOffering.catalog_revision_id == sc_rev.id,
                                        CatalogOffering.status.in_(["active", "compatibility"]),
                                    )
                                ).all()
                                if o.catalog_revision_id == sc_rev.id
                                and o.status in {"active", "compatibility"}
                            ]
                            for p in sc_pkgs:
                                p_offs = [o for o in sc_offerings if o.applies_to_type != "package" or o.applies_to_id == p.id]
                                def_count = sum(1 for o in p_offs if o.role == "included" or (o.role is None and o.offering_kind == "base"))
                                add_count = sum(1 for o in p_offs if o.role in {"addon_option", "bundle_component"})
                                all_package_tiers.append({
                                    "package_id": p.id,
                                    "package_key": p.package_key,
                                    "name": p.name,
                                    "sort_order": int(p.sort_order or 0),
                                    "catalog_id": sc.id,
                                    "catalog_revision_id": sc_rev.id,
                                    "defaults_count": def_count,
                                    "addons_count": add_count,
                                    "is_current": p.id == target_active_pkg_id or draft.catalog_revision_id == sc_rev.id,
                                })
                        if len(all_package_tiers) > 1:
                            all_package_tiers.sort(key=lambda item: (item["sort_order"], item["name"].casefold()))
                            return all_package_tiers

                offerings = [
                    item for item in db.scalars(
                        select(CatalogOffering).where(
                            CatalogOffering.catalog_revision_id == revision.id,
                            CatalogOffering.status.in_(["active", "compatibility"]),
                        )
                    ).all()
                    if item.catalog_revision_id == revision.id
                    and item.status in {"active", "compatibility"}
                ]
                tiers: list[dict] = []
                for package in packages:
                    pkg_offerings = [
                        item for item in offerings
                        if item.applies_to_type != "package" or item.applies_to_id == package.id
                    ]
                    def_count = sum(
                        1 for item in pkg_offerings
                        if item.role == "included" or (item.role is None and item.offering_kind == "base")
                    )
                    add_count = sum(
                        1 for item in pkg_offerings
                        if item.role in {"addon_option", "bundle_component"}
                    )
                    tiers.append({
                        "package_id": package.id,
                        "package_key": package.package_key,
                        "name": package.name,
                        "sort_order": int(package.sort_order or 0),
                        "catalog_id": catalog.id if catalog else "",
                        "catalog_revision_id": revision.id,
                        "defaults_count": def_count,
                        "addons_count": add_count,
                        "is_current": package.id == current_pkg_id,
                    })
                return tiers

    if not draft.company_id:
        return []
    catalogs = [
        item for item in db.scalars(
            select(BenefitCatalog).where(
                BenefitCatalog.company_id == draft.company_id,
                BenefitCatalog.status.in_(["active", "published"]),
            )
        ).all()
        if item.company_id == draft.company_id and item.status in {"active", "published"}
    ]
    if draft.product_id:
        catalogs = [item for item in catalogs if not item.product_id or item.product_id == draft.product_id]
    if not catalogs:
        return []

    tiers = []
    for catalog in catalogs:
        revs = [
            item for item in db.scalars(
                select(BenefitCatalogRevision).where(
                    BenefitCatalogRevision.catalog_id == catalog.id,
                    BenefitCatalogRevision.state == "published",
                )
            ).all()
            if item.catalog_id == catalog.id and item.state == "published"
        ]
        if not revs:
            continue
        revision = max(revs, key=lambda item: (int(item.revision_number), str(item.id)))
        rev_packages = [
            item for item in db.scalars(
                select(BenefitPackage).where(
                    BenefitPackage.catalog_revision_id == revision.id,
                    BenefitPackage.package_kind == "comprehensive",
                    BenefitPackage.status == "active",
                )
            ).all()
            if item.catalog_revision_id == revision.id
            and item.package_kind == "comprehensive"
            and item.status == "active"
        ]
        package = None
        if catalog.package_id:
            package = next((p for p in rev_packages if p.id == catalog.package_id), None)
            if package is None:
                package = db.get(BenefitPackage, catalog.package_id)
        elif rev_packages:
            package = min(rev_packages, key=lambda p: (int(p.sort_order or 0), p.name.casefold()))
        if package is None:
            continue

        offerings = [
            item for item in db.scalars(
                select(CatalogOffering).where(
                    CatalogOffering.catalog_revision_id == revision.id,
                    CatalogOffering.status.in_(["active", "compatibility"]),
                )
            ).all()
            if item.catalog_revision_id == revision.id
            and item.status in {"active", "compatibility"}
        ]
        pkg_offerings = [
            item for item in offerings
            if item.applies_to_type != "package" or item.applies_to_id == package.id
        ]
        def_count = sum(
            1 for item in pkg_offerings
            if item.role == "included" or (item.role is None and item.offering_kind == "base")
        )
        add_count = sum(
            1 for item in pkg_offerings
            if item.role in {"addon_option", "bundle_component"}
        )
        tiers.append({
            "package_id": package.id,
            "package_key": package.package_key,
            "name": package.name,
            "sort_order": int(package.sort_order or 0),
            "catalog_id": catalog.id,
            "catalog_revision_id": revision.id,
            "defaults_count": def_count,
            "addons_count": add_count,
            "is_current": draft.catalog_revision_id == revision.id,
        })
    tiers.sort(key=lambda item: (item["sort_order"], item["name"].casefold()))
    return tiers



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
    target = db.get(TemplateRevision, template_revision_id)
    if target is None or target.state not in {"published", "compatibility"}:
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

