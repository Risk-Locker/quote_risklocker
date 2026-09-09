"""Tests for bulk upload limit settings and retrieval."""

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
        "GEMINI_API_KEY": "fake-gemini-key",
    }
)

from app.api import routes
from app.api.deps import current_user, settings_dep
from app.core.errors import register_error_handlers
from app.db.session import get_db
from app.models.tables import AppSetting, User
from app.services.admin_service import get_bulk_upload_limit, set_bulk_upload_limit


def auth_settings():
    return SimpleNamespace(
        app_env="test",
        cors_origins=("http://localhost:3000",),
        session_cookie_name="risklocker_session",
        session_cookie_secure=False,
        session_idle_hours=8,
        session_max_days=30,
        auth_hash_secret="test-auth-hash-secret-that-is-long-enough",
        max_upload_files=1,
        max_upload_bytes=1024 * 1024,
        max_source_pdf_bytes=20 * 1024 * 1024,
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


def _staff_user() -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=str(uuid4()),
        email="staff@risklocker.com",
        password_hash="",
        role="staff",
        status="active",
        created_at=now,
        updated_at=now,
    )


class MemoryDb:
    def __init__(self):
        self.store = {}

    def get(self, model, key):
        if model is AppSetting:
            return self.store.get(key)
        return None

    def add(self, obj):
        if isinstance(obj, AppSetting):
            self.store[obj.key] = obj

    def commit(self):
        pass

    def refresh(self, _obj):
        pass


def _http_client(*, user: User | None = None, db: MemoryDb | None = None):
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(routes.router)
    memory_db = db or MemoryDb()
    app.dependency_overrides[get_db] = lambda: memory_db
    app.dependency_overrides[settings_dep] = auth_settings
    if user:
        app.dependency_overrides[current_user] = lambda: user
    return TestClient(app)


def test_bulk_upload_limit_default():
    db = MemoryDb()
    assert get_bulk_upload_limit(db) == 5


def test_bulk_upload_limit_set_and_get():
    db = MemoryDb()
    user = _admin_user()
    set_bulk_upload_limit(db, user, 8)
    assert get_bulk_upload_limit(db) == 8


def test_bulk_upload_limit_minimum_validation():
    db = MemoryDb()
    user = _admin_user()
    with pytest.raises(Exception) as exc_info:
        set_bulk_upload_limit(db, user, 2)
    assert "cannot be less than 3" in str(exc_info.value)


def test_get_settings_limits_includes_max_bulk_upload_files():
    db = MemoryDb()
    client = _http_client(user=_admin_user(), db=db)
    res = client.get("/settings/limits")
    assert res.status_code == 200
    data = res.json()
    assert data["max_upload_files"] == 1
    assert data["max_bulk_upload_files"] == 5


def test_admin_upload_limits_endpoints():
    db = MemoryDb()
    admin_client = _http_client(user=_admin_user(), db=db)

    # GET default
    res = admin_client.get("/admin/settings/upload-limits")
    assert res.status_code == 200
    assert res.json()["max_bulk_upload_files"] == 5
    assert res.json()["min_allowed"] == 3

    # POST valid update (e.g. 8)
    res = admin_client.post("/admin/settings/upload-limits", json={"max_bulk_upload_files": 8})
    assert res.status_code == 200
    assert res.json()["max_bulk_upload_files"] == 8

    # Verify reflected in /settings/limits
    res = admin_client.get("/settings/limits")
    assert res.status_code == 200
    assert res.json()["max_bulk_upload_files"] == 8

    # POST invalid update (< 3)
    res = admin_client.post("/admin/settings/upload-limits", json={"max_bulk_upload_files": 2})
    assert res.status_code == 400
    assert "cannot be less than 3" in res.json()["error"]["message"]


def test_staff_cannot_change_upload_limits():
    db = MemoryDb()
    staff_client = _http_client(user=_staff_user(), db=db)

    res = staff_client.post("/admin/settings/upload-limits", json={"max_bulk_upload_files": 6})
    assert res.status_code == 403
