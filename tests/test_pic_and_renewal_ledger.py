"""Hermetic tests for Person In Charge (PIC) / SubAgents and Motor Renewal Ledger APIs."""

from datetime import datetime, timezone
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes
from app.api.deps import current_user, get_db
from app.models.tables import Base, InsuranceTenure, PersonInCharge, TrackedVehicle, User, new_id


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


def test_pic_crud_and_metrics(client: TestClient, db_session: Session):
    # 1. Create a SubAgent with BNI group and 2% commission
    res_sub = client.post(
        "/api/pics",
        json={
            "name": "Gina Tee",
            "type": "subagent",
            "agency_group": "BNI",
            "commission_rate": 2.0,
            "phone": "+60123456789",
            "email": "gina@bni.local",
            "notes": "Handles high volume corporate renewals",
        },
    )
    assert res_sub.status_code == 201
    gina = res_sub.json()
    assert gina["name"] == "Gina Tee"
    assert gina["type"] == "subagent"
    assert gina["commission_rate"] == 2.0

    # 2. Create a Company Personnel (0% commission)
    res_pic = client.post(
        "/api/pics",
        json={
            "name": "Tan Yao Feng (Fleet Manager)",
            "type": "company_personnel",
            "agency_group": None,
            "commission_rate": 0.0,
            "phone": "+60198765432",
        },
    )
    assert res_pic.status_code == 201
    tan = res_pic.json()
    assert tan["name"] == "Tan Yao Feng (Fleet Manager)"
    assert tan["commission_rate"] == 0.0

    # 3. List PICs with type filter
    res_list = client.get("/api/pics?type=subagent")
    assert res_list.status_code == 200
    subagents = res_list.json()
    assert len(subagents) == 1
    assert subagents[0]["name"] == "Gina Tee"

    # 4. Update PIC
    res_update = client.patch(
        f"/api/pics/{gina['id']}",
        json={"phone": "+60129998877", "commission_rate": 2.5},
    )
    assert res_update.status_code == 200
    assert res_update.json()["phone"] == "+60129998877"
    assert res_update.json()["commission_rate"] == 2.5

    # 5. Delete PIC
    res_del = client.delete(f"/api/pics/{tan['id']}")
    assert res_del.status_code == 200
    assert res_del.json()["ok"] is True


def test_tenure_stage_summary_and_ledger_fields(client: TestClient, db_session: Session):
    # 1. Create a tracked vehicle and tenure for January 2027
    veh = TrackedVehicle(id=new_id(), vehicle_no="JYP3000")
    db_session.add(veh)
    db_session.flush()

    now = datetime(2027, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2027, 1, 31, 23, 59, 59, tzinfo=timezone.utc)

    t1 = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=veh.id,
        vehicle_no="JYP3000",
        customer_name="TAN YAO FENG",
        coverage_start_date=now,
        coverage_end_date=end,
        expiry_month="2027-01",
        stage="Quotations",
        business_type="New Business",
        comment="Quote for 2027",
    )
    t2 = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=veh.id,
        vehicle_no="JWR8053",
        customer_name="CSH BAKERY & CONFECTIONERY",
        coverage_start_date=now,
        coverage_end_date=end,
        expiry_month="2027-01",
        stage="UCD Invoice to Client",
        business_type="Renewal",
        key_in_ucd=True,
    )
    db_session.add_all([t1, t2])
    db_session.commit()

    # 2. Test Stage KPI Summary API
    res_kpi = client.get("/api/tenures/stage-summary?year=2027&month=1")
    assert res_kpi.status_code == 200
    kpi_data = res_kpi.json()
    assert kpi_data["quotations"] == 1
    assert kpi_data["ucd_invoice_to_client"] == 1
    assert kpi_data["total"] == 2

    # 3. Test Patching Ledger Fields inline
    res_patch = client.patch(
        f"/api/tenures/{t1.id}/ledger-fields",
        json={
            "stage": "UCD Invoice to Client",
            "key_in_ucd": True,
            "print_roadtax": "Yes",
            "roadtax_receipt": "Yes",
            "client_payment_received": True,
            "sub_agent_name": "Gina Tee",
            "comment": "Keyed in UCD, roadtax printed",
        },
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["stage"] == "UCD Invoice to Client"

    # 4. Verify GET /api/tenures returns the updated ledger fields
    res_list = client.get("/api/tenures?year=2027&month=1")
    assert res_list.status_code == 200
    items = res_list.json()["items"]
    assert len(items) == 2
    patched_item = next(i for i in items if i["id"] == t1.id)
    assert patched_item["stage"] == "UCD Invoice to Client"
    assert patched_item["key_in_ucd"] is True
    assert patched_item["print_roadtax"] == "Yes"
    assert patched_item["sub_agent_name"] == "Gina Tee"
    assert patched_item["comment"] == "Keyed in UCD, roadtax printed"


def test_create_tenure_with_chassis_number_and_batch_loading(client: TestClient, db_session: Session):
    """Verify creating a vehicle policy deal anchored on Chassis No. for unregistered vehicles."""
    res_create = client.post(
        "/api/tenures",
        json={
            "customer_name": "Datuk Seri Bernard",
            "chassis_no": "VIN-BMW-2026-XYZ",
            "coverage_start_date": "2026-10-15",
            "coverage_end_date": "2027-10-14",
            "ic_no": "750312-10-5566",
            "car_model": "BMW i4 eDrive35",
            "sub_agent_name": "Gina Tee",
            "windscreen_target": 3500.0,
            "road_tax": 0.0,
            "runner_fee": 10.0,
        },
    )
    assert res_create.status_code == 200
    deal = res_create.json()
    assert deal["chassis_no"] == "VIN-BMW-2026-XYZ"
    assert "VIN" in deal["vehicle_no"]
    assert deal["customer_name"] == "Datuk Seri Bernard"

    # Query ledger endpoint to ensure batch session loading works cleanly
    res_list = client.get("/api/tenures?search=Bernard")
    assert res_list.status_code == 200
    items = res_list.json()["items"]
    assert len(items) >= 1
    found = next(i for i in items if i["id"] == deal["id"])
    assert "VIN" in found["vehicle_no"]
    assert found["customer_name"] == "Datuk Seri Bernard"
    assert found["sub_agent_name"] == "Gina Tee"

