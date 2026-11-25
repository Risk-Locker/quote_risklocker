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
    return any(tok in name for tok in ("AMASSURANCE", "AMGEN", "AMGENERAL", "KURNIA", "LIBERTY"))


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


def _has_betterment_waiver(entry: Any) -> bool:
    """Return True strictly when Betterment Waiver (0% co-pay) applies, never for bare 'No' / TPO."""
    if bool(getattr(entry, "waiver_betterment", False)):
        return True
    disp = str(getattr(entry, "betterment_display", "") or "").strip().lower()
    if disp in ("no", "n/a", "n/a (third party)"):
        return False
    raw_rate = getattr(entry, "betterment_rate", None)
    return raw_rate is not None and float(raw_rate) <= 0.0


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
    if _has_betterment_waiver(entry):
        strengths.append("Betterment Waiver (0%)")
    sp = str(getattr(entry, "special_perils", "") or "").strip()
    if sp and sp.lower() not in ("", "-", "—", "none", "not included"):
        strengths.append("Flood / Special Perils")
    return strengths


def _format_prev_policy_yoy_insight(
    entry: Any,
    prev_policy: dict[str, Any] | None,
) -> str:
    """Build a crisp year-over-year comparative insight against the previous policy."""
    if not isinstance(prev_policy, dict) or not prev_policy:
        return ""
    prev_prem = float(prev_policy.get("insurance_premium") or 0.0)
    prev_tot = float(prev_policy.get("total_payable") or 0.0)
    if prev_prem <= 0.0 and prev_tot <= 0.0:
        return ""

    curr_prem = float(getattr(entry, "motor_premium", 0) or 0.0)
    curr_tot = float(getattr(entry, "total_payable", 0) or 0.0)
    prev_si = float(prev_policy.get("sum_insured") or 0.0)
    curr_si = float(getattr(entry, "sum_insured", 0) or 0.0)

    # Prefer Total Payable comparison when both totals exist, otherwise Motor Premium
    if prev_tot > 0.0 and curr_tot > 0.0:
        tot_delta = curr_tot - prev_tot
        prem_delta = (curr_prem - prev_prem) if prev_prem > 0 else tot_delta
        if abs(tot_delta) < 0.50:
            delta_head = f"Same total as last year (RM {prev_tot:,.2f})"
        elif tot_delta > 0:
            delta_head = f"+RM {tot_delta:,.2f} vs last year (RM {prev_tot:,.2f})"
            if prev_prem > 0 and abs(prem_delta - tot_delta) >= 1.0:
                delta_head += f", motor {'+' if prem_delta >= 0 else '-'}RM {abs(prem_delta):,.2f}"
        else:
            delta_head = f"RM {abs(tot_delta):,.2f} cheaper vs last year (RM {prev_tot:,.2f})"
    elif prev_prem > 0.0 and curr_prem > 0.0:
        prem_delta = curr_prem - prev_prem
        if abs(prem_delta) < 0.50:
            delta_head = f"Same motor premium as last year (RM {prev_prem:,.2f})"
        elif prem_delta > 0:
            delta_head = f"+RM {prem_delta:,.2f} motor vs last year (RM {prev_prem:,.2f})"
        else:
            delta_head = f"RM {abs(prem_delta):,.2f} lower motor vs last year (RM {prev_prem:,.2f})"
    else:
        return ""

    reasons: list[str] = []
    benefits: list[str] = []

    prev_ws = float(prev_policy.get("windscreen") or 0.0)
    curr_ws = float(getattr(entry, "windscreen_sum_insured", 0) or 0.0)
    if curr_ws > 0.0 and prev_ws <= 0.0:
        reasons.append(f"added RM {curr_ws:,.0f} Windscreen")
        benefits.append("Windscreen cover")
    elif curr_ws <= 0.0 and prev_ws > 0.0:
        reasons.append(f"removed RM {prev_ws:,.0f} Windscreen")
    elif curr_ws > 0.0 and prev_ws > 0.0 and abs(curr_ws - prev_ws) >= 100.0:
        reasons.append(f"Windscreen RM {prev_ws:,.0f}→RM {curr_ws:,.0f}")

    def _has_cover(v: Any) -> bool:
        s = str(v or "").strip().lower()
        return bool(s and s not in {"", "-", "—", "none", "nil", "no", "not included", "not covered", "tiada"})

    prev_sp = _has_cover(prev_policy.get("special_perils")) or ("special perils" in str(prev_policy.get("perils") or "").lower())
    curr_sp = _has_cover(getattr(entry, "special_perils", None))
    if curr_sp and not prev_sp:
        reasons.append("added Special Perils (Flood)")
        benefits.append("Flood cover")
    elif prev_sp and not curr_sp:
        reasons.append("removed Special Perils")

    prev_llp = _has_cover(prev_policy.get("llp_llop")) or ("llp" in str(prev_policy.get("perils") or "").lower())
    curr_llp = _has_cover(getattr(entry, "llp_llop", None))
    if curr_llp and not prev_llp:
        reasons.append("added LLP/LLOP")

    prev_ea = {k for k, v in (prev_policy.get("extra_addons") or {}).items() if str(v).lower() == "yes"}
    curr_ea = {k for k, v in (getattr(entry, "extra_addons", None) or {}).items() if str(v).lower() == "yes"}
    added_ea = sorted(curr_ea - prev_ea)
    if added_ea:
        pretty_ea = [k.replace("_", " ").title() for k in added_ea[:2]]
        reasons.append(f"added {', '.join(pretty_ea)}")

    if prev_si > 0.0 and curr_si > 0.0:
        si_diff = curr_si - prev_si
        if abs(si_diff) >= 500.0:
            sign = "+" if si_diff > 0 else "-"
            reasons.append(f"Sum Insured {sign}RM {abs(si_diff):,.0f}")

    prev_agreed = prev_policy.get("agreed_value")
    curr_agreed = bool(getattr(entry, "agreed_value", False)) or str(getattr(entry, "valuation_type", "")).lower() == "agreed_value"
    if prev_agreed is False and curr_agreed:
        benefits.append("upgraded to Agreed Value")
    elif curr_agreed:
        benefits.append("keeps Agreed Value")

    prev_tow = str(prev_policy.get("towing") or "").lower()
    curr_tow = str(getattr(entry, "towing_km", "") or getattr(entry, "towing_limit", "") or "").strip()
    if "unlimited" in curr_tow.lower() and "unlimited" not in prev_tow:
        benefits.append("upgraded to Unlimited Towing")

    if _has_betterment_waiver(entry):
        if prev_policy.get("waiver_betterment") is False:
            benefits.append("Betterment Waiver (0%)")

    if reasons and benefits:
        return f"Vs Last Year: {delta_head} due to {', '.join(reasons[:2])}; {'; '.join(benefits[:2])}."
    if reasons:
        return f"Vs Last Year: {delta_head} due to {', '.join(reasons[:3])}."
    if benefits:
        return f"Vs Last Year: {delta_head} ({', '.join(benefits[:2])})."
    return f"Vs Last Year: {delta_head} under comparable terms."


