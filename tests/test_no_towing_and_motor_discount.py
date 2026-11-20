"""Tests for No Towing (0) option and Motor Insurance Percentage Discount sync."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_PROVIDER", "supabase_postgres")
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:password@db.test.supabase.co:5432/postgres")
os.environ.setdefault("AUTH_HASH_SECRET", "test-auth-hash-secret-that-is-long-enough")
os.environ.setdefault("STORAGE_DRIVER", "supabase")
os.environ.setdefault("SUPABASE_URL", "https://project-ref.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")

from app.api import routes
from app.api.deps import current_user, get_db
from app.domain.motor.discount_calculator import calculate_motor_discount
from app.models.tables import (
    Base,
    InsuranceTenure,
    QuotationDraft,
    Session as SessionModel,
    TenureComparisonEntry,
    TrackedVehicle,
    UploadedFile,
    Batch,
    User,
    new_id,
)
from app.rendering.render_context import adjusted_total_text
from app.rendering.template_renderer_design2 import render_design2_html
from app.services.marketing_comparison.benefits_extractor import _resolve_comparison_benefits
from app.services.marketing_comparison.ncd_evaluator import normalize_towing_km
from app.services.marketing_comparison.towing_evaluator import resolve_insurer_towing_limit
from app.services.marketing_comparison.whatsapp_formatter import format_whatsapp_teaser_from_data


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


def _build_client(db_session):
    app = FastAPI()
    app.include_router(routes.router)
    admin = User(
        id=new_id(),
        email="admin@risklocker.test",
        name="Admin User",
        role="super_admin",
        password_hash="hashed",
    )
    db_session.add(admin)
    db_session.commit()

    def override_get_db():
        yield db_session

    def override_current_user():
        return SimpleNamespace(
            id=admin.id,
            email=admin.email,
            name=admin.name,
            role="super_admin",
            is_active=True,
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[current_user] = override_current_user
    return TestClient(app), admin


def _seed_tenure_with_entries(db_session, admin_id: str):
    now = datetime.now(timezone.utc)
    tv = TrackedVehicle(
        id=new_id(),
        vehicle_no="JVU3005",
        car_brand="MITSUBISHI",
        car_model="Mitsubishi Fuso Canter",
        engine_cc="3000 KG",
        manufacture_year=2020,
    )
    db_session.add(tv)
    db_session.flush()

    batch = Batch(id=new_id(), owner_id=admin_id, name="Test Batch", status="ready")
    db_session.add(batch)
    db_session.flush()

    def _make_session(doc_type: str, company: str, motor_prem: str):
        uf = UploadedFile(
            id=new_id(),
            batch_id=batch.id,
            owner_id=admin_id,
            original_filename=f"{company}_{doc_type}.pdf",
            content_type="application/pdf",
            storage_path=f"test/{new_id()}.pdf",
            storage_provider="supabase",
            storage_status="available",
            size_bytes=100,
            status="ready",
        )
        db_session.add(uf)
        db_session.flush()
        draft = QuotationDraft(
            id=new_id(),
            uploaded_file_id=uf.id,
            owner_id=admin_id,
            status="ready",
            fields={
                "vehicle_no": {"value": "JVU3005", "status": "ready"},
                "vehicle_type": {"value": "Lorry", "status": "ready"},
                "coverage_type": {"value": "Comprehensive", "status": "ready"},
                "insurance_company": {"value": company, "status": "ready"},
                "sum_insured": {"value": "50000.00", "status": "ready"},
                "premium": {"value": motor_prem, "status": "ready"},
                "motor_premium": {"value": motor_prem, "status": "ready"},
                "roadtax": {"value": "90.00", "status": "ready"},
                "service_fee": {"value": "20.00", "status": "ready"},
                "total_amount": {"value": f"{float(motor_prem) + 110:.2f}", "status": "ready"},
            },
        )
        db_session.add(draft)
        db_session.flush()
        sess = SessionModel(
            id=new_id(),
            owner_id=admin_id,
            uploaded_file_id=uf.id,
            draft_id=draft.id,
            tracked_vehicle_id=tv.id,
            document_type=doc_type,
            detected_company=company,
            status="active",
        )
        db_session.add(sess)
        db_session.flush()
        return sess, draft

    cn_sess, cn_draft = _make_session("covernote", "AmAssurance", "1000.00")
    q1_sess, q1_draft = _make_session("quotation", "AmAssurance", "1000.00")
    q2_sess, q2_draft = _make_session("quotation", "QBE", "1200.00")

    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=tv.id,
        vehicle_no="JVU3005",
        customer_name="TEST LOGISTICS SDN BHD",
        coverage_start_date=now,
        coverage_end_date=now,
        expiry_month="2026-12",
        road_tax=90.00,
        runner_fee=20.00,
        include_road_tax=True,
        include_runner_fee=True,
        covernote_session_id=cn_sess.id,
        won_premium=1110.00,
        stage="Issue Policy",
    )
    db_session.add(tenure)
    db_session.flush()

    cn_sess.tenure_id = tenure.id
    q1_sess.tenure_id = tenure.id
    q2_sess.tenure_id = tenure.id

    e1 = TenureComparisonEntry(
        id=new_id(),
        tenure_id=tenure.id,
        session_id=q1_sess.id,
        company_name="AmAssurance",
        sum_insured=50000.00,
        motor_premium=1000.00,
        road_tax=90.00,
        runner_fee=20.00,
        total_payable=1110.00,
        towing_limit="100 km",
        towing_km="100 km",
        is_recommended=True,
    )
    e2 = TenureComparisonEntry(
        id=new_id(),
        tenure_id=tenure.id,
        session_id=q2_sess.id,
        company_name="QBE",
        sum_insured=50000.00,
        motor_premium=1200.00,
        road_tax=90.00,
        runner_fee=20.00,
        total_payable=1310.00,
        towing_limit="RM 500",
        towing_km="RM 500",
    )
    db_session.add_all([e1, e2])
    db_session.commit()
    return tenure, e1, e2, cn_sess, q1_draft, cn_draft


def test_no_towing_unit_resolvers():
    for raw in ("0", "0 km", "RM 0", "No towing", "Not Included", "none"):
        assert normalize_towing_km(raw, company_name="QBE") == "No towing"
        assert resolve_insurer_towing_limit(
            company_name="AmAssurance",
            combined_text="Comprehensive policy",
            extracted_towing=raw,
        ) == "No towing"


def test_no_towing_persists_through_entry_and_covernote_patch(db_session):
    client, admin = _build_client(db_session)
    tenure, e1, _, cn_sess, q1_draft, cn_draft = _seed_tenure_with_entries(db_session, admin.id)

    # Patch comparison entry towing_limit to "0" -> normalized to "No towing"
    res = client.patch(
        f"/comparison/{tenure.id}/entries/{e1.id}",
        json={"towing_limit": "0"},
    )
    assert res.status_code == 200
    assert res.json()["towing_limit"] == "No towing"
    assert res.json()["towing_km"] == "No towing"

    # Extract benefits directly from draft with manual_override -> must preserve "No towing"
    db_session.refresh(q1_draft)
    b_res = _resolve_comparison_benefits(db_session, None, None, q1_draft.fields)
    assert b_res["towing_limit"] == "No towing"

    # Patch cover note towing_limit to "No towing" -> must persist and read back as "No towing"
    cn_res = client.patch(
        f"/comparison/{tenure.id}/covernote",
        json={"towing_limit": "No towing"},
    )
    assert cn_res.status_code == 200
    payload = cn_res.json()
    assert payload["covernote_policy"]["towing_limit"] == "No towing"

    # GET comparison must still return "No towing" on both entry and covernote
    get_res = client.get(f"/comparison/{tenure.id}")
    assert get_res.status_code == 200
    comp = get_res.json()
    e1_out = next(x for x in comp["entries"] if x["id"] == e1.id)
    assert e1_out["towing_limit"] == "No towing"
    assert comp["covernote_policy"]["towing_limit"] == "No towing"


def test_motor_discount_pct_decimal_math_only_discounts_motor_insurance():
    bd = calculate_motor_discount("1000.00", "10", "0")
    assert bd.motor_discount_pct == Decimal("10.00")
    assert bd.pct_discount_amount == Decimal("100.00")
    assert bd.net_motor_premium == Decimal("900.00")
    # Road tax 90 + Runner fee 20 are NOT discounted
    assert bd.net_total_payable("90.00", "20.00") == Decimal("1010.00")


def test_motor_discount_pct_syncs_across_comparison_covernote_draft_whatsapp_and_pdf(db_session):
    client, admin = _build_client(db_session)
    tenure, e1, e2, cn_sess, q1_draft, cn_draft = _seed_tenure_with_entries(db_session, admin.id)

    res = client.post(
        f"/comparison/{tenure.id}/toggle-fees",
        json={"motor_discount_pct": 10},
    )
    assert res.status_code == 200
    comp = res.json()

    # 1. Tenure + Entries + Cover Note synced
    assert comp["tenure"]["motor_discount_pct"] == 10.0
    e1_out = next(x for x in comp["entries"] if x["id"] == e1.id)
    e2_out = next(x for x in comp["entries"] if x["id"] == e2.id)
    assert e1_out["motor_discount_pct"] == 10.0
    assert e1_out["motor_discount_amount"] == 100.0
    assert e1_out["net_motor_premium"] == 900.0
    assert e1_out["net_total_payable"] == 1010.0
    assert e2_out["motor_discount_amount"] == 120.0
    assert e2_out["net_motor_premium"] == 1080.0
    assert e2_out["net_total_payable"] == 1190.0
    assert comp["covernote_policy"]["net_motor_premium"] == 900.0
    assert comp["covernote_policy"]["net_total_payable"] == 1010.0

    # 2. Tenure won_premium & QuotationDraft fields synced
    db_session.refresh(tenure)
    db_session.refresh(q1_draft)
    db_session.refresh(cn_draft)
    assert float(tenure.won_premium) == 1010.0
    assert q1_draft.fields["motor_discount_pct"]["value"] == "10.00"
    assert q1_draft.fields["motor_discount_amount"]["value"] == "100.00"
    assert q1_draft.fields["total_amount"]["value"] == "1010.00"
    assert cn_draft.fields["total_amount"]["value"] == "1010.00"

    # 3. RenderContext adjusted_total_text + Design 2 HTML + WhatsApp teaser synced
    assert adjusted_total_text(q1_draft.fields, []) == "1,010"
    assert adjusted_total_text(q1_draft.fields, [], round_total=True) == "1,010.00"
    html = render_design2_html(q1_draft.fields, template_config={}, db=db_session)
    assert "Motor Discount (10%)" in html
    assert "RM 100.00" in html
    assert "RM 1,010.00" in html

    wa = format_whatsapp_teaser_from_data(comp)
    assert "10%" in wa
    assert "RM 900.00" in wa
    assert "RM 1,010.00" in wa
