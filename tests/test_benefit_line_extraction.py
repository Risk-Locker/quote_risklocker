"""Conservative, evidence-bearing extraction of quotation benefit lines with scoped aliases and templates."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.extraction.benefit_lines import extract_benefit_lines


CONCEPTS = [
    {
        "concept_id": "windscreen",
        "concept_key": "windscreen",
        "label": "Windscreen Cover",
        "description": "up to RM1,000",
        "description_variants": [
            {"key": "default", "template": "up to {value}", "value_type": "money"}
        ],
        "match_dataset": ["windscreen", "window", "glass", "tinted glass"],
        "aliases": [
            {"phrase": "Windscreen Damage", "scope": "global"},
            {"phrase": "Etiqa Windscreen Plus", "scope": "company", "company_id": "etiqa-123"},
        ],
    },
    {
        "concept_id": "special-perils",
        "concept_key": "special-perils",
        "label": "Special Perils",
        "description": "up to RM50,000",
        "description_variants": [
            {"key": "default", "template": "up to {value}", "value_type": "money"}
        ],
        "match_dataset": ["special perils", "storm", "flood", "landslide", "natural disaster"],
        "aliases": [
            {"phrase": "Damage by Natural Disasters", "scope": "global"},
        ],
    },
    {
        "concept_id": "towing",
        "concept_key": "towing",
        "label": "Towing",
        "description": "up to 50 km",
        "description_variants": [
            {"key": "default", "template": "up to {value}", "value_type": "distance"}
        ],
        "match_dataset": ["towing", "breakdown", "roadside assistance"],
        "aliases": [
            {"phrase": "24/7 Roadside Towing", "scope": "global"},
            {"phrase": "QBE Super Towing", "scope": "company", "company_id": "qbe-123"},
        ],
    },
    {
        "concept_id": "warranty",
        "concept_key": "repair-workmanship-warranty",
        "label": "Repair Workmanship Warranty",
        "description": "up to 3 years",
        "description_variants": [
            {"key": "default", "template": "up to {value}", "value_type": "duration"}
        ],
        "match_dataset": ["workmanship", "repair warranty"],
        "aliases": [
            {"phrase": "Panel Workshop Warranty", "scope": "global"},
        ],
    },
    {
        "concept_id": "hospital-income",
        "concept_key": "daily-hospital-income",
        "label": "Daily Hospital Income",
        "description": "up to RM100/day",
        "description_variants": [
            {"key": "default", "template": "up to {value}", "value_type": "per_day"}
        ],
        "match_dataset": ["hospital income", "hospital allowance"],
        "aliases": [],
    },
]


def test_explicit_checkbox_state_separates_selected_and_unselected_lines():
    text = """SELECTED OPTIONAL COVERS
☑ Windscreen Damage RM 1,500.00 Premium RM 150.00
☐ Special Perils
"""
    lines = extract_benefit_lines([{"page": 1, "text": text}], concepts=CONCEPTS)

    assert [(line["normalized_label"], line["inclusion_state"]) for line in lines] == [
        ("windscreen damage", "selected"),
        ("special perils", "not_selected"),
    ]
    assert lines[0]["extracted_value"] == {
        "type": "money",
        "value": "1500.00",
        "currency": "MYR",
        "semantic_role": "insured_limit",
        "premium": {"amount": "150.00", "currency": "MYR"},
    }
    assert lines[0]["candidate_mappings"][0]["concept_id"] == "windscreen"
    assert lines[0]["evidence"]["page"] == 1


def test_quote_selected_section_is_selected_without_checkbox_but_not_available_section():
    text = """OPTIONAL COVER LIST
Legal Liability to Passenger
Windscreen Damage RM 1,000.00
AVAILABLE OPTIONAL COVERS
Special Perils
"""
    lines = extract_benefit_lines([{"page": 2, "text": text}], concepts=CONCEPTS)

    by_label = {line["normalized_label"]: line for line in lines}
    assert by_label["legal liability to passenger"]["inclusion_state"] == "selected"
    assert by_label["windscreen damage"]["inclusion_state"] == "selected"
    assert by_label["special perils"]["inclusion_state"] == "not_selected"


def test_pds_narrative_examples_and_totals_never_become_selected_benefits():
    text = """PRODUCT DISCLOSURE SHEET
