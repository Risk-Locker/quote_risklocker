"""Integration tests for Milestone 2: Pricing Precision and Staff Freedom.

Verifies:
1. Database and service support for include_road_tax and include_runner_fee toggles.
2. Net total payable and fixed cost synchronization across tenure entries.
3. Authoritative BNM 5-cent cash rounding parity across exact and rounded outputs.
4. Fast quote / manual entry saving with fixed cost inheritance.
"""

from datetime import datetime, timezone
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.tables import (
    Base,
    InsuranceCompany,
    InsuranceTenure,
    Session as SessionModel,
    TenureComparisonEntry,
    TrackedVehicle,
    User,
    new_id,
)
from app.services.marketing_comparison_service import (
    get_marketing_comparison,
    save_comparison_entry,
    update_tenure_fixed_costs,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def _seed_test_tenure(db: Session) -> tuple[InsuranceTenure, InsuranceCompany]:
    owner = User(
        id=new_id(),
        email="agent@risklocker.test",
        name="Staff Agent",
        password_hash="mock",
        role="agent",
    )
    db.add(owner)

    vehicle = TrackedVehicle(
        id=new_id(),
        vehicle_no="WXY1234",
        car_brand="Honda",
        car_model="Civic 1.5 Turbo",
        engine_cc="1498 CC",
    )
    db.add(vehicle)

    company = InsuranceCompany(
        id=new_id(),
        name="AmAssurance",
        slug="amassurance",
    )
    db.add(company)

    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=vehicle.id,
        vehicle_no="WXY1234",
        customer_name="Ahmad bin Ali",
        coverage_start_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 5, 31, tzinfo=timezone.utc),
        expiry_month="2027-05",
        status="sourced",
        road_tax=90.00,
        runner_fee=50.00,
        include_road_tax=True,
        include_runner_fee=True,
        quotation_discount=0.00,
        ncd_percentage=55.0,
    )
    db.add(tenure)
    db.commit()
    db.refresh(tenure)
    return tenure, company


def test_include_road_tax_and_runner_fee_toggles(db_session: Session):
    """Test excluding and including road tax and runner fees updates entries correctly."""
    tenure, company = _seed_test_tenure(db_session)

    # Add a comparison entry with motor_premium = 1200.12
    entry = TenureComparisonEntry(
        id=new_id(),
        tenure_id=tenure.id,
        company_id=company.id,
        company_name="AmAssurance",
        sum_insured=50000.00,
        motor_premium=1200.12,
        road_tax=90.00,
        runner_fee=50.00,
        include_road_tax=True,
        include_runner_fee=True,
        total_payable=1340.12,
        towing_limit="365km",
        agreed_value=True,
        waiver_betterment=True,
        excess=0.00,
        is_manual=True,
    )
    db_session.add(entry)
    db_session.commit()

    # 1. Default: Both included
    data = get_marketing_comparison(db_session, tenure.id)
    entry_data = data["entries"][0]
    assert entry_data["road_tax"] == 90.00
    assert entry_data["runner_fee"] == 50.00
    assert entry_data["exact_total_payable"] == pytest.approx(1340.12, rel=1e-3)
    # BNM 5-cent rounding on 1340.12 (ends in 2 cents -> round down to 1340.10)
    assert entry_data["bnm_5cent_total_payable"] == 1340.10

    # 2. Exclude Road Tax (e.g. self-renewing client or lorry road tax handled separately)
    update_tenure_fixed_costs(
        db_session,
        tenure.id,
        road_tax=90.00,
        runner_fee=50.00,
        include_road_tax=False,
        include_runner_fee=True,
    )

    data = get_marketing_comparison(db_session, tenure.id)
    assert data["tenure"]["include_road_tax"] is False
    assert data["tenure"]["include_runner_fee"] is True
    entry_data = data["entries"][0]
    assert entry_data["road_tax"] == 0.00
    assert entry_data["runner_fee"] == 50.00
    assert entry_data["exact_total_payable"] == pytest.approx(1250.12, rel=1e-3)
    assert entry_data["bnm_5cent_total_payable"] == 1250.10

    # 3. Exclude Both Road Tax and Runner Fee
    update_tenure_fixed_costs(
        db_session,
        tenure.id,
        road_tax=90.00,
        runner_fee=50.00,
        include_road_tax=False,
        include_runner_fee=False,
    )

    data = get_marketing_comparison(db_session, tenure.id)
    assert data["tenure"]["include_road_tax"] is False
    assert data["tenure"]["include_runner_fee"] is False
    entry_data = data["entries"][0]
    assert entry_data["road_tax"] == 0.00
    assert entry_data["runner_fee"] == 0.00
    # Total payable is strictly motor premium only
    assert entry_data["exact_total_payable"] == pytest.approx(1200.12, rel=1e-3)
    assert entry_data["bnm_5cent_total_payable"] == 1200.10

    # 4. Re-enable both
    update_tenure_fixed_costs(
        db_session,
        tenure.id,
        road_tax=90.00,
        runner_fee=50.00,
        include_road_tax=True,
        include_runner_fee=True,
    )

    data = get_marketing_comparison(db_session, tenure.id)
    entry_data = data["entries"][0]
    assert entry_data["road_tax"] == 90.00
    assert entry_data["runner_fee"] == 50.00
    assert entry_data["exact_total_payable"] == pytest.approx(1340.12, rel=1e-3)


