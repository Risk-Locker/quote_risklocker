import pytest
from app.rendering.unified_addon_engine import (
    extract_free_coverage_items,
    build_unified_matrix_cards,
)


def test_towing_upgrade_etiqa_oto_360():
    """Given Etiqa + OTO 360 rider: Top-Right Towing card upgrades in-place to UNLIMITED TOWING ASSISTANCE,
    while bottom matrix contains [✔] OTO 360 without duplicate generic towing card."""
    active_benefits = [
        {
            "id": "oto_360_rider",
            "title": "OTO 360",
            "is_extra": True,
            "cost_status": "paid",
            "price": "RM 120.00",
            "is_selected": True,
        }
    ]

    free_items = extract_free_coverage_items(active_benefits, insurer_name="Etiqa")
    towing_item = next(
        (item for item in free_items if "towing" in item["title"].lower()), None
    )

    assert towing_item is not None
    assert towing_item["title"] == "Unlimited Towing Assistance"
    assert "Upgraded via OTO 360" in towing_item["description"]

    # In bottom matrix cards:
    matrix_cards = build_unified_matrix_cards(active_benefits)
    # The selected rider must be present and ticked
    rider_card = next(
        (c for c in matrix_cards if "oto 360" in c["title"].lower()), None
    )
    assert rider_card is not None
    assert rider_card["is_selected"] is True

    # Generic unselected Unlimited Towing card must be suppressed from bottom matrix
    duplicate_towing_card = next(
        (
            c
            for c in matrix_cards
            if c["id"] == "towing" and c.get("is_selected") is not True
        ),
        None,
    )
    assert duplicate_towing_card is None


def test_towing_upgrade_takaful_motor_pa_plus_plans():
    """Given Takaful Malaysia: Plan 4 gives Unlimited Towing; Plan 3 gives 300 km Towing."""
    # Plan 4 -> Unlimited
    benefits_plan4 = [
        {
            "title": "Motor PA Plus - Plan 4",
            "is_extra": True,
            "cost_status": "paid",
            "is_selected": True,
        }
    ]
    free_items_p4 = extract_free_coverage_items(
        benefits_plan4, insurer_name="Takaful Malaysia"
    )
    towing_p4 = next(
        (i for i in free_items_p4 if "towing" in i["title"].lower()), None
    )
    assert towing_p4 is not None
    assert towing_p4["title"] == "Unlimited Towing Assistance"
    assert "Upgraded via Motor PA Plus" in towing_p4["description"]

    # Plan 3 -> 300 km
    benefits_plan3 = [
        {
            "title": "Motor PA Plus - Plan 3",
            "is_extra": True,
            "cost_status": "paid",
            "is_selected": True,
        }
    ]
    free_items_p3 = extract_free_coverage_items(
        benefits_plan3, insurer_name="Takaful Malaysia"
    )
    towing_p3 = next(
        (i for i in free_items_p3 if "towing" in i["title"].lower()), None
    )
    assert towing_p3 is not None
    assert towing_p3["title"] == "Extended Towing Assistance (300 km)"
    assert "Upgraded via Motor PA Plus" in towing_p3["description"]


def test_towing_standard_without_rider():
    """Without upgrade rider, Top-Right Towing card remains standard Emergency Towing Assistance."""
    active_benefits = [
        {
            "title": "Windscreen Protection",
            "is_extra": True,
            "cost_status": "paid",
            "price": "RM 300.00",
            "is_selected": True,
        }
    ]
    free_items = extract_free_coverage_items(active_benefits, insurer_name="Etiqa")
    towing_item = next(
        (item for item in free_items if "towing" in item["title"].lower()), None
    )

    assert towing_item is not None
    assert towing_item["title"] == "Emergency Towing Assistance (RM 200.00)"
    assert "Upgraded via" not in towing_item["description"]

