"""Runtime configuration for the backend app."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    database_provider: str
    database_url: str
    storage_driver: str
    supabase_url: str
    supabase_service_role_key: str
    supabase_storage_bucket: str
    pdf_retention_days: int
    require_malware_scanner: bool
    max_upload_bytes: int
    auth_hash_secret: str
    session_idle_hours: int
    session_max_days: int
    session_cookie_name: str
    session_cookie_secure: bool
    trash_retention_days: int
    cors_origins: tuple[str, ...]
    super_admin_email: str | None
    super_admin_password: str | None


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


def _database_url(app_env: str) -> str:
    env_name = "TEST_DATABASE_URL" if app_env == "test" and os.getenv("TEST_DATABASE_URL") else "DATABASE_URL"
    database_url = os.getenv(env_name, "").strip()
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is required. Set it to a Supabase/Postgres connection string before starting the app."
        )
    lowered = database_url.lower()
    if lowered.startswith("sqlite"):
        raise RuntimeError("SQLite is not supported. Use a Supabase/Postgres DATABASE_URL.")
    if not lowered.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("DATABASE_URL must be a Supabase/Postgres connection string.")
    return database_url


def _database_provider() -> str:
    provider = os.getenv("DATABASE_PROVIDER", "supabase_postgres").strip()
    if provider not in {"supabase_postgres", "postgres"}:
        raise RuntimeError("DATABASE_PROVIDER must be either 'supabase_postgres' or 'postgres'.")
    return provider


def _auth_hash_secret(app_env: str) -> str:
    secret = os.getenv("AUTH_HASH_SECRET", "").strip()
    if not secret:
        raise RuntimeError("AUTH_HASH_SECRET is required.")
    placeholders = {"replace_me_with_a_long_random_string", "change_me_to_a_long_random_secret", "local-development-change-me"}
    if app_env == "production" and (secret.lower() in placeholders or len(secret) < 32):
        raise RuntimeError("AUTH_HASH_SECRET must be changed to a long random value before production startup.")
    return secret


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required.")
    return value


def _storage_settings() -> tuple[str, str, str, str]:
    driver = os.getenv("STORAGE_DRIVER", "supabase").strip().lower()
    if driver != "supabase":
        raise RuntimeError("STORAGE_DRIVER must be 'supabase'. Persistent local PDF storage is not supported.")
    url = _required("SUPABASE_URL").rstrip("/")
    if not url.lower().startswith("https://"):
        raise RuntimeError("SUPABASE_URL must be an HTTPS Supabase project URL.")
    service_key = _required("SUPABASE_SERVICE_ROLE_KEY")
    bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "risklocker-pdfs").strip()
    if not bucket or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for ch in bucket.lower()):
        raise RuntimeError("SUPABASE_STORAGE_BUCKET must use letters, numbers, hyphens, or underscores.")
    return driver, url, service_key, bucket


def get_settings() -> Settings:
    app_env = os.getenv("APP_ENV", "local").strip().lower()
    database_url = _database_url(app_env)
    storage_driver, supabase_url, service_key, storage_bucket = _storage_settings()
    origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    retention_days = _int("PDF_RETENTION_DAYS", 30)
    max_upload_bytes = _int("MAX_UPLOAD_BYTES", 1024 * 1024)
    session_idle_hours = _int("SESSION_IDLE_HOURS", 8)
    session_max_days = _int("SESSION_MAX_DAYS", 30)
    session_cookie_secure = _bool("SESSION_COOKIE_SECURE", app_env == "production")
    if retention_days < 1 or retention_days > 365:
        raise RuntimeError("PDF_RETENTION_DAYS must be between 1 and 365.")
    if max_upload_bytes < 1024 or max_upload_bytes > 10 * 1024 * 1024:
        raise RuntimeError("MAX_UPLOAD_BYTES must be between 1KB and 10MB.")
    if session_idle_hours != 8 or session_max_days != 30:
        raise RuntimeError("Risklocker sessions require SESSION_IDLE_HOURS=8 and SESSION_MAX_DAYS=30.")
    if app_env == "production" and not session_cookie_secure:
        raise RuntimeError("SESSION_COOKIE_SECURE must be enabled in production.")
    return Settings(
        app_name=os.getenv("APP_NAME", "Risklocker Quotation Converter"),
        app_env=app_env,
        database_provider=_database_provider(),
        database_url=database_url,
        storage_driver=storage_driver,
        supabase_url=supabase_url,
        supabase_service_role_key=service_key,
        supabase_storage_bucket=storage_bucket,
        pdf_retention_days=retention_days,
        require_malware_scanner=_bool("REQUIRE_MALWARE_SCANNER", app_env == "production"),
        max_upload_bytes=max_upload_bytes,
        auth_hash_secret=_auth_hash_secret(app_env),
        session_idle_hours=session_idle_hours,
        session_max_days=session_max_days,
        session_cookie_name=os.getenv("SESSION_COOKIE_NAME", "risklocker_session").strip() or "risklocker_session",
        session_cookie_secure=session_cookie_secure,
        trash_retention_days=_int("TRASH_RETENTION_DAYS", 14),
        cors_origins=tuple(origin.strip().rstrip("/") for origin in origins.split(",") if origin.strip()),
        super_admin_email=os.getenv("SUPER_ADMIN_EMAIL", "").strip() or None,
        super_admin_password=os.getenv("SUPER_ADMIN_PASSWORD", "").strip() or None,
    )
