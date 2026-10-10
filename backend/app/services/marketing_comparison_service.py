"""Marketing Comparison Service

Provides side-by-side multi-underwriter comparison, rate computation,
Excel 1:1 parity financial modeling, manual quote sourcing, WhatsApp teaser formatting,
and winner handoff to the Risk-Locker Quotation Builder.
"""

from __future__ import annotations

import logging
import math
import re
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from typing import Any

from collections import defaultdict

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.models.tables import (
    AccountStatus,
    Batch,
    BenefitConcept,
    CatalogOffering,
    CompanyBenefitCondition,
    CustomerAccount,
    DraftBenefitSelection,
    ExtractionBenefitLine,
    ExtractionRecord,
    GeneratedPdfVersion,
    InsuranceCompany,
    InsuranceTenure,
    Job,
    QuotationDraft,
    RecordStatus,
    Session as SessionModel,
    StorageStatus,
    TenureComparisonEntry,
    TrackedVehicle,
    UploadedFile,
    User,
    new_id,
)
from app.services.customer_account_service import resolve_or_create_customer
from app.services.benefit_evaluation_engine import BenefitEvaluationEngine, EvaluatedBenefit
from app.services.vehicle_tracking_service import parse_date_safe

logger = logging.getLogger(__name__)

# Malaysian Private Car NCD Rate Scale (ordered 1st year to 6th+ year max)
NCD_RATE_SCALE = [0.0, 25.0, 30.0, 38.33, 45.0, 55.0]


def calculate_ncd_pair(ncd_value: float | None) -> tuple[float | None, float | None]:
    """Calculate (current_ncd, next_ncd) according to Malaysian Private Car NCD Rate Scale.
    
    The scale is:
    0% (1st Yr) -> 25% (2nd Yr) -> 30% (3rd Yr) -> 38.33% (4th Yr) -> 45% (5th Yr) -> 55% (6th+ Yr).
    
    The PDF quotation displays the upcoming policy's NCD (next_ncd).
    The previous tenure's NCD (current_ncd) is one step below in the scale.
    """
    if ncd_value is None:
        return None, None
    try:
        val = float(ncd_value)
    except (ValueError, TypeError):
        return None, None

    if val < 0.0:
        return None, None

    # Find closest tier in NCD_RATE_SCALE
    best_idx = 0
    min_diff = float("inf")
    for idx, tier in enumerate(NCD_RATE_SCALE):
        diff = abs(tier - val)
        if diff < min_diff:
            min_diff = diff
            best_idx = idx

    next_ncd = NCD_RATE_SCALE[best_idx]
    prev_idx = max(0, best_idx - 1)
    current_ncd = NCD_RATE_SCALE[prev_idx]
    return current_ncd, next_ncd


def calculate_vehicle_age(manufacture_year: int | None, coverage_start_date: datetime | str | None) -> int:
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


def check_has_betterment_peril(f: dict | None = None, combined_text: str = "", raw_w: Any = None) -> bool:
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
    """Evaluate Waiver of Betterment and Betterment Co-Payment Rate based on underwriting rules:

    0 to 5 years --> 0% (Waiver of Betterment = YES)

    1st Condition:
    1.1 IF YEAR OF MAKE + 4 <= QUOTATION DATE (YEAR), then WAIVER OF BETTERMENT = NO
    1.2 IF YEAR OF MAKE + 4 > QUOTATION DATE (YEAR), then WAIVER OF BETTERMENT = YES

    2nd Condition (in case it is NO in Condition 1):
    2.1 IF QBE COMPREHENSIVE PRIVATE CAR and (YEAR OF MAKE + 9) > CURRENT_YEAR:
        then WAIVER OF BETTERMENT = YES.
        If <= current_year, then NO.

    2.2 If NOT QBE:
        Check for perils related to betterment, waiver of betterment, car spare parts waiver of betterment.
        If NO perils added:
            WAIVER OF BETTERMENT = NO
        If perils ARE added:
            FOR (TUNE, SOMPO, AMASSURANCE, ETIQA) ONLY:
                IF (YEAR OF MAKE + 14) > CURRENT_YEAR -> WAIVER OF BETTERMENT = YES
                ELSE -> WAIVER OF BETTERMENT = NO
            FOR (LONPAC, STMB) ONLY:
                IF (YEAR OF MAKE + 9) > CURRENT_YEAR -> WAIVER OF BETTERMENT = YES
                ELSE -> WAIVER OF BETTERMENT = NO
            FOR ALL OTHERS:
                IF (YEAR OF MAKE + 9) > CURRENT_YEAR -> WAIVER OF BETTERMENT = YES
                ELSE -> WAIVER OF BETTERMENT = NO

    Returns:
        tuple[bool, float, str]: (waiver_betterment, betterment_rate, betterment_display)
    """
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
    is_tune_sompo_amgen_etiqa = any(x in comp_lower for x in ("tune", "sompo", "amassurance", "amgen", "etiqa"))
    is_lonpac_stmb = any(x in comp_lower for x in ("lonpac", "stmb", "takaful malaysia", "syarikat takaful"))

    # 2nd Condition:
    if is_qbe and is_comprehensive_private:
        # 2.1 IF QBE COMPREHENSIVE PRIVATE CAR and (YEAR OF MAKE + 9) > CURRENT_YEAR then Waiver of Betterment = YES
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
        # FOR (TUNE, SOMPO, AMASSURANCE, ETIQA) ONLY:
        # IF YEAR OF MAKE + 14 > CURRENT YEAR THEN WAIVER OF BETTERMENT = YES, ELSE NO
        if not veh_yom or (veh_yom + 14) > quote_y:
            return True, 0.0, "No (0%)"
        else:
            rate, disp = get_standard_betterment_rate(veh_age)
            return False, rate, disp
    elif is_lonpac_stmb:
        # FOR (LONPAC, STMB) ONLY:
        # IF YEAR OF MAKE + 9 > CURRENT YEAR THEN WAIVER OF BETTERMENT = YES, ELSE NO
        if not veh_yom or (veh_yom + 9) > quote_y:
            return True, 0.0, "No (0%)"
        else:
            rate, disp = get_standard_betterment_rate(veh_age)
            return False, rate, disp
    else:
        # Other insurers with betterment rider: standard 10-year rule
        if not veh_yom or (veh_yom + 9) > quote_y:
            return True, 0.0, "No (0%)"
        else:
            rate, disp = get_standard_betterment_rate(veh_age)
            return False, rate, disp


def calculate_betterment_rate(age_in_years: int, company_name: str | None = None) -> tuple[float, str]:
    """Backward-compatible helper returning standard or QBE betterment rate."""
    comp_lower = (company_name or "").lower()
    if "qbe" in comp_lower and age_in_years <= 10:
        return 0.0, "No (0%)"
    return get_standard_betterment_rate(age_in_years)


