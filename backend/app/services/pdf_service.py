"""Generate versioned Risklocker PDFs and persist them in Supabase Storage."""

from __future__ import annotations

import logging
import tempfile
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.models.enums import RecordStatus, StorageStatus
from app.models.tables import GeneratedPdfVersion, OutputTemplateConfig, QuotationDraft
from app.rendering.pdf_generator import html_to_pdf
from app.rendering.template_renderer import render_quotation_html
from app.services.document_security import quarantined_pdf
from app.services.client_record_service import upsert_from_draft
from app.services.template_config import normalize_template_config
from app.storage.supabase import StorageError, SupabaseStorage


logger = logging.getLogger(__name__)


def _version_filename(original_filename: str, version_number: int) -> str:
    base = Path(original_filename).stem or "quotation"
    suffix = "original" if version_number == 1 else f"edited_{version_number - 1}"
    return f"{base}_{suffix}.pdf"


def generate_pdf(db: Session, settings: Settings, user, draft: QuotationDraft, acknowledge_check_needed: bool = False) -> GeneratedPdfVersion:
    check_needed = [name for name, field in draft.fields.items() if field.get("status") == "check_needed"]
    if check_needed:
        raise AppError("Please check highlighted values before generating.")
    if not draft.reviewed_at:
        raise AppError("Save the reviewed draft before generating.")
    if not draft.uploaded_file or not draft.uploaded_file.template_id:
        raise AppError("Choose a Risklocker template before generating.")
    template = db.get(OutputTemplateConfig, draft.uploaded_file.template_id)
    if not template:
        raise AppError("Choose a valid Risklocker template before generating.")

    template_config = normalize_template_config(template.fixed_fields, template.name)
    html = render_quotation_html(
        draft.fields,
        template_name=template.name,
        static_notes=template.static_notes,
        template_config=template_config,
        insurer_name=(draft.fields.get("insurance_company") or {}).get("value"),
    )
    next_number = (db.scalar(select(func.max(GeneratedPdfVersion.version_number)).where(GeneratedPdfVersion.draft_id == draft.id)) or 0) + 1
    filename = _version_filename(draft.uploaded_file.original_filename, next_number)
    now = datetime.now(timezone.utc)
    object_key = f"generated/{now:%Y}/{now:%m}/{draft.id}/v{next_number}-{uuid4()}.pdf"
    storage = SupabaseStorage(settings)
    stored = None
    try:
        with tempfile.TemporaryDirectory(prefix="risklocker-render-") as directory:
            output_path = Path(directory) / filename
            _, warnings = html_to_pdf(html, output_path)
            if warnings:
                draft.warnings = list({*draft.warnings, *warnings})
            data = output_path.read_bytes()
            if len(data) > settings.max_upload_bytes:
                raise AppError("Generated PDF exceeds the configured storage limit.")
            with quarantined_pdf(data, settings):
                stored = storage.upload_pdf(object_key, data)
    except StorageError as exc:
        raise AppError(str(exc), 503) from exc
    except ValueError as exc:
        raise AppError(str(exc)) from exc

    version = GeneratedPdfVersion(
        draft_id=draft.id,
        uploaded_file_id=draft.uploaded_file_id,
        version_number=next_number,
        filename=filename,
        storage_path=stored.object_key,
        storage_provider="supabase",
        storage_bucket=stored.bucket,
        storage_status=StorageStatus.AVAILABLE.value,
        storage_sha256=stored.sha256,
        storage_etag=stored.etag,
        storage_stored_at=now,
        storage_expires_at=now + timedelta(days=settings.pdf_retention_days),
        draft_snapshot=deepcopy(draft.fields),
        template_snapshot=deepcopy(template_config),
        generated_by=user.id,
    )
    db.add(version)
    draft.status = RecordStatus.GENERATED.value
    draft.uploaded_file.status = RecordStatus.GENERATED.value
    from app.models.tables import Session as SessionModel
    session = db.scalar(select(SessionModel).where(SessionModel.uploaded_file_id == draft.uploaded_file_id))
    upsert_from_draft(
        db,
        draft.fields,
        session_id=session.id if session else None,
        draft_id=draft.id,
        uploaded_file_id=draft.uploaded_file_id,
    )
    try:
        db.commit()
    except Exception as exc:
        logger.exception("Failed to commit generated PDF for draft %s: %s", draft.id, exc)
        try:
            storage.delete_pdf(stored.object_key)
        except StorageError as cleanup_exc:
            logger.warning("Could not clean up generated PDF %s after commit failure: %s", stored.object_key, cleanup_exc)
        raise
    db.refresh(version)
    return version
