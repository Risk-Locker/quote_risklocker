"""Canonical one-file upload and job-status HTTP contracts."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.api import routes
from app.api.deps import current_user, settings_dep
from app.core.errors import register_error_handlers
from app.db.session import get_db
from app.models.tables import Job
from app.services.upload_intake_service import QueuedUpload


class FakeDb:
    def __init__(self, job=None):
        self.job = job
        self.commits = 0

    def get(self, model, object_id):
        return self.job if model is Job and self.job and self.job.id == object_id else None

    def commit(self):
        self.commits += 1


def _job() -> Job:
    now = datetime.now(timezone.utc)
    return Job(
        id="job-1",
        owner_id="owner-1",
        session_id="session-1",
        uploaded_file_id="file-1",
        job_type="extract_pdf",
        idempotency_key="upload-1",
        state="queued",
        payload={},
        result={},
        safe_error={},
        progress=0,
        attempt=0,
        max_attempts=3,
        available_at=now,
        created_at=now,
        updated_at=now,
    )


def _client(db: FakeDb | None = None) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(routes.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db or FakeDb()
    app.dependency_overrides[current_user] = lambda: SimpleNamespace(id="owner-1", role="staff")
    app.dependency_overrides[settings_dep] = lambda: SimpleNamespace(max_source_pdf_bytes=20 * 1024 * 1024)
    return TestClient(app)


def test_upload_accepts_exactly_one_file_and_returns_202(monkeypatch):
    async def fake_create(_db, _settings, **kwargs):
        assert kwargs["idempotency_key"] == "upload-1"
        assert kwargs["upload"].filename == "quote.pdf"
        job = _job()
        return QueuedUpload(
            True,
            job,
            SimpleNamespace(id="session-1"),
            SimpleNamespace(id="file-1"),
            SimpleNamespace(id="draft-1"),
        )

    monkeypatch.setattr(routes, "create_queued_upload", fake_create)
    response = _client().post(
        "/api/uploads",
        headers={"Idempotency-Key": "upload-1"},
        files={"file": ("quote.pdf", b"%PDF-1.4", "application/pdf")},
    )

    assert response.status_code == 202
    assert response.json() == {
        "session_id": "session-1",
        "job_id": "job-1",
        "uploaded_file_id": "file-1",
        "created": True,
    }


def test_upload_requires_idempotency_key_before_service_call():
    response = _client().post(
        "/api/uploads",
        files={"file": ("quote.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert response.status_code == 422


def test_job_status_is_shared_with_authenticated_staff():
    response = _client(FakeDb(_job())).get("/api/jobs/job-1")
    assert response.status_code == 200
    assert response.json()["job"]["state"] == "queued"
    assert response.json()["job"]["session_id"] == "session-1"


def test_job_cancel_changes_a_nonterminal_job():
    db = FakeDb(_job())
    response = _client(db).post("/api/jobs/job-1/cancel")
    assert response.status_code == 200
    assert response.json()["job"]["state"] == "cancelled"
    assert db.commits == 1


def test_missing_job_returns_404():
    response = _client().get("/api/jobs/missing")
    assert response.status_code == 404
