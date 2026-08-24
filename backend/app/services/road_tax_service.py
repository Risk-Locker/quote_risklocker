"""Road-tax rule management and matching."""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta

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


_PRIVATE_MOTORCYCLE_RATES = (
    (150, 2.00),
    (200, 30.00),
    (250, 50.00),
    (500, 100.00),
    (800, 250.00),
    (float("inf"), 350.00),
)

_COMPANY_MOTORCYCLE_RATES = (
    (150, 2.00),
    (200, 30.00),
    (250, 50.00),
    (500, 180.00),
    (800, 250.00),
    (float("inf"), 350.00),
)

_COMMERCIAL_RATES = (
    (1600, 120.00),
    (2500, 240.00),
    (float("inf"), 480.00),
)

_COMPANY_CAR_RATES = (
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

_PRIVATE_CAR_RATES = (
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


def calculate_road_tax(
    cc: int | float | None,
    vehicle_type: str = "Car",
    owner_type: str = "Individual",
    jurisdiction: str = "West Malaysia",
) -> float:
    """Calculate Malaysian road tax directly from standard JPJ schedules."""
    if cc is None or cc <= 0:
        return 0.0
    engine_cc = round(cc)
    norm_vtype = (vehicle_type or "Car").strip().capitalize()
    norm_owner = (owner_type or "Individual").strip().capitalize()
    is_company = norm_owner in {"Company", "Corporate", "Business"}

    # Motorcycle (Private vs Corporate scale)
    if norm_vtype in {"Motorcycle", "Bike", "Motor"}:
        rates = _COMPANY_MOTORCYCLE_RATES if is_company else _PRIVATE_MOTORCYCLE_RATES
        for max_cc, rate in rates:
            if engine_cc <= max_cc:
                return rate

    # Lorry / Commercial vehicle default fallback
    if norm_vtype in {"Lorry", "Truck", "Commercial", "Others"}:
        for max_cc, rate in _COMMERCIAL_RATES:
            if engine_cc <= max_cc:
                return rate

    # Car - Company vs Private Ownership
    car_rates = _COMPANY_CAR_RATES if is_company else _PRIVATE_CAR_RATES
    for max_cc, base, per_cc, threshold in car_rates:
        if engine_cc <= max_cc:
            if per_cc == 0.0:
                return base
            return round(base + ((engine_cc - threshold) * per_cc), 2)

    return 0.0


def find_matching_rule(
    db: Session,
    cc: int,
    vehicle_type: str = "Car",
    owner_type: str = "Individual",
    jurisdiction: str = "West Malaysia",
) -> RoadTaxRule | None:
    today = date.today()
    rules = db.scalars(
        select(RoadTaxRule).where(
            and_(
                RoadTaxRule.status == "active",
                RoadTaxRule.vehicle_type == vehicle_type,
                RoadTaxRule.owner_type == owner_type,
                RoadTaxRule.jurisdiction == jurisdiction,
                RoadTaxRule.min_cc <= cc,
                or_(RoadTaxRule.max_cc.is_(None), RoadTaxRule.max_cc >= cc),
                RoadTaxRule.effective_from <= today,
                or_(RoadTaxRule.effective_to.is_(None), RoadTaxRule.effective_to >= today),
            )
        )
    ).all()
    if len(rules) == 1:
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
    q = select(RoadTaxRule).order_by(RoadTaxRule.vehicle_type, RoadTaxRule.min_cc)
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


STANDARD_ROAD_TAX_RULES = [
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
]


def seed_standard_road_tax_rules(db: Session) -> int:
    """Seed standard Malaysian road tax rules if none exist or update active rules."""
    seeded = 0
    today = date.today()
    for item in STANDARD_ROAD_TAX_RULES:
        existing = db.scalar(
            select(RoadTaxRule).where(
                RoadTaxRule.vehicle_type == item["vehicle_type"],
                RoadTaxRule.owner_type == item["owner_type"],
                RoadTaxRule.jurisdiction == item["jurisdiction"],
                RoadTaxRule.min_cc == item["min_cc"],
                or_(RoadTaxRule.max_cc.is_(None), RoadTaxRule.max_cc == item["max_cc"]),
            )
        )
        if not existing:
            rule = RoadTaxRule(
                vehicle_type=item["vehicle_type"],
                owner_type=item["owner_type"],
                jurisdiction=item["jurisdiction"],
                min_cc=item["min_cc"],
                max_cc=item["max_cc"],
                base_rate=item["base_rate"],
                formula=item["formula"],
                source=item["source"],
                effective_from=today,
                status="active",
            )
            db.add(rule)
            seeded += 1
    if seeded > 0:
        db.commit()
    return seeded
