"""Hermetic unit tests for custom vehicle creation, plate/brand updates in comparison matrix, and stage-summary parity."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_PROVIDER": "supabase_postgres",
        "DATABASE_URL": "postgresql://postgres:password@db.test.supabase.co:5432/postgres",
        "AUTH_HASH_SECRET": "test-auth-hash-secret-that-is-long-enough",
        "STORAGE_DRIVER": "supabase",
        "SUPABASE_URL": "https://project-ref.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
    }
)

from app.api import routes
from app.api.deps import current_user, get_db
from app.models.tables import (
    Base,
    InsuranceTenure,
    TrackedVehicle,
    User,
    new_id,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session):
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")

    admin = User(
        id=str(uuid4()),
        name="Admin Tester",
        email="admin@risklocker.local",
        password_hash="mock",
        role="admin",
    )
    db_session.add(admin)
    db_session.flush()

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[current_user] = lambda: admin

    with TestClient(app) as test_client:
        yield test_client


def test_create_custom_vehicle_endpoint(client: TestClient, db_session: Session):
    payload = {
        "vehicle_no": "VAA8888",
        "customer_name": "Tan Ah Kow",
        "ic_no": "901010-14-1234",
        "car_brand": "Toyota",
        "car_model": "Corolla Cross Hybrid",
        "manufacture_year": 2023,
        "engine_cc": "1798 CC",
        "coverage_start_date": "2026-10-15",
        "coverage_end_date": "2027-10-14",
        "windscreen_target": 1500.0,
    }

    res = client.post("/api/tenures", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["vehicle_no"] == "VAA8888"
    assert data["customer_name"] == "Tan Ah Kow"

    # Verify database persistence
    tenure = db_session.get(InsuranceTenure, data["id"])
    assert tenure is not None
    assert tenure.vehicle_no == "VAA8888"
    assert tenure.customer_name == "Tan Ah Kow"
    assert tenure.tracked_vehicle is not None
    assert tenure.tracked_vehicle.car_brand == "Toyota"
    assert tenure.tracked_vehicle.car_model == "Corolla Cross Hybrid"
    assert tenure.tracked_vehicle.manufacture_year == 2023
    assert tenure.tracked_vehicle.engine_cc == "1798 CC"


def test_update_fixed_costs_plate_and_brand(client: TestClient, db_session: Session):
    # 1. Create a blank tenure
    create_res = client.post(
        "/api/tenures",
        json={
            "vehicle_no": "UNPLATED",
            "customer_name": "Initial Customer",
            "car_brand": "Other",
            "car_model": "Unknown",
        },
    )
    assert create_res.status_code == 200
    tenure_id = create_res.json()["id"]

    # 2. Update plate and brand via /api/comparison/{tenure_id}/fixed-costs
    update_res = client.post(
        f"/api/comparison/{tenure_id}/fixed-costs",
        json={
            "vehicle_no": "WVV 1234",
            "car_brand": "Proton",
            "car_model": "X50 Flagship",
            "engine_cc": "1477 CC",
            "manufacture_year": 2022,
            "road_tax": 90.0,
            "runner_fee": 50.0,
            "windscreen_target": 1200.0,
        },
    )
    assert update_res.status_code == 200, update_res.text
    matrix_data = update_res.json()

    assert matrix_data["tenure"]["vehicle_no"] == "WVV1234"
    assert matrix_data["tenure"]["car_brand"] == "Proton"

    # Verify database state
    db_session.expire_all()
    tenure = db_session.get(InsuranceTenure, tenure_id)
    assert tenure.vehicle_no == "WVV1234"
    assert tenure.tracked_vehicle is not None
    assert tenure.tracked_vehicle.car_brand == "Proton"
    assert tenure.tracked_vehicle.car_model == "X50 Flagship"


def test_stage_summary_and_tenures_parity(client: TestClient, db_session: Session):
    # Create 3 tenures isolated in future year 2029:
    # t1: active in 2029-10 (start 2029-10-01, end 2030-09-30) - stage Quotations
    # t2: active in 2029-10 (start 2028-10-02, end 2029-10-01) - stage Issue Policy
    # t3: active in 2031-05 only (start 2031-05-01, end 2032-04-30) - stage Close - Win

    r1 = client.post(
        "/api/tenures",
        json={
            "vehicle_no": "PARITY1",
            "customer_name": "Customer 1",
            "stage": "Quotations",
            "coverage_start_date": "2029-10-01",
            "coverage_end_date": "2030-09-30",
        },
    )
    assert r1.status_code == 200

    r2 = client.post(
        "/api/tenures",
        json={
            "vehicle_no": "PARITY2",
            "customer_name": "Customer 2",
            "stage": "Issue Policy",
            "coverage_start_date": "2028-10-02",
            "coverage_end_date": "2029-10-01",
        },
    )
    assert r2.status_code == 200

    r3 = client.post(
        "/api/tenures",
        json={
            "vehicle_no": "PARITY3",
            "customer_name": "Customer 3",
            "stage": "Close - Win",
            "coverage_start_date": "2031-05-01",
            "coverage_end_date": "2032-04-30",
        },
    )
    assert r3.status_code == 200

    # 1. Query for month 2029-10
    sum_res = client.get("/api/tenures/stage-summary?year=2029&month=10")
    assert sum_res.status_code == 200
    sum_data = sum_res.json()
    assert sum_data["quotations"] == 1
    assert sum_data["issue_policy"] == 1
    assert sum_data["total"] == 2

    # Query list_tenures with same month
    list_res = client.get("/api/tenures?year=2029&month=2029-10&category=all")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] == 2
    assert list_data["total"] == sum_data["total"]

    # 2. Query for year 2029
    sum_year_res = client.get("/api/tenures/stage-summary?year=2029")
    assert sum_year_res.status_code == 200
    sum_year = sum_year_res.json()

    list_year_res = client.get("/api/tenures?year=2029&category=all")
    assert list_year_res.status_code == 200
    list_year = list_year_res.json()

    assert sum_year["total"] == 2
    assert list_year["total"] == 2
    assert sum_year["total"] == list_year["total"]


def make_test_session(
    db_session: Session,
    tenure_id: str,
    detected_company: str,
    document_type: str = "quotation",
    filename: str = "test.pdf",
) -> SessionModel:
    from app.models.tables import Batch, UploadedFile, QuotationDraft, Session as SessionModel, User
    from sqlalchemy import select
    user = db_session.scalars(select(User)).first()
    owner_id = user.id if user else str(uuid4())

    b = Batch(id=str(uuid4()), owner_id=owner_id, name="Test Batch")
    db_session.add(b)
    db_session.flush()

    uf = UploadedFile(
        id=str(uuid4()),
        batch_id=b.id,
        owner_id=owner_id,
        original_filename=filename,
        content_type="application/pdf",
        storage_path="mock/path.pdf",
        size_bytes=1000,
    )
    db_session.add(uf)
    db_session.flush()

    qd = QuotationDraft(
        id=str(uuid4()),
        uploaded_file_id=uf.id,
        owner_id=owner_id,
        fields={},
    )
    db_session.add(qd)
    db_session.flush()

    sess = SessionModel(
        id=str(uuid4()),
        owner_id=owner_id,
        uploaded_file_id=uf.id,
        draft_id=qd.id,
        tenure_id=tenure_id,
        detected_company=detected_company,
        document_type=document_type,
        status="active",
        is_tenure_active=True,
    )
    db_session.add(sess)
    db_session.flush()
    return sess


def test_covernote_never_in_marketing_comparison(client: TestClient, db_session: Session):
    # 1. Create a tenure
    t_res = client.post(
        "/api/tenures",
        json={
            "vehicle_no": "TEST_CN_EXCLUSION",
            "customer_name": "Test CN Exclude",
            "coverage_start_date": "2026-11-15",
            "coverage_end_date": "2027-11-14",
        },
    )
    assert t_res.status_code == 200
    tenure_id = t_res.json()["id"]

    # 2. Add an uploaded file and session with 'CoverNote' in filename
    make_test_session(
        db_session=db_session,
        tenure_id=tenure_id,
        detected_company="QBE Insurance",
        document_type="covernote",
        filename="20261002_TEST_CoverNote_QBE.pdf",
    )

    # 3. Add an underwriter quotation session
    make_test_session(
        db_session=db_session,
        tenure_id=tenure_id,
        detected_company="Allianz",
        document_type="quotation",
        filename="20261002_TEST_Quote_Allianz.pdf",
    )
    db_session.commit()

    # 4. Fetch marketing comparison
    comp_res = client.get(f"/api/comparison/{tenure_id}")
    assert comp_res.status_code == 200
    comp_data = comp_res.json()

    # Assert only Allianz is in entries, QBE CoverNote is NOT a quotation column
    entries = comp_data.get("entries", [])
    entry_companies = [e["company_name"] for e in entries]
    assert "Allianz" in entry_companies
    assert "QBE Insurance" not in entry_companies
    # Assert QBE is assigned as the cover note
    assert comp_data.get("covernote_policy") is not None
    assert comp_data["covernote_policy"]["company_name"] == "QBE Insurance"


def test_delete_comparison_entry_all_versions(client: TestClient, db_session: Session):
    from app.models.tables import Session as SessionModel, TenureComparisonEntry
    # 1. Create a tenure
    t_res = client.post(
        "/api/tenures",
        json={"vehicle_no": "TEST_DEL_VERSIONS", "customer_name": "Test Delete"},
    )
    assert t_res.status_code == 200
    tenure_id = t_res.json()["id"]

    # 2. Add two sessions/entries for the same company (v1 and v2)
    s1 = make_test_session(
        db_session=db_session,
        tenure_id=tenure_id,
        detected_company="Sompo",
        document_type="quotation",
        filename="quote_v1.pdf",
    )
    s2 = make_test_session(
        db_session=db_session,
        tenure_id=tenure_id,
        detected_company="Sompo",
        document_type="quotation",
        filename="quote_v2.pdf",
    )

    e1 = TenureComparisonEntry(
        id=str(uuid4()),
        tenure_id=tenure_id,
        session_id=s1.id,
        company_name="Sompo",
        version=1,
        sum_insured=50000.0,
        motor_premium=1500.0,
    )
    e2 = TenureComparisonEntry(
        id=str(uuid4()),
        tenure_id=tenure_id,
        session_id=s2.id,
        company_name="Sompo",
        version=2,
        sum_insured=50000.0,
        motor_premium=1400.0,
    )
    db_session.add_all([e1, e2])
    db_session.commit()

    # 3. Delete with all_versions=true
    del_res = client.delete(f"/api/comparison/{tenure_id}/entry/{e1.id}?all_versions=true")
    assert del_res.status_code == 200
    del_data = del_res.json()
    assert len(del_data["entries"]) == 0

    # 4. Verify sessions are trashed in db
    db_session.expire_all()
    s1_re = db_session.get(SessionModel, s1.id)
    s2_re = db_session.get(SessionModel, s2.id)
    assert s1_re.status == "trash"
    assert s2_re.status == "trash"


def test_yoy_stats_covers_start_and_end_year(client: TestClient, db_session: Session):
    # Create tenure spanning 2026 into 2027
    res = client.post(
        "/api/tenures",
        json={
            "vehicle_no": "YOY_TEST_2026_2027",
            "customer_name": "Test YoY",
            "coverage_start_date": "2026-11-15",
            "coverage_end_date": "2027-11-14",
        },
    )
    assert res.status_code == 200

    # Check YoY stats
    yoy_res = client.get("/api/tenures/stats/yoy")
    assert yoy_res.status_code == 200
    yoy_data = yoy_res.json()

    years_map = {y["year"]: y["total"] for y in yoy_data["years"]}
    assert years_map.get("2026", 0) >= 1
    assert years_map.get("2027", 0) >= 1
