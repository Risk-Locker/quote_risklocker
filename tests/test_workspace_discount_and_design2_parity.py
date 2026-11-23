"""Tests for Quotation Workspace discount bidirectional sync & Design 2 1:1 HTML/PDF parity."""

from __future__ import annotations

from datetime import datetime, timezone
import os
import sys
from pathlib import Path

import pytest
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

from app.models.enums import AccountStatus, RecordStatus, Role
from app.models.tables import (
    Base,
    Batch,
    InsuranceCompany,
    InsuranceTenure,
    QuotationDraft,
    Session as QuotationSession,
    TenureComparisonEntry,
    TrackedVehicle,
    UploadedFile,
    User,
    new_id,
)
from app.rendering.pdf_generator import html_to_pdf
from app.rendering.template_renderer_design2 import render_design2_html
from app.services.marketing_comparison_service import get_marketing_comparison
from app.services.workspace_patch_service import apply_workspace_patch
from app.services.workspace_snapshot_service import build_workspace_snapshot


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine)
    db = SessionFactory()
    try:
        yield db
    finally:
        db.close()


def _seed_workspace_and_comparison(db):
    now = datetime.now(timezone.utc)
    user = User(
        id=new_id(),
        email="staff@risklocker.test",
        name="Staff User",
        role=Role.STAFF.value,
        password_hash="x",
        status=AccountStatus.ACTIVE.value,
    )
    liberty = InsuranceCompany(
        id="c0000000-0000-4000-8000-000000000091",
        name="Liberty",
        slug="liberty",
        detection_phrases=["Liberty", "Liberty Insurance"],
        status=AccountStatus.ACTIVE.value,
    )
    tv = TrackedVehicle(id=new_id(), vehicle_no="QBG1431", car_brand="HONDA", car_model="WR-V E", engine_cc="1498 CC")
    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=tv.id,
        vehicle_no="QBG1431",
        customer_name="WONG SUI PENG",
        coverage_start_date=now,
        coverage_end_date=now,
        expiry_month="2028-01",
        road_tax=120.00,
        runner_fee=20.00,
        include_road_tax=True,
        include_runner_fee=True,
        motor_discount_pct=0.00,
        quotation_discount=0.00,
        won_premium=1342.95,
        created_by_id=user.id,
    )
    batch = Batch(id=new_id(), owner_id=user.id, name="Test Batch", status=RecordStatus.READY.value)

    def _make_quote(comp_name: str, gross_motor: str):
        uf = UploadedFile(
            id=new_id(),
            batch_id=batch.id,
            owner_id=user.id,
            original_filename=f"{comp_name}.pdf",
            content_type="application/pdf",
            storage_path=f"test/{new_id()}.pdf",
            storage_provider="local_ephemeral",
            size_bytes=100,
            status=RecordStatus.READY.value,
        )
        db.add(uf)
        db.flush()
        total_init = f"{float(gross_motor) + 140.0:.2f}"
        draft = QuotationDraft(
            id=new_id(),
            revision=1,
            uploaded_file_id=uf.id,
            owner_id=user.id,
            company_id=liberty.id if comp_name == "Liberty" else None,
            status=RecordStatus.READY.value,
            fields={
                "quotation_reference": {"value": "RL260000991", "status": "ready"},
                "customer_name": {"value": "WONG SUI PENG", "status": "ready"},
                "vehicle_no": {"value": "QBG1431", "status": "ready"},
                "car_model": {"value": "HONDA WR-V E", "status": "ready"},
                "cover_period": {"value": "02/01/2027 - 01/01/2028", "status": "ready"},
                "coverage_type": {"value": "Comprehensive", "status": "ready"},
                "ncd_percent": {"value": "55.00%", "status": "ready"},
                "valuation_type": {"value": "Agreed Value", "status": "ready"},
                "excess_amount": {"value": "0.00", "status": "ready"},
                "coverage_amount": {"value": "66000.00", "status": "ready"},
                "insurance_company": {"value": comp_name, "status": "ready"},
                "premium": {"value": gross_motor, "status": "ready"},
                "roadtax": {"value": "120.00", "status": "ready"},
                "service_fee": {"value": "20.00", "status": "ready"},
                "motor_discount_pct": {"value": "0.00", "status": "ready"},
                "motor_discount_amount": {"value": "0.00", "status": "ready"},
                "effective_discount": {"value": "0.00", "status": "ready"},
                "net_motor_premium": {"value": gross_motor, "status": "ready"},
                "total_amount": {"value": total_init, "status": "ready"},
            },
            display_options={"include_road_tax": True, "include_runner_fee": True},
            scalar_decisions={},
        )
        db.add(draft)
        db.flush()
        sess = QuotationSession(
            id=new_id(),
            owner_id=user.id,
            uploaded_file_id=uf.id,
            draft_id=draft.id,
            tenure_id=tenure.id,
            tracked_vehicle_id=tv.id,
            quotation_ref="RL260000991",
            detected_company=comp_name,
            status=AccountStatus.ACTIVE.value,
        )
        db.add(sess)
        db.flush()
        entry = TenureComparisonEntry(
            id=new_id(),
            tenure_id=tenure.id,
            session_id=sess.id,
            company_name=comp_name,
            sum_insured=66000.00,
            motor_premium=float(gross_motor),
            road_tax=120.00,
            runner_fee=20.00,
            total_payable=float(total_init),
            towing_limit="365 km",
            towing_km="365 km",
            is_recommended=comp_name == "Liberty",
        )
        db.add(entry)
        return sess, draft, entry

    db.add_all([user, liberty, tv, tenure, batch])
    db.flush()
    s1, d1, e1 = _make_quote("Liberty", "1266.26")
    s2, d2, e2 = _make_quote("Kurnia", "1400.00")
    db.commit()
    return user, tenure, s1, d1, e1, s2, d2, e2


