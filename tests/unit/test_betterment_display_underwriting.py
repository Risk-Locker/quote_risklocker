"""Unit tests for Waiver of Betterment Underwriting and Matrix Display Rules."""

import pytest
from app.rendering.unified_addon_engine import (
    build_unified_matrix_cards,
    format_addon_value,
    CANONICAL_24_CATALOG,
)
from app.services.marketing_comparison.ncd_evaluator import evaluate_betterment_rules


def test_canonical_betterment_default_value():
    betterment = next((item for item in CANONICAL_24_CATALOG if item["id"] == "betterment"), None)
    assert betterment is not None
    assert betterment["default_value"] == "Up to 15 Years"
    assert "RM" not in betterment["default_value"]


def test_format_addon_value_suppresses_rm_for_betterment():
    # If raw OCR or user typed RM 120.00, it must be suppressed
    assert format_addon_value("betterment", "RM 120.00") == "Up to 15 Years"
    assert format_addon_value("betterment", "RM 150.00") == "Up to 15 Years"
    assert format_addon_value("betterment", "") == "Up to 15 Years"
    # Explicit year limits are preserved cleanly
    assert format_addon_value("betterment", "Up to 10 Years") == "Up to 10 Years"
    assert format_addon_value("betterment", "Up to 16 Years") == "Up to 16 Years"
    assert format_addon_value("betterment", "Betterment Waived") == "Betterment Waived"


@pytest.mark.parametrize(
    "insurer,expected_default_years",
    [
        ("QBE", "Up to 10 Years"),
        ("QBE Insurance (Malaysia) Berhad", "Up to 10 Years"),
        ("STMB", "Up to 10 Years"),
        ("Syarikat Takaful Malaysia Am Berhad", "Up to 10 Years"),
        ("Takaful Malaysia", "Up to 10 Years"),
        ("Lonpac", "Up to 10 Years"),
        ("Lonpac Insurance Bhd", "Up to 10 Years"),
        ("Etiqa", "Up to 15 Years"),
        ("Etiqa General Insurance Berhad", "Up to 15 Years"),
        ("Allianz", "Up to 15 Years"),
        ("Zurich", "Up to 15 Years"),
        ("Berjaya Sompo", "Up to 15 Years"),
        ("AmAssurance", "Up to 15 Years"),
        ("Liberty Insurance", "Up to 15 Years"),
        ("Kurnia", "Up to 15 Years"),
    ],
)
def test_build_unified_matrix_cards_insurer_betterment_limits(insurer, expected_default_years):
    # Case 1: Unselected / catalog default
    cards = build_unified_matrix_cards(
        active_benefits=[],
        available_addons=[],
        insurer_name=insurer,
        fill_to_slots=24,
    )
    b_card = next((c for c in cards if c["id"] == "betterment"), None)
    assert b_card is not None
    assert b_card["value"] == expected_default_years
    assert "RM" not in b_card["value"]

    # Case 2: Selected with raw RM price attached (must sanitize and ignore RM)
    selected_betterment = [
        {
            "id": "betterment",
            "title": "Betterment Waiver",
            "value": "RM 135.00",
            "is_selected": True,
            "cost_status": "paid",
        }
    ]
    cards_selected = build_unified_matrix_cards(
        active_benefits=selected_betterment,
        available_addons=[],
        insurer_name=insurer,
        fill_to_slots=24,
    )
    b_sel = next((c for c in cards_selected if c["id"] == "betterment"), None)
    assert b_sel is not None
    assert b_sel["is_selected"] is True
    assert b_sel["value"] == expected_default_years
    assert "RM" not in b_sel["value"]


def test_evaluate_betterment_rules_actuarial_stability():
    # 1. Under 5 completed years -> Always 0% exemption
    waived, rate, disp = evaluate_betterment_rules(
        quote_year=2026,
        yom=2023,
        company_name="Allianz",
        has_betterment_peril=False,
    )
    assert waived is True
    assert rate == 0.0

    # 2. QBE Comprehensive Private <= 10 completed years -> FOC Waiver (0%)
    waived_qbe, rate_qbe, disp_qbe = evaluate_betterment_rules(
        quote_year=2026,
        yom=2018,  # 8 years
        company_name="QBE",
        has_betterment_peril=False,
    )
    assert waived_qbe is True
    assert rate_qbe == 0.0

    # 3. STMB / Lonpac: 8 years with peril added -> Waived (0%)
    waived_stmb, rate_stmb, disp_stmb = evaluate_betterment_rules(
        quote_year=2026,
        yom=2018,  # 8 years
        company_name="STMB",
        has_betterment_peril=True,
    )
    assert waived_stmb is True
    assert rate_stmb == 0.0

    # 4. STMB / Lonpac: 12 years with peril added -> Ineligible (scale rate applies)
    waived_stmb_old, rate_stmb_old, disp_stmb_old = evaluate_betterment_rules(
        quote_year=2026,
        yom=2014,  # 12 years
        company_name="STMB",
        has_betterment_peril=True,
    )
    assert waived_stmb_old is False
    assert rate_stmb_old == 40.0  # 10+ years capped at 40% (percentage)

    # 5. Etiqa / Sompo / AmAssurance: 12 years with peril added -> Waived up to 15 years
    waived_etiqa, rate_etiqa, disp_etiqa = evaluate_betterment_rules(
        quote_year=2026,
        yom=2014,  # 12 years
        company_name="Etiqa",
        has_betterment_peril=True,
    )
    assert waived_etiqa is True
    assert rate_etiqa == 0.0
