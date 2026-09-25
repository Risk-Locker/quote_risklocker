"""Domain service: benefit_profile_service."""

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

from app.services.company_setup_service import _catalog


__all__ = ['get_active_benefit_profile', 'get_active_company_profile', 'list_benefit_profiles', 'list_company_profiles', 'create_benefit_profile', 'create_company_profile', 'clone_benefit_profile', 'clone_company_profile', 'update_benefit_profile', 'update_company_profile', 'activate_benefit_profile', 'activate_company_profile', 'delete_benefit_profile', 'delete_company_profile', 'get_company_benefit_configs', '_clean_baseline_cost', 'update_company_benefit_configs', 'sync_company_catalogs_to_profile']


def get_active_benefit_profile(db) -> BenefitProfile:
    """Resolve the active unified profile with defensive auto-fallback."""
    profile = db.scalar(
        select(BenefitProfile).where(
            BenefitProfile.is_active.is_(True),
        )
    )
    if profile is not None:
        return profile

    fallback = db.scalar(
        select(BenefitProfile)
        .order_by(BenefitProfile.version_number.desc())
    )
    if fallback is not None:
        fallback.is_active = True
        fallback.status = "active"
        fallback.updated_at = utcnow()
        db.commit()
        db.refresh(fallback)
        return fallback

    new_prof = BenefitProfile(
        id=new_id(),
        name="Main Unified Baseline (14/09/2026)",
        version_number=1,
        is_active=True,
        status="active",
        notes="Auto-provisioned unified baseline profile",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(new_prof)
    db.commit()
    db.refresh(new_prof)
    return new_prof



def get_active_company_profile(db, company_id: str | None = None) -> BenefitProfile:
    """Backwards-compatible alias for get_active_benefit_profile."""
    return get_active_benefit_profile(db)



def list_benefit_profiles(db, user) -> list[dict]:
    _require_business(user)
    cached = _memory_cache.get("business:benefit_profiles")
    if cached is not None:
        return cached

    get_active_benefit_profile(db)

    profiles = list(
        db.scalars(
            select(BenefitProfile)
            .order_by(BenefitProfile.is_active.desc(), BenefitProfile.version_number.desc(), BenefitProfile.created_at.desc())
        ).all()
    )

    # 2 bulk aggregate count queries instead of N+1 lazy queries
    configs_counts = dict(
        db.execute(
            select(CompanyBenefitConfig.profile_id, func.count(CompanyBenefitConfig.id))
            .group_by(CompanyBenefitConfig.profile_id)
        ).all()
    )
    conditions_counts = dict(
        db.execute(
            select(CompanyBenefitCondition.profile_id, func.count(CompanyBenefitCondition.id))
            .group_by(CompanyBenefitCondition.profile_id)
        ).all()
    )

    result = [
        {
            "id": p.id,
            "name": p.name,
            "version_number": p.version_number,
            "is_active": p.is_active,
            "status": p.status,
            "notes": p.notes,
            "configs_count": configs_counts.get(p.id, 0),
            "conditions_count": conditions_counts.get(p.id, 0),
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        }
        for p in profiles
    ]
    _memory_cache.set("business:benefit_profiles", result, ttl_seconds=60.0)
    return result



def list_company_profiles(db, user, company_id: str | None = None) -> list[dict]:
    """Backwards-compatible alias for list_benefit_profiles."""
    return list_benefit_profiles(db, user)



def create_benefit_profile(db, user, payload: dict) -> dict:
    _require_business(user)

    name = str(payload.get("name") or "").strip()
    if not name:
        raise AppError("Profile name is required.", 422)

    notes = payload.get("notes")
    notes_clean = notes.strip() if isinstance(notes, str) and notes.strip() else None

    max_v = db.scalar(
        select(func.coalesce(func.max(BenefitProfile.version_number), 0))
    ) or 0

    profile = BenefitProfile(
        id=new_id(),
        name=name,
        version_number=max_v + 1,
        is_active=False,
        status="draft",
        notes=notes_clean,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(profile)
    _audit(db, user, "business.benefit_profile.create", "benefit_profile", profile.id, {"name": profile.name})
    db.commit()
    invalidate_cache("business:benefit_profiles")
    db.refresh(profile)
    return {
        "id": profile.id,
        "name": profile.name,
        "version_number": profile.version_number,
        "is_active": profile.is_active,
        "status": profile.status,
        "notes": profile.notes,
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }



def create_company_profile(db, user, company_id: str, payload: dict) -> dict:
    """Backwards-compatible alias for create_benefit_profile."""
    return create_benefit_profile(db, user, payload)



def clone_benefit_profile(db, user, profile_id: str, payload: dict) -> dict:
    _require_business(user)

    parent = db.scalar(
        select(BenefitProfile).where(
            BenefitProfile.id == profile_id,
        )
    )
    if parent is None:
        raise AppError("Source profile not found.", 404)

    name = str(payload.get("name") or "").strip()
    if not name:
        name = f"{parent.name} (v{parent.version_number + 1})"

    notes = payload.get("notes")
    notes_clean = notes.strip() if isinstance(notes, str) and notes.strip() else parent.notes

    max_v = db.scalar(
        select(func.coalesce(func.max(BenefitProfile.version_number), 0))
    ) or parent.version_number

    new_profile = BenefitProfile(
        id=new_id(),
        name=name,
        version_number=max_v + 1,
        is_active=False,
        status="draft",
        notes=notes_clean,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(new_profile)
    db.flush()

    # Deep copy ALL configs across all companies
    parent_configs = db.scalars(select(CompanyBenefitConfig).where(CompanyBenefitConfig.profile_id == parent.id)).all()
    for cfg in parent_configs:
        db.add(
            CompanyBenefitConfig(
                id=new_id(),
                company_id=cfg.company_id,
                profile_id=new_profile.id,
                concept_id=cfg.concept_id,
                is_enabled=cfg.is_enabled,
                baseline_description=cfg.baseline_description,
                baseline_cost=cfg.baseline_cost,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
        )

    # Deep copy ALL conditions across all companies
    parent_conditions = db.scalars(select(CompanyBenefitCondition).where(CompanyBenefitCondition.profile_id == parent.id)).all()
    for cond in parent_conditions:
        db.add(
            CompanyBenefitCondition(
                id=new_id(),
                company_id=cond.company_id,
                profile_id=new_profile.id,
                name=cond.name,
                trigger_concept_id=cond.trigger_concept_id,
                trigger_plan_filter=cond.trigger_plan_filter,
                target_concept_id=cond.target_concept_id,
                action_type=getattr(cond, "action_type", "replace_description") or "replace_description",
                replacement_description=cond.replacement_description,
                is_active=cond.is_active,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
        )

    _audit(db, user, "business.benefit_profile.clone", "benefit_profile", new_profile.id, {
        "parent_profile_id": parent.id,
        "name": new_profile.name,
        "configs_cloned": len(parent_configs),
        "conditions_cloned": len(parent_conditions),
    })
    db.commit()
    invalidate_cache("business:benefit_profiles")
    db.refresh(new_profile)
    return {
        "id": new_profile.id,
        "name": new_profile.name,
        "version_number": new_profile.version_number,
        "is_active": new_profile.is_active,
        "status": new_profile.status,
        "notes": new_profile.notes,
        "created_at": new_profile.created_at.isoformat() if new_profile.created_at else None,
        "updated_at": new_profile.updated_at.isoformat() if new_profile.updated_at else None,
    }



def clone_company_profile(db, user, company_id: str, profile_id: str, payload: dict) -> dict:
    """Backwards-compatible alias for clone_benefit_profile."""
    return clone_benefit_profile(db, user, profile_id, payload)



def update_benefit_profile(db, user, profile_id: str, payload: dict) -> dict:
    _require_business(user)
    profile = db.scalar(
        select(BenefitProfile).where(
            BenefitProfile.id == profile_id,
        ).with_for_update()
    )
    if profile is None:
        raise AppError("Profile not found.", 404)

    if profile.status == "archived":
        raise AppError("Cannot modify an archived profile. Clone it to create a new draft.", 400)

    name = payload.get("name")
    if name is not None:
        clean_name = str(name).strip()
        if not clean_name:
            raise AppError("Profile name cannot be empty.", 422)
        profile.name = clean_name

    notes = payload.get("notes")
    if notes is not None:
        profile.notes = str(notes).strip() if str(notes).strip() else None

    profile.updated_at = utcnow()
    _audit(db, user, "business.benefit_profile.update", "benefit_profile", profile.id, {"name": profile.name})
    db.commit()
    invalidate_cache("business:benefit_profiles")
    db.refresh(profile)
    return {
        "id": profile.id,
        "name": profile.name,
        "version_number": profile.version_number,
        "is_active": profile.is_active,
        "status": profile.status,
        "notes": profile.notes,
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }



def update_company_profile(db, user, company_id: str, profile_id: str, payload: dict) -> dict:
    """Backwards-compatible alias for update_benefit_profile."""
    return update_benefit_profile(db, user, profile_id, payload)



def activate_benefit_profile(db, user, profile_id: str) -> dict:
    _require_business(user)

    target = db.scalar(
        select(BenefitProfile).where(
            BenefitProfile.id == profile_id,
        ).with_for_update()
    )
    if target is None:
        raise AppError("Profile not found.", 404)

    if target.is_active:
        return {
            "id": target.id,
            "name": target.name,
            "version_number": target.version_number,
            "is_active": True,
            "status": "active",
            "notes": target.notes,
        }

    # Deactivate previous active profiles globally
    db.execute(
        update(BenefitProfile)
        .where(BenefitProfile.is_active.is_(True))
        .values({
            BenefitProfile.is_active: False,
            BenefitProfile.status: "archived",
            BenefitProfile.updated_at: utcnow(),
        })
    )

    target.is_active = True
    target.status = "active"
    target.updated_at = utcnow()

    _audit(db, user, "business.benefit_profile.activate", "benefit_profile", target.id, {
        "name": target.name,
        "version_number": target.version_number,
    })

    # Cascade disabled benefits across all companies for the newly activated profile
    companies = db.scalars(select(InsuranceCompany)).all()
    for comp in companies:
        sync_company_catalogs_to_profile(db, comp.id, target.id)

    db.commit()
    invalidate_cache("business:benefit_profiles")
    db.refresh(target)
    return {
        "id": target.id,
        "name": target.name,
        "version_number": target.version_number,
        "is_active": True,
        "status": "active",
        "notes": target.notes,
    }



def activate_company_profile(db, user, company_id: str, profile_id: str) -> dict:
    """Backwards-compatible alias for activate_benefit_profile."""
    return activate_benefit_profile(db, user, profile_id)



def delete_benefit_profile(db, user, profile_id: str) -> None:
    _require_business(user)
    profile = db.scalar(
        select(BenefitProfile).where(
            BenefitProfile.id == profile_id,
        ).with_for_update()
    )
    if profile is None:
        raise AppError("Profile not found.", 404)

    if profile.is_active:
        raise AppError("Cannot delete an active profile. Switch to another active profile first.", 400)

    db.execute(delete(CompanyBenefitCondition).where(CompanyBenefitCondition.profile_id == profile_id))
    db.execute(delete(CompanyBenefitConfig).where(CompanyBenefitConfig.profile_id == profile_id))
    db.delete(profile)
    _audit(db, user, "business.benefit_profile.delete", "benefit_profile", profile_id, {"name": profile.name})
    db.commit()
    invalidate_cache("business:benefit_profiles")



def delete_company_profile(db, user, company_id: str, profile_id: str) -> None:
    """Backwards-compatible alias for delete_benefit_profile."""
    delete_benefit_profile(db, user, profile_id)



def get_company_benefit_configs(db, user, company_id: str, profile_id: str | None = None) -> list[dict]:
    _require_business(user)
    if profile_id:
        target_profile = db.get(BenefitProfile, profile_id)
        if target_profile is None:
            raise AppError("Profile not found.", 404)
        active_prof_id = target_profile.id
    else:
        active_prof_id = get_active_benefit_profile(db).id

    configs = list(
        db.scalars(
            select(CompanyBenefitConfig)
            .where(
                CompanyBenefitConfig.company_id == company_id,
                CompanyBenefitConfig.profile_id == active_prof_id,
            )
        ).all()
    )
    return [
        {
            "id": c.id,
            "company_id": c.company_id,
            "profile_id": c.profile_id,
            "concept_id": c.concept_id,
            "is_enabled": c.is_enabled,
            "baseline_description": c.baseline_description,
            "baseline_cost": c.baseline_cost,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in configs
    ]



def _clean_baseline_cost(val: Any) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    lower = s.lower()
    norm = re.sub(r"^(rm|myr)\s*", "", lower).strip()
    if norm in {"", "0", "00", "0.0", "0.00", "null", "none", "quoted", "as quoted", "foc", "included"}:
        return None
    if lower in {"null", "none", "rm", "rm0", "rm00", "rm 0", "rm 0.0", "rm 0.00", "rm0.00", "rm quoted", "as quoted", "foc", "included"}:
        return None
    return s



def update_company_benefit_configs(db, user, company_id: str, items: list[dict], profile_id: str | None = None) -> list[dict]:
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

    results = []
    for item in items:
        concept_id = item.get("concept_id")
        if not concept_id:
            continue
        concept = db.get(BenefitConcept, concept_id)
        if concept is None:
            continue

        cfg = db.scalar(
            select(CompanyBenefitConfig).where(
                CompanyBenefitConfig.company_id == company_id,
                CompanyBenefitConfig.profile_id == target_profile.id,
                CompanyBenefitConfig.concept_id == concept_id,
            )
        )
        is_enabled = bool(item.get("is_enabled", True))
        desc_raw = item.get("baseline_description")
        desc = desc_raw.strip() if isinstance(desc_raw, str) and desc_raw.strip() else None
        cost = _clean_baseline_cost(item.get("baseline_cost"))

        if cfg is not None:
            cfg.is_enabled = is_enabled
            cfg.baseline_description = desc
            cfg.baseline_cost = cost
            cfg.updated_at = utcnow()
        else:
            cfg = CompanyBenefitConfig(
                id=new_id(),
                company_id=company_id,
                profile_id=target_profile.id,
                concept_id=concept_id,
                is_enabled=is_enabled,
                baseline_description=desc,
                baseline_cost=cost,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            db.add(cfg)
        results.append(cfg)

    # Automatically cascade any disabled concepts to this company's catalogs and packages
    sync_company_catalogs_to_profile(db, company_id, target_profile.id)

    _audit(db, user, "business.company.benefit_configs", "benefit_profile", target_profile.id, {
        "company_id": company_id,
        "count": len(results),
    })
    db.commit()
    invalidate_cache("business:benefit_profiles")

    return [
        {
            "id": c.id,
            "company_id": c.company_id,
            "profile_id": c.profile_id,
            "concept_id": c.concept_id,
            "is_enabled": c.is_enabled,
            "baseline_description": c.baseline_description,
            "baseline_cost": c.baseline_cost,
        }
        for c in results
    ]



def sync_company_catalogs_to_profile(db, company_id: str, profile_id: str | None = None) -> dict:
    """Cascade disabled concepts in the active/target benefit profile to all catalog revisions of the company.

    Any catalog offering and package plan item corresponding to a disabled concept in the company profile
    is cleanly purged so catalogues and matrix stay 100% consistent with the active profile pool.

    If a catalog's latest revision is draft, disabled offerings and plan items are purged directly.
    If a catalog's latest revision is published and contains disabled offerings, a clean new revision is
    forked (copying forward only the enabled offerings, packages, plans, and relations) and published,
    preserving database immutability triggers for published historical revisions.
    """
    if profile_id:
        target_profile = db.get(BenefitProfile, profile_id)
    else:
        target_profile = get_active_benefit_profile(db)

    if target_profile is None:
        return {"purged_offerings": 0, "purged_plan_items": 0}

    # Find disabled concepts for this company under target_profile
    disabled_configs = db.scalars(
        select(CompanyBenefitConfig.concept_id).where(
            CompanyBenefitConfig.company_id == company_id,
            CompanyBenefitConfig.profile_id == target_profile.id,
            CompanyBenefitConfig.is_enabled.is_(False),
        )
    ).all()
    disabled_concept_ids = set(disabled_configs)
    if not disabled_concept_ids:
        return {"purged_offerings": 0, "purged_plan_items": 0}

    # Find all catalogs for this company
    catalogs = list(
        db.scalars(
            select(BenefitCatalog).where(BenefitCatalog.company_id == company_id)
        ).all()
    )
    if not catalogs:
        return {"purged_offerings": 0, "purged_plan_items": 0}

    total_purged_offerings = 0
    total_purged_plan_items = 0

    for catalog in catalogs:
        latest_rev = db.scalar(
            select(BenefitCatalogRevision)
            .where(BenefitCatalogRevision.catalog_id == catalog.id)
            .order_by(BenefitCatalogRevision.revision_number.desc())
        )
        if latest_rev is None:
            continue

        # Offerings currently in latest_rev
        current_offerings = list(
            db.scalars(
                select(CatalogOffering).where(CatalogOffering.catalog_revision_id == latest_rev.id)
            ).all()
        )
        disabled_in_rev = [o for o in current_offerings if o.concept_id in disabled_concept_ids]
        if not disabled_in_rev:
            continue

        disabled_offering_ids = [o.id for o in disabled_in_rev]

        if latest_rev.state == "draft":
            # Direct cleanup in mutable draft revision
            db.execute(
                update(DraftBenefitSelection)
                .where(DraftBenefitSelection.catalog_offering_id.in_(disabled_offering_ids))
                .values(
                    item_kind="custom",
                    label_override=func.coalesce(DraftBenefitSelection.label_override, "Archived Benefit"),
                    catalog_offering_id=None,
                )
            )
            deleted_items = db.execute(
                delete(BenefitPackagePlanItem).where(BenefitPackagePlanItem.offering_id.in_(disabled_offering_ids))
            ).rowcount or 0
            db.execute(
                delete(BenefitRelation).where(
                    or_(
                        BenefitRelation.from_offering_id.in_(disabled_offering_ids),
                        BenefitRelation.to_offering_id.in_(disabled_offering_ids),
                    )
                )
            )
            deleted_offs = db.execute(
                delete(CatalogOffering).where(CatalogOffering.id.in_(disabled_offering_ids))
            ).rowcount or 0
            total_purged_offerings += deleted_offs
            total_purged_plan_items += deleted_items

        else:
            # Fork a clean new revision from published revision, keeping only enabled offerings
            new_rev = BenefitCatalogRevision(
                id=new_id(),
                catalog_id=catalog.id,
                revision_number=latest_rev.revision_number + 1,
                state="published",
                source_document_ids=list(latest_rev.source_document_ids or []),
                content_hash=canonical_context_hash({}),
                published_at=utcnow(),
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            db.add(new_rev)
            db.flush()

            # 1. Copy forward packages
            pkg_map: dict[str, str] = {}
            for pkg in db.scalars(
                select(BenefitPackage)
                .where(BenefitPackage.catalog_revision_id == latest_rev.id)
                .order_by(BenefitPackage.sort_order, BenefitPackage.package_key)
            ).all():
                new_pkg = BenefitPackage(
                    id=new_id(),
                    catalog_revision_id=new_rev.id,
                    package_key=pkg.package_key,
                    name=pkg.name,
                    package_kind=pkg.package_kind,
                    sort_order=pkg.sort_order,
                    revision=pkg.revision,
                    status=pkg.status,
                    created_at=utcnow(),
                    updated_at=utcnow(),
                )
                db.add(new_pkg)
                pkg_map[pkg.id] = new_pkg.id
            db.flush()

            # 2. Copy forward plans
            plan_map: dict[str, str] = {}
            if pkg_map:
                for plan in db.scalars(
                    select(BenefitPackagePlan)
                    .where(BenefitPackagePlan.package_id.in_(list(pkg_map.keys())))
                    .order_by(BenefitPackagePlan.sort_order, BenefitPackagePlan.name)
                ).all():
                    new_plan = BenefitPackagePlan(
                        id=new_id(),
                        package_id=pkg_map[plan.package_id],
                        plan_key=plan.plan_key,
                        name=plan.name,
                        sort_order=plan.sort_order,
                        status=plan.status,
                        created_at=utcnow(),
                        updated_at=utcnow(),
                    )
                    db.add(new_plan)
                    plan_map[plan.id] = new_plan.id
                db.flush()

            # 3. Copy forward ONLY enabled offerings
            offering_map: dict[str, str] = {}
            for off in current_offerings:
                if off.concept_id in disabled_concept_ids:
                    total_purged_offerings += 1
                    continue
                new_off_id = new_id()
                offering_map[off.id] = new_off_id
                if off.applies_to_type == "package":
                    new_applies_to_id = pkg_map.get(str(off.applies_to_id)) if off.applies_to_id else None
                    new_applies_to_type = "package" if new_applies_to_id else None
                elif off.applies_to_type == "product":
                    new_applies_to_id = off.applies_to_id or catalog.product_id
                    new_applies_to_type = "product" if new_applies_to_id else None
                else:
                    new_applies_to_id = None
                    new_applies_to_type = None

                if not new_applies_to_id or not new_applies_to_type:
                    new_applies_to_id = None
                    new_applies_to_type = None

                db.add(
                    CatalogOffering(
                        id=new_off_id,
                        catalog_revision_id=new_rev.id,
                        offering_key=off.offering_key,
                        concept_id=off.concept_id,
                        offering_kind=off.offering_kind,
                        applies_to_type=new_applies_to_type,
                        applies_to_id=new_applies_to_id,
                        role=off.role,
                        label_override=off.label_override,
                        description_override=off.description_override,
                        typed_value=off.typed_value,
                        display_value=off.display_value,
                        optional_price=off.optional_price,
                        source_document_id=off.source_document_id,
                        source_citation=off.source_citation,
                        source_aliases=list(off.source_aliases or []),
                        presentation_facet_ids=list(off.presentation_facet_ids or []),
                        sort_order=off.sort_order,
                        status=off.status,
                        created_at=utcnow(),
                        updated_at=utcnow(),
                    )
                )
            db.flush()

            # 4. Copy forward plan items for kept offerings
            if plan_map:
                for p_item in db.scalars(
                    select(BenefitPackagePlanItem)
                    .where(BenefitPackagePlanItem.plan_id.in_(list(plan_map.keys())))
                ).all():
                    if p_item.offering_id in offering_map:
                        db.add(
                            BenefitPackagePlanItem(
                                id=new_id(),
                                plan_id=plan_map[p_item.plan_id],
                                offering_id=offering_map[p_item.offering_id],
                                typed_value_override=p_item.typed_value_override,
                                sort_order=p_item.sort_order,
                                created_at=utcnow(),
                                updated_at=utcnow(),
                            )
                        )
                    else:
                        total_purged_plan_items += 1
                db.flush()

            # 5. Copy forward relations for kept offerings
            for rel in db.scalars(
                select(BenefitRelation).where(BenefitRelation.catalog_revision_id == latest_rev.id)
            ).all():
                if rel.from_offering_id in offering_map and rel.to_offering_id in offering_map:
                    db.add(
                        BenefitRelation(
                            id=new_id(),
                            catalog_revision_id=new_rev.id,
                            from_offering_id=offering_map[rel.from_offering_id],
                            to_offering_id=offering_map[rel.to_offering_id],
                            relation_kind=rel.relation_kind,
                            branch_key=rel.branch_key,
                            sort_order=rel.sort_order,
                            created_at=utcnow(),
                            updated_at=utcnow(),
                        )
                    )
            db.flush()

            # 6. Update catalog pointer
            if catalog.package_id and str(catalog.package_id) in pkg_map:
                catalog.package_id = pkg_map[str(catalog.package_id)]
            catalog.revision = new_rev.revision_number
            catalog.status = "published"
            catalog.updated_at = utcnow()

    db.flush()

    return {
        "purged_offerings": total_purged_offerings,
        "purged_plan_items": total_purged_plan_items,
    }

