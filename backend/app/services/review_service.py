"""Draft review, correction memory, history, and trash operations."""

from __future__ import annotations

import logging
from copy import deepcopy
from datetime import datetime, timezone

from sqlalchemy import and_, delete, select
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm import Session, selectinload

from app.auth.rbac import can_view_owner_record
from app.core.config import Settings
from app.core.errors import AppError
from app.models.enums import RecordStatus, Role, StorageStatus
from app.models.tables import Batch, CorrectionMemory, InsuranceCompany, OutputTemplateConfig, QuotationDraft, TemplateGroup, TrashRecord, UploadedFile
from app.services.template_config import normalize_template_config, review_schema_for
from app.services.admin_service import get_runner_fee_default


logger = logging.getLogger(__name__)


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
    templates = db.scalars(
        select(OutputTemplateConfig).where(
            OutputTemplateConfig.status == "active",
            OutputTemplateConfig.deleted_at.is_(None),
        ).order_by(OutputTemplateConfig.name)
    ).all()
    output: list[dict] = []
    for template in templates:
        config = normalize_template_config(template.fixed_fields if isinstance(template.fixed_fields, dict) else {}, template.name)
        group = db.get(TemplateGroup, template.group_id) if template.group_id else None
        group_company = db.get(InsuranceCompany, group.company_id) if group and group.company_id else None
        template_company = db.get(InsuranceCompany, template.insurance_company_id) if template.insurance_company_id else None
        output.append(
            {
                "id": template.id,
                "name": template.name,
                "insurance_type": template.insurance_type,
                "insurance_company_id": template.insurance_company_id,
                "insurance_company_name": template_company.name if template_company else None,
                "group_id": template.group_id,
                "group_name": group.name if group else None,
                "group_company_id": group.company_id if group else None,
                "group_company_name": group_company.name if group_company else None,
                "status": template.status,
                "locked": bool(config.get("locked")),
                "is_default": bool(config.get("is_default")),
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
        "insurance_company": "Found from file name or document heading.",
    }
    return {field: friendly.get(field, "Found in the uploaded quotation.") for field, candidates in record.candidates.items() if candidates}


def _field_evidence(draft: QuotationDraft) -> dict[str, list[dict]]:
    record = draft.uploaded_file.extraction_record if draft.uploaded_file and draft.uploaded_file.extraction_record else None
    if not record or not record.candidates:
        return {}
    return {
        field: [
            {
                "value": c.get("value", ""),
                "score": c.get("score", 0),
                "source_method": c.get("source_method", ""),
                "page": c.get("page"),
                "evidence": c.get("evidence", ""),
            }
            for c in candidates
        ]
        for field, candidates in record.candidates.items()
        if candidates
    }


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
    config = _draft_template_config(draft, db)
    return {
        "id": draft.id,
        "uploaded_file_id": draft.uploaded_file_id,
        "filename": draft.uploaded_file.original_filename if draft.uploaded_file else "",
        "status": draft.status,
        "fields": draft.fields,
        "warnings": draft.warnings,
        "layout_override": draft.layout_override,
        "source_pdf_url": source_pdf_url,
        "source_pdf_status": uploaded.storage_status if uploaded else StorageStatus.DELETED.value,
        "source_pdf_expires_at": uploaded.storage_expires_at.isoformat() if uploaded and uploaded.storage_expires_at else None,
        "extracted_text": "\n\n".join(str(page.get("text", "")) for page in page_text),
        "page_text": page_text,
        "field_evidence": _field_evidence(draft),
        "field_hints": _field_hints(draft),
        "available_templates": _available_templates(db),
        "selected_template_id": selected_template_id,
        "runner_fee_default": get_runner_fee_default(db) if db else 20.0,
        "review_schema": review_schema_for(config, None),
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
    layout_override: dict | None = None,
) -> QuotationDraft:
    draft = get_accessible_draft(db, user, draft_id)
    fields = deepcopy(draft.fields or {})
    if layout_override is not None:
        draft.layout_override = layout_override
        flag_modified(draft, "layout_override")
    if template_id is not None:
        template = db.get(OutputTemplateConfig, template_id)
        if not template:
            raise AppError("Choose a valid Risklocker template.")
        if draft.uploaded_file:
            draft.uploaded_file.template_id = template.id
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
            purge_after=None,
        )
    )
    db.commit()


def list_trash(db: Session, user) -> list[UploadedFile]:
    query = select(UploadedFile).where(UploadedFile.deleted_at.is_not(None)).options(selectinload(UploadedFile.draft))
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


def purge_expired_trash(db: Session, user, storage) -> int:
    # RL-DISABLED timed trash purge — disabled 2026-08-14. Use the explicit
    # reference-aware permanent-delete endpoints instead.
    return 0

