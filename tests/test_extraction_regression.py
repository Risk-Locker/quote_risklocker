import sys
from pathlib import Path
from typing import Any

import fitz
import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FIXTURES = ROOT / "tests" / "fixtures"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.extraction.candidate_finder import find_candidates
from app.extraction.draft_mapper import build_draft
from app.extraction.orchestrator import ExtractionOrchestrator


COMPANY_RECORDS = [
    {"name": "AmGen", "source_template_category": "Amgen / AmAssurance / Kurnia-style", "aliases": ["amgen", "amgeneral"]},
    {"name": "Etiqa Takaful", "source_template_category": "Etiqa Takaful", "aliases": ["etiqa"]},
    {"name": "Lonpac", "source_template_category": "Other / Unknown", "aliases": ["lonpac"]},
    {"name": "Kurnia", "source_template_category": "Amgen / AmAssurance / Kurnia-style", "aliases": ["kurnia"]},
]


def extract_fixture(name: str, source_filename: str) -> dict:
    text = (FIXTURES / name).read_text(encoding="utf-8")
    candidates = find_candidates(
        text,
        [{"page": 1, "text": text}],
        source_filename=source_filename,
        db_companies=COMPANY_RECORDS,
    )
    fields, warnings, status = build_draft(candidates)
    return {"fields": fields, "warnings": warnings, "status": status}


def field_value(fields: dict, key: str) -> str:
    return str(fields[key]["value"])


def test_amgen_fixture_extracts_visible_motor_values():
    fields = extract_fixture("amgen_motor.txt", "20260522_TST1234_Quotation_Amgen.pdf")["fields"]
    assert field_value(fields, "customer_name") == "TEST CUSTOMER"
    assert field_value(fields, "vehicle_no") == "TST1234"
    assert field_value(fields, "car_brand") == "PROTON"
    assert "WAJA ENHANCED" in field_value(fields, "car_model")
    assert field_value(fields, "vehicle_year") == "2005"
    assert field_value(fields, "cover_start_date") == "2026-07-09"
    assert field_value(fields, "cover_end_date") == "2027-07-08"
    assert field_value(fields, "coverage_amount") == "10000.00"
    assert field_value(fields, "ncd_percent") == "45.00"
    assert field_value(fields, "total_amount") == "717.02"
    assert field_value(fields, "insurance_company") == "AmGen"
    assert "Windscreen Damage" in field_value(fields, "optional_covers")


def test_etiqa_fixture_extracts_semantic_values():
    fields = extract_fixture("etiqa_motor.txt", "20260330_TST5678_Quotation_ETIQA.pdf")["fields"]
    assert field_value(fields, "customer_name") == "ALICE TESTER"
    assert field_value(fields, "vehicle_no") == "TST5678"
    assert field_value(fields, "car_brand") == "PERODUA"
    assert field_value(fields, "car_model") == "ATIVA 1.0L TURBO AV"
    assert field_value(fields, "vehicle_year") == "2023"
    assert field_value(fields, "cover_start_date") == "2026-05-16"
    assert field_value(fields, "cover_end_date") == "2027-05-15"
    assert field_value(fields, "coverage_type") == "Comprehensive"
    assert field_value(fields, "coverage_amount") == "57000.00"
    assert field_value(fields, "ncd_percent") == "55.00"
    assert field_value(fields, "total_amount") == "1242.62"


@pytest.mark.parametrize(
    ("filename", "company"),
    [
        ("20260522_TST1234_Quotation_Amgen.pdf", "AmGen"),
        ("20260522_TST1234_Quotation_Etiqa_REF.pdf", "Etiqa Takaful"),
        ("20260603_TST1234_Quotation_Lonpac.pdf", "Lonpac"),
        ("20260707_TST339_Quotation_Kurnia.pdf", "Kurnia"),
    ],
)
def test_filename_company_detection_is_specific(filename: str, company: str):
    fields, _, _ = build_draft(find_candidates(
        "MOTOR QUOTATION",
        [{"page": 1, "text": "MOTOR QUOTATION"}],
        source_filename=filename,
        db_companies=COMPANY_RECORDS,
    ))
    assert field_value(fields, "insurance_company") == company


