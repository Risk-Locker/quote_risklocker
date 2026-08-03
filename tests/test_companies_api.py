"""HTTP and service tests for insurance company CRUD endpoints."""

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
from app.api.deps import AuthContext, current_auth, settings_dep
from app.core.errors import register_error_handlers
from app.db.session import get_db
from app.models.tables import AuthSession, InsuranceCompany, User
from app.models.enums import AccountStatus, InsuranceType
from app.services.admin_service import delete_company, upsert_company
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
    )


def _make_company(**overrides) -> InsuranceCompany:
    defaults = {
        "id": str(uuid4()),
        "name": "QBE",
        "category": InsuranceType.MOTOR.value,
        "source_template_category": "QBE",
        "detection_phrases": ["qbe"],
        "logo_path": None,
        "status": AccountStatus.ACTIVE.value,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return InsuranceCompany(**defaults)


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


def _admin_auth() -> tuple[User, AuthSession, str]:
    now = datetime.now(timezone.utc)
    user = _admin_user()
    raw_token = "admin-token"
    session = AuthSession(
        id=str(uuid4()),
        user_id=user.id,
        token_hash=hash_session_token(raw_token),
        last_activity_at=now,
        idle_expires_at=now.replace(year=2099),
        absolute_expires_at=now.replace(year=2099),
        revoked_at=None,
        created_at=now,
        updated_at=now,
    )
    return user, session, raw_token


def _staff_auth() -> tuple[User, AuthSession, str]:
    now = datetime.now(timezone.utc)
    user = _staff_user()
    raw_token = "staff-token"
    session = AuthSession(
        id=str(uuid4()),
        user_id=user.id,
        token_hash=hash_session_token(raw_token),
        last_activity_at=now,
        idle_expires_at=now.replace(year=2099),
        absolute_expires_at=now.replace(year=2099),
        revoked_at=None,
        created_at=now,
        updated_at=now,
    )
    return user, session, raw_token


class FakeDb:
    """A fake SQLAlchemy Session-like object for testing companies endpoints."""

    def __init__(self, session: AuthSession | None = None, user: User | None = None, companies: list[InsuranceCompany] | None = None):
        self._session = session
        self._user = user
        self._companies = companies or []
        self.added: list = []
        self.deleted: list = []
        self.commits = 0

    def scalar(self, statement):
        if self._session is not None and self._session.revoked_at is not None:
            return None
        if self._session is not None:
            return self._session
        return len(self._companies)

    def scalars(self, statement):
        return _ScalarResult(self._companies)

    def get(self, model, object_id):
        if model is User and self._user:
            return self._user if str(self._user.id) == str(object_id) else None
        for c in self._companies:
            if str(c.id) == str(object_id):
                return c
        return None

    def add(self, value):
        self.added.append(value)
        if isinstance(value, InsuranceCompany):
            self._companies.append(value)

    def delete(self, value):
        self.deleted.append(value)
        if value in self._companies:
            self._companies.remove(value)

    def commit(self):
        self.commits += 1

    def refresh(self, _value):
        pass


class _ScalarResult:
    """Mimics SQLAlchemy ScalarResult for .all() calls."""

    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)


