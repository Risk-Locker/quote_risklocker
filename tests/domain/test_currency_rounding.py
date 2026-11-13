"""Hermetic Unit Tests for Bank Negara Malaysia (BNM) Currency Rounding Engine."""

from decimal import Decimal
import pytest

from app.domain.motor.currency_rounding import (
    apply_bnm_cash_rounding,
    apply_whole_ringgit_rounding,
    calculate_bnm_rounding_adjustment,
    format_currency_with_precision,
)


@pytest.mark.parametrize(
    "raw_input,expected_rounded,expected_adj",
    [
        # Ending in 0 -> 0 (0 adjustment)
        ("10.00", Decimal("10.00"), Decimal("0.00")),
        ("10.10", Decimal("10.10"), Decimal("0.00")),
        ("10.90", Decimal("10.90"), Decimal("0.00")),
        # Ending in 1 -> 0 (-0.01 adjustment)
        ("10.01", Decimal("10.00"), Decimal("-0.01")),
        ("10.11", Decimal("10.10"), Decimal("-0.01")),
        ("10.91", Decimal("10.90"), Decimal("-0.01")),
        # Ending in 2 -> 0 (-0.02 adjustment)
        ("10.02", Decimal("10.00"), Decimal("-0.02")),
        ("10.12", Decimal("10.10"), Decimal("-0.02")),
        ("10.92", Decimal("10.90"), Decimal("-0.02")),
        # Ending in 3 -> 5 (+0.02 adjustment)
        ("10.03", Decimal("10.05"), Decimal("0.02")),
        ("10.13", Decimal("10.15"), Decimal("0.02")),
        ("10.93", Decimal("10.95"), Decimal("0.02")),
        # Ending in 4 -> 5 (+0.01 adjustment)
        ("10.04", Decimal("10.05"), Decimal("0.01")),
        ("10.14", Decimal("10.15"), Decimal("0.01")),
        ("10.94", Decimal("10.95"), Decimal("0.01")),
        # Ending in 5 -> 5 (0 adjustment)
        ("10.05", Decimal("10.05"), Decimal("0.00")),
        ("10.15", Decimal("10.15"), Decimal("0.00")),
        ("10.95", Decimal("10.95"), Decimal("0.00")),
        # Ending in 6 -> 5 (-0.01 adjustment)
        ("10.06", Decimal("10.05"), Decimal("-0.01")),
        ("10.16", Decimal("10.15"), Decimal("-0.01")),
        ("10.96", Decimal("10.95"), Decimal("-0.01")),
        # Ending in 7 -> 5 (-0.02 adjustment)
        ("10.07", Decimal("10.05"), Decimal("-0.02")),
        ("10.17", Decimal("10.15"), Decimal("-0.02")),
        ("10.97", Decimal("10.95"), Decimal("-0.02")),
        # Ending in 8 -> 10 (+0.02 adjustment)
        ("10.08", Decimal("10.10"), Decimal("0.02")),
        ("10.18", Decimal("10.20"), Decimal("0.02")),
        # Ending in 9 -> 10 (+0.01 adjustment)
        ("10.09", Decimal("10.10"), Decimal("0.01")),
        ("10.19", Decimal("10.20"), Decimal("0.01")),
    ],
)
def test_bnm_cash_rounding_all_digit_endings(raw_input, expected_rounded, expected_adj):
    """Test every single digit ending (0-9) adheres strictly to the BNM 5-cent cash rounding rule."""
    rounded = apply_bnm_cash_rounding(raw_input)
    assert rounded == expected_rounded

    adj = calculate_bnm_rounding_adjustment(raw_input)
    assert adj == expected_adj


