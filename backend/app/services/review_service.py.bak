"""Draft review, correction memory, history, and trash operations."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm import Session, selectinload

from app.auth.rbac import can_view_owner_record
from app.core.config import Settings
from app.core.errors import AppError
from app.models.enums import RecordStatus, Role, StorageStatus
from app.models.tables import Batch, CorrectionMemory, OutputTemplateConfig, QuotationDraft, TrashRecord, UploadedFile
from app.services.template_config import normalize_template_config, review_schema_for


def get_accessible_draft(db: Session, user, draft_id: str) -> QuotationDraft:
    draft = db.scalar(
        select(QuotationDraft)
        .where(QuotationDraft.id == draft_id)
        .options(
            selectinload(QuotationDraft.uploaded_file).selectinload(UploadedFile.extraction_record),
            selectinload(QuotationDraft.versions),
        )
    )
    if not draft or draft.deleted_at:
        raise AppError("Draft not found.", 404)
    if not can_view_owner_record(db, user, draft.owner_id):
        raise AppError("You do not have permission to view this draft.", 403)
    return draft


def _available_templates(db: Session | None) -> list[dict]:
    if db is None:
        return []
    templates = db.scalars(select(OutputTemplateConfig).where(OutputTemplateConfig.status == "active").order_by(OutputTemplateConfig.name)).all()
    output: list[dict] = []
    for template in templates:
        config = normalize_template_config(template.fixed_fields if isinstance(template.fixed_fields, dict) else {}, template.name)
        output.append(
            {
                "id": template.id,
                "name": template.name,
                "insurance_type": template.insurance_type,
                "status": template.status,
                "locked": bool(config.get("locked")),
                "is_default": bool(config.get("is_default")),
                "packages": config.get("packages") or [{"name": "Base", "included": [], "add_ons": []}],
                "cards": config.get("cards") or {},
                "review_schema": review_schema_for(config, None),
            }
        )
    return output


def _field_hints(draft: QuotationDraft) -> dict[str, str]:
    record = draft.uploaded_file.extraction_record if draft.uploaded_file and draft.uploaded_file.extraction_record else None
    if not record or not record.candidates:
        return {}
    friendly = {
        "customer_name": "Found under customer details.",
        "vehicle_no": "Found under vehicle information.",
        "car_brand": "Found under vehicle information.",
        "car_model": "Found under vehicle information.",
        "vehicle_year": "Found under vehicle information.",
        "engine_cc": "Found under vehicle information.",
        "cover_start_date": "Found under cover period.",
        "cover_end_date": "Found under cover period.",
        "cover_period": "Found under cover period.",
        "coverage_type": "Found under coverage information.",
        "coverage_amount": "Found under coverage information.",
        "premium": "Found under contribution summary.",
        "gross_premium": "Found under contribution summary.",
        "total_amount": "Found under total payable.",
        "ncd_percent": "Found under NCD.",
        "optional_covers": "Found under optional cover list.",
        "benefits_selected": "Found under optional cover list.",
        "add_ons_selected": "Selected from template package.",
        "insurance_company": "Found from file name or document heading.",
    }
    return {field: friendly.get(field, "Found in the uploaded quotation.") for field, candidates in record.candidates.items() if candidates}


def _draft_template_config(draft: QuotationDraft, db: Session | None) -> dict:
    template = None
    if db is not None and draft.uploaded_file and draft.uploaded_file.template_id:
        template = db.get(OutputTemplateConfig, draft.uploaded_file.template_id)
    template_category = (draft.fields.get("source_template_category") or {}).get("value") or "Other / Unknown"
    return normalize_template_config(template.fixed_fields if template and isinstance(template.fixed_fields, dict) else {}, template_category)


def serialize_draft(draft: QuotationDraft, db: Session | None = None) -> dict:
    record = draft.uploaded_file.extraction_record if draft.uploaded_file and draft.uploaded_file.extraction_record else None
    page_text = record.page_text if record else []
    uploaded = draft.uploaded_file
    source_available = bool(
        uploaded
        and uploaded.storage_status not in {StorageStatus.EXPIRED.value, StorageStatus.DELETED.value}
        and (not uploaded.storage_expires_at or uploaded.storage_expires_at > datetime.now(timezone.utc))
    )
    source_archived = bool(uploaded and uploaded.archive_status == StorageStatus.ARCHIVED.value)
    source_pdf_url = f"/uploaded-files/{uploaded.id}/content" if uploaded and (source_available or source_archived) else ""
    selected_template_id = draft.uploaded_file.template_id if draft.uploaded_file else None
    selected_package = (draft.fields.get("selected_package") or {}).get("value")
    config = _draft_template_config(draft, db)
    return {
        "id": draft.id,
        "uploaded_file_id": draft.uploaded_file_id,
        "filename": draft.uploaded_file.original_filename if draft.uploaded_file else "",
        "status": draft.status,
        "fields": draft.fields,
        "warnings": draft.warnings,
        "source_pdf_url": source_pdf_url,
        "source_pdf_status": uploaded.storage_status if uploaded else StorageStatus.DELETED.value,
        "source_pdf_expires_at": uploaded.storage_expires_at.isoformat() if uploaded and uploaded.storage_expires_at else None,
        "extracted_text": "\n\n".join(str(page.get("text", "")) for page in page_text),
        "page_text": page_text,
        "field_evidence": {},
        "field_hints": _field_hints(draft),
        "available_templates": _available_templates(db),
        "selected_template_id": selected_template_id,
        "selected_package": selected_package,
        "review_schema": review_schema_for(config, selected_package),
        "versions": [
            {
                "id": version.id,
                "version_number": version.version_number,
                "filename": version.filename,
                "download_url": (
                    f"/generated-versions/{version.id}/content?download=true"
                    if version.storage_status not in {StorageStatus.EXPIRED.value, StorageStatus.DELETED.value}
                    else ""
                ),
                "pdf_status": version.storage_status,
                "pdf_expires_at": version.storage_expires_at.isoformat() if version.storage_expires_at else None,
                "generated_at": version.generated_at.isoformat(),
            }
            for version in draft.versions
        ],
    }


def update_draft_fields(
    db: Session,
    user,
    draft_id: str,
    field_updates: dict[str, str | None],
    template_id: str | None = None,
    selected_package: str | None = None,
    benefits_selected: str | None = None,
    add_ons_selected: str | None = None,
) -> QuotationDraft:
    draft = get_accessible_draft(db, user, draft_id)
    fields = deepcopy(draft.fields or {})
    if template_id is not None:
        template = db.get(OutputTemplateConfig, template_id)
        if not template:
            raise AppError("Choose a valid Risklocker template.")
        if draft.uploaded_file:
            draft.uploaded_file.template_id = template.id
    extra_updates = {
        "selected_package": selected_package,
        "benefits_selected": benefits_selected,
        "add_ons_selected": add_ons_selected,
    }
    for key, value in extra_updates.items():
        if value is not None:
            field_updates[key] = value
    for field_name, new_value in field_updates.items():
        current = fields.get(field_name, {"value": None, "status": "ready", "message": ""})
        original_value = current.get("value")
        current["value"] = new_value
        current["status"] = "ready"
        current["message"] = ""
        fields[field_name] = current
        if original_value != new_value:
            db.add(
                CorrectionMemory(
                    draft_id=draft.id,
                    uploaded_file_id=draft.uploaded_file_id,
                    field_name=field_name,
                    original_value=original_value,
                    corrected_value=new_value,
                    insurance_company_id=draft.uploaded_file.insurance_company_id if draft.uploaded_file else None,
                    corrected_by=user.id,
                )
            )
    draft.fields = fields
    flag_modified(draft, "fields")
    draft.status = RecordStatus.READY.value if all(field.get("status") != "check_needed" for field in fields.values()) else RecordStatus.CHECK_NEEDED.value
    draft.reviewed_at = datetime.now(timezone.utc)
    draft.reviewed_by = user.id
    if draft.uploaded_file:
        draft.uploaded_file.status = draft.status
    db.commit()
    db.refresh(draft)
    return draft


def list_history(db: Session, user, status_filter: str | None = None, search: str | None = None) -> list[UploadedFile]:
    query = select(UploadedFile).options(selectinload(UploadedFile.draft)).where(UploadedFile.deleted_at.is_(None))
    if user.role == Role.STAFF.value:
        query = query.where(UploadedFile.owner_id == user.id)
    elif user.role == Role.MANAGER.value:
        from app.models.tables import User

        query = query.join(User, UploadedFile.owner_id == User.id).where(User.role == Role.STAFF.value)
    if status_filter:
        query = query.where(UploadedFile.status == status_filter)
    if search:
        like = f"%{search.lower()}%"
        query = query.where(
            or_(
                UploadedFile.original_filename.ilike(like),
                UploadedFile.draft.has(QuotationDraft.fields.cast(str).ilike(like)),
            )
        )
    return list(db.scalars(query.order_by(UploadedFile.created_at.desc())).all())


def move_to_trash(db: Session, settings: Settings, user, uploaded_file_id: str) -> None:
    uploaded = db.get(UploadedFile, uploaded_file_id)
    if not uploaded or uploaded.deleted_at:
        raise AppError("Record not found.", 404)
    if not can_view_owner_record(db, user, uploaded.owner_id):
        raise AppError("You do not have permission to delete this record.", 403)
    original_status = uploaded.status
    uploaded.status = RecordStatus.DELETED.value
    uploaded.mark_deleted(settings.trash_retention_days)
    if uploaded.draft:
        uploaded.draft.status = RecordStatus.DELETED.value
        uploaded.draft.mark_deleted(settings.trash_retention_days)
    db.add(
        TrashRecord(
            entity_type="uploaded_file",
            entity_id=uploaded.id,
            original_status=original_status,
            deleted_by=user.id,
            purge_after=datetime.now(timezone.utc) + timedelta(days=settings.trash_retention_days),
        )
    )
    db.commit()


def list_trash(db: Session, user) -> list[UploadedFile]:
    query = select(UploadedFile).where(UploadedFile.deleted_at.is_not(None)).options(selectinload(UploadedFile.draft))
    if user.role == Role.STAFF.value:
        query = query.where(UploadedFile.owner_id == user.id)
    elif user.role == Role.MANAGER.value:
        from app.models.tables import User

        query = query.join(User, UploadedFile.owner_id == User.id).where(User.role == Role.STAFF.value)
    return list(db.scalars(query.order_by(UploadedFile.deleted_at.desc())).all())


def restore_from_trash(db: Session, user, uploaded_file_id: str) -> None:
    uploaded = db.get(UploadedFile, uploaded_file_id)
    if not uploaded or not uploaded.deleted_at:
        raise AppError("Trash record not found.", 404)
    if not can_view_owner_record(db, user, uploaded.owner_id):
        raise AppError("You do not have permission to restore this record.", 403)
    restored_status = uploaded.draft.status if uploaded.draft and uploaded.draft.status != RecordStatus.DELETED.value else RecordStatus.CHECK_NEEDED.value
    uploaded.restore()
    uploaded.status = restored_status
    if uploaded.draft:
        uploaded.draft.restore()
        uploaded.draft.status = restored_status
    db.commit()


def purge_expired_trash(db: Session, user) -> int:
    if user.role != Role.ADMIN.value:
        raise AppError("Only Admin can permanently delete records.", 403)
    now = datetime.now(timezone.utc)
    records = list(db.scalars(select(UploadedFile).where(and_(UploadedFile.deleted_at.is_not(None), UploadedFile.purge_after <= now))).all())
    count = len(records)
    for record in records:
        db.delete(record)
    db.commit()
    return count