def _http_client(*, user: User | None = None, companies=None):
    db = FakeDb(user=user, companies=companies)
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(routes.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[settings_dep] = auth_settings
    if user:
        app.dependency_overrides[current_user] = lambda: user
    return TestClient(app)


from app.api.deps import current_user


class TestCompanyRoutesHttp:
    """HTTP tests for /admin/companies endpoints."""

    def test_get_companies_returns_list(self, monkeypatch):
        qbe = _make_company(name="QBE")
        amgen = _make_company(name="AmGen")
        user = _admin_user()
        client = _http_client(user=user, companies=[qbe, amgen])

        response = client.get("/admin/companies")

        assert response.status_code == 200
        data = response.json()
        assert len(data["companies"]) == 2
        names = {c["name"] for c in data["companies"]}
        assert names == {"QBE", "AmGen"}

    def test_post_create_company(self, monkeypatch):
        user = _admin_user()
        client = _http_client(user=user)

        response = client.post(
            "/admin/companies",
            json={"name": "STMB", "category": "Motor", "detection_phrases": ["stmb"]},
        )

        assert response.status_code == 200
        company = response.json()["company"]
        assert company["name"] == "STMB"

    def test_post_update_company(self, monkeypatch):
        qbe = _make_company(id="11111111-1111-1111-1111-111111111111", name="QBE")
        user = _admin_user()
        client = _http_client(user=user, companies=[qbe])

        response = client.post(
            "/admin/companies",
            json={"id": qbe.id, "name": "QBE Updated", "status": "inactive"},
        )

        assert response.status_code == 200
        company = response.json()["company"]
        assert company["name"] == "QBE Updated"
        assert company["status"] == "inactive"

    def test_delete_company_succeeds_when_multiple_exist(self, monkeypatch):
        qbe = _make_company(id="a", name="QBE")
        amgen = _make_company(id="b", name="AmGen")
        user = _admin_user()
        client = _http_client(user=user, companies=[qbe, amgen])

        response = client.delete("/admin/companies/a")

        assert response.status_code == 200
        assert response.json()["deleted"] is True

    def test_delete_company_rejects_last_remaining(self, monkeypatch):
        qbe = _make_company(id="last", name="QBE")
        user = _admin_user()
        client = _http_client(user=user, companies=[qbe])

        response = client.delete("/admin/companies/last")

        assert response.status_code == 400
        assert "At least one company" in response.json()["error"]["message"]

    def test_delete_company_rejects_non_admin(self, monkeypatch):
        qbe = _make_company(id="a", name="QBE")
        amgen = _make_company(id="b", name="AmGen")
        user = _staff_user()
        client = _http_client(user=user, companies=[qbe, amgen])

        response = client.delete("/admin/companies/a")

        assert response.status_code == 403

    def test_delete_company_returns_404_for_missing(self, monkeypatch):
        qbe = _make_company(id="a", name="QBE")
        user = _admin_user()
        client = _http_client(user=user, companies=[qbe])

        response = client.delete("/admin/companies/nonexistent")

        assert response.status_code == 404


class TestDeleteCompanyService:
    """Unit tests for the delete_company service function."""

    def test_delete_removes_company_and_commits(self):
        qbe = _make_company(id="a", name="QBE")
        amgen = _make_company(id="b", name="AmGen")
        user = _admin_user()
        db = FakeDb(companies=[qbe, amgen])

        delete_company(db, user, "a")

        assert len(db.deleted) == 1
        assert db.deleted[0].id == "a"
        assert len(db._companies) == 1
        assert db._companies[0].id == "b"
        assert db.commits == 1

    def test_delete_raises_when_last_company(self):
        qbe = _make_company(id="sole", name="QBE")
        user = _admin_user()
        db = FakeDb(companies=[qbe])

        with pytest.raises(AppError, match="At least one company must remain"):
            delete_company(db, user, "sole")

        assert len(db.deleted) == 0
        assert len(db._companies) == 1

    def test_delete_raises_when_zero_companies(self):
        user = _admin_user()
        db = FakeDb(companies=[])

        with pytest.raises(AppError, match="Company not found"):
            delete_company(db, user, "none")

    def test_delete_raises_for_non_admin_user(self):
        qbe = _make_company(id="a", name="QBE")
        amgen = _make_company(id="b", name="AmGen")
        user = _staff_user()
        db = FakeDb(companies=[qbe, amgen])

        with pytest.raises(AppError, match="Only Admin"):
            delete_company(db, user, "a")

    def test_delete_raises_404_for_missing_id(self):
        qbe = _make_company(id="a", name="QBE")
        amgen = _make_company(id="b", name="AmGen")
        user = _admin_user()
        db = FakeDb(companies=[qbe, amgen])

        with pytest.raises(AppError, match="Company not found"):
            delete_company(db, user, "c")
