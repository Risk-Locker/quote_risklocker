import pytest
from decimal import Decimal
from app.extraction.types import CandidateValue
from app.extraction.candidate_finder import (
    find_candidates,
    _add_2d_spatial_candidates,
    _to_money_flt,
)
from app.extraction.draft_mapper import build_draft
from app.services.marketing_comparison_service import (
    _extract_exact_basic_figure,
    _extract_vehicle_basic_premium,
    calculate_exact_rate,
)


def test_2d_spatial_alignment_extracts_separated_basic_premium():
    """
    In tabular/columnar PDF layouts like QBE, label 'Basic Premium' and
    value 'RM 3,060.07' appear on the same horizontal line (top ~ 305.95)
    but separated horizontally by a wide gap.
    """
    words = [
        {"text": "Basic", "x0": 50.0, "top": 305.95, "x1": 80.0, "bottom": 316.0, "page": 1},
        {"text": "Premium", "x0": 85.0, "top": 305.95, "x1": 130.0, "bottom": 316.0, "page": 1},
        {"text": "Premium", "x0": 140.0, "top": 305.95, "x1": 180.0, "bottom": 316.0, "page": 1},
        {"text": "Asas", "x0": 185.0, "top": 305.95, "x1": 210.0, "bottom": 316.0, "page": 1},
        {"text": "RM", "x0": 450.0, "top": 305.99, "x1": 468.0, "bottom": 316.0, "page": 1},
        {"text": "3,060.07", "x0": 475.0, "top": 305.99, "x1": 530.0, "bottom": 316.0, "page": 1},
    ]

    results: dict[str, list[CandidateValue]] = {}
    page_text = [{"page": 1, "text": "Basic Premium Premium Asas RM 3,060.07"}]
    _add_2d_spatial_candidates(words, results, page_text)

    assert "basic_premium_vehicle" in results
    assert len(results["basic_premium_vehicle"]) > 0
    best = results["basic_premium_vehicle"][0]
    assert best.value == "3060.07"
    assert "basic premium" in best.evidence.lower()


def test_trailer_and_ncd_date_line_does_not_extract_25():
    """
    Quotation line: 'Trailer Premium Premium Treler NCB (25.00%) DTT NCB Effective Date (25-02-2026)'
    must NOT extract 25.00 as basic_premium_vehicle.
    """
    words = [
        {"text": "Trailer", "x0": 50.0, "top": 340.0, "x1": 90.0, "bottom": 350.0, "page": 1},
        {"text": "Premium", "x0": 95.0, "top": 340.0, "x1": 140.0, "bottom": 350.0, "page": 1},
        {"text": "NCB", "x0": 150.0, "top": 340.0, "x1": 170.0, "bottom": 350.0, "page": 1},
        {"text": "(25.00%)", "x0": 175.0, "top": 340.0, "x1": 215.0, "bottom": 350.0, "page": 1},
        {"text": "(25-02-2026)", "x0": 220.0, "top": 340.0, "x1": 280.0, "bottom": 350.0, "page": 1},
    ]
    raw_text = "Trailer Premium Premium Treler NCB (25.00%) DTT NCB Effective Date (25-02-2026) Tarikh Berkuatkuasa DTT"
    page_text = [{"page": 1, "text": raw_text}]

    candidates = find_candidates(raw_text, page_text, words=words)
    bp_cands = candidates.get("basic_premium_vehicle", [])
    extracted_values = [c.value for c in bp_cands]
    assert "25.00" not in extracted_values
    assert "25" not in extracted_values


def test_underwriting_sanity_recheck_and_bnm_derivation_in_draft_mapper():
    """
    If basic_premium_vehicle candidate is 25.00 while sum insured is RM 96,000,
    draft mapper must reject 25.00, apply BNM formula derivation:
    (Gross 3198.30 - Extras 903.25) / (1 - 0.25) = RM 3,060.07,
    and calculate rate as 0.031876 (3.1876%).
    """
    candidates = {
        "coverage_amount": [CandidateValue(field="coverage_amount", value="96000.00", score=0.9, source_method="regex")],
        "gross_premium": [CandidateValue(field="gross_premium", value="3198.30", score=0.9, source_method="regex")],
        "ncd_percent": [CandidateValue(field="ncd_percent", value="25.00", score=0.9, source_method="regex")],
        "basic_premium_vehicle": [CandidateValue(field="basic_premium_vehicle", value="25.00", score=0.6, source_method="table")],
    }
    benefit_lines = [
        {"benefit_name": "Windscreen", "premium_cost": "600.00"},
        {"benefit_name": "Special Perils", "premium_cost": "303.25"},
    ]

    fields, warnings, status = build_draft(candidates, benefit_lines=benefit_lines)

    bp_field = fields.get("basic_premium_vehicle", {})
    rate_field = fields.get("rate", {})

    assert bp_field.get("value") == "3060.07", f"Expected 3060.07 but got {bp_field.get('value')}"
    assert rate_field.get("value") == "0.031876", f"Expected 0.031876 but got {rate_field.get('value')}"


def test_comparison_service_exact_basic_figure_rejection_and_math():
    """
    Verify marketing comparison service extracts 3060.07 and calculates 0.031876 rate
    even if fields contain legacy corrupt 25.00 basic_premium_vehicle.
    """
    f_obj = {
        "basic_premium_vehicle": {"value": "25.00"},
        "basic_premium": {"value": 3060.07},
        "coverage_amount": {"value": "96000.00"},
        "gross_premium": {"value": "3198.30"},
        "ncd_percent": {"value": "25.00"},
    }

    bp, label = _extract_exact_basic_figure(f_obj, "QBE")
    assert bp == 3060.07
    assert label == "Basic Premium"

    rate_str, rate_num = calculate_exact_rate(bp, 96000.0)
    assert rate_str == "0.031876"
    assert abs(rate_num - 0.031876) < 1e-6
