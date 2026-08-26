"""The final session step is the only canonical PDF generation surface."""

from __future__ import annotations

import os
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
os.environ.setdefault("APP_ENV", "test")

from app.api import routes  # noqa: E402
from app.api.deps import current_user, settings_dep  # noqa: E402
from app.core.errors import register_error_handlers  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.models.tables import GeneratedPdfVersion, Job  # noqa: E402


NOW = datetime.now(timezone.utc)


class FakeDb:
    def __init__(self, version=None): self.version = version
    def scalar(self, _query): return self.version


def client(db=None):
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(routes.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db or FakeDb()
    app.dependency_overrides[current_user] = lambda: SimpleNamespace(id="staff-1", role="staff")
    app.dependency_overrides[settings_dep] = lambda: SimpleNamespace()
    return TestClient(app)


def job():
    return Job(
        id="job-1", owner_id="staff-1", session_id="session-1", uploaded_file_id="file-1",
        job_type="render_pdf", idempotency_key="gen-1", state="queued", payload={}, result={}, safe_error={},
        progress=0, attempt=0, max_attempts=3, available_at=NOW, created_at=NOW, updated_at=NOW,
    )


def test_final_step_generation_requires_exact_revision_and_key_and_returns_202(monkeypatch):
    called = {}
    monkeypatch.setattr(routes, "request_version_generation", lambda _db, user, session_id, **kwargs: (
        called.update(user=user.id, session_id=session_id, **kwargs) or {"created": True, "job": job(), "version": None}
    ))
    response = client().post(
        "/api/sessions/session-1/versions",
        headers={"Idempotency-Key": "gen-1"},
        json={"draft_revision": 7},
    )
    assert response.status_code == 202
    assert response.json()["job"]["id"] == "job-1"
    assert called == {"user": "staff-1", "session_id": "session-1", "draft_revision": 7, "idempotency_key": "gen-1"}
    # Omitting Idempotency-Key is now tolerated — backend auto-generates one
    assert client().post("/api/sessions/session-1/versions", json={"draft_revision": 7}).status_code == 202


def test_idempotent_completed_request_returns_existing_version_without_new_job(monkeypatch):
    version = SimpleNamespace(id="version-1", version_number=3, draft_revision=7)
    monkeypatch.setattr(routes, "request_version_generation", lambda *_args, **_kwargs: {"created": False, "job": None, "version": version})
    response = client().post(
        "/api/sessions/session-1/versions",
        headers={"Idempotency-Key": "gen-1"},
        json={"draft_revision": 7},
    )
    assert response.status_code == 200
    assert response.json() == {"created": False, "version": {"id": "version-1", "version_number": 3, "draft_revision": 7}}


def test_download_alias_authorizes_and_streams_without_generation(monkeypatch):
    draft = SimpleNamespace(owner_id="someone")
    version = SimpleNamespace(id="version-1", draft=draft, filename="quote.pdf")
    monkeypatch.setattr(routes, "load_pdf_bytes", lambda record, _settings: b"%PDF-1.7\nbytes\n%%EOF")
    response = client(FakeDb(version)).get("/api/versions/version-1/pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_legacy_generate_and_preview_routes_are_disabled():
    assert client().post("/api/drafts/draft-1/generate", json={}).status_code == 410
    assert client().post("/api/drafts/draft-1/preview-png").status_code == 410
