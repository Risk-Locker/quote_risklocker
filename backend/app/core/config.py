"""Runtime configuration for the backend app."""

from __future__ import annotations

import os
from ipaddress import ip_network
from dataclasses import dataclass
from urllib.parse import urlsplit

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    app_origin: str
    trusted_hosts: tuple[str, ...]
    trusted_proxy_ips: tuple[str, ...]
    database_provider: str
    database_url: str
    storage_driver: str
    supabase_url: str
    supabase_service_role_key: str
    supabase_storage_bucket: str
    pdf_retention_days: int
    require_malware_scanner: bool
    max_upload_files: int
    max_source_pdf_bytes: int
    max_pdf_pages: int
    max_generated_pdf_bytes: int
    max_asset_bytes: int
    max_asset_pixels: int
    max_catalog_import_bytes: int
    max_catalog_import_rows: int
    max_template_json_bytes: int
    max_template_elements: int
    rate_limit_login_attempts: int
    rate_limit_login_window_seconds: int
    rate_limit_login_block_seconds: int
    rate_limit_upload_attempts: int
    rate_limit_upload_window_seconds: int
    rate_limit_preview_attempts: int
    rate_limit_preview_window_seconds: int
    rate_limit_generation_attempts: int
    rate_limit_generation_window_seconds: int
    rate_limit_download_attempts: int
    rate_limit_download_window_seconds: int
    rate_limit_import_attempts: int
    rate_limit_import_window_seconds: int
    auth_hash_secret: str
    session_idle_hours: int
    session_max_days: int
    session_cookie_name: str
    csrf_cookie_name: str
    session_cookie_secure: bool
    trash_retention_days: int
    cors_origins: tuple[str, ...]
    gemini_api_keys: tuple[str, ...] = ()
    gemini_model: str = "gemini-3.1-flash-lite-preview"

    @property
    def max_upload_bytes(self) -> int:
        """RL-DISABLED shared upload limit — disabled 2026-08-13; compatibility alias until callers use typed limits."""

        return self.max_source_pdf_bytes


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be a boolean (true/false).")


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    value = _int(name, default)
    if value < minimum or value > maximum:
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}.")
    return value


def _app_environment() -> str:
    app_env = os.getenv("APP_ENV", "local").strip().lower()
    allowed = {"local", "test", "staging", "production"}
    if app_env not in allowed:
        raise RuntimeError(f"APP_ENV must be one of: {', '.join(sorted(allowed))}.")
    return app_env


def _app_network_settings(app_env: str) -> tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    raw_origin = os.getenv("APP_ORIGIN", "").strip().rstrip("/")
    if not raw_origin:
        if app_env == "production":
            raise RuntimeError("APP_ORIGIN is required in production.")
        raw_origin = "http://localhost:3000"

    parsed = urlsplit(raw_origin)
    if not parsed.scheme or not parsed.hostname or parsed.username or parsed.password:
        raise RuntimeError("APP_ORIGIN must be an absolute HTTP(S) origin without credentials.")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise RuntimeError("APP_ORIGIN must not contain a path, query, or fragment.")
    if app_env == "production" and parsed.scheme.lower() != "https":
        raise RuntimeError("APP_ORIGIN must use HTTPS in production.")
    if parsed.scheme.lower() not in {"http", "https"}:
        raise RuntimeError("APP_ORIGIN must use HTTP or HTTPS.")

    raw_hosts = os.getenv("TRUSTED_HOSTS", "").strip()
    if app_env == "production" and not raw_hosts:
        raise RuntimeError("TRUSTED_HOSTS is required in production.")
    hosts = tuple(part.strip().lower() for part in raw_hosts.split(",") if part.strip())
    if not hosts:
        hosts = (parsed.hostname.lower(), "localhost", "127.0.0.1", "testserver")
    if "*" in hosts:
        raise RuntimeError("TRUSTED_HOSTS must not contain a wildcard.")
    if parsed.hostname.lower() not in hosts:
        raise RuntimeError("TRUSTED_HOSTS must include the APP_ORIGIN hostname.")

    raw_proxies = os.getenv("TRUSTED_PROXY_IPS", "").strip()
    if app_env == "production" and not raw_proxies:
        raise RuntimeError("TRUSTED_PROXY_IPS is required in production.")
    proxies = tuple(part.strip() for part in raw_proxies.split(",") if part.strip())
    for proxy in proxies:
        try:
            network = ip_network(proxy, strict=False)
        except ValueError as exc:
            raise RuntimeError("TRUSTED_PROXY_IPS must contain only IP addresses or CIDR ranges.") from exc
        if network.prefixlen == 0:
            raise RuntimeError("TRUSTED_PROXY_IPS must not trust the entire internet.")

    raw_origins = os.getenv("CORS_ORIGINS", "").strip()
    origins = tuple(origin.strip().rstrip("/") for origin in raw_origins.split(",") if origin.strip())
    if not origins:
        origins = (raw_origin,) if app_env in {"staging", "production"} else tuple(
            dict.fromkeys((raw_origin, "http://localhost:3000", "http://127.0.0.1:3000"))
        )
    if app_env == "production" and any(origin != raw_origin for origin in origins):
        raise RuntimeError("CORS_ORIGINS must use the same origin as APP_ORIGIN in production.")
    return raw_origin, hosts, proxies, origins


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