def test_workspace_discount_syncs_bidirectionally_and_resets_cleanly(db_session):
    user, tenure, s1, d1, e1, _, d2, e2 = _seed_workspace_and_comparison(db_session)

    # Apply 5% Motor Discount directly from Quotation Workspace
    res = apply_workspace_patch(
        db_session,
        user,
        d1.id,
        base_revision=d1.revision,
        operations=[
            {"op": "scalar_decision", "field": "motor_discount_pct", "decision": "edit", "value": "5"},
            {"op": "scalar_decision", "field": "total_amount", "decision": "clear"},
        ],
    )
    assert res["fields"]["motor_discount_pct"]["value"] == "5.00"
    assert res["fields"]["effective_discount"]["value"] == "63.31"
    # 1266.26 - 63.31 = 1202.95 net motor premium; 1202.95 + 140.00 fees = 1342.95 total payable
    assert res["fields"]["net_motor_premium"]["value"] == "1202.95"

    db_session.refresh(tenure)
    db_session.refresh(d1)
    db_session.refresh(d2)
    db_session.refresh(e1)
    db_session.refresh(e2)

    assert float(tenure.motor_discount_pct) == 5.0
    assert d1.fields["net_motor_premium"]["value"] == "1202.95"
    assert d1.fields["total_amount"]["value"] == "1342.95"
    # Comparison serializer & sibling draft synced in lockstep
    comp5 = get_marketing_comparison(db_session, tenure.id)
    assert comp5["tenure"]["motor_discount_pct"] == 5.0
    ce1 = next(x for x in comp5["entries"] if x["id"] == e1.id)
    ce2 = next(x for x in comp5["entries"] if x["id"] == e2.id)
    assert ce1["motor_discount_pct"] == 5.0
    assert ce1["motor_discount_amount"] == 63.31
    assert ce1["net_motor_premium"] == 1202.95
    assert ce1["net_total_payable"] == 1342.95
    # Kurnia sibling (1400.00 * 5% = 70.00 -> net 1330.00 -> total 1470.00)
    assert ce2["motor_discount_amount"] == 70.0
    assert ce2["net_motor_premium"] == 1330.0
    assert d2.fields["motor_discount_pct"]["value"] == "5.00"
    assert d2.fields["net_motor_premium"]["value"] == "1330.00"
    assert d2.fields["total_amount"]["value"] == "1470.00"

    # Snapshot reflects same canonical discount_summary
    snap = build_workspace_snapshot(db_session, user, s1.id)
    assert snap["discount_summary"]["motor_discount_pct"] == "5.00"
    assert snap["discount_summary"]["net_motor_premium"] == "1202.95"

    # Reset back to 0% -> zeroes out discount cleanly everywhere
    res_zero = apply_workspace_patch(
        db_session,
        user,
        d1.id,
        base_revision=d1.revision,
        operations=[
            {"op": "scalar_decision", "field": "motor_discount_pct", "decision": "edit", "value": "0"},
            {"op": "scalar_decision", "field": "total_amount", "decision": "clear"},
        ],
    )
    assert res_zero["fields"]["motor_discount_pct"]["value"] == "0.00"
    assert res_zero["fields"]["effective_discount"]["value"] == "0.00"
    assert res_zero["fields"]["net_motor_premium"]["value"] == "1266.26"

    snap_zero = build_workspace_snapshot(db_session, user, s1.id)
    assert snap_zero["discount_summary"]["motor_discount_pct"] == "0.00"
    assert snap_zero["discount_summary"]["effective_discount"] == "0.00"

    db_session.refresh(tenure)
    comp0 = get_marketing_comparison(db_session, tenure.id)
    ce1_0 = next(x for x in comp0["entries"] if x["id"] == e1.id)
    assert float(tenure.motor_discount_pct) == 0.0
    assert ce1_0["motor_discount_pct"] == 0.0
    assert ce1_0["motor_discount_amount"] == 0.0
    assert ce1_0["net_motor_premium"] == 1266.26
    assert ce1_0["net_total_payable"] == 1406.26


