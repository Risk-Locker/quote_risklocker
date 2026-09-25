"""Shared constants and helpers for workspace services."""

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




SCALAR_DECISIONS = frozenset({"confirm", "edit", "clear", "keep_check_needed"})
SELECTION_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,159}$")
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
BUSINESS_ROLES = frozenset({Role.STAFF.value, Role.ADMIN.value, Role.SUPER_ADMIN.value})
PIN_SENSITIVE_FIELDS = frozenset({"insurance_company", "product_name", "product", "tier_name", "product_tier", "plan_name"})
MONEY_FIELDS = frozenset({
    "coverage_amount", "sum_insured", "market_value", "agreed_value", "excess_amount", "basic_premium_vehicle",
    "premium", "coverage_premium", "ncd_amount", "loading_amount", "all_riders_amount", "optional_cover_amount",
    "service_tax", "stamp_duty", "gross_premium", "roadtax", "road_tax_amount", "service_fee", "runner_fee", "total_amount",
})
DATE_FIELDS = frozenset({"issue_date", "valid_until", "cover_start_date", "cover_end_date"})
TOTAL_SOURCES = frozenset({"premium", "coverage_premium", "roadtax", "road_tax_amount", "service_fee", "runner_fee"})


__all__ = ['_utcnow', '_require_business_user', '_session_and_draft', '_rows_for_draft', '_template_for_draft', '_field_summary', 'generation_blockers', 'SCALAR_DECISIONS', 'SELECTION_KEY_RE', '_UUID_RE', 'BUSINESS_ROLES', 'PIN_SENSITIVE_FIELDS', 'MONEY_FIELDS', 'DATE_FIELDS', 'TOTAL_SOURCES']


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)



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
    if draft.layout_override is not None and draft.layout_override_template_revision_id:
        rev = db.get(TemplateRevision, draft.layout_override_template_revision_id)
        if rev:
            return rev

    if draft.template_revision_id:
        rev = db.get(TemplateRevision, draft.template_revision_id)
        if rev:
            latest_revs = list(
                db.scalars(
                    select(TemplateRevision)
                    .where(
                        TemplateRevision.template_id == rev.template_id,
                        TemplateRevision.state.in_(["published", "compatibility"]),
                    )
                    .order_by(TemplateRevision.revision_number.desc())
                ).all()
            )
            if latest_revs:
                return latest_revs[0]
            return rev
    # Look for active template marked is_default=True or agency_bilingual
    templates = list(
        db.scalars(select(OutputTemplateConfig).where(OutputTemplateConfig.deleted_at.is_(None))).all()
    )
    default_tmpl = next(
        (t for t in templates if bool((t.fixed_fields or {}).get("is_default"))),
        next(
            (t for t in templates if (t.fixed_fields or {}).get("v7_master_key") == "agency_bilingual" or "bilingual" in t.name.lower()),
            None,
        ),
    )
    if default_tmpl:
        found_revs = list(
            db.scalars(
                select(TemplateRevision)
                .where(
                    TemplateRevision.template_id == default_tmpl.id,
                    TemplateRevision.state.in_(["published", "compatibility"]),
                )
                .order_by(TemplateRevision.revision_number.desc())
            ).all()
        )
        if found_revs:
            return found_revs[0]

    all_revs = list(
        db.scalars(
            select(TemplateRevision)
            .where(TemplateRevision.state.in_(["published", "compatibility"]))
            .order_by(TemplateRevision.revision_number.desc())
        ).all()
    )
    return all_revs[0] if all_revs else None



def _field_summary(draft: QuotationDraft, session_ref: str | None = None) -> dict[str, dict]:
    output: dict[str, dict] = {}
    rec_candidates: dict = {}
    if draft.uploaded_file and getattr(draft.uploaded_file, "extraction_record", None):
        rec_candidates = getattr(draft.uploaded_file.extraction_record, "candidates", {}) or {}

    for name, value in (draft.fields or {}).items():
        field = value if isinstance(value, dict) else {"value": value}
        det_val = field.get("detected_value")
        if det_val is None:
            cands = rec_candidates.get(name) or []
            if cands and isinstance(cands, list) and isinstance(cands[0], dict):
                det_val = cands[0].get("value")
            if det_val is None:
                det_val = field.get("value")
        output[name] = {
            "value": field.get("value"),
            "detected_value": det_val,
            "status": field.get("status", "check_needed"),
            "message": field.get("message", ""),
            "decision": (draft.scalar_decisions or {}).get(name),
        }
    current_qref = output.get("quotation_reference", {}).get("value")
    if (not current_qref or not str(current_qref).startswith("RL")) and session_ref and session_ref.startswith("RL"):
        output["quotation_reference"] = {
            "value": session_ref,
            "detected_value": session_ref,
            "status": "ready",
            "message": "",
            "decision": None,
        }
    return output



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

