"""Regression tests for AmAssurance vs Kurnia detection, mirror-field Needs Review hygiene,
Detected Benefits cleanup (auto365 package vs Private Car 365 Plan 1-4), and Level-2 grounding fast-path.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.extraction.benefit_lines import extract_benefit_lines, is_spurious_benefit_line
from app.extraction.candidate_finder import find_candidates
from app.extraction.company_resolution import resolve_company
from app.extraction.conflict_detector import select_field
from app.extraction.draft_mapper import build_draft
from app.extraction.orchestrator import ExtractionOrchestrator
from app.extraction.types import CandidateValue
from app.extraction.vehicle_grounding_service import resolve_vehicle_level2_grounding
from app.models.tables import (
    Base,
    BenefitConcept,
    CustomerAccount,
    ExtractionRecord,
    InsuranceTenure,
    QuotationDraft,
    TrackedVehicle,
    UploadedFile,
    new_id,
)
from app.services.tenure_identity_sync_service import _update_single_draft_fields
from app.services.workspace_common import _field_summary
from app.services.workspace_snapshot_service import _workspace_extracted_benefits_section


COMPANIES = [
    {
        "company_id": "am-id",
        "name": "AmAssurance",
        "source_template_category": "Amgen / AmAssurance / Kurnia-style",
        "aliases": [
            "AmAssurance",
            "amassurance",
            "AmGen",
            "AmGeneral",
            "AmGeneral Insurance",
            "auto365",
            "www.amassurance.com.my",
        ],
    },
    {
        "company_id": "kurnia-id",
        "name": "Kurnia",
        "source_template_category": "Amgen / AmAssurance / Kurnia-style",
        "aliases": [
            "Kurnia",
            "Kurnia Insurans",
            "Kurnia Insurance",
            "Kurnia Insurans (Malaysia) Berhad",
            "www.kurnia.com",
            "kurnia.com",
            "Kurnia Auto Assist",
        ],
    },
]


def test_amassurance_with_kurnia_one_touch_footer_and_pdpa_resolves_to_amassurance():
    amgen_text = (
        "Liberty General Insurance Berhad\n"
        "auto365 Comprehensive Premier\n"
        "Insured Name: YAP KEE MENG\n"
        "Vehicle No: PQP9933\n"
        "Visit www.amassurance.com.my for policy info.\n"
        "Download the Kurnia One Touch Mobile App today!\n"
        "Privacy Notice: customer@libertyinsurance.com.my or customer@amassurance.com.my or customer@kurnia.com\n"
        "https://www.amassurance.com.my/content/privacy-policy-documents\n"
        "https://www.kurnia.com/privacy-policy-documents\n"
    )
    # 1. Direct resolution without filename
    resolved = resolve_company(amgen_text, COMPANIES)
    assert resolved["status"] == "matched"
    assert resolved["display_name"] == "AmAssurance"

    # 2. Full candidate pipeline with _Amgen filename
    cands = find_candidates(
        amgen_text,
        [{"page": 1, "text": amgen_text}],
        source_filename="20260928_PQP9933_Quotation_Amgen.pdf",
        db_companies=COMPANIES,
    )
    fields, _, _ = build_draft(cands)
    assert fields["insurance_company"]["value"] == "AmAssurance"
    assert fields["insurance_company"]["status"] == "ready"


def test_real_kurnia_covernote_with_amgen_agency_code_resolves_to_kurnia():
    page1 = (
        "COMMERCIAL VEHICLE SCHEDULE / JADUAL KENDERAAN PERDAGANGAN\n"
        "Issued By / Dikeluarkan Oleh : AMGEN J1 RISK LOCKER 2 MANAGEMENT\n"
        "Vehicle No: JQY5673\n"
        "Liberty General Insurance Berhad\n"
    )
    page4 = (
        "Website: www.kurnia.com\n"
        "Kurnia Insurans\n"
        "customer@libertyinsurance.com.my or customer@amassurance.com.my or customer@kurnia.com\n"
        "https://www.amassurance.com.my/content/privacy-policy-documents\n"
        "https://www.kurnia.com/privacy-policy-documents\n"
    )
    cands = find_candidates(
        f"{page1}\n{page4}",
        [{"page": 1, "text": page1}, {"page": 4, "text": page4}],
        source_filename="20261111_JQY5673_CoverNote_Kurnia.pdf",
        db_companies=COMPANIES,
    )
    fields, _, _ = build_draft(cands)
    assert fields["insurance_company"]["value"] == "Kurnia"
    assert fields["insurance_company"]["status"] == "ready"
    assert cands["insurance_company"][0].value == "Kurnia"


def test_conflict_detector_trusts_gemini_vision_for_liberty_group_text_ambiguity():
    cands = [
        CandidateValue(
            field="insurance_company",
            value="Kurnia",
            source_method="database_company_text",
            score=0.95,
            page=1,
            evidence="Kurnia",
        ),
        CandidateValue(
            field="insurance_company",
            value="AmAssurance",
            source_method="gemini_vision",
            score=0.88,
            page=1,
            evidence="Gemini multimodal extraction: AmAssurance",
        ),
    ]
    sel = select_field("insurance_company", cands)
    assert sel.value == "AmAssurance"
    assert sel.status == "ready"


def test_update_single_draft_fields_does_not_create_mirror_needs_review_fields():
    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=new_id(),
        vehicle_no="PQP9933",
        customer_name="YAP KEE MENG",
        ncd_percentage=55.0,
        road_tax=367.60,
        runner_fee=20.00,
    )
    cust = CustomerAccount(id=new_id(), canonical_name="YAP KEE MENG", id_number="890316016517", id_type="nric")
    tv = TrackedVehicle(
        id=new_id(),
        vehicle_no="PQP9933",
        car_brand="VOLVO",
        car_model="Volvo XC40 B5 Ultimate",
        engine_cc="1969 CC",
        manufacture_year=2022,
        chassis_no="PNVXZL5A8P5944373",
        engine_no="B420T107892557",
    )
    initial_fields = {
        "customer_name": {"value": "YAP KEE MENG", "status": "ready"},
        "ic_or_brn": {"value": "890316016517", "status": "ready"},
        "vehicle_no": {"value": "PQP9933", "status": "ready"},
        "car_brand": {"value": "VOLVO", "status": "ready"},
        "car_model": {"value": "Volvo XC40 B5 Ultimate", "status": "manual_override"},
        "premium": {"value": "3985.96", "status": "ready"},
    }
    updated = _update_single_draft_fields(
        initial_fields,
        tenure=tenure,
        cust=cust,
        tv=tv,
        vehicle_type="NonSaloonCar",
        powertrain="ICE",
        dt_start=datetime(2026, 12, 1, tzinfo=timezone.utc),
        dt_end=datetime(2027, 11, 30, tzinfo=timezone.utc),
        eff_rt=Decimal("367.60"),
        eff_rf=Decimal("20.00"),
    )
    for mirror in (
        "make", "ic_no", "nric_no", "id_number", "customer_ic_no",
        "veh_reg_no", "registration_no", "client_name", "insured_name",
        "policyholder_name", "engine_number", "chassis_number",
        "vehicle_model",
    ):
        assert mirror not in updated, f"Mirror key {mirror!r} should not be created"

    draft_stub = SimpleNamespace(fields=updated, scalar_decisions={}, uploaded_file=None)
    summary = _field_summary(draft_stub, "RL260001311")
    check_needed = [k for k, v in summary.items() if v.get("status") == "check_needed"]
    assert check_needed == []


def test_benefit_hygiene_rejects_noise_and_separates_auto365_from_private_car_365():
    # Reject Image 3 noise + base package title
    for junk in (
        "15,000.00T",
        "RM 15,000.00T",
        "ANY AUTHORISED DRIVER",
        "Provisional (P) or Learner (L) driver’s licence / unnamed driver. / Ekses wajib",
        "Replacing Cover Note No./",
        "auto365 Comprehensive Premier",
        "auto365 Comprehensive Plus",
        "auto365 Comprehensive Lite",
    ):
        assert is_spurious_benefit_line(junk) is True, junk

    # Preserve genuine Private Car 365 Plan 1..4 add-on benefits
    for valid in (
        "Private Car 365 Plan 1",
        "Private Car 365 Plan 2",
        "Private Car 365 Plan 3",
        "Private Car 365 Plan 4",
        "Legal Liability To Passengers",
        "Windscreen Damage",
        "ALL DRIVERS",
    ):
        assert is_spurious_benefit_line(valid) is False, valid


def test_workspace_extracted_benefits_section_cleans_legacy_noise_and_dedupes_concepts():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db: Session = factory()
    try:
        c_pc365 = BenefitConcept(id=new_id(), concept_key="private-car-365", label="Private Car 365", status="active")
        c_llp = BenefitConcept(id=new_id(), concept_key="legal-liability-to-passengers", label="Legal Liability to Passengers (LLP)", status="active")
        c_ws = BenefitConcept(id=new_id(), concept_key="windscreen", label="Windscreen Coverage", status="active")
        db.add_all([c_pc365, c_llp, c_ws])
        uf = UploadedFile(id=new_id(), batch_id=new_id(), owner_id=new_id(), original_filename="amgen.pdf", content_type="application/pdf", storage_path="tmp/a.pdf")
        rec = ExtractionRecord(
            id=new_id(),
            uploaded_file_id=uf.id,
            raw_text="",
            ocr_text="",
            page_text=[],
            words=[],
            blocks=[],
            tables=[],
            images=[],
            regions=[],
            candidates={"product_tier": [{"value": "auto365 Comprehensive Premier"}]},
            benefit_lines=[
                {"line_id": "gemini_1", "raw_label": "Private Car 365 Plan 2", "premium_cost": "130.00", "coverage_limit": "", "candidate_mappings": [{"concept_id": c_pc365.id, "concept_key": "private-car-365"}]},
                {"line_id": "gemini_2", "raw_label": "Legal Liability to Passengers (LLP)", "premium_cost": "41.85", "coverage_limit": "", "candidate_mappings": [{"concept_id": c_llp.id, "concept_key": "legal-liability-to-passengers"}]},
                {"line_id": "gemini_3", "raw_label": "Windscreen Damage", "premium_cost": "2,250.00", "coverage_limit": "15,000.00", "candidate_mappings": [{"concept_id": c_ws.id, "concept_key": "windscreen"}]},
                {"line_id": "det_4", "raw_label": "Legal Liability To Passengers / Liabiliti Dari Segi T", "premium_cost": None, "coverage_limit": None, "candidate_mappings": [{"concept_id": c_llp.id, "concept_key": "legal-liability-to-passengers"}]},
                {"line_id": "det_5", "raw_label": "15,000.00T", "premium_cost": "15000.00", "coverage_limit": None, "candidate_mappings": []},
                {"line_id": "det_6", "raw_label": "ANY AUTHORISED DRIVER", "premium_cost": None, "coverage_limit": None, "candidate_mappings": []},
                {"line_id": "det_7", "raw_label": "Provisional (P) or Learner (L) driver’s licence / unnamed driver. / Ekses wajib", "premium_cost": None, "coverage_limit": None, "candidate_mappings": []},
                {"line_id": "det_8", "raw_label": "auto365 Comprehensive Premier", "premium_cost": None, "coverage_limit": None, "candidate_mappings": [{"concept_id": c_pc365.id, "concept_key": "private-car-365"}]},
            ],
            company_resolution={},
            warnings=[],
            reading_quality="ready",
        )
        draft = QuotationDraft(id=new_id(), uploaded_file_id=uf.id, owner_id=uf.owner_id, fields={}, scalar_decisions={}, warnings=[])
        db.add_all([rec, draft])
        db.flush()

        sec = _workspace_extracted_benefits_section(db, draft, [], [])
        labels = [e["label"] for e in sec["extras"]]
        assert labels == [
            "Private Car 365 Plan 2",
            "Legal Liability to Passengers (LLP)",
            "Windscreen Damage",
        ]
        assert sec["total_optional_cover_amount"] == "2,421.85"
        assert sec["detected_package"]["name"] == "auto365 Comprehensive Premier"
    finally:
        db.close()


def test_level2_grounding_fast_path_skips_live_search_on_unambiguous_vehicles(monkeypatch):
    def explode(**kwargs):
        raise AssertionError("Should not invoke Google Search on unambiguous vehicles")

    monkeypatch.setattr("app.extraction.gemini_extractor.call_gemini_grounded_search", explode)

    res_car = resolve_vehicle_level2_grounding(
        db=None,
        car_brand="VOLVO",
        car_model="Volvo XC40 B5 Ultimate",
        engine_cc="1969 CC",
        vehicle_class="PRIVATE CAR EX GOODS",
        product_name="auto365 Comprehensive Premier",
        extracted_vehicle_type="NonSaloonCar",
    )
    assert res_car["source"] == "deterministic_clear"
    assert res_car["vehicle_type"] == "NonSaloonCar"
    assert res_car["powertrain"] == "ICE"
    assert res_car["tariff_class"] == "Private Car"

    res_lorry = resolve_vehicle_level2_grounding(
        db=None,
        car_brand="HINO",
        car_model="HINO WU302R",
        engine_cc="3000 KG",
        vehicle_class="'C' PERMIT GOODS VEHICLE",
        product_name="Commercial Vehicle",
        extracted_vehicle_type="Lorry",
    )
    assert res_lorry["source"] == "deterministic_clear"
    assert res_lorry["vehicle_type"] == "Lorry"
    assert res_lorry["tariff_class"] == "Commercial Vehicle"
