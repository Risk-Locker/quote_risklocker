"""Hermetic tests for Betterment & Waiver of Betterment Rule Engine.

Covers:
1. Condition 1: 0 to 5 years (YOM + 4 > Quote Year) -> Waiver = YES -> 'No (0%)'
2. Condition 2.1: QBE Comprehensive Private Car (YOM + 9 > Current Year) -> Waiver = YES
3. Condition 2.2: Insurers without peril -> Waiver = NO
4. Condition 2.2: Tune, Sompo, AmAssurance, Etiqa with peril (YOM + 14 > Current Year)
5. Condition 2.2: Lonpac, STMB with peril (YOM + 9 > Current Year)
6. Peril detector check_has_betterment_peril
"""

from datetime import datetime, timezone
import pytest

from app.services.marketing_comparison_service import (
    evaluate_betterment_rules,
    get_standard_betterment_rate,
    check_has_betterment_peril,
)


def test_condition_1_zero_to_five_years():
    """If YEAR OF MAKE + 4 > Quotation Year, then WAIVER OF BETTERMENT = YES (0% co-payment)."""
    # 2023 YOM, Quote Year 2026 -> 2023 + 4 = 2027 > 2026 -> YES
    has_waiver, rate, display = evaluate_betterment_rules(
        yom=2023,
        quote_year=2026,
        company_name="Allianz",
        has_betterment_peril=False,
    )
    assert has_waiver is True
    assert rate == 0.0
    assert display == "No (0%)"

    # 2024 YOM, Quote Year 2026 -> 2024 + 4 = 2028 > 2026 -> YES
    has_waiver, rate, display = evaluate_betterment_rules(
        yom=2024,
        quote_year=2026,
        company_name="Etiqa",
        has_betterment_peril=False,
    )
    assert has_waiver is True
    assert rate == 0.0
    assert display == "No (0%)"


def test_condition_1_older_cars_fall_through():
    """If YEAR OF MAKE + 4 <= Quotation Year, evaluates Condition 2."""
    # 2022 YOM, Quote Year 2026 -> 2022 + 4 = 2026 <= 2026 -> falls through
    # For standard insurer without peril, 2022 in 2026 is 4-5 completed years -> tariff scale applies
    has_waiver, rate, display = evaluate_betterment_rules(
        yom=2021,
        quote_year=2026,
        company_name="Allianz",
        has_betterment_peril=False,
    )
    assert has_waiver is False
    assert rate == 15.0
    assert display == "Yes (15%)"


def test_condition_2_1_qbe_ten_year_rule():
    """QBE Comprehensive Private Car: if YOM + 9 > Current Year -> Waiver = YES, else NO."""
    curr_y = datetime.now().year
    # YOM 2018 in 2026 -> 2018 + 9 = 2027 > 2026 -> YES (no peril needed)
    has_waiver, rate, display = evaluate_betterment_rules(
        yom=curr_y - 8,
        quote_year=curr_y,
        company_name="QBE Comprehensive Private Car",
        has_betterment_peril=False,
    )
    assert has_waiver is True
    assert rate == 0.0
    assert display == "No (0%)"

    # YOM 2015 in 2026 -> 2015 + 9 = 2024 <= 2026 -> NO (tariff rate applied: 10y+ is 40%)
    has_waiver, rate, display = evaluate_betterment_rules(
        yom=curr_y - 11,
        quote_year=curr_y,
        company_name="QBE Insurance (Malaysia) Berhad",
        has_betterment_peril=False,
    )
    assert has_waiver is False
    assert rate == 40.0
    assert display == "Yes (40%)"


def test_condition_2_2_other_insurers_without_peril():
    """If not QBE and NO betterment perils added -> Waiver = NO (tariff scale)."""
    curr_y = datetime.now().year
    # Etiqa YOM curr_y - 7, 7y vehicle, no peril -> Waiver = NO (25%)
    has_waiver, rate, display = evaluate_betterment_rules(
        yom=curr_y - 7,
        quote_year=curr_y,
        company_name="Etiqa General Insurance",
        has_betterment_peril=False,
    )
    assert has_waiver is False
    assert rate == 25.0
    assert display == "Yes (25%)"

    # Berjaya Sompo YOM curr_y - 8, 8y vehicle, no peril -> Waiver = NO (30%)
    has_waiver, rate, display = evaluate_betterment_rules(
        yom=curr_y - 8,
        quote_year=curr_y,
        company_name="Berjaya Sompo",
        has_betterment_peril=False,
    )
    assert has_waiver is False
    assert rate == 30.0
    assert display == "Yes (30%)"


