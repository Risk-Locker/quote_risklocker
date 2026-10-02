"""Hermetic tests for full tenure month presence, car counts, and chassis fallback."""

from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.tables import Base, InsuranceTenure, TrackedVehicle, User
from app.api.routers.tenures import list_tenure_months, get_tenure_yoy_stats, list_tenures
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


def test_month_stats_start_and_end_counts(db_session: Session):
    dummy_user = User(id="u1", email="admin@risklocker.local", role="admin")

    # Tenure 1: Starts in May 2027, Ends in May 2028
    resolve_or_create_tenure(
        db_session,
        vehicle_no="VAA 1111",
        customer_name="Customer 1",
        start_date=datetime(2027, 5, 10, tzinfo=timezone.utc),
        end_date=datetime(2028, 5, 9, tzinfo=timezone.utc),
    )
    # Tenure 2: Starts in Jan 2027, Ends in May 2027
    resolve_or_create_tenure(
        db_session,
        vehicle_no="VBB 2222",
        customer_name="Customer 2",
        start_date=datetime(2027, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2027, 5, 31, tzinfo=timezone.utc),
    )
    # Tenure 3: Starts in May 2027, Ends in Nov 2027
    resolve_or_create_tenure(
        db_session,
        vehicle_no="VCC 3333",
        customer_name="Customer 3",
        start_date=datetime(2027, 5, 15, tzinfo=timezone.utc),
        end_date=datetime(2027, 11, 14, tzinfo=timezone.utc),
    )
    db_session.commit()

    res = list_tenure_months(show_hidden=False, db=db_session, user=dummy_user)
    months = res["months"]
    may_2027 = next((m for m in months if m["month"] == "2027-05"), None)

    assert may_2027 is not None
    # In May 2027: 2 starting (Customer 1 & 3), 1 ending (Customer 2)
    assert may_2027["start_count"] == 2
    assert may_2027["end_count"] == 1
    # Total distinct tenures present in May 2027 is 3!
    assert may_2027["total"] == 3
    assert may_2027["cars"] == 3


def test_yoy_stats_car_and_period_counts(db_session: Session):
    dummy_user = User(id="u1", email="admin@risklocker.local", role="admin")

    # 2 tenures on the SAME vehicle in 2027
    resolve_or_create_tenure(
        db_session,
        vehicle_no="CAR 888",
        customer_name="Alice",
        start_date=datetime(2027, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2027, 6, 30, tzinfo=timezone.utc),
    )
    resolve_or_create_tenure(
        db_session,
        vehicle_no="CAR 888",
        customer_name="Alice",
        start_date=datetime(2027, 7, 1, tzinfo=timezone.utc),
        end_date=datetime(2027, 12, 31, tzinfo=timezone.utc),
    )
    # 1 tenure on a DIFFERENT vehicle in 2027
    resolve_or_create_tenure(
        db_session,
        vehicle_no="CAR 999",
        customer_name="Bob",
        start_date=datetime(2027, 3, 1, tzinfo=timezone.utc),
        end_date=datetime(2028, 2, 28, tzinfo=timezone.utc),
    )
    db_session.commit()

    stats = get_tenure_yoy_stats(show_hidden=False, db=db_session, user=dummy_user)
    years = stats["years"]
    y2027 = next((y for y in years if y["year"] == "2027"), None)

    assert y2027 is not None
    # 3 total periods involved in 2027
    assert y2027["total"] == 3
    # 2 distinct cars (CAR 888, CAR 999)
    assert y2027["cars"] == 2