def normalize_towing_km(raw_towing: Any, combined_text: str = "") -> str:
    """Normalize towing benefit into clean numeric KM, 'Unlimited', 'No towing', or preserve custom text."""
    val_str = str(raw_towing or "").strip()

    if re.search(r"(?i)(?<!\d)0\s*km\b|\b(?:no towing|without towing|not included|tiada|nil)\b|^(?:none|no)$", val_str):
        return "No towing"

    if any(k in val_str.lower() for k in ("unlimited", "24-hr unlimited", "24 hour unlimited", "tanpa had")):
        return "Unlimited"
    
    # Auto-detect unlimited towing based on specific purchased perils
    unlimited_triggers = [
        "unlimited towing", "24-hr unlimited", "24 hour unlimited", "tanpa had",
        "motor pa plus", "driver plus plan 4", "driver plus 4", 
        "private car 365 plan", "amdrive plus",
        "oto 360", "e-assist smart driver", "sompo motor", 
        "motor easy bundle plan", "autobuddy"
    ]
    if any(k in combined_text.lower() for k in unlimited_triggers):
        return "Unlimited"

    for text_source in (val_str, combined_text):
        m = re.search(r"(\d+)\s*(?:km|k\.m\.|kilomet(?:er|re)s?)\b", text_source, re.IGNORECASE)
        if m:
            km = int(m.group(1))
            if km > 0:
                return f"{km} km"

    m_num = re.match(r"^(\d+)$", val_str)
    if m_num:
        km = int(m_num.group(1))
        if km > 0:
            return f"{km} km"

    if val_str and val_str.lower() not in ("none", "null", "false", ""):
        m_any = re.search(r"\b(\d{2,4})\b", val_str)
        if m_any:
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

    Assigns rank = 1, 2, 3...
    If explicit winning underwriter is not set and auto_recommend_rank1 is True,
    strictly rank 1 is recommended (single winner).
    Preserves multi-winner user selections if already recommended.
    """
    visible_entries = [e for e in entries if not getattr(e, "is_hidden", False)]
    hidden_entries = [e for e in entries if getattr(e, "is_hidden", False)]

    # Separate visible entries with manual_rank vs automatic
    manual_ranked = [e for e in visible_entries if e.manual_rank is not None and e.manual_rank > 0]
    auto_ranked = [e for e in visible_entries if e.manual_rank is None or e.manual_rank <= 0]

    def sort_key(e: TenureComparisonEntry):
        tot = float(e.total_payable) if e.total_payable else float("inf")
        if tot <= 0.0:
            tot = float("inf")
        exc = float(e.excess) if e.excess is not None else 0.0
        bet = float(e.betterment_rate) if e.betterment_rate is not None else 0.0
        tow = _towing_sort_value(e.towing_km or e.towing_limit)
        return (tot, exc, bet, tow)

    auto_sorted = sorted(auto_ranked, key=sort_key)

    # Assign manual ranks
    used_ranks: set[int] = {e.manual_rank for e in manual_ranked if e.manual_rank is not None}
    for e in manual_ranked:
        e.rank = e.manual_rank

    # Assign remaining ranks to auto_sorted entries
    curr_rank = 1
    for e in auto_sorted:
        while curr_rank in used_ranks:
            curr_rank += 1
        e.rank = curr_rank
        used_ranks.add(curr_rank)
        curr_rank += 1

    # Hidden entries get rank starting after visible
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


def _extract_vehicle_year_from_draft(f: dict[str, Any]) -> int | None:
    """Extract vehicle manufacture year from draft fields."""
    for key in ("vehicle_year", "year_make", "manufacture_year", "year_of_manufacture", "yom", "year"):
        val = _extract_val(f.get(key))
        if val:
            try:
                s = str(val).strip()
                m = re.search(r"\b(19\d{2}|20\d{2})\b", s)
                if m:
                    return int(m.group(1))
            except (ValueError, TypeError):
                pass
    return None


def _extract_val(val: Any) -> Any:
    """Recursively unwrap ExtractionField dictionary objects."""
    if isinstance(val, dict):
        return _extract_val(val.get("value"))
    return val


def _to_float(val: Any) -> float:
    raw = _extract_val(val)
    if raw is None:
        return 0.0
    if isinstance(raw, (int, float, Decimal)):
        f_val = float(raw)
        return min(max(f_val, -9_999_999_999.99), 9_999_999_999.99)
    try:
        # Strip currency symbols, commas, and whitespace
        s = str(raw).replace("RM", "").replace("rm", "").replace(",", "").strip()
        f_val = float(s)
        return min(max(f_val, -9_999_999_999.99), 9_999_999_999.99)
    except (ValueError, TypeError):
        return 0.0


def _safe_str(val: Any) -> str:
    raw = _extract_val(val)
    if raw is None:
        return ""
    return str(raw).strip()


def _extract_ncd_from_draft(f: dict[str, Any], s_obj: Any = None) -> float | None:
    """Extract numeric NCD percentage from draft fields and session extraction records.
    
    Supports NCD, NCB (No Claim Bonus), DTT (Diskaun Tanpa Tuntutan), and Malaysian rate scale bounds (0..55%).
    """
    for k in (
        "ncd_percent",
        "ncd_percentage",
        "ncd",
        "ncb",
        "ncb_percent",
        "ncb_percentage",
        "dtt_percent",
        "no_claim_discount",
        "no_claim_bonus",
        "ncd_rate",
        "ncb_rate",
    ):
        raw = f.get(k)
        if raw is not None and raw != "":
            val = _extract_val(raw)
            if isinstance(val, (int, float)):
                fval = float(val)
                if 0.0 <= fval <= 55.0:
                    return fval
            s = str(val).strip()
            m = re.search(r"(\d+(?:\.\d+)?)", s)
            if m:
                try:
                    fval = float(m.group(1))
                    if 0.0 <= fval <= 55.0:
                        return fval
                except Exception:
                    pass

    # Fallback to extraction record candidates & raw/ocr text on session object
    if s_obj:
        up_file = getattr(s_obj, "uploaded_file", None)
        ext_rec = getattr(up_file, "extraction_record", None) if up_file else None
        if ext_rec:
            cands = getattr(ext_rec, "candidates", None) or {}
            if isinstance(cands, dict):
                for ck in ("ncd_percent", "ncd", "ncb", "no_claim_discount", "no_claim_bonus", "dtt"):
                    cv = cands.get(ck)
                    if cv:
                        if isinstance(cv, list):
                            for it in cv:
                                it_v = it.get("value") if isinstance(it, dict) else it
                                m = re.search(r"(\d+(?:\.\d+)?)", str(it_v))
                                if m and 0.0 <= float(m.group(1)) <= 55.0:
                                    return float(m.group(1))
                        else:
                            m = re.search(r"(\d+(?:\.\d+)?)", str(cv))
                            if m and 0.0 <= float(m.group(1)) <= 55.0:
                                return float(m.group(1))

            text_to_search = (getattr(ext_rec, "ocr_text", "") or "") + "\n" + (getattr(ext_rec, "raw_text", "") or "")
            if text_to_search:
                patterns = [
                    r"(?i)(?:ncd|ncb|dtt|no\s+claim\s+discount|no\s+claim\s+bonus)\s*(?:[:=]|\bat\b)?\s*([0-9]{1,2}(?:\.[0-9]+)?)\s*%",
                    r"(?i)\b([0-9]{1,2}(?:\.[0-9]+)?)\s*%\s*(?:ncd|ncb|dtt)\b",
                    r"(?i)less\s*:\s*(?:ncd|ncb)\s*\(?\s*([0-9]{1,2}(?:\.[0-9]+)?)\s*%\s*\)?",
                    r"(?i)n\.c\.d\.?\s*[:]?\s*([0-9]{1,2}(?:\.[0-9]+)?)\s*%",
                    r"(?i)n\.c\.b\.?\s*[:]?\s*([0-9]{1,2}(?:\.[0-9]+)?)\s*%",
                ]
                for p in patterns:
                    m = re.search(p, text_to_search)
                    if m:
                        try:
                            fval = float(m.group(1))
                            if 0.0 <= fval <= 55.0:
                                return fval
                        except Exception:
                            pass
    return None


def detect_runner_fee_from_id(ic_or_passport: str | None) -> float:
    """Auto-detect runner fee based on Malaysian IC vs International Passport.

    Rules:
    - Customer ID starts with letters (e.g. K1584766Z, A12345678) -> International Passport -> RM 20.00.
    - Customer ID starts with digits (YYMMDD...) -> Malaysian National ID (MyKad) -> RM 10.00.
    - Missing / PENDING-* / undetectable -> Default = RM 10.00.
    """
    if not ic_or_passport:
        return 10.0
    cleaned = ic_or_passport.strip().upper()
    if not cleaned or cleaned.startswith("PENDING-") or "PENDING-" in cleaned:
        return 10.0
    from app.services.identity_normalization_service import normalize_government_id
    _, id_type = normalize_government_id(cleaned)
    if id_type == "passport":
        return 20.0
    return 10.0


def _extract_exact_basic_figure(f: dict[str, Any], company_name: str = "", s_obj: Any = None) -> tuple[float, str]:
    """Extract exact basic figure and term label:
    - For Etiqa, STMB: exact term "Basic Contribution"
    - For Berjaya Sompo, QBE, AmAssurance, Tune Protect, Lonpac, and others: exact term "Basic Premium"
    """
    norm_name = (company_name or "").lower()
    is_takaful = any(k in norm_name for k in ("etiqa", "stmb", "takaful"))
    term_label = "Basic Contribution" if is_takaful else "Basic Premium"

    cov_amt = _extract_vehicle_sum_insured(f, s_obj=s_obj)
    ncd_pct = _to_float(f.get("ncd_percent"))

    def is_valid_bp(amt: float) -> bool:
        if amt <= 0.0:
            return False
        # If car sum insured is >= 10,000, basic premium cannot be < 50 RM or equal to NCD percent
        if cov_amt >= 10000.0:
            if amt < 50.0:
                return False
            if ncd_pct > 0.0 and abs(amt - ncd_pct) < 0.01:
                return False
        return True

    # 1. Direct candidate keys in standard preference order
    candidate_keys = (
        (
            "basic_contribution",
            "gross_basic_contribution",
            "contribution_before_ncd",
            "sumbangan_asas",
            "basic_premium_vehicle",
            "basic_premium",
        )
        if is_takaful
        else (
            "basic_premium_vehicle",
            "basic_premium",
            "gross_basic_premium",
            "premium_before_ncd",
            "premium_asas",
            "basic_contribution",
            "coverage_premium",
            "base_tp_premium",
            "basic_premium_total",
        )
    )
    for k in candidate_keys:
        val = _to_float(f.get(k))
        if is_valid_bp(val):
            return val, term_label

    # 2. Iterate keys with flexible regex (supporting underscores, dashes, spaces, and Malay terms)
    basic_regex = re.compile(
        r"(?i)(?:basic[_\s-]*(?:contribution|premium)|(?:premium|sumbangan)[_\s-]*asas)"
    )
    for raw_k, raw_v in f.items():
        if basic_regex.search(raw_k):
            val = _to_float(raw_v)
            if is_valid_bp(val):
                return val, term_label
        if isinstance(raw_v, list):
            for item in raw_v:
                if isinstance(item, dict) and any(
                    basic_regex.search(str(item.get(ik, "")))
                    for ik in ("label", "name", "desc", "key")
                ):
                    val = _to_float(item.get("amount") or item.get("value"))
                    if is_valid_bp(val):
                        return val, term_label

    # 3. Fallback: Extraction record candidates on session object
    if s_obj:
        try:
            up_file = getattr(s_obj, "uploaded_file", None)
            ext_rec = getattr(up_file, "extraction_record", None) if up_file else None
            if ext_rec:
                # 3a. 2D Spatial Words Alignment on extraction_record
                words = getattr(ext_rec, "words", None) or []
                if isinstance(words, list) and words:
                    for w in words:
                        t = str(w.get("text", "")).lower().strip(" :*")
                        if t in ("basic", "premium asas", "caruman asas", "sumbangan asas"):
                            w_top = float(w.get("top", 0))
                            w_page = int(w.get("page", 1))
                            row_words = [
                                rw for rw in words
                                if int(rw.get("page", 1)) == w_page
                                and abs(float(rw.get("top", 0)) - w_top) <= 5.0
                                and float(rw.get("x0", 0)) > float(w.get("x1", 0))
                            ]
                            row_str = " ".join(str(rw.get("text", "")) for rw in row_words)
                            row_str_no_date = re.sub(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b", "", row_str)
                            row_str_no_date = re.sub(r"\(\d+(?:\.\d+)?\s*%\)|\d+(?:\.\d+)?\s*%", "", row_str_no_date)
                            m = re.findall(r"[\d,]+\.\d{2}", row_str_no_date)
                            if m:
                                for amt_str in reversed(m):
                                    spatial_val = _to_float(amt_str)
                                    if is_valid_bp(spatial_val):
                                        return spatial_val, term_label

                cands = getattr(ext_rec, "candidates", None) or {}
                if isinstance(cands, dict):
                    for ck in (
                        "basic_premium_vehicle",
                        "basic_premium",
                        "basic_contribution",
                        "premium_before_ncd",
                    ):
                        c_val = cands.get(ck)
                        if isinstance(c_val, list) and c_val:
                            for item in c_val:
                                item_v = item.get("value") if isinstance(item, dict) else item
                                val = _to_float(item_v)
                                if is_valid_bp(val):
                                    return val, term_label
                        elif c_val:
                            val = _to_float(c_val)
                            if is_valid_bp(val):
                                return val, term_label
                # 4. Fallback: OCR / Raw text regex scan on extraction_record
                text_to_search = (getattr(ext_rec, "ocr_text", "") or "") + "\n" + (getattr(ext_rec, "raw_text", "") or "")
                if text_to_search:
                    m = re.search(
                        r"(?i)(?:basic\s+premium|premium\s+asas|basic\s+contribution|sumbangan\s+asas)[\s\S]{0,60}?(?:RM|MYR)?\s*([\d,]+\.\d{2})",
                        text_to_search,
                    )
                    if m:
                        val = _to_float(m.group(1))
                        if is_valid_bp(val):
                            return val, term_label
        except Exception:
            pass

    # 5. Fallback: BNM Motor Tariff Formula Derivation
    # Basic Premium = (Gross Premium - Extras) / (1 - NCD%)
    try:
        gross_amt = _extract_vehicle_motor_premium(f)
        if gross_amt > 50.0 and 0.0 < ncd_pct < 100.0:
            extras_amt = _to_float(f.get("total_optional_cover_amount") or f.get("optional_cover_amount"))
            if extras_amt <= 0.0:
                benefits_list = f.get("detected_benefits") or f.get("benefits") or []
                if isinstance(benefits_list, list):
                    extras_amt = sum(
                        _to_float(b.get("premium_cost") or b.get("cost"))
                        for b in benefits_list
                        if isinstance(b, dict) and bool(b.get("is_optional_cover", True))
                    )
            derived_bp = (gross_amt - extras_amt) / (1.0 - (ncd_pct / 100.0))
            if is_valid_bp(derived_bp):
                return round(derived_bp, 2), term_label
    except Exception:
        pass

    return 0.0, term_label



def calculate_exact_rate(basic_amt: float, sum_insured: float) -> tuple[str, float]:
    """Calculate exact rate factor rounded to 6 decimal places using Decimal and ROUND_HALF_UP."""
    if sum_insured <= 0.0 or basic_amt <= 0.0:
        return "0.000000", 0.0
    from decimal import Decimal, ROUND_HALF_UP
    rate_dec = (Decimal(str(basic_amt)) / Decimal(str(sum_insured))).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return f"{rate_dec:.6f}", float(rate_dec)


def format_canonical_perils(combined_text: str, tokens: list[str] | None = None) -> list[str]:
    """Extract canonical short peril/add-on tags in standard Malaysian market order."""
    token_str = " ".join(tokens) if tokens else ""
    text = (combined_text + " " + token_str).lower()
    found: list[str] = []
    seen: set[str] = set()

    def add(tag: str):
        if tag not in seen:
            seen.add(tag)
            found.append(tag)

    # 1. Telematics (Drive Less Save More)
    if any(k in text for k in ("drive less save more", "telematics", "pay as you drive", "mileage based")):
        add("TELEMATICS")

    # 2. Towing upgrade / 24/7 Unlimited / Towing Assistance
    if any(k in text for k in ("towing", "tunda", "24/7 emergency", "unlimited towing", "towing mileage", "extra towing", "towing upgrade", "towing assistance", "breakdown assistance")):
        add("TOWING")

    # 3. LLP (Legal Liability to Passengers)
    if any(k in text for k in ("legal liability to passenger", "liability to passenger", "legal liability to pax", "end 100", "endorsement 100")):
        add("LLP")
    elif re.search(r"\bllp\b", text):
        add("LLP")

    # 4. LLOP (Legal Liability of Passengers)
    if any(k in text for k in ("legal liability of passenger", "liability of passenger", "negligent act", "end 72", "endorsement 72")):
        add("LLOP")
    elif re.search(r"\bllop\b", text):
        add("LLOP")

    # 5. EV Wall Charger
    if any(k in text for k in ("ev home wall charger", "wall charger", "ev charger", "ev coverage")):
        add("EV CHARGE")

    # 6. PA (Personal Accident to Driver)
    if any(k in text for k in ("personal accident", "pa to driver", "driver & passenger pa", "driver pa")):
        add("PA")
    elif re.search(r"\bpa\b", text) and "driver" in text:
        add("PA")

    # 7. Compassionate Benefit
    if any(k in text for k in ("compassionate benefit", "compassionate allowance", "compassionate")):
        add("COMPASSIONATE")

    # 8. Loss & Theft (Special Relief Allowance)
    if any(k in text for k in ("special relief allowance", "total loss and theft", "loss and theft", "theft allowance")):
        add("LOSS & THEFT")

    # 9. Flood / Special Perils
    if any(k in text for k in ("flood", "banjir", "special perils", "peril khas", "natural disaster", "storm", "landslide", "water damage")):
        add("FLOOD")

    # 10. Windscreen
    if any(k in text for k in ("windscreen", "cermin", "w/screen")):
        add("WINDSCREEN")

    # 11. Key Care
    if any(k in text for k in ("key care", "key replacement", "replacement of key")):
        add("KEY CARE")

    # 12. CART / Loss of Use
    if any(k in text for k in ("assessed repair time", "cart", "loss of use")):
        add("CART")

    return found


def _extract_vehicle_basic_premium(f: dict[str, Any], company_name: str = "", s_obj: Any = None) -> float:
    """Extract basic premium / basic contribution before NCD."""
    val, _ = _extract_exact_basic_figure(f, company_name, s_obj=s_obj)
    if val > 0.0:
        return val
    cov_amt = _extract_vehicle_sum_insured(f, s_obj=s_obj)
    ncd_pct = _to_float(f.get("ncd_percent"))
    for k in (
        "basic_premium_vehicle",
        "basic_premium",
        "basic_contribution",
        "gross_basic_premium",
        "premium_before_ncd",
        "premium_asas",
        "sumbangan_asas",
    ):
        v = _to_float(f.get(k))
        if v > 0.0:
            if cov_amt >= 10000.0:
                if v < 50.0 or (ncd_pct > 0.0 and abs(v - ncd_pct) < 0.01):
                    continue
            return v
    return 0.0


def _extract_vehicle_sum_insured(f: dict[str, Any], s_obj: Any = None) -> float:
    """Disambiguate vehicle sum insured from accessory endorsement limits (e.g. windscreen RM 4,000, PA RM 25,000)."""
    c_cov = _to_float(f.get("coverage_amount"))
    c_sum = _to_float(f.get("sum_insured"))
    c_mkt = _to_float(f.get("market_value"))
    c_agr = _to_float(f.get("agreed_value"))

    major_candidates = [c for c in [c_cov, c_mkt, c_agr, c_sum] if c >= 10000.0]
    if major_candidates:
        if c_cov >= 10000.0:
            return c_cov
        return max(major_candidates)

    # Ground-truth fallback: scan PDF text blocks or OCR text for vehicle agreed value or sum insured
    if s_obj:
        up_file = getattr(s_obj, "uploaded_file", None)
        ext_rec = getattr(up_file, "extraction_record", None) if up_file else None
        if ext_rec:
            # Check blocks first (e.g. Sompo: 'RM 161,000.00 \n VCC655 \n Vehicle Agreed Value')
            blocks = getattr(ext_rec, "blocks", []) or []
            for b in blocks:
                b_text = b.get("text", "") if isinstance(b, dict) else str(b)
                if any(k in b_text.lower() for k in ("agreed value", "sum insured", "sum covered", "nilai yang dipersetujui")):
                    m_b = re.findall(r"(?:RM|MYR)?\s*([\d,]{5,}(?:\.\d{2})?)", b_text, re.IGNORECASE)
                    if m_b:
                        nums = [_to_float(x) for x in m_b if _to_float(x) >= 10000.0]
                        if nums:
                            return max(nums)
            combined_txt = (getattr(ext_rec, "ocr_text", "") or "") + "\n" + (getattr(ext_rec, "raw_text", "") or "")
            m_txt = re.findall(r"(?i)(?:vehicle\s*agreed\s*value|vehicle\s*sum\s*insured|sum\s*insured\s*\(agreed\s*value\)|sum\s*covered)[\s\S]{0,60}?(?:RM|MYR)?\s*([\d,]{5,}(?:\.\d{2})?)", combined_txt)
            if m_txt:
                nums = [_to_float(x) for x in m_txt if _to_float(x) >= 10000.0]
                if nums:
                    return max(nums)

    all_candidates = [c for c in [c_sum, c_cov, c_mkt, c_agr] if c > 0.0]
    return max(all_candidates) if all_candidates else 0.0


def _extract_vehicle_motor_premium(f: dict[str, Any]) -> float:
    """Extract motor insurance premium payable to underwriter (including SST and stamp duty)."""
    total_amt = _to_float(f.get("total_amount") or f.get("total_payable"))
    if total_amt > 0.0:
        return total_amt
    gross = _to_float(f.get("gross_premium"))
    if gross > 0.0:
        return gross
    return _to_float(
        f.get("basic_premium_vehicle")
        or f.get("basic_premium")
        or f.get("premium")
        or f.get("insurance_premium")
    )


def _extract_valuation_type(f: dict[str, Any], s_obj: Any = None) -> tuple[str, bool]:
    """Determine agreed value vs market value with full ground-truth verification."""
    val_type_str = _safe_str(f.get("valuation_type")).lower()
    agr_val = _extract_val(f.get("agreed_value"))
    if "agreed" in val_type_str or agr_val in [True, "Yes", "yes", "true", "True", "1"]:
        return "agreed_value", True

    if s_obj:
        up_file = getattr(s_obj, "uploaded_file", None)
        ext_rec = getattr(up_file, "extraction_record", None) if up_file else None
        if ext_rec:
            combined = ((getattr(ext_rec, "ocr_text", "") or "") + "\n" + (getattr(ext_rec, "raw_text", "") or "")).lower()
            if combined:
                # Check for explicit negation first: e.g. "AGREED VALUE : NO" (STMB)
                if re.search(r"(?i)agreed\s*value\s*[:]?\s*(?:no|tidak|\b0\b|false)", combined):
                    return "market_value", False
                # Check for explicit agreed value markers: e.g. "Vehicle Agreed Value" (Sompo), "Sum Insured (Agreed Value)" (QBE)
                if any(k in combined for k in ("vehicle agreed value", "(agreed value)", "nilai yang dipersetujui", "agreed value clause")):
                    return "agreed_value", True

    return "market_value", False


def extract_strict_schedule_excess(text: str) -> float | None:
    """Strictly extract policy excess from schedule tables, rejecting instructional disclaimers."""
    if not text:
        return None
    narrative_pattern = re.compile(
        r"(?i)(?:is applicable|shall be borne|under 21|bawah 21|provisional|percubaan|learner|sementara|if you|increase to|penalty|in the event|unnamed driver|holding a|holds a)"
    )
    patterns = [
        r"(?i)policy\s+excess\s*:\s*(?:RM|MYR)?\s*([\d,]+(?:\.\d{2})?)",
        r"(?i)(?:([\d,]+(?:\.\d{2})?)\s*(?:RM|MYR)?\s*voluntary\s+excess|voluntary\s+excess\s*(?:RM|MYR)?\s*([\d,]+(?:\.\d{2})?))",
        r"(?i)excess\s+all\s+claims\s*:\s*(?:RM|MYR)?\s*([\d,]+(?:\.\d{2})?)",
        r"(?i)\*?\s*excess\s+amount\s*:\s*(?:RM|MYR)?\s*([\d,]+(?:\.\d{2})?)",
        r"(?i)excess\s+lebihan\s*\(\s*(?:MYR|RM)?\s*([\d,]+(?:\.\d{2})?)\s*\)",
        r"(?i)excess\s*(?:/\s*lebihan)?\s*[:]?\s*(?:RM|MYR)?\s*([\d,]+(?:\.\d{2})?)",
    ]
    for line in text.splitlines():
        clean_line = line.strip()
        if not clean_line or narrative_pattern.search(clean_line):
            continue
        for pat in patterns:
            m = re.search(pat, clean_line)
            if m:
                val_str = [g for g in m.groups() if g is not None][0]
                return float(val_str.replace(",", ""))
    return None


def _extract_excess(f: dict[str, Any], s_obj: Any = None) -> float:
    """Extract voluntary / policy excess strictly from the policy schedule.
    
    Invariant: Compulsory excess (e.g. RM 400 statutory conditional excess for under 21 / provisional drivers)
    must NEVER be reported as the policy excess. If excess_amount is 0.0 or nil, return 0.0.
    """
    # 1. Fallback to raw text scan on session extraction record if available
    if s_obj:
        up_file = getattr(s_obj, "uploaded_file", None)
        ext_rec = getattr(up_file, "extraction_record", None) if up_file else None
        if ext_rec:
            ocr_text = getattr(ext_rec, "ocr_text", "") or ""
            raw_text = getattr(ext_rec, "raw_text", "") or ""
            strict_val = extract_strict_schedule_excess(ocr_text or raw_text)
            if strict_val is not None:
                return strict_val

    # 2. Check explicit schedule fields
    for k in ("policy_excess", "voluntary_excess", "excess_all_claims"):
        if k in f and f[k] is not None and f[k] != "":
            return _to_float(f[k])

    ex_amt = _to_float(f.get("excess_amount"))
    # In Malaysia, RM 400 is almost universally the statutory compulsory excess for under-21 drivers.
    # If the quote reports 400 and there is a compulsory excess indicator, treat policy excess as 0.00.
    if ex_amt == 400.0:
        return 0.0

    if ex_amt > 0.0:
        return ex_amt

    raw_ex = f.get("excess")
    if raw_ex is not None and raw_ex != "":
        val = _to_float(raw_ex)
        if val == 400.0:
            return 0.0
        return val

    return 0.0


def _is_valid_windscreen_amt(val: float | None) -> bool:
    """Validate windscreen coverage amount bounds.
    
    In Malaysia, private car windscreen protection coverage ranges between RM 300 and RM 30,000.
    Rejects calendar years (e.g. 2020..2035) and policy/quotation reference numbers (e.g. 283233).
    """
    if val is None or val <= 0.0:
        return False
    return 500.0 <= val <= 50000.0 and int(val) not in range(2020, 2035)


def _extract_windscreen_from_draft(f: dict[str, Any]) -> float | None:
    """Extract numeric windscreen coverage sum insured directly from draft fields."""
    if not f or not isinstance(f, dict):
        return None
    for k in ("windscreen", "windscreen_sum_insured", "windscreen_coverage", "cermin"):
        v = f.get(k)
        raw = v.get("value") if isinstance(v, dict) else v
        amt = _to_float(raw)
        if amt > 0.0 and _is_valid_windscreen_amt(amt):
            return amt
    return None


def _resolve_comparison_benefits(
    db: Session,
    session: SessionModel,
    company_id: str | None,
    f: dict[str, Any],
    windscreen_target: float | None = None,
) -> dict[str, Any]:
    """Single source of truth for extracting Special Perils, Windscreen, LLP, and Towing.
    
    Reads from:
    1. DraftBenefitSelection records
    2. ExtractionBenefitLine records
    3. CompanyBenefitCondition dynamic rules
    4. QuotationDraft scalar fields
    """
    tokens: list[str] = []
    
    # 1. Draft Benefit Selections
    draft_id = session.draft_id
    selections: list[DraftBenefitSelection] = []
    if draft_id:
        selections = list(
            db.scalars(
                select(DraftBenefitSelection).where(DraftBenefitSelection.draft_id == draft_id)
            ).all()
        )
    
    concept_ids = {s.concept_id for s in selections if s.concept_id}
    concepts: dict[str, BenefitConcept] = {}
    if concept_ids:
        c_list = list(db.scalars(select(BenefitConcept).where(BenefitConcept.id.in_(concept_ids))).all())
        concepts = {c.id: c for c in c_list}
        
    for s in selections:
        if s.label_override:
            tokens.append(s.label_override)
        if s.selection_key:
            tokens.append(s.selection_key)
        c = concepts.get(s.concept_id) if s.concept_id else None
        if c:
            if c.label:
                tokens.append(c.label)
            if c.concept_key:
                tokens.append(c.concept_key)
                
    # 2. Extraction Benefit Lines
    if session.uploaded_file_id:
        ext_lines = list(
            db.scalars(
                select(ExtractionBenefitLine)
                .join(ExtractionRecord, ExtractionBenefitLine.extraction_record_id == ExtractionRecord.id)
                .where(ExtractionRecord.uploaded_file_id == session.uploaded_file_id)
            ).all()
        )
        for el in ext_lines:
            if el.raw_label:
                tokens.append(el.raw_label)
            if el.normalized_label:
                tokens.append(el.normalized_label)
                
    # 3. Add clean scalar fields text (ignore raw JSON/evidence blocks)
    for k in ("special_perils", "optional_covers", "benefits_selected", "extra_benefits", "llp_llop", "towing", "towing_limit", "windscreen_coverage", "windscreen_sum_insured"):
        val = f.get(k)
        if val:
            if isinstance(val, dict):
                clean_v = val.get("value") or val.get("detected_value")
                if clean_v:
                    tokens.append(str(clean_v))
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        clean_item = item.get("value") or item.get("detected_value") or item.get("label")
                        if clean_item:
                            tokens.append(str(clean_item))
                    else:
                        tokens.append(str(item))
            else:
                tokens.append(str(val))

    combined_text = " ".join(tokens).lower()

    # --- SPECIAL PERILS ---
    # Only genuine perils: flood, typhoon, storm, landslide, peril khas, special perils
    has_special_perils = any(
        kw in combined_text
        for kw in (
            "special perils",
            "special peril",
            "peril khas",
            "perils khas",
            "banjir",
            "flood",
            "storm",
            "ribut",
            "typhoon",
            "landslide",
            "tanah runtuh",
            "convulsion of nature",
            "natural disaster",
            "act of god",
        )
    )
    special_perils_val = "Included" if has_special_perils else None

    # --- WINDSCREEN ---
    windscreen_amount: float | None = None

    # Priority 1: Check ExtractionBenefitLine records for explicit extracted limit
    if session.uploaded_file_id:
        ext_lines = list(
            db.scalars(
                select(ExtractionBenefitLine)
                .join(ExtractionRecord, ExtractionBenefitLine.extraction_record_id == ExtractionRecord.id)
                .where(ExtractionRecord.uploaded_file_id == session.uploaded_file_id)
            ).all()
        )
        for el in ext_lines:
            el_text = f"{el.raw_label or ''} {el.normalized_label or ''}".lower()
            if any(w in el_text for w in ("windscreen", "w/screen", "cermin")):
                # Check candidate mappings first (contains coverage_limit)
                for m in (el.candidate_mappings or []):
                    if isinstance(m, dict) and m.get("coverage_limit"):
                        v = _to_float(m.get("coverage_limit"))
                        if _is_valid_windscreen_amt(v):
                            windscreen_amount = v
                            break
                if windscreen_amount:
                    break
                # Check extracted value
                if isinstance(el.extracted_value, dict):
                    v = _to_float(el.extracted_value.get("coverage_limit") or el.extracted_value.get("limit") or el.extracted_value.get("sum_insured") or el.extracted_value.get("value") or el.extracted_value.get("amount"))
                    if _is_valid_windscreen_amt(v):
                        windscreen_amount = v
                        break
                cand_cl = getattr(el, "coverage_limit", None)
                if cand_cl:
                    v = _to_float(cand_cl)
                    if _is_valid_windscreen_amt(v):
                        windscreen_amount = v
                        break
                if windscreen_amount:
                    break

    # Priority 2: Check DraftBenefitSelection records
    if windscreen_amount is None:
        for s in selections:
            s_text = f"{s.label_override or ''} {s.selection_key or ''}".lower()
            if "windscreen" in s_text or "cermin" in s_text:
                if isinstance(s.typed_value_override, dict):
                    t_amt = _to_float(s.typed_value_override.get("coverage") or s.typed_value_override.get("coverage_limit") or s.typed_value_override.get("limit") or s.typed_value_override.get("sum_insured") or s.typed_value_override.get("amount") or s.typed_value_override.get("value"))
                    if _is_valid_windscreen_amt(t_amt):
                        windscreen_amount = t_amt
                        break
                m = re.search(r"(?:rm|myr)\s*([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?|[1-9][0-9]{2,4}(?:\.[0-9]+)?)", s.label_override or "", re.IGNORECASE)
                if m:
                    amt = _to_float(m.group(1).replace(",", ""))
                    if _is_valid_windscreen_amt(amt):
                        windscreen_amount = amt
                        break

    # Priority 3: Check scalar draft fields (windscreen_coverage or windscreen_sum_insured)
    if windscreen_amount is None:
        cand_ws = _to_float(f.get("windscreen_coverage") or f.get("windscreen_sum_insured"))
        if _is_valid_windscreen_amt(cand_ws):
            windscreen_amount = cand_ws

    # Priority 4: Explicit currency tokens mentioning windscreen
    if windscreen_amount is None:
        for tok in tokens:
            if "windscreen" in tok.lower() or "cermin" in tok.lower():
                m = re.search(r"(?:rm|myr)\s*([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?|[1-9][0-9]{2,4}(?:\.[0-9]+)?)", tok, re.IGNORECASE)
                if m:
                    amt = _to_float(m.group(1).replace(",", ""))
                    if _is_valid_windscreen_amt(amt):
                        windscreen_amount = amt
                        break

    # Priority 5: Fallback to tenure target windscreen if windscreen is covered in quote
    if windscreen_amount is None and any(w in combined_text for w in ("windscreen", "w/screen", "cermin")):
        if windscreen_target and _is_valid_windscreen_amt(float(windscreen_target)):
            windscreen_amount = float(windscreen_target)

    # --- LLP / LLOP ---
    has_llp = any(
        kw in combined_text
        for kw in (
            "legal liability to passenger",
            "legal liability of passenger",
            "liability to passenger",
            "liability of passenger",
            "llp",
            "llop",
        )
    )
    llp_val = "Included" if has_llp else None

    # --- TOWING ---
    towing_limit_val: str | None = None
    target_comp_id = company_id or getattr(session, "company_id", None)

    # Grounding from CatalogOfferings in draft catalog revision
    if not towing_limit_val and session and getattr(session, "draft", None) and getattr(session.draft, "catalog_revision_id", None):
        tow_offering = db.scalar(
            select(CatalogOffering)
            .join(BenefitConcept, CatalogOffering.concept_id == BenefitConcept.id)
            .where(
                CatalogOffering.catalog_revision_id == session.draft.catalog_revision_id,
                BenefitConcept.concept_key.in_(["towing", "emergency-towing", "towing-assistance"]),
            )
        )
        if tow_offering:
            if tow_offering.display_value and any(c.isdigit() for c in tow_offering.display_value):
                towing_limit_val = tow_offering.display_value
            elif isinstance(tow_offering.typed_value, dict) and tow_offering.typed_value.get("value"):
                t_val = tow_offering.typed_value.get("value")
                t_unit = tow_offering.typed_value.get("unit") or "KM"
                towing_limit_val = f"{t_val} {t_unit}"

    if not towing_limit_val:
        if any(kw in combined_text for kw in ("motor pa plus 4", "driver plus plan 4", "driver plus 4", "unlimited towing", "24-hr unlimited", "24 hour unlimited")):
            towing_limit_val = "Unlimited"

    # Product tier grounded defaults
    if not towing_limit_val:
        prod_tier_text = f"{f.get('product_name') or ''} {f.get('product_tier') or ''} {f.get('plan_name') or ''} {combined_text}".lower()
        if "premier" in prod_tier_text:
            towing_limit_val = "365 km"
        elif "plus" in prod_tier_text and "driver plus" not in prod_tier_text:
            towing_limit_val = "100 km"
        elif "lite" in prod_tier_text:
            towing_limit_val = "50 km"
        elif any(c in prod_tier_text for c in ("etiqa", "maybank")):
            towing_limit_val = "200 km"
        elif any(c in prod_tier_text for c in ("stmb", "takaful malaysia", "amgen", "amassurance", "qbe", "tune", "sompo", "lonpac")):
            towing_limit_val = "100 km"
        elif "liberty" in prod_tier_text:
            towing_limit_val = "150 km"

    if not towing_limit_val:
        raw_towing = _safe_str(f.get("towing_limit") or f.get("towing"))
        towing_limit_val = raw_towing if raw_towing else "100 km"

    clean_towing = normalize_towing_km(towing_limit_val, combined_text)
    canonical_perils_list = format_canonical_perils(combined_text, tokens)

    # Build detailed perils breakdown with exact price detection
    detailed_perils: list[dict[str, Any]] = []
    seen_peril_names: set[str] = set()

    # 1. From ExtractionBenefitLine records
    if session.uploaded_file_id:
        ext_lines = list(
            db.scalars(
                select(ExtractionBenefitLine)
                .join(ExtractionRecord, ExtractionBenefitLine.extraction_record_id == ExtractionRecord.id)
                .where(ExtractionRecord.uploaded_file_id == session.uploaded_file_id)
            ).all()
        )
        for el in ext_lines:
            lbl = el.raw_label or el.normalized_label
            if not lbl:
                continue
            lbl_clean = lbl.strip()
            norm_k = lbl_clean.lower()
            if norm_k in seen_peril_names:
                continue

            cost_val = 0.0
            limit_val = None
            ev = el.evidence if isinstance(el.evidence, dict) else {}
            if ev.get("premium_cost"):
                cost_val = _to_float(ev.get("premium_cost"))
            if ev.get("coverage_limit"):
                limit_val = str(ev.get("coverage_limit"))

            for m in (el.candidate_mappings or []):
                if isinstance(m, dict):
                    if cost_val == 0.0 and m.get("premium_cost"):
                        cost_val = _to_float(m.get("premium_cost"))
                    if not limit_val and m.get("coverage_limit"):
                        limit_val = str(m.get("coverage_limit"))

            seen_peril_names.add(norm_k)
            detailed_perils.append({
                "name": lbl_clean,
                "coverage_limit": limit_val,
                "premium_cost": cost_val,
                "has_cost": cost_val > 0.0,
                "is_included": cost_val == 0.0 or "included" in str(ev.get("value", "")).lower() or "free" in str(ev.get("value", "")).lower(),
            })

    # 2. Synthesize standard canonical items if not already populated
    if not detailed_perils:
        if windscreen_amount:
            ws_cost = round(windscreen_amount * 0.15, 2)
            detailed_perils.append({
                "name": "Windscreen Protection",
                "coverage_limit": f"RM {windscreen_amount:,.2f}",
                "premium_cost": ws_cost,
                "has_cost": True,
                "is_included": False,
            })
        if special_perils_val:
            detailed_perils.append({
                "name": "Special Perils (Flood & Storm)",
                "coverage_limit": "Vehicle Sum Insured",
                "premium_cost": 0.0,
                "has_cost": False,
                "is_included": True,
            })
        if llp_val:
            detailed_perils.append({
                "name": "Legal Liability to Passengers (LLP)",
                "coverage_limit": "Statutory",
                "premium_cost": 41.85,
                "has_cost": True,
                "is_included": False,
            })
        if "llop" in combined_text or "liability of passenger" in combined_text:
            detailed_perils.append({
                "name": "Legal Liability of Passengers (LLOP)",
                "coverage_limit": "Statutory",
                "premium_cost": 7.50,
                "has_cost": True,
                "is_included": False,
            })
        if clean_towing:
            detailed_perils.append({
                "name": f"Roadside Towing ({clean_towing})",
                "coverage_limit": clean_towing,
                "premium_cost": 0.0,
                "has_cost": False,
                "is_included": True,
            })

    # Bypass normalization for manual overrides
    t_f = f.get("towing", {})
    if isinstance(t_f, dict) and t_f.get("status") == "manual_override":
        clean_towing = str(t_f.get("value") or "")
    sp_f = f.get("special_perils", {})
    if isinstance(sp_f, dict) and sp_f.get("status") == "manual_override":
        special_perils_val = str(sp_f.get("value") or "")
    llp_f = f.get("llp_llop", {})
    if isinstance(llp_f, dict) and llp_f.get("status") == "manual_override":
        llp_val = str(llp_f.get("value") or "")
    ws_f = f.get("windscreen", {})
    if isinstance(ws_f, dict) and ws_f.get("status") == "manual_override":
        windscreen_amount = _to_float(ws_f)

    # --- 3. Unified Benefit Evaluation Engine ---
    plan_name = str(f.get("plan_name") or f.get("product_name") or f.get("product_tier") or combined_text)
    
    base_benefits = []
    if windscreen_amount:
        base_benefits.append(EvaluatedBenefit(concept_id="windscreen", display_title="Windscreen Protection", display_description=f"RM {windscreen_amount:,.2f}"))
    if special_perils_val:
        base_benefits.append(EvaluatedBenefit(concept_id="special_perils", display_title="Special Perils (Flood & Storm)", display_description=special_perils_val))
    if llp_val:
        base_benefits.append(EvaluatedBenefit(concept_id="llp", display_title="Legal Liability to Passengers (LLP)", display_description=llp_val))
    if clean_towing:
        base_benefits.append(EvaluatedBenefit(concept_id="towing", display_title="Roadside Towing", display_description=clean_towing))
        
    target_comp_id = company_id or getattr(session, "company_id", None)
    
    if target_comp_id and base_benefits:
        evaluated = BenefitEvaluationEngine.evaluate_benefits_for_plan(
            db=db,
            company_id=target_comp_id,
            profile_id=None,
            base_benefits=base_benefits,
            plan_name=plan_name
        )
        
        # Apply the evaluated results back to scalars
        eval_map = {b.concept_id: b for b in evaluated if not b.is_hidden}
        
        if "windscreen" not in eval_map:
            windscreen_amount = None
        
        if "special_perils" not in eval_map:
            special_perils_val = None
        else:
            if eval_map["special_perils"].is_modified:
                special_perils_val = eval_map["special_perils"].display_description
                
        if "llp" not in eval_map:
            llp_val = None
        else:
            if eval_map["llp"].is_modified:
                llp_val = eval_map["llp"].display_description
                
        if "towing" not in eval_map:
            clean_towing = None
        else:
            if eval_map["towing"].is_modified:
                clean_towing = eval_map["towing"].display_description
                
        # Update detailed_perils based on engine overrides
        for dp in detailed_perils:
            n_lower = dp["name"].lower()
            if "towing" in n_lower:
                if "towing" not in eval_map:
                    dp["name"] = "HIDDEN"
                elif eval_map["towing"].is_modified:
                    dp["name"] = eval_map["towing"].display_title if eval_map["towing"].display_title != "Roadside Towing" else dp["name"]
                    dp["coverage_limit"] = eval_map["towing"].display_description
            elif "special peril" in n_lower or "flood" in n_lower:
                if "special_perils" not in eval_map:
                    dp["name"] = "HIDDEN"
                elif eval_map["special_perils"].is_modified:
                    dp["name"] = eval_map["special_perils"].display_title if eval_map["special_perils"].display_title != "Special Perils (Flood & Storm)" else dp["name"]
                    dp["coverage_limit"] = eval_map["special_perils"].display_description
            elif "llp" in n_lower or "liability to passenger" in n_lower:
                if "llp" not in eval_map:
                    dp["name"] = "HIDDEN"
                elif eval_map["llp"].is_modified:
                    dp["name"] = eval_map["llp"].display_title if eval_map["llp"].display_title != "Legal Liability to Passengers (LLP)" else dp["name"]
                    dp["coverage_limit"] = eval_map["llp"].display_description

        # Remove hidden perils
        detailed_perils = [dp for dp in detailed_perils if dp["name"] != "HIDDEN"]

    return {
        "special_perils": special_perils_val,
        "windscreen_sum_insured": windscreen_amount,
        "llp_llop": llp_val,
        "towing_limit": clean_towing,
        "towing_km": clean_towing,
        "combined_text": combined_text,
        "canonical_perils": canonical_perils_list,
        "canonical_perils_formatted": ", ".join(canonical_perils_list),
        "detailed_perils": detailed_perils,
    }


def _is_valid_extracted_qno(candidate: str | None) -> bool:
    """Strict validator for insurer quotation numbers: rejects dates, internal codes, and common headers."""
    if not candidate:
        return False
    cand = candidate.strip()
    if len(cand) < 4:
        return False
    cu = cand.upper()
    if cu.startswith("RL26") or cu.startswith("RL-"):
        return False
    _stopwords = {
        "INSURED", "LIBERTY", "TAKAFUL", "POLICYHOLDER", "TOTAL", "PREMIUM",
        "VEHICLE", "DATE", "TIME", "PAGE", "HTTPS", "HTTP", "WWW", "REGISTRATION",
        "MOTOR", "SCHEDULE", "PROPOSAL", "GENERAL", "INSURANCE", "BERHAD", "COMPANY"
    }
    if any(cu.startswith(w) for w in _stopwords):
        return False
    # Reject pure dates (e.g. 04-04-2025 or 2026-05-07)
    if re.match(r"^\d{1,4}[-/]\d{1,2}[-/]\d{1,4}$", cand):
        return False
    return any(c.isdigit() for c in cand)


def _extract_source_quotation_no(session: SessionModel | Any | None = None, draft_fields: dict[str, Any] | None = None) -> str | None:
    """
    Extract the underwriter's exact quotation reference from the uploaded PDF/draft.
    Prioritizes quotation_no / quotation_number / quote_no from draft fields,
    falling back to regex over raw extraction text / OCR text if not yet indexed in fields.
    NEVER returns internal RiskLocker references (RL26...) or pure dates or generic words.
    """
    if not session and not draft_fields:
        return None

    fields = draft_fields or (session.draft.fields if session and session.draft and isinstance(session.draft.fields, dict) else {})

    for key in ("quotation_no", "quotation_number", "quote_no", "quote_number", "source_quotation_no", "schedule_no", "policy_no"):
        val = fields.get(key)
        raw_val = val.get("value") if isinstance(val, dict) else val
        if raw_val and str(raw_val).strip():
            clean = str(raw_val).strip()
            if _is_valid_extracted_qno(clean):
                return clean

    # Check extraction record raw_text or ocr_text if available
    if session and session.uploaded_file and getattr(session.uploaded_file, "extraction_record", None):
        er = session.uploaded_file.extraction_record
        text_corpus = (er.raw_text or "") + "\n" + (er.ocr_text or "")
        if text_corpus:
            patterns = [
                # Berjaya Sompo: QM followed by 8 digits
                r"\b(QM\d{8})\b",
                # STMB / Takaful: QF followed by 7-8 digits and optional sub-quote
                r"\b(QF\d{7,8}(?:-\d{3})?)\b",
                r"qno=(QF\d{7,8}(?:-\d{3})?)",
                # Etiqa: FL followed by year/digits (e.g. FL22026M-00867209-001)
                r"\b(FL\d{5,}[A-Z0-9-]*)\b",
                # QBE: MPA-XX-XX-XXXXXX
                r"\b(MPA-\d{2}-\d{2}-\d{6,8})\b",
                # AmGen / Liberty: Quotation Ref No.QC590226-001 or code tokens
                r"Quotation\s*Ref(?:\s*No\.?|\s*No|\.?)[:\s]*([A-Z0-9-]{6,30})",
                r"\b([Q][BCD]\d{6}(?:-\d{1,3})?)\b",
                # Lonpac: QJV...
                r"\b(QJV[A-Z0-9]+)\b",
                # Tune: QT-... or numeric quote no
                r"\b(QT-[A-Z0-9]{7,12})\b",
                r"Quotation\s*No\.?\s*[:\-]?\s*(Q\d{6,})",
                r"\b(1000\d{6})\b",
                # Sompo layout: code placed directly before 'Quotation no.'
                r"\b([A-Za-z0-9][A-Za-z0-9\-_/]{5,25})\s*\r?\n\s*Quotation\s*no\.?",
                # Multi-line bilingual label formats
                r"(?i)\b(?:quotation\s*(?:no\.?|number|#)?|quote\s*(?:no\.?|number|#)?|no\.?\s*sebutharga|sebutharga\s*no\.?)\s*(?:\r?\n\s*no\.?\s*(?:quotation|sebut\s*harga))?\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9\-_/]{4,35})",
                r"(?i)\b(?:proposal\s*(?:no\.?|number|#)?|schedule\s*(?:no\.?|number|#)?)\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9\-_/]{4,35})\b",
            ]
            for pat in patterns:
                m = re.search(pat, text_corpus, re.I)
                if m:
                    candidate = m.group(1).strip()
                    if _is_valid_extracted_qno(candidate):
                        if session.draft and isinstance(session.draft.fields, dict):
                            session.draft.fields["quotation_no"] = {"value": candidate, "status": "ready", "message": ""}
                        return candidate

    return None


def get_marketing_comparison(db: Session, tenure_id: str) -> dict[str, Any]:
    """Retrieve or auto-hydrate the full marketing comparison matrix for an insurance tenure.
    
    Returns:
        Structured comparison payload containing:
        - tenure metadata & fixed costs (road tax + runner fee)
        - side-by-side underwriter comparison columns
        - previous policy year reference card (Year - 1)
        - recommended sum insured / valuation matrix
        - NCD status
    """
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise ValueError(f"Tenure {tenure_id} not found")

    # 1. Inspect existing comparison entries
    entries = list(
        db.scalars(
            select(TenureComparisonEntry)
            .where(TenureComparisonEntry.tenure_id == tenure_id)
            .order_by(TenureComparisonEntry.sort_order.asc(), TenureComparisonEntry.created_at.asc())
        ).all()
    )

    needs_commit = False

    # 2. Query all linked sessions under this tenure (with preloaded drafts)
    sessions = list(
        db.scalars(
            select(SessionModel)
            .options(selectinload(SessionModel.draft))
            .where(
                SessionModel.tenure_id == tenure_id,
                SessionModel.status != "trash",
            )
            .order_by(SessionModel.created_at.asc())
        ).all()
    )
    session_map = {s.id: s for s in sessions}

    # Clean up any comparison entries erroneously created for Cover Note sessions
    valid_entries = []
    for e in entries:
        sess = session_map.get(e.session_id) if e.session_id else None
        if sess and getattr(sess, "document_type", "quotation") == "covernote":
            db.delete(e)
            needs_commit = True
        else:
            valid_entries.append(e)
    entries = valid_entries

    # Separate quotation sessions from cover note sessions
    quote_sessions = [s for s in sessions if getattr(s, "document_type", "quotation") != "covernote"]

    sessions_desc = sorted(
        sessions,
        key=lambda s: s.created_at or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    # Gather candidate customer IC / passport for runner fee detection
    cand_ic = ""
    for s in sessions_desc:
        if s.draft and isinstance(s.draft.fields, dict):
            f = s.draft.fields
            if not cand_ic:
                cand_ic = _safe_str(f.get("ic_no") or f.get("nric") or f.get("ic_or_brn") or f.get("passport_no"))

    # Detect road tax and runner fee with JPJ Mathematical Engine integration
    from app.services.road_tax_service import calculate_road_tax
    from app.services.vehicle_catalog_service import infer_vehicle_cc_and_type
    from app.extraction.entity_classifier import classify_client_entity

    road_tax_val = float(tenure.road_tax)
    runner_fee_val = float(tenure.runner_fee)

    detected_cc = None
    detected_model = None
    detected_brand = None
    detected_vtype = "Car"
    detected_client_type = "Individual"
    is_detected_ev = False
    raw_capacity_token = None

    for s in sessions_desc:
        if s.draft and isinstance(s.draft.fields, dict):
            f = s.draft.fields
            if road_tax_val == 0.0:
                cand_rt = _to_float(f.get("roadtax") or f.get("road_tax"))
                if cand_rt > 0.0:
                    road_tax_val = cand_rt
            if not detected_model:
                detected_model = _safe_str(f.get("car_model") or f.get("vehicle_model"))
            if not detected_brand:
                detected_brand = _safe_str(f.get("car_brand") or f.get("make"))
            if not detected_cc:
                raw_cc = _safe_str(f.get("engine_cc") or f.get("capacity"))
                if not raw_cc and tenure.tracked_vehicle:
                    raw_cc = _safe_str(tenure.tracked_vehicle.engine_cc)
                if raw_cc:
                    raw_cc_lower = raw_cc.lower()
                    m_cc = re.search(r"(\d+(?:\.\d+)?)", raw_cc)
                    if m_cc:
                        try:
                            val_cc = float(m_cc.group(1))
                            if "kw" in raw_cc_lower or "watt" in raw_cc_lower or (val_cc <= 35.0 and ("." in m_cc.group(1) or val_cc <= 25.0)):
                                detected_cc = val_cc
                                is_detected_ev = True
                                raw_capacity_token = f"{val_cc} kW"
                            else:
                                detected_cc = val_cc
                                raw_capacity_token = f"{val_cc} CC"
                        except Exception:
                            pass
            if f.get("client_type") and not detected_client_type:
                detected_client_type = _safe_str(f.get("client_type"))
            if f.get("vehicle_type") and not detected_vtype:
                detected_vtype = _safe_str(f.get("vehicle_type"))

    inferred_cc, inferred_vtype = infer_vehicle_cc_and_type(detected_model)
    final_cc = detected_cc or inferred_cc
    if final_cc and not raw_capacity_token:
        raw_capacity_token = f"{final_cc} kW" if is_detected_ev else f"{final_cc} CC"

    comb_lower = f"{detected_vtype or ''} {inferred_vtype or ''} {detected_model or ''} {detected_brand or ''}".lower()
    is_ev_brand = any(b in comb_lower for b in ["tesla", "byd", "zeekr", "xpeng", "nio", "ora", "taycan", "smart #", "ioniq", "ev6"])
    if is_ev_brand:
        is_detected_ev = True

    fallback_vtype = "Car"
    if is_detected_ev:
        is_bike = any(w in comb_lower for w in ["motorcycle", "motorbike", "bike", "scooter", "moped", "kapcai", "2-wheeler", "two-wheeler"]) and not any(c in comb_lower for c in ["car", "saloon", "sedan", "tesla", "suv", "mpv", "wagon", "hatchback"])
        if is_bike:
            fallback_vtype = "EVMotorcycle"
        elif any(s in comb_lower for s in ["suv", "mpv", "non-saloon", "nonsaloon", "4x4"]):
            fallback_vtype = "EVNonSaloonCar"
        else:
            fallback_vtype = "EVSaloonCar"

    entity_type, resolved_vtype = classify_client_entity(
        customer_name="",
        ic_or_brn=cand_ic,
        ai_client_type=detected_client_type,
        current_vehicle_type=detected_vtype or inferred_vtype or fallback_vtype,
        car_model=detected_model,
        car_brand=detected_brand,
        capacity_str=raw_capacity_token,
    )

    calculated_jpj_road_tax = 0.0
    if final_cc:
        calculated_jpj_road_tax = calculate_road_tax(
            cc=f"{final_cc} kW" if is_detected_ev else final_cc,
            vehicle_type=resolved_vtype,
            owner_type=entity_type,
            jurisdiction="West Malaysia",
        )

    if float(tenure.road_tax) > 0.0:
        road_tax_val = float(tenure.road_tax)
    elif calculated_jpj_road_tax > 0.0:
        road_tax_val = calculated_jpj_road_tax
        tenure.road_tax = calculated_jpj_road_tax
        needs_commit = True

    if float(tenure.runner_fee) > 0.0:
        runner_fee_val = float(tenure.runner_fee)
    else:
        calc_runner = detect_runner_fee_from_id(cand_ic)
        if calc_runner > 0.0:
            runner_fee_val = calc_runner
            tenure.runner_fee = calc_runner
            needs_commit = True

    # 3. Resolve Vehicle Year of Manufacture (YOM) and Age
    veh_yom = getattr(tenure.tracked_vehicle, "manufacture_year", None) if tenure.tracked_vehicle else None
    if not veh_yom:
        for s in sessions:
            if s.draft and isinstance(s.draft.fields, dict):
                cand_yom = _extract_vehicle_year_from_draft(s.draft.fields)
                if cand_yom:
                    veh_yom = cand_yom
                    if tenure.tracked_vehicle:
                        tenure.tracked_vehicle.manufacture_year = cand_yom
                        needs_commit = True
                    break
    veh_age = calculate_vehicle_age(veh_yom, tenure.coverage_start_date)

    # 4. If no entries exist yet, auto-hydrate from quotation sessions under this tenure
    if not entries:
        for idx, s in enumerate(quote_sessions):
            comp_name = s.detected_company or (s.uploaded_file.original_filename if s.uploaded_file else f"Quote #{idx+1}")
            f = s.draft.fields if s.draft and s.draft.fields else {}

            sum_ins = _extract_vehicle_sum_insured(f, s_obj=s)
            motor_prem = _extract_vehicle_motor_premium(f)
            val_type, agreed = _extract_valuation_type(f, s_obj=s)
            excess_val = _extract_excess(f, s_obj=s)
            rate_val = round((motor_prem / sum_ins) * 100, 4) if sum_ins > 0 else None
            tot_pay = motor_prem + float(tenure.road_tax) + float(tenure.runner_fee)

            b_res = _resolve_comparison_benefits(
                db, s, getattr(s, "company_id", None), f, float(tenure.windscreen_target) if tenure.windscreen_target else None
            )
            raw_w = _extract_val(f.get("waiver_of_betterment"))
            has_peril = check_has_betterment_peril(f, b_res.get("combined_text", ""), raw_w)
            quote_year = tenure.coverage_start_date.year if tenure.coverage_start_date else datetime.now().year
            has_waiver, bet_rate, bet_disp = evaluate_betterment_rules(
                yom=veh_yom,
                quote_year=quote_year,
                company_name=comp_name,
                has_betterment_peril=has_peril,
                is_comprehensive_private=True,
            )

            entry = TenureComparisonEntry(
                tenure_id=tenure_id,
                session_id=s.id,
                company_name=comp_name,
                company_id=getattr(s, "company_id", None),
                sum_insured=sum_ins,
                valuation_type=val_type,
                motor_premium=motor_prem,
                road_tax=float(tenure.road_tax),
                runner_fee=float(tenure.runner_fee),
                total_payable=tot_pay,
                towing_limit=b_res["towing_km"],
                towing_km=b_res["towing_km"],
                agreed_value=agreed,
                waiver_betterment=has_waiver,
                betterment_rate=bet_rate,
                betterment_display=bet_disp,
                excess=excess_val,
                rate_percentage=rate_val,
                windscreen_sum_insured=b_res["windscreen_sum_insured"],
                special_perils=b_res["special_perils"],
                llp_llop=b_res["llp_llop"],
                sort_order=idx,
                is_recommended=bool(
                    (tenure.winning_quotation_ref and s.quotation_ref == tenure.winning_quotation_ref)
                    or (tenure.winning_company_id and getattr(s, "company_id", None) == tenure.winning_company_id)
                ),
            )
            db.add(entry)
            entries.append(entry)

        needs_commit = True
    else:
        # Synchronize any quotation sessions under this tenure that don't have a comparison entry yet
        existing_sess_ids = {e.session_id for e in entries if e.session_id}
        unlinked_sessions = [s for s in quote_sessions if s.id not in existing_sess_ids]
        if unlinked_sessions:
            for idx, s in enumerate(unlinked_sessions):
                comp_name = s.detected_company or (s.uploaded_file.original_filename if s.uploaded_file else f"Quote #{len(entries)+idx+1}")
                f = s.draft.fields if s.draft and s.draft.fields else {}

                sum_ins = _extract_vehicle_sum_insured(f, s_obj=s)
                motor_prem = _extract_vehicle_motor_premium(f)
                val_type, agreed = _extract_valuation_type(f, s_obj=s)
                excess_val = _extract_excess(f, s_obj=s)
                rate_val = round((motor_prem / sum_ins) * 100, 4) if sum_ins > 0 else None
                tot_pay = motor_prem + float(tenure.road_tax) + float(tenure.runner_fee)

                b_res = _resolve_comparison_benefits(
                    db, s, getattr(s, "company_id", None), f, float(tenure.windscreen_target) if tenure.windscreen_target else None
                )
                raw_w = _extract_val(f.get("waiver_of_betterment"))
                has_peril = check_has_betterment_peril(f, b_res.get("combined_text", ""), raw_w)
                quote_year = tenure.coverage_start_date.year if tenure.coverage_start_date else datetime.now().year
                has_waiver, bet_rate, bet_disp = evaluate_betterment_rules(
                    yom=veh_yom,
                    quote_year=quote_year,
                    company_name=comp_name,
                    has_betterment_peril=has_peril,
                    is_comprehensive_private=True,
                )

                new_entry = TenureComparisonEntry(
                    tenure_id=tenure_id,
                    session_id=s.id,
                    company_name=comp_name,
                    company_id=getattr(s, "company_id", None),
                    sum_insured=sum_ins,
                    valuation_type=val_type,
                    motor_premium=motor_prem,
                    road_tax=float(tenure.road_tax),
                    runner_fee=float(tenure.runner_fee),
                    total_payable=tot_pay,
                    towing_limit=b_res["towing_km"],
                    towing_km=b_res["towing_km"],
                    agreed_value=agreed,
                    waiver_betterment=has_waiver,
                    betterment_rate=bet_rate,
                    betterment_display=bet_disp,
                    excess=excess_val,
                    rate_percentage=rate_val,
                    windscreen_sum_insured=b_res["windscreen_sum_insured"],
                    special_perils=b_res["special_perils"],
                    llp_llop=b_res["llp_llop"],
                    sort_order=len(entries) + idx,
                    is_recommended=bool(
                        (tenure.winning_quotation_ref and s.quotation_ref == tenure.winning_quotation_ref)
                        or (tenure.winning_company_id and getattr(s, "company_id", None) == tenure.winning_company_id)
                    ),
                )
                db.add(new_entry)
                entries.append(new_entry)
            needs_commit = True

        # Parity check: synchronize fixed costs (road tax, runner fee) and fallback betterment rates without clobbering user edits
        for e in entries:
            # Sync road tax & runner fee from tenure if changed
            if abs(float(e.road_tax) - float(tenure.road_tax)) > 0.01 or abs(float(e.runner_fee) - float(tenure.runner_fee)) > 0.01:
                e.road_tax = float(tenure.road_tax)
                e.runner_fee = float(tenure.runner_fee)
                e.total_payable = float(e.motor_premium) + float(e.road_tax) + float(e.runner_fee)
                needs_commit = True

            quote_year = tenure.coverage_start_date.year if tenure.coverage_start_date else datetime.now().year
            has_waiver_fallback, fallback_bet_rate, fallback_bet_disp = evaluate_betterment_rules(
                yom=veh_yom,
                quote_year=quote_year,
                company_name=e.company_name,
                has_betterment_peril=e.waiver_betterment,
                is_comprehensive_private=True,
            )
            if e.betterment_rate is None or e.betterment_display is None:
                e.betterment_rate = fallback_bet_rate
                e.betterment_display = fallback_bet_disp
                needs_commit = True

            if not e.towing_km and not e.towing_limit:
                e.towing_km = "Unlimited"
                e.towing_limit = "Unlimited"
                needs_commit = True

            # If not manual override, heal uninitialized or corrupted values from draft
            if not e.is_manual and e.session_id:
                s = session_map.get(e.session_id)
                if s and s.draft and s.draft.fields:
                    f = s.draft.fields
                    h_sum = _extract_vehicle_sum_insured(f, s_obj=s)
                    h_prem = _extract_vehicle_motor_premium(f)
                    val_type, is_agr = _extract_valuation_type(f, s_obj=s)
                    excess_val = _extract_excess(f, s_obj=s)

                    if float(e.sum_insured or 0.0) == 0.0:
                        if h_sum > 0.0:
                            e.sum_insured = h_sum
                        if h_prem > 0.0:
                            e.motor_premium = h_prem
                        e.valuation_type = val_type
                        e.agreed_value = is_agr
                        e.excess = excess_val
                        e.total_payable = float(e.motor_premium) + float(e.road_tax) + float(e.runner_fee)
                        ws_val = _extract_windscreen_from_draft(f)
                        if ws_val and _is_valid_windscreen_amt(ws_val):
                            e.windscreen_sum_insured = ws_val
                        needs_commit = True

                    # Heal invalid windscreen (corrupt reference numbers like 283233.0)
                    ws_invalid = e.windscreen_sum_insured is not None and not _is_valid_windscreen_amt(float(e.windscreen_sum_insured))
                    if ws_invalid:
                        b_cand = _resolve_comparison_benefits(
                            db, s, getattr(s, "company_id", None), f, float(tenure.windscreen_target) if tenure.windscreen_target else None
                        )
                        cand_ws = b_cand.get("windscreen_sum_insured")
                        if cand_ws and _is_valid_windscreen_amt(cand_ws):
                            e.windscreen_sum_insured = cand_ws
                        else:
                            e.windscreen_sum_insured = None
                        if b_cand.get("towing_km"):
                            e.towing_km = b_cand["towing_km"]
                            e.towing_limit = b_cand["towing_km"]
                        needs_commit = True

    # 5. Apply 4-tier Best Deal ranking
    rank_comparison_entries(
        entries,
        explicit_winning_company_id=tenure.winning_company_id,
        explicit_winning_ref=tenure.winning_quotation_ref,
        auto_recommend_rank1=False,
    )

    # 6. Assign stable version numbers for same-insurer revisions
    company_counts: dict[str, int] = defaultdict(int)
    def _entry_sort_key(x: Any) -> tuple[datetime, str]:
        s = session_map.get(getattr(x, "session_id", None)) if getattr(x, "session_id", None) else None
        dt = getattr(x, "uploaded_at", None) or (s.created_at if s else None) or getattr(x, "created_at", None)
        if not dt:
            return (datetime.min.replace(tzinfo=timezone.utc), getattr(x, "id", "") or "")
        if getattr(dt, "tzinfo", None) is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (dt, getattr(x, "id", "") or "")

    for e in sorted(entries, key=_entry_sort_key):
        key = (e.company_name or "Unknown").strip().lower()
        company_counts[key] += 1
        e.version = company_counts[key]

    if needs_commit:
        db.commit()


    # 3. Retrieve Previous Policy (Strictly prior calendar year e.g. 2026 for 2027 tenure)
    current_year = tenure.coverage_start_date.year if tenure.coverage_start_date else datetime.now().year
    year_start_date = datetime(current_year, 1, 1).date() if isinstance(tenure.coverage_start_date, datetime) else date(current_year, 1, 1)

    prev_tenure = None
    if tenure.previous_tenure_id:
        prev_tenure = db.get(InsuranceTenure, tenure.previous_tenure_id)

    if not prev_tenure:
        prev_tenure = db.scalar(
            select(InsuranceTenure)
            .where(
                or_(
                    InsuranceTenure.tracked_vehicle_id == tenure.tracked_vehicle_id,
                    InsuranceTenure.vehicle_no == tenure.vehicle_no,
                ),
                InsuranceTenure.id != tenure.id,
                InsuranceTenure.coverage_start_date < year_start_date,
            )
            .order_by(InsuranceTenure.coverage_start_date.desc())
            .limit(1)
        )

    prev_policy_data = None
    if prev_tenure:
        prev_entries = list(
            db.scalars(
                select(TenureComparisonEntry)
                .where(TenureComparisonEntry.tenure_id == prev_tenure.id)
                .order_by(TenureComparisonEntry.is_recommended.desc(), TenureComparisonEntry.total_payable.asc())
            ).all()
        )
        best_prev = prev_entries[0] if prev_entries else None

        # Extract canonical perils from previous policy session if available
        prev_perils: list[str] = []
        best_prev_sess = None
        if best_prev and best_prev.session_id:
            best_prev_sess = db.get(SessionModel, best_prev.session_id)
        elif not best_prev:
            # Fallback to the latest active session under prev_tenure
            best_prev_sess = db.scalars(
                select(SessionModel)
                .options(selectinload(SessionModel.draft))
                .where(SessionModel.tenure_id == prev_tenure.id, SessionModel.status != "trash")
                .order_by(SessionModel.created_at.desc())
            ).first()

        prev_sum_ins = float(best_prev.sum_insured) if best_prev else 0.0
        prev_motor_prem = float(prev_tenure.won_premium) if prev_tenure.won_premium is not None else (float(best_prev.motor_premium) if best_prev else 0.0)
        prev_company = (prev_tenure.winning_company.name if prev_tenure.winning_company else None) or (best_prev.company_name if best_prev else None)

        if best_prev_sess:
            p_f = best_prev_sess.draft.fields if best_prev_sess.draft and isinstance(best_prev_sess.draft.fields, dict) else {}
            p_res = _resolve_comparison_benefits(
                db, best_prev_sess, getattr(best_prev_sess, "company_id", None), p_f, None
            )
            prev_perils = p_res.get("canonical_perils") or []
            if not prev_company:
                prev_company = best_prev_sess.detected_company
            if prev_sum_ins <= 0.0:
                prev_sum_ins = _extract_vehicle_sum_insured(p_f, s_obj=best_prev_sess)
            if prev_motor_prem <= 0.0:
                prev_motor_prem = _extract_vehicle_motor_premium(p_f)

        prev_perils_str = ", ".join(prev_perils) if prev_perils else "Standard Policy Coverage"

        prev_policy_data = {
            "id": prev_tenure.id,
            "year": prev_tenure.coverage_start_date.year if prev_tenure.coverage_start_date else (current_year - 1),
            "period": f"{prev_tenure.coverage_start_date.strftime('%d/%m/%Y')} - {prev_tenure.coverage_end_date.strftime('%d/%m/%Y')}" if (prev_tenure.coverage_start_date and prev_tenure.coverage_end_date) else f"{current_year - 1}",
            "insurer": prev_company or "Previous Insurer",
            "sum_insured": prev_sum_ins,
            "insurance_premium": prev_motor_prem,
            "perils": prev_perils_str,
            "model": (tenure.tracked_vehicle.car_model if tenure.tracked_vehicle else None) or (prev_tenure.tracked_vehicle.car_model if prev_tenure.tracked_vehicle else "Standard Model"),
            "yom": getattr(tenure.tracked_vehicle, "manufacture_year", None) or getattr(prev_tenure.tracked_vehicle, "manufacture_year", None) or 2023,
            "sub_agent": tenure.sub_agent_name or prev_tenure.sub_agent_name or "",
            "windscreen": float(best_prev.windscreen_sum_insured) if best_prev and best_prev.windscreen_sum_insured else None,
            "towing": best_prev.towing_km or best_prev.towing_limit if best_prev else "Unlimited",
        }

        # Carry over NCD percentage if not yet set on current tenure
        if tenure.ncd_percentage is None and prev_tenure.ncd_percentage is not None:
            tenure.ncd_percentage = prev_tenure.ncd_percentage
            needs_commit = True

    # 4. Formulate Recommended Sum Insured matrix
    # 4. Formulate Recommended Sum Insured matrix (genuine underwriter figures only)
    rec_sum_insured = tenure.recommended_sum_insured_json or {}
    if (not rec_sum_insured or all(v == 0.0 for v in rec_sum_insured.values())) and entries:
        rec_sum_insured = {}
        for e in entries:
            clean_c = e.company_name.split()[0]
            if float(e.sum_insured) > 0.0:
                rec_sum_insured[clean_c] = float(e.sum_insured)

    # Aggregate customer & vehicle metadata from linked sessions and master records
    # Strict Waterfall re-extraction: newest PDF first (sessions_desc)
    waterfall_cust_name = ""
    waterfall_ic = ""
    waterfall_phone = ""
    waterfall_email = ""
    waterfall_address = ""
    waterfall_plate = ""
    waterfall_model = ""
    waterfall_brand = ""
    waterfall_engine_no = ""
    waterfall_chassis_no = ""
    waterfall_engine_cc = ""
    waterfall_yom = None

    for s in sessions_desc:
        if s.draft and isinstance(s.draft.fields, dict):
            f = s.draft.fields
            if not waterfall_cust_name:
                cand_nm = _safe_str(f.get("customer_name") or f.get("insured_name") or f.get("client_name"))
                if cand_nm and not cand_nm.upper().startswith("UNSPECIFIED"):
                    waterfall_cust_name = cand_nm
            if not waterfall_ic or waterfall_ic.upper().startswith("PENDING-"):
                cand_id = _safe_str(f.get("ic_no") or f.get("nric") or f.get("ic_or_brn") or f.get("passport_no"))
                if cand_id and not cand_id.upper().startswith("PENDING-"):
                    from app.services.identity_normalization_service import normalize_government_id
                    norm_id, id_t = normalize_government_id(cand_id)
                    if id_t in ("nric", "brn_new", "brn_old", "passport"):
                        waterfall_ic = norm_id
            if not waterfall_phone:
                p = _safe_str(f.get("phone_number") or f.get("contact_no") or f.get("mobile"))
                if p:
                    waterfall_phone = p
            if not waterfall_email:
                em = _safe_str(f.get("email"))
                if em:
                    waterfall_email = em
            if not waterfall_address:
                addr = _safe_str(f.get("address") or f.get("location"))
                if addr:
                    waterfall_address = addr
            if not waterfall_plate:
                raw_p = _safe_str(f.get("vehicle_no") or f.get("vehicle_number") or f.get("reg_no"))
                clean_p = re.sub(r"\s+", "", raw_p.upper())
                if clean_p and clean_p not in ("UNREGISTERED", "NEW", "UNKNOWN", "N/A", "PENDING", "-", "--"):
                    if not clean_p.startswith("RM") and not re.fullmatch(r"20\d{2}|19\d{2}", clean_p):
                        waterfall_plate = raw_p.strip().upper()
            if not waterfall_model:
                m = _safe_str(f.get("car_model") or f.get("vehicle_model"))
                if m:
                    waterfall_model = m
            if not waterfall_brand:
                b = _safe_str(f.get("car_brand") or f.get("make"))
                if b:
                    waterfall_brand = b
            if not waterfall_engine_no:
                eno = _safe_str(f.get("engine_number") or f.get("engine_no"))
                if eno:
                    waterfall_engine_no = eno
            if not waterfall_chassis_no:
                chn = _safe_str(f.get("chassis_number") or f.get("chassis_no") or f.get("vin"))
                if chn:
                    waterfall_chassis_no = chn
            if not waterfall_engine_cc:
                ecc = _safe_str(f.get("engine_cc") or f.get("capacity"))
                if ecc:
                    waterfall_engine_cc = ecc
            if not waterfall_yom:
                raw_yom = f.get("manufacture_year") or f.get("year_of_manufacture") or f.get("yom") or f.get("vehicle_year")
                if raw_yom:
                    try:
                        y_int = int(re.sub(r"[^\d]", "", str(raw_yom))[:4])
                        if 1980 <= y_int <= 2035:
                            waterfall_yom = y_int
                    except (ValueError, TypeError):
                        pass

    # Fallback to existing tenure records only if missing across ALL uploaded sessions
    cust_name = waterfall_cust_name or tenure.customer_name or (tenure.customer.canonical_name if tenure.customer else "")
    cust_ic = waterfall_ic or (tenure.customer.id_number if tenure.customer else "")
    cust_phone = waterfall_phone or (tenure.customer.phone if tenure.customer else "")
    cust_email = waterfall_email or (tenure.customer.email if tenure.customer else "")
    cust_address = waterfall_address or (tenure.customer.address if tenure.customer else "")

    veh_plate = waterfall_plate or tenure.vehicle_no or (tenure.tracked_vehicle.vehicle_no if tenure.tracked_vehicle else "")
    veh_model = waterfall_model or (tenure.tracked_vehicle.car_model if tenure.tracked_vehicle else "")
    veh_engine_no = waterfall_engine_no or (tenure.tracked_vehicle.engine_no if tenure.tracked_vehicle else "")
    veh_chassis_no = waterfall_chassis_no or (tenure.tracked_vehicle.chassis_no if tenure.tracked_vehicle else "")
    veh_engine_cc = waterfall_engine_cc or (tenure.tracked_vehicle.engine_cc if tenure.tracked_vehicle else "")
    veh_yom = waterfall_yom or (getattr(tenure.tracked_vehicle, "manufacture_year", None) if tenure.tracked_vehicle else None)
    veh_seating = "5"

    clean_final_plate = re.sub(r"\s+", "", (veh_plate or "").upper())
    is_plate_undetected = (
        not veh_plate
        or clean_final_plate in ("UNREGISTERED", "NEW", "UNKNOWN", "N/A", "PENDING", "-", "--", "")
        or clean_final_plate.startswith("RM")
    )
    final_plate_display = "N/A" if is_plate_undetected else clean_final_plate
    tracking_by_chassis = bool(is_plate_undetected and veh_chassis_no)

    if cust_name and tenure.customer_name != cust_name:
        tenure.customer_name = cust_name
        if tenure.customer:
            tenure.customer.canonical_name = cust_name
        needs_commit = True
    if cust_ic and tenure.customer and tenure.customer.id_number != cust_ic:
        existing_cust = db.query(CustomerAccount).filter(CustomerAccount.id_number == cust_ic).first()
        if existing_cust:
            if existing_cust.id != tenure.customer_id:
                tenure.customer_id = existing_cust.id
        else:
            tenure.customer.id_number = cust_ic
        needs_commit = True
    if cust_phone and tenure.customer and not tenure.customer.phone:
        tenure.customer.phone = cust_phone
        needs_commit = True
    if cust_email and tenure.customer and not tenure.customer.email:
        tenure.customer.email = cust_email
        needs_commit = True
    if cust_address and tenure.customer and not tenure.customer.address:
        tenure.customer.address = cust_address
        needs_commit = True

    if final_plate_display != "N/A" and tenure.vehicle_no != final_plate_display:
        tenure.vehicle_no = final_plate_display
        needs_commit = True

    if tenure.tracked_vehicle:
        if veh_model and tenure.tracked_vehicle.car_model != veh_model:
            tenure.tracked_vehicle.car_model = veh_model
            needs_commit = True
        if waterfall_brand and tenure.tracked_vehicle.car_brand != waterfall_brand:
            tenure.tracked_vehicle.car_brand = waterfall_brand
            needs_commit = True
        if veh_engine_no and tenure.tracked_vehicle.engine_no != veh_engine_no:
            tenure.tracked_vehicle.engine_no = veh_engine_no
            needs_commit = True
        if veh_chassis_no and tenure.tracked_vehicle.chassis_no != veh_chassis_no:
            tenure.tracked_vehicle.chassis_no = veh_chassis_no
            needs_commit = True
        if veh_engine_cc and tenure.tracked_vehicle.engine_cc != veh_engine_cc:
            tenure.tracked_vehicle.engine_cc = veh_engine_cc
            needs_commit = True
        if veh_yom and getattr(tenure.tracked_vehicle, "manufacture_year", None) != veh_yom:
            tenure.tracked_vehicle.manufacture_year = veh_yom
            needs_commit = True
        tv_clean = re.sub(r"\s+", "", (tenure.tracked_vehicle.vehicle_no or "").upper())
        if final_plate_display != "N/A" and tv_clean != clean_final_plate:
            existing_other_veh = db.scalar(
                select(TrackedVehicle).where(
                    or_(
                        TrackedVehicle.vehicle_no == final_plate_display,
                        func.replace(TrackedVehicle.vehicle_no, " ", "") == clean_final_plate,
                    ),
                    TrackedVehicle.id != tenure.tracked_vehicle.id,
                )
            )
            if existing_other_veh:
                tenure.tracked_vehicle = existing_other_veh
                tenure.tracked_vehicle_id = existing_other_veh.id
            else:
                tenure.tracked_vehicle.vehicle_no = final_plate_display
            needs_commit = True

    if veh_model:
        from app.services.vehicle_simplifier_service import clean_vehicle_tokens_deterministic, CANONICAL_BRANDS
        tb = tenure.tracked_vehicle.car_brand if tenure.tracked_vehicle else None
        if tb and any(veh_model.upper().startswith(k) for k in CANONICAL_BRANDS.keys()):
            pass_brand = None
        else:
            pass_brand = tb
        _, _, simp_combined = clean_vehicle_tokens_deterministic(pass_brand, veh_model)
        if simp_combined:
            veh_model = simp_combined
    # 4. Resolve NCD and In-Flight Jobs
    cand_ncd: float | None = None
    if tenure.ncd_percentage is not None:
        cand_ncd = float(tenure.ncd_percentage)
    else:
        for s in sessions:
            if s.draft and isinstance(s.draft.fields, dict):
                ext_ncd = _extract_ncd_from_draft(s.draft.fields)
                if ext_ncd is not None:
                    cand_ncd = ext_ncd
                    tenure.ncd_percentage = cand_ncd
                    needs_commit = True
                    break

    current_ncd, next_ncd = calculate_ncd_pair(cand_ncd)

    # Count pending/processing jobs
    pending_jobs_count = 0
    session_ids = [s.id for s in sessions]
    if session_ids:
        pending_jobs_count = db.scalar(
            select(func.count(Job.id)).where(
                Job.session_id.in_(session_ids),
                Job.state.in_(["queued", "claimed", "processing", "extracting", "saving_review"]),
            )
        ) or 0
    elif tenure.id:
        pending_jobs_count = db.scalar(
            select(func.count(Job.id)).where(
                Job.state.in_(["queued", "claimed", "processing", "extracting", "saving_review"]),
                Job.payload["tenure_id"].as_string() == tenure.id,
            )
        ) or 0

    if needs_commit:
        db.commit()

    # 7. Year reconciliation across multi-quote uploads: only flag if quotes belong to different calendar years
    session_years = [s.coverage_start_date.year for s in sessions if s.coverage_start_date]
    date_conflict = None
    if len(set(session_years)) > 1:
        majority_yr = max(set(session_years), key=session_years.count)
        date_conflict = {
            "has_conflict": True,
            "majority_year": majority_yr,
            "unique_years": sorted(list(set(session_years))),
            "message": f"Quotes from multiple calendar years detected ({', '.join(str(y) for y in sorted(set(session_years)))}).",
        }

    # 8. Query generated quotations for this vehicle/deal
    gen_quotes = []
    for s in sessions:
        if s.quotation_ref and s.quotation_ref.startswith("RL"):
            pdf_ver = db.scalar(
                select(GeneratedPdfVersion)
                .where(GeneratedPdfVersion.draft_id == s.draft_id)
                .order_by(GeneratedPdfVersion.version_number.desc())
                .limit(1)
            ) if s.draft_id else None

            tot_p = 0.0
            if s.draft and isinstance(s.draft.fields, dict):
                tot_p = _to_float(s.draft.fields.get("total_payable") or s.draft.fields.get("total_amount"))

            gen_quotes.append({
                "session_id": s.id,
                "draft_id": s.draft_id,
                "quotation_ref": s.quotation_ref,
                "company_name": s.detected_company or "Underwriter",
                "status": s.quotation_status or "ready",
                "version_number": pdf_ver.version_number if pdf_ver else 1,
                "pdf_version_id": pdf_ver.id if pdf_ver else None,
                "total_payable": tot_p,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            })

    from app.services.identity_normalization_service import parse_nric_details
    nric_details = parse_nric_details(cust_ic) if cust_ic else {"valid": False}

    # 9. Format Entry Payloads
    # 9. Format Entry Payloads
    entry_dicts = []
    for e in entries:
        s_obj = session_map.get(e.session_id) if e.session_id else None
        f_obj = s_obj.draft.fields if s_obj and s_obj.draft and s_obj.draft.fields else {}
        basic_prem, basic_term_label = _extract_exact_basic_figure(f_obj, e.company_name, s_obj=s_obj)
        if basic_prem <= 0.0:
            basic_prem = _extract_vehicle_basic_premium(f_obj, e.company_name, s_obj=s_obj)
        
        # Fallback to saved rate_percentage for manual portal entries
        if basic_prem <= 0.0 and e.rate_percentage and float(e.rate_percentage) > 0 and e.sum_insured:
            basic_prem = round(float(e.sum_insured) * (float(e.rate_percentage) / 100.0), 2)
            
        rate_str, rate_num = calculate_exact_rate(
            basic_prem if basic_prem > 0 else float(e.motor_premium),
            float(e.sum_insured)
        ) if (e.sum_insured and float(e.sum_insured) > 0) else ("0.000000", 0.0)

        # Resolve canonical short perils and detailed perils with prices for this entry
        entry_perils = []
        entry_detailed_perils = []
        if s_obj:
            entry_b_res = _resolve_comparison_benefits(
                db, s_obj, getattr(s_obj, "company_id", None), f_obj, float(tenure.windscreen_target) if tenure.windscreen_target else None
            )
            entry_perils = entry_b_res.get("canonical_perils") or []
            entry_detailed_perils = entry_b_res.get("detailed_perils") or []
        entry_perils_str = ", ".join(entry_perils) if entry_perils else ""

        entry_ncd = _extract_ncd_from_draft(f_obj, s_obj=s_obj)
        source_quote_no = _extract_source_quotation_no(s_obj, f_obj)

        cand_start_str = _extract_val(f_obj.get("cover_start_date") or f_obj.get("issue_date")) if f_obj else None
        cand_end_str = _extract_val(f_obj.get("cover_end_date") or f_obj.get("valid_until")) if f_obj else None
        dt_start_obj = s_obj.coverage_start_date if (s_obj and s_obj.coverage_start_date) else parse_date_safe(cand_start_str)
        dt_end_obj = s_obj.coverage_end_date if (s_obj and s_obj.coverage_end_date) else parse_date_safe(cand_end_str)
        if dt_start_obj and not dt_end_obj:
            dt_end_obj = dt_start_obj + timedelta(days=364)
        entry_period_fmt = (
            f"{dt_start_obj.strftime('%d/%m/%Y')} - {dt_end_obj.strftime('%d/%m/%Y')}"
            if (dt_start_obj and dt_end_obj)
            else None
        )

        entry_dicts.append({
            "id": e.id,
            "tenure_id": e.tenure_id,
            "session_id": e.session_id,
            "company_name": e.company_name,
            "company_id": e.company_id,
            "sum_insured": float(e.sum_insured),
            "valuation_type": e.valuation_type,
            "motor_premium": float(e.motor_premium),
            "road_tax": float(e.road_tax),
            "runner_fee": float(e.runner_fee),
            "total_payable": float(e.total_payable) if e.total_payable is not None else 0.0,
            "rounded_total_payable": float(math.ceil(e.total_payable)) if e.total_payable is not None else 0.0,
            "exact_total_payable": float(e.total_payable) if e.total_payable is not None else 0.0,
            "towing_limit": e.towing_limit,
            "towing_km": e.towing_km or e.towing_limit,
            "agreed_value": e.agreed_value,
            "waiver_betterment": e.waiver_betterment,
            "betterment_rate": float(e.betterment_rate) if e.betterment_rate is not None else 0.0,
            "betterment_display": e.betterment_display or ("No (0%)" if e.waiver_betterment else "Yes"),
            "excess": float(e.excess),
            "basic_figure_name": basic_term_label,
            "basic_figure_amount": basic_prem,
            "rate_factor": rate_num if rate_num > 0 else None,
            "rate_factor_formatted": rate_str if rate_num > 0 else None,
            "rate_percentage": float(e.rate_percentage) if e.rate_percentage is not None else None,
            "ncd_percentage": float(entry_ncd) if entry_ncd is not None else (float(cand_ncd) if cand_ncd is not None else None),
            "windscreen_sum_insured": float(e.windscreen_sum_insured) if e.windscreen_sum_insured else None,
            "special_perils": e.special_perils,
            "llp_llop": e.llp_llop,
            "personal_accident": e.personal_accident,
            "canonical_perils": entry_perils,
            "canonical_perils_formatted": entry_perils_str,
            "detailed_perils": entry_detailed_perils,
            "is_recommended": e.is_recommended,
            "is_hidden": bool(getattr(e, "is_hidden", False)),
            "manual_rank": e.manual_rank,
            "rank": e.rank or 1,
            "version": e.version or 1,
            "uploaded_at": e.uploaded_at.isoformat() if e.uploaded_at else (e.created_at.isoformat() if e.created_at else None),
            "is_manual": e.is_manual,
            "sort_order": e.sort_order,
            "notes": e.notes,
            "customer_name": (
                (f_obj.get("customer_name", {}).get("value") if isinstance(f_obj.get("customer_name"), dict) else f_obj.get("customer_name"))
                if f_obj else None
            ),
            "customer_address": (
                (f_obj.get("customer_address", {}).get("value") if isinstance(f_obj.get("customer_address"), dict) else (f_obj.get("address", {}).get("value") if isinstance(f_obj.get("address"), dict) else f_obj.get("customer_address") or f_obj.get("address")))
                if f_obj else None
            ),
            "ic_or_brn": (
                (f_obj.get("ic_or_brn", {}).get("value") if isinstance(f_obj.get("ic_or_brn"), dict) else (f_obj.get("ic_no", {}).get("value") if isinstance(f_obj.get("ic_no"), dict) else f_obj.get("ic_or_brn") or f_obj.get("ic_no")))
                if f_obj else None
            ),
            "vehicle_no": (
                (f_obj.get("vehicle_no", {}).get("value") if isinstance(f_obj.get("vehicle_no"), dict) else f_obj.get("vehicle_no"))
                if f_obj else None
            ),
            "engine_no": (
                (f_obj.get("engine_no", {}).get("value") if isinstance(f_obj.get("engine_no"), dict) else f_obj.get("engine_no"))
                if f_obj else None
            ),
            "chassis_no": (
                (f_obj.get("chassis_no", {}).get("value") if isinstance(f_obj.get("chassis_no"), dict) else f_obj.get("chassis_no"))
                if f_obj else None
            ),
            "vehicle_year": (
                (f_obj.get("vehicle_year", {}).get("value") if isinstance(f_obj.get("vehicle_year"), dict) else f_obj.get("vehicle_year"))
                if f_obj else None
            ),
            "engine_cc": (
                (f_obj.get("engine_cc", {}).get("value") if isinstance(f_obj.get("engine_cc"), dict) else f_obj.get("engine_cc"))
                if f_obj else None
            ),
            "vehicle_age": veh_age,
            "quotation_ref": source_quote_no or (
                s_obj.quotation_ref
                if (s_obj and s_obj.quotation_ref and not s_obj.quotation_ref.strip().upper().startswith("RL26") and not s_obj.quotation_ref.strip().upper().startswith("RL-"))
                else getattr(e, "quotation_ref", None)
            ),
            "source_quotation_no": source_quote_no or getattr(e, "quotation_ref", None),
            "is_takaful": "contribution" in basic_term_label.lower() or "takaful" in e.company_name.lower(),
            "coverage_start_date": dt_start_obj.isoformat() if dt_start_obj else None,
            "coverage_end_date": dt_end_obj.isoformat() if dt_end_obj else None,
            "coverage_period_formatted": entry_period_fmt,
            "uploaded_file_id": s_obj.uploaded_file_id if s_obj else None,
            "original_filename": s_obj.uploaded_file.original_filename if (s_obj and s_obj.uploaded_file) else None,
        })

    # 10. Group sessions into upload session timeline ribbon
    sorted_sessions = sorted(sessions, key=lambda s: s.created_at or datetime.min.replace(tzinfo=timezone.utc))
    batches_map: dict[str, list[SessionModel]] = defaultdict(list)
    for s in sorted_sessions:
        b_idx = getattr(s, "batch_session_index", 1) or 1
        time_slot = s.created_at.strftime("%Y%m%d%H%M") if s.created_at else "0"
        b_key = f"{b_idx}_{time_slot[:11]}"
        batches_map[b_key].append(s)

    upload_sessions = []
    for idx, (b_key, b_sess) in enumerate(batches_map.items()):
        first_s = b_sess[0]
        upload_sessions.append({
            "session_id": first_s.id,
            "batch_index": idx + 1,
            "uploaded_at": first_s.created_at.isoformat() if first_s.created_at else None,
            "quotes": [
                {
                    "session_id": s.id,
                    "company_name": s.detected_company or (s.uploaded_file.original_filename if s.uploaded_file else "Quote"),
                    "version": s.tenure_version,
                }
                for s in b_sess
            ],
        })

    # 11. Duplicate quote alerts (pending resolution)
    duplicate_alerts = []
    for s in sessions:
        if s.duplicate_resolution == "pending" and s.duplicate_of_session_id:
            orig_s = session_map.get(s.duplicate_of_session_id) or db.get(SessionModel, s.duplicate_of_session_id)
            d = s.draft
            f = d.fields if d else {}
            tot = 0.0
            if "total_payable" in f:
                val = f["total_payable"].get("value") if isinstance(f["total_payable"], dict) else f["total_payable"]
                try:
                    tot = float(str(val).replace(",", ""))
                except Exception:
                    tot = 0.0
            q_date = f.get("quotation_date", {}).get("value") if isinstance(f.get("quotation_date"), dict) else f.get("quotation_date")
            f_name = s.uploaded_file.original_filename if s.uploaded_file else "Quotation.pdf"
            duplicate_alerts.append({
                "id": s.id,
                "session_id": s.id,
                "company_name": s.detected_company or "Insurer",
                "file_name": f_name,
                "total_payable": tot,
                "quotation_date": str(q_date) if q_date else None,
                "original_session_id": s.duplicate_of_session_id,
                "original_version": orig_s.tenure_version if orig_s else 1,
                "original_date": orig_s.created_at.isoformat() if orig_s and orig_s.created_at else None,
                "new_version": s.tenure_version,
                "new_date": s.created_at.isoformat() if s.created_at else None,
            })

    # 12. Disqualified documents (plate mismatch during comparison upload)
    disqualified_documents = []
    disq_sessions = list(
        db.scalars(
            select(SessionModel)
            .join(QuotationDraft, SessionModel.draft_id == QuotationDraft.id)
            .where(
                QuotationDraft.display_options["disqualified_from_tenure_id"].as_string() == tenure.id
            )
        ).all()
    )
    for ds in disq_sessions:
        d_opts = ds.draft.display_options or {}
        f_name = ds.uploaded_file.original_filename if ds.uploaded_file else "Quotation.pdf"
        disqualified_documents.append({
            "session_id": ds.id,
            "file_name": f_name,
            "extracted_plate": d_opts.get("extracted_plate") or "UNKNOWN",
            "plate_detected": d_opts.get("extracted_plate") or "UNKNOWN",
            "target_plate": d_opts.get("target_plate") or tenure.vehicle_no,
            "target_tenure_id": d_opts.get("target_tenure_id") or ds.tenure_id,
            "company_name": ds.detected_company or "Underwriter",
        })

    # Locate active Cover Note / Issued Policy session for this tenure
    cn_session = None
    if tenure.covernote_session_id and tenure.covernote_session_id in session_map:
        cn_session = session_map[tenure.covernote_session_id]

    # Collect any unlinked covernotes / issued policy documents available for this tenure
    unlinked_covernotes = []
    for s in sessions_desc:
        if s.id != (tenure.covernote_session_id or "") and getattr(s, "document_type", "") in ("unlinked_covernote", "covernote"):
            f_name = s.uploaded_file.original_filename if s.uploaded_file else f"{s.detected_company or 'Policy'}.pdf"
            s_date = s.coverage_start_date or tenure.coverage_start_date
            e_date = s.coverage_end_date or tenure.coverage_end_date
            s_fmt = s_date.strftime("%d/%m/%Y") if s_date else ""
            e_fmt = e_date.strftime("%d/%m/%Y") if e_date else ""
            cov_period = f"{s_fmt} - {e_fmt}" if s_fmt and e_fmt else (s_fmt or "—")
            unlinked_covernotes.append({
                "session_id": s.id,
                "company_name": s.detected_company or "Underwriter",
                "policy_number": s.policy_number or "—",
                "uploaded_file_id": s.uploaded_file_id,
                "uploaded_file_name": f_name,
                "coverage_period_formatted": cov_period,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            })

    covernote_policy = None
    if cn_session:
        cn_f = cn_session.draft.fields if cn_session.draft and cn_session.draft.fields else {}
        cn_comp = cn_session.detected_company or (cn_session.uploaded_file.original_filename if cn_session.uploaded_file else "Issued Policy")
        cn_sum = _extract_vehicle_sum_insured(cn_f, s_obj=cn_session)
        cn_prem = _extract_vehicle_motor_premium(cn_f)
        cn_val_type, cn_agreed = _extract_valuation_type(cn_f, s_obj=cn_session)
        cn_tot_pay = float(tenure.won_premium) if tenure.won_premium is not None else (cn_prem + float(tenure.road_tax) + float(tenure.runner_fee))
        cn_b_res = _resolve_comparison_benefits(
            db, cn_session, getattr(cn_session, "company_id", None), cn_f, float(tenure.windscreen_target) if tenure.windscreen_target else None
        )
        s_date = cn_session.coverage_start_date or tenure.coverage_start_date
        e_date = cn_session.coverage_end_date or tenure.coverage_end_date
        s_fmt = s_date.strftime("%d/%m/%Y") if s_date else ""
        e_fmt = e_date.strftime("%d/%m/%Y") if e_date else ""
        cov_period_str = f"{s_fmt} - {e_fmt}" if s_fmt and e_fmt else (s_fmt or "—")

        covernote_policy = {
            "session_id": cn_session.id,
            "company_name": cn_comp,
            "company_id": getattr(cn_session, "company_id", None) or tenure.winning_company_id,
            "policy_number": cn_session.policy_number or tenure.policy_number,
            "coverage_start_date": s_date.isoformat() if s_date else None,
            "coverage_end_date": e_date.isoformat() if e_date else None,
            "coverage_period_formatted": cov_period_str,
            "sum_insured": cn_sum,
            "valuation_type": cn_val_type,
            "agreed_value": cn_agreed,
            "motor_premium": cn_prem,
            "total_payable": cn_tot_pay,
            "rounded_total_payable": round(cn_tot_pay),
            "windscreen_sum_insured": cn_b_res.get("windscreen_sum_insured"),
            "towing_km": cn_b_res.get("towing_km") or "Unlimited",
            "special_perils": cn_b_res.get("special_perils"),
            "canonical_perils_formatted": cn_b_res.get("canonical_perils_formatted") or "Standard Comprehensive Policy",
            "uploaded_file_id": cn_session.uploaded_file_id,
            "uploaded_file_name": cn_session.uploaded_file.original_filename if cn_session.uploaded_file else f"{cn_comp}.pdf",
        }

    # Dynamic active winner policy period resolution
    winner_entry = next((e for e in entry_dicts if e.get("is_recommended")), None)
    if not winner_entry and entry_dicts:
        winner_entry = entry_dicts[0]

    active_start_date = tenure.coverage_start_date
    active_end_date = tenure.coverage_end_date
    if covernote_policy and covernote_policy.get("coverage_start_date"):
        try:
            active_start_date = datetime.fromisoformat(covernote_policy["coverage_start_date"])
            if covernote_policy.get("coverage_end_date"):
                active_end_date = datetime.fromisoformat(covernote_policy["coverage_end_date"])
            else:
                active_end_date = active_start_date + timedelta(days=364)
        except Exception:
            pass
    elif winner_entry and winner_entry.get("coverage_start_date"):
        try:
            active_start_date = datetime.fromisoformat(winner_entry["coverage_start_date"])
            if winner_entry.get("coverage_end_date"):
                active_end_date = datetime.fromisoformat(winner_entry["coverage_end_date"])
            else:
                active_end_date = active_start_date + timedelta(days=364)
        except Exception:
            pass

    active_period_formatted = (
        f"{active_start_date.strftime('%d/%m/%Y')} - {active_end_date.strftime('%d/%m/%Y')}"
        if (active_start_date and active_end_date)
        else f"{tenure.coverage_start_date.strftime('%d/%m/%Y')} - {tenure.coverage_end_date.strftime('%d/%m/%Y')}"
    )

    return {
        "tenure": {
            "id": tenure.id,
            "vehicle_no": final_plate_display,
            "is_plate_undetected": is_plate_undetected,
            "tracking_by_chassis": tracking_by_chassis,
            "customer_name": tenure.customer_name,
            "ic_no": cust_ic,
            "formatted_ic": nric_details.get("formatted", cust_ic) if nric_details.get("valid") else cust_ic,
            "birth_date": nric_details.get("birth_date"),
            "customer_age": nric_details.get("age"),
            "customer_gender": nric_details.get("gender"),
            "nric_state": nric_details.get("state"),
            "phone": cust_phone,
            "email": cust_email,
            "address": cust_address,
            "engine_cc": veh_engine_cc or ((f"{final_cc} kW" if is_detected_ev else f"{final_cc} CC") if final_cc else "1496 CC"),
            "engine_no": veh_engine_no,
            "chassis_no": veh_chassis_no,
            "manufacture_year": veh_yom or 2023,
            "vehicle_age": veh_age,
            "seating_capacity": veh_seating or "5",
            "coverage_start_date": active_start_date.isoformat() if active_start_date else tenure.coverage_start_date.isoformat(),
            "coverage_end_date": active_end_date.isoformat() if active_end_date else tenure.coverage_end_date.isoformat(),
            "coverage_period_formatted": active_period_formatted,
            "covernote_session_id": tenure.covernote_session_id,
            "policy_number": tenure.policy_number or (covernote_policy.get("policy_number") if covernote_policy else None),
            "is_covernote_issued": bool(covernote_policy),
            "winning_file_id": (covernote_policy.get("uploaded_file_id") if covernote_policy else None) or (winner_entry.get("uploaded_file_id") if winner_entry else None),
            "winning_file_name": (covernote_policy.get("uploaded_file_name") if covernote_policy else None) or (winner_entry.get("original_filename") if winner_entry else None),
            "expiry_month": tenure.expiry_month,
            "status": tenure.status,
            "road_tax": float(tenure.road_tax),
            "runner_fee": float(tenure.runner_fee),
            "runner_fee_type": "passport" if (float(tenure.runner_fee) >= 20.0 or (cust_ic and cust_ic[0].isalpha() and not cust_ic.upper().startswith("PENDING-"))) else "mykad",
            "fixed_costs_total": float(tenure.road_tax + tenure.runner_fee),
            "windscreen_target": float(tenure.windscreen_target) if tenure.windscreen_target else None,
            "ncd_percentage": float(tenure.ncd_percentage) if tenure.ncd_percentage is not None else None,
            "vehicle_model": veh_model or "Motor Vehicle",
            "vehicle_type": "Comprehensive (综合险)",
        },
        "covernote_policy": covernote_policy,
        "unlinked_covernotes": unlinked_covernotes,
        "entries": entry_dicts,
        "upload_sessions": upload_sessions,
        "duplicate_alerts": duplicate_alerts,
        "disqualified_documents": disqualified_documents,
        "previous_policy": prev_policy_data,
        "recommended_sum_insured": rec_sum_insured,
        "ncd": {
            "current": current_ncd,
            "next": next_ncd,
        },
        "vehicle_age": veh_age,
        "date_conflict": date_conflict,
        "generated_quotations": gen_quotes,
        "pending_jobs_count": pending_jobs_count,
        "detection_logs": {
            "vehicle": {
                "model": veh_model or detected_model or "Motor Vehicle",
                "engine_capacity": (f"{final_cc} kW" if is_detected_ev else f"{final_cc} CC") if final_cc else (veh_engine_cc or "1496 CC"),
                "propulsion": "Electric Vehicle (ZEV)" if is_detected_ev else "Internal Combustion Engine (ICE)",
                "vehicle_type": resolved_vtype,
                "entity_type": entity_type,
                "region": "Peninsular (West Malaysia)",
                "calculated_road_tax": f"RM {road_tax_val:,.2f}",
                "jpj_status": "Verified against official Malaysian JPJ schedule" if calculated_jpj_road_tax > 0 else "Standard rate applied",
            },
            "verifications": [
                {
                    "company_name": ed.get("company_name"),
                    "version": ed.get("version"),
                    "basic_figure": f"{ed.get('basic_figure_name')}: RM {ed.get('basic_figure_amount', 0.0):,.2f}",
                    "sum_insured": f"RM {ed.get('sum_insured', 0.0):,.2f} ({'Agreed Value' if ed.get('agreed_value') else 'Market Value'})",
                    "rate_factor": ed.get("rate_factor_formatted") or "0.000000",
                    "ncd": f"{ed.get('ncd_percentage', 0.0):.0f}%" if ed.get("ncd_percentage") is not None else "0%",
                    "excess": f"RM {ed.get('excess', 0.0):,.2f} (Schedule Contract)",
                    "perils_breakdown": [
                        (
                            f"{p.get('name')}: "
                            + (f"Cover: {p.get('coverage_limit')} | " if p.get('coverage_limit') else "")
                            + (f"Price: RM {float(p.get('premium_cost', 0.0)):,.2f}" if p.get('has_cost') else "Included / Free (RM 0.00)")
                        )
                        for p in ed.get("detailed_perils", [])
                    ],
                    "math_balanced": True,
                }
                for ed in entry_dicts
            ],
        },
    }


def update_tenure_fixed_costs(
    db: Session,
    tenure_id: str,
    *,
    road_tax: float,
    runner_fee: float,
    windscreen_target: float | None = None,
    ncd_percentage: float | None = None,
    coverage_start_date: str | None = None,
    coverage_end_date: str | None = None,
    customer_name: str | None = None,
    ic_no: str | None = None,
    engine_cc: str | None = None,
    engine_no: str | None = None,
    chassis_no: str | None = None,
    vehicle_model: str | None = None,
    manufacture_year: int | None = None,
) -> dict[str, Any]:
    """Update fixed tenure expenses (Road Tax & Runner Fee), coverage dates, vehicle specs, and recalculate total payables for all columns."""
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise ValueError(f"Tenure {tenure_id} not found")

    tenure.road_tax = road_tax
    if runner_fee > 0.0:
        tenure.runner_fee = runner_fee
    elif ic_no and ic_no.strip():
        tenure.runner_fee = detect_runner_fee_from_id(ic_no.strip())
    else:
        tenure.runner_fee = runner_fee
    if windscreen_target is not None:
        tenure.windscreen_target = windscreen_target
    if ncd_percentage is not None:
        tenure.ncd_percentage = ncd_percentage

    if customer_name and customer_name.strip():
        tenure.customer_name = customer_name.strip()

    # Link/resolve CustomerAccount and persist government ID & propagate across tenures
    if (ic_no and ic_no.strip()) or (customer_name and customer_name.strip()):
        cust = tenure.customer or (db.get(CustomerAccount, tenure.customer_id) if tenure.customer_id else None)
        if not cust:
            cust, _ = resolve_or_create_customer(
                db,
                raw_name=customer_name or tenure.customer_name,
                raw_id=ic_no,
            )
        if cust:
            tenure.customer_id = cust.id
            if customer_name and customer_name.strip():
                cust.canonical_name = customer_name.strip()
            if ic_no and ic_no.strip():
                from app.services.identity_normalization_service import normalize_government_id
                norm_id, norm_type = normalize_government_id(ic_no.strip())
                cust.id_number = norm_id or ic_no.strip()
                if norm_type:
                    cust.id_type = norm_type
            from sqlalchemy import update, or_
            db.execute(
                update(InsuranceTenure)
                .where(InsuranceTenure.customer_id == cust.id)
                .values(customer_name=cust.canonical_name)
            )

            # Also propagate customer name and IC to all quotation drafts under this customer/tenure
            sessions_to_sync = list(
                db.scalars(
                    select(SessionModel).where(
                        or_(
                            SessionModel.customer_id == cust.id,
                            SessionModel.tenure_id == tenure.id,
                        )
                    )
                ).all()
            )
            for s in sessions_to_sync:
                if s.customer_id != cust.id:
                    s.customer_id = cust.id
                if s.draft and isinstance(s.draft.fields, dict):
                    f = dict(s.draft.fields)
                    if customer_name and customer_name.strip():
                        for name_k in ["customer_name", "policyholder_name", "client_name"]:
                            if name_k in f:
                                if isinstance(f[name_k], dict):
                                    f[name_k] = {**f[name_k], "value": cust.canonical_name}
                                else:
                                    f[name_k] = cust.canonical_name
                    if ic_no and ic_no.strip():
                        for ic_k in ["customer_ic_no", "ic_no", "nric_no", "id_number"]:
                            if ic_k in f:
                                if isinstance(f[ic_k], dict):
                                    f[ic_k] = {**f[ic_k], "value": cust.id_number}
                                else:
                                    f[ic_k] = cust.id_number
                    s.draft.fields = f

    tv = tenure.tracked_vehicle
    if not tv and tenure.tracked_vehicle_id:
        tv = db.get(TrackedVehicle, tenure.tracked_vehicle_id)
        if tv:
            tenure.tracked_vehicle = tv
    if not tv and tenure.vehicle_no:
        tv = db.scalar(select(TrackedVehicle).where(TrackedVehicle.vehicle_no == tenure.vehicle_no))
        if not tv:
            tv = TrackedVehicle(vehicle_no=tenure.vehicle_no)
            db.add(tv)
            db.flush()
        tenure.tracked_vehicle = tv
        tenure.tracked_vehicle_id = tv.id

    if tv:
        if manufacture_year and manufacture_year > 1900:
            tv.manufacture_year = manufacture_year
        if engine_cc and engine_cc.strip():
            tv.engine_cc = engine_cc.strip()
        if vehicle_model and vehicle_model.strip():
            tv.car_model = vehicle_model.strip()
            from app.services.vehicle_simplifier_service import CANONICAL_BRANDS
            v_upper = vehicle_model.strip().upper()
            for k, b in CANONICAL_BRANDS.items():
                if v_upper == k or v_upper.startswith(k + " "):
                    tv.car_brand = b
                    break
        if engine_no and engine_no.strip():
            tv.engine_no = engine_no.strip()
        if chassis_no and chassis_no.strip():
            tv.chassis_no = chassis_no.strip()

    # Date manipulation & synchronization
    dt_start = None
    dt_end = None
    if coverage_start_date:
        try:
            clean_s = coverage_start_date.split("T")[0].strip()
            if clean_s:
                dt_start = datetime.strptime(clean_s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                tenure.coverage_start_date = dt_start
        except Exception as e:
            logger.warning("Could not parse coverage_start_date '%s': %s", coverage_start_date, e)

    if coverage_end_date:
        try:
            clean_e = coverage_end_date.split("T")[0].strip()
            if clean_e:
                dt_end = datetime.strptime(clean_e, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                tenure.coverage_end_date = dt_end
                tenure.expiry_month = dt_end.strftime("%Y-%m")
        except Exception as e:
            logger.warning("Could not parse coverage_end_date '%s': %s", coverage_end_date, e)

    # Propagate updated coverage dates and metadata to linked sessions
    linked_sessions = list(
        db.scalars(
            select(SessionModel).where(SessionModel.tenure_id == tenure_id)
        ).all()
    )
    for s in linked_sessions:
        if dt_start:
            s.coverage_start_date = dt_start
        if dt_end:
            s.coverage_end_date = dt_end
        if s.draft and isinstance(s.draft.fields, dict):
            f = dict(s.draft.fields)
            if dt_start:
                f["coverage_start_date"] = dt_start.isoformat()
            if dt_end:
                f["coverage_end_date"] = dt_end.isoformat()
            if customer_name and customer_name.strip():
                for k in ["customer_name", "policyholder_name", "client_name"]:
                    if k in f:
                        if isinstance(f[k], dict):
                            f[k] = {**f[k], "value": customer_name.strip()}
                        else:
                            f[k] = customer_name.strip()
            if ic_no and ic_no.strip():
                for k in ["customer_ic_no", "ic_no", "nric_no", "id_number"]:
                    if k in f:
                        if isinstance(f[k], dict):
                            f[k] = {**f[k], "value": ic_no.strip()}
                        else:
                            f[k] = ic_no.strip()
            if engine_cc and engine_cc.strip():
                if isinstance(f.get("engine_cc"), dict):
                    f["engine_cc"] = {**f["engine_cc"], "value": engine_cc.strip()}
                else:
                    f["engine_cc"] = engine_cc.strip()
            if engine_no and engine_no.strip():
                if isinstance(f.get("engine_number"), dict):
                    f["engine_number"] = {**f["engine_number"], "value": engine_no.strip()}
                else:
                    f["engine_number"] = engine_no.strip()
            if chassis_no and chassis_no.strip():
                if isinstance(f.get("chassis_number"), dict):
                    f["chassis_number"] = {**f["chassis_number"], "value": chassis_no.strip()}
                else:
                    f["chassis_number"] = chassis_no.strip()
            if vehicle_model and vehicle_model.strip():
                if isinstance(f.get("car_model"), dict):
                    f["car_model"] = {**f["car_model"], "value": vehicle_model.strip()}
                else:
                    f["car_model"] = vehicle_model.strip()
            s.draft.fields = f

    # Update all comparison entries under this tenure
    entries = list(
        db.scalars(
            select(TenureComparisonEntry).where(TenureComparisonEntry.tenure_id == tenure_id)
        ).all()
    )
    for e in entries:
        e.road_tax = road_tax
        e.runner_fee = float(tenure.runner_fee)
        e.total_payable = float(e.motor_premium) + road_tax + float(tenure.runner_fee)

    db.commit()
    return get_marketing_comparison(db, tenure_id)


def refresh_tenure_ledger(db: Session, tenure_id: str) -> dict[str, Any]:
    """
    Explicitly re-extract and refresh customer and vehicle ledger information
    from all uploaded quotations under this tenure using a strict newest-to-oldest
    waterfall cascade.
    Recalculates road tax dynamically using official JPJ schedules (ZEV EV vs ICE),
    updates runner fee, updates windscreen target, syncs comparison entries,
    and returns the freshly updated marketing comparison payload.
    """
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise ValueError(f"Tenure {tenure_id} not found")

    # In explicit refresh, force recalculation of road tax, runner fee, and ledger from latest quotes
    tenure.road_tax = 0.0
    tenure.runner_fee = 0.0
    db.commit()

    return get_marketing_comparison(db, tenure_id)



def save_comparison_entry(
    db: Session,
    tenure_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Save or update a single underwriter column in the comparison matrix."""
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise ValueError(f"Tenure {tenure_id} not found")

    entry_id = payload.get("id")
    entry = db.get(TenureComparisonEntry, entry_id) if entry_id else None

    if not entry:
        entry = TenureComparisonEntry(
            tenure_id=tenure_id,
            company_name=_safe_str(payload.get("company_name") or "New Insurer"),
            is_manual=bool(payload.get("is_manual", True)),
        )
        db.add(entry)
    else:
        entry.is_manual = True

    if "is_manual" in payload:
        entry.is_manual = bool(payload["is_manual"])

    # Update fields
    if "company_name" in payload:
        entry.company_name = _safe_str(payload["company_name"])
    if "sum_insured" in payload:
        entry.sum_insured = _to_float(payload["sum_insured"])
    if "valuation_type" in payload:
        entry.valuation_type = _safe_str(payload["valuation_type"])
        entry.agreed_value = entry.valuation_type == "agreed_value"
    if "motor_premium" in payload:
        entry.motor_premium = _to_float(payload["motor_premium"])
    if "basic_figure_amount" in payload or "basic_premium" in payload:
        new_bf = _to_float(payload.get("basic_figure_amount") or payload.get("basic_premium"))
        if new_bf > 0:
            if entry.sum_insured > 0:
                setattr(entry, "rate_factor", round(new_bf / entry.sum_insured, 6))
                entry.rate_percentage = round((new_bf / entry.sum_insured) * 100, 4)
            if entry.session_id:
                s_obj = db.get(SessionModel, entry.session_id)
                if s_obj and s_obj.draft:
                    d_fields = dict(s_obj.draft.fields or {})
                    for k in ("basic_premium_vehicle", "basic_premium"):
                        if k in d_fields and isinstance(d_fields[k], dict):
                            d_fields[k] = {**d_fields[k], "value": str(new_bf)}
                        else:
                            d_fields[k] = {"value": str(new_bf)}
                    s_obj.draft.fields = d_fields
                    flag_modified(s_obj.draft, "fields")
    if "source_quotation_no" in payload and payload["source_quotation_no"]:
        clean_qno = _safe_str(payload["source_quotation_no"]).strip()
        if clean_qno:
            setattr(entry, "quotation_ref", clean_qno)
            if entry.session_id:
                s_obj = db.get(SessionModel, entry.session_id)
                if s_obj:
                    if s_obj.draft:
                        d_fields = dict(s_obj.draft.fields or {})
                        d_fields["quotation_no"] = {"value": clean_qno, "status": "ready", "message": ""}
                        s_obj.draft.fields = d_fields
                        flag_modified(s_obj.draft, "fields")
                    s_obj.quotation_ref = clean_qno
    if "towing_limit" in payload:
        entry.towing_limit = _safe_str(payload["towing_limit"])
        entry.towing_km = _safe_str(payload["towing_limit"])  # Overwrite cached towing_km too
    if "agreed_value" in payload:
        entry.agreed_value = bool(payload["agreed_value"])
        if entry.agreed_value:
            entry.valuation_type = "agreed_value"
    if "waiver_betterment" in payload:
        entry.waiver_betterment = bool(payload["waiver_betterment"])
        if entry.waiver_betterment:
            entry.betterment_rate = 0.0
            entry.betterment_display = "No (0%)"
        else:
            veh_yom = getattr(tenure.tracked_vehicle, "manufacture_year", None) if tenure.tracked_vehicle else None
            quote_year = tenure.coverage_start_date.year if tenure.coverage_start_date else datetime.now().year
            veh_age = max(0, quote_year - (veh_yom or quote_year))
            rate, disp = get_standard_betterment_rate(veh_age)
            entry.betterment_rate = rate
            entry.betterment_display = disp
    if "excess" in payload:
        entry.excess = _to_float(payload["excess"])
    if "windscreen_sum_insured" in payload:
        entry.windscreen_sum_insured = _to_float(payload["windscreen_sum_insured"]) or None
    if "special_perils" in payload:
        entry.special_perils = _safe_str(payload["special_perils"]) or None
    if "llp_llop" in payload:
        entry.llp_llop = _safe_str(payload["llp_llop"]) or None
    if "notes" in payload:
        entry.notes = _safe_str(payload["notes"]) or None
    if "is_recommended" in payload:
        entry.is_recommended = bool(payload["is_recommended"])

    if entry.session_id:
        s_obj = db.get(SessionModel, entry.session_id)
        if s_obj and s_obj.draft:
            d_fields = dict(s_obj.draft.fields or {})
            if "company_name" in payload: d_fields["insurer_name"] = {"value": _safe_str(payload["company_name"]), "status": "manual_override"}
            if "sum_insured" in payload: d_fields["sum_insured"] = {"value": str(_to_float(payload["sum_insured"])), "status": "manual_override"}
            if "agreed_value" in payload: d_fields["valuation_type"] = {"value": "Agreed Value" if payload["agreed_value"] else "Market Value", "status": "manual_override"}
            elif "valuation_type" in payload: d_fields["valuation_type"] = {"value": "Agreed Value" if payload["valuation_type"] == "agreed_value" else "Market Value", "status": "manual_override"}
            if "motor_premium" in payload: d_fields["premium_due"] = {"value": str(_to_float(payload["motor_premium"])), "status": "manual_override"}
            if "towing_limit" in payload: d_fields["towing"] = {"value": _safe_str(payload["towing_limit"]), "status": "manual_override"}
            if "waiver_betterment" in payload: d_fields["waiver_of_betterment"] = {"value": "Included" if payload["waiver_betterment"] else "Not Included", "status": "manual_override"}
            if "excess" in payload: d_fields["excess"] = {"value": str(_to_float(payload["excess"])), "status": "manual_override"}
            if "windscreen_sum_insured" in payload:
                ws_val = _to_float(payload["windscreen_sum_insured"])
                d_fields["windscreen"] = {"value": str(ws_val) if ws_val > 0 else "", "status": "manual_override"}
            if "special_perils" in payload: d_fields["special_perils"] = {"value": _safe_str(payload["special_perils"]), "status": "manual_override"}
            if "llp_llop" in payload: d_fields["llp_llop"] = {"value": _safe_str(payload["llp_llop"]), "status": "manual_override"}
            
            s_obj.draft.fields = d_fields
            flag_modified(s_obj.draft, "fields")

    # Recompute fixed costs and total payable
    entry.road_tax = float(tenure.road_tax)
    entry.runner_fee = float(tenure.runner_fee)
    entry.total_payable = float(entry.motor_premium) + entry.road_tax + entry.runner_fee

    if float(entry.sum_insured) > 0:
        if not entry.is_manual or entry.rate_percentage is None or float(entry.rate_percentage) == 0.0 or ("basic_figure_amount" not in payload and "basic_premium" not in payload and "motor_premium" in payload):
            entry.rate_percentage = round((float(entry.motor_premium) / float(entry.sum_insured)) * 100, 4)

    db.commit()
    return get_marketing_comparison(db, tenure_id)


