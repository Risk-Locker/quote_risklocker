"""Bounded extraction-worker dispatch and persistence behavior."""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.models.enums import RecordStatus
from app.models.tables import Batch, DraftSourceLineDecision, ExtractionBenefitLine, ExtractionRecord, Job, QuotationDraft, Session, UploadedFile
from app.workers.extraction_worker import JobProcessingError, process_extraction_job, run_one_job
from app.workers.render_worker import JobProcessingError as RenderJobProcessingError


NOW = datetime.now(timezone.utc)
PDF = b"%PDF-1.4 worker source"


def _objects():
    batch = Batch(id="batch-1", owner_id="owner-1", name="Upload", status=RecordStatus.PREPARING.value)
    uploaded = UploadedFile(
        id="file-1",
        batch_id=batch.id,
        owner_id="owner-1",
        original_filename="quote.pdf",
        content_type="application/pdf",
        storage_path="source/file-1.pdf",
        storage_status="available",
        storage_sha256=hashlib.sha256(PDF).hexdigest(),
        security_scan={"result": "clean"},
        size_bytes=len(PDF),
        status=RecordStatus.PREPARING.value,
    )
    draft = QuotationDraft(
        id="draft-1",
        uploaded_file_id=uploaded.id,
        owner_id="owner-1",
        revision=1,
        fields={},
        scalar_decisions={},
        warnings=[],
        status=RecordStatus.PREPARING.value,
    )
    session = Session(
        id="session-1",
        owner_id="owner-1",
        uploaded_file_id=uploaded.id,
        draft_id=draft.id,
        status="active",
    )
    job = Job(
        id="job-1",
        owner_id="owner-1",
        session_id=session.id,
        uploaded_file_id=uploaded.id,
        job_type="extract_pdf",
        idempotency_key="upload-1",
        state="processing",
        payload={"enhanced_reading": True},
        result={},
        safe_error={},
        progress=0,
        attempt=1,
        max_attempts=3,
        available_at=NOW,
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(minutes=5),
    )
    return batch, uploaded, draft, session, job


class FakeDb:
    def __init__(self, objects):
        self.objects = {(type(item), item.id): item for item in objects}
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.claimed = None

    def get(self, model, object_id):
        return self.objects.get((model, object_id))

    def scalar(self, _statement):
        return None

    def scalars(self, _statement):
        return SimpleNamespace(all=lambda: [])

    def add(self, item):
        self.added.append(item)

    def flush(self):
        return None

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, _item):
        return None


class Storage:
    def __init__(self, data=PDF):
        self.data = data
        self.downloaded = []

    def download_bytes(self, key):
        self.downloaded.append(key)
        return self.data


def extraction_result():
    return {
        "full_record": {
            "method_summary": ["native"],
            "raw_text": "PRIVATE CUSTOMER TEXT",
            "ocr_text": "",
            "page_text": [{"page": 1, "text": "PRIVATE CUSTOMER TEXT"}],
            "words": [],
            "blocks": [],
            "tables": [],
            "images": [],
            "regions": [],
            "candidates": {},
            "benefit_lines": [{"line_id": "line-1", "raw_label": "Towing"}],
            "company_resolution": {"company_id": "company-1", "status": "matched"},
            "warnings": [],
            "reading_quality": "check_needed",
        },
        "draft": {
            "status": RecordStatus.CHECK_NEEDED.value,
            "fields": {"insurance_company": {"value": "Nova Mutual", "status": "ready"}},
            "warnings": ["Review values"],
        },
    }


