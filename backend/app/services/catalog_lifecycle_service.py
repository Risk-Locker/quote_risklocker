"""Domain service: catalog_lifecycle_service."""

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

from app.services.benefit_concept_service import serialize_concept
from app.services.company_setup_service import _catalog


__all__ = ['create_benefit_catalog', 'retire_benefit_catalog', '_validate_catalog_context', 'update_catalog_context', '_offering', '_package', '_revision_content_payload', '_validate_assignment_context', 'save_catalog_offering', 'remove_catalog_offering', 'create_new_draft_revision', 'publish_catalog_revision', 'get_catalog_workspace', 'list_source_documents']


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



def retire_benefit_catalog(db, user, catalog_id: str) -> None:
    _require_business(user)
    catalog = db.scalar(select(BenefitCatalog).where(BenefitCatalog.id == catalog_id).with_for_update())
    if catalog is None:
        raise AppError("Catalog not found.", 404)
    catalog.status = "retired"
    _audit(db, user, "business.catalog.retire", "benefit_catalog", catalog.id, {"name": catalog.name})
    db.commit()



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
    engine_type = payload.get("engine_type", "ice")
    context["engine_type"] = engine_type if engine_type in {"ice", "ev"} else "ice"
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
    disp_val = item.display_value
    if disp_val:
        d_str = disp_val.strip()
        has_digits = any(c.isdigit() for c in d_str)
        is_unlimited = d_str.lower() == "unlimited"
        if not has_digits and not is_unlimited:
            disp_val = None
        elif d_str.lower() in {"included", "optional", "foc", "as quoted", "selected", "standard"}:
            disp_val = None

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
        "description_override": getattr(item, "description_override", None),
        "typed_value": item.typed_value,
        "display_value": disp_val,
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
    """Canonical revision content: offerings + packages + plans + package-scoped aliases."""
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
    plans = [
        {
            "id": item.id,
            "package_id": item.package_id,
            "plan_key": item.plan_key,
            "name": item.name,
            "sort_order": item.sort_order,
            "status": item.status,
        }
        for item in db.scalars(
            select(BenefitPackagePlan)
            .where(BenefitPackagePlan.package_id.in_(package_ids))
            .order_by(BenefitPackagePlan.sort_order, BenefitPackagePlan.plan_key)
        ).all()
    ] if package_ids else []
    plan_ids = {item["id"] for item in plans}
    plan_items = [
        {
            "plan_id": item.plan_id,
            "offering_id": item.offering_id,
            "typed_value_override": item.typed_value_override,
            "sort_order": item.sort_order,
        }
        for item in db.scalars(
            select(BenefitPackagePlanItem)
            .where(BenefitPackagePlanItem.plan_id.in_(plan_ids))
            .order_by(BenefitPackagePlanItem.plan_id, BenefitPackagePlanItem.sort_order)
        ).all()
    ] if plan_ids else []
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
    return {
        "offerings": offerings,
        "packages": packages,
        "plans": plans,
        "plan_items": plan_items,
        "aliases": aliases,
    }



