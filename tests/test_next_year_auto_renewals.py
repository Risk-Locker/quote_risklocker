"""Hermetic unit tests for next-year (2027) auto-renewal roll-forward and marketing comparison baseline."""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes
from app.api.deps import current_user, get_db
from app.models.tables import (
    Base,
    InsuranceCompany,
    InsuranceTenure,
    QuotationDraft,
    Session as SessionModel,
    TenureComparisonEntry,
    TrackedVehicle,
    User,
    new_id,
)
from app.services.insurance_tenure_service import (
    create_next_year_renewal_tenure,
    ensure_next_year_renewal_tenures,
)
from app.services.marketing_comparison_service import get_marketing_comparison


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


def _make_vehicle(db: Session, vehicle_no: str, model: str = "Honda Civic") -> TrackedVehicle:
    v = TrackedVehicle(
        id=new_id(),
        vehicle_no=vehicle_no,
        car_brand="Honda",
        car_model=model,
        engine_cc="1498",
        manufacture_year=2022,
    )
    db.add(v)
    db.flush()
    return v


def test_ensure_next_year_renewal_tenures_roll_forward(db_session: Session, test_user: User):
    """Active 2026 vehicles that are never missed/dropped get 2027 renewal tenures."""
    v1 = _make_vehicle(db_session, "WXY 1234")
    v_drop = _make_vehicle(db_session, "BBA 9999")
    v_miss = _make_vehicle(db_session, "CCC 8888")

    # 1. Active vehicle 1 (eligible)
    t1 = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=v1.id,
        vehicle_no="WXY 1234",
        customer_name="Alice Tan",
        coverage_start_date=datetime(2026, 8, 15, 0, 0, 0, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 8, 14, 0, 0, 0, tzinfo=timezone.utc),
        expiry_month="2027-08",
        status="draft",
        stage="Quotations",
        business_type="Renewal",
        road_tax=90.0,
        runner_fee=15.0,
        is_discarded=False,
        is_projected=False,
    )

    # 2. Dropped vehicle (ineligible)
    t_dropped = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=v_drop.id,
        vehicle_no="BBA 9999",
        customer_name="Bob Drop",
        coverage_start_date=datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 4, 30, 0, 0, 0, tzinfo=timezone.utc),
        expiry_month="2027-04",
        status="draft",
        stage="Quotations",
        is_discarded=True,  # DROPPED
        is_projected=False,
    )

    # 3. Missed vehicle (ineligible)
    t_missed = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=v_miss.id,
        vehicle_no="CCC 8888",
        customer_name="Charlie Miss",
        coverage_start_date=datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 5, 31, 0, 0, 0, tzinfo=timezone.utc),
        expiry_month="2027-05",
        status="miss",  # MISSED
        stage="Close - Lose",
        is_discarded=False,
        is_projected=False,
    )

    db_session.add_all([t1, t_dropped, t_missed])
    db_session.commit()

    # Trigger ensure_next_year_renewal_tenures for 2027
    created = ensure_next_year_renewal_tenures(db_session, target_year=2027, user_id=test_user.id)
    assert len(created) == 1
    new_t = created[0]
    assert new_t.vehicle_no == "WXY 1234"
    assert new_t.customer_name == "Alice Tan"
    assert new_t.previous_tenure_id == t1.id
    assert new_t.coverage_start_date.year == 2027
    assert new_t.coverage_start_date.month == 8
    assert new_t.coverage_start_date.day == 15
    assert new_t.coverage_end_date.year == 2028
    assert new_t.coverage_end_date.month == 8
    assert new_t.coverage_end_date.day == 13
    assert new_t.road_tax == 90.0
    assert new_t.runner_fee == 15.0
    assert new_t.status == "draft"
    assert new_t.stage == "Quotations"
    assert new_t.is_projected is False
    assert new_t.is_discarded is False

    # Second call is idempotent (no duplicates)
    second_run = ensure_next_year_renewal_tenures(db_session, target_year=2027, user_id=test_user.id)
    assert len(second_run) == 0


