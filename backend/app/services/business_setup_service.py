"""Company-first business setup services for the revisioned v7 catalog."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, func, or_, select, text, update

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
    InsuranceCompany,
    InsuranceProduct,
    InsuranceProductTier,
    QuotationDraft,
    SourceDocument,
    new_id,
)
from app.rendering.render_context import canonical_context_hash
from app.services.asset_intake import create_derivative, validate_image_bytes
from app.storage.supabase import SupabaseStorage


BUSINESS_ROLES = frozenset({Role.STAFF.value, Role.ADMIN.value, Role.SUPER_ADMIN.value})
OFFERING_KINDS = frozenset({"base", "upgrade", "optional", "package_component"})
STATUSES = frozenset({"active", "inactive", "retired"})
ALIAS_KINDS = frozenset({"detection", "legal_name", "brand", "product", "compatibility"})


def _require_business(user) -> None:
    if user.role not in BUSINESS_ROLES:
        raise AppError("You do not have permission to manage Business Setup.", 403)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _require_revision(record, supplied: int | None, label: str) -> None:
    if supplied is None or record.revision != supplied:
        raise AppError(f"This {label} changed elsewhere. Reload before saving.", 409)


def _audit(db, user, action: str, entity_type: str, entity_id: str, details: dict) -> None:
    db.add(AuditEvent(actor_id=user.id, action=action, entity_type=entity_type, entity_id=entity_id, details=details))


def _asset_summary(asset: BusinessAsset | None) -> dict | None:
    if asset is None:
        return None
    return {
        "id": asset.id,
        "asset_key": asset.asset_key,
        "asset_kind": asset.asset_kind,
        "label": asset.label,
        "width_px": asset.width_px,
        "height_px": asset.height_px,
        "status": asset.status,
        "url": f"/business/assets/{asset.id}/content?profile=ui",
    }


def serialize_company(db, company: InsuranceCompany) -> dict:
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
    query = select(InsuranceCompany)
    count_query = select(func.count()).select_from(InsuranceCompany)
    term = search.strip()
    if term:
        pattern = f"%{term}%"
        predicate = or_(InsuranceCompany.name.ilike(pattern), InsuranceCompany.slug.ilike(pattern))
        query = query.where(predicate)
        count_query = count_query.where(predicate)
    total = int(db.scalar(count_query) or 0)
    items = db.scalars(
        query.order_by(InsuranceCompany.name.asc()).limit(page_size).offset((page - 1) * page_size)
    ).all()
    return {
        "items": [serialize_company(db, item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


def _normalize_alias(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _normalize_string_list(values, label: str) -> list[str]:
    output: list[str] = []
    for value in values or []:
        text = str(value).strip()
        if not text:
            continue
        if len(text) > 500:
            raise AppError(f"{label} entries must be at most 500 characters.", 422)
        output.append(text)
    return list(dict.fromkeys(output))


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
    company = db.get(InsuranceCompany, payload["company_id"])
    if company is None:
        raise AppError("Company not found.", 404)
    alias = str(payload["alias"]).strip()
    normalized = _normalize_alias(alias)
    if not normalized:
        raise AppError("Enter a usable detection phrase.", 422)
    kind = payload.get("alias_kind", "detection")
    if kind not in ALIAS_KINDS:
        raise AppError("Alias type is invalid.", 422)
    item = None
    if payload.get("id"):
        item = db.scalar(select(CompanyAlias).where(CompanyAlias.id == payload["id"]).with_for_update())
        if item is None:
            raise AppError("Company alias not found.", 404)
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


def get_business_company_workspace(db, user, company_id: str) -> dict:
    _require_business(user)
    company = db.get(InsuranceCompany, company_id)
    if company is None:
        raise AppError("Company not found.", 404)
    products = list(db.scalars(select(InsuranceProduct).where(InsuranceProduct.company_id == company_id)).all())
    product_ids = [item.id for item in products]
    tiers = list(
        db.scalars(
            select(InsuranceProductTier)
            .where(InsuranceProductTier.product_id.in_(product_ids))
            .order_by(InsuranceProductTier.sort_order, InsuranceProductTier.name)
        ).all()
    ) if product_ids else []
    catalogs = list(
        db.scalars(select(BenefitCatalog).where(BenefitCatalog.company_id == company_id).order_by(BenefitCatalog.name)).all()
    )
    return {
        "company": serialize_company(db, company),
        "products": [_product(item) for item in products],
        "tiers": [_tier(item) for item in tiers],
        "catalogs": [_catalog(db, item) for item in catalogs],
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
        if asset is None or asset.asset_kind != "company_logo":
            raise AppError("Select a valid company logo asset.", 422)
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


def save_business_product(db, user, payload: dict) -> dict:
    _require_business(user)
    if db.get(InsuranceCompany, payload["company_id"]) is None:
        raise AppError("Company not found.", 404)
    product = None
    if payload.get("id"):
        product = db.scalar(select(InsuranceProduct).where(InsuranceProduct.id == payload["id"]).with_for_update())
        if product is None:
            raise AppError("Product not found.", 404)
        _require_revision(product, payload.get("base_revision"), "product")
    if product is None:
        product = InsuranceProduct(id=new_id(), company_id=payload["company_id"], product_key="", name=payload["name"])
        db.add(product)
    product.company_id = payload["company_id"]
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


def save_business_tier(db, user, payload: dict) -> dict:
    _require_business(user)
    if db.get(InsuranceProduct, payload["product_id"]) is None:
        raise AppError("Product not found.", 404)
    tier = None
    if payload.get("id"):
        tier = db.scalar(select(InsuranceProductTier).where(InsuranceProductTier.id == payload["id"]).with_for_update())
        if tier is None:
            raise AppError("Tier not found.", 404)
        _require_revision(tier, payload.get("base_revision"), "tier")
    if tier is None:
        tier = InsuranceProductTier(id=new_id(), product_id=payload["product_id"], tier_key="", name=payload["name"])
        db.add(tier)
    tier.product_id = payload["product_id"]
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


VARIANT_TYPES = frozenset({"money", "distance", "duration"})


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


def serialize_concept(db, item: BenefitConcept) -> dict:
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
        "sort_order": item.sort_order,
        "default_asset": _asset_summary(db.get(BusinessAsset, item.default_asset_id)) if item.default_asset_id else None,
        "revision": item.revision,
        "status": item.status,
    }


def list_benefit_concepts(db, user, *, search: str, page: int, page_size: int) -> dict:
    _require_business(user)
    query = select(BenefitConcept)
    count_query = select(func.count()).select_from(BenefitConcept)
    if search.strip():
        pattern = f"%{search.strip()}%"
        predicate = or_(BenefitConcept.label.ilike(pattern), BenefitConcept.concept_key.ilike(pattern))
        query = query.where(predicate)
        count_query = count_query.where(predicate)
    total = int(db.scalar(count_query) or 0)
    rows = db.scalars(query.order_by(BenefitConcept.sort_order.asc(), BenefitConcept.label.asc()).limit(page_size).offset((page - 1) * page_size)).all()
    return {"items": [serialize_concept(db, row) for row in rows], "total": total, "page": page, "page_size": page_size}


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
    concept.status = payload.get("status", "active")
    if payload.get("id"):
        concept.revision += 1
    _audit(db, user, "business.benefit_concept.save", "benefit_concept", concept.id, {"new_revision": concept.revision})
    db.commit()
    db.refresh(concept)
    return serialize_concept(db, concept)


def list_business_assets(db, user, *, search: str, kind: str | None, page: int, page_size: int) -> dict:
    _require_business(user)
    query = select(BusinessAsset)
    count_query = select(func.count()).select_from(BusinessAsset)
    predicates = []
    if search.strip():
        pattern = f"%{search.strip()}%"
        predicates.append(or_(BusinessAsset.label.ilike(pattern), BusinessAsset.original_filename.ilike(pattern)))
    if kind:
        predicates.append(BusinessAsset.asset_kind == kind)
    for predicate in predicates:
        query = query.where(predicate)
        count_query = count_query.where(predicate)
    total = int(db.scalar(count_query) or 0)
    rows = db.scalars(query.order_by(BusinessAsset.label).limit(page_size).offset((page - 1) * page_size)).all()
    return {"items": [_asset_summary(row) for row in rows], "total": total, "page": page, "page_size": page_size}


def upload_business_asset(db, settings, user, *, filename: str, label: str, kind: str, data: bytes) -> dict:
    _require_business(user)
    if kind not in {"benefit_art", "company_logo", "template_background", "decorative"}:
        raise AppError("Asset kind is invalid.", 422)
    try:
        technical = validate_image_bytes(
            data,
            filename,
            max_bytes=settings.max_asset_bytes,
            max_pixels=settings.max_asset_pixels,
        )
    except ValueError as exc:
        raise AppError(str(exc), 422) from exc
    existing = db.scalar(select(BusinessAsset).where(BusinessAsset.content_hash == technical["content_hash"]))
    if existing:
        return _asset_summary(existing) or {}

    def extension(content_type: str) -> str:
        return {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[content_type]

    content_hash = technical["content_hash"]
    original_path = f"assets/original/{content_hash[:2]}/{content_hash}.{extension(technical['content_type'])}"
    derivatives = {
        "ui": create_derivative(data, max_width=512, max_height=512, quality=85),
        "pdf": create_derivative(data, max_width=1_600, max_height=1_600, quality=92),
    }
    storage = SupabaseStorage(settings)
    uploaded: list[str] = []
    try:
        storage.upload_asset(original_path, data, technical["content_type"])
        uploaded.append(original_path)
        derivative_manifest = {}
        for profile, derivative in derivatives.items():
            derivative_path = f"assets/derivative/{profile}/{derivative.content_hash[:2]}/{derivative.content_hash}.{extension(derivative.content_type)}"
            storage.upload_asset(derivative_path, derivative.data, derivative.content_type)
            uploaded.append(derivative_path)
            derivative_manifest[profile] = {
                "storage_path": derivative_path,
                "content_type": derivative.content_type,
                "content_hash": derivative.content_hash,
                "width_px": derivative.width_px,
                "height_px": derivative.height_px,
            }
        asset = BusinessAsset(
            id=new_id(),
            asset_key=f"upload:{kind}:{content_hash}",
            asset_kind=kind,
            label=label.strip() or Path(filename).stem,
            original_filename=filename,
            content_type=technical["content_type"],
            content_hash=content_hash,
            storage_path=original_path,
            size_bytes=technical["size_bytes"],
            width_px=technical["width_px"],
            height_px=technical["height_px"],
            has_transparency=technical["has_transparency"],
            derivative_manifest=derivative_manifest,
            revision=1,
            status="active" if kind != "benefit_art" else "unassigned",
        )
        db.add(asset)
        _audit(db, user, "business.asset.upload", "business_asset", asset.id, {"kind": kind, "content_hash": content_hash})
        db.commit()
        db.refresh(asset)
        return _asset_summary(asset) or {}
    except Exception:
        db.rollback()
        for storage_path in reversed(uploaded):
            try:
                storage.delete_pdf(storage_path)
            except Exception:
                pass
        raise


def create_benefit_catalog(db, user, payload: dict) -> dict:
    _require_business(user)
    company = db.get(InsuranceCompany, payload["company_id"])
    if company is None:
        raise AppError("Company not found.", 404)
    context_ids = _validate_catalog_context(db, payload)
    catalog = BenefitCatalog(
        id=new_id(), company_id=company.id, product_id=payload.get("product_id"), tier_id=payload.get("tier_id"),
        name=payload["name"].strip(), revision=1, status="draft", **context_ids,
    )
    revision = BenefitCatalogRevision(
        id=new_id(), catalog_id=catalog.id, revision_number=1, state="draft",
        source_document_ids=[], content_hash=canonical_context_hash({}),
    )
    db.add_all([catalog, revision])
    _audit(db, user, "business.catalog.create", "benefit_catalog", catalog.id, {"revision": 1})
    db.commit()
    db.refresh(catalog)
    return _catalog(db, catalog)


def _validate_catalog_context(db, payload: dict) -> dict:
    """Resolve and validate the hierarchy path context ids for a catalog."""
    context: dict[str, str | None] = {}
    from app.models.tables import CoverageType, Segment, VehicleCategory, VehicleSubcategory

    checks = (
        ("segment_id", Segment),
        ("vehicle_category_id", VehicleCategory),
        ("vehicle_subcategory_id", VehicleSubcategory),
        ("coverage_type_id", CoverageType),
    )
    for field, model in checks:
        value = payload.get(field)
        if value and db.get(model, value) is None:
            raise AppError(f"{field.replace('_', ' ')} is invalid.", 422)
        context[field] = value or None
    return context


def update_catalog_context(db, user, catalog_id: str, payload: dict) -> dict:
    """Set the hierarchy path context of a catalog (segment/vehicle/coverage)."""
    _require_business(user)
    catalog = db.scalar(select(BenefitCatalog).where(BenefitCatalog.id == catalog_id).with_for_update())
    if catalog is None:
        raise AppError("Catalog not found.", 404)
    _require_revision(catalog, payload.get("base_revision"), "catalog")
    context = _validate_catalog_context(db, payload)
    for field, value in context.items():
        setattr(catalog, field, value)
    catalog.revision += 1
    _audit(db, user, "business.catalog.context", "benefit_catalog", catalog.id, {
        "new_revision": catalog.revision, **context,
    })
    db.commit()
    db.refresh(catalog)
    return _catalog(db, catalog)


def _offering(item: CatalogOffering) -> dict:
    return {
        "id": item.id,
        "catalog_revision_id": item.catalog_revision_id,
        "offering_key": item.offering_key,
        "concept_id": item.concept_id,
        "offering_kind": item.offering_kind,
        "applies_to_type": item.applies_to_type,
        "applies_to_id": item.applies_to_id,
        "role": item.role,
        "label_override": item.label_override,
        "typed_value": item.typed_value,
        "display_value": item.display_value,
        "optional_price": item.optional_price,
        "source_document_id": item.source_document_id,
        "source_citation": item.source_citation,
        "source_aliases": item.source_aliases,
        "presentation_facet_ids": item.presentation_facet_ids,
        "sort_order": item.sort_order,
        "status": item.status,
    }


def _package(item: BenefitPackage) -> dict:
    return {
        "id": item.id,
        "catalog_revision_id": item.catalog_revision_id,
        "package_key": item.package_key,
        "name": item.name,
        "package_kind": item.package_kind,
        "sort_order": item.sort_order,
        "revision": item.revision,
        "status": item.status,
    }


def _revision_content_payload(db, revision: BenefitCatalogRevision) -> dict:
    """Canonical revision content: offerings + packages + package-scoped aliases."""
    offerings = [
        _offering(row)
        for row in db.scalars(
            select(CatalogOffering)
            .where(CatalogOffering.catalog_revision_id == revision.id)
            .order_by(CatalogOffering.sort_order, CatalogOffering.offering_key)
        ).all()
    ]
    packages = [
        _package(row)
        for row in db.scalars(
            select(BenefitPackage)
            .where(BenefitPackage.catalog_revision_id == revision.id)
            .order_by(BenefitPackage.sort_order, BenefitPackage.package_key)
        ).all()
    ]
    package_ids = {item["id"] for item in packages}
    from app.models.tables import BenefitAlias

    aliases = [
        {
            "benefit_id": item.benefit_id,
            "phrase": item.phrase,
            "normalized_phrase": item.normalized_phrase,
            "scope": item.scope,
            "package_id": item.package_id,
            "status": item.status,
        }
        for item in db.scalars(select(BenefitAlias)).all()
        if item.package_id and str(item.package_id) in package_ids
    ]
    aliases.sort(key=lambda item: (item["scope"], item["normalized_phrase"], str(item["package_id"])))
    return {"offerings": offerings, "packages": packages, "aliases": aliases}


def _validate_assignment_context(db, catalog: BenefitCatalog, revision: BenefitCatalogRevision, payload: dict) -> dict:
    """Resolve and validate applies_to/role against the catalog context."""
    legacy = bool(catalog.tier_id) and not catalog.package_id
    applies_type = payload.get("applies_to_type")
    applies_id = payload.get("applies_to_id")
    role = payload.get("role")
    if applies_type is None and not legacy:
        applies_type = "package" if catalog.package_id else "product"
        applies_id = catalog.package_id if catalog.package_id else None
    elif applies_type == "package" and catalog.package_id:
        applies_id = catalog.package_id
    if applies_type is not None and applies_type not in {"product", "package", "bundle"}:
        raise AppError("Assignment target type must be product, package, or bundle.", 422)
    if role is not None and role not in {"included", "addon_option", "bundle_component"}:
        raise AppError("Assignment role is invalid.", 422)
    if applies_type is not None:
        if applies_type == "package":
            if catalog.package_id is None:
                raise AppError("This catalog has no package; assignments must be product-level.", 422)
            applies_id = catalog.package_id
        elif applies_type == "bundle":
            if catalog.package_id is None:
                raise AppError("Add-on bundles require a packaged catalog.", 422)
            bundle = db.get(BenefitPackage, applies_id) if applies_id else None
            if bundle is None or bundle.catalog_revision_id != revision.id or bundle.package_kind != "addon_bundle":
                raise AppError("Choose an add-on bundle from this catalog's draft revision.", 422)
        elif applies_type == "product" and catalog.package_id is not None:
            raise AppError("This catalog is packaged; assign benefits to the package instead.", 422)
    optional_price = payload.get("optional_price")
    if optional_price is not None:
        if not isinstance(optional_price, dict):
            raise AppError("Optional price must be a typed value object.", 422)
        if "type" in optional_price:
            try:
                BenefitValue.model_validate(optional_price)
            except Exception as exc:
                raise AppError("Optional price is an invalid typed value.", 422) from exc
    payload["applies_to_type"] = applies_type
    payload["applies_to_id"] = applies_id if applies_type is not None else None
    return payload


def save_catalog_offering(db, user, catalog_id: str, payload: dict) -> dict:
    _require_business(user)
    catalog = db.scalar(select(BenefitCatalog).where(BenefitCatalog.id == catalog_id).with_for_update())
    if catalog is None:
        raise AppError("Catalog not found.", 404)
    revision = db.scalar(
        select(BenefitCatalogRevision)
        .where(BenefitCatalogRevision.catalog_id == catalog.id, BenefitCatalogRevision.state == "draft")
        .order_by(BenefitCatalogRevision.revision_number.desc())
    )
    if revision is None:
        revisions = list(
            db.scalars(
                select(BenefitCatalogRevision)
                .where(BenefitCatalogRevision.catalog_id == catalog.id)
                .order_by(BenefitCatalogRevision.revision_number.desc())
            ).all()
        )
        if revisions:
            source = revisions[0]
            draft = BenefitCatalogRevision(
                id=new_id(), catalog_id=catalog.id, revision_number=source.revision_number + 1, state="draft",
                source_document_ids=[], content_hash=canonical_context_hash(_revision_content_payload(db, source)),
            )
            db.add(draft)
            db.flush()
            package_map: dict[str, str] = {}
            for package in db.scalars(
                select(BenefitPackage).where(BenefitPackage.catalog_revision_id == source.id).order_by(BenefitPackage.sort_order, BenefitPackage.package_key)
            ).all():
                copy_pkg = BenefitPackage(
                    id=new_id(), catalog_revision_id=draft.id, package_key=package.package_key, name=package.name,
                    package_kind=package.package_kind, sort_order=package.sort_order, status=package.status,
                )
                db.add(copy_pkg)
                package_map[package.id] = copy_pkg.id
            db.flush()
            for off in db.scalars(
                select(CatalogOffering).where(CatalogOffering.catalog_revision_id == source.id).order_by(CatalogOffering.sort_order, CatalogOffering.offering_key)
            ).all():
                db.add(CatalogOffering(
                    id=new_id(), catalog_revision_id=draft.id, offering_key=off.offering_key,
                    concept_id=off.concept_id, offering_kind=off.offering_kind,
                    applies_to_type=off.applies_to_type,
                    applies_to_id=package_map.get(str(off.applies_to_id)) if off.applies_to_id else None,
                    role=off.role, label_override=off.label_override, typed_value=off.typed_value,
                    display_value=off.display_value, optional_price=off.optional_price,
                    source_document_id=off.source_document_id, source_citation=off.source_citation,
                    source_aliases=list(off.source_aliases or []),
                    presentation_facet_ids=list(off.presentation_facet_ids or []),
                    sort_order=off.sort_order, status=off.status,
                ))
            if catalog.package_id and catalog.package_id in package_map:
                catalog.package_id = package_map[catalog.package_id]
            catalog.revision += 1
            catalog.status = "draft"
            db.flush()
            revision = draft
        else:
            draft = BenefitCatalogRevision(
                id=new_id(), catalog_id=catalog.id, revision_number=1, state="draft",
                source_document_ids=[], content_hash=canonical_context_hash({}),
            )
            db.add(draft)
            db.flush()
            catalog.revision = 1
            catalog.status = "draft"
            db.flush()
            revision = draft
    if payload.get("offering_kind") and payload["offering_kind"] not in OFFERING_KINDS:
        raise AppError("Offering kind is invalid.", 422)
    if payload.get("concept_id") and db.get(BenefitConcept, payload["concept_id"]) is None:
        raise AppError("Benefit concept not found.", 404)
    if payload.get("source_document_id") and db.get(SourceDocument, payload["source_document_id"]) is None:
        raise AppError("Source document not found.", 422)
    payload = _validate_assignment_context(db, catalog, revision, payload)
    offering = None
    if payload.get("id"):
        offering = db.get(CatalogOffering, payload["id"])
        if offering is None or offering.catalog_revision_id != revision.id:
            # If from previous revision, find matching concept in draft revision
            if payload.get("concept_id"):
                offering = db.scalar(
                    select(CatalogOffering).where(
                        CatalogOffering.catalog_revision_id == revision.id,
                        CatalogOffering.concept_id == payload["concept_id"],
                    )
                )
    if offering is None:
        offering = CatalogOffering(
            id=new_id(),
            catalog_revision_id=revision.id,
            offering_key=payload.get("offering_key", f"offering-{new_id()[:8]}"),
            concept_id=payload["concept_id"],
            offering_kind=payload.get("offering_kind", "base"),
        )
        db.add(offering)
    for key in (
        "offering_key", "concept_id", "offering_kind", "applies_to_type", "applies_to_id", "role",
        "label_override", "typed_value", "display_value", "optional_price", "source_document_id",
        "source_citation", "source_aliases", "presentation_facet_ids", "sort_order", "status",
    ):
        if key in payload:
            setattr(offering, key, payload[key])
    db.flush()
    revision.content_hash = canonical_context_hash(_revision_content_payload(db, revision))
    revision.source_document_ids = sorted({row.source_document_id for row in db.scalars(
        select(CatalogOffering).where(CatalogOffering.catalog_revision_id == revision.id)
    ).all() if row.source_document_id})
    catalog.revision += 1
    _audit(db, user, "business.catalog_offering.save", "catalog_offering", offering.id, {"catalog_id": catalog.id, "new_revision": catalog.revision})
    db.commit()
    db.refresh(offering)
    return _offering(offering)


def remove_catalog_offering(db, user, catalog_id: str, offering_id: str, *, base_revision: int | None = None) -> None:
    _require_business(user)
    catalog = db.scalar(select(BenefitCatalog).where(BenefitCatalog.id == catalog_id).with_for_update())
    if catalog is None:
        raise AppError("Catalog not found.", 404)
    revision = db.scalar(
        select(BenefitCatalogRevision)
        .where(BenefitCatalogRevision.catalog_id == catalog.id, BenefitCatalogRevision.state == "draft")
        .order_by(BenefitCatalogRevision.revision_number.desc())
    )
    if revision is None:
        revisions = list(
            db.scalars(
                select(BenefitCatalogRevision)
                .where(BenefitCatalogRevision.catalog_id == catalog.id)
                .order_by(BenefitCatalogRevision.revision_number.desc())
            ).all()
        )
        if revisions:
            source = revisions[0]
            draft = BenefitCatalogRevision(
                id=new_id(), catalog_id=catalog.id, revision_number=source.revision_number + 1, state="draft",
                source_document_ids=[], content_hash=canonical_context_hash(_revision_content_payload(db, source)),
            )
            db.add(draft)
            db.flush()
            package_map: dict[str, str] = {}
            for package in db.scalars(
                select(BenefitPackage).where(BenefitPackage.catalog_revision_id == source.id).order_by(BenefitPackage.sort_order, BenefitPackage.package_key)
            ).all():
                copy_pkg = BenefitPackage(
                    id=new_id(), catalog_revision_id=draft.id, package_key=package.package_key, name=package.name,
                    package_kind=package.package_kind, sort_order=package.sort_order, status=package.status,
                )
                db.add(copy_pkg)
                package_map[package.id] = copy_pkg.id
            db.flush()
            old_offering = db.get(CatalogOffering, offering_id)
            for off in db.scalars(
                select(CatalogOffering).where(CatalogOffering.catalog_revision_id == source.id).order_by(CatalogOffering.sort_order, CatalogOffering.offering_key)
            ).all():
                if off.id == offering_id or (old_offering and off.concept_id == old_offering.concept_id and off.applies_to_id == old_offering.applies_to_id):
                    continue
                db.add(CatalogOffering(
                    id=new_id(), catalog_revision_id=draft.id, offering_key=off.offering_key,
                    concept_id=off.concept_id, offering_kind=off.offering_kind,
                    applies_to_type=off.applies_to_type,
                    applies_to_id=package_map.get(str(off.applies_to_id)) if off.applies_to_id else None,
                    role=off.role, label_override=off.label_override, typed_value=off.typed_value,
                    display_value=off.display_value, optional_price=off.optional_price,
                    source_document_id=off.source_document_id, source_citation=off.source_citation,
                    source_aliases=list(off.source_aliases or []),
                    presentation_facet_ids=list(off.presentation_facet_ids or []),
                    sort_order=off.sort_order, status=off.status,
                ))
            if catalog.package_id and catalog.package_id in package_map:
                catalog.package_id = package_map[catalog.package_id]
            catalog.revision += 1
            catalog.status = "draft"
            db.commit()
            return
        else:
            draft = BenefitCatalogRevision(
                id=new_id(), catalog_id=catalog.id, revision_number=1, state="draft",
                source_document_ids=[], content_hash=canonical_context_hash({}),
            )
            db.add(draft)
            db.flush()
            catalog.revision = 1
            catalog.status = "draft"
            db.commit()
            return
    offering = db.get(CatalogOffering, offering_id)
    if offering is not None:
        db.delete(offering)
        db.flush()
        revision.content_hash = canonical_context_hash(_revision_content_payload(db, revision))
        catalog.revision += 1
        _audit(db, user, "business.catalog_offering.delete", "catalog_offering", offering_id, {"catalog_id": catalog.id, "new_revision": catalog.revision})
        db.commit()


def create_new_draft_revision(db, user, catalog_id: str, *, base_revision: int) -> dict:
    """Open a new draft revision copying the latest revision forward.

    Packages and assignments are revision-scoped rows, so the copy re-creates
    them with new ids in the new draft and re-links the catalog's package_id
    (and package-scoped benefit aliases) to the copies.
    """
    _require_business(user)
    catalog = db.scalar(select(BenefitCatalog).where(BenefitCatalog.id == catalog_id).with_for_update())
    if catalog is None:
        raise AppError("Catalog not found.", 404)
    if catalog.revision != base_revision:
        raise AppError("This catalog changed elsewhere. Reload before editing.", 409)
    revisions = list(
        db.scalars(
            select(BenefitCatalogRevision)
            .where(BenefitCatalogRevision.catalog_id == catalog.id)
            .order_by(BenefitCatalogRevision.revision_number.desc())
        ).all()
    )
    if any(item.state == "draft" for item in revisions):
        raise AppError("This catalog already has a draft revision to edit.", 409)
    if not revisions:
        raise AppError("This catalog has no revision to copy from.", 409)
    source = revisions[0]
    draft = BenefitCatalogRevision(
        id=new_id(), catalog_id=catalog.id, revision_number=source.revision_number + 1, state="draft",
        source_document_ids=[], content_hash=canonical_context_hash(_revision_content_payload(db, source)),
    )
    db.add(draft)
    db.flush()

    package_map: dict[str, str] = {}
    for package in db.scalars(
        select(BenefitPackage).where(BenefitPackage.catalog_revision_id == source.id).order_by(BenefitPackage.sort_order, BenefitPackage.package_key)
    ).all():
        copy = BenefitPackage(
            id=new_id(), catalog_revision_id=draft.id, package_key=package.package_key, name=package.name,
            package_kind=package.package_kind, sort_order=package.sort_order, status=package.status,
        )
        db.add(copy)
        package_map[package.id] = copy.id
    db.flush()
    for offering in db.scalars(
        select(CatalogOffering).where(CatalogOffering.catalog_revision_id == source.id).order_by(CatalogOffering.sort_order, CatalogOffering.offering_key)
    ).all():
        db.add(CatalogOffering(
            id=new_id(), catalog_revision_id=draft.id, offering_key=offering.offering_key,
            concept_id=offering.concept_id, offering_kind=offering.offering_kind,
            applies_to_type=offering.applies_to_type,
            applies_to_id=package_map.get(str(offering.applies_to_id)) if offering.applies_to_id else None,
            role=offering.role, label_override=offering.label_override, typed_value=offering.typed_value,
            display_value=offering.display_value, optional_price=offering.optional_price,
            source_document_id=offering.source_document_id, source_citation=offering.source_citation,
            source_aliases=list(offering.source_aliases or []),
            presentation_facet_ids=list(offering.presentation_facet_ids or []),
            sort_order=offering.sort_order, status=offering.status,
        ))
    if catalog.package_id and str(catalog.package_id) in package_map:
        catalog.package_id = package_map[str(catalog.package_id)]
    from app.models.tables import BenefitAlias

    for alias in db.scalars(select(BenefitAlias).where(BenefitAlias.package_id.is_not(None))).all():
        if str(alias.package_id) in package_map:
            alias.package_id = package_map[str(alias.package_id)]
    catalog.revision += 1
    catalog.status = "draft"
    _audit(db, user, "business.catalog.new_draft", "benefit_catalog_revision", draft.id, {
        "catalog_id": catalog.id, "source_revision": source.revision_number, "new_revision": draft.revision_number,
    })
    db.commit()
    db.refresh(catalog)
    return _catalog(db, catalog)


def publish_catalog_revision(db, user, catalog_id: str, *, base_revision: int) -> dict:
    _require_business(user)
    catalog = db.scalar(select(BenefitCatalog).where(BenefitCatalog.id == catalog_id).with_for_update())
    if catalog is None:
        raise AppError("Catalog not found.", 404)
    if catalog.revision != base_revision:
        raise AppError("This catalog changed elsewhere. Reload before publishing.", 409)
    revisions = list(
        db.scalars(
            select(BenefitCatalogRevision)
            .where(BenefitCatalogRevision.catalog_id == catalog.id)
            .order_by(BenefitCatalogRevision.revision_number.desc())
        ).all()
    )
    draft = next((item for item in revisions if item.state == "draft"), None)
    if draft is None:
        raise AppError("This catalog has no draft revision to publish.", 409)
    offerings = list(
        db.scalars(
            select(CatalogOffering)
            .where(CatalogOffering.catalog_revision_id == draft.id)
            .order_by(CatalogOffering.sort_order, CatalogOffering.offering_key)
        ).all()
    )
    if not offerings:
        raise AppError("Add at least one benefit offering before publishing.", 422)
    content_hash = canonical_context_hash(_revision_content_payload(db, draft))
    matching = [item for item in revisions if item.state == "published" and item.content_hash == content_hash]
    if matching:
        return _catalog(db, catalog)
    draft.state = "published"
    draft.content_hash = content_hash
    draft.published_by = user.id
    draft.published_at = datetime.now(timezone.utc)
    catalog.status = "published"
    catalog.revision += 1
    _audit(db, user, "business.catalog.publish", "benefit_catalog_revision", draft.id, {
        "catalog_id": catalog.id,
        "revision_number": draft.revision_number,
        "content_hash": content_hash,
        "offering_count": len(offerings),
        "base_revision": base_revision,
        "new_revision": catalog.revision,
    })
    db.commit()
    db.refresh(catalog)
    return _catalog(db, catalog)


def get_catalog_workspace(db, user, catalog_id: str) -> dict:
    _require_business(user)
    catalog = db.get(BenefitCatalog, catalog_id)
    if catalog is None:
        raise AppError("Catalog not found.", 404)
    revisions = list(
        db.scalars(
            select(BenefitCatalogRevision)
            .where(BenefitCatalogRevision.catalog_id == catalog.id)
            .order_by(BenefitCatalogRevision.revision_number.desc())
        ).all()
    )
    revision = next((item for item in revisions if item.state == "draft"), revisions[0] if revisions else None)
    if revision is None:
        raise AppError("Catalog has no revision.", 409)
    offerings = list(
        db.scalars(
            select(CatalogOffering)
            .where(CatalogOffering.catalog_revision_id == revision.id)
            .order_by(CatalogOffering.sort_order, CatalogOffering.offering_key)
        ).all()
    )
    concepts = {item.id: item for item in db.scalars(select(BenefitConcept)).all()}
    relations = list(
        db.scalars(
            select(BenefitRelation)
            .where(BenefitRelation.catalog_revision_id == revision.id)
            .order_by(BenefitRelation.sort_order, BenefitRelation.branch_key)
        ).all()
    )
    packages = list(
        db.scalars(select(BenefitPackage).where(BenefitPackage.catalog_revision_id == revision.id).order_by(BenefitPackage.name)).all()
    )
    package_ids = [item.id for item in packages]
    plans = list(
        db.scalars(
            select(BenefitPackagePlan)
            .where(BenefitPackagePlan.package_id.in_(package_ids))
            .order_by(BenefitPackagePlan.sort_order, BenefitPackagePlan.name)
        ).all()
    ) if package_ids else []
    plan_ids = [item.id for item in plans]
    plan_items = list(
        db.scalars(
            select(BenefitPackagePlanItem)
            .where(BenefitPackagePlanItem.plan_id.in_(plan_ids))
            .order_by(BenefitPackagePlanItem.sort_order)
        ).all()
    ) if plan_ids else []
    return {
        "catalog": _catalog(db, catalog),
        "active_revision": {
            "id": revision.id,
            "revision_number": revision.revision_number,
            "state": revision.state,
            "content_hash": revision.content_hash,
        },
        "offerings": [
            {
                **_offering(item),
                "concept": serialize_concept(db, concepts[item.concept_id]) if item.concept_id in concepts else None,
            }
            for item in offerings
        ],
        "relations": [
            {
                "id": item.id,
                "from_offering_id": item.from_offering_id,
                "to_offering_id": item.to_offering_id,
                "relation_kind": item.relation_kind,
                "branch_key": item.branch_key,
                "sort_order": item.sort_order,
            }
            for item in relations
        ],
        "packages": [_package(item) for item in packages],
        "plans": [
            {
                "id": item.id,
                "package_id": item.package_id,
                "plan_key": item.plan_key,
                "name": item.name,
                "sort_order": item.sort_order,
                "status": item.status,
            }
            for item in plans
        ],
        "plan_items": [
            {
                "id": item.id,
                "plan_id": item.plan_id,
                "offering_id": item.offering_id,
                "typed_value_override": item.typed_value_override,
                "sort_order": item.sort_order,
            }
            for item in plan_items
        ],
    }


def list_source_documents(db, user, *, page: int, page_size: int) -> dict:
    _require_business(user)
    total = int(db.scalar(select(func.count()).select_from(SourceDocument)) or 0)
    rows = db.scalars(
        select(SourceDocument).order_by(SourceDocument.created_at.desc()).limit(page_size).offset((page - 1) * page_size)
    ).all()
    return {
        "items": [
            {
                "id": item.id,
                "issuer": item.issuer,
                "title": item.title,
                "reference_url": item.reference_url,
                "effective_from": item.effective_from.isoformat() if item.effective_from else None,
                "effective_to": item.effective_to.isoformat() if item.effective_to else None,
                "verification_status": item.verification_status,
                "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
            }
            for item in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
