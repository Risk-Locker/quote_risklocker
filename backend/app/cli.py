"""Small operational CLI helpers."""

from __future__ import annotations

import argparse

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.init_db import seed_defaults
from app.db.session import SessionLocal
from app.models.enums import AccountStatus, Role
from app.models.tables import User


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if "@" not in normalized or "." not in normalized.split("@")[-1]:
        raise ValueError("Please provide a valid email address.")
    return normalized


def init_db() -> None:
    settings = get_settings()
    with SessionLocal() as db:
        seed_defaults(db, settings)


def create_admin(email: str, password: str) -> None:
    init_db()
    with SessionLocal() as db:
        normalized_email = _normalize_email(email)
        user = db.scalar(select(User).where(User.email == normalized_email))
        action = "Updated"
        if user:
            user.role = Role.ADMIN.value
            user.status = AccountStatus.ACTIVE.value
            user.password_hash = hash_password(password)
        else:
            action = "Created"
            user = User(
                email=normalized_email,
                password_hash=hash_password(password),
                role=Role.ADMIN.value,
                status=AccountStatus.ACTIVE.value,
            )
            db.add(user)
        db.commit()
        print(f"{action} Admin account: {normalized_email}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db")
    admin = sub.add_parser("create-admin")
    admin.add_argument("email")
    admin.add_argument("password")
    args = parser.parse_args()
    if args.command == "init-db":
        init_db()
    elif args.command == "create-admin":
        create_admin(args.email, args.password)


if __name__ == "__main__":
    main()
