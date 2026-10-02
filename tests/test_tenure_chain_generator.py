"""Hermetic unit tests verifying no automatic past or future tenure projection is generated."""

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
    auto_project_next_renewal,
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


def test_resolve_or_create_tenure_creates_single_policy_without_auto_projections(db_session: Session):
    """Verify that resolving or creating a tenure creates strictly ONE policy for the uploaded quotation period."""
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
    assert tenure.is_projected is False

    # Strictly 1 tenure created: NO automatic previous or future slots
    all_tenures = db_session.scalars(
        select(InsuranceTenure)
        .where(InsuranceTenure.tracked_vehicle_id == tenure.tracked_vehicle_id)
    ).all()
    assert len(all_tenures) == 1
    assert all_tenures[0].id == tenure.id


def test_ensure_vehicle_tenure_chain_and_auto_project_are_disabled(db_session: Session):
    """Calling ensure_vehicle_tenure_chain or auto_project_next_renewal does NOT generate dummy future slots."""
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

    # ensure_vehicle_tenure_chain returns empty list and creates 0 tenures
    result = ensure_vehicle_tenure_chain(
        db_session,
        tenure,
        target_years=(2024, 2025, 2026, 2027, 2028, 2029),
    )
    assert result == []

    # auto_project_next_renewal does not create a new tenure
    proj_result = auto_project_next_renewal(db_session, tenure.id)
    assert proj_result.id == tenure.id

    # Total tenures in DB remains exactly 1
    total_tenures = db_session.scalars(
        select(InsuranceTenure).where(InsuranceTenure.tracked_vehicle_id == tenure.tracked_vehicle_id)
    ).all()
    assert len(total_tenures) == 1
