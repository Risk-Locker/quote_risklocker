"""Domain service: company_benefit_bundle_service."""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.core.errors import AppError
from app.models.tables import (
    BenefitConcept,
    BenefitProfile,
    CompanyBenefitBundle,
    CompanyBenefitBundleEffect,
    CompanyBenefitBundleTier,
    InsuranceCompany,
    new_id,
    utcnow,
)
from app.services.benefit_profile_service import get_active_benefit_profile
from app.services.business_setup_common import (
    _audit,
    _normalize_string_list,
    _require_business,
    _slug,
)

__all__ = [
    "BUNDLE_EFFECT_TYPES",
    "load_active_company_bundles",
    "serialize_bundle",
    "list_company_bundles",
    "save_company_bundle",
    "delete_company_bundle",
]

BUNDLE_EFFECT_TYPES = frozenset({"upgrade_to_box2", "add_to_box2", "hide_from_box1"})


def serialize_bundle(bundle: CompanyBenefitBundle) -> dict[str, Any]:
    """Serialize a bundle along with ordered tiers and effects."""
    tiers = sorted(
        list(getattr(bundle, "tiers", None) or []),
        key=lambda t: (int(getattr(t, "sort_order", 0) or 0), str(getattr(t, "tier_key", "") or "")),
    )
    return {
        "id": bundle.id,
        "company_id": bundle.company_id,
        "profile_id": bundle.profile_id,
        "bundle_key": bundle.bundle_key,
        "name": bundle.name,
        "primary_concept_id": bundle.primary_concept_id,
        "trigger_concept_ids": list(bundle.trigger_concept_ids or []),
        "match_aliases": list(bundle.match_aliases or []),
        "catalog_scope": bundle.catalog_scope,
        "force_box2": bool(bundle.force_box2),
        "has_plan_tiers": bool(bundle.has_plan_tiers),
        "is_active": bool(bundle.is_active),
        "sort_order": int(bundle.sort_order or 0),
        "created_at": bundle.created_at.isoformat() if getattr(bundle, "created_at", None) else None,
        "updated_at": bundle.updated_at.isoformat() if getattr(bundle, "updated_at", None) else None,
        "tiers": [
            {
                "id": t.id,
                "bundle_id": t.bundle_id,
                "tier_key": t.tier_key,
                "label": t.label,
                "display_title": getattr(t, "display_title", None),
                "display_description": getattr(t, "display_description", None),
                "match_tokens": list(t.match_tokens or []),
                "is_default_fallback": bool(t.is_default_fallback),
                "sort_order": int(t.sort_order or 0),
                "effects": [
                    {
                        "id": e.id,
                        "tier_id": e.tier_id,
                        "target_concept_id": e.target_concept_id,
                        "effect_type": e.effect_type,
                        "display_title": e.display_title,
                        "display_value": e.display_value,
                        "display_description": e.display_description,
                        "icon_hint": e.icon_hint,
                        "comparison_value": e.comparison_value,
                        "sort_order": int(e.sort_order or 0),
                    }
                    for e in sorted(
                        list(getattr(t, "effects", None) or []),
                        key=lambda eff: (int(getattr(eff, "sort_order", 0) or 0), str(getattr(eff, "id", ""))),
                    )
                ],
            }
            for t in tiers
        ],
    }


