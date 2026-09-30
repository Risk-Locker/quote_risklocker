"""Hermetic unit tests for vehicle tracking by chassis number and plate assignment."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.tables import Base, TrackedVehicle
from app.services.vehicle_tracking_service import get_or_create_vehicle_tracking


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def test_unplated_new_car_tracked_by_chassis(db_session: Session):
    # Brand new car with no plate yet (plate is N/A or empty)
    veh1, _ = get_or_create_vehicle_tracking(
        db=db_session,
        vehicle_no="N/A",
        customer_name="Tan Ah Kow",
        validity_date="31-12-2026",
        brand="BYD",
        model="Seal Performance",
        chassis_no="LC0CE4BC9P0123456",
        engine_no="TZ200XSK",
    )
    assert veh1 is not None
    assert veh1.chassis_no == "LC0CE4BC9P0123456"
    assert veh1.engine_no == "TZ200XSK"
    assert veh1.vehicle_no.startswith("UNPLATED-")
    db_session.commit()

    # Second quotation uploaded for same new car while still unplated
    veh2, _ = get_or_create_vehicle_tracking(
        db=db_session,
        vehicle_no="",
        customer_name="Tan Ah Kow",
        validity_date="31-12-2026",
        chassis_no="LC0CE4BC9P0123456",
    )
    # Must resolve to the exact same TrackedVehicle!
    assert veh1.id == veh2.id


def test_plate_assigned_to_previously_unplated_car(db_session: Session):
    # Initial quote before registration
    veh1, _ = get_or_create_vehicle_tracking(
        db=db_session,
        vehicle_no="UNKNOWN",
        customer_name="Tan Ah Kow",
        validity_date="31-12-2026",
        brand="Proton",
        model="S70",
        chassis_no="PL1S70XXXX12345",
    )
    db_session.commit()
    assert veh1.vehicle_no.startswith("UNPLATED-")

    # Registration plate is officially assigned later: WXY 8888
    veh2, _ = get_or_create_vehicle_tracking(
        db=db_session,
        vehicle_no="WXY 8888",
        customer_name="Tan Ah Kow",
        validity_date="31-12-2026",
        chassis_no="PL1S70XXXX12345",
    )

    # Resolves to same vehicle and updates vehicle_no to the real plate!
    assert veh1.id == veh2.id
    assert veh2.vehicle_no == "WXY 8888"
    assert veh2.chassis_no == "PL1S70XXXX12345"
