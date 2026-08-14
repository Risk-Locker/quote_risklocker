"""Consume a frozen render snapshot and persist one immutable PDF version."""

from __future__ import annotations

import base64
import hashlib
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select

from app.core.workspace import qc_temp_directory
from app.models.enums import RecordStatus, StorageStatus
from app.models.tables import GeneratedPdfVersion, Job, QuotationDraft, RenderSnapshot, Session
from app.rendering.pdf_generator import PdfOutputInvalid, PdfRendererUnavailable, html_to_pdf
from app.rendering.render_context import canonical_context_hash
from app.rendering.template_renderer import render_quotation_html
from app.services.job_service import complete_job, heartbeat_job
from app.storage.supabase import StorageError, SupabaseStorage


@dataclass(frozen=True)
class JobProcessingError(RuntimeError):
    code: str
    safe_message: str

    def __str__(self) -> str:
        return self.safe_message


def _filename(source_filename: str, version_number: int) -> str:
    stem = Path(source_filename or "quotation").stem or "quotation"
    safe = "".join(character if character.isalnum() or character in {"-", "_", " "} else "_" for character in stem).strip()
    return f"{safe[:150] or 'quotation'}_v{version_number}.pdf"


def _validate_pdf_bytes(data: bytes) -> bool:
    return len(data) >= 100 and data.startswith(b"%PDF-") and b"%%EOF" in data[-2_048:]


def _resolve_assets(snapshot: RenderSnapshot, storage: SupabaseStorage) -> dict[str, str]:
    assets = snapshot.context.get("assets") or {}
    resolved = dict(assets.get("embedded") or {})
    manifest = assets.get("manifest") or {}
    for asset_id, item in sorted(manifest.items()):
        data = storage.download_bytes(str(item.get("storage_path") or ""))
        expected = str(item.get("content_hash") or "")
        if not expected or hashlib.sha256(data).hexdigest() != expected:
            raise JobProcessingError("render_asset_integrity_failed", "A frozen render asset failed its integrity check.")
        content_type = str(item.get("content_type") or "application/octet-stream")
        resolved[asset_id] = f"data:{content_type};base64,{base64.b64encode(data).decode('ascii')}"
    for asset_id, expected in (snapshot.asset_hashes or {}).items():
        if asset_id in manifest:
            continue
        uri = resolved.get(asset_id, "")
        if not uri.startswith("data:") or "," not in uri:
            raise JobProcessingError("render_asset_missing", "A frozen render asset is unavailable.")
        try:
            data = base64.b64decode(uri.split(",", 1)[1], validate=True)
        except ValueError as exc:
            raise JobProcessingError("render_asset_integrity_failed", "A frozen render asset is invalid.") from exc
        if hashlib.sha256(data).hexdigest() != expected:
            raise JobProcessingError("render_asset_integrity_failed", "A frozen render asset failed its integrity check.")
    return resolved


