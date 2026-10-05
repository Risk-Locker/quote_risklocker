"""Hermetic tests for 5-attempt login lockout, Master Admin role gate, and Resend alert."""

from datetime import datetime, timezone
from typing import cast
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import hash_password
from app.models.enums import AccountStatus, Role
from app.models.tables import AuthSession, User
from app.services.auth_service import (
    check_login_lockout,
    create_user,
    login_with_password,
    record_login_failure,
    reset_login_failures,
)
from app.services.security_notification_service import send_login_alert


class DummyFakeSession:
    def __init__(self, users=None):
        self.users = users or {}
        self.added = []

    def scalar(self, query):
        # Simplistic matcher for User lookup by email
        for user in self.users.values():
            return user
        return None

    def get(self, model, ident):
        return self.users.get(ident)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass

    def refresh(self, obj):
        pass


def dummy_settings():
    return MagicMock(
        session_idle_hours=8,
        session_max_days=30,
        app_env="test",
        auth_hash_secret="test-secret-long-enough-32-chars-at-least!",
    )


def test_login_lockout_after_five_failed_attempts():
    test_email = f"target-{uuid4()}@example.com"
    reset_login_failures(test_email)

    # 4 failures should increment without blocking
    for i in range(4):
        wait = record_login_failure(test_email)
        assert wait == 0, f"Attempt {i+1} should not trigger lockout"

    # 5th failure triggers 120s lockout
    wait = record_login_failure(test_email)
    assert wait == 120, "5th attempt must trigger 120-second lockout"

    # Subsequent check raises AppError 429 with Retry-After header
    with pytest.raises(AppError) as exc_info:
        check_login_lockout(test_email)

    assert exc_info.value.status_code == 429
    assert "Too many failed login attempts" in exc_info.value.message
    assert exc_info.value.headers is not None
    assert "Retry-After" in exc_info.value.headers
    assert int(exc_info.value.headers["Retry-After"]) > 0

    # Successful reset clears lockout
    reset_login_failures(test_email)
    # Check should now pass without raising
    check_login_lockout(test_email)


def test_login_with_password_resets_failures_on_success():
    test_email = f"user-{uuid4()}@example.com"
    reset_login_failures(test_email)

    user = User(
        id=str(uuid4()),
        email=test_email,
        password_hash=hash_password("correct-password"),
        role=Role.STAFF.value,
        status=AccountStatus.ACTIVE.value,
    )
    db = cast(Session, DummyFakeSession(users={user.id: user}))

    # 2 wrong password attempts
    for _ in range(2):
        with pytest.raises(AppError) as exc:
            login_with_password(db, dummy_settings(), test_email, "wrong-password", "ua", "127.0.0.1")
        assert exc.value.status_code == 401

    # Now login with correct password
    logged_user, session, token = login_with_password(
        db, dummy_settings(), test_email, "correct-password", "ua", "127.0.0.1"
    )
    assert logged_user.id == user.id

    # Check lockout state is clean
    check_login_lockout(test_email)


def test_staff_cannot_manage_users():
    staff_user = User(
        id=str(uuid4()),
        email="staff@example.com",
        password_hash=hash_password("pw"),
        role=Role.STAFF.value,
        status=AccountStatus.ACTIVE.value,
    )
    super_admin = User(
        id=str(uuid4()),
        email="system@risklocker.com",
        password_hash=hash_password("pw"),
        role=Role.SUPER_ADMIN.value,
        status=AccountStatus.ACTIVE.value,
    )
    db = cast(Session, DummyFakeSession())

    # Staff trying to create user must be blocked with 403
    with pytest.raises(AppError) as exc_info:
        create_user(db, staff_user, "new@example.com", Role.STAFF.value, password="secret-password")

    assert exc_info.value.status_code == 403
    assert "master administrator" in exc_info.value.message


def test_resend_security_alert_skipped_when_no_api_key(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    result = send_login_alert(
        user_email="system@risklocker.com",
        ip_address="192.168.1.100",
        user_agent="Mozilla/5.0",
    )
    assert result is False


def test_resend_security_alert_dispatches_when_key_present(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_dummy_key_123")
    monkeypatch.setenv("SECURITY_ALERT_EMAIL", "system@risklocker.com")

    with patch("httpx.Client.post") as mock_post:
        mock_response = MagicMock(status_code=200)
        mock_post.return_value = mock_response

        result = send_login_alert(
            user_email="admin@client.com",
            ip_address="203.0.113.45",
            user_agent="Chrome/120.0",
        )

        assert result is True
        assert mock_post.called
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["to"] == ["system@risklocker.com"]
        assert "admin@client.com" in call_kwargs["json"]["subject"]
        assert "203.0.113.45" in call_kwargs["json"]["html"]
