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
    """Calculate vehicle age in years anchored on 1 Jan of manufacture year.

    Malaysian Scale Rule:
    Start year = coverage_start_date.year.
    Completed calendar years = start_year - manufacture_year.
    If coverage starts after Jan 1 (month > 1 or day > 1), vehicle is entering its next year of age (+1).
    Example: YOM 2020, coverage 08 Feb 2026 -> 2026 - 2020 = 6 years;
    Since 08 Feb > 01 Jan, vehicle is in 7th year -> age is 7 years.
    """
    if not manufacture_year or manufacture_year <= 1900:
        return 0
    dt: datetime
    if isinstance(coverage_start_date, str):
        try:
            clean_s = coverage_start_date.split("T")[0].strip()
            dt = datetime.strptime(clean_s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            dt = datetime.now(timezone.utc)
    elif isinstance(coverage_start_date, datetime):
        dt = coverage_start_date
    else:
        dt = datetime.now(timezone.utc)

    completed = dt.year - manufacture_year
    if completed < 0:
        return 0
    if dt.month > 1 or dt.day > 1:
        return completed + 1
    return completed


def get_standard_betterment_rate(age_in_years: int) -> tuple[float, str]:
    """Calculate Malaysian Tariff standard scale for Betterment co-payment:
    < 5 years: 0% ("No (0%)")
    5 years: 15% ("Yes (15%)")
    6 years: 20% ("Yes (20%)")
    7 years: 25% ("Yes (25%)")
    8 years: 30% ("Yes (30%)")
    9 years: 35% ("Yes (35%)")
    >= 10 years: 40% ("Yes (40%)")
    """
    if age_in_years < 5:
        return 0.0, "No (0%)"
    elif age_in_years == 5:
        return 15.0, "Yes (15%)"
    elif age_in_years == 6:
        return 20.0, "Yes (20%)"
    elif age_in_years == 7:
        return 25.0, "Yes (25%)"
    elif age_in_years == 8:
        return 30.0, "Yes (30%)"
    elif age_in_years == 9:
        return 35.0, "Yes (35%)"
    else:  # >= 10
        return 40.0, "Yes (40%)"


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
) -> tuple[bool, float, str]:
    """Evaluate Waiver of Betterment and Betterment Co-Payment Rate based on underwriting rules."""
    quote_y = quote_year or datetime.now().year
    veh_yom = yom if (yom and yom > 1900) else None
    veh_age = max(0, quote_y - veh_yom) if veh_yom else 0

    # 1st Condition:
    # 1.2 IF YEAR OF MAKE + 4 > QUOTATION DATE, then WAIVER OF BETTERMENT = YES (0% betterment)
    if veh_yom and (veh_yom + 4) > quote_y:
        return True, 0.0, "No (0%)"

    # 1.1 IF YEAR OF MAKE + 4 <= QUOTATION DATE, then WAIVER OF BETTERMENT = NO initially
    comp_lower = (company_name or "").lower()
    is_qbe = "qbe" in comp_lower
    is_tune_sompo_amgen_etiqa = any(
        x in comp_lower for x in ("tune", "sompo", "amassurance", "amgen", "etiqa")
    )
    is_lonpac_stmb = any(
        x in comp_lower for x in ("lonpac", "stmb", "takaful malaysia", "syarikat takaful")
    )

    # 2nd Condition:
    if is_qbe and is_comprehensive_private:
        if veh_yom and (veh_yom + 9) > quote_y:
            return True, 0.0, "No (0%)"
        else:
            rate, disp = get_standard_betterment_rate(veh_age)
            return False, rate, disp

    # 2.2 If it's not QBE: check for perils related to betterment
    if not has_betterment_peril:
        rate, disp = get_standard_betterment_rate(veh_age)
        return False, rate, disp

    # Perils added: check insurance company
    if is_tune_sompo_amgen_etiqa:
        if not veh_yom or (veh_yom + 14) > quote_y:
            return True, 0.0, "No (0%)"
        else:
            rate, disp = get_standard_betterment_rate(veh_age)
            return False, rate, disp
    elif is_lonpac_stmb:
        if not veh_yom or (veh_yom + 9) > quote_y:
            return True, 0.0, "No (0%)"
        else:
            rate, disp = get_standard_betterment_rate(veh_age)
            return False, rate, disp
    else:
        if not veh_yom or (veh_yom + 9) > quote_y:
            return True, 0.0, "No (0%)"
        else:
            rate, disp = get_standard_betterment_rate(veh_age)
            return False, rate, disp


