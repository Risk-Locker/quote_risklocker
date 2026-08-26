"""Road-tax rule management, full schedule seeding, and dynamic formula calculation."""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
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
    cc: int | float | None,
    vehicle_type: str = "Car",
    owner_type: str = "Individual",
    jurisdiction: str = "West Malaysia",
    db: Session | None = None,
) -> float:
    """Calculate Malaysian road tax dynamically using active DB rules or standard JPJ schedules."""
    if cc is None or cc <= 0:
        return 0.0
    engine_cc = round(cc)
    norm_vtype = (vehicle_type or "Car").strip().capitalize()
    norm_owner = (owner_type or "Individual").strip().capitalize()
    is_company = norm_owner in {"Company", "Corporate", "Business"}
    norm_jur = _normalize_jurisdiction(jurisdiction)

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

    # 2. Motorcycle
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

    # 3. Lorry / Commercial vehicle
    if norm_vtype in {"Lorry", "Truck", "Commercial", "Others"}:
        for max_cc, rate in _COMMERCIAL_RATES:
            if engine_cc <= max_cc:
                return rate

    # 4. Car (Private vs Company across Jurisdictions)
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
    norm_vtype = (vehicle_type or "Car").strip().capitalize()
    norm_owner = (owner_type or "Individual").strip().capitalize()
    is_company = norm_owner in {"Company", "Corporate", "Business"}
    norm_jur = _normalize_jurisdiction(jurisdiction)

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


def upsert_rule(db: Session, payload: dict) -> RoadTaxRule:
    rule = db.get(RoadTaxRule, payload.get("id")) if payload.get("id") else None
    if not rule:
        rule = RoadTaxRule()
        db.add(rule)
    for key in [
        "vehicle_type", "owner_type", "jurisdiction", "min_cc", "max_cc",
        "base_rate", "formula", "source", "status",
    ]:
        if key in payload:
            setattr(rule, key, payload[key])
    effective_from_val = payload.get("effective_from")
    if effective_from_val:
        setattr(rule, "effective_from", date.fromisoformat(effective_from_val) if isinstance(effective_from_val, str) else effective_from_val)
    elif getattr(rule, "effective_from", None) is None:
        setattr(rule, "effective_from", date.today())

    effective_to_val = payload.get("effective_to")
    if effective_to_val:
        setattr(rule, "effective_to", date.fromisoformat(effective_to_val) if isinstance(effective_to_val, str) else effective_to_val)
    elif getattr(rule, "effective_to", None) is None:
        setattr(rule, "effective_to", date.today() + timedelta(days=365))

    db.commit()
    db.refresh(rule)
    return rule


def delete_rule(db: Session, rule_id: str) -> None:
    rule = db.get(RoadTaxRule, rule_id)
    if not rule:
        raise AppError("Road-tax rule not found.", 404)
    db.delete(rule)
    db.commit()


def list_rules(db: Session, vehicle_type: str | None = None) -> list[RoadTaxRule]:
    q = select(RoadTaxRule).order_by(
        RoadTaxRule.jurisdiction,
        RoadTaxRule.vehicle_type,
        RoadTaxRule.owner_type,
        RoadTaxRule.min_cc,
    )
    if vehicle_type:
        q = q.where(RoadTaxRule.vehicle_type == vehicle_type)
    return list(db.scalars(q).all())


def serialize_rule(r: RoadTaxRule) -> dict:
    return {
        "id": r.id,
        "vehicle_type": r.vehicle_type,
        "owner_type": r.owner_type,
        "jurisdiction": r.jurisdiction,
        "min_cc": r.min_cc,
        "max_cc": r.max_cc,
        "base_rate": float(str(r.base_rate)),
        "formula": r.formula,
        "source": r.source,
        "effective_from": r.effective_from.isoformat() if r.effective_from else None,
        "effective_to": r.effective_to.isoformat() if r.effective_to else None,
        "status": r.status,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
    }


EXPORT_COLUMNS = [
    "vehicle_type", "owner_type", "jurisdiction", "min_cc", "max_cc",
    "base_rate", "formula", "source", "effective_from", "effective_to", "status",
]


