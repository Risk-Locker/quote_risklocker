"""Integration tests for 1-click Document Type toggle between Quotation and Cover Note."""

import pytest
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db, current_user
from app.api.routers import sessions as sessions_router
from app.models.tables import (
    Base,
    Batch,
    InsuranceTenure,
    QuotationDraft,
    Session as SessionModel,
    TenureComparisonEntry,
    TrackedVehicle,
    UploadedFile,
    User,
    new_id,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_user(db_session: Session):
    user = User(
        id=new_id(),
        email="staff@risklocker.local",
        password_hash="dummy_hash",
        name="Staff Member",
        role="staff",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def client(db_session: Session, test_user: User):
    app = FastAPI()
    app.include_router(sessions_router.router, prefix="/api")

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_current_user():
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[current_user] = override_current_user

    with TestClient(app) as test_client:
        yield test_client


def test_session_document_type_toggle(client: TestClient, db_session: Session, test_user: User):
    # 1. Setup vehicle & tenure
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

    batch = Batch(id=new_id(), owner_id=test_user.id, name="Test Batch")
    db_session.add(batch)
    db_session.flush()

    # 2. Add an uploaded file and quotation session
    u1 = UploadedFile(
        id=new_id(),
        batch_id=batch.id,
        owner_id=test_user.id,
        original_filename="20260930_JQM2682_CoverNote_Amgen.pdf",
        content_type="application/pdf",
        storage_path="source/cn1.pdf",
        size_bytes=225000,
    )
    db_session.add(u1)

    d1 = QuotationDraft(
        id=new_id(),
        uploaded_file_id=u1.id,
        owner_id=test_user.id,
        fields={
            "sum_insured": {"value": "50000.00"},
            "total_amount": {"value": "1350.00"},
        },
    )
    db_session.add(d1)

    s1 = SessionModel(
        id=new_id(),
        owner_id=test_user.id,
        tenure_id=tenure.id,
        uploaded_file_id=u1.id,
        draft_id=d1.id,
        detected_company="AmAssurance",
        document_type="quotation",
        tenure_version=1,
        is_tenure_active=True,
    )
    db_session.add(s1)

    # Add a comparison entry for this quote
    entry = TenureComparisonEntry(
        id=new_id(),
        tenure_id=tenure.id,
        session_id=s1.id,
        company_name="AmAssurance",
        sum_insured=50000.0,
        motor_premium=1350.0,
    )
    db_session.add(entry)
    db_session.commit()

    # Verify initial state
    assert s1.document_type == "quotation"
    assert tenure.covernote_session_id is None
    assert tenure.stage == "Quotations"

    # Step 1: Patch document_type to "covernote"
    resp = client.patch(f"/api/sessions/{s1.id}", json={"document_type": "covernote"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "success"
    assert data["document_type"] == "covernote"

    db_session.refresh(s1)
    db_session.refresh(tenure)

    assert s1.document_type == "covernote"
    assert tenure.covernote_session_id == s1.id
    assert tenure.stage == "Issue Policy"

    # Comparison entry should have been detached / deleted
    entries = db_session.query(TenureComparisonEntry).filter_by(tenure_id=tenure.id, session_id=s1.id).all()
    assert len(entries) == 0

    # Step 2: Flip back to "quotation"
    resp2 = client.patch(f"/api/sessions/{s1.id}", json={"document_type": "quotation"})
    assert resp2.status_code == 200, resp2.text
    data2 = resp2.json()
    assert data2["status"] == "success"
    assert data2["document_type"] == "quotation"

    db_session.refresh(s1)
    db_session.refresh(tenure)

    assert s1.document_type == "quotation"
    assert tenure.covernote_session_id is None
    assert tenure.stage == "Quotations"

