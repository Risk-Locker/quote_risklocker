"""Domain service: company_setup_service."""

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


__all__ = ['serialize_company', 'list_business_companies', '_normalize_alias', '_company_alias', 'list_company_aliases', 'save_company_alias', 'retire_company_alias', '_product', '_tier', '_catalog', '_catalogs_batch', 'get_business_company_workspace', 'save_business_company', 'delete_business_company', 'save_business_product', 'delete_business_product', 'save_business_tier', 'delete_business_tier']


def serialize_company(db, company: InsuranceCompany, preloaded_logos: dict[str, BusinessAsset | None] | None = None) -> dict:
    if preloaded_logos is not None:
        logo = preloaded_logos.get(company.logo_asset_id) if company.logo_asset_id else None
    else:
        logo = db.get(BusinessAsset, company.logo_asset_id) if company.logo_asset_id else None
    return {
        "id": company.id,
        "slug": company.slug,
        "revision": company.revision,
        "name": company.name,
        "category": company.category,
        "legal_entity_id": company.legal_entity_id,
        "logo": _asset_summary(logo),
        "status": company.status,
        "created_at": company.created_at.isoformat() if company.created_at else None,
        "updated_at": company.updated_at.isoformat() if company.updated_at else None,
    }



def list_business_companies(db, user, *, search: str, page: int, page_size: int) -> dict:
    _require_business(user)
    term = search.strip()
    cache_key = f"business:companies:{page}:{page_size}" if not term else None
    if cache_key:
        cached = _memory_cache.get(cache_key)
        if cached is not None:
            return cached

    query = select(InsuranceCompany)
    count_query = select(func.count()).select_from(InsuranceCompany)
    if term:
        pattern = f"%{term}%"
        predicate = or_(InsuranceCompany.name.ilike(pattern), InsuranceCompany.slug.ilike(pattern))
        query = query.where(predicate)
        count_query = count_query.where(predicate)
    total = int(db.scalar(count_query) or 0)
    items = list(
        db.scalars(
            query.order_by(InsuranceCompany.name.asc()).limit(page_size).offset((page - 1) * page_size)
        ).all()
    )

    logo_ids = [c.logo_asset_id for c in items if c.logo_asset_id]
    logos_map: dict[str, BusinessAsset | None] = {}
    if logo_ids:
        assets = db.scalars(select(BusinessAsset).where(BusinessAsset.id.in_(logo_ids))).all()
        logos_map = {a.id: a for a in assets}

    result = {
        "items": [serialize_company(db, item, logos_map) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }
    if cache_key:
        _memory_cache.set(cache_key, result, ttl_seconds=60.0)
    return result



def _normalize_alias(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()



def _company_alias(db, item: CompanyAlias) -> dict:
    company = db.get(InsuranceCompany, item.company_id)
    return {
        "id": item.id,
        "company_id": item.company_id,
        "company_name": company.name if company else "Unavailable company",
        "alias": item.alias,
        "normalized_alias": item.normalized_alias,
        "alias_kind": item.alias_kind,
        "status": item.status,
    }



def list_company_aliases(db, user, *, search: str, page: int, page_size: int) -> dict:
    _require_business(user)
    query = select(CompanyAlias)
    count_query = select(func.count()).select_from(CompanyAlias)
    term = search.strip()
    if term:
        pattern = f"%{term}%"
        predicate = or_(CompanyAlias.alias.ilike(pattern), CompanyAlias.normalized_alias.ilike(pattern))
        query = query.where(predicate)
        count_query = count_query.where(predicate)
    total = int(db.scalar(count_query) or 0)
    items = db.scalars(
        query.order_by(CompanyAlias.alias.asc()).limit(page_size).offset((page - 1) * page_size)
    ).all()
    return {
        "items": [_company_alias(db, item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }



def save_company_alias(db, user, payload: dict) -> dict:
    _require_business(user)
    item = None
    if payload.get("id"):
        item = db.scalar(select(CompanyAlias).where(CompanyAlias.id == payload["id"]).with_for_update())
        if item is None:
            raise AppError("Company alias not found.", 404)
    company_id = payload.get("company_id") or (item.company_id if item else None)
    if not company_id:
        raise AppError("Company is required.", 422)
    company = db.get(InsuranceCompany, company_id)
    if company is None:
        raise AppError("Company not found.", 404)
    alias = str(payload["alias"]).strip()
    normalized = _normalize_alias(alias)
    if not normalized:
        raise AppError("Enter a usable detection phrase.", 422)
    kind = payload.get("alias_kind", "detection")
    if kind not in ALIAS_KINDS:
        raise AppError("Alias type is invalid.", 422)
    duplicate = db.scalar(
        select(CompanyAlias).where(
            CompanyAlias.normalized_alias == normalized,
            CompanyAlias.id != (item.id if item else "00000000-0000-0000-0000-000000000000"),
        )
    )
    if duplicate:
        raise AppError(f'This phrase already resolves to {_company_alias(db, duplicate)["company_name"]}.', 409)
    if item is None:
        item = CompanyAlias(id=new_id(), company_id=company.id, alias=alias, normalized_alias=normalized)
        db.add(item)
    item.company_id = company.id
    item.alias = alias
    item.normalized_alias = normalized
    item.alias_kind = kind
    item.status = payload.get("status", "active")
    if item.status not in STATUSES:
        raise AppError("Alias status is invalid.", 422)
    _audit(db, user, "business.company_alias.save", "company_alias", item.id, {"company_id": company.id, "alias_kind": kind})
    db.commit()
    db.refresh(item)
    return _company_alias(db, item)



def retire_company_alias(db, user, alias_id: str) -> None:
    _require_business(user)
    item = db.scalar(select(CompanyAlias).where(CompanyAlias.id == alias_id).with_for_update())
    if item is None:
        raise AppError("Company alias not found.", 404)
    item.status = "retired"
    _audit(db, user, "business.company_alias.retire", "company_alias", item.id, {"company_id": item.company_id})
    db.commit()



def _product(item: InsuranceProduct) -> dict:
    return {
        "id": item.id,
        "company_id": item.company_id,
        "product_key": item.product_key,
        "name": item.name,
        "channel": item.channel,
        "revision": item.revision,
        "status": item.status,
    }



def _tier(item: InsuranceProductTier) -> dict:
    return {
        "id": item.id,
        "product_id": item.product_id,
        "tier_key": item.tier_key,
        "name": item.name,
        "sort_order": item.sort_order,
        "revision": item.revision,
        "status": item.status,
    }



def _catalog(db, item: BenefitCatalog) -> dict:
    revisions = db.scalars(
        select(BenefitCatalogRevision)
        .where(BenefitCatalogRevision.catalog_id == item.id)
        .order_by(BenefitCatalogRevision.revision_number.desc())
    ).all()
    package = db.get(BenefitPackage, item.package_id) if item.package_id else None
    return {
        "id": item.id,
        "company_id": item.company_id,
        "product_id": item.product_id,
        "tier_id": item.tier_id,
        "package_id": item.package_id,
        "package": {
            "id": package.id,
            "package_key": package.package_key,
            "name": package.name,
            "package_kind": package.package_kind,
            "sort_order": package.sort_order,
        } if package else None,
        "segment_id": item.segment_id,
        "vehicle_category_id": item.vehicle_category_id,
        "vehicle_subcategory_id": item.vehicle_subcategory_id,
        "coverage_type_id": item.coverage_type_id,
        "coverage_type_key": (
            "comprehensive" if item.coverage_type_id == "d1111111-0000-4000-8000-000000000001"
            else ("tpft" if item.coverage_type_id == "d1111111-0000-4000-8000-000000000002"
            else ("third_party" if item.coverage_type_id == "d1111111-0000-4000-8000-000000000003" else None))
        ),
        "engine_type": getattr(item, "engine_type", None) or "ice",
        "name": item.name,
        "revision": item.revision,
        "status": item.status,
        "revisions": [
            {
                "id": revision.id,
                "revision_number": revision.revision_number,
                "state": revision.state,
                "content_hash": revision.content_hash,
                "published_at": revision.published_at.isoformat() if revision.published_at else None,
            }
            for revision in revisions
        ],
    }



def _catalogs_batch(db, catalogs: list[BenefitCatalog]) -> list[dict]:
    """Batch-serialize catalogs: 2 queries total instead of 2 per catalog."""
    if not catalogs:
        return []
    catalog_ids = [item.id for item in catalogs]
    # 1. Batch-load all revisions for all catalogs in 1 query
    all_revisions = list(db.scalars(
        select(BenefitCatalogRevision)
        .where(BenefitCatalogRevision.catalog_id.in_(catalog_ids))
        .order_by(BenefitCatalogRevision.revision_number.desc())
    ).all())
    revisions_by_catalog: dict[str, list] = defaultdict(list)
    for rev in all_revisions:
        revisions_by_catalog[str(rev.catalog_id)].append(rev)
    # 2. Batch-load all referenced packages in 1 query
    package_ids = {item.package_id for item in catalogs if item.package_id}
    packages_map: dict[str, BenefitPackage] = {}
    if package_ids:
        packages_map = {
            pkg.id: pkg
            for pkg in db.scalars(select(BenefitPackage).where(BenefitPackage.id.in_(package_ids))).all()
        }
    # 3. Build result dicts using preloaded data
    result = []
    for item in catalogs:
        revisions = revisions_by_catalog.get(item.id, [])
        package = packages_map.get(item.package_id) if item.package_id else None
        result.append({
            "id": item.id,
            "company_id": item.company_id,
            "product_id": item.product_id,
            "tier_id": item.tier_id,
            "package_id": item.package_id,
            "package": {
                "id": package.id,
                "package_key": package.package_key,
                "name": package.name,
                "package_kind": package.package_kind,
                "sort_order": package.sort_order,
            } if package else None,
            "segment_id": item.segment_id,
            "vehicle_category_id": item.vehicle_category_id,
            "vehicle_subcategory_id": item.vehicle_subcategory_id,
            "coverage_type_id": item.coverage_type_id,
            "coverage_type_key": (
                "comprehensive" if item.coverage_type_id == "d1111111-0000-4000-8000-000000000001"
                else ("tpft" if item.coverage_type_id == "d1111111-0000-4000-8000-000000000002"
                else ("third_party" if item.coverage_type_id == "d1111111-0000-4000-8000-000000000003" else None))
            ),
            "engine_type": getattr(item, "engine_type", None) or "ice",
            "name": item.name,
            "revision": item.revision,
            "status": item.status,
            "revisions": [
                {
                    "id": revision.id,
                    "revision_number": revision.revision_number,
                    "state": revision.state,
                    "content_hash": revision.content_hash,
                    "published_at": revision.published_at.isoformat() if revision.published_at else None,
                }
                for revision in revisions
            ],
        })
    return result



def get_business_company_workspace(db, user, company_id: str, include_archived: bool = False) -> dict:
    _require_business(user)
    company = db.get(InsuranceCompany, company_id)
    if company is None:
        raise AppError("Company not found.", 404)
    prod_stmt = select(InsuranceProduct).where(InsuranceProduct.company_id == company_id)
    if not include_archived:
        prod_stmt = prod_stmt.where(InsuranceProduct.status != "archived", InsuranceProduct.status != "retired")
    products = list(db.scalars(prod_stmt).all())
    product_ids = [item.id for item in products]
    tiers = list(
        db.scalars(
            select(InsuranceProductTier)
            .where(InsuranceProductTier.product_id.in_(product_ids))
            .order_by(InsuranceProductTier.sort_order, InsuranceProductTier.name)
        ).all()
    ) if product_ids else []
    cat_stmt = select(BenefitCatalog).where(BenefitCatalog.company_id == company_id).order_by(BenefitCatalog.name)
    if not include_archived:
        cat_stmt = cat_stmt.where(BenefitCatalog.status != "archived", BenefitCatalog.status != "retired")
    catalogs = list(db.scalars(cat_stmt).all())
    return {
        "company": serialize_company(db, company),
        "products": [_product(item) for item in products],
        "tiers": [_tier(item) for item in tiers],
        "catalogs": _catalogs_batch(db, catalogs),
    }



def save_business_company(db, user, payload: dict) -> dict:
    _require_business(user)
    company = None
    if payload.get("id"):
        company = db.scalar(select(InsuranceCompany).where(InsuranceCompany.id == payload["id"]).with_for_update())
        if company is None:
            raise AppError("Company not found.", 404)
    if company is None:
        company = InsuranceCompany(id=new_id(), name=payload["name"], category="Motor", revision=1)
        db.add(company)
    base_slug = _slug(payload.get("slug") or payload["name"])
    if not base_slug:
        base_slug = f"company-{int(datetime.now(timezone.utc).timestamp())}"
    slug = base_slug
    counter = 1
    while True:
        duplicate = db.scalar(select(InsuranceCompany).where(InsuranceCompany.slug == slug, InsuranceCompany.id != company.id))
        if not duplicate:
            break
        counter += 1
        slug = f"{base_slug}-{counter}"
    asset_id = payload.get("logo_asset_id")
    if asset_id:
        asset = db.get(BusinessAsset, asset_id)
        if asset is None:
            raise AppError("Select a valid company logo asset.", 422)
        if asset.asset_kind != "company_logo":
            asset.asset_kind = "company_logo"
    previous = company.revision
    company.name = payload["name"].strip()
    company.slug = slug
    company.legal_entity_id = payload.get("legal_entity_id")
    company.logo_asset_id = asset_id
    company.logo_path = None
    company.status = payload.get("status", "active")
    if company.status not in STATUSES:
        raise AppError("Company status is invalid.", 422)
    if payload.get("id"):
        company.revision += 1
    _audit(db, user, "business.company.save", "insurance_company", company.id, {"base_revision": previous, "new_revision": company.revision})
    db.commit()
    invalidate_cache("business:companies")
    db.refresh(company)
    return serialize_company(db, company)



def delete_business_company(db, user, company_id: str) -> None:
    _require_business(user)
    company = db.get(InsuranceCompany, company_id)
    if company is None:
        raise AppError("Company not found.", 404)

    # 1. Delete associated company aliases & benefit aliases
    db.execute(delete(CompanyAlias).where(CompanyAlias.company_id == company.id))
    db.execute(delete(BenefitAlias).where(BenefitAlias.company_id == company.id))

    # 2. Delete associated catalogs, revisions, packages, plans, plan items, offerings
    catalogs = db.scalars(select(BenefitCatalog).where(BenefitCatalog.company_id == company.id)).all()
    cat_ids = [c.id for c in catalogs]
    if cat_ids:
        revisions = db.scalars(select(BenefitCatalogRevision).where(BenefitCatalogRevision.catalog_id.in_(cat_ids))).all()
        rev_ids = [r.id for r in revisions]
        if rev_ids:
            packages = db.scalars(select(BenefitPackage).where(BenefitPackage.catalog_revision_id.in_(rev_ids))).all()
            pkg_ids = [p.id for p in packages]
            if pkg_ids:
                plans = db.scalars(select(BenefitPackagePlan).where(BenefitPackagePlan.package_id.in_(pkg_ids))).all()
                plan_ids = [pl.id for pl in plans]
                if plan_ids:
                    db.execute(delete(BenefitPackagePlanItem).where(BenefitPackagePlanItem.plan_id.in_(plan_ids)))
                    db.execute(delete(BenefitPackagePlan).where(BenefitPackagePlan.id.in_(plan_ids)))
                db.execute(delete(BenefitPackage).where(BenefitPackage.id.in_(pkg_ids)))
            db.execute(delete(CatalogOffering).where(CatalogOffering.catalog_revision_id.in_(rev_ids)))
            db.execute(delete(BenefitCatalogRevision).where(BenefitCatalogRevision.id.in_(rev_ids)))
        db.execute(delete(BenefitCatalog).where(BenefitCatalog.id.in_(cat_ids)))

    # 3. Delete associated products & tiers
    products = db.scalars(select(InsuranceProduct).where(InsuranceProduct.company_id == company.id)).all()
    prod_ids = [p.id for p in products]
    if prod_ids:
        db.execute(delete(InsuranceProductTier).where(InsuranceProductTier.product_id.in_(prod_ids)))
        db.execute(delete(InsuranceProduct).where(InsuranceProduct.id.in_(prod_ids)))

    # 4. Nullify optional FK references in other tables
    db.execute(text("UPDATE output_template_configs SET insurance_company_id = NULL WHERE insurance_company_id = :cid"), {"cid": company.id})
    db.execute(text("UPDATE template_groups SET company_id = NULL WHERE company_id = :cid"), {"cid": company.id})
    db.execute(text("UPDATE quotation_drafts SET company_id = NULL WHERE company_id = :cid"), {"cid": company.id})
    db.execute(text("UPDATE uploaded_files SET insurance_company_id = NULL WHERE insurance_company_id = :cid"), {"cid": company.id})
    db.execute(text("UPDATE benefit_options SET insurance_company_id = NULL WHERE insurance_company_id = :cid"), {"cid": company.id})
    db.execute(text("UPDATE correction_memory SET insurance_company_id = NULL WHERE insurance_company_id = :cid"), {"cid": company.id})

    _audit(db, user, "business.company.delete", "insurance_company", company.id, {"company_name": company.name})
    db.delete(company)
    db.commit()
    invalidate_cache("business:companies")



def save_business_product(db, user, payload: dict) -> dict:
    _require_business(user)
    product = None
    if payload.get("id"):
        product = db.scalar(select(InsuranceProduct).where(InsuranceProduct.id == payload["id"]).with_for_update())
        if product is None:
            raise AppError("Product not found.", 404)
        _require_revision(product, payload.get("base_revision"), "product")
    company_id = payload.get("company_id") or (product.company_id if product else None)
    if not company_id:
        raise AppError("Company is required.", 422)
    if db.get(InsuranceCompany, company_id) is None:
        raise AppError("Company not found.", 404)
    if product is None:
        product = InsuranceProduct(id=new_id(), company_id=company_id, product_key="", name=payload["name"])
        db.add(product)
    product.company_id = company_id
    product.product_key = _slug(payload.get("product_key") or payload["name"])
    product.name = payload["name"].strip()
    product.channel = payload.get("channel")
    product.status = payload.get("status", "active")
    if payload.get("id"):
        product.revision += 1
    _audit(db, user, "business.product.save", "insurance_product", product.id, {"new_revision": product.revision})
    db.commit()
    db.refresh(product)
    return _product(product)



def delete_business_product(db, user, product_id: str) -> None:
    _require_business(user)
    product = db.get(InsuranceProduct, product_id)
    if product is None:
        raise AppError("Product not found.", 404)
    # Delete associated tiers
    db.execute(delete(InsuranceProductTier).where(InsuranceProductTier.product_id == product.id))
    # Delete associated benefit aliases
    db.execute(delete(BenefitAlias).where(BenefitAlias.product_id == product.id))
    # Delete associated catalogs, revisions, packages, plans, plan items, offerings
    catalogs = db.scalars(select(BenefitCatalog).where(BenefitCatalog.product_id == product.id)).all()
    cat_ids = [c.id for c in catalogs]
    if cat_ids:
        revisions = db.scalars(select(BenefitCatalogRevision).where(BenefitCatalogRevision.catalog_id.in_(cat_ids))).all()
        rev_ids = [r.id for r in revisions]
        if rev_ids:
            packages = db.scalars(select(BenefitPackage).where(BenefitPackage.catalog_revision_id.in_(rev_ids))).all()
            pkg_ids = [p.id for p in packages]
            if pkg_ids:
                plans = db.scalars(select(BenefitPackagePlan).where(BenefitPackagePlan.package_id.in_(pkg_ids))).all()
                plan_ids = [pl.id for pl in plans]
                if plan_ids:
                    db.execute(delete(BenefitPackagePlanItem).where(BenefitPackagePlanItem.plan_id.in_(plan_ids)))
                    db.execute(delete(BenefitPackagePlan).where(BenefitPackagePlan.id.in_(plan_ids)))
                db.execute(delete(BenefitPackage).where(BenefitPackage.id.in_(pkg_ids)))
            db.execute(delete(CatalogOffering).where(CatalogOffering.catalog_revision_id.in_(rev_ids)))
            db.execute(delete(BenefitCatalogRevision).where(BenefitCatalogRevision.id.in_(rev_ids)))
        db.execute(delete(BenefitCatalog).where(BenefitCatalog.id.in_(cat_ids)))
    db.execute(text("UPDATE quotation_drafts SET product_id = NULL WHERE product_id = :pid"), {"pid": product.id})
    _audit(db, user, "business.product.delete", "insurance_product", product.id, {"product_name": product.name})
    db.delete(product)
    db.commit()



def save_business_tier(db, user, payload: dict) -> dict:
    _require_business(user)
    tier = None
    if payload.get("id"):
        tier = db.scalar(select(InsuranceProductTier).where(InsuranceProductTier.id == payload["id"]).with_for_update())
        if tier is None:
            raise AppError("Tier not found.", 404)
        _require_revision(tier, payload.get("base_revision"), "tier")
    product_id = payload.get("product_id") or (tier.product_id if tier else None)
    if not product_id:
        raise AppError("Product is required.", 422)
    if db.get(InsuranceProduct, product_id) is None:
        raise AppError("Product not found.", 404)
    if tier is None:
        tier = InsuranceProductTier(id=new_id(), product_id=product_id, tier_key="", name=payload["name"])
        db.add(tier)
    tier.product_id = product_id
    tier.tier_key = _slug(payload.get("tier_key") or payload["name"])
    tier.name = payload["name"].strip()
    tier.sort_order = payload.get("sort_order", 0)
    tier.status = payload.get("status", "active")
    if payload.get("id"):
        tier.revision += 1
    _audit(db, user, "business.tier.save", "insurance_product_tier", tier.id, {"new_revision": tier.revision})
    db.commit()
    db.refresh(tier)
    return _tier(tier)



def delete_business_tier(db, user, tier_id: str) -> None:
    _require_business(user)
    tier = db.get(InsuranceProductTier, tier_id)
    if tier is None:
        raise AppError("Tier not found.", 404)
    catalogs = db.scalars(select(BenefitCatalog).where(BenefitCatalog.tier_id == tier.id)).all()
    cat_ids = [c.id for c in catalogs]
    if cat_ids:
        revisions = db.scalars(select(BenefitCatalogRevision).where(BenefitCatalogRevision.catalog_id.in_(cat_ids))).all()
        rev_ids = [r.id for r in revisions]
        if rev_ids:
            packages = db.scalars(select(BenefitPackage).where(BenefitPackage.catalog_revision_id.in_(rev_ids))).all()
            pkg_ids = [p.id for p in packages]
            if pkg_ids:
                plans = db.scalars(select(BenefitPackagePlan).where(BenefitPackagePlan.package_id.in_(pkg_ids))).all()
                plan_ids = [pl.id for pl in plans]
                if plan_ids:
                    db.execute(delete(BenefitPackagePlanItem).where(BenefitPackagePlanItem.plan_id.in_(plan_ids)))
                    db.execute(delete(BenefitPackagePlan).where(BenefitPackagePlan.id.in_(plan_ids)))
                db.execute(delete(BenefitPackage).where(BenefitPackage.id.in_(pkg_ids)))
            db.execute(delete(CatalogOffering).where(CatalogOffering.catalog_revision_id.in_(rev_ids)))
            db.execute(delete(BenefitCatalogRevision).where(BenefitCatalogRevision.id.in_(rev_ids)))
        db.execute(delete(BenefitCatalog).where(BenefitCatalog.id.in_(cat_ids)))
    db.execute(text("UPDATE quotation_drafts SET tier_id = NULL WHERE tier_id = :tid"), {"tid": tier.id})
    _audit(db, user, "business.tier.delete", "insurance_product_tier", tier.id, {"tier_name": tier.name})
    db.delete(tier)
    db.commit()