def build_underwriter_ranking_explanation(
    entry: Any,
    all_visible: Sequence[Any],
    rank: int,
    prev_policy: dict[str, Any] | None = None,
) -> str:
    """Generate an insightful underwriter-grade explanation covering peer rank and YoY change vs previous policy."""
    visible = [e for e in all_visible if float(getattr(e, "total_payable", 0) or 0) > 0]
    if not visible:
        return "Standard comparison option."

    my_price = Decimal(str(getattr(entry, "total_payable", 0) or 0))
    cheapest = min(visible, key=lambda x: Decimal(str(getattr(x, "total_payable", 0) or 0)))
    cheapest_price = Decimal(str(getattr(cheapest, "total_payable", 0) or 0))
    delta = my_price - cheapest_price
    strengths = _entry_strengths(entry)
    leader = next((x for x in visible if (getattr(x, "rank", 99) or 99) == 1), visible[0])
    leader_name = str(getattr(leader, "company_name", "Rank #1") or "Rank #1").split()[0]

    if getattr(entry, "manual_rank", None) is not None and int(getattr(entry, "manual_rank", 0)) > 0:
        peer_line = f"Manual Rank #{rank} · {', '.join(strengths[:3]) if strengths else 'Custom selection'}."
    elif rank == 1:
        if delta <= Decimal("0.05"):
            perk_str = f" with {', '.join(strengths[:3])}" if strengths else ""
            peer_line = f"Ranked #1 (Best Overall): Lowest payable at RM {my_price:,.2f}{perk_str}."
        else:
            cheapest_name = str(getattr(cheapest, "company_name", "lowest quote")).split()[0]
            cheapest_strengths = set(_entry_strengths(cheapest))
            extra_perks = [s for s in strengths if s not in cheapest_strengths] or strengths
            perk_reason = ", ".join(extra_perks[:3]) if extra_perks else "stronger coverage terms"
            peer_line = f"Ranked #1 (Best Value Logic): +RM {delta:,.2f} vs {cheapest_name}, winning on {perk_reason}."
    elif delta <= Decimal("0.05"):
        leader_perks = [s for s in _entry_strengths(leader) if s not in set(strengths)]
        missing_str = f"lacks {', '.join(leader_perks[:2])}" if leader_perks else "narrower terms"
        peer_line = f"Ranked #{rank} (Lowest Price): RM {my_price:,.2f}, behind {leader_name} as it {missing_str}."
    else:
        leader_strengths = _entry_strengths(leader)
        missing_vs_leader = [s for s in leader_strengths if s not in set(strengths)]
        my_unique = [s for s in strengths if s not in set(leader_strengths)]
        detail_parts: list[str] = []
        if my_unique:
            detail_parts.append(f"includes {', '.join(my_unique[:2])}")
        elif strengths:
            detail_parts.append(", ".join(strengths[:2]))
        if missing_vs_leader:
            detail_parts.append(f"lacks {', '.join(missing_vs_leader[:1])}")
        detail_txt = f" ({'; '.join(detail_parts)})" if detail_parts else ""
        peer_line = f"Ranked #{rank}: +RM {delta:,.2f} vs lowest{detail_txt}."

    yoy_line = _format_prev_policy_yoy_insight(entry, prev_policy)
    return f"{peer_line}\n{yoy_line}" if yoy_line else peer_line


def evaluate_logical_value_rerank(
    entries: list[Any],
    prev_policy: dict[str, Any] | None = None,
) -> list[Any]:
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
        if _has_betterment_waiver(e):
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
        reason = build_underwriter_ranking_explanation(e, visible_sorted, int(e.rank or 1), prev_policy=prev_policy)
        e.notes = reason

    return all_sorted

