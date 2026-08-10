"""HTTP and service tests for Our Specials CRUD endpoints."""

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
from app.models.tables import OurSpecial, OurSpecialVariant, User
from app.models.enums import AccountStatus, InsuranceType
from app.services.admin_service import delete_special, delete_variant, upsert_special, upsert_variant
from app.core.errors import AppError


def auth_settings():
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


def _staff_user() -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=str(uuid4()),
        email="staff@risklocker.com",
        password_hash="",
        role="staff",
        status=AccountStatus.ACTIVE.value,
        created_at=now,
        updated_at=now,
    )


def _make_special(**overrides) -> OurSpecial:
    defaults = {
        "id": str(uuid4()),
        "label": "Windscreen",
        "category": "FOC",
        "status": AccountStatus.ACTIVE.value,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    special = OurSpecial(**defaults)
    special.variants = []
    return special


def _make_variant(special_id: str, **overrides) -> OurSpecialVariant:
    defaults = {
        "id": str(uuid4()),
        "special_id": special_id,
        "label": "Windscreen Coverage",
        "secondary_label": None,
        "value_text": "Up to RM 1,000",
        "icon_asset_id": None,
        "shape": None,
        "bg_color": None,
        "text_color": None,
        "border_width": None,
        "border_color": None,
        "shadow": None,
        "status": AccountStatus.ACTIVE.value,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return OurSpecialVariant(**defaults)


class FakeDb:
    def __init__(self, user: User | None = None, specials: list[OurSpecial] | None = None, variants: list[OurSpecialVariant] | None = None):
        self._user = user
        self._specials = specials or []
        self._variants = variants or []
        self.added: list = []
        self.deleted: list = []
        self.commits = 0

    def scalars(self, statement):
        from sqlalchemy import select as _select
        return _ScalarResult(self._specials)

    def get(self, model, object_id):
        sid = str(object_id)
        if model is User and self._user:
            return self._user if str(self._user.id) == sid else None
        if model is OurSpecial:
            for s in self._specials:
                if str(s.id) == sid:
                    return s
            return None
        if model is OurSpecialVariant:
            for v in self._variants:
                if str(v.id) == sid:
                    return v
            return None
        return None

    def add(self, value):
        self.added.append(value)
        if isinstance(value, OurSpecial):
            self._specials.append(value)
        elif isinstance(value, OurSpecialVariant):
            self._variants.append(value)

    def delete(self, value):
        self.deleted.append(value)
        if isinstance(value, OurSpecial) and value in self._specials:
            self._specials.remove(value)
        elif isinstance(value, OurSpecialVariant) and value in self._variants:
            self._variants.remove(value)

    def commit(self):
        self.commits += 1

    def refresh(self, _value):
        pass


class _ScalarResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)

    def unique(self):
        return self


def _http_client(*, user: User | None = None, specials=None, variants=None):
    db = FakeDb(user=user, specials=specials, variants=variants)
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(routes.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[settings_dep] = auth_settings
    if user:
        app.dependency_overrides[current_user] = lambda: user
    return TestClient(app)


class TestOurSpecialsRoutesHttp:
    """HTTP tests for /admin/our-specials and variant endpoints."""

    def test_get_our_specials_returns_list(self, monkeypatch):
        special = _make_special(id="a", label="Windscreen", category="FOC")
        special.variants = [_make_variant("a", id="v1", label="Windscreen Coverage")]
        user = _admin_user()
        client = _http_client(user=user, specials=[special])

        response = client.get("/admin/our-specials")

        assert response.status_code == 200
        data = response.json()
        assert len(data["our_specials"]) == 1
        s = data["our_specials"][0]
        assert s["label"] == "Windscreen"
        assert s["category"] == "FOC"
        assert len(s["variants"]) == 1
        assert s["variants"][0]["label"] == "Windscreen Coverage"

    def test_post_create_special(self, monkeypatch):
        user = _admin_user()
        client = _http_client(user=user)

        response = client.post(
            "/admin/our-specials",
            json={"label": "Towing", "category": "FOC"},
        )

        assert response.status_code == 200
        s = response.json()["our_special"]
        assert s["label"] == "Towing"
        assert s["category"] == "FOC"
        assert s["variants"] == []

    def test_delete_special(self, monkeypatch):
        special = _make_special(id="a", label="Windscreen")
        user = _admin_user()
        client = _http_client(user=user, specials=[special])

        response = client.delete("/admin/our-specials/a")

        assert response.status_code == 200
        assert response.json()["deleted"] is True

    def test_delete_special_returns_404(self, monkeypatch):
        user = _admin_user()
        client = _http_client(user=user)

        response = client.delete("/admin/our-specials/nonexistent")

        assert response.status_code == 404

    def test_post_create_special_rejects_non_admin(self, monkeypatch):
        user = _staff_user()
        client = _http_client(user=user)

        response = client.post(
            "/admin/our-specials",
            json={"label": "Towing", "category": "FOC"},
        )

        assert response.status_code == 403

    def test_post_create_variant(self, monkeypatch):
        special = _make_special(id="a", label="Windscreen")
        user = _admin_user()
        client = _http_client(user=user, specials=[special])

        response = client.post(
            "/admin/our-special-variants",
            json={"special_id": "a", "label": "Windscreen Coverage", "value_text": "Up to RM 1,000"},
        )

        assert response.status_code == 200
        v = response.json()["variant"]
        assert v["label"] == "Windscreen Coverage"
        assert v["value_text"] == "Up to RM 1,000"
        assert v["special_id"] == "a"

    def test_post_create_variant_404_on_bad_parent(self, monkeypatch):
        user = _admin_user()
        client = _http_client(user=user)

        response = client.post(
            "/admin/our-special-variants",
            json={"special_id": "nope", "label": "Test"},
        )

        assert response.status_code == 404

    def test_delete_variant(self, monkeypatch):
        variant = _make_variant("a", id="v1", label="Test")
        user = _admin_user()
        client = _http_client(user=user, variants=[variant])

        response = client.delete("/admin/our-special-variants/v1")

        assert response.status_code == 200
        assert response.json()["deleted"] is True

    def test_delete_variant_404(self, monkeypatch):
        user = _admin_user()
        client = _http_client(user=user)

        response = client.delete("/admin/our-special-variants/nonexistent")

        assert response.status_code == 404


class TestOurSpecialsService:
    """Unit tests for Our Specials service functions."""

    def test_upsert_creates_special(self):
        user = _admin_user()
        db = FakeDb(user=user)

        special = upsert_special(db, user, {"label": "Windscreen", "category": "FOC"})

        assert special.label == "Windscreen"
        assert special.category == "FOC"
        assert len(db.added) == 1
        assert db.commits == 1

    def test_upsert_updates_special(self):
        existing = _make_special(id="a", label="Old")
        user = _admin_user()
        db = FakeDb(user=user, specials=[existing])

        special = upsert_special(db, user, {"id": "a", "label": "Updated"})

        assert special.label == "Updated"
        assert db.commits == 1

    def test_delete_removes_special(self):
        existing = _make_special(id="a")
        user = _admin_user()
        db = FakeDb(user=user, specials=[existing])

        delete_special(db, user, "a")

        assert len(db.deleted) == 1
        assert db.commits == 1

    def test_delete_raises_404(self):
        user = _admin_user()
        db = FakeDb(user=user)

        with pytest.raises(AppError, match="Special not found"):
            delete_special(db, user, "nope")

    def test_upsert_variant_creates(self):
        parent = _make_special(id="a")
        user = _admin_user()
        db = FakeDb(user=user, specials=[parent])

        variant = upsert_variant(db, user, {"special_id": "a", "label": "Test", "value_text": "RM 500"})

        assert variant.label == "Test"
        assert variant.value_text == "RM 500"
        assert db.commits == 1

    def test_upsert_variant_raises_404_on_bad_parent(self):
        user = _admin_user()
        db = FakeDb(user=user)

        with pytest.raises(AppError, match="Parent special not found"):
            upsert_variant(db, user, {"special_id": "nope", "label": "Test"})

    def test_delete_variant_removes(self):
        variant = _make_variant("a", id="v1")
        user = _admin_user()
        db = FakeDb(user=user, variants=[variant])

        delete_variant(db, user, "v1")

        assert len(db.deleted) == 1
        assert db.commits == 1

    def test_delete_variant_raises_404(self):
        user = _admin_user()
        db = FakeDb(user=user)

        with pytest.raises(AppError, match="Variant not found"):
            delete_variant(db, user, "nope")

    def test_move_variant_changes_special(self):
        from app.services.admin_service import move_variant

        parent_a = _make_special(id="a", label="Towing")
        parent_b = _make_special(id="b", label="Windscreen")
        variant = _make_variant("a", id="v1", label="Windscreen Coverage")
        user = _admin_user()
        db = FakeDb(user=user, specials=[parent_a, parent_b], variants=[variant])

        moved = move_variant(db, user, "v1", "b")

        assert moved.special_id == "b"
        assert db.commits == 1

    def test_move_variant_raises_404_on_bad_target(self):
        from app.services.admin_service import move_variant

        variant = _make_variant("a", id="v1")
        user = _admin_user()
        db = FakeDb(user=user, variants=[variant])

        with pytest.raises(AppError, match="Target special not found"):
            move_variant(db, user, "v1", "nope")
