"""Deterministic Towing Benefit Resolution Engine.

Implements Malaysian underwriter-specific towing metrics (RM monetary limit vs KM distance limit)
and conditional upgrades triggered by policy riders, packages, and endorsement add-ons:
- QBE: Base RM (Default RM 500; tariff RM 200). Upgrades to Unlimited via DPA / DPP (Endorsement N4).
- Lonpac: Base RM (Default RM 400; tariff RM 200). Upgrades via SDPA / SDPA Plus (Plan 1 -> RM 600, Plan 2/Plus -> Unlimited).
- Berjaya Sompo: Flagship SOMPO Motor bundles Unlimited towing costs directly; tariff basic RM 200; upgrades via Motor N-hancer Pack -> Unlimited.
- Tune Protect: Conventional/agent base RM 300; Motor Easy base 200 km; upgrades via AutoBuddy -> Unlimited.
- Etiqa: Base KM (Default 200 km). Upgrades via OTO 360 -> Unlimited.
- Takaful Malaysia / STMB: Base KM (Default 50 km). Upgrades via Motor PA Plus (Plan 1 -> 100 km, Plan 2 -> 200 km, Plan 3 -> 300 km, Plan 4 -> Unlimited).
- AmAssurance / Liberty: Base KM (Standard 100 km, Liberty 150 km, Premier 365 km). Upgrades via AmDrive Plus / Private Car 365 -> Unlimited.
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
    1. Direct explicit catalog offering or user manual override if specifically provided.
    2. Upgrade add-ons & conditional riders (DPA/DPP, SDPA, Motor N-hancer, AutoBuddy, OTO 360, Motor PA Plus).
    3. Grounded underwriter product tier defaults (RM vs KM).
    4. Fallback normalization.
    """
    comp = (company_name or "").lower().strip()
    text = (combined_text or "").lower()
    raw_ext = str(extracted_towing or "").strip()

    # 1. Check for explicit manual override / catalog display value if already formatted with RM or Unlimited
    if catalog_display_value and catalog_display_value.strip():
        cdv = catalog_display_value.strip()
        if any(kw in cdv.lower() for kw in ("unlimited", "tanpa had")):
            return "Unlimited"
        if re.search(r"^(?:rm|myr)\s*[\d,]+", cdv, re.IGNORECASE):
            return cdv
        if re.search(r"\b\d+\s*km\b", cdv, re.IGNORECASE):
            return cdv

    # 2. Universal Unlimited Triggers across all underwriters
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
    if any(kw in text for kw in universal_unlimited_kw) or any(kw in raw_ext.lower() for kw in universal_unlimited_kw):
        return "Unlimited"

    # =========================================================================
    # RM-BASED INSURERS
    # =========================================================================

    # --- 1. QBE (QBE Auto Assist / Mestari Assist) ---
    if "qbe" in comp:
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
                "mestari assist upgrade",
                "private car protector dpa",
            )
        ) or any(kw in raw_ext.lower() for kw in ("dpa", "dpp", "n4", "driver plus"))

        if has_qbe_upgrade:
            return "Unlimited"

        # Check if statutory tariff policy
        if any(kw in text for kw in ("statutory tariff", "tariff policy", "act only", "basic tariff", "tariff basic")) or ("tariff" in text and "basic" in text):
            return "RM 200"

        # Explicit extracted RM limit
        m_rm = re.search(r"(?:rm|myr)\s*(\d{2,4})", f"{raw_ext} {text}", re.IGNORECASE)
        if m_rm:
            return f"RM {m_rm.group(1)}"

        # Default standard comprehensive Private Car Protector
        return "RM 500"

    # --- 2. LONPAC (Lonpac E-Assist) ---
    if "lonpac" in comp:
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

        # Explicit extracted RM limit
        m_rm = re.search(r"(?:rm|myr)\s*(\d{2,4})", f"{raw_ext} {text}", re.IGNORECASE)
        if m_rm:
            return f"RM {m_rm.group(1)}"

        # Default standard comprehensive E-Assist cap
        return "RM 400"

    # --- 3. BERJAYA SOMPO (SOMPO Motor) ---
    if any(k in comp for k in ("sompo", "berjaya sompo")):
        # Basic statutory tariff without Sompo Motor branding
        is_statutory = (any(kw in text for kw in ("statutory tariff", "tariff policy", "act policy", "tariff basic", "basic tariff")) or ("tariff" in text and "basic" in text)) and "sompo motor" not in text and "n-hancer" not in text
        if is_statutory:
            return "RM 200"

        # Upgrade Add-On: Motor N-hancer Pack or standard flagship SOMPO Motor bundles unlimited towing
        return "Unlimited"

    # --- 4. TUNE PROTECT ---
    if "tune" in comp:
        # Upgrade Add-On: AutoBuddy (Motor PA rider)
        has_autobuddy = any(
            kw in text
            for kw in ("autobuddy", "auto buddy", "motor pa autobuddy")
        ) or "autobuddy" in raw_ext.lower()

        if has_autobuddy:
            return "Unlimited"

        # Tune Protect Motor Easy (Online Portal): 200 km
        if "motor easy" in text or "online" in text:
            return "200 km"

        # Conventional / Agent Policies: Base RM 300
        m_rm = re.search(r"(?:rm|myr)\s*(\d{2,4})", f"{raw_ext} {text}", re.IGNORECASE)
        if m_rm:
            return f"RM {m_rm.group(1)}"

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

        if has_oto360:
            return "Unlimited"

        # Default complimentary breakdown towing: 200 km
        return "200 km"

    # --- 6. TAKAFUL MALAYSIA / STMB (Tele Bantuan) ---
    if any(k in comp for k in ("stmb", "takaful malaysia", "tele bantuan")):
        # Upgrade Add-On: Motor PA Plus
        has_pa_plus = any(
            kw in text
            for kw in ("motor pa plus", "motor pa+", "pa plus", "tele bantuan plus")
        ) or "pa plus" in raw_ext.lower()

        if has_pa_plus:
            # Plan 1 (100 km), Plan 2 (200 km), Plan 3 (300 km), Plan 4 (Unlimited)
            if any(p in text for p in ("plan 4", "pelan 4", "plan d", "unlimited", "4")):
                return "Unlimited"
            if any(p in text for p in ("plan 3", "pelan 3", "plan c", "300 km", "300")):
                return "300 km"
            if any(p in text for p in ("plan 2", "pelan 2", "plan b", "200 km", "200")):
                return "200 km"
            if any(p in text for p in ("plan 1", "pelan 1", "plan a", "100 km", "100")):
                return "100 km"
            return "100 km"

        # Default complimentary breakdown towing: 50 km
        return "50 km"

    # --- 7. AMASSURANCE / LIBERTY ---
    if any(k in comp for k in ("amassurance", "amgen", "liberty", "kurnia")):
        if any(kw in text for kw in ("amdrive plus", "private car 365", "unlimited")):
            return "Unlimited"
        if "premier" in text:
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
    if m_raw_rm:
        return f"RM {m_raw_rm.group(1)}"

    # If raw_ext has explicit distance "200 km", "50 km"
    m_raw_km = re.search(r"(\d+)\s*km\b", raw_ext, re.IGNORECASE)
    if m_raw_km:
        return f"{m_raw_km.group(1)} km"

    # Plain integer in raw_ext
    m_num = re.match(r"^(\d+)$", raw_ext)
    if m_num:
        val = int(m_num.group(1))
        # Large values like 200, 300, 400, 500, 600 might be RM or KM depending on context
        if val in (200, 400, 500, 600) and any(c in comp for c in ("qbe", "lonpac", "sompo", "tune")):
            return f"RM {val}"
        return f"{val} km"

    return "Unlimited"
