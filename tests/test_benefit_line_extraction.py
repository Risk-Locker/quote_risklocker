"""Conservative, evidence-bearing extraction of quotation benefit lines."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.extraction.benefit_lines import extract_benefit_lines


CONCEPTS = [
    {"concept_id": "windscreen", "label": "Windscreen Cover", "aliases": ["windscreen", "windscreen damage"]},
    {"concept_id": "special-perils", "label": "Special Perils", "aliases": ["special perils"]},
    {"concept_id": "towing", "label": "Towing", "aliases": ["towing", "roadside towing"]},
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
    text = "BENEFITS\nRoadside Towing 200 km\n"
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
    assert "flood" not in {candidate["concept_id"] for line in lines for candidate in line["candidate_mappings"]}
