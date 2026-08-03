"""Regression tests for template-asset route and public settings limits."""

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
        "DATABASE_PROVIDER": "supabase_postgres",
        "DATABASE_URL": "postgresql://postgres:password@db.test.supabase.co:5432/postgres",
        "AUTH_HASH_SECRET": "test-auth-hash-secret-that-is-long-enough",
        "STORAGE_DRIVER": "supabase",
        "SUPABASE_URL": "https://project-ref.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
    }
)

from app.api import routes
from app.api.deps import current_user, settings_dep
from app.core.errors import register_error_handlers
from app.db.session import get_db
from app.models.tables import User


def auth_settings():
    return SimpleNamespace(
        app_env="test",
        cors_origins=("http://localhost:3000",),
        session_cookie_name="risklocker_session",
        session_cookie_secure=False,
        session_idle_hours=8,
        session_max_days=30,
        auth_hash_secret="test-auth-hash-secret-that-is-long-enough",
        max_upload_files=25,
        max_upload_bytes=1024 * 1024,
        trash_retention_days=14,
    )


def _admin_user() -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=str(uuid4()),
        email="admin@risklocker.com",
        password_hash="",
        role="admin",
        status="active",
        created_at=now,
        updated_at=now,
    )


class FakeDb:
    def scalar(self, _statement):
        return None

    def scalars(self, _statement):
        class Empty:
            def all(self):
                return []
        return Empty()

    def get(self, _model, _object_id):
        return None


def _http_client(*, user: User | None = None):
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(routes.router)
    app.dependency_overrides[get_db] = lambda: FakeDb()
    app.dependency_overrides[settings_dep] = auth_settings
    if user:
        app.dependency_overrides[current_user] = lambda: user
    return TestClient(app)


def test_template_asset_file_accepts_path_response(monkeypatch, tmp_path):
    asset_file = tmp_path / "logo.png"
    asset_file.write_bytes(b"fake-image-data")

    def fake_resolve(_db, asset_id):
        if asset_id == "logo-asset":
            return Path(asset_file)
        raise FileNotFoundError()

    monkeypatch.setattr(routes, "resolve_template_asset", fake_resolve)
    client = _http_client(user=_admin_user())

    response = client.get("/template-assets/logo-asset")

    assert response.status_code == 200
    assert response.content == b"fake-image-data"


def test_template_asset_file_returns_404_for_missing_file(monkeypatch):
    monkeypatch.setattr(
        routes, "resolve_template_asset", lambda _db, _asset_id: (_ for _ in ()).throw(FileNotFoundError())
    )
    client = _http_client(user=_admin_user())

    response = client.get("/template-assets/missing")

    assert response.status_code == 404
    assert "File not found" in response.json()["error"]["message"]


def test_settings_limits_returns_backend_values():
    client = _http_client(user=_admin_user())

    response = client.get("/settings/limits")

    assert response.status_code == 200
    data = response.json()
    assert data["max_upload_files"] == 25
    assert data["max_upload_bytes"] == 1024 * 1024


def test_trash_includes_retention_days(monkeypatch):
    monkeypatch.setattr(routes, "list_trash", lambda _db, _user: [])
    client = _http_client(user=_admin_user())

    response = client.get("/trash")

    assert response.status_code == 200
    assert response.json()["retention_days"] == 14
