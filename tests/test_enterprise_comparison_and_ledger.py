"""Hermetic tests for enterprise comparison matrix and renewal ledger features."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
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
    QuotationDraft,
    Session as SessionModel,
    StorageStatus,
    TenureComparisonEntry,
    TrackedVehicle,
    UploadedFile,
    User,
    new_id,
)
from app.services.marketing_comparison_service import calculate_exact_rate


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
def admin_user(db_session: Session) -> User:
    admin = User(
        id=str(uuid4()),
        name="Admin Tester",
        email="admin@risklocker.local",
        password_hash="mock",
        role="admin",
    )
    db_session.add(admin)
    db_session.flush()
    return admin


@pytest.fixture
def client(db_session: Session, admin_user: User):
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[current_user] = lambda: admin_user

    with TestClient(app) as test_client:
        yield test_client


from app.models.tables import Batch


def _create_uploaded_file(db_session: Session, owner_id: str) -> UploadedFile:
    batch = Batch(id=new_id(), owner_id=owner_id, name="Test Batch")
    db_session.add(batch)
    db_session.flush()

    uf = UploadedFile(
        id=new_id(),
        batch_id=batch.id,
        owner_id=owner_id,
        original_filename="quote.pdf",
        content_type="application/pdf",
        size_bytes=2048,
        storage_path="uploads/quote.pdf",
        storage_status=StorageStatus.AVAILABLE.value,
    )
    db_session.add(uf)
    db_session.flush()
    return uf


def test_exact_rate_formula_precision_and_takaful():
    basic_prem = 1234.56
    sum_ins = 50000.0
    rate_str, factor = calculate_exact_rate(basic_prem, sum_ins)
    assert factor is not None
    # 1234.56 / 50000.0 = 0.0246912 -> rounded to 6 decimals: 0.024691
    assert abs(factor - 0.024691) < 0.00001
    assert rate_str == "0.024691"


def test_comparison_entry_hide_and_manual_rank(client: TestClient, db_session: Session):
    vehicle = TrackedVehicle(
        id=new_id(),
        vehicle_no="ABC1234",
        car_brand="Toyota",
        car_model="Vios 1.5G",
    )
    db_session.add(vehicle)

    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=vehicle.id,
        vehicle_no="ABC1234",
        customer_name="John Doe",
        coverage_start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 1, 1, tzinfo=timezone.utc),
        expiry_month="2027-01",
        road_tax=70.0,
        runner_fee=50.0,
    )
    db_session.add(tenure)
    db_session.flush()

    entry1 = TenureComparisonEntry(
        id=new_id(),
        tenure_id=tenure.id,
        company_name="Allianz General Insurance Company (Malaysia) Berhad",
        sum_insured=50000.0,
        motor_premium=1200.0,
        total_payable=1320.0,
        sort_order=1,
    )
    entry2 = TenureComparisonEntry(
        id=new_id(),
        tenure_id=tenure.id,
        company_name="Takaful Ikhlas General Berhad",
        sum_insured=50000.0,
        motor_premium=1100.0,
        total_payable=1220.0,
        sort_order=2,
    )
    db_session.add_all([entry1, entry2])
    db_session.commit()

    # 1. Fetch comparison matrix
    res = client.get(f"/api/comparison/{tenure.id}")
    assert res.status_code == 200
    data = res.json()
    assert len(data["entries"]) == 2
    # Check that Takaful uses 'Basic Contribution' and Conventional uses 'Basic Premium'
    takaful_entry = next(e for e in data["entries"] if "Takaful" in e["company_name"])
    conv_entry = next(e for e in data["entries"] if "Allianz" in e["company_name"])
    assert takaful_entry["basic_figure_name"] == "Basic Contribution"
    assert conv_entry["basic_figure_name"] == "Basic Premium"

    # 2. Hide entry2
    patch_res = client.patch(
        f"/api/comparison/{tenure.id}/entries/{entry2.id}",
        json={"is_hidden": True},
    )
    assert patch_res.status_code == 200
    res2 = client.get(f"/api/comparison/{tenure.id}")
    entries_after_hide = res2.json()["entries"]
    e2_updated = next(e for e in entries_after_hide if e["id"] == entry2.id)
    assert e2_updated["is_hidden"] is True

    # 3. Set manual rank on entry1
    patch_rank = client.patch(
        f"/api/comparison/{tenure.id}/entries/{entry1.id}",
        json={"manual_rank": 1},
    )
    assert patch_rank.status_code == 200
    res3 = client.get(f"/api/comparison/{tenure.id}")
    e1_updated = next(e for e in res3.json()["entries"] if e["id"] == entry1.id)
    assert e1_updated["manual_rank"] == 1
    assert e1_updated["rank"] == 1


def test_duplicate_resolution_endpoint(client: TestClient, db_session: Session, admin_user: User):
    vehicle = TrackedVehicle(id=new_id(), vehicle_no="DUP9999")
    db_session.add(vehicle)

    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=vehicle.id,
        vehicle_no="DUP9999",
        customer_name="Test Customer",
        coverage_start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 1, 1, tzinfo=timezone.utc),
        expiry_month="2027-01",
    )
    db_session.add(tenure)
    db_session.flush()

    uf1 = _create_uploaded_file(db_session, admin_user.id)
    uf2 = _create_uploaded_file(db_session, admin_user.id)

    draft1 = QuotationDraft(id=str(uuid4()), owner_id=admin_user.id, uploaded_file_id=uf1.id, fields={})
    draft2 = QuotationDraft(id=str(uuid4()), owner_id=admin_user.id, uploaded_file_id=uf2.id, fields={})
    db_session.add_all([draft1, draft2])
    db_session.flush()

    sess1 = SessionModel(
        id=str(uuid4()),
        owner_id=admin_user.id,
        uploaded_file_id=uf1.id,
        draft_id=draft1.id,
        tenure_id=tenure.id,
        detected_company="Allianz General Insurance Company (Malaysia) Berhad",
        tenure_version=1,
        is_tenure_active=True,
        status="active",
    )
    sess2 = SessionModel(
        id=str(uuid4()),
        owner_id=admin_user.id,
        uploaded_file_id=uf2.id,
        draft_id=draft2.id,
        tenure_id=tenure.id,
        detected_company="Allianz General Insurance Company (Malaysia) Berhad",
        tenure_version=2,
        is_tenure_active=False,
        status="active",
        duplicate_of_session_id=sess1.id,
        duplicate_resolution="pending",
    )
    db_session.add_all([sess1, sess2])
    db_session.commit()

    # Resolve with 'replace'
    resolve_res = client.post(
        f"/api/comparison/{tenure.id}/duplicates/{sess2.id}/resolve",
        json={"resolution": "replace"},
    )
    assert resolve_res.status_code == 200
    db_session.refresh(sess1)
    db_session.refresh(sess2)
    assert sess1.is_tenure_active is False
    assert sess2.is_tenure_active is True
    assert sess2.duplicate_resolution == "replaced"


def test_ledger_sorting_and_calendar_sessions(client: TestClient, db_session: Session, admin_user: User):
    v1 = TrackedVehicle(id=new_id(), vehicle_no="CAL1111")
    v2 = TrackedVehicle(id=new_id(), vehicle_no="CAL2222")
    db_session.add_all([v1, v2])
    db_session.flush()

    t1 = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=v1.id,
        vehicle_no="CAL1111",
        customer_name="Alice",
        coverage_start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 1, 1, tzinfo=timezone.utc),
        expiry_month="2027-01",
        is_discarded=False,
        last_activity_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    t2 = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=v2.id,
        vehicle_no="CAL2222",
        customer_name="Bob",
        coverage_start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 1, 1, tzinfo=timezone.utc),
        expiry_month="2027-01",
        is_discarded=True,
        last_activity_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    db_session.add_all([t1, t2])
    db_session.flush()

    uf = _create_uploaded_file(db_session, admin_user.id)

    draft = QuotationDraft(
        id=str(uuid4()),
        owner_id=admin_user.id,
        uploaded_file_id=uf.id,
        fields={
            "quotation_date": {"value": "2026-03-15"},
            "total_payable": {"value": 1500.0},
            "sum_insured": {"value": 55000.0},
        },
    )
    db_session.add(draft)
    db_session.flush()

    sess = SessionModel(
        id=str(uuid4()),
        owner_id=admin_user.id,
        uploaded_file_id=uf.id,
        draft_id=draft.id,
        tenure_id=t1.id,
        detected_company="Allianz",
        status="active",
        created_at=datetime(2026, 3, 15, tzinfo=timezone.utc),
    )
    db_session.add(sess)
    db_session.commit()

    # 1. Test ledger excludes discarded by default
    res = client.get("/api/tenures?year=2026")
    assert res.status_code == 200
    items = res.json()["items"]
    vehicles = [i["vehicle_no"] for i in items]
    assert "CAL1111" in vehicles
    assert "CAL2222" not in vehicles

    # 2. Test show_discarded=true includes discarded
    res_discarded = client.get("/api/tenures?year=2026&show_discarded=true")
    assert res_discarded.status_code == 200
    vehicles_all = [i["vehicle_no"] for i in res_discarded.json()["items"]]
    assert "CAL2222" in vehicles_all

    # 3. Test calendar sessions endpoint
    cal_res = client.get("/api/tenures/calendar-sessions?year=2026&month=3")
    assert cal_res.status_code == 200
    sessions_plotted = cal_res.json()["sessions"]
    assert len(sessions_plotted) == 1
    assert sessions_plotted[0]["vehicle_no"] == "CAL1111"
    assert sessions_plotted[0]["quotation_date"] == "2026-03-15"
