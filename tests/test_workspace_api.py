"""HTTP surface for canonical workspace snapshots and optimistic patches."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.api import routes
from app.api.deps import current_user
from app.core.errors import register_error_handlers
from app.db.session import get_db


def client():
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(routes.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()
    app.dependency_overrides[current_user] = lambda: SimpleNamespace(id="staff-1", role="staff")
    return TestClient(app)


def test_workspace_get_calls_canonical_service(monkeypatch):
    monkeypatch.setattr(routes, "build_workspace_snapshot", lambda _db, user, session_id: {
        "session_id": session_id, "revision": 7, "capabilities": {"can_edit_fields": user.role == "staff"}
    })
    response = client().get("/api/sessions/session-1/workspace")
    assert response.status_code == 200
    assert response.json()["workspace"]["revision"] == 7


def test_workspace_patch_requires_revision_and_dirty_operations(monkeypatch):
    called = {}

    def apply(_db, user, draft_id, *, base_revision, operations):
        called.update(user=user.id, draft_id=draft_id, base_revision=base_revision, operations=operations)
        return {"draft_id": draft_id, "revision": base_revision + 1}

    monkeypatch.setattr(routes, "apply_workspace_patch", apply)
    response = client().patch("/api/drafts/draft-1/workspace", json={
        "base_revision": 4,
        "operations": [{"op": "scalar_decision", "field": "customer_name", "decision": "confirm"}],
    })
    assert response.status_code == 200
    assert response.json()["workspace"]["revision"] == 5
    assert called["operations"][0]["field"] == "customer_name"

    assert client().patch("/api/drafts/draft-1/workspace", json={"operations": []}).status_code == 422
    assert client().patch("/api/drafts/draft-1/workspace", json={"base_revision": 4, "operations": []}).status_code == 422
