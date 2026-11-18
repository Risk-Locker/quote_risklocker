import pytest
from app.rendering.unified_addon_engine import (
    extract_free_coverage_items,
    build_unified_matrix_cards,
)


def test_towing_upgrade_etiqa_oto_360():
    """Given Etiqa + Box 1 Towing + OTO 360 rider: Top-Right Towing card upgrades in-place to UNLIMITED TOWING ASSISTANCE,
    while bottom matrix contains [✔] OTO 360 without duplicate generic towing card.
    Without a Box 1 Towing card, Top-Right must NEVER synthesize phantom towing."""
    active_benefits = [
        {
            "id": "tow_base",
            "concept_key": "towing",
            "title": "Emergency Towing Assistance",
            "value": "200 km",
            "is_extra": False,
            "cost_status": "included",
        },
        {
            "id": "oto_360_rider",
            "title": "OTO 360",
            "is_extra": True,
            "cost_status": "paid",
            "price": "RM 120.00",
            "is_selected": True,
        },
    ]

    free_items = extract_free_coverage_items(active_benefits, insurer_name="Etiqa")
    towing_item = next(
        (item for item in free_items if "towing" in item["title"].lower()), None
    )

    assert towing_item is not None
    assert towing_item["title"] == "Unlimited Towing Assistance (Unlimited - Driver Plan 1)"
    assert "Upgraded via OTO 360" in towing_item["description"]

    # Strictly 1:1 Box 1 rule: removing Box 1 towing leaves zero towing in Top-Right
    free_without_box1_tow = extract_free_coverage_items([active_benefits[1]], insurer_name="Etiqa")
    assert not any("towing" in i["title"].lower() for i in free_without_box1_tow)

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
    """Given Takaful Malaysia + Box 1 Towing: Plan 4 gives Unlimited Towing; Plan 3 gives 300 km Towing."""
    # Plan 4 -> Unlimited
    benefits_plan4 = [
        {
            "id": "tow_base",
            "concept_key": "towing",
            "title": "Emergency Towing Assistance",
            "value": "50 km",
            "is_extra": False,
            "cost_status": "included",
        },
        {
            "title": "Motor PA Plus - Plan 4",
            "is_extra": True,
            "cost_status": "paid",
            "is_selected": True,
        },
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
            "id": "tow_base",
            "concept_key": "towing",
            "title": "Emergency Towing Assistance",
            "value": "50 km",
            "is_extra": False,
            "cost_status": "included",
        },
        {
            "title": "Motor PA Plus - Plan 3",
            "is_extra": True,
            "cost_status": "paid",
            "is_selected": True,
        },
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
    """Without upgrade rider, Box 1 Towing card remains standard Emergency Towing Assistance; if omitted, zero phantom towing."""
    active_benefits = [
        {
            "id": "tow_base",
            "concept_key": "towing",
            "title": "Emergency Towing Assistance",
            "value": "200 km",
            "is_extra": False,
            "cost_status": "included",
        },
        {
            "title": "Windscreen Protection",
            "is_extra": True,
            "cost_status": "paid",
            "price": "RM 300.00",
            "is_selected": True,
        },
    ]
    free_items = extract_free_coverage_items(active_benefits, insurer_name="Etiqa")
    towing_item = next(
        (item for item in free_items if "towing" in item["title"].lower()), None
    )

    assert towing_item is not None
    assert towing_item["title"] == "Emergency Towing Assistance (200 km)"
    assert "Upgraded via" not in towing_item["description"]


def test_commercial_lorry_has_zero_towing_in_free_coverage():
    """For Commercial Vehicles (lorry, truck, rigid, commercial), towing DOES NOT synthesize unless explicitly placed in Box 1."""
    active_benefits = [
        {
            "title": "Legal Defense Costs",
            "is_extra": False,
            "cost_status": "included",
            "description": "Reimburses court legal representation and defense fees up to RM2,000.",
        },
        {
            "title": "Commercial Windscreen Protection",
            "is_extra": True,
            "cost_status": "paid",
            "price": "RM 300.00",
            "is_selected": True,
        },
    ]
    # 1. Commercial Lorry vehicle_type
    free_items_lorry = extract_free_coverage_items(
        active_benefits,
        insurer_name="Etiqa",
        vehicle_type="Lorry",
        car_model="Hino 300 Rigid Truck",
    )
    towing_in_lorry = [
        item for item in free_items_lorry if "towing" in item["title"].lower()
    ]
    assert len(towing_in_lorry) == 0, "Commercial lorry must NEVER synthesize towing in free coverage"

    # Must also not have child car seat or drive-less save-more
    titles_lower = [item["title"].lower() for item in free_items_lorry]
    assert not any("child" in t for t in titles_lower), "No child seats for commercial lorries"
    assert not any("drive-less" in t for t in titles_lower), "No drive-less save-more for commercial lorries"

    # Legal Defense Costs from Box 1 should be present
    assert any("legal defense" in t for t in titles_lower), "Legal defense costs from Box 1 must be present"


def test_commercial_lorry_matrix_excludes_towing_and_ev():
    """Commercial vehicle 24-card matrix must exclude Towing, EV Wall Charger, EV Battery,
    E-Hailing, and Key Care, while preserving valid commercial endorsements.
    """
    matrix_cards = build_unified_matrix_cards(
        active_benefits=[],
        available_addons=[],
        fill_to_slots=24,
        vehicle_type="Lorry",
        car_model="Isuzu NPR 66",
        insurer_name="AmAssurance",
    )
    card_ids = [c["id"] for c in matrix_cards]

    assert "towing" not in card_ids, "Commercial lorry matrix must NOT contain towing"
    assert "international_towing" not in card_ids, "Commercial lorry matrix must NOT contain international towing"
    assert "ev_wall_charger" not in card_ids, "Commercial lorry matrix must NOT contain EV wall charger"
    assert "ev_out_of_charge" not in card_ids, "Commercial lorry matrix must NOT contain EV out of charge towing"
    assert "ehailing" not in card_ids, "Commercial lorry matrix must NOT contain e-hailing"
    assert "key_care" not in card_ids, "Commercial lorry matrix must NOT contain key care"
    assert len(matrix_cards) > 0