def load_active_company_bundles(
    db: Any,
    company_id: str | None,
    profile_id: str | None = None,
) -> list[CompanyBenefitBundle]:
    """Load active CompanyBenefitBundle rows (with tiers & effects) safely across real/mock DBs."""
    if not company_id or db is None:
        return []
    try:
        active_prof_id = profile_id
        if active_prof_id is None:
            prof_stmt = select(BenefitProfile.id).where(BenefitProfile.is_active.is_(True))
            if hasattr(db, "scalars"):
                active_prof_id = db.scalars(prof_stmt).first()
            elif hasattr(db, "execute"):
                res = db.execute(prof_stmt)
                active_prof_id = res.scalars().first() if hasattr(res, "scalars") else None

        stmt = (
            select(CompanyBenefitBundle)
            .where(
                CompanyBenefitBundle.company_id == company_id,
                CompanyBenefitBundle.is_active.is_(True),
            )
            .options(
                selectinload(CompanyBenefitBundle.tiers).selectinload(CompanyBenefitBundleTier.effects)
            )
            .order_by(CompanyBenefitBundle.sort_order.asc(), CompanyBenefitBundle.name.asc())
        )
        if active_prof_id:
            stmt = stmt.where(
                or_(
                    CompanyBenefitBundle.profile_id == active_prof_id,
                    CompanyBenefitBundle.profile_id.is_(None),
                )
            )
        else:
            stmt = stmt.where(CompanyBenefitBundle.profile_id.is_(None))

        if hasattr(db, "scalars"):
            rows = list(db.scalars(stmt).all())
        elif hasattr(db, "execute"):
            res = db.execute(stmt)
            rows = list(res.scalars().all()) if hasattr(res, "scalars") else []
        else:
            rows = []
        # Touch relationships while session is active so downstream callers never hit detached lazy loads
        for b in rows:
            for t in list(getattr(b, "tiers", None) or []):
                list(getattr(t, "effects", None) or [])
        return rows
    except Exception:
        return []


def list_company_bundles(db: Any, user: Any, company_id: str, profile_id: str | None = None) -> list[dict[str, Any]]:
    _require_business(user)
    if profile_id:
        target_profile = db.get(BenefitProfile, profile_id)
        if target_profile is None:
            raise AppError("Profile not found.", 404)
        active_prof_id = target_profile.id
    else:
        active_prof_id = db.scalars(
            select(BenefitProfile.id).where(BenefitProfile.is_active.is_(True))
        ).first()
        if not active_prof_id:
            return []

    stmt = (
        select(CompanyBenefitBundle)
        .where(
            CompanyBenefitBundle.company_id == company_id,
            CompanyBenefitBundle.profile_id == active_prof_id,
        )
        .options(
            selectinload(CompanyBenefitBundle.tiers).selectinload(CompanyBenefitBundleTier.effects)
        )
        .order_by(CompanyBenefitBundle.sort_order.asc(), CompanyBenefitBundle.name.asc())
    )
    bundles = list(db.scalars(stmt).all())
    return [serialize_bundle(b) for b in bundles]


def _validate_concept_exists(db: Any, concept_id: str, label: str) -> str:
    cid = str(concept_id or "").strip()
    if not cid or db.get(BenefitConcept, cid) is None:
        raise AppError(f"{label} benefit concept is invalid.", 422)
    return cid


