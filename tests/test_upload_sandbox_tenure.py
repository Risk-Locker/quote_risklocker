"""Tests for sandbox mode tenure grouping and customer propagation across tenures."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_PROVIDER": "supabase_postgres",
        "DATABASE_URL": "postgresql://postgres:password@db.test.supabase.co:5432/postgres",
        "AUTH_HASH_SECRET": "test-auth-hash-secret-that-is-long-enough",
        "STORAGE_DRIVER": "supabase",
        "SUPABASE_URL": "https://project-ref.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
    }
)

from app.models.tables import (
    Base,
    CustomerAccount,
    InsuranceTenure,
    TrackedVehicle,
    new_id,
)
from app.services.marketing_comparison_service import update_tenure_fixed_costs
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def setup_in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_customer_name_propagation_across_tenures():
    db = setup_in_memory_db()

    # Create a customer account
    cust = CustomerAccount(
        id=new_id(),
        canonical_name="ORIGINAL CUSTOMER NAME",
        id_number="880101141234",
    )
    veh = TrackedVehicle(
        id=new_id(),
        vehicle_no="JYH8773",
        customer_id=cust.id,
    )
    db.add_all([cust, veh])
    db.flush()

    # Create 2 distinct tenures for this customer (e.g. 2024-2025 and 2025-2026)
    tenure1 = InsuranceTenure(
        id=new_id(),
        vehicle_no="JYH8773",
        tracked_vehicle_id=veh.id,
        customer_name="ORIGINAL CUSTOMER NAME",
        customer_id=cust.id,
        expiry_month="2025-09",
        coverage_start_date=datetime(2024, 9, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2025, 8, 31, tzinfo=timezone.utc),
        road_tax=70.0,
        runner_fee=50.0,
    )
    tenure2 = InsuranceTenure(
        id=new_id(),
        vehicle_no="JYH8773",
        tracked_vehicle_id=veh.id,
        customer_name="ORIGINAL CUSTOMER NAME",
        customer_id=cust.id,
        expiry_month="2026-09",
        coverage_start_date=datetime(2025, 9, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2026, 8, 31, tzinfo=timezone.utc),
        road_tax=70.0,
        runner_fee=50.0,
    )
    db.add_all([tenure1, tenure2])
    db.commit()

    # Update customer name and IC on tenure 1 via update_tenure_fixed_costs
    update_tenure_fixed_costs(
        db=db,
        tenure_id=tenure1.id,
        road_tax=70.0,
        runner_fee=50.0,
        customer_name="UPDATED MASTER CUSTOMER NAME",
        ic_no="900202-10-5678",
    )

    db.refresh(tenure1)
    db.refresh(tenure2)
    db.refresh(cust)

    # Both tenures and the customer account must reflect the updated name and normalized IC
    assert cust.canonical_name == "UPDATED MASTER CUSTOMER NAME"
    assert cust.id_number == "900202105678"
    assert tenure1.customer_name == "UPDATED MASTER CUSTOMER NAME"
    assert tenure2.customer_name == "UPDATED MASTER CUSTOMER NAME"


def test_ledger_patch_propagates_customer_and_drafts():
    from app.api.routers.tenures import UpdateTenureLedgerRequest, update_tenure_ledger_fields
    from app.models.tables import Batch, Session as SessionModel, QuotationDraft, UploadedFile, User

    db = setup_in_memory_db()

    user = User(
        id=new_id(),
        email="agent@risklocker.local",
        password_hash="test",
        name="Agent Test",
        role="staff",
    )
    cust = CustomerAccount(
        id=new_id(),
        canonical_name="OLD PERSON NAME",
        id_number="750505011111",
    )
    veh = TrackedVehicle(
        id=new_id(),
        vehicle_no="ABC1234",
        customer_id=cust.id,
    )
    batch = Batch(
        id=new_id(),
        owner_id=user.id,
        name="test_batch",
    )
    up_file = UploadedFile(
        id=new_id(),
        batch_id=batch.id,
        owner_id=user.id,
        original_filename="test.pdf",
        storage_path="test/path.pdf",
        size_bytes=1024,
        content_type="application/pdf",
    )
    draft = QuotationDraft(
        id=new_id(),
        owner_id=user.id,
        uploaded_file_id=up_file.id,
        fields={
            "customer_name": {"value": "OLD PERSON NAME", "status": "extracted"},
            "customer_ic_no": {"value": "750505-01-1111", "status": "extracted"},
        },
    )
    tenure_a = InsuranceTenure(
        id=new_id(),
        vehicle_no="ABC1234",
        tracked_vehicle_id=veh.id,
        customer_name="OLD PERSON NAME",
        customer_id=cust.id,
        expiry_month="2025-05",
        coverage_start_date=datetime(2024, 5, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2025, 4, 30, tzinfo=timezone.utc),
    )
    tenure_b = InsuranceTenure(
        id=new_id(),
        vehicle_no="ABC1234",
        tracked_vehicle_id=veh.id,
        customer_name="OLD PERSON NAME",
        customer_id=cust.id,
        expiry_month="2026-05",
        coverage_start_date=datetime(2025, 5, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2026, 4, 30, tzinfo=timezone.utc),
    )
    sess = SessionModel(
        id=new_id(),
        owner_id=user.id,
        uploaded_file_id=up_file.id,
        draft_id=draft.id,
        customer_id=cust.id,
        tenure_id=tenure_a.id,
    )
    db.add_all([user, cust, veh, batch, up_file, draft, tenure_a, tenure_b, sess])
    db.commit()

    # Patch from ledger fields
    payload = UpdateTenureLedgerRequest(
        customer_name="NEW PROPAGATED PERSON",
        customer_ic_no="850606-14-9999",
        vehicle_no="WXY9999",
        road_tax=120.0,
        runner_fee=60.0,
    )
    res = update_tenure_ledger_fields(tenure_a.id, payload, db=db, user=user)
    assert res["success"] is True

    db.refresh(tenure_a)
    db.refresh(tenure_b)
    db.refresh(cust)
    db.refresh(draft)

    # Customer and both tenures updated
    assert cust.canonical_name == "NEW PROPAGATED PERSON"
    assert cust.id_number == "850606149999"
    assert tenure_a.customer_name == "NEW PROPAGATED PERSON"
    assert tenure_b.customer_name == "NEW PROPAGATED PERSON"
    assert tenure_a.vehicle_no == "WXY9999"
    assert float(tenure_a.road_tax) == 120.0
    assert float(tenure_a.runner_fee) == 60.0

    # Quotation draft fields updated
    assert draft.fields["customer_name"]["value"] == "NEW PROPAGATED PERSON"
    assert draft.fields["customer_ic_no"]["value"] == "850606149999"


def test_customer_account_patch_propagates_tenures_and_drafts():
    from app.api.routers.insights import CustomerUpdateRequest, update_customer_endpoint
    from app.models.tables import Batch, Session as SessionModel, QuotationDraft, UploadedFile, User

    db = setup_in_memory_db()

    user = User(
        id=new_id(),
        email="staff@risklocker.local",
        password_hash="test",
        name="Staff Test",
        role="staff",
    )
    cust = CustomerAccount(
        id=new_id(),
        canonical_name="ORIGINAL DOSSIER CLIENT",
        id_number="920101103333",
    )
    veh = TrackedVehicle(
        id=new_id(),
        vehicle_no="KLA8888",
        customer_id=cust.id,
    )
    batch = Batch(
        id=new_id(),
        owner_id=user.id,
        name="batch_2",
    )
    up_file = UploadedFile(
        id=new_id(),
        batch_id=batch.id,
        owner_id=user.id,
        original_filename="dossier.pdf",
        storage_path="test/dossier.pdf",
        size_bytes=2048,
        content_type="application/pdf",
    )
    draft = QuotationDraft(
        id=new_id(),
        owner_id=user.id,
        uploaded_file_id=up_file.id,
        fields={
            "customer_name": {"value": "ORIGINAL DOSSIER CLIENT", "status": "extracted"},
            "customer_ic_no": {"value": "920101-10-3333", "status": "extracted"},
        },
    )
    tenure1 = InsuranceTenure(
        id=new_id(),
        vehicle_no="KLA8888",
        tracked_vehicle_id=veh.id,
        customer_name="ORIGINAL DOSSIER CLIENT",
        customer_id=cust.id,
        expiry_month="2025-11",
        coverage_start_date=datetime(2024, 11, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2025, 10, 31, tzinfo=timezone.utc),
    )
    tenure2 = InsuranceTenure(
        id=new_id(),
        vehicle_no="KLA8888",
        tracked_vehicle_id=veh.id,
        customer_name="ORIGINAL DOSSIER CLIENT",
        customer_id=cust.id,
        expiry_month="2026-11",
        coverage_start_date=datetime(2025, 11, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2026, 10, 31, tzinfo=timezone.utc),
    )
    sess = SessionModel(
        id=new_id(),
        owner_id=user.id,
        uploaded_file_id=up_file.id,
        draft_id=draft.id,
        customer_id=cust.id,
        tenure_id=tenure1.id,
    )
    db.add_all([user, cust, veh, batch, up_file, draft, tenure1, tenure2, sess])
    db.commit()

    # Update customer directly from customer dossier edit modal endpoint
    payload = CustomerUpdateRequest(
        canonical_name="FINAL EDITED DOSSIER CLIENT",
        id_number="920101-10-9999",
        phone="+60129998888",
        email="edited@client.com",
    )
    res = update_customer_endpoint(cust.id, payload, db=db, user=user)
    assert res["success"] is True

    db.refresh(cust)
    db.refresh(tenure1)
    db.refresh(tenure2)
    db.refresh(draft)

    # Master customer updated
    assert cust.canonical_name == "FINAL EDITED DOSSIER CLIENT"
    assert cust.id_number == "920101109999"
    assert cust.phone == "+60129998888"
    assert cust.email == "edited@client.com"

    # All tenures for this customer updated
    assert tenure1.customer_name == "FINAL EDITED DOSSIER CLIENT"
    assert tenure2.customer_name == "FINAL EDITED DOSSIER CLIENT"

    # All drafts updated
    assert draft.fields["customer_name"]["value"] == "FINAL EDITED DOSSIER CLIENT"
    assert draft.fields["customer_ic_no"]["value"] == "920101109999"


def test_update_vehicle_specs_and_delete_tenure():
    from app.api.routers.tenures import (
        UpdateTenureLedgerRequest,
        delete_tenure_endpoint,
        list_tenures,
        update_tenure_ledger_fields,
    )
    from app.models.tables import Session as SessionModel, User

    db = setup_in_memory_db()

    user = User(
        id=new_id(),
        email="admin@risklocker.local",
        password_hash="test",
        name="Admin Test",
        role="admin",
    )
    veh = TrackedVehicle(
        id=new_id(),
        vehicle_no="TEST999",
        chassis_no="CHASSIS12345",
        engine_no="ENG67890",
        engine_cc="1998 CC",
        car_brand="HONDA",
        car_model="CIVIC RS",
    )
    tenure = InsuranceTenure(
        id=new_id(),
        vehicle_no="TEST999",
        tracked_vehicle_id=veh.id,
        customer_name="TEST OWNER",
        expiry_month="2026-10",
        coverage_start_date=datetime(2025, 10, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2026, 9, 30, tzinfo=timezone.utc),
    )
    db.add_all([user, veh, tenure])
    db.commit()

    # 1. Verify list_tenures returns vehicle specs
    res = list_tenures(db=db, user=user)
    assert res["total"] == 1
    item = res["items"][0]
    assert item["chassis_no"] == "CHASSIS12345"
    assert item["engine_no"] == "ENG67890"
    assert item["car_model"] == "CIVIC RS"
    assert item["engine_cc"] == "1998 CC"

    # 2. Update vehicle specs via ledger-fields
    patch_req = UpdateTenureLedgerRequest(
        chassis_no="UPDATED_CHASSIS_99",
        car_model="CIVIC TYPE R",
        engine_cc="2000 CC",
    )
    update_res = update_tenure_ledger_fields(tenure.id, patch_req, db=db, user=user)
    assert update_res["success"] is True

    db.refresh(veh)
    assert veh.chassis_no == "UPDATED_CHASSIS_99"
    assert veh.car_model == "CIVIC TYPE R"
    assert veh.engine_cc == "2000 CC"

    # 3. Delete tenure via delete_tenure_endpoint
    del_res = delete_tenure_endpoint(tenure.id, db=db, user=user)
    assert del_res["success"] is True
    assert del_res["deleted_tenure_id"] == tenure.id

    assert db.get(InsuranceTenure, tenure.id) is None



