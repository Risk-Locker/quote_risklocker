"""
Unit tests for PLAN 1: Immutable Database Core & Real-Time Synchronization Engine.
Verifies:
  1. Key Name Alignment: save_comparison_entry sets canonical keys ('insurance_company', 'premium', 'excess_amount', 'windscreen_sum_insured', 'roadtax', 'service_fee', 'total_amount')
  2. Two-Way Quotation Sync: apply_workspace_patch updates linked TenureComparisonEntry
  3. Atomic sync_tenure_identity_transaction across TrackedVehicle, InsuranceTenure, CustomerAccount, Sessions, and Comparison Entries
  4. Concurrency Protection: expected_version prevents overwrite collisions and auto-increments version
  5. Universal Flat Runner Fee: strictly RM 20.00
  6. Benefit Concept Uniqueness: duplicate concepts on DraftBenefitSelection are prevented
"""

from datetime import datetime, timezone
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as OrmSession, sessionmaker

from app.models.tables import (
    Base,
    Batch,
    CustomerAccount,
    DraftBenefitSelection,
    InsuranceTenure,
    QuotationDraft,
    Session as SessionModel,
    TenureComparisonEntry,
    TrackedVehicle,
    UploadedFile,
    User,
    new_id,
)
from app.services.marketing_comparison_service import (
    detect_runner_fee_from_id,
    save_comparison_entry,
)
from app.services.tenure_identity_sync_service import (
    UNIVERSAL_RUNNER_FEE,
    sync_tenure_identity_transaction,
)
from app.services.workspace_patch_service import apply_workspace_patch


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def seed_data(db: OrmSession):
    user = User(id=new_id(), name="Agent", email="agent@test.com", password_hash="hash")
    db.add(user)
    db.flush()

    vehicle = TrackedVehicle(
        id=new_id(),
        vehicle_no="WFW8977",
        car_brand="Honda",
        car_model="Civic",
        engine_cc="1797",
        manufacture_year=1997,
    )
    db.add(vehicle)
    db.flush()

    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=vehicle.id,
        vehicle_no="WFW8977",
        customer_name="YAU YEN CHEN",
        coverage_start_date=datetime(2026, 11, 8, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 11, 7, tzinfo=timezone.utc),
        expiry_month="2027-11",
        status="draft",
        road_tax=278.80,
        runner_fee=20.00,
        include_road_tax=True,
        include_runner_fee=True,
        ncd_percentage=45.0,
    )
    db.add(tenure)
    db.flush()

    batch = Batch(id=new_id(), owner_id=user.id, name="Batch 1")
    db.add(batch)
    db.flush()

    uf = UploadedFile(
        id=new_id(),
        batch_id=batch.id,
        owner_id=user.id,
        original_filename="qbe.pdf",
        content_type="application/pdf",
        storage_path="tmp/qbe.pdf",
    )
    db.add(uf)
    db.flush()

    draft = QuotationDraft(
        id=new_id(),
        owner_id=user.id,
        uploaded_file_id=uf.id,
        revision=1,
        fields={
            "vehicle_no": {"value": "WFW8977"},
            "customer_name": {"value": "YAU YEN CHEN"},
            "ic_or_brn": {"value": "860630-43-5720"},
            "car_model": {"value": "Civic"},
            "vehicle_year": {"value": "1997"},
            "vehicle_type": {"value": "Car (Private Saloon)"},
            "insurance_company": {"value": "QBE"},
            "premium": {"value": "335.00"},
            "roadtax": {"value": "278.80"},
            "service_fee": {"value": "20.00"},
            "total_amount": {"value": "633.80"},
            "sum_insured": {"value": "0.00"},
            "valuation_type": {"value": "Market Value"},
            "excess_amount": {"value": "0.00"},
        },
    )
    db.add(draft)
    db.flush()

    session_obj = SessionModel(
        id=new_id(),
        owner_id=user.id,
        uploaded_file_id=uf.id,
        draft_id=draft.id,
        tenure_id=tenure.id,
        detected_company="QBE",
        is_tenure_active=True,
    )
    db.add(session_obj)
    db.flush()

    entry = TenureComparisonEntry(
        id=new_id(),
        tenure_id=tenure.id,
        session_id=session_obj.id,
        company_name="QBE",
        motor_premium=335.00,
        sum_insured=0.00,
        valuation_type="market_value",
        road_tax=278.80,
        runner_fee=20.00,
        total_payable=633.80,
        version=1,
    )
    db.add(entry)
    db.commit()

    return {
        "user": user,
        "vehicle": vehicle,
        "tenure": tenure,
        "draft": draft,
        "session": session_obj,
        "entry": entry,
    }


