"""Canonical Unit Tests for BNM Currency Rounding Engine."""

from decimal import Decimal
from app.domain.motor.currency_rounding import (
    apply_bnm_cash_rounding,
    calculate_bnm_rounding_adjustment,
    format_currency_with_precision,
)


def test_bnm_rounding_unit_suite():
    # Endings
    assert apply_bnm_cash_rounding("100.01") == Decimal("100.00")
    assert apply_bnm_cash_rounding("100.02") == Decimal("100.00")
    assert apply_bnm_cash_rounding("100.03") == Decimal("100.05")
    assert apply_bnm_cash_rounding("100.04") == Decimal("100.05")
    assert apply_bnm_cash_rounding("100.05") == Decimal("100.05")
    assert apply_bnm_cash_rounding("100.06") == Decimal("100.05")
    assert apply_bnm_cash_rounding("100.07") == Decimal("100.05")
    assert apply_bnm_cash_rounding("100.08") == Decimal("100.10")
    assert apply_bnm_cash_rounding("100.09") == Decimal("100.10")
    assert apply_bnm_cash_rounding("100.00") == Decimal("100.00")

    # Formatting
    assert format_currency_with_precision("1234567.89", mode="exact") == "1,234,567.89"
    assert format_currency_with_precision("1234567.89", mode="rounded_5cent") == "1,234,567.90"