def test_successful_job_persists_initial_extraction_and_completes(tmp_path):
    batch, uploaded, draft, session, job = _objects()
    db = FakeDb([batch, uploaded, draft, session, job])
    seen = {}

    def extractor(path, **kwargs):
        assert path.is_relative_to((ROOT / ".qc-tmp").resolve())
        assert path.read_bytes() == PDF
        seen.update(kwargs)
        return extraction_result()

    process_extraction_job(
        db,
        SimpleNamespace(),
        job,
        worker_id="worker-1",
        storage=Storage(),
        extractor=extractor,
        context_loader=lambda _db: {
            "db_aliases": {"vehicle_no": ["registration"]},
            "db_brands": ["ORBIT"],
            "db_models": ["ZEPHYR"],
            "db_companies": [{"name": "Nova Mutual", "aliases": ["nova"]}],
        },
    )

    record = next(item for item in db.added if isinstance(item, ExtractionRecord))
    persisted_line = next(item for item in db.added if isinstance(item, ExtractionBenefitLine))
    persisted_decision = next(item for item in db.added if isinstance(item, DraftSourceLineDecision))
    assert record.benefit_lines[0]["line_id"] == "line-1"
    assert record.company_resolution["company_id"] == "company-1"
    assert persisted_line.line_id == "line-1"
    assert persisted_line.extraction_record_id == record.id
    assert persisted_decision.source_line_id == persisted_line.id
    assert persisted_decision.draft_id == draft.id
    assert persisted_decision.disposition == "unresolved"
    assert draft.company_id == "company-1"
    assert uploaded.insurance_company_id == "company-1"
    assert draft.fields["insurance_company"]["value"] == "Nova Mutual"
    assert draft.scalar_decisions["insurance_company"]["decision"] == "confirm"
    assert draft.fields["insurance_company"]["status"] == "ready"
    assert draft.revision == 1
    assert uploaded.status == RecordStatus.CHECK_NEEDED.value
    assert batch.status == RecordStatus.CHECK_NEEDED.value
    assert session.detected_company == "Nova Mutual"
    assert job.state == "completed"
    assert job.result == {"session_id": "session-1", "draft_id": "draft-1"}
    assert "PRIVATE CUSTOMER TEXT" not in str(job.result)
    assert seen["enhanced_reading"] is True
    assert seen["db_companies"][0]["name"] == "Nova Mutual"


def test_source_hash_mismatch_fails_before_extraction():
    batch, uploaded, draft, session, job = _objects()
    db = FakeDb([batch, uploaded, draft, session, job])

    with pytest.raises(JobProcessingError) as error:
        process_extraction_job(
            db,
            SimpleNamespace(),
            job,
            worker_id="worker-1",
            storage=Storage(b"tampered"),
            extractor=lambda *_args, **_kwargs: pytest.fail("must not extract"),
            context_loader=lambda _db: {},
        )

    assert error.value.code == "source_integrity_failed"
    assert "tampered" not in error.value.safe_message


def test_worker_dispatch_requeues_a_retryable_failure_without_leaking_exception(monkeypatch):
    batch, uploaded, draft, session, job = _objects()
    db = FakeDb([batch, uploaded, draft, session, job])

    monkeypatch.setattr("app.workers.extraction_worker.claim_next_job", lambda *_args, **_kwargs: job)
    monkeypatch.setattr(
        "app.workers.extraction_worker.process_extraction_job",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("PRIVATE CUSTOMER TEXT")),
    )

    result = run_one_job(db, SimpleNamespace(), worker_id="worker-1", storage=Storage())

    assert result is job
    assert job.state == "queued"
    assert job.safe_error["code"] == "processing_failed"
    assert "PRIVATE" not in job.safe_error["message"]


def test_worker_rejects_unknown_job_type_safely(monkeypatch):
    *objects, job = _objects()
    job.job_type = "unknown"
    db = FakeDb([*objects, job])
    monkeypatch.setattr("app.workers.extraction_worker.claim_next_job", lambda *_args, **_kwargs: job)

    run_one_job(db, SimpleNamespace(), worker_id="worker-1", storage=Storage())

    assert job.safe_error == {"code": "unsupported_job", "message": "This background task is not supported."}


def test_worker_dispatches_render_jobs_through_the_same_single_heavy_slot(monkeypatch):
    *objects, job = _objects()
    job.job_type = "render_pdf"
    db = FakeDb([*objects, job])
    called = {}
    monkeypatch.setattr("app.workers.extraction_worker.claim_next_job", lambda *_args, **_kwargs: job)
    monkeypatch.setattr(
        "app.workers.extraction_worker.process_render_job",
        lambda _db, _settings, selected, **kwargs: called.update(job=selected, worker_id=kwargs["worker_id"]),
    )

    assert run_one_job(db, SimpleNamespace(), worker_id="worker-1", storage=Storage()) is job
    assert called == {"job": job, "worker_id": "worker-1"}


def test_worker_preserves_safe_render_failure_code(monkeypatch):
    *objects, job = _objects()
    job.job_type = "render_pdf"
    db = FakeDb([*objects, job])
    monkeypatch.setattr("app.workers.extraction_worker.claim_next_job", lambda *_args, **_kwargs: job)
    monkeypatch.setattr(
        "app.workers.extraction_worker.process_render_job",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RenderJobProcessingError("renderer_unavailable", "Renderer unavailable.")),
    )
    run_one_job(db, SimpleNamespace(), worker_id="worker-1", storage=Storage())
    assert job.safe_error == {"code": "renderer_unavailable", "message": "Renderer unavailable."}
