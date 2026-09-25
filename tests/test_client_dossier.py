"""Hermetic unit tests for connected client dossiers, monthly breakdown, and backfill preview."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.models.tables import Base, QuotationDraft, Session as SessionModel, TrackedVehicle, VehicleOwnership, new_id
from app.services.client_dossier_service import get_client_dossiers
from app.services.quotation_activity_service import (
    backfill_existing_sessions,
    get_insights_analytics,
    preview_backfill_sessions,
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


def test_backfill_preview_and_targeted_backfill(db_session: Session):
    user_id = new_id()

    # Session 1: Clean and ready (plate + customer)
    d1 = QuotationDraft(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=new_id(),
        fields={
            "vehicle_no": {"value": "ABC 1234"},
            "customer_name": {"value": "Alice Wong"},
            "valid_until": {"value": "2026-10-10"},
            "total_amount": {"value": "RM 1,500.00"},
        },
    )
    db_session.add(d1)
    db_session.flush()

    s1 = SessionModel(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=new_id(),
        draft_id=d1.id,
        detected_company="Allianz",
        quotation_status="hit",
    )
    db_session.add(s1)

    # Session 2: Ambiguous (missing plate)
    d2 = QuotationDraft(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=new_id(),
        fields={
            "customer_name": {"value": "Bob Smith"},
            "total_amount": {"value": "RM 800.00"},
        },
    )
    db_session.add(d2)
    db_session.flush()

    s2 = SessionModel(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=new_id(),
        draft_id=d2.id,
        detected_company="Etiqa",
        quotation_status="pending",
    )
    db_session.add(s2)
    db_session.commit()

    # Test preview
    prev = preview_backfill_sessions(db=db_session)
    assert prev["total_detected"] == 2
    assert prev["ready_count"] == 1
    assert prev["ambiguous_count"] == 1

    s1_item = next(it for it in prev["sessions"] if it["session_id"] == s1.id)
    assert s1_item["is_ready"] is True
    assert s1_item["normalized_plate"] == "ABC 1234"
    assert s1_item["customer_name"] == "Alice Wong"

    s2_item = next(it for it in prev["sessions"] if it["session_id"] == s2.id)
    assert s2_item["is_ready"] is False
    assert any("plate" in issue.lower() for issue in s2_item["issues"])

    # Test targeted backfill with override for s2
    res = backfill_existing_sessions(
        db=db_session,
        session_ids=[s1.id, s2.id],
        manual_overrides={
            s2.id: {"vehicle_no": "DEF 5678", "customer_name": "Bob Smith"},
        },
    )
    db_session.commit()

    assert res["sessions_processed"] == 2
    assert res["vehicles_tracked"] == 2
    assert res["activities_created"] >= 2


def test_client_dossier_and_monthly_analytics(db_session: Session):
    user_id = new_id()

    # Create 2 sessions for same customer, different vehicles
    d1 = QuotationDraft(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=new_id(),
        fields={
            "vehicle_no": {"value": "JMC 8218"},
            "customer_name": {"value": "Sadik Enterprise"},
            "car_model": {"value": "Honda City"},
            "total_amount": {"value": "RM 1,400.00"},
        },
    )
    d2 = QuotationDraft(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=new_id(),
        fields={
            "vehicle_no": {"value": "WXY 9999"},
            "customer_name": {"value": "Sadik Enterprise"},
            "car_model": {"value": "Toyota Vios"},
            "total_amount": {"value": "RM 1,800.00"},
        },
    )
    db_session.add_all([d1, d2])
    db_session.flush()

    s1 = SessionModel(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=new_id(),
        draft_id=d1.id,
        detected_company="AmAssurance",
        quotation_status="hit",
    )
    s2 = SessionModel(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=new_id(),
        draft_id=d2.id,
        detected_company="Kurnia",
        quotation_status="miss",
        miss_reason="Price too high",
    )
    db_session.add_all([s1, s2])
    db_session.commit()

    # Backfill so tracked vehicles exist
    backfill_existing_sessions(db=db_session)
    db_session.commit()

    # Test client dossier
    dossiers = get_client_dossiers(db=db_session)
    assert dossiers["summary"]["total_unique_clients"] >= 1
    assert dossiers["summary"]["total_connected_vehicles"] >= 2
    assert dossiers["summary"]["total_quotations"] == 2

    # Find Sadik Enterprise
    sadik = next(c for c in dossiers["clients"] if c["customer_name"] == "Sadik Enterprise")
    assert len(sadik["connected_vehicles"]) == 2
    assert len(sadik["quotations"]) == 2
    assert sadik["stats"]["hits"] == 1
    assert sadik["stats"]["misses"] == 1
    assert sadik["stats"]["hit_rate_percent"] == 50.0
    assert sadik["stats"]["won_premium_total"] == 1400.0
    assert sadik["stats"]["lost_premium_total"] == 1800.0

    # Test monthly breakdown in analytics
    analytics = get_insights_analytics(db=db_session)
    assert "monthly_breakdown" in analytics
    assert len(analytics["monthly_breakdown"]) >= 1
    cur_month = analytics["monthly_breakdown"][0]
    assert cur_month["total_quotations"] == 2
    assert cur_month["hits_count"] == 1
    assert cur_month["misses_count"] == 1
    assert cur_month["hit_rate_percent"] == 50.0


def test_client_dossier_with_raw_string_fields(db_session: Session):
    """Regression test: verify get_client_dossiers does not crash when session draft fields contain raw strings."""
    user_id = new_id()
    # Legacy session where fields are flat strings instead of nested {"value": "..."} dicts
    legacy_draft = QuotationDraft(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=new_id(),
        fields={
            "customer_name": "Legacy Logistics Sdn Bhd",
            "vehicle_no": "WXY 8888",
            "vehicle_type": "Lorry",
            "car_model": "Hino 300",
            "insurance_company": "AmAssurance",
            "total_amount": "RM 3,250.00",
            "quotation_no": "RL-LEGACY-001",
        },
    )
    db_session.add(legacy_draft)
    db_session.flush()

    legacy_session = SessionModel(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=new_id(),
        draft_id=legacy_draft.id,
        detected_company="AmAssurance",
        quotation_status="hit",
    )
    db_session.add(legacy_session)
    db_session.commit()

    # Must succeed without AttributeError: 'str' object has no attribute 'get'
    res = get_client_dossiers(db=db_session)
    assert res["summary"]["total_quotations"] >= 1
    legacy_client = next(c for c in res["clients"] if "Legacy Logistics" in c["customer_name"])
    assert legacy_client["is_corporate"] is True
    assert legacy_client["stats"]["hits"] == 1
    assert legacy_client["stats"]["won_premium_total"] == 3250.0