def export_csv_bytes(rules: list[RoadTaxRule]) -> bytes:
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=EXPORT_COLUMNS)
    writer.writeheader()
    for rule in rules:
        serialized = serialize_rule(rule)
        writer.writerow({col: serialized.get(col, "") for col in EXPORT_COLUMNS})
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def import_rules(db: Session, rows: list[list[object]]) -> dict:
    """Import road-tax rules from parsed rows (header row + data rows)."""
    from app.services.import_export import MAX_ROWS

    created = 0
    updated = 0
    errors: list[str] = []
    if not rows:
        raise AppError("The file contains no data.", 400)
    header = [str(c).strip().lower().replace(" ", "_") if c else "" for c in rows[0]]
    body = rows[1:MAX_ROWS + 1]
    for index, row in enumerate(body, start=2):
        payload: dict = {}
        try:
            for idx, col in enumerate(header):
                value = row[idx] if idx < len(row) else None
                if col in {"min_cc", "max_cc"}:
                    if value not in (None, ""):
                        payload[col] = int(str(value))
                elif col == "base_rate":
                    if value in (None, ""):
                        raise ValueError("base_rate is required")
                    payload[col] = float(str(value))
                elif col == "status":
                    if value not in (None, ""):
                        payload[col] = str(value)
                elif col in {"formula", "source", "vehicle_type", "owner_type", "jurisdiction", "effective_from", "effective_to"}:
                    if value not in (None, ""):
                        payload[col] = str(value)
            if not payload.get("vehicle_type"):
                payload["vehicle_type"] = "Car"
            if not payload.get("owner_type"):
                payload["owner_type"] = "Individual"
            if not payload.get("jurisdiction"):
                payload["jurisdiction"] = "West Malaysia"
            eff_from = date.fromisoformat(payload["effective_from"]) if payload.get("effective_from") else date.today()
            existing = db.scalar(
                select(RoadTaxRule).where(
                    RoadTaxRule.vehicle_type == payload["vehicle_type"],
                    RoadTaxRule.owner_type == payload["owner_type"],
                    RoadTaxRule.jurisdiction == payload["jurisdiction"],
                    RoadTaxRule.min_cc == payload.get("min_cc", 0),
                    or_(RoadTaxRule.max_cc.is_(None), RoadTaxRule.max_cc == payload.get("max_cc")),
                    RoadTaxRule.effective_from == eff_from,
                )
            )
            if existing:
                payload["id"] = existing.id
                updated += 1
            else:
                created += 1
            upsert_rule(db, payload)
        except (ValueError, TypeError) as exc:
            errors.append(f"Row {index}: {exc}")
    return {"created": created, "updated": updated, "errors": errors}


# ── Complete Canonical Standard Schedules (68 Rules) ─────────────────────────