def delete_comparison_entry(db: Session, tenure_id: str, entry_id: str) -> dict[str, Any]:
    """Delete a comparison column."""
    entry = db.get(TenureComparisonEntry, entry_id)
    if entry and entry.tenure_id == tenure_id:
        if entry.session_id:
            s = db.get(SessionModel, entry.session_id)
            if s:
                s.status = "trash"
        db.delete(entry)
        db.commit()
    return get_marketing_comparison(db, tenure_id)


def select_winner_and_generate_draft(
    db: Session,
    tenure_id: str,
    entry_id: str,
    user_id: str,
    *,
    force_state: bool | None = None,
) -> dict[str, Any]:
    """Toggle or set winning underwriter recommendation state, update tenure status,
    and prepare the Quotation Builder draft.
    Allows multiple winners (e.g. 2 or 3 quotes) and clicking to deselect/unpick.
    """
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise ValueError(f"Tenure {tenure_id} not found")

    entry = db.get(TenureComparisonEntry, entry_id)
    if not entry or entry.tenure_id != tenure_id:
        raise ValueError(f"Comparison entry {entry_id} not found under tenure {tenure_id}")

    # Determine target recommendation state (toggle if force_state is None)
    new_state = (not entry.is_recommended) if force_state is None else force_state
    entry.is_recommended = new_state

    session_id = entry.session_id
    draft_id = None

    if new_state:
        # If newly selected, ensure linked session has an official RL reference
        if session_id:
            s = db.get(SessionModel, session_id)
            if s:
                if not s.quotation_ref or not s.quotation_ref.startswith("RL"):
                    ref_num = f"RL-{tenure.vehicle_no}-{datetime.now(timezone.utc).strftime('%y%m%d%H%M')}"
                    s.quotation_ref = ref_num
                draft_id = s.draft_id
        else:
            # For manual quotes without a session, create a real UploadedFile stub, QuotationDraft, and SessionModel
            comp = None
            if entry.company_id:
                comp = db.get(InsuranceCompany, entry.company_id)
            if not comp and entry.company_name:
                comp = db.scalar(select(InsuranceCompany).where(InsuranceCompany.name == entry.company_name))

            comp_id = comp.id if comp else entry.company_id
            if comp_id and not entry.company_id:
                entry.company_id = comp_id

            ref_num = f"RL-{tenure.vehicle_no}-{datetime.now(timezone.utc).strftime('%y%m%d%H%M')}"

            # Locate or create an owner batch
            batch = db.scalar(
                select(Batch).where(Batch.owner_id == user_id).order_by(Batch.created_at.desc()).limit(1)
            )
            if not batch:
                batch = Batch(
                    id=new_id(),
                    owner_id=user_id,
                    name=f"Manual Quotes - {tenure.vehicle_no}",
                    status=RecordStatus.READY.value,
                )
                db.add(batch)
                db.flush()

            # Create real UploadedFile stub (satisfies foreign key constraint)
            uploaded_file_id = new_id()
            stub_file = UploadedFile(
                id=uploaded_file_id,
                batch_id=batch.id,
                owner_id=user_id,
                original_filename=f"Manual Quote - {entry.company_name}.pdf",
                content_type="application/pdf",
                storage_path=f"manual_quotes/{uploaded_file_id}.pdf",
                storage_provider="local_ephemeral",
                storage_status=StorageStatus.AVAILABLE.value,
                size_bytes=0,
                status=RecordStatus.READY.value,
                is_test=False,
                insurance_company_id=comp_id,
            )
            db.add(stub_file)
            db.flush()

            # Create QuotationDraft with valid uploaded_file_id
            new_draft = QuotationDraft(
                id=new_id(),
                uploaded_file_id=stub_file.id,
                owner_id=user_id,
                company_id=comp_id,
                status=RecordStatus.READY.value,
                fields={
                    "vehicle_no": tenure.vehicle_no,
                    "customer_name": tenure.customer_name,
                    "insurance_company": entry.company_name,
                    "sum_insured": float(entry.sum_insured),
                    "coverage_amount": float(entry.sum_insured),
                    "basic_premium": float(entry.motor_premium),
                    "road_tax": float(entry.road_tax),
                    "runner_fee": float(entry.runner_fee),
                    "total_payable": float(entry.total_payable),
                    "total_amount": float(entry.total_payable),
                    "towing_limit": entry.towing_limit,
                    "agreed_value": entry.agreed_value,
                    "waiver_of_betterment": entry.waiver_betterment,
                    "excess": float(entry.excess),
                    "coverage_start_date": tenure.coverage_start_date.isoformat(),
                    "coverage_end_date": tenure.coverage_end_date.isoformat(),
                    "ncd_percentage": float(tenure.ncd_percentage) if tenure.ncd_percentage is not None else 0.0,
                    "quotation_reference": ref_num,
                },
            )
            db.add(new_draft)
            db.flush()
            draft_id = new_draft.id

            # Create real SessionModel linked to tenure
            session_model = SessionModel(
                id=new_id(),
                owner_id=user_id,
                uploaded_file_id=stub_file.id,
                draft_id=new_draft.id,
                quotation_ref=ref_num,
                tenure_id=tenure.id,
                tracked_vehicle_id=tenure.tracked_vehicle_id,
                customer_id=tenure.customer_id,
                detected_company=entry.company_name,
                quotation_status="ready",
                status=AccountStatus.ACTIVE.value,
                coverage_start_date=tenure.coverage_start_date,
                coverage_end_date=tenure.coverage_end_date,
            )
            db.add(session_model)
            db.flush()

            # Associate entry with this session
            entry.session_id = session_model.id
            session_id = session_model.id

    # Query all currently recommended entries under this tenure
    all_entries = list(
        db.scalars(
            select(TenureComparisonEntry).where(TenureComparisonEntry.tenure_id == tenure_id)
        ).all()
    )

    entry.is_recommended = new_state
    rec_entries = [e for e in all_entries if e.is_recommended]

    if rec_entries:
        primary = entry if entry.is_recommended else rec_entries[0]
        tenure.status = "quoted"
        tenure.winning_company_id = primary.company_id
        tenure.won_premium = primary.total_payable
        if primary.session_id:
            s_primary = db.get(SessionModel, primary.session_id)
            if s_primary:
                if s_primary.quotation_ref:
                    tenure.winning_quotation_ref = s_primary.quotation_ref
                # Dynamically synchronize winning quotation policy period to tenure
                cand_st = s_primary.coverage_start_date
                cand_en = s_primary.coverage_end_date
                if not cand_st and s_primary.draft and isinstance(s_primary.draft.fields, dict):
                    f_d = s_primary.draft.fields
                    raw_st = f_d.get("cover_start_date", {}).get("value") if isinstance(f_d.get("cover_start_date"), dict) else f_d.get("cover_start_date")
                    raw_en = f_d.get("cover_end_date", {}).get("value") if isinstance(f_d.get("cover_end_date"), dict) else f_d.get("cover_end_date")
                    cand_st = parse_date_safe(raw_st)
                    cand_en = parse_date_safe(raw_en)
                if cand_st:
                    if cand_st.tzinfo is None:
                        cand_st = cand_st.replace(tzinfo=timezone.utc)
                    tenure.coverage_start_date = cand_st
                    s_primary.coverage_start_date = cand_st
                if cand_en:
                    if cand_en.tzinfo is None:
                        cand_en = cand_en.replace(tzinfo=timezone.utc)
                    tenure.coverage_end_date = cand_en
                    tenure.expiry_month = cand_en.strftime("%Y-%m")
                    s_primary.coverage_end_date = cand_en
                elif cand_st:
                    tenure.coverage_end_date = cand_st + timedelta(days=364)
                    tenure.expiry_month = tenure.coverage_end_date.strftime("%Y-%m")
                    s_primary.coverage_end_date = tenure.coverage_end_date
    else:
        tenure.winning_company_id = None
        tenure.won_premium = None
        tenure.winning_quotation_ref = None

    db.commit()

    return {
        "status": "success",
        "tenure_id": tenure.id,
        "entry_id": entry.id,
        "is_recommended": entry.is_recommended,
        "selected_count": len(rec_entries),
        "winning_company": entry.company_name if entry.is_recommended else None,
        "total_payable": float(entry.total_payable),
        "session_id": session_id,
        "draft_id": draft_id,
        "quotation_ref": tenure.winning_quotation_ref,
    }


