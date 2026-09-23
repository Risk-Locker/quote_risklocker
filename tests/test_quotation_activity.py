"""Hermetic unit and integration tests for quotation activity logging, status updates, and calendar metrics."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.models.tables import Base, QuotationActivity, QuotationDraft, Session as SessionModel, TrackedVehicle, new_id
from app.services.quotation_activity_service import (
    backfill_existing_sessions,
    get_calendar_activities,
    get_insights_analytics,
    log_quotation_activity,
    update_quotation_status,
)


@pytest.fixture
def db_session():
    """Hermetic in-memory SQLite database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_log_activity_and_status_changes(db_session: Session):
    user_id = new_id()
    # Setup session with draft
    f_id = new_id()
    draft = QuotationDraft(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=f_id,
        fields={
            "vehicle_no": {"value": "WXY 9988"},
            "customer_name": {"value": "John Doe"},
            "total_amount": {"value": "RM 1,250.00"},
        },
    )
    db_session.add(draft)
    db_session.flush()

    s = SessionModel(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=f_id,
        quotation_ref="RL260000010",
        quotation_status="pending",
        detected_company="Etiqa Takaful",
        draft_id=draft.id,
    )
    db_session.add(s)
    db_session.commit()

    # 1. Log scan activity
    act1 = log_quotation_activity(
        db=db_session,
        session_id=s.id,
        action_type="upload_scan",
        sent_to_client=False,
        summary="Scanned quotation for WXY 9988",
    )
    db_session.commit()

    assert act1.id is not None
    assert act1.vehicle_no == "WXY 9988"
    assert act1.customer_name == "John Doe"
    assert act1.sent_to_client is False
    assert s.tracked_vehicle_id is not None

    # 2. Log PDF export / sent to client
    act2 = log_quotation_activity(
        db=db_session,
        session_id=s.id,
        action_type="sent_to_client",
        sent_to_client=True,
        summary="Sent quotation PDF to client",
        version_number=1,
    )
    db_session.commit()

    assert act2.sent_to_client is True

    # 3. Update status to HIT (Won)
    res_hit = update_quotation_status(
        db=db_session,
        session_id=s.id,
        status="hit",
        won_premium=1250.0,
    )
    db_session.commit()

    assert res_hit["quotation_status"] == "hit"
    assert res_hit["closed_at"] is not None
    assert s.quotation_status == "hit"

    # 4. Check calendar activities
    cal = get_calendar_activities(db=db_session)
    assert cal["total_activities"] >= 3
    dates = list(cal["dates"].keys())
    assert len(dates) >= 1

    # 5. Check analytics
    analytics = get_insights_analytics(db=db_session)
    assert analytics["total_quotations"] == 1
    assert analytics["hits_count"] == 1
    assert analytics["misses_count"] == 0
    assert analytics["hit_rate_percent"] == 100.0
    assert analytics["won_premium_total"] == 1250.0
    assert analytics["sent_to_client_count"] == 1
    assert analytics["company_hits"].get("Etiqa Takaful") == 1

    # 6. Change status to MISS (Lost)
    res_miss = update_quotation_status(
        db=db_session,
        session_id=s.id,
        status="miss",
        miss_reason="Competitor cheaper",
    )
    db_session.commit()

    assert res_miss["quotation_status"] == "miss"
    assert res_miss["miss_reason"] == "Competitor cheaper"

    analytics2 = get_insights_analytics(db=db_session)
    assert analytics2["hits_count"] == 0
    assert analytics2["misses_count"] == 1
    assert analytics2["hit_rate_percent"] == 0.0
    assert analytics2["lost_premium_total"] == 1250.0
    assert analytics2["miss_reasons"].get("Competitor cheaper") == 1


