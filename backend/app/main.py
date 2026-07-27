"""FastAPI entrypoint for Risklocker Quotation Converter."""

from __future__ import annotations

import asyncio
from contextlib import suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.db.init_db import seed_defaults
from app.db.session import SessionLocal, verify_database_connection
from app.services.storage_retention import purge_expired_pdfs
from app.storage.supabase import SupabaseStorage


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(router, prefix="/api")
    app.include_router(router)

    def retention_cycle() -> None:
        with SessionLocal() as db:
            purge_expired_pdfs(db, SupabaseStorage(settings))

    async def retention_loop() -> None:
        while True:
            await asyncio.sleep(24 * 60 * 60)
            await asyncio.to_thread(retention_cycle)

    @app.on_event("startup")
    async def startup() -> None:
        verify_database_connection()
        SupabaseStorage(settings).ensure_bucket()
        if settings.app_env != "production":
            with SessionLocal() as db:
                seed_defaults(db, settings)
        await asyncio.to_thread(retention_cycle)
        app.state.storage_retention_task = asyncio.create_task(retention_loop())

    @app.on_event("shutdown")
    async def shutdown() -> None:
        task = getattr(app.state, "storage_retention_task", None)
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    return app


app = create_app()
