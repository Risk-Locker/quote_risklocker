import pytest
from app.rendering.unified_addon_engine import (
    extract_free_coverage_items,
    build_unified_matrix_cards,
)


def test_towing_upgrade_etiqa_oto_360():
    """New Box 1 -> Box 2 architecture:
    1. Raw paid OTO 360 rider WITHOUT bundle promotion does NOT mutate Box 1 towing in place.
    2. When OTO 360 is promoted via DB Bundled Benefits (bundle_included towing in Box 2 + parent bundle),
       Box 1 removes towing completely and Box 2 contains [check] OTO 360 (with price) and
       [check] Unlimited Towing Assistance (with price=None).
    """
    raw_without_bundle_flags = [
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

    free_items = extract_free_coverage_items(raw_without_bundle_flags, insurer_name="Etiqa")
    towing_item = next(
        (item for item in free_items if "towing" in item["title"].lower()), None
    )
    assert towing_item is not None
    assert towing_item["title"] == "Emergency Towing Assistance (200 km)"
    assert "Upgraded via" not in towing_item["description"]

    # Strictly 1:1 Box 1 rule: removing Box 1 towing leaves zero towing in Top-Right
    free_without_box1_tow = extract_free_coverage_items([raw_without_bundle_flags[1]], insurer_name="Etiqa")
    assert not any("towing" in i["title"].lower() for i in free_without_box1_tow)

    # New Box 1 -> Box 2 bundle behavior
    bundled_active_benefits = [
        {
            "id": "tow_bundle",
            "concept_key": "towing",
            "title": "Unlimited Towing Assistance",
            "value": "",
            "is_extra": True,
            "promoted_to_addon": True,
            "is_bundle_effect": True,
            "cost_status": "bundle_included",
            "price": None,
            "icon_hint": "unlimited_towing",
            "is_selected": True,
        },
        {
            "id": "oto_360_rider",
            "concept_key": "oto-360",
            "title": "OTO 360",
            "value": "",
            "is_extra": True,
            "is_bundle": True,
            "cost_status": "paid",
            "price": {"amount": "120.00", "currency": "MYR"},
            "is_selected": True,
        },
    ]
    free_bundled = extract_free_coverage_items(bundled_active_benefits, insurer_name="Etiqa")
    assert not any("towing" in i["title"].lower() for i in free_bundled)
    assert not any("oto 360" in i["title"].lower() for i in free_bundled)

    matrix_cards = build_unified_matrix_cards(bundled_active_benefits)
    rider_card = next((c for c in matrix_cards if "oto 360" in c["title"].lower()), None)
    tow_card = next((c for c in matrix_cards if c["id"] == "towing"), None)
    assert rider_card is not None and rider_card["is_selected"] is True and rider_card["price"] is not None
    assert tow_card is not None and tow_card["is_selected"] is True
    assert tow_card["title"] == "Unlimited Towing Assistance"
    assert tow_card["price"] is None
    assert tow_card["cost_status"] == "bundle_included"


def test_towing_upgrade_takaful_motor_pa_plus_plans():
    """Given Takaful Malaysia: without bundle promotion Box 1 keeps standard 50 km;
    when Motor PA Plus bundle promotes towing to Box 2, Box 1 removes towing and Box 2 shows
    exact plan title without duplicate plan value + no-price connected towing card."""
    # Unpromoted raw cards leave Box 1 standard 50 km untouched (no legacy detect_towing_upgrade mutation)
    raw_unpromoted = [
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
    free_items_raw = extract_free_coverage_items(raw_unpromoted, insurer_name="Takaful Malaysia")
    towing_raw = next((i for i in free_items_raw if "towing" in i["title"].lower()), None)
    assert towing_raw is not None
    assert towing_raw["title"] == "Emergency Towing Assistance (50 km)"

    # Promoted bundle -> Plan 3 in Box 2 with 300 km connected towing (no price) and zero towing in Box 1
    promoted_p3 = [
        {
            "id": "tow_p3",
            "concept_key": "towing",
            "title": "Towing Assistance (300 km)",
            "value": "",
            "is_extra": True,
            "promoted_to_addon": True,
            "is_bundle_effect": True,
            "cost_status": "bundle_included",
            "price": None,
            "is_selected": True,
        },
        {
            "id": "pa_p3",
            "concept_key": "motor-pa-plus",
            "title": "Motor PA Plus - Plan 3",
            "value": "Plan 3",
            "is_extra": True,
            "is_bundle": True,
            "selected_bundle_tier_label": "Plan 3",
            "cost_status": "paid",
            "price": {"amount": "150.00", "currency": "MYR"},
            "is_selected": True,
        },
    ]
    assert not any("towing" in i["title"].lower() for i in extract_free_coverage_items(promoted_p3, insurer_name="Takaful Malaysia"))
    box2_p3 = build_unified_matrix_cards(promoted_p3)
    bundle_card = next(c for c in box2_p3 if "motor pa plus" in c["title"].lower())
    tow_card = next(c for c in box2_p3 if c["id"] == "towing")
    assert bundle_card["title"] == "Motor PA Plus - Plan 3"
    assert bundle_card["value"] == ""
    assert bundle_card["price"] is not None
    assert tow_card["title"] == "Towing Assistance (300 km)"
    assert tow_card["price"] is None


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


