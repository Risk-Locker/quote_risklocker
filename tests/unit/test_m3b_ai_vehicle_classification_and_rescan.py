"""TDD test suite for Milestone 3b: AI Vehicle Intelligence, Unit Preservation, Default Commercial Fees, Real ★ Detected Provenance, and Deep Multi-Pass Re-detect."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.models.enums import AccountStatus, RecordStatus, Role
from app.models.tables import (
    AppSetting,
    Base,
    Batch,
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    DraftBenefitSelection,
    ExtractionRecord,
    InsuranceCompany,
    InsuranceProduct,
    QuotationDraft,
    Session as QuotationSession,
    UploadedFile,
    User,
    new_id,
)


def _make_sqlite_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return SessionLocal()


def test_gemini_schema_and_prompt_include_vehicle_classification_and_unit_rules():
    from app.extraction.gemini_extractor import GEMINI_EXTRACTION_SCHEMA, build_rag_system_prompt

    props = GEMINI_EXTRACTION_SCHEMA["properties"]
    for key in ("vehicle_type", "vehicle_class", "powertrain", "capacity_unit", "clean_vehicle_name"):
        assert key in props, f"GEMINI_EXTRACTION_SCHEMA missing {key}"

    prompt = build_rag_system_prompt()
    upper_prompt = prompt.upper()
    assert "KG" in upper_prompt and "TON" in upper_prompt
    assert "KW" in upper_prompt
    assert "LORRY" in upper_prompt


def test_sany_a_permit_12000kg_preserves_kg_lorry_and_disables_fees():
    from app.extraction.candidate_finder import CandidateValue
    from app.extraction.draft_mapper import build_draft

    candidates = {
        "customer_name": [CandidateValue("customer_name", "M. A. TRANSPORTATION SDN BHD", "gemini_multimodal", 0.99, 1)],
        "vehicle_no": [CandidateValue("vehicle_no", "VRS7732", "gemini_multimodal", 0.99, 1)],
        "car_brand": [CandidateValue("car_brand", "SANY", "gemini_multimodal", 0.99, 1)],
        "car_model": [CandidateValue("car_model", "SANY OTHER COMMERCIAL MAKE SANY", "gemini_multimodal", 0.95, 1)],
        "clean_vehicle_name": [CandidateValue("clean_vehicle_name", "SANY", "gemini_multimodal", 0.99, 1)],
        "engine_cc": [CandidateValue("engine_cc", "12000 KG", "gemini_multimodal", 0.99, 1)],
        "capacity_unit": [CandidateValue("capacity_unit", "KG", "gemini_multimodal", 0.99, 1)],
        "vehicle_type": [CandidateValue("vehicle_type", "Lorry", "gemini_multimodal", 0.99, 1)],
        "vehicle_class": [CandidateValue("vehicle_class", "'A' PERMIT GOODS VEHICLE", "gemini_multimodal", 0.99, 1)],
        "powertrain": [CandidateValue("powertrain", "ICE", "gemini_multimodal", 0.99, 1)],
        "premium": [CandidateValue("premium", "13004.20", "gemini_multimodal", 0.99, 1)],
    }

    fields, _warnings, _status = build_draft(candidates, benefit_lines=[])

    assert fields["vehicle_type"]["value"] == "Lorry"
    assert fields["engine_cc"]["value"] == "12000 KG"
    assert "CC" not in fields["engine_cc"]["value"]
    assert "OTHER COMMERCIAL MAKE" not in fields["car_model"]["value"].upper()
    assert fields["car_model"]["value"].strip().upper() == "SANY"
    assert fields["include_road_tax"]["value"] == "false"
    assert fields["include_runner_fee"]["value"] == "false"
    assert fields["roadtax"]["value"] == "0.00"
    assert fields["service_fee"]["value"] == "0.00"


def test_commercial_tonnage_never_coerced_to_ev_and_hohan_isuzu_lorry_defaults():
    from app.extraction.candidate_finder import CandidateValue
    from app.extraction.draft_mapper import build_draft
    from app.services.road_tax_engine import calculate_road_tax, calculate_road_tax_unified

    # 11 TON Lorry must NEVER become EVSaloonCar 11 kW
    tax_lorry = calculate_road_tax(11, "Lorry", "Company")
    unified_ton = calculate_road_tax_unified("11 TON", vehicle_type="Lorry", owner_type="Company")
    assert unified_ton["vehicle_type"] == "Lorry"
    assert unified_ton["unit"] in {"kg", "ton"}
    assert tax_lorry == unified_ton["road_tax"]

    # HOHAN concrete mixer + OTHER COMMERCIAL ALL MODELS 11 TON -> Lorry, fees disabled
    hohan_candidates = {
        "customer_name": [CandidateValue("customer_name", "MEGA CONCRETE SDN BHD", "gemini_multimodal", 0.99, 1)],
        "car_brand": [CandidateValue("car_brand", "HOHAN", "gemini_multimodal", 0.99, 1)],
        "car_model": [CandidateValue("car_model", "HOHAN ZZ 4255 CONCRETE MIXER", "gemini_multimodal", 0.99, 1)],
        "engine_cc": [CandidateValue("engine_cc", "11 TON", "gemini_multimodal", 0.99, 1)],
        "vehicle_type": [CandidateValue("vehicle_type", "Car", "native_pattern", 0.7, 1)],
    }
    fields, _, _ = build_draft(hohan_candidates, benefit_lines=[])
    assert fields["vehicle_type"]["value"] == "Lorry"
    assert fields["include_road_tax"]["value"] == "false"
    assert fields["include_runner_fee"]["value"] == "false"
    assert fields["roadtax"]["value"] == "0.00"

    # ISUZU NKR55UEEH 3000 CC light truck -> Lorry, preserves 3000 CC, fees disabled
    isuzu_candidates = {
        "customer_name": [CandidateValue("customer_name", "SYARIKAT LOGISTIK JAYA SDN BHD", "gemini_multimodal", 0.99, 1)],
        "car_brand": [CandidateValue("car_brand", "ISUZU", "gemini_multimodal", 0.99, 1)],
        "car_model": [CandidateValue("car_model", "ISUZU NKR55UEEH", "gemini_multimodal", 0.99, 1)],
        "engine_cc": [CandidateValue("engine_cc", "3000 CC", "gemini_multimodal", 0.99, 1)],
        "vehicle_class": [CandidateValue("vehicle_class", "GOODS VEHICLE 'C' PERMIT", "gemini_multimodal", 0.95, 1)],
    }
    isuzu_fields, _, _ = build_draft(isuzu_candidates, benefit_lines=[])
    assert isuzu_fields["vehicle_type"]["value"] == "Lorry"
    assert isuzu_fields["engine_cc"]["value"] == "3000 CC"
    assert isuzu_fields["include_road_tax"]["value"] == "false"
    assert isuzu_fields["include_runner_fee"]["value"] == "false"


def test_byd_ev_70000_w_converts_to_kw_and_rejects_unbounded_ids():
    from app.extraction.candidate_finder import CandidateValue
    from app.extraction.draft_mapper import build_draft
    from app.extraction.validators import validate_engine_cc
    from app.services.road_tax_engine import calculate_road_tax

    # Modern EV: BYD Dolphin 70000 W -> 70 kW EVSaloonCar (NEVER 70000 CC = RM 303,630!)
    ev_candidates = {
        "customer_name": [CandidateValue("customer_name", "LIM WEI MING", "gemini_multimodal", 0.99, 1)],
        "car_brand": [CandidateValue("car_brand", "BYD", "gemini_multimodal", 0.99, 1)],
        "car_model": [CandidateValue("car_model", "BYD DOLPHIN STANDARD", "gemini_multimodal", 0.99, 1)],
        "engine_cc": [CandidateValue("engine_cc", "70000 W", "gemini_multimodal", 0.99, 1)],
        "vehicle_type": [CandidateValue("vehicle_type", "Car", "native_pattern", 0.7, 1)],
    }
    ev_fields, _, _ = build_draft(ev_candidates, benefit_lines=[])
    assert ev_fields["vehicle_type"]["value"] == "EVSaloonCar"
    assert ev_fields["engine_cc"]["value"] in {"70 kW", "70.0 kW"}
    rt_val = float(ev_fields["roadtax"]["value"])
    assert 0.0 < rt_val < 500.0
    assert calculate_road_tax("70000 W", "EVSaloonCar", "Private") == rt_val

    # Implausible serial numbers / IDs must NOT produce massive CC road tax
    bad_candidates = {
        "customer_name": [CandidateValue("customer_name", "LOGISTICS SDN BHD", "gemini_multimodal", 0.99, 1)],
        "car_brand": [CandidateValue("car_brand", "ISUZU", "gemini_multimodal", 0.99, 1)],
        "car_model": [CandidateValue("car_model", "ISUZU NPR", "gemini_multimodal", 0.99, 1)],
        "engine_cc": [CandidateValue("engine_cc", "411823", "native_pattern", 0.6, 1)],
    }
    bad_fields, _, _ = build_draft(bad_candidates, benefit_lines=[])
    assert bad_fields["roadtax"]["value"] in {"0.00", ""}
    assert "411823" not in bad_fields["engine_cc"]["value"]

    assert validate_engine_cc("411823 CC")[0] is False
    assert validate_engine_cc("10340321623029704 CC")[0] is False
    assert validate_engine_cc("12000 KG")[0] is True
    assert validate_engine_cc("150 kW")[0] is True


def test_company_passenger_car_preserves_trims_and_fees_enabled():
    from app.extraction.candidate_finder import CandidateValue
    from app.extraction.draft_mapper import build_draft
    from app.services.vehicle_simplifier_service import clean_vehicle_tokens_deterministic

    _brand, _model, combined = clean_vehicle_tokens_deterministic("MERCEDES-BENZ", "MERCEDES-BENZ S 400")
    assert "S 400" in combined.upper() or "S400" in combined.upper()

    _b2, _m2, combined2 = clean_vehicle_tokens_deterministic("MERCEDES-BENZ", "MERCEDES-BENZ G 350")
    assert "G 350" in combined2.upper() or "G350" in combined2.upper()

    corp_car_candidates = {
        "customer_name": [CandidateValue("customer_name", "RISKLOCKER HOLDINGS SDN BHD", "gemini_multimodal", 0.99, 1)],
        "car_brand": [CandidateValue("car_brand", "MERCEDES-BENZ", "gemini_multimodal", 0.99, 1)],
        "car_model": [CandidateValue("car_model", "MERCEDES-BENZ S 400", "gemini_multimodal", 0.99, 1)],
        "engine_cc": [CandidateValue("engine_cc", "2996 CC", "gemini_multimodal", 0.99, 1)],
        "vehicle_type": [CandidateValue("vehicle_type", "Car", "gemini_multimodal", 0.99, 1)],
    }
    fields, _, _ = build_draft(corp_car_candidates, benefit_lines=[])
    assert fields["client_type"]["value"] == "Company"
    assert fields["vehicle_type"]["value"] == "CompanyCar"
    assert fields["include_road_tax"]["value"] == "true"
    assert fields["include_runner_fee"]["value"] == "true"
    assert float(fields["roadtax"]["value"]) > 100.0


def test_render_context_is_detected_requires_true_extraction_provenance():
    from app.rendering.render_context import _card

    concept = SimpleNamespace(
        id="c1",
        concept_key="legal-defense-costs",
        label="Legal Defense Costs",
        description="Reimburses court legal defense fees.",
        description_variants={},
        requires_value=False,
        default_unit=None,
    )
    offering = SimpleNamespace(
        id="off1",
        concept_id="c1",
        category="default",
        cost_status="included",
        optional_price=None,
        description_override=None,
        display_value=None,
        asset_id=None,
    )

    # DB catalog baseline default added automatically (NOT extracted from PDF!)
    baseline_selection = SimpleNamespace(
        id="sel1",
        source_kind="published_base",
        source="published_base",
        source_line_id=None,
        evidence_snapshot={"source": "published_base", "coverage_limit": None},
        cost_status="included",
        price=None,
        typed_value_override=None,
    )
    baseline_card = _card(
        selection=baseline_selection,
        offering=offering,
        concept=concept,
        typed_value=None,
    )
    assert baseline_card["is_detected"] is False
    assert baseline_card["is_extra"] is False

    # Genuinely extracted benefit line from source PDF
    extracted_selection = SimpleNamespace(
        id="sel2",
        source_kind="extracted",
        source="extracted",
        source_line_id="ext-line-1",
        evidence_snapshot={"source": "extracted", "source_line_id": "ext-line-1", "coverage_limit": "RM 2,000"},
        cost_status="included",
        price=None,
        typed_value_override=None,
    )
    extracted_card = _card(
        selection=extracted_selection,
        offering=offering,
        concept=concept,
        typed_value=None,
    )
    assert extracted_card["is_detected"] is True


def test_deep_rescan_heals_broken_sany_draft_and_rolls_back_on_ai_error(tmp_path):
    from app.core.config import get_settings
    from app.core.errors import AppError
    from app.services.session_rescan_service import rescan_session

    db = _make_sqlite_db()
    user = User(
        id=new_id(),
        email="staff@risklocker.test",
        name="Staff User",
        password_hash="x",
        role=Role.STAFF.value,
        status=AccountStatus.ACTIVE.value,
    )
    company = InsuranceCompany(
        id=new_id(),
        name="AmAssurance",
        detection_phrases=["AMASSURANCE"],
        status=AccountStatus.ACTIVE.value,
    )
    product = InsuranceProduct(
        id=new_id(),
        company_id=company.id,
        product_key="comm-comp",
        name="Commercial Vehicle Comprehensive",
        status=AccountStatus.ACTIVE.value,
    )
    catalog = BenefitCatalog(
        id=new_id(),
        company_id=company.id,
        product_id=product.id,
        name="AmAssurance Commercial",
        status=AccountStatus.ACTIVE.value,
    )
    rev = BenefitCatalogRevision(
        id=new_id(),
        catalog_id=catalog.id,
        revision_number=1,
        state="published",
        content_hash="abc123",
    )
    concept = BenefitConcept(
        id=new_id(),
        concept_key="panel-workmanship-warranty",
        label="Panel Workmanship Warranty",
        description="Guaranteed repair workmanship",
        status=AccountStatus.ACTIVE.value,
    )
    pdf_path = tmp_path / "vrs7732.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% SANY 'A' PERMIT GOODS VEHICLE 12000 KG\n%%EOF")

    batch = Batch(
        id=new_id(),
        owner_id=user.id,
        name="VRS7732",
        status=RecordStatus.READY.value,
    )
    uploaded = UploadedFile(
        id=new_id(),
        batch_id=batch.id,
        owner_id=user.id,
        original_filename="VRS7732.pdf",
        content_type="application/pdf",
        storage_path=str(pdf_path),
        storage_provider="local_ephemeral",
        size_bytes=pdf_path.stat().st_size,
        status=RecordStatus.READY.value,
        enhanced_reading=False,
    )
    extraction = ExtractionRecord(
        id=new_id(),
        uploaded_file_id=uploaded.id,
        raw_text="INSURED: M. A. TRANSPORTATION SDN BHD 'A' PERMIT GOODS VEHICLE SANY 12000 KG",
        candidates={},
        benefit_lines=[],
        reading_quality="ready",
    )
    draft = QuotationDraft(
        id=new_id(),
        revision=1,
        uploaded_file_id=uploaded.id,
        owner_id=user.id,
        company_id=company.id,
        product_id=product.id,
        catalog_revision_id=rev.id,
        status=RecordStatus.READY.value,
        fields={
            "quotation_reference": {"value": "RL260000670", "status": "ready"},
            "customer_name": {"value": "M. A. TRANSPORTATION SDN BHD", "status": "ready"},
            "vehicle_no": {"value": "VRS7732", "status": "ready"},
            "car_model": {"value": "SANY OTHER COMMERCIAL MAKE SANY", "status": "ready"},
            "engine_cc": {"value": "12000 CC", "status": "ready"},
            "vehicle_type": {"value": "CompanyCar", "status": "ready"},
            "client_type": {"value": "Company", "status": "ready"},
            "roadtax": {"value": "127510.00", "status": "ready"},
            "service_fee": {"value": "20.00", "status": "ready"},
            "premium": {"value": "13004.20", "status": "ready"},
            "total_amount": {"value": "140534.00", "status": "ready"},
        },
        display_options={"include_road_tax": True, "include_runner_fee": True},
        scalar_decisions={},
        warnings=[],
    )
    session = QuotationSession(
        id=new_id(),
        owner_id=user.id,
        uploaded_file_id=uploaded.id,
        draft_id=draft.id,
        quotation_ref="RL260000670",
        status=AccountStatus.ACTIVE.value,
        detected_company="AmAssurance",
    )
    db.add(AppSetting(key="default_runner_fee", value={"amount": 20.0}))
    db.add_all([user, company, product, catalog, rev, concept, batch, uploaded, extraction, draft, session])
    db.commit()

    settings = get_settings()

    # 1. AI outage during deep rescan MUST roll back / preserve broken or user-edited draft cleanly
    with patch("app.services.session_rescan_service.load_pdf_bytes", return_value=pdf_path.read_bytes()), \
         patch("app.extraction.gemini_extractor.extract_with_gemini_sync", return_value=None):
        with pytest.raises(AppError):
            rescan_session(db, session.id, user, settings, mode="in_place", engine="deep")
    db.refresh(draft)
    assert draft.fields["premium"]["value"] == "13004.20"

    # 2. Successful deep multi-pass rescan heals 12000 CC -> 12000 KG, CompanyCar -> Lorry, fees OFF
    gemini_good = {
        "customer_name": "M. A. TRANSPORTATION SDN BHD",
        "vehicle_no": "VRS7732",
        "insurance_company": "AmAssurance",
        "car_brand": "SANY",
        "car_model": "SANY OTHER COMMERCIAL MAKE SANY",
        "clean_vehicle_name": "SANY",
        "engine_cc": "12000 KG",
        "capacity_unit": "KG",
        "vehicle_type": "Lorry",
        "vehicle_class": "'A' PERMIT GOODS VEHICLE",
        "powertrain": "ICE",
        "total_amount": "13004.20",
        "detected_benefits": [
            {"label": "Panel Workmanship Warranty", "value": "Included", "concept_key": "panel-workmanship-warranty"},
        ],
    }
    with patch("app.services.session_rescan_service.load_pdf_bytes", return_value=pdf_path.read_bytes()), \
         patch("app.extraction.gemini_extractor.extract_with_gemini_sync", return_value=gemini_good):
        res = rescan_session(db, session.id, user, settings, mode="in_place", engine="deep")

    assert res["success"] is True
    assert "diff" in res
    db.refresh(draft)
    assert draft.fields["engine_cc"]["value"] == "12000 KG"
    assert draft.fields["vehicle_type"]["value"] == "Lorry"
    assert draft.fields["car_model"]["value"] == "SANY"
    assert draft.fields["roadtax"]["value"] == "0.00"
    assert draft.fields["service_fee"]["value"] == "0.00"
    assert draft.fields["include_road_tax"]["value"] == "false"
    assert draft.fields["include_runner_fee"]["value"] == "false"
    assert draft.display_options["include_road_tax"] is False
    assert draft.display_options["include_runner_fee"] is False
    assert draft.fields["total_amount"]["value"] == "13004.20"


def test_simplify_vehicle_name_avoids_duplicate_unpaced_gemini_call():
    from app.services.vehicle_simplifier_service import simplify_vehicle_name_with_ai

    with patch("httpx.post", side_effect=AssertionError("Must not fire un-paced 2nd HTTP Gemini request!")):
        brand, model, combined = simplify_vehicle_name_with_ai(
            "SANY",
            "SANY OTHER COMMERCIAL MAKE SANY",
            gemini_clean_name="SANY",
        )
    assert combined.upper() == "SANY"
    assert "OTHER COMMERCIAL MAKE" not in model.upper()


def test_fastapi_rescan_extract_gemini_and_comparison_rescan_routes(tmp_path):
    from datetime import datetime, timezone
    from app.api.deps import current_user, get_db
    from app.api.routers.comparison import router as comparison_router
    from app.api.routers.sessions import router as sessions_router
    from app.core.errors import register_error_handlers
    from app.models.tables import InsuranceTenure, TrackedVehicle

    db = _make_sqlite_db()
    owner = User(
        id=new_id(),
        email="owner@risklocker.test",
        name="Owner",
        password_hash="x",
        role=Role.STAFF.value,
        status=AccountStatus.ACTIVE.value,
    )
    unauthorized_dev = User(
        id=new_id(),
        email="dev@risklocker.test",
        name="Dev Role",
        password_hash="x",
        role=Role.DEV.value,
        status=AccountStatus.ACTIVE.value,
    )
    company = InsuranceCompany(
        id=new_id(),
        name="AmAssurance",
        detection_phrases=["AMASSURANCE"],
        status=AccountStatus.ACTIVE.value,
    )
    tv = TrackedVehicle(
        id=new_id(),
        vehicle_no="VRS7732",
        car_brand="SANY",
        car_model="SANY OTHER COMMERCIAL MAKE SANY",
        engine_cc="12000 CC",
    )
    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=tv.id,
        vehicle_no="VRS7732",
        customer_name="M. A. TRANSPORTATION SDN BHD",
        coverage_start_date=datetime(2026, 1, 10, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 1, 10, tzinfo=timezone.utc),
        expiry_month="2027-01",
        road_tax=127510.0,
        runner_fee=20.0,
        include_road_tax=True,
        include_runner_fee=True,
        created_by_id=owner.id,
    )
    pdf_path = tmp_path / "vrs_route.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% SANY 'A' PERMIT GOODS VEHICLE 12000 KG\n%%EOF")
    batch = Batch(id=new_id(), owner_id=owner.id, name="VRS7732", status=RecordStatus.READY.value)
    uploaded = UploadedFile(
        id=new_id(),
        batch_id=batch.id,
        owner_id=owner.id,
        original_filename="VRS7732.pdf",
        content_type="application/pdf",
        storage_path=str(pdf_path),
        storage_provider="local_ephemeral",
        size_bytes=pdf_path.stat().st_size,
        status=RecordStatus.READY.value,
        enhanced_reading=False,
    )
    draft = QuotationDraft(
        id=new_id(),
        revision=1,
        uploaded_file_id=uploaded.id,
        owner_id=owner.id,
        company_id=company.id,
        status=RecordStatus.READY.value,
        fields={
            "quotation_reference": {"value": "RL260000671", "status": "ready"},
            "customer_name": {"value": "M. A. TRANSPORTATION SDN BHD", "status": "ready"},
            "vehicle_no": {"value": "VRS7732", "status": "ready"},
            "car_model": {"value": "SANY OTHER COMMERCIAL MAKE SANY", "status": "ready"},
            "engine_cc": {"value": "12000 CC", "status": "ready"},
            "vehicle_type": {"value": "CompanyCar", "status": "ready"},
            "roadtax": {"value": "127510.00", "status": "ready"},
            "service_fee": {"value": "20.00", "status": "ready"},
            "total_amount": {"value": "140534.00", "status": "ready"},
        },
        display_options={"include_road_tax": True, "include_runner_fee": True},
        scalar_decisions={},
        warnings=[],
    )
    session = QuotationSession(
        id=new_id(),
        owner_id=owner.id,
        uploaded_file_id=uploaded.id,
        draft_id=draft.id,
        quotation_ref="RL260000671",
        status=AccountStatus.ACTIVE.value,
        detected_company="AmAssurance",
        tracked_vehicle_id=tv.id,
        tenure_id=tenure.id,
    )
    db.add_all([owner, unauthorized_dev, company, tv, tenure, batch, uploaded, draft, session])
    db.commit()

    active_user = {"user": owner}
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(sessions_router, prefix="/api")
    app.include_router(comparison_router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[current_user] = lambda: active_user["user"]
    client = TestClient(app)

    gemini_good = {
        "customer_name": "M. A. TRANSPORTATION SDN BHD",
        "vehicle_no": "VRS7732",
        "insurance_company": "AmAssurance",
        "car_brand": "SANY",
        "car_model": "SANY OTHER COMMERCIAL MAKE SANY",
        "clean_vehicle_name": "SANY",
        "engine_cc": "12000 KG",
        "capacity_unit": "KG",
        "vehicle_type": "Lorry",
        "vehicle_class": "'A' PERMIT GOODS VEHICLE",
        "powertrain": "ICE",
        "total_amount": "13004.20",
        "detected_benefits": [],
    }

    # 1. Non-business role RBAC check: Role.DEV cannot view/mutate owner session (404 zero data leakage)
    active_user["user"] = unauthorized_dev
    forbidden_res = client.post(f"/api/sessions/{session.id}/rescan", json={"mode": "in_place", "engine": "deep"})
    assert forbidden_res.status_code == 404

    # 2. Comparison deep rescan via API fixes both draft AND tenure fees atomically
    active_user["user"] = owner
    with patch("app.services.session_rescan_service.load_pdf_bytes", return_value=pdf_path.read_bytes()), \
         patch("app.extraction.gemini_extractor.extract_with_gemini_sync", return_value=gemini_good):
        comp_res = client.post(f"/api/comparison/{tenure.id}/rescan", json={"session_id": session.id, "deep": True})
    assert comp_res.status_code == 200
    body = comp_res.json()
    assert body["tenure"]["include_road_tax"] is False
    assert body["tenure"]["include_runner_fee"] is False
    assert float(body["tenure"]["road_tax"]) == 0.0
    assert float(body["tenure"]["runner_fee"]) == 0.0

    # 3. Direct session /rescan (engine='deep') + /extract-gemini routes both return HTTP 200 with KG & Lorry
    with patch("app.services.session_rescan_service.load_pdf_bytes", return_value=pdf_path.read_bytes()), \
         patch("app.extraction.gemini_extractor.extract_with_gemini_sync", return_value=gemini_good):
        rescan_res = client.post(f"/api/sessions/{session.id}/rescan", json={"mode": "in_place", "engine": "deep"})
        assert rescan_res.status_code == 200
        assert rescan_res.json()["engine_used"] == "deep"

    with patch("app.api.routers.sessions.load_pdf_bytes", return_value=pdf_path.read_bytes()), \
         patch("app.extraction.gemini_extractor.extract_with_gemini_sync", return_value=gemini_good):
        ext_res = client.post(f"/api/sessions/{session.id}/extract-gemini")
        assert ext_res.status_code == 200
        db.refresh(draft)
        assert draft.fields["engine_cc"]["value"] == "12000 KG"
        assert draft.fields["vehicle_type"]["value"] == "Lorry"
        assert draft.fields["roadtax"]["value"] == "0.00"
