"""FastAPI entrypoint for Risklocker Quotation Converter."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        verify_database_connection()
        verify_schema_version()
        SupabaseStorage(settings).ensure_bucket()
        try:
            yield
        finally:
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
