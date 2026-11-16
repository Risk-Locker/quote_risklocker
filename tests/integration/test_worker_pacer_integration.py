"""Integration test for extraction worker PacerSentinel wiring and quota protection."""

import hashlib
from unittest.mock import MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.extraction.pacer_sentinel import PacerSentinel
from app.models.tables import (
    Base,
    Batch,
    Job,
    QuotationDraft,
    Session,
    UploadedFile,
    new_id,
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


def test_extraction_worker_triggers_pacer_sentinel_acquire(db_session):
    """Verify that extraction worker acquires slot from PacerSentinel and respects pacing delay."""
    # Setup test DB entities
    session_id = new_id()
    draft_id = new_id()
    batch_id = new_id()
    uploaded_id = new_id()
    job_id = new_id()

    # Create dummy PDF bytes
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((10, 10), "Test quotation document for pacer wiring")
    pdf_bytes = doc.tobytes()
    doc.close()
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()

    owner_id = new_id()
    batch = Batch(id=batch_id, owner_id=owner_id, name="Upload")
    uploaded = UploadedFile(
        id=uploaded_id,
        owner_id=owner_id,
        batch_id=batch_id,
        original_filename="test.pdf",
        content_type="application/pdf",
        storage_provider="supabase",
        storage_path="tenants/default/uploads/test.pdf",
        storage_sha256=pdf_hash,
    )
    draft = QuotationDraft(
        id=draft_id,
        uploaded_file_id=uploaded_id,
        owner_id=owner_id,
        revision=1,
        fields={},
        scalar_decisions={},
    )
    sess = Session(
        id=session_id,
        owner_id=owner_id,
        uploaded_file_id=uploaded_id,
        draft_id=draft_id,
        status="active",
    )
    from datetime import datetime, timezone, timedelta
    now_utc = datetime.now(timezone.utc)
    job = Job(
        id=job_id,
        owner_id=owner_id,
        session_id=session_id,
        uploaded_file_id=uploaded_id,
        job_type="extract_pdf",
        idempotency_key=f"idemp-{job_id}",
        state="processing",
        attempt=1,
        max_attempts=3,
        available_at=now_utc,
        lease_owner="test_worker_1",
        lease_expires_at=now_utc + timedelta(minutes=5),
        payload={"enhanced_reading": True},
    )

    db_session.add_all([batch, draft, sess, uploaded, job])
    db_session.commit()

    # Mock storage returning pdf_bytes
    mock_storage = MagicMock()
    mock_storage.download_bytes.return_value = pdf_bytes

    # Track pacer acquire calls
    sleep_calls: list[float] = []
    fake_time = [1000.0]

    def mock_sleep(d: float):
        sleep_calls.append(d)
        fake_time[0] += d

    test_pacer = PacerSentinel(slot_count=2)

    # Wrap acquire to use mock_sleep
    orig_acquire = test_pacer.acquire

    def tracking_acquire(*args, **kwargs):
        kwargs["sleep_fn"] = mock_sleep
        kwargs["time_fn"] = lambda: fake_time[0]
        return orig_acquire(*args, **kwargs)

    test_pacer.acquire = tracking_acquire

    # Mock extractor and context_loader
    mock_extractor = MagicMock(return_value={"full_record": {}, "draft": {"fields": {}}})
    mock_context_loader = MagicMock(return_value={})

    settings = MagicMock()
    settings.max_source_pdf_bytes = 10_000_000

    process_extraction_job(
        db_session,
        settings,
        job,
        worker_id="test_worker_1",
        storage=mock_storage,
        extractor=mock_extractor,
        context_loader=mock_context_loader,
        pacer=test_pacer,
    )

    # Assertions
    assert len(sleep_calls) == 1
    assert sleep_calls[0] == 2.0  # Interactive pacing delay
    assert mock_extractor.called
    # enhanced_reading should be True since 1-page PDF is well under 200k tokens
    assert mock_extractor.call_args[1]["enhanced_reading"] is True


def test_extraction_worker_downgrades_over_capacity_pdf_quota_protection(db_session):
    """Verify that a multi-page PDF exceeding 200k tokens is safely downgraded to deterministic extraction."""
    session_id = new_id()
    draft_id = new_id()
    batch_id = new_id()
    uploaded_id = new_id()
    job_id = new_id()

    # Create large 120-page PDF
    import fitz
    doc = fitz.open()
    for _ in range(120):
        p = doc.new_page()
        p.insert_text((10, 10), "Schedule terms policy contract words text " * 5)
    pdf_bytes = doc.tobytes()
    doc.close()
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()

    owner_id = new_id()
    batch = Batch(id=batch_id, owner_id=owner_id, name="Upload")
    uploaded = UploadedFile(
        id=uploaded_id,
        owner_id=owner_id,
        batch_id=batch_id,
        original_filename="manual_120p.pdf",
        content_type="application/pdf",
        storage_provider="supabase",
        storage_path="tenants/default/uploads/manual_120p.pdf",
        storage_sha256=pdf_hash,
    )
    draft = QuotationDraft(
        id=draft_id,
        uploaded_file_id=uploaded_id,
        owner_id=owner_id,
        revision=1,
        fields={},
        scalar_decisions={},
    )
    sess = Session(
        id=session_id,
        owner_id=owner_id,
        uploaded_file_id=uploaded_id,
        draft_id=draft_id,
        status="active",
    )
    from datetime import datetime, timezone, timedelta
    now_utc = datetime.now(timezone.utc)
    job = Job(
        id=job_id,
        owner_id=owner_id,
        session_id=session_id,
        uploaded_file_id=uploaded_id,
        job_type="extract_pdf",
        idempotency_key=f"idemp-{job_id}",
        state="processing",
        attempt=1,
        max_attempts=3,
        available_at=now_utc,
        lease_owner="test_worker_1",
        lease_expires_at=now_utc + timedelta(minutes=5),
        payload={"enhanced_reading": True},
    )

    db_session.add_all([batch, draft, sess, uploaded, job])
    db_session.commit()

    mock_storage = MagicMock()
    mock_storage.download_bytes.return_value = pdf_bytes

    test_pacer = PacerSentinel(slot_count=2)
    mock_extractor = MagicMock(return_value={"full_record": {}, "draft": {"fields": {}}})
    mock_context_loader = MagicMock(return_value={})

    settings = MagicMock()
    settings.max_source_pdf_bytes = 50_000_000

    process_extraction_job(
        db_session,
        settings,
        job,
        worker_id="test_worker_1",
        storage=mock_storage,
        extractor=mock_extractor,
        context_loader=mock_context_loader,
        pacer=test_pacer,
    )

    # 120-page document (120 * 2000 = 240,000 image tokens > 200,000 ceiling)
    # Must be safely downgraded to enhanced_reading=False to protect Google AI Studio fleet
    assert mock_extractor.called
    assert mock_extractor.call_args[1]["enhanced_reading"] is False