def test_task_1_1_canonical_key_sync_from_comparison(db: OrmSession, seed_data: dict):
    """When an agent edits an underwriter quote in Comparison Matrix, canonical keys sync to QuotationDraft."""
    tenure = seed_data["tenure"]
    entry = seed_data["entry"]
    draft = seed_data["draft"]

    payload = {
        "id": entry.id,
        "company_name": "QBE Insurance",
        "motor_premium": 450.00,
        "sum_insured": 15000.00,
        "agreed_value": True,
        "excess": 200.00,
        "windscreen_sum_insured": 1200.00,
        "towing_limit": "200 KM",
        "waiver_betterment": True,
    }

    res = save_comparison_entry(db, tenure.id, payload)
    db.refresh(draft)

    fields = draft.fields
    # Task 1.1 Invariant: Canonical keys exist and reflect the new 2-decimal values
    assert fields["insurance_company"]["value"] == "QBE Insurance"
    assert fields["premium"]["value"] == "450.00"
    assert fields["sum_insured"]["value"] == "15000.00"
    assert fields["valuation_type"]["value"] == "Agreed Value"
    assert fields["excess_amount"]["value"] == "200.00"
    assert fields["windscreen_sum_insured"]["value"] == "1200.00"
    assert fields["towing"]["value"] == "200 KM"
    assert fields["waiver_of_betterment"]["value"] == "Included"

    # Total amount in draft recomputed: 450.00 + 278.80 (RT) + 20.00 (Runner) = 748.80
    assert fields["total_amount"]["value"] == "748.80"

    # Backward compatibility aliases also preserved
    assert fields["insurer_name"]["value"] == "QBE Insurance"
    assert fields["premium_due"]["value"] == "450.00"
    assert fields["excess"]["value"] == "200.00"


def test_task_1_1_bidirectional_quotation_workspace_to_comparison(db: OrmSession, seed_data: dict):
    """When an agent edits premium or vehicle sum in Quotation Workspace, TenureComparisonEntry updates automatically."""
    draft = seed_data["draft"]
    entry = seed_data["entry"]
    tenure = seed_data["tenure"]

    # Patch Quotation Workspace with new premium, sum insured, and agreed value
    patch_payload = {
        "operations": [
            {"op": "scalar_decision", "field": "premium", "decision": "edit", "value": "512.50"},
            {"op": "scalar_decision", "field": "sum_insured", "decision": "edit", "value": "25000.00"},
            {"op": "scalar_decision", "field": "valuation_type", "decision": "edit", "value": "Agreed Value"},
            {"op": "scalar_decision", "field": "excess_amount", "decision": "edit", "value": "150.00"},
            {"op": "scalar_decision", "field": "windscreen_sum_insured", "decision": "edit", "value": "1500.00"},
            {"op": "scalar_decision", "field": "towing", "decision": "edit", "value": "Unlimited"},
        ]
    }

    apply_workspace_patch(db, seed_data["user"], draft.id, base_revision=1, operations=patch_payload["operations"])
    db.refresh(entry)

    # Invariant 2: Comparison entry immediately reflects workspace patch
    assert float(entry.motor_premium) == 512.50
    assert float(entry.sum_insured) == 25000.00
    assert entry.valuation_type == "agreed_value"
    assert entry.agreed_value is True
    assert float(entry.excess) == 150.00
    assert float(entry.windscreen_sum_insured) == 1500.00
    assert entry.towing_limit == "Unlimited"

    # Total payable recomputed: 512.50 + 278.80 + 20.00 = 811.30
    assert float(entry.total_payable) == 811.30
    # Revision auto-incremented
    assert entry.revision == 2


