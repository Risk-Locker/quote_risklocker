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
        "title": "Unlimited Towing Distance",
        "description": "Provides 24-hour free unlimited towing distance anywhere in Malaysia.",
        "default_value": "Unlimited",
        "icon_hint": "towing",
    },
    {
        "id": "llop",
        "title": "Legal Liability Of Passengers",
        "description": "Protects against third-party claims caused by passenger negligence.",
        "default_value": "",
        "icon_hint": "llop",
    },
    {
        "id": "llp",
        "title": "Legal Liability To Passengers",
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
        "id": "betterment",
        "title": "Waiver Of Betterment",
        "description": "Waives betterment deduction on new replacement parts up to 10 years.",
        "default_value": "",
        "icon_hint": "betterment",
    },
    {
        "id": "all_drivers",
        "title": "All Drivers",
        "description": "Waives RM400 compulsory excess penalty for unnamed authorized drivers.",
        "default_value": "",
        "icon_hint": "all_driver",
    },
    {
        "id": "srcc",
        "title": "Strike, Riot & Civil Commotion",
        "description": "Covers physical damage caused by strikes, riots or public unrest.",
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
        "description": "Covers fitted aftermarket accessories, dashcams, multimedia and rims.",
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
        "id": "pa",
        "title": "Driver Passenger Personal Accident",
        "description": "Accidental Death, Permanent Disablement and Medical Expenses.",
        "default_value": "",
        "icon_hint": "pa",
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
        "description": "Up to 60km from Malaysia border.",
        "default_value": "60 km",
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
        "title": "Private Hire Car ( E-HAILING )",
        "description": "Coverage while providing a legitimate E-Hailing Service.",
        "default_value": "",
        "icon_hint": "ehailing",
    },
    {
        "id": "non_fare_passenger",
        "title": "Legal Liability To Non Fare Paying Passenger",
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
        "title": "Accidental Damage To Boom",
        "description": "Commercial Vehicle - Crane",
        "default_value": "",
        "icon_hint": "boom_damage",
    },
    {
        "id": "overturning",
        "title": "Damage By Overturning",
        "description": "Commercial Vehicle - Crane",
        "default_value": "",
        "icon_hint": "overturning",
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
    s = str(name_or_id or "").lower().strip()
    s = re.sub(r"[^a-z0-9]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def format_addon_value(raw_val: Any) -> str:
    """Normalizes coverage limits for compact card pills, suppressing empty/zero noise."""
    if raw_val is None:
        return ""
    s = re.sub(r"\s+", " ", str(raw_val)).strip()
    if not s:
        return ""
    low = s.lower().rstrip(" .")
    if low in _SUPPRESSED_VALUES:
        return ""

    # Already has RM prefix? Check if zero, otherwise standardize RM x,xxx.xx formatting.
    rm_match = re.fullmatch(r"(?i)rm\s*([0-9][0-9,]*(?:\.[0-9]+)?)", s)
    if rm_match:
        try:
            num = float(rm_match.group(1).replace(",", ""))
            if num <= 0:
                return ""
            return f"RM {num:,.2f}"
        except Exception:
            return s

    # Pure numeric coverage limit (e.g. "1000.0", "350000.0") -> RM x,xxx.xx
    if re.fullmatch(r"[0-9][0-9,]*(?:\.[0-9]+)?", s):
        try:
            num = float(s.replace(",", ""))
            if num <= 0:
                return ""
            return f"RM {num:,.2f}"
        except Exception:
            return s

    # Compact common verbose betterment strings cleanly to 1 crisp line
    if "up to 10 years" in low and "betterment" in low:
        return "Up to 10 Years"
    if len(s) > 28 and "up to " in low:
        m = re.search(r"(up to [0-9]+\s+\w+)", s, re.IGNORECASE)
        if m:
            return m.group(1).title()
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
        return str(matched_cat["icon_hint"])
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
        # Active draft benefit rows that match a canonical matrix slot (e.g. Unlimited Towing included by insurer)
        if matched_cat_id and item.get("is_extra") is not False:
            return True
        if matched_cat_id and item.get("selection_id"):
            return True

    return False


def extract_free_coverage_items(
    active_benefits: list[dict[str, Any]] | None,
    *,
    limit: int = 6,
) -> list[dict[str, str]]:
    """Extracts insurer FOC perks for the top-right 'Free Added Coverage' card without duplication."""
    seen_titles: set[str] = set()
    items: list[dict[str, str]] = []
    for raw in active_benefits or []:
        if raw.get("is_extra") or raw.get("cost_status") == "paid" or _positive_price(raw):
            continue
        matched_cat = _match_catalog_item(raw)
        # If an FOC benefit occupies a canonical matrix add-on slot (like Unlimited Towing),
        # keep it in the Add-On Upgrades ++ matrix rather than repeating it in Free Added Coverage.
        if matched_cat is not None:
            continue
        title = str(raw.get("title") or raw.get("label") or "").strip()
        if not title:
            continue
        norm_title = _normalize_benefit_code(title)
        if norm_title in seen_titles:
            continue
        seen_titles.add(norm_title)
        desc = str(raw.get("description") or raw.get("short_description") or "").strip()
        val = format_addon_value(raw.get("value") or raw.get("coverage_limit"))
        if val:
            val_compact = re.sub(r"\.00\b", "", val).lower()
            desc_norm = desc.lower()
            if val.lower() not in desc_norm and val_compact not in desc_norm:
                desc = f"{desc} ({val})".strip() if desc else val
        items.append({"title": title, "description": desc})
        if len(items) >= limit:
            break
    return items


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
    fill_to_slots: int = 24,
) -> list[dict[str, Any]]:
    """Builds the unified Add-On Upgrades ++ card matrix for Design 2.

    1. Evaluates `active_benefits` (marking paid/selected items or canonical included matrix items).
       Pure non-matrix FOC insurer perks (e.g. Legal Defense Costs, basic Emergency Towing)
       stay in the Free Added Coverage box and are not injected into Add-On Upgrades ++.
    2. Evaluates `available_addons` as UNSELECTED catalog choices (ignoring formula price metadata
       unless explicitly selected / in `selected_ids`).
    3. Preserves exact `CANONICAL_24_CATALOG` initial positions for unselected canonical benefits
       and appends any unmatched custom add-ons afterwards (keeping overflow slots 25+ intact
       when >24 items exist).
    4. Floats selected items to top ('01', '02'..), preserving unselected order afterwards.
    """
    canonical_overrides: dict[str, dict[str, Any]] = {}
    custom_cards: list[dict[str, Any]] = []
    seen_custom_ids: set[str] = set()
    ordered_active_ids: list[str] = []

    def _build_card_dict(item: dict[str, Any], cat_id: str, sel: bool, matched_cat: dict[str, Any] | None) -> dict[str, Any]:
        raw_val = item.get("value") if item.get("value") not in (None, "") else item.get("coverage_limit")
        formatted_val = format_addon_value(raw_val)
        if not formatted_val and matched_cat:
            formatted_val = format_addon_value(matched_cat.get("default_value"))

        cost_status = (
            str(item.get("cost_status") or "paid")
            if sel
            else ("included" if item.get("cost_status") == "included" else "optional")
        )
        return {
            "id": cat_id,
            "code": cat_id,
            "title": str(item.get("title") or item.get("label") or (matched_cat["title"] if matched_cat else cat_id.replace("_", " ").title())),
            "description": str(item.get("description") or item.get("short_description") or (matched_cat["description"] if matched_cat else "")),
            "value": formatted_val,
            "icon_hint": _infer_icon_hint(item, matched_cat),
            "is_selected": sel,
            "cost_status": cost_status,
            "price": item.get("price") or item.get("optional_price"),
            "concept_key": str(item.get("concept_key") or cat_id),
        }

    def _push_item(item: dict[str, Any], source_kind: str) -> None:
        matched_cat = _match_catalog_item(item)
        sel = is_item_selected(
            item,
            selected_ids,
            source_kind=source_kind,
            matched_cat_id=matched_cat["id"] if matched_cat else None,
        )

        # Keep non-canonical unselected FOC perks strictly inside "Free Added Coverage"
        if source_kind == "active" and matched_cat is None and not sel:
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

    processed_cards: list[dict[str, Any]] = []
    if fill_to_slots and fill_to_slots > 0:
        seen_in_output: set[str] = set()
        for cat in CANONICAL_24_CATALOG[:fill_to_slots]:
            cat_id = cat["id"]
            seen_in_output.add(cat_id)
            if cat_id in canonical_overrides:
                processed_cards.append(canonical_overrides[cat_id])
            else:
                is_cat_sel = bool(selected_ids and (cat_id in selected_ids or cat["title"] in selected_ids))
                processed_cards.append(
                    {
                        "id": cat_id,
                        "code": cat_id,
                        "title": cat["title"],
                        "description": cat["description"],
                        "value": format_addon_value(cat.get("default_value")),
                        "icon_hint": cat.get("icon_hint", "generic"),
                        "is_selected": is_cat_sel,
                        "cost_status": "paid" if is_cat_sel else "optional",
                        "concept_key": cat_id,
                    }
                )
        for cat_id in ordered_active_ids:
            if cat_id not in seen_in_output:
                seen_in_output.add(cat_id)
                processed_cards.append(canonical_overrides[cat_id])
    else:
        for cat_id in ordered_active_ids:
            processed_cards.append(canonical_overrides[cat_id])

    processed_cards.extend(custom_cards)
    return sort_unified_addons(processed_cards, selected_ids=selected_ids)
