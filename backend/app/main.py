"""FastAPI entrypoint for Risklocker Quotation Converter."""

from __future__ import annotations

import logging
import os
import sys
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.http_security import RequestSecurityMiddleware, SecurityHeadersMiddleware
from app.core.rate_limit import RateLimitMiddleware
from app.db.init_db import seed_defaults  # RL-DISABLED startup seeding — disabled 2026-08-13; invoke explicitly from CLI only.
from app.db.session import SessionLocal, verify_database_connection, verify_schema_version
from app.models.tables import Base  # RL-DISABLED runtime schema creation — disabled 2026-08-13; migrations own schema changes.
from app.services.storage_retention import purge_expired_pdfs  # RL-DISABLED automatic expiry — disabled 2026-08-13; PDFs are manually retained.
from app.storage.supabase import SupabaseStorage, close_shared_storage_client


def _setup_logging() -> None:
    """Ensure root and application loggers stream to stdout in real time."""
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
    logging.getLogger("app").setLevel(logging.INFO)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every incoming HTTP request and response status in real time."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger = logging.getLogger("app.http")
        logger.info("%s %s -> %d (%.1fms)", request.method, request.url.path, response.status_code, duration_ms)
        return response


def create_app() -> FastAPI:
    _setup_logging()
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        logger = logging.getLogger("app.main")
        logger.info("Risklocker backend starting (env=%s)", settings.app_env)
        verify_database_connection()
        verify_schema_version()
        SupabaseStorage(settings).ensure_bucket()
        worker_task = None
        if settings.app_env != "test" and os.getenv("ENABLE_EMBEDDED_WORKER", "1") == "1":
            import asyncio
            import socket
            from app.workers.extraction_worker import run_one_job

            async def _embedded_worker_loop():
                worker_id = f"embedded:{socket.gethostname()}:{os.getpid()}"
                while True:
                    try:
                        def _work():
                            with SessionLocal() as db:
                                return run_one_job(db, settings, worker_id=worker_id)

                        job = await asyncio.to_thread(_work)
                        if job is None:
                            await asyncio.sleep(1.0)
                    except asyncio.CancelledError:
                        break
                    except Exception:
                        logger.exception("Embedded worker loop iteration failed — sleeping 2s before retry")
                        await asyncio.sleep(2.0)

            worker_task = asyncio.create_task(_embedded_worker_loop())

        try:
            yield
        finally:
            if worker_task:
                worker_task.cancel()
                try:
                    await worker_task
                except (asyncio.CancelledError, Exception):
                    pass
            close_shared_storage_client()

    production = settings.app_env == "production"
    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "HEAD", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Idempotency-Key", "Range", "X-CSRF-Token"],
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        RequestSecurityMiddleware,
        settings=settings,
        csrf_exempt_paths={"/api/auth/login", "/auth/login"},
    )
    app.add_middleware(RateLimitMiddleware, settings=settings, session_factory=SessionLocal)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.trusted_hosts))
    app.add_middleware(SecurityHeadersMiddleware, production=production)
    register_error_handlers(app)
    app.include_router(router, prefix="/api")
    if not production:
        app.include_router(router)

    return app


app = create_app()
