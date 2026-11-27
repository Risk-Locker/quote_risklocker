"""Postgres-backed fixed-window rate limits for expensive API surfaces."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from re import fullmatch

from fastapi.responses import JSONResponse
from sqlalchemy import select
from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import cookie_parser

from app.core.client_address import resolve_client_ip
from app.core.security import keyed_hash
from app.models.tables import RateLimitBucket


@dataclass(frozen=True)
class RateLimitPolicy:
    scope: str
    attempts: int
    window_seconds: int
    block_seconds: int = 0


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after: int
    blocked_until: datetime | None


def policy_for_request(method: str, path: str, settings) -> RateLimitPolicy | None:
    method = method.upper()
    if method == "POST" and path == "/api/auth/login":
        return RateLimitPolicy("login", settings.rate_limit_login_attempts, settings.rate_limit_login_window_seconds, settings.rate_limit_login_block_seconds)
    if method == "POST" and path in {"/api/uploads", "/api/batches/upload"}:
        return RateLimitPolicy("upload", settings.rate_limit_upload_attempts, settings.rate_limit_upload_window_seconds)
    if method == "POST" and (path.endswith("/preview-png") or path.endswith("/preview-render")):
        return RateLimitPolicy("preview", settings.rate_limit_preview_attempts, settings.rate_limit_preview_window_seconds)
    if method == "POST" and (path.endswith("/versions") or path.endswith("/generate")):
        return RateLimitPolicy("generation", settings.rate_limit_generation_attempts, settings.rate_limit_generation_window_seconds)
    if method == "GET" and (fullmatch(r"/api/(?:versions|generated-versions)/[^/]+/(?:pdf|content)", path)):
        return RateLimitPolicy("download", settings.rate_limit_download_attempts, settings.rate_limit_download_window_seconds)
    if method == "POST" and (path.endswith("/import") or "/imports" in path):
        return RateLimitPolicy("import", settings.rate_limit_import_attempts, settings.rate_limit_import_window_seconds)
    if method == "POST" and (fullmatch(r"/api/copilot/threads/[^/]+/stream", path) or path == "/api/copilot/chat"):
        return RateLimitPolicy("copilot_chat", settings.rate_limit_copilot_attempts, settings.rate_limit_copilot_window_seconds)
    return None


def consume_rate_limit(db, scope: str, key_hash: str, policy: RateLimitPolicy) -> RateLimitResult:
    now = datetime.now(timezone.utc)
    bucket = db.scalar(
        select(RateLimitBucket)
        .where(RateLimitBucket.scope == scope, RateLimitBucket.key_hash == key_hash)
        .with_for_update()
    )
    if bucket is None:
        bucket = RateLimitBucket(scope=scope, key_hash=key_hash, window_started_at=now, request_count=0)
        db.add(bucket)
        db.flush()
    if bucket.blocked_until and bucket.blocked_until > now:
        retry = max(1, math.ceil((bucket.blocked_until - now).total_seconds()))
        db.commit()
        return RateLimitResult(False, 0, retry, bucket.blocked_until)
    if (now - bucket.window_started_at).total_seconds() >= policy.window_seconds:
        bucket.window_started_at = now
        bucket.request_count = 0
        bucket.blocked_until = None
    bucket.request_count += 1
    allowed = bucket.request_count <= policy.attempts
    retry_after = 0
    if not allowed:
        wait_seconds = policy.block_seconds or policy.window_seconds
        bucket.blocked_until = now + timedelta(seconds=wait_seconds)
        retry_after = wait_seconds
    db.commit()
    return RateLimitResult(
        allowed=allowed,
        remaining=max(0, policy.attempts - bucket.request_count),
        retry_after=retry_after,
        blocked_until=bucket.blocked_until,
    )


class RateLimitMiddleware:
    """Pure ASGI rate-limiting middleware safe for SSE and streaming responses."""

    def __init__(self, app, *, settings, session_factory, consumer=consume_rate_limit):
        self.app = app
        self.settings = settings
        self.session_factory = session_factory
        self.consumer = consumer

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = (scope.get("method") or "GET").upper()
        path = scope.get("path", "")
        policy = policy_for_request(method, path, self.settings)
        if policy is None:
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        cookies = cookie_parser(headers.get("cookie", ""))
        peer = scope["client"][0] if scope.get("client") else None
        client_ip = resolve_client_ip(peer, headers.get("x-forwarded-for"), self.settings.trusted_proxy_ips)
        subject = cookies.get(self.settings.session_cookie_name) or client_ip
        key_hash = keyed_hash(f"rate:{policy.scope}:{subject}", self.settings.auth_hash_secret)
        try:
            with self.session_factory() as db:
                result = self.consumer(db, policy.scope, key_hash, policy)
        except Exception:
            resp = JSONResponse(
                status_code=503,
                content={"error": {"code": "dependency_unavailable", "message": "Request protection is temporarily unavailable."}},
                headers={"Retry-After": "30"},
            )
            await resp(scope, receive, send)
            return

        if not result.allowed:
            resp = JSONResponse(
                status_code=429,
                content={"error": {"code": "rate_limited", "message": "Too many requests. Try again later."}},
                headers={"Retry-After": str(result.retry_after)},
            )
            await resp(scope, receive, send)
            return

        async def send_wrapper(message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["X-RateLimit-Remaining"] = str(result.remaining)
            await send(message)

        await self.app(scope, receive, send_wrapper)