def test_design2_html_and_pdf_discount_parity_bilingual_and_english(db_session, tmp_path):
    _, _, _, d1, _, _, _, _ = _seed_workspace_and_comparison(db_session)

    # Active 5% discount case (matching user spec: RM 1,202.95 net motor premium)
    fields_5pct = {
        **d1.fields,
        "motor_discount_pct": {"value": "5.00"},
        "effective_discount": {"value": "63.31"},
        "net_motor_premium": {"value": "1202.95"},
        "total_amount": {"value": "1342.95"},
    }
    html_bi = render_design2_html(fields_5pct, template_config={"language_mode": "bilingual"}, db=db_session)
    disc_idx = html_bi.index("Discount / 折扣")
    prem_idx = html_bi.index("Insurance Premium / 保费 (after discount)")
    rt_idx = html_bi.index("Roadtax and Runner Fee / 路税及服务费")
    assert disc_idx < prem_idx < rt_idx
    assert "5%" in html_bi
    assert "RM 1,202.95" in html_bi
    assert "RM 140.00" in html_bi
    assert "width: 214px;" in html_bi

    html_en = render_design2_html(fields_5pct, template_config={"language_mode": "en"}, db=db_session)
    assert "Discount / 折扣" not in html_en
    assert ">Discount<" in html_en
    assert "Insurance Premium (after discount)" in html_en
    assert "width: 214px;" in html_en

    # 0% discount case: Discount row omitted, standard label & 186px width
    html_zero = render_design2_html(d1.fields, template_config={"language_mode": "bilingual"}, db=db_session)
    assert "Discount / 折扣" not in html_zero
    assert "(after discount)" not in html_zero
    assert "Insurance Premium / 保费" in html_zero
    assert "RM 1,266.26" in html_zero
    assert "width: 214px;" not in html_zero

    # Playwright Chromium PDF generation succeeds cleanly for both 0% and 5%
    pdf5_path = tmp_path / "design2_5pct.pdf"
    pdf0_path = tmp_path / "design2_0pct.pdf"
    html_to_pdf(html_bi, pdf5_path, width=794, height=1123)
    html_to_pdf(html_zero, pdf0_path, width=794, height=1123)
    pdf_5 = pdf5_path.read_bytes()
    pdf_0 = pdf0_path.read_bytes()
    assert pdf_5.startswith(b"%PDF-") and len(pdf_5) > 5000
    assert pdf_0.startswith(b"%PDF-") and len(pdf_0) > 5000
