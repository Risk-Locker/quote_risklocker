"""Audit event recording helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.models.tables import AuditEvent

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def record_audit_event(
    db: Session,
    actor_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str | None,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    """Record a structured audit trail event in the active database session."""
    event = AuditEvent(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details or {},
    )
    db.add(event)
    return event
