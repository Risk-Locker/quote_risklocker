"""Hermetic tests for Betterment Waiver Rule Engine.

Covers:
1. Condition 1: 0 to 5 years (YOM + 4 > Quote Year) -> Waiver = YES -> 'Yes (0%)'
2. Condition 2.1: QBE Comprehensive Private Car (YOM + 9 > Current Year) -> Waiver = YES
3. Condition 2.2: Insurers without peril -> Waiver = NO -> 'No (X%)'
4. Condition 2.2: Tune, Sompo, AmAssurance, Etiqa with peril (YOM + 14 > Current Year)
5. Condition 2.2: Lonpac, STMB with peril (YOM + 9 > Current Year)
6. Peril detector check_has_betterment_peril
7. TPO / TPFT / MMIP bare 'No' mode, legacy display normalization, ranking, WhatsApp, and DB patch persistence
"""

from datetime import datetime, timezone
from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routers.comparison import UpdateComparisonEntryPatch, patch_comparison_entry
from app.domain.motor.winner_ranking_rules import (
    _entry_strengths,
    _format_prev_policy_yoy_insight,
    evaluate_logical_value_rerank,
)
from app.models.enums import AccountStatus, Role
from app.models.tables import (
    Base,
    CustomerAccount,
    InsuranceTenure,
    TenureComparisonEntry,
    TrackedVehicle,
    User,
    new_id,
)
from app.services.marketing_comparison.ncd_evaluator import (
    format_betterment_waiver_display,
    normalize_betterment_display,
    rank_comparison_entries,
)
from app.services.marketing_comparison.whatsapp_formatter import format_whatsapp_teaser_from_data
from app.services.marketing_comparison_service import (
    evaluate_betterment_rules,
    get_standard_betterment_rate,
    check_has_betterment_peril,
)


def test_condition_1_zero_to_five_years():
    """If YEAR OF MAKE + 4 > Quotation Year, then BETTERMENT WAIVER = YES (0% co-payment)."""
    # 2023 YOM, Quote Year 2026 -> 2023 + 4 = 2027 > 2026 -> YES
    has_waiver, rate, display = evaluate_betterment_rules(
        yom=2023,
        quote_year=2026,
        company_name="Allianz",
        has_betterment_peril=False,
    )
    assert has_waiver is True
    assert rate == 0.0
    assert display == "Yes (0%)"

    # 2024 YOM, Quote Year 2026 -> 2024 + 4 = 2028 > 2026 -> YES
    has_waiver, rate, display = evaluate_betterment_rules(
        yom=2024,
        quote_year=2026,
        company_name="Etiqa",
        has_betterment_peril=False,
    )
    assert has_waiver is True
    assert rate == 0.0
    assert display == "Yes (0%)"


def test_condition_1_older_cars_fall_through():
    """If YEAR OF MAKE + 4 <= Quotation Year, evaluates Condition 2."""
    # 2021 YOM, Quote Year 2026 -> 5 completed years -> tariff scale applies
    has_waiver, rate, display = evaluate_betterment_rules(
        yom=2021,
        quote_year=2026,
        company_name="Allianz",
        has_betterment_peril=False,
    )
    assert has_waiver is False
    assert rate == 15.0
    assert display == "No (15%)"


def test_condition_2_1_qbe_ten_year_rule():
    """QBE Comprehensive Private Car: if YOM + 9 > Current Year -> Waiver = YES, else NO."""
    curr_y = datetime.now().year
    # YOM 2018 in 2026 -> 2018 + 9 = 2027 > 2026 -> YES (no peril needed)
    has_waiver, rate, display = evaluate_betterment_rules(
        yom=curr_y - 8,
        quote_year=curr_y,
        company_name="QBE Comprehensive Private Car",
        has_betterment_peril=False,
    )
    assert has_waiver is True
    assert rate == 0.0
    assert display == "Yes (0%)"

    # YOM 2015 in 2026 -> 2015 + 9 = 2024 <= 2026 -> NO (tariff rate applied: 10y+ is 40%)
    has_waiver, rate, display = evaluate_betterment_rules(
        yom=curr_y - 11,
        quote_year=curr_y,
        company_name="QBE Insurance (Malaysia) Berhad",
        has_betterment_peril=False,
    )
    assert has_waiver is False
    assert rate == 40.0
    assert display == "No (40%)"


