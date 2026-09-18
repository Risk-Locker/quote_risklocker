"""Service for managing Global Benefit Visual Profiles, Category-bound asset mappings, and health monitoring."""

from __future__ import annotations

import re
from typing import Any
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth.rbac import require_role
from app.core.errors import AppError
from app.models.enums import Role
from app.models.tables import (
    AuditEvent,
    BenefitConcept,
    BusinessAsset,
    GlobalBenefitProfile,
    GlobalBenefitProfileAsset,
    User,
    new_id,
    utcnow,
)


def _require_business(user: Any) -> None:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF)


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _audit(db: Session, user: Any, action: str, entity_type: str, entity_id: str, details: dict) -> None:
    event = AuditEvent(
        id=new_id(),
        actor_id=user.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(event)


def get_active_visual_profile(db: Session) -> GlobalBenefitProfile | None:
    return db.scalar(
        select(GlobalBenefitProfile).where(GlobalBenefitProfile.is_active.is_(True))
    )


def get_active_visual_profile_asset_map(db: Session) -> dict[str, str]:
    """Returns a map of concept_id -> asset_id for the active visual profile."""
    active_profile = get_active_visual_profile(db)
    if not active_profile:
        return {}
    rows = db.scalars(
        select(GlobalBenefitProfileAsset).where(
            GlobalBenefitProfileAsset.profile_id == active_profile.id
        )
    ).all()
    return {r.concept_id: r.asset_id for r in rows}


def list_global_benefit_profiles(db: Session, user: Any) -> list[dict]:
    _require_business(user)
    profiles = list(
        db.scalars(
            select(GlobalBenefitProfile).order_by(
                GlobalBenefitProfile.is_active.desc(),
                GlobalBenefitProfile.created_at.desc(),
            )
        ).all()
    )

    all_concepts = list(
        db.scalars(
            select(BenefitConcept).where(BenefitConcept.status != "retired")
        ).all()
    )
    total_concepts = len(all_concepts)

    result = []
    for p in profiles:
        items = list(
            db.scalars(
                select(GlobalBenefitProfileAsset).where(
                    GlobalBenefitProfileAsset.profile_id == p.id
                )
            ).all()
        )
        asset_ids = {item.asset_id for item in items}
        active_assets = set(
            db.scalars(
                select(BusinessAsset.id).where(
                    BusinessAsset.id.in_(asset_ids),
                    BusinessAsset.status.in_(["active", "unassigned"]),
                )
            ).all()
        ) if asset_ids else set()

        missing_count = sum(1 for item in items if item.asset_id not in active_assets)
        mapped_count = sum(1 for item in items if item.asset_id in active_assets)

        result.append({
            "id": p.id,
            "name": p.name,
            "slug": p.slug,
            "description": p.description,
            "asset_category": p.asset_category,
            "is_active": p.is_active,
            "status": p.status,
            "total_concepts": total_concepts,
            "mapped_count": mapped_count,
            "missing_count": missing_count,
            "is_complete": mapped_count == total_concepts and missing_count == 0,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        })
    return result


def get_global_benefit_profile_detail(db: Session, user: Any, profile_id: str) -> dict:
    _require_business(user)
    profile = db.get(GlobalBenefitProfile, profile_id)
    if not profile:
        raise AppError("Visual profile not found.", 404)

    all_concepts = list(
        db.scalars(
            select(BenefitConcept).where(BenefitConcept.status != "retired").order_by(BenefitConcept.sort_order)
        ).all()
    )
    items = list(
        db.scalars(
            select(GlobalBenefitProfileAsset).where(
                GlobalBenefitProfileAsset.profile_id == profile.id
            )
        ).all()
    )
    items_by_concept = {item.concept_id: item for item in items}
    asset_ids = {item.asset_id for item in items}
    assets_by_id = {
        a.id: a for a in db.scalars(select(BusinessAsset).where(BusinessAsset.id.in_(asset_ids))).all()
    } if asset_ids else {}

    concept_items = []
    missing_assets_count = 0
    for c in all_concepts:
        bound_item = items_by_concept.get(c.id)
        asset = assets_by_id.get(bound_item.asset_id) if bound_item else None
        is_missing = False
        if bound_item:
            if not asset or asset.status not in ["active", "unassigned"]:
                is_missing = True
                missing_assets_count += 1

        concept_items.append({
            "concept_id": c.id,
            "concept_key": c.concept_key,
            "label": c.label,
            "sort_order": c.sort_order,
            "category": c.description_variants if isinstance(c.description_variants, str) else ("default" if c.sort_order <= 11 else "addon"),
            "assigned_asset": {
                "id": asset.id,
                "label": asset.label,
                "category": asset.category,
                "url": f"/business/assets/{asset.id}/content?profile=ui",
            } if asset and not is_missing else None,
            "is_missing": is_missing,
            "has_override": bound_item is not None,
        })

    return {
        "profile": {
            "id": profile.id,
            "name": profile.name,
            "slug": profile.slug,
            "description": profile.description,
            "asset_category": profile.asset_category,
            "is_active": profile.is_active,
            "status": profile.status,
            "missing_assets_count": missing_assets_count,
            "total_concepts": len(all_concepts),
            "mapped_concepts": len(items) - missing_assets_count,
            "created_at": profile.created_at.isoformat() if profile.created_at else None,
            "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        },
        "concepts": concept_items,
    }


def create_global_benefit_profile(db: Session, user: Any, payload: dict) -> dict:
    _require_business(user)
    name = str(payload.get("name") or "").strip()
    if not name:
        raise AppError("Profile name is required.", 422)

    asset_category = str(payload.get("asset_category") or "").strip()
    if not asset_category:
        raise AppError("An asset category/folder must be selected for this visual profile.", 422)

    base_slug = _slugify(name)
    slug = base_slug
    counter = 1
    while db.scalar(select(GlobalBenefitProfile).where(GlobalBenefitProfile.slug == slug)):
        slug = f"{base_slug}-{counter}"
        counter += 1

    profile = GlobalBenefitProfile(
        id=new_id(),
        name=name,
        slug=slug,
        description=str(payload.get("description") or "").strip() or None,
        asset_category=asset_category,
        is_active=False,
        status="draft",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(profile)
    _audit(db, user, "business.visual_profile.create", "global_benefit_profile", profile.id, {"name": name, "category": asset_category})
    db.commit()
    db.refresh(profile)
    return get_global_benefit_profile_detail(db, user, profile.id)


def clone_global_benefit_profile(db: Session, user: Any, profile_id: str, payload: dict) -> dict:
    _require_business(user)
    source = db.get(GlobalBenefitProfile, profile_id)
    if not source:
        raise AppError("Source visual profile not found.", 404)

    name = str(payload.get("name") or "").strip()
    if not name:
        name = f"Clone of {source.name}"

    asset_category = str(payload.get("asset_category") or "").strip() or source.asset_category

    base_slug = _slugify(name)
    slug = base_slug
    counter = 1
    while db.scalar(select(GlobalBenefitProfile).where(GlobalBenefitProfile.slug == slug)):
        slug = f"{base_slug}-{counter}"
        counter += 1

    clone = GlobalBenefitProfile(
        id=new_id(),
        name=name,
        slug=slug,
        description=str(payload.get("description") or "").strip() or source.description,
        asset_category=asset_category,
        is_active=False,
        status="draft",
        cloned_from_id=source.id,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(clone)
    db.flush()

    # Duplicate concept bindings
    source_items = db.scalars(
        select(GlobalBenefitProfileAsset).where(GlobalBenefitProfileAsset.profile_id == source.id)
    ).all()
    for item in source_items:
        clone_item = GlobalBenefitProfileAsset(
            id=new_id(),
            profile_id=clone.id,
            concept_id=item.concept_id,
            asset_id=item.asset_id,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(clone_item)

    _audit(db, user, "business.visual_profile.clone", "global_benefit_profile", clone.id, {"source_id": source.id, "name": name})
    db.commit()
    db.refresh(clone)
    return get_global_benefit_profile_detail(db, user, clone.id)


def activate_global_benefit_profile(db: Session, user: Any, profile_id: str) -> dict:
    _require_business(user)
    target = db.get(GlobalBenefitProfile, profile_id)
    if not target:
        raise AppError("Visual profile not found.", 404)

    # Deactivate all others
    active_profiles = db.scalars(
        select(GlobalBenefitProfile).where(GlobalBenefitProfile.is_active.is_(True))
    ).all()
    for p in active_profiles:
        if p.id != target.id:
            p.is_active = False

    target.is_active = True
    target.status = "active"
    target.updated_at = utcnow()
    _audit(db, user, "business.visual_profile.activate", "global_benefit_profile", target.id, {"name": target.name})
    db.commit()
    db.refresh(target)
    return get_global_benefit_profile_detail(db, user, target.id)


def delete_global_benefit_profile(db: Session, user: Any, profile_id: str) -> None:
    _require_business(user)
    target = db.get(GlobalBenefitProfile, profile_id)
    if not target:
        raise AppError("Visual profile not found.", 404)
    if target.is_active:
        raise AppError("Cannot delete the currently active visual profile.", 422)

    _audit(db, user, "business.visual_profile.delete", "global_benefit_profile", target.id, {"name": target.name})
    db.delete(target)
    db.commit()


def auto_assign_category_assets(db: Session, user: Any, profile_id: str) -> dict:
    """Matches images in the profile's asset category against all global concepts using fuzzy matching."""
    _require_business(user)
    profile = db.get(GlobalBenefitProfile, profile_id)
    if not profile:
        raise AppError("Visual profile not found.", 404)

    # Fetch available assets strictly in this category
    category_assets = list(
        db.scalars(
            select(BusinessAsset).where(
                BusinessAsset.category == profile.asset_category,
                BusinessAsset.status.in_(["active", "unassigned"]),
            )
        ).all()
    )

    concepts = list(
        db.scalars(
            select(BenefitConcept).where(BenefitConcept.status != "retired").order_by(BenefitConcept.sort_order)
        ).all()
    )

    # Build match dictionary
    matches = []
    used_asset_ids: set[str] = set()

    for c in concepts:
        c_slug = _slugify(c.label)
        c_key_slug = _slugify(c.concept_key)
        c_words = set(re.findall(r"\w+", f"{c.label} {c.concept_key}".lower()))

        best_asset: BusinessAsset | None = None
        best_confidence = 0.0
        match_reason = "No match"

        for a in category_assets:
            if a.id in used_asset_ids:
                continue

            a_label_slug = _slugify(a.label)
            a_filename_slug = _slugify(a.original_filename.split(".")[0])
            a_words = set(re.findall(r"\w+", f"{a.label} {a.original_filename}".lower()))

            # Tier 1: Exact slug or key match
            if a_label_slug == c_slug or a_filename_slug == c_slug or a_label_slug == c_key_slug or a_filename_slug == c_key_slug:
                best_asset = a
                best_confidence = 1.0
                match_reason = "Exact Name Match"
                break

            # Tier 2: Strong prefix or key containment (e.g. "towing" in filename and "towing" in key)
            if (c_key_slug in a_filename_slug or c_key_slug in a_label_slug or
                a_label_slug in c_key_slug or a_filename_slug in c_key_slug):
                if best_confidence < 0.90:
                    best_asset = a
                    best_confidence = 0.90
                    match_reason = "Direct Keyword Match"

            # Tier 3: Common keywords intersection
            common_words = c_words.intersection(a_words) - {"cover", "coverage", "insurance", "plan", "benefit", "car", "motor", "png", "webp", "jpg"}
            if len(common_words) >= 2 and best_confidence < 0.80:
                best_asset = a
                best_confidence = 0.80
                match_reason = f"Keyword Match ({', '.join(common_words)})"
            elif len(common_words) == 1 and best_confidence < 0.65:
                best_asset = a
                best_confidence = 0.65
                match_reason = f"Partial Keyword ({list(common_words)[0]})"

        if best_asset and best_confidence >= 0.60:
            used_asset_ids.add(best_asset.id)

        matches.append({
            "concept_id": c.id,
            "concept_key": c.concept_key,
            "concept_label": c.label,
            "sort_order": c.sort_order,
            "matched_asset": {
                "id": best_asset.id,
                "label": best_asset.label,
                "original_filename": best_asset.original_filename,
                "url": f"/business/assets/{best_asset.id}/content?profile=ui",
            } if best_asset else None,
            "confidence": best_confidence,
            "match_reason": match_reason,
            "status": "matched" if best_asset else "unmatched",
        })

    return {
        "profile_id": profile.id,
        "category": profile.asset_category,
        "total_concepts": len(concepts),
        "total_category_assets": len(category_assets),
        "matched_count": len(used_asset_ids),
        "unmatched_count": len(concepts) - len(used_asset_ids),
        "matches": matches,
        "available_category_assets": [
            {
                "id": a.id,
                "label": a.label,
                "original_filename": a.original_filename,
                "url": f"/business/assets/{a.id}/content?profile=ui",
            }
            for a in category_assets
        ],
    }


def save_global_benefit_profile_assets(
    db: Session, user: Any, profile_id: str, items: list[dict]
) -> dict:
    """Saves assignments while enforcing category exclusivity."""
    _require_business(user)
    profile = db.get(GlobalBenefitProfile, profile_id)
    if not profile:
        raise AppError("Visual profile not found.", 404)

    # Verify that any submitted asset belongs to the profile's asset_category
    submitted_asset_ids = [item["asset_id"] for item in items if item.get("asset_id")]
    if submitted_asset_ids:
        invalid_assets = db.scalars(
            select(BusinessAsset).where(
                BusinessAsset.id.in_(submitted_asset_ids),
                BusinessAsset.category != profile.asset_category,
            )
        ).all()
        if invalid_assets:
            names = ", ".join(a.label for a in invalid_assets[:3])
            raise AppError(
                f"Category Exclusivity Violation: Assets [{names}] do not belong to folder '{profile.asset_category}'.",
                422,
            )

    # Delete existing items for this profile and insert new
    db.query(GlobalBenefitProfileAsset).filter(
        GlobalBenefitProfileAsset.profile_id == profile.id
    ).delete(synchronize_session=False)

    for item in items:
        concept_id = item.get("concept_id")
        asset_id = item.get("asset_id")
        if concept_id and asset_id:
            profile_asset = GlobalBenefitProfileAsset(
                id=new_id(),
                profile_id=profile.id,
                concept_id=concept_id,
                asset_id=asset_id,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            db.add(profile_asset)

    profile.updated_at = utcnow()
    _audit(db, user, "business.visual_profile.save_assets", "global_benefit_profile", profile.id, {"items_count": len(items)})
    db.commit()
    db.refresh(profile)
    return get_global_benefit_profile_detail(db, user, profile.id)