def test_task_1_2_sync_tenure_identity_transaction(db: OrmSession, seed_data: dict):
    """sync_tenure_identity_transaction atomically propagates changes to vehicle, tenure, customer, sessions, and entries."""
    tenure = seed_data["tenure"]
    vehicle = seed_data["vehicle"]
    draft = seed_data["draft"]
    entry = seed_data["entry"]

    sync_tenure_identity_transaction(
        db,
        tenure.id,
        customer_name="CHENG WING JIN",
        ic_or_brn="860630-43-5720",
        vehicle_no="WFW8977",
        car_brand="HONDA",
        car_model="CIVIC 1.8L",
        engine_cc="1800 CC",
        manufacture_year=2000,
        vehicle_type="Car (Private Saloon)",
        road_tax=280.00,
        runner_fee=20.00,
    )
    db.commit()

    db.refresh(tenure)
    db.refresh(vehicle)
    db.refresh(draft)
    db.refresh(entry)

    # 1. TrackedVehicle updated
    assert vehicle.car_model == "CIVIC 1.8L"
    assert vehicle.manufacture_year == 2000
    assert vehicle.engine_cc == "1800 CC"

    # 2. InsuranceTenure updated
    assert tenure.customer_name == "CHENG WING JIN"
    assert float(tenure.road_tax) == 280.00
    assert float(tenure.runner_fee) == 20.00

    # 3. CustomerAccount resolved and linked
    assert tenure.customer_id is not None
    cust = db.get(CustomerAccount, tenure.customer_id)
    assert cust is not None
    assert cust.canonical_name == "CHENG WING JIN"
    assert cust.id_number == "860630435720"

    # 4. QuotationDraft fields updated
    fields = draft.fields
    assert fields["customer_name"]["value"] == "CHENG WING JIN"
    assert fields["ic_or_brn"]["value"] == "860630435720"
    assert fields["car_model"]["value"] == "CIVIC 1.8L"
    assert fields["vehicle_year"]["value"] == "2000"
    assert fields["vehicle_type"]["value"] == "Car (Private Saloon)"
    assert fields["roadtax"]["value"] == "280.00"
    assert fields["service_fee"]["value"] == "20.00"

    # 5. TenureComparisonEntry updated
    assert entry.road_tax == 280.00
    assert entry.runner_fee == 20.00
    assert entry.total_payable == 335.00 + 280.00 + 20.00


def test_task_1_3_universal_runner_fee_enforcement():
    """Universal flat runner fee is strictly RM 20.00 regardless of ID type."""
    assert UNIVERSAL_RUNNER_FEE == Decimal("20.00")
    # All customer IDs yield exactly RM 20.00
    assert detect_runner_fee_from_id("860630-43-5720") == 20.0
    assert detect_runner_fee_from_id("A12345678") == 20.0
    assert detect_runner_fee_from_id("PENDING-123") == 20.0
    assert detect_runner_fee_from_id(None) == 20.0


