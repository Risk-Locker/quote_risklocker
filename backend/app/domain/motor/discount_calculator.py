"""Deterministic Decimal math for Motor Insurance percentage & flat discounts.

Discounts apply strictly to the Motor Insurance premium (excluding Road Tax and
Runner Fee), and Net Total Payable is computed as:
  max(0, gross_motor_premium - effective_discount + road_tax + runner_fee)
where for percentage-only discounts (0..100%),
  net_motor_premium = gross_motor_premium - pct_discount_amount
  net_total_payable = net_motor_premium + road_tax + runner_fee
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from typing import Any

_ZERO = Decimal("0.00")
_HUNDRED = Decimal("100.00")
_CENT = Decimal("0.01")


def to_decimal_clean(value: Any, default: Decimal = _ZERO) -> Decimal:
    """Parse numeric/currency strings safely to Decimal."""
    if value is None or value == "":
        return default
    if isinstance(value, dict):
        value = value.get("value")
        if value is None or value == "":
            return default
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return default
    cleaned = re.sub(r"[^\d.-]", "", str(value).strip())
    if not cleaned or cleaned in {"-", "."}:
        return default
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return default


def clamp_discount_pct(raw_pct: Any) -> Decimal:
    """Clamp percentage discount to [0.00, 100.00] quantized to 2 decimals."""
    pct = to_decimal_clean(raw_pct, _ZERO)
    if pct < _ZERO:
        pct = _ZERO
    if pct > _HUNDRED:
        pct = _HUNDRED
    return pct.quantize(_CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class MotorDiscountBreakdown:
    gross_motor_premium: Decimal
    motor_discount_pct: Decimal
    pct_discount_amount: Decimal
    flat_discount_amount: Decimal
    effective_discount: Decimal
    net_motor_premium: Decimal

    def net_total_payable(self, road_tax: Any = _ZERO, runner_fee: Any = _ZERO) -> Decimal:
        rt = max(_ZERO, to_decimal_clean(road_tax, _ZERO)).quantize(_CENT, rounding=ROUND_HALF_UP)
        rf = max(_ZERO, to_decimal_clean(runner_fee, _ZERO)).quantize(_CENT, rounding=ROUND_HALF_UP)
        gross_total = self.gross_motor_premium + rt + rf
        return max(_ZERO, (gross_total - self.effective_discount).quantize(_CENT, rounding=ROUND_HALF_UP))


def calculate_motor_discount(
    motor_premium: Any,
    motor_discount_pct: Any = _ZERO,
    flat_discount: Any = _ZERO,
) -> MotorDiscountBreakdown:
    """Compute exact Decimal motor discount breakdown using ROUND_HALF_UP."""
    gross_mp = max(_ZERO, to_decimal_clean(motor_premium, _ZERO)).quantize(_CENT, rounding=ROUND_HALF_UP)
    pct = clamp_discount_pct(motor_discount_pct)
    pct_amt = (gross_mp * pct / _HUNDRED).quantize(_CENT, rounding=ROUND_HALF_UP)
    flat_amt = max(_ZERO, to_decimal_clean(flat_discount, _ZERO)).quantize(_CENT, rounding=ROUND_HALF_UP)
    eff_disc = (pct_amt + flat_amt).quantize(_CENT, rounding=ROUND_HALF_UP)
    net_mp = max(_ZERO, (gross_mp - eff_disc).quantize(_CENT, rounding=ROUND_HALF_UP))
    return MotorDiscountBreakdown(
        gross_motor_premium=gross_mp,
        motor_discount_pct=pct,
        pct_discount_amount=pct_amt,
        flat_discount_amount=flat_amt,
        effective_discount=eff_disc,
        net_motor_premium=net_mp,
    )