def test_test_session_is_strictly_isolated_from_activities_and_analytics(db_session: Session):
    user_id = new_id()
    f_id = new_id()
    draft = QuotationDraft(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=f_id,
        fields={
            "vehicle_no": {"value": "TEST 1234"},
            "customer_name": {"value": "Test Customer"},
            "total_amount": {"value": "RM 3,500.00"},
        },
    )
    db_session.add(draft)
    db_session.flush()

    test_sess = SessionModel(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=f_id,
        draft_id=draft.id,
        insurance_type="Motor",
        detected_company="Allianz",
        status="active",
        quotation_status="pending",
        is_test=True,
    )
    db_session.add(test_sess)
    db_session.commit()

    # 1. log_quotation_activity must return None and insert nothing
    act = log_quotation_activity(
        db=db_session,
        session_id=test_sess.id,
        action_type="quote_generated",
        user_id=user_id,
        sent_to_client=False,
        summary="Test quote generation",
    )
    assert act is None

    # 2. update_quotation_status updates status on session but does not log activity or touch vehicle tracking
    res = update_quotation_status(
        db=db_session,
        session_id=test_sess.id,
        status="hit",
        won_premium=3500.0,
    )
    assert res["quotation_status"] == "hit"
    assert test_sess.tracked_vehicle_id is None

    # 3. get_calendar_activities must be empty for test session
    cal = get_calendar_activities(db=db_session, vehicle_no="TEST 1234")
    assert cal["total_activities"] == 0

    # 4. get_insights_analytics must strictly exclude test session
    analytics = get_insights_analytics(db=db_session)
    # The only session in this db is test_sess; analytics must show 0 quotations and 0 won premium
    assert analytics["total_quotations"] == 0
    assert analytics["hits_count"] == 0
    assert analytics["won_premium_total"] == 0.0

    # 5. upsert_from_draft must return None for test session (no client_record created)
    from app.services.client_record_service import upsert_from_draft
    client_rec = upsert_from_draft(
        db=db_session,
        draft_fields=draft.fields,
        session_id=test_sess.id,
        draft_id=draft.id,
        uploaded_file_id=f_id,
    )
    assert client_rec is None


def test_completeness_validation_blocks_hit_miss_on_incomplete_draft(db_session: Session):
    user_id = new_id()
    f_id = new_id()

    # 1. Draft with missing vehicle number
    draft_no_plate = QuotationDraft(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=f_id,
        fields={
            "customer_name": {"value": "Jane Tan"},
            "total_amount": {"value": "RM 1,800.00"},
        },
    )
    db_session.add(draft_no_plate)
    db_session.flush()

    sess1 = SessionModel(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=f_id,
        draft_id=draft_no_plate.id,
        quotation_status="pending",
    )
    db_session.add(sess1)
    db_session.commit()

    with pytest.raises(ValueError, match="Missing vehicle registration number"):
        update_quotation_status(db=db_session, session_id=sess1.id, status="miss", miss_reason="Price too high")

    with pytest.raises(ValueError, match="Missing vehicle registration number"):
        update_quotation_status(db=db_session, session_id=sess1.id, status="hit", won_premium=1800.0)

    # 2. Draft with missing customer name
    draft_no_cust = QuotationDraft(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=new_id(),
        fields={
            "vehicle_no": {"value": "VAA 1122"},
            "total_amount": {"value": "RM 2,200.00"},
        },
    )
    db_session.add(draft_no_cust)
    db_session.flush()

    sess2 = SessionModel(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=new_id(),
        draft_id=draft_no_cust.id,
        quotation_status="pending",
    )
    db_session.add(sess2)
    db_session.commit()

    with pytest.raises(ValueError, match="Missing customer name"):
        update_quotation_status(db=db_session, session_id=sess2.id, status="miss", miss_reason="Other")

    # 3. Draft with plate and customer, but hit with missing/0 premium
    draft_no_prem = QuotationDraft(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=new_id(),
        fields={
            "vehicle_no": {"value": "VAA 1122"},
            "customer_name": {"value": "Valid Client"},
        },
    )
    db_session.add(draft_no_prem)
    db_session.flush()

    sess3 = SessionModel(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=new_id(),
        draft_id=draft_no_prem.id,
        quotation_status="pending",
    )
    db_session.add(sess3)
    db_session.commit()

    with pytest.raises(ValueError, match="Winning policy premium amount is required"):
        update_quotation_status(db=db_session, session_id=sess3.id, status="hit", won_premium=None)

    # 4. Valid fields: status update succeeds
    draft_complete = QuotationDraft(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=new_id(),
        fields={
            "vehicle_no": {"value": "VAA 1122"},
            "customer_name": {"value": "Valid Client"},
            "total_amount": {"value": "RM 1,500.00"},
        },
    )
    db_session.add(draft_complete)
    db_session.flush()

    sess4 = SessionModel(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=new_id(),
        draft_id=draft_complete.id,
        quotation_status="pending",
    )
    db_session.add(sess4)
    db_session.commit()

    res_hit = update_quotation_status(db=db_session, session_id=sess4.id, status="hit", won_premium=1500.0)
    assert res_hit["quotation_status"] == "hit"

    # 5. Reopening back to pending does not require premium
    res_reopen = update_quotation_status(db=db_session, session_id=sess4.id, status="pending")
    assert res_reopen["quotation_status"] == "pending"
