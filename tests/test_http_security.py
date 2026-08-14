"""HTTP boundary regressions for headers, origin checks, and CSRF."""

from __future__ import annotations

import os
import sys
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

from app import main as main_module
from app.api.deps import settings_dep
from app.core.http_security import RequestSecurityMiddleware, SecurityHeadersMiddleware
from app.core.security import csrf_token_for_session


def security_settings(**overrides):
    values = {
        "app_name": "Risklocker",
        "app_env": "production",
        "app_origin": "https://quotes.risklocker.com",
        "trusted_hosts": ("quotes.risklocker.com",),
        "trusted_proxy_ips": ("10.0.0.2",),
        "cors_origins": ("https://quotes.risklocker.com",),
        "session_cookie_name": "risklocker_session",
        "csrf_cookie_name": "risklocker_csrf",
        "session_cookie_secure": True,
        "auth_hash_secret": "test-auth-hash-secret-that-is-long-enough",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def csrf_app() -> TestClient:
    settings = security_settings()
    app = FastAPI()
    app.add_middleware(
        RequestSecurityMiddleware,
        settings=settings,
        csrf_exempt_paths={"/api/auth/login"},
    )
    app.add_middleware(SecurityHeadersMiddleware, production=True)

    @app.get("/api/value")
    def read_value():
        return {"ok": True}

    @app.post("/api/value")
    def change_value():
        return {"ok": True}

    @app.post("/api/auth/login")
    def login():
        return {"ok": True}

    return TestClient(app, base_url=settings.app_origin)


def test_csrf_token_is_session_bound_and_required_for_authenticated_mutations():
    client = csrf_app()
    origin = {"Origin": "https://quotes.risklocker.com"}
    client.cookies.set("risklocker_session", "session-a")

    missing = client.post("/api/value", headers=origin)
    wrong = client.post(
        "/api/value",
        headers={**origin, "X-CSRF-Token": "wrong"},
        cookies={"risklocker_csrf": "wrong"},
    )
    token = csrf_token_for_session("session-a", "test-auth-hash-secret-that-is-long-enough")
    accepted = client.post(
        "/api/value",
        headers={**origin, "X-CSRF-Token": token},
        cookies={"risklocker_csrf": token},
    )

    assert missing.status_code == 403
    assert wrong.status_code == 403
    assert accepted.status_code == 200
    assert token != csrf_token_for_session("session-b", "test-auth-hash-secret-that-is-long-enough")


def test_login_is_csrf_exempt_but_still_requires_the_trusted_origin():
    client = csrf_app()

    trusted = client.post("/api/auth/login", headers={"Origin": "https://quotes.risklocker.com"})
    untrusted = client.post("/api/auth/login", headers={"Origin": "https://attacker.example"})
    missing = client.post("/api/auth/login")

    assert trusted.status_code == 200
    assert untrusted.status_code == 403
    assert missing.status_code == 403


def test_security_headers_cover_success_and_rejection_responses():
    client = csrf_app()

    success = client.get("/api/value")
    rejected = client.post("/api/value", headers={"Origin": "https://attacker.example"})

    for response in (success, rejected):
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "SAMEORIGIN"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert "frame-ancestors 'self'" in response.headers["content-security-policy"]
        assert response.headers["strict-transport-security"].startswith("max-age=")


def test_production_factory_exposes_only_api_and_rejects_unknown_hosts(monkeypatch):
    settings = security_settings()
    monkeypatch.setattr(main_module, "get_settings", lambda: settings)
    app = main_module.create_app()
    app.dependency_overrides[settings_dep] = lambda: settings
    client = TestClient(app, base_url=settings.app_origin)

    assert client.get("/health").status_code == 404
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert client.get("/api/health", headers={"Host": "attacker.example"}).status_code == 400
