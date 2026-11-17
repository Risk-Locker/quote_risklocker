"""Deterministic Towing Benefit Resolution Engine.

Implements Malaysian underwriter-specific towing metrics (RM monetary limit vs KM distance limit)
and conditional upgrades triggered by policy riders, packages, and endorsement add-ons:
- QBE: Base RM (Default RM 500 Private Car Protector; tariff RM 200). Upgrades to Unlimited via DPA / DPP (Endorsement N4).
- Lonpac: Base RM (Default RM 400 E-Assist; tariff RM 200). Upgrades via SDPA / SDPA Plus (Plan 1 -> RM 600, Plan 2/Plus -> Unlimited).
- Berjaya Sompo: Default Unlimited (no upgrade required on comprehensive packages).
- Tune Protect: Standard RM 300; upgrades to Unlimited via Motor Easy Bundle / AutoBuddy / Motor Shield.
- Etiqa: Base KM (Default 200 km). Upgrades via OTO 360 -> Unlimited - Driver Plan 1.
- Takaful Malaysia / STMB: Base KM (Default 50 km). Upgrades via Motor PA Plus (Plan 1 -> 100 km, Plan 2 -> 200 km, Plan 3 -> 300 km, Plan 4 -> Unlimited).
- AmAssurance / Liberty: auto365 Plus -> 100 km, auto365 Premier -> 365 km (no upgrade required).
- Allianz: Road Rangers (150 km breakdown; unlimited accident towing to panel workshops).
"""

from __future__ import annotations

import re
from typing import Any


