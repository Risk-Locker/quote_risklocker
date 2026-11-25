"""Central HTTP boundary protections for the API (pure ASGI for SSE/streaming safety)."""

from __future__ import annotations

import hmac

from fastapi.responses import JSONResponse
from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import cookie_parser

from app.core.security import csrf_token_for_session


SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class RequestSecurityMiddleware:
    """Enforce same-origin mutations and session-bound double-submit CSRF."""

    def __init__(self, app, *, settings, csrf_exempt_paths: set[str] | None = None):
        self.app = app
        self.settings = settings
        self.csrf_exempt_paths = frozenset(csrf_exempt_paths or set())

    @staticmethod
    def _reject(message: str) -> JSONResponse:
        return JSONResponse(status_code=403, content={"error": {"code": "forbidden", "message": message}})

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = (scope.get("method") or "GET").upper()
        if method not in SAFE_METHODS:
            headers = Headers(scope=scope)
            origin = (headers.get("origin") or "").rstrip("/")
            if origin:
                if origin not in self.settings.cors_origins:
                    resp = self._reject("This request origin is not allowed.")
                    await resp(scope, receive, send)
                    return
            elif self.settings.app_env == "production":
                resp = self._reject("This request origin is not allowed.")
                await resp(scope, receive, send)
                return

            cookies = cookie_parser(headers.get("cookie", ""))
            session_token = cookies.get(self.settings.session_cookie_name, "")
            path = scope.get("path", "")
            if session_token and path not in self.csrf_exempt_paths:
                cookie_name = getattr(self.settings, "csrf_cookie_name", "risklocker_csrf")
                cookie_token = cookies.get(cookie_name, "")
                header_token = headers.get("x-csrf-token", "")
                expected = csrf_token_for_session(session_token, self.settings.auth_hash_secret)
                if (
                    not cookie_token
                    or not header_token
                    or not hmac.compare_digest(cookie_token, header_token)
                    or not hmac.compare_digest(header_token, expected)
                ):
                    resp = self._reject("The security token is missing or invalid. Refresh and try again.")
                    await resp(scope, receive, send)
                    return

        await self.app(scope, receive, send)


class SecurityHeadersMiddleware:
    """Attach security headers to success and error responses without stream buffering."""

    def __init__(self, app, *, production: bool):
        self.app = app
        self.production = production

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Referrer-Policy"] = "no-referrer"
                headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
                if headers.get("content-type") != "application/pdf":
                    headers["X-Frame-Options"] = "SAMEORIGIN"
                    headers["Content-Security-Policy"] = (
                        "default-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'self'"
                    )
                if self.production:
                    headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            await send(message)

        await self.app(scope, receive, send_wrapper)
