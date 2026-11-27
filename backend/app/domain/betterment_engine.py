"""Domain engine for exact vehicle age and Malaysian PIAM Betterment scale calculations.

Enforces:
- Exact calendar date difference using relativedelta (completed calendar years).
  A vehicle aged 9 years 11 months 29 days is strictly 9 completed years (35% scale),
  NOT 10 years (40% scale).
- Standard PIAM Betterment Co-Payment Scale:
  < 5 years: 0% (Exempt)
  5 years: 15%
  6 years: 20%
  7 years: 25%
  8 years: 30%
  9 years: 35%
  10+ years: 40%
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import re
from typing import Any
from dateutil.relativedelta import relativedelta


def _to_date(val: date | datetime | str | None) -> date | None:
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        val = val.strip().split("T")[0]
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(val, fmt).date()
            except ValueError:
                pass
    return None


def calculate_exact_vehicle_age(
    registration_date: date | datetime | str | None,
    inception_date: date | datetime | str | None = None,
) -> int:
    """Calculate completed vehicle age in years from registration date to policy inception date.

    Uses exact calendar relativedelta:
    2016-06-15 to 2026-06-14 -> 9 completed years.
    2016-06-15 to 2026-06-15 -> 10 completed years.
    """
    dt_reg = _to_date(registration_date)
    if dt_reg is None:
        return 0

    dt_inc = _to_date(inception_date)
    if dt_inc is None:
        dt_inc = datetime.now(timezone.utc).date()

    if dt_inc < dt_reg:
        return 0

    delta = relativedelta(dt_inc, dt_reg)
    return max(0, delta.years)


def resolve_vehicle_age_years(
    registration_date: date | datetime | str | None = None,
    yom: int | str | None = None,
    inception_date: date | datetime | str | None = None,
    quote_year: int | None = None,
) -> int | None:
    """Resolve completed vehicle age in years from registration date or manufacture year."""
    dt_inc = _to_date(inception_date)
    eff_quote_year = dt_inc.year if dt_inc else (quote_year or datetime.now(timezone.utc).year)

    dt_reg = _to_date(registration_date)
    if dt_reg is not None:
        return calculate_exact_vehicle_age(dt_reg, dt_inc or date(eff_quote_year, 1, 1))

    yom_int: int | None = None
    if yom is not None:
        digits = re.sub(r"[^\d]", "", str(yom).strip())
        if len(digits) == 4:
            parsed = int(digits)
            if 1900 < parsed <= 2100:
                yom_int = parsed
    if yom_int is not None:
        return max(0, eff_quote_year - yom_int)
    return None


def _draft_field_str(fields: dict | None, *keys: str) -> str:
    if not isinstance(fields, dict):
        return ""
    for key in keys:
        raw = fields.get(key)
        val = raw.get("value") if isinstance(raw, dict) else raw
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def resolve_draft_vehicle_age(
    draft: Any,
    session: Any = None,
    tenure: Any = None,
) -> int | None:
    """Resolve completed vehicle age from draft fields with tracked_vehicle.manufacture_year fallback."""
    fields = getattr(draft, "fields", None) if draft is not None else None
    reg_date = _draft_field_str(fields, "registration_date", "reg_date")
    yom_raw: Any = _draft_field_str(
        fields,
        "vehicle_year",
        "year_of_manufacture",
        "manufacture_year",
        "yom",
    )
    if not yom_raw and session is not None:
        tv = getattr(session, "tracked_vehicle", None)
        if tv is not None and getattr(tv, "manufacture_year", None):
            yom_raw = tv.manufacture_year
    if not yom_raw and tenure is not None:
        tv = getattr(tenure, "tracked_vehicle", None)
        if tv is not None and getattr(tv, "manufacture_year", None):
            yom_raw = tv.manufacture_year

    inc_date: Any = _draft_field_str(fields, "cover_start_date", "coverage_start_date", "inception_date")
    if not inc_date and session is not None:
        inc_date = getattr(session, "coverage_start_date", None)
    if not inc_date and tenure is not None:
        inc_date = getattr(tenure, "coverage_start_date", None)
    if not inc_date:
        period_val = _draft_field_str(fields, "cover_period")
        if " to " in period_val:
            inc_date = period_val.split(" to ", 1)[0].strip()

    return resolve_vehicle_age_years(
        registration_date=reg_date or None,
        yom=yom_raw or None,
        inception_date=inc_date,
    )


def evaluate_betterment_catalog_eligibility(
    veh_age: int | None,
    *,
    company_name: str | None = None,
    company_obj: Any = None,
    coverage_type: str | None = None,
    is_commercial_or_moto: bool = False,
) -> dict[str, Any]:
    """Return authoritative Box 1 / Box 2 / Hidden placement for Waiver of Betterment from DB rules."""
    from app.services.marketing_comparison.company_rules import resolve_company_betterment_policy

    policy = resolve_company_betterment_policy(company_name=company_name, company_obj=company_obj)
    auto_waive = bool(policy["auto_waive_without_peril"])
    allow_purchase = bool(policy["allow_addon_purchase"])
    free_years = int(policy["free_exemption_years"])
    max_years = int(policy["max_waiver_years"])
    default_disp = str(policy["default_display"])
    free_disp = str(policy["free_display"])

    cov_clean = re.sub(
        r"\bcomprehensive\b(?=\s+(?:lite|plus)\s*\(\s*(?:tpft|tpo|third\s+party))",
        "",
        str(coverage_type or "").strip().lower(),
        flags=re.IGNORECASE,
    ).strip()
    is_non_comp = cov_clean in {
        "third party",
        "tpo",
        "tp",
        "third_party",
        "third party only",
        "tpft",
        "third_party_fire_theft",
    } or any(
        tok in cov_clean
        for tok in ("third party", "third_party", "tpo", "tpft", "fire & theft", "fire and theft")
    )

    base = {
        "veh_age": veh_age,
        "auto_waive": auto_waive,
        "allow_addon_purchase": allow_purchase,
        "free_exemption_years": free_years,
        "max_waiver_years": max_years,
    }

    if is_non_comp or is_commercial_or_moto or max_years <= 0:
        return {**base, "placement": "hidden", "eligible": False, "display_value": None, "description": None}

    if veh_age is not None and veh_age > max_years:
        return {**base, "placement": "hidden", "eligible": False, "display_value": None, "description": None}

    if auto_waive:
        return {
            **base,
            "placement": "box1_free",
            "eligible": True,
            "display_value": default_disp,
            "description": f"0% betterment deduction on new original replacement parts for vehicles up to {max_years} years old.",
        }

    if veh_age is not None and free_years > 0 and veh_age < free_years:
        return {
            **base,
            "placement": "box1_free",
            "eligible": True,
            "display_value": free_disp,
            "description": f"Automatic betterment exemption for vehicles under {free_years} years old under standard Malaysian motor tariff.",
        }

    if allow_purchase:
        return {
            **base,
            "placement": "box2_optional",
            "eligible": True,
            "display_value": default_disp,
            "description": f"Waives betterment contribution on new original replacement parts for vehicles up to {max_years} years old.",
        }

    return {**base, "placement": "hidden", "eligible": False, "display_value": None, "description": None}


def resolve_draft_betterment_policy_context(
    db: Any,
    draft: Any,
    *,
    company: Any = None,
) -> dict[str, Any] | None:
    """Resolve DB-driven betterment eligibility context for workspace cards and PDF generation."""
    if draft is None:
        return None
    from sqlalchemy import select
    from app.models.tables import InsuranceCompany, InsuranceProduct, InsuranceTenure, Session as SessionModel, TrackedVehicle

    comp_obj = company or getattr(draft, "company", None)
    if comp_obj is None and getattr(draft, "company_id", None) and hasattr(db, "get"):
        try:
            comp_obj = db.get(InsuranceCompany, draft.company_id)
        except Exception:
            comp_obj = None

    session_obj = None
    tenure_obj = None
    if getattr(draft, "id", None) and hasattr(db, "scalar"):
        try:
            session_obj = db.scalar(select(SessionModel).where(SessionModel.draft_id == draft.id))
            if session_obj and getattr(session_obj, "tenure_id", None) and hasattr(db, "get"):
                tenure_obj = db.get(InsuranceTenure, session_obj.tenure_id)
            if session_obj and getattr(session_obj, "tracked_vehicle_id", None) and hasattr(db, "get"):
                if getattr(session_obj, "tracked_vehicle", None) is None:
                    tv = db.get(TrackedVehicle, session_obj.tracked_vehicle_id)
                    if tv is not None:
                        session_obj.tracked_vehicle = tv
        except Exception:
            session_obj = None
            tenure_obj = None

    fields = getattr(draft, "fields", None) or {}
    comp_name = (getattr(comp_obj, "name", None) if comp_obj else None) or _draft_field_str(fields, "insurance_company")
    if session_obj and not comp_name:
        comp_name = getattr(session_obj, "detected_company", None) or ""

    prod_obj = getattr(draft, "product", None)
    if prod_obj is None and getattr(draft, "product_id", None) and hasattr(db, "get"):
        try:
            prod_obj = db.get(InsuranceProduct, draft.product_id)
        except Exception:
            prod_obj = None

    prod_name = str(getattr(prod_obj, "name", None) or _draft_field_str(fields, "product_name") or "").lower()
    vtype_str = _draft_field_str(fields, "vehicle_type", "vehicle_category", "vehicle_class").lower()
    ctype_str = _draft_field_str(fields, "client_type").lower()
    cov_type = _draft_field_str(fields, "coverage_type", "coverage", "policy_type")
    if not cov_type and ("third party" in prod_name or "tpft" in prod_name or "tpo" in prod_name):
        cov_type = prod_name

    combined_scope = f"{prod_name} {vtype_str} {ctype_str}"
    is_commercial_or_moto = any(
        tok in combined_scope
        for tok in ("motorcycle", "motor cycle", "motosikal", "bike", "lorry", "truck", "commercial", "company", "haulage", "c permit", "a permit")
    )

    veh_age = resolve_draft_vehicle_age(draft, session=session_obj, tenure=tenure_obj)
    return evaluate_betterment_catalog_eligibility(
        veh_age,
        company_name=comp_name or None,
        company_obj=comp_obj,
        coverage_type=cov_type or None,
        is_commercial_or_moto=is_commercial_or_moto,
    )


def get_betterment_scale(completed_years: int) -> dict[str, Any]:
    """Return the PIAM tariff standard betterment co-payment rate for vehicle age in completed years."""
    if completed_years < 5:
        rate = 0.0
        eligible = False
        desc = "Exempt from betterment deduction (< 5 years old)"
    elif completed_years == 5:
        rate = 0.15
        eligible = True
        desc = "15% Betterment Scale (5 completed years)"
    elif completed_years == 6:
        rate = 0.20
        eligible = True
        desc = "20% Betterment Scale (6 completed years)"
    elif completed_years == 7:
        rate = 0.25
        eligible = True
        desc = "25% Betterment Scale (7 completed years)"
    elif completed_years == 8:
        rate = 0.30
        eligible = True
        desc = "30% Betterment Scale (8 completed years)"
    elif completed_years == 9:
        rate = 0.35
        eligible = True
        desc = "35% Betterment Scale (9 completed years)"
    else:
        rate = 0.40
        eligible = True
        desc = f"40% Betterment Scale ({completed_years} completed years)"

    pct_str = f"{int(rate * 100)}%"
    return {
        "completed_years": completed_years,
        "rate": rate,
        "percentage_str": pct_str,
        "eligible_for_endorsement_113": eligible,
        "description": desc,
    }