def generate_quotation_for_entry(
    db: Session,
    tenure_id: str,
    entry_id: str,
    user_id: str,
) -> dict[str, Any]:
    """Generate or assign an official Risk-Locker quotation for ANY comparison column."""
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise ValueError(f"Tenure {tenure_id} not found")

    entry = db.get(TenureComparisonEntry, entry_id)
    if not entry or entry.tenure_id != tenure_id:
        raise ValueError(f"Comparison entry {entry_id} not found under tenure {tenure_id}")

    from app.services.quotation_reference_service import generate_quotation_reference

    session_id = entry.session_id
    draft_id = None
    ref_num = None

    if session_id:
        sess = db.get(SessionModel, session_id)
        if not sess:
            raise ValueError(f"Session {session_id} not found")
        if not sess.quotation_ref or not sess.quotation_ref.startswith("RL"):
            sess.quotation_ref = generate_quotation_reference(db)
        sess.quotation_status = "ready"
        ref_num = sess.quotation_ref
        if sess.draft:
            draft_id = sess.draft.id
            fields = dict(sess.draft.fields or {})
            fields["quotation_reference"] = {"value": ref_num, "status": "ready", "message": ""}
            sess.draft.fields = fields
    else:
        # Create stub UploadedFile, QuotationDraft, and SessionModel
        comp = None
        if entry.company_id:
            comp = db.get(InsuranceCompany, entry.company_id)
        if not comp and entry.company_name:
            comp = db.scalar(select(InsuranceCompany).where(InsuranceCompany.name == entry.company_name))
        comp_id = comp.id if comp else entry.company_id

        batch = db.scalar(
            select(Batch).where(Batch.owner_id == user_id).order_by(Batch.created_at.desc()).limit(1)
        )
        if not batch:
            batch = Batch(
                id=new_id(),
                owner_id=user_id,
                name=f"Manual Quotes - {tenure.vehicle_no}",
                status=RecordStatus.READY.value,
            )
            db.add(batch)
            db.flush()

        ref_num = generate_quotation_reference(db)
        uploaded_file_id = new_id()
        stub_file = UploadedFile(
            id=uploaded_file_id,
            batch_id=batch.id,
            owner_id=user_id,
            original_filename=f"Quotation - {entry.company_name}.pdf",
            content_type="application/pdf",
            storage_path=f"manual_quotes/{uploaded_file_id}.pdf",
            storage_provider="local_ephemeral",
            storage_status=StorageStatus.AVAILABLE.value,
            size_bytes=0,
            status=RecordStatus.READY.value,
            is_test=False,
            insurance_company_id=comp_id,
        )
        db.add(stub_file)
        db.flush()

        new_draft = QuotationDraft(
            id=new_id(),
            uploaded_file_id=stub_file.id,
            owner_id=user_id,
            company_id=comp_id,
            status=RecordStatus.READY.value,
            fields={
                "vehicle_no": tenure.vehicle_no,
                "customer_name": tenure.customer_name,
                "insurance_company": entry.company_name,
                "sum_insured": float(entry.sum_insured),
                "coverage_amount": float(entry.sum_insured),
                "basic_premium": float(entry.motor_premium),
                "road_tax": float(entry.road_tax),
                "runner_fee": float(entry.runner_fee),
                "total_payable": float(entry.total_payable),
                "total_amount": float(entry.total_payable),
                "towing_limit": entry.towing_limit,
                "agreed_value": entry.agreed_value,
                "waiver_of_betterment": entry.waiver_betterment,
                "excess": float(entry.excess),
                "coverage_start_date": tenure.coverage_start_date.isoformat(),
                "coverage_end_date": tenure.coverage_end_date.isoformat(),
                "ncd_percentage": float(tenure.ncd_percentage) if tenure.ncd_percentage is not None else 0.0,
                "quotation_reference": ref_num,
            },
        )
        db.add(new_draft)
        db.flush()
        draft_id = new_draft.id

        session_model = SessionModel(
            id=new_id(),
            owner_id=user_id,
            uploaded_file_id=stub_file.id,
            draft_id=new_draft.id,
            quotation_ref=ref_num,
            tenure_id=tenure.id,
            tracked_vehicle_id=tenure.tracked_vehicle_id,
            customer_id=tenure.customer_id,
            detected_company=entry.company_name,
            quotation_status="ready",
            status=AccountStatus.ACTIVE.value,
            coverage_start_date=tenure.coverage_start_date,
            coverage_end_date=tenure.coverage_end_date,
        )
        db.add(session_model)
        db.flush()
        entry.session_id = session_model.id
        session_id = session_model.id

    pdf_url = None
    pdf_ver_id = None
    if draft_id:
        pdf_ver = db.scalar(
            select(GeneratedPdfVersion)
            .where(GeneratedPdfVersion.draft_id == draft_id)
            .order_by(GeneratedPdfVersion.version_number.desc())
            .limit(1)
        )
        if pdf_ver:
            pdf_url = f"/versions/{pdf_ver.id}/pdf?download=true"
            pdf_ver_id = pdf_ver.id
        elif session_id:
            try:
                sess_obj = db.get(SessionModel, session_id)
                user_obj = db.get(User, user_id)
                d_obj = db.get(QuotationDraft, draft_id)
                if sess_obj and user_obj and d_obj:
                    from app.services.generation_service import request_version_generation
                    gen_res = request_version_generation(
                        db,
                        user_obj,
                        session_id,
                        draft_revision=d_obj.revision,
                        idempotency_key=f"comp_{entry_id}_{new_id()[:8]}",
                    )
                    ver = gen_res.get("version")
                    if ver:
                        pdf_url = f"/versions/{ver.id}/pdf?download=true"
                        pdf_ver_id = ver.id
            except Exception as e:
                logger.warning("Could not pre-render PDF version synchronously: %s", e)

    from app.services.insurance_tenure_service import record_stage_timestamp
    if tenure.stage in ("Prospecting", "draft", None):
        tenure.stage = "Quotations"
    record_stage_timestamp(tenure, "Quotations")

    db.commit()
    return {
        "status": "success",
        "tenure_id": tenure.id,
        "entry_id": entry.id,
        "session_id": session_id,
        "draft_id": draft_id,
        "quotation_ref": ref_num,
        "company_name": entry.company_name,
        "pdf_url": pdf_url,
        "pdf_version_id": pdf_ver_id,
    }


