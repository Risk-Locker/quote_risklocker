"""Trusted client addressing and durable rate-limit HTTP behavior."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient


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

from app.core.client_address import resolve_client_ip
from app.core.rate_limit import RateLimitMiddleware, RateLimitResult, policy_for_request


def settings():
    return SimpleNamespace(
        trusted_proxy_ips=("10.0.0.0/24",),
        auth_hash_secret="test-auth-hash-secret-that-is-long-enough",
        session_cookie_name="risklocker_session",
        rate_limit_login_attempts=5,
        rate_limit_login_window_seconds=900,
        rate_limit_login_block_seconds=1800,
        rate_limit_upload_attempts=20,
        rate_limit_upload_window_seconds=3600,
        rate_limit_preview_attempts=30,
        rate_limit_preview_window_seconds=60,
        rate_limit_generation_attempts=10,
        rate_limit_generation_window_seconds=3600,
        rate_limit_download_attempts=120,
        rate_limit_download_window_seconds=60,
        rate_limit_import_attempts=5,
        rate_limit_import_window_seconds=3600,
    )


def test_forwarded_client_ip_is_used_only_from_configured_proxies():
    assert resolve_client_ip("203.0.113.9", "198.51.100.7", ("10.0.0.0/24",)) == "203.0.113.9"
    assert resolve_client_ip("10.0.0.2", "198.51.100.7, 10.0.0.1", ("10.0.0.0/24",)) == "198.51.100.7"
    assert resolve_client_ip("10.0.0.2", "not-an-ip", ("10.0.0.0/24",)) == "10.0.0.2"


def test_route_policies_cover_every_locked_expensive_surface():
    configured = settings()
    assert policy_for_request("POST", "/api/auth/login", configured).scope == "login"
    assert policy_for_request("POST", "/api/uploads", configured).scope == "upload"
    assert policy_for_request("POST", "/api/drafts/d1/preview-png", configured).scope == "preview"
    assert policy_for_request("POST", "/api/sessions/s1/versions", configured).scope == "generation"
    assert policy_for_request("GET", "/api/versions/v1/pdf", configured).scope == "download"
    assert policy_for_request("POST", "/api/business/catalogs/import", configured).scope == "import"
    assert policy_for_request("GET", "/api/sessions", configured) is None


def test_rate_limit_response_has_retry_after_and_does_not_call_endpoint():
    calls = {"endpoint": 0, "consumer": 0}
    blocked_until = datetime.now(timezone.utc) + timedelta(seconds=37)

    def consumer(_db, _scope, _key_hash, _policy):
        calls["consumer"] += 1
        return RateLimitResult(allowed=False, remaining=0, retry_after=37, blocked_until=blocked_until)

    class DbContext:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        settings=settings(),
        session_factory=DbContext,
        consumer=consumer,
    )

    @app.post("/api/auth/login")
    def login():
        calls["endpoint"] += 1
        return {"ok": True}

    response = TestClient(app).post("/api/auth/login")

    assert response.status_code == 429
    assert response.headers["retry-after"] == "37"
    assert response.json()["error"]["code"] == "rate_limited"
    assert calls == {"endpoint": 0, "consumer": 1}
