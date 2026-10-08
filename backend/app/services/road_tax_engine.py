"""JPJ Road Tax Engine and Calculator."""

from __future__ import annotations

import logging
import math
import re
from datetime import date, timedelta
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.tables import RoadTaxRule

logger = logging.getLogger(__name__)

_SAFE_FORMULA_RE = re.compile(r"^[\d\s+\-*/().,cc]*$")


def _eval_formula(formula: str, cc: int) -> float | None:
    if not formula or not _SAFE_FORMULA_RE.match(formula):
        return None
    try:
        namespace = {"cc": cc}
        return float(eval(formula, {"__builtins__": {}}, namespace))
    except (ValueError, TypeError, SyntaxError, NameError) as exc:
        logger.warning("Road-tax formula evaluation failed for %r with cc=%s: %s", formula, cc, exc)
        return None


# ── 1. Peninsular / West Malaysia Rate Tables ────────────────────────────────

_WEST_MY_PRIVATE_CAR_RATES = (
    (1000, 20.00, 0.0, 0),
    (1200, 55.00, 0.0, 0),
    (1400, 70.00, 0.0, 0),
    (1600, 90.00, 0.0, 0),
    (1800, 200.00, 0.40, 1600),
    (2000, 280.00, 0.50, 1800),
    (2500, 380.00, 1.00, 2000),
    (3000, 840.00, 2.50, 2500),
    (float("inf"), 2130.00, 4.50, 3000),
)

_WEST_MY_COMPANY_CAR_RATES = (
    (1000, 20.00, 0.0, 0),
    (1200, 110.00, 0.0, 0),
    (1400, 140.00, 0.0, 0),
    (1600, 180.00, 0.0, 0),
    (1800, 400.00, 0.80, 1600),
    (2000, 560.00, 1.00, 1800),
    (2500, 760.00, 3.00, 2000),
    (3000, 2260.00, 7.50, 2500),
    (float("inf"), 6010.00, 13.50, 3000),
)

_WEST_MY_NON_SALOON_RATES = (
    (1000, 20.00, 0.0, 0),
    (1200, 85.00, 0.0, 1000),
    (1400, 100.00, 0.0, 1200),
    (1600, 120.00, 0.0, 1400),
    (1800, 300.00, 0.30, 1600),
    (2000, 360.00, 0.40, 1800),
    (2500, 440.00, 0.80, 2000),
    (3000, 840.00, 1.60, 2500),
    (float("inf"), 1640.00, 1.60, 3000),
)

_WEST_MY_PRIVATE_MOTORCYCLE_RATES = (
    (150, 2.00),
    (200, 30.00),
    (250, 50.00),
    (500, 100.00),
    (800, 250.00),
    (float("inf"), 350.00),
)

_WEST_MY_COMPANY_MOTORCYCLE_RATES = (
    (150, 2.00),
    (200, 30.00),
    (250, 50.00),
    (500, 180.00),
    (800, 250.00),
    (float("inf"), 350.00),
)

# Backward-compat aliases for internal tests
_PRIVATE_CAR_RATES = _WEST_MY_PRIVATE_CAR_RATES
_COMPANY_CAR_RATES = _WEST_MY_COMPANY_CAR_RATES
_PRIVATE_MOTORCYCLE_RATES = _WEST_MY_PRIVATE_MOTORCYCLE_RATES
_COMPANY_MOTORCYCLE_RATES = _WEST_MY_COMPANY_MOTORCYCLE_RATES


# ── 2. East Malaysia (Sabah & Sarawak) Rate Tables ───────────────────────────

_EAST_MY_PRIVATE_CAR_RATES = (
    (1000, 20.00, 0.0, 0),
    (1200, 44.00, 0.0, 0),
    (1400, 56.00, 0.0, 0),
    (1600, 72.00, 0.0, 0),
    (1800, 160.00, 0.32, 1600),
    (2000, 224.00, 0.25, 1800),
    (2500, 304.00, 0.50, 2000),
    (3000, 554.00, 1.00, 2500),
    (float("inf"), 1054.00, 1.35, 3000),
)

