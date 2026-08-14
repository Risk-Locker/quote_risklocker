"""Ordered, checksummed Postgres migration planning and execution."""

from __future__ import annotations

import argparse
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Connection, Engine, create_engine, text

from app.core.config import get_settings
from app.db.session import _sqlalchemy_url


MIGRATION_NAME = re.compile(r"^(?P<version>\d{3})_[a-z0-9][a-z0-9_-]*\.sql$")
MIGRATION_LOCK_KEY = 7_621_326_744


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    path: Path
    checksum: str


@dataclass(frozen=True)
class AppliedMigration:
    version: int
    name: str
    checksum: str


def discover_migrations(root: Path) -> list[Migration]:
    migrations: list[Migration] = []
    versions: set[int] = set()
    for path in sorted(root.glob("*.sql"), key=lambda item: item.name):
        match = MIGRATION_NAME.fullmatch(path.name)
        if not match:
            raise MigrationError(f"Invalid migration filename: {path.name}")
        version = int(match.group("version"))
        if version in versions:
            raise MigrationError(f"Migration version {version:03d} is duplicate.")
        versions.add(version)
        migrations.append(
            Migration(
                version=version,
                name=path.name,
                path=path,
                checksum=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
    expected = list(range(1, len(migrations) + 1))
    actual = [item.version for item in migrations]
    if actual != expected:
        raise MigrationError(f"Migration versions must be contiguous from 001; found {actual}.")
    return migrations


def build_plan(migrations: list[Migration], applied: list[AppliedMigration]) -> list[Migration]:
    available = {item.version: item for item in migrations}
    for history in applied:
        source = available.get(history.version)
        if source is None:
            raise MigrationError(
                f"Database migration {history.version:03d} is newer than this release or unknown to it."
            )
        if history.name != source.name or history.checksum != source.checksum:
            raise MigrationError(f"Migration {history.version:03d} checksum/name drift detected.")
    applied_versions = {item.version for item in applied}
    return [item for item in migrations if item.version not in applied_versions]


def validate_schema_history(migrations: list[Migration], applied: list[AppliedMigration]) -> None:
    pending = build_plan(migrations, applied)
    if pending:
        raise MigrationError(
            f"Database schema is behind this release by {len(pending)} migration(s); next is {pending[0].name}."
        )


def default_migration_root() -> Path:
    return Path(__file__).resolve().parents[3] / "migrations"


def _ensure_ledger(connection: Connection) -> None:
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


def _history(connection: Connection) -> list[AppliedMigration]:
    rows = connection.execute(
        text("SELECT version, name, checksum FROM public.schema_migrations ORDER BY version")
    ).mappings()
    return [AppliedMigration(version=row["version"], name=row["name"], checksum=row["checksum"]) for row in rows]


def apply_migrations(engine: Engine, migrations: list[Migration], *, dry_run: bool = False) -> list[Migration]:
    with engine.connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK_KEY})
        try:
            with connection.begin_nested():
                _ensure_ledger(connection)
            connection.commit()
            history = _history(connection)
            connection.commit()
            plan = build_plan(migrations, history)
            if dry_run:
                return plan
            for migration in plan:
                sql = migration.path.read_text(encoding="utf-8")
                with connection.begin():
                    connection.connection.cursor().execute(sql)
                    connection.execute(
                        text(
                            "INSERT INTO public.schema_migrations(version, name, checksum) "
                            "VALUES (:version, :name, :checksum)"
                        ),
                        {"version": migration.version, "name": migration.name, "checksum": migration.checksum},
                    )
            return plan
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK_KEY})
            connection.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply ordered Risklocker Postgres migrations safely.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--root", type=Path, default=default_migration_root())
    args = parser.parse_args()
    settings = get_settings()
    engine = create_engine(_sqlalchemy_url(settings.database_url), pool_pre_ping=True)
    plan = apply_migrations(engine, discover_migrations(args.root), dry_run=args.dry_run)
    verb = "Would apply" if args.dry_run else "Applied"
    for migration in plan:
        print(f"{verb} {migration.name}")
    if not plan:
        print("Schema is current.")


if __name__ == "__main__":
    main()