def test_bnm_5cent_cash_rounding_comparison_parity(db_session: Session):
    """Verify BNM 5-cent rounding outputs across diverse cents endings (1 through 9)."""
    tenure, company = _seed_test_tenure(db_session)

    # Test cases: (raw_premium, expected_exact_total, expected_bnm_5c_total)
    # With road_tax=90.00 and runner_fee=50.00 (sum=140.00)
    test_cases = [
        (4530.15, 4670.15, 4670.15),  # Ends in 5 -> stays 5
        (4530.11, 4670.11, 4670.10),  # Ends in 1 -> round down to 0
        (4530.12, 4670.12, 4670.10),  # Ends in 2 -> round down to 0
        (4530.13, 4670.13, 4670.15),  # Ends in 3 -> round up to 5
        (4530.14, 4670.14, 4670.15),  # Ends in 4 -> round up to 5
        (4530.16, 4670.16, 4670.15),  # Ends in 6 -> round down to 5
        (4530.17, 4670.17, 4670.15),  # Ends in 7 -> round down to 5
        (4530.18, 4670.18, 4670.20),  # Ends in 8 -> round up to 10
        (4530.19, 4670.19, 4670.20),  # Ends in 9 -> round up to 10
    ]

    for prem, exp_exact, exp_bnm in test_cases:
        entry = TenureComparisonEntry(
            id=new_id(),
            tenure_id=tenure.id,
            company_id=company.id,
            company_name="AmAssurance",
            sum_insured=60000.00,
            motor_premium=prem,
            road_tax=90.00,
            runner_fee=50.00,
            total_payable=exp_exact,
            towing_limit="365km",
            is_manual=True,
        )
        db_session.add(entry)
        db_session.commit()

        data = get_marketing_comparison(db_session, tenure.id)
        # Find this entry
        saved = next(e for e in data["entries"] if e["id"] == entry.id)
        assert saved["exact_total_payable"] == pytest.approx(exp_exact, rel=1e-3)
        assert saved["bnm_5cent_total_payable"] == pytest.approx(exp_bnm, rel=1e-3)

        # Cleanup for next iteration
        db_session.delete(entry)
        db_session.commit()


def test_fast_quote_entry_saving(db_session: Session):
    """Verify adding manual fast quote via save_comparison_entry inherits tenure fixed costs."""
    tenure, company = _seed_test_tenure(db_session)

    payload = {
        "company_name": "Lonpac Insurance",
        "sum_insured": 85000.00,
        "motor_premium": 2150.34,
        "towing_limit": "RM400",
        "valuation_type": "agreed_value",
        "agreed_value": True,
        "waiver_betterment": False,
        "excess": 0.00,
        "is_manual": True,
    }

    res = save_comparison_entry(db_session, tenure.id, payload)
    assert res is not None

    data = get_marketing_comparison(db_session, tenure.id)
    entry = next(e for e in data["entries"] if e["company_name"] == "Lonpac Insurance")
    assert entry["sum_insured"] == 85000.00
    assert entry["motor_premium"] == 2150.34
    assert entry["towing_limit"] == "RM400"
    # Tenure has road_tax=90, runner_fee=50 -> 2150.34 + 140 = 2290.34
    assert entry["exact_total_payable"] == pytest.approx(2290.34, rel=1e-3)
    # BNM 5¢: 2290.34 (ends in 4) -> 2290.35
    assert entry["bnm_5cent_total_payable"] == pytest.approx(2290.35, rel=1e-3)