Special Perils may cover flood, storm, typhoon and other events.
Example: towing assistance could cost RM 300.00.
Total Optional Cover Amount RM 450.00
This benefit is not included.
"""
    lines = extract_benefit_lines([{"page": 4, "text": text}], concepts=CONCEPTS)

    assert all(line["inclusion_state"] != "selected" for line in lines)
    assert all(line["source_scope"] in {"pds", "narrative"} for line in lines)
    assert not any(line["normalized_label"].startswith("total optional") for line in lines)


def test_unstructured_benefit_like_line_remains_unknown_for_review():
    text = "BENEFITS\n24/7 Roadside Towing 200 km\n"
    lines = extract_benefit_lines([{"page": 3, "text": text}], concepts=CONCEPTS)

    assert len(lines) == 1
    assert lines[0]["inclusion_state"] == "unknown"
    assert lines[0]["source_scope"] == "unknown"
    assert lines[0]["extracted_value"] == {"type": "distance", "value": "200", "unit": "km", "unlimited": False}


def test_line_ids_are_stable_and_duplicate_occurrences_are_distinct():
    pages = [{"page": 1, "text": "SELECTED BENEFITS\n☑ Towing\n☑ Towing\n"}]
    first = extract_benefit_lines(pages, concepts=CONCEPTS)
    second = extract_benefit_lines(pages, concepts=CONCEPTS)

    assert [line["line_id"] for line in first] == [line["line_id"] for line in second]
    assert len({line["line_id"] for line in first}) == 2


def test_broad_coverage_facets_are_not_split_into_extra_entitlements():
    text = "SELECTED BENEFITS\n☑ Special Perils covering flood, storm and typhoon\n"
    lines = extract_benefit_lines([{"page": 1, "text": text}], concepts=CONCEPTS)

    assert len(lines) == 1
    assert lines[0]["candidate_mappings"][0]["concept_id"] == "special-perils"


def test_scoped_aliases_priority_boost():
    # When company_id='qbe-123', 'QBE Super Towing' gets boosted priority
    text = "SELECTED BENEFITS\n☑ QBE Super Towing 150 km\n"
    lines = extract_benefit_lines(
        [{"page": 1, "text": text}],
        concepts=CONCEPTS,
        company_id="qbe-123",
    )
    assert len(lines) == 1
    mapping = lines[0]["candidate_mappings"][0]
    assert mapping["concept_id"] == "towing"
    assert mapping["match_type"] == "scoped_alias"
    assert mapping["shaped_description"] == "up to 150 km"


def test_match_dataset_fallback_matching():
    # Line contains match dataset word 'breakdown' rather than explicit alias
    text = "SELECTED BENEFITS\n☑ Emergency Breakdown Assistance 50 km\n"
    lines = extract_benefit_lines([{"page": 1, "text": text}], concepts=CONCEPTS)

    assert len(lines) == 1
    assert any(c["concept_id"] == "towing" and c["match_type"] == "match_dataset" for c in lines[0]["candidate_mappings"])
    assert lines[0]["candidate_mappings"][0]["shaped_description"] == "up to 50 km"


def test_typed_values_and_description_shaping_across_types():
    text = """SELECTED BENEFITS
☑ Towing Unlimited
☑ Windscreen Damage RM 2,500.00
☑ Repair Workmanship Warranty 3 years
☑ Daily Hospital Income RM 100 per day
"""
    lines = extract_benefit_lines([{"page": 1, "text": text}], concepts=CONCEPTS)
    by_concept = {l["candidate_mappings"][0]["concept_id"]: l for l in lines if l["candidate_mappings"]}

    # 1. Distance unlimited
    assert by_concept["towing"]["extracted_value"] == {"type": "distance", "value": None, "unit": "km", "unlimited": True}
    assert by_concept["towing"]["candidate_mappings"][0]["shaped_description"] == "up to Unlimited"

    # 2. Money limit
    assert by_concept["windscreen"]["extracted_value"]["value"] == "2500.00"
    assert by_concept["windscreen"]["candidate_mappings"][0]["shaped_description"] == "up to RM2,500"

    # 3. Duration
    assert by_concept["warranty"]["extracted_value"] == {"type": "duration", "value": "3", "unit": "years"}
    assert by_concept["warranty"]["candidate_mappings"][0]["shaped_description"] == "up to 3 years"

    # 4. Per day income
    assert by_concept["hospital-income"]["extracted_value"] == {"type": "per_day", "value": "100.00", "currency": "MYR", "unit": "day"}
    assert by_concept["hospital-income"]["candidate_mappings"][0]["shaped_description"] == "up to RM100/day"


def test_table_stitching_and_section_stop_rejects_accounting_noise():
    text = """ADDITIONAL COVERS
:
BREAKAGE OF GLASS IN
W/SCREEN   4,000.00
:
RM 600.00
PASSENGER LIABILITY COVER   :
RM 71.85
ALL DRIVERS  
:
RM 0.00
TOTAL
:
RM 671.85
TAKAFUL CONTRIBUTION
:
BASIC CONTRIBUTION
:
RM 4,294.71
- NCD (55.00 %)
:
RM 2,362.09
+ ADDITIONAL COVERAGE
:
RM 671.85
GROSS CONTRIBUTION
:
RM 2,604.47
TOTAL CONTRIBUTION
:
RM 2,822.85
QUOTATION TYPE: STANDARD
Acceptance of any referred case is subject to the approval of Motor Underwriter.
AGENT CODE : GCA03986 - ALM CONSULTANCY
"""
    lines = extract_benefit_lines([{"page": 1, "text": text}], concepts=CONCEPTS)
    assert len(lines) == 3

    # 1. Breakage of glass
    assert "breakage of glass in windscreen" in lines[0]["normalized_label"]
    assert lines[0]["coverage_limit"] == "4000.00"
    assert lines[0]["premium_cost"] == "600.00"

    # 2. Passenger liability cover
    assert lines[1]["normalized_label"] == "passenger liability cover"
    assert lines[1]["premium_cost"] == "71.85"

    # 3. All drivers
    assert lines[2]["normalized_label"] == "all drivers"
    assert lines[2]["premium_cost"] == "0.00"


def test_pure_amounts_and_negative_selection_rejected():
    text = """SELECTED BENEFITS
RM 600.00
4,294.71
AGREED VALUE : NO
TAKAFUL SCHEME : MOTOR TAKAFUL
TOTAL PAYABLE : RM 2,822.85
"""
    lines = extract_benefit_lines([{"page": 1, "text": text}], concepts=CONCEPTS)
    assert len(lines) == 0

