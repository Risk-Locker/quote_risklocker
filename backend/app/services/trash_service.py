"""Trash (soft-delete) handling for templates, our specials, variants, and client records.

Sessions share the existing uploaded-file trash flow in review_service.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.models.enums import AccountStatus, Role
from app.models.tables import (
    ClientRecord,
    GeneratedPdfVersion,
    OurSpecial,
    OurSpecialVariant,
    OutputTemplateConfig,
    TemplateAsset,
    TrashRecord,
    UploadedFile,
)
from app.auth.rbac import can_view_owner_record
from app.services.review_service import list_trash
from app.services.upload_service import serialize_file


logger = logging.getLogger(__name__)


def _trash_entry(db: Session, user, entity_type: str, entity_id: str, original_status: str, retention_days: int) -> None:
    db.add(
        TrashRecord(
            entity_type=entity_type,
            entity_id=entity_id,
            original_status=original_status,
            deleted_by=user.id,
            purge_after=None,
        )
    )


def _soft_delete_item(
    db: Session,
    settings: Settings,
    user,
    item,
    entity_type: str,
    *,
    has_status: bool = True,
) -> None:
    if has_status and hasattr(item, "status"):
        item.status = AccountStatus.INACTIVE.value
    item.mark_deleted(settings.trash_retention_days)
    _trash_entry(db, user, entity_type, item.id, getattr(item, "status", "active"), settings.trash_retention_days)
    db.commit()


def _restore_item(
    db: Session,
    item,
    *,
    has_status: bool = True,
) -> None:
    if has_status and hasattr(item, "status"):
        item.status = AccountStatus.ACTIVE.value
    item.restore()
    db.commit()


def _list_trash_items(db: Session, model_cls):
    return list(
        db.scalars(
            select(model_cls)
            .where(model_cls.deleted_at.is_not(None))
            .order_by(model_cls.deleted_at.desc())
        ).all()
    )


# ---------------------------------------------------------------- templates

def delete_template(db: Session, settings: Settings, user, template_id: str) -> None:
    template = db.get(OutputTemplateConfig, template_id)
    if not template or template.deleted_at:
        raise AppError("Template not found.", 404)
    from app.services.template_config import normalize_template_config
    config = normalize_template_config(template.fixed_fields, template.name)
    if config.get("locked") or config.get("is_default"):
        raise AppError("The locked default template cannot be deleted. Copy it first.", 400)
    _soft_delete_item(db, settings, user, template, "template")


def restore_template(db: Session, user, template_id: str) -> None:
    template = db.get(OutputTemplateConfig, template_id)
    if not template or not template.deleted_at:
        raise AppError("Trash template not found.", 404)
    _restore_item(db, template)


def list_trash_templates(db: Session) -> list[OutputTemplateConfig]:
    return _list_trash_items(db, OutputTemplateConfig)


def purge_expired_templates(db: Session, now: datetime) -> int:
    # RL-DISABLED timed trash purge — disabled 2026-08-14; explicit permanent
    # deletion performs reference checks through the handlers below.
    return 0


# ---------------------------------------------------------------- our specials

def delete_special(db: Session, settings: Settings, user, special_id: str) -> None:
    special = db.get(OurSpecial, special_id)
    if not special or special.deleted_at:
        raise AppError("Our Special not found.", 404)
    for variant in special.variants:
        variant.status = AccountStatus.INACTIVE.value
        variant.mark_deleted(settings.trash_retention_days)
    _soft_delete_item(db, settings, user, special, "our_special")


def restore_special(db: Session, user, special_id: str) -> None:
    special = db.get(OurSpecial, special_id)
    if not special or not special.deleted_at:
        raise AppError("Trash Our Special not found.", 404)
    for variant in special.variants:
        variant.status = AccountStatus.ACTIVE.value
        variant.restore()
    _restore_item(db, special)


def delete_special_variant(db: Session, settings: Settings, user, variant_id: str) -> None:
    variant = db.get(OurSpecialVariant, variant_id)
    if not variant or variant.deleted_at:
        raise AppError("Variant not found.", 404)
    _soft_delete_item(db, settings, user, variant, "our_special_variant")


def restore_special_variant(db: Session, user, variant_id: str) -> None:
    variant = db.get(OurSpecialVariant, variant_id)
    if not variant or not variant.deleted_at:
        raise AppError("Trash variant not found.", 404)
    _restore_item(db, variant)


def list_trash_specials(db: Session) -> list[OurSpecial]:
    return _list_trash_items(db, OurSpecial)


def list_trash_variants(db: Session) -> list[OurSpecialVariant]:
    return _list_trash_items(db, OurSpecialVariant)


def purge_expired_specials(db: Session, now: datetime) -> int:
    return 0


# ---------------------------------------------------------------- client records

def delete_client_record(db: Session, settings: Settings, user, record_id: str) -> None:
    record = db.get(ClientRecord, record_id)
    if not record or record.deleted_at:
        raise AppError("Client record not found.", 404)
    _soft_delete_item(db, settings, user, record, "client_record", has_status=False)


def restore_client_record(db: Session, user, record_id: str) -> None:
    record = db.get(ClientRecord, record_id)
    if not record or not record.deleted_at:
        raise AppError("Trash client record not found.", 404)
    _restore_item(db, record, has_status=False)


def list_trash_client_records(db: Session) -> list[ClientRecord]:
    return _list_trash_items(db, ClientRecord)


def purge_expired_client_records(db: Session, now: datetime) -> int:
    return 0


# ---------------------------------------------------------------- template assets

def delete_template_asset(db: Session, settings: Settings, user, asset_id: str) -> None:
    from app.models.tables import TemplateAsset
    asset = db.get(TemplateAsset, asset_id)
    if not asset or asset.deleted_at:
        raise AppError("Asset not found.", 404)
    _soft_delete_item(db, settings, user, asset, "template_asset")


def restore_template_asset(db: Session, user, asset_id: str) -> None:
    from app.models.tables import TemplateAsset
    asset = db.get(TemplateAsset, asset_id)
    if not asset or not asset.deleted_at:
        raise AppError("Trash asset not found.", 404)
    _restore_item(db, asset)


def list_trash_template_assets(db: Session) -> list:
    from app.models.tables import TemplateAsset
    return _list_trash_items(db, TemplateAsset)


def purge_expired_template_assets(db: Session, now: datetime) -> int:
    return 0


# ---------------------------------------------------------------- combined

def list_trash_categorized(db: Session, user, retention_days: int) -> dict:
    sessions = []
    for uploaded in list_trash(db, user):
        item = serialize_file(uploaded)
        sessions.append(item)

    templates = [
        {"id": t.id, "name": t.name, "deleted_at": t.deleted_at.isoformat() if t.deleted_at else None}
        for t in list_trash_templates(db)
    ]
    specials = [
        {
            "id": s.id,
            "label": s.label,
            "category": s.category,
            "deleted_at": s.deleted_at.isoformat() if s.deleted_at else None,
            "variant_count": sum(1 for v in s.variants if not v.deleted_at),
        }
        for s in list_trash_specials(db)
    ]
    variants = [
        {
            "id": v.id,
            "label": v.label,
            "special_label": (db.get(OurSpecial, v.special_id).label if v.special_id and db.get(OurSpecial, v.special_id) else "—"),
            "deleted_at": v.deleted_at.isoformat() if v.deleted_at else None,
        }
        for v in list_trash_variants(db)
    ]
    records = [
        {"id": r.id, "insurer_no": r.insurer_no, "customer_name": r.customer_name, "vehicle_no": r.vehicle_no,
         "deleted_at": r.deleted_at.isoformat() if r.deleted_at else None}
        for r in list_trash_client_records(db)
    ]
    assets = [
        {"id": a.id, "label": a.label, "filename": a.filename, "folder": a.folder,
         "deleted_at": a.deleted_at.isoformat() if a.deleted_at else None}
        for a in list_trash_template_assets(db)
    ]
    return {
        "retention_policy": "manual_reference_aware_purge",
        "sessions": sessions,
        "templates": templates,
        "our_specials": specials,
        "our_special_variants": variants,
        "client_records": records,
        "assets": assets,
    }


def purge_all_expired(db: Session, retention_days: int | None = None) -> int:
    return 0


# ---------------------------------------------------------------- permanent delete (empty trash)

def _remove_trash_entries(db: Session, entity_type: str, entity_ids: list[str]) -> None:
    if not entity_ids:
        return
    db.execute(delete(TrashRecord).where(TrashRecord.entity_type == entity_type, TrashRecord.entity_id.in_(entity_ids)))


def _require_admin_for_category(user) -> None:
    if user.role not in {Role.SUPER_ADMIN.value, Role.ADMIN.value, Role.DEV.value}:
        raise AppError("Only Admin can permanently delete these items.", 403)


def permanent_delete_session(db: Session, user, uploaded_file_id: str, storage) -> None:
    uploaded = db.get(UploadedFile, uploaded_file_id)
    if not uploaded or not uploaded.deleted_at:
        raise AppError("Trash record not found.", 404)
    if not can_view_owner_record(db, user, uploaded.owner_id):
        raise AppError("You do not have permission to delete this record.", 403)
    if uploaded.storage_path:
        try:
            storage.delete_pdf(uploaded.storage_path)
        except Exception as exc:
            logger.warning("Could not delete source PDF %s during trash clear: %s", uploaded.storage_path, exc)
    for version in db.scalars(select(GeneratedPdfVersion).where(GeneratedPdfVersion.uploaded_file_id == uploaded.id)).all():
        if version.storage_path:
            try:
                storage.delete_pdf(version.storage_path)
            except Exception as exc:
                logger.warning("Could not delete generated PDF %s during trash clear: %s", version.storage_path, exc)
    # Some FKs lack ON DELETE CASCADE, so remove dependent rows explicitly before the parent.
    from app.models.tables import CorrectionMemory, ExtractionRecord, QuotationDraft, Session as SessionModel

    client_ids = [
        r.id for r in db.scalars(select(ClientRecord).where(ClientRecord.uploaded_file_id == uploaded.id)).all()
    ]
    if client_ids:
        _remove_trash_entries(db, "client_record", client_ids)
    db.execute(delete(ClientRecord).where(ClientRecord.uploaded_file_id == uploaded.id))
    db.execute(delete(SessionModel).where(SessionModel.uploaded_file_id == uploaded.id))
    db.execute(delete(CorrectionMemory).where(CorrectionMemory.uploaded_file_id == uploaded.id))
    db.execute(delete(GeneratedPdfVersion).where(GeneratedPdfVersion.uploaded_file_id == uploaded.id))
    db.execute(delete(ExtractionRecord).where(ExtractionRecord.uploaded_file_id == uploaded.id))
    db.execute(delete(QuotationDraft).where(QuotationDraft.uploaded_file_id == uploaded.id))
    _remove_trash_entries(db, "uploaded_file", [uploaded.id])
    db.delete(uploaded)
    db.commit()


def permanent_delete_template(db: Session, user, template_id: str) -> None:
    _require_admin_for_category(user)
    template = db.get(OutputTemplateConfig, template_id)
    if not template or not template.deleted_at:
        raise AppError("Trash template not found.", 404)
    _remove_trash_entries(db, "template", [template.id])
    db.delete(template)
    db.commit()


def permanent_delete_special(db: Session, user, special_id: str) -> None:
    _require_admin_for_category(user)
    special = db.get(OurSpecial, special_id)
    if not special or not special.deleted_at:
        raise AppError("Trash Our Special not found.", 404)
    variant_ids = [v.id for v in special.variants]
    for variant in list(special.variants):
        db.delete(variant)
    _remove_trash_entries(db, "our_special", [special.id])
    if variant_ids:
        _remove_trash_entries(db, "our_special_variant", variant_ids)
    db.delete(special)
    db.commit()


def permanent_delete_special_variant(db: Session, user, variant_id: str) -> None:
    _require_admin_for_category(user)
    variant = db.get(OurSpecialVariant, variant_id)
    if not variant or not variant.deleted_at:
        raise AppError("Trash variant not found.", 404)
    _remove_trash_entries(db, "our_special_variant", [variant.id])
    db.delete(variant)
    db.commit()


def permanent_delete_client_record(db: Session, user, record_id: str) -> None:
    _require_admin_for_category(user)
    record = db.get(ClientRecord, record_id)
    if not record or not record.deleted_at:
        raise AppError("Trash client record not found.", 404)
    _remove_trash_entries(db, "client_record", [record.id])
    db.delete(record)
    db.commit()


def permanent_delete_template_asset(db: Session, user, asset_id: str) -> None:
    _require_admin_for_category(user)
    asset = db.get(TemplateAsset, asset_id)
    if not asset or not asset.deleted_at:
        raise AppError("Trash asset not found.", 404)
    _remove_trash_entries(db, "template_asset", [asset.id])
    db.delete(asset)
    db.commit()


def empty_all_trash(db: Session, user, storage) -> dict:
    """Permanently delete everything currently in the trash."""
    counts: dict[str, int] = {"sessions": 0, "templates": 0, "our_specials": 0, "our_special_variants": 0, "client_records": 0, "assets": 0}

    for uploaded in list_trash(db, user):
        permanent_delete_session(db, user, uploaded.id, storage)
        counts["sessions"] += 1

    if user.role not in {Role.SUPER_ADMIN.value, Role.ADMIN.value, Role.DEV.value}:
        return counts

    for template in list_trash_templates(db):
        permanent_delete_template(db, user, template.id)
        counts["templates"] += 1
    for special in list_trash_specials(db):
        permanent_delete_special(db, user, special.id)
        counts["our_specials"] += 1
    for variant in list_trash_variants(db):
        if not (variant.special_id and db.get(OurSpecial, variant.special_id) and not db.get(OurSpecial, variant.special_id).deleted_at):
            continue
        permanent_delete_special_variant(db, user, variant.id)
        counts["our_special_variants"] += 1
    for record in list_trash_client_records(db):
        permanent_delete_client_record(db, user, record.id)
        counts["client_records"] += 1
    for asset in list_trash_template_assets(db):
        permanent_delete_template_asset(db, user, asset.id)
        counts["assets"] += 1

    return counts
