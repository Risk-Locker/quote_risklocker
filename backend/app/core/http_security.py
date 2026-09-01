"""Central HTTP boundary protections for the API."""

from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.security import csrf_token_for_session


SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class RequestSecurityMiddleware(BaseHTTPMiddleware):
    """Enforce same-origin mutations and session-bound double-submit CSRF."""

    def __init__(self, app, *, settings, csrf_exempt_paths: set[str] | None = None):
        super().__init__(app)
        self.settings = settings
        self.csrf_exempt_paths = frozenset(csrf_exempt_paths or set())

    @staticmethod
    def _reject(message: str) -> JSONResponse:
        return JSONResponse(status_code=403, content={"error": {"code": "forbidden", "message": message}})

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method.upper() not in SAFE_METHODS:
            origin = (request.headers.get("origin") or "").rstrip("/")
            if origin:
                if origin not in self.settings.cors_origins:
                    print(f"DEBUG: Rejected origin {origin!r}. Allowed: {self.settings.cors_origins}", flush=True)
                    return self._reject("This request origin is not allowed.")
            elif self.settings.app_env == "production":
                return self._reject("This request origin is not allowed.")

            session_token = request.cookies.get(self.settings.session_cookie_name, "")
            if session_token and request.url.path not in self.csrf_exempt_paths:
                cookie_name = getattr(self.settings, "csrf_cookie_name", "risklocker_csrf")
                cookie_token = request.cookies.get(cookie_name, "")
                header_token = request.headers.get("x-csrf-token", "")
                expected = csrf_token_for_session(session_token, self.settings.auth_hash_secret)
                if (
                    not cookie_token
                    or not header_token
                    or not hmac.compare_digest(cookie_token, header_token)
                    or not hmac.compare_digest(header_token, expected)
                ):
                    return self._reject("The security token is missing or invalid. Refresh and try again.")

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach security headers to success and error responses."""

    def __init__(self, app, *, production: bool):
        super().__init__(app)
        self.production = production

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'self'"
        )
        if self.production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