def test_condition_2_2_other_insurers_without_peril():
    """If not QBE and NO betterment perils added -> Waiver = NO (tariff scale)."""
    curr_y = datetime.now().year
    # Etiqa YOM curr_y - 7, 7y vehicle, no peril -> Waiver = NO (25%)
    has_waiver, rate, display = evaluate_betterment_rules(
        yom=curr_y - 7,
        quote_year=curr_y,
        company_name="Etiqa General Insurance",
        has_betterment_peril=False,
    )
    assert has_waiver is False
    assert rate == 25.0
    assert display == "No (25%)"

    # Berjaya Sompo YOM curr_y - 8, 8y vehicle, no peril -> Waiver = NO (30%)
    has_waiver, rate, display = evaluate_betterment_rules(
        yom=curr_y - 8,
        quote_year=curr_y,
        company_name="Berjaya Sompo",
        has_betterment_peril=False,
    )
    assert has_waiver is False
    assert rate == 30.0
    assert display == "No (30%)"


def test_condition_2_2_tune_sompo_amassurance_etiqa_with_peril():
    """For (TUNE, SOMPO, AMASSURANCE, ETIQA): universal 10-year inclusive cap when peril added."""
    curr_y = datetime.now().year
    for company in ["Tune Insurance", "Berjaya Sompo Insurance", "AmAssurance Berhad", "Etiqa Auto360"]:
        # Completed age 9 (<= 10) -> Yes (0%)
        has_waiver, rate, display = evaluate_betterment_rules(
            yom=curr_y - 9,
            quote_year=curr_y,
            company_name=company,
            has_betterment_peril=True,
        )
        assert has_waiver is True, f"Failed for {company}"
        assert rate == 0.0, f"Failed for {company}"
        assert display == "Yes (0%)", f"Failed for {company}"

        # Completed age 10 (inclusive <= 10) -> Yes (0%)
        has_waiver, rate, display = evaluate_betterment_rules(
            yom=curr_y - 10,
            quote_year=curr_y,
            company_name=company,
            has_betterment_peril=True,
        )
        assert has_waiver is True, f"Failed for {company}"
        assert rate == 0.0, f"Failed for {company}"
        assert display == "Yes (0%)", f"Failed for {company}"

        # Completed age 11 (> 10, 11th year) -> No (40%)
        has_waiver, rate, display = evaluate_betterment_rules(
            yom=curr_y - 11,
            quote_year=curr_y,
            company_name=company,
            has_betterment_peril=True,
        )
        assert has_waiver is False, f"Failed for {company}"
        assert rate == 40.0, f"Failed for {company}"
        assert display == "No (40%)", f"Failed for {company}"


def test_condition_2_2_lonpac_stmb_with_peril():
    """For (LONPAC, STMB): inclusive 10-year cap when peril added."""
    curr_y = datetime.now().year
    for company in ["Lonpac Insurance", "Syarikat Takaful Malaysia Berhad (STMB)"]:
        # Completed age 8 (<= 10) -> Yes (0%)
        has_waiver, rate, display = evaluate_betterment_rules(
            yom=curr_y - 8,
            quote_year=curr_y,
            company_name=company,
            has_betterment_peril=True,
        )
        assert has_waiver is True, f"Failed for {company}"
        assert rate == 0.0, f"Failed for {company}"
        assert display == "Yes (0%)", f"Failed for {company}"

        # Completed age 10 (inclusive <= 10) -> Yes (0%)
        has_waiver, rate, display = evaluate_betterment_rules(
            yom=curr_y - 10,
            quote_year=curr_y,
            company_name=company,
            has_betterment_peril=True,
        )
        assert has_waiver is True, f"Failed for {company}"
        assert rate == 0.0, f"Failed for {company}"
        assert display == "Yes (0%)", f"Failed for {company}"

        # Completed age 11 (> 10, 11th year) -> No (40%)
        has_waiver, rate, display = evaluate_betterment_rules(
            yom=curr_y - 11,
            quote_year=curr_y,
            company_name=company,
            has_betterment_peril=True,
        )
        assert has_waiver is False, f"Failed for {company}"
        assert rate == 40.0, f"Failed for {company}"
        assert display == "No (40%)", f"Failed for {company}"


