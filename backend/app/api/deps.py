"""FastAPI authentication and request dependencies."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.models.tables import AuthSession, User
from app.services.auth_service import authenticate_session
from app.core.security import csrf_token_for_session


@dataclass(frozen=True)
class AuthContext:
    user: User
    session: AuthSession
    raw_token: str


def settings_dep() -> Settings:
    return get_settings()


def ensure_trusted_origin(request: Request, settings: Settings) -> None:
    if request.method.upper() in {"GET", "HEAD", "OPTIONS"}:
        return
    origin = (request.headers.get("origin") or "").rstrip("/")
    if origin and origin not in settings.cors_origins:
        raise AppError("This request origin is not allowed.", 403)
    if settings.app_env == "production" and not origin:
        raise AppError("This request origin is not allowed.", 403)


def current_auth(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
) -> AuthContext:
    ensure_trusted_origin(request, settings)
    raw_token = request.cookies.get(settings.session_cookie_name, "")
    if not raw_token:
        raise AppError("Please log in.", 401)
    user, session = authenticate_session(db, settings, raw_token)
    remaining_seconds = max(0, int((session.absolute_expires_at - session.last_activity_at).total_seconds()))
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        max_age=remaining_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key=getattr(settings, "csrf_cookie_name", "risklocker_csrf"),
        value=csrf_token_for_session(raw_token, settings.auth_hash_secret),
        max_age=remaining_seconds,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return AuthContext(user=user, session=session, raw_token=raw_token)


def current_user(auth: AuthContext = Depends(current_auth)) -> User:
    return auth.user


def current_auth_optional(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
) -> AuthContext | None:
    """Return the current session if one exists, otherwise None."""
    ensure_trusted_origin(request, settings)
    raw_token = request.cookies.get(settings.session_cookie_name, "")
    if not raw_token:
        return None
    try:
        user, session = authenticate_session(db, settings, raw_token)
    except AppError:
        return None
    remaining_seconds = max(0, int((session.absolute_expires_at - session.last_activity_at).total_seconds()))
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        max_age=remaining_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key=getattr(settings, "csrf_cookie_name", "risklocker_csrf"),
        value=csrf_token_for_session(raw_token, settings.auth_hash_secret),
        max_age=remaining_seconds,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return AuthContext(user=user, session=session, raw_token=raw_token)