def process_render_job(
    db,
    settings,
    job: Job,
    *,
    worker_id: str,
    storage: SupabaseStorage | None = None,
    renderer=html_to_pdf,
    validate_pdf=_validate_pdf_bytes,
) -> None:
    payload = job.payload or {}
    snapshot = db.get(RenderSnapshot, payload.get("render_snapshot_id"))
    if not snapshot or snapshot.id != payload.get("render_snapshot_id"):
        raise JobProcessingError("render_snapshot_missing", "The frozen render snapshot is unavailable.")
    if canonical_context_hash(snapshot.context) != snapshot.context_hash:
        raise JobProcessingError("render_snapshot_integrity_failed", "The frozen render snapshot failed its integrity check.")
    if (
        snapshot.draft_id != payload.get("draft_id")
        or snapshot.draft_revision != int(payload.get("draft_revision") or 0)
        or snapshot.renderer_version != snapshot.context.get("renderer_version")
    ):
        raise JobProcessingError("render_snapshot_mismatch", "The generation request does not match its frozen snapshot.")

    existing = next(
        (
            version for version in db.scalars(
                select(GeneratedPdfVersion).where(
                    GeneratedPdfVersion.draft_id == snapshot.draft_id,
                    GeneratedPdfVersion.idempotency_key == job.idempotency_key,
                )
            ).all()
            if version.draft_id == snapshot.draft_id and version.idempotency_key == job.idempotency_key
        ),
        None,
    )
    if existing:
        complete_job(db, job, worker_id, {"version_id": existing.id, "version_number": existing.version_number})
        return

    draft = db.get(QuotationDraft, snapshot.draft_id)
    session = db.get(Session, job.session_id) if job.session_id else None
    if not draft or not session or session.draft_id != draft.id:
        raise JobProcessingError("render_workspace_missing", "The quotation workspace is unavailable.")
    storage_client = storage or SupabaseStorage(settings)
    heartbeat_job(db, job, worker_id=worker_id, progress=10, phase="resolving_assets", lease_seconds=300)
    try:
        resolved_assets = _resolve_assets(snapshot, storage_client)
    except StorageError as exc:
        raise JobProcessingError("render_asset_unavailable", "A frozen render asset is temporarily unavailable.") from exc

    context = snapshot.context
    page_profile = context.get("page_profile") or {}
    width = float(page_profile.get("width") or 0)
    height = float(page_profile.get("height") or 0)
    html = render_quotation_html(
        context.get("fields") or {},
        template_name=str(context.get("template_name") or "Risklocker Quotation"),
        template_config=context.get("template_config") or {},
        render_context={
            "current_benefits": context.get("current_benefits") or [],
            "available_addons": context.get("available_addons") or [],
        },
        resolved_assets=resolved_assets,
    )
    heartbeat_job(db, job, worker_id=worker_id, progress=45, phase="rendering_pdf", lease_seconds=300)
    with qc_temp_directory("render-") as directory:
        output = directory / "quotation.pdf"
        try:
            renderer(html, output, width=width, height=height)
        except PdfRendererUnavailable as exc:
            raise JobProcessingError("renderer_unavailable", "The PDF renderer is temporarily unavailable.") from exc
        except PdfOutputInvalid as exc:
            raise JobProcessingError("render_output_invalid", "The PDF renderer produced invalid output.") from exc
        data = output.read_bytes()
    if len(data) > int(settings.max_generated_pdf_bytes):
        raise JobProcessingError("render_output_too_large", "The generated PDF exceeds the configured output limit.")
    if not validate_pdf(data):
        raise JobProcessingError("render_output_invalid", "The PDF renderer produced invalid output.")

    heartbeat_job(db, job, worker_id=worker_id, progress=80, phase="storing_pdf", lease_seconds=300)

    # The draft row is locked only for short version allocation/finalization;
    # heavy rendering happens outside the transaction lock.
    locked_draft = db.scalar(
        select(QuotationDraft).where(QuotationDraft.id == snapshot.draft_id).with_for_update()
    ) or draft
    next_number = (
        db.scalar(select(func.max(GeneratedPdfVersion.version_number)).where(GeneratedPdfVersion.draft_id == snapshot.draft_id))
        or 0
    ) + 1
    filename = _filename(str(context.get("source_filename") or "quotation.pdf"), next_number)
    now = datetime.now(timezone.utc)
    object_key = f"generated/{now:%Y}/{now:%m}/{snapshot.draft_id}/v{next_number}-{uuid4()}.pdf"
    try:
        stored = storage_client.upload_generated_pdf(object_key, data)
    except StorageError as exc:
        raise JobProcessingError("generated_storage_unavailable", "Generated PDF storage is temporarily unavailable.") from exc

    version = GeneratedPdfVersion(
        draft_id=snapshot.draft_id,
        uploaded_file_id=job.uploaded_file_id,
        version_number=next_number,
        draft_revision=snapshot.draft_revision,
        catalog_revision_id=snapshot.catalog_revision_id,
        template_revision_id=snapshot.template_revision_id,
        idempotency_key=job.idempotency_key,
        filename=filename,
        storage_path=stored.object_key,
        storage_provider="supabase",
        storage_bucket=stored.bucket,
        storage_status=StorageStatus.AVAILABLE.value,
        storage_sha256=stored.sha256,
        storage_etag=stored.etag,
        storage_stored_at=now,
        storage_expires_at=None,
        draft_snapshot=deepcopy(context.get("fields") or {}),
        template_snapshot=deepcopy(context.get("template_config") or {}),
        render_context_snapshot=deepcopy(context),
        render_context_hash=snapshot.context_hash,
        renderer_version=snapshot.renderer_version,
        generated_by=job.owner_id,
    )
    db.add(version)
    db.flush()
    if locked_draft.revision == snapshot.draft_revision:
        locked_draft.status = RecordStatus.GENERATED.value
        if locked_draft.uploaded_file:
            locked_draft.uploaded_file.status = RecordStatus.GENERATED.value
    try:
        complete_job(db, job, worker_id, {"version_id": version.id, "version_number": next_number})
    except Exception:
        try:
            storage_client.delete_pdf(stored.object_key)
        except StorageError:
            pass
        raise
