"""Domain service: benefit_concept_service."""

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


__all__ = ['_derive_description_variant', '_normalize_description_variants', 'serialize_concept', 'list_benefit_concepts', 'save_benefit_concept', 'retire_benefit_concept', 'restore_benefit_concept']


def _derive_description_variant(description_text: str | None) -> list[dict]:
    if not description_text:
        return []
    text = description_text.strip()
    if not text:
        return []
    if "{value}" in text:
        lower_desc = text.lower()
        if any(kw in lower_desc for kw in ("km", "kilometre", "kilometer", "distance", "radius")):
            derived_type = "distance"
        elif any(kw in lower_desc for kw in ("year", "month", "day", "hour", "week", "duration", "period")):
            derived_type = "duration"
        else:
            derived_type = "money"
        return [{"key": "default", "template": text, "value_type": derived_type}]

    # Check for money patterns e.g. "RM 200", "RM200", "RM 1,500.00", "MYR 500"
    m_money = re.search(r"(?:RM|MYR)\s*(\d+(?:,\d+)*(?:\.\d+)?)", text, re.IGNORECASE)
    if m_money:
        tpl = text[:m_money.start()] + re.sub(r"\d+(?:,\d+)*(?:\.\d+)?", "{value}", text[m_money.start():m_money.end()], count=1) + text[m_money.end():]
        return [{"key": "default", "template": tpl, "value_type": "money"}]

    # Check for distance patterns e.g. "50 km", "100km", "50 kilometers"
    m_dist = re.search(r"(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:km|kilometres?|kilometers?)", text, re.IGNORECASE)
    if m_dist:
        tpl = text[:m_dist.start()] + re.sub(r"\d+(?:,\d+)*(?:\.\d+)?", "{value}", text[m_dist.start():m_dist.end()], count=1) + text[m_dist.end():]
        return [{"key": "default", "template": tpl, "value_type": "distance"}]

    # Check for duration patterns e.g. "3 years", "12 months", "1 year"
    m_dur = re.search(r"(\d+)\s*(?:years?|months?|days?|weeks?|hours?)", text, re.IGNORECASE)
    if m_dur:
        tpl = text[:m_dur.start()] + re.sub(r"\d+", "{value}", text[m_dur.start():m_dur.end()], count=1) + text[m_dur.end():]
        return [{"key": "default", "template": tpl, "value_type": "duration"}]

    return [{"key": "default", "template": f"{text} {{value}}", "value_type": "money"}]



def _normalize_description_variants(values) -> list[dict]:
    """Validate up to two description variants: {key, template, value_type, demo_value?}.

    The value type is implied by the template — never asked first. Templates must
    contain the {value} placeholder so extraction and rendering can fill them.
    """
    items = list(values or [])
    if len(items) > 2:
        raise AppError("A benefit can carry at most two description variants.", 422)
    seen: set[str] = set()
    output: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            raise AppError("Description variants must be objects.", 422)
        key = _slug(str(item.get("key") or ""))
        if not key:
            raise AppError("Each description variant requires a key.", 422)
        if key in seen:
            raise AppError("Description variant keys must be unique.", 422)
        seen.add(key)
        template = str(item.get("template") or "").strip()
        if not template or len(template) > 500:
            raise AppError("Each description variant requires a template of at most 500 characters.", 422)
        if "{value}" not in template:
            raise AppError("Description templates must contain the {value} placeholder.", 422)
        value_type = str(item.get("value_type") or "")
        if value_type not in VARIANT_TYPES:
            raise AppError("Variant value type must be money, distance, or duration.", 422)
        demo = item.get("demo_value")
        if demo is not None and not isinstance(demo, dict):
            raise AppError("Variant demo value must be an object.", 422)
        variant: dict = {"key": key, "template": template, "value_type": value_type}
        if demo:
            demo_value = dict(demo)
            if "value" not in demo_value:
                raise AppError("Variant demo values require a sample value.", 422)
            variant["demo_value"] = demo_value
        output.append(variant)
    return output