def test_native_pdf_extraction_uses_real_text_layer(tmp_path):
    path = tmp_path / "quotation.pdf"
    document: Any = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "MOTOR QUOTATION TEST CUSTOMER TST1234")
    document.save(path)
    document.close()

    result = ExtractionOrchestrator().extract_file(path)
    assert "MOTOR QUOTATION" in result["full_record"]["raw_text"]
    assert "PyMuPDF native text" in result["full_record"]["method_summary"]


def test_review_ui_contains_pdf_text_and_template_workflow():
    review_page = (ROOT / "frontend" / "src" / "app" / "review" / "[id]" / "page.tsx").read_text(encoding="utf-8")
    batch_page = (ROOT / "frontend" / "src" / "app" / "batches" / "[id]" / "page.tsx").read_text(encoding="utf-8")
    assert "Review / Edit" in batch_page
    assert "<iframe" in review_page
    assert "Extracted Text" in review_page
    assert "Template:" in review_page
    assert "Found near" not in review_page
    assert "confidence" not in review_page.lower()
    assert "regex" not in review_page.lower().replace("regexp", "")  # RegExp constructor is fine


def test_byte_fallback_is_not_used_for_draft_candidates():
    native_pdf = (ROOT / "backend" / "app" / "extraction" / "native_pdf.py").read_text(encoding="utf-8")
    assert "fallback byte text" not in native_pdf


def test_quotation_final_price_and_insurance_premium_netting():
    from app.extraction.candidate_finder import CandidateValue
    from app.extraction.draft_mapper import build_draft

    candidates = {
        "customer_name": [CandidateValue(page=1, field="customer_name", score=0.99, value="HING GUAN SENG", evidence="", warnings=[], source_method="test")],
        "vehicle_no": [CandidateValue(page=1, field="vehicle_no", score=0.99, value="JXA8233", evidence="", warnings=[], source_method="test")],
        "insurance_company": [CandidateValue(page=1, field="insurance_company", score=0.99, value="AmAssurance", evidence="", warnings=[], source_method="test")],
        "total_amount": [CandidateValue(page=1, field="total_amount", score=0.99, value="2,922.85", evidence="", warnings=[], source_method="test")],
        "premium": [CandidateValue(page=1, field="premium", score=0.99, value="2,922.85", evidence="", warnings=[], source_method="test")],
    }
    benefit_lines = [
        {"raw_label": "Windscreen", "premium_cost": "600.00"},
        {"raw_label": "LLTP", "premium_cost": "71.85"},
        {"raw_label": "LLOP", "premium_cost": "7.50"},
        {"raw_label": "Private Car 365 Plan 2", "premium_cost": "166.00"},
    ]
    fields, _, _ = build_draft(candidates, benefit_lines=benefit_lines)
    # Total Payable is preserved as Final Price
    assert fields["total_amount"]["value"] == "2922.85"
    # Insurance Premium is Final Price - Extras (2922.85 - 845.35 = 2077.50)
    assert fields["premium"]["value"] == "2077.50"
    # Unmentioned roadtax/runner fee are not auto-injected
    assert fields["roadtax"]["value"] == ""
    assert fields["service_fee"]["value"] == ""


def test_adjusted_total_text_reactive_and_no_double_count():
    from app.rendering.render_context import adjusted_total_text

    fields = {
        "premium": {"value": "2077.50"},
        "total_amount": {"value": "2922.85"},
        "roadtax": {"value": ""},
        "service_fee": {"value": ""},
    }
    extras = [
        {"price": {"amount": 600.0}},
        {"price": {"amount": 71.85}},
        {"price": {"amount": 7.5}},
        {"price": {"amount": 166.0}},
    ]
    # Sum is exactly 2,922.85 (no double-counting)
    assert adjusted_total_text(fields, extras) == "2,922.85"

    # Adding an add-on reactively increases only the final price
    extras_with_addon = extras + [{"price": {"amount": 50.0}}]
    assert adjusted_total_text(fields, extras_with_addon) == "2,972.85"

