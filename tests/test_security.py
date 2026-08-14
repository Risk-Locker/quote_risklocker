"""Security tests for password hashing, sessions, and role checks."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.errors import AppError
from app.core.security import hash_password, hash_session_token, verify_password
from app.models.tables import AuthSession, User
from app.services.auth_service import (
    authenticate_session,
    bootstrap_primary_admin,
    change_password,
    create_user,
    login_with_password,
    revoke_session,
    update_user,
)


def settings(**overrides):
    values = {
        "app_env": "test",
        "auth_hash_secret": "test-auth-hash-secret-that-is-long-enough",
        "session_idle_hours": 8,
        "session_max_days": 30,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class ScalarRows:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class FakeSession:
    def __init__(self, scalar_values=None, objects=None, rows=None, session=None):
        self.scalar_values = list(scalar_values or [])
        self.objects = objects or {}
        self.rows = list(rows or [])
        self.session = session
        self.added = []
        self.commits = 0
        self.executed = []

    def scalar(self, _statement):
        if self.scalar_values:
            value = self.scalar_values.pop(0)
            if isinstance(value, AuthSession) and value.revoked_at is not None:
                return None
            return value
        if isinstance(self.session, AuthSession) and self.session.revoked_at is not None:
            return None
        return self.session

    def scalars(self, _statement):
        return ScalarRows(self.rows)

    def get(self, _model, object_id):
        return self.objects.get(object_id)

    def add(self, value):
        if getattr(value, "id", None) is None:
            value.id = str(uuid4())
        if hasattr(value, "created_at") and getattr(value, "created_at", None) is None:
            value.created_at = datetime.now(timezone.utc)
        self.added.append(value)

    def flush(self):
        return None

    def commit(self):
        self.commits += 1

    def refresh(self, _value):
        return None

    def execute(self, statement):
        self.executed.append(str(statement))


def test_password_hash_round_trip():
    digest = hash_password("plain-password")
    assert "plain-password" not in digest
    assert verify_password("plain-password", digest)
    assert not verify_password("wrong-password", digest)


def test_session_token_hashing():
    token = "opaque-session-token"
    digest = hash_session_token(token)
    assert token not in digest
    assert len(digest) == 64


def test_login_with_password_rejects_invalid_credentials():
    user = User(
        id=str(uuid4()),
        email="person.name@example.com",
        password_hash=hash_password("secret"),
        role="staff",
        status="active",
    )
    db = FakeSession(scalar_values=[user])

    with pytest.raises(AppError, match="Invalid email or password"):
        login_with_password(db, settings(), user.email, "wrong", None, None)

    db = FakeSession(scalar_values=[None])
    with pytest.raises(AppError, match="Invalid email or password"):
        login_with_password(db, settings(), "missing@example.com", "secret", None, None)


def test_login_with_password_creates_session():
    user = User(
        id=str(uuid4()),
        email="person.name@example.com",
        password_hash=hash_password("secret"),
        role="staff",
        status="active",
    )
    db = FakeSession(scalar_values=[user])
    authenticated_user, session, raw_token = login_with_password(db, settings(), user.email, "secret", None, None)
    assert authenticated_user is user
    assert session.token_hash == hash_session_token(raw_token)
    assert raw_token not in session.token_hash


def test_eight_hour_window_rolls_on_activity_and_then_expires():
    user = User(
        id=str(uuid4()),
        email="person.name@example.com",
        password_hash=hash_password("secret"),
        role="staff",
        status="active",
    )
    issued = datetime.now(timezone.utc)
    session = AuthSession(
        id=str(uuid4()),
        user_id=user.id,
        token_hash=hash_session_token("token"),
        last_activity_at=issued,
        idle_expires_at=issued + timedelta(hours=8),
        absolute_expires_at=issued + timedelta(days=30),
        revoked_at=None,
    )
    auth_db = FakeSession(scalar_values=[session], objects={user.id: user})
    authenticate_session(auth_db, settings(), "token")
    assert session.last_activity_at >= issued
    assert session.idle_expires_at >= issued + timedelta(hours=8)

    expired_db = FakeSession(scalar_values=[session], objects={user.id: user})
    session.idle_expires_at = issued - timedelta(seconds=1)
    with pytest.raises(AppError, match="expired"):
        authenticate_session(expired_db, settings(), "token")


def test_session_has_hard_thirty_day_limit_and_revocation_is_immediate():
    user = User(
        id=str(uuid4()),
        email="person.name@example.com",
        password_hash=hash_password("secret"),
        role="staff",
        status="active",
    )
    issued = datetime.now(timezone.utc)
    session = AuthSession(
        id=str(uuid4()),
        user_id=user.id,
        token_hash=hash_session_token("token"),
        last_activity_at=issued,
        idle_expires_at=issued + timedelta(hours=8),
        absolute_expires_at=issued + timedelta(days=30),
        revoked_at=None,
    )
    expired_db = FakeSession(scalar_values=[session], objects={user.id: user})
    session.absolute_expires_at = issued - timedelta(seconds=1)
    with pytest.raises(AppError, match="expired"):
        authenticate_session(expired_db, settings(), "token")

    session.absolute_expires_at = issued + timedelta(days=30)
    session.revoked_at = None
    revoke_session(FakeSession(), session, user.id)
    revoked_db = FakeSession(scalar_values=[session], objects={user.id: user})
    with pytest.raises(AppError, match="Please log in"):
        authenticate_session(revoked_db, settings(), "token")


def test_inactive_account_cannot_use_existing_session():
    user = User(
        id=str(uuid4()),
        email="person.name@example.com",
        password_hash=hash_password("secret"),
        role="staff",
        status="inactive",
    )
    issued = datetime.now(timezone.utc)
    session = AuthSession(
        id=str(uuid4()),
        user_id=user.id,
        token_hash=hash_session_token("token"),
        last_activity_at=issued,
        idle_expires_at=issued + timedelta(hours=8),
        absolute_expires_at=issued + timedelta(days=30),
        revoked_at=None,
    )
    auth_db = FakeSession(scalar_values=[session], objects={user.id: user})
    with pytest.raises(AppError, match="not active"):
        authenticate_session(auth_db, settings(), "token")
    assert session.revoked_at is not None


def test_dev_account_cannot_login_or_keep_a_session_in_production():
    user = User(
        id=str(uuid4()),
        email="developer@example.com",
        password_hash=hash_password("secret-password"),
        role="dev",
        status="active",
    )
    issued = datetime.now(timezone.utc)
    session = AuthSession(
        id=str(uuid4()),
        user_id=user.id,
        token_hash=hash_session_token("token"),
        last_activity_at=issued,
        idle_expires_at=issued + timedelta(hours=8),
        absolute_expires_at=issued + timedelta(days=30),
        revoked_at=None,
    )
    auth_db = FakeSession(scalar_values=[session], objects={user.id: user})

    with pytest.raises(AppError, match="Invalid email or password"):
        login_with_password(
            FakeSession(scalar_values=[user]),
            settings(app_env="production"),
            user.email,
            "secret-password",
            None,
            None,
        )
    with pytest.raises(AppError, match="not available"):
        authenticate_session(auth_db, settings(app_env="production"), "token")

    assert session.revoked_at is not None


def test_primary_admin_bootstrap_is_one_time_and_transaction_locked():
    db = FakeSession(scalar_values=[None, None])

    created = bootstrap_primary_admin(db, "primary@example.com", "long-bootstrap-password")

    assert created.role == "super_admin"
    assert created.status == "active"
    assert db.commits == 1
    assert any("pg_advisory_xact_lock" in statement for statement in db.executed)

    existing = User(
        id=str(uuid4()),
        email="existing@example.com",
        password_hash=hash_password("existing-password"),
        role="super_admin",
        status="active",
    )
    blocked_db = FakeSession(scalar_values=[existing])
    with pytest.raises(AppError, match="already exists"):
        bootstrap_primary_admin(blocked_db, "primary@example.com", "different-password")
    assert blocked_db.added == []
    assert existing.email == "existing@example.com"


def test_user_management_roles():
    now = datetime.now(timezone.utc)
    super_admin = User(id=str(uuid4()), email="super@example.com", password_hash=hash_password("secret"), role="super_admin", status="active", created_at=now, updated_at=now)
    admin = User(id=str(uuid4()), email="admin@example.com", password_hash=hash_password("secret"), role="admin", status="active", created_at=now, updated_at=now)
    staff = User(id=str(uuid4()), email="staff@example.com", password_hash=hash_password("secret"), role="staff", status="active", created_at=now, updated_at=now)

    # Super admin can create admin
    db = FakeSession(scalar_values=[None])
    created = create_user(db, super_admin, "new.admin@example.com", "admin", password="secret-password")
    assert created.role == "admin"

    # Admin cannot create super_admin
    with pytest.raises(AppError, match="Only the super administrator"):
        create_user(FakeSession(), admin, "new.super@example.com", "super_admin", password="secret-password")

    # Admin cannot update themselves
    with pytest.raises(AppError, match="cannot modify your own account"):
        update_user(FakeSession(), admin, admin, role="staff")

    # Staff cannot create users
    with pytest.raises(AppError, match="permission to manage users"):
        create_user(FakeSession(), staff, "new.user@example.com", "staff", password="secret-password")


def test_change_password_requires_current_password():
    user = User(id=str(uuid4()), email="person@example.com", password_hash=hash_password("old-secret"), role="staff", status="active")
    with pytest.raises(AppError, match="Current password is incorrect"):
        change_password(FakeSession(), user, "wrong", "new-secret-long")


def test_frontend_does_not_store_authentication_tokens_in_browser_storage():
    api_source = (ROOT / "frontend" / "src" / "lib" / "api.ts").read_text(encoding="utf-8")
    login_source = (ROOT / "frontend" / "src" / "app" / "login" / "page.tsx").read_text(encoding="utf-8")
    combined = api_source + login_source
    assert "risklocker_token" not in combined
    assert "Authorization" not in combined
    assert "Bearer " not in combined
    assert "localStorage" not in combined
    assert "sessionStorage" not in combined
    assert "credentials: \"include\"" in api_source
