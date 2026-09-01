"""Ordered, checksummed Postgres migration planning and execution."""

from __future__ import annotations

import argparse
import hashlib
import re
import time
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

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
    equivalent_checksums: frozenset[str] = frozenset()


@dataclass(frozen=True)
class AppliedMigration:
    version: int
    name: str
    checksum: str


def _normalize_line_endings(data: bytes) -> bytes:
    """Normalize CRLF and lone CR line endings to LF (stable cross-platform checksums)."""
    return re.sub(rb"\r\n|\r", b"\n", data)


def migration_checksums(data: bytes) -> tuple[str, frozenset[str]]:
    """Return (canonical line-ending-normalized checksum, equivalent checksums).

    The canonical checksum is hashed from line-ending-normalized bytes, so the
    same SQL yields the same checksum on Windows/Linux/macOS and under any git
    checkout style. The equivalence set additionally contains the CRLF byte
    representation, which is what older ledgers recorded when migrations were
    applied from CRLF checkouts. Only line-ending variants of the identical
    content are accepted; any genuine content change produces a new canonical
    hash and therefore fails drift detection.
    """
    canonical = _normalize_line_endings(data)
    canonical_hash = hashlib.sha256(canonical).hexdigest()
    crlf_hash = hashlib.sha256(canonical.replace(b"\n", b"\r\n")).hexdigest()
    return canonical_hash, frozenset({canonical_hash, crlf_hash})


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
        data = path.read_bytes()
        checksum, equivalent_checksums = migration_checksums(data)
        migrations.append(
            Migration(
                version=version,
                name=path.name,
                path=path,
                checksum=checksum,
                equivalent_checksums=equivalent_checksums,
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
        if history.name != source.name:
            raise MigrationError(f"Migration {history.version:03d} checksum/name drift detected.")
        if history.checksum not in source.equivalent_checksums:
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


def connect_with_retry(
    engine: Engine,
    *,
    max_attempts: int = 15,
    initial_delay: float = 2.0,
    max_delay: float = 10.0,
    backoff_factor: float = 1.5,
) -> Connection:
    """Connect to the database with exponential backoff on transient connection failures or pool exhaustion (e.g. EMAXCONNSESSION)."""
    delay = initial_delay
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return engine.connect()
        except SQLAlchemyError as exc:
            last_error = exc
            if attempt == max_attempts:
                break
            err_msg = str(exc).strip().replace("\n", " ")
            if len(err_msg) > 160:
                err_msg = err_msg[:157] + "..."
            print(
                f"[db:migrations] Database connection busy or pool limit reached ({err_msg}). "
                f"Retrying in {delay:.1f}s (attempt {attempt}/{max_attempts})...",
                flush=True,
            )
            time.sleep(delay)
            delay = min(delay * backoff_factor, max_delay)
    if last_error:
        raise last_error
    raise RuntimeError("Failed to connect to database after retries.")


def apply_migrations(
    engine: Engine,
    migrations: list[Migration],
    *,
    dry_run: bool = False,
    max_connect_attempts: int = 15,
) -> list[Migration]:
    with connect_with_retry(engine, max_attempts=max_connect_attempts) as connection:
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
    parser.add_argument(
        "--allow-local",
        action="store_true",
        help="Explicitly allow running against a non-production database (local development only).",
    )
    args = parser.parse_args()
    settings = get_settings()
    if settings.app_env != "production" and not args.allow_local:
        raise SystemExit(
            "Refusing to run migrations: APP_ENV=%s is not production. Migrations must run from the "
            "production deploy (the VPS) so the database never drifts ahead of deployed code. "
            "Re-run with --allow-local only when intentionally migrating a local/development database."
            % settings.app_env
        )
    engine = create_engine(
        _sqlalchemy_url(settings.database_url),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    plan = apply_migrations(engine, discover_migrations(args.root), dry_run=args.dry_run)
    verb = "Would apply" if args.dry_run else "Applied"
    for migration in plan:
        print(f"{verb} {migration.name}")
    if not plan:
        print("Schema is current.")


if __name__ == "__main__":
    main()