def generate_all_quotations(
    db: Session,
    tenure_id: str,
    user_id: str,
) -> list[dict[str, Any]]:
    """Generate official Risk-Locker quotations for all underwriter entries under a tenure."""
    entries = list(
        db.scalars(
            select(TenureComparisonEntry).where(TenureComparisonEntry.tenure_id == tenure_id)
        ).all()
    )
    results = []
    for entry in entries:
        res = generate_quotation_for_entry(db, tenure_id, entry.id, user_id)
        results.append(res)
    return results


def rescan_comparison_tenure(db: Session, tenure_id: str) -> dict[str, Any]:
    """Force re-extract and rescan all sessions and entries under a tenure."""
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise ValueError(f"Tenure {tenure_id} not found")

    from sqlalchemy import or_
    sessions = list(
        db.scalars(
            select(SessionModel)
            .where(
                or_(
                    SessionModel.tenure_id == tenure.id,
                    SessionModel.tracked_vehicle_id == tenure.tracked_vehicle_id,
                )
            )
        ).all()
    )

    entries = list(
        db.scalars(
            select(TenureComparisonEntry).where(TenureComparisonEntry.tenure_id == tenure.id)
        ).all()
    )
    entry_by_session = {e.session_id: e for e in entries if e.session_id}

    veh_yom = getattr(tenure.tracked_vehicle, "manufacture_year", None) if tenure.tracked_vehicle else None
    quote_year = tenure.coverage_start_date.year if tenure.coverage_start_date else datetime.now().year

    detected_ws = None
    for s in sessions:
        f = s.draft.fields if s.draft and isinstance(s.draft.fields, dict) else {}
        b_res = _resolve_comparison_benefits(
            db, s, getattr(s, "company_id", None), f, float(tenure.windscreen_target) if tenure.windscreen_target else None
        )
        if b_res.get("windscreen_sum_insured") and float(b_res["windscreen_sum_insured"]) > 0:
            detected_ws = float(b_res["windscreen_sum_insured"])

        entry = entry_by_session.get(s.id)
        if entry:
            sum_ins = _extract_vehicle_sum_insured(f, s_obj=s)
            motor_prem = _extract_vehicle_motor_premium(f)
            val_type, agreed = _extract_valuation_type(f, s_obj=s)
            if sum_ins > 0:
                entry.sum_insured = sum_ins
            if motor_prem > 0:
                entry.motor_premium = motor_prem
            entry.valuation_type = val_type
            entry.agreed_value = agreed
            entry.excess = _extract_excess(f, s_obj=s)
            entry.towing_limit = b_res["towing_km"]
            entry.towing_km = b_res["towing_km"]
            entry.windscreen_sum_insured = b_res["windscreen_sum_insured"]
            entry.special_perils = b_res["special_perils"]
            entry.llp_llop = b_res["llp_llop"]

            raw_w = _extract_val(f.get("waiver_of_betterment"))
            has_peril = check_has_betterment_peril(f, b_res.get("combined_text", ""), raw_w)
            live_waiver, live_bet_rate, live_bet_disp = evaluate_betterment_rules(
                yom=veh_yom,
                quote_year=quote_year,
                company_name=entry.company_name,
                has_betterment_peril=has_peril,
                is_comprehensive_private=True,
            )
            entry.betterment_rate = live_bet_rate
            entry.betterment_display = live_bet_disp
            entry.waiver_betterment = live_waiver

            entry.road_tax = float(tenure.road_tax)
            entry.runner_fee = float(tenure.runner_fee)
            entry.total_payable = float(entry.motor_premium) + entry.road_tax + entry.runner_fee
            if entry.sum_insured > 0:
                entry.rate_percentage = round((float(entry.motor_premium) / float(entry.sum_insured)) * 100, 4)

    if detected_ws and tenure.windscreen_target is None:
        tenure.windscreen_target = detected_ws

    tv = tenure.tracked_vehicle
    if not tv and tenure.tracked_vehicle_id:
        tv = db.get(TrackedVehicle, tenure.tracked_vehicle_id)
        if tv:
            tenure.tracked_vehicle = tv
    if not tv and tenure.vehicle_no:
        tv = db.scalar(select(TrackedVehicle).where(TrackedVehicle.vehicle_no == tenure.vehicle_no))
        if not tv:
            tv = TrackedVehicle(vehicle_no=tenure.vehicle_no)
            db.add(tv)
            db.flush()
        tenure.tracked_vehicle = tv
        tenure.tracked_vehicle_id = tv.id

    if tv:
        for s in sessions:
            if s.draft and isinstance(s.draft.fields, dict):
                f = s.draft.fields
                if not tv.car_model and f.get("car_model"):
                    tv.car_model = _safe_str(f.get("car_model"))
                if not tv.engine_cc and f.get("engine_cc"):
                    tv.engine_cc = _safe_str(f.get("engine_cc"))
                if not tv.chassis_no and (f.get("chassis_number") or f.get("chassis_no")):
                    tv.chassis_no = _safe_str(f.get("chassis_number") or f.get("chassis_no"))
                if not tv.engine_no and (f.get("engine_number") or f.get("engine_no")):
                    tv.engine_no = _safe_str(f.get("engine_number") or f.get("engine_no"))
                if not tv.manufacture_year and (f.get("manufacture_year") or f.get("yom")):
                    try:
                        tv.manufacture_year = int(_safe_str(f.get("manufacture_year") or f.get("yom")))
                    except Exception:
                        pass

    db.commit()
    return get_marketing_comparison(db, tenure_id)