_EAST_MY_COMPANY_CAR_RATES = (
    (1000, 20.00, 0.0, 0),
    (1200, 88.00, 0.0, 0),
    (1400, 112.00, 0.0, 0),
    (1600, 144.00, 0.0, 0),
    (1800, 320.00, 0.64, 1600),
    (2000, 448.00, 0.80, 1800),
    (2500, 608.00, 1.60, 2000),
    (3000, 1408.00, 3.00, 2500),
    (float("inf"), 2908.00, 4.00, 3000),
)

_EAST_MY_NON_SALOON_RATES = (
    (1000, 20.00, 0.0, 0),
    (1200, 68.00, 0.0, 1000),
    (1400, 80.00, 0.0, 1200),
    (1600, 96.00, 0.0, 1400),
    (1800, 240.00, 0.24, 1600),
    (2000, 288.00, 0.32, 1800),
    (2500, 352.00, 0.64, 2000),
    (3000, 672.00, 1.28, 2500),
    (float("inf"), 1312.00, 1.28, 3000),
)

_EAST_MY_MOTORCYCLE_RATES = (
    (150, 2.00),
    (200, 9.00),
    (250, 12.00),
    (500, 30.00),
    (800, 90.00),
    (float("inf"), 140.00),
)


# ── 3. FT Labuan (Duty Free 50% Concession) Rate Tables ──────────────────────

_LABUAN_PRIVATE_CAR_RATES = (
    (1000, 10.00, 0.0, 0),
    (1200, 27.50, 0.0, 0),
    (1400, 35.00, 0.0, 0),
    (1600, 45.00, 0.0, 0),
    (1800, 100.00, 0.20, 1600),
    (2000, 140.00, 0.25, 1800),
    (2500, 190.00, 0.50, 2000),
    (3000, 420.00, 1.25, 2500),
    (float("inf"), 1065.00, 2.25, 3000),
)

_LABUAN_COMPANY_CAR_RATES = (
    (1000, 10.00, 0.0, 0),
    (1200, 55.00, 0.0, 0),
    (1400, 70.00, 0.0, 0),
    (1600, 90.00, 0.0, 0),
    (1800, 200.00, 0.40, 1600),
    (2000, 280.00, 0.50, 1800),
    (2500, 380.00, 1.50, 2000),
    (3000, 1130.00, 3.75, 2500),
    (float("inf"), 3005.00, 6.75, 3000),
)

_LABUAN_NON_SALOON_RATES = (
    (1000, 10.00, 0.0, 0),
    (1200, 42.50, 0.0, 1000),
    (1400, 50.00, 0.0, 1200),
    (1600, 60.00, 0.0, 1400),
    (1800, 150.00, 0.15, 1600),
    (2000, 180.00, 0.20, 1800),
    (2500, 220.00, 0.40, 2000),
    (3000, 420.00, 0.80, 2500),
    (float("inf"), 820.00, 0.80, 3000),
)

_LABUAN_MOTORCYCLE_RATES = (
    (150, 2.00),
    (200, 15.00),
    (250, 25.00),
    (500, 50.00),
    (800, 125.00),
    (float("inf"), 175.00),
)


# ── 4. Commercial / Lorry Rates ──────────────────────────────────────────────

_COMMERCIAL_RATES = (
    (1600, 120.00),
    (2500, 240.00),
    (5000, 480.00),
    (float("inf"), 720.00),
)


# ── 5. Electric Vehicle (ZEV) 2026 Rate Tables (Private & Company identical) ─
# Official Malaysian JPJ 2026 Rate Structure (Anthony Loke / MOT)

_EV_MOTORCYCLE_RATES = (
    (7500, 2.00),
    (10000, 9.00),
    (12500, 12.00),
    (25000, 30.00),
    (40000, 40.00),
    (float("inf"), 42.00),
)


