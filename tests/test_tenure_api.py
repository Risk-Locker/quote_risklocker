"""Hermetic API tests for /tenures endpoints."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

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
    TrackedVehicle,
    User,
    new_id,
)
from app.services.insurance_tenure_service import resolve_or_create_tenure


from sqlalchemy.pool import StaticPool


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
        role="admin",
    )
    db_session.add(admin)
    db_session.flush()

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[current_user] = lambda: admin

    with TestClient(app) as test_client:
        yield test_client


def test_list_tenure_months_and_tenures(client: TestClient, db_session: Session):
    # Seed 2 tenures in different months
    t1 = resolve_or_create_tenure(
        db_session,
        vehicle_no="JWK 9488",
        customer_name="TEY SIOK BEE",
        start_date="08/09/2026",
        end_date="07/09/2027",
    )
    t2 = resolve_or_create_tenure(
        db_session,
        vehicle_no="VDM 3321",
        customer_name="AHMAD BIN ALI",
        start_date="15/10/2026",
        end_date="14/10/2027",
    )
    db_session.flush()

    # 1. GET /api/tenures/months
    res = client.get("/api/tenures/months")
    assert res.status_code == 200
    months_data = res.json()["months"]
    month_keys = [m["month"] for m in months_data]
    assert "2027-09" in month_keys
    assert "2027-10" in month_keys

    # Find 2027-09 month stat
    m_sep = next(m for m in months_data if m["month"] == "2027-09")
    assert m_sep["total"] == 1

    # 2. GET /api/tenures filtered by month
    res_list = client.get("/api/tenures?month=2027-09")
    assert res_list.status_code == 200
    items = res_list.json()["items"]
    assert len(items) == 1
    assert items[0]["vehicle_no"] == "JWK 9488"
    assert items[0]["customer_name"] == "TEY SIOK BEE"

    # 3. GET /api/tenures filtered by search
    res_search = client.get("/api/tenures?search=VDM")
    assert res_search.status_code == 200
    search_items = res_search.json()["items"]
    assert len(search_items) >= 1
    assert all(item["vehicle_no"] == "VDM 3321" for item in search_items)


def test_tenure_quote_generation_and_status(client: TestClient, db_session: Session):
    admin = db_session.scalar(select(User))
    admin_id = admin.id if admin else new_id()

    tenure = resolve_or_create_tenure(
        db_session,
        vehicle_no="JWK 9488",
        customer_name="TEY SIOK BEE",
        start_date="08/09/2026",
        end_date="07/09/2027",
    )

    f_id = new_id()
    draft = QuotationDraft(
        uploaded_file_id=f_id,
        owner_id=admin_id,
        fields={"total_amount": {"value": "995.00"}},
    )
    db_session.add(draft)
    db_session.flush()

    sess = SessionModel(
        owner_id=admin_id,
        uploaded_file_id=f_id,
        draft_id=draft.id,
        detected_company="STMB",
        tenure_id=tenure.id,
        tenure_version=1,
        is_tenure_active=True,
    )
    db_session.add(sess)
    db_session.flush()

    # 1. POST /api/tenures/{id}/generate-quote
    gen_res = client.post(
        f"/api/tenures/{tenure.id}/generate-quote",
        json={"session_id": sess.id},
    )
    assert gen_res.status_code == 200
    qref = gen_res.json()["quotation_ref"]
    assert str(qref).startswith("RL")

    # 2. GET /api/tenures/{id} (full timeline)
    detail_res = client.get(f"/api/tenures/{tenure.id}")
    assert detail_res.status_code == 200
    data = detail_res.json()
    assert len(data["generated_risklocker_quotations"]) == 1
    assert data["generated_risklocker_quotations"][0]["quotation_ref"] == qref

    # 3. POST /api/tenures/{id}/status (mark HIT)
    status_res = client.post(
        f"/api/tenures/{tenure.id}/status",
        json={
            "status": "hit",
            "winning_quotation_ref": qref,
            "won_premium": 995.00,
            "notes": "Closed on WhatsApp",
        },
    )
    assert status_res.status_code == 200
    assert status_res.json()["tenure"]["status"] == "hit"
    assert status_res.json()["tenure"]["won_premium"] == 995.00