def serialize_concept(db, item: BenefitConcept, preloaded_assets: dict | None = None) -> dict:
    value_schema = item.value_schema or {}
    category = value_schema.get("category") or ("default" if item.sort_order <= 11 else "addon")
    variants = value_schema.get("variants") or []
    return {
        "id": item.id,
        "concept_key": item.concept_key,
        "label": item.label,
        "category": category,
        "variants": variants,
        "value_schema": item.value_schema,
        "display_template": item.display_template,
        "required_variables": item.required_variables,
        "optional_variables": item.optional_variables,
        "validation_rules": item.validation_rules,
        "description": item.description,
        "demo_value": item.demo_value,
        "match_dataset": item.match_dataset,
        "value_pattern_dataset": item.value_pattern_dataset,
        "description_variants": item.description_variants,
        "display_overrides": item.display_overrides or {},
        "sort_order": item.sort_order,
        "default_asset": _asset_summary(preloaded_assets.get(item.default_asset_id) if preloaded_assets is not None else db.get(BusinessAsset, item.default_asset_id)) if item.default_asset_id else None,
        "revision": item.revision,
        "status": item.status,
    }



def list_benefit_concepts(
    db, user, *, search: str, page: int, page_size: int, visual_profile_id: str | None = None
) -> dict:
    _require_business(user)
    from app.models.tables import GlobalBenefitProfile, GlobalBenefitProfileAsset

    query = select(BenefitConcept)
    count_query = select(func.count()).select_from(BenefitConcept)
    if search.strip():
        pattern = f"%{search.strip()}%"
        predicate = or_(BenefitConcept.label.ilike(pattern), BenefitConcept.concept_key.ilike(pattern))
        query = query.where(predicate)
        count_query = count_query.where(predicate)
    total = int(db.scalar(count_query) or 0)
    rows = db.scalars(query.order_by(BenefitConcept.sort_order.asc(), BenefitConcept.label.asc()).limit(page_size).offset((page - 1) * page_size)).all()

    target_profile_id = visual_profile_id
    if not target_profile_id:
        active_prof = db.scalar(
            select(GlobalBenefitProfile).where(GlobalBenefitProfile.is_active.is_(True))
        )
        if active_prof:
            target_profile_id = active_prof.id

    profile_asset_map: dict[str, str] = {}
    if target_profile_id:
        p_items = db.scalars(
            select(GlobalBenefitProfileAsset).where(
                GlobalBenefitProfileAsset.profile_id == target_profile_id
            )
        ).all()
        profile_asset_map = {str(item.concept_id): str(item.asset_id) for item in p_items}

    asset_ids: set[str] = set()
    for row in rows:
        aid = profile_asset_map.get(str(row.id)) or row.default_asset_id
        if aid:
            asset_ids.add(aid)
        if row.default_asset_id:
            asset_ids.add(row.default_asset_id)

    preloaded_assets: dict[str, BusinessAsset] = {}
    if asset_ids:
        assets = db.scalars(select(BusinessAsset).where(BusinessAsset.id.in_(asset_ids))).all()
        preloaded_assets = {a.id: a for a in assets}

    items = []
    for row in rows:
        target_asset_id = profile_asset_map.get(str(row.id)) or row.default_asset_id
        asset_obj = preloaded_assets.get(target_asset_id) if target_asset_id else None
        if (not asset_obj or asset_obj.status not in ["active", "unassigned"]) and row.default_asset_id:
            asset_obj = preloaded_assets.get(row.default_asset_id)

        serialized = serialize_concept(db, row, preloaded_assets=preloaded_assets)
        if asset_obj:
            serialized["default_asset"] = _asset_summary(asset_obj)
        items.append(serialized)

    return {"items": items, "total": total, "page": page, "page_size": page_size}



