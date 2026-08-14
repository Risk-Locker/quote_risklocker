"""Transactional intake for the canonical one-PDF upload workflow."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Callable, ContextManager

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.config import Settings
from app.core.errors import AppError
from app.models.enums import AccountStatus, RecordStatus, StorageStatus
from app.models.tables import (
    Batch,
    Job,
    QuotationDraft,
    Session as QuotationSession,
    UploadedFile,
    new_id,
)
from app.services.document_security import quarantined_pdf
from app.services.file_validation import display_filename, validate_upload_bytes
from app.storage.supabase import SupabaseStorage


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QueuedUpload:
    """Canonical upload response before extraction finishes."""

    created: bool
    job: Job
    session: Any
    uploaded_file: Any
    draft: Any | None


def _source_key(now: datetime, session_id: str, uploaded_file_id: str) -> str:
    return f"source/{now:%Y}/{now:%m}/{session_id}/{uploaded_file_id}.pdf"


def _load_or_reference(db: DbSession, model: type, object_id: str | None) -> Any | None:
    if not object_id:
        return None
    get = getattr(db, "get", None)
    loaded = get(model, object_id) if callable(get) else None
    return loaded or SimpleNamespace(id=object_id)


def _existing_result(db: DbSession, job: Job) -> QueuedUpload:
    session = _load_or_reference(db, QuotationSession, job.session_id)
    uploaded_file = _load_or_reference(db, UploadedFile, job.uploaded_file_id)
    draft = None
    if session is not None:
        draft_id = getattr(session, "draft_id", None)
        draft = _load_or_reference(db, QuotationDraft, draft_id)
    return QueuedUpload(False, job, session, uploaded_file, draft)


def _validate_idempotency_key(value: str) -> str:
    key = value.strip()
    if not key or len(key) > 160:
        raise AppError("A non-empty Idempotency-Key of at most 160 characters is required.")
    return key


async def create_queued_upload(
    db: DbSession,
    settings: Settings,
    *,
    owner_id: str,
    upload: UploadFile,
    idempotency_key: str,
    enhanced_reading: bool = False,
    storage: SupabaseStorage | None = None,
    quarantine: Callable[[bytes, Settings], ContextManager[tuple[Any, dict]]] = quarantined_pdf,
) -> QueuedUpload:
    """Validate, scan, store, and enqueue one PDF as a single DB transaction.

    The object store cannot participate in the Postgres transaction. If the
    database commit fails, the just-uploaded object is reconciled immediately.
    """

    key = _validate_idempotency_key(idempotency_key)
    existing = db.scalar(
        select(Job).where(Job.job_type == "extract_pdf", Job.idempotency_key == key)
    )
    if existing is not None:
        if existing.owner_id != owner_id:
            raise AppError("This idempotency key is already in use.", status_code=409)
        return _existing_result(db, existing)

    data = await upload.read()
    filename = display_filename(upload.filename)
    try:
        validate_upload_bytes(
            upload.filename,
            upload.content_type,
            data,
            settings.max_source_pdf_bytes,
        )
    except ValueError as exc:
        raise AppError(str(exc)) from exc

    storage_client = storage or SupabaseStorage(settings)
    stored_key: str | None = None
    now = datetime.now(timezone.utc)
    batch_id = new_id()
    uploaded_file_id = new_id()
    draft_id = new_id()
    session_id = new_id()
    job_id = new_id()

    try:
        with quarantine(data, settings) as (_quarantine_path, scan):
            object_key = _source_key(now, session_id, uploaded_file_id)
            stored = storage_client.upload_pdf(object_key, data)
            stored_key = stored.object_key

        batch = Batch(
            id=batch_id,
            owner_id=owner_id,
            name=f"Upload: {filename}",
            status=RecordStatus.PREPARING.value,
            enhanced_reading_requested=enhanced_reading,
        )
        uploaded_file = UploadedFile(
            id=uploaded_file_id,
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
            status=RecordStatus.PREPARING.value,
            enhanced_reading=enhanced_reading,
        )
        draft = QuotationDraft(
            id=draft_id,
            revision=1,
            uploaded_file_id=uploaded_file_id,
            owner_id=owner_id,
            status=RecordStatus.PREPARING.value,
            fields={},
            scalar_decisions={},
            warnings=[],
        )
        session = QuotationSession(
            id=session_id,
            owner_id=owner_id,
            uploaded_file_id=uploaded_file_id,
            draft_id=draft_id,
            status=AccountStatus.ACTIVE.value,
        )
        job = Job(
            id=job_id,
            owner_id=owner_id,
            session_id=session_id,
            uploaded_file_id=uploaded_file_id,
            job_type="extract_pdf",
            idempotency_key=key,
            state="queued",
            payload={"enhanced_reading": enhanced_reading},
            result={},
            safe_error={},
            progress=0,
            attempt=0,
            max_attempts=3,
            available_at=now,
        )
        # Insert in explicit dependency order. The session unit-of-work can
        # otherwise emit INSERTs in table-name order (batches, jobs, ...) and
        # violate the jobs->sessions foreign key.
        db.add(batch)
        db.flush()
        db.add(uploaded_file)
        db.flush()
        db.add(draft)
        db.flush()
        db.add(session)
        db.flush()
        db.add(job)
        db.commit()
        return QueuedUpload(True, job, session, uploaded_file, draft)
    except ValueError as exc:
        db.rollback()
        if stored_key:
            try:
                storage_client.delete_pdf(stored_key)
            except Exception:
                logger.exception("Failed to reconcile rejected upload object")
        raise AppError(str(exc)) from exc
    except Exception:
        db.rollback()
        if stored_key:
            try:
                storage_client.delete_pdf(stored_key)
            except Exception:
                logger.exception("Failed to reconcile upload after database failure")
        raise
