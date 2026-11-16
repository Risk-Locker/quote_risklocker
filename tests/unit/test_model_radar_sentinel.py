"""Unit tests for Idle-Period Model & Quota Radar Background Sentinel (Task 3.3)."""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch
import pytest
from sqlalchemy.orm import Session

from app.models.tables import AppSetting, AuditEvent, Job, Notification, User, new_id


def test_is_extraction_idle_detection(db_session: Session):
    from app.workers.model_radar_sentinel import is_extraction_idle

    # 1. Empty database -> idle
    assert is_extraction_idle(db_session, idle_hours=1.0) is True

    # 2. Active job -> not idle
    user = User(
        id=new_id(),
        email="agent@risklocker.local",
        name="Agent User",
        password_hash="mock",
        role="staff",
    )
    db_session.add(user)
    job = Job(
        id=new_id(),
        owner_id=user.id,
        job_type="extraction",
        idempotency_key=new_id(),
        state="processing",
    )
    db_session.add(job)
    db_session.commit()

    assert is_extraction_idle(db_session, idle_hours=1.0) is False

    # 3. Job finished 2 hours ago -> idle
    job.state = "completed"
    past_time = datetime.now(timezone.utc) - timedelta(hours=2)
    job.created_at = past_time
    job.updated_at = past_time
    db_session.commit()

    assert is_extraction_idle(db_session, idle_hours=1.0) is True


def test_run_model_radar_sentinel_creates_notifications_on_model_change(db_session: Session):
    from app.workers.model_radar_sentinel import run_model_radar_sentinel

    # Seed Super Admin
    admin = User(
        id=new_id(),
        email="admin@risklocker.local",
        name="Super Admin",
        password_hash="mock",
        role="super_admin",
    )
    db_session.add(admin)

    # Initialize baseline with 3.1
    setting = AppSetting(
        key="ai_model_baseline",
        value={
            "known_models": ["gemini-3.1-flash-lite"],
            "last_synced_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    db_session.add(setting)
    db_session.commit()

    # Mock fetch_live_google_models to simulate Google announcing gemini-3.5-flash-lite
    simulated_google_models = [
        {
            "name": "models/gemini-3.1-flash-lite",
            "displayName": "Gemini 3.1 Flash-Lite",
            "supportedGenerationMethods": ["generateContent"],
            "inputTokenLimit": 1048576,
            "outputTokenLimit": 8192,
        },
        {
            "name": "models/gemini-3.5-flash-lite",
            "displayName": "Gemini 3.5 Flash-Lite",
            "supportedGenerationMethods": ["generateContent"],
            "inputTokenLimit": 1048576,
            "outputTokenLimit": 8192,
        },
    ]

    with patch("app.extraction.model_discovery_service.fetch_live_google_models") as mock_fetch:
        mock_fetch.return_value = (True, simulated_google_models, None)

        report = run_model_radar_sentinel(db_session, force=True, api_key="AIzaSyMockKeyForTest12345")

    assert report["ran"] is True
    assert report["changed"] is True
    assert any("gemini-3.5-flash-lite" in alert for alert in report["alerts"])

    # Verify Notification created for Super Admin
    notifications = db_session.query(Notification).filter_by(recipient_id=admin.id).all()
    assert len(notifications) >= 1
    alert_notif = next(n for n in notifications if n.event_type == "ai_model_alert")
    assert "Google AI Studio Model Update" in alert_notif.title
    assert "gemini-3.5-flash-lite" in alert_notif.body

    # Verify AuditEvent recorded
    audits = db_session.query(AuditEvent).filter_by(action="ai_model_radar_alert").all()
    assert len(audits) >= 1
