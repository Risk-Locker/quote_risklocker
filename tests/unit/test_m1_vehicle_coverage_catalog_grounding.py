"""Hermetic Red-First TDD suite for Milestone 1:
- Field-scoped Commercial Lorry vs Private Passenger Car classification (no Trailer header false positives)
- CandidateFinder coverage_type hygiene (Comprehensive vs TPFT vs Third Party without Private Car pollution)
- Catalog pinning priority (ICE vs EV, company_commercial segment_key, auto365 tier disambiguation)
- Level-2 Online Grounding (Google Search tool + DB VehicleModel cache + 3-Eye Consensus wiring)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.extraction.candidate_finder import find_candidates
from app.extraction.entity_classifier import classify_client_entity, is_commercial_heavy_vehicle
from app.extraction.referee import audit_and_reconcile_draft
from app.models.tables import (
    Base,
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    CatalogOffering,
    CoverageType,
    InsuranceCompany,
    InsuranceProduct,
    QuotationDraft,
    Segment,
    VehicleBrand,
    VehicleCategory,
    VehicleModel,
    new_id,
)
from app.services.catalog_review_service import initialize_catalog_review


@pytest.fixture()
def hermetic_db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()


def test_amgen_honda_crv_with_trailer_header_stays_private_car_and_comprehensive():
    """Real AmAssurance quotation prints 'Trailer No' and 'Basic Premium (Trailer)' with 0.00.
    Honda CR-V (2354 CC, PRIVATE CAR EX GOODS) must NEVER be classified as Lorry.
    """
    raw_text = (
        "QUOTATION auto365 Comprehensive Plus\n"
        "Insured Name : HOW YEOK CHIAN\n"
        "Vehicle Class : PRIVATE CAR EX GOODS\n"
        "Make / Model : HONDA CR-V 2.4\n"
        "Capacity : 2354 CC\n"
        "Coverage Type : Comprehensive\n"
        "Vehicle No : JPQ6655\n"
        "Trailer No :   Basic Premium (Trailer) : 0.00   Trailer Sum Insured : 0.00\n"
        "Subject to liability to third party property damage endorsement.\n"
    )
    assert is_commercial_heavy_vehicle(
        vehicle_type="NonSaloonCar",
        car_model="HONDA CR-V",
        vehicle_class="PRIVATE CAR EX GOODS",
        capacity_str="2354 CC",
        raw_text=raw_text,
    ) is False

    fields = {
        "customer_name": {"value": "HOW YEOK CHIAN", "status": "ready"},
        "car_brand": {"value": "HONDA", "status": "ready"},
        "car_model": {"value": "Honda CR-V", "status": "ready"},
        "vehicle_class": {"value": "PRIVATE CAR EX GOODS", "status": "ready"},
        "vehicle_type": {"value": "NonSaloonCar", "status": "ready"},
        "engine_cc": {"value": "2354 CC", "status": "ready"},
        "coverage_type": {"value": "Comprehensive", "status": "ready"},
        "product_name": {"value": "auto365 Comprehensive Plus", "status": "ready"},
    }
    reconciled, notices = audit_and_reconcile_draft(fields, raw_text=raw_text)
    assert reconciled["vehicle_type"]["value"] in {"Car", "NonSaloonCar"}
    assert reconciled["vehicle_type"]["value"] != "Lorry"
    assert reconciled["coverage_type"]["value"] == "Comprehensive"
    assert str((reconciled.get("include_road_tax") or {}).get("value", "")).lower() != "false"


def test_candidate_finder_coverage_type_excludes_private_car_and_false_third_party():
    """Messy compact text on a Comprehensive quote with 'third party' in liability copy
    must resolve Comprehensive, never Private Car / Motor Takaful / false Third Party.
    """
    comp_text = (
        "SYARIKAT TAKAFUL MALAYSIA AM BERHAD\n"
        "MOTOR TAKAFUL PRIVATE CAR COMPREHENSIVE\n"
        "Covers loss or damage and legal liability to third party property.\n"
    )
    cands = find_candidates(comp_text, [{"page": 1, "text": comp_text}])
    cov_vals = [c.value for c in cands.get("coverage_type", [])]
    assert "Private Car" not in cov_vals
    assert "Motor Takaful" not in cov_vals
    assert cov_vals[0] == "Comprehensive"

    tp_text = "COVER TYPE: THIRD PARTY ONLY\nVehicle: ISUZU NPR\nBasic Premium RM 450.00"
    tp_cands = find_candidates(tp_text, [{"page": 1, "text": tp_text}])
    assert tp_cands["coverage_type"][0].value == "Third Party"

    tpft_text = "Policy Coverage: Third Party Fire and Theft\nVehicle: PROTON SAGA"
    tpft_cands = find_candidates(tpft_text, [{"page": 1, "text": tpft_text}])
    assert tpft_cands["coverage_type"][0].value == "Third Party Fire & Theft"


def test_referee_preserves_third_party_on_commercial_lorry():
    """Even when vehicle IS a Lorry, Third Party / TPFT coverage must NOT be clobbered."""
    fields = {
        "customer_name": {"value": "MAJU LOGISTICS SDN BHD", "status": "ready"},
        "car_brand": {"value": "ISUZU", "status": "ready"},
        "car_model": {"value": "ISUZU NPR PRO", "status": "ready"},
        "vehicle_type": {"value": "Lorry", "status": "ready"},
        "engine_cc": {"value": "7500 KG", "status": "ready"},
        "coverage_type": {"value": "Third Party", "status": "ready"},
        "product_name": {"value": "Private Car Third Party", "status": "ready"},
        "sum_insured": {"value": "0.00", "status": "ready"},
    }
    reconciled, _ = audit_and_reconcile_draft(fields, raw_text="ISUZU NPR 7500 KG THIRD PARTY ONLY")
    assert reconciled["vehicle_type"]["value"] == "Lorry"
    assert reconciled["coverage_type"]["value"] == "Third Party"
    assert "Comprehensive" not in reconciled["product_name"]["value"]


def test_pin_catalog_context_never_picks_ev_for_petrol_and_honors_company_commercial_and_auto365_tiers(hermetic_db: Session):
    """Reproduces the exact Postgres catalog hierarchy:
    1) Takaful myMotor (Private Car) ICE (no 'comprehensive' word in product name) vs Takaful Malaysia Private Car Comprehensive (EV)
    2) AmAssurance Private Car Comprehensive product holding 3 catalogs: Lite, Plus, Premier + EV catalog
    3) Commercial Lorry Third Party using live segment_key='company_commercial'
    """
    stmb = InsuranceCompany(id=new_id(), slug="takaful-malaysia", name="Takaful Malaysia", category="Motor", status="active")
    amgen = InsuranceCompany(id=new_id(), slug="amassurance", name="AmAssurance", category="Motor", status="active")
    seg_priv = Segment(id=new_id(), segment_key="private", name="Private", status="active")
    seg_comm = Segment(id=new_id(), segment_key="company_commercial", name="Company / Commercial", status="active")
    cat_car = VehicleCategory(id=new_id(), category_key="car", name="Car", status="active")
    cat_lorry = VehicleCategory(id=new_id(), category_key="commercial_vehicle", name="Lorry", status="active")
    cov_comp = CoverageType(id=new_id(), coverage_key="comprehensive", name="Comprehensive", status="active")
    cov_tp = CoverageType(id=new_id(), coverage_key="third_party", name="Third Party", status="active")
    c_towing = BenefitConcept(id=new_id(), concept_key="towing", label="Emergency Towing Assistance", status="active")

    # STMB products & catalogs (exactly matching live Postgres naming trap!)
    p_stmb_ice = InsuranceProduct(id=new_id(), company_id=stmb.id, product_key="mymotor", name="Takaful myMotor (Private Car)", status="active")
    p_stmb_ev = InsuranceProduct(id=new_id(), company_id=stmb.id, product_key="stmb-ev", name="Takaful Malaysia Private Car Comprehensive (EV)", status="active")
    c_stmb_ice = BenefitCatalog(id=new_id(), company_id=stmb.id, product_id=p_stmb_ice.id, segment_id=seg_priv.id, vehicle_category_id=cat_car.id, coverage_type_id=cov_comp.id, engine_type="ice", name="Takaful myMotor (Private Car)", status="published")
    c_stmb_ev = BenefitCatalog(id=new_id(), company_id=stmb.id, product_id=p_stmb_ev.id, segment_id=seg_priv.id, vehicle_category_id=cat_car.id, coverage_type_id=cov_comp.id, engine_type="ev", name="Takaful Malaysia Private Car Comprehensive (EV)", status="published")
    r_stmb_ice = BenefitCatalogRevision(id=new_id(), catalog_id=c_stmb_ice.id, revision_number=1, state="published", content_hash="stmb-ice")
    r_stmb_ev = BenefitCatalogRevision(id=new_id(), catalog_id=c_stmb_ev.id, revision_number=1, state="published", content_hash="stmb-ev")

    # AmAssurance products & catalogs (single Private Car Comprehensive product + Lite/Plus/Premier catalogs + Commercial Lorry TP)
    p_amg_car = InsuranceProduct(id=new_id(), company_id=amgen.id, product_key="amg-priv-car", name="Private Car Comprehensive", status="active")
    p_amg_ev = InsuranceProduct(id=new_id(), company_id=amgen.id, product_key="amg-priv-ev", name="AmAssurance Private Car Comprehensive (EV)", status="active")
    p_amg_lorry_tp = InsuranceProduct(id=new_id(), company_id=amgen.id, product_key="amg-lorry-tp", name="Commercial Lorry (Own Goods - C Permit) (Third Party)", status="active")

    c_amg_lite = BenefitCatalog(id=new_id(), company_id=amgen.id, product_id=p_amg_car.id, segment_id=seg_priv.id, vehicle_category_id=cat_car.id, coverage_type_id=cov_comp.id, engine_type="ice", name="auto365 Comprehensive Lite", status="published")
    c_amg_plus = BenefitCatalog(id=new_id(), company_id=amgen.id, product_id=p_amg_car.id, segment_id=seg_priv.id, vehicle_category_id=cat_car.id, coverage_type_id=cov_comp.id, engine_type="ice", name="auto365 Comprehensive Plus", status="published")
    c_amg_premier = BenefitCatalog(id=new_id(), company_id=amgen.id, product_id=p_amg_car.id, segment_id=seg_priv.id, vehicle_category_id=cat_car.id, coverage_type_id=cov_comp.id, engine_type="ice", name="auto365 Comprehensive Premier", status="published")
    c_amg_ev = BenefitCatalog(id=new_id(), company_id=amgen.id, product_id=p_amg_ev.id, segment_id=seg_priv.id, vehicle_category_id=cat_car.id, coverage_type_id=cov_comp.id, engine_type="ev", name="auto365 Comprehensive Plus (EV)", status="published")
    c_amg_lorry_tp = BenefitCatalog(id=new_id(), company_id=amgen.id, product_id=p_amg_lorry_tp.id, segment_id=seg_comm.id, vehicle_category_id=cat_lorry.id, coverage_type_id=cov_tp.id, engine_type="ice", name="Commercial Lorry (Own Goods - C Permit) (Third Party)", status="published")

    r_amg_lite = BenefitCatalogRevision(id=new_id(), catalog_id=c_amg_lite.id, revision_number=1, state="published", content_hash="amg-lite")
    r_amg_plus = BenefitCatalogRevision(id=new_id(), catalog_id=c_amg_plus.id, revision_number=1, state="published", content_hash="amg-plus")
    r_amg_premier = BenefitCatalogRevision(id=new_id(), catalog_id=c_amg_premier.id, revision_number=1, state="published", content_hash="amg-premier")
    r_amg_ev = BenefitCatalogRevision(id=new_id(), catalog_id=c_amg_ev.id, revision_number=1, state="published", content_hash="amg-ev")
    r_amg_lorry_tp = BenefitCatalogRevision(id=new_id(), catalog_id=c_amg_lorry_tp.id, revision_number=1, state="published", content_hash="amg-lorry-tp")

    o_stmb_tow = CatalogOffering(id=new_id(), catalog_revision_id=r_stmb_ice.id, concept_id=c_towing.id, offering_key="stmb-tow-50", offering_kind="base", role="included", display_value="50 km", status="active")
    o_plus_tow = CatalogOffering(id=new_id(), catalog_revision_id=r_amg_plus.id, concept_id=c_towing.id, offering_key="plus-tow-100", offering_kind="base", role="included", display_value="100 km", status="active")

    hermetic_db.add_all([
        stmb, amgen, seg_priv, seg_comm, cat_car, cat_lorry, cov_comp, cov_tp, c_towing,
        p_stmb_ice, p_stmb_ev, c_stmb_ice, c_stmb_ev, r_stmb_ice, r_stmb_ev,
        p_amg_car, p_amg_ev, p_amg_lorry_tp,
        c_amg_lite, c_amg_plus, c_amg_premier, c_amg_ev, c_amg_lorry_tp,
        r_amg_lite, r_amg_plus, r_amg_premier, r_amg_ev, r_amg_lorry_tp,
        o_stmb_tow, o_plus_tow,
    ])
    hermetic_db.commit()

    # Case 1: STMB petrol CR-V must pin to Takaful myMotor ICE, NEVER EV
    draft_stmb = QuotationDraft(
        id=new_id(),
        uploaded_file_id=new_id(),
        owner_id=new_id(),
        company_id=stmb.id,
        fields={
            "car_brand": {"value": "HONDA"},
            "car_model": {"value": "CR-V"},
            "engine_cc": {"value": "2354 CC"},
            "vehicle_type": {"value": "NonSaloonCar"},
            "vehicle_class": {"value": "Private Car"},
            "coverage_type": {"value": "Comprehensive"},
            "product_name": {"value": "MOTOR TAKAFUL"},
        },
        scalar_decisions={},
        warnings=[],
    )
    hermetic_db.add(draft_stmb)
    hermetic_db.flush()
    res_stmb = initialize_catalog_review(hermetic_db, draft_stmb)
    assert res_stmb["catalog_revision_id"] == r_stmb_ice.id
    assert draft_stmb.product_id == p_stmb_ice.id

    # Case 2: AmAssurance petrol CR-V auto365 Comprehensive Plus must pin to auto365 Comprehensive Plus ICE (NOT Lite, NOT EV)
    draft_amg = QuotationDraft(
        id=new_id(),
        uploaded_file_id=new_id(),
        owner_id=new_id(),
        company_id=amgen.id,
        fields={
            "car_brand": {"value": "HONDA"},
            "car_model": {"value": "CR-V"},
            "engine_cc": {"value": "2354 CC"},
            "vehicle_type": {"value": "NonSaloonCar"},
            "vehicle_class": {"value": "PRIVATE CAR EX GOODS"},
            "coverage_type": {"value": "Comprehensive"},
            "product_name": {"value": "auto365 Comprehensive Plus"},
        },
        scalar_decisions={},
        warnings=[],
    )
    hermetic_db.add(draft_amg)
    hermetic_db.flush()
    res_amg = initialize_catalog_review(hermetic_db, draft_amg)
    assert res_amg["catalog_revision_id"] == r_amg_plus.id

    # Case 3: Commercial Lorry Third Party with company_commercial segment
    draft_lorry_tp = QuotationDraft(
        id=new_id(),
        uploaded_file_id=new_id(),
        owner_id=new_id(),
        company_id=amgen.id,
        fields={
            "customer_name": {"value": "KILANG KAYU SDN BHD"},
            "car_brand": {"value": "ISUZU"},
            "car_model": {"value": "NPR"},
            "engine_cc": {"value": "7500 KG"},
            "vehicle_type": {"value": "Lorry"},
            "coverage_type": {"value": "Third Party"},
        },
        scalar_decisions={},
        warnings=[],
    )
    hermetic_db.add(draft_lorry_tp)
    hermetic_db.flush()
    res_lorry = initialize_catalog_review(hermetic_db, draft_lorry_tp)
    assert res_lorry["catalog_revision_id"] == r_amg_lorry_tp.id


def test_level2_online_grounding_google_search_and_cache(hermetic_db: Session, monkeypatch):
    """Level-2 online grounding calls Gemini with tools=[{'google_search': {}}] on cache miss,
    writes verified classification into VehicleModel.grounding_meta, and uses cache on repeat calls.
    """
    from app.extraction.vehicle_grounding_service import resolve_vehicle_level2_grounding

    brand = VehicleBrand(id=new_id(), name="HONDA", aliases=["Honda"], status="active")
    model = VehicleModel(
        id=new_id(),
        brand_id=brand.id,
        name="CR-V",
        aliases=["CRV", "HONDA CR-V"],
        status="active",
    )
    hermetic_db.add_all([brand, model])
    hermetic_db.commit()

    captured_payloads = []

    def fake_search_caller(*, query_prompt: str, response_schema: dict, **kwargs):
        captured_payloads.append({"prompt": query_prompt, "schema": response_schema, **kwargs})
        return {
            "vehicle_category": "NonSaloonCar",
            "powertrain": "ICE",
            "malaysian_tariff_class": "Private Car",
            "product_tier_confirmed": "auto365 Comprehensive Plus",
            "confidence": 0.96,
            "citations": ["https://www.honda.com.my/model/cr-v"],
            "reasoning": "Honda CR-V 2.4L 2354cc is a passenger SUV (NonSaloonCar), ICE petrol engine.",
        }

    # First call: cache miss -> calls online search and persists grounding metadata
    result_live = resolve_vehicle_level2_grounding(
        db=hermetic_db,
        car_brand="HONDA",
        car_model="CR-V",
        engine_cc="2354 CC",
        vehicle_class="PRIVATE CAR EX GOODS",
        product_name="auto365 Comprehensive Plus",
        extracted_vehicle_type="Lorry",
        search_fn=fake_search_caller,
    )
    assert len(captured_payloads) == 1
    assert result_live["vehicle_type"] == "NonSaloonCar"
    assert result_live["powertrain"] == "ICE"
    assert result_live["tariff_class"] == "Private Car"
    assert result_live["source"] == "online_google_search"

    # Second call: DB cache hit -> zero external API calls
    result_cached = resolve_vehicle_level2_grounding(
        db=hermetic_db,
        car_brand="HONDA",
        car_model="CR-V",
        engine_cc="2354 CC",
        vehicle_class="PRIVATE CAR EX GOODS",
        product_name="auto365 Comprehensive Plus",
        extracted_vehicle_type="Car",
        search_fn=fake_search_caller,
    )
    assert len(captured_payloads) == 1  # Still 1!
    assert result_cached["vehicle_type"] == "NonSaloonCar"
    assert result_cached["source"] == "vehicle_model_cache"


def test_3eye_grounding_pipeline_pins_ice_catalog_and_flags_ev_mismatch(hermetic_db: Session):
    """Worker/rescan shared 3-Eye gate corrects false Lorry -> NonSaloonCar, restores road tax flag,
    pins active ICE catalog, persists verdict on ExtractionRecord, and catches EV catalog leaks.
    """
    from app.extraction.vehicle_grounding_service import (
        finalize_catalog_and_3eye_gate,
        run_level2_grounding_gate,
    )
    from app.extraction.visual_referee import audit_extraction_3_eye_consensus
    from app.models.tables import ExtractionRecord

    amgen = InsuranceCompany(id=new_id(), slug="amassurance", name="AmAssurance", category="Motor", status="active")
    seg_priv = Segment(id=new_id(), segment_key="private", name="Private", status="active")
    cat_car = VehicleCategory(id=new_id(), category_key="car", name="Car", status="active")
    cov_comp = CoverageType(id=new_id(), coverage_key="comprehensive", name="Comprehensive", status="active")
    p_car = InsuranceProduct(id=new_id(), company_id=amgen.id, product_key="amg-car", name="Private Car Comprehensive", status="active")
    cat_plus = BenefitCatalog(
        id=new_id(),
        company_id=amgen.id,
        product_id=p_car.id,
        segment_id=seg_priv.id,
        vehicle_category_id=cat_car.id,
        coverage_type_id=cov_comp.id,
        engine_type="ice",
        name="auto365 Comprehensive Plus",
        status="published",
    )
    rev_plus = BenefitCatalogRevision(id=new_id(), catalog_id=cat_plus.id, revision_number=1, state="published", content_hash="amg-plus-m1")

    draft = QuotationDraft(
        id=new_id(),
        uploaded_file_id=new_id(),
        owner_id=new_id(),
        company_id=amgen.id,
        fields={},
        scalar_decisions={},
        warnings=[],
    )
    record = ExtractionRecord(
        id=new_id(),
        uploaded_file_id=draft.uploaded_file_id,
        raw_text="auto365 Comprehensive Plus HONDA CR-V 2354 CC",
        ocr_text="",
        words=[],
        blocks=[],
        tables=[],
        images=[],
        regions=[],
        candidates={},
        benefit_lines=[],
        company_resolution={"company_id": amgen.id},
        warnings=[],
        reading_quality="ready",
    )
    hermetic_db.add_all([amgen, seg_priv, cat_car, cov_comp, p_car, cat_plus, rev_plus, draft, record])
    hermetic_db.flush()

    raw_fields = {
        "customer_name": {"value": "HOW YEOK CHIAN", "status": "ready"},
        "car_brand": {"value": "HONDA", "status": "ready"},
        "car_model": {"value": "CR-V", "status": "ready"},
        "engine_cc": {"value": "2354 CC", "status": "ready"},
        "vehicle_class": {"value": "PRIVATE CAR EX GOODS", "status": "ready"},
        "vehicle_type": {"value": "Lorry", "status": "ready"},
        "include_road_tax": {"value": "false", "status": "ready"},
        "include_runner_fee": {"value": "false", "status": "ready"},
        "coverage_type": {"value": "Comprehensive", "status": "ready"},
        "product_name": {"value": "auto365 Comprehensive Plus", "status": "ready"},
    }

    def fake_search(**kwargs):
        return {
            "vehicle_category": "NonSaloonCar",
            "powertrain": "ICE",
            "malaysian_tariff_class": "Private Car",
            "product_tier_confirmed": "auto365 Comprehensive Plus",
            "confidence": 0.98,
            "citations": ["https://www.honda.com.my/model/cr-v"],
            "reasoning": "Honda CR-V 2354 CC is a Private Passenger SUV.",
        }

    reconciled, grounding, _notices = run_level2_grounding_gate(
        db=hermetic_db,
        fields=raw_fields,
        raw_text="QUOTATION auto365 Comprehensive Plus HONDA CR-V 2354 CC PRIVATE CAR EX GOODS",
        search_fn=fake_search,
    )
    assert reconciled["vehicle_type"]["value"] == "NonSaloonCar"
    assert reconciled["include_road_tax"]["value"] == "true"

    draft.fields = reconciled
    cat_ctx, three_eye = finalize_catalog_and_3eye_gate(
        db=hermetic_db,
        draft=draft,
        grounding=grounding,
        raw_text="auto365 Comprehensive Plus HONDA CR-V",
        record=record,
        company_resolution=record.company_resolution,
    )
    assert cat_ctx["catalog_revision_id"] == rev_plus.id
    assert three_eye["status"] == "PASS"
    assert record.company_resolution["level2_grounding"]["source"] == "online_google_search"
    assert record.company_resolution["three_eye_consensus"]["audit_seal"] == "PASS"

    # Negative check: Eye 2/3 must catch an ICE car mistakenly pinned to an EV catalog or TPFT -> Comprehensive
    bad_verdict = audit_extraction_3_eye_consensus(
        fields={"vehicle_type": {"value": "NonSaloonCar"}, "coverage_type": {"value": "Third Party"}},
        grounding={"vehicle_type": "NonSaloonCar", "powertrain": "ICE"},
        catalog_context={"catalog_name": "AmAssurance Private Car Comprehensive (EV)"},
    )
    assert bad_verdict["status"] == "FLAGGED"
    assert len(bad_verdict["discrepancies"]) >= 2


def test_resolve_tenure_coverage_label_preserves_third_party_and_tpft():
    """Comparison matrix summary coverage label must distinguish Third Party / TPFT from Comprehensive."""
    from app.services.marketing_comparison_service import _resolve_tenure_coverage_label

    assert _resolve_tenure_coverage_label([{"coverage_type": "Third Party", "is_recommended": True}], [], is_commercial=True).startswith(
        "Commercial Vehicle Third Party"
    )
    assert _resolve_tenure_coverage_label([{"coverage_type": "Third Party Fire & Theft", "is_recommended": True}], [], is_commercial=False).startswith(
        "Third Party Fire & Theft"
    )
    assert _resolve_tenure_coverage_label([{"coverage_type": "Comprehensive", "is_recommended": True}], [], is_commercial=False).startswith(
        "Comprehensive"
    )


def test_extract_vehicle_motor_premium_does_not_double_count_road_tax(monkeypatch):
    """Comparison motor_premium must reflect underwriter payable, excluding roadtax rolled into draft total_amount."""
    from app.services.marketing_comparison.benefits_extractor import _extract_vehicle_motor_premium

    # Case 1: legacy rescan draft where total_amount rolled in roadtax (1883.65 + 723.20 = 2606.85)
    rescan_rolled_fields = {
        "gross_premium": {"value": "1,734.85", "status": "ready"},
        "service_tax": {"value": "138.79", "status": "ready"},
        "roadtax": {"value": "723.20", "status": "ready"},
        "service_fee": {"value": "0.00", "status": "manual_override"},
        "include_road_tax": {"value": "true", "status": "ready"},
        "include_runner_fee": {"value": "true", "status": "ready"},
        "total_amount": {"value": "2606.85", "status": "ready"},
    }
    assert _extract_vehicle_motor_premium(rescan_rolled_fields) == 1883.65

    # Case 2: fresh rescan stores raw underwriter total_payable alongside customer grand total_amount
    explicit_payable_fields = {
        **rescan_rolled_fields,
        "total_payable": {"value": "1883.65", "status": "ready"},
    }
    assert _extract_vehicle_motor_premium(explicit_payable_fields) == 1883.65

    # Case 3: direct underwriter PDF extraction where roadtax is not rolled into total_amount
    direct_uw_fields = {
        "gross_premium": {"value": "1,734.85", "status": "ready"},
        "service_tax": {"value": "138.79", "status": "ready"},
        "roadtax": {"value": "723.20", "status": "ready"},
        "include_road_tax": {"value": "true", "status": "ready"},
        "total_amount": {"value": "1883.65", "status": "ready"},
    }
    assert _extract_vehicle_motor_premium(direct_uw_fields) == 1883.65


def test_call_gemini_grounded_search_rotates_slots_after_429(monkeypatch):
    """Level-2 google_search must fall back to healthy slots when an earlier slot returns HTTP 429."""
    from types import SimpleNamespace
    import httpx
    from app.extraction import gemini_extractor

    gemini_extractor._GROUNDING_COOLDOWN_UNTIL = 0.0
    recorded_failures: list[str] = []
    recorded_successes: list[str] = []
    slots = [
        ("key-a", "gemini-3.1-flash-lite", "slot-1"),
        ("key-b", "gemini-3.5-flash-lite", "slot-2"),
    ]

    class FakePool:
        def acquire_parallel_slot(self, batch_item_index=0, requested_model=None):
            return slots[batch_item_index % len(slots)]

        def record_slot_failure(self, slot_id, status_code, err_msg, latency_ms=0):
            recorded_failures.append(f"{slot_id}:{status_code}")

        def record_slot_success(self, slot_id, prompt_tokens=0, candidate_tokens=0, total_tokens=0, latency_ms=0):
            recorded_successes.append(slot_id)

        def record_failure(self, *args, **kwargs):
            pass

        def record_success(self, *args, **kwargs):
            pass

    monkeypatch.setattr(gemini_extractor, "get_key_pool", lambda: FakePool())

    calls: list[str] = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json=None):
            calls.append(url)
            if "key-a" in url:
                return SimpleNamespace(status_code=429, text='{"error":{"code":429,"message":"quota exceeded"}}')
            return SimpleNamespace(
                status_code=200,
                text="",
                json=lambda: {
                    "candidates": [
                        {
                            "content": {"parts": [{"text": '{"vehicle_category":"NonSaloonCar","powertrain":"ICE","confidence":0.97}'}]},
                            "groundingMetadata": {"groundingChunks": [{"web": {"uri": "https://honda.com.my/cr-v"}}]},
                        }
                    ],
                    "usageMetadata": {"promptTokenCount": 50, "candidatesTokenCount": 20, "totalTokenCount": 70},
                },
            )

    monkeypatch.setattr(httpx, "Client", FakeClient)

    result = gemini_extractor.call_gemini_grounded_search(
        query_prompt="Honda CR-V 2354 CC",
        response_schema={"type": "object", "properties": {"vehicle_category": {"type": "string"}}},
        batch_item_index=0,
    )
    assert result is not None
    assert result["vehicle_category"] == "NonSaloonCar"
    assert len(calls) == 2
    assert recorded_failures == ["slot-1:429"]
    assert recorded_successes == ["slot-2"]


