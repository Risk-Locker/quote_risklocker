"""Tests for trash purge with Supabase storage deletion and dead code removal."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

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

from app.services.review_service import list_history, list_trash, purge_expired_trash
from app.models.enums import Role


def test_no_manager_role_references_in_source():
    src = (BACKEND / "app" / "services" / "review_service.py").read_text(encoding="utf-8")
    assert "Role.MANAGER" not in src
    assert "MANAGER" not in src


def test_list_history_does_not_reference_manager():
    src = (BACKEND / "app" / "services" / "review_service.py").read_text(encoding="utf-8")
    history_fn = src[src.index("def list_history"): src.index("def move_to_trash")]
    assert "MANAGER" not in history_fn


def test_list_trash_does_not_reference_manager():
    src = (BACKEND / "app" / "services" / "review_service.py").read_text(encoding="utf-8")
    trash_fn = src[src.index("def list_trash"): src.index("def restore_from_trash")]
    assert "MANAGER" not in trash_fn


def test_purge_expired_trash_calls_storage_delete(monkeypatch):
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from uuid import uuid4

    from app.models.tables import QuotationDraft, UploadedFile, new_id
    from app.models.enums import RecordStatus, StorageStatus

    class FakeDb:
        def __init__(self, *records):
            self._records = list(records)
            self.deleted_items = []
            self.commits = 0

        def scalars(self, statement):
            return _FakeResult(self._records)

        def delete(self, record):
            self.deleted_items.append(record)
            if record in self._records:
                self._records.remove(record)

        def commit(self):
            self.commits += 1

    class _FakeResult:
        def __init__(self, items):
            self._items = items

        def all(self):
            return list(self._items)

    now = datetime.now(timezone.utc)
    file = UploadedFile(
        id=str(uuid4()),
        batch_id=str(uuid4()),
        owner_id=str(uuid4()),
        original_filename="test.pdf",
        content_type="application/pdf",
        storage_path="source/2026/01/batch/file.pdf",
        storage_provider="supabase",
        storage_bucket="risklocker-pdfs",
        storage_status=StorageStatus.AVAILABLE.value,
        size_bytes=1000,
        status=RecordStatus.DELETED.value,
        created_at=now,
        updated_at=now,
        deleted_at=now,
        purge_after=now,
    )
    storage = MagicMock()
    storage.delete_pdf = MagicMock()
    user = SimpleNamespace(role=Role.ADMIN.value)
    db = FakeDb(file)

    count = purge_expired_trash(db, user, storage)

    assert count == 1
    storage.delete_pdf.assert_any_call("source/2026/01/batch/file.pdf")
    assert len(db.deleted_items) == 1
    assert db.commits == 1
