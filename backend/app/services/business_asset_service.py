"""Domain service: business_asset_service."""

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


__all__ = ['list_business_assets', 'list_business_asset_categories', '_find_collision_in_category', '_generate_unique_label_and_filename', 'upload_business_asset', 'batch_upload_business_assets', 'update_business_asset', 'replace_business_asset_file', 'bulk_move_business_assets', 'delete_business_asset', 'bulk_delete_business_assets', 'rename_business_asset_folder', 'delete_business_asset_folder']


def list_business_assets(
    db, user, *, search: str, kind: str | None, category: str | None = None, page: int, page_size: int
) -> dict:
    _require_business(user)
    query = select(BusinessAsset)
    count_query = select(func.count()).select_from(BusinessAsset)
    predicates = []
    if search.strip():
        pattern = f"%{search.strip()}%"
        predicates.append(or_(BusinessAsset.label.ilike(pattern), BusinessAsset.original_filename.ilike(pattern)))
    if kind:
        predicates.append(BusinessAsset.asset_kind == kind)
    if category and category.strip():
        predicates.append(BusinessAsset.category == category.strip())
    for predicate in predicates:
        query = query.where(predicate)
        count_query = count_query.where(predicate)
    total = int(db.scalar(count_query) or 0)
    rows = db.scalars(query.order_by(BusinessAsset.label).limit(page_size).offset((page - 1) * page_size)).all()
    return {"items": [_asset_summary(row) for row in rows], "total": total, "page": page, "page_size": page_size}



def list_business_asset_categories(db, user) -> list[dict]:
    _require_business(user)
    rows = db.execute(
        select(BusinessAsset.category, func.count(BusinessAsset.id))
        .where(BusinessAsset.status.in_(["active", "unassigned"]))
        .group_by(BusinessAsset.category)
        .order_by(BusinessAsset.category)
    ).all()
    return [
        {
            "category": str(cat or "General"),
            "name": str(cat or "General"),
            "count": int(count),
        }
        for cat, count in rows
    ]



def _find_collision_in_category(db, category: str, label: str, filename: str) -> BusinessAsset | None:
    norm_label = label.strip().lower()
    norm_fn = filename.strip().lower()
    return db.scalar(
        select(BusinessAsset).where(
            BusinessAsset.category == category,
            BusinessAsset.status.in_(["active", "unassigned"]),
            or_(
                func.lower(BusinessAsset.label) == norm_label,
                func.lower(BusinessAsset.original_filename) == norm_fn,
            ),
        )
    )



def _generate_unique_label_and_filename(db, category: str, base_label: str, filename: str) -> tuple[str, str]:
    existing_labels = set(
        db.scalars(
            select(func.lower(BusinessAsset.label)).where(
                BusinessAsset.category == category,
                BusinessAsset.status.in_(["active", "unassigned"]),
            )
        ).all()
    )
    existing_filenames = set(
        db.scalars(
            select(func.lower(BusinessAsset.original_filename)).where(
                BusinessAsset.category == category,
                BusinessAsset.status.in_(["active", "unassigned"]),
            )
        ).all()
    )
    norm_base = base_label.strip()
    p = Path(filename)
    stem = p.stem
    suffix = p.suffix

    if norm_base.lower() not in existing_labels and filename.lower() not in existing_filenames:
        return norm_base, filename

    counter = 1
    while True:
        candidate_label = f"{norm_base} ({counter})"
        candidate_fn = f"{stem} ({counter}){suffix}"
        if candidate_label.lower() not in existing_labels and candidate_fn.lower() not in existing_filenames:
            return candidate_label, candidate_fn
        counter += 1



