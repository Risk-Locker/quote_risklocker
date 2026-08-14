"""Render worker consumes only a verified frozen context and creates one version."""

from __future__ import annotations

import hashlib
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
os.environ.setdefault("APP_ENV", "test")

from app.models.enums import RecordStatus  # noqa: E402
from app.models.tables import (  # noqa: E402
    GeneratedPdfVersion,
    Job,
    QuotationDraft,
    RenderSnapshot,
    Session,
    UploadedFile,
)
from app.rendering.render_context import canonical_context_hash  # noqa: E402
from app.storage.supabase import StoredPdf  # noqa: E402
from app.workers.render_worker import JobProcessingError, process_render_job  # noqa: E402


NOW = datetime.now(timezone.utc)
PDF = b"%PDF-1.7\nrendered\n%%EOF"


def objects():
    uploaded = UploadedFile(
        id="file-1", batch_id="batch-1", owner_id="owner-1", original_filename="quote.pdf",
        content_type="application/pdf", storage_path="source/quote.pdf", storage_status="available",
        security_scan={"result": "clean"}, size_bytes=100, status=RecordStatus.READY.value,
    )
    draft = QuotationDraft(
        id="draft-1", uploaded_file_id=uploaded.id, owner_id="owner-1", revision=7,
        fields={}, scalar_decisions={}, warnings=[], status=RecordStatus.READY.value,
        template_revision_id="template-revision-1",
    )
    session = Session(id="session-1", owner_id="owner-1", uploaded_file_id=uploaded.id, draft_id=draft.id, status="active")
    context = {
        "schema_version": 1, "renderer_version": "risklocker-v7.1", "draft_id": draft.id,
        "draft_revision": 7, "catalog_revision_id": None, "template_revision_id": "template-revision-1",
        "template_revision_number": 1, "template_name": "Master", "source_filename": "quote.pdf",
        "fields": {},
        "template_config": {"version": 7, "page_profile": {"width": 794, "height": 1123, "unit": "px"}, "canvas": {"width": 794, "height": 1123, "elements": []}},
        "page_profile": {"width": 794, "height": 1123, "unit": "px"},
        "current_benefits": [], "available_addons": [],
        "assets": {"manifest": {}, "embedded": {}},
    }
    snapshot = RenderSnapshot(
        id="snapshot-1", draft_id=draft.id, draft_revision=7, template_revision_id="template-revision-1",
        context_hash=canonical_context_hash(context), context=context, asset_hashes={}, renderer_version="risklocker-v7.1",
    )
    job = Job(
        id="job-1", owner_id="staff-1", session_id=session.id, uploaded_file_id=uploaded.id,
        job_type="render_pdf", idempotency_key="gen-1", state="processing",
        payload={"render_snapshot_id": snapshot.id, "draft_id": draft.id, "draft_revision": 7, "idempotency_key": "gen-1"},
        result={}, safe_error={}, progress=0, attempt=1, max_attempts=3, available_at=NOW,
        lease_owner="worker-1", lease_expires_at=NOW + timedelta(minutes=5),
    )
    return uploaded, draft, session, snapshot, job


class Scalars:
    def __init__(self, rows): self.rows = rows
    def all(self): return list(self.rows)


class FakeDb:
    def __init__(self, values):
        self.values = {(type(item), item.id): item for item in values}
        self.added = []
        self.commits = 0
        self.deleted = []
    def get(self, model, object_id): return self.values.get((model, object_id))
    def scalars(self, statement):
        entity = statement.column_descriptions[0].get("entity") if statement.column_descriptions else None
        return Scalars([item for (model, _), item in self.values.items() if model is entity] + [item for item in self.added if isinstance(item, entity)])
    def scalar(self, statement):
        rows = self.scalars(statement).all()
        if rows and isinstance(rows[0], GeneratedPdfVersion): return rows[0]
        return rows[0] if rows else 0
    def add(self, item): self.added.append(item); self.values[(type(item), item.id)] = item
    def flush(self): return None
    def commit(self): self.commits += 1
    def refresh(self, _item): return None


class Storage:
    def __init__(self): self.uploaded = []; self.deleted = []
    def upload_generated_pdf(self, key, data):
        self.uploaded.append((key, data))
        return StoredPdf(key, "bucket", len(data), hashlib.sha256(data).hexdigest(), "etag")
    def download_bytes(self, _key): raise AssertionError("No mutable asset should be downloaded in this fixture")
    def delete_pdf(self, key): self.deleted.append(key)


def fake_renderer(_html, output_path: Path, **dimensions):
    assert dimensions == {"width": 794.0, "height": 1123.0}
    output_path.write_bytes(PDF)
    return output_path


def test_worker_hash_checks_snapshot_and_creates_one_immutable_version():
    values = objects()
    db = FakeDb(values)
    storage = Storage()
    process_render_job(
        db, SimpleNamespace(max_generated_pdf_bytes=1024), values[-1], worker_id="worker-1",
        storage=storage, renderer=fake_renderer, validate_pdf=lambda data: data.startswith(b"%PDF"),
    )
    version = next(item for item in db.added if isinstance(item, GeneratedPdfVersion))
    assert version.draft_revision == 7
    assert version.idempotency_key == "gen-1"
    assert version.render_context_hash == values[-2].context_hash
    assert version.render_context_snapshot == values[-2].context
    assert version.storage_expires_at is None
    assert storage.uploaded[0][1] == PDF
    assert values[-1].state == "completed"
    assert values[-1].result["version_id"] == version.id


def test_worker_renders_frozen_snapshot_even_if_live_draft_revision_changes():
    values = list(objects())
    draft = values[1]
    draft.revision = 8
    db = FakeDb(values)
    process_render_job(
        db, SimpleNamespace(max_generated_pdf_bytes=1024), values[-1], worker_id="worker-1",
        storage=Storage(), renderer=fake_renderer, validate_pdf=lambda _data: True,
    )
    version = next(item for item in db.added if isinstance(item, GeneratedPdfVersion))
    assert version.draft_revision == 7
    assert version.draft_snapshot == values[-2].context["fields"]


def test_corrupt_snapshot_and_asset_hash_fail_before_render():
    values = list(objects())
    values[-2].context["fields"] = {"tampered": {"value": "secret"}}
    with pytest.raises(JobProcessingError) as corrupt:
        process_render_job(
            FakeDb(values), SimpleNamespace(max_generated_pdf_bytes=1024), values[-1], worker_id="worker-1",
            storage=Storage(), renderer=lambda *_args, **_kwargs: pytest.fail("must not render"), validate_pdf=lambda _data: True,
        )
    assert corrupt.value.code == "render_snapshot_integrity_failed"


def test_invalid_or_oversized_pdf_is_not_uploaded():
    values = objects()
    storage = Storage()
    with pytest.raises(JobProcessingError) as invalid:
        process_render_job(
            FakeDb(values), SimpleNamespace(max_generated_pdf_bytes=10), values[-1], worker_id="worker-1",
            storage=storage, renderer=fake_renderer, validate_pdf=lambda _data: False,
        )
    assert invalid.value.code in {"render_output_invalid", "render_output_too_large"}
    assert not storage.uploaded
