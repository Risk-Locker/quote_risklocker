"""Hermetic tests for Asset Management: edit, delete, bulk actions, folders, and collision handling."""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault("APP_ENV", "test")

from app.core.errors import AppError
from app.models.tables import (
    Base,
    BenefitConcept,
    BusinessAsset,
    GlobalBenefitProfile,
    GlobalBenefitProfileAsset,
    InsuranceCompany,
    new_id,
)
from app.services.business_setup_service import (
    _find_collision_in_category,
    _generate_unique_label_and_filename,
    bulk_delete_business_assets,
    bulk_move_business_assets,
    delete_business_asset,
    delete_business_asset_folder,
    rename_business_asset_folder,
    replace_business_asset_file,
    update_business_asset,
    upload_business_asset,
)


@pytest.fixture
def db_session():
    """In-memory SQLite session hermetic fixture."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def make_user(role="admin") -> Any:
    return SimpleNamespace(id=str(uuid4()), role=role, email="admin@risklocker.local")


def make_png_bytes(color=(255, 0, 0), size=(32, 32)) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGBA", size, color)
    img.save(buf, format="PNG")
    return buf.getvalue()


class MockStorage:
    def __init__(self):
        self.uploaded = {}
        self.deleted = []

    def upload_asset(self, path, data, content_type):
        self.uploaded[path] = data

    def delete_pdf(self, path):
        self.deleted.append(path)
        self.uploaded.pop(path, None)


def create_asset_in_db(db: Session, label: str, category: str = "General", kind: str = "benefit_art") -> BusinessAsset:
    uid = new_id()
    asset = BusinessAsset(
        id=uid,
        asset_key=f"asset:{uid}",
        asset_kind=kind,
        category=category,
        label=label,
        original_filename=f"{label.lower().replace(' ', '_')}.png",
        content_type="image/png",
        content_hash=f"hash_{uid[:12]}",
        storage_path=f"assets/original/{uid[:2]}/{uid}.png",
        size_bytes=1024,
        width_px=32,
        height_px=32,
        has_transparency=True,
        derivative_manifest={
            "ui": {"storage_path": f"assets/derivative/ui/{uid}.png"},
            "pdf": {"storage_path": f"assets/derivative/pdf/{uid}.png"},
        },
        revision=1,
        status="active",
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def test_update_business_asset(db_session: Session):
    user = make_user("admin")
    asset = create_asset_in_db(db_session, "Towing Cover", "General", "benefit_art")

    updated = update_business_asset(
        db_session,
        user,
        asset.id,
        label="Emergency Road Assistance",
        category="Road Support",
        kind="benefit_art",
    )

    assert updated["label"] == "Emergency Road Assistance"
    assert updated["category"] == "Road Support"
    db_asset = db_session.get(BusinessAsset, asset.id)
    assert db_asset.label == "Emergency Road Assistance"
    assert db_asset.category == "Road Support"
    assert db_asset.revision == 2


def test_bulk_move_business_assets(db_session: Session):
    user = make_user("admin")
    a1 = create_asset_in_db(db_session, "Asset 1", "General")
    a2 = create_asset_in_db(db_session, "Asset 2", "General")

    res = bulk_move_business_assets(db_session, user, [a1.id, a2.id], "3D Icons")
    assert res["success"] is True
    assert res["moved_count"] == 2
    assert res["category"] == "3D Icons"

    assert db_session.get(BusinessAsset, a1.id).category == "3D Icons"
    assert db_session.get(BusinessAsset, a2.id).category == "3D Icons"


def test_delete_business_asset_with_unlinking(db_session: Session):
    user = make_user("admin")
    asset = create_asset_in_db(db_session, "Own Damage", "General")

    # Link to visual profile, concept, and company
    profile = GlobalBenefitProfile(
        id=new_id(),
        name="Test Profile",
        slug="test-profile",
        asset_category="General",
        is_active=False,
    )
    concept = BenefitConcept(
        id=new_id(),
        concept_key="own-damage",
        label="Own Damage",
        default_asset_id=asset.id,
    )
    company = InsuranceCompany(
        id=new_id(),
        name="Test Insurer",
        logo_asset_id=asset.id,
    )
    db_session.add_all([profile, concept, company])
    db_session.flush()

    binding = GlobalBenefitProfileAsset(
        id=new_id(),
        profile_id=profile.id,
        concept_id=concept.id,
        asset_id=asset.id,
    )
    db_session.add(binding)
    db_session.commit()

    # Verify links exist
    assert db_session.scalar(select(GlobalBenefitProfileAsset).where(GlobalBenefitProfileAsset.asset_id == asset.id)) is not None

    mock_storage = MockStorage()
    mock_settings = SimpleNamespace(supabase_storage_bucket="test")

    # Execute deletion
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.services.business_setup_service.SupabaseStorage", lambda s: mock_storage)
        res = delete_business_asset(db_session, mock_settings, user, asset.id)

    assert res["success"] is True
    assert db_session.get(BusinessAsset, asset.id) is None

    # Foreign key unlinking verification
    assert db_session.scalar(select(GlobalBenefitProfileAsset).where(GlobalBenefitProfileAsset.asset_id == asset.id)) is None
    db_session.refresh(concept)
    assert concept.default_asset_id is None
    db_session.refresh(company)
    assert company.logo_asset_id is None

    # Verify storage paths were purged
    assert f"assets/original/{asset.id[:2]}/{asset.id}.png" in mock_storage.deleted


def test_bulk_delete_business_assets(db_session: Session):
    user = make_user("admin")
    a1 = create_asset_in_db(db_session, "Delete Me 1", "General")
    a2 = create_asset_in_db(db_session, "Delete Me 2", "General")

    mock_storage = MockStorage()
    mock_settings = SimpleNamespace(supabase_storage_bucket="test")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.services.business_setup_service.SupabaseStorage", lambda s: mock_storage)
        res = bulk_delete_business_assets(db_session, mock_settings, user, [a1.id, a2.id])

    assert res["success"] is True
    assert res["deleted_count"] == 2
    assert db_session.get(BusinessAsset, a1.id) is None
    assert db_session.get(BusinessAsset, a2.id) is None


def test_rename_business_asset_folder(db_session: Session):
    user = make_user("admin")
    a1 = create_asset_in_db(db_session, "Icon 1", "Old Folder")
    a2 = create_asset_in_db(db_session, "Icon 2", "Old Folder")
    profile = GlobalBenefitProfile(
        id=new_id(),
        name="Profile Old",
        slug="profile-old",
        asset_category="Old Folder",
        is_active=False,
    )
    db_session.add(profile)
    db_session.commit()

    res = rename_business_asset_folder(db_session, user, "Old Folder", "New 3D Folder")
    assert res["success"] is True
    assert res["updated_assets"] == 2

    assert db_session.get(BusinessAsset, a1.id).category == "New 3D Folder"
    assert db_session.get(BusinessAsset, a2.id).category == "New 3D Folder"
    db_session.refresh(profile)
    assert profile.asset_category == "New 3D Folder"


def test_delete_business_asset_folder_move_to_general(db_session: Session):
    user = make_user("admin")
    a1 = create_asset_in_db(db_session, "Icon A", "Temp Folder")
    profile = GlobalBenefitProfile(
        id=new_id(),
        name="Profile Temp",
        slug="profile-temp",
        asset_category="Temp Folder",
        is_active=False,
    )
    db_session.add(profile)
    db_session.commit()

    mock_settings = SimpleNamespace(supabase_storage_bucket="test")
    res = delete_business_asset_folder(db_session, mock_settings, user, "Temp Folder", action="move_to_general")
    assert res["success"] is True
    assert db_session.get(BusinessAsset, a1.id).category == "General"
    db_session.refresh(profile)
    assert profile.asset_category == "General"


def test_delete_business_asset_folder_delete_all(db_session: Session):
    user = make_user("admin")
    a1 = create_asset_in_db(db_session, "Purge 1", "Purge Folder")
    mock_storage = MockStorage()
    mock_settings = SimpleNamespace(supabase_storage_bucket="test")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.services.business_setup_service.SupabaseStorage", lambda s: mock_storage)
        res = delete_business_asset_folder(db_session, mock_settings, user, "Purge Folder", action="delete_all")

    assert res["success"] is True
    assert res["deleted_assets"] == 1
    assert db_session.get(BusinessAsset, a1.id) is None


def test_collision_helper_rename(db_session: Session):
    create_asset_in_db(db_session, "Car Crash", "Vehicles")
    label, fn = _generate_unique_label_and_filename(db_session, "Vehicles", "Car Crash", "car_crash.png")
    assert label == "Car Crash (1)"
    assert fn == "car_crash (1).png"

    # Add (1) and verify (2)
    create_asset_in_db(db_session, "Car Crash (1)", "Vehicles")
    label2, fn2 = _generate_unique_label_and_filename(db_session, "Vehicles", "Car Crash", "car_crash.png")
    assert label2 == "Car Crash (2)"
    assert fn2 == "car_crash (2).png"


def test_upload_collision_replace(db_session: Session):
    user = make_user("admin")
    data1 = make_png_bytes(color=(255, 0, 0))
    data2 = make_png_bytes(color=(0, 255, 0))

    mock_storage = MockStorage()
    mock_settings = SimpleNamespace(
        max_asset_bytes=10_000_000,
        max_asset_pixels=10_000_000,
        supabase_storage_bucket="test",
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.services.business_setup_service.SupabaseStorage", lambda s: mock_storage)
        first = upload_business_asset(
            db_session,
            mock_settings,
            user,
            filename="my_icon.png",
            label="My Icon",
            kind="benefit_art",
            data=data1,
            category="Test Cat",
        )
        assert first["label"] == "My Icon"

        # Now upload with on_duplicate="replace"
        replaced = upload_business_asset(
            db_session,
            mock_settings,
            user,
            filename="my_icon.png",
            label="My Icon",
            kind="benefit_art",
            data=data2,
            category="Test Cat",
            on_duplicate="replace",
        )
        assert replaced["id"] == first["id"]
        assert replaced["label"] == "My Icon"
        db_asset = db_session.get(BusinessAsset, first["id"])
        assert db_asset.revision == 2


def test_asset_management_api_routes(monkeypatch):
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
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()
    app.dependency_overrides[current_user] = lambda: SimpleNamespace(id="admin-1", role="admin")

    c = TestClient(app)

    # 1. PATCH /api/business/assets/{id}
    monkeypatch.setattr(routes, "update_business_asset", lambda _db, _user, asset_id, **kwargs: {"id": asset_id, "label": kwargs.get("label")})
    res = c.patch("/api/business/assets/a1", json={"label": "New Label", "category": "New Cat"})
    assert res.status_code == 200
    assert res.json()["asset"]["label"] == "New Label"

    # 2. DELETE /api/business/assets/{id}
    monkeypatch.setattr(routes, "delete_business_asset", lambda _db, _s, _user, asset_id: {"success": True, "id": asset_id})
    res = c.delete("/api/business/assets/a1")
    assert res.status_code == 200
    assert res.json()["success"] is True

    # 3. POST /api/business/assets/bulk-delete
    monkeypatch.setattr(routes, "bulk_delete_business_assets", lambda _db, _s, _user, ids: {"success": True, "deleted_count": len(ids)})
    res = c.post("/api/business/assets/bulk-delete", json={"asset_ids": ["a1", "a2"]})
    assert res.status_code == 200
    assert res.json()["deleted_count"] == 2

    # 4. POST /api/business/assets/bulk-move
    monkeypatch.setattr(routes, "bulk_move_business_assets", lambda _db, _user, ids, target: {"success": True, "moved_count": len(ids), "category": target})
    res = c.post("/api/business/assets/bulk-move", json={"asset_ids": ["a1", "a2"], "target_category": "3D Folder"})
    assert res.status_code == 200
    assert res.json()["moved_count"] == 2
    assert res.json()["category"] == "3D Folder"

    # 5. PATCH /api/business/assets/folders
    monkeypatch.setattr(routes, "rename_business_asset_folder", lambda _db, _user, old, new: {"success": True, "old_category": old, "new_category": new})
    res = c.patch("/api/business/assets/folders", json={"old_name": "Old", "new_name": "New"})
    assert res.status_code == 200
    assert res.json()["new_category"] == "New"

    # 6. DELETE /api/business/assets/folders
    monkeypatch.setattr(routes, "delete_business_asset_folder", lambda _db, _s, _user, cat, **kwargs: {"success": True, "category": cat})
    res = c.request("DELETE", "/api/business/assets/folders", json={"category": "Temp", "action": "move_to_general"})
    assert res.status_code == 200
    assert res.json()["success"] is True

    # 7. POST /api/business/assets/{id}/replace-file
    monkeypatch.setattr(routes, "replace_business_asset_file", lambda _db, _s, _user, asset_id, **kwargs: {"id": asset_id, "replaced": True})
    png_bytes = make_png_bytes()
    res = c.post("/api/business/assets/a1/replace-file", files={"file": ("swap.png", png_bytes, "image/png")})
    assert res.status_code == 200
    assert res.json()["asset"]["replaced"] is True


def test_replace_business_asset_file(db_session: Session):
    user = make_user("admin")
    mock_storage = MockStorage()
    mock_settings = SimpleNamespace(
        max_asset_bytes=10_000_000,
        max_asset_pixels=10_000_000,
        supabase_storage_bucket="test",
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.services.business_setup_service.SupabaseStorage", lambda s: mock_storage)

        # 1. Create initial asset
        init_bytes = make_png_bytes(color=(255, 0, 0), size=(64, 64))
        asset_summary = upload_business_asset(
            db_session, mock_settings, user,
            filename="initial.png", label="Towing Original", kind="benefit_art", data=init_bytes, category="General",
        )
        asset_id = asset_summary["id"]
        db_asset_init = db_session.get(BusinessAsset, asset_id)
        assert db_asset_init is not None
        old_hash = db_asset_init.content_hash

        # 2. Replace with new green image
        new_bytes = make_png_bytes(color=(0, 255, 0), size=(128, 128))
        updated_summary = replace_business_asset_file(
            db_session, mock_settings, user,
            asset_id=asset_id, filename="replaced_towing.png", data=new_bytes,
        )

        assert updated_summary["id"] == asset_id
        assert updated_summary["original_filename"] == "replaced_towing.png"
        assert updated_summary["width_px"] == 128
        assert updated_summary["height_px"] == 128

        # 3. Check DB record
        db_asset = db_session.get(BusinessAsset, asset_id)
        assert db_asset is not None
        assert db_asset.content_hash != old_hash
        assert db_asset.revision == 2



