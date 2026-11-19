"""Unified Add-On & Benefits Engine for Risklocker Quotation Design 2.

Merges default perks, purchased extras, and optional add-ons into a single unified
4-column card matrix. Selected / ticked benefits float dynamically to the top (slots 01, 02..),
followed by unselected catalog benefits in their standard sequence.
"""

from __future__ import annotations

import re
from typing import Any


CANONICAL_24_CATALOG: list[dict[str, Any]] = [
    {
        "id": "windscreen",
        "title": "Windscreen Coverage",
        "description": "Covers windscreen, window glass and tint repair without affecting NCD.",
        "default_value": "RM 10,000.00",
        "icon_hint": "windscreen",
    },
    {
        "id": "towing",
        "title": "Unlimited Towing",
        "description": "24/7 emergency unlimited towing assistance all over Malaysia.",
        "default_value": "Unlimited",
        "icon_hint": "towing",
    },
    {
        "id": "llop",
        "title": "Legal Liability of Passengers",
        "description": "Protects against third-party claims caused by passenger negligence.",
        "default_value": "",
        "icon_hint": "llop",
    },
    {
        "id": "llp",
        "title": "Legal Liability to Passengers",
        "description": "Protects driver from lawsuits for injury or death to passengers.",
        "default_value": "",
        "icon_hint": "llp",
    },
    {
        "id": "special_perils",
        "title": "Special Perils",
        "description": "Full cover for flood, storm, landslide, earthquake and fallen trees.",
        "default_value": "Full Coverage",
        "icon_hint": "special_perils",
    },
    {
        "id": "all_drivers",
        "title": "All Drivers Excess Waiver",
        "description": "Waives RM400 compulsory excess penalty for all authorized drivers.",
        "default_value": "",
        "icon_hint": "all_driver",
    },
    {
        "id": "pa",
        "title": "Motor PA Plus",
        "description": "Named personal accident protection for driver and passengers.",
        "default_value": "",
        "icon_hint": "pa",
    },
    {
        "id": "betterment",
        "title": "Waiver of Betterment",
        "description": "Waives betterment deduction on new parts for vehicles up to 15 years.",
        "default_value": "Up to 15 Years",
        "icon_hint": "betterment",
    },
    {
        "id": "srcc",
        "title": "Strike, Riot & Civil Commotion",
        "description": "Covers physical loss or damage caused by strikes, riots or public unrest.",
        "default_value": "",
        "icon_hint": "srcc",
    },
    {
        "id": "respray",
        "title": "Vehicle Respray Cover",
        "description": "Reimburses full exterior vehicle spray painting up to RM1,000 after repairs.",
        "default_value": "RM 1,000.00",
        "icon_hint": "respray",
    },
    {
        "id": "gas_conversion",
        "title": "Gas Conversion Kit Cover",
        "description": "Dedicated damage cover for installed NGV gas conversion tanks and kits.",
        "default_value": "",
        "icon_hint": "gas_conversion",
    },
    {
        "id": "cart",
        "title": "Compensation for Assessed Repair Time",
        "description": "Daily cash allowance during workshop repairs assessed by claims adjuster.",
        "default_value": "",
        "icon_hint": "cart",
    },
    {
        "id": "accessories",
        "title": "Vehicle Accessories Cover",
        "description": "Covers installed aftermarket accessories, dashcams, multimedia and rims.",
        "default_value": "",
        "icon_hint": "accessories",
    },
    {
        "id": "ncd_protector",
        "title": "NCD Protector",
        "description": "Protects No-Claim Discount entitlement against eligible fault claims.",
        "default_value": "",
        "icon_hint": "ncd",
    },
    {
        "id": "key_care",
        "title": "Key Care Replacement",
        "description": "Reimburses key and lock replacement up to RM1,000 following theft or loss.",
        "default_value": "RM 1,000.00",
        "icon_hint": "key_care",
    },
    {
        "id": "international_towing",
        "title": "International Towing Assistance",
        "description": "Up to 50km from Malaysia border.",
        "default_value": "50 km",
        "icon_hint": "international_towing",
    },
    {
        "id": "ev_wall_charger",
        "title": "EV Wall Charger Cover",
        "description": "Covers accidental damage, fire or theft of home EV wallbox charger.",
        "default_value": "",
        "icon_hint": "ev_charger",
    },
    {
        "id": "ev_out_of_charge",
        "title": "EV Battery Out Of Charge Towing",
        "description": "Emergency flatbed towing to nearest public EV charging station.",
        "default_value": "",
        "icon_hint": "ev_towing",
    },
    {
        "id": "ev_charger_liability",
        "title": "EV Charger Liability",
        "description": "Third-party injury and property liability from home EV charger.",
        "default_value": "",
        "icon_hint": "ev_liability",
    },
    {
        "id": "ehailing",
        "title": "Private Hire Car (E-Hailing)",
        "description": "Coverage while providing a legitimate E-Hailing Service.",
        "default_value": "",
        "icon_hint": "ehailing",
    },
    {
        "id": "non_fare_passenger",
        "title": "Legal Liability to Non-Fare Paying Passengers",
        "description": "Commercial Vehicle",
        "default_value": "",
        "icon_hint": "non_fare_passenger",
    },
    {
        "id": "third_party_working",
        "title": "Third Party Working Risk",
        "description": "Commercial Vehicle - Crane",
        "default_value": "",
        "icon_hint": "third_party_working",
    },
    {
        "id": "boom_damage",
        "title": "Accidental Damage to Boom",
        "description": "Commercial Vehicle - Crane",
        "default_value": "",
        "icon_hint": "boom_damage",
    },
    {
        "id": "overturning",
        "title": "Damage by Overturning",
        "description": "Commercial Vehicle - Crane",
        "default_value": "",
        "icon_hint": "overturning",
    },
]

