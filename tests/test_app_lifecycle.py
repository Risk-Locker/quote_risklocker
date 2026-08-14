"""Regression tests for production-safe application lifecycle behavior."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


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

from app import main as main_module
from app.db import init_db


class FakeSessionContext:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def get_bind(self):
        return object()


def test_web_startup_checks_dependencies_without_mutating_schema_credentials_or_retention(monkeypatch):
    calls = {"database": 0, "readiness": 0, "storage": 0, "schema": 0, "seed": 0, "retention": 0}

    monkeypatch.setattr(
        main_module,
        "verify_database_connection",
        lambda: calls.__setitem__("database", calls["database"] + 1),
    )
    monkeypatch.setattr(
        main_module,
        "verify_schema_version",
        lambda: calls.__setitem__("readiness", calls["readiness"] + 1),
    )
    monkeypatch.setattr(
        main_module.Base.metadata,
        "create_all",
        lambda **_kwargs: calls.__setitem__("schema", calls["schema"] + 1),
    )
    monkeypatch.setattr(
        main_module,
        "seed_defaults",
        lambda *_args: calls.__setitem__("seed", calls["seed"] + 1),
    )
    monkeypatch.setattr(
        main_module,
        "purge_expired_pdfs",
        lambda *_args: calls.__setitem__("retention", calls["retention"] + 1),
    )
    monkeypatch.setattr(main_module, "SessionLocal", FakeSessionContext)

    class FakeStorage:
        def __init__(self, _settings):
            pass

        def ensure_bucket(self):
            calls["storage"] += 1

    monkeypatch.setattr(main_module, "SupabaseStorage", FakeStorage)
    application = main_module.create_app()

    async def exercise_lifecycle() -> None:
        async with application.router.lifespan_context(application):
            pass

    asyncio.run(exercise_lifecycle())

    assert calls == {"database": 1, "readiness": 1, "storage": 1, "schema": 0, "seed": 0, "retention": 0}
    assert not hasattr(application.state, "storage_retention_task")


def test_default_data_seed_never_bootstraps_or_resets_primary_admin(monkeypatch):
    bootstrap = MagicMock()
    monkeypatch.setattr(init_db, "ensure_super_admin", bootstrap)
    db = MagicMock()

    init_db.seed_defaults(db, SimpleNamespace())

    bootstrap.assert_not_called()
