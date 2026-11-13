"""Unit tests for Storage Janitor Service."""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.models.tables import (
    Base,
    Batch,
    BusinessAsset,
    InsuranceTenure,
    QuotationDraft,
    Session as SessionModel,
    TenureComparisonEntry,
    TrackedVehicle,
    UploadedFile,
    User,
    new_id,
)
from app.services.storage_janitor_service import (
    delete_file_safely,
    prune_superseded_quotations,
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
def test_setup(db_session: Session, tmp_path: Path):
    user = User(
        id=new_id(),
        email="janitor@risklocker.local",
        password_hash="dummy",
        name="Janitor Test",
        role="admin",
    )
    db_session.add(user)

    vehicle = TrackedVehicle(
        id=new_id(),
        vehicle_no="JQM2682",
        car_brand="HINO",
        car_model="500",
    )
    db_session.add(vehicle)

    batch = Batch(id=new_id(), owner_id=user.id, name="Janitor Batch")
    db_session.add(batch)

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

    return {
        "user": user,
        "vehicle": vehicle,
        "batch": batch,
        "tenure": tenure,
        "tmp_path": tmp_path,
    }


def _create_session(
    db: Session,
    user: User,
    tenure: InsuranceTenure,
    uploaded_file: UploadedFile,
    **session_kwargs,
) -> SessionModel:
    draft = QuotationDraft(
        id=new_id(),
        uploaded_file_id=uploaded_file.id,
        owner_id=user.id,
        fields={},
    )
    db.add(draft)
    db.flush()

    sess = SessionModel(
        id=new_id(),
        owner_id=user.id,
        tenure_id=tenure.id,
        uploaded_file_id=uploaded_file.id,
        draft_id=draft.id,
        **session_kwargs,
    )
    db.add(sess)
    db.flush()
    return sess


def test_dry_run_identifies_candidates_without_deleting(db_session: Session, test_setup: dict):
    tmp_path = test_setup["tmp_path"]
    user = test_setup["user"]
    batch = test_setup["batch"]
    tenure = test_setup["tenure"]

    dummy_file = tmp_path / "quote_v1.pdf"
    dummy_file.write_bytes(b"dummy pdf content 12345")

    u1 = UploadedFile(
        id=new_id(),
        batch_id=batch.id,
        owner_id=user.id,
        original_filename="quote_v1.pdf",
        content_type="application/pdf",
        storage_path=str(dummy_file),
        size_bytes=len(dummy_file.read_bytes()),
    )
    db_session.add(u1)
    db_session.flush()

    s1 = _create_session(
        db_session,
        user,
        tenure,
        u1,
        detected_company="AmAssurance",
        document_type="quotation",
        tenure_version=1,
        is_tenure_active=False,
        duplicate_resolution="superseded",
    )
    db_session.commit()

    result = prune_superseded_quotations(db_session, tenure_id=tenure.id, dry_run=True)

    assert result["dry_run"] is True
    assert result["pruned_files_count"] == 1
    assert result["reclaimed_bytes"] == len(dummy_file.read_bytes())
    assert u1.id in result["pruned_file_ids"]

    # File on disk MUST still exist in dry run
    assert dummy_file.exists()

    # DB record MUST NOT be marked deleted
    db_session.refresh(u1)
    assert u1.storage_status != "deleted"
    assert u1.status != "pruned"


def test_active_session_and_covernote_protection(db_session: Session, test_setup: dict):
    tmp_path = test_setup["tmp_path"]
    user = test_setup["user"]
    batch = test_setup["batch"]
    tenure = test_setup["tenure"]

    # File 1: Active quotation
    f1 = tmp_path / "quote_active.pdf"
    f1.write_bytes(b"active quote")
    u_active = UploadedFile(
        id=new_id(),
        batch_id=batch.id,
        owner_id=user.id,
        original_filename="quote_active.pdf",
        content_type="application/pdf",
        storage_path=str(f1),
        size_bytes=len(f1.read_bytes()),
    )
    db_session.add(u_active)
    db_session.flush()

    s_active = _create_session(
        db_session,
        user,
        tenure,
        u_active,
        detected_company="AmAssurance",
        document_type="quotation",
        tenure_version=2,
        is_tenure_active=True,
    )

    # File 2: Bound Cover Note
    f2 = tmp_path / "covernote_bound.pdf"
    f2.write_bytes(b"cover note bound")
    u_cn = UploadedFile(
        id=new_id(),
        batch_id=batch.id,
        owner_id=user.id,
        original_filename="covernote_bound.pdf",
        content_type="application/pdf",
        storage_path=str(f2),
        size_bytes=len(f2.read_bytes()),
    )
    db_session.add(u_cn)
    db_session.flush()

    s_cn = _create_session(
        db_session,
        user,
        tenure,
        u_cn,
        detected_company="Allianz",
        document_type="covernote",
        tenure_version=1,
        is_tenure_active=True,
    )

    tenure.covernote_session_id = s_cn.id
    db_session.commit()

    result = prune_superseded_quotations(db_session, tenure_id=tenure.id, dry_run=False)

    # 0 active/bound files must be pruned
    assert result["pruned_files_count"] == 0
    assert result["reclaimed_bytes"] == 0
    assert f1.exists()
    assert f2.exists()


def test_business_asset_protection(db_session: Session, test_setup: dict):
    tmp_path = test_setup["tmp_path"]
    user = test_setup["user"]
    batch = test_setup["batch"]
    tenure = test_setup["tenure"]

    asset_file = tmp_path / "shared_letterhead.pdf"
    asset_file.write_bytes(b"company logo or letterhead")

    u_asset = UploadedFile(
        id=new_id(),
        batch_id=batch.id,
        owner_id=user.id,
        original_filename="shared_letterhead.pdf",
        content_type="application/pdf",
        storage_path=str(asset_file),
        size_bytes=len(asset_file.read_bytes()),
    )
    db_session.add(u_asset)
    db_session.flush()

    # Inactive session pointing to this file
    s_superseded = _create_session(
        db_session,
        user,
        tenure,
        u_asset,
        detected_company="AmAssurance",
        document_type="quotation",
        is_tenure_active=False,
        duplicate_resolution="superseded",
    )

    # Business asset pointing to same storage path
    asset = BusinessAsset(
        id=new_id(),
        asset_key="amassurance_logo",
        asset_kind="logo",
        label="AmAssurance Logo",
        original_filename="shared_letterhead.pdf",
        content_type="application/pdf",
        content_hash="mockhash",
        storage_path=str(asset_file),
        size_bytes=len(asset_file.read_bytes()),
    )
    db_session.add(asset)
    db_session.commit()

    result = prune_superseded_quotations(db_session, tenure_id=tenure.id, dry_run=False)

    # Must be protected because business asset references the path
    assert result["pruned_files_count"] == 0
    assert asset_file.exists()


def test_actual_pruning_and_resilience(db_session: Session, test_setup: dict):
    tmp_path = test_setup["tmp_path"]
    user = test_setup["user"]
    batch = test_setup["batch"]
    tenure = test_setup["tenure"]

    # 1. Existing file that will be deleted
    f1 = tmp_path / "to_delete.pdf"
    f1.write_bytes(b"1234567890")
    u1 = UploadedFile(
        id=new_id(),
        batch_id=batch.id,
        owner_id=user.id,
        original_filename="to_delete.pdf",
        content_type="application/pdf",
        storage_path=str(f1),
        size_bytes=10,
    )
    db_session.add(u1)
    db_session.flush()

    s1 = _create_session(
        db_session,
        user,
        tenure,
        u1,
        detected_company="AmAssurance",
        document_type="quotation",
        tenure_version=1,
        is_tenure_active=False,
        duplicate_resolution="superseded",
    )

    # 2. File already missing from disk (resilience test)
    u_missing = UploadedFile(
        id=new_id(),
        batch_id=batch.id,
        owner_id=user.id,
        original_filename="missing.pdf",
        content_type="application/pdf",
        storage_path=str(tmp_path / "non_existent.pdf"),
        size_bytes=20,
    )
    db_session.add(u_missing)
    db_session.flush()

    s_missing = _create_session(
        db_session,
        user,
        tenure,
        u_missing,
        detected_company="Etiqa",
        document_type="quotation",
        tenure_version=1,
        is_tenure_active=False,
        duplicate_resolution="superseded",
    )
    db_session.commit()

    result = prune_superseded_quotations(db_session, tenure_id=tenure.id, dry_run=False)

    assert result["pruned_files_count"] == 2
    assert result["reclaimed_bytes"] == 30
    assert not f1.exists()

    db_session.refresh(u1)
    assert u1.status == "pruned"
    assert u1.storage_status == "deleted"
    assert u1.storage_deleted_at is not None

    db_session.refresh(s1)
    assert s1.duplicate_resolution == "superseded_pruned"
    assert s1.status == "trash"
