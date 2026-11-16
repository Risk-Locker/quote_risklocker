"""Idle-Period Model & Quota Radar Background Sentinel.

Runs during quiet system hours (e.g. >= 1 hour without active quotation uploads
and when extraction queue is completely idle).
Executes a lightweight Google AI Studio metadata probe to detect new model releases,
deprecations, or quota shifts without consuming quotation generation tokens.
Alerts Super Admins via Notification cards and AuditEvent records when shifts occur.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import AppSetting, AuditEvent, Job, Notification, User, new_id
from app.extraction.model_discovery_service import (
    get_verified_eligible_models,
    sync_model_baseline,
)


def is_extraction_idle(db: Session, idle_hours: float = 1.0) -> bool:
    """Check whether the AI extraction pipeline has been idle for >= idle_hours."""
    # 1. Any active (pending / processing) extraction jobs?
    active_stmt = select(Job).where(
        Job.job_type == "extraction",
        Job.state.in_(["pending", "processing"]),
    )
    if db.scalars(active_stmt).first() is not None:
        return False

    # 2. Check the most recent completed/failed extraction job timestamp
    recent_stmt = (
        select(Job)
        .where(Job.job_type == "extraction")
        .order_by(Job.created_at.desc())
        .limit(1)
    )
    latest_job = db.scalars(recent_stmt).first()
    if latest_job is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=idle_hours)
        # Ensure job timestamp is timezone-aware for comparison
        job_time = latest_job.created_at
        if job_time.tzinfo is None:
            job_time = job_time.replace(tzinfo=timezone.utc)
        if job_time > cutoff:
            return False

    return True


def run_model_radar_sentinel(
    db: Session, force: bool = False, api_key: str | None = None
) -> dict[str, Any]:
    """Execute the radar sentinel check, comparing live models against the stored baseline."""
    # Enforce idle check unless forced
    if not force and not is_extraction_idle(db, idle_hours=1.0):
        return {
            "ran": False,
            "reason": "Extraction pipeline is currently active; sentinel runs during quiet idle periods.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Resolve API key if not supplied
    resolved_key = api_key
    if not resolved_key:
        from app.services.gemini_account_service import get_key_pool

        pool = get_key_pool()
        keys = pool.get_all_keys()
        if keys:
            resolved_key = keys[0]

    # Probe live catalog & filter eligible models
    discovery = get_verified_eligible_models(api_key=resolved_key)
    eligible = discovery.get("eligible_models", [])

    # Synchronize baseline and check for shifts
    has_changed, alerts = sync_model_baseline(db, eligible)

    # If shifts detected, alert Super Admins & record AuditEvent
    notified_count = 0
    if has_changed and alerts:
        admin_stmt = select(User).where(User.role.in_(["super_admin", "admin"]))
        admins = list(db.scalars(admin_stmt).all())

        combined_body = "\n".join(alerts)
        for admin in admins:
            notif = Notification(
                id=new_id(),
                recipient_id=admin.id,
                event_type="ai_model_alert",
                title="Google AI Studio Model Update Detected",
                body=combined_body,
                delivery_state="delivered",
            )
            db.add(notif)
            notified_count += 1

        audit = AuditEvent(
            id=new_id(),
            actor_id=None,
            action="ai_model_radar_alert",
            entity_type="app_setting",
            entity_id=new_id(),
            details={"alerts": alerts, "eligible_count": len(eligible)},
        )
        db.add(audit)
        db.commit()

    return {
        "ran": True,
        "changed": has_changed,
        "alerts": alerts,
        "notified_admins": notified_count,
        "source": discovery.get("source"),
        "eligible_models_count": len(eligible),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
