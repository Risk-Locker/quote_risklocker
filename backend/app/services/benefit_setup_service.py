"""Benefits-refactor setup services: hierarchy dimensions and scoped benefit aliases.

Hierarchy: segments, vehicle categories/subcategories, coverage types — the
database-driven path dimensions a product/package configuration hangs off.
Aliases: scoped phrase -> Global Benefit (global | company | product | package)
used by extraction (Task 6) and by the Global Benefits manager.

Hierarchy rows follow the CompanyAlias pattern (simple admin-extendable
dictionaries): no optimistic revision counter; save/retire only.
"""

from __future__ import annotations

import re

from sqlalchemy import func, or_, select

from app.core.errors import AppError
from app.models.enums import Role
from app.models.tables import (
    AuditEvent,
    BenefitAlias,
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    BenefitPackage,
    CatalogOffering,
    CoverageType,
    InsuranceCompany,
    InsuranceProduct,
    Segment,
    VehicleCategory,
    VehicleSubcategory,
    new_id,
)
from app.rendering.render_context import canonical_context_hash
from app.services.business_setup_service import _revision_content_payload


BUSINESS_ROLES = frozenset({Role.STAFF.value, Role.ADMIN.value, Role.SUPER_ADMIN.value})
STATUSES = frozenset({"active", "inactive", "retired"})
ALIAS_SCOPES = frozenset({"global", "company", "product", "package"})
PACKAGE_KINDS = frozenset({"comprehensive", "addon_bundle"})