def test_marketing_comparison_hydrates_previous_policy_baseline(db_session: Session, test_user: User):
    """Marketing comparison for 2027 tenure displays 2026 previous policy baseline."""
    # Create underwriter
    company = InsuranceCompany(id=new_id(), name="Allianz General Insurance")
    db_session.add(company)
    db_session.flush()

    v = _make_vehicle(db_session, "ABC 1122", model="Honda CR-V")

    # Create 2026 tenure with quotes
    t_2026 = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=v.id,
        vehicle_no="ABC 1122",
        customer_name="David Lim",
        coverage_start_date=datetime(2026, 9, 20, 0, 0, 0, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 9, 19, 0, 0, 0, tzinfo=timezone.utc),
        expiry_month="2027-09",
        status="hit",
        stage="Close - Win",
        won_premium=1450.0,
        winning_company_id=company.id,
        road_tax=120.0,
        runner_fee=20.0,
        ncd_percentage=55.0,
        is_discarded=False,
        is_projected=False,
    )
    db_session.add(t_2026)
    db_session.flush()

    # Add a comparison entry under 2026
    entry_2026 = TenureComparisonEntry(
        id=new_id(),
        tenure_id=t_2026.id,
        company_name="Allianz General Insurance",
        company_id=company.id,
        sum_insured=50000.0,
        valuation_type="market_value",
        motor_premium=1450.0,
        road_tax=120.0,
        runner_fee=20.0,
        total_payable=1590.0,
        towing_limit="Unlimited",
        towing_km="Unlimited",
        agreed_value=False,
        waiver_betterment=True,
        excess=0.0,
        rate_percentage=2.9,
        is_recommended=True,
    )
    db_session.add(entry_2026)
    db_session.commit()

    # Roll forward to 2027
    created = ensure_next_year_renewal_tenures(db_session, target_year=2027, user_id=test_user.id)
    assert len(created) == 1
    t_2027 = created[0]
    assert t_2027.previous_tenure_id == t_2026.id

    # Call get_marketing_comparison on t_2027
    res = get_marketing_comparison(db_session, t_2027.id)
    assert res is not None
    assert len(res["entries"]) == 0  # Empty comparison matrix ready for 2027 quotes!
    assert res["previous_policy"] is not None
    prev = res["previous_policy"]
    assert prev["id"] == t_2026.id
    assert prev["year"] == 2026
    assert prev["insurer"] == "Allianz General Insurance"
    assert prev["sum_insured"] == 50000.0
    assert prev["insurance_premium"] == 1450.0
    assert "20/09/2026" in prev["period"]


def test_api_yoy_stats_and_sync_endpoint(client: TestClient, db_session: Session, test_user: User):
    """API endpoints /stats/yoy and /sync-next-year-renewals surface 2027 renewals."""
    v = _make_vehicle(db_session, "KAA 5566", model="Toyota Corolla Cross")

    t_2026 = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=v.id,
        vehicle_no="KAA 5566",
        customer_name="Grace Wong",
        coverage_start_date=datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 9, 30, 0, 0, 0, tzinfo=timezone.utc),
        expiry_month="2027-09",
        status="draft",
        stage="Quotations",
        is_discarded=False,
        is_projected=False,
    )
    db_session.add(t_2026)
    db_session.commit()

    # Call GET /api/tenures/stats/yoy
    res = client.get("/api/tenures/stats/yoy")
    assert res.status_code == 200
    data = res.json()
    years = [y["year"] for y in data["years"]]
    assert "2026" in years
    assert "2027" in years  # 2027 is now surfaced!

    # Verify 2027 count in YoY stats
    y27 = next(y for y in data["years"] if y["year"] == "2027")
    assert y27["total"] >= 1
    assert y27["active"] >= 1
    assert y27["lost"] == 0

    # Call GET /api/tenures?year=2027
    res_list = client.get("/api/tenures?year=2027")
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert list_data["total"] >= 1
    veh_plates = [item["vehicle_no"] for item in list_data["items"]]
    assert "KAA 5566" in veh_plates

    # Call POST /api/tenures/sync-next-year-renewals
    res_sync = client.post("/api/tenures/sync-next-year-renewals?target_year=2027")
    assert res_sync.status_code == 200
    sync_data = res_sync.json()
    assert sync_data["status"] == "success"
    assert sync_data["target_year"] == 2027
