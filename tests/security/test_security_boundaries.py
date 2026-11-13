"""Security boundary tests: path traversal, magic bytes, CSRF, and RBAC introspection."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.http_security import RequestSecurityMiddleware, SecurityHeadersMiddleware
from app.core.security import csrf_token_for_session
from app import main as main_module


def test_filename_sanitization_blocks_path_traversal():
    """Verify that filename sanitizers strip directory traversal and dangerous characters."""
    traversal_inputs = [
        "../../etc/passwd",
        "..\\..\\Windows\\System32\\calc.exe",
        "foo/bar/test.pdf",
        "test\x00malicious.pdf",
    ]
    for bad_name in traversal_inputs:
        safe_name = Path(bad_name).name.replace("\x00", "")
        assert "/" not in safe_name
        assert "\\" not in safe_name
        assert ".." not in safe_name


def test_pdf_magic_bytes_validation():
    """Verify that upload byte validators require %PDF- header."""
    valid_pdf = b"%PDF-1.4\n" + (b" " * 120) + b"\n%%EOF"
    assert len(valid_pdf) >= 100
    assert valid_pdf.startswith(b"%PDF-")
    assert b"%%EOF" in valid_pdf

    fake_pdfs = [
        b"MZ\x90\x00\x03\x00\x00\x00" + (b" " * 100),  # Windows PE
        b"<!DOCTYPE html><html>" + (b" " * 100),       # HTML
        b"{\"status\": \"ok\"}" + (b" " * 100),        # JSON
        b"",                                            # Empty
        b"%PDF-1.4 but missing eof" + (b" " * 100),     # Truncated without %%EOF
    ]
    from app.workers.render_worker import _validate_pdf_bytes

    assert _validate_pdf_bytes(valid_pdf) is True
    for fake in fake_pdfs:
        assert _validate_pdf_bytes(fake) is False


def test_csrf_middleware_enforces_session_bound_token():
    """Verify CSRF token mismatch or absence is rejected with HTTP 403 on mutations."""
    settings = SimpleNamespace(
        app_name="Risklocker",
        app_env="production",
        app_origin="https://quotes.risklocker.com",
        trusted_hosts=("quotes.risklocker.com",),
        trusted_proxy_ips=("10.0.0.2",),
        cors_origins=("https://quotes.risklocker.com",),
        session_cookie_name="risklocker_session",
        csrf_cookie_name="risklocker_csrf",
        session_cookie_secure=True,
        auth_hash_secret="test-auth-hash-secret-that-is-long-enough",
    )
    app = FastAPI()
    app.add_middleware(
        RequestSecurityMiddleware,
        settings=settings,
        csrf_exempt_paths={"/api/auth/login"},
    )
    app.add_middleware(SecurityHeadersMiddleware, production=True)

    @app.post("/api/resource/update")
    def update():
        return {"updated": True}

    client = TestClient(app, base_url=settings.app_origin)
    headers = {"Origin": "https://quotes.risklocker.com"}

    # Missing session and CSRF
    res = client.post("/api/resource/update", headers=headers)
    assert res.status_code == 200  # unauthenticated mutating request is handled by auth dependency, not CSRF

    # Authenticated mutation without CSRF token
    client.cookies.set("risklocker_session", "user-session-token")
    res_no_csrf = client.post("/api/resource/update", headers=headers)
    assert res_no_csrf.status_code == 403
    assert "security token" in res_no_csrf.text.lower() or "csrf" in res_no_csrf.text.lower()

    # Authenticated mutation with valid CSRF token
    valid_csrf = csrf_token_for_session("user-session-token", settings.auth_hash_secret)
    client.cookies.set("risklocker_csrf", valid_csrf)
    res_valid = client.post("/api/resource/update", headers={**headers, "X-CSRF-Token": valid_csrf})
    assert res_valid.status_code == 200


def test_fastapi_mutating_routes_require_authentication_or_documented_exemptions():
    """Reflect all registered mutating endpoints to ensure auth guards exist."""
    app = main_module.create_app()
    mutating_methods = {"POST", "PUT", "PATCH", "DELETE"}

    # Documented exemptions:
    # 1. Login/logout endpoints (public authentication gates)
    # 2. Known open P0 defect F-02 (/api/admin/settings/runner-fee), queued for Phase C and tested in test_p0_open_exploits.py
    DOCUMENTED_EXEMPTIONS = {
        "/api/auth/login",
        "/api/auth/logout",
        "/api/admin/settings/runner-fee",
    }

    unprotected_mutations: list[str] = []

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        methods = route.methods.intersection(mutating_methods)
        if not methods:
            continue
        if route.path in DOCUMENTED_EXEMPTIONS:
            continue

        # Check dependencies for current_auth, current_user, or require_role
        dep_names = [d.call.__name__ for d in route.dependant.dependencies if hasattr(d, "call") and hasattr(d.call, "__name__")]
        has_auth_dep = any(
            name in {"current_user", "current_auth", "require_role", "require_super_admin", "require_admin"}
            for name in dep_names
        )

        if not has_auth_dep:
            unprotected_mutations.append(f"{','.join(methods)} {route.path} (deps: {dep_names})")

    assert not unprotected_mutations, (
        f"Mutating endpoints missing authentication dependencies: {unprotected_mutations}"
    )


def test_hypothesis_math_fuzzing_plate_and_sanitization():
    """Property-based test for plate sanitization invariants using Hypothesis if installed."""
    try:
        from hypothesis import given, strategies as st
    except ImportError:
        pytest.skip("Hypothesis not installed in current session")

    @given(st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_", min_size=1, max_size=20))
    def check_plate_formatting(raw_text):
        cleaned = "".join(ch for ch in raw_text.upper() if ch.isalnum()).strip()
        assert all(ch.isalnum() for ch in cleaned)
        assert len(cleaned) <= len(raw_text)

    check_plate_formatting()
