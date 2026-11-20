"""Hermetic unit & integration tests for MMIP, Kurnia, Override Auto-Clear, Prev Policy Upload, YoY Insights, and Design 2 Variants."""

from __future__ import annotations

import io
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as OrmSession, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.api.deps import current_user, get_db, settings_dep
from app.api.routers.comparison import router as comparison_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.db.init_db import seed_defaults
from app.domain.motor.winner_ranking_rules import build_underwriter_ranking_explanation
from app.extraction.candidate_finder import find_candidates
from app.extraction.company_resolution import build_companies_payload, resolve_company
from app.models.tables import (
    Base,
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    CatalogOffering,
    InsuranceCompany,
    InsuranceProduct,
    InsuranceTenure,
    QuotationDraft,
    Role,
    Session as SessionModel,
    TenureComparisonEntry,
    TrackedVehicle,
    UploadedFile,
    User,
    Batch,
    new_id,
)
from app.rendering.benefit_schedule_renderer import get_company_logo_data_uri
from app.rendering.template_renderer_design2 import render_design2_html
from app.rendering.unified_addon_engine import build_unified_matrix_cards, extract_free_coverage_items
from app.services.catalog_review_service import pin_catalog_context
from app.services.company_names import get_insurer_short_name, get_official_insurer_name
from app.services.marketing_comparison.towing_evaluator import resolve_insurer_towing_limit
from app.services.marketing_comparison_service import get_marketing_comparison
from app.services.master_template_service import (
    DESIGN2_EN_MASTER_KEY,
    DESIGN2_MASTER_KEY,
    DESIGN2_TPO_BILINGUAL_MASTER_KEY,
    DESIGN2_TPO_EN_MASTER_KEY,
    ensure_design2_master_template,
)
from app.services.template_revision_service import list_published_templates
from app.services.workspace_patch_service import apply_workspace_patch


@pytest.fixture
def hermetic_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


def test_mmip_priority_over_servicing_insurer_and_kurnia_vs_liberty(hermetic_db: OrmSession):
    seed_defaults(hermetic_db, get_settings())
    hermetic_db.add_all([
        InsuranceCompany(
            id=new_id(),
            slug="liberty",
            name="Liberty",
            category="Motor",
            detection_phrases=["Liberty", "Liberty Insurance", "Liberty General Insurance Berhad"],
            status="active",
        ),
        InsuranceCompany(
            id=new_id(),
            slug="amassurance",
            name="AmAssurance",
            category="Motor",
            source_template_category="Amgen / AmAssurance / Kurnia-style",
            detection_phrases=["AmAssurance", "AmGen", "AmGeneral"],
            status="active",
        ),
    ])
    hermetic_db.commit()

    payload = build_companies_payload(list(hermetic_db.scalars(select(InsuranceCompany)).all()))

    # 1. MMIP must take priority even when QBE / another servicing insurer appears in the text
    res_mmip = resolve_company(
        "QBE Insurance (Malaysia) Berhad - Servicing Insurer for Malaysian Motor Insurance Pool (MMIP)",
        payload,
    )
    assert res_mmip["status"] == "matched"
    assert res_mmip["display_name"] == "MMIP"
    assert get_insurer_short_name("QBE / MMIP Pool") == "MMIP"
    assert "Malaysian Motor Insurance Pool" in get_official_insurer_name("MMIP")

    # 2. Kurnia PDF header has "Liberty General Insurance Berhad" + footer "www.kurnia.com" -> Kurnia wins over Liberty
    res_kurnia = resolve_company(
        "QUOTATION Liberty General Insurance Berhad 197801007153 (44191-P) Website www.kurnia.com",
        payload,
    )
    assert res_kurnia["status"] == "matched"
    assert res_kurnia["display_name"] == "Kurnia"

    # 3. Candidate finder prioritizes MMIP + Third Party
    cands = find_candidates(
        "QBE Insurance (Malaysia) Berhad\nMalaysian Motor Insurance Pool (MMIP)\nThird Party Only\nTotal Payable: RM 350.00",
        [{"page": 1, "text": "Malaysian Motor Insurance Pool (MMIP)"}],
        db_companies=payload,
    )
    assert cands["insurance_company"][0].value == "MMIP"
    assert cands["coverage_type"][0].value == "Third Party"