def calculate_ev_car_road_tax(kw: float, jurisdiction: str = "West Malaysia") -> float:
    """
    Official Malaysian JPJ 2026 EV passenger car road tax structure (announced by Anthony Loke, MOT).
    Applies equally to all electric passenger motorcars (Saloon, Non-Saloon, SUV, MPV).
    """
    if kw <= 0:
        return 0.0
    if kw <= 50.0:
        rate = 20.00
    elif kw <= 100.0:
        blocks = math.ceil((kw - 50.0) / 10.0)
        rate = 20.00 + blocks * 10.00
    elif kw <= 210.0:
        blocks = math.ceil((kw - 100.0) / 10.0)
        rate = 80.00 + (blocks - 1) * 20.00
    elif kw <= 310.0:
        blocks = math.ceil((kw - 210.0) / 10.0)
        rate = 305.00 + (blocks - 1) * 30.00
    elif kw <= 410.0:
        blocks = math.ceil((kw - 310.0) / 10.0)
        rate = 615.00 + (blocks - 1) * 50.00
    elif kw <= 510.0:
        blocks = math.ceil((kw - 410.0) / 10.0)
        rate = 1140.00 + (blocks - 1) * 100.00
    elif kw <= 610.0:
        blocks = math.ceil((kw - 510.0) / 10.0)
        rate = 2165.00 + (blocks - 1) * 150.00
    elif kw <= 710.0:
        blocks = math.ceil((kw - 610.0) / 10.0)
        rate = 3695.00 + (blocks - 1) * 200.00
    elif kw <= 810.0:
        blocks = math.ceil((kw - 710.0) / 10.0)
        rate = 5745.00 + (blocks - 1) * 250.00
    elif kw <= 910.0:
        blocks = math.ceil((kw - 810.0) / 10.0)
        rate = 8295.00 + (blocks - 1) * 300.00
    elif kw <= 1010.0:
        blocks = math.ceil((kw - 910.0) / 10.0)
        rate = 11345.00 + (blocks - 1) * 350.00
    else:
        blocks = math.ceil((kw - 1010.0) / 10.0)
        rate = 14895.00 + (blocks - 1) * 400.00

    if jurisdiction == "Labuan" and kw > 100.0:
        rate = rate * 0.5
    elif jurisdiction in ("Sabah", "Sarawak"):
        rate = rate * 0.5
    return round(rate, 2)


def calculate_ev_motorcycle_road_tax(kw: float, jurisdiction: str = "West Malaysia") -> float:
    """Official Malaysian JPJ 2026 EV motorcycle road tax structure."""
    if kw <= 0:
        return 0.0
    if kw <= 7.5:
        rate = 2.00
    elif kw <= 10.0:
        rate = 9.00
    elif kw <= 12.5:
        rate = 12.00
    elif kw <= 25.0:
        rate = 30.00
    elif kw <= 40.0:
        rate = 40.00
    else:
        rate = 42.00

    if jurisdiction in ("Sabah", "Sarawak", "Labuan"):
        rate = max(2.00, round(rate * 0.5, 2))
    return round(rate, 2)


def normalize_power_to_watts(power_val: float | int | str | None) -> float:
    """
    Normalize vehicle power into Watts (W).
    - If string has explicit 'kw' -> multiply by 1000.
    - If string has explicit 'w' (not 'kw') -> keep unchanged.
    - If numeric:
      - < 1000 -> considered kW (e.g. 50, 85, 150, 200) -> multiply by 1000.
      - >= 1000 -> considered Watts (e.g. 7500, 50000, 150000) -> keep unchanged.
    """
    if power_val is None:
        return 0.0
    val_str = str(power_val).strip().lower()
    num_match = re.search(r"[\d.]+", val_str)
    if not num_match:
        return 0.0
    try:
        num = float(num_match.group(0))
    except ValueError:
        return 0.0

    if "kw" in val_str:
        return num * 1000.0
    if "w" in val_str:
        return num
    if num < 1000.0:
        return num * 1000.0
    return num