def upload_business_asset(
    db,
    settings,
    user,
    *,
    filename: str,
    label: str,
    kind: str,
    data: bytes,
    category: str = "General",
    on_duplicate: str = "rename",
) -> dict:
    _require_business(user)
    if kind not in {"benefit_art", "company_logo", "template_background", "decorative"}:
        raise AppError("Asset kind is invalid.", 422)
    clean_category = category.strip() or "General"
    clean_label = label.strip() or Path(filename).stem
    try:
        technical = validate_image_bytes(
            data,
            filename,
            max_bytes=settings.max_asset_bytes,
            max_pixels=settings.max_asset_pixels,
        )
    except ValueError as exc:
        raise AppError(str(exc), 422) from exc

    def extension(content_type: str) -> str:
        return {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[content_type]

    content_hash = technical["content_hash"]
    collision = _find_collision_in_category(db, clean_category, clean_label, filename)

    if collision and on_duplicate == "replace":
        storage = SupabaseStorage(settings)
        uploaded: list[str] = []
        try:
            original_path = f"assets/original/{content_hash[:2]}/{content_hash}.{extension(technical['content_type'])}"
            storage.upload_asset(original_path, data, technical["content_type"])
            uploaded.append(original_path)

            derivatives = {
                "ui": create_derivative(data, max_width=512, max_height=512, quality=85),
                "pdf": create_derivative(data, max_width=1_600, max_height=1_600, quality=92),
            }
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

            old_storage_paths = [collision.storage_path]
            for deriv in (collision.derivative_manifest or {}).values():
                if isinstance(deriv, dict) and deriv.get("storage_path"):
                    old_storage_paths.append(deriv["storage_path"])

            collision.original_filename = filename
            collision.label = clean_label
            collision.content_type = technical["content_type"]
            collision.content_hash = content_hash
            collision.storage_path = original_path
            collision.size_bytes = technical["size_bytes"]
            collision.width_px = technical["width_px"]
            collision.height_px = technical["height_px"]
            collision.has_transparency = technical["has_transparency"]
            collision.derivative_manifest = derivative_manifest
            collision.revision += 1

            db.commit()
            db.refresh(collision)

            for old_path in old_storage_paths:
                if old_path not in uploaded:
                    try:
                        storage.delete_pdf(old_path)
                    except Exception:
                        pass

            _audit(db, user, "business.asset.replace", "business_asset", collision.id, {"category": clean_category, "content_hash": content_hash})
            return _asset_summary(collision) or {}
        except Exception:
            db.rollback()
            for storage_path in reversed(uploaded):
                try:
                    storage.delete_pdf(storage_path)
                except Exception:
                    pass
            raise

    # on_duplicate == "rename" or no collision:
    final_label, final_filename = _generate_unique_label_and_filename(db, clean_category, clean_label, filename)

    # If identical content and identical label already exist in this category, return existing
    existing = db.scalar(select(BusinessAsset).where(BusinessAsset.content_hash == content_hash))
    if existing and existing.category == clean_category and existing.label == final_label:
        return _asset_summary(existing) or {}

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
        unique_key = f"upload:{kind}:{content_hash}:{new_id()[:8]}"
        asset = BusinessAsset(
            id=new_id(),
            asset_key=unique_key,
            asset_kind=kind,
            category=clean_category,
            label=final_label,
            original_filename=final_filename,
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
        _audit(db, user, "business.asset.upload", "business_asset", asset.id, {"kind": kind, "category": clean_category, "content_hash": content_hash})
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



def batch_upload_business_assets(
    db,
    settings,
    user,
    *,
    files: list[tuple[str, str, bytes]],
    kind: str,
    category: str = "General",
    on_duplicate: str = "rename",
) -> dict:
    _require_business(user)
    clean_category = category.strip() or "General"
    uploaded_summaries: list[dict] = []
    errors: list[dict] = []
    for filename, label, data in files:
        clean_label = label.strip() or Path(filename).stem
        readable_label = re.sub(r"[_\-]+", " ", clean_label).strip().title()
        try:
            summary = upload_business_asset(
                db,
                settings,
                user,
                filename=filename,
                label=readable_label,
                kind=kind,
                data=data,
                category=clean_category,
                on_duplicate=on_duplicate,
            )
            if summary:
                uploaded_summaries.append(summary)
        except Exception as exc:
            errors.append({"filename": filename, "error": str(exc)})
    return {
        "items": uploaded_summaries,
        "total": len(uploaded_summaries),
        "errors": errors,
        "category": clean_category,
    }



def update_business_asset(
    db,
    user,
    asset_id: str,
    *,
    label: str | None = None,
    category: str | None = None,
    kind: str | None = None,
) -> dict:
    _require_business(user)
    asset = db.get(BusinessAsset, asset_id)
    if asset is None or asset.status not in {"active", "unassigned"}:
        raise AppError("Asset not found.", 404)
    if label is not None and label.strip():
        asset.label = label.strip()
    if category is not None:
        asset.category = category.strip() or "General"
    if kind is not None and kind.strip():
        if kind not in {"benefit_art", "company_logo", "template_background", "decorative"}:
            raise AppError("Asset kind is invalid.", 422)
        asset.asset_kind = kind.strip()
    asset.revision += 1
    _audit(db, user, "business.asset.update", "business_asset", asset.id, {"label": asset.label, "category": asset.category, "kind": asset.asset_kind})
    db.commit()
    db.refresh(asset)
    return _asset_summary(asset) or {}



def replace_business_asset_file(
    db,
    settings,
    user,
    asset_id: str,
    *,
    filename: str,
    data: bytes,
) -> dict:
    """Replace the underlying binary file and derivatives of an existing business asset."""
    _require_business(user)
    asset = db.get(BusinessAsset, asset_id)
    if asset is None or asset.status not in {"active", "unassigned"}:
        raise AppError("Asset not found.", 404)

    try:
        technical = validate_image_bytes(
            data,
            filename,
            max_bytes=settings.max_asset_bytes,
            max_pixels=settings.max_asset_pixels,
        )
    except ValueError as exc:
        raise AppError(str(exc), 422) from exc

    def extension(content_type: str) -> str:
        return {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}.get(content_type, "png")

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

        old_storage_paths = [asset.storage_path]
        for deriv in (asset.derivative_manifest or {}).values():
            if isinstance(deriv, dict) and deriv.get("storage_path"):
                old_storage_paths.append(deriv["storage_path"])

        asset.original_filename = filename
        asset.content_type = technical["content_type"]
        asset.content_hash = content_hash
        asset.storage_path = original_path
        asset.size_bytes = technical["size_bytes"]
        asset.width_px = technical["width_px"]
        asset.height_px = technical["height_px"]
        asset.has_transparency = technical["has_transparency"]
        asset.derivative_manifest = derivative_manifest
        asset.revision += 1

        db.commit()
        db.refresh(asset)

        for old_path in old_storage_paths:
            if old_path not in uploaded:
                try:
                    storage.delete_pdf(old_path)
                except Exception:
                    pass

        _audit(db, user, "business.asset.replace_file", "business_asset", asset.id, {
            "category": asset.category,
            "filename": filename,
            "content_hash": content_hash,
        })
        return _asset_summary(asset) or {}
    except Exception:
        db.rollback()
        for storage_path in reversed(uploaded):
            try:
                storage.delete_pdf(storage_path)
            except Exception:
                pass
        raise



def bulk_move_business_assets(db, user, asset_ids: list[str], target_category: str) -> dict:
    _require_business(user)
    clean_category = target_category.strip() or "General"
    assets = db.scalars(
        select(BusinessAsset).where(
            BusinessAsset.id.in_(asset_ids),
            BusinessAsset.status.in_(["active", "unassigned"]),
        )
    ).all()
    for asset in assets:
        asset.category = clean_category
        asset.revision += 1
    _audit(db, user, "business.asset.bulk_move", "business_asset", "bulk", {"count": len(assets), "target_category": clean_category})
    db.commit()
    return {"success": True, "moved_count": len(assets), "category": clean_category}



def delete_business_asset(db, settings, user, asset_id: str) -> dict:
    _require_business(user)
    asset = db.get(BusinessAsset, asset_id)
    if asset is None or asset.status not in {"active", "unassigned"}:
        raise AppError("Asset not found.", 404)

    # 1. Safely unlink foreign key references
    db.execute(delete(GlobalBenefitProfileAsset).where(GlobalBenefitProfileAsset.asset_id == asset.id))
    db.execute(update(BenefitConcept).where(BenefitConcept.default_asset_id == asset.id).values(default_asset_id=None))
    db.execute(update(InsuranceCompany).where(InsuranceCompany.logo_asset_id == asset.id).values(logo_asset_id=None))

    # 2. Collect storage paths to purge
    storage_paths = [asset.storage_path]
    for deriv in (asset.derivative_manifest or {}).values():
        if isinstance(deriv, dict) and deriv.get("storage_path"):
            storage_paths.append(deriv["storage_path"])

    # 3. Delete from DB
    _audit(db, user, "business.asset.delete", "business_asset", asset.id, {"label": asset.label, "category": asset.category})
    db.delete(asset)
    db.commit()

    # 4. Storage cleanup
    storage = SupabaseStorage(settings)
    for path in storage_paths:
        try:
            storage.delete_pdf(path)
        except Exception:
            pass

    return {"success": True, "id": asset_id}



def bulk_delete_business_assets(db, settings, user, asset_ids: list[str]) -> dict:
    _require_business(user)
    if not asset_ids:
        return {"success": True, "deleted_count": 0, "deleted_ids": []}

    assets = db.scalars(
        select(BusinessAsset).where(
            BusinessAsset.id.in_(asset_ids),
            BusinessAsset.status.in_(["active", "unassigned"]),
        )
    ).all()
    if not assets:
        return {"success": True, "deleted_count": 0, "deleted_ids": []}

    target_ids = [a.id for a in assets]
    storage_paths = []
    for asset in assets:
        storage_paths.append(asset.storage_path)
        for deriv in (asset.derivative_manifest or {}).values():
            if isinstance(deriv, dict) and deriv.get("storage_path"):
                storage_paths.append(deriv["storage_path"])

    # 1. Unlink references
    db.execute(delete(GlobalBenefitProfileAsset).where(GlobalBenefitProfileAsset.asset_id.in_(target_ids)))
    db.execute(update(BenefitConcept).where(BenefitConcept.default_asset_id.in_(target_ids)).values(default_asset_id=None))
    db.execute(update(InsuranceCompany).where(InsuranceCompany.logo_asset_id.in_(target_ids)).values(logo_asset_id=None))

    # 2. Delete rows
    for asset in assets:
        db.delete(asset)

    _audit(db, user, "business.asset.bulk_delete", "business_asset", "bulk", {"count": len(target_ids)})
    db.commit()

    # 3. Storage cleanup
    storage = SupabaseStorage(settings)
    for path in storage_paths:
        try:
            storage.delete_pdf(path)
        except Exception:
            pass

    return {"success": True, "deleted_count": len(target_ids), "deleted_ids": target_ids}



def rename_business_asset_folder(db, user, old_category: str, new_category: str) -> dict:
    _require_business(user)
    old_clean = old_category.strip()
    new_clean = new_category.strip()
    if not old_clean or not new_clean:
        raise AppError("Folder name cannot be empty.", 422)
    if old_clean.lower() == new_clean.lower():
        return {"success": True, "old_category": old_clean, "new_category": new_clean, "updated_assets": 0}

    res = db.execute(
        update(BusinessAsset)
        .where(
            BusinessAsset.category == old_clean,
            BusinessAsset.status.in_(["active", "unassigned"]),
        )
        .values(category=new_clean, revision=BusinessAsset.revision + 1)
    )
    db.execute(
        update(GlobalBenefitProfile)
        .where(GlobalBenefitProfile.asset_category == old_clean)
        .values(asset_category=new_clean)
    )
    _audit(db, user, "business.asset.folder_rename", "folder", old_clean, {"new_category": new_clean})
    db.commit()
    return {"success": True, "old_category": old_clean, "new_category": new_clean, "updated_assets": res.rowcount}



def delete_business_asset_folder(db, settings, user, category: str, *, action: str = "move_to_general") -> dict:
    _require_business(user)
    clean_category = category.strip()
    if clean_category.lower() == "general":
        raise AppError("Cannot delete the default General folder.", 422)

    if action == "move_to_general":
        db.execute(
            update(BusinessAsset)
            .where(
                BusinessAsset.category == clean_category,
                BusinessAsset.status.in_(["active", "unassigned"]),
            )
            .values(category="General", revision=BusinessAsset.revision + 1)
        )
        db.execute(
            update(GlobalBenefitProfile)
            .where(GlobalBenefitProfile.asset_category == clean_category)
            .values(asset_category="General")
        )
        _audit(db, user, "business.asset.folder_delete", "folder", clean_category, {"action": "move_to_general"})
        db.commit()
        return {"success": True, "category": clean_category, "action": "move_to_general"}

    elif action == "delete_all":
        asset_ids = list(
            db.scalars(
                select(BusinessAsset.id).where(
                    BusinessAsset.category == clean_category,
                    BusinessAsset.status.in_(["active", "unassigned"]),
                )
            ).all()
        )
        if asset_ids:
            bulk_delete_business_assets(db, settings, user, asset_ids)
        db.execute(
            update(GlobalBenefitProfile)
            .where(GlobalBenefitProfile.asset_category == clean_category)
            .values(asset_category="General")
        )
        _audit(db, user, "business.asset.folder_delete", "folder", clean_category, {"action": "delete_all"})
        db.commit()
        return {"success": True, "category": clean_category, "action": "delete_all", "deleted_assets": len(asset_ids)}
    else:
        raise AppError("Invalid folder delete action. Must be 'move_to_general' or 'delete_all'.", 422)