STANDARD_ROAD_TAX_RULES = [
    # ── 1. West Malaysia (Peninsular) ──
    # Private Car (West Malaysia)
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "West Malaysia", "min_cc": 1, "max_cc": 1000, "base_rate": 20.00, "formula": None, "source": "JPJ Schedule (Peninsular)"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "West Malaysia", "min_cc": 1001, "max_cc": 1200, "base_rate": 55.00, "formula": None, "source": "JPJ Schedule (Peninsular)"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "West Malaysia", "min_cc": 1201, "max_cc": 1400, "base_rate": 70.00, "formula": None, "source": "JPJ Schedule (Peninsular)"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "West Malaysia", "min_cc": 1401, "max_cc": 1600, "base_rate": 90.00, "formula": None, "source": "JPJ Schedule (Peninsular)"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "West Malaysia", "min_cc": 1601, "max_cc": 1800, "base_rate": 200.00, "formula": "200 + ((cc - 1600) * 0.40)", "source": "JPJ Schedule (Peninsular)"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "West Malaysia", "min_cc": 1801, "max_cc": 2000, "base_rate": 280.00, "formula": "280 + ((cc - 1800) * 0.50)", "source": "JPJ Schedule (Peninsular)"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "West Malaysia", "min_cc": 2001, "max_cc": 2500, "base_rate": 380.00, "formula": "380 + ((cc - 2000) * 1.00)", "source": "JPJ Schedule (Peninsular)"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "West Malaysia", "min_cc": 2501, "max_cc": 3000, "base_rate": 840.00, "formula": "840 + ((cc - 2500) * 2.50)", "source": "JPJ Schedule (Peninsular)"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "West Malaysia", "min_cc": 3001, "max_cc": None, "base_rate": 2130.00, "formula": "2130 + ((cc - 3000) * 4.50)", "source": "JPJ Schedule (Peninsular)"},

    # Company Car (West Malaysia)
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 1, "max_cc": 1000, "base_rate": 20.00, "formula": None, "source": "JPJ Schedule (Peninsular)"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 1001, "max_cc": 1200, "base_rate": 110.00, "formula": None, "source": "JPJ Schedule (Peninsular)"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 1201, "max_cc": 1400, "base_rate": 140.00, "formula": None, "source": "JPJ Schedule (Peninsular)"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 1401, "max_cc": 1600, "base_rate": 180.00, "formula": None, "source": "JPJ Schedule (Peninsular)"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 1601, "max_cc": 1800, "base_rate": 400.00, "formula": "400 + ((cc - 1600) * 0.80)", "source": "JPJ Schedule (Peninsular)"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 1801, "max_cc": 2000, "base_rate": 560.00, "formula": "560 + ((cc - 1800) * 1.00)", "source": "JPJ Schedule (Peninsular)"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 2001, "max_cc": 2500, "base_rate": 760.00, "formula": "760 + ((cc - 2000) * 3.00)", "source": "JPJ Schedule (Peninsular)"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 2501, "max_cc": 3000, "base_rate": 2260.00, "formula": "2260 + ((cc - 2500) * 7.50)", "source": "JPJ Schedule (Peninsular)"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 3001, "max_cc": None, "base_rate": 6010.00, "formula": "6010 + ((cc - 3000) * 13.50)", "source": "JPJ Schedule (Peninsular)"},

    # Motorcycle Private (West Malaysia)
    {"vehicle_type": "Motorcycle", "owner_type": "Individual", "jurisdiction": "West Malaysia", "min_cc": 1, "max_cc": 150, "base_rate": 2.00, "formula": None, "source": "JPJ Schedule (Peninsular)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Individual", "jurisdiction": "West Malaysia", "min_cc": 151, "max_cc": 200, "base_rate": 30.00, "formula": None, "source": "JPJ Schedule (Peninsular)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Individual", "jurisdiction": "West Malaysia", "min_cc": 201, "max_cc": 250, "base_rate": 50.00, "formula": None, "source": "JPJ Schedule (Peninsular)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Individual", "jurisdiction": "West Malaysia", "min_cc": 251, "max_cc": 500, "base_rate": 100.00, "formula": None, "source": "JPJ Schedule (Peninsular)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Individual", "jurisdiction": "West Malaysia", "min_cc": 501, "max_cc": 800, "base_rate": 250.00, "formula": None, "source": "JPJ Schedule (Peninsular)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Individual", "jurisdiction": "West Malaysia", "min_cc": 801, "max_cc": None, "base_rate": 350.00, "formula": None, "source": "JPJ Schedule (Peninsular)"},

    # Motorcycle Company (West Malaysia)
    {"vehicle_type": "Motorcycle", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 1, "max_cc": 150, "base_rate": 2.00, "formula": None, "source": "JPJ Schedule (Peninsular)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 151, "max_cc": 200, "base_rate": 30.00, "formula": None, "source": "JPJ Schedule (Peninsular)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 201, "max_cc": 250, "base_rate": 50.00, "formula": None, "source": "JPJ Schedule (Peninsular)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 251, "max_cc": 500, "base_rate": 180.00, "formula": None, "source": "JPJ Schedule (Peninsular)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 501, "max_cc": 800, "base_rate": 250.00, "formula": None, "source": "JPJ Schedule (Peninsular)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 801, "max_cc": None, "base_rate": 350.00, "formula": None, "source": "JPJ Schedule (Peninsular)"},

    # ── 2. Sabah ──
    # Private Car (Sabah)
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "Sabah", "min_cc": 1, "max_cc": 1000, "base_rate": 20.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "Sabah", "min_cc": 1001, "max_cc": 1200, "base_rate": 44.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "Sabah", "min_cc": 1201, "max_cc": 1400, "base_rate": 56.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "Sabah", "min_cc": 1401, "max_cc": 1600, "base_rate": 72.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "Sabah", "min_cc": 1601, "max_cc": 1800, "base_rate": 160.00, "formula": "160 + ((cc - 1600) * 0.32)", "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "Sabah", "min_cc": 1801, "max_cc": 2000, "base_rate": 224.00, "formula": "224 + ((cc - 1800) * 0.25)", "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "Sabah", "min_cc": 2001, "max_cc": 2500, "base_rate": 304.00, "formula": "304 + ((cc - 2000) * 0.50)", "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "Sabah", "min_cc": 2501, "max_cc": 3000, "base_rate": 554.00, "formula": "554 + ((cc - 2500) * 1.00)", "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "Sabah", "min_cc": 3001, "max_cc": None, "base_rate": 1054.00, "formula": "1054 + ((cc - 3000) * 1.35)", "source": "JPJ Schedule (East Malaysia)"},

    # Company Car (Sabah)
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 1, "max_cc": 1000, "base_rate": 20.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 1001, "max_cc": 1200, "base_rate": 88.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 1201, "max_cc": 1400, "base_rate": 112.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 1401, "max_cc": 1600, "base_rate": 144.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 1601, "max_cc": 1800, "base_rate": 320.00, "formula": "320 + ((cc - 1600) * 0.64)", "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 1801, "max_cc": 2000, "base_rate": 448.00, "formula": "448 + ((cc - 1800) * 0.80)", "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 2001, "max_cc": 2500, "base_rate": 608.00, "formula": "608 + ((cc - 2000) * 1.60)", "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 2501, "max_cc": 3000, "base_rate": 1408.00, "formula": "1408 + ((cc - 2500) * 3.00)", "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 3001, "max_cc": None, "base_rate": 2908.00, "formula": "2908 + ((cc - 3000) * 4.00)", "source": "JPJ Schedule (East Malaysia)"},

    # Motorcycle Private & Company (Sabah)
    {"vehicle_type": "Motorcycle", "owner_type": "Individual", "jurisdiction": "Sabah", "min_cc": 1, "max_cc": 150, "base_rate": 2.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Individual", "jurisdiction": "Sabah", "min_cc": 151, "max_cc": 200, "base_rate": 9.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Individual", "jurisdiction": "Sabah", "min_cc": 201, "max_cc": 250, "base_rate": 12.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Individual", "jurisdiction": "Sabah", "min_cc": 251, "max_cc": 500, "base_rate": 30.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Individual", "jurisdiction": "Sabah", "min_cc": 501, "max_cc": 800, "base_rate": 90.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Individual", "jurisdiction": "Sabah", "min_cc": 801, "max_cc": None, "base_rate": 140.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},

    {"vehicle_type": "Motorcycle", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 1, "max_cc": 150, "base_rate": 2.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 151, "max_cc": 200, "base_rate": 9.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 201, "max_cc": 250, "base_rate": 12.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 251, "max_cc": 500, "base_rate": 30.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 501, "max_cc": 800, "base_rate": 90.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 801, "max_cc": None, "base_rate": 140.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},

    # ── 3. Sarawak ──
    # Private Car (Sarawak)
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "Sarawak", "min_cc": 1, "max_cc": 1000, "base_rate": 20.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "Sarawak", "min_cc": 1001, "max_cc": 1200, "base_rate": 44.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "Sarawak", "min_cc": 1201, "max_cc": 1400, "base_rate": 56.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "Sarawak", "min_cc": 1401, "max_cc": 1600, "base_rate": 72.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "Sarawak", "min_cc": 1601, "max_cc": 1800, "base_rate": 160.00, "formula": "160 + ((cc - 1600) * 0.32)", "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "Sarawak", "min_cc": 1801, "max_cc": 2000, "base_rate": 224.00, "formula": "224 + ((cc - 1800) * 0.25)", "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "Sarawak", "min_cc": 2001, "max_cc": 2500, "base_rate": 304.00, "formula": "304 + ((cc - 2000) * 0.50)", "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "Sarawak", "min_cc": 2501, "max_cc": 3000, "base_rate": 554.00, "formula": "554 + ((cc - 2500) * 1.00)", "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "Sarawak", "min_cc": 3001, "max_cc": None, "base_rate": 1054.00, "formula": "1054 + ((cc - 3000) * 1.35)", "source": "JPJ Schedule (East Malaysia)"},

    # Company Car (Sarawak)
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 1, "max_cc": 1000, "base_rate": 20.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 1001, "max_cc": 1200, "base_rate": 88.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 1201, "max_cc": 1400, "base_rate": 112.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 1401, "max_cc": 1600, "base_rate": 144.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 1601, "max_cc": 1800, "base_rate": 320.00, "formula": "320 + ((cc - 1600) * 0.64)", "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 1801, "max_cc": 2000, "base_rate": 448.00, "formula": "448 + ((cc - 1800) * 0.80)", "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 2001, "max_cc": 2500, "base_rate": 608.00, "formula": "608 + ((cc - 2000) * 1.60)", "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 2501, "max_cc": 3000, "base_rate": 1408.00, "formula": "1408 + ((cc - 2500) * 3.00)", "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 3001, "max_cc": None, "base_rate": 2908.00, "formula": "2908 + ((cc - 3000) * 4.00)", "source": "JPJ Schedule (East Malaysia)"},

    # Motorcycle Private & Company (Sarawak)
    {"vehicle_type": "Motorcycle", "owner_type": "Individual", "jurisdiction": "Sarawak", "min_cc": 1, "max_cc": 150, "base_rate": 2.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Individual", "jurisdiction": "Sarawak", "min_cc": 151, "max_cc": 200, "base_rate": 9.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Individual", "jurisdiction": "Sarawak", "min_cc": 201, "max_cc": 250, "base_rate": 12.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Individual", "jurisdiction": "Sarawak", "min_cc": 251, "max_cc": 500, "base_rate": 30.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Individual", "jurisdiction": "Sarawak", "min_cc": 501, "max_cc": 800, "base_rate": 90.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Individual", "jurisdiction": "Sarawak", "min_cc": 801, "max_cc": None, "base_rate": 140.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},

    {"vehicle_type": "Motorcycle", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 1, "max_cc": 150, "base_rate": 2.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 151, "max_cc": 200, "base_rate": 9.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 201, "max_cc": 250, "base_rate": 12.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 251, "max_cc": 500, "base_rate": 30.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 501, "max_cc": 800, "base_rate": 90.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},
    {"vehicle_type": "Motorcycle", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 801, "max_cc": None, "base_rate": 140.00, "formula": None, "source": "JPJ Schedule (East Malaysia)"},

    # ── 4. FT Labuan (Duty Free 50% Concession) ──
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "Labuan", "min_cc": 1, "max_cc": 1000, "base_rate": 10.00, "formula": None, "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "Labuan", "min_cc": 1001, "max_cc": 1200, "base_rate": 27.50, "formula": None, "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "Labuan", "min_cc": 1201, "max_cc": 1400, "base_rate": 35.00, "formula": None, "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "Labuan", "min_cc": 1401, "max_cc": 1600, "base_rate": 45.00, "formula": None, "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "Labuan", "min_cc": 1601, "max_cc": 1800, "base_rate": 100.00, "formula": "100 + ((cc - 1600) * 0.20)", "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "Labuan", "min_cc": 1801, "max_cc": 2000, "base_rate": 140.00, "formula": "140 + ((cc - 1800) * 0.25)", "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "Labuan", "min_cc": 2001, "max_cc": 2500, "base_rate": 190.00, "formula": "190 + ((cc - 2000) * 0.50)", "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "Labuan", "min_cc": 2501, "max_cc": 3000, "base_rate": 420.00, "formula": "420 + ((cc - 2500) * 1.25)", "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "Labuan", "min_cc": 3001, "max_cc": None, "base_rate": 1065.00, "formula": "1065 + ((cc - 3000) * 2.25)", "source": "JPJ Labuan Duty-Free Concession"},

    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "Labuan", "min_cc": 1, "max_cc": 1000, "base_rate": 10.00, "formula": None, "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "Labuan", "min_cc": 1001, "max_cc": 1200, "base_rate": 55.00, "formula": None, "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "Labuan", "min_cc": 1201, "max_cc": 1400, "base_rate": 70.00, "formula": None, "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "Labuan", "min_cc": 1401, "max_cc": 1600, "base_rate": 90.00, "formula": None, "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "Labuan", "min_cc": 1601, "max_cc": 1800, "base_rate": 200.00, "formula": "200 + ((cc - 1600) * 0.40)", "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "Labuan", "min_cc": 1801, "max_cc": 2000, "base_rate": 280.00, "formula": "280 + ((cc - 1800) * 0.50)", "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "Labuan", "min_cc": 2001, "max_cc": 2500, "base_rate": 380.00, "formula": "380 + ((cc - 2000) * 1.50)", "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "Labuan", "min_cc": 2501, "max_cc": 3000, "base_rate": 1130.00, "formula": "1130 + ((cc - 2500) * 3.75)", "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "Car", "owner_type": "Company", "jurisdiction": "Labuan", "min_cc": 3001, "max_cc": None, "base_rate": 3005.00, "formula": "3005 + ((cc - 3000) * 6.75)", "source": "JPJ Labuan Duty-Free Concession"},

    # ── 5. Commercial Lorry / Goods Vehicles (All Jurisdictions) ──
    {"vehicle_type": "Lorry", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 1, "max_cc": 1600, "base_rate": 120.00, "formula": None, "source": "JPJ Commercial Schedule"},
    {"vehicle_type": "Lorry", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 1601, "max_cc": 2500, "base_rate": 240.00, "formula": None, "source": "JPJ Commercial Schedule"},
    {"vehicle_type": "Lorry", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 2501, "max_cc": 5000, "base_rate": 480.00, "formula": None, "source": "JPJ Commercial Schedule"},
    {"vehicle_type": "Lorry", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 5001, "max_cc": None, "base_rate": 720.00, "formula": None, "source": "JPJ Commercial Schedule"},

    {"vehicle_type": "Lorry", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 1, "max_cc": 1600, "base_rate": 120.00, "formula": None, "source": "JPJ Commercial Schedule (East Malaysia)"},
    {"vehicle_type": "Lorry", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 1601, "max_cc": 2500, "base_rate": 240.00, "formula": None, "source": "JPJ Commercial Schedule (East Malaysia)"},
    {"vehicle_type": "Lorry", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 2501, "max_cc": 5000, "base_rate": 480.00, "formula": None, "source": "JPJ Commercial Schedule (East Malaysia)"},
    {"vehicle_type": "Lorry", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 5001, "max_cc": None, "base_rate": 720.00, "formula": None, "source": "JPJ Commercial Schedule (East Malaysia)"},

    {"vehicle_type": "Lorry", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 1, "max_cc": 1600, "base_rate": 120.00, "formula": None, "source": "JPJ Commercial Schedule (East Malaysia)"},
    {"vehicle_type": "Lorry", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 1601, "max_cc": 2500, "base_rate": 240.00, "formula": None, "source": "JPJ Commercial Schedule (East Malaysia)"},
    {"vehicle_type": "Lorry", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 2501, "max_cc": 5000, "base_rate": 480.00, "formula": None, "source": "JPJ Commercial Schedule (East Malaysia)"},
    {"vehicle_type": "Lorry", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 5001, "max_cc": None, "base_rate": 720.00, "formula": None, "source": "JPJ Commercial Schedule (East Malaysia)"},
]


