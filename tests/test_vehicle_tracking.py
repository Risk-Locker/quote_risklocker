"""Hermetic unit and integration tests for vehicle tracking and sequential ownership history."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.models.tables import Base, QuotationDraft, Session as SessionModel, TrackedVehicle, VehicleOwnership, new_id
from app.services.vehicle_tracking_service import (
    assign_or_get_deal_cycle,
    check_vehicle_ownership_conflict,
    get_or_create_vehicle_tracking,
    get_upcoming_renewals,
    get_vehicle_history,
    is_same_customer,
    is_valid_malaysian_plate,
    normalize_plate,
    parse_date_safe,
    resolve_vehicle_ownership,
)
from app.services.quotation_activity_service import update_quotation_status


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


def test_normalize_plate():
    assert normalize_plate("jmc 8218") == "JMC 8218"
    assert normalize_plate("  w  1234  a  ") == "W 1234 A"
    assert normalize_plate("ABC-1234") == "ABC 1234"
    assert normalize_plate("vba_4567") == "VBA 4567"
    assert normalize_plate("") == ""
    assert normalize_plate(None) == ""


def test_parse_date_safe():
    d1 = parse_date_safe("2026-08-25")
    assert d1 is not None
    assert d1.year == 2026 and d1.month == 8 and d1.day == 25

    d2 = parse_date_safe("25/08/2026")
    assert d2 is not None
    assert d2.year == 2026 and d2.month == 8 and d2.day == 25

    d3 = parse_date_safe("25-08-2026")
    assert d3 is not None
    assert d3.year == 2026 and d3.month == 8 and d3.day == 25

    assert parse_date_safe("invalid-date") is None
    assert parse_date_safe(None) is None


def test_vehicle_tracking_and_sequential_ownership(db_session: Session):
    user_id = new_id()
    # 1. First quote for JMC 8218 with owner Sadik
    f1 = new_id()
    d1 = QuotationDraft(id=new_id(), owner_id=user_id, uploaded_file_id=f1, fields={})
    db_session.add(d1)
    s1 = SessionModel(id=new_id(), owner_id=user_id, uploaded_file_id=f1, draft_id=d1.id, quotation_ref="RL260000001", quotation_status="pending")
    db_session.add(s1)
    db_session.flush()

    veh, alert = get_or_create_vehicle_tracking(
        db=db_session,
        vehicle_no="JMC 8218",
        customer_name="Sadik",
        validity_date="2026-05-15",
        session_id=s1.id,
        brand="HONDA",
        model="CIVIC",
    )
    db_session.commit()

    assert veh is not None
    assert veh.vehicle_no == "JMC 8218"
    assert veh.current_owner_name == "Sadik"
    assert veh.car_brand == "HONDA"
    assert alert is None

    # Verify ownership record
    ownerships = db_session.query(VehicleOwnership).filter_by(vehicle_id=veh.id).all()
    assert len(ownerships) == 1
    assert ownerships[0].customer_name == "Sadik"
    assert ownerships[0].sequence_order == 1
    assert ownerships[0].is_current is True

    # 2. Second quote for same vehicle and same customer (Sadik) with extended date
    f2 = new_id()
    d2 = QuotationDraft(id=new_id(), owner_id=user_id, uploaded_file_id=f2, fields={})
    db_session.add(d2)
    s2 = SessionModel(id=new_id(), owner_id=user_id, uploaded_file_id=f2, draft_id=d2.id, quotation_ref="RL260000002", quotation_status="pending")
    db_session.add(s2)
    db_session.flush()

    veh2, alert2 = get_or_create_vehicle_tracking(
        db=db_session,
        vehicle_no="jmc 8218",  # lower case test
        customer_name="Sadik",
        validity_date="2027-05-15",
        session_id=s2.id,
    )
    db_session.commit()

    assert veh2 is not None
    assert veh2.id == veh.id
    assert alert2 is None
    ownerships2 = db_session.query(VehicleOwnership).filter_by(vehicle_id=veh.id).all()
    assert len(ownerships2) == 1
    assert ownerships2[0].valid_until == "2027-05-15"

    # 3. Third quote for SAME vehicle but NEW OWNER (Alice Tan) with newer date
    f3 = new_id()
    d3 = QuotationDraft(id=new_id(), owner_id=user_id, uploaded_file_id=f3, fields={})
    db_session.add(d3)
    s3 = SessionModel(id=new_id(), owner_id=user_id, uploaded_file_id=f3, draft_id=d3.id, quotation_ref="RL260000003", quotation_status="pending")
    db_session.add(s3)
    db_session.flush()

    veh3, alert3 = get_or_create_vehicle_tracking(
        db=db_session,
        vehicle_no="JMC 8218",
        customer_name="Alice Tan",
        validity_date="2028-05-15",
        session_id=s3.id,
    )
    db_session.commit()

    assert veh3 is not None
    assert veh3.id == veh.id
    assert alert3 is not None
    assert alert3["previous_owner"] == "Sadik"
    assert alert3["new_owner"] == "Alice Tan"
    assert "Reassigning owner" in alert3["message"]

    # Verify ownership sequence: Sadik is sequence 1 (is_current=False), Alice Tan is sequence 2 (is_current=True)
    ownerships3 = db_session.query(VehicleOwnership).filter_by(vehicle_id=veh.id).order_by(VehicleOwnership.sequence_order.asc()).all()
    assert len(ownerships3) == 2
    assert ownerships3[0].customer_name == "Sadik"
    assert ownerships3[0].is_current is False
    assert ownerships3[1].customer_name == "Alice Tan"
    assert ownerships3[1].sequence_order == 2
    assert ownerships3[1].is_current is True

    # 4. Fourth quote: Historical older quote uploaded for Bob (2025-01-01)
    f4 = new_id()
    d4 = QuotationDraft(id=new_id(), owner_id=user_id, uploaded_file_id=f4, fields={})
    db_session.add(d4)
    s4 = SessionModel(id=new_id(), owner_id=user_id, uploaded_file_id=f4, draft_id=d4.id, quotation_ref="RL260000004", quotation_status="pending")




    db_session.add(s4)
    db_session.flush()

    veh4, alert4 = get_or_create_vehicle_tracking(
        db=db_session,
        vehicle_no="JMC 8218",
        customer_name="Bob Older",
        validity_date="2025-01-01",
        session_id=s4.id,
    )
    db_session.commit()

    # Current owner must still be Alice Tan since Bob's quote is older
    assert veh4 is not None
    assert veh4.current_owner_name == "Alice Tan"
    assert alert4 is None

    # 5. Check full vehicle history API helper
    history = get_vehicle_history(db_session, "JMC 8218")
    assert history["found"] is True
    assert history["vehicle"]["vehicle_no"] == "JMC 8218"
    assert history["vehicle"]["current_owner_name"] == "Alice Tan"
    assert len(history["ownerships"]) == 3
    assert history["ownerships"][0]["sequence_label"] == "1st Owner"
    assert history["ownerships"][2]["sequence_label"] == "2nd Owner"


def test_deal_cycle_superseding_and_policy_renewals(db_session: Session):
    user_id = new_id()

    # 1. Primary quote session for vehicle VQL 5852
    f1 = new_id()
    d1 = QuotationDraft(id=new_id(), owner_id=user_id, uploaded_file_id=f1, fields={})
    db_session.add(d1)
    s1 = SessionModel(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=f1,
        draft_id=d1.id,
        quotation_ref="RL260000101",
        quotation_status="pending",
    )
    db_session.add(s1)
    db_session.flush()

    veh1, _ = get_or_create_vehicle_tracking(
        db=db_session,
        vehicle_no="VQL 5852",
        customer_name="John Doe",
        validity_date="2026-09-20",
        session_id=s1.id,
    )
    db_session.commit()

    assert veh1 is not None
    cycle_id_1 = assign_or_get_deal_cycle(db_session, s1, veh1.vehicle_no)
    assert cycle_id_1 is not None
    assert s1.deal_cycle_id == cycle_id_1
    assert "VQL5852" in cycle_id_1

    # 2. Competitor / alternative quote for the same vehicle
    f2 = new_id()
    d2 = QuotationDraft(id=new_id(), owner_id=user_id, uploaded_file_id=f2, fields={})
    db_session.add(d2)
    s2 = SessionModel(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=f2,
        draft_id=d2.id,
        quotation_ref="RL260000102",
        quotation_status="pending",
    )
    db_session.add(s2)
    db_session.flush()

    get_or_create_vehicle_tracking(
        db=db_session,
        vehicle_no="VQL 5852",
        customer_name="John Doe",
        validity_date="2026-09-21",
        session_id=s2.id,
    )
    db_session.commit()

    cycle_id_2 = assign_or_get_deal_cycle(db_session, s2, veh1.vehicle_no)
    assert cycle_id_2 == cycle_id_1
    assert s2.deal_cycle_id == cycle_id_1

    # 3. Mark primary quote as HIT (won) with 1-year coverage
    res = update_quotation_status(
        db=db_session,
        session_id=s1.id,
        status="hit",
        won_premium=1850.50,
        coverage_start_date="2026-09-01",
        coverage_end_date="2027-08-31",
        user_id=user_id,
    )
    db_session.commit()

    assert res["quotation_status"] == "hit"
    assert s1.quotation_status == "hit"
    assert s1.coverage_start_date is not None
    assert s1.coverage_end_date is not None

    # 4. Sibling competitor quote S2 must be automatically marked as superseded
    db_session.refresh(s2)
    assert s2.quotation_status == "superseded"
    assert s2.closed_at is not None

    # 5. VehicleOwnership must have coverage dates and 90-day renewal alert date
    ownership = db_session.query(VehicleOwnership).filter_by(vehicle_id=veh1.id, is_current=True).first()
    assert ownership is not None
    assert ownership.coverage_start_date is not None
    assert ownership.coverage_end_date is not None
    assert ownership.policy_status == "active"
    assert ownership.renewal_alert_date is not None
    # 90 days before 2027-08-31 is 2027-06-02
    assert ownership.renewal_alert_date.year == 2027
    assert ownership.renewal_alert_date.month == 6

    # 6. Check upcoming renewals service helper
    renewals = get_upcoming_renewals(db_session, days_ahead=400)
    assert len(renewals) >= 1
    found_renewal = next((r for r in renewals if r["vehicle_no"] == "VQL 5852"), None)
    assert found_renewal is not None
    assert found_renewal["customer_name"] == "John Doe"
    assert found_renewal["policy_status"] == "active"


def test_plate_validation_and_customer_matching():
    # Plate validation
    assert is_valid_malaysian_plate("JJC 9250") is True
    assert is_valid_malaysian_plate("WTT 339") is True
    assert is_valid_malaysian_plate("VQL 5852") is True
    assert is_valid_malaysian_plate("SB 24 K") is True
    assert is_valid_malaysian_plate("WD 8302 E") is True

    # Bad plates / OCR leaks must be False
    assert is_valid_malaysian_plate("RM 2") is False
    assert is_valid_malaysian_plate("VehicleMake") is False
    assert is_valid_malaysian_plate("Trailer No") is False
    assert is_valid_malaysian_plate("-UNREGISTERED-") is False
    assert is_valid_malaysian_plate("UNKNOWN") is False
    assert is_valid_malaysian_plate("RM 191") is False
    assert is_valid_malaysian_plate("") is False
    assert is_valid_malaysian_plate(None) is False

    # Intelligent customer matching
    assert is_same_customer("LIM CHEE KEONG", "MR LIM CHEE KEONG") is True
    assert is_same_customer("LIM CHEE KEONG (DR)", "LIM CHEE KEONG") is True
    assert is_same_customer("M. A. TRANSPORTATION SDN BHD", "M.A. TRANSPORTATION SDN. BHD.") is True
    assert is_same_customer("LIM KEE", "AHMAD BIN ISMAIL") is False
    assert is_same_customer("CHUA AI FEN", "SADIKIN") is False


def test_vehicle_ownership_conflict_and_resolution(db_session: Session):
    user_id = new_id()

    # 1. Historical quote session from 2025: JJC 9250 insured by LIM KEE
    f1 = new_id()
    d1 = QuotationDraft(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=f1,
        fields={
            "vehicle_no": {"value": "JJC 9250"},
            "client_name": {"value": "LIM KEE"},
            "period_of_insurance_from": {"value": "10/05/2025"},
            "car_model": {"value": "Honda City 1.5L"},
        },
    )
    db_session.add(d1)
    s1 = SessionModel(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=f1,
        draft_id=d1.id,
        quotation_ref="RL250000142",
        quotation_status="pending",
    )
    db_session.add(s1)
    db_session.flush()

    # Register initial vehicle tracking
    veh, _ = get_or_create_vehicle_tracking(
        db=db_session,
        vehicle_no="JJC 9250",
        customer_name="LIM KEE",
        validity_date="2025-05-10",
        session_id=s1.id,
        brand="HONDA",
        model="City 1.5L",
    )
    db_session.commit()
    assert veh is not None
    assert veh.current_owner_name == "LIM KEE"

    # 2. New quote in 2026 for JJC 9250 under AHMAD BIN ISMAIL
    f2 = new_id()
    d2 = QuotationDraft(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=f2,
        fields={
            "vehicle_no": {"value": "JJC 9250"},
            "client_name": {"value": "AHMAD BIN ISMAIL"},
            "period_of_insurance_from": {"value": "15/06/2026"},
            "car_model": {"value": "Honda City 1.5L"},
        },
    )
    db_session.add(d2)
    s2 = SessionModel(
        id=new_id(),
        owner_id=user_id,
        uploaded_file_id=f2,
        draft_id=d2.id,
        quotation_ref="RL260000088",
        quotation_status="pending",
    )
    db_session.add(s2)
    db_session.commit()

    # Conflict check must detect that JJC 9250 has an ownership conflict
    conflict = check_vehicle_ownership_conflict(db_session, s2.id)
    assert conflict["has_conflict"] is True
    assert conflict["resolved"] is False
    assert conflict["vehicle_no"] == "JJC 9250"
    assert conflict["previous_owner"] == "LIM KEE"
    assert conflict["new_customer"] == "AHMAD BIN ISMAIL"
    assert conflict["new_session_ref"] == "RL260000088"

    # 3. Resolve conflict with Option 1: Car Sold / New Owner
    res = resolve_vehicle_ownership(
        db=db_session,
        session_id=s2.id,
        resolution_type="car_sold_new_owner",
        user_id=user_id,
        notes="LIM KEE sold the car; AHMAD is the new owner",
    )
    assert res["success"] is True

    # Vehicle current owner must now be AHMAD BIN ISMAIL
    db_session.refresh(veh)
    assert veh.current_owner_name == "AHMAD BIN ISMAIL"

    # Conflict check on s2 must now return resolved = True
    post_conflict = check_vehicle_ownership_conflict(db_session, s2.id)
    assert post_conflict["has_conflict"] is False
    assert post_conflict["resolved"] is True


