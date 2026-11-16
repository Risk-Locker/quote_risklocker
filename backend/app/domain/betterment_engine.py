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

