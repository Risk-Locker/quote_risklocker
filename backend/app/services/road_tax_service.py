"""Road-tax rule management, full schedule seeding, and dynamic formula calculation."""

from __future__ import annotations

import logging
import math
import re
from datetime import date, timedelta
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.tables import RoadTaxRule


logger = logging.getLogger(__name__)

from app.services.road_tax_engine import (
    calculate_road_tax,
    calculate_breakdown,
    find_matching_rule,
    compute_rate,
    _eval_formula,
    normalize_power_to_watts,
    _normalize_jurisdiction,
    calculate_ev_car_road_tax,
    calculate_ev_motorcycle_road_tax,
)


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

    # Non-Saloon Car (SUV / MPV / 4x4 / Pickup / Van - West Malaysia)
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "West Malaysia", "min_cc": 1, "max_cc": 1000, "base_rate": 20.00, "formula": None, "source": "JPJ Schedule (Non-Saloon)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "West Malaysia", "min_cc": 1001, "max_cc": 1200, "base_rate": 85.00, "formula": None, "source": "JPJ Schedule (Non-Saloon)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "West Malaysia", "min_cc": 1201, "max_cc": 1400, "base_rate": 100.00, "formula": None, "source": "JPJ Schedule (Non-Saloon)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "West Malaysia", "min_cc": 1401, "max_cc": 1600, "base_rate": 120.00, "formula": None, "source": "JPJ Schedule (Non-Saloon)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "West Malaysia", "min_cc": 1601, "max_cc": 1800, "base_rate": 300.00, "formula": "300 + ((cc - 1600) * 0.30)", "source": "JPJ Schedule (Non-Saloon)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "West Malaysia", "min_cc": 1801, "max_cc": 2000, "base_rate": 360.00, "formula": "360 + ((cc - 1800) * 0.40)", "source": "JPJ Schedule (Non-Saloon)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "West Malaysia", "min_cc": 2001, "max_cc": 2500, "base_rate": 440.00, "formula": "440 + ((cc - 2000) * 0.80)", "source": "JPJ Schedule (Non-Saloon)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "West Malaysia", "min_cc": 2501, "max_cc": 3000, "base_rate": 840.00, "formula": "840 + ((cc - 2500) * 1.60)", "source": "JPJ Schedule (Non-Saloon)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "West Malaysia", "min_cc": 3001, "max_cc": None, "base_rate": 1640.00, "formula": "1640 + ((cc - 3000) * 1.60)", "source": "JPJ Schedule (Non-Saloon)"},

    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 1, "max_cc": 1000, "base_rate": 20.00, "formula": None, "source": "JPJ Schedule (Non-Saloon)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 1001, "max_cc": 1200, "base_rate": 85.00, "formula": None, "source": "JPJ Schedule (Non-Saloon)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 1201, "max_cc": 1400, "base_rate": 100.00, "formula": None, "source": "JPJ Schedule (Non-Saloon)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 1401, "max_cc": 1600, "base_rate": 120.00, "formula": None, "source": "JPJ Schedule (Non-Saloon)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 1601, "max_cc": 1800, "base_rate": 300.00, "formula": "300 + ((cc - 1600) * 0.30)", "source": "JPJ Schedule (Non-Saloon)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 1801, "max_cc": 2000, "base_rate": 360.00, "formula": "360 + ((cc - 1800) * 0.40)", "source": "JPJ Schedule (Non-Saloon)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 2001, "max_cc": 2500, "base_rate": 440.00, "formula": "440 + ((cc - 2000) * 0.80)", "source": "JPJ Schedule (Non-Saloon)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 2501, "max_cc": 3000, "base_rate": 840.00, "formula": "840 + ((cc - 2500) * 1.60)", "source": "JPJ Schedule (Non-Saloon)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "West Malaysia", "min_cc": 3001, "max_cc": None, "base_rate": 1640.00, "formula": "1640 + ((cc - 3000) * 1.60)", "source": "JPJ Schedule (Non-Saloon)"},

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

    # Non-Saloon Car (SUV / MPV / 4x4 / Pickup / Van - Sabah)
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "Sabah", "min_cc": 1, "max_cc": 1000, "base_rate": 20.00, "formula": None, "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "Sabah", "min_cc": 1001, "max_cc": 1200, "base_rate": 68.00, "formula": None, "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "Sabah", "min_cc": 1201, "max_cc": 1400, "base_rate": 80.00, "formula": None, "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "Sabah", "min_cc": 1401, "max_cc": 1600, "base_rate": 96.00, "formula": None, "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "Sabah", "min_cc": 1601, "max_cc": 1800, "base_rate": 240.00, "formula": "240 + ((cc - 1600) * 0.24)", "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "Sabah", "min_cc": 1801, "max_cc": 2000, "base_rate": 288.00, "formula": "288 + ((cc - 1800) * 0.32)", "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "Sabah", "min_cc": 2001, "max_cc": 2500, "base_rate": 352.00, "formula": "352 + ((cc - 2000) * 0.64)", "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "Sabah", "min_cc": 2501, "max_cc": 3000, "base_rate": 672.00, "formula": "672 + ((cc - 2500) * 1.28)", "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "Sabah", "min_cc": 3001, "max_cc": None, "base_rate": 1312.00, "formula": "1312 + ((cc - 3000) * 1.28)", "source": "JPJ Schedule (Non-Saloon East MY)"},

    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 1, "max_cc": 1000, "base_rate": 20.00, "formula": None, "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 1001, "max_cc": 1200, "base_rate": 68.00, "formula": None, "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 1201, "max_cc": 1400, "base_rate": 80.00, "formula": None, "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 1401, "max_cc": 1600, "base_rate": 96.00, "formula": None, "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 1601, "max_cc": 1800, "base_rate": 240.00, "formula": "240 + ((cc - 1600) * 0.24)", "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 1801, "max_cc": 2000, "base_rate": 288.00, "formula": "288 + ((cc - 1800) * 0.32)", "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 2001, "max_cc": 2500, "base_rate": 352.00, "formula": "352 + ((cc - 2000) * 0.64)", "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 2501, "max_cc": 3000, "base_rate": 672.00, "formula": "672 + ((cc - 2500) * 1.28)", "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "Sabah", "min_cc": 3001, "max_cc": None, "base_rate": 1312.00, "formula": "1312 + ((cc - 3000) * 1.28)", "source": "JPJ Schedule (Non-Saloon East MY)"},

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

    # Non-Saloon Car (SUV / MPV / 4x4 / Pickup / Van - Sarawak)
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "Sarawak", "min_cc": 1, "max_cc": 1000, "base_rate": 20.00, "formula": None, "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "Sarawak", "min_cc": 1001, "max_cc": 1200, "base_rate": 68.00, "formula": None, "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "Sarawak", "min_cc": 1201, "max_cc": 1400, "base_rate": 80.00, "formula": None, "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "Sarawak", "min_cc": 1401, "max_cc": 1600, "base_rate": 96.00, "formula": None, "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "Sarawak", "min_cc": 1601, "max_cc": 1800, "base_rate": 240.00, "formula": "240 + ((cc - 1600) * 0.24)", "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "Sarawak", "min_cc": 1801, "max_cc": 2000, "base_rate": 288.00, "formula": "288 + ((cc - 1800) * 0.32)", "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "Sarawak", "min_cc": 2001, "max_cc": 2500, "base_rate": 352.00, "formula": "352 + ((cc - 2000) * 0.64)", "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "Sarawak", "min_cc": 2501, "max_cc": 3000, "base_rate": 672.00, "formula": "672 + ((cc - 2500) * 1.28)", "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "Sarawak", "min_cc": 3001, "max_cc": None, "base_rate": 1312.00, "formula": "1312 + ((cc - 3000) * 1.28)", "source": "JPJ Schedule (Non-Saloon East MY)"},

    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 1, "max_cc": 1000, "base_rate": 20.00, "formula": None, "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 1001, "max_cc": 1200, "base_rate": 68.00, "formula": None, "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 1201, "max_cc": 1400, "base_rate": 80.00, "formula": None, "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 1401, "max_cc": 1600, "base_rate": 96.00, "formula": None, "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 1601, "max_cc": 1800, "base_rate": 240.00, "formula": "240 + ((cc - 1600) * 0.24)", "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 1801, "max_cc": 2000, "base_rate": 288.00, "formula": "288 + ((cc - 1800) * 0.32)", "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 2001, "max_cc": 2500, "base_rate": 352.00, "formula": "352 + ((cc - 2000) * 0.64)", "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 2501, "max_cc": 3000, "base_rate": 672.00, "formula": "672 + ((cc - 2500) * 1.28)", "source": "JPJ Schedule (Non-Saloon East MY)"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "Sarawak", "min_cc": 3001, "max_cc": None, "base_rate": 1312.00, "formula": "1312 + ((cc - 3000) * 1.28)", "source": "JPJ Schedule (Non-Saloon East MY)"},

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

    # Non-Saloon Car (SUV / MPV / 4x4 / Pickup / Van - Labuan)
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "Labuan", "min_cc": 1, "max_cc": 1000, "base_rate": 10.00, "formula": None, "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "Labuan", "min_cc": 1001, "max_cc": 1200, "base_rate": 42.50, "formula": None, "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "Labuan", "min_cc": 1201, "max_cc": 1400, "base_rate": 50.00, "formula": None, "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "Labuan", "min_cc": 1401, "max_cc": 1600, "base_rate": 60.00, "formula": None, "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "Labuan", "min_cc": 1601, "max_cc": 1800, "base_rate": 150.00, "formula": "150 + ((cc - 1600) * 0.15)", "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "Labuan", "min_cc": 1801, "max_cc": 2000, "base_rate": 180.00, "formula": "180 + ((cc - 1800) * 0.20)", "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "Labuan", "min_cc": 2001, "max_cc": 2500, "base_rate": 220.00, "formula": "220 + ((cc - 2000) * 0.40)", "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "Labuan", "min_cc": 2501, "max_cc": 3000, "base_rate": 420.00, "formula": "420 + ((cc - 2500) * 0.80)", "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Individual", "jurisdiction": "Labuan", "min_cc": 3001, "max_cc": None, "base_rate": 820.00, "formula": "820 + ((cc - 3000) * 0.80)", "source": "JPJ Labuan Duty-Free Concession"},

    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "Labuan", "min_cc": 1, "max_cc": 1000, "base_rate": 10.00, "formula": None, "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "Labuan", "min_cc": 1001, "max_cc": 1200, "base_rate": 42.50, "formula": None, "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "Labuan", "min_cc": 1201, "max_cc": 1400, "base_rate": 50.00, "formula": None, "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "Labuan", "min_cc": 1401, "max_cc": 1600, "base_rate": 60.00, "formula": None, "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "Labuan", "min_cc": 1601, "max_cc": 1800, "base_rate": 150.00, "formula": "150 + ((cc - 1600) * 0.15)", "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "Labuan", "min_cc": 1801, "max_cc": 2000, "base_rate": 180.00, "formula": "180 + ((cc - 1800) * 0.20)", "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "Labuan", "min_cc": 2001, "max_cc": 2500, "base_rate": 220.00, "formula": "220 + ((cc - 2000) * 0.40)", "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "Labuan", "min_cc": 2501, "max_cc": 3000, "base_rate": 420.00, "formula": "420 + ((cc - 2500) * 0.80)", "source": "JPJ Labuan Duty-Free Concession"},
    {"vehicle_type": "NonSaloonCar", "owner_type": "Company", "jurisdiction": "Labuan", "min_cc": 3001, "max_cc": None, "base_rate": 820.00, "formula": "820 + ((cc - 3000) * 0.80)", "source": "JPJ Labuan Duty-Free Concession"},

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

