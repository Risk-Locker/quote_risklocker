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
from app.core.errors import register_error_handlers
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
    register_error_handlers(app)
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
    assert "2026-09" in month_keys
    assert "2026-10" in month_keys

    # Find 2026-09 month stat (anchored on start date)
    m_sep = next(m for m in months_data if m["month"] == "2026-09")
    assert m_sep["total"] == 1
    assert m_sep["start_count"] == 1

    # Find 2027-09 month stat (expiring policy with no 2027 renewal deal yet -> visible in unified anchor="all")
    m_sep_end = next(m for m in months_data if m["month"] == "2027-09")
    assert m_sep_end["total"] == 1
    assert m_sep_end["end_count"] == 1

    res_exp_list = client.get("/api/tenures?month=2027-09")
    assert res_exp_list.status_code == 200
    assert res_exp_list.json()["total"] == 1
    assert res_exp_list.json()["items"][0]["is_upcoming_renewal"] is True

    # Under anchor=starting, 2027-09 has 0 starting deals
    res_start_months = client.get("/api/tenures/months?anchor=starting")
    m_sep_start_only = next(m for m in res_start_months.json()["months"] if m["month"] == "2027-09")
    assert m_sep_start_only["total"] == 0
    assert m_sep_start_only["end_count"] == 1

    # 2. GET /api/tenures filtered by start month
    res_list = client.get("/api/tenures?month=2026-09")
    assert res_list.status_code == 200
    items = res_list.json()["items"]
    assert len(items) == 1
    assert items[0]["vehicle_no"] == "JWK9488"
    assert items[0]["customer_name"] == "TEY SIOK BEE"

    # 3. GET /api/tenures filtered by search
    res_search = client.get("/api/tenures?search=VDM")
    assert res_search.status_code == 200
    search_items = res_search.json()["items"]
    assert len(search_items) >= 1
    assert all(item["vehicle_no"] == "VDM3321" for item in search_items)


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


