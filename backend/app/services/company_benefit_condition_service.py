"""Domain service: company_benefit_condition_service."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from collections import defaultdict

from sqlalchemy import delete, func, or_, select, text, update

from app.core.cache import _memory_cache, invalidate_cache
from app.core.errors import AppError
from app.domain.benefits import BenefitValue
from app.models.enums import Role
from app.models.tables import (
    AuditEvent,
    BenefitAlias,
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    BenefitPackage,
    BenefitPackagePlan,
    BenefitPackagePlanItem,
    BenefitRelation,
    BusinessAsset,
    CatalogOffering,
    CompanyAlias,
    CompanyBenefitCondition,
    CompanyBenefitConfig,
    BenefitProfile,
    CompanyBenefitProfile,
    GlobalBenefitProfile,
    GlobalBenefitProfileAsset,
    InsuranceCompany,
    InsuranceProduct,
    InsuranceProductTier,
    QuotationDraft,
    DraftBenefitSelection,
    SourceDocument,
    new_id,
    utcnow,
)
from app.rendering.render_context import canonical_context_hash
from app.services.asset_intake import create_derivative, validate_image_bytes
from app.storage.supabase import SupabaseStorage




from app.services.business_setup_common import (
    BUSINESS_ROLES, OFFERING_KINDS, STATUSES, ALIAS_KINDS, VARIANT_TYPES,
    _require_business, _slug, _require_revision, _audit, _asset_summary, _normalize_string_list
)

from app.services.benefit_profile_service import get_active_benefit_profile


__all__ = ['list_company_conditions', 'save_company_condition', 'delete_company_condition']


def list_company_conditions(db, user, company_id: str, profile_id: str | None = None) -> list[dict]:
    _require_business(user)
    if profile_id:
        target_profile = db.get(BenefitProfile, profile_id)
        if target_profile is None:
            raise AppError("Profile not found.", 404)
        active_prof_id = target_profile.id
    else:
        active_prof_id = get_active_benefit_profile(db).id

    conditions = list(
        db.scalars(
            select(CompanyBenefitCondition)
            .where(
                CompanyBenefitCondition.company_id == company_id,
                CompanyBenefitCondition.profile_id == active_prof_id,
            )
            .order_by(CompanyBenefitCondition.created_at.asc())
        ).all()
    )
    return [
        {
            "id": c.id,
            "company_id": c.company_id,
            "profile_id": c.profile_id,
            "name": c.name,
            "trigger_concept_id": c.trigger_concept_id,
            "trigger_plan_filter": c.trigger_plan_filter,
            "target_concept_id": c.target_concept_id,
            "action_type": getattr(c, "action_type", "replace_description") or "replace_description",
            "replacement_description": c.replacement_description,
            "is_active": c.is_active,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in conditions
    ]



def save_company_condition(db, user, company_id: str, payload: dict, profile_id: str | None = None) -> dict:
    _require_business(user)
    company = db.get(InsuranceCompany, company_id)
    if company is None:
        raise AppError("Company not found.", 404)

    if profile_id:
        target_profile = db.get(BenefitProfile, profile_id)
        if target_profile is None:
            raise AppError("Profile not found.", 404)
    else:
        target_profile = get_active_benefit_profile(db)

    if target_profile.status == "archived":
        raise AppError("Cannot modify an archived profile. Clone it to create a new draft.", 400)

    name = str(payload.get("name") or "").strip()
    if not name:
        raise AppError("Condition name is required.", 422)

    trigger_concept_id = payload.get("trigger_concept_id")
    if not trigger_concept_id or db.get(BenefitConcept, trigger_concept_id) is None:
        raise AppError("Trigger benefit concept is invalid.", 422)

    target_concept_id = payload.get("target_concept_id")
    if not target_concept_id or db.get(BenefitConcept, target_concept_id) is None:
        raise AppError("Target benefit concept is invalid.", 422)

    action_type = str(payload.get("action_type") or "replace_description").strip()
    if action_type not in {"replace_description", "hide_target"}:
        action_type = "replace_description"

    replacement_desc = str(payload.get("replacement_description") or "").strip()
    if action_type == "hide_target":
        replacement_desc = replacement_desc or "[Hidden by condition rule]"
    elif not replacement_desc:
        raise AppError("Replacement description is required.", 422)

    trigger_plan_filter = payload.get("trigger_plan_filter")
    if isinstance(trigger_plan_filter, str):
        trigger_plan_filter = trigger_plan_filter.strip() or None
    else:
        trigger_plan_filter = None

    is_active = bool(payload.get("is_active", True))

    cond_id = payload.get("id")
    if cond_id:
        cond = db.scalar(
            select(CompanyBenefitCondition).where(
                CompanyBenefitCondition.id == cond_id,
                CompanyBenefitCondition.company_id == company_id,
            ).with_for_update()
        )
        if cond is None:
            raise AppError("Condition not found.", 404)
        cond.name = name
        cond.profile_id = target_profile.id
        cond.trigger_concept_id = trigger_concept_id
        cond.trigger_plan_filter = trigger_plan_filter
        cond.target_concept_id = target_concept_id
        cond.action_type = action_type
        cond.replacement_description = replacement_desc
        cond.is_active = is_active
        cond.updated_at = utcnow()
    else:
        cond = CompanyBenefitCondition(
            id=new_id(),
            company_id=company_id,
            profile_id=target_profile.id,
            name=name,
            trigger_concept_id=trigger_concept_id,
            trigger_plan_filter=trigger_plan_filter,
            target_concept_id=target_concept_id,
            action_type=action_type,
            replacement_description=replacement_desc,
            is_active=is_active,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(cond)

    _audit(db, user, "business.company.condition.save", "company_benefit_condition", cond.id, {"name": cond.name})
    db.commit()
    db.refresh(cond)
    return {
        "id": cond.id,
        "company_id": cond.company_id,
        "profile_id": cond.profile_id,
        "name": cond.name,
        "trigger_concept_id": cond.trigger_concept_id,
        "trigger_plan_filter": cond.trigger_plan_filter,
        "target_concept_id": cond.target_concept_id,
        "action_type": cond.action_type,
        "replacement_description": cond.replacement_description,
        "is_active": cond.is_active,
    }



def delete_company_condition(db, user, company_id: str, condition_id: str) -> None:
    _require_business(user)
    cond = db.scalar(
        select(CompanyBenefitCondition).where(
            CompanyBenefitCondition.id == condition_id,
            CompanyBenefitCondition.company_id == company_id,
        ).with_for_update()
    )
    if cond is None:
        raise AppError("Condition not found.", 404)

    if cond.profile and cond.profile.status == "archived":
        raise AppError("Cannot modify an archived profile. Clone it to create a new draft.", 400)

    db.delete(cond)
    _audit(db, user, "business.company.condition.delete", "company_benefit_condition", condition_id, {"company_id": company_id})
    db.commit()