def test_condition_2_2_tune_sompo_amassurance_etiqa_with_peril():
    """For (TUNE, SOMPO, AMASSURANCE, ETIQA): if peril added and YOM + 14 > Current Year -> Waiver = YES."""
    curr_y = datetime.now().year
    for company in ["Tune Insurance", "Berjaya Sompo Insurance", "AmAssurance Berhad", "Etiqa Auto360"]:
        # YOM curr_y - 12 -> (curr_y - 12) + 14 = curr_y + 2 > curr_y -> YES
        has_waiver, rate, display = evaluate_betterment_rules(
            yom=curr_y - 12,
            quote_year=curr_y,
            company_name=company,
            has_betterment_peril=True,
        )
        assert has_waiver is True, f"Failed for {company}"
        assert rate == 0.0, f"Failed for {company}"
        assert display == "No (0%)", f"Failed for {company}"

        # YOM curr_y - 15 -> (curr_y - 15) + 14 = curr_y - 1 <= curr_y -> NO (exceeds 15 years)
        has_waiver, rate, display = evaluate_betterment_rules(
            yom=curr_y - 15,
            quote_year=curr_y,
            company_name=company,
            has_betterment_peril=True,
        )
        assert has_waiver is False, f"Failed for {company}"
        assert rate == 40.0, f"Failed for {company}"
        assert display == "Yes (40%)", f"Failed for {company}"


def test_condition_2_2_lonpac_stmb_with_peril():
    """For (LONPAC, STMB): if peril added and YOM + 9 > Current Year -> Waiver = YES."""
    curr_y = datetime.now().year
    for company in ["Lonpac Insurance", "Syarikat Takaful Malaysia Berhad (STMB)"]:
        # YOM curr_y - 8 -> (curr_y - 8) + 9 = curr_y + 1 > curr_y -> YES
        has_waiver, rate, display = evaluate_betterment_rules(
            yom=curr_y - 8,
            quote_year=curr_y,
            company_name=company,
            has_betterment_peril=True,
        )
        assert has_waiver is True, f"Failed for {company}"
        assert rate == 0.0, f"Failed for {company}"
        assert display == "No (0%)", f"Failed for {company}"

        # YOM curr_y - 10 -> (curr_y - 10) + 9 = curr_y - 1 <= curr_y -> NO (exceeds 10 years)
        has_waiver, rate, display = evaluate_betterment_rules(
            yom=curr_y - 10,
            quote_year=curr_y,
            company_name=company,
            has_betterment_peril=True,
        )
        assert has_waiver is False, f"Failed for {company}"
        assert rate == 40.0, f"Failed for {company}"
        assert display == "Yes (40%)", f"Failed for {company}"


def test_check_has_betterment_peril():
    """Tests peril keyword detection across structured benefits and OCR text."""
    # Matches in structured fields
    assert check_has_betterment_peril(f={"benefit_name": "Waiver of Betterment"}) is True
    assert check_has_betterment_peril(f={"peril": "car spare parts waiver of betterment"}) is True
    assert check_has_betterment_peril(combined_text="Waiver of betterment contribution") is True
    assert check_has_betterment_peril(combined_text="Endorsement 111: Betterment Waiver Included") is True

    # Explicit flag
    assert check_has_betterment_peril(raw_w="Yes") is True
    assert check_has_betterment_peril(raw_w=True) is True
    assert check_has_betterment_peril(raw_w="No") is False

    # Negative case
    assert check_has_betterment_peril(f={"title": "Windscreen Coverage", "cost": "150.0"}) is False
    assert check_has_betterment_peril(combined_text="Standard comprehensive coverage with towing 200km") is False
