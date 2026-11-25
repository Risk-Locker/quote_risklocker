"""NCD Evaluation, Betterment Scale, and Ranking Rules for Marketing Comparison."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app.models.tables import TenureComparisonEntry

# Malaysian Private Car NCD Rate Scale (ordered 1st year to 6th+ year max)
NCD_RATE_SCALE = [0.0, 25.0, 30.0, 38.33, 45.0, 55.0]
COMMERCIAL_NCD_SCALE = [0.0, 15.0, 20.0, 25.0]


def calculate_ncd_pair(
    ncd_value: float | None, is_commercial: bool = False
) -> tuple[float | None, float | None]:
    """Calculate (current_ncd, next_ncd) according to Malaysian PIAM NCD Rate Scale.

    Private Car scale:
    0% (1st Yr) -> 25% (2nd Yr) -> 30% (3rd Yr) -> 38.33% (4th Yr) -> 45% (5th Yr) -> 55% (6th+ Yr max).

    Commercial / Motorcycle scale:
    0% (1st Yr) -> 15% (2nd Yr) -> 20% (3rd Yr) -> 25% (4th+ Yr max).

    The PDF quotation displays the active policy term's NCD (current_ncd).
    The upcoming renewal tenure's NCD (next_ncd) advances to the next step, or stays at the max cap (55% or 25%).
    """
    if ncd_value is None:
        return None, None
    try:
        val = float(ncd_value)
    except (ValueError, TypeError):
        return None, None

    if val < 0.0:
        return None, None

    scale = COMMERCIAL_NCD_SCALE if is_commercial else NCD_RATE_SCALE

    # Find closest tier in scale
    best_idx = 0
    min_diff = float("inf")
    for idx, tier in enumerate(scale):
        diff = abs(tier - val)
        if diff < min_diff:
            min_diff = diff
            best_idx = idx

    current_ncd = scale[best_idx]
    next_idx = min(len(scale) - 1, best_idx + 1)
    next_ncd = scale[next_idx]
    return current_ncd, next_ncd


def calculate_vehicle_age(
    manufacture_year: int | None, coverage_start_date: datetime | str | None
) -> int:
    """Calculate vehicle age in completed years anchored on registration/manufacture date.

    Uses exact completed calendar years via dateutil.relativedelta. A vehicle aged
    9 years 11 months 29 days is strictly 9 completed years, NOT 10 years.
    """
    if not manufacture_year or manufacture_year <= 1900:
        return 0
    from app.domain.betterment_engine import calculate_exact_vehicle_age
    from datetime import date

    reg_date = date(manufacture_year, 1, 1)
    return calculate_exact_vehicle_age(reg_date, coverage_start_date)


def format_betterment_waiver_display(
    waiver_betterment: bool,
    betterment_rate: float | None,
    *,
    bare_no: bool = False,
) -> str:
    """Format Betterment Waiver display label using customer-intuitive polarity.

    - Waived / Exempt (0% co-payment): 'Yes (0%)'
    - Co-payment applies (15%..40%): 'No (15%)' .. 'No (40%)'
    - Not applicable / TPO / TPFT / manual bare No: 'No'
    """
    if waiver_betterment:
        return "Yes (0%)"
    if bare_no or betterment_rate is None:
        return "No"
    r = round(float(betterment_rate), 2)
    if r <= 0.0:
        return "No"
    fmt = int(r) if float(r).is_integer() else r
    return f"No ({fmt}%)"


def normalize_betterment_display(
    raw_display: str | None,
    waiver_betterment: bool,
    betterment_rate: float | None,
) -> str:
    """Normalize legacy DB betterment_display strings into Yes (0%) / No (X%) / No."""
    txt = str(raw_display or "").strip()
    low = txt.lower()
    if not txt:
        return format_betterment_waiver_display(waiver_betterment, betterment_rate)
    if low in ("no (0%)", "yes (0%)"):
        return "Yes (0%)"
    if low in ("n/a (third party)", "n/a", "no"):
        return "No"
    m_legacy_pct = re.match(r"^yes\s*\((\d+(?:\.\d+)?)%\)$", txt, re.IGNORECASE)
    if m_legacy_pct and float(m_legacy_pct.group(1)) > 0.0:
        return f"No ({m_legacy_pct.group(1)}%)"
    if low == "yes":
        return format_betterment_waiver_display(False, betterment_rate)
    return txt


def get_standard_betterment_rate(age_in_years: int) -> tuple[float, str]:
    """Calculate Malaysian Tariff standard scale for Betterment Waiver status:
    < 5 years: 0% ("Yes (0%)")
    5 years: 15% ("No (15%)")
    6 years: 20% ("No (20%)")
    7 years: 25% ("No (25%)")
    8 years: 30% ("No (30%)")
    9 years: 35% ("No (35%)")
    >= 10 years: 40% ("No (40%)")
    """
    if age_in_years < 5:
        return 0.0, "Yes (0%)"
    elif age_in_years == 5:
        return 15.0, "No (15%)"
    elif age_in_years == 6:
        return 20.0, "No (20%)"
    elif age_in_years == 7:
        return 25.0, "No (25%)"
    elif age_in_years == 8:
        return 30.0, "No (30%)"
    elif age_in_years == 9:
        return 35.0, "No (35%)"
    else:  # >= 10
        return 40.0, "No (40%)"


def check_has_betterment_peril(
    f: dict | None = None, combined_text: str = "", raw_w: Any = None
) -> bool:
    """Check if quotation draft fields, perils, or benefit selections include betterment benefits/riders."""
    if raw_w is not None:
        if str(raw_w).strip().lower() in ("true", "yes", "1"):
            return True
        if str(raw_w).strip().lower() in ("false", "no", "0"):
            return False

    txt = (combined_text or "").lower()
    if f and isinstance(f, dict):
        txt += " " + " ".join(str(v) for v in f.values()).lower()

    keywords = (
        "waiver of betterment",
        "betterment waiver",
        "car spare parts waiver",
        "spare parts waiver",
        "waiver for betterment",
        "waiver of betterment contribution",
        "exemption of betterment",
        "betterment",
    )
    return any(k in txt for k in keywords)


def evaluate_betterment_rules(
    yom: int | None,
    quote_year: int | None,
    company_name: str | None = None,
    has_betterment_peril: bool = False,
    is_comprehensive_private: bool = True,
    registration_date: Any = None,
    coverage_start_date: Any = None,
    coverage_type: str | None = None,
    company_obj: Any = None,
) -> tuple[bool, float | None, str]:
    """Evaluate Betterment Waiver and Betterment Co-Payment Rate based on DB underwriting rules.

    Uses exact completed calendar years via calculate_exact_vehicle_age when registration_date is available,
    or completed years (`quote_y - veh_yom`) without off-by-1 thresholds when only YOM is provided.
    Third Party (TPO) and Third Party Fire & Theft (TPFT) policies do not cover Own Damage collision
    repair, so Betterment Waiver is strictly 'No' with rate=None.
    """
    from app.domain.betterment_engine import calculate_exact_vehicle_age
    from app.services.marketing_comparison.company_rules import resolve_company_betterment_rule

    cov_raw = str(coverage_type or "").strip().lower()
    cov_clean = re.sub(
        r"\bcomprehensive\b(?=\s+(?:lite|plus)\s*\(\s*(?:tpft|tpo|third\s+party))",
        "",
        cov_raw,
        flags=re.IGNORECASE,
    ).strip()
    is_non_od_third_party = cov_clean in {
        "third party",
        "tpo",
        "tp",
        "third_party",
        "third party only",
        "tpft",
        "third_party_fire_theft",
    } or any(
        k in cov_clean
        for k in ("third party", "third_party", "tpo", "tpft", "fire & theft", "fire and theft")
    )

    auto_waive, max_waiver_years, _ = resolve_company_betterment_rule(
        company_name=company_name,
        company_obj=company_obj,
    )
    if is_non_od_third_party or (max_waiver_years <= 0 and not auto_waive):
        return False, None, "No"

    quote_y = quote_year or datetime.now().year
    veh_yom = yom if (yom and yom > 1900) else None

    if registration_date:
        veh_age = calculate_exact_vehicle_age(registration_date, coverage_start_date or f"{quote_y}-01-01")
        is_under_5 = veh_age < 5
        within_waiver_cap = veh_age < max_waiver_years
    elif veh_yom:
        veh_age = max(0, quote_y - veh_yom)
        is_under_5 = veh_age < 5
        within_waiver_cap = veh_age < max_waiver_years
    else:
        veh_age = 0
        is_under_5 = False
        within_waiver_cap = True  # Unknown age: honor insurer waiver cap if peril added

    # 1st Condition: Vehicles under 5 completed years are exempt from betterment co-payment (0%)
    if is_under_5:
        return True, 0.0, "Yes (0%)"

    # 2nd Condition: Insurers with automatic waiver (e.g. QBE Comprehensive Private up to 10 completed years)
    if auto_waive and is_comprehensive_private:
        if (registration_date or veh_yom) and within_waiver_cap:
            return True, 0.0, "Yes (0%)"
        rate, disp = get_standard_betterment_rate(veh_age)
        return False, rate, disp

    # 3rd Condition: Non-auto-waive insurers require betterment peril/endorsement
    if not has_betterment_peril:
        rate, disp = get_standard_betterment_rate(veh_age)
        return False, rate, disp

    if within_waiver_cap:
        return True, 0.0, "Yes (0%)"
    rate, disp = get_standard_betterment_rate(veh_age)
    return False, rate, disp


def calculate_betterment_rate(
    age_in_years: int, company_name: str | None = None, company_obj: Any = None,
) -> tuple[float, str]:
    """Backward-compatible helper returning standard or auto-waive insurer betterment rate."""
    from app.services.marketing_comparison.company_rules import resolve_company_betterment_rule

    auto_waive, max_years, _ = resolve_company_betterment_rule(company_name=company_name, company_obj=company_obj)
    if auto_waive and age_in_years <= max_years:
        return 0.0, "Yes (0%)"
    return get_standard_betterment_rate(age_in_years)


from app.domain.motor.towing_matrix import resolve_towing_entitlement
from app.domain.motor.winner_ranking_rules import apply_towing_advantage_rule


def normalize_towing_km(raw_towing: Any, combined_text: str = "", company_name: str | None = None) -> str:
    """Normalize towing benefit into authoritative Malaysian towing entitlement (RM, km, or Unlimited)."""
    val_str = str(raw_towing or "").strip()
    if re.search(
        r"(?i)(?<!\d)0(?:\.0+)?\s*km\b|\b(?:no towing|without towing|not included|tiada|nil)\b|^(?:none|no|0(?:\.0+)?|(?:rm|myr)\s*0(?:\.0+)?)$",
        val_str,
    ):
        return "No towing"

    # Preserve explicit Unlimited (or specific driver plan unlimited tiers)
    if val_str and "unlimited" in val_str.lower():
        return val_str if re.search(r"plan\s*\d+", val_str, re.IGNORECASE) else "Unlimited"

    # Preserve explicit user-entered RM or KM caps verbatim cleanly (e.g. RM 100, RM 400, 50 km, 100 km)
    m_explicit_rm = re.match(r"^(?:rm|myr)\s*([\d,]+(?:\.\d{1,2})?)$", val_str, re.IGNORECASE)
    if m_explicit_rm:
        amt = float(m_explicit_rm.group(1).replace(",", ""))
        return f"RM {int(amt):,}" if amt.is_integer() else f"RM {amt:,.2f}"

    m_explicit_km = re.match(r"^(\d+(?:\.\d+)?)\s*(?:km|kilomet(?:er|re)s?)$", val_str, re.IGNORECASE)
    if m_explicit_km:
        km_f = float(m_explicit_km.group(1))
        return f"{int(km_f)} km" if km_f.is_integer() else f"{km_f} km"

    m_raw_num = re.match(r"^(\d+)$", val_str)
    if m_raw_num:
        val = int(m_raw_num.group(1))
        comp_l = (company_name or "").lower()
        if val in (100, 200, 300, 400, 500, 600) and any(c in comp_l for c in ("qbe", "lonpac", "sompo", "tune")):
            return f"RM {val}"
        return f"{val} km"

    entitlement = resolve_towing_entitlement(
        company_name=company_name,
        package_or_rider=val_str,
        raw_document_text=combined_text,
    )
    return entitlement.formatted


def _towing_sort_value(towing_str: str | None) -> float:
    """Sort helper for towing distance: higher is better (negative for ASC sort)."""
    s = (towing_str or "").lower().strip()
    if "unlimited" in s:
        return -999999.0
    s_clean = s.replace(",", "")
    m = re.search(r"(\d+)", s_clean)
    if m:
        num = float(m.group(1))
        if "rm" in s:
            num = num * 0.5
        return -num
    return 0.0


def rank_comparison_entries(
    entries: list[TenureComparisonEntry],
    explicit_winning_company_id: str | None = None,
    explicit_winning_ref: str | None = None,
    auto_recommend_rank1: bool = True,
) -> list[TenureComparisonEntry]:
    """Rank entries using the 4-tier Best Deal criteria, respecting manual_rank and is_hidden:
    1. total_payable ASC (lowest premium)
    2. excess ASC (lower excess)
    3. betterment_rate ASC (lower co-pay)
    4. towing distance DESC (higher towing km)
    """
    visible_entries = [e for e in entries if not getattr(e, "is_hidden", False)]
    hidden_entries = [e for e in entries if getattr(e, "is_hidden", False)]

    manual_ranked = [
        e for e in visible_entries if e.manual_rank is not None and e.manual_rank > 0
    ]
    auto_ranked = [
        e for e in visible_entries if e.manual_rank is None or e.manual_rank <= 0
    ]

    def sort_key(e: TenureComparisonEntry):
        tot = float(e.total_payable) if e.total_payable else float("inf")
        if tot <= 0.0:
            tot = float("inf")
        exc = float(e.excess) if e.excess is not None else 0.0
        bet = 0.0 if bool(getattr(e, "waiver_betterment", False)) else (
            float(e.betterment_rate) if e.betterment_rate is not None else 100.0
        )
        tow = _towing_sort_value(e.towing_km or e.towing_limit)
        return (tot, exc, bet, tow)

    auto_sorted = sorted(auto_ranked, key=sort_key)
    auto_sorted = apply_towing_advantage_rule(auto_sorted)

    used_ranks: set[int] = {
        e.manual_rank for e in manual_ranked if e.manual_rank is not None
    }
    for e in manual_ranked:
        e.rank = e.manual_rank

    curr_rank = 1
    for e in auto_sorted:
        while curr_rank in used_ranks:
            curr_rank += 1
        e.rank = curr_rank
        used_ranks.add(curr_rank)
        curr_rank += 1

    base_hidden_rank = max(used_ranks, default=0) + 1
    for idx, e in enumerate(hidden_entries):
        e.rank = base_hidden_rank + idx

    all_sorted = sorted(entries, key=lambda x: x.rank or 999)

    has_explicit_winners = any(e.is_recommended for e in visible_entries)
    if explicit_winning_company_id or explicit_winning_ref:
        for e in visible_entries:
            if explicit_winning_company_id and e.company_id == explicit_winning_company_id:
                e.is_recommended = True
            elif explicit_winning_ref and e.notes and explicit_winning_ref in e.notes:
                e.is_recommended = True
    elif not has_explicit_winners and auto_recommend_rank1 and visible_entries:
        min_rank_entry = min(visible_entries, key=lambda x: x.rank or 999)
        min_rank_entry.is_recommended = True
        for e in visible_entries:
            if e.id != min_rank_entry.id:
                e.is_recommended = False

    return all_sorted
