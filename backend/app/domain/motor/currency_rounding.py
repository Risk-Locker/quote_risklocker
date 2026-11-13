"""Bank Negara Malaysia (BNM) Cash Rounding Engine.

Authoritative domain engine for 5-cent cash rounding mechanism mandated by
Bank Negara Malaysia for consumer financial transactions and cash settlement.

Rounding Rules (applies to the 1-cent digit):
- 1, 2 cents -> Round down to nearest 0 cents (-1¢ / -2¢)
- 3, 4 cents -> Round up to 5 cents (+2¢ / +1¢)
- 5 cents    -> Stays at 5 cents (0¢)
- 6, 7 cents -> Round down to 5 cents (-1¢ / -2¢)
- 8, 9 cents -> Round up to nearest 10 cents (+2¢ / +1¢)
- 0 cents    -> Stays at 0 cents (0¢)

All calculations are strictly performed using Python `decimal.Decimal`
with integer arithmetic on quantized cents to eliminate IEEE 754 float drift.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING
from typing import Literal, Union

# Cent quantization template (2 decimal places)
_CENT_QUANTUM = Decimal("0.01")

# BNM 5-cent delta mapping for digit (0-9)
_BNM_DELTA_MAP: dict[int, int] = {
    0: 0,
    1: -1,
    2: -2,
    3: 2,
    4: 1,
    5: 0,
    6: -1,
    7: -2,
    8: 2,
    9: 1,
}

NumericType = Union[Decimal, str, int, float]


def _to_decimal(val: NumericType | None) -> Decimal:
    """Safely convert any numeric input to a 2-decimal quantized Decimal."""
    if val is None:
        return Decimal("0.00")
    if isinstance(val, Decimal):
        return val.quantize(_CENT_QUANTUM, rounding=ROUND_HALF_UP)
    # Convert via str to avoid binary float artifacts
    return Decimal(str(val)).quantize(_CENT_QUANTUM, rounding=ROUND_HALF_UP)


def apply_bnm_cash_rounding(amount: NumericType | None) -> Decimal:
    """Apply Bank Negara Malaysia (BNM) 5-cent cash rounding.

    Args:
        amount: Monetary amount in MYR (Decimal, str, int, float, or None).

    Returns:
        Decimal quantized to 2 decimal places ending in .x0 or .x5.
    """
    dec = _to_decimal(amount)
    total_cents = int((dec * 100).to_integral_value(rounding=ROUND_HALF_UP))

    if total_cents == 0:
        return Decimal("0.00")

    is_negative = total_cents < 0
    abs_cents = abs(total_cents)
    last_digit = abs_cents % 10

    delta = _BNM_DELTA_MAP[last_digit]
    rounded_abs_cents = abs_cents + delta
    final_cents = -rounded_abs_cents if is_negative else rounded_abs_cents

    return (Decimal(final_cents) / Decimal(100)).quantize(_CENT_QUANTUM)


def apply_whole_ringgit_rounding(amount: NumericType | None) -> Decimal:
    """Round up to the nearest whole Ringgit (ceiling integer).

    Examples:
        1300.01 -> 1301.00
        1300.29 -> 1301.00
        1300.98 -> 1301.00
        1300.00 -> 1300.00
    """
    dec = _to_decimal(amount)
    if dec == Decimal("0.00"):
        return Decimal("0.00")
    return dec.to_integral_value(rounding=ROUND_CEILING).quantize(_CENT_QUANTUM)


def calculate_bnm_rounding_adjustment(amount: NumericType | None) -> Decimal:
    """Calculate the BNM rounding adjustment (delta between rounded and exact amount).

    Positive delta represents rounding up; negative delta represents rounding down.
    Equation: adjustment = rounded_amount - exact_amount
    """
    exact = _to_decimal(amount)
    rounded = apply_bnm_cash_rounding(exact)
    return (rounded - exact).quantize(_CENT_QUANTUM)


def format_currency_with_precision(
    amount: NumericType | None,
    mode: Literal["exact", "rounded_5cent", "rounded_ringgit", "whole_ringgit", "whole"] = "exact",
) -> str:
    """Format currency in MYR with Malaysian comma separation and selected precision.

    Args:
        amount: Monetary value in MYR.
        mode:
            - 'exact': 2 decimal places preserved (e.g. "4,530.15", "4,530.12").
            - 'rounded_5cent': 5¢ cash rounded (e.g. "4,530.15", "4,530.10").
            - 'whole_ringgit' / 'whole': Whole ringgit rounded up without cents (e.g. "1,301").
            - 'rounded_ringgit': Whole ringgit rounded with .00 (e.g. "4,530.00").

    Returns:
        Formatted string (e.g. "4,530.15" or "1,301").
    """
    exact = _to_decimal(amount)
    if mode == "rounded_5cent":
        target = apply_bnm_cash_rounding(exact)
        return f"{target:,.2f}"
    elif mode in ("whole_ringgit", "whole"):
        target = apply_whole_ringgit_rounding(exact)
        return f"{int(target):,}"
    elif mode == "rounded_ringgit":
        target = Decimal(int((exact).to_integral_value(rounding=ROUND_HALF_UP))).quantize(_CENT_QUANTUM)
        return f"{target:,.2f}"
    else:
        return f"{exact:,.2f}"