def _require_business(user) -> None:
    if user.role not in BUSINESS_ROLES:
        raise AppError("You do not have permission to manage Business Setup.", 403)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _normalize_phrase(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _audit(db, user, action: str, entity_type: str, entity_id: str, details: dict) -> None:
    db.add(AuditEvent(actor_id=user.id, action=action, entity_type=entity_type, entity_id=entity_id, details=details))


def _serialize_hierarchy(item) -> dict:
    key = (
        item.segment_key
        if isinstance(item, Segment)
        else item.category_key
        if isinstance(item, VehicleCategory)
        else item.subcategory_key
        if isinstance(item, VehicleSubcategory)
        else item.coverage_key
    )
    return {
        "id": item.id,
        "key": key,
        "name": item.name,
        "sort_order": item.sort_order,
        "status": item.status,
    }


def _paged(db, model, search_fields: tuple[str, ...], *, extra_predicates: list | None, search: str, page: int, page_size: int, order_field: str) -> dict:
    query = select(model)
    count_query = select(func.count()).select_from(model)
    predicates = list(extra_predicates or [])
    term = search.strip()
    if term:
        pattern = f"%{term}%"
        predicates.append(or_(*[getattr(model, field).ilike(pattern) for field in search_fields]))
    for predicate in predicates:
        query = query.where(predicate)
        count_query = count_query.where(predicate)
    total = int(db.scalar(count_query) or 0)
    rows = db.scalars(
        query.order_by(getattr(model, order_field).asc(), model.sort_order.asc()).limit(page_size).offset((page - 1) * page_size)
    ).all()
    return {
        "items": [_serialize_hierarchy(item) for item in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


# --- Segments ---


def list_segments(db, user, *, search: str, page: int, page_size: int) -> dict:
    _require_business(user)
    return _paged(db, Segment, ("name", "segment_key"), extra_predicates=None, search=search, page=page, page_size=page_size, order_field="segment_key")


def save_segment(db, user, payload: dict) -> dict:
    _require_business(user)
    item = None
    if payload.get("id"):
        item = db.scalar(select(Segment).where(Segment.id == payload["id"]).with_for_update())
        if item is None:
            raise AppError("Segment not found.", 404)
    proposed_key = _slug(payload.get("segment_key") or payload["name"])
    if not proposed_key:
        raise AppError("Segment key is invalid.", 422)
    duplicate = db.scalar(
        select(Segment).where(
            Segment.segment_key == proposed_key,
            Segment.id != (item.id if item else "00000000-0000-0000-0000-000000000000"),
        )
    )
    if duplicate:
        raise AppError("A segment already uses this key.", 409)
    if item is None:
        item = Segment(id=new_id(), segment_key=proposed_key, name=payload["name"])
        db.add(item)
    else:
        item.segment_key = proposed_key
    item.name = payload["name"].strip()
    item.sort_order = max(0, int(payload.get("sort_order") or 0))
    item.status = payload.get("status", "active")
    if item.status not in STATUSES:
        raise AppError("Segment status is invalid.", 422)
    _audit(db, user, "business.segment.save", "segment", item.id, {"new_key": item.segment_key})
    db.commit()
    db.refresh(item)
    return _serialize_hierarchy(item)


def retire_segment(db, user, segment_id: str) -> None:
    _require_business(user)
    item = db.scalar(select(Segment).where(Segment.id == segment_id).with_for_update())
    if item is None:
        raise AppError("Segment not found.", 404)
    item.status = "retired"
    _audit(db, user, "business.segment.retire", "segment", item.id, {})
    db.commit()


# --- Vehicle categories / subcategories ---


def list_vehicle_categories(db, user, *, search: str, page: int, page_size: int) -> dict:
    _require_business(user)
    return _paged(db, VehicleCategory, ("name", "category_key"), extra_predicates=None, search=search, page=page, page_size=page_size, order_field="category_key")


def save_vehicle_category(db, user, payload: dict) -> dict:
    _require_business(user)
    item = None
    if payload.get("id"):
        item = db.scalar(select(VehicleCategory).where(VehicleCategory.id == payload["id"]).with_for_update())
        if item is None:
            raise AppError("Vehicle category not found.", 404)
    proposed_key = _slug(payload.get("category_key") or payload["name"])
    if not proposed_key:
        raise AppError("Vehicle category key is invalid.", 422)
    duplicate = db.scalar(
        select(VehicleCategory).where(
            VehicleCategory.category_key == proposed_key,
            VehicleCategory.id != (item.id if item else "00000000-0000-0000-0000-000000000000"),
        )
    )
    if duplicate:
        raise AppError("A vehicle category already uses this key.", 409)
    if item is None:
        item = VehicleCategory(id=new_id(), category_key=proposed_key, name=payload["name"])
        db.add(item)
    else:
        item.category_key = proposed_key
    item.name = payload["name"].strip()
    item.sort_order = max(0, int(payload.get("sort_order") or 0))
    item.status = payload.get("status", "active")
    if item.status not in STATUSES:
        raise AppError("Vehicle category status is invalid.", 422)
    _audit(db, user, "business.vehicle_category.save", "vehicle_category", item.id, {"new_key": item.category_key})
    db.commit()
    db.refresh(item)
    return _serialize_hierarchy(item)


def retire_vehicle_category(db, user, category_id: str) -> None:
    _require_business(user)
    item = db.scalar(select(VehicleCategory).where(VehicleCategory.id == category_id).with_for_update())
    if item is None:
        raise AppError("Vehicle category not found.", 404)
    item.status = "retired"
    _audit(db, user, "business.vehicle_category.retire", "vehicle_category", item.id, {})
    db.commit()


def list_vehicle_subcategories(db, user, *, category_id: str | None, search: str, page: int, page_size: int) -> dict:
    _require_business(user)
    predicates = [VehicleSubcategory.category_id == category_id] if category_id else None
    return _paged(db, VehicleSubcategory, ("name", "subcategory_key"), extra_predicates=predicates, search=search, page=page, page_size=page_size, order_field="subcategory_key")


def save_vehicle_subcategory(db, user, payload: dict) -> dict:
    _require_business(user)
    category = db.get(VehicleCategory, payload["category_id"])
    if category is None:
        raise AppError("Vehicle category not found.", 404)
    item = None
    if payload.get("id"):
        item = db.scalar(select(VehicleSubcategory).where(VehicleSubcategory.id == payload["id"]).with_for_update())
        if item is None:
            raise AppError("Vehicle subcategory not found.", 404)
    proposed_key = _slug(payload.get("subcategory_key") or payload["name"])
    if not proposed_key:
        raise AppError("Vehicle subcategory key is invalid.", 422)
    duplicate = db.scalar(
        select(VehicleSubcategory).where(
            VehicleSubcategory.category_id == category.id,
            VehicleSubcategory.subcategory_key == proposed_key,
            VehicleSubcategory.id != (item.id if item else "00000000-0000-0000-0000-000000000000"),
        )
    )
    if duplicate:
        raise AppError("A vehicle subcategory already uses this key in this category.", 409)
    if item is None:
        item = VehicleSubcategory(id=new_id(), category_id=category.id, subcategory_key=proposed_key, name=payload["name"])
        db.add(item)
    else:
        item.subcategory_key = proposed_key
    item.category_id = category.id
    item.name = payload["name"].strip()
    item.sort_order = max(0, int(payload.get("sort_order") or 0))
    item.status = payload.get("status", "active")
    if item.status not in STATUSES:
        raise AppError("Vehicle subcategory status is invalid.", 422)
    _audit(db, user, "business.vehicle_subcategory.save", "vehicle_subcategory", item.id, {"new_key": item.subcategory_key})
    db.commit()
    db.refresh(item)
    return _serialize_hierarchy(item)


def retire_vehicle_subcategory(db, user, subcategory_id: str) -> None:
    _require_business(user)
    item = db.scalar(select(VehicleSubcategory).where(VehicleSubcategory.id == subcategory_id).with_for_update())
    if item is None:
        raise AppError("Vehicle subcategory not found.", 404)
    item.status = "retired"
    _audit(db, user, "business.vehicle_subcategory.retire", "vehicle_subcategory", item.id, {})
    db.commit()


# --- Coverage types ---


def list_coverage_types(db, user, *, search: str, page: int, page_size: int) -> dict:
    _require_business(user)
    return _paged(db, CoverageType, ("name", "coverage_key"), extra_predicates=None, search=search, page=page, page_size=page_size, order_field="coverage_key")


def save_coverage_type(db, user, payload: dict) -> dict:
    _require_business(user)
    item = None
    if payload.get("id"):
        item = db.scalar(select(CoverageType).where(CoverageType.id == payload["id"]).with_for_update())
        if item is None:
            raise AppError("Coverage type not found.", 404)
    proposed_key = _slug(payload.get("coverage_key") or payload["name"])
    if not proposed_key:
        raise AppError("Coverage type key is invalid.", 422)
    duplicate = db.scalar(
        select(CoverageType).where(
            CoverageType.coverage_key == proposed_key,
            CoverageType.id != (item.id if item else "00000000-0000-0000-0000-000000000000"),
        )
    )
    if duplicate:
        raise AppError("A coverage type already uses this key.", 409)
    if item is None:
        item = CoverageType(id=new_id(), coverage_key=proposed_key, name=payload["name"])
        db.add(item)
    else:
        item.coverage_key = proposed_key
    item.name = payload["name"].strip()
    item.sort_order = max(0, int(payload.get("sort_order") or 0))
    item.status = payload.get("status", "active")
    if item.status not in STATUSES:
        raise AppError("Coverage type status is invalid.", 422)
    _audit(db, user, "business.coverage_type.save", "coverage_type", item.id, {"new_key": item.coverage_key})
    db.commit()
    db.refresh(item)
    return _serialize_hierarchy(item)


def retire_coverage_type(db, user, coverage_id: str) -> None:
    _require_business(user)
    item = db.scalar(select(CoverageType).where(CoverageType.id == coverage_id).with_for_update())
    if item is None:
        raise AppError("Coverage type not found.", 404)
    item.status = "retired"
    _audit(db, user, "business.coverage_type.retire", "coverage_type", item.id, {})
    db.commit()


# --- Scoped benefit aliases ---


def _alias_duplicate(db, item: BenefitAlias | None, benefit_id: str, normalized: str, scope: str, company_id: str | None, product_id: str | None, package_id: str | None) -> BenefitAlias | None:
    query = select(BenefitAlias).where(BenefitAlias.benefit_id == benefit_id, BenefitAlias.normalized_phrase == normalized)
    if item is not None:
        query = query.where(BenefitAlias.id != item.id)
    rows = list(db.scalars(query).all())
    for row in rows:
        if scope == "global" and row.scope == "global":
            return row
        if scope == "company" and row.scope == "company" and row.company_id == company_id:
            return row
        if scope == "product" and row.scope == "product" and row.product_id == product_id:
            return row
        if scope == "package" and row.scope == "package" and row.package_id == package_id:
            return row
    return None


def serialize_benefit_alias(db, item: BenefitAlias) -> dict:
    concept = db.get(BenefitConcept, item.benefit_id)
    company = db.get(InsuranceCompany, item.company_id) if item.company_id else None
    product = db.get(InsuranceProduct, item.product_id) if item.product_id else None
    package = db.get(BenefitPackage, item.package_id) if item.package_id else None
    return {
        "id": item.id,
        "benefit_id": item.benefit_id,
        "benefit_label": concept.label if concept else "Unavailable benefit",
        "phrase": item.phrase,
        "normalized_phrase": item.normalized_phrase,
        "scope": item.scope,
        "company_id": item.company_id,
        "company_name": company.name if company else None,
        "product_id": item.product_id,
        "product_name": product.name if product else None,
        "package_id": item.package_id,
        "package_name": package.name if package else None,
        "status": item.status,
    }


def list_benefit_aliases(db, user, *, benefit_id: str | None, scope: str | None, product_id: str | None, package_id: str | None, search: str, page: int, page_size: int) -> dict:
    _require_business(user)
    query = select(BenefitAlias)
    count_query = select(func.count()).select_from(BenefitAlias)
    if benefit_id:
        query = query.where(BenefitAlias.benefit_id == benefit_id)
        count_query = count_query.where(BenefitAlias.benefit_id == benefit_id)
    if scope:
        query = query.where(BenefitAlias.scope == scope)
        count_query = count_query.where(BenefitAlias.scope == scope)
    if product_id:
        query = query.where(BenefitAlias.product_id == product_id)
        count_query = count_query.where(BenefitAlias.product_id == product_id)
    if package_id:
        query = query.where(BenefitAlias.package_id == package_id)
        count_query = count_query.where(BenefitAlias.package_id == package_id)
    term = search.strip()
    if term:
        pattern = f"%{term}%"
        predicate = or_(BenefitAlias.phrase.ilike(pattern), BenefitAlias.normalized_phrase.ilike(pattern))
        query = query.where(predicate)
        count_query = count_query.where(predicate)
    total = int(db.scalar(count_query) or 0)
    rows = db.scalars(query.order_by(BenefitAlias.phrase).limit(page_size).offset((page - 1) * page_size)).all()
    return {
        "items": [serialize_benefit_alias(db, item) for item in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


def save_benefit_alias(db, user, payload: dict) -> dict:
    _require_business(user)
    concept = db.get(BenefitConcept, payload["benefit_id"])
    if concept is None:
        raise AppError("Global benefit not found.", 404)
    scope = str(payload.get("scope") or "global")
    if scope not in ALIAS_SCOPES:
        raise AppError("Alias scope is invalid.", 422)
    company_id = payload.get("company_id")
    product_id = payload.get("product_id")
    package_id = payload.get("package_id")
    if scope == "company":
        if not company_id or db.get(InsuranceCompany, company_id) is None:
            raise AppError("Company-scoped aliases require a valid company.", 422)
        product_id = None
        package_id = None
    elif scope == "product":
        if not product_id or db.get(InsuranceProduct, product_id) is None:
            raise AppError("Product-scoped aliases require a valid product.", 422)
        company_id = None
        package_id = None
    elif scope == "package":
        if not package_id:
            raise AppError("Package-scoped aliases require a package.", 422)
        company_id = None
        product_id = None
    else:
        company_id = None
        product_id = None
        package_id = None

    phrase = str(payload["phrase"]).strip()
    normalized = _normalize_phrase(phrase)
    if not normalized:
        raise AppError("Enter a usable alias phrase.", 422)
    item = None
    if payload.get("id"):
        item = db.scalar(select(BenefitAlias).where(BenefitAlias.id == payload["id"]).with_for_update())
        if item is None:
            raise AppError("Benefit alias not found.", 404)
    duplicate = _alias_duplicate(db, item, concept.id, normalized, scope, company_id, product_id, package_id)
    if duplicate is not None:
        raise AppError("This phrase already maps to another global benefit in this scope.", 409)
    if item is None:
        item = BenefitAlias(id=new_id(), benefit_id=concept.id, phrase=phrase, normalized_phrase=normalized, scope=scope)
        db.add(item)
    item.benefit_id = concept.id
    item.phrase = phrase
    item.normalized_phrase = normalized
    item.scope = scope
    item.company_id = company_id
    item.product_id = product_id
    item.package_id = package_id
    item.status = payload.get("status", "active")
    if item.status not in STATUSES:
        raise AppError("Alias status is invalid.", 422)
    _audit(db, user, "business.benefit_alias.save", "benefit_alias", item.id, {"benefit_id": concept.id, "scope": scope})
    db.commit()
    db.refresh(item)
    return serialize_benefit_alias(db, item)


def retire_benefit_alias(db, user, alias_id: str) -> None:
    _require_business(user)
    item = db.scalar(select(BenefitAlias).where(BenefitAlias.id == alias_id).with_for_update())
    if item is None:
        raise AppError("Benefit alias not found.", 404)
    item.status = "retired"
    _audit(db, user, "business.benefit_alias.retire", "benefit_alias", item.id, {})
    db.commit()


# --- Packages: comprehensive chain | add-on bundles ---


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


def _locked_catalog_with_draft(db, catalog_id: str, base_revision: int | None) -> tuple[BenefitCatalog, BenefitCatalogRevision]:
    catalog = db.scalar(select(BenefitCatalog).where(BenefitCatalog.id == catalog_id).with_for_update())
    if catalog is None:
        raise AppError("Catalog not found.", 404)
    if base_revision is None or catalog.revision != base_revision:
        raise AppError("This catalog changed elsewhere. Reload before saving.", 409)
    revision = db.scalar(
        select(BenefitCatalogRevision)
        .where(BenefitCatalogRevision.catalog_id == catalog.id, BenefitCatalogRevision.state == "draft")
        .order_by(BenefitCatalogRevision.revision_number.desc())
    )
    if revision is None:
        raise AppError("Create a new draft revision before editing this published catalog.", 409)
    return catalog, revision


def save_package(db, user, catalog_id: str, payload: dict) -> dict:
    _require_business(user)
    catalog, revision = _locked_catalog_with_draft(db, catalog_id, payload.get("base_revision"))
    name = str(payload["name"]).strip()
    if not name or len(name) > 255:
        raise AppError("Packages require a name of at most 255 characters.", 422)
    package_key = _slug(payload.get("package_key") or name)
    if not package_key:
        raise AppError("Package key is invalid.", 422)
    package_kind = str(payload.get("package_kind") or "comprehensive")
    if package_kind not in PACKAGE_KINDS:
        raise AppError("Package kind must be comprehensive or addon_bundle.", 422)
    status = payload.get("status", "active")
    if status not in STATUSES:
        raise AppError("Package status is invalid.", 422)
    item = None
    if payload.get("id"):
        item = db.get(BenefitPackage, payload["id"])
        if item is None or item.catalog_revision_id != revision.id:
            raise AppError("Package not found in this draft revision.", 404)
    duplicate = db.scalar(
        select(BenefitPackage).where(
            BenefitPackage.catalog_revision_id == revision.id,
            BenefitPackage.package_key == package_key,
            BenefitPackage.id != (item.id if item else "00000000-0000-0000-0000-000000000000"),
        )
    )
    if duplicate:
        raise AppError("A package already uses this key in this draft revision.", 409)
    if item is None:
        if package_kind == "comprehensive":
            if catalog.package_id is not None:
                raise AppError("This catalog already targets a comprehensive package; create a new catalog for another package.", 409)
        elif catalog.package_id is None:
            raise AppError("Add-on bundles require a catalog that targets a comprehensive package.", 422)
        item = BenefitPackage(
            id=new_id(), catalog_revision_id=revision.id, package_key=package_key,
            name=name, package_kind=package_kind, sort_order=max(0, int(payload.get("sort_order") or 0)),
        )
        db.add(item)
        db.flush()
        if package_kind == "comprehensive" and catalog.package_id is None and catalog.tier_id is None:
            catalog.package_id = item.id
    else:
        item.package_key = package_key
        item.name = name
        item.package_kind = package_kind
        item.sort_order = max(0, int(payload.get("sort_order") or 0))
        item.status = status
    catalog.revision += 1
    revision.content_hash = canonical_context_hash(_revision_content_payload(db, revision))
    _audit(db, user, "business.package.save", "benefit_package", item.id, {"catalog_id": catalog.id, "package_kind": package_kind, "new_revision": catalog.revision})
    db.commit()
    db.refresh(item)
    return _package(item)


def clone_package(db, user, catalog_id: str, source_package_id: str, payload: dict) -> dict:
    """Clone a package and its assignments as an explicit, independent copy.

    The source package may live in another catalog's revision (published or
    draft) — this is how Lite becomes Plus: a new catalog is created for the
    clone and the source's assignments are copied verbatim.
    """
    _require_business(user)
    catalog, revision = _locked_catalog_with_draft(db, catalog_id, payload.get("base_revision"))
    source = db.get(BenefitPackage, source_package_id)
    if source is None:
        raise AppError("Source package not found.", 404)
    if source.catalog_revision_id == revision.id:
        source_revision = revision
    else:
        source_revision = db.get(BenefitCatalogRevision, source.catalog_revision_id)
        if source_revision is None:
            raise AppError("Source package revision is unavailable.", 404)
    name = str(payload["name"]).strip()
    if not name or len(name) > 255:
        raise AppError("Packages require a name of at most 255 characters.", 422)
    package_key = _slug(payload.get("package_key") or name)
    if not package_key:
        raise AppError("Package key is invalid.", 422)
    package_kind = str(payload.get("package_kind") or source.package_kind)
    if package_kind not in PACKAGE_KINDS:
        raise AppError("Package kind must be comprehensive or addon_bundle.", 422)
    duplicate = db.scalar(
        select(BenefitPackage).where(
            BenefitPackage.catalog_revision_id == revision.id, BenefitPackage.package_key == package_key
        )
    )
    if duplicate:
        raise AppError("A package already uses this key in this draft revision.", 409)
    if package_kind == "comprehensive" and catalog.package_id is not None and str(catalog.package_id) != str(source.id):
        raise AppError("This catalog already targets another comprehensive package.", 409)

    target = BenefitPackage(
        id=new_id(), catalog_revision_id=revision.id, package_key=package_key,
        name=name, package_kind=package_kind, sort_order=max(0, int(payload.get("sort_order") or source.sort_order or 0)),
    )
    db.add(target)
    db.flush()
    if package_kind == "comprehensive" and catalog.package_id is None and catalog.tier_id is None:
        catalog.package_id = target.id
    copied = 0
    for offering in db.scalars(
        select(CatalogOffering)
        .where(CatalogOffering.catalog_revision_id == source_revision.id, CatalogOffering.applies_to_id == source.id)
        .order_by(CatalogOffering.sort_order, CatalogOffering.offering_key)
    ).all():
        db.add(CatalogOffering(
            id=new_id(),
            catalog_revision_id=revision.id,
            offering_key=f"{package_key}:{offering.offering_key}"[:160],
            concept_id=offering.concept_id,
            offering_kind=offering.offering_kind,
            applies_to_type=offering.applies_to_type,
            applies_to_id=target.id,
            role=offering.role,
            label_override=offering.label_override,
            typed_value=offering.typed_value,
            display_value=offering.display_value,
            optional_price=offering.optional_price,
            source_document_id=offering.source_document_id,
            source_citation=offering.source_citation,
            source_aliases=list(offering.source_aliases or []),
            presentation_facet_ids=list(offering.presentation_facet_ids or []),
            sort_order=offering.sort_order,
            status=offering.status,
        ))
        copied += 1
    catalog.revision += 1
    revision.content_hash = canonical_context_hash(_revision_content_payload(db, revision))
    _audit(db, user, "business.package.clone", "benefit_package", target.id, {
        "catalog_id": catalog.id, "source_package_id": source.id, "copied_assignments": copied,
    })
    db.commit()
    db.refresh(target)
    return {"package": _package(target), "copied_assignments": copied}


def retire_package(db, user, catalog_id: str, package_id: str) -> None:
    _require_business(user)
    catalog = db.scalar(select(BenefitCatalog).where(BenefitCatalog.id == catalog_id).with_for_update())
    if catalog is None:
        raise AppError("Catalog not found.", 404)
    item = db.get(BenefitPackage, package_id)
    if item is None:
        raise AppError("Package not found.", 404)
    revision = db.scalar(
        select(BenefitCatalogRevision).where(BenefitCatalogRevision.catalog_id == catalog.id, BenefitCatalogRevision.state == "draft")
    )
    if revision is None or item.catalog_revision_id != revision.id:
        raise AppError("Only packages of the draft revision can be retired.", 409)
    if catalog.package_id and str(catalog.package_id) == str(item.id):
        raise AppError("This package is the catalog's configuration target; retire the catalog instead.", 409)
    item.status = "retired"
    _audit(db, user, "business.package.retire", "benefit_package", item.id, {"catalog_id": catalog.id})
    db.commit()
