"""Secure upload, extraction, and draft creation flow."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.extraction.company_resolution import build_companies_payload
from app.extraction.sandbox import extract_with_limits
from app.models.enums import AccountStatus, RecordStatus, StorageStatus
from app.models.tables import AppSetting, Batch, BenefitConcept, CompanyAlias, ExtractionRecord, FieldAlias, InsuranceCompany, QuotationDraft, UploadedFile, VehicleBrand, VehicleModel, new_id
from app.services.document_security import quarantined_pdf
from app.services.file_validation import display_filename, validate_upload_bytes
from app.services.session_service import create_session
from app.storage.supabase import StorageError, SupabaseStorage


logger = logging.getLogger(__name__)


def _source_key(now: datetime, batch_id: str, uploaded_file_id: str) -> str:
    return f"source/{now:%Y}/{now:%m}/{batch_id}/{uploaded_file_id}.pdf"


def _cannot_read_result() -> dict:
    return {
        "full_record": {
            "method_summary": ["PDF accepted; reading could not be completed"],
            "raw_text": "",
            "ocr_text": "",
            "page_text": [],
            "words": [],
            "blocks": [],
            "tables": [],
            "images": [],
            "regions": [],
            "candidates": {},
            "warnings": ["Cannot Read"],
            "reading_quality": "cannot_read",
        },
        "draft": {"status": RecordStatus.CANNOT_READ.value, "fields": {}, "warnings": ["Cannot Read"]},
    }


def _persist_upload(
    db: Session,
    settings: Settings,
    *,
    batch_id: str,
    owner_id: str,
    uploaded_id: str,
    filename: str,
    enhanced_reading: bool,
    now: datetime,
    stored,
    scan: dict,
    result: dict,
) -> None:
    full = result["full_record"]
    draft_data = result["draft"]
    uploaded = UploadedFile(
        id=uploaded_id,
        batch_id=batch_id,
        owner_id=owner_id,
        original_filename=filename,
        content_type="application/pdf",
        storage_path=stored.object_key,
        storage_provider="supabase",
        storage_bucket=stored.bucket,
        storage_status=StorageStatus.AVAILABLE.value,
        storage_sha256=stored.sha256,
        storage_etag=stored.etag,
        storage_stored_at=now,
        storage_expires_at=None,
        security_scan=scan,
        size_bytes=stored.size_bytes,
        status=draft_data["status"],
        enhanced_reading=enhanced_reading,
        simple_issue=(
            "Please check this value."
            if draft_data["status"] == RecordStatus.CHECK_NEEDED.value
            else "Cannot Read" if draft_data["status"] == RecordStatus.CANNOT_READ.value else None
        ),
    )
    db.add(uploaded)
    db.flush()
    db.add(
        ExtractionRecord(
            uploaded_file_id=uploaded.id,
            method_summary=full["method_summary"],
            raw_text=full["raw_text"],
            ocr_text=full["ocr_text"],
            page_text=full["page_text"],
            words=full["words"],
            blocks=full["blocks"],
            tables=full["tables"],
            images=full["images"],
            regions=full["regions"],
            candidates=full["candidates"],
            warnings=full["warnings"],
            reading_quality=full["reading_quality"],
        )
    )
    db.add(
        QuotationDraft(
            uploaded_file_id=uploaded.id,
            owner_id=owner_id,
            status=draft_data["status"],
            fields=draft_data["fields"],
            warnings=draft_data["warnings"],
        )
    )
    db.flush()
    detected = (draft_data.get("fields") or {}).get("insurance_company", {}).get("value")
    draft = db.scalar(select(QuotationDraft).where(QuotationDraft.uploaded_file_id == uploaded.id))
    if draft:
        create_session(db, owner_id, uploaded.id, draft.id, detected)


async def create_batch_from_uploads(
    db: Session,
    settings: Settings,
    owner_id: str,
    files: list[UploadFile],
    enhanced_reading: bool = False,
) -> Batch:
    if not files:
        raise AppError("Choose at least one file to upload.")
    if len(files) > settings.max_upload_files:
        raise AppError(f"Upload up to {settings.max_upload_files} files at a time.")

    storage = SupabaseStorage(settings)
    batch = Batch(
        owner_id=owner_id,
        name=f"Upload batch ({len(files)} files)",
        status=RecordStatus.PREPARING.value,
        enhanced_reading_requested=enhanced_reading,
    )
    db.add(batch)
    db.flush()

    db_aliases = {f.field_name: f.aliases for f in db.scalars(select(FieldAlias)).all()} if db else None
    db_brands: list[str] = []
    db_models: list[str] = []
    for b in db.scalars(select(VehicleBrand)).all():
        db_brands.append(b.name)
        db_brands.extend(b.aliases or [])
    for m in db.scalars(select(VehicleModel)).all():
        db_models.append(m.name)
        db_models.extend(m.aliases or [])

    db_companies = None
    if db:
        company_rows = db.scalars(
            select(InsuranceCompany).where(InsuranceCompany.status == AccountStatus.ACTIVE.value)
        ).all()
        alias_rows = db.scalars(
            select(CompanyAlias).where(CompanyAlias.status == AccountStatus.ACTIVE.value)
        ).all()
        db_companies = build_companies_payload(company_rows, alias_rows)

    db_benefit_concepts = [
        {
            "concept_id": concept.id,
            "concept_key": concept.concept_key,
            "label": concept.label,
        }
        for concept in db.scalars(select(BenefitConcept)).all()
    ] if db else None

    prompt_override = None
    if db:
        setting = db.get(AppSetting, "ai_system_prompt")
        if setting and isinstance(setting.value, dict) and str(setting.value.get("text") or "").strip():
            prompt_override = str(setting.value["text"]).strip()

    upload_failures: list[dict] = []
    for file in files:
        filename = display_filename(file.filename)
        stored_key: str | None = None
        try:
            data = await file.read()
            validate_upload_bytes(file.filename, file.content_type, data, settings.max_upload_bytes)
            now = datetime.now(timezone.utc)
            uploaded_id = new_id()
            with quarantined_pdf(data, settings) as (quarantine_path, scan):
                try:
                    result = extract_with_limits(
                        quarantine_path,
                        enhanced_reading=enhanced_reading,
                        source_filename=filename,
                        db_aliases=db_aliases,
                        db_brands=db_brands,
                        db_models=db_models,
                        db_companies=db_companies,
                        db_benefit_concepts=db_benefit_concepts,
                        prompt_override=prompt_override,
                    )
                except Exception as exc:
                    logger.warning("Extraction failed for %s: %s", filename, exc)
                    result = _cannot_read_result()
                object_key = _source_key(now, batch.id, uploaded_id)
                stored = storage.upload_pdf(object_key, data)
                stored_key = stored.object_key

            with db.begin_nested():
                _persist_upload(
                    db,
                    settings,
                    batch_id=batch.id,
                    owner_id=owner_id,
                    uploaded_id=uploaded_id,
                    filename=filename,
                    enhanced_reading=enhanced_reading,
                    now=now,
                    stored=stored,
                    scan=scan,
                    result=result,
                )
        except (ValueError, StorageError) as exc:
            if stored_key:
                try:
                    storage.delete_pdf(stored_key)
                except StorageError as cleanup_exc:
                    logger.warning("Could not clean up uploaded file %s: %s", stored_key, cleanup_exc)
            upload_failures.append({"filename": filename, "message": str(exc)})
            continue
        except Exception as exc:
            logger.exception("Upload preparation failed for %s", filename)
            if stored_key:
                try:
                    storage.delete_pdf(stored_key)
                except StorageError as cleanup_exc:
                    logger.warning("Could not clean up uploaded file %s: %s", stored_key, cleanup_exc)
            upload_failures.append({"filename": filename, "message": "This PDF could not be prepared."})
            continue

    db.flush()
    statuses = {item.status for item in batch.files}
    if not batch.files or upload_failures or RecordStatus.CANNOT_READ.value in statuses or RecordStatus.CHECK_NEEDED.value in statuses:
        batch.status = RecordStatus.CHECK_NEEDED.value
    else:
        batch.status = RecordStatus.READY.value
    db.commit()
    db.refresh(batch)
    setattr(batch, "_upload_failures", upload_failures)
    return batch


def serialize_file(file: UploadedFile) -> dict:
    draft_id = file.draft.id if file.draft else None
    return {
        "id": file.id,
        "draft_id": draft_id,
        "filename": file.original_filename,
        "status": file.status,
        "pdf_status": file.storage_status,
        "pdf_expires_at": file.storage_expires_at.isoformat() if file.storage_expires_at else None,
        "enhanced_reading": file.enhanced_reading,
        "simple_issue": file.simple_issue,
        "created_at": file.created_at.isoformat(),
    }


def serialize_batch(batch: Batch) -> dict:
    return {
        "id": batch.id,
        "name": batch.name,
        "status": batch.status,
        "created_at": batch.created_at.isoformat(),
        "files": [serialize_file(file) for file in batch.files if not file.deleted_at],
        "failed_files": getattr(batch, "_upload_failures", []),
    }
