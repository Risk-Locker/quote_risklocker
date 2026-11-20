"""Deterministic Towing Benefit Resolution Engine.

Resolves Malaysian underwriter towing entitlements (RM monetary limit, KM distance limit,
or Unlimited) from `InsuranceCompany.policy_rules["towing"]` (seeded in Migration 082),
with safe fallback defaults in `company_rules.py` for unit tests without DB rows.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.marketing_comparison.company_rules import resolve_company_towing_rule

_UNIVERSAL_UNLIMITED_KW: tuple[str, ...] = (
    "unlimited towing",
    "24-hr unlimited",
    "24 hour unlimited",
    "tanpa had",
    "unlimited mileage",
    "unlimited distance",
    "unlimited towing costs",
    "unlimited towing breakdown",
)

_TARIFF_PATTERNS: tuple[str, ...] = (
    "statutory tariff",
    "tariff policy",
    "act only",
    "act policy",
    "basic tariff",
    "tariff basic",
)

_PLAN_PATTERNS: tuple[tuple[str, str], ...] = (
    ("plan 4", r"\b(?:plan|pelan)\s*(?:4|d)\b|\bunlimited\b|\bpa\s*plus\s*4\b|\bpa\+\s*4\b|\bpa\s*4\b"),
    ("plan 3", r"\b(?:plan|pelan)\s*(?:3|c)\b|\b300\s*km\b|\bpa\s*plus\s*3\b|\bpa\+\s*3\b|\bpa\s*3\b"),
    ("plan 2", r"\b(?:plan|pelan)\s*(?:2|b)\b|\b200\s*km\b|\bpa\s*plus\s*2\b|\bpa\+\s*2\b|\bpa\s*2\b"),
    ("plan 1", r"\b(?:plan|pelan)\s*(?:1|a)\b|\b100\s*km\b|\bpa\s*plus\s*1\b|\bpa\+\s*1\b|\bpa\s*1\b"),
)


def _is_non_comprehensive(text: str) -> bool:
    return (
        any(k in text for k in ("third party only", "third party fire", "tpft"))
        or text.strip() in {"third party", "tp", "tpo"}
    ) and "comprehensive" not in text


def _is_statutory_tariff(text: str, exclude_brand_keywords: list[str] | tuple[str, ...]) -> bool:
    is_stat = any(kw in text for kw in _TARIFF_PATTERNS) or ("tariff" in text and "basic" in text)
    if not is_stat:
        return False
    return not any(b in text for b in exclude_brand_keywords)


def _match_catalog_display(cdv: str, is_rm_based: bool) -> str | None:
    if any(kw in cdv.lower() for kw in ("unlimited", "tanpa had")):
        return cdv
    if is_rm_based:
        m_rm = re.search(r"^(?:rm|myr)\s*([\d,]+)", cdv, re.IGNORECASE)
        if m_rm:
            val = int(m_rm.group(1).replace(",", ""))
            if val >= 200:
                return f"RM {val}"
        return None
    if re.search(r"\b\d+\s*km\b", cdv, re.IGNORECASE):
        return cdv
    return None


def _is_explicit_no_towing(raw_val: str) -> bool:
    s = (raw_val or "").strip()
    if not s:
        return False
    return bool(
        re.search(
            r"(?i)^(?:0(?:\.0+)?|(?:rm|myr)\s*0(?:\.0+)?|0(?:\.0+)?\s*km|no\s*towing|without\s*towing|not\s*included|none|no|tiada|nil)$",
            s,
        )
    )


def resolve_insurer_towing_limit(
    company_name: str | None = None,
    combined_text: str = "",
    extracted_towing: str | None = None,
    catalog_display_value: str | None = None,
    *,
    company_obj: Any = None,
) -> str:
    """Resolve exact towing limit string (RM, km, Unlimited, or No towing) from DB policy_rules."""
    comp = (company_name or getattr(company_obj, "name", None) or "").lower().strip()
    text = (combined_text or "").lower()
    raw_ext = str(extracted_towing or "").strip()

    if _is_explicit_no_towing(raw_ext):
        return "No towing"

    if _is_non_comprehensive(text):
        return "-"

    rule = resolve_company_towing_rule(company_name=company_name, company_obj=company_obj)
    metric = str(rule.get("metric") or "").strip()
    metric_low = metric.lower()
    is_rm_based = metric_low == "rm" or metric_low == "unlimited"

    respect_universal = rule.get("respect_universal_unlimited", True)
    if respect_universal and (
        any(kw in text for kw in _UNIVERSAL_UNLIMITED_KW)
        or any(kw in raw_ext.lower() for kw in _UNIVERSAL_UNLIMITED_KW)
    ):
        return "Unlimited"

    if catalog_display_value and catalog_display_value.strip():
        matched_cdv = _match_catalog_display(catalog_display_value.strip(), is_rm_based=is_rm_based)
        if matched_cdv:
            return matched_cdv

    # 1. SDPA / plan-tiered RM rider (e.g., Lonpac E-Assist Smart Driver)
    sdpa_triggers = [str(t).lower() for t in (rule.get("sdpa_triggers") or [])]
    raw_sdpa_triggers = [str(t).lower() for t in (rule.get("raw_ext_sdpa_triggers") or [])]
    if sdpa_triggers and (
        any(kw in text for kw in sdpa_triggers) or any(kw in raw_ext.lower() for kw in raw_sdpa_triggers)
    ):
        sdpa_plan1 = str(rule.get("sdpa_plan1_limit") or "").strip()
        if sdpa_plan1 and any(p in text for p in ("plan 1", "pelan 1", "plan a", "rm 600", "rm600", "600")):
            return sdpa_plan1
        return str(rule.get("unlimited_label") or "Unlimited")

    # 2. Plan-tiered KM upgrade riders (e.g., Takaful Malaysia Motor PA Plus)
    upgrade_triggers = [str(t).lower() for t in (rule.get("upgrade_triggers") or [])]
    raw_upgrade_triggers = [str(t).lower() for t in (rule.get("raw_ext_upgrade_triggers") or [])]
    plan_limits = rule.get("plan_limits") if isinstance(rule.get("plan_limits"), dict) else {}
    if upgrade_triggers and plan_limits and (
        any(kw in text for kw in upgrade_triggers) or any(kw in raw_ext.lower() for kw in raw_upgrade_triggers)
    ):
        for plan_key, pattern in _PLAN_PATTERNS:
            if re.search(pattern, text):
                if plan_key in plan_limits:
                    return str(plan_limits[plan_key])
        return str(plan_limits.get("plan 1") or rule.get("base_limit") or "100 km")

    # 3. Direct Unlimited triggers (QBE N4/DPA/DPP, Etiqa OTO 360, Tune AutoBuddy, Allianz Road Rangers, etc.)
    unlimited_triggers = [str(t).lower() for t in (rule.get("unlimited_triggers") or [])]
    raw_unlim_triggers = [str(t).lower() for t in (rule.get("raw_ext_unlimited_triggers") or [])]
    if unlimited_triggers and (
        any(kw in text for kw in unlimited_triggers)
        or any(kw in raw_ext.lower() for kw in raw_unlim_triggers)
        or (not respect_universal and "unlimited" in text)
    ):
        return str(rule.get("unlimited_label") or "Unlimited")

    # 4. Statutory tariff policy limit (RM 200) when applicable
    tariff_limit = str(rule.get("tariff_limit") or "").strip()
    exclude_brands = [str(b).lower() for b in (rule.get("tariff_exclude_brand_keywords") or [])]
    if tariff_limit and _is_statutory_tariff(text, exclude_brands):
        return tariff_limit

    # 5. Tiered KM package variants (Premier / Lite / Liberty)
    premier_limit = str(rule.get("premier_limit") or "").strip()
    lite_limit = str(rule.get("lite_limit") or "").strip()
    if premier_limit and ("premier" in text or "365 km" in text or "365km" in text or "365-km" in text):
        return premier_limit
    if "liberty" in comp or "liberty" in text:
        if "amdrive plus" in text or "unlimited" in text:
            return "Unlimited"
        return "150 km"
    if lite_limit and "lite" in text:
        return lite_limit

    # 6. Explicit extracted limit matching insurer's metric
    if is_rm_based:
        allowed_vals = rule.get("allowed_rm_values")
        m_raw_rm = re.search(r"(?:rm|myr)\s*(\d{2,4})", raw_ext, re.IGNORECASE)
        if m_raw_rm:
            val = int(m_raw_rm.group(1))
            if isinstance(allowed_vals, list) and allowed_vals:
                if val in allowed_vals:
                    return f"RM {val}"
            elif val >= 200:
                return f"RM {val}"
    else:
        m_raw_km = re.search(r"(\d+)\s*km\b", raw_ext, re.IGNORECASE)
        if m_raw_km:
            return f"{m_raw_km.group(1)} km"

    # 7. Plain integer in raw_ext when no company rule matched
    if not rule:
        m_num = re.match(r"^(\d+)$", raw_ext)
        if m_num:
            val = int(m_num.group(1))
            if val in (200, 300, 400, 500, 600):
                return f"RM {val}"
            return f"{val} km"

    # 8. DB-configured base limit (or generic 50 km fallback for unknown KM insurers)
    base_limit = str(rule.get("base_limit") or "").strip()
    if base_limit:
        return base_limit
    return "-" if is_rm_based else "50 km"
