"""Authentication and authorization services for password-based sessions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    keyed_hash,
    verify_password,
)
from app.models.enums import AccountStatus, Role
from app.models.tables import AuthSession, User


# Token collision retry limit
MAX_SESSION_RETRIES = 3


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _audit(db: Session, actor_id: str | None, action: str, entity_type: str, entity_id: str | None, details: dict) -> None:
    from app.models.tables import AuditEvent

    db.add(
        AuditEvent(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
    )


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "status": user.status,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


def _create_session(
    db: Session,
    settings: Settings,
    user_id: str,
    user_agent: str | None,
    ip_address: str | None,
) -> tuple[AuthSession, str]:
    now = _utcnow()
    idle = now + timedelta(hours=settings.session_idle_hours)
    absolute = now + timedelta(days=settings.session_max_days)
    raw_token = generate_session_token()
    token_hash = hash_session_token(raw_token)

    for _ in range(MAX_SESSION_RETRIES - 1):
        existing = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash))
        if not existing:
            break
        raw_token = generate_session_token()
        token_hash = hash_session_token(raw_token)

    session = AuthSession(
        user_id=user_id,
        token_hash=token_hash,
        last_activity_at=now,
        idle_expires_at=idle,
        absolute_expires_at=absolute,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session, raw_token


def authenticate_session(db: Session, settings: Settings, raw_token: str) -> tuple[User, AuthSession]:
    token_hash = hash_session_token(raw_token)
    session = db.scalar(
        select(AuthSession)
        .where(
            AuthSession.token_hash == token_hash,
            AuthSession.revoked_at.is_(None),
        )
        .order_by(AuthSession.created_at.desc())
    )
    if not session:
        raise AppError("Please log in.", 401)

    now = _utcnow()
    if now > session.absolute_expires_at or now > session.idle_expires_at:
        raise AppError("Your session has expired. Please log in again.", 401)

    user = session.user
    if user is None:
        user = db.get(User, session.user_id)
    if user is None or user.status != AccountStatus.ACTIVE.value:
        if session.revoked_at is None:
            session.revoked_at = now
            db.commit()
        raise AppError("This account is not active.", 401)
    if getattr(settings, "app_env", "test") == "production" and user.role == Role.DEV.value:
        if session.revoked_at is None:
            session.revoked_at = now
            db.commit()
        raise AppError("This account type is not available in production.", 401)

    session.last_activity_at = now
    session.idle_expires_at = now + timedelta(hours=settings.session_idle_hours)
    db.commit()
    return user, session


def revoke_session(db: Session, session: AuthSession, revoked_by: str | None = None) -> None:
    if session.revoked_at:
        return
    session.revoked_at = _utcnow()
    if revoked_by:
        session.revoked_by = revoked_by
    db.commit()


def revoke_user_sessions(db: Session, user_id: str, revoked_by: str | None = None) -> int:
    count = 0
    now = _utcnow()
    for session in db.scalars(
        select(AuthSession).where(
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
        )
    ):
        session.revoked_at = now
        if revoked_by:
            session.revoked_by = revoked_by
        count += 1
    db.commit()
    return count


def _require_user_management_permission(actor: User, target: User | None = None) -> None:
    """Only super_admin and admin may manage users. super_admin can manage anyone.
    admin cannot delete themselves or the super_admin."""
    if actor.role == Role.SUPER_ADMIN.value:
        return
    if actor.role != Role.ADMIN.value:
        raise AppError("You do not have permission to manage users.", 403)
    if target is None:
        return
    if target.role == Role.SUPER_ADMIN.value:
        raise AppError("You do not have permission to manage the super administrator.", 403)
    if target.id == actor.id:
        raise AppError("You cannot modify your own account this way.", 403)


def _normalize_email(email: str | None) -> str:
    if not email:
        raise AppError("Email is required.", 400)
    normalized = email.strip().lower()
    if "@" not in normalized or "." not in normalized.split("@")[-1]:
        raise AppError("Please provide a valid email address.", 400)
    return normalized


def login_with_password(
    db: Session,
    settings: Settings,
    email: str,
    password: str,
    user_agent: str | None,
    ip_address: str | None,
) -> tuple[User, AuthSession, str]:
    normalized = _normalize_email(email)
    user = db.scalar(select(User).where(User.email == normalized))
    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        raise AppError("Invalid email or password.", 401)
    if getattr(settings, "app_env", "test") == "production" and user.role == Role.DEV.value:
        raise AppError("Invalid email or password.", 401)
    if user.status != AccountStatus.ACTIVE.value:
        raise AppError("This account is not active.", 401)

    session, raw_token = _create_session(db, settings, user.id, user_agent, ip_address)
    _audit(db, user.id, "login", "user", user.id, {"ip": ip_address, "ua": user_agent})
    db.commit()
    return user, session, raw_token


def change_password(db: Session, user: User, current_password: str, new_password: str) -> User:
    if not verify_password(current_password, user.password_hash):
        raise AppError("Current password is incorrect.", 400)
    if len(new_password) < 8:
        raise AppError("Password must be at least 8 characters.", 400)
    user.password_hash = hash_password(new_password)
    db.commit()
    db.refresh(user)
    return user


def create_user(
    db: Session,
    actor: User,
    email: str,
    role: str,
    password: str | None = None,
    status: str = AccountStatus.ACTIVE.value,
) -> User:
    _require_user_management_permission(actor)
    normalized = _normalize_email(email)
    if role not in {Role.SUPER_ADMIN.value, Role.ADMIN.value, Role.STAFF.value, Role.DEV.value}:
        raise AppError("Invalid role.", 400)
    if role == Role.SUPER_ADMIN.value and actor.role != Role.SUPER_ADMIN.value:
        raise AppError("Only the super administrator can assign the super administrator role.", 403)
    if db.scalar(select(User).where(User.email == normalized)):
        raise AppError("A user with this email already exists.", 409)

    user = User(
        email=normalized,
        password_hash=hash_password(password) if password else "",
        role=role,
        status=status,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    _audit(db, actor.id, "create_user", "user", user.id, {"email": normalized, "role": role})
    db.commit()
    return user


def update_user(
    db: Session,
    actor: User,
    target: User,
    email: str | None = None,
    role: str | None = None,
    status: str | None = None,
    password: str | None = None,
) -> User:
    _require_user_management_permission(actor, target)
    if email is not None:
        normalized = _normalize_email(email)
        existing = db.scalar(select(User).where(User.email == normalized, User.id != target.id))
        if existing:
            raise AppError("A user with this email already exists.", 409)
        target.email = normalized
    if role is not None:
        if role not in {Role.SUPER_ADMIN.value, Role.ADMIN.value, Role.STAFF.value, Role.DEV.value}:
            raise AppError("Invalid role.", 400)
        # Only super_admin can create/promote another super_admin.
        if role == Role.SUPER_ADMIN.value and actor.role != Role.SUPER_ADMIN.value:
            raise AppError("Only the super administrator can assign the super administrator role.", 403)
        target.role = role
    if status is not None:
        if status not in {AccountStatus.ACTIVE.value, AccountStatus.INACTIVE.value}:
            raise AppError("Invalid status.", 400)
        target.status = status
    if password is not None:
        if len(password) < 8:
            raise AppError("Password must be at least 8 characters.", 400)
        target.password_hash = hash_password(password)
    db.commit()
    db.refresh(target)
    _audit(db, actor.id, "update_user", "user", target.id, {"email": target.email, "role": target.role, "status": target.status})
    db.commit()
    return target


def bootstrap_primary_admin(db: Session, email: str, password: str) -> User:
    """Create the sole Primary Admin without modifying an existing owner."""

    if len(password) < 12:
        raise AppError("The bootstrap password must be at least 12 characters.", 400)
    normalized = _normalize_email(email)
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext('risklocker_primary_admin_bootstrap'))"))
    owner = db.scalar(select(User).where(User.role == Role.SUPER_ADMIN.value).with_for_update())
    if owner is not None:
        raise AppError("A Primary Admin already exists. Bootstrap cannot modify it.", 409)
    if db.scalar(select(User).where(User.email == normalized).with_for_update()) is not None:
        raise AppError("A user with this email already exists.", 409)
    user = User(
        email=normalized,
        password_hash=hash_password(password),
        role=Role.SUPER_ADMIN.value,
        status=AccountStatus.ACTIVE.value,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def ensure_super_admin(db: Session, settings: Settings) -> User | None:
    """RL-DISABLED environment credential reset — disabled 2026-08-13; bootstrap once via CLI."""

    return None


def initial_super_admin_from_env(db: Session, settings: Settings) -> User | None:
    """RL-DISABLED legacy environment bootstrap — disabled 2026-08-13."""

    return None
