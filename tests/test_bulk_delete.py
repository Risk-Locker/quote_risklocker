"""HTTP tests for bulk delete endpoints."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": "postgresql://postgres:password@db.test.supabase.co:5432/postgres",
        "AUTH_HASH_SECRET": "test-auth-hash-secret-that-is-long-enough",
        "SUPABASE_URL": "https://project-ref.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
    }
)

from app.api import routes  # noqa: E402
from app.api.deps import current_user, settings_dep  # noqa: E402
from app.core.errors import AppError, register_error_handlers  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.models.tables import User  # noqa: E402
from app.models.enums import AccountStatus  # noqa: E402


def _settings():
    return SimpleNamespace(
        app_env="test",
        cors_origins=("http://localhost:3000",),
        session_cookie_name="risklocker_session",
        session_cookie_secure=False,
        session_idle_hours=8,
        session_max_days=30,
        auth_hash_secret="test-auth-hash-secret-that-is-long-enough",
        trash_retention_days=14,
    )


def _admin_user() -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=str(uuid4()),
        email="admin@risklocker.com",
        password_hash="",
        role="admin",
        status=AccountStatus.ACTIVE.value,
        created_at=now,
        updated_at=now,
    )


class FakeDb:
    def get(self, _model, _object_id):
        return None

    def add(self, _value):
        return None

    def commit(self):
        return None


def _http_client(db: FakeDb):
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(routes.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[settings_dep] = _settings
    app.dependency_overrides[current_user] = lambda: _admin_user()
    return TestClient(app)


def test_bulk_delete_client_records_calls_service_per_id(monkeypatch):
    from app.services import trash_service

    seen: list[str] = []
    monkeypatch.setattr(trash_service, "delete_client_record", lambda db, settings, user, record_id: seen.append(record_id))
    client = _http_client(FakeDb())

    response = client.post("/client-records/bulk-delete", json={"record_ids": ["a", "b", "c"]})

    assert response.status_code == 200
    assert response.json()["deleted"] == ["a", "b", "c"]
    assert response.json()["failed"] == []
    assert seen == ["a", "b", "c"]


def test_bulk_delete_client_records_continues_on_failure(monkeypatch):
    from app.services import trash_service

    def flaky(_db, _settings, _user, record_id: str):
        if record_id == "bad":
            raise AppError("Record not found.", 404)
        return None

    monkeypatch.setattr(trash_service, "delete_client_record", flaky)
    client = _http_client(FakeDb())

    response = client.post("/client-records/bulk-delete", json={"record_ids": ["ok", "bad"]})

    assert response.status_code == 200
    assert response.json()["deleted"] == ["ok"]
    assert len(response.json()["failed"]) == 1
    assert response.json()["failed"][0]["id"] == "bad"


def test_bulk_delete_records_moves_each_to_trash(monkeypatch):
    from app.services import trash_service

    seen: list[str] = []
    monkeypatch.setattr(routes, "move_to_trash", lambda db, settings, user, uploaded_file_id: seen.append(uploaded_file_id))
    client = _http_client(FakeDb())

    response = client.post("/records/bulk-delete", json={"uploaded_file_ids": ["f1", "f2"]})

    assert response.status_code == 200
    assert response.json()["deleted"] == ["f1", "f2"]
    assert seen == ["f1", "f2"]
