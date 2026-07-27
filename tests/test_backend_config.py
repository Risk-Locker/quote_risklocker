import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings


BASE_ENV = {
    "APP_ENV": "local",
    "DATABASE_PROVIDER": "supabase_postgres",
    "AUTH_HASH_SECRET": "test-secret-value-that-is-long-enough",
    "STORAGE_DRIVER": "supabase",
    "SUPABASE_URL": "https://project-ref.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
}


def test_backend_database_url_is_required():
    with patch.dict(os.environ, BASE_ENV, clear=True):
        with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
            get_settings()


def test_backend_database_url_rejects_sqlite():
    env = {**BASE_ENV, "DATABASE_URL": "sqlite:///./storage/risklocker-local.db"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(RuntimeError, match="SQLite is not supported"):
            get_settings()


def test_backend_database_url_accepts_supabase_postgres():
    env = {
        **BASE_ENV,
        "DATABASE_URL": "postgresql://postgres:password@db.project-ref.supabase.co:5432/postgres?sslmode=require",
    }
    with patch.dict(os.environ, env, clear=True):
        settings = get_settings()
    assert settings.database_provider == "supabase_postgres"
    assert settings.database_url.startswith("postgresql://")
    assert settings.storage_driver == "supabase"


def test_backend_database_provider_rejects_unknown_provider():
    env = {
        **BASE_ENV,
        "DATABASE_PROVIDER": "sqlite",
        "DATABASE_URL": "postgresql://postgres:password@db.project-ref.supabase.co:5432/postgres?sslmode=require",
    }
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(RuntimeError, match="DATABASE_PROVIDER must be"):
            get_settings()


def test_backend_test_env_uses_explicit_test_database_url():
    env = {
        **BASE_ENV,
        "APP_ENV": "test",
        "DATABASE_URL": "postgresql://postgres:password@db.production.supabase.co:5432/postgres?sslmode=require",
        "TEST_DATABASE_URL": "postgresql://postgres:password@db.test.supabase.co:5432/postgres?sslmode=require",
    }
    with patch.dict(os.environ, env, clear=True):
        settings = get_settings()
    assert "db.test.supabase.co" in settings.database_url


def test_backend_auth_hash_secret_is_required():
    env = {
        key: value
        for key, value in {
            **BASE_ENV,
            "DATABASE_URL": "postgresql://postgres:password@db.project-ref.supabase.co:5432/postgres?sslmode=require",
        }.items()
        if key != "AUTH_HASH_SECRET"
    }
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(RuntimeError, match="AUTH_HASH_SECRET is required"):
            get_settings()


def test_backend_production_rejects_placeholder_auth_hash_secret():
    env = {
        **BASE_ENV,
        "APP_ENV": "production",
        "DATABASE_URL": "postgresql://postgres:password@db.project-ref.supabase.co:5432/postgres?sslmode=require",
        "AUTH_HASH_SECRET": "replace_me_with_a_long_random_string",
    }
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(RuntimeError, match="AUTH_HASH_SECRET must be changed"):
            get_settings()


def test_backend_production_requires_secure_cookie():
    base = {
        **BASE_ENV,
        "APP_ENV": "production",
        "DATABASE_URL": "postgresql://postgres:password@db.project-ref.supabase.co:5432/postgres?sslmode=require",
        "AUTH_HASH_SECRET": "a-production-auth-hash-secret-that-is-long-enough",
    }
    with patch.dict(os.environ, base, clear=True):
        settings = get_settings()
    assert settings.session_cookie_secure is True

    insecure = {**base, "SESSION_COOKIE_SECURE": "false"}
    with patch.dict(os.environ, insecure, clear=True):
        with pytest.raises(RuntimeError, match="SESSION_COOKIE_SECURE"):
            get_settings()


def test_session_policy_is_fixed_at_eight_hours_and_thirty_days():
    env = {
        **BASE_ENV,
        "DATABASE_URL": "postgresql://postgres:password@db.project-ref.supabase.co:5432/postgres?sslmode=require",
        "SESSION_IDLE_HOURS": "7",
    }
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(RuntimeError, match="SESSION_IDLE_HOURS=8"):
            get_settings()
