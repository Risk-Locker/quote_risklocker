"""Authoritative preview uses the same immutable render context as PDF output."""

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


def client():
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(routes.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()
    app.dependency_overrides[current_user] = lambda: SimpleNamespace(id="staff-1", role="staff")
    app.dependency_overrides[settings_dep] = lambda: SimpleNamespace()
    return TestClient(app)


def test_preview_request_requires_exact_saved_revision_and_returns_cached_url(monkeypatch):
    snapshot = SimpleNamespace(id="snapshot-1", context_hash="a" * 64)
    monkeypatch.setattr(routes, "request_preview_render", lambda _db, user, session_id, **kwargs: (
        snapshot if user.role == "staff" and session_id == "session-1" and kwargs["draft_revision"] == 7 else None
    ))
    response = client().post("/api/sessions/session-1/preview-render", json={"draft_revision": 7})
    assert response.status_code == 200
    assert response.json() == {
        "preview_id": "snapshot-1", "context_hash": "a" * 64,
        "preview_url": "/previews/snapshot-1/html",
    }


def test_preview_html_is_private_scriptless_and_rendered_from_frozen_snapshot(monkeypatch):
    monkeypatch.setattr(routes, "render_snapshot_preview_html", lambda *_args, **_kwargs: "<!doctype html><main>Frozen preview</main>")
    response = client().get("/api/previews/snapshot-1/html")
    assert response.status_code == 200
    assert "Frozen preview" in response.text
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["content-security-policy"] == "default-src 'none'; img-src data:; style-src 'unsafe-inline'"