def _validate_assignment_context(db, catalog: BenefitCatalog, revision: BenefitCatalogRevision, payload: dict) -> dict:
    """Resolve and validate applies_to/role against the catalog context."""
    legacy = bool(catalog.tier_id) and not catalog.package_id
    applies_type = payload.get("applies_to_type")
    applies_id = payload.get("applies_to_id")
    role = payload.get("role")

    # If updating an existing offering and applies_to_type was not specified in the payload, preserve it
    if applies_type is None and payload.get("id"):
        existing_off = db.get(CatalogOffering, payload["id"])
        if existing_off is not None:
            applies_type = existing_off.applies_to_type
            applies_id = existing_off.applies_to_id

    rev_packages = list(db.scalars(select(BenefitPackage).where(BenefitPackage.catalog_revision_id == revision.id)).all())
    is_catalog_packaged = bool(catalog.package_id) or bool(rev_packages)

    if applies_type is None and not legacy:
        applies_type = "package" if is_catalog_packaged else "product"
        applies_id = (catalog.package_id or (rev_packages[0].id if rev_packages else None)) if is_catalog_packaged else catalog.product_id
    elif applies_type == "product" and applies_id is None and catalog.product_id:
        applies_id = catalog.product_id
    elif applies_type == "package" and applies_id is None:
        applies_id = catalog.package_id or (rev_packages[0].id if rev_packages else None)

    # Database constraint catalog_offerings_applies_check requires:
    # (applies_to_type IS NULL AND applies_to_id IS NULL) OR (applies_to_type IS NOT NULL AND applies_to_id IS NOT NULL)
    if applies_type is not None and applies_id is None:
        if applies_type == "product" and catalog.product_id:
            applies_id = catalog.product_id
        elif applies_type == "package" and (catalog.package_id or rev_packages):
            applies_id = catalog.package_id or rev_packages[0].id
        else:
            applies_type = None

    if applies_type is not None and applies_type not in {"product", "package", "bundle"}:
        raise AppError("Assignment target type must be product, package, or bundle.", 422)
    if role is not None and role not in {"included", "addon_option", "bundle_component"}:
        raise AppError("Assignment role is invalid.", 422)
    if applies_type is not None:
        if applies_type == "package":
            if not rev_packages and catalog.package_id is None:
                applies_type = "product"
                applies_id = catalog.product_id
            elif applies_id is None:
                applies_id = catalog.package_id or (rev_packages[0].id if rev_packages else None)
            else:
                package = db.get(BenefitPackage, applies_id)
                if package and package.catalog_revision_id != revision.id:
                    matched_pkg = db.scalar(
                        select(BenefitPackage).where(
                            BenefitPackage.catalog_revision_id == revision.id,
                            (BenefitPackage.package_key == package.package_key) | (BenefitPackage.name == package.name),
                        )
                    )
                    if matched_pkg:
                        package = matched_pkg
                        applies_id = matched_pkg.id
                if package is None or package.catalog_revision_id != revision.id or package.package_kind not in {"comprehensive", "tpft", "tpo"}:
                    raise AppError("Package assignment is invalid.", 422)
        elif applies_type == "bundle":
            bundle = db.get(BenefitPackage, applies_id) if applies_id else None
            if bundle is None or bundle.catalog_revision_id != revision.id or bundle.package_kind != "addon_bundle":
                raise AppError("Bundle assignment is invalid.", 422)
        elif applies_type == "product" and catalog.package_id is not None:
            raise AppError("This catalog is packaged; assign benefits to the package instead.", 422)

    # Final safety invariant for catalog_offerings_applies_check
    if applies_type is not None and applies_id is None:
        applies_type = None
    optional_price = payload.get("optional_price")
    if optional_price is not None:
        if isinstance(optional_price, (int, float, str)):
            str_val = str(optional_price).replace("RM", "").replace(",", "").strip()
            try:
                num_val = float(str_val)
                payload["optional_price"] = {"type": "money", "value": num_val, "currency": "MYR"}
            except ValueError:
                payload["optional_price"] = None
        elif isinstance(optional_price, dict):
            if "type" in optional_price:
                try:
                    BenefitValue.model_validate(optional_price)
                except Exception as exc:
                    raise AppError("Optional price is an invalid typed value.", 422) from exc
            elif "amount" in optional_price:
                str_val = str(optional_price["amount"]).replace("RM", "").replace(",", "").strip()
                try:
                    num_val = float(str_val)
                    payload["optional_price"] = {"type": "money", "value": num_val, "currency": optional_price.get("currency") or "MYR"}
                except ValueError:
                    payload["optional_price"] = None
        else:
            raise AppError("Optional price must be a typed value object or price amount.", 422)
    if applies_id is None:
        applies_type = None
    elif applies_type is None:
        applies_id = None
    payload["applies_to_type"] = applies_type
    payload["applies_to_id"] = applies_id
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
                    role=off.role, label_override=off.label_override,
                    description_override=getattr(off, "description_override", None),
                    typed_value=off.typed_value,
                    display_value=off.display_value, optional_price=off.optional_price,
                    source_document_id=off.source_document_id, source_citation=off.source_citation,
                    source_aliases=list(off.source_aliases or []),
                    presentation_facet_ids=list(off.presentation_facet_ids or []),
                    sort_order=off.sort_order, status=off.status,
                ))
            if catalog.package_id and catalog.package_id in package_map:
                catalog.package_id = package_map[catalog.package_id]
            if payload.get("applies_to_id") and payload["applies_to_id"] in package_map:
                payload["applies_to_id"] = package_map[payload["applies_to_id"]]
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
        target_off = db.get(CatalogOffering, payload["id"])
        if target_off is not None:
            if target_off.catalog_revision_id == revision.id:
                offering = target_off
            else:
                target_key = payload.get("offering_key") or target_off.offering_key
                offering = db.scalar(
                    select(CatalogOffering).where(
                        CatalogOffering.catalog_revision_id == revision.id,
                        CatalogOffering.offering_key == target_key,
                    )
                )
                if offering is None and target_off.concept_id:
                    offering = db.scalar(
                        select(CatalogOffering).where(
                            CatalogOffering.catalog_revision_id == revision.id,
                            CatalogOffering.concept_id == target_off.concept_id,
                        )
                    )
    if offering is None and payload.get("offering_key"):
        offering = db.scalar(
            select(CatalogOffering).where(
                CatalogOffering.catalog_revision_id == revision.id,
                CatalogOffering.offering_key == payload["offering_key"],
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
        "label_override", "description_override", "typed_value", "display_value", "optional_price", "source_document_id",
        "source_citation", "source_aliases", "presentation_facet_ids", "sort_order", "status",
    ):
        if key in payload:
            val = payload[key]
            if key == "description_override" and val is not None:
                v_str = str(val).strip()
                val = v_str if v_str else None
            elif key == "display_value" and val:
                v_str = str(val).strip()
                if not any(c.isdigit() for c in v_str) and v_str.lower() != "unlimited":
                    val = None
                elif v_str.lower() in {"included", "optional", "foc", "as quoted", "selected", "standard"}:
                    val = None
            setattr(offering, key, val)
    if offering.applies_to_id is None:
        offering.applies_to_type = None
    elif offering.applies_to_type is None:
        offering.applies_to_id = None
    db.flush()
    # Lightweight content hash: use offering IDs only instead of full _revision_content_payload
    # (the full hash is recomputed on publish via publish_catalog_revision)
    _offering_ids = sorted(str(row.id) for row in db.scalars(
        select(CatalogOffering.id).where(CatalogOffering.catalog_revision_id == revision.id)
    ).all())
    revision.content_hash = hashlib.sha256(",".join(_offering_ids).encode()).hexdigest()
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
                    role=off.role, label_override=off.label_override,
                    description_override=getattr(off, "description_override", None),
                    typed_value=off.typed_value,
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
    target_offering = None
    if offering is not None:
        if offering.catalog_revision_id == revision.id:
            target_offering = offering
        else:
            target_offering = db.scalar(
                select(CatalogOffering).where(
                    CatalogOffering.catalog_revision_id == revision.id,
                    (CatalogOffering.offering_key == offering.offering_key)
                    | (
                        (CatalogOffering.concept_id == offering.concept_id)
                        & (CatalogOffering.role == offering.role)
                    ),
                )
            )
    if target_offering is not None:
        deleted_id = target_offering.id
        db.delete(target_offering)
        db.flush()
        # Lightweight content hash: use offering IDs only (full hash on publish)
        _offering_ids = sorted(str(row.id) for row in db.scalars(
            select(CatalogOffering.id).where(CatalogOffering.catalog_revision_id == revision.id)
        ).all())
        revision.content_hash = hashlib.sha256(",".join(_offering_ids).encode()).hexdigest()
        catalog.revision += 1
        _audit(db, user, "business.catalog_offering.delete", "catalog_offering", deleted_id, {"catalog_id": catalog.id, "new_revision": catalog.revision})
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

    plan_map: dict[str, str] = {}
    if package_map:
        for plan in db.scalars(
            select(BenefitPackagePlan)
            .where(BenefitPackagePlan.package_id.in_(list(package_map.keys())))
            .order_by(BenefitPackagePlan.sort_order, BenefitPackagePlan.name)
        ).all():
            new_plan = BenefitPackagePlan(
                id=new_id(),
                package_id=package_map[plan.package_id],
                plan_key=plan.plan_key,
                name=plan.name,
                sort_order=plan.sort_order,
                status=plan.status,
            )
            db.add(new_plan)
            plan_map[plan.id] = new_plan.id
        db.flush()

    offering_map: dict[str, str] = {}
    for offering in db.scalars(
        select(CatalogOffering).where(CatalogOffering.catalog_revision_id == source.id).order_by(CatalogOffering.sort_order, CatalogOffering.offering_key)
    ).all():
        new_off_id = new_id()
        offering_map[offering.id] = new_off_id
        db.add(CatalogOffering(
            id=new_off_id, catalog_revision_id=draft.id, offering_key=offering.offering_key,
            concept_id=offering.concept_id, offering_kind=offering.offering_kind,
            applies_to_type=offering.applies_to_type,
            applies_to_id=package_map.get(str(offering.applies_to_id)) if offering.applies_to_id else None,
            role=offering.role, label_override=offering.label_override,
            description_override=getattr(offering, "description_override", None),
            typed_value=offering.typed_value,
            display_value=offering.display_value, optional_price=offering.optional_price,
            source_document_id=offering.source_document_id, source_citation=offering.source_citation,
            source_aliases=list(offering.source_aliases or []),
            presentation_facet_ids=list(offering.presentation_facet_ids or []),
            sort_order=offering.sort_order, status=offering.status,
        ))
    db.flush()

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
                    )
                )
        db.flush()
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
    # Batch-preload all assets referenced by concepts (eliminates N+1 in serialize_concept)
    _concept_asset_ids = {c.default_asset_id for c in concepts.values() if c.default_asset_id}
    _preloaded_assets: dict = {}
    if _concept_asset_ids:
        _preloaded_assets = {
            str(a.id): a
            for a in db.scalars(select(BusinessAsset).where(BusinessAsset.id.in_(_concept_asset_ids))).all()
        }
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
                "concept": serialize_concept(db, concepts[item.concept_id], preloaded_assets=_preloaded_assets) if item.concept_id in concepts else None,
            }
            for item in offerings
            if item.concept_id in concepts
            and getattr(concepts[item.concept_id], "status", "active") != "retired"
            and item.status != "retired"
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