FALLBACK_ICE_PERKS_CATALOG: list[dict[str, Any]] = [
    {
        "id": "child_seat",
        "title": "Child Car Safety Seat",
        "description": "Reimburses replacement of damaged child car safety seat up to RM500.",
        "default_value": "RM 500.00",
        "icon_hint": "child_seat",
    },
    {
        "id": "inconvenience_allowance",
        "title": "Inconvenience Allowance",
        "description": "Lump sum cash payout for travel inconvenience during vehicle repairs.",
        "default_value": "RM 500.00",
        "icon_hint": "allowance",
    },
    {
        "id": "car_replacement",
        "title": "Courtesy Car Replacement",
        "description": "Temporary courtesy car replacement while vehicle is under workshop repair.",
        "default_value": "Up to 14 Days",
        "icon_hint": "car_replacement",
    },
    {
        "id": "rim_tyre",
        "title": "Rim & Tyre Protection",
        "description": "Covers accidental tyre puncture or alloy wheel rim kerb damage.",
        "default_value": "RM 1,000.00",
        "icon_hint": "rim_tyre",
    },
    {
        "id": "flood_allowance",
        "title": "Flood Relief Allowance",
        "description": "Immediate cash relief payout upon flood damage claims.",
        "default_value": "RM 1,000.00",
        "icon_hint": "flood",
    },
    {
        "id": "airbag_replacement",
        "title": "Airbag Replacement Cover",
        "description": "Reimburses genuine OEM airbag modules following collision deployment.",
        "default_value": "Up to Sum Insured",
        "icon_hint": "airbag",
    },
    {
        "id": "ambulance_fees",
        "title": "Emergency Ambulance Service",
        "description": "Reimbursement of emergency ambulance transport charges up to RM500.",
        "default_value": "RM 500.00",
        "icon_hint": "pa",
    },
    {
        "id": "legal_defense",
        "title": "Legal Representation & Defense",
        "description": "Covers court legal defense counsel costs up to RM2,000.",
        "default_value": "RM 2,000.00",
        "icon_hint": "legal_defense",
    },
]

CANONICAL_BY_ID: dict[str, dict[str, Any]] = {c["id"]: c for c in CANONICAL_24_CATALOG}

_SUPPRESSED_VALUES = {
    "",
    "0",
    "0.0",
    "0.00",
    "rm 0",
    "rm 0.0",
    "rm 0.00",
    "rm0",
    "rm0.00",
    "included",
    "included standard cover",
    "foc",
    "as quoted",
    "selected",
    "yes",
    "true",
    "standard",
    "optional",
    "none",
    "null",
    "nil",
    "-",
    "—",
}

_EXACT_ID_ALIASES: dict[str, str] = {
    "windscreen": "windscreen",
    "windscreen_coverage": "windscreen",
    "windscreen_protection": "windscreen",
    "towing": "towing",
    "unlimited_towing": "towing",
    "unlimited_towing_distance": "towing",
    "llop": "llop",
    "legal_liability_of_passengers": "llop",
    "legal_liability_of_passengers_llop": "llop",
    "llp": "llp",
    "lltp": "llp",
    "legal_liability_to_passengers": "llp",
    "legal_liability_to_passengers_lltp": "llp",
    "special_perils": "special_perils",
    "flood_special_perils": "special_perils",
    "flood_and_special_perils": "special_perils",
    "betterment": "betterment",
    "betterment_protection": "betterment",
    "betterment_waiver": "betterment",
    "waiver_of_betterment": "betterment",
    "all_driver": "all_drivers",
    "all_drivers": "all_drivers",
    "all_drivers_excess_waiver": "all_drivers",
    "srcc": "srcc",
    "strike_riot_civil_commotion": "srcc",
    "respray": "respray",
    "repaint_spray_paint": "respray",
    "vehicle_respray_cover": "respray",
    "car_spray_repainting": "respray",
    "gas_conversion": "gas_conversion",
    "gas_conversion_kit": "gas_conversion",
    "gas_conversion_kit_cover": "gas_conversion",
    "cart": "cart",
    "repair_allowance": "cart",
    "compensation_for_assessed_repair_time": "cart",
    "accessories": "accessories",
    "vehicle_accessories": "accessories",
    "vehicle_accessories_cover": "accessories",
    "vehicle_accessories_protection": "accessories",
    "ncd_protector": "ncd_protector",
    "ncd_relief": "ncd_protector",
    "pa": "pa",
    "personal_accident": "pa",
    "motor_pa_plus": "pa",
    "driver_passenger_pa": "pa",
    "driver_and_passenger_pa": "pa",
    "driver_passenger_personal_accident": "pa",
    "key_care": "key_care",
    "key_replacement": "key_care",
    "key_care_replacement": "key_care",
    "key_care_protection": "key_care",
    "international_towing": "international_towing",
    "international_towing_assistance": "international_towing",
    "ev_wall_charger": "ev_wall_charger",
    "ev_wall_charger_cover": "ev_wall_charger",
    "ev_out_of_charge": "ev_out_of_charge",
    "ev_battery_towing": "ev_out_of_charge",
    "ev_battery_depletion_towing": "ev_out_of_charge",
    "ev_battery_out_of_charge_towing": "ev_out_of_charge",
    "ev_charger_liability": "ev_charger_liability",
    "ev_home_charger_liability": "ev_charger_liability",
    "ehailing": "ehailing",
    "e_hailing": "ehailing",
    "e_hailing_cover": "ehailing",
    "e_hailing_extension": "ehailing",
    "private_hire_car_e_hailing": "ehailing",
    "non_fare_passenger": "non_fare_passenger",
    "legal_liability_to_non_fare_paying_passenger": "non_fare_passenger",
    "third_party_working": "third_party_working",
    "third_party_working_risk": "third_party_working",
    "boom_damage": "boom_damage",
    "accidental_damage_to_boom": "boom_damage",
    "overturning": "overturning",
    "damage_by_overturning": "overturning",
}


