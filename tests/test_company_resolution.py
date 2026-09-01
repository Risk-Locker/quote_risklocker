"""Alias-aware insurance company resolution (Part A: AMGEN/AmGeneral detection)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.extraction.company_resolution import build_companies_payload, normalize_detection, resolve_company
from app.extraction.candidate_finder import find_candidates


AM = "amassurance-company-id"
QBE = "qbe-company-id"
COMPANIES = [
    {
        "company_id": AM,
        "name": "AmAssurance",
        "source_template_category": "Amgen / AmAssurance / Kurnia-style",
        "aliases": ["AmAssurance", "AmGen", "AmGeneral", "AmGeneral Insurance", "Kurnia", "auto365"],
    },
    {
        "company_id": QBE,
        "name": "QBE",
        "source_template_category": "QBE",
        "aliases": ["qbe", "QBE Insurance", "QBE Insurance (Malaysia) Berhad"],
    },
]


@pytest.mark.parametrize(
    "variant",
    [
        "AmGen",
        "AMGEN",
        "Amgeneral",
        "AmGeneral",
        "AM General Insurance Berhad",
        "AmGeneral Insurance",
        "Kurnia",
        "auto365",
        "AmAssurance",
        "AMASSURANCE",
    ],
)
def test_variants_resolve_to_amassurance(variant: str):
    resolved = resolve_company(variant, COMPANIES)
    assert resolved["status"] == "matched"
    assert resolved["company_id"] == AM
    assert resolved["display_name"] == "AmAssurance"


def test_unrelated_tokens_never_match():
    for value in ["AmBank", "Maybank", "AM Garden", "QBEz", "Sompo", "Takaful Malaysia"]:
        resolved = resolve_company(value, COMPANIES)
        assert resolved["status"] == "unresolved", value
        assert resolved["company_id"] is None


def test_empty_value_is_unresolved():
    resolved = resolve_company("", COMPANIES)
    assert resolved["status"] == "unresolved"
    assert resolved["company_id"] is None


def test_ambiguous_alias_across_companies_is_reported():
    companies = [
        {"company_id": "a", "name": "Alpha", "aliases": ["shared"]},
        {"company_id": "b", "name": "Beta", "aliases": ["shared"]},
    ]
    resolved = resolve_company("shared", companies)
    assert resolved["status"] == "ambiguous"
    assert resolved["company_id"] is None


def test_normalize_detection_collapses_separators():
    assert normalize_detection("AM General Insurance BERHAD") == "am general insurance berhad"
    assert normalize_detection("AmGen") == "amgen"


def test_build_companies_payload_unions_detection_phrases_and_alias_rows():
    class Row:
        def __init__(self, company_id, alias, status):
            self.company_id = company_id
            self.alias = alias
            self.status = status

    class Company:
        def __init__(self, cid, name, phrases, category):
            self.id = cid
            self.name = name
            self.detection_phrases = phrases
            self.source_template_category = category

    company = Company(AM, "AmAssurance", ["AmAssurance"], "Amgen-style")
    alias_rows = [
        Row(AM, "AmGen", "active"),
        Row(AM, "AmGen", "active"),
        Row(AM, "Kurnia", "active"),
    ]
    payload = build_companies_payload([company], alias_rows)
    assert payload[0]["name"] == "AmAssurance"
    assert payload[0]["source_template_category"] == "Amgen-style"
    assert payload[0]["aliases"] == ["AmAssurance", "AmGen", "Kurnia"]


def test_upload_filename_amgen_detects_amassurance():
    results = find_candidates(
        "some quotation text without a company name",
        page_text=[],
        source_filename="20250701_AMGEN_QUOTATION.pdf",
        db_companies=COMPANIES,
    )
    company_values = [c.value for c in results.get("insurance_company", [])]
    assert "AmAssurance" in company_values


def test_text_amgeneral_variant_detects_amassurance():
    results = find_candidates(
        "Insured under AmGeneral Insurance Berhad effective today",
        page_text=[],
        db_companies=COMPANIES,
    )
    company_values = [c.value for c in results.get("insurance_company", [])]
    assert "AmAssurance" in company_values


def test_upload_filename_qbe_detects_qbe():
    results = find_candidates(
        "PRIVATE CAR PROTECTOR QUOTATION without company in text",
        page_text=[],
        source_filename="20260506_VKL7831_Quotation_QBE.pdf",
        db_companies=COMPANIES,
    )
    company_values = [c.value for c in results.get("insurance_company", [])]
    assert "QBE" in company_values


def test_conflict_detector_prefers_database_company_filename_over_conflicting_gemini():
    from app.extraction.conflict_detector import select_field
    from app.extraction.types import CandidateValue

    candidates = [
        CandidateValue(
            field="insurance_company",
            value="AmAssurance",
            source_method="gemini_vision",
            score=0.99,
            page=1,
            evidence="Gemini multimodal extraction: AmAssurance",
        ),
        CandidateValue(
            field="insurance_company",
            value="QBE",
            source_method="database_company_filename",
            score=0.99,
            page=1,
            evidence="20260506_VKL7831_Quotation_QBE.pdf",
        ),
    ]
    selection = select_field("insurance_company", candidates)
    assert selection.value == "QBE"
    assert selection.status == "ready"

