"""HTTP tests for password-based authentication and sessions."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
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
from app.api.deps import settings_dep
from app.core.errors import register_error_handlers
from app.core.security import hash_password, hash_session_token
from app.db.session import get_db
from app.models.tables import AuthSession, User


class FakeSession:
    def __init__(self, session: AuthSession | None = None, user: User | None = None):
        self.session = session
        self.user = user
        self.added = []
        self.commits = 0

    def scalar(self, _statement):
        if isinstance(self.session, AuthSession) and self.session.revoked_at is not None:
            return None
        return self.session

    def get(self, _model, object_id):
        return self.user if self.user and self.user.id == object_id else None

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.commits += 1

    def refresh(self, _value):
        return None


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


def app_client(db: FakeSession):
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(routes.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[settings_dep] = auth_settings
    return TestClient(app)


def active_user_and_session(status="active"):
    now = datetime.now(timezone.utc)
    user = User(
        id=str(uuid4()),
        email="person.name@risklocker.com",
        password_hash=hash_password("secret-password"),
        role="staff",
        status=status,
        created_at=now,
        updated_at=now,
    )
    raw_token = "opaque-session-token"
    session = AuthSession(
        id=str(uuid4()),
        user_id=user.id,
        token_hash=hash_session_token(raw_token),
        last_activity_at=now,
        idle_expires_at=now + timedelta(hours=8),
        absolute_expires_at=now + timedelta(days=30),
        revoked_at=None,
        created_at=now,
        updated_at=now,
    )
    return user, session, raw_token


def test_login_with_password_sets_http_only_session_cookie(monkeypatch):
    user, session, _ = active_user_and_session()
    monkeypatch.setattr(
        routes,
        "login_with_password",
        lambda *_args, **_kwargs: (user, session, "new-opaque-token"),
    )
    client = app_client(FakeSession())

    response = client.post("/auth/login", json={"email": user.email, "password": "secret-password"})

    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "risklocker_session=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "new-opaque-token" not in response.text


def test_login_me_logout_and_revoked_session_http_flow():
    user, session, raw_token = active_user_and_session()
    db = FakeSession(session, user)
    client = app_client(db)
    client.cookies.set("risklocker_session", raw_token)

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == user.email

    logout = client.post("/auth/logout")
    assert logout.status_code == 200
    assert session.revoked_at is not None

    client.cookies.set("risklocker_session", raw_token)
    rejected = client.get("/auth/me")
    assert rejected.status_code == 401


@pytest.mark.parametrize("status", ["inactive"])
def test_inactive_account_is_rejected_over_http(status):
    user, session, raw_token = active_user_and_session(status=status)
    client = app_client(FakeSession(session, user))
    client.cookies.set("risklocker_session", raw_token)

    response = client.get("/auth/me")

    assert response.status_code == 401
    assert "not active" in response.json()["error"]["message"]
    assert session.revoked_at is not None