def _normalize_benefit_code(name_or_id: str) -> str:
    s = (name_or_id or "").lower().strip()
    s = re.sub(r"[^a-z0-9]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def format_addon_value(raw_val: Any, val_override: Any = None) -> str:
    """Normalizes coverage limits for compact card pills, enforcing super-short 2-4 words max."""
    is_betterment_ctx = False
    if val_override is not None:
        if "betterment" in str(raw_val).lower():
            is_betterment_ctx = True
        actual_val = val_override
    else:
        actual_val = raw_val

    if actual_val is None:
        return "Up to 15 Years" if is_betterment_ctx else ""
    s = re.sub(r"\s+", " ", str(actual_val)).strip()
    if not s:
        return "Up to 15 Years" if is_betterment_ctx else ""
    low = s.lower().rstrip(" .")
    if low in _SUPPRESSED_VALUES:
        return "Up to 15 Years" if is_betterment_ctx else ""

    # 0. Betterment: Never display an RM monetary amount. Normalize to vehicle age limit or "Betterment Waived".
    if is_betterment_ctx or "betterment" in low:
        if re.match(r"(?i)^\s*rm\b", s):
            return "Up to 15 Years"
        m_bet = re.search(r"(?:up to\s+)?(\d+\s*(?:years?|yrs?))", s, re.IGNORECASE)
        if m_bet:
            return f"Up to {m_bet.group(1).title()}"
        return "Betterment Waived"

    # 1. Exact RM amount formatting: "RM 1000", "RM 1,000.00" -> "RM 1,000.00"
    rm_match = re.fullmatch(r"(?i)rm\s*([0-9][0-9,]*(?:\.[0-9]+)?)", s)
    if rm_match:
        try:
            num = float(rm_match.group(1).replace(",", ""))
            if num <= 0:
                return ""
            return f"RM {num:,.2f}"
        except Exception:
            return s

    # 2. Pure numeric coverage limit (e.g. "1000.0", "350000.0") -> "RM 1,000.00"
    if re.fullmatch(r"[0-9][0-9,]*(?:\.[0-9]+)?", s):
        try:
            num = float(s.replace(",", ""))
            if num <= 0:
                return ""
            return f"RM {num:,.2f}"
        except Exception:
            return s

    # 3. Betterment: Keep super short (e.g. "Up to 10 Years", "Betterment Waived")
    if "betterment" in low or "up to " in low:
        m = re.search(r"up to\s+(\d+\s*(?:years?|yrs?))", s, re.IGNORECASE)
        if m:
            return f"Up to {m.group(1).title()}"
        if "waiv" in low:
            return "Betterment Waived"

    # 4. Excess Waiver: e.g. "Compulsory RM400 excess waived" -> "RM 400.00 Waived"
    if "excess" in low:
        m = re.search(r"rm\s*([0-9][0-9,]*(?:\.[0-9]+)?)", s, re.IGNORECASE)
        if m:
            try:
                num = float(m.group(1).replace(",", ""))
                return f"RM {num:,.2f} Waived"
            except Exception:
                pass
        if "waiv" in low:
            return "Excess Waived"

    # 5. Personal Accident (PA): e.g. "RM 10,000 per person" -> "RM 10,000 / pax"
    if "per person" in low or "pax" in low:
        m = re.search(r"rm\s*([0-9][0-9,]*(?:\.[0-9]+)?)", s, re.IGNORECASE)
        if m:
            try:
                num = float(m.group(1).replace(",", ""))
                return f"RM {num:,.2f} / pax"
            except Exception:
                pass

    # 6. CART / Repair Time: e.g. "14 Days @ RM 100/day" -> "14 Days @ RM100"
    m_cart = re.search(r"(\d+\s*days?)\s*@\s*rm\s*(\d+)", s, re.IGNORECASE)
    if m_cart:
        return f"{m_cart.group(1).title()} @ RM{m_cart.group(2)}"

    # 7. Special Perils: e.g. "Full Sum Insured Coverage" -> "Full Sum Insured"
    if "peril" in low or "flood" in low:
        if "sum insured" in low or "full" in low:
            return "Full Sum Insured"

    # 8. Distance / Towing: e.g. "Unlimited Distance" -> "Unlimited"
    if "unlimited" in low:
        return "Unlimited"
    m_km = re.search(r"(\d+)\s*km", s, re.IGNORECASE)
    if m_km:
        return f"{m_km.group(1)} km"

    # 9. Embedded RM Extraction from verbose sentences:
    # e.g. "Covers wall charger damage up to RM 12,000.00" -> "RM 12,000.00"
    m_rm = re.search(r"(?i)\brm\s*([0-9][0-9,]*(?:\.[0-9]+)?)\b", s)
    if m_rm:
        try:
            num = float(m_rm.group(1).replace(",", ""))
            if num > 0:
                return f"RM {num:,.2f}"
        except Exception:
            pass

    # 10. Reject unparsed multi-word prose sentences instead of slicing mid-sentence fragments
    if len(s.split()) > 3 or len(s) > 28:
        return ""

    return s


def _is_basic_emergency_towing(title: str, desc: str, val: str) -> bool:
    combined = f"{title} {desc} {val}".lower()
    if "unlimited" in combined or "international" in combined or "ev battery" in combined or "out of charge" in combined:
        return False
    return "emergency towing" in title.lower() or ("roadside assistance" in title.lower() and "unlimited" not in combined)


def _match_catalog_item(item: dict[str, Any]) -> dict[str, Any] | None:
    target_title = str(item.get("title") or item.get("label") or "").strip()
    target_title_l = target_title.lower()
    target_desc_l = str(item.get("description") or "").lower()
    target_val_l = str(item.get("value") or "").lower()

    # Keep insurer basic RM200 emergency towing strictly in Free Added Coverage, not Unlimited Towing slot.
    if _is_basic_emergency_towing(target_title_l, target_desc_l, target_val_l):
        return None

    candidate_codes = [
        _normalize_benefit_code(str(item.get("id") or "")),
        _normalize_benefit_code(str(item.get("concept_key") or "")),
        _normalize_benefit_code(str(item.get("code") or "")),
        _normalize_benefit_code(target_title),
    ]
    raw_ck = str(item.get("card_key") or "")
    if raw_ck and ":" not in raw_ck:
        candidate_codes.append(_normalize_benefit_code(raw_ck))

    for code in candidate_codes:
        if not code:
            continue
        if code in _EXACT_ID_ALIASES:
            mapped_id = _EXACT_ID_ALIASES[code]
            if mapped_id == "towing" and _is_basic_emergency_towing(target_title_l, target_desc_l, target_val_l):
                return None
            return CANONICAL_BY_ID.get(mapped_id)
        if code in CANONICAL_BY_ID:
            return CANONICAL_BY_ID[code]

    words = set(_normalize_benefit_code(target_title_l).split("_"))

    if "windscreen" in target_title_l:
        return CANONICAL_BY_ID["windscreen"]
    if "towing" in target_title_l and ("unlimited" in target_title_l or "unlimited" in target_val_l or "unlimited" in target_desc_l):
        return CANONICAL_BY_ID["towing"]
    if "towing" in target_title_l and "international" in target_title_l:
        return CANONICAL_BY_ID["international_towing"]
    if "towing" in target_title_l and ("ev" in words or "battery" in target_title_l or "out of charge" in target_title_l or "depletion" in target_title_l):
        return CANONICAL_BY_ID["ev_out_of_charge"]
    if "non" in words and "fare" in words:
        return CANONICAL_BY_ID["non_fare_passenger"]
    if "passengers" in target_title_l and ("of" in words or "llop" in words):
        return CANONICAL_BY_ID["llop"]
    if "passengers" in target_title_l and ("to" in words or "llp" in words or "lltp" in words):
        return CANONICAL_BY_ID["llp"]
    if "special peril" in target_title_l or "flood & special" in target_title_l or "flood and special" in target_title_l:
        return CANONICAL_BY_ID["special_perils"]
    if "betterment" in target_title_l:
        return CANONICAL_BY_ID["betterment"]
    if "all driver" in target_title_l:
        return CANONICAL_BY_ID["all_drivers"]
    if "strike" in target_title_l or "riot" in target_title_l or "srcc" in words:
        return CANONICAL_BY_ID["srcc"]
    if "respray" in target_title_l or "spray paint" in target_title_l or "repaint" in target_title_l:
        return CANONICAL_BY_ID["respray"]
    if "gas" in words and "conversion" in target_title_l:
        return CANONICAL_BY_ID["gas_conversion"]
    if "cart" in words or "assessed repair" in target_title_l or "repair allowance" in target_title_l or "compensation repair" in target_title_l:
        return CANONICAL_BY_ID["cart"]
    if "accessories" in target_title_l:
        return CANONICAL_BY_ID["accessories"]
    if "ncd" in words and ("protector" in target_title_l or "relief" in target_title_l):
        return CANONICAL_BY_ID["ncd_protector"]
    if "personal accident" in target_title_l or "driver passenger" in target_title_l or "driver & passenger pa" in target_title_l or "motor pa" in target_title_l:
        return CANONICAL_BY_ID["pa"]
    if "key" in words and ("care" in words or "replacement" in words):
        return CANONICAL_BY_ID["key_care"]
    if "charger" in target_title_l and "liability" in target_title_l:
        return CANONICAL_BY_ID["ev_charger_liability"]
    if "wall" in target_title_l and "charger" in target_title_l:
        return CANONICAL_BY_ID["ev_wall_charger"]
    if "out of charge" in target_title_l or "battery depletion" in target_title_l or "ev battery" in target_title_l:
        return CANONICAL_BY_ID["ev_out_of_charge"]
    if "e-hailing" in target_title_l or "ehailing" in target_title_l or "e hailing" in target_title_l or "private hire" in target_title_l:
        return CANONICAL_BY_ID["ehailing"]
    if "boom" in words:
        return CANONICAL_BY_ID["boom_damage"]
    if "overturning" in words:
        return CANONICAL_BY_ID["overturning"]
    if "working risk" in target_title_l:
        return CANONICAL_BY_ID["third_party_working"]

    return None


def _infer_icon_hint(item: dict[str, Any], matched_cat: dict[str, Any] | None) -> str:
    if item.get("icon_hint") and item["icon_hint"] != "generic":
        return str(item["icon_hint"])
    if matched_cat and matched_cat.get("icon_hint"):
        return matched_cat["icon_hint"]
    txt = f"{item.get('id') or ''} {item.get('concept_key') or ''} {item.get('title') or item.get('label') or ''}".lower()
    if "ncd" in txt or "cashback" in txt:
        return "ncd"
    if "detail" in txt or "clean" in txt or "respray" in txt or "paint" in txt:
        return "respray"
    if "out of pocket" in txt or "cart" in txt or "allowance" in txt or "courtesy" in txt:
        return "cart"
    if "agreed value" in txt or "market value" in txt or "settlement" in txt:
        return "ncd"
    if "child" in txt or "seat" in txt or "pa" in re.split(r"[^a-z0-9]", txt):
        return "pa"
    if "tyre" in txt or "tire" in txt or "rim" in txt or "accessor" in txt:
        return "accessories"
    return "generic"


def _positive_price(item: dict[str, Any]) -> bool:
    price = item.get("price") or item.get("cost_value")
    if price is None:
        return False
    val = price.get("amount") if isinstance(price, dict) else price
    if val is None and isinstance(price, dict):
        val = price.get("value")
    if val is None:
        return False
    try:
        return float(re.sub(r"[^0-9.]", "", str(val)) or "0") > 0
    except Exception:
        return False


def is_item_selected(
    item: dict[str, Any],
    selected_ids: set[str] | None = None,
    *,
    source_kind: str = "generic",
    matched_cat_id: str | None = None,
) -> bool:
    """Determines whether an add-on card should appear ticked (green check) and floated to top.

    - `source_kind == 'available'`: items in available_addons are UNSELECTED by default even
      when they carry formula catalog `is_extra=True`, `cost_status='paid'`, or `price > 0`.
      Only explicit `selected` / `is_selected` flags or membership in `selected_ids` selects them.
    - `source_kind == 'active'`: items from `current_benefits` on the quotation draft are selected
      if paid/extra/selected/explicitly ticked, OR if they have a persisted `selection_id` and match
      an upgrade/endorsement slot in `CANONICAL_24_CATALOG` (e.g. insurer-included Unlimited Towing).
    - `source_kind == 'generic'`: direct calls to `sort_unified_addons(items)`.
    """
    if selected_ids:
        candidates = [
            str(item.get("id") or ""),
            str(item.get("code") or ""),
            str(item.get("card_key") or ""),
            str(item.get("selection_id") or ""),
            str(item.get("concept_key") or ""),
            str(item.get("title") or item.get("label") or "").strip(),
        ]
        if matched_cat_id:
            candidates.append(matched_cat_id)
        for cand in candidates:
            if not cand:
                continue
            if cand in selected_ids or _normalize_benefit_code(cand) in selected_ids:
                return True

    if item.get("selected") is True or item.get("is_selected") is True:
        return True

    if item.get("selected") is False or item.get("is_selected") is False:
        return False

    if source_kind == "available":
        return False

    if item.get("is_extra") or item.get("cost_status") == "paid" or _positive_price(item):
        return True

    if source_kind == "active":
        # FOC / included perks stay in Free Added Coverage, not marked as purchased add-on riders
        if item.get("cost_status") in ("included", "foc") and not item.get("is_extra") and not _positive_price(item):
            return False
        if matched_cat_id and item.get("is_extra") is True:
            return True
        if matched_cat_id and item.get("selection_id") and (item.get("is_extra") or item.get("cost_status") == "paid" or _positive_price(item)):
            return True

    return False


def detect_towing_upgrade(
    active_benefits: list[dict[str, Any]] | None,
    insurer_name: str = "",
) -> dict[str, str] | None:
    """Detect if an active paid rider upgrades towing entitlement based on Malaysian Motor Towing Reference."""
    for raw in active_benefits or []:
        if not (
            raw.get("is_extra")
            or raw.get("cost_status") == "paid"
            or raw.get("is_selected") is True
            or raw.get("selected") is True
            or _positive_price(raw)
        ):
            continue
        title = str(raw.get("title") or raw.get("label") or "").lower()
        concept = str(raw.get("concept_key") or "").lower()
        val_str = str(raw.get("value") or "").lower()
        desc_str = str(raw.get("description") or "").lower()
        off_key = str(raw.get("offering_key") or raw.get("card_key") or "").lower()
        tv = raw.get("typed_value")
        tv_str = ""
        if isinstance(tv, dict):
            tv_str = f"{tv.get('display_text') or ''} {tv.get('value') or ''} {tv.get('plan_key') or ''} {tv.get('enum_key') or ''}".lower()
        elif tv is not None:
            tv_str = str(tv).lower()
        combined = f"{title} {concept} {val_str} {desc_str} {off_key} {tv_str}"

        # 1. Etiqa + OTO 360
        if "oto 360" in combined or "oto_360" in combined or "oto-360" in combined or "oto360" in combined:
            return {
                "title": "Unlimited Towing Assistance (Unlimited - Driver Plan 1)",
                "limit": "Unlimited - Driver Plan 1",
                "description": "24/7 unlimited breakdown & accidental towing assistance (Driver Plan 1). Upgraded via OTO 360.",
                "rider": "OTO 360",
            }

        # 2. Takaful Malaysia / STMB + Motor PA Plus
        if any(k in combined for k in ("motor pa plus", "motor-pa-plus", "motor_pa_plus", "motor pa plan", "pa plus", "pa-plus")):
            if "plan 4" in combined or "plan-4" in combined or "p4" in combined:
                return {
                    "title": "Unlimited Towing Assistance",
                    "limit": "Unlimited",
                    "description": "24/7 unlimited towing assistance nationwide. Upgraded via Motor PA Plus - Plan 4.",
                    "rider": "Motor PA Plus - Plan 4",
                }
            if "plan 3" in combined or "plan-3" in combined or "p3" in combined:
                return {
                    "title": "Extended Towing Assistance (300 km)",
                    "limit": "300 km",
                    "description": "24/7 extended towing assistance up to 300 km. Upgraded via Motor PA Plus - Plan 3.",
                    "rider": "Motor PA Plus - Plan 3",
                }
            if "plan 2" in combined or "plan-2" in combined or "p2" in combined:
                return {
                    "title": "Extended Towing Assistance (200 km)",
                    "limit": "200 km",
                    "description": "24/7 extended towing assistance up to 200 km. Upgraded via Motor PA Plus - Plan 2.",
                    "rider": "Motor PA Plus - Plan 2",
                }
            if "plan 1" in combined or "plan-1" in combined or "p1" in combined:
                return {
                    "title": "Extended Towing Assistance (100 km)",
                    "limit": "100 km",
                    "description": "24/7 extended towing assistance up to 100 km. Upgraded via Motor PA Plus - Plan 1.",
                    "rider": "Motor PA Plus - Plan 1",
                }

        # 3. QBE + Driver & Passenger Protector (N4 - Unlimited Auto Assistance)
        if any(
            k in combined
            for k in (
                "driver passenger protector",
                "driver-passenger-protector",
                "driver & passenger protector",
                "driver and passenger protector",
                "unlimited auto assistance",
                "dpp",
                "n4",
            )
        ):
            return {
                "title": "Unlimited Towing Assistance (Unlimited - Plan 1)",
                "limit": "Unlimited - Plan 1",
                "description": "24/7 unlimited auto towing assistance (Plan 1). Upgraded via Driver & Passenger Protector (N4).",
                "rider": "Driver & Passenger Protector (N4)",
            }

        # 4. Lonpac + E-Assist Smart Driver (Plan 1 -> RM 600; Plan 2 / EV Plan -> Unlimited)
        if any(k in combined for k in ("e-assist", "smart driver", "smart-driver-pa")):
            if any(k in combined for k in ("plan 2", "plan-2", "plan b", "ev plan", "ev-plan", "ev")):
                return {
                    "title": "Unlimited Towing Assistance",
                    "limit": "Unlimited",
                    "description": "24/7 unlimited breakdown towing nationwide. Upgraded via E-Assist Smart Driver (Plan 2 / EV Plan).",
                    "rider": "E-Assist Smart Driver - Plan 2 / EV Plan",
                }
            if any(k in combined for k in ("plan 1", "plan-1", "plan a")):
                return {
                    "title": "Extended Towing Assistance (RM 600)",
                    "limit": "RM 600",
                    "description": "24/7 breakdown towing coverage up to RM 600. Upgraded via E-Assist Smart Driver (Plan 1).",
                    "rider": "E-Assist Smart Driver - Plan 1",
                }

        # 5. Tune Protect + Motor Easy Bundle / AutoBuddy / Motor Shield
        if any(
            k in combined
            for k in (
                "motor easy",
                "motor-easy",
                "autobuddy",
                "auto-buddy",
                "motor shield",
                "motorshield",
            )
        ):
            return {
                "title": "Unlimited Towing Assistance",
                "limit": "Unlimited",
                "description": "24/7 unlimited towing assistance nationwide. Upgraded via Motor Easy Bundle / AutoBuddy / Motor Shield.",
                "rider": "Motor Easy Bundle / AutoBuddy / Motor Shield",
            }

        # 6. AmAssurance + Breakdown Towing Assistance
        if "breakdown towing" in combined:
            return {
                "title": "Extended Towing Assistance (150 km)",
                "limit": "150 km",
                "description": "24/7 breakdown towing assistance up to 150 km. Upgraded via Breakdown Towing Assistance.",
                "rider": "Breakdown Towing Assistance",
            }

    return None


COMMERCIAL_EXCLUDED_MATRIX_IDS = frozenset({
    "towing",
    "international_towing",
    "ev_wall_charger",
    "ev_out_of_charge",
    "ev_charger_liability",
    "ehailing",
    "key_care",
    "child_seat",
})

PRIVATE_CAR_EXCLUDED_MATRIX_IDS = frozenset({
    "non_fare_passenger",
    "third_party_working",
    "boom_damage",
    "overturning",
})

ICE_EXCLUDED_MATRIX_IDS = frozenset({
    "ev_wall_charger",
    "ev_out_of_charge",
    "ev_charger_liability",
})

COMMERCIAL_KEYWORDS = (
    "lorry", "truck", "hino", "fuso", "canter", "rigid", "trailer", "tipper",
    "prime mover", "c permit", "a permit", "haulage", "commercial", "isuzu npr",
    "isuzu nqr", "isuzu elf", "ud trucks", "scania", "sinotruk", "daihatsu delta",
    "toyota dyna", "goods vehicle",
)


def is_commercial_vehicle(
    vehicle_type: str = "",
    car_model: str = "",
    fields: dict[str, Any] | None = None,
) -> bool:
    """Returns True if the vehicle is classified as a commercial vehicle, lorry, truck, trailer, or haulage."""
    raw = f"{vehicle_type or ''} {car_model or ''}".lower()
    if fields:
        raw += f" {fields.get('vehicle_type', '')} {fields.get('car_model', '')} {fields.get('capacity', '')}".lower()
    return any(k in raw for k in COMMERCIAL_KEYWORDS) or "kg" in raw or "bdm" in raw


def is_ev_vehicle(
    vehicle_type: str = "",
    car_model: str = "",
    fields: dict[str, Any] | None = None,
) -> bool:
    """Returns True if the vehicle is classified as an Electric Vehicle (EV / BEV / ZEV)."""
    raw = f"{vehicle_type or ''} {car_model or ''}".lower()
    if fields:
        raw += f" {fields.get('vehicle_type', '')} {fields.get('powertrain', '')} {fields.get('engine_cc', '')}".lower()
    return "ev" in raw or "electric" in raw or "zev" in raw or "bev" in raw or "kw" in raw


def extract_free_coverage_items(
    active_benefits: list[dict[str, Any]] | None,
    insurer_name: str = "",
    *,
    limit: int = 6,
    vehicle_type: str = "",
    car_model: str = "",
    fields: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """Extracts Top-Right 'Free Added Coverage' cards with strict 1:1 Box 1 parity.

    Only complimentary benefits actually present in Box 1 (`active_benefits`) are returned,
    in exact Box 1 order. Never fabricates phantom RM 200 towing or hardcoded fallback perks,
    and never drops Box 1 items whose concept happens to overlap the bottom 24-card catalog.
    When Box 1 includes a base Towing card on Private Cars without a manual override, eligible
    selected riders (e.g. OTO 360 / Motor PA Plus) upgrade that Box 1 towing card in-place.
    """
    seen_titles: set[str] = set()
    items: list[dict[str, str]] = []

    is_comm = is_commercial_vehicle(vehicle_type, car_model, fields)
    cov_raw = fields.get("coverage_type") if isinstance(fields, dict) else None
    cov_val = str(cov_raw.get("value") if isinstance(cov_raw, dict) else cov_raw or "").strip().lower()
    is_non_comp = (
        "third party" in cov_val
        or "tpft" in cov_val
        or cov_val in {"tp", "tpo", "act"}
    ) and "comprehensive" not in cov_val

    def _is_base_towing_card(raw: dict[str, Any]) -> bool:
        if raw.get("is_extra") or raw.get("cost_status") == "paid" or _positive_price(raw):
            return False
        ckey = str(raw.get("concept_key") or "").strip().lower()
        if ckey == "towing":
            return True
        if ckey == "ev-battery-depletion-towing":
            return False
        t_norm = _normalize_benefit_code(str(raw.get("title") or raw.get("label") or ""))
        return "towing" in t_norm and "battery" not in t_norm

    def _is_coverage_hidden_or_cleared(raw: dict[str, Any]) -> bool:
        if raw.get("hide_coverage") is True or raw.get("show_coverage") is False:
            return True
        for k in ("typed_value_override", "typed_value"):
            tv = raw.get(k)
            if isinstance(tv, dict):
                if tv.get("hide_limit") is True or tv.get("hideCoverage") is True:
                    return True
                if "display_text" in tv and str(tv.get("display_text") or "").strip() == "" and tv.get("value") in (None, ""):
                    return True
        return False

    def _strip_trailing_metric_parens(title_str: str) -> str:
        return re.sub(
            r"\s*\((?:(?:RM|MYR)\s*[\d,]+(?:\.\d{1,2})?|\d+\s*km|Unlimited[^)]*)\)\s*$",
            "",
            (title_str or "").strip(),
            flags=re.IGNORECASE,
        ).strip()

    def _format_towing_title(base_label: str, limit_val: str, *, is_manual_val: bool = False) -> str:
        clean_title = (base_label or "Emergency Towing Assistance").strip()
        raw_lim = (limit_val or "").strip()
        if is_manual_val and raw_lim:
            clean_title = _strip_trailing_metric_parens(clean_title)
        # Extract only a concise towing metric (e.g. '200 km', 'RM 400', 'Unlimited'); never wrap prose sentences in parens
        clean_val = ""
        if raw_lim:
            if is_manual_val and len(raw_lim) <= 40:
                clean_val = raw_lim
            elif re.fullmatch(r"(?:Unlimited(?:\s*-\s*[A-Za-z0-9 ]+)?|RM\s*[\d,]+(?:\.\d{1,2})?|\d+\s*km)", raw_lim, re.IGNORECASE):
                clean_val = raw_lim
            elif "unlimited" in raw_lim.lower() and len(raw_lim.split()) <= 4:
                clean_val = "Unlimited"
            else:
                m_km = re.search(r"\b(\d+\s*km)\b", raw_lim, re.IGNORECASE)
                m_rm = re.search(r"\b(RM\s*[\d,]+(?:\.\d{1,2})?)\b", raw_lim, re.IGNORECASE)
                if m_km:
                    clean_val = m_km.group(1).lower()
                elif m_rm:
                    clean_val = m_rm.group(1).upper()
        if not clean_val:
            return clean_title
        val_compact = re.sub(r"\.00\b", "", clean_val).lower()
        title_low = clean_title.lower()
        if clean_val.lower() in title_low or (val_compact and val_compact in title_low):
            return clean_title
        if re.search(r"\([^)]+\)$", clean_title):
            return clean_title
        return f"{clean_title} ({clean_val})"

    for raw in active_benefits or []:
        if raw.get("is_extra") or raw.get("cost_status") == "paid" or _positive_price(raw):
            continue

        is_hide_cov = _is_coverage_hidden_or_cleared(raw)
        has_manual_val_ovr = bool(raw.get("has_manual_value_override"))

        if _is_base_towing_card(raw):
            c_title = str(raw.get("label") or raw.get("title") or "Emergency Towing Assistance").strip()
            c_val = "" if is_hide_cov else str(raw.get("value") or raw.get("display_value") or raw.get("coverage_limit") or "").strip()
            if is_hide_cov:
                c_title = _strip_trailing_metric_parens(c_title)
            c_desc = str(raw.get("description") or raw.get("short_description") or "").strip()
            has_manual_override = bool(
                raw.get("has_manual_override")
                or has_manual_val_ovr
                or is_hide_cov
                or raw.get("is_manual")
                or str(raw.get("source") or "").lower() == "manual"
                or raw.get("label_override")
            )
            towing_upgrade = None
            if not is_comm and not is_non_comp and not has_manual_override:
                card_already_upgraded = (
                    "unlimited" in c_val.lower()
                    or "unlimited" in c_title.lower()
                    or "extended" in c_title.lower()
                )
                if not card_already_upgraded:
                    towing_upgrade = detect_towing_upgrade(active_benefits, insurer_name)

            if towing_upgrade:
                out_title = towing_upgrade["title"]
                out_desc = towing_upgrade["description"]
            else:
                out_title = _format_towing_title(c_title, c_val, is_manual_val=has_manual_val_ovr)
                out_desc = c_desc or "24/7 accidental towing service to nearest panel workshop or approved repairer."

            norm_out = _normalize_benefit_code(out_title)
            if norm_out not in seen_titles and "emergency_towing_assistance" not in seen_titles:
                seen_titles.add(norm_out)
                seen_titles.add("emergency_towing_assistance")
                seen_titles.add("unlimited_towing_assistance")
                items.append({"title": out_title, "description": out_desc})
            if len(items) >= limit:
                break
            continue

        title = str(raw.get("title") or raw.get("label") or "").strip()
        if not title:
            continue
        if is_hide_cov:
            title = _strip_trailing_metric_parens(title)
        elif has_manual_val_ovr:
            c_val = str(raw.get("value") or "").strip()
            if c_val and len(c_val) <= 40 and c_val.lower() not in title.lower():
                title = f"{_strip_trailing_metric_parens(title)} ({c_val})"
        norm_title = _normalize_benefit_code(title)
        if norm_title in seen_titles:
            continue
        seen_titles.add(norm_title)
        desc = str(raw.get("description") or raw.get("short_description") or "").strip()
        items.append({"title": title, "description": desc})
        if len(items) >= limit:
            break

    return items[:limit]


def sort_unified_addons(
    items: list[dict[str, Any]],
    selected_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Floats all selected/ticked benefits to the front, preserving their order,
    followed by unselected catalog benefits in their normal initial order.
    Re-assigns sequential 2-digit serial numbers ('01', '02'...).
    """
    selected: list[dict[str, Any]] = []
    unselected: list[dict[str, Any]] = []

    for item in items:
        sel = is_item_selected(item, selected_ids, source_kind="generic")
        title = item.get("title") or item.get("label") or "Benefit"
        card = dict(item)
        card["title"] = title
        card["is_selected"] = sel
        if "value" in card:
            formatted_v = format_addon_value(card.get("value"))
            card["value"] = formatted_v
        if sel:
            selected.append(card)
        else:
            unselected.append(card)

    combined = selected + unselected
    for rank, card in enumerate(combined, start=1):
        card["serial_number"] = f"{rank:02d}"

    return combined


def build_unified_matrix_cards(
    active_benefits: list[dict[str, Any]] | None = None,
    available_addons: list[dict[str, Any]] | None = None,
    selected_ids: set[str] | None = None,
    *,
    fill_to_slots: int = 0,
    max_slots: int = 24,
    insurer_name: str = "",
    vehicle_type: str = "",
    car_model: str = "",
    fields: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Builds the unified Add-On Upgrades ++ card matrix for Design 2.

    1. Evaluates `active_benefits` (marking paid/selected items or canonical included matrix items).
       Pure non-matrix FOC insurer perks (e.g. Legal Defense Costs, basic Emergency Towing)
       stay in the Free Added Coverage box and are not injected into Add-On Upgrades ++.
    2. Evaluates `available_addons` as UNSELECTED catalog choices (ignoring formula price metadata
       unless explicitly selected / in `selected_ids`).
    3. Fills up to `fill_to_slots` from CANONICAL_24_CATALOG, filtering out irrelevant items:
       - For Commercial Vehicles (lorries/trucks): towing and consumer EV/e-hailing are strictly excluded.
       - For Private Cars: heavy equipment crane/boom working risks are excluded.
    4. Floats selected cards to the front while preserving canonical ordering.
    """
    is_comm = is_commercial_vehicle(vehicle_type, car_model, fields)
    is_ev = is_ev_vehicle(vehicle_type, car_model, fields)
    if is_comm:
        excluded_ids = set(COMMERCIAL_EXCLUDED_MATRIX_IDS)
    elif not is_ev:
        excluded_ids = set(PRIVATE_CAR_EXCLUDED_MATRIX_IDS | ICE_EXCLUDED_MATRIX_IDS)
    else:
        excluded_ids = set(PRIVATE_CAR_EXCLUDED_MATRIX_IDS)

    canonical_overrides: dict[str, dict[str, Any]] = {}
    custom_cards: list[dict[str, Any]] = []
    seen_custom_ids: set[str] = set()
    ordered_active_ids: list[str] = []

    def _build_card_dict(item: dict[str, Any], cat_id: str, sel: bool, matched_cat: dict[str, Any] | None) -> dict[str, Any]:
        raw_val = item.get("value")
        if raw_val in (None, ""):
            raw_val = item.get("coverage_limit")
        if raw_val in (None, "") and isinstance(item.get("typed_value"), dict):
            raw_val = item["typed_value"].get("display_text")
        if raw_val in (None, "") and isinstance(item.get("typed_value_override"), dict):
            raw_val = item["typed_value_override"].get("display_text")

        # Betterment protection: Never display an RM monetary amount for Waiver of Betterment
        is_betterment = cat_id == "betterment" or (matched_cat and matched_cat.get("id") == "betterment")
        if is_betterment:
            if re.match(r"(?i)^\s*rm\b", str(raw_val or "").strip()):
                raw_val = ""
            try:
                from app.services.marketing_comparison.company_rules import resolve_company_betterment_rule

                _, _, default_years = resolve_company_betterment_rule(company_name=insurer_name)
            except Exception:
                comp_l = (insurer_name or "").lower()
                default_years = (
                    "Up to 10 Years"
                    if ("qbe" in comp_l or any(k in comp_l for k in ("lonpac", "stmb", "takaful malaysia", "syarikat takaful")))
                    else "Up to 15 Years"
                )
            if not raw_val or raw_val in ("Up to 10 Years", "Up to 15 Years", "Standard"):
                formatted_val = default_years
            else:
                formatted_val = format_addon_value("betterment", raw_val) or default_years
        else:
            formatted_val = format_addon_value(raw_val)
            if not formatted_val and matched_cat:
                formatted_val = format_addon_value(matched_cat.get("default_value"))

        title_str = str(item.get("title") or item.get("label") or (matched_cat["title"] if matched_cat else cat_id.replace("_", " ").title()))

        # Check if coverage limit is explicitly hidden (Windscreen is strictly mandatory on Malaysian motor quotes)
        is_hide_cov = bool(
            item.get("hide_coverage")
            or item.get("show_coverage") is False
            or (isinstance(item.get("typed_value"), dict) and item["typed_value"].get("hide_limit") is True)
            or (isinstance(item.get("typed_value_override"), dict) and item["typed_value_override"].get("hide_limit") is True)
        )
        is_mandatory_cov = "windscreen" in cat_id.lower() or "windscreen" in title_str.lower()
        if is_hide_cov and not is_mandatory_cov:
            formatted_val = ""

        cost_status = (
            str(item.get("cost_status") or "paid")
            if sel
            else ("included" if item.get("cost_status") == "included" else "optional")
        )
        return {
            "id": cat_id,
            "code": cat_id,
            "title": title_str,
            "description": str(item.get("description") or item.get("short_description") or (matched_cat["description"] if matched_cat else "")),
            "value": formatted_val,
            "icon_hint": _infer_icon_hint(item, matched_cat),
            "is_selected": sel,
            "cost_status": cost_status,
            "price": item.get("price") or item.get("optional_price"),
            "concept_key": str(item.get("concept_key") or cat_id),
            "asset_id": item.get("asset_id") or (matched_cat.get("default_asset_id") if matched_cat else None),
        }

    def _push_item(item: dict[str, Any], source_kind: str) -> None:
        matched_cat = _match_catalog_item(item)
        sel = is_item_selected(
            item,
            selected_ids,
            source_kind=source_kind,
            matched_cat_id=matched_cat["id"] if matched_cat else None,
        )

        # Keep non-matrix unselected basic perks strictly inside "Free Added Coverage"
        if source_kind == "active" and not sel:
            return

        cat_id = (
            matched_cat["id"]
            if matched_cat
            else _normalize_benefit_code(str(item.get("concept_key") or item.get("id") or item.get("title") or item.get("label") or ""))
        )
        if not cat_id:
            return

        if matched_cat is not None:
            existing = canonical_overrides.get(cat_id)
            if existing is None:
                canonical_overrides[cat_id] = _build_card_dict(item, cat_id, sel, matched_cat)
                ordered_active_ids.append(cat_id)
            else:
                # Never overwrite a selected active card's status; only enrich missing price/value/description
                new_card = _build_card_dict(item, cat_id, sel, matched_cat)
                if not existing.get("value") and new_card.get("value"):
                    existing["value"] = new_card["value"]
                if not existing.get("price") and new_card.get("price"):
                    existing["price"] = new_card["price"]
                if not existing.get("description") and new_card.get("description"):
                    existing["description"] = new_card["description"]
                if not existing.get("asset_id") and new_card.get("asset_id"):
                    existing["asset_id"] = new_card["asset_id"]
                if sel and not existing.get("is_selected"):
                    existing["is_selected"] = True
                    existing["cost_status"] = new_card["cost_status"]
        else:
            if cat_id in seen_custom_ids:
                return
            seen_custom_ids.add(cat_id)
            custom_cards.append(_build_card_dict(item, cat_id, sel, None))

    for item in active_benefits or []:
        _push_item(item, "active")

    for item in available_addons or []:
        _push_item(item, "available")

    towing_upgraded = bool(detect_towing_upgrade(active_benefits))
    processed_cards: list[dict[str, Any]] = []
    seen_in_output: set[str] = set()

    # 1. Add provided canonical overrides (in canonical catalog sequence)
    for cat in CANONICAL_24_CATALOG:
        cat_id = cat["id"]
        if is_comm and cat_id in excluded_ids and not (cat_id in canonical_overrides and canonical_overrides[cat_id].get("is_selected")):
            continue
        if (
            cat_id == "towing"
            and (is_comm or towing_upgraded)
            and not (cat_id in canonical_overrides and canonical_overrides[cat_id].get("is_selected"))
        ):
            continue
        if cat_id in canonical_overrides:
            seen_in_output.add(cat_id)
            processed_cards.append(canonical_overrides[cat_id])

    # 2. Add active draft benefits matching other canonical slots
    for cat_id in ordered_active_ids:
        if cat_id not in seen_in_output and cat_id in canonical_overrides:
            if is_comm and cat_id in excluded_ids and not canonical_overrides[cat_id].get("is_selected"):
                continue
            seen_in_output.add(cat_id)
            processed_cards.append(canonical_overrides[cat_id])

    # 3. Add custom active benefits and available addons provided for this quote
    for custom in custom_cards:
        c_id = custom.get("id") or custom.get("concept_key")
        if c_id and c_id not in seen_in_output:
            if is_comm and any(k in str(c_id).lower() for k in ("towing", "roadside")):
                continue
            seen_in_output.add(c_id)
            processed_cards.append(custom)

    # 4. Fill remaining slots up to fill_to_slots from CANONICAL_24_CATALOG and FALLBACK_ICE_PERKS_CATALOG
    if fill_to_slots and fill_to_slots > 0:
        for cat in [*CANONICAL_24_CATALOG, *FALLBACK_ICE_PERKS_CATALOG]:
            if len(processed_cards) >= fill_to_slots:
                break
            cat_id = cat["id"]
            if cat_id in excluded_ids:
                continue
            if (
                cat_id == "towing"
                and (is_comm or (towing_upgraded and not (cat_id in canonical_overrides and canonical_overrides[cat_id].get("is_selected"))))
            ):
                continue
            if cat_id not in seen_in_output:
                seen_in_output.add(cat_id)
                fill_val = format_addon_value(cat.get("default_value"))
                if cat_id == "betterment":
                    try:
                        from app.services.marketing_comparison.company_rules import resolve_company_betterment_rule

                        _, _, fill_val = resolve_company_betterment_rule(company_name=insurer_name)
                    except Exception:
                        comp_l = (insurer_name or "").lower()
                        fill_val = (
                            "Up to 10 Years"
                            if ("qbe" in comp_l or any(k in comp_l for k in ("lonpac", "stmb", "takaful malaysia", "syarikat takaful")))
                            else "Up to 15 Years"
                        )
                processed_cards.append(
                    {
                        "id": cat["id"],
                        "code": cat["id"],
                        "title": cat["title"],
                        "description": cat["description"],
                        "value": fill_val,
                        "icon_hint": cat.get("icon_hint", "generic"),
                        "is_selected": False,
                        "cost_status": "optional",
                        "concept_key": cat["id"],
                    }
                )

    sorted_cards = sort_unified_addons(processed_cards, selected_ids=selected_ids)
    if fill_to_slots and fill_to_slots > 0:
        return sorted_cards[:fill_to_slots]
    if max_slots and max_slots > 0:
        return sorted_cards[:max_slots]
    return sorted_cards