def _normalize_jurisdiction(j: str | None) -> str:
    if not j:
        return "West Malaysia"
    cleaned = j.strip().lower()
    if "sabah" in cleaned:
        return "Sabah"
    if "sarawak" in cleaned:
        return "Sarawak"
    if "labuan" in cleaned:
        return "Labuan"
    return "West Malaysia"


def calculate_road_tax(
    cc: int | float | str | None,
    vehicle_type: str = "Car",
    owner_type: str = "Individual",
    jurisdiction: str = "West Malaysia",
    db: Session | None = None,
) -> float:
    """Calculate Malaysian road tax dynamically using active DB rules or standard JPJ schedules."""
    if cc is None:
        return 0.0

    numeric_cc = 0.0
    if isinstance(cc, (int, float)):
        numeric_cc = float(cc)
    else:
        m_num = re.search(r"[\d.]+", str(cc).strip())
        if m_num:
            try:
                numeric_cc = float(m_num.group(0))
            except ValueError:
                return 0.0
        else:
            return 0.0

    if numeric_cc <= 0.0:
        return 0.0
    engine_cc = round(numeric_cc)
    raw_vtype = (vehicle_type or "Car").strip()
    low_vtype = raw_vtype.lower()
    norm_owner = (owner_type or "Individual").strip().capitalize()
    is_company = norm_owner in {"Company", "Corporate", "Business"} or "company" in low_vtype

    if "evsaloon" in low_vtype:
        norm_vtype = "EVSaloonCar"
    elif "evnonsaloon" in low_vtype or ("ev" in low_vtype and ("suv" in low_vtype or "non" in low_vtype or "mpv" in low_vtype)):
        norm_vtype = "EVNonSaloonCar"
    elif "evmotor" in low_vtype or ("ev" in low_vtype and ("bike" in low_vtype or "motor" in low_vtype)):
        norm_vtype = "EVMotorcycle"
    elif "nonsaloon" in low_vtype or "non-saloon" in low_vtype or "suv" in low_vtype or "mpv" in low_vtype:
        norm_vtype = "NonSaloonCar"
    elif "motor" in low_vtype or "bike" in low_vtype:
        norm_vtype = "Motorcycle"
    elif "lorry" in low_vtype or "truck" in low_vtype or "commercial" in low_vtype:
        norm_vtype = "Lorry"
    else:
        norm_vtype = "Car"

    norm_jur = _normalize_jurisdiction(jurisdiction)

    # Auto-detect Electric Vehicle if capacity denotes kW/Watts or is typical EV rating (e.g. 9.4 kW = 9400 Watts)
    is_ev_capacity = False
    if isinstance(cc, str) and ("kw" in cc.lower() or "watt" in cc.lower()):
        is_ev_capacity = True
    elif isinstance(cc, (int, float)) and 0 < float(cc) <= 35.0:
        is_ev_capacity = True

    if is_ev_capacity and norm_vtype not in {"EVSaloonCar", "EVNonSaloonCar", "EVMotorcycle"}:
        if norm_vtype in {"Motorcycle", "Bike"}:
            norm_vtype = "EVMotorcycle"
        elif norm_vtype == "NonSaloonCar":
            norm_vtype = "EVNonSaloonCar"
        else:
            norm_vtype = "EVSaloonCar"

    # 1. Try resolving through active DB rules if Session provided
    if db is not None:
        matched_rule = find_matching_rule(
            db=db,
            cc=engine_cc,
            vehicle_type=norm_vtype,
            owner_type="Company" if is_company else "Individual",
            jurisdiction=norm_jur,
        )
        if matched_rule is not None:
            return round(compute_rate(matched_rule, engine_cc), 2)

    # 2. Electric Vehicles (ZEV - 2026 JPJ Guideline)
    if norm_vtype in {"EVSaloonCar", "EVNonSaloonCar", "EVMotorcycle"}:
        watts = normalize_power_to_watts(cc)
        kw = watts / 1000.0
        if norm_vtype == "EVMotorcycle":
            return calculate_ev_motorcycle_road_tax(kw, norm_jur)
        return calculate_ev_car_road_tax(kw, norm_jur)

    # 2. Non-Saloon Car (SUV / MPV / 4x4 / Pickup - Identical for Individual & Company)
    if norm_vtype == "NonSaloonCar":
        if norm_jur in {"Sabah", "Sarawak"}:
            rates = _EAST_MY_NON_SALOON_RATES
        elif norm_jur == "Labuan":
            rates = _LABUAN_NON_SALOON_RATES
        else:
            rates = _WEST_MY_NON_SALOON_RATES

        for max_cc, base, per_cc, threshold in rates:
            if engine_cc <= max_cc:
                if per_cc == 0.0:
                    return round(base, 2)
                return round(base + ((engine_cc - threshold) * per_cc), 2)

    # 3. Motorcycle
    if norm_vtype in {"Motorcycle", "Bike", "Motor"}:
        if norm_jur in {"Sabah", "Sarawak"}:
            rates = _EAST_MY_MOTORCYCLE_RATES
        elif norm_jur == "Labuan":
            rates = _LABUAN_MOTORCYCLE_RATES
        else:
            rates = _WEST_MY_COMPANY_MOTORCYCLE_RATES if is_company else _WEST_MY_PRIVATE_MOTORCYCLE_RATES

        for max_cc, rate in rates:
            if engine_cc <= max_cc:
                return rate

    # 4. Lorry / Commercial vehicle
    if norm_vtype in {"Lorry", "Truck", "Commercial", "Others"}:
        for max_cc, rate in _COMMERCIAL_RATES:
            if engine_cc <= max_cc:
                return rate

    # 5. Car (Private vs Company across Jurisdictions)
    if norm_jur in {"Sabah", "Sarawak"}:
        car_rates = _EAST_MY_COMPANY_CAR_RATES if is_company else _EAST_MY_PRIVATE_CAR_RATES
    elif norm_jur == "Labuan":
        car_rates = _LABUAN_COMPANY_CAR_RATES if is_company else _LABUAN_PRIVATE_CAR_RATES
    else:
        car_rates = _WEST_MY_COMPANY_CAR_RATES if is_company else _WEST_MY_PRIVATE_CAR_RATES

    for max_cc, base, per_cc, threshold in car_rates:
        if engine_cc <= max_cc:
            if per_cc == 0.0:
                return round(base, 2)
            return round(base + ((engine_cc - threshold) * per_cc), 2)

    return 0.0