def resolve_insurer_towing_limit(
    company_name: str | None = None,
    combined_text: str = "",
    extracted_towing: str | None = None,
    catalog_display_value: str | None = None,
) -> str:
    """Resolve exact towing limit string (with RM or KM metric) for an underwriter quotation or cover note.
    
    Priority Order:
    1. Universal Unlimited indicators (tanpa had, unlimited towing).
    2. Underwriter classification (RM-based vs KM-based).
    3. Conditional riders and upgrade endorsements (DPA/DPP, E-Assist Smart Driver, AutoBuddy/MotorShield, OTO 360, Motor PA Plus).
    4. Explicit catalog offering or manual override (strictly respecting insurer metric).
    5. Statutory tariff vs standard product tier defaults.
    """
    comp = (company_name or "").lower().strip()
    text = (combined_text or "").lower()
    raw_ext = str(extracted_towing or "").strip()

    # Non-comprehensive quotes (Third Party / TPFT) do not bundle complimentary emergency towing
    if (
        any(k in text for k in ("third party only", "third party fire", "tpft"))
        or text.strip() in {"third party", "tp", "tpo"}
    ) and "comprehensive" not in text:
        return "-"

    # Identify whether insurer operates on RM monetary limit or KM distance limit
    is_qbe = "qbe" in comp
    is_lonpac = "lonpac" in comp
    is_sompo = any(k in comp for k in ("sompo", "berjaya sompo"))
    is_tune = "tune" in comp

    # Universal Unlimited Triggers across all underwriters (insurer-specific Plan labels win first for QBE/Etiqa!)
    universal_unlimited_kw = (
        "unlimited towing",
        "24-hr unlimited",
        "24 hour unlimited",
        "tanpa had",
        "unlimited mileage",
        "unlimited distance",
        "unlimited towing costs",
        "unlimited towing breakdown",
    )
    if not (is_qbe or "etiqa" in comp) and (
        any(kw in text for kw in universal_unlimited_kw) or any(kw in raw_ext.lower() for kw in universal_unlimited_kw)
    ):
        return "Unlimited"

    is_rm_based = is_qbe or is_lonpac or is_sompo or is_tune

    # 1. Follow exact builder benefits catalog value first (when no add-on plan triggers below override it)
    if catalog_display_value and catalog_display_value.strip():
        cdv = catalog_display_value.strip()
        if any(kw in cdv.lower() for kw in ("unlimited", "tanpa had")):
            return cdv
        
        if is_rm_based:
            # RM-based insurers MUST NEVER adopt KM distance from catalog display values
            m_cdv_rm = re.search(r"^(?:rm|myr)\s*([\d,]+)", cdv, re.IGNORECASE)
            if m_cdv_rm:
                val = int(m_cdv_rm.group(1).replace(",", ""))
                if val >= 200:
                    return f"RM {val}"
        else:
            # KM-based insurers
            if re.search(r"\b\d+\s*km\b", cdv, re.IGNORECASE):
                return cdv

    # =========================================================================
    # RM-BASED INSURERS
    # =========================================================================

    # --- 1. QBE (QBE Auto Assist / Mestari Assist) ---
    if is_qbe:
        # Upgrade Add-On: DPA / DPP (Driver Passenger Protector / Endorsement N4)
        has_qbe_upgrade = any(
            kw in text
            for kw in (
                "dpa",
                "dpp",
                "driver plus",
                "driver plus plan",
                "driver passenger protector",
                "driver & passenger protector",
                "driver and passenger protector",
                "endorsement n4",
                "end n4",
                "end. n4",
                "n4",
                "unlimited auto assistance",
                "mestari assist upgrade",
                "private car protector dpa",
            )
        ) or any(kw in raw_ext.lower() for kw in ("dpa", "dpp", "n4", "driver plus", "unlimited auto assistance"))

        if has_qbe_upgrade or "unlimited" in text:
            return "Unlimited - Plan 1"

        # Check if statutory tariff policy
        if any(kw in text for kw in ("statutory tariff", "tariff policy", "act only", "basic tariff", "tariff basic")) or ("tariff" in text and "basic" in text):
            return "RM 200"

        # Explicit extracted RM limit in raw_ext (valid QBE monetary caps: RM 200 tariff, RM 500 standard)
        m_raw_rm = re.search(r"(?:rm|myr)\s*(\d{2,4})", raw_ext, re.IGNORECASE)
        if m_raw_rm:
            val = int(m_raw_rm.group(1))
            if val in (200, 300, 400, 500):
                return f"RM {val}"

        # Default under standard non-tariff Private Car Protector policy
        return "RM 500"

    # --- 2. LONPAC (Lonpac E-Assist) ---
    if is_lonpac:
        # Upgrade Add-On: SDPA / SDPA Plus (Secure Driver & Passenger PA rider)
        has_sdpa = any(
            kw in text
            for kw in (
                "sdpa",
                "sdpa plus",
                "sdpa+",
                "secure driver",
                "secure driver & passenger",
                "secure driver and passenger",
                "e-assist smart driver",
                "smart driver",
            )
        ) or any(kw in raw_ext.lower() for kw in ("sdpa", "smart driver"))

        if has_sdpa:
            # Check Plan 1 (RM 600) vs Plan 2 (Unlimited)
            if any(p in text for p in ("plan 1", "pelan 1", "plan a", "rm 600", "rm600", "600")):
                return "RM 600"
            return "Unlimited"

        # Check statutory tariff policy
        if any(kw in text for kw in ("statutory tariff", "tariff policy", "basic tariff", "tariff basic")) or ("tariff" in text and "basic" in text):
            return "RM 200"

        # Explicit extracted RM limit in raw_ext (valid Lonpac denominations: RM 200 tariff, RM 400 standard, RM 600 SDPA)
        m_raw_rm = re.search(r"(?:rm|myr)\s*(\d{2,4})", raw_ext, re.IGNORECASE)
        if m_raw_rm:
            val = int(m_raw_rm.group(1))
            if val in (200, 300, 400, 600):
                return f"RM {val}"

        # Default standard comprehensive E-Assist cap
        return "RM 400"

    # --- 3. BERJAYA SOMPO (SOMPO Motor) ---
    if is_sompo:
        # Basic statutory tariff without Sompo Motor branding
        is_statutory = (any(kw in text for kw in ("statutory tariff", "tariff policy", "act policy", "tariff basic", "basic tariff")) or ("tariff" in text and "basic" in text)) and "sompo motor" not in text and "n-hancer" not in text
        if is_statutory:
            return "RM 200"

        # Flagship comprehensive SOMPO Motor plan bundles unlimited towing costs directly by default
        # Upgrade Add-On: Motor N-hancer Pack -> Unlimited
        return "Unlimited"

    # --- 4. TUNE PROTECT ---
    if is_tune:
        # Upgrade Add-On: Motor Easy Bundle / AutoBuddy / Motor Shield
        has_tune_upgrade = any(
            kw in text
            for kw in ("autobuddy", "auto buddy", "motor pa autobuddy", "motor shield", "motorshield", "motor easy bundle")
        ) or any(kw in raw_ext.lower() for kw in ("autobuddy", "motor shield", "motorshield", "motor easy bundle"))

        if has_tune_upgrade:
            return "Unlimited"

        # Conventional / Standard Policies: Base RM -> RM 300
        m_raw_rm = re.search(r"(?:rm|myr)\s*(\d{2,4})", raw_ext, re.IGNORECASE)
        if m_raw_rm:
            val = int(m_raw_rm.group(1))
            if val in (200, 300, 400):
                return f"RM {val}"

        return "RM 300"

    # =========================================================================
    # KM-BASED INSURERS
    # =========================================================================

    # --- 5. ETIQA (Etiqa Auto Assist) ---
    if any(k in comp for k in ("etiqa", "maybank")):
        # Upgrade Add-On: OTO 360 (Standalone / Motor PA rider)
        has_oto360 = any(
            kw in text
            for kw in ("oto 360", "oto360", "oto-360", "oto premier")
        ) or any(kw in raw_ext.lower() for kw in ("oto 360", "oto360"))

        if has_oto360 or "unlimited" in text:
            return "Unlimited - Driver Plan 1"

        m_raw_km = re.search(r"(\d+)\s*km\b", raw_ext, re.IGNORECASE)
        if m_raw_km:
            return f"{m_raw_km.group(1)} km"

        # Default complimentary breakdown towing: 200 km
        return "200 km"

    # --- 6. TAKAFUL MALAYSIA / STMB (Tele Bantuan) ---
    if any(k in comp for k in ("stmb", "takaful malaysia", "tele bantuan")):
        # Upgrade Add-On: Motor PA Plus / Motor PA Plan
        has_pa_plus = any(
            kw in text
            for kw in ("motor pa plus", "motor pa+", "pa plus", "tele bantuan plus", "pa+", "motor pa plan", "motor pa")
        ) or any(kw in raw_ext.lower() for kw in ("pa plus", "pa+", "motor pa"))

        if has_pa_plus:
            # Plan 1 (100 km), Plan 2 (200 km), Plan 3 (300 km), Plan 4 (Unlimited)
            if re.search(r"\b(?:plan|pelan)\s*(?:4|d)\b|\bunlimited\b|\bpa\s*plus\s*4\b|\bpa\+\s*4\b|\bpa\s*4\b", text):
                return "Unlimited"
            if re.search(r"\b(?:plan|pelan)\s*(?:3|c)\b|\b300\s*km\b|\bpa\s*plus\s*3\b|\bpa\+\s*3\b|\bpa\s*3\b", text):
                return "300 km"
            if re.search(r"\b(?:plan|pelan)\s*(?:2|b)\b|\b200\s*km\b|\bpa\s*plus\s*2\b|\bpa\+\s*2\b|\bpa\s*2\b", text):
                return "200 km"
            if re.search(r"\b(?:plan|pelan)\s*(?:1|a)\b|\b100\s*km\b|\bpa\s*plus\s*1\b|\bpa\+\s*1\b|\bpa\s*1\b", text):
                return "100 km"
            return "100 km"

        # Default complimentary breakdown towing: 50 km
        return "50 km"

    # --- 7. AMASSURANCE / LIBERTY ---
    if any(k in comp for k in ("amassurance", "amgen", "liberty", "kurnia")):
        if "unlimited" in text:
            return "Unlimited"
        if "premier" in text or "365 km" in text or "365km" in text or "365-km" in text:
            return "365 km"
        if "liberty" in comp or "liberty" in text:
            return "150 km"
        if "lite" in text:
            return "50 km"
        return "100 km"

    # --- 8. ALLIANZ ---
    if "allianz" in comp:
        if any(kw in text for kw in ("road rangers", "unlimited")):
            return "Unlimited"
        return "150 km"

    # =========================================================================
    # GENERIC FALLBACK EVALUATION
    # =========================================================================

    # If raw_ext has explicit currency "RM 500", "RM 400"
    m_raw_rm = re.search(r"^(?:rm|myr)\s*(\d{2,4})", raw_ext, re.IGNORECASE)
    if m_raw_rm and int(m_raw_rm.group(1)) >= 200:
        return f"RM {m_raw_rm.group(1)}"

    # If raw_ext has explicit distance "200 km", "50 km"
    if not is_rm_based:
        m_raw_km = re.search(r"(\d+)\s*km\b", raw_ext, re.IGNORECASE)
        if m_raw_km:
            return f"{m_raw_km.group(1)} km"

    # Plain integer in raw_ext
    m_num = re.match(r"^(\d+)$", raw_ext)
    if m_num:
        val = int(m_num.group(1))
        if val in (200, 300, 400, 500, 600) or is_rm_based:
            return f"RM {val}"
        return f"{val} km"

    # Absolute fallback for RM-based vs KM-based
    if is_qbe:
        return "RM 500"
    if is_lonpac:
        return "RM 400"
    if is_sompo:
        return "Unlimited"
    if is_tune:
        return "RM 300"

    if is_rm_based:
        return "RM 200"
    return "50 km"
