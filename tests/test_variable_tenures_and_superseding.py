"""Hermetic tests for variable duration tenures, no auto-chaining, and collision superseding."""

from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.tables import Base, InsuranceTenure, TrackedVehicle
from app.services.insurance_tenure_service import resolve_or_create_tenure


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_variable_tenure_and_no_dummy_projections(db_session: Session):
    # Create a 4-month tenure: 2026-02-01 to 2026-06-01
    start_dt = datetime(2026, 2, 1, tzinfo=timezone.utc)
    end_dt = datetime(2026, 6, 1, tzinfo=timezone.utc)

    t1 = resolve_or_create_tenure(
        db_session,
        vehicle_no="VAA1234",
        customer_name="John Doe",
        start_date=start_dt,
        end_date=end_dt,
    )
    db_session.commit()

    assert t1.vehicle_no == "VAA1234"
    assert t1.coverage_start_date.date() == start_dt.date()
    assert t1.coverage_end_date.date() == end_dt.date()
    assert t1.is_hidden is False
    assert t1.superseded_by_tenure_id is None

    # Invariant: No dummy 1-year / 2-year projected future tenures auto-created
    all_tenures = list(db_session.scalars(select(InsuranceTenure)).all())
    assert len(all_tenures) == 1


def test_overlapping_tenure_collision_superseding(db_session: Session):
    # Existing tenure from July 2025 to June 2026
    start_1 = datetime(2025, 7, 1, tzinfo=timezone.utc)
    end_1 = datetime(2026, 6, 30, tzinfo=timezone.utc)

    t1 = resolve_or_create_tenure(
        db_session,
        vehicle_no="WXY9999",
        customer_name="Alice Smith",
        start_date=start_1,
        end_date=end_1,
    )
    db_session.commit()
    assert t1.is_hidden is False

    # A new quotation arrives on same vehicle in 2026 with overlapping date (e.g. 2026-03-01 to 2027-02-28)
    start_2 = datetime(2026, 3, 1, tzinfo=timezone.utc)
    end_2 = datetime(2027, 2, 28, tzinfo=timezone.utc)

    t2 = resolve_or_create_tenure(
        db_session,
        vehicle_no="WXY9999",
        customer_name="Alice Smith",
        start_date=start_2,
        end_date=end_2,
    )
    db_session.commit()

    db_session.refresh(t1)
    db_session.refresh(t2)

    # Invariant: t1 is superseded and marked is_hidden = True, pointing to t2
    assert t1.is_hidden is True
    assert t1.superseded_by_tenure_id == t2.id
    assert t2.is_hidden is False