def save_benefit_concept(db, user, payload: dict) -> dict:
    _require_business(user)
    concept = None
    if payload.get("id"):
        concept = db.scalar(select(BenefitConcept).where(BenefitConcept.id == payload["id"]).with_for_update())
        if concept is None:
            raise AppError("Benefit concept not found.", 404)
        _require_revision(concept, payload.get("base_revision"), "benefit concept")
    if concept is None:
        concept = BenefitConcept(id=new_id(), concept_key=payload["concept_key"], label=payload["label"])
        db.add(concept)
    asset_id = payload.get("default_asset_id")
    if asset_id and db.get(BusinessAsset, asset_id) is None:
        raise AppError("Benefit artwork was not found.", 422)
    concept.concept_key = _slug(payload["concept_key"])
    concept.label = payload["label"].strip()
    value_schema = dict(payload.get("value_schema") or {})
    if "category" in payload:
        value_schema["category"] = payload["category"]
    if "variants" in payload:
        value_schema["variants"] = payload["variants"]
    concept.value_schema = value_schema
    concept.display_template = payload.get("display_template") or "{label}"
    concept.required_variables = list(dict.fromkeys(payload.get("required_variables") or []))
    concept.optional_variables = list(dict.fromkeys(payload.get("optional_variables") or []))
    concept.validation_rules = payload.get("validation_rules") or {}
    concept.description = payload.get("description")
    demo_value = payload.get("demo_value")
    if demo_value is not None and not isinstance(demo_value, dict):
        raise AppError("Demo value must be a typed value object.", 422)
    concept.demo_value = demo_value
    concept.match_dataset = _normalize_string_list(payload.get("match_dataset"), "Match dataset")
    concept.value_pattern_dataset = _normalize_string_list(payload.get("value_pattern_dataset"), "Value-pattern dataset")
    # Amendment 1: auto-derive description_variants from description when it contains {value}.
    # The UI sends only a plain description string; we derive the hidden shape here.
    if payload.get("description_variants"):
        # Accept explicitly provided variants (e.g. from seed scripts or API callers who know the shape).
        concept.description_variants = _normalize_description_variants(payload.get("description_variants"))
    else:
        concept.description_variants = _derive_description_variant(concept.description)

    concept.sort_order = max(0, int(payload.get("sort_order") or 0))
    concept.default_asset_id = asset_id
    concept.display_overrides = payload.get("display_overrides") or {}
    concept.status = payload.get("status", "active")
    if payload.get("id"):
        concept.revision += 1
    _audit(db, user, "business.benefit_concept.save", "benefit_concept", concept.id, {"new_revision": concept.revision})
    db.commit()
    db.refresh(concept)
    return serialize_concept(db, concept)



def retire_benefit_concept(db, user, concept_id: str) -> None:
    _require_business(user)
    concept = db.scalar(select(BenefitConcept).where(BenefitConcept.id == concept_id).with_for_update())
    if concept is None:
        raise AppError("Benefit concept not found.", 404)
    concept.status = "retired"
    _audit(db, user, "business.benefit_concept.retire", "benefit_concept", concept.id, {"concept_key": concept.concept_key})
    # Cascade status to offerings in draft revisions (published revisions remain immutable)
    draft_rev_ids = list(db.scalars(
        select(BenefitCatalogRevision.id).where(BenefitCatalogRevision.state != "published")
    ).all())
    if draft_rev_ids:
        db.execute(
            update(CatalogOffering)
            .where(
                CatalogOffering.concept_id == concept.id,
                CatalogOffering.catalog_revision_id.in_(draft_rev_ids),
            )
            .values(status="retired")
        )
    db.commit()



def restore_benefit_concept(db, user, concept_id: str) -> dict:
    _require_business(user)
    concept = db.scalar(select(BenefitConcept).where(BenefitConcept.id == concept_id).with_for_update())
    if concept is None:
        raise AppError("Benefit concept not found.", 404)
    concept.status = "active"
    concept.revision += 1
    _audit(db, user, "business.benefit_concept.restore", "benefit_concept", concept.id, {"concept_key": concept.concept_key})
    # Restore offerings in draft revisions
    draft_rev_ids = list(db.scalars(
        select(BenefitCatalogRevision.id).where(BenefitCatalogRevision.state != "published")
    ).all())
    if draft_rev_ids:
        db.execute(
            update(CatalogOffering)
            .where(
                CatalogOffering.concept_id == concept.id,
                CatalogOffering.catalog_revision_id.in_(draft_rev_ids),
            )
            .values(status="active")
        )
    db.commit()
    db.refresh(concept)
    return serialize_concept(db, concept)

