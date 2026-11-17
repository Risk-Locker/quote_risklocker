"""Hermetic unit and API contract regressions for Milestone 1 (Save, Sync & API Repairs).

Covers:
  - F-01: Cross-vehicle, multi-year tenure, and sandbox (is_test) isolation during identity sync.
  - F-02: PATCH /tenures/{tenure_id}/ledger-fields inline & customer-sync parity (excluding sandbox).
  - F-03: POST /comparison/{tenure_id}/fixed-costs saves current_ncd and ncd_percentage cleanly.
  - Single-source-of-truth adjusted_total_text honoring include_road_tax / include_runner_fee flags.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as OrmSession, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.api.deps import current_user, get_db
from app.api.routers.comparison import router as comparison_router
from app.api.routers.tenures import router as tenures_router
from app.core.errors import register_error_handlers
from app.models.tables import (
    Base,
    Batch,
    CustomerAccount,
    InsuranceTenure,
    QuotationDraft,
    Session as SessionModel,
    TrackedVehicle,
    UploadedFile,
    User,
    new_id,
)
from app.rendering.render_context import adjusted_total_text
from app.services.tenure_identity_sync_service import sync_tenure_identity_transaction


@pytest.fixture
def db() -> OrmSession:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _create_session_with_draft(
    db: OrmSession,
    *,
    owner_id: str,
    batch_id: str,
    customer_id: str,
    tracked_vehicle_id: str,
    tenure_id: str | None,
    filename: str,
    fields: dict,
    coverage_start: datetime,
    coverage_end: datetime,
    is_test: bool = False,
) -> tuple[SessionModel, QuotationDraft]:
    uf = UploadedFile(
        id=new_id(),
        batch_id=batch_id,
        owner_id=owner_id,
        original_filename=filename,
        content_type="application/pdf",
        storage_path=f"tmp/{filename}",
    )
    db.add(uf)
    db.flush()

    draft = QuotationDraft(
        id=new_id(),
        owner_id=owner_id,
        uploaded_file_id=uf.id,
        revision=1,
        fields=fields,
    )
    db.add(draft)
    db.flush()

    sess = SessionModel(
        id=new_id(),
        owner_id=owner_id,
        uploaded_file_id=uf.id,
        draft_id=draft.id,
        customer_id=customer_id,
        tracked_vehicle_id=tracked_vehicle_id,
        tenure_id=tenure_id,
        coverage_start_date=coverage_start,
        coverage_end_date=coverage_end,
        detected_company="ALLIANZ",
        is_test=is_test,
        is_tenure_active=True,
    )
    db.add(sess)
    db.flush()
    return sess, draft


def test_f01_cross_vehicle_same_customer_and_sandbox_isolation(db: OrmSession):
    """Updating Car A must NEVER overwrite Car B specs/dates/fees or Sandbox (is_test) drafts."""
    user = User(
        id=new_id(),
        email="staff@risklocker.test",
        name="Staff",
        password_hash="x",
        role="staff",
        status="active",
    )
    cust = CustomerAccount(
        id=new_id(),
        canonical_name="TAN AH KOW",
        id_number="800101015555",
        id_type="nric",
    )
    veh_a = TrackedVehicle(
        id=new_id(),
        vehicle_no="WYY1111",
        car_brand="BYD",
        car_model="Seal",
        engine_cc="150 kW",
    )
    veh_b = TrackedVehicle(
        id=new_id(),
        vehicle_no="VAA2222",
        car_brand="Honda",
        car_model="CR-V",
        engine_cc="1997 CC",
    )
    db.add_all([user, cust, veh_a, veh_b])
    db.flush()

    ten_a = InsuranceTenure(
        id=new_id(),
        customer_id=cust.id,
        tracked_vehicle_id=veh_a.id,
        vehicle_no="WYY1111",
        customer_name="TAN AH KOW",
        coverage_start_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 5, 31, tzinfo=timezone.utc),
        expiry_month="2027-05",
        road_tax=Decimal("90.00"),
        runner_fee=Decimal("20.00"),
        include_road_tax=True,
        include_runner_fee=True,
    )
    ten_a_prev = InsuranceTenure(
        id=new_id(),
        customer_id=cust.id,
        tracked_vehicle_id=veh_a.id,
        vehicle_no="WYY1111",
        customer_name="TAN AH KOW",
        coverage_start_date=datetime(2025, 6, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2026, 5, 31, tzinfo=timezone.utc),
        expiry_month="2026-05",
        road_tax=Decimal("75.00"),
        runner_fee=Decimal("20.00"),
        include_road_tax=True,
        include_runner_fee=True,
    )
    ten_b = InsuranceTenure(
        id=new_id(),
        customer_id=cust.id,
        tracked_vehicle_id=veh_b.id,
        vehicle_no="VAA2222",
        customer_name="TAN AH KOW",
        coverage_start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 9, 30, tzinfo=timezone.utc),
        expiry_month="2027-09",
        road_tax=Decimal("438.00"),
        runner_fee=Decimal("20.00"),
        include_road_tax=True,
        include_runner_fee=True,
    )
    batch = Batch(id=new_id(), owner_id=user.id, name="Multi-Car Batch")
    db.add_all([ten_a, ten_a_prev, ten_b, batch])
    db.flush()

    sess_a, draft_a = _create_session_with_draft(
        db,
        owner_id=user.id,
        batch_id=batch.id,
        customer_id=cust.id,
        tracked_vehicle_id=veh_a.id,
        tenure_id=ten_a.id,
        filename="car_a.pdf",
        coverage_start=datetime(2026, 6, 1, tzinfo=timezone.utc),
        coverage_end=datetime(2027, 5, 31, tzinfo=timezone.utc),
        fields={
            "vehicle_no": {"value": "WYY1111"},
            "customer_name": {"value": "TAN AH KOW"},
            "car_model": {"value": "Seal"},
            "engine_cc": {"value": "150 kW"},
            "roadtax": {"value": "90.00"},
            "cover_start_date": {"value": "2026-06-01"},
            "cover_end_date": {"value": "2027-05-31"},
        },
    )
    sess_a_prev, draft_a_prev = _create_session_with_draft(
        db,
        owner_id=user.id,
        batch_id=batch.id,
        customer_id=cust.id,
        tracked_vehicle_id=veh_a.id,
        tenure_id=ten_a_prev.id,
        filename="car_a_2025.pdf",
        coverage_start=datetime(2025, 6, 1, tzinfo=timezone.utc),
        coverage_end=datetime(2026, 5, 31, tzinfo=timezone.utc),
        fields={
            "vehicle_no": {"value": "WYY1111"},
            "customer_name": {"value": "TAN AH KOW"},
            "car_model": {"value": "Seal"},
            "engine_cc": {"value": "150 kW"},
            "roadtax": {"value": "75.00"},
            "cover_start_date": {"value": "2025-06-01"},
            "cover_end_date": {"value": "2026-05-31"},
        },
    )
    sess_b, draft_b = _create_session_with_draft(
        db,
        owner_id=user.id,
        batch_id=batch.id,
        customer_id=cust.id,
        tracked_vehicle_id=veh_b.id,
        tenure_id=ten_b.id,
        filename="car_b.pdf",
        coverage_start=datetime(2026, 10, 1, tzinfo=timezone.utc),
        coverage_end=datetime(2027, 9, 30, tzinfo=timezone.utc),
        fields={
            "vehicle_no": {"value": "VAA2222"},
            "customer_name": {"value": "TAN AH KOW"},
            "car_brand": {"value": "Honda"},
            "car_model": {"value": "CR-V"},
            "engine_cc": {"value": "1997 CC"},
            "roadtax": {"value": "438.00"},
            "cover_start_date": {"value": "2026-10-01"},
            "cover_end_date": {"value": "2027-09-30"},
        },
    )
    sess_test, draft_test = _create_session_with_draft(
        db,
        owner_id=user.id,
        batch_id=batch.id,
        customer_id=cust.id,
        tracked_vehicle_id=veh_b.id,
        tenure_id=None,
        filename="sandbox.pdf",
        coverage_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        coverage_end=datetime(2026, 12, 31, tzinfo=timezone.utc),
        is_test=True,
        fields={
            "vehicle_no": {"value": "VAA2222"},
            "customer_name": {"value": "SANDBOX ORIGINAL"},
            "roadtax": {"value": "111.00"},
        },
    )
    db.commit()

    sync_tenure_identity_transaction(
        db,
        ten_a.id,
        customer_name="TAN AH KOW UPDATED",
        ic_or_brn="800101-01-5555",
        vehicle_no="WYY1111",
        car_brand="BYD",
        car_model="SEAL PERFORMANCE",
        engine_cc="390 kW",
        powertrain="ev",
        road_tax=120.00,
        runner_fee=30.00,
        coverage_start_date="2026-06-15",
        coverage_end_date="2027-06-14",
    )
    db.commit()

    for obj in (sess_a, draft_a, sess_a_prev, draft_a_prev, sess_b, draft_b, sess_test, draft_test):
        db.refresh(obj)

    # Same tenure (Car A 2026): receives full sync
    assert draft_a.fields["customer_name"]["value"] == "TAN AH KOW UPDATED"
    assert draft_a.fields["car_model"]["value"] == "SEAL PERFORMANCE"
    assert draft_a.fields["engine_cc"]["value"] == "390 kW"
    assert draft_a.fields["roadtax"]["value"] == "120.00"
    assert draft_a.fields["cover_period"] == "15/06/2026 - 14/06/2027"
    assert sess_a.coverage_start_date.replace(tzinfo=None) == datetime(2026, 6, 15)

    # Same car, previous year (Car A 2025): receives vehicle spec + customer name, keeps 2025 dates & roadtax
    assert draft_a_prev.fields["customer_name"]["value"] == "TAN AH KOW UPDATED"
    assert draft_a_prev.fields["car_model"]["value"] == "SEAL PERFORMANCE"
    assert draft_a_prev.fields["cover_start_date"]["value"] == "2025-06-01"
    assert draft_a_prev.fields["roadtax"]["value"] == "75.00"
    assert "cover_period" not in draft_a_prev.fields
    assert sess_a_prev.coverage_start_date.replace(tzinfo=None) == datetime(2025, 6, 1)

    # Sibling Car B owned by SAME customer: receives ONLY customer identity, zero Car A contamination
    assert draft_b.fields["customer_name"]["value"] == "TAN AH KOW UPDATED"
    assert draft_b.fields["vehicle_no"]["value"] == "VAA2222"
    assert draft_b.fields["car_model"]["value"] == "CR-V"
    assert draft_b.fields["engine_cc"]["value"] == "1997 CC"
    assert draft_b.fields["roadtax"]["value"] == "438.00"
    assert draft_b.fields["cover_start_date"]["value"] == "2026-10-01"
    assert "cover_period" not in draft_b.fields
    assert "coverage_start_date" not in draft_b.fields
    assert sess_b.coverage_start_date.replace(tzinfo=None) == datetime(2026, 10, 1)

    # Sandbox session: completely isolated
    assert draft_test.fields["customer_name"]["value"] == "SANDBOX ORIGINAL"
    assert draft_test.fields["roadtax"]["value"] == "111.00"


def test_f02_and_f03_ledger_fields_patch_and_comparison_fixed_costs_post(db: OrmSession):
    """F-02 & F-03: Verify live FastAPI endpoints accept canonical HTTP methods and persist fields."""
    staff = User(
        id=new_id(),
        email="ops@risklocker.test",
        name="Ops User",
        password_hash="x",
        role="staff",
        status="active",
    )
    cust = CustomerAccount(
        id=new_id(),
        canonical_name="LEE MEI MEI",
        id_number="900202026666",
        id_type="nric",
    )
    tv = TrackedVehicle(
        id=new_id(),
        vehicle_no="JPG8888",
        car_brand="Proton",
        car_model="S70",
        engine_cc="1499 CC",
    )
    db.add_all([staff, cust, tv])
    db.flush()

    tenure = InsuranceTenure(
        id=new_id(),
        customer_id=cust.id,
        tracked_vehicle_id=tv.id,
        vehicle_no="JPG8888",
        customer_name="LEE MEI MEI",
        stage="Quotations",
        status="draft",
        coverage_start_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 7, 31, tzinfo=timezone.utc),
        expiry_month="2027-07",
        road_tax=Decimal("90.00"),
        runner_fee=Decimal("20.00"),
        include_road_tax=True,
        include_runner_fee=True,
        ncd_percentage=Decimal("25.00"),
    )
    batch = Batch(id=new_id(), owner_id=staff.id, name="Endpoint Batch")
    db.add_all([tenure, batch])
    db.flush()

    _, test_draft = _create_session_with_draft(
        db,
        owner_id=staff.id,
        batch_id=batch.id,
        customer_id=cust.id,
        tracked_vehicle_id=tv.id,
        tenure_id=None,
        filename="sandbox_ep.pdf",
        coverage_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        coverage_end=datetime(2026, 12, 31, tzinfo=timezone.utc),
        is_test=True,
        fields={"customer_name": {"value": "SANDBOX DO NOT TOUCH"}},
    )
    db.commit()

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(tenures_router)
    app.include_router(comparison_router)
    app.dependency_overrides[current_user] = lambda: staff
    app.dependency_overrides[get_db] = lambda: db

    client = TestClient(app)

    # F-02: PATCH /tenures/{id}/ledger-fields works cleanly; PATCH /tenures/{id} is 405
    bad_method_ledger = client.patch(f"/tenures/{tenure.id}", json={"stage": "Material to Client"})
    assert bad_method_ledger.status_code == 405

    ok_ledger = client.patch(
        f"/tenures/{tenure.id}/ledger-fields",
        json={
            "stage": "Material to Client",
            "customer_name": "LEE MEI MEI LEE",
            "comment": "Sent via WhatsApp",
            "road_tax": 110.0,
        },
    )
    assert ok_ledger.status_code == 200, ok_ledger.text
    db.refresh(tenure)
    db.refresh(test_draft)
    assert tenure.stage == "Material to Client"
    assert tenure.customer_name == "LEE MEI MEI LEE"
    assert tenure.comment == "Sent via WhatsApp"
    assert float(tenure.road_tax) == 110.0
    assert test_draft.fields["customer_name"]["value"] == "SANDBOX DO NOT TOUCH"

    # F-03: POST /comparison/{id}/fixed-costs works cleanly; PATCH is 405
    bad_method_comp = client.patch(
        f"/comparison/{tenure.id}/fixed-costs",
        json={"road_tax": 110.0, "runner_fee": 20.0, "ncd_percentage": 38.33, "current_ncd": 25.0},
    )
    assert bad_method_comp.status_code == 405

    ok_comp = client.post(
        f"/comparison/{tenure.id}/fixed-costs",
        json={"road_tax": 110.0, "runner_fee": 20.0, "ncd_percentage": 38.33, "current_ncd": 25.0},
    )
    assert ok_comp.status_code == 200, ok_comp.text
    db.refresh(tenure)
    assert float(tenure.ncd_percentage) == 38.33


def test_adjusted_total_text_respects_fee_exclusion_flags():
    """Backend authoritative Decimal total respects include_road_tax / include_runner_fee exclusions."""
    fields = {
        "premium": {"value": "1000.25"},
        "roadtax": {"value": "90.00"},
        "service_fee": {"value": "20.00"},
        "engine_cc": {"value": "1500 CC"},
    }
    assert adjusted_total_text(fields, [], round_total=False) == "1,110.25"
    assert adjusted_total_text(fields, [], round_total=False, include_road_tax=False) == "1,020.25"
    assert adjusted_total_text(fields, [], round_total=False, include_runner_fee=False) == "1,090.25"
    assert (
        adjusted_total_text(
            {**fields, "include_road_tax": {"value": "false"}},
            [],
            round_total=False,
        )
        == "1,020.25"
    )
    assert adjusted_total_text(fields, [], round_total=True, include_road_tax=False) == "1,020.00"