def test_check_has_betterment_peril():
    """Tests peril keyword detection across structured benefits and OCR text."""
    # Matches in structured fields
    assert check_has_betterment_peril(f={"benefit_name": "Waiver of Betterment"}) is True
    assert check_has_betterment_peril(f={"peril": "car spare parts waiver of betterment"}) is True
    assert check_has_betterment_peril(combined_text="Waiver of betterment contribution") is True
    assert check_has_betterment_peril(combined_text="Endorsement 111: Betterment Waiver Included") is True

    # Explicit flag
    assert check_has_betterment_peril(raw_w="Yes") is True
    assert check_has_betterment_peril(raw_w=True) is True
    assert check_has_betterment_peril(raw_w="No") is False

    # Negative case
    assert check_has_betterment_peril(f={"title": "Windscreen Coverage", "cost": "150.0"}) is False
    assert check_has_betterment_peril(combined_text="Standard comprehensive coverage with towing 200km") is False


def test_evaluate_betterment_rules_tpo_and_tpft_return_bare_no():
    for cov in ("Third Party", "TPO", "Third Party Only", "Third Party Fire & Theft", "TPFT", "Comprehensive Lite (TPFT)"):
        assert evaluate_betterment_rules(
            yom=2024,
            quote_year=2026,
            company_name="Etiqa",
            has_betterment_peril=True,
            coverage_type=cov,
        ) == (False, None, "No")

    assert evaluate_betterment_rules(
        yom=2024, quote_year=2026, company_name="MMIP", has_betterment_peril=False, coverage_type="Comprehensive"
    ) == (False, None, "No")

    # 30-year Comprehensive car still incurs 40% co-payment
    assert evaluate_betterment_rules(
        yom=1996, quote_year=2026, company_name="Etiqa", has_betterment_peril=True, coverage_type="Comprehensive"
    ) == (False, 40.0, "No (40%)")


def test_normalize_and_format_betterment_display():
    assert format_betterment_waiver_display(True, 0.0) == "Yes (0%)"
    assert format_betterment_waiver_display(False, None) == "No"
    assert format_betterment_waiver_display(False, 30.0) == "No (30%)"
    assert normalize_betterment_display("No (0%)", True, 0.0) == "Yes (0%)"
    assert normalize_betterment_display("Yes (0%)", True, 0.0) == "Yes (0%)"
    assert normalize_betterment_display("Yes (30%)", False, 30.0) == "No (30%)"
    assert normalize_betterment_display("No (30%)", False, 30.0) == "No (30%)"
    assert normalize_betterment_display("N/A (Third Party)", False, 0.0) == "No"
    assert normalize_betterment_display("No", False, None) == "No"
    assert normalize_betterment_display(None, False, None) == "No"


def test_ranking_does_not_reward_bare_no_as_waiver():
    waived = SimpleNamespace(
        id="e-waived",
        company_name="QBE",
        total_payable=1200.0,
        excess=0.0,
        agreed_value=False,
        valuation_type="market_value",
        towing_km="RM 500",
        towing_limit="RM 500",
        special_perils="",
        waiver_betterment=True,
        betterment_rate=0.0,
        betterment_display="Yes (0%)",
        manual_rank=None,
        is_hidden=False,
        rank=1,
        notes="",
        is_recommended=False,
    )
    bare_no = SimpleNamespace(
        id="e-no",
        company_name="MMIP",
        total_payable=1200.0,
        excess=0.0,
        agreed_value=False,
        valuation_type="market_value",
        towing_km="No towing",
        towing_limit="No towing",
        special_perils="",
        waiver_betterment=False,
        betterment_rate=None,
        betterment_display="No",
        manual_rank=None,
        is_hidden=False,
        rank=2,
        notes="",
        is_recommended=False,
    )

    assert "Betterment Waiver (0%)" in _entry_strengths(waived)
    assert "Betterment Waiver (0%)" not in _entry_strengths(bare_no)
    assert "Betterment Waiver (0%)" not in _format_prev_policy_yoy_insight(
        bare_no,
        {"insurance_premium": 1300.0, "total_payable": 1300.0, "waiver_betterment": False},
    )

    ranked = rank_comparison_entries([bare_no, waived], auto_recommend_rank1=False)
    assert ranked[0].id == "e-waived"
    assert ranked[0].rank == 1
    assert ranked[1].id == "e-no"
    assert ranked[1].rank == 2

    reranked = evaluate_logical_value_rerank([bare_no, waived])
    assert reranked[0].id == "e-waived"


