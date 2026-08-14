"""Backfill the schema_migrations ledger for migrations applied before the ledger existed.

Use only when the database already has the pre-ledger schema (e.g. migrations
001-022 applied manually) but the schema_migrations table is missing or empty.
Refuses to run when the ledger already contains rows.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import text

from app.core.config import get_settings
from app.db.migrations import MIGRATION_LOCK_KEY, discover_migrations
from app.db.session import engine


def _ledger_row_count(connection) -> int:
    if not engine.dialect.has_table(connection, "schema_migrations", schema="public"):
        return -1
    return connection.execute(text("SELECT count(*) FROM public.schema_migrations")).scalar()


def main() -> None:
    parser = argparse.ArgumentParser(description="Record already-applied migrations in the schema_migrations ledger.")
    parser.add_argument("--upto", type=int, default=22, help="Highest migration version to backfill (default 22).")
    parser.add_argument("--dry-run", action="store_true", help="Print the rows that would be inserted without writing.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1] / "migrations")
    args = parser.parse_args()

    migrations = discover_migrations(args.root)
    targets = [item for item in migrations if item.version <= args.upto]
    if not targets:
        raise SystemExit(f"No migrations with version <= {args.upto} found.")
    if args.upto > 22:
        print(f"WARNING: backfilling past version 22 ({args.upto}) marks newer migrations as applied without running them.")

    with engine.connect() as connection:
        existing = _ledger_row_count(connection)
        if existing > 0:
            raise SystemExit(f"Refusing to backfill: schema_migrations already has {existing} row(s).")
        print("Migrations to record in the ledger:")
        for item in targets:
            print(f"  {item.version:03d}  {item.name}  {item.checksum[:12]}")
        if args.dry_run:
            print(f"Dry run: {len(targets)} row(s) would be inserted. Ledger currently {('missing' if existing < 0 else 'empty')}.")
            return

        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK_KEY})
        try:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS public.schema_migrations (
                        version INTEGER PRIMARY KEY,
                        name TEXT NOT NULL UNIQUE,
                        checksum CHAR(64) NOT NULL,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            connection.execute(text("REVOKE ALL PRIVILEGES ON TABLE public.schema_migrations FROM anon, authenticated"))
            connection.execute(text("ALTER TABLE public.schema_migrations ENABLE ROW LEVEL SECURITY"))
            connection.execute(
                text(
                    "INSERT INTO public.schema_migrations(version, name, checksum) VALUES (:version, :name, :checksum)"
                ),
                [{"version": item.version, "name": item.name, "checksum": item.checksum} for item in targets],
            )
            connection.commit()
            print(f"Backfilled {len(targets)} ledger row(s) up to version {args.upto:03d}.")
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK_KEY})
            connection.commit()


if __name__ == "__main__":
    main()
