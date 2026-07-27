"""In-app notification records for invitations, role changes, and account status events."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.tables import Notification, User


def create_notification(
    db: Session,
    recipient_id: str,
    event_type: str,
    title: str,
    body: str,
    delivery_state: str = "sent",
    delivery_error: str | None = None,
    audit_event_id: str | None = None,
) -> Notification:
    notification = Notification(
        recipient_id=recipient_id,
        event_type=event_type,
        title=title,
        body=body,
        delivery_state=delivery_state,
        delivery_error=delivery_error,
        audit_event_id=audit_event_id,
    )
    db.add(notification)
    db.flush()
    return notification


def get_notifications(db: Session, user_id: str) -> list[Notification]:
    return list(
        db.scalars(
            select(Notification)
            .where(Notification.recipient_id == user_id)
            .order_by(Notification.created_at.desc())
        ).all()
    )


def get_unread_count(db: Session, user_id: str) -> int:
    return len(
        list(
            db.scalars(
                select(Notification).where(
                    Notification.recipient_id == user_id,
                    Notification.read_at.is_(None),
                )
            ).all()
        )
    )


def mark_read(db: Session, notification_id: str, user_id: str) -> Notification:
    notification = db.get(Notification, notification_id)
    if not notification:
        raise AppError("Notification not found.", 404)
    if notification.recipient_id != user_id:
        raise AppError("Notification not found.", 404)
    from datetime import datetime, timezone

    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)
    return notification


def mark_all_read(db: Session, user_id: str) -> int:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    updated = 0
    notifications = list(
        db.scalars(
            select(Notification).where(
                Notification.recipient_id == user_id,
                Notification.read_at.is_(None),
            )
        ).all()
    )
    for notification in notifications:
        notification.read_at = now
        updated += 1
    if updated:
        db.commit()
    return updated


def serialize_notification(notification: Notification) -> dict:
    return {
        "id": notification.id,
        "event_type": notification.event_type,
        "title": notification.title,
        "body": notification.body,
        "read_at": notification.read_at.isoformat() if notification.read_at else None,
        "delivery_state": notification.delivery_state,
        "created_at": notification.created_at.isoformat(),
    }