def _database_provider(database_url: str) -> str:
    provider = os.getenv("DATABASE_PROVIDER", "").strip().lower()
    if provider:
        if provider not in {"supabase_postgres", "postgres"}:
            raise RuntimeError("DATABASE_PROVIDER must be either 'supabase_postgres' or 'postgres'.")
        return provider
    # Auto-detect from the connection string so switching DB servers is just a DATABASE_URL change.
    return "supabase_postgres" if "supabase" in database_url.lower() else "postgres"


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
    app_env = _app_environment()
    database_url = _database_url(app_env)
    storage_driver, supabase_url, service_key, storage_bucket = _storage_settings()
    app_origin, trusted_hosts, trusted_proxy_ips, origins = _app_network_settings(app_env)
    retention_days = _int("PDF_RETENTION_DAYS", 30)
    max_upload_files = _int("MAX_UPLOAD_FILES", 1)
    source_limit_name = "MAX_SOURCE_PDF_BYTES" if os.getenv("MAX_SOURCE_PDF_BYTES") is not None else "MAX_UPLOAD_BYTES"
    max_source_pdf_bytes = _bounded_int(source_limit_name, 20 * 1024 * 1024, 1024, 100 * 1024 * 1024)
    max_pdf_pages = _bounded_int("MAX_PDF_PAGES", 100, 1, 2_000)
    max_generated_pdf_bytes = _bounded_int("MAX_GENERATED_PDF_BYTES", 25 * 1024 * 1024, 1024, 100 * 1024 * 1024)
    max_asset_bytes = _bounded_int("MAX_ASSET_BYTES", 10 * 1024 * 1024, 1024, 50 * 1024 * 1024)
    max_asset_pixels = _bounded_int("MAX_ASSET_PIXELS", 32_000_000, 1, 100_000_000)
    max_catalog_import_bytes = _bounded_int("MAX_CATALOG_IMPORT_BYTES", 5 * 1024 * 1024, 1024, 20 * 1024 * 1024)
    max_catalog_import_rows = _bounded_int("MAX_CATALOG_IMPORT_ROWS", 5_000, 1, 50_000)
    max_template_json_bytes = _bounded_int("MAX_TEMPLATE_JSON_BYTES", 2 * 1024 * 1024, 1024, 10 * 1024 * 1024)
    max_template_elements = _bounded_int("MAX_TEMPLATE_ELEMENTS", 2_000, 1, 10_000)
    session_idle_hours = _int("SESSION_IDLE_HOURS", 8)
    session_max_days = _int("SESSION_MAX_DAYS", 30)
    session_cookie_secure = _bool("SESSION_COOKIE_SECURE", app_env == "production")
    require_malware_scanner = _bool("REQUIRE_MALWARE_SCANNER", app_env == "production")
    if retention_days < 1 or retention_days > 365:
        raise RuntimeError("PDF_RETENTION_DAYS must be between 1 and 365.")
    if max_upload_files != 1:
        raise RuntimeError("MAX_UPLOAD_FILES must be 1 for the v7 upload contract.")
    if session_idle_hours != 8 or session_max_days != 30:
        raise RuntimeError("Risklocker sessions require SESSION_IDLE_HOURS=8 and SESSION_MAX_DAYS=30.")
    if app_env == "production" and not session_cookie_secure:
        raise RuntimeError("SESSION_COOKIE_SECURE must be enabled in production.")
    if app_env == "production" and not require_malware_scanner:
        raise RuntimeError("REQUIRE_MALWARE_SCANNER must be enabled in production.")
    return Settings(
        app_name=os.getenv("APP_NAME", "Risklocker Quotation Converter"),
        app_env=app_env,
        app_origin=app_origin,
        trusted_hosts=trusted_hosts,
        trusted_proxy_ips=trusted_proxy_ips,
        database_provider=_database_provider(database_url),
        database_url=database_url,
        storage_driver=storage_driver,
        supabase_url=supabase_url,
        supabase_service_role_key=service_key,
        supabase_storage_bucket=storage_bucket,
        pdf_retention_days=retention_days,
        require_malware_scanner=require_malware_scanner,
        max_upload_files=max_upload_files,
        max_source_pdf_bytes=max_source_pdf_bytes,
        max_pdf_pages=max_pdf_pages,
        max_generated_pdf_bytes=max_generated_pdf_bytes,
        max_asset_bytes=max_asset_bytes,
        max_asset_pixels=max_asset_pixels,
        max_catalog_import_bytes=max_catalog_import_bytes,
        max_catalog_import_rows=max_catalog_import_rows,
        max_template_json_bytes=max_template_json_bytes,
        max_template_elements=max_template_elements,
        rate_limit_login_attempts=_bounded_int("RATE_LIMIT_LOGIN_ATTEMPTS", 5, 1, 100),
        rate_limit_login_window_seconds=_bounded_int("RATE_LIMIT_LOGIN_WINDOW_SECONDS", 900, 1, 86_400),
        rate_limit_login_block_seconds=_bounded_int("RATE_LIMIT_LOGIN_BLOCK_SECONDS", 1_800, 1, 86_400),
        rate_limit_upload_attempts=_bounded_int("RATE_LIMIT_UPLOAD_ATTEMPTS", 20, 1, 10_000),
        rate_limit_upload_window_seconds=_bounded_int("RATE_LIMIT_UPLOAD_WINDOW_SECONDS", 3_600, 1, 86_400),
        rate_limit_preview_attempts=_bounded_int("RATE_LIMIT_PREVIEW_ATTEMPTS", 30, 1, 10_000),
        rate_limit_preview_window_seconds=_bounded_int("RATE_LIMIT_PREVIEW_WINDOW_SECONDS", 60, 1, 86_400),
        rate_limit_generation_attempts=_bounded_int("RATE_LIMIT_GENERATION_ATTEMPTS", 10, 1, 10_000),
        rate_limit_generation_window_seconds=_bounded_int("RATE_LIMIT_GENERATION_WINDOW_SECONDS", 3_600, 1, 86_400),
        rate_limit_download_attempts=_bounded_int("RATE_LIMIT_DOWNLOAD_ATTEMPTS", 120, 1, 100_000),
        rate_limit_download_window_seconds=_bounded_int("RATE_LIMIT_DOWNLOAD_WINDOW_SECONDS", 60, 1, 86_400),
        rate_limit_import_attempts=_bounded_int("RATE_LIMIT_IMPORT_ATTEMPTS", 5, 1, 1_000),
        rate_limit_import_window_seconds=_bounded_int("RATE_LIMIT_IMPORT_WINDOW_SECONDS", 3_600, 1, 86_400),
        auth_hash_secret=_auth_hash_secret(app_env),
        session_idle_hours=session_idle_hours,
        session_max_days=session_max_days,
        session_cookie_name=os.getenv("SESSION_COOKIE_NAME", "risklocker_session").strip() or "risklocker_session",
        csrf_cookie_name=os.getenv("CSRF_COOKIE_NAME", "risklocker_csrf").strip() or "risklocker_csrf",
        session_cookie_secure=session_cookie_secure,
        trash_retention_days=_int("TRASH_RETENTION_DAYS", 14),
        cors_origins=origins,
        gemini_api_keys=tuple(
            k.strip() for k in (os.getenv("GEMINI_API_KEYS") or os.getenv("GEMINI_API_KEY") or "").split(",") if k.strip()
        ),
        gemini_model="gemini-3.1-flash-lite-preview" if (os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite-preview").strip() in {"", "gemini-2.0-flash", "gemini-2.5-flash", "gemini-3.6-flash"}) else os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite-preview").strip(),
    )