def seed_standard_road_tax_rules(db: Session) -> dict[str, int]:
    """Seed or update standard Malaysian road tax rules across all jurisdictions."""
    created = 0
    updated = 0
    today = date.today()
    for item in STANDARD_ROAD_TAX_RULES:
        existing = db.scalar(
            select(RoadTaxRule).where(
                RoadTaxRule.vehicle_type == item["vehicle_type"],
                RoadTaxRule.owner_type == item["owner_type"],
                RoadTaxRule.jurisdiction == item["jurisdiction"],
                RoadTaxRule.min_cc == item["min_cc"],
            )
        )
        if existing:
            existing.max_cc = int(item["max_cc"]) if item["max_cc"] is not None else None
            existing.base_rate = float(item["base_rate"])
            existing.formula = str(item["formula"]) if item["formula"] is not None else None
            existing.source = str(item["source"]) if item["source"] is not None else None
            existing.status = "active"
            updated += 1
        else:
            rule = RoadTaxRule(
                vehicle_type=str(item["vehicle_type"]),
                owner_type=str(item["owner_type"]),
                jurisdiction=str(item["jurisdiction"]),
                min_cc=int(item["min_cc"]),
                max_cc=int(item["max_cc"]) if item["max_cc"] is not None else None,
                base_rate=float(item["base_rate"]),
                formula=str(item["formula"]) if item["formula"] is not None else None,
                source=str(item["source"]) if item["source"] is not None else None,
                effective_from=today,
                status="active",
            )
            db.add(rule)
            created += 1

    db.commit()
    return {"created": created, "updated": updated, "total": len(STANDARD_ROAD_TAX_RULES)}