def test_bnm_cash_rounding_dollar_boundary_rollover():
    """Test rounding rolls over the 1-dollar boundary properly (e.g. 10.98 -> 11.00)."""
    assert apply_bnm_cash_rounding("10.98") == Decimal("11.00")
    assert calculate_bnm_rounding_adjustment("10.98") == Decimal("0.02")

    assert apply_bnm_cash_rounding("10.99") == Decimal("11.00")
    assert calculate_bnm_rounding_adjustment("10.99") == Decimal("0.01")

    assert apply_bnm_cash_rounding(Decimal("999.98")) == Decimal("1000.00")
    assert apply_bnm_cash_rounding(Decimal("999.99")) == Decimal("1000.00")


def test_user_scenario_4530_15():
    """Verify specific user prompt scenario: RM 4,530.15 preserves .15 exact cents."""
    assert apply_bnm_cash_rounding(4530.15) == Decimal("4530.15")
    assert apply_bnm_cash_rounding("4530.15") == Decimal("4530.15")
    assert calculate_bnm_rounding_adjustment("4530.15") == Decimal("0.00")

    # If 4530.12 -> 4530.10
    assert apply_bnm_cash_rounding("4530.12") == Decimal("4530.10")
    assert calculate_bnm_rounding_adjustment("4530.12") == Decimal("-0.02")

    # If 4530.13 -> 4530.15
    assert apply_bnm_cash_rounding("4530.13") == Decimal("4530.15")
    assert calculate_bnm_rounding_adjustment("4530.13") == Decimal("0.02")


def test_bnm_cash_rounding_edge_cases():
    """Test None, 0, negative amounts, and float inputs."""
    assert apply_bnm_cash_rounding(None) == Decimal("0.00")
    assert apply_bnm_cash_rounding(0) == Decimal("0.00")
    assert apply_bnm_cash_rounding("0.00") == Decimal("0.00")

    # Negative bounds
    assert apply_bnm_cash_rounding("-10.02") == Decimal("-10.00")
    assert apply_bnm_cash_rounding("-10.03") == Decimal("-10.05")
    assert apply_bnm_cash_rounding("-10.08") == Decimal("-10.10")

    # Integer input
    assert apply_bnm_cash_rounding(100) == Decimal("100.00")


def test_format_currency_with_precision():
    """Test format_currency_with_precision for all modes."""
    amt = Decimal("4530.12")

    # Exact mode preserves exact cents
    assert format_currency_with_precision(amt, mode="exact") == "4,530.12"

    # BNM 5-cent mode rounds to .10
    assert format_currency_with_precision(amt, mode="rounded_5cent") == "4,530.10"

    # Whole ringgit mode rounds to 4,530.00
    assert format_currency_with_precision(amt, mode="rounded_ringgit") == "4,530.00"

    # When amount already ends in .15
    amt15 = Decimal("4530.15")
    assert format_currency_with_precision(amt15, mode="exact") == "4,530.15"
    assert format_currency_with_precision(amt15, mode="rounded_5cent") == "4,530.15"


def test_apply_whole_ringgit_rounding_ceiling():
    """Test ceiling whole ringgit rounding without cents (e.g. 1300.01 -> 1301)."""
    assert apply_whole_ringgit_rounding(Decimal("1300.01")) == Decimal("1301.00")
    assert apply_whole_ringgit_rounding(Decimal("1300.29")) == Decimal("1301.00")
    assert apply_whole_ringgit_rounding(Decimal("1300.98")) == Decimal("1301.00")
    assert apply_whole_ringgit_rounding(Decimal("1300.00")) == Decimal("1300.00")
    assert apply_whole_ringgit_rounding(0) == Decimal("0.00")
    assert apply_whole_ringgit_rounding(None) == Decimal("0.00")

    # String format without cents
    assert format_currency_with_precision(Decimal("1300.01"), mode="whole") == "1,301"
    assert format_currency_with_precision(Decimal("1300.29"), mode="whole") == "1,301"
    assert format_currency_with_precision(Decimal("1300.98"), mode="whole") == "1,301"
    assert format_currency_with_precision(Decimal("1300.00"), mode="whole") == "1,300"


