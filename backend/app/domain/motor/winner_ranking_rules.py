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


def _entry_strengths(entry: Any) -> list[str]:
    """Extract key underwriting protection strengths for an entry."""
    strengths: list[str] = []
    if bool(getattr(entry, "agreed_value", False)) or str(getattr(entry, "valuation_type", "")).lower() == "agreed_value":
        strengths.append("Agreed Value")
    tow = str(getattr(entry, "towing_km", "") or getattr(entry, "towing_limit", "") or "").strip()
    tow_l = tow.lower()
    if "unlimited" in tow_l:
        strengths.append("Unlimited Towing")
    elif any(k in tow_l for k in ("365", "300", "500")):
        strengths.append(f"{tow} Towing")
    exc = float(getattr(entry, "excess", 0) or 0)
    if exc <= 0.0:
        strengths.append("RM 0 Excess")
    bet_rate = float(getattr(entry, "betterment_rate", 0) or 0)
    if bool(getattr(entry, "waiver_betterment", False)) or bet_rate <= 0.0:
        strengths.append("0% Betterment")
    sp = str(getattr(entry, "special_perils", "") or "").strip()
    if sp and sp.lower() not in ("", "-", "—", "none", "not included"):
        strengths.append("Flood / Special Perils")
    return strengths


def build_underwriter_ranking_explanation(
    entry: Any,
    all_visible: Sequence[Any],
    rank: int,
) -> str:
    """Generate a concise, underwriter-grade logical explanation for why an entry holds its rank."""
    visible = [e for e in all_visible if float(getattr(e, "total_payable", 0) or 0) > 0]
    if not visible:
        return "Standard comparison option."

    my_price = Decimal(str(getattr(entry, "total_payable", 0) or 0))
    cheapest = min(visible, key=lambda x: Decimal(str(getattr(x, "total_payable", 0) or 0)))
    cheapest_price = Decimal(str(getattr(cheapest, "total_payable", 0) or 0))
    delta = my_price - cheapest_price
    strengths = _entry_strengths(entry)

    if getattr(entry, "manual_rank", None) is not None and int(getattr(entry, "manual_rank", 0)) > 0:
        return f"Manual Rank #{rank} override · {', '.join(strengths[:3]) if strengths else 'Custom order'}."

    if rank == 1:
        if delta <= Decimal("0.05"):
            perk_str = f" + {', '.join(strengths[:3])}" if strengths else ""
            return f"Ranked #1 (Best Overall): Lowest payable (RM {my_price:,.2f}){perk_str}."
        cheapest_name = str(getattr(cheapest, "company_name", "lowest quote")).split()[0]
        cheapest_strengths = set(_entry_strengths(cheapest))
        extra_perks = [s for s in strengths if s not in cheapest_strengths] or strengths
        perk_reason = ", ".join(extra_perks[:3]) if extra_perks else "stronger coverage terms"
        return f"Ranked #1 (Best Value Logic): +RM {delta:,.2f} vs {cheapest_name}, chosen for {perk_reason}."

    if delta <= Decimal("0.05"):
        leader = next((x for x in visible if (getattr(x, "rank", 99) or 99) == 1), visible[0])
        leader_perks = [s for s in _entry_strengths(leader) if s not in set(strengths)]
        missing_str = f"lacks {', '.join(leader_perks[:2])}" if leader_perks else "standard terms"
        return f"Ranked #{rank} (Lowest Price): Cheapest at RM {my_price:,.2f}, but {missing_str}."

    perk_summary = ", ".join(strengths[:2]) if strengths else "Standard cover"
    return f"Ranked #{rank}: +RM {delta:,.2f} vs lowest ({perk_summary})."


def evaluate_logical_value_rerank(entries: list[Any]) -> list[Any]:
    """ logically rerank visible entries by weighing minor price deltas (<= RM 65) against tangible protection advantages."""
    visible = [e for e in entries if not getattr(e, "is_hidden", False)]
    hidden = [e for e in entries if getattr(e, "is_hidden", False)]
    if not visible:
        return entries

    manual = [e for e in visible if getattr(e, "manual_rank", None) is not None and int(e.manual_rank) > 0]
    auto = [e for e in visible if not (getattr(e, "manual_rank", None) is not None and int(e.manual_rank) > 0)]

    def risk_adjusted_score(e: Any) -> tuple[float, float]:
        price = float(getattr(e, "total_payable", 0) or 0)
        if price <= 0:
            return (float("inf"), float("inf"))
        bonus = 0.0
        if bool(getattr(e, "agreed_value", False)) or str(getattr(e, "valuation_type", "")).lower() == "agreed_value":
            bonus += 25.0
        tow_l = str(getattr(e, "towing_km", "") or getattr(e, "towing_limit", "") or "").lower()
        if "unlimited" in tow_l:
            bonus += 35.0
        elif "365" in tow_l or "500" in tow_l:
            bonus += 25.0
        exc = float(getattr(e, "excess", 0) or 0)
        if exc > 0:
            bonus -= min(exc * 0.10, 50.0)
        if bool(getattr(e, "waiver_betterment", False)) or float(getattr(e, "betterment_rate", 0) or 0) <= 0.0:
            bonus += 20.0
        sp = str(getattr(e, "special_perils", "") or "").strip().lower()
        if sp and sp not in ("", "-", "—", "none", "not included"):
            bonus += 20.0
        return (price - bonus, price)

    auto_sorted = sorted(auto, key=risk_adjusted_score)
    auto_sorted = apply_towing_advantage_rule(auto_sorted)

    used_ranks: set[int] = {int(e.manual_rank) for e in manual if e.manual_rank is not None}
    for e in manual:
        e.rank = int(e.manual_rank)

    curr = 1
    for e in auto_sorted:
        while curr in used_ranks:
            curr += 1
        e.rank = curr
        used_ranks.add(curr)
        curr += 1

    base_hidden = max(used_ranks, default=0) + 1
    for idx, e in enumerate(hidden):
        e.rank = base_hidden + idx

    all_sorted = sorted(entries, key=lambda x: getattr(x, "rank", 999) or 999)
    visible_sorted = [e for e in all_sorted if not getattr(e, "is_hidden", False)]
    for e in visible_sorted:
        reason = build_underwriter_ranking_explanation(e, visible_sorted, int(e.rank or 1))
        e.notes = reason

    return all_sorted

