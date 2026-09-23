"""Tests for corporate fleet management, fleet vehicle breakdowns, and bulk PDF operations."""

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.models.tables import (
    Base,
    ExtractionRecord,
    GeneratedPdfVersion,
    QuotationDraft,
    Session as SessionModel,
    UploadedFile,
    User,
    new_id,
)
from app.services.client_dossier_service import (
    _categorize_vehicle,
    _resolve_session_client_identity,
    get_client_dossiers,
)
from app.services.quotation_activity_service import bulk_update_quotation_status


@pytest.fixture
def db_session():
    """Hermetic in-memory SQLite database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_resolve_session_client_identity_corporate_and_private():
    # Corporate quotation with corporate customer_name
    fields_corp = {
        "customer_name": {"value": "MEGA FACTORY LOGISTICS SDN BHD"},
        "client_type": {"value": "Company"},
        "ic_or_brn": {"value": "202001012345"},
    }
    name, is_comp, brn = _resolve_session_client_identity(fields_corp)
    assert is_comp is True
    assert name == "MEGA FACTORY LOGISTICS SDN BHD"
    assert brn == "202001012345"

    # Corporate quotation with blank customer_name but corporate insured_name
    fields_insured = {
        "customer_name": {"value": ""},
        "insured_name": {"value": "SYARIKAT PENGANGKUTAN JAYA BHD"},
        "client_type": {"value": "Company"},
    }
    name2, is_comp2, _ = _resolve_session_client_identity(fields_insured)
    assert is_comp2 is True
    assert name2 == "SYARIKAT PENGANGKUTAN JAYA BHD"

    # Private individual client
    fields_ind = {
        "customer_name": {"value": "AHMAD BIN MOHD ALI"},
        "client_type": {"value": "Private"},
        "ic_or_brn": {"value": "900101-14-5555"},
    }
    name3, is_comp3, _ = _resolve_session_client_identity(fields_ind)
    assert is_comp3 is False
    assert name3 == "AHMAD BIN MOHD ALI"


def test_categorize_vehicle_types():
    assert _categorize_vehicle("Lorry", "HINO 300 RIGID") == "lorry"
    assert _categorize_vehicle("Commercial", "ISUZU NPR 75") == "lorry"
    assert _categorize_vehicle("Motorcycle", "YAMAHA Y15ZR") == "motorcycle"
    assert _categorize_vehicle("NonSaloonCar", "MAZDA CX-5") == "suv"
    assert _categorize_vehicle("Car", "HONDA CIVIC") == "sedan"
    assert _categorize_vehicle("EVSaloonCar", "TESLA MODEL 3") == "ev"


def test_bulk_update_quotation_status(db_session):
    user = db_session.query(User).first()
    if not user:
        user = User(id=new_id(), email="fleet_tester@example.com", password_hash="x", name="Fleet Tester", role="admin")
        db_session.add(user)
        db_session.flush()

    from app.models.tables import Batch

    batch = Batch(id=new_id(), owner_id=user.id, name="Fleet Batch")
    db_session.add(batch)
    db_session.flush()

    # Create 3 sessions: 2 for same lorry (AmAssurance and QBE) and 1 for another lorry
    up1 = UploadedFile(id=new_id(), batch_id=batch.id, owner_id=user.id, original_filename="lorry1_amg.pdf", content_type="application/pdf", size_bytes=100, storage_provider="local_ephemeral", storage_path="p1.pdf")
    up2 = UploadedFile(id=new_id(), batch_id=batch.id, owner_id=user.id, original_filename="lorry1_qbe.pdf", content_type="application/pdf", size_bytes=100, storage_provider="local_ephemeral", storage_path="p2.pdf")
    up3 = UploadedFile(id=new_id(), batch_id=batch.id, owner_id=user.id, original_filename="lorry2_amg.pdf", content_type="application/pdf", size_bytes=100, storage_provider="local_ephemeral", storage_path="p3.pdf")
    db_session.add_all([up1, up2, up3])
    db_session.flush()

    d1 = QuotationDraft(id=new_id(), owner_id=user.id, uploaded_file_id=up1.id, fields={"vehicle_no": {"value": "JTC 1111"}, "customer_name": {"value": "ABC LOGISTICS SDN BHD"}, "client_type": {"value": "Company"}}, status="ready")
    d2 = QuotationDraft(id=new_id(), owner_id=user.id, uploaded_file_id=up2.id, fields={"vehicle_no": {"value": "JTC 1111"}, "customer_name": {"value": "ABC LOGISTICS SDN BHD"}, "client_type": {"value": "Company"}}, status="ready")
    d3 = QuotationDraft(id=new_id(), owner_id=user.id, uploaded_file_id=up3.id, fields={"vehicle_no": {"value": "JTC 2222"}, "customer_name": {"value": "ABC LOGISTICS SDN BHD"}, "client_type": {"value": "Company"}}, status="ready")
    db_session.add_all([d1, d2, d3])
    db_session.flush()

    s1 = SessionModel(id=new_id(), owner_id=user.id, uploaded_file_id=up1.id, draft_id=d1.id, detected_company="AmAssurance", quotation_status="pending")
    s2 = SessionModel(id=new_id(), owner_id=user.id, uploaded_file_id=up2.id, draft_id=d2.id, detected_company="QBE", quotation_status="pending")
    s3 = SessionModel(id=new_id(), owner_id=user.id, uploaded_file_id=up3.id, draft_id=d3.id, detected_company="AmAssurance", quotation_status="pending")
    db_session.add_all([s1, s2, s3])
    db_session.commit()

    # Bulk update s1 and s3 to 'hit'
    result = bulk_update_quotation_status(
        db=db_session,
        session_ids=[s1.id, s3.id],
        status="hit",
        coverage_start_date="2026-10-01",
        coverage_end_date="2027-09-30",
        user_id=user.id,
    )
    assert result["updated_count"] == 2
    assert result["error_count"] == 0

    db_session.refresh(s1)
    db_session.refresh(s2)
    db_session.refresh(s3)

    assert s1.quotation_status == "hit"
    assert s3.quotation_status == "hit"
    # Sibling s2 (same vehicle JTC 1111) should be automatically superseded!
    assert s2.quotation_status == "superseded"


def test_bulk_download_zip_endpoint(db_session, monkeypatch):
    user = db_session.query(User).first()
    if not user:
        user = User(id=new_id(), email="zip_tester@example.com", password_hash="x", name="Zip Tester", role="admin")
        db_session.add(user)
        db_session.flush()

    from app.models.tables import Batch
    batch = Batch(id=new_id(), owner_id=user.id, name="Zip Batch")
    db_session.add(batch)
    db_session.flush()

    up = UploadedFile(id=new_id(), batch_id=batch.id, owner_id=user.id, original_filename="fleet_doc.pdf", content_type="application/pdf", size_bytes=32, storage_provider="local_ephemeral", storage_path="fleet_doc.pdf")
    db_session.add(up)
    db_session.flush()

    d = QuotationDraft(id=new_id(), owner_id=user.id, uploaded_file_id=up.id, fields={"vehicle_no": {"value": "JTC 9999"}, "customer_name": {"value": "ABC FLEET SDN BHD"}}, status="ready")
    db_session.add(d)
    db_session.flush()

    s = SessionModel(id=new_id(), owner_id=user.id, uploaded_file_id=up.id, draft_id=d.id, detected_company="AmAssurance", quotation_status="hit")
    db_session.add(s)
    db_session.commit()

    from app.api.routes import sessions_bulk_download_zip
    from app.api.schemas import BulkDownloadZipRequest
    from app.core.config import get_settings

    req = BulkDownloadZipRequest(session_ids=[s.id])
    settings = get_settings()

    # Monkeypatch load_pdf_bytes to return mock PDF content
    monkeypatch.setattr("app.api.routes.load_pdf_bytes", lambda record, settings: b"%PDF-1.4 dummy quotation content")

    response = sessions_bulk_download_zip(req, db=db_session, settings=settings, user=user)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "Risklocker_Quotations_" in response.headers["content-disposition"]

    # Validate zip file contents
    zip_bytes = io.BytesIO(response.body)
    with zipfile.ZipFile(zip_bytes, "r") as zf:
        names = zf.namelist()
        assert len(names) == 1
        assert "JTC9999" in names[0]
