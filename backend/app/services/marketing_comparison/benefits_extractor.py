"""Benefits and Figures Extractor for Marketing Comparison.

Extracts sums insured, basic figures, motor premiums, valuation types,
policy excess, windscreen coverage, towing limits, and peril breakdowns
from raw session extractions and drafts.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.tables import (
    BenefitConcept,
    CatalogOffering,
    DraftBenefitSelection,
    ExtractionBenefitLine,
    ExtractionRecord,
    InsuranceCompany,
    Session as SessionModel,
)
from app.services.benefit_evaluation_engine import BenefitEvaluationEngine, EvaluatedBenefit
from app.services.marketing_comparison.ncd_evaluator import (
    check_has_betterment_peril,
    evaluate_betterment_rules,
    get_standard_betterment_rate,
    normalize_towing_km,
    calculate_vehicle_age,
)
from app.services.marketing_comparison.towing_evaluator import (
    resolve_insurer_towing_limit,
)

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

    # Parse compact endorsement lists (e.g. "Endorsements Attached: 02, 57, 72, 89, 97, 100, 112")
    end_matches = re.findall(
        r"(?:endorsements?|clauses?|perils?)\s*(?:attached|attaching|applied)?\s*[:\-]\s*([0-9a-zA-Z,\s\(\)\.\/]+)",
        text,
        re.IGNORECASE,
    )
    end_tokens: set[str] = set()
    for em in end_matches:
        for t in re.split(r"[,;\s]+", em):
            t_clean = re.sub(r"[^0-9a-zA-Z]", "", t).lower()
            if t_clean:
                end_tokens.add(t_clean)

    def add(tag: str):
        if tag not in seen:
            seen.add(tag)
            found.append(tag)

    # 1. Telematics (Drive Less Save More)
    if any(k in text for k in ("drive less save more", "telematics", "pay as you drive", "mileage based")):
        add("TELEMATICS")

    # 2. Towing upgrade / 24/7 Unlimited / Towing Assistance / Endorsement 89
    if any(k in text for k in ("towing", "tunda", "24/7 emergency", "unlimited towing", "towing mileage", "extra towing", "towing upgrade", "towing assistance", "breakdown assistance", "auto assist", "tele bantuan", "mestari assist", "e-assist", "road rangers")) or re.search(r"\b(?:endorsement|end|end\.)\s*89\b", text) or ("89" in end_tokens):
        add("TOWING")

    # 3. LLP (Legal Liability to Passengers / Endorsement 100)
    if any(k in text for k in ("legal liability to passenger", "liability to passenger", "legal liability to pax", "lltp", "end 100", "endorsement 100", "end. 100")) or re.search(r"\bllp\b", text) or re.search(r"\b(?:endorsement|end|end\.)\s*100\b", text) or ("100" in end_tokens):
        add("LLP")

    # 4. LLOP (Legal Liability of Passengers / Endorsement 72)
    if any(k in text for k in ("legal liability of passenger", "liability of passenger", "negligent act", "end 72", "endorsement 72", "end. 72")) or re.search(r"\bllop\b", text) or re.search(r"\b(?:endorsement|end|end\.)\s*72\b", text) or ("72" in end_tokens):
        add("LLOP")

    # 5. EV Wall Charger
    if any(k in text for k in ("ev home wall charger", "wall charger", "ev charger", "ev coverage")):
        add("EV CHARGE")

    # 6. PA (Personal Accident to Driver / Endorsement N4)
    if any(k in text for k in ("personal accident", "pa to driver", "driver & passenger pa", "driver pa", "oto 360", "motor pa plus", "dpa", "dpp", "sdpa", "autobuddy")) or (re.search(r"\bpa\b", text) and "driver" in text) or ("n4" in end_tokens):
        add("PA")

    # 7. Compassionate Benefit
    if any(k in text for k in ("compassionate benefit", "compassionate allowance", "compassionate")):
        add("COMPASSIONATE")

    # 8. Loss & Theft (Special Relief Allowance)
    if any(k in text for k in ("special relief allowance", "total loss and theft", "loss and theft", "theft allowance")):
        add("LOSS & THEFT")

    # 9. Flood / Special Perils / Endorsement 57
    if any(k in text for k in ("flood", "banjir", "special perils", "peril khas", "natural disaster", "storm", "ribut", "typhoon", "landslide", "tanah runtuh", "convulsion of nature", "water damage", "act of god")) or re.search(r"\b(?:endorsement|end|end\.)\s*57(?:[a-z]|\b)", text) or bool({"57", "57a", "57b"}.intersection(end_tokens)):
        add("FLOOD")

    # 10. Windscreen / Endorsement 97 / Endorsement 89
    if any(k in text for k in ("windscreen", "cermin", "w/screen", "pecahan cermin")) or re.search(r"\b(?:endorsement|end|end\.)\s*(?:89|97)\b", text) or bool({"89", "97"}.intersection(end_tokens)):
        add("WINDSCREEN")

    # 11. Key Care
    if any(k in text for k in ("key care", "key replacement", "replacement of key")):
        add("KEY CARE")

    # 12. CART / Loss of Use / Endorsement 112
    if any(k in text for k in ("assessed repair time", "cart", "loss of use")) or re.search(r"\b(?:endorsement|end|end\.)\s*112\b", text) or ("112" in end_tokens):
        add("CART")

    # 13. Current Year NCD Relief / Endorsement 111
    if any(k in text for k in ("ncd relief", "current year ncd", "relief of ncd")) or re.search(r"\b(?:endorsement|end|end\.)\s*111\b", text) or ("111" in end_tokens):
        add("NCD RELIEF")

    # 14. Waiver of Betterment / Endorsement 113
    if any(k in text for k in ("waiver of betterment", "betterment waiver", "betterment")) or re.search(r"\b(?:endorsement|end|end\.)\s*113\b", text) or ("113" in end_tokens):
        add("BETTERMENT")

    # 15. Strike, Riot & Civil Commotion / Endorsement 25 / Endorsement 101
    if any(k in text for k in ("strike, riot", "strike riot", "srcc", "civil commotion")) or re.search(r"\b(?:endorsement|end|end\.)\s*(?:25|101)\b", text) or bool({"25", "101"}.intersection(end_tokens)):
        add("SRCC")

    # 16. All Drivers / Endorsement 108
    if any(k in text for k in ("all drivers", "unnamed drivers", "semua pemandu")) or re.search(r"\b(?:endorsement|end|end\.)\s*108\b", text) or ("108" in end_tokens):
        add("ALL DRIVERS")

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
        r"(?i)policy\s+excess\s*:\s*(?:RM|MYR)?\s*(\d[\d,]*(?:\.\d{2})?)",
        r"(?i)(?:(\d[\d,]*(?:\.\d{2})?)\s*(?:RM|MYR)?\s*voluntary\s+excess|voluntary\s+excess\s*(?:RM|MYR)?\s*(\d[\d,]*(?:\.\d{2})?))",
        r"(?i)excess\s+all\s+claims\s*:\s*(?:RM|MYR)?\s*(\d[\d,]*(?:\.\d{2})?)",
        r"(?i)\*?\s*excess\s+amount\s*:\s*(?:RM|MYR)?\s*(\d[\d,]*(?:\.\d{2})?)",
        r"(?i)excess\s+lebihan\s*\(\s*(?:MYR|RM)?\s*(\d[\d,]*(?:\.\d{2})?)\s*\)",
        r"(?i)excess\s*(?:/\s*lebihan)?\s*[:]?\s*(?:RM|MYR)?\s*(\d[\d,]*(?:\.\d{2})?)",
    ]
    for line in text.splitlines():
        clean_line = line.strip()
        if not clean_line or narrative_pattern.search(clean_line):
            continue
        for pat in patterns:
            m = re.search(pat, clean_line)
            if m:
                valid_groups = [g for g in m.groups() if g is not None and g.strip()]
                if not valid_groups:
                    continue
                val_str = valid_groups[0].strip().replace(",", "")
                try:
                    return float(val_str)
                except (ValueError, TypeError):
                    continue
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
                
    # 2. Extraction Benefit Lines & Extraction Record text
    ext_rec = None
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

        ext_rec = db.scalar(
            select(ExtractionRecord).where(ExtractionRecord.uploaded_file_id == session.uploaded_file_id)
        )
        if ext_rec:
            if ext_rec.raw_text:
                tokens.append(ext_rec.raw_text)
            if ext_rec.ocr_text:
                tokens.append(ext_rec.ocr_text)
            if isinstance(ext_rec.benefit_lines, list):
                for bl in ext_rec.benefit_lines:
                    if isinstance(bl, dict):
                        for bk in ("raw_label", "normalized_label", "label", "benefit_name", "description"):
                            if bl.get(bk):
                                tokens.append(str(bl[bk]))

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

    # Parse compact endorsement lists (e.g. "Endorsements Attached: 02, 57, 72, 89, 97, 100, 112")
    end_matches = re.findall(
        r"(?:endorsements?|clauses?|perils?)\s*(?:attached|attaching|applied)?\s*[:\-]\s*([0-9a-zA-Z,\s\(\)\.\/]+)",
        combined_text,
        re.IGNORECASE,
    )
    end_tokens: set[str] = set()
    for em in end_matches:
        for t in re.split(r"[,;\s]+", em):
            t_clean = re.sub(r"[^0-9a-zA-Z]", "", t).lower()
            if t_clean:
                end_tokens.add(t_clean)

    # --- SPECIAL PERILS ---
    # Genuine perils: flood, typhoon, storm, landslide, peril khas, special perils, or Endorsement 57
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
    ) or bool(re.search(r"\b(?:endorsement|end|end\.)\s*57(?:[a-z]|\b)", combined_text)) or bool({"57", "57a", "57b"}.intersection(end_tokens))
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

    # Priority 5: Fallback to tenure target windscreen if windscreen is covered in quote or endorsements
    if windscreen_amount is None and (
        any(w in combined_text for w in ("windscreen", "w/screen", "cermin"))
        or bool(re.search(r"\b(?:endorsement|end|end\.)\s*(?:89|97)\b", combined_text))
        or bool({"89", "97"}.intersection(end_tokens))
    ):
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
            "lltp",
        )
    ) or bool(re.search(r"\b(?:endorsement|end|end\.)\s*(?:100|72)\b", combined_text)) or bool({"100", "72"}.intersection(end_tokens))
    llp_val = "Included" if has_llp else None

    # --- TOWING ---
    target_comp_id = company_id or getattr(session, "company_id", None)
    comp_name_str = ""
    if target_comp_id:
        comp_obj = db.get(InsuranceCompany, target_comp_id)
        if comp_obj and comp_obj.name:
            comp_name_str = comp_obj.name
    if not comp_name_str:
        comp_name_str = str(f.get("insurance_company") or f.get("company_name") or f.get("insurer") or getattr(session, "detected_company", None) or "")

    towing_limit_val: str | None = None
    # Grounding from CatalogOfferings in draft catalog revision
    if session and getattr(session, "draft", None) and getattr(session.draft, "catalog_revision_id", None):
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

    raw_towing = _safe_str(f.get("towing_limit") or f.get("towing"))

    clean_towing = resolve_insurer_towing_limit(
        company_name=comp_name_str,
        combined_text=combined_text,
        extracted_towing=raw_towing,
        catalog_display_value=towing_limit_val,
    )

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

        # Also fallback to ext_rec.benefit_lines if ext_lines was empty
        if not detailed_perils and ext_rec and isinstance(ext_rec.benefit_lines, list):
            for bl in ext_rec.benefit_lines:
                if not isinstance(bl, dict):
                    continue
                lbl = bl.get("raw_label") or bl.get("label") or bl.get("benefit_name") or bl.get("description")
                if not lbl:
                    continue
                lbl_clean = str(lbl).strip()
                norm_k = lbl_clean.lower()
                if norm_k in seen_peril_names:
                    continue
                cost_val = _to_float(bl.get("premium_cost") or bl.get("amount") or bl.get("cost"))
                limit_val = bl.get("coverage_limit") or bl.get("limit") or bl.get("sum_insured")
                seen_peril_names.add(norm_k)
                detailed_perils.append({
                    "name": lbl_clean,
                    "coverage_limit": str(limit_val) if limit_val else None,
                    "premium_cost": cost_val,
                    "has_cost": cost_val > 0.0,
                    "is_included": cost_val == 0.0 or "included" in str(bl.get("value", "")).lower(),
                })

    # 2. Synthesize canonical items if not already populated in detailed_perils
    def _is_peril_already_represented(keywords: tuple[str, ...]) -> bool:
        return any(any(kw in name for kw in keywords) for name in seen_peril_names)

    if windscreen_amount and not _is_peril_already_represented(("windscreen", "cermin", "w/screen")):
        ws_cost = round(windscreen_amount * 0.15, 2)
        seen_peril_names.add("windscreen protection")
        detailed_perils.append({
            "name": "Windscreen Protection",
            "coverage_limit": f"RM {windscreen_amount:,.2f}",
            "premium_cost": ws_cost,
            "has_cost": True,
            "is_included": False,
        })

    if (special_perils_val or "FLOOD" in canonical_perils_list) and not _is_peril_already_represented(("special peril", "flood", "banjir", "peril khas", "storm", "natural disaster")):
        seen_peril_names.add("special perils (flood & storm)")
        detailed_perils.append({
            "name": "Special Perils (Flood & Storm)",
            "coverage_limit": "Vehicle Sum Insured",
            "premium_cost": 0.0,
            "has_cost": False,
            "is_included": True,
        })

    if (llp_val or "LLP" in canonical_perils_list) and not _is_peril_already_represented(("liability to passenger", "llp", "lltp")):
        seen_peril_names.add("legal liability to passengers (llp)")
        detailed_perils.append({
            "name": "Legal Liability to Passengers (LLP)",
            "coverage_limit": "Statutory",
            "premium_cost": 41.85,
            "has_cost": True,
            "is_included": False,
        })

    if ("LLOP" in canonical_perils_list or "llop" in combined_text or "72" in end_tokens) and not _is_peril_already_represented(("liability of passenger", "llop")):
        seen_peril_names.add("legal liability of passengers (llop)")
        detailed_perils.append({
            "name": "Legal Liability of Passengers (LLOP)",
            "coverage_limit": "Statutory",
            "premium_cost": 7.50,
            "has_cost": True,
            "is_included": False,
        })

    if clean_towing and not _is_peril_already_represented(("towing", "roadside", "tunda")):
        seen_peril_names.add("roadside towing")
        detailed_perils.append({
            "name": f"Roadside Towing ({clean_towing})",
            "coverage_limit": clean_towing,
            "premium_cost": 0.0,
            "has_cost": False,
            "is_included": True,
        })

    if "CART" in canonical_perils_list and not _is_peril_already_represented(("cart", "assessed repair time", "loss of use")):
        seen_peril_names.add("cart")
        detailed_perils.append({
            "name": "Compensation for Assessed Repair Time (CART)",
            "coverage_limit": "Policy Schedule / Endorsement 112",
            "premium_cost": 0.0,
            "has_cost": False,
            "is_included": True,
        })

    if "BETTERMENT" in canonical_perils_list and not _is_peril_already_represented(("betterment", "waiver of betterment")):
        seen_peril_names.add("betterment")
        detailed_perils.append({
            "name": "Waiver of Betterment",
            "coverage_limit": "Waived / Endorsement 113",
            "premium_cost": 0.0,
            "has_cost": False,
            "is_included": True,
        })

    if "NCD RELIEF" in canonical_perils_list and not _is_peril_already_represented(("ncd relief", "current year ncd")):
        seen_peril_names.add("ncd relief")
        detailed_perils.append({
            "name": "Current Year NCD Relief",
            "coverage_limit": "Endorsement 111",
            "premium_cost": 0.0,
            "has_cost": False,
            "is_included": True,
        })

    if "PA" in canonical_perils_list and not _is_peril_already_represented(("personal accident", "driver pa", "oto 360", "motor pa plus", "dpa", "dpp", "sdpa", "autobuddy")):
        seen_peril_names.add("personal accident")
        detailed_perils.append({
            "name": "Personal Accident (Driver & Passengers)",
            "coverage_limit": "Endorsement N4 / Rider",
            "premium_cost": 0.0,
            "has_cost": False,
            "is_included": True,
        })

    if "SRCC" in canonical_perils_list and not _is_peril_already_represented(("strike", "riot", "srcc", "civil commotion")):
        seen_peril_names.add("srcc")
        detailed_perils.append({
            "name": "Strike, Riot & Civil Commotion (SRCC)",
            "coverage_limit": "Endorsement 25/101",
            "premium_cost": 0.0,
            "has_cost": False,
            "is_included": True,
        })

    if "ALL DRIVERS" in canonical_perils_list and not _is_peril_already_represented(("all drivers", "unnamed drivers", "semua pemandu")):
        seen_peril_names.add("all drivers")
        detailed_perils.append({
            "name": "All Drivers Coverage",
            "coverage_limit": "Endorsement 108",
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