def test_mmip_strict_tpo_lock_box1_only_two_benefits_and_empty_box2(hermetic_db: OrmSession):
    seed_defaults(hermetic_db, get_settings())
    mmip = hermetic_db.scalar(select(InsuranceCompany).where(InsuranceCompany.name == "MMIP"))
    assert mmip is not None

    # Seed MMIP TPO catalog with 2 statutory benefits
    c_tpbi = BenefitConcept(id=new_id(), concept_key="third-party-bodily-injury", label="Third Party Bodily Injury", status="active")
    c_tppd = BenefitConcept(id=new_id(), concept_key="third-party-property-damage", label="Third Party Property Damage", status="active")
    hermetic_db.add_all([c_tpbi, c_tppd])
    prod = InsuranceProduct(id=new_id(), company_id=mmip.id, product_key="mmip-tpo", name="Third Party Only (MMIP)", status="active")
    hermetic_db.add(prod)
    hermetic_db.flush()
    cat = BenefitCatalog(id=new_id(), company_id=mmip.id, product_id=prod.id, name="MMIP Third Party Only", status="published")
    hermetic_db.add(cat)
    hermetic_db.flush()
    rev = BenefitCatalogRevision(id=new_id(), catalog_id=cat.id, revision_number=1, state="published", content_hash="0" * 64, published_at=datetime.now(timezone.utc))
    hermetic_db.add(rev)
    hermetic_db.flush()
    hermetic_db.add_all([
        CatalogOffering(id=new_id(), catalog_revision_id=rev.id, offering_key="base:tpbi", concept_id=c_tpbi.id, offering_kind="base", role="included", label_override="Third Party Bodily Injury", sort_order=1),
        CatalogOffering(id=new_id(), catalog_revision_id=rev.id, offering_key="base:tppd", concept_id=c_tppd.id, offering_kind="base", role="included", label_override="Third Party Property Damage", sort_order=2),
    ])

    user = User(id=new_id(), email="staff@risklocker.test", password_hash="x", role=Role.ADMIN.value, status="active")
    batch = Batch(id=new_id(), owner_id=user.id, name="MMIP", status="ready")
    up = UploadedFile(id=new_id(), batch_id=batch.id, owner_id=user.id, original_filename="mmip.pdf", content_type="application/pdf", storage_path="mmip.pdf", size_bytes=10, status="ready")
    draft = QuotationDraft(
        id=new_id(),
        revision=1,
        uploaded_file_id=up.id,
        owner_id=user.id,
        company_id=mmip.id,
        status="ready",
        fields={
            "insurance_company": {"value": "MMIP", "status": "ready"},
            "coverage_type": {"value": "Comprehensive", "status": "ready"},
        },
        scalar_decisions={},
    )
    hermetic_db.add_all([user, batch, up, draft])
    hermetic_db.commit()

    # Pin catalog enforces Third Party on draft.fields
    pinned_rev = pin_catalog_context(hermetic_db, draft)
    assert pinned_rev is not None
    assert draft.fields["coverage_type"]["value"] == "Third Party"

    # Attempt to patch coverage_type to Comprehensive under MMIP -> coerced to Third Party
    apply_workspace_patch(
        hermetic_db,
        user,
        draft.id,
        base_revision=draft.revision,
        operations=[{"op": "scalar_decision", "field": "coverage_type", "decision": "edit", "value": "Comprehensive"}],
    )
    hermetic_db.refresh(draft)
    assert draft.fields["coverage_type"]["value"] == "Third Party"

    # Box 1 strictly 2 benefits, Box 2 strictly empty, Towing = No towing
    box1 = extract_free_coverage_items([], insurer_name="MMIP")
    assert [i["title"] for i in box1] == ["Third Party Bodily Injury", "Third Party Property Damage"]
    box2 = build_unified_matrix_cards([], [], fill_to_slots=24, insurer_name="MMIP")
    assert box2 == []
    assert resolve_insurer_towing_limit(company_name="MMIP") == "No towing"
    assert get_company_logo_data_uri("MMIP").startswith("data:image/")
    assert get_company_logo_data_uri("Kurnia Insurans (Malaysia) Berhad").startswith("data:image/")