def test_task_1_4_optimistic_concurrency_protection(db: OrmSession, seed_data: dict):
    """Passing expected_revision prevents overwrite collisions and auto-increments revision."""
    tenure = seed_data["tenure"]
    entry = seed_data["entry"]

    # Initial revision is 1
    assert entry.revision == 1

    # Attempt to save with mismatched revision raises ValueError
    with pytest.raises(ValueError, match="Concurrent modification conflict"):
        save_comparison_entry(
            db,
            tenure.id,
            {"id": entry.id, "motor_premium": 400.0, "expected_revision": 99},
        )

    # Save with matching revision succeeds and increments revision to 2
    save_comparison_entry(
        db,
        tenure.id,
        {"id": entry.id, "motor_premium": 400.0, "expected_revision": 1},
    )
    db.refresh(entry)
    assert entry.revision == 2
    assert entry.motor_premium == 400.0


def test_task_1_4_draft_benefit_selection_duplicate_concept_prevention(db: OrmSession, seed_data: dict):
    """DraftBenefitSelection prevents duplicate active ('current') concept selections per draft,
    while allowing 'removed' or 'available_addon' rows for the same concept to coexist."""
    from sqlalchemy.exc import IntegrityError
    draft = seed_data["draft"]

    # Ensure TenureComparisonEntry uses live Postgres 'version' column without an unmigrated 'revision' column
    assert "version" in TenureComparisonEntry.__table__.columns
    assert "revision" not in TenureComparisonEntry.__table__.columns

    ws_concept_id = new_id()
    # A removed selection and an available_addon selection for the same concept must NOT block a current selection
    sel_removed = DraftBenefitSelection(
        id=new_id(),
        draft_id=draft.id,
        selection_key="catalog:windscreen_removed",
        concept_id=ws_concept_id,
        item_kind="catalog",
        state="removed",
        cost_status="paid",
    )
    sel_available = DraftBenefitSelection(
        id=new_id(),
        draft_id=draft.id,
        selection_key="catalog:windscreen_available",
        concept_id=ws_concept_id,
        item_kind="catalog",
        state="available_addon",
        cost_status="paid",
    )
    sel1 = DraftBenefitSelection(
        id=new_id(),
        draft_id=draft.id,
        selection_key="catalog:windscreen_1",
        concept_id=ws_concept_id,
        item_kind="catalog",
        state="current",
        cost_status="paid",
    )
    db.add_all([sel_removed, sel_available, sel1])
    db.commit()

    # Attempting to add another 'current' non-superseded selection with the SAME concept_id must fail
    sel2 = DraftBenefitSelection(
        id=new_id(),
        draft_id=draft.id,
        selection_key="catalog:windscreen_2",
        concept_id=ws_concept_id,
        item_kind="catalog",
        state="current",
        cost_status="paid",
    )
    db.add(sel2)
    with pytest.raises(IntegrityError):
        db.commit()


def test_workspace_patch_does_not_double_count_extracted_paid_addons_in_total_amount(db: OrmSession, seed_data: dict):
    """Net underwriter premium already includes extracted paid riders; _recompute_total must not add extras a second time."""
    draft = seed_data["draft"]
    entry = seed_data["entry"]

    # Add an active paid benefit selection (e.g. Windscreen RM 150.00 already included in net premium RM 335.00)
    paid_rider = DraftBenefitSelection(
        id=new_id(),
        draft_id=draft.id,
        selection_key="catalog:windscreen_paid",
        concept_id=new_id(),
        item_kind="custom",
        state="current",
        cost_status="paid",
        label_override="Windscreen",
        price={"amount": "150.00", "currency": "MYR"},
    )
    db.add(paid_rider)
    db.commit()

    apply_workspace_patch(
        db,
        seed_data["user"],
        draft.id,
        base_revision=1,
        operations=[{"op": "scalar_decision", "field": "premium", "decision": "edit", "value": "335.00"}],
    )
    db.refresh(draft)
    db.refresh(entry)

    # Total Payable = 335.00 (Net Premium) + 278.80 (Road Tax) + 20.00 (Runner Fee) = 633.80 (NOT 783.80)
    assert draft.fields["total_amount"]["value"] == "633.80"
    assert float(entry.total_payable) == 633.80