# ── 6. Electric Vehicles (ZEV - Official JPJ 2026 Schedule) ───────────────────
_EV_RULES_TEMPLATE: list[dict[str, Any]] = []
for _jur in ("West Malaysia", "Sabah", "Sarawak", "Labuan"):
    for _owner in ("Individual", "Company"):
        for _vtype in ("EVSaloonCar", "EVNonSaloonCar"):
            _EV_RULES_TEMPLATE.extend([
                {"vehicle_type": _vtype, "owner_type": _owner, "jurisdiction": _jur, "min_cc": 1, "max_cc": 50000, "base_rate": 20.00, "formula": None, "source": "Official JPJ 2026 ZEV Structure"},
                {"vehicle_type": _vtype, "owner_type": _owner, "jurisdiction": _jur, "min_cc": 50001, "max_cc": 100000, "base_rate": 20.00, "formula": "20 + (ceil((cc - 50000) / 10000) * 10)", "source": "Official JPJ 2026 ZEV Structure"},
                {"vehicle_type": _vtype, "owner_type": _owner, "jurisdiction": _jur, "min_cc": 100001, "max_cc": 210000, "base_rate": 80.00, "formula": "80 + ((ceil((cc - 100000) / 10000) - 1) * 20)", "source": "Official JPJ 2026 ZEV Structure"},
                {"vehicle_type": _vtype, "owner_type": _owner, "jurisdiction": _jur, "min_cc": 210001, "max_cc": 310000, "base_rate": 305.00, "formula": "305 + ((ceil((cc - 210000) / 10000) - 1) * 30)", "source": "Official JPJ 2026 ZEV Structure"},
                {"vehicle_type": _vtype, "owner_type": _owner, "jurisdiction": _jur, "min_cc": 310001, "max_cc": 410000, "base_rate": 615.00, "formula": "615 + ((ceil((cc - 310000) / 10000) - 1) * 50)", "source": "Official JPJ 2026 ZEV Structure"},
                {"vehicle_type": _vtype, "owner_type": _owner, "jurisdiction": _jur, "min_cc": 410001, "max_cc": 510000, "base_rate": 1140.00, "formula": "1140 + ((ceil((cc - 410000) / 10000) - 1) * 100)", "source": "Official JPJ 2026 ZEV Structure"},
                {"vehicle_type": _vtype, "owner_type": _owner, "jurisdiction": _jur, "min_cc": 510001, "max_cc": 610000, "base_rate": 2165.00, "formula": "2165 + ((ceil((cc - 510000) / 10000) - 1) * 150)", "source": "Official JPJ 2026 ZEV Structure"},
                {"vehicle_type": _vtype, "owner_type": _owner, "jurisdiction": _jur, "min_cc": 610001, "max_cc": None, "base_rate": 3695.00, "formula": "3695 + ((ceil((cc - 610000) / 10000) - 1) * 200)", "source": "Official JPJ 2026 ZEV Structure"},
            ])
        # Electric Motorcycle
        _EV_RULES_TEMPLATE.extend([
            {"vehicle_type": "EVMotorcycle", "owner_type": _owner, "jurisdiction": _jur, "min_cc": 1, "max_cc": 7500, "base_rate": 2.00, "formula": None, "source": "Official JPJ 2026 ZEV Structure"},
            {"vehicle_type": "EVMotorcycle", "owner_type": _owner, "jurisdiction": _jur, "min_cc": 7501, "max_cc": 10000, "base_rate": 9.00, "formula": None, "source": "Official JPJ 2026 ZEV Structure"},
            {"vehicle_type": "EVMotorcycle", "owner_type": _owner, "jurisdiction": _jur, "min_cc": 10001, "max_cc": 12500, "base_rate": 12.00, "formula": None, "source": "Official JPJ 2026 ZEV Structure"},
            {"vehicle_type": "EVMotorcycle", "owner_type": _owner, "jurisdiction": _jur, "min_cc": 12501, "max_cc": 25000, "base_rate": 30.00, "formula": None, "source": "Official JPJ 2026 ZEV Structure"},
            {"vehicle_type": "EVMotorcycle", "owner_type": _owner, "jurisdiction": _jur, "min_cc": 25001, "max_cc": 40000, "base_rate": 40.00, "formula": None, "source": "Official JPJ 2026 ZEV Structure"},
            {"vehicle_type": "EVMotorcycle", "owner_type": _owner, "jurisdiction": _jur, "min_cc": 40001, "max_cc": None, "base_rate": 42.00, "formula": None, "source": "Official JPJ 2026 ZEV Structure"},
        ])

