"""Migrate verified legacy local PDFs to private Supabase Storage."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.enums import StorageStatus  # noqa: E402
from app.models.tables import GeneratedPdfVersion, UploadedFile  # noqa: E402
from app.services.document_security import quarantined_pdf  # noqa: E402
from app.storage.supabase import StorageError, SupabaseStorage  # noqa: E402


def safe_local_path(root: Path, relative: str) -> Path:
    resolved_root = root.resolve()
    path = (resolved_root / relative).resolve()
    if path != resolved_root and resolved_root not in path.parents:
        raise ValueError("Legacy storage path escapes the storage root.")
    return path


def source_key(record: UploadedFile, now: datetime) -> str:
    return f"source/{now:%Y}/{now:%m}/{record.batch_id}/{record.id}.pdf"


def generated_key(record: GeneratedPdfVersion, now: datetime) -> str:
    return f"generated/{now:%Y}/{now:%m}/{record.draft_id}/v{record.version_number}-{record.id}.pdf"


def migrate(cleanup_verified: bool) -> int:
    settings = get_settings()
    storage = SupabaseStorage(settings)
    storage.ensure_bucket()
    local_root = (ROOT / "storage").resolve()
    migrated = 0
    missing: list[str] = []
    failed: list[str] = []
    referenced: set[Path] = set()

    with SessionLocal() as db:
        uploads = list(db.scalars(select(UploadedFile).where(UploadedFile.storage_provider == "local")).all())
        versions = list(db.scalars(select(GeneratedPdfVersion).where(GeneratedPdfVersion.storage_provider == "local")).all())
        records = [("source", item) for item in uploads] + [("generated", item) for item in versions]
        for kind, record in records:
            try:
                local_path = safe_local_path(local_root, record.storage_path)
                referenced.add(local_path)
                if not local_path.is_file():
                    missing.append(f"{kind}:{record.id}:{record.storage_path}")
                    continue
                data = local_path.read_bytes()
                if len(data) > settings.max_upload_bytes:
                    raise ValueError("PDF exceeds MAX_UPLOAD_BYTES")
                now = datetime.now(timezone.utc)
                with quarantined_pdf(data, settings) as (_, scan):
                    key = source_key(record, now) if kind == "source" else generated_key(record, now)
                    stored = storage.upload_pdf(key, data)
                downloaded = storage.download_bytes(stored.object_key)
                if len(downloaded) != len(data) or sha256(downloaded).hexdigest() != stored.sha256:
                    storage.delete_pdf(stored.object_key)
                    raise ValueError("Supabase checksum verification failed")

                record.storage_path = stored.object_key
                record.storage_provider = "supabase"
                record.storage_bucket = stored.bucket
                record.storage_status = StorageStatus.AVAILABLE.value
                record.storage_sha256 = stored.sha256
                record.storage_etag = stored.etag
                record.storage_stored_at = now
                record.storage_expires_at = now + timedelta(days=settings.pdf_retention_days)
                if kind == "source":
                    record.security_scan = {**(record.security_scan or {}), **scan, "migrated_from_local": True}
                db.commit()
                migrated += 1
                print(f"Migrated {kind} PDF {record.id}.")
                if cleanup_verified:
                    local_path.unlink()
            except (OSError, ValueError, StorageError) as exc:
                db.rollback()
                failed.append(f"{kind}:{record.id}:{exc}")

    local_files = set(local_root.rglob("*.pdf")) if local_root.exists() else set()
    orphaned = sorted(str(path.relative_to(local_root)) for path in local_files - referenced)
    print(f"Summary: migrated={migrated}, missing={len(missing)}, failed={len(failed)}, orphaned={len(orphaned)}")
    for item in missing:
        print(f"Missing: {item}")
    for item in failed:
        print(f"Failed: {item}")
    for item in orphaned:
        print(f"Orphaned: {item}")
    return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cleanup-verified",
        action="store_true",
        help="Delete each local PDF only after upload and checksum verification succeed.",
    )
    args = parser.parse_args()
    raise SystemExit(migrate(args.cleanup_verified))