def calculate_betterment_rate(
    age_in_years: int, company_name: str | None = None
) -> tuple[float, str]:
    """Backward-compatible helper returning standard or QBE betterment rate."""
    comp_lower = (company_name or "").lower()
    if "qbe" in comp_lower and age_in_years <= 10:
        return 0.0, "No (0%)"
    return get_standard_betterment_rate(age_in_years)


def normalize_towing_km(raw_towing: Any, combined_text: str = "", company_name: str | None = None) -> str:
    """Normalize towing benefit into clean numeric KM, RM currency cap, 'Unlimited', 'No towing', or preserve custom text."""
    val_str = str(raw_towing or "").strip()

    if re.search(
        r"(?i)(?<!\d)0\s*km\b|\b(?:no towing|without towing|not included|tiada|nil)\b|^(?:none|no)$",
        val_str,
    ):
        return "No towing"

    if any(
        k in val_str.lower()
        for k in ("unlimited", "24-hr unlimited", "24 hour unlimited", "tanpa had")
    ):
        return "Unlimited"

    # Preserve explicit RM currency limits
    m_rm = re.search(r"^(?:RM|MYR)\s*([\d,]+(?:\.\d{2})?)", val_str, re.IGNORECASE)
    if m_rm:
        return f"RM {m_rm.group(1)}"

    unlimited_triggers = [
        "unlimited towing",
        "24-hr unlimited",
        "24 hour unlimited",
        "tanpa had",
        "motor pa plus",
        "driver plus plan 4",
        "driver plus 4",
        "private car 365 plan",
        "amdrive plus",
        "oto 360",
        "e-assist smart driver",
        "sompo motor",
        "motor easy bundle plan",
        "autobuddy",
    ]
    if any(k in combined_text.lower() for k in unlimited_triggers):
        return "Unlimited"

    for text_source in (val_str, combined_text):
        m = re.search(
            r"(\d+)\s*(?:km|k\.m\.|kilomet(?:er|re)s?)\b", text_source, re.IGNORECASE
        )
        if m:
            km = int(m.group(1))
            if km > 0:
                return f"{km} km"

    m_num = re.match(r"^(\d+)$", val_str)
    if m_num:
        val = int(m_num.group(1))
        if val > 0:
            comp_l = (company_name or "").lower()
            if val in (200, 300, 400, 500, 600) and any(c in comp_l for c in ("qbe", "lonpac", "sompo", "tune")):
                return f"RM {val}"
            return f"{val} km"

    if val_str and val_str.lower() not in ("none", "null", "false", ""):
        # Check if the string has RM anywhere
        m_rm_inner = re.search(r"(?:RM|MYR)\s*(\d{2,4})", val_str, re.IGNORECASE)
        if m_rm_inner:
            return f"RM {m_rm_inner.group(1)}"
        m_any = re.search(r"\b(\d{2,4})\b", val_str)
        if m_any:
            comp_l = (company_name or "").lower()
            val = int(m_any.group(1))
            if val in (200, 300, 400, 500, 600) and any(c in comp_l for c in ("qbe", "lonpac", "sompo", "tune")):
                return f"RM {val}"
            return f"{m_any.group(1)} km"
        return val_str

    return "Unlimited"


def _towing_sort_value(towing_str: str | None) -> float:
    """Sort helper for towing distance: higher is better (negative for ASC sort)."""
    s = (towing_str or "").lower().strip()
    if "unlimited" in s:
        return -999999.0
    m = re.search(r"(\d+)", s)
    if m:
        return -float(m.group(1))
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
        bet = float(e.betterment_rate) if e.betterment_rate is not None else 0.0
        tow = _towing_sort_value(e.towing_km or e.towing_limit)
        return (tot, exc, bet, tow)

    auto_sorted = sorted(auto_ranked, key=sort_key)

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
