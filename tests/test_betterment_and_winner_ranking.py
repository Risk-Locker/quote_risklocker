"""Hermetic tests for Betterment engine, Towing normalizer, and 4-tier Best Deal ranking."""

from datetime import datetime, timezone
import pytest

from app.models.tables import TenureComparisonEntry
from app.services.marketing_comparison_service import (
    calculate_betterment_rate,
    calculate_vehicle_age,
    normalize_towing_km,
    rank_comparison_entries,
)


def test_calculate_vehicle_age():
    # 2020 YOM with 08 Feb 2026 = 6 completed years, Feb > Jan -> in 7th year -> 7 years
    age_feb = calculate_vehicle_age(2020, datetime(2026, 2, 8, tzinfo=timezone.utc))
    assert age_feb == 7

    # 2020 YOM with 01 Jan 2026 = exact 6 completed years -> 6 years
    age_jan1 = calculate_vehicle_age(2020, datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert age_jan1 == 6

    # 2023 YOM with 08 Feb 2026 = 3 completed years + 1 -> 4 years
    age_new = calculate_vehicle_age(2023, "2026-02-08")
    assert age_new == 4

    # Invalid / empty
    assert calculate_vehicle_age(None, "2026-02-08") == 0
    assert calculate_vehicle_age(0, "2026-02-08") == 0


def test_calculate_betterment_rate_standard():
    # < 5 years: 0% ("No (0%)")
    r0, d0 = calculate_betterment_rate(4, "Etiqa")
    assert r0 == 0.0
    assert d0 == "No (0%)"

    # 5 years: 15% ("Yes (15%)")
    r5, d5 = calculate_betterment_rate(5, "Allianz")
    assert r5 == 15.0
    assert d5 == "Yes (15%)"

    # 6 years: 20% ("Yes (20%)")
    r6, d6 = calculate_betterment_rate(6, "Zurich")
    assert r6 == 20.0
    assert d6 == "Yes (20%)"

    # 7 years: 25% ("Yes (25%)")
    r7, d7 = calculate_betterment_rate(7, "Etiqa")
    assert r7 == 25.0
    assert d7 == "Yes (25%)"

    # 8 years: 30% ("Yes (30%)")
    r8, d8 = calculate_betterment_rate(8, "Tune")
    assert r8 == 30.0
    assert d8 == "Yes (30%)"

    # 9 years: 35% ("Yes (35%)")
    r9, d9 = calculate_betterment_rate(9, "Berjaya Sompo")
    assert r9 == 35.0
    assert d9 == "Yes (35%)"

    # >= 10 years: 40% ("Yes (40%)")
    r10, d10 = calculate_betterment_rate(10, "MPI Generali")
    assert r10 == 40.0
    assert d10 == "Yes (40%)"

    r15, d15 = calculate_betterment_rate(15, "MPI Generali")
    assert r15 == 40.0
    assert d15 == "Yes (40%)"


def test_calculate_betterment_rate_qbe():
    # QBE rule: 0–10 years inclusive: 0% ("No (0%)")
    q0, dq0 = calculate_betterment_rate(4, "QBE Insurance (Malaysia) Berhad")
    assert q0 == 0.0
    assert dq0 == "No (0%)"

    q7, dq7 = calculate_betterment_rate(7, "QBE")
    assert q7 == 0.0
    assert dq7 == "No (0%)"

    q10, dq10 = calculate_betterment_rate(10, "QBE")
    assert q10 == 0.0
    assert dq10 == "No (0%)"

    # QBE rule: > 10 years: 40% ("Yes (40%)")
    q11, dq11 = calculate_betterment_rate(11, "QBE")
    assert q11 == 40.0
    assert dq11 == "Yes (40%)"


def test_normalize_towing_km():
    assert normalize_towing_km("Towing assistance up to 200km per event") == "200 km"
    assert normalize_towing_km("150 km free breakdown towing") == "150 km"
    assert normalize_towing_km("50km") == "50 km"
    assert normalize_towing_km("200") == "200 km"
    assert normalize_towing_km("Unlimited") == "Unlimited"
    assert normalize_towing_km("24-hr unlimited towing service") == "Unlimited"
    assert normalize_towing_km("", "Motor PA Plus 4 unlimited towing") == "Unlimited"


def test_rank_comparison_entries_4tier_and_single_winner():
    e1 = TenureComparisonEntry(
        id="1",
        company_name="Company A (Higher Price)",
        total_payable=1500.0,
        excess=0.0,
        betterment_rate=0.0,
        towing_km="Unlimited",
    )
    e2 = TenureComparisonEntry(
        id="2",
        company_name="Company B (Best Price)",
        total_payable=1200.0,
        excess=400.0,
        betterment_rate=25.0,
        towing_km="150 km",
    )
    e3 = TenureComparisonEntry(
        id="3",
        company_name="Company C (Same Price as B, but No Excess)",
        total_payable=1200.0,
        excess=0.0,
        betterment_rate=25.0,
        towing_km="150 km",
    )
    e4 = TenureComparisonEntry(
        id="4",
        company_name="Company D (Same Price & Excess as C, but Betterment is 0%)",
        total_payable=1200.0,
        excess=0.0,
        betterment_rate=0.0,
        towing_km="150 km",
    )
    e5 = TenureComparisonEntry(
        id="5",
        company_name="Company E (Same as D, but Unlimited Towing)",
        total_payable=1200.0,
        excess=0.0,
        betterment_rate=0.0,
        towing_km="Unlimited",
    )

    ranked = rank_comparison_entries([e1, e2, e3, e4, e5])

    # Rank 1 must be Company E (lowest price 1200, 0 excess, 0% betterment, Unlimited towing)
    assert ranked[0].id == "5"
    assert ranked[0].rank == 1
    assert ranked[0].is_recommended is True

    # Rank 2 must be Company D (150 km towing vs Unlimited)
    assert ranked[1].id == "4"
    assert ranked[1].rank == 2
    assert ranked[1].is_recommended is False

    # Rank 3 must be Company C (25% betterment vs 0%)
    assert ranked[2].id == "3"
    assert ranked[2].rank == 3
    assert ranked[2].is_recommended is False

    # Rank 4 must be Company B (400 excess vs 0)
    assert ranked[3].id == "2"
    assert ranked[3].rank == 4
    assert ranked[3].is_recommended is False

    # Rank 5 must be Company A (1500 price vs 1200)
    assert ranked[4].id == "1"
    assert ranked[4].rank == 5
    assert ranked[4].is_recommended is False

    # Invariant: exactly 1 winner recommended
    assert sum(1 for e in ranked if e.is_recommended) == 1
