"""Resolve private PDF bytes without exposing provider object URLs."""

from __future__ import annotations

from hashlib import sha256

from app.core.config import Settings
from app.core.errors import AppError
from app.models.enums import StorageStatus
from app.storage.supabase import StorageError, StorageNotFound, SupabaseStorage


ACTIVE_STORAGE_STATUSES = {
    StorageStatus.AVAILABLE.value,
    StorageStatus.ARCHIVE_PENDING.value,
    StorageStatus.ARCHIVE_FAILED.value,
}


def load_pdf_bytes(record, settings: Settings) -> bytes:
    supabase_available = (
        record.storage_provider == "supabase"
        and record.storage_status in ACTIVE_STORAGE_STATUSES
    )
    if supabase_available:
        try:
            data = SupabaseStorage(settings).download_bytes(record.storage_path)
        except StorageNotFound:
            raise AppError("PDF Expired", 410) from None
        except StorageError as exc:
            raise AppError("PDF storage is temporarily unavailable.", 503) from exc
        if record.storage_sha256 and sha256(data).hexdigest() != record.storage_sha256:
            raise AppError("PDF integrity verification failed.", 503)
        return data

    if record.storage_provider == "local_ephemeral":
        import os
        from pathlib import Path
        if not os.path.exists(record.storage_path):
            raise AppError("PDF Ephemeral File Expired", 410)
        data = Path(record.storage_path).read_bytes()
        if record.storage_sha256 and sha256(data).hexdigest() != record.storage_sha256:
            raise AppError("PDF integrity verification failed.", 503)
        # For zero-persistence, we delete the PDF once it's downloaded by the user
        Path(record.storage_path).unlink(missing_ok=True)
        return data

    if record.archive_status == StorageStatus.ARCHIVED.value and record.archive_item_id:
        raise AppError("The permanent archive is not available in this deployment.", 503)
    raise AppError("PDF Expired", 410)


def parse_byte_range(value: str | None, total: int) -> tuple[int, int] | None:
    if not value:
        return None
    if not value.startswith("bytes=") or "," in value:
        raise AppError("Requested PDF range is not supported.", 416)
    spec = value[6:].strip()
    start_text, separator, end_text = spec.partition("-")
    if not separator:
        raise AppError("Requested PDF range is not supported.", 416)
    try:
        if start_text:
            start = int(start_text)
            end = int(end_text) if end_text else total - 1
        else:
            suffix = int(end_text)
            if suffix <= 0:
                raise ValueError
            start = max(0, total - suffix)
            end = total - 1
    except ValueError:
        raise AppError("Requested PDF range is not supported.", 416) from None
    if start < 0 or start >= total or end < start:
        raise AppError("Requested PDF range is not available.", 416)
    return start, min(end, total - 1)