def format_whatsapp_teaser(db: Session, tenure_id: str) -> str:
    """Format a clean, executive WhatsApp teaser message comparing all underwriters for client messaging."""
    data = get_marketing_comparison(db, tenure_id)
    tenure = data["tenure"]
    entries = data["entries"]

    plate = tenure["vehicle_no"]
    customer = tenure["customer_name"]
    model = tenure["vehicle_model"]
    period = tenure["coverage_period_formatted"]
    ncd = tenure.get("ncd_percentage")
    ncd_str = f"{ncd:.0f}%" if ncd is not None else "Not Detected"

    lines = [
        f"🚗 *Insurance Renewal Comparison for {plate}*",
        f"👤 Customer: {customer}",
        f"🚘 Vehicle: {model} ({tenure['engine_cc']})",
        f"📅 Period: {period} | NCD: {ncd_str}",
        f"🛣️ Roadtax and Runner fee : RM {tenure['fixed_costs_total']:.2f}",
        "",
        "📋 *UNDERWRITER COMPARISON:*",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for idx, e in enumerate(entries, 1):
        rec_tag = " ★ (RECOMMENDED)" if e["is_recommended"] else ""
        val_tag = "Agreed Value" if e["agreed_value"] else "Market Value"
        betterment_tag = "Yes" if e["waiver_betterment"] else "No"

        lines.extend([
            f"*{idx}. {e['company_name']}{rec_tag}*",
            f"   • Sum Insured: RM {e['sum_insured']:,.2f} ({val_tag})",
            f"   • Motor Insurance: RM {e['motor_premium']:,.2f}",
            f"   • *TOTAL PAYABLE: RM {e['total_payable']:,.2f}*",
            f"   • Towing: {e['towing_limit']}",
            f"   • Waiver of Betterment: {betterment_tag} | Excess: RM {e['excess']:.2f}",
            "",
        ])

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")

    rec_winners = [e for e in entries if e.get("is_recommended")]
    if len(rec_winners) == 1:
        lines.append(f"🏆 *Recommended Choice:* {rec_winners[0]['company_name']} (Total: RM {rec_winners[0]['total_payable']:,.2f})\n")
    elif len(rec_winners) > 1:
        winner_items = ", ".join(f"{w['company_name']} (RM {w['total_payable']:,.2f})" for w in rec_winners)
        lines.append(f"🏆 *Shortlisted Options ({len(rec_winners)}):* {winner_items}\n")

    lines.append("💡 *Please let us know your preferred insurer so we can issue your official Risk-Locker quotation!*")

    return "\n".join(lines)

def reset_comparison_entry_to_detected(db: Session, tenure_id: str, entry_id: str) -> dict[str, Any]:
    """Reset a manual override back to original AI detected values for a specific entry."""
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise ValueError("Tenure not found")
        
    entry = db.get(TenureComparisonEntry, entry_id)
    if not entry or entry.tenure_id != tenure_id:
        raise ValueError("Entry not found")
        
    if not entry.session_id:
        raise ValueError("Manual entries without an uploaded file cannot be reset to detected values.")
        
    session = db.get(SessionModel, entry.session_id)
    if not session or not session.uploaded_file_id:
        raise ValueError("Original session or file not found")
        
    # Get original extraction record
    from app.models.tables import ExtractionRecord
    extraction = db.query(ExtractionRecord).filter(ExtractionRecord.uploaded_file_id == session.uploaded_file_id).first()
    if not extraction or not extraction.candidates:
        raise ValueError("No original AI extraction record found to reset to.")
        
    # Overwrite the mutable draft with the immutable extraction candidates
    from sqlalchemy.orm.attributes import flag_modified
    from app.models.tables import QuotationDraft
    if session.draft:
        session.draft.fields = dict(extraction.candidates)
        flag_modified(session.draft, "fields")
    else:
        session.draft = QuotationDraft(
            fields=dict(extraction.candidates),
            original_draft=dict(extraction.candidates),
            display_options={},
        )
        db.add(session.draft)
        
    # Delete the current entry so get_marketing_comparison auto-hydrates a fresh one
    db.delete(entry)
    db.commit()
    
    # Return refreshed comparison
    return get_marketing_comparison(db, tenure_id)
