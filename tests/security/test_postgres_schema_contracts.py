"""PostgreSQL schema, RLS, and migration ledger contracts.

These tests run against a real PostgreSQL instance (e.g. GitHub Actions
postgres:16 service container or local Docker) when RL_TEST_POSTGRES_URL
or TEST_POSTGRES_URL is configured. When unset, they are safely skipped,
preserving 100% hermetic offline execution during local development.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

POSTGRES_URL = os.getenv("RL_TEST_POSTGRES_URL") or os.getenv("TEST_POSTGRES_URL")
postgres_required = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="Requires live PostgreSQL URL in RL_TEST_POSTGRES_URL or TEST_POSTGRES_URL (opt-in CI parity).",
)


@postgres_required
@pytest.mark.postgres
def test_all_migrations_apply_cleanly_on_fresh_postgres():
    from app.db.migrations import apply_migrations, default_migration_root, discover_migrations
    from app.db.session import _sqlalchemy_url, verify_schema_version

    engine = create_engine(_sqlalchemy_url(POSTGRES_URL), poolclass=NullPool)
    migrations = discover_migrations(default_migration_root())

    # Pre-create required roles if not existing (matching Supabase / CI setup)
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'anon') THEN
                        CREATE ROLE anon NOLOGIN;
                    END IF;
                    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticated') THEN
                        CREATE ROLE authenticated NOLOGIN;
                    END IF;
                END
                $$;
                """
            )
        )
        conn.commit()

    # Apply all migrations
    plan = apply_migrations(engine, migrations)
    assert len(plan) == len(migrations), f"Expected all {len(migrations)} migrations to apply on fresh DB"

    # Schema version verify
    verify_schema_version(engine)

    # Idempotent re-run
    second_plan = apply_migrations(engine, migrations)
    assert len(second_plan) == 0, "Second migration execution must produce an empty plan"


@postgres_required
@pytest.mark.postgres
def test_schema_migrations_table_has_rls_and_revoked_roles():
    from app.db.session import _sqlalchemy_url

    engine = create_engine(_sqlalchemy_url(POSTGRES_URL), poolclass=NullPool)
    with engine.connect() as conn:
        # Check row level security is enabled
        rls_res = conn.execute(
            text(
                """
                SELECT relrowsecurity
                FROM pg_class
                WHERE relname = 'schema_migrations'
                """
            )
        ).scalar()
        assert rls_res is True, "RLS must be enabled on schema_migrations table"

        # Check privileges revoked from anon and authenticated
        priv_res = conn.execute(
            text(
                """
                SELECT grantee, privilege_type
                FROM information_schema.role_table_grants
                WHERE table_name = 'schema_migrations'
                  AND grantee IN ('anon', 'authenticated')
                """
            )
        ).all()
        assert len(priv_res) == 0, f"Expected 0 privileges for anon/authenticated on schema_migrations, found {priv_res}"


@postgres_required
@pytest.mark.postgres
def test_migration_advisory_locking():
    from app.db.migrations import MIGRATION_LOCK_KEY
    from app.db.session import _sqlalchemy_url

    engine = create_engine(_sqlalchemy_url(POSTGRES_URL), poolclass=NullPool)
    with engine.connect() as conn1, engine.connect() as conn2:
        # Acquire lock in session 1
        locked1 = conn1.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": MIGRATION_LOCK_KEY}).scalar()
        assert locked1 is True, "Session 1 should acquire advisory lock"

        # Session 2 try lock should return False
        locked2 = conn2.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": MIGRATION_LOCK_KEY}).scalar()
        assert locked2 is False, "Session 2 should be rejected while session 1 holds lock"

        # Release lock in session 1
        conn1.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK_KEY})

        # Session 2 should now succeed
        locked2_retry = conn2.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": MIGRATION_LOCK_KEY}).scalar()
        assert locked2_retry is True, "Session 2 should acquire lock after session 1 releases"
        conn2.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK_KEY})