def test_comparison_edit_autoclears_manual_when_reverted_to_detected(hermetic_db: OrmSession):
    user = User(id=new_id(), email="staff@risklocker.test", password_hash="x", role=Role.STAFF.value, status="active")
    veh = TrackedVehicle(id=new_id(), vehicle_no="JAA1234", car_brand="Perodua", car_model="Myvi", manufacture_year=2023)
    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=veh.id,
        vehicle_no="JAA1234",
        customer_name="Ali",
        road_tax=Decimal("90.00"),
        runner_fee=Decimal("20.00"),
        coverage_start_date=datetime(2026, 11, 29, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 11, 28, tzinfo=timezone.utc),
        expiry_month="2027-11",
    )
    batch = Batch(id=new_id(), owner_id=user.id, name="B", status="ready")
    up = UploadedFile(id=new_id(), batch_id=batch.id, owner_id=user.id, original_filename="q.pdf", content_type="application/pdf", storage_path="q.pdf", size_bytes=10, status="ready")
    draft = QuotationDraft(
        id=new_id(),
        revision=1,
        uploaded_file_id=up.id,
        owner_id=user.id,
        status="ready",
        fields={
            "towing": {"value": "50 km", "detected_value": "50 km", "status": "ready"},
            "valuation_type": {"value": "Agreed Value", "detected_value": "Agreed Value", "status": "ready"},
        },
        scalar_decisions={},
        display_options={},
    )
    sess = SessionModel(
        id=new_id(),
        owner_id=user.id,
        uploaded_file_id=up.id,
        draft_id=draft.id,
        tenure_id=tenure.id,
        detected_company="STMB",
        quotation_ref="QE131244",
    )
    entry = TenureComparisonEntry(
        id=new_id(),
        tenure_id=tenure.id,
        session_id=sess.id,
        company_name="STMB",
        sum_insured=23000.0,
        motor_premium=634.0,
        total_payable=744.0,
        towing_limit="50 km",
        towing_km="50 km",
        agreed_value=True,
        valuation_type="agreed_value",
        version=1,
        is_manual=False,
        manual_overrides=[],
    )
    hermetic_db.add_all([user, veh, tenure, batch, up, draft, sess, entry])
    hermetic_db.commit()

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(comparison_router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: hermetic_db
    app.dependency_overrides[current_user] = lambda: user
    client = TestClient(app)

    # Edit towing 50 km -> Unlimited => manual_overrides includes towing_limit
    r1 = client.patch(
        f"/api/comparison/{tenure.id}/entries/{entry.id}",
        json={"towing_limit": "Unlimited"},
    )
    assert r1.status_code == 200
    assert "towing_limit" in r1.json()["manual_overrides"]

    # Edit towing back Unlimited -> 50 km => auto-clears manual_overrides without pressing Reset!
    r2 = client.patch(
        f"/api/comparison/{tenure.id}/entries/{entry.id}",
        json={"towing_limit": "50 km"},
    )
    assert r2.status_code == 200
    assert "towing_limit" not in r2.json()["manual_overrides"]
    assert r2.json()["is_manual"] is False


def test_yoy_ranking_explanation_explains_windscreen_and_prev_policy_diff():
    class _MockEntry:
        def __init__(self, id_, comp, tot, prem, si, ws=None, agreed=True, tow="50 km", rank=1):
            self.id = id_
            self.company_name = comp
            self.total_payable = tot
            self.motor_premium = prem
            self.sum_insured = si
            self.windscreen_sum_insured = ws
            self.agreed_value = agreed
            self.valuation_type = "agreed_value" if agreed else "market_value"
            self.towing_limit = tow
            self.towing_km = tow
            self.excess = 0.0
            self.waiver_betterment = True
            self.betterment_rate = 0.0
            self.special_perils = None
            self.llp_llop = "Included"
            self.extra_addons = {}
            self.manual_rank = None
            self.rank = rank

    e_new = _MockEntry("e1", "STMB", 854.0, 774.0, 23000.0, ws=900.0, rank=1)
    e_other = _MockEntry("e2", "Etiqa", 910.0, 830.0, 23000.0, ws=900.0, tow="200 km", rank=2)
    prev_policy = {
        "sum_insured": 23000.0,
        "insurance_premium": 634.0,
        "total_payable": 754.0,
        "windscreen": None,
        "agreed_value": True,
        "towing": "50 km",
        "waiver_betterment": True,
    }
    msg = build_underwriter_ranking_explanation(e_new, [e_new, e_other], 1, prev_policy=prev_policy)
    assert "Ranked #1" in msg
    assert "+RM 100.00 vs last year (RM 754.00)" in msg
    assert "added RM 900 Windscreen" in msg
    assert "Agreed Value" in msg


def test_previous_policy_upload_creates_ledger_and_extracts_quotation(hermetic_db: OrmSession, monkeypatch):
    user = User(id=new_id(), email="staff@risklocker.test", password_hash="x", role=Role.ADMIN.value, status="active")
    veh = TrackedVehicle(id=new_id(), vehicle_no="JXX8888", car_brand="Proton", car_model="X50", manufacture_year=2023)
    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=veh.id,
        vehicle_no="JXX8888",
        customer_name="Ah Hock",
        road_tax=Decimal("90.00"),
        runner_fee=Decimal("20.00"),
        coverage_start_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 5, 31, tzinfo=timezone.utc),
        expiry_month="2027-05",
    )
    hermetic_db.add_all([user, veh, tenure])
    hermetic_db.commit()

    def _fake_process_job(db, settings, job, *, worker_id, storage=None, **kwargs):
        sess = db.get(SessionModel, job.session_id)
        draft = db.get(QuotationDraft, sess.draft_id)
        sess.document_type = "quotation"
        sess.detected_company = "Etiqa"
        sess.quotation_ref = "Q-2025-PREV"
        draft.fields = {
            "insurance_company": {"value": "Etiqa", "status": "ready"},
            "coverage_amount": {"value": "68000.00", "status": "ready"},
            "premium": {"value": "1420.00", "status": "ready"},
            "roadtax": {"value": "90.00", "status": "ready"},
            "service_fee": {"value": "20.00", "status": "ready"},
            "include_road_tax": {"value": "true", "status": "ready"},
            "include_runner_fee": {"value": "true", "status": "ready"},
            "total_amount": {"value": "1530.00", "status": "ready"},
            "ncd_percent": {"value": "45", "status": "ready"},
            "valuation_type": {"value": "Agreed Value", "status": "ready"},
            "excess_amount": {"value": "0.00", "status": "ready"},
        }
        job.state = "completed"
        db.commit()

    import app.workers.extraction_worker as ew
    monkeypatch.setattr(ew, "process_extraction_job", _fake_process_job)

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(comparison_router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: hermetic_db
    app.dependency_overrides[current_user] = lambda: user
    app.dependency_overrides[settings_dep] = get_settings
    client = TestClient(app)

    import fitz

    pdf_doc = fitz.open()
    pdf_doc.new_page()
    valid_pdf_bytes = pdf_doc.tobytes()
    pdf_doc.close()

    res = client.post(
        f"/api/comparison/{tenure.id}/upload-previous-policy",
        files={"file": ("2025_prev_quote.pdf", io.BytesIO(valid_pdf_bytes), "application/pdf")},
    )
    assert res.status_code == 200
    body = res.json()
    prev_id = body["prev_tenure_id"]
    prev_t = hermetic_db.get(InsuranceTenure, prev_id)
    hermetic_db.refresh(tenure)
    assert prev_t is not None
    assert tenure.previous_tenure_id == prev_t.id
    assert prev_t.tenure_chain_id == tenure.tenure_chain_id
    assert prev_t.stage == "Close - Win"
    assert prev_t.status == "hit"
    assert len(prev_t.expiry_month) == 7 and "-" in prev_t.expiry_month  # YYYY-MM format

    comp = get_marketing_comparison(hermetic_db, tenure.id)
    assert comp["previous_policy"] is not None
    assert comp["previous_policy"]["insurer"] == "Etiqa"
    assert comp["previous_policy"]["sum_insured"] == 68000.0
    assert comp["previous_policy"]["insurance_premium"] == 1420.0


def test_design2_new_variants_and_box2_visual_updates(hermetic_db: OrmSession):
    seed_defaults(hermetic_db, get_settings())
    admin = User(id=new_id(), email="admin@risklocker.test", password_hash="x", role=Role.ADMIN.value, status="active")
    hermetic_db.add(admin)
    hermetic_db.commit()

    report = ensure_design2_master_template(hermetic_db, admin, apply=True)
    assert report["key"] == DESIGN2_MASTER_KEY
    assert len(report["variants"]) == 3

    published = list_published_templates(hermetic_db, admin)
    keys = {t["config"].get("template_key") for t in published}
    assert {
        DESIGN2_MASTER_KEY,
        DESIGN2_EN_MASTER_KEY,
        DESIGN2_TPO_BILINGUAL_MASTER_KEY,
        DESIGN2_TPO_EN_MASTER_KEY,
    }.issubset(keys)

    base_fields = {
        "customer_name": {"value": "TAN WEI MING"},
        "quotation_reference": {"value": "RL260000123"},
        "vehicle_no": {"value": "JAA 8888"},
        "insurance_company": {"value": "MMIP"},
        "cover_period": {"value": "01-12-2026 TO 30-11-2027"},
        "coverage_type": {"value": "Third Party"},
        "car_model": {"value": "PROTON SAGA"},
        "ncd_percent": {"value": "55.00%"},
        "valuation_type": {"value": "Market Value"},
        "excess_amount": {"value": "0.00"},
        "coverage_amount": {"value": "0.00"},
        "premium": {"value": "280.00"},
        "roadtax": {"value": "90.00"},
        "runner_fee": {"value": "20.00"},
        "total_amount": {"value": "390.00"},
    }

    # 1. Standard Bilingual Design 2: check larger italic Box 2 tick + bigger fonts (11.8px / 11.0px / 10.0px)
    html_bi = render_design2_html(
        draft_fields={**base_fields, "insurance_company": {"value": "Kurnia Insurans (Malaysia) Berhad"}},
        template_config={"layout_engine": "design2", "language_mode": "bilingual", "fill_to_slots": 24},
        render_context={"current_benefits": [], "available_addons": [], "selected_ids": ["windscreen"]},
    )
    assert "skewX(-6deg)" in html_bi
    assert "font-size: 11.8px" in html_bi
    assert "font-size: 11.0px" in html_bi
    assert "font-size: 10.0px" in html_bi
    assert "车辆资料" in html_bi
    assert "Add-On" in html_bi

    # 2. Pure English Design 2: zero Chinese characters
    html_en = render_design2_html(
        draft_fields={**base_fields, "insurance_company": {"value": "Kurnia"}},
        template_config={"layout_engine": "design2", "language_mode": "en", "fill_to_slots": 24},
        render_context={"current_benefits": [], "available_addons": []},
    )
    assert "车辆资料" not in html_en
    assert "客户姓名" not in html_en
    assert "应付总额" not in html_en
    assert "公司银行戶口" not in html_en
    assert "Add-On" in html_en

    # 3. TPO Half-Page Bilingual (MMIP): no Add-On Upgrades, 580px page height, 2 TP benefits
    html_tpo_bi = render_design2_html(
        draft_fields=base_fields,
        template_config={"layout_engine": "design2", "language_mode": "bilingual", "hide_addon_upgrades": True, "page_profile": {"height": 580}},
        render_context={"current_benefits": [], "available_addons": []},
    )
    assert "794px 580px" in html_tpo_bi
    assert "Add-On" not in html_tpo_bi
    assert "Third Party Bodily Injury" in html_tpo_bi
    assert "Third Party Property Damage" in html_tpo_bi
    assert "车辆资料" in html_tpo_bi

    # 4. TPO Half-Page English-Only (MMIP): no Chinese & no Add-On Upgrades
    html_tpo_en = render_design2_html(
        draft_fields=base_fields,
        template_config={"layout_engine": "design2", "language_mode": "en", "hide_addon_upgrades": True, "page_profile": {"height": 580}},
        render_context={"current_benefits": [], "available_addons": []},
    )
    assert "794px 580px" in html_tpo_en
    assert "Add-On" not in html_tpo_en
    assert "车辆资料" not in html_tpo_en
    assert "Third Party Bodily Injury" in html_tpo_en
    assert "Third Party Property Damage" in html_tpo_en
