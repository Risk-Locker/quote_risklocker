"""Unit tests for Milestone 1: Sandbox/Test Session Ledger Isolation & Sessions Service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.extraction.pacer_sentinel import PacerSentinel

from app.models.tables import (
    Base,
    Batch,
    CustomerAccount,
    InsuranceTenure,
    Job,
    OutputTemplateConfig,
    QuotationDraft,
    Session as SessionModel,
    TemplateRevision,
    TrackedVehicle,
    UploadedFile,
    User,
    new_id,
)
from app.services.session_service import (
    get_session_tab_counts,
    list_sessions,
    purge_test_sessions,
    serialize_session,
)
from app.workers.extraction_worker import process_extraction_job


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
def staff_user(db_session: Session) -> User:
    user = User(
        id=new_id(),
        email="staff@risklocker.local",
        password_hash="hash",
        name="Staff User",
        role="staff",
    )
    db_session.add(user)
    db_session.commit()
    return user


def test_sandbox_extraction_never_pollutes_live_ledger(db_session: Session, staff_user: User, tmp_path: Path):
    """Verify is_test=True extraction jobs never create CustomerAccount, TrackedVehicle, or InsuranceTenure rows."""
    import hashlib

    pdf_bytes = b"%PDF-1.4\n1 0 obj <<>> endobj\ntrailer <<>>\n%%EOF"
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    ephemeral_file = tmp_path / "test_upload.pdf"
    ephemeral_file.write_bytes(pdf_bytes)

    batch = Batch(id=new_id(), owner_id=staff_user.id, name="Test Upload", status="preparing", is_test=True)
    uploaded = UploadedFile(
        id=new_id(),
        batch_id=batch.id,
        owner_id=staff_user.id,
        original_filename="2026_JUM2709_QBE_Test.pdf",
        content_type="application/pdf",
        storage_path=str(ephemeral_file),
        storage_provider="local_ephemeral",
        storage_sha256=sha,
        size_bytes=len(pdf_bytes),
        status="preparing",
        is_test=True,
    )
    draft = QuotationDraft(
        id=new_id(),
        revision=1,
        uploaded_file_id=uploaded.id,
        owner_id=staff_user.id,
        status="preparing",
        fields={},
        scalar_decisions={},
        warnings=[],
    )
    sess = SessionModel(
        id=new_id(),
        owner_id=staff_user.id,
        uploaded_file_id=uploaded.id,
        draft_id=draft.id,
        status="active",
        is_test=True,
    )
    job = Job(
        id=new_id(),
        owner_id=staff_user.id,
        session_id=sess.id,
        uploaded_file_id=uploaded.id,
        job_type="extract_pdf",
        idempotency_key=f"test-{new_id()}",
        state="processing",
        lease_owner="worker-1",
        payload={"enhanced_reading": False, "is_test": True},
    )
    db_session.add_all([batch, uploaded, draft, sess, job])
    db_session.commit()

    def fake_extractor(path, **kwargs):
        return {
            "full_record": {
                "raw_text": "Quotation QBE Insurance JUM2709",
                "page_text": ["Quotation QBE Insurance JUM2709"],
                "benefit_lines": [],
            },
            "draft": {
                "status": "ready",
                "fields": {
                    "customer_name": {"value": "SANDBOX TEST CLIENT SDN BHD", "status": "ready"},
                    "ic_or_brn": {"value": "202001099999", "status": "ready"},
                    "vehicle_no": {"value": "JUM2709", "status": "ready"},
                    "car_brand": {"value": "HONDA", "status": "ready"},
                    "car_model": {"value": "CIVIC 1.5 TC-P", "status": "ready"},
                    "insurance_company": {"value": "QBE", "status": "ready"},
                    "cover_start_date": {"value": "01/11/2026", "status": "ready"},
                    "cover_end_date": {"value": "31/10/2027", "status": "ready"},
                    "total_amount": {"value": "1850.00", "status": "ready"},
                },
                "warnings": [],
            },
        }

    class DummySettings:
        max_source_pdf_bytes = 20 * 1024 * 1024

    class DummyPacer:
        def acquire(self, estimated_tokens: int = 0, **_kwargs):
            return 0, 0.0

    process_extraction_job(
        db_session,
        DummySettings(),
        job,
        worker_id="worker-1",
        extractor=fake_extractor,
        context_loader=lambda _db: {"db_companies": []},
        pacer=cast(PacerSentinel, DummyPacer()),
    )

    db_session.refresh(sess)
    db_session.refresh(draft)

    # Assert 0 rows leaked into live CustomerAccount, TrackedVehicle, or InsuranceTenure
    assert db_session.scalar(select(func.count(CustomerAccount.id))) == 0
    assert db_session.scalar(select(func.count(TrackedVehicle.id))) == 0
    assert db_session.scalar(select(func.count(InsuranceTenure.id))) == 0
    assert sess.tenure_id is None
    assert sess.customer_id is None
    assert sess.tracked_vehicle_id is None
    assert sess.quotation_ref is not None and sess.quotation_ref.startswith("TEST-RL")
    assert draft.fields["quotation_reference"]["value"].startswith("TEST-RL")


def test_list_sessions_defaults_to_newest_first_and_purges_sandbox(db_session: Session, staff_user: User):
    """Verify list_sessions defaults to newest-first (date_desc), computes tab_counts, and purges only test sessions."""
    now = datetime.now(timezone.utc)
    batch = Batch(id=new_id(), owner_id=staff_user.id, name="Batch")
    tv = TrackedVehicle(id=new_id(), vehicle_no="ZZZ9999", car_brand="Proton", car_model="X50")
    db_session.add_all([batch, tv])
    db_session.flush()

    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=tv.id,
        vehicle_no="ZZZ9999",
        customer_name="Live Client",
        coverage_start_date=now,
        coverage_end_date=now + timedelta(days=364),
        expiry_month="2027-11",
        is_discarded=False,
    )
    db_session.add(tenure)
    db_session.flush()

    def make_sess(plate: str, created_offset_minutes: int, is_test: bool, doc_type: str = "quotation"):
        uf = UploadedFile(
            id=new_id(),
            batch_id=batch.id,
            owner_id=staff_user.id,
            original_filename=f"{plate}.pdf",
            content_type="application/pdf",
            storage_path=f"/test/{plate}.pdf",
        )
        qd = QuotationDraft(
            id=new_id(),
            uploaded_file_id=uf.id,
            owner_id=staff_user.id,
            fields={"vehicle_no": {"value": plate}},
        )
        db_session.add_all([uf, qd])
        db_session.flush()
        s = SessionModel(
            id=new_id(),
            owner_id=staff_user.id,
            uploaded_file_id=uf.id,
            draft_id=qd.id,
            tenure_id=None if is_test else tenure.id,
            is_test=is_test,
            document_type=doc_type,
            status="active",
            created_at=now + timedelta(minutes=created_offset_minutes),
        )
        db_session.add(s)
        return s

    older_a = make_sess("AAA1111", -30, is_test=False, doc_type="quotation")
    newer_z = make_sess("ZZZ9999", -5, is_test=False, doc_type="covernote")
    newest_test = make_sess("TEST888", -1, is_test=True, doc_type="quotation")
    db_session.commit()

    rows, total = list_sessions(db_session, user_id=staff_user.id)
    assert total == 3
    # Newest uploaded must be first by default
    assert [r.id for r in rows] == [newest_test.id, newer_z.id, older_a.id]

    counts = get_session_tab_counts(db_session)
    assert counts["all"] == 3
    assert counts["live"] == 2
    assert counts["quotations"] == 1
    assert counts["covernotes"] == 1
    assert counts["test"] == 1

    purged = purge_test_sessions(db_session)
    assert purged == 1

    counts_after = get_session_tab_counts(db_session)
    assert counts_after["test"] == 0
    assert counts_after["live"] == 2
