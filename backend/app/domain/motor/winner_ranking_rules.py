"""Winner ranking domain rules for Malaysian motor comparison.

Implements domain-specific actuarial advantage adjustments:
- STMB vs Amgen RM 40 Towing Rule:
  When STMB is lowest price, but AmAssurance/Amgen has 365 km towing and its
  total payable is within RM 40.00 of STMB, promote Amgen as recommended winner.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Sequence

MAX_AMGEN_TOWING_DELTA = Decimal("40.00")


def _is_stmb(company_name: str | None) -> bool:
    name = (company_name or "").upper()
    return "STMB" in name or "TAKAFUL MALAYSIA" in name


def _is_amgen(company_name: str | None) -> bool:
    name = (company_name or "").upper()
    return "AMASSURANCE" in name or "AMGEN" in name or "AMGENERAL" in name


def _has_365km_towing(entry: Any) -> bool:
    towing = str(getattr(entry, "towing_km", "") or getattr(entry, "towing_limit", "")).lower()
    return "365" in towing


def apply_towing_advantage_rule(entries: Sequence[Any]) -> list[Any]:
    """Applies the STMB vs Amgen RM 40 towing-advantage ranking rule.

    If STMB is the lowest-priced candidate but an AmAssurance/Amgen quote with
    365km towing is within RM 40.00, Amgen is promoted to Rank #1.
    """
    if not entries or len(entries) < 2:
        return list(entries)

    items = list(entries)

    # Find the lowest-priced valid STMB entry
    stmb_idx = -1
    for idx, e in enumerate(items):
        if _is_stmb(getattr(e, "company_name", None)):
            stmb_idx = idx
            break

    # If STMB is not the leader or not present, no advantage swap needed
    if stmb_idx != 0:
        return items

    stmb_entry = items[0]
    stmb_price = Decimal(str(getattr(stmb_entry, "total_payable", 0) or 0))
    if stmb_price <= 0:
        return items

    # Look for an Amgen candidate with 365km towing
    amgen_idx = -1
    for idx in range(1, len(items)):
        candidate = items[idx]
        if _is_amgen(getattr(candidate, "company_name", None)) and _has_365km_towing(candidate):
            amgen_idx = idx
            break

    if amgen_idx == -1:
        return items

    amgen_entry = items[amgen_idx]
    amgen_price = Decimal(str(getattr(amgen_entry, "total_payable", 0) or 0))

    delta = amgen_price - stmb_price
    if Decimal("0.00") <= delta <= MAX_AMGEN_TOWING_DELTA:
        # Promote Amgen over STMB
        amgen_entry.rank = 1
        amgen_entry.is_recommended = True
        if hasattr(amgen_entry, "recommendation_reason"):
            amgen_entry.recommendation_reason = "Best Value: 365km Towing (within RM 40 difference)"
        if hasattr(amgen_entry, "notes"):
            amgen_entry.notes = "Best Value: 365km Towing (within RM 40 difference)"

        stmb_entry.rank = 2
        stmb_entry.is_recommended = False

        # Reorder list: pop amgen and insert at index 0
        items.pop(amgen_idx)
        items.insert(0, amgen_entry)

    return items