def test_whatsapp_teaser_uses_betterment_waiver_and_display():
    msg = format_whatsapp_teaser_from_data(
        {
            "tenure": {
                "vehicle_no": "VAA1234",
                "customer_name": "Ali",
                "vehicle_model": "Proton Saga",
                "engine_cc": "1332 cc",
                "coverage_period_formatted": "01/01/2026 - 31/12/2026",
                "ncd_percentage": 55.0,
                "fixed_costs_total": 70.0,
            },
            "entries": [
                {
                    "company_name": "Etiqa",
                    "sum_insured": 30000.0,
                    "agreed_value": True,
                    "motor_premium": 900.0,
                    "total_payable": 970.0,
                    "towing_limit": "200 km",
                    "waiver_betterment": False,
                    "betterment_display": "No (30%)",
                    "excess": 0.0,
                    "is_recommended": True,
                }
            ],
        }
    )
    assert "Betterment Waiver: No (30%)" in msg
    assert "Waiver of Betterment:" not in msg


def test_patch_comparison_entry_betterment_modes_persist():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    uid = new_id()
    cid = new_id()
    vid = new_id()
    tid = new_id()
    eid = new_id()

    with SessionLocal() as db:
        user = User(
            id=uid,
            email="staff@example.com",
            name="Staff",
            password_hash="x",
            role=Role.STAFF.value,
            status=AccountStatus.ACTIVE.value,
        )
        cust = CustomerAccount(id=cid, canonical_name="Ali", id_number="900101-10-1234")
        veh = TrackedVehicle(id=vid, vehicle_no="VAA1234", manufacture_year=2018, customer_id=cid)
        tenure = InsuranceTenure(
            id=tid,
            tracked_vehicle_id=vid,
            customer_id=cid,
            customer_name="Ali",
            vehicle_no="VAA1234",
            coverage_start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            coverage_end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
            expiry_month="2026-12",
        )
        entry = TenureComparisonEntry(
            id=eid,
            tenure_id=tid,
            company_name="Etiqa",
            sum_insured=30000.0,
            motor_premium=900.0,
            total_payable=900.0,
            waiver_betterment=False,
            betterment_rate=30.0,
            betterment_display="No (30%)",
            manual_overrides=[],
        )
        db.add_all([user, cust, veh, tenure, entry])
        db.commit()

        res_no = patch_comparison_entry(
            tid, eid, UpdateComparisonEntryPatch(betterment_mode="no"), db=db, user=user
        )
        assert res_no["waiver_betterment"] is False
        assert res_no["betterment_rate"] is None
        assert res_no["betterment_display"] == "No"
        assert res_no["betterment_is_auto"] is False

        res_copay = patch_comparison_entry(
            tid,
            eid,
            UpdateComparisonEntryPatch(betterment_mode="copay", waiver_betterment=False, betterment_rate=40),
            db=db,
            user=user,
        )
        assert res_copay["waiver_betterment"] is False
        assert res_copay["betterment_rate"] == 40.0
        assert res_copay["betterment_display"] == "No (40%)"

        res_waived = patch_comparison_entry(
            tid,
            eid,
            UpdateComparisonEntryPatch(betterment_mode="waived", waiver_betterment=True, betterment_rate=0),
            db=db,
            user=user,
        )
        assert res_waived["waiver_betterment"] is True
        assert res_waived["betterment_rate"] == 0.0
        assert res_waived["betterment_display"] == "Yes (0%)"

        res_auto = patch_comparison_entry(
            tid, eid, UpdateComparisonEntryPatch(betterment_mode="auto"), db=db, user=user
        )
        assert res_auto["betterment_is_auto"] is True

    with SessionLocal() as fresh_db:
        persisted = fresh_db.get(TenureComparisonEntry, eid)
        assert persisted is not None
        assert persisted.betterment_display == "No (30%)"
        assert float(persisted.betterment_rate) == 30.0
        assert persisted.waiver_betterment is False
