"""Unit tests for the unified float-to-top add-on engine and value formatting."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
os.environ.setdefault("APP_ENV", "test")

from app.rendering.unified_addon_engine import (
    CANONICAL_24_CATALOG,
    build_unified_matrix_cards,
    extract_free_coverage_items,
    format_addon_value,
    sort_unified_addons,
)


def test_selected_addons_float_to_top_and_renumber():
    items = [
        {"id": "betterment", "title": "Waiver of Betterment", "is_extra": False},
        {"id": "windscreen", "title": "Windscreen Coverage", "is_extra": True, "value": "RM 10,000.00"},
        {"id": "respray", "title": "Vehicle Respray Cover", "is_extra": False},
        {"id": "towing", "title": "Unlimited Towing Distance", "is_extra": True, "value": "Unlimited"},
        {"id": "all_drivers", "title": "All Drivers", "is_extra": True},
    ]

    result = sort_unified_addons(items)

    assert len(result) == 5
    assert [r["id"] for r in result[:3]] == ["windscreen", "towing", "all_drivers"]
    assert [r["id"] for r in result[3:]] == ["betterment", "respray"]

    assert result[0]["is_selected"] is True
    assert result[1]["is_selected"] is True
    assert result[2]["is_selected"] is True
    assert result[3]["is_selected"] is False
    assert result[4]["is_selected"] is False
    assert [r["serial_number"] for r in result] == ["01", "02", "03", "04", "05"]


def test_selected_ids_override():
    items = [
        {"id": "cart", "title": "Compensation for Assessed Repair Time"},
        {"id": "special_perils", "title": "Special Perils"},
        {"id": "key_care", "title": "Key Care Replacement"},
    ]
    result = sort_unified_addons(items, selected_ids={"special_perils"})

    assert result[0]["id"] == "special_perils"
    assert result[0]["is_selected"] is True
    assert result[0]["serial_number"] == "01"
    assert [r["id"] for r in result[1:]] == ["cart", "key_care"]
    assert all(r["is_selected"] is False for r in result[1:])


def test_build_unified_matrix_cards_pads_to_24_canonical_slots():
    active_cards = [
        {"id": "windscreen", "label": "Windscreen Coverage", "value": "RM 10,000.00", "is_extra": True},
        {"id": "special_perils", "label": "Special Perils", "is_extra": True},
    ]

    matrix = build_unified_matrix_cards(active_benefits=active_cards, fill_to_slots=24)

    assert len(matrix) == 24
    assert "Windscreen" in matrix[0]["title"]
    assert matrix[0]["is_selected"] is True
    assert matrix[0]["serial_number"] == "01"
    assert matrix[0]["value"] == "RM 10,000.00"
    assert matrix[1]["is_selected"] is True
    assert matrix[1]["serial_number"] == "02"
    for idx in range(2, 24):
        assert matrix[idx]["is_selected"] is False
        assert matrix[idx]["serial_number"] == f"{idx + 1:02d}"


def test_lonpac_priced_available_addons_never_auto_tick():
    active_benefits = [
        {"id": "b1", "concept_key": "towing", "label": "Emergency Towing Assistance", "value": "RM 200", "is_extra": False, "cost_status": "included"},
    ]
    available_addons = [
        {"id": "a1", "concept_key": "windscreen", "label": "Windscreen Coverage", "value": "RM 1,000.0", "price": {"amount": 150.0}, "cost_status": "paid", "is_extra": True},
        {"id": "a2", "concept_key": "special_perils", "label": "Special Perils", "price": {"amount": 320.0}, "cost_status": "paid"},
        {"id": "a3", "concept_key": "cart", "label": "Compensation for Assessed Repair Time (CART)", "value": "14 Days", "price": {"amount": 200.0}},
    ]

    matrix = build_unified_matrix_cards(active_benefits=active_benefits, available_addons=available_addons, fill_to_slots=24)
    assert len(matrix) == 24
    assert all(c["is_selected"] is False for c in matrix), "Lonpac basic FOC + unselected priced catalog items must NOT auto-tick"
    wind = next(c for c in matrix if c["id"] == "windscreen")
    assert wind["value"] == "RM 1,000.00"

    free = extract_free_coverage_items(active_benefits)
    assert len(free) == 1
    assert "Emergency Towing Assistance" in free[0]["title"]


def test_format_addon_value_and_rm0_suppression():
    assert format_addon_value("RM 0") == ""
    assert format_addon_value("RM 0.00") == ""
    assert format_addon_value("0") == ""
    assert format_addon_value("Included") == ""
    assert format_addon_value("FOC") == ""
    assert format_addon_value("1000.0") == "RM 1,000.00"
    assert format_addon_value("RM 8,000") == "RM 8,000.00"
    assert format_addon_value("Waiver of betterment for up to 10 years of age") == "Up to 10 Years"
    assert format_addon_value("Unlimited") == "Unlimited"


def test_matching_safety_and_overflow_beyond_24():
    # car_repair must not accidentally match "pa" (personal_accident)
    # empty ids must never match anything
    active_benefits = [
        {"id": "", "label": "Emergency Towing Assistance", "value": "Free", "is_extra": False},
        {"id": "x1", "label": "Driver & Passenger PA", "value": "RM 0", "is_extra": True},
        {"id": "x2", "label": "Legal Defense Costs", "value": "RM 2,000", "is_extra": False, "cost_status": "included"},
    ]
    available_addons = [
        {"id": "car_repair", "label": "Car Repair Concierge"},
        {"id": "e1", "label": "Custom EV Road Hazard Protection", "description": "Extra item 1"},
        {"id": "e2", "label": "Custom Flood Telemetry Sensor", "description": "Extra item 2"},
        {"id": "e3", "label": "Custom VIP Concierge Dispatch", "description": "Extra item 3"},
        {"id": "e4", "label": "Custom Windshield Coating Rider", "description": "Extra item 4"},
        {"id": "e5", "label": "Custom Fleet Replacement Vehicle", "description": "Extra item 5"},
    ]

    matrix = build_unified_matrix_cards(active_benefits=active_benefits, available_addons=available_addons, fill_to_slots=24)
    assert len(matrix) == 30  # 24 canonical + car_repair + 5 custom addons
    assert matrix[0]["id"] == "pa"
    assert matrix[0]["is_selected"] is True
    assert matrix[0]["value"] == ""  # RM 0 suppressed
    car_repair_card = next(c for c in matrix if c["id"] == "car_repair")
    assert car_repair_card["is_selected"] is False
    assert [c["serial_number"] for c in matrix] == [f"{i + 1:02d}" for i in range(30)]

    free = extract_free_coverage_items(active_benefits)
    free_titles = [f["title"] for f in free]
    assert "Legal Defense Costs" in free_titles
    assert "Emergency Towing Assistance" in free_titles
    assert "Driver & Passenger PA" not in free_titles


def test_canonical_catalog_contains_24_items():
    assert len(CANONICAL_24_CATALOG) == 24
    assert CANONICAL_24_CATALOG[0]["id"] == "windscreen"