def calculate_breakdown(
    cc: int | float | None,
    vehicle_type: str = "Car",
    owner_type: str = "Individual",
    jurisdiction: str = "West Malaysia",
    db: Session | None = None,
) -> dict[str, Any]:
    """Calculate road tax with detailed progressive breakdown for live UI testers."""
    if cc is None or cc <= 0:
        return {
            "engine_cc": 0,
            "vehicle_type": vehicle_type,
            "owner_type": owner_type,
            "jurisdiction": jurisdiction,
            "base_rate": 0.0,
            "progressive_rate": 0.0,
            "excess_cc": 0,
            "progressive_amount": 0.0,
            "total_road_tax": 0.0,
            "formula_text": "Invalid engine CC",
            "matched_tier": "N/A",
        }

    engine_cc = round(cc)
    raw_vtype = (vehicle_type or "Car").strip()
    low_vtype = raw_vtype.lower()
    norm_owner = (owner_type or "Individual").strip().capitalize()
    is_company = norm_owner in {"Company", "Corporate", "Business"} or "company" in low_vtype

    if "evsaloon" in low_vtype:
        norm_vtype = "EVSaloonCar"
    elif "evnonsaloon" in low_vtype or ("ev" in low_vtype and ("suv" in low_vtype or "non" in low_vtype or "mpv" in low_vtype)):
        norm_vtype = "EVNonSaloonCar"
    elif "evmotor" in low_vtype or ("ev" in low_vtype and ("bike" in low_vtype or "motor" in low_vtype)):
        norm_vtype = "EVMotorcycle"
    elif "nonsaloon" in low_vtype or "non-saloon" in low_vtype or "suv" in low_vtype or "mpv" in low_vtype:
        norm_vtype = "NonSaloonCar"
    elif "motor" in low_vtype or "bike" in low_vtype:
        norm_vtype = "Motorcycle"
    elif "lorry" in low_vtype or "truck" in low_vtype or "commercial" in low_vtype:
        norm_vtype = "Lorry"
    else:
        norm_vtype = "Car"

    norm_jur = _normalize_jurisdiction(jurisdiction)

    # Electric Vehicles (ZEV - 2026 JPJ Guideline)
    if norm_vtype in {"EVSaloonCar", "EVNonSaloonCar", "EVMotorcycle"}:
        watts = normalize_power_to_watts(cc)
        kw = watts / 1000.0
        if norm_vtype == "EVMotorcycle":
            rates = _EV_MOTORCYCLE_RATES
            for max_w, rate in rates:
                if watts <= max_w:
                    tier_label = f"≤ {max_w} W ({max_w/1000:g} kW)" if max_w != float("inf") else "> 40,000 W (40 kW)"
                    return {
                        "engine_cc": int(watts),
                        "vehicle_type": "EVMotorcycle",
                        "owner_type": "Company" if is_company else "Individual",
                        "jurisdiction": norm_jur,
                        "base_rate": rate,
                        "progressive_rate": 0.0,
                        "excess_cc": 0,
                        "progressive_amount": 0.0,
                        "total_road_tax": rate,
                        "formula_text": f"Fixed JPJ 2026 EV rate for {tier_label}",
                        "matched_tier": tier_label,
                    }
            return {
                "engine_cc": int(watts),
                "vehicle_type": "EVMotorcycle",
                "owner_type": "Company" if is_company else "Individual",
                "jurisdiction": norm_jur,
                "base_rate": 42.0,
                "progressive_rate": 0.0,
                "excess_cc": 0,
                "progressive_amount": 0.0,
                "total_road_tax": 42.0,
                "formula_text": "Fixed JPJ 2026 EV rate for > 40,000 W",
                "matched_tier": "> 40,000 W",
            }
        else:
            total = calculate_ev_car_road_tax(kw, norm_jur)
            vname = "Saloon EV" if norm_vtype == "EVSaloonCar" else "Non-Saloon EV"
            if kw <= 50.0:
                tier_label = "≤ 50 kW"
                formula_text = "Official JPJ 2026 rate: RM 20.00 flat"
            elif kw <= 100.0:
                blocks = math.ceil((kw - 50.0) / 10.0)
                tier_label = "50.1 – 100 kW"
                formula_text = f"RM 20.00 + ({blocks} blocks × RM 10.00) = RM {total:.2f}"
            elif kw <= 210.0:
                blocks = math.ceil((kw - 100.0) / 10.0)
                tier_label = "100.1 – 210 kW"
                formula_text = f"RM 80.00 + ({blocks - 1} blocks × RM 20.00) = RM {total:.2f}"
            elif kw <= 310.0:
                blocks = math.ceil((kw - 210.0) / 10.0)
                tier_label = "210.1 – 310 kW"
                formula_text = f"RM 305.00 + ({blocks - 1} blocks × RM 30.00) = RM {total:.2f}"
            elif kw <= 410.0:
                blocks = math.ceil((kw - 310.0) / 10.0)
                tier_label = "310.1 – 410 kW"
                formula_text = f"RM 615.00 + ({blocks - 1} blocks × RM 50.00) = RM {total:.2f}"
            elif kw <= 510.0:
                blocks = math.ceil((kw - 410.0) / 10.0)
                tier_label = "410.1 – 510 kW"
                formula_text = f"RM 1,140.00 + ({blocks - 1} blocks × RM 100.00) = RM {total:.2f}"
            elif kw <= 610.0:
                blocks = math.ceil((kw - 510.0) / 10.0)
                tier_label = "510.1 – 610 kW"
                formula_text = f"RM 2,165.00 + ({blocks - 1} blocks × RM 150.00) = RM {total:.2f}"
            else:
                blocks = math.ceil((kw - 610.0) / 10.0)
                tier_label = "> 610 kW"
                formula_text = f"RM 3,695.00 + ({blocks - 1} blocks × RM 200.00) = RM {total:.2f}"

            return {
                "engine_cc": int(watts),
                "vehicle_type": norm_vtype,
                "owner_type": "Company" if is_company else "Individual",
                "jurisdiction": norm_jur,
                "base_rate": total,
                "progressive_rate": 0.0,
                "excess_cc": int(kw),
                "progressive_amount": 0.0,
                "total_road_tax": total,
                "formula_text": formula_text,
                "matched_tier": tier_label,
            }

    # Non-Saloon Car
    if norm_vtype == "NonSaloonCar":
        if norm_jur in {"Sabah", "Sarawak"}:
            rates = _EAST_MY_NON_SALOON_RATES
        elif norm_jur == "Labuan":
            rates = _LABUAN_NON_SALOON_RATES
        else:
            rates = _WEST_MY_NON_SALOON_RATES

        for max_cc, base, per_cc, threshold in rates:
            if engine_cc <= max_cc:
                excess_cc = max(0, engine_cc - threshold) if per_cc > 0 else 0
                prog_amount = round(excess_cc * per_cc, 2)
                total = round(base + prog_amount, 2)
                tier_label = f"{threshold + 1} – {max_cc} cc" if max_cc != float("inf") else f"Over {threshold} cc"

                if per_cc == 0.0:
                    formula_text = f"Flat base rate for {tier_label}"
                else:
                    formula_text = f"RM {base:.2f} + ({excess_cc} cc × RM {per_cc:.2f})"

                return {
                    "engine_cc": engine_cc,
                    "vehicle_type": "NonSaloonCar",
                    "owner_type": "Company" if is_company else "Individual",
                    "jurisdiction": norm_jur,
                    "base_rate": base,
                    "progressive_rate": per_cc,
                    "excess_cc": excess_cc,
                    "progressive_amount": prog_amount,
                    "total_road_tax": total,
                    "formula_text": formula_text,
                    "matched_tier": tier_label,
                }

    # Motorcycle
    if norm_vtype in {"Motorcycle", "Bike", "Motor"}:
        if norm_jur in {"Sabah", "Sarawak"}:
            rates = _EAST_MY_MOTORCYCLE_RATES
        elif norm_jur == "Labuan":
            rates = _LABUAN_MOTORCYCLE_RATES
        else:
            rates = _WEST_MY_COMPANY_MOTORCYCLE_RATES if is_company else _WEST_MY_PRIVATE_MOTORCYCLE_RATES

        for max_cc, rate in rates:
            if engine_cc <= max_cc:
                tier_label = f"Up to {max_cc} cc" if max_cc != float("inf") else "Over 800 cc"
                return {
                    "engine_cc": engine_cc,
                    "vehicle_type": "Motorcycle",
                    "owner_type": "Company" if is_company else "Individual",
                    "jurisdiction": norm_jur,
                    "base_rate": rate,
                    "progressive_rate": 0.0,
                    "excess_cc": 0,
                    "progressive_amount": 0.0,
                    "total_road_tax": rate,
                    "formula_text": f"Flat rate for {tier_label}",
                    "matched_tier": tier_label,
                }

    # Lorry / Commercial
    if norm_vtype in {"Lorry", "Truck", "Commercial", "Others"}:
        for max_cc, rate in _COMMERCIAL_RATES:
            if engine_cc <= max_cc:
                tier_label = f"Up to {max_cc} cc" if max_cc != float("inf") else "Over 5,000 cc"
                return {
                    "engine_cc": engine_cc,
                    "vehicle_type": "Lorry",
                    "owner_type": "Company" if is_company else "Individual",
                    "jurisdiction": norm_jur,
                    "base_rate": rate,
                    "progressive_rate": 0.0,
                    "excess_cc": 0,
                    "progressive_amount": 0.0,
                    "total_road_tax": rate,
                    "formula_text": f"Commercial tariff for {tier_label}",
                    "matched_tier": tier_label,
                }

    # Car
    if norm_jur in {"Sabah", "Sarawak"}:
        car_rates = _EAST_MY_COMPANY_CAR_RATES if is_company else _EAST_MY_PRIVATE_CAR_RATES
    elif norm_jur == "Labuan":
        car_rates = _LABUAN_COMPANY_CAR_RATES if is_company else _LABUAN_PRIVATE_CAR_RATES
    else:
        car_rates = _WEST_MY_COMPANY_CAR_RATES if is_company else _WEST_MY_PRIVATE_CAR_RATES

    for max_cc, base, per_cc, threshold in car_rates:
        if engine_cc <= max_cc:
            excess_cc = max(0, engine_cc - threshold) if per_cc > 0 else 0
            prog_amount = round(excess_cc * per_cc, 2)
            total = round(base + prog_amount, 2)
            tier_label = f"{threshold + 1} – {max_cc} cc" if max_cc != float("inf") else f"Over {threshold} cc"

            if per_cc == 0.0:
                formula_text = f"Flat base rate for {tier_label}"
            else:
                formula_text = f"RM {base:.2f} + ({excess_cc} cc × RM {per_cc:.2f})"

            return {
                "engine_cc": engine_cc,
                "vehicle_type": "Car",
                "owner_type": "Company" if is_company else "Individual",
                "jurisdiction": norm_jur,
                "base_rate": base,
                "progressive_rate": per_cc,
                "excess_cc": excess_cc,
                "progressive_amount": prog_amount,
                "total_road_tax": total,
                "formula_text": formula_text,
                "matched_tier": tier_label,
            }

    return {
        "engine_cc": engine_cc,
        "vehicle_type": norm_vtype,
        "owner_type": norm_owner,
        "jurisdiction": norm_jur,
        "base_rate": 0.0,
        "progressive_rate": 0.0,
        "excess_cc": 0,
        "progressive_amount": 0.0,
        "total_road_tax": 0.0,
        "formula_text": "No matching rate tier found",
        "matched_tier": "N/A",
    }


def find_matching_rule(
    db: Session,
    cc: int,
    vehicle_type: str = "Car",
    owner_type: str = "Individual",
    jurisdiction: str = "West Malaysia",
) -> RoadTaxRule | None:
    today = date.today()
    norm_jur = _normalize_jurisdiction(jurisdiction)
    rules = db.scalars(
        select(RoadTaxRule).where(
            and_(
                RoadTaxRule.status == "active",
                RoadTaxRule.vehicle_type == vehicle_type,
                RoadTaxRule.owner_type == owner_type,
                RoadTaxRule.jurisdiction == norm_jur,
                RoadTaxRule.min_cc <= cc,
                or_(RoadTaxRule.max_cc.is_(None), RoadTaxRule.max_cc >= cc),
                RoadTaxRule.effective_from <= today,
                or_(RoadTaxRule.effective_to.is_(None), RoadTaxRule.effective_to >= today),
            )
        )
    ).all()
    if len(rules) >= 1:
        return rules[0]
    return None


def compute_rate(rule: RoadTaxRule, cc: int) -> float:
    if rule.formula:
        result = _eval_formula(rule.formula, cc)
        if result is not None:
            return result
    return float(str(rule.base_rate)) if rule.base_rate is not None else 0.0

