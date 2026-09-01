"""Single-file, idempotent queued upload intake."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.errors import AppError
from app.models.tables import Job
from app.services.upload_intake_service import create_queued_upload


class Upload:
    filename = "quote.pdf"
    content_type = "application/pdf"

    def __init__(self, data: bytes):
        self.data = data
        self.reads = 0

    async def read(self):
        self.reads += 1
        return self.data


class FakeDb:
    def __init__(self, scalar_values=None, commit_error: Exception | None = None):
        self.scalar_values = list(scalar_values or [])
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.commit_error = commit_error

    def scalar(self, _statement):
        return self.scalar_values.pop(0) if self.scalar_values else None

    def add(self, item):
        self.added.append(item)

    def flush(self):
        for item in self.added:
            if getattr(item, "id", None) is None:
                item.id = f"generated-{item.__class__.__name__.lower()}"

    def commit(self):
        self.commits += 1
        if self.commit_error:
            raise self.commit_error

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, _item):
        return None


def settings():
    return SimpleNamespace(max_source_pdf_bytes=20 * 1024 * 1024, max_upload_bytes=20 * 1024 * 1024)


class Storage:
    def __init__(self):
        self.uploads = []
        self.deletes = []

    def upload_pdf(self, key, data):
        self.uploads.append((key, data))
        return SimpleNamespace(
            object_key=key,
            bucket="private",
            size_bytes=len(data),
            sha256="a" * 64,
            etag="etag",
        )

    def delete_pdf(self, key):
        self.deletes.append(key)


def scan(_data, _settings):
    class Context:
        def __enter__(self):
            return Path(".qc-tmp/scanned.pdf"), {"pages": 2, "result": "clean"}

        def __exit__(self, *_args):
            return None

    return Context()


@pytest.mark.anyio
async def test_new_upload_creates_one_queued_session_transaction_and_no_expiry():
    db = FakeDb([None])
    storage = Storage()
    upload = Upload(b"%PDF-1.4 queued")

    result = await create_queued_upload(
        db,
        settings(),
        owner_id="user-1",
        upload=upload,
        idempotency_key="upload-key-1",
        enhanced_reading=False,
        storage=storage,
        quarantine=scan,
    )

    assert result.created is True
    assert result.job.state == "queued"
    assert result.job.session_id == result.session.id
    assert result.job.uploaded_file_id == result.uploaded_file.id
    assert result.uploaded_file.storage_expires_at is None
    assert result.uploaded_file.security_scan == {"pages": 2, "result": "clean"}
    assert result.uploaded_file.storage_provider == "local_ephemeral"
    assert result.draft.revision == 1
    assert result.session.draft_id == result.draft.id
    assert db.commits == 1
    # Supabase upload is DEFERRED to the worker — the request handler must not block on it.
    assert storage.uploads == [], "storage must not be touched in the request handler (deferred to worker)"
    assert storage.deletes == []


@pytest.mark.anyio
async def test_safe_retry_returns_existing_job_without_reading_or_uploading_file():
    existing = Job(
        id="job-existing",
        owner_id="user-1",
        session_id="session-existing",
        uploaded_file_id="file-existing",
        job_type="extract_pdf",
        idempotency_key="same-key",
        state="queued",
        payload={},
        result={},
        safe_error={},
        progress=0,
        attempt=0,
        max_attempts=3,
        available_at=datetime.now(timezone.utc),
    )
    db = FakeDb([existing])
    storage = Storage()
    upload = Upload(b"not even inspected")

    result = await create_queued_upload(
        db,
        settings(),
        owner_id="user-1",
        upload=upload,
        idempotency_key="same-key",
        enhanced_reading=False,
        storage=storage,
        quarantine=scan,
    )

    assert result.created is False
    assert result.job is existing
    assert result.session.id == "session-existing"
    assert upload.reads == 0
    assert storage.uploads == []


@pytest.mark.anyio
async def test_idempotency_key_owned_by_another_user_is_conflict():
    existing = SimpleNamespace(owner_id="other-user")
    with pytest.raises(AppError, match="idempotency key") as error:
        await create_queued_upload(
            FakeDb([existing]), settings(), owner_id="user-1", upload=Upload(b"%PDF"),
            idempotency_key="same-key", enhanced_reading=False, storage=Storage(), quarantine=scan,
        )
    assert error.value.status_code == 409


@pytest.mark.anyio
async def test_database_failure_rolls_back_and_reconciles_uploaded_object():
    db = FakeDb([None], commit_error=RuntimeError("database unavailable"))
    storage = Storage()

    with pytest.raises(RuntimeError, match="database unavailable"):
        await create_queued_upload(
            db, settings(), owner_id="user-1", upload=Upload(b"%PDF-1.4 queued"),
            idempotency_key="key", enhanced_reading=False, storage=storage, quarantine=scan,
        )

    assert db.rollbacks == 1
    # Supabase upload is deferred to the worker; on rollback we only delete the local ephemeral file.
    assert storage.uploads == [], "storage must not be touched in the request handler"
    assert storage.deletes == []


@pytest.mark.anyio
async def test_upload_requires_nonempty_bounded_idempotency_key():
    for key in ("", "x" * 161):
        with pytest.raises(AppError, match="Idempotency-Key"):
            await create_queued_upload(
                FakeDb(), settings(), owner_id="user-1", upload=Upload(b"%PDF"),
                idempotency_key=key, enhanced_reading=False, storage=Storage(), quarantine=scan,
            )
