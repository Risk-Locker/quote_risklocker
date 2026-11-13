import pytest
from datetime import datetime, timezone
from app.models.tables import (
    InsuranceTenure,
    Session,
    UploadedFile,
    QuotationDraft,
    TenureComparisonEntry,
    TrackedVehicle,
    Batch,
    User,
    new_id,
)
from app.services.marketing_comparison_service import get_marketing_comparison

def test_single_active_quote_upsert_deduplication(db_session):
    # 0. User and batch
    user = User(
        id=new_id(),
        email="broker@risklocker.local",
        name="Eugene Lee",
        password_hash="mock",
        role="agent",
    )
    db_session.add(user)
    batch = Batch(id=new_id(), owner_id=user.id, name="Test Batch")
    db_session.add(batch)
    db_session.flush()

    # 1. Create vehicle & tenure
    vehicle = TrackedVehicle(
        id=new_id(),
        vehicle_no="JQM2682",
        car_brand="HINO",
        car_model="500",
    )
    db_session.add(vehicle)
    db_session.flush()

    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=vehicle.id,
        vehicle_no="JQM2682",
        customer_name="EXCEL READY-MIX SDN BHD",
        coverage_start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 9, 30, tzinfo=timezone.utc),
        expiry_month="2027-09",
        stage="Quotations",
        road_tax=100.0,
        runner_fee=50.0,
    )
    db_session.add(tenure)
    db_session.commit()

    # 2. Add first quotation (v1) for AmAssurance
    u1 = UploadedFile(
        batch_id=batch.id,
        owner_id=user.id,
        original_filename="20260930_JQM2682_Quotation_Amgen.pdf",
        content_type="application/pdf",
        storage_path="source/dummy1.pdf",
        size_bytes=225000,
    )
    db_session.add(u1)
    db_session.flush()

    d1 = QuotationDraft(
        id=new_id(),
        uploaded_file_id=u1.id,
        owner_id=user.id,
        fields={
            "sum_insured": {"value": "50000.00"},
            "basic_premium": {"value": "1200.00"},
            "total_amount": {"value": "1350.00"},
        }
    )
    db_session.add(d1)
    db_session.flush()

    s1 = Session(
        id=new_id(),
        owner_id=user.id,
        tenure_id=tenure.id,
        uploaded_file_id=u1.id,
        draft_id=d1.id,
        detected_company="AmAssurance",
        document_type="quotation",
        tenure_version=1,
        is_tenure_active=True,
    )
    db_session.add(s1)
    db_session.commit()

    # First fetch: should create 1 comparison entry
    res1 = get_marketing_comparison(db_session, tenure.id)
    assert len(res1["entries"]) == 1
    assert res1["entries"][0]["company_name"] == "AmAssurance"
    assert res1["entries"][0]["sum_insured"] == 50000.0

    # 3. Add second quotation revision (v2) for AmAssurance with updated sum insured
    u2 = UploadedFile(
        batch_id=batch.id,
        owner_id=user.id,
        original_filename="20260930_JQM2682_Quotation_Amgen_v2.pdf",
        content_type="application/pdf",
        storage_path="source/dummy2.pdf",
        size_bytes=225500,
    )
    db_session.add(u2)
    db_session.flush()

    d2 = QuotationDraft(
        id=new_id(),
        uploaded_file_id=u2.id,
        owner_id=user.id,
        fields={
            "sum_insured": {"value": "55000.00"},
            "basic_premium": {"value": "1300.00"},
            "total_amount": {"value": "1450.00"},
        }
    )
    db_session.add(d2)
    db_session.flush()

    s2 = Session(
        id=new_id(),
        owner_id=user.id,
        tenure_id=tenure.id,
        uploaded_file_id=u2.id,
        draft_id=d2.id,
        detected_company="AmAssurance",
        document_type="quotation",
        tenure_version=2,
        is_tenure_active=True,
    )
    s1.is_tenure_active = False # Older revision demoted
    db_session.add(s2)
    db_session.commit()

    # Second fetch: MUST NOT CREATE DUPLICATE COLUMN! Must update the existing column in place!
    res2 = get_marketing_comparison(db_session, tenure.id)
    assert len(res2["entries"]) == 1, f"Expected 1 entry, got {len(res2['entries'])}"
    assert res2["entries"][0]["company_name"] == "AmAssurance"
    assert res2["entries"][0]["sum_insured"] == 55000.0
    assert res2["entries"][0]["session_id"] == s2.id

