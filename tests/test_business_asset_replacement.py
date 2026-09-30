"""Hermetic tests for business asset replacement and cache invalidation headers."""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault("APP_ENV", "test")

from app.models.tables import Base, BusinessAsset, new_id
from app.services.business_asset_service import (
    replace_business_asset_file,
    upload_business_asset,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def make_png_bytes(color=(255, 0, 0), size=(64, 64)) -> bytes:
    img = Image.new("RGBA", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class MockStorage:
    def __init__(self):
        self.storage: dict[str, bytes] = {}

    def upload_asset(self, path: str, data: bytes, content_type: str = "image/png") -> str:
        self.storage[path] = data
        return path

    def download_bytes(self, path: str) -> bytes:
        if path not in self.storage:
            raise Exception("NotFound")
        return self.storage[path]

    def delete_pdf(self, path: str) -> None:
        self.storage.pop(path, None)


def test_replace_business_asset_file_cache_busting(db_session: Session):
    user = SimpleNamespace(id="admin-1", role="admin")
    mock_storage = MockStorage()
    mock_settings = SimpleNamespace(
        max_asset_bytes=10_000_000,
        max_asset_pixels=10_000_000,
        supabase_storage_bucket="test",
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.services.business_asset_service.SupabaseStorage", lambda s: mock_storage)

        # 1. Upload initial
        data1 = make_png_bytes(color=(255, 0, 0), size=(32, 32))
        res1 = upload_business_asset(
            db_session, mock_settings, user,
            filename="towing.png", label="Towing", kind="benefit_art", data=data1, category="General",
        )
        assert res1["revision"] == 1
        assert "v=1" in res1["url"]
        asset_id = res1["id"]

        # 2. Replace file
        data2 = make_png_bytes(color=(0, 255, 0), size=(64, 64))
        res2 = replace_business_asset_file(
            db_session, mock_settings, user,
            asset_id=asset_id, filename="new_towing.png", data=data2,
        )
        assert res2["id"] == asset_id
        assert res2["revision"] == 2
        assert "v=2" in res2["url"]
        assert res2["width_px"] == 64

        # DB entity verification
        asset = db_session.get(BusinessAsset, asset_id)
        assert asset is not None
        assert asset.revision == 2
        assert asset.content_hash == res2["content_hash"]


def test_business_asset_content_headers(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api import routes
    from app.api.deps import current_user
    from app.core.config import get_settings
    from app.core.errors import register_error_handlers
    from app.db.session import get_db

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(routes.router, prefix="/api")

    mock_asset = BusinessAsset(
        id="asset-test-1",
        label="Test Icon",
        original_filename="icon.png",
        content_type="image/png",
        content_hash="hash12345678",
        storage_path="assets/original/hash12345678.png",
        category="General",
        asset_kind="benefit_art",
        revision=3,
        status="active",
        derivative_manifest={
            "ui": {
                "storage_path": "assets/derivative/ui/hash_ui.webp",
                "content_type": "image/webp",
                "content_hash": "hash_ui",
            }
        },
    )

    class MockDb:
        def get(self, model, ident):
            if ident == "asset-test-1":
                return mock_asset
            return None

    app.dependency_overrides[get_db] = lambda: MockDb()
    app.dependency_overrides[current_user] = lambda: SimpleNamespace(id="admin-1", role="admin")

    monkeypatch.setattr("app.api.routers.templates._get_cached_asset_bytes", lambda p, s: b"fake_bytes")

    client = TestClient(app)

    # 1. With version query parameter => immutable caching
    res_versioned = client.get("/api/business/assets/asset-test-1/content?profile=ui&v=3")
    assert res_versioned.status_code == 200
    assert "immutable" in res_versioned.headers.get("cache-control", "")
    assert res_versioned.headers.get("etag") == '"hash_ui"'

    # 2. Without version query parameter => no-cache (must revalidate)
    res_bare = client.get("/api/business/assets/asset-test-1/content?profile=ui")
    assert res_bare.status_code == 200
    assert "no-cache" in res_bare.headers.get("cache-control", "")
    assert "immutable" not in res_bare.headers.get("cache-control", "")

    # 3. Conditional request matching ETag => 304 Not Modified
    res_304 = client.get(
        "/api/business/assets/asset-test-1/content?profile=ui",
        headers={"if-none-match": '"hash_ui"'},
    )
    assert res_304.status_code == 304
