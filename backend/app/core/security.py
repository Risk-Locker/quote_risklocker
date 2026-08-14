"""Cryptographic helpers for opaque sessions and password hashing."""

from __future__ import annotations

import hashlib
import hmac
import secrets

import bcrypt


def generate_session_token() -> str:
    """Return an opaque high-entropy token; only its hash is persisted."""
    return secrets.token_urlsafe(48)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    """Hash a plain password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def keyed_hash(value: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def csrf_token_for_session(session_token: str, secret: str) -> str:
    """Derive a CSRF token that is valid only for one opaque server session."""

    return keyed_hash(f"csrf:{session_token}", secret)
