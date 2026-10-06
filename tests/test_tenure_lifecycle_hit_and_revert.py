"""Hermetic tests for insurance tenure stage history and auto-renewal lifecycle upon HIT/Revert/Drop."""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes
from app.api.deps import current_user, get_db
from app.models.tables import Base, InsuranceTenure, TrackedVehicle, User, new_id
from app.services.insurance_tenure_service import (
    create_next_year_renewal_tenure,
    record_stage_timestamp,
    remove_auto_created_next_year_tenure,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_user(db_session: Session):
    user = User(
        id=new_id(),
        email="staff@risklocker.local",
        password_hash="dummy_hash",
        name="Staff Member",
        role="staff",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def client(db_session: Session, test_user: User):
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[current_user] = lambda: test_user
    with TestClient(app) as test_client:
        yield test_client


def _make_tenure(db: Session, user: User, vehicle_no: str = "WXY1234", year: int = 2026) -> InsuranceTenure:
    vehicle = TrackedVehicle(
        id=new_id(),
        vehicle_no=vehicle_no,
        car_brand="Mercedes-Benz",
        car_model="S 400 L Hybrid",
        engine_cc="3498",
    )
    db.add(vehicle)
    db.flush()

    start = datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=vehicle.id,
        vehicle_no=vehicle_no,
        customer_name="Tan Sri Dato",
        coverage_start_date=start,
        coverage_end_date=end,
        expiry_month="December",
        status="draft",
        stage="Issue Policy",
        created_by_id=user.id,
        road_tax=350.0,
        runner_fee=20.0,
        stage_history={"Quotations": start.isoformat(), "Issue Policy": start.isoformat()},
    )
    db.add(tenure)
    db.commit()
    db.refresh(tenure)
    return tenure


def test_record_stage_timestamp_updates_history(db_session: Session, test_user: User):
    tenure = _make_tenure(db_session, test_user)
    record_stage_timestamp(tenure, "Material to Client")
    db_session.commit()

    assert "Material to Client" in tenure.stage_history
    assert tenure.stage_history["Material to Client"].endswith("+00:00") or "T" in tenure.stage_history["Material to Client"]


def test_hit_creates_next_year_empty_renewal(client: TestClient, db_session: Session, test_user: User):
    tenure = _make_tenure(db_session, test_user, vehicle_no="WXY1234", year=2026)

    # Patch stage to Close - Win (HIT)
    res = client.patch(
        f"/api/tenures/{tenure.id}/ledger-fields",
        json={"stage": "Close - Win", "status": "hit"},
    )
    assert res.status_code == 200

    # Verify next year's 2027 renewal tenure was created
    next_tenure = db_session.scalar(
        select(InsuranceTenure).where(
            InsuranceTenure.previous_tenure_id == tenure.id,
            InsuranceTenure.is_discarded == False,
        )
    )
    assert next_tenure is not None
    assert next_tenure.stage == "Quotations"
    assert next_tenure.status == "draft"
    assert next_tenure.coverage_start_date.year == 2027
    assert next_tenure.vehicle_no == "WXY1234"
    assert next_tenure.customer_name == "Tan Sri Dato"
    assert len(next_tenure.sessions) == 0
    assert len(next_tenure.comparison_entries) == 0


def test_revert_hit_deletes_empty_next_year_renewal(client: TestClient, db_session: Session, test_user: User):
    tenure = _make_tenure(db_session, test_user, vehicle_no="VAA8888", year=2026)

    # 1. Mark as HIT
    client.patch(
        f"/api/tenures/{tenure.id}/ledger-fields",
        json={"stage": "Close - Win", "status": "hit"},
    )
    next_tenure = db_session.scalar(
        select(InsuranceTenure).where(InsuranceTenure.previous_tenure_id == tenure.id)
    )
    assert next_tenure is not None

    # 2. Revert back to Issue Policy
    revert_res = client.patch(
        f"/api/tenures/{tenure.id}/ledger-fields",
        json={"stage": "Issue Policy", "status": "draft"},
    )
    assert revert_res.status_code == 200

    # 3. Verify next tenure was cleanly deleted
    reverted_next = db_session.scalar(
        select(InsuranceTenure).where(InsuranceTenure.previous_tenure_id == tenure.id)
    )
    assert reverted_next is None


def test_miss_or_discarded_does_not_create_next_year_renewal(client: TestClient, db_session: Session, test_user: User):
    tenure = _make_tenure(db_session, test_user, vehicle_no="KKL9999", year=2026)

    # Mark as Close - Lose (dropped)
    res = client.patch(
        f"/api/tenures/{tenure.id}/ledger-fields",
        json={"stage": "Close - Lose", "status": "miss", "is_discarded": True},
    )
    assert res.status_code == 200

    next_tenure = db_session.scalar(
        select(InsuranceTenure).where(InsuranceTenure.previous_tenure_id == tenure.id)
    )
    assert next_tenure is None