def save_company_bundle(
    db: Any,
    user: Any,
    company_id: str,
    payload: dict[str, Any],
    profile_id: str | None = None,
) -> dict[str, Any]:
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
        raise AppError("Bundle name is required.", 422)

    bundle_key = (_slug(str(payload.get("bundle_key") or name)) or "bundle")[:120]
    primary_concept_id = _validate_concept_exists(db, str(payload.get("primary_concept_id") or ""), "Primary")

    raw_triggers = payload.get("trigger_concept_ids") or []
    trigger_concept_ids: list[str] = [primary_concept_id]
    for raw_cid in raw_triggers:
        cid = _validate_concept_exists(db, str(raw_cid or ""), "Trigger")
        if cid not in trigger_concept_ids:
            trigger_concept_ids.append(cid)

    match_aliases = _normalize_string_list(payload.get("match_aliases"), "Match aliases")
    catalog_scope_raw = payload.get("catalog_scope")
    catalog_scope = catalog_scope_raw.strip() or None if isinstance(catalog_scope_raw, str) else None
    force_box2 = bool(payload.get("force_box2", True))
    has_plan_tiers = bool(payload.get("has_plan_tiers", False))
    is_active = bool(payload.get("is_active", True))
    sort_order = max(0, int(payload.get("sort_order") or 0))

    raw_tiers = list(payload.get("tiers") or [])
    if not raw_tiers:
        raise AppError("At least one plan tier (or Default tier) is required.", 422)

    normalized_tiers: list[dict[str, Any]] = []
    seen_tier_keys: set[str] = set()
    has_fallback = False
    for idx, t_raw in enumerate(raw_tiers):
        if not isinstance(t_raw, dict):
            continue
        t_label = str(t_raw.get("label") or "").strip() or ("Default" if not has_plan_tiers else f"Plan {idx + 1}")
        t_key = (_slug(str(t_raw.get("tier_key") or t_label)) or f"tier_{idx + 1}").replace("-", "_")[:80]
        if t_key in seen_tier_keys:
            t_key = f"{t_key[:70]}_{idx + 1}"
        seen_tier_keys.add(t_key)
        is_fb = bool(t_raw.get("is_default_fallback", False))
        if is_fb:
            has_fallback = True

        raw_effects = list(t_raw.get("effects") or [])
        norm_effects: list[dict[str, Any]] = []
        for eff_idx, eff_raw in enumerate(raw_effects):
            if not isinstance(eff_raw, dict):
                continue
            target_cid = _validate_concept_exists(db, str(eff_raw.get("target_concept_id") or ""), "Effect target")
            eff_type = str(eff_raw.get("effect_type") or "upgrade_to_box2").strip()
            if eff_type not in BUNDLE_EFFECT_TYPES:
                raise AppError("Invalid bundle effect type.", 422)
            disp_title = str(eff_raw.get("display_title") or "").strip() or None
            disp_val = str(eff_raw.get("display_value") or "").strip() if eff_raw.get("display_value") is not None else None
            if disp_val == "":
                disp_val = ""
            disp_desc = str(eff_raw.get("display_description") or "").strip() or None
            icon_hint = str(eff_raw.get("icon_hint") or "").strip() or None
            comp_val = str(eff_raw.get("comparison_value") or "").strip() or None
            norm_effects.append(
                {
                    "id": str(eff_raw.get("id") or "").strip() or None,
                    "target_concept_id": target_cid,
                    "effect_type": eff_type,
                    "display_title": disp_title,
                    "display_value": disp_val,
                    "display_description": disp_desc,
                    "icon_hint": icon_hint,
                    "comparison_value": comp_val,
                    "sort_order": max(0, int(eff_raw.get("sort_order") if eff_raw.get("sort_order") is not None else eff_idx)),
                }
            )
        disp_t_title = str(t_raw.get("display_title") or "").strip() or None
        disp_t_desc = str(t_raw.get("display_description") or "").strip() or None
        normalized_tiers.append(
            {
                "id": str(t_raw.get("id") or "").strip() or None,
                "tier_key": t_key,
                "label": t_label,
                "display_title": disp_t_title,
                "display_description": disp_t_desc,
                "match_tokens": _normalize_string_list(t_raw.get("match_tokens"), "Match tokens"),
                "is_default_fallback": is_fb,
                "sort_order": max(0, int(t_raw.get("sort_order") if t_raw.get("sort_order") is not None else idx)),
                "effects": norm_effects,
            }
        )

    if not has_fallback and normalized_tiers:
        normalized_tiers[0]["is_default_fallback"] = True

    bundle_id = str(payload.get("id") or "").strip() or None
    if bundle_id:
        bundle = db.scalar(
            select(CompanyBenefitBundle)
            .where(
                CompanyBenefitBundle.id == bundle_id,
                CompanyBenefitBundle.company_id == company_id,
            )
            .with_for_update()
        )
        if bundle is None:
            raise AppError("Bundle not found.", 404)
        bundle.profile_id = target_profile.id
        bundle.bundle_key = bundle_key
        bundle.name = name
        bundle.primary_concept_id = primary_concept_id
        bundle.trigger_concept_ids = trigger_concept_ids
        bundle.match_aliases = match_aliases
        bundle.catalog_scope = catalog_scope
        bundle.force_box2 = force_box2
        bundle.has_plan_tiers = has_plan_tiers
        bundle.is_active = is_active
        bundle.sort_order = sort_order
        bundle.updated_at = utcnow()
    else:
        existing_key = db.scalar(
            select(CompanyBenefitBundle).where(
                CompanyBenefitBundle.company_id == company_id,
                CompanyBenefitBundle.profile_id == target_profile.id,
                CompanyBenefitBundle.bundle_key == bundle_key,
            )
        )
        if existing_key is not None:
            raise AppError(f"A bundle with key '{bundle_key}' already exists in this profile.", 409)
        bundle = CompanyBenefitBundle(
            id=new_id(),
            company_id=company_id,
            profile_id=target_profile.id,
            bundle_key=bundle_key,
            name=name,
            primary_concept_id=primary_concept_id,
            trigger_concept_ids=trigger_concept_ids,
            match_aliases=match_aliases,
            catalog_scope=catalog_scope,
            force_box2=force_box2,
            has_plan_tiers=has_plan_tiers,
            is_active=is_active,
            sort_order=sort_order,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(bundle)
        db.flush()

    existing_tiers_by_id = {
        str(t.id): t
        for t in db.scalars(
            select(CompanyBenefitBundleTier).where(CompanyBenefitBundleTier.bundle_id == bundle.id)
        ).all()
    }
    kept_tier_ids: set[str] = set()
    for t_data in normalized_tiers:
        t_obj = existing_tiers_by_id.get(str(t_data["id"])) if t_data["id"] else None
        if t_obj is None:
            t_obj = CompanyBenefitBundleTier(
                id=new_id(),
                bundle_id=bundle.id,
                tier_key=t_data["tier_key"],
                label=t_data["label"],
                display_title=t_data["display_title"],
                display_description=t_data["display_description"],
                match_tokens=t_data["match_tokens"],
                is_default_fallback=t_data["is_default_fallback"],
                sort_order=t_data["sort_order"],
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            db.add(t_obj)
            db.flush()
        else:
            t_obj.tier_key = t_data["tier_key"]
            t_obj.label = t_data["label"]
            t_obj.display_title = t_data["display_title"]
            t_obj.display_description = t_data["display_description"]
            t_obj.match_tokens = t_data["match_tokens"]
            t_obj.is_default_fallback = t_data["is_default_fallback"]
            t_obj.sort_order = t_data["sort_order"]
            t_obj.updated_at = utcnow()
        kept_tier_ids.add(t_obj.id)

        existing_effs = list(
            db.scalars(
                select(CompanyBenefitBundleEffect).where(CompanyBenefitBundleEffect.tier_id == t_obj.id)
            ).all()
        )
        for old_eff in existing_effs:
            db.delete(old_eff)
        db.flush()

        for eff_data in t_data["effects"]:
            db.add(
                CompanyBenefitBundleEffect(
                    id=new_id(),
                    tier_id=t_obj.id,
                    target_concept_id=eff_data["target_concept_id"],
                    effect_type=eff_data["effect_type"],
                    display_title=eff_data["display_title"],
                    display_value=eff_data["display_value"],
                    display_description=eff_data["display_description"],
                    icon_hint=eff_data["icon_hint"],
                    comparison_value=eff_data["comparison_value"],
                    sort_order=eff_data["sort_order"],
                    created_at=utcnow(),
                    updated_at=utcnow(),
                )
            )

    for old_tid, old_tier in existing_tiers_by_id.items():
        if old_tid not in kept_tier_ids:
            db.delete(old_tier)

    _audit(db, user, "business.company.bundle.save", "company_benefit_bundle", bundle.id, {"name": bundle.name})
    db.commit()

    refreshed = db.scalar(
        select(CompanyBenefitBundle)
        .where(CompanyBenefitBundle.id == bundle.id)
        .options(selectinload(CompanyBenefitBundle.tiers).selectinload(CompanyBenefitBundleTier.effects))
    )
    return serialize_bundle(refreshed or bundle)


def delete_company_bundle(db: Any, user: Any, company_id: str, bundle_id: str) -> None:
    _require_business(user)
    bundle = db.scalar(
        select(CompanyBenefitBundle)
        .where(
            CompanyBenefitBundle.id == bundle_id,
            CompanyBenefitBundle.company_id == company_id,
        )
        .with_for_update()
    )
    if bundle is None:
        raise AppError("Bundle not found.", 404)

    if bundle.profile and bundle.profile.status == "archived":
        raise AppError("Cannot modify an archived profile. Clone it to create a new draft.", 400)

    db.delete(bundle)
    _audit(db, user, "business.company.bundle.delete", "company_benefit_bundle", bundle_id, {"company_id": company_id})
    db.commit()