STANDARD_ROAD_TAX_RULES = STANDARD_ROAD_TAX_RULES + _EV_RULES_TEMPLATE


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
        base_rate_raw = item.get("base_rate")
        base_rate = float(base_rate_raw) if base_rate_raw is not None else 0.0
        min_cc_raw = item.get("min_cc")
        min_cc = int(min_cc_raw) if min_cc_raw is not None else 0
        max_cc_raw = item.get("max_cc")
        max_cc = int(max_cc_raw) if max_cc_raw is not None else None

        if existing:
            existing.max_cc = max_cc
            existing.base_rate = base_rate
            existing.formula = str(item["formula"]) if item.get("formula") is not None else None
            existing.source = str(item["source"]) if item.get("source") is not None else None
            existing.status = "active"
            updated += 1
        else:
            rule = RoadTaxRule(
                vehicle_type=str(item["vehicle_type"]),
                owner_type=str(item["owner_type"]),
                jurisdiction=str(item["jurisdiction"]),
                min_cc=min_cc,
                max_cc=max_cc,
                base_rate=base_rate,
                formula=str(item["formula"]) if item.get("formula") is not None else None,
                source=str(item["source"]) if item.get("source") is not None else None,
                effective_from=today,
                status="active",
            )
            db.add(rule)
            created += 1

    db.commit()
    return {"created": created, "updated": updated, "total": len(STANDARD_ROAD_TAX_RULES)}
