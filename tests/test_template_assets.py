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

    def add(self, _obj):
        return None

    def commit(self):
        return None

    def refresh(self, _obj):
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
    assert data["max_upload_files"] == 1
    assert data["max_upload_bytes"] == 1024 * 1024
    assert data["max_source_pdf_bytes"] == 20 * 1024 * 1024


def test_trash_includes_retention_days(monkeypatch):
    from app.services import trash_service

    monkeypatch.setattr(
        trash_service,
        "list_trash_categorized",
        lambda _db, _user, retention_days: {"retention_days": retention_days, "sessions": [], "templates": [], "our_specials": [], "our_special_variants": [], "client_records": []},
    )
    client = _http_client(user=_admin_user())

    response = client.get("/trash")

    assert response.status_code == 200
    assert response.json()["retention_days"] == 14


def test_sanitize_folder_defaults_and_cleans():
    from app.services.template_assets import FOLDER_DEFAULT, sanitize_folder

    assert sanitize_folder(None) == FOLDER_DEFAULT
    assert sanitize_folder("") == FOLDER_DEFAULT
    assert sanitize_folder("   ") == FOLDER_DEFAULT
    assert sanitize_folder("  Stickers & Symbols!! ") == "Stickers Symbols"
    assert sanitize_folder("Logo/Backup") == "LogoBackup"
    assert len(sanitize_folder("x" * 200)) <= 60


def test_upload_template_asset_stores_into_folder_path(monkeypatch):
    from app.services import template_assets as ta

    captured: dict = {}

    class FakeStored:
        provider = "supabase"
        bucket = "bucket"
        object_key = None
        sha256 = "abc123"

    class FakeStorage:
        def upload_asset(self, path, _data, _mime):
            captured["path"] = path
            stored = FakeStored()
            stored.object_key = path
            return stored

    monkeypatch.setattr(ta, "SupabaseStorage", lambda _settings: FakeStorage())

    record = ta.upload_template_asset(
        FakeDb(),
        SimpleNamespace(),
        _admin_user(),
        filename="sticker.png",
        content_type="image/png",
        data=b"\x89PNG\r\n\x1a\nfake",
        label="Sticker",
        folder="Stickers",
    )

    assert captured["path"] == f"template-assets/Stickers/{record.id}.png"
    assert record.folder == "Stickers"
    assert record.storage_path.startswith("template-assets/Stickers/")


def test_upload_route_accepts_folder_and_returns_it(monkeypatch):
    fake_record = SimpleNamespace(
        id="asset-1",
        label="Sticker",
        filename="sticker.png",
        folder="Symbols",
        size_bytes=9,
    )
    monkeypatch.setattr(routes, "upload_template_asset", lambda *_args, **_kwargs: fake_record)
    client = _http_client(user=_admin_user())

    response = client.post(
        "/admin/template-assets",
        files={"file": ("sticker.png", b"\x89PNG\r\n\x1a\nfake", "image/png")},
        data={"label": "Sticker", "folder": "Symbols"},
    )

    assert response.status_code == 200
    assert response.json()["asset"]["folder"] == "Symbols"


def test_upload_route_defaults_folder_when_omitted(monkeypatch):
    from app.services.template_assets import FOLDER_DEFAULT

    fake_record = SimpleNamespace(
        id="asset-2",
        label="Sticker",
        filename="sticker.png",
        folder=FOLDER_DEFAULT,
        size_bytes=9,
    )
    monkeypatch.setattr(routes, "upload_template_asset", lambda *_args, **_kwargs: fake_record)
    client = _http_client(user=_admin_user())

    response = client.post(
        "/admin/template-assets",
        files={"file": ("sticker.png", b"\x89PNG\r\n\x1a\nfake", "image/png")},
        data={"label": "Sticker"},
    )

    assert response.status_code == 200
    assert response.json()["asset"]["folder"] == FOLDER_DEFAULT


def test_list_assets_includes_folder(monkeypatch):
    from app.services import template_assets as ta

    fake_uploaded = SimpleNamespace(
        id="asset-3",
        label="Sticker",
        filename="sticker.png",
        size_bytes=9,
        status="active",
        created_at=None,
        folder="Stickers",
    )
    monkeypatch.setattr(ta, "_local_assets", lambda: [])
    monkeypatch.setattr(
        ta,
        "_uploaded_assets",
        lambda _db: [
            {
                "id": fake_uploaded.id,
                "label": fake_uploaded.label,
                "filename": fake_uploaded.filename,
                "extension": ".png",
                "url": f"/template-assets/{fake_uploaded.id}",
                "size_bytes": fake_uploaded.size_bytes,
                "source": "uploaded",
                "folder": fake_uploaded.folder,
            }
        ],
    )

    assets = ta.list_template_assets(FakeDb())

    assert assets == [
        {
            "id": "asset-3",
            "label": "Sticker",
            "filename": "sticker.png",
            "extension": ".png",
            "url": "/template-assets/asset-3",
            "size_bytes": 9,
            "source": "uploaded",
            "folder": "Stickers",
        }
    ]


def test_active_asset_library_never_lists_legacy_local_assets(monkeypatch):
    from app.services import template_assets as ta

    monkeypatch.setattr(
        ta,
        "_local_assets",
        lambda: [{"id": "legacy", "source": "local", "folder": "Local"}],
    )
    monkeypatch.setattr(ta, "_uploaded_assets", lambda _db: [])

    assert ta.list_template_assets(FakeDb()) == []
