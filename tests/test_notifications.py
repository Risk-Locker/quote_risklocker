"""Tests for the in-app notification service."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

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

from app.core.errors import AppError
from app.models.enums import NotificationEventType
from app.models.tables import Notification
from app.services.notification_service import (
    create_notification,
    get_notifications,
    get_unread_count,
    mark_all_read,
    mark_read,
    serialize_notification,
)


class ScalarRows:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class FakeSession:
    def __init__(self, scalar_values=None, objects=None, rows=None):
        self.scalar_values = list(scalar_values or [])
        self.objects = objects or {}
        self.rows = list(rows or [])
        self.added = []
        self.commits = 0

    def scalar(self, _statement):
        return self.scalar_values.pop(0) if self.scalar_values else None

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


class TestNotificationService:
    def test_create_notification(self):
        db = FakeSession()
        notification = create_notification(
            db,
            recipient_id="recipient-1",
            event_type=NotificationEventType.ROLE_CHANGE,
            title="Role changed",
            body="Your role was changed to admin.",
        )
        assert notification.recipient_id == "recipient-1"
        assert notification.event_type == NotificationEventType.ROLE_CHANGE.value
        assert notification.title == "Role changed"
        assert notification.read_at is None

    def test_get_notifications_returns_newest_first(self):
        now = datetime.now(timezone.utc)
        n1 = Notification(
            id=str(uuid4()),
            recipient_id="r1",
            event_type=NotificationEventType.STATUS_CHANGE.value,
            title="First",
            body="Body",
            created_at=now,
        )
        n2 = Notification(
            id=str(uuid4()),
            recipient_id="r1",
            event_type=NotificationEventType.STATUS_CHANGE.value,
            title="Second",
            body="Body",
            created_at=now + timedelta(minutes=1),
        )
        db = FakeSession(rows=[n2, n1])
        result = get_notifications(db, "r1")
        assert result == [n2, n1]

    def test_unread_count(self):
        now = datetime.now(timezone.utc)
        n1 = Notification(
            id=str(uuid4()),
            recipient_id="r1",
            event_type=NotificationEventType.STATUS_CHANGE.value,
            title="Unread",
            body="Body",
            created_at=now,
        )
        n2 = Notification(
            id=str(uuid4()),
            recipient_id="r1",
            event_type=NotificationEventType.STATUS_CHANGE.value,
            title="Read",
            body="Body",
            read_at=now,
            created_at=now,
        )
        db = FakeSession(rows=[n1])
        assert get_unread_count(db, "r1") == 1
        db2 = FakeSession(rows=[n1, n2])
        assert get_unread_count(db2, "r1") == 2

    def test_mark_read(self):
        now = datetime.now(timezone.utc)
        n1 = Notification(
            id=str(uuid4()),
            recipient_id="r1",
            event_type=NotificationEventType.STATUS_CHANGE.value,
            title="Unread",
            body="Body",
            created_at=now,
        )
        db = FakeSession(objects={n1.id: n1})
        result = mark_read(db, n1.id, "r1")
        assert result.read_at is not None

    def test_mark_read_rejects_other_recipient(self):
        now = datetime.now(timezone.utc)
        n1 = Notification(
            id=str(uuid4()),
            recipient_id="r1",
            event_type=NotificationEventType.STATUS_CHANGE.value,
            title="Unread",
            body="Body",
            created_at=now,
        )
        db = FakeSession(objects={n1.id: n1})
        with pytest.raises(AppError, match="not found"):
            mark_read(db, n1.id, "r2")

    def test_mark_all_read(self):
        now = datetime.now(timezone.utc)
        n1 = Notification(
            id=str(uuid4()),
            recipient_id="r1",
            event_type=NotificationEventType.STATUS_CHANGE.value,
            title="Unread",
            body="Body",
            created_at=now,
        )
        db = FakeSession(rows=[n1])
        assert mark_all_read(db, "r1") == 1
        assert n1.read_at is not None

    def test_serialize_notification(self):
        now = datetime.now(timezone.utc)
        n1 = Notification(
            id=str(uuid4()),
            recipient_id="r1",
            event_type=NotificationEventType.ROLE_CHANGE.value,
            title="Role changed",
            body="Body",
            created_at=now,
        )
        serialized = serialize_notification(n1)
        assert serialized["title"] == "Role changed"
        assert serialized["read_at"] is None
