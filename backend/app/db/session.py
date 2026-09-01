"""Database engine/session helpers."""

from __future__ import annotations

from collections.abc import Generator

from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from app.core.config import get_settings


settings = get_settings()


def _sqlalchemy_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    return database_url


engine = create_engine(
    _sqlalchemy_url(settings.database_url),
    poolclass=QueuePool,
    pool_size=2,
    max_overflow=2,
    pool_timeout=25,
    pool_recycle=60,
    pool_pre_ping=True,
    connect_args={
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    },
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def verify_database_connection() -> None:
    from app.db.migrations import connect_with_retry

    try:
        with connect_with_retry(engine, max_attempts=8, initial_delay=1.5, max_delay=6.0) as connection:
            connection.execute(text("select 1"))
    except SQLAlchemyError as exc:
        message = str(exc).lower()
        if "password authentication failed" in message:
            raise RuntimeError(
                "Supabase/Postgres database connection failed: password authentication failed for DATABASE_URL. "
                "Use the Supabase database password, not the anon or service-role API key."
            ) from exc
        raise RuntimeError(
            f"Supabase/Postgres database connection failed: {exc}. Check DATABASE_URL, network access, and Supabase database status."
        ) from exc


def verify_schema_version() -> None:
    from app.db.migrations import (
        AppliedMigration,
        MigrationError,
        connect_with_retry,
        discover_migrations,
        validate_schema_history,
    )

    migration_root = Path(__file__).resolve().parents[3] / "migrations"
    migrations = discover_migrations(migration_root)
    with connect_with_retry(engine, max_attempts=8, initial_delay=1.5, max_delay=6.0) as connection:
        if not inspect(connection).has_table("schema_migrations", schema="public"):
            raise RuntimeError("Database schema migration ledger is missing. Run the migration command before startup.")
        rows = connection.execute(
            text("SELECT version, name, checksum FROM public.schema_migrations ORDER BY version")
        ).mappings()
        history = [AppliedMigration(row["version"], row["name"], row["checksum"]) for row in rows]
    try:
        validate_schema_history(migrations, history)
    except MigrationError as exc:
        raise RuntimeError(str(exc)) from exc


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