def test_ledger_parity_comparison_pricing_covernote_miss_trash_rbac_and_leap_year(
    client: TestClient,
    db_session: Session,
):
    from app.models.tables import InsuranceCompany, TenureComparisonEntry
    from app.services.insurance_tenure_service import create_next_year_renewal_tenure

    admin = db_session.scalar(select(User))
    admin_id = admin.id if admin else new_id()

    comp = InsuranceCompany(id=new_id(), name="Allianz", slug="allianz")
    db_session.add(comp)
    db_session.flush()

    # 1. Vehicle with 2026 policy expiring in June 2027 (no 2027 child yet)
    t_jun = resolve_or_create_tenure(
        db_session,
        vehicle_no="WTA 3205",
        customer_name="CHONG MEI LING",
        start_date="05/06/2026",
        end_date="04/06/2027",
    )
    t_jun.stage = "Issue Policy"
    t_jun.winning_company_id = comp.id
    t_jun.won_premium = 1450.50

    # 2. Vehicle with BOTH 2026 policy AND 2027 child renewal in Oct
    t_26 = resolve_or_create_tenure(
        db_session,
        vehicle_no="VNE 8901",
        customer_name="LIM WEI HAN",
        start_date="30/10/2026",
        end_date="29/10/2027",
    )
    t_26.stage = "Close - Win"
    t_26.status = "hit"
    db_session.flush()
    t_27 = create_next_year_renewal_tenure(db_session, t_26, user_id=admin_id)
    assert t_27 is not None

    # 3. Lost deal (must NOT leak into category=active)
    t_lost = resolve_or_create_tenure(
        db_session,
        vehicle_no="LOST 999",
        customer_name="LOST CLIENT",
        start_date="01/03/2026",
        end_date="28/02/2027",
    )
    t_lost.stage = "Close - Lose"
    t_lost.status = "miss"

    # 4. Quote session with stale draft total_amount vs authoritative TenureComparisonEntry.total_payable
    f_id = new_id()
    draft = QuotationDraft(
        uploaded_file_id=f_id,
        owner_id=admin_id,
        company_id=comp.id,
        fields={"total_amount": {"value": "9999.00"}},
    )
    db_session.add(draft)
    db_session.flush()
    sess = SessionModel(
        owner_id=admin_id,
        uploaded_file_id=f_id,
        draft_id=draft.id,
        detected_company="Allianz",
        tenure_id=t_jun.id,
        tenure_version=1,
        is_tenure_active=True,
    )
    db_session.add(sess)
    db_session.flush()
    db_session.add(
        TenureComparisonEntry(
            id=new_id(),
            tenure_id=t_jun.id,
            session_id=sess.id,
            company_id=comp.id,
            company_name="Allianz",
            total_payable=1450.50,
            sum_insured=65000.00,
            is_recommended=True,
            rank=1,
        )
    )
    db_session.commit()

    # A) Parity across YoY, Months, Stage Summary, and List Tenures for 2027 & 2027-06
    yoy = client.get("/api/tenures/stats/yoy?category=active").json()
    y27 = next(y for y in yoy["years"] if y["year"] == "2027")
    tenures_27 = client.get("/api/tenures?year=2027&category=active").json()
    kpi_27 = client.get("/api/tenures/stage-summary?year=2027&category=active").json()
    assert y27["total"] == tenures_27["total"] == kpi_27["total"]
    # VNE8901 appears ONCE in 2027 (its 2027 renewal, not duplicated by 2026 expiry)
    assert [i["vehicle_no"] for i in tenures_27["items"]].count("VNE8901") == 1

    months_res = client.get("/api/tenures/months?category=active").json()
    jun_27_m = next(m for m in months_res["months"] if m["month"] == "2027-06")
    jun_27_list = client.get("/api/tenures?year=2027&month=6&category=active").json()
    jun_27_kpi = client.get("/api/tenures/stage-summary?year=2027&month=6&category=active").json()
    assert jun_27_m["total"] == 1
    assert jun_27_list["total"] == 1
    assert jun_27_kpi["total"] == 1

    # B) Comparison pricing wins over stale draft total_amount, and winner without CN PDF is NOT fake Cover Note
    jun_item = jun_27_list["items"][0]
    assert jun_item["sourced_quotes"][0]["total_payable"] == "1450.50"
    assert jun_item["has_selected_winner"] is True
    assert jun_item["is_covernote_issued"] is False
    assert jun_item["covernote_policy"] is None

    # C) category=active excludes Close - Lose
    active_all = client.get("/api/tenures?category=active").json()
    assert "LOST999" not in [i["vehicle_no"] for i in active_all["items"]]

    # D) Atomic Miss + create_next_year_deal=True + leap-year end date (2027-03-01 -> 2028-02-29)
    leap_t = resolve_or_create_tenure(
        db_session,
        vehicle_no="LEAP 2028",
        customer_name="LEAP TEST",
        start_date="01/03/2026",
        end_date="28/02/2027",
    )
    db_session.commit()
    miss_res = client.patch(
        f"/api/tenures/{leap_t.id}/ledger-fields",
        json={
            "stage": "Close - Lose",
            "status": "miss",
            "is_discarded": False,
            "create_next_year_deal": True,
            "external_insurer": "Etiqa",
            "miss_reason": "Cheaper quote",
        },
    )
    assert miss_res.status_code == 200
    leap_next = db_session.scalar(
        select(InsuranceTenure).where(InsuranceTenure.previous_tenure_id == leap_t.id)
    )
    assert leap_next is not None
    assert leap_next.coverage_start_date.strftime("%Y-%m-%d") == "2027-03-01"
    assert leap_next.coverage_end_date.strftime("%Y-%m-%d") == "2028-02-29"

    # E) 30-day Soft-Delete -> GET /api/trash -> Restore round-trip
    del_res = client.delete(f"/api/tenures/{t_jun.id}")
    assert del_res.status_code == 200
    assert client.get(f"/api/tenures/{t_jun.id}").status_code == 404

    trash_res = client.get("/api/trash").json()
    assert any(row["id"] == t_jun.id for row in trash_res["tenures"])

    rest_res = client.post(f"/api/trash/tenures/{t_jun.id}/restore", json={})
    assert rest_res.status_code == 200
    assert client.get(f"/api/tenures/{t_jun.id}").status_code == 200

    # F) RBAC guard on /tenures mutations
    app = client.app
    viewer = User(id=new_id(), name="Viewer", email="viewer@risklocker.local", role="viewer")
    db_session.add(viewer)
    db_session.flush()
    app.dependency_overrides[current_user] = lambda: viewer
    forbidden = client.delete(f"/api/tenures/{t_jun.id}")
    assert forbidden.status_code == 403
