"""Pure Decimal pricing helpers for quotation benefit add-ons and premium deltas.

Guarantees single-source-of-truth idempotency:
- PDF-extracted benefits initialize `evidence_snapshot.applied_to_premium` to
  their extracted effective RM cost because the insurer's bottom Insurance
  Premium already includes them.
- Staff additions, price edits, removals, or Comparison benefit toggles apply
  exact RM deltas (`new_effective_price - applied_to_premium`) to `fields.premium`
  so Total Payable (excl. Road Tax & Runner Fee) is always identical to
  Insurance Premium with zero double-counting.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


EXTRACTED_BENEFIT_SOURCES = frozenset({
    "extracted_addon",
    "extracted_upgrade",
    "extracted_custom",
})


def parse_money_decimal(raw: Any) -> Decimal:
    """Parse scalar/dict money representations safely into a quantized Decimal('0.01')."""
    if raw is None or isinstance(raw, bool):
        return Decimal("0.00")
    val = raw
    if isinstance(raw, dict):
        val = raw.get("amount") if raw.get("amount") is not None else raw.get("value")
    if val is None or isinstance(val, bool):
        return Decimal("0.00")
    cleaned = re.sub(r"[^\d.\-]", "", str(val).replace(",", "").strip())
    if not cleaned or cleaned in {"-", ".", "-."}:
        return Decimal("0.00")
    try:
        dec = Decimal(cleaned)
        if dec < Decimal("0.00"):
            return Decimal("0.00")
        return dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")


def selection_effective_price(selection: Any, offering: Any = None) -> Decimal:
    """Return active charged RM price for a benefit selection, else Decimal('0.00')."""
    state = str(getattr(selection, "state", "") or "").lower()
    if state != "current":
        return Decimal("0.00")
    cost_status = str(getattr(selection, "cost_status", "") or "").lower()
    if cost_status in {"included", "foc"}:
        return Decimal("0.00")
    price_obj = getattr(selection, "price", None)
    if not price_obj and offering is not None and cost_status == "paid":
        price_obj = getattr(offering, "optional_price", None)
    return parse_money_decimal(price_obj)


def is_selection_included_in_premium(selection: Any) -> bool:
    """Return True when this selection's price is already reflected inside fields.premium."""
    ev = getattr(selection, "evidence_snapshot", None)
    if not isinstance(ev, dict):
        return False
    if "applied_to_premium" in ev and ev["applied_to_premium"] is not None:
        return True
    src = str(ev.get("source") or "").strip().lower()
    if src in EXTRACTED_BENEFIT_SOURCES:
        return True
    if ev.get("is_detected") is True:
        return True
    return False


def selection_applied_to_premium(selection: Any) -> Decimal:
    """Return the RM amount from this selection currently baked into fields.premium."""
    ev = getattr(selection, "evidence_snapshot", None)
    if isinstance(ev, dict) and ev.get("applied_to_premium") is not None:
        return parse_money_decimal(ev.get("applied_to_premium"))
    if is_selection_included_in_premium(selection):
        return selection_effective_price(selection)
    return Decimal("0.00")


def unapplied_selection_amount(selection: Any, offering: Any = None) -> Decimal:
    """Return any extra price on an active selection not yet folded into fields.premium."""
    effective = selection_effective_price(selection, offering=offering)
    if is_selection_included_in_premium(selection):
        applied = selection_applied_to_premium(selection)
        return max(Decimal("0.00"), (effective - applied).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return effective


def stamp_applied_to_premium(selection: Any, applied_amount: Decimal | None = None) -> None:
    """Persist applied_to_premium on selection.evidence_snapshot cleanly."""
    amt = selection_effective_price(selection) if applied_amount is None else applied_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    ev = dict(getattr(selection, "evidence_snapshot", None) or {})
    ev["applied_to_premium"] = f"{amt:.2f}"
    selection.evidence_snapshot = ev


def reconcile_selections_premium_delta(
    pre_applied: dict[str, Decimal],
    selections: list[Any],
    *,
    apply_delta: bool = True,
) -> Decimal:
    """Compute net RM change across all draft selections and stamp applied_to_premium.

    When `apply_delta` is False (e.g. Comparison explicitly overrode motor_premium),
    keeps fields.premium untouched while recording current effective prices as applied
    or zeroed accurately for future removals.
    """
    net_delta = Decimal("0.00")
    seen_ids: set[str] = set()
    for sel in selections:
        sel_id = getattr(sel, "id", None)
        if sel_id:
            seen_ids.add(sel_id)
        eff = selection_effective_price(sel)
        prev = pre_applied.get(sel_id, Decimal("0.00"))
        delta = (eff - prev).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if apply_delta and delta != Decimal("0.00"):
            net_delta += delta
        if apply_delta or delta != Decimal("0.00") or is_selection_included_in_premium(sel):
            stamp_applied_to_premium(sel, eff)
    if apply_delta:
        for sid, prev_amt in pre_applied.items():
            if sid not in seen_ids and prev_amt > Decimal("0.00"):
                net_delta -= prev_amt
    return net_delta.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
