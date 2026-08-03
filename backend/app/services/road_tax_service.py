"""Road-tax rule management and matching."""

from __future__ import annotations

import logging
import re
from datetime import date

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
    return float(rule.base_rate)


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
    if "effective_from" in payload:
        rule.effective_from = date.fromisoformat(payload["effective_from"]) if isinstance(payload["effective_from"], str) else payload["effective_from"]
    if "effective_to" in payload and payload["effective_to"]:
        rule.effective_to = date.fromisoformat(payload["effective_to"]) if isinstance(payload["effective_to"], str) else payload["effective_to"]
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
        "base_rate": float(r.base_rate),
        "formula": r.formula,
        "source": r.source,
        "effective_from": r.effective_from.isoformat() if r.effective_from else None,
        "effective_to": r.effective_to.isoformat() if r.effective_to else None,
        "status": r.status,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
    }
