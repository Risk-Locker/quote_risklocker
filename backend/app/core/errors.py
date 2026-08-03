"""API error helpers."""

from __future__ import annotations

from traceback import format_exc

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette import status


class AppError(Exception):
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"message": exc.message}},
        )

    @app.exception_handler(Exception)
    async def catch_all_handler(_: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, (SystemExit, KeyboardInterrupt)):
            raise
        msg = "Internal server error"
        print(f"[ERROR] {exc.__class__.__name__}: {exc}\n{format_exc()}", flush=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": {"message": msg}},
        )
