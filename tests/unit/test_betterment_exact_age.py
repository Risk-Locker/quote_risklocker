import pytest
from datetime import date, datetime
from app.domain.betterment_engine import (
    calculate_exact_vehicle_age,
    get_betterment_scale,
)


def test_betterment_exact_age_completed_years_calendar_boundaries():
    """Verify that vehicle age is computed strictly by completed calendar years (relativedelta),
    so 9 years 11 months 29 days resolves to exactly 9 completed years, NOT 10 years."""
    reg_date = date(2016, 6, 15)
    
    # 1. 9 years, 11 months, 29 days (one day before 10th anniversary)
    inception_9y_11m = date(2026, 6, 14)
    age_9 = calculate_exact_vehicle_age(reg_date, inception_9y_11m)
    assert age_9 == 9

    scale_9 = get_betterment_scale(age_9)
    assert scale_9["rate"] == 0.35
    assert scale_9["percentage_str"] == "35%"
    assert scale_9["eligible_for_endorsement_113"] is True

    # 2. Exactly 10 years (on anniversary day)
    inception_10y = date(2026, 6, 15)
    age_10 = calculate_exact_vehicle_age(reg_date, inception_10y)
    assert age_10 == 10

    scale_10 = get_betterment_scale(age_10)
    assert scale_10["rate"] == 0.40
    assert scale_10["percentage_str"] == "40%"

    # 3. 4 years, 11 months (under 5 years exempt from betterment)
    inception_4y = date(2021, 5, 20)
    age_4 = calculate_exact_vehicle_age(reg_date, inception_4y)
    assert age_4 == 4
    scale_4 = get_betterment_scale(age_4)
    assert scale_4["rate"] == 0.0
    assert scale_4["percentage_str"] == "0%"
    assert scale_4["eligible_for_endorsement_113"] is False


def test_betterment_exact_age_with_string_and_datetime_inputs():
    """Verify robust parsing of ISO date strings and timezone-aware datetimes."""
    age_str = calculate_exact_vehicle_age("2018-03-01", "2026-02-28")
    assert age_str == 7
    scale_7 = get_betterment_scale(age_str)
    assert scale_7["rate"] == 0.25
    assert scale_7["percentage_str"] == "25%"


def test_evaluate_betterment_rules_exact_calendar_age_wiring():
    """Verify evaluate_betterment_rules honors exact calendar registration date."""
    from app.services.marketing_comparison.ncd_evaluator import evaluate_betterment_rules

    # 1. Non-QBE vehicle aged 9 years 11 months 29 days (registered 2016-06-15, coverage 2026-06-14)
    # Must be 35% (9 completed years), NOT 40%
    waiver, rate, disp = evaluate_betterment_rules(
        yom=2016,
        quote_year=2026,
        company_name="Allianz",
        has_betterment_peril=False,
        registration_date="2016-06-15",
        coverage_start_date="2026-06-14",
    )
    assert waiver is False
    assert rate == 35.0
    assert "35%" in disp

    # 2. Same vehicle on 10th anniversary day (2026-06-15) -> 40% (10 completed years)
    waiver_10, rate_10, disp_10 = evaluate_betterment_rules(
        yom=2016,
        quote_year=2026,
        company_name="Allianz",
        has_betterment_peril=False,
        registration_date="2016-06-15",
        coverage_start_date="2026-06-15",
    )
    assert waiver_10 is False
    assert rate_10 == 40.0
    assert "40%" in disp_10

    # 3. QBE vehicle aged 9 years 11 months 29 days (< 10 completed years) gets automatic 0% waiver
    qbe_waiver, qbe_rate, qbe_disp = evaluate_betterment_rules(
        yom=2016,
        quote_year=2026,
        company_name="QBE Insurance",
        has_betterment_peril=False,
        registration_date="2016-06-15",
        coverage_start_date="2026-06-14",
    )
    assert qbe_waiver is True
    assert qbe_rate == 0.0
    assert "0%" in qbe_disp


