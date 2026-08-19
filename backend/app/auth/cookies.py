"""Authentication and CSRF cookie lifecycle helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.security import csrf_token_for_session

if TYPE_CHECKING:
    from fastapi import Response
    from app.core.config import Settings


def set_auth_cookies(response: Response, settings: Settings, raw_token: str, max_age: int) -> None:
    """Set the HttpOnly session cookie and the non-HttpOnly CSRF token cookie."""
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        max_age=max_age,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key=getattr(settings, "csrf_cookie_name", "risklocker_csrf"),
        value=csrf_token_for_session(raw_token, settings.auth_hash_secret),
        max_age=max_age,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    """Delete both the session cookie and CSRF cookie from the response."""
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        getattr(settings, "csrf_cookie_name", "risklocker_csrf"),
        path="/",
        secure=settings.session_cookie_secure,
        httponly=False,
        samesite="lax",
    )
