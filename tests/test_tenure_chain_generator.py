"""Hermetic unit tests for perpetual multi-year tenure chain generation and cohort alignment."""

from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.tables import (
    Base,
    InsuranceTenure,
    TrackedVehicle,
)
from app.services.insurance_tenure_service import (
    ensure_vehicle_tenure_chain,
    resolve_or_create_tenure,
)


@pytest.fixture
def db_session():
    """In-memory SQLite hermetic database fixture."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def test_ensure_vehicle_tenure_chain_auto_generates_future_and_multi_year(db_session: Session):
    """Verify default upcoming renewal projection and full multi-year chain backfill."""
    start_dt = datetime(2026, 1, 17, tzinfo=timezone.utc)
    end_dt = datetime(2027, 1, 16, tzinfo=timezone.utc)

    # Ingest a tenure for JTV 7029
    tenure = resolve_or_create_tenure(
        db_session,
        vehicle_no="JTV 7029",
        customer_name="HAW TRANSPORT CO",
        start_date=start_dt,
        end_date=end_dt,
    )
    db_session.commit()

    assert tenure.id is not None
    assert tenure.tracked_vehicle_id is not None
    assert tenure.expiry_month == "2027-01"

    # Default projection creates anchor (2026-2027, exp 2027) + upcoming (exp 2028, exp 2029) => 3 slots
    initial_tenures = db_session.scalars(
        select(InsuranceTenure)
        .where(InsuranceTenure.tracked_vehicle_id == tenure.tracked_vehicle_id)
        .order_by(InsuranceTenure.coverage_start_date.asc())
    ).all()
    assert len(initial_tenures) == 3

    # Now run multi-year backfill across 2024-2029
    ensure_vehicle_tenure_chain(
        db_session,
        tenure,
        target_years=(2024, 2025, 2026, 2027, 2028, 2029),
    )
    db_session.commit()

    all_tenures = db_session.scalars(
        select(InsuranceTenure)
        .where(InsuranceTenure.tracked_vehicle_id == tenure.tracked_vehicle_id)
        .order_by(InsuranceTenure.coverage_start_date.asc())
    ).all()

    # Target years (2024, 2025, 2026, 2027, 2028, 2029) => 6 total slots
    assert len(all_tenures) == 6

    # Verify each year slot exists
    years = [t.coverage_start_date.year for t in all_tenures]
    assert 2023 in years or 2024 in years
    assert 2025 in years
    assert 2026 in years
    assert 2027 in years
    assert 2028 in years

    # Verify that chain IDs are linked
    for t in all_tenures:
        assert t.tenure_chain_id == tenure.tenure_chain_id
        assert t.vehicle_no == "JTV 7029"

    # Verify projected flags
    projected_tenures = [t for t in all_tenures if t.id != tenure.id]
    for pt in projected_tenures:
        assert pt.is_projected is True
        assert pt.status in ("upcoming", "untracked")

    # Verify original tenure is NOT projected
    assert tenure.is_projected is False


def test_tenure_chain_idempotency(db_session: Session):
    """Calling ensure_vehicle_tenure_chain multiple times should not create duplicate tenures."""
    start_dt = datetime(2026, 10, 11, tzinfo=timezone.utc)
    end_dt = datetime(2027, 10, 10, tzinfo=timezone.utc)

    tenure = resolve_or_create_tenure(
        db_session,
        vehicle_no="JTK 343",
        customer_name="TEST CLIENT",
        start_date=start_dt,
        end_date=end_dt,
    )
    db_session.commit()

    count_before = len(
        db_session.scalars(
            select(InsuranceTenure).where(InsuranceTenure.tracked_vehicle_id == tenure.tracked_vehicle_id)
        ).all()
    )

    # Call again explicitly with target years
    ensure_vehicle_tenure_chain(
        db_session,
        tenure,
        target_years=(2024, 2025, 2026, 2027, 2028, 2029),
    )
    db_session.commit()

    count_intermediate = len(
        db_session.scalars(
            select(InsuranceTenure).where(InsuranceTenure.tracked_vehicle_id == tenure.tracked_vehicle_id)
        ).all()
    )

    # Call a third time
    ensure_vehicle_tenure_chain(
        db_session,
        tenure,
        target_years=(2024, 2025, 2026, 2027, 2028, 2029),
    )
    db_session.commit()

    count_after = len(
        db_session.scalars(
            select(InsuranceTenure).where(InsuranceTenure.tracked_vehicle_id == tenure.tracked_vehicle_id)
        ).all()
    )

    assert count_intermediate == count_after
