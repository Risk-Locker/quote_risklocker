"""Hermetic TDD suite for Milestone 4b: Workspace Save Semantics, Learn 422 & Fee Toggles."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.errors import AppError
from app.models.tables import (
    Base,
    InsuranceTenure,
    QuotationDraft,
    Session as SessionModel,
    TenureComparisonEntry,
    TrackedVehicle,
    UploadedFile,
    User,
    new_id,
)
from app.services.admin_service import dictionary_contains, learn_dictionary_value
from app.services.marketing_comparison_service import (
    get_marketing_comparison,
    rescan_comparison_tenure,
)
from app.services.workspace_patch_service import apply_workspace_patch


@pytest.fixture()
def hermetic_db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()


def test_learn_dictionary_accepts_singular_car_brand_and_car_model_and_rejects_plural(hermetic_db: Session):
    """P6: /api/business/dictionaries/learn accepts 'car_brand' and 'car_model' and rejects plural 'car_models'."""
    user = User(id=new_id(), email="staff-learn@risklocker.test", password_hash="x", role="staff", status="active")
    hermetic_db.add(user)
    hermetic_db.commit()

    res_brand = learn_dictionary_value(hermetic_db, user, "car_brand", "Zeekr")
    assert res_brand["field"] == "car_brand"
    assert dictionary_contains(hermetic_db, "car_brand", "Zeekr") is True

    res_model = learn_dictionary_value(hermetic_db, user, "car_model", "Zeekr 009")
    assert res_model["field"] == "car_model"
    assert dictionary_contains(hermetic_db, "car_model", "Zeekr 009") is True

    with pytest.raises(AppError) as exc_info:
        learn_dictionary_value(hermetic_db, user, "car_models", "Atto 3")
    assert exc_info.value.status_code == 422


def test_workspace_road_tax_and_runner_fee_toggles_recompute_total_and_sync_tenure(hermetic_db: Session):
    """P7: Toggling include_road_tax / include_runner_fee updates draft total_amount and linked tenure."""
    user = User(id=new_id(), email="staff@risklocker.test", password_hash="x", role="staff", status="active")
    veh = TrackedVehicle(
        id=new_id(),
        vehicle_no="VRS7732",
        car_brand="SANY",
        car_model="SYM5410THB",
        engine_cc="16000 KG",
        manufacture_year=2022,
    )
    file_id = new_id()
    hermetic_db.add_all([user, veh])
    hermetic_db.flush()

    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=veh.id,
        vehicle_no="VRS7732",
        customer_name="Sany Heavy Construction Sdn Bhd",
        road_tax=Decimal("120.00"),
        runner_fee=Decimal("50.00"),
        include_road_tax=True,
        include_runner_fee=True,
        coverage_start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
        expiry_month="2026-12",
    )
    draft = QuotationDraft(
        id=new_id(),
        uploaded_file_id=file_id,
        owner_id=user.id,
        revision=1,
        fields={
            "premium": {"value": "2000.00", "status": "ready"},
            "roadtax": {"value": "120.00", "status": "ready"},
            "service_fee": {"value": "50.00", "status": "ready"},
            "total_amount": {"value": "2170.00", "status": "ready"},
        },
        scalar_decisions={},
        display_options={"include_road_tax": True, "include_runner_fee": True},
    )
    sess = SessionModel(
        id=new_id(),
        owner_id=user.id,
        uploaded_file_id=file_id,
        draft_id=draft.id,
        tenure_id=tenure.id,
        tracked_vehicle_id=veh.id,
        detected_company="Berjaya Sompo",
        document_type="quotation",
        status="active",
        is_tenure_active=True,
    )
    entry = TenureComparisonEntry(
        id=new_id(),
        tenure_id=tenure.id,
        session_id=sess.id,
        company_name="Berjaya Sompo",
        sum_insured=150000.0,
        motor_premium=2000.0,
        road_tax=120.0,
        runner_fee=50.0,
        include_road_tax=True,
        include_runner_fee=True,
        total_payable=2170.0,
        manual_overrides=[],
    )
    hermetic_db.add_all([tenure, draft, sess, entry])
    hermetic_db.commit()

    # 1. Disable Road Tax via workspace patch (both display_options and scalar_decision)
    apply_workspace_patch(
        hermetic_db,
        user,
        draft.id,
        base_revision=1,
        operations=[
            {"op": "update_display_options", "options": {"include_road_tax": False}},
            {"op": "scalar_decision", "field": "include_road_tax", "decision": "edit", "value": "false"},
            {"op": "scalar_decision", "field": "total_amount", "decision": "clear", "value": ""},
        ],
    )
    hermetic_db.refresh(draft)
    hermetic_db.refresh(tenure)
    assert draft.fields["total_amount"]["value"] == "2050.00"
    assert tenure.include_road_tax is False
    assert tenure.include_runner_fee is True

    # 2. Disable Runner Fee as well
    apply_workspace_patch(
        hermetic_db,
        user,
        draft.id,
        base_revision=draft.revision,
        operations=[
            {"op": "update_display_options", "options": {"include_runner_fee": False}},
            {"op": "scalar_decision", "field": "include_runner_fee", "decision": "edit", "value": "false"},
            {"op": "scalar_decision", "field": "total_amount", "decision": "clear", "value": ""},
        ],
    )
    hermetic_db.refresh(draft)
    hermetic_db.refresh(tenure)
    assert draft.fields["total_amount"]["value"] == "2000.00"
    assert tenure.include_road_tax is False
    assert tenure.include_runner_fee is False

    # 3. Re-enable Runner Fee on a Commercial Heavy Vehicle and verify rescan does NOT wipe it back to False
    apply_workspace_patch(
        hermetic_db,
        user,
        draft.id,
        base_revision=draft.revision,
        operations=[
            {"op": "update_display_options", "options": {"include_runner_fee": True}},
            {"op": "scalar_decision", "field": "include_runner_fee", "decision": "edit", "value": "true"},
            {"op": "scalar_decision", "field": "total_amount", "decision": "clear", "value": ""},
        ],
    )
    hermetic_db.refresh(draft)
    hermetic_db.refresh(tenure)
    assert draft.fields["total_amount"]["value"] == "2050.00"
    assert tenure.include_runner_fee is True

    after_rescan = rescan_comparison_tenure(hermetic_db, tenure.id)
    assert after_rescan["tenure"]["include_runner_fee"] is True
    assert after_rescan["tenure"]["runner_fee"] == 50.0
