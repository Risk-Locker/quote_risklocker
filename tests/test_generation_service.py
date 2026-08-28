"""Exact-revision snapshot and idempotent generation queue contract."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
os.environ.setdefault("APP_ENV", "test")

from app.core.errors import AppError  # noqa: E402
from app.models.enums import RecordStatus  # noqa: E402
from app.models.tables import (  # noqa: E402
    DraftBenefitSelection,
    DraftSourceLineDecision,
    GeneratedPdfVersion,
    Job,
    OutputTemplateConfig,
    QuotationDraft,
    RenderSnapshot,
    Session,
    TemplatePageProfile,
    TemplateRevision,
    UploadedFile,
)
from app.services.generation_service import request_version_generation  # noqa: E402


NOW = datetime.now(timezone.utc)


class Scalars:
    def __init__(self, rows): self.rows = rows
    def all(self): return list(self.rows)
    def first(self): return self.rows[0] if self.rows else None


class FakeDb:
    def __init__(self, values):
        self.values = {(type(item), item.id): item for item in values}
        self.added = []
        self.commits = 0
        self.executed = []

    def get(self, model, object_id): return self.values.get((model, object_id))
    def scalars(self, statement):
        entity = statement.column_descriptions[0].get("entity") if statement.column_descriptions else None
        return Scalars([item for (model, _), item in self.values.items() if model is entity] + [item for item in self.added if isinstance(item, entity)])
    def scalar(self, statement):
        rows = self.scalars(statement).all()
        return rows[0] if rows else None
    def add(self, item):
        self.added.append(item)
        self.values[(type(item), item.id)] = item
    def execute(self, statement, parameters=None): self.executed.append((str(statement), parameters or {}))
    def flush(self): return None
    def commit(self): self.commits += 1
    def refresh(self, _item): return None


def objects(*, blockers=False):
    uploaded = UploadedFile(
        id="file-1", batch_id="batch-1", owner_id="owner-1", original_filename="quote.pdf",
        content_type="application/pdf", storage_path="source/quote.pdf", storage_status="available",
        security_scan={"result": "clean"}, size_bytes=100, status=RecordStatus.READY.value,
    )
    fields = {"customer_name": {"value": "Customer", "status": "ready", "message": ""}}
    decisions = {} if blockers else {"customer_name": {"decision": "confirm"}}
    draft = QuotationDraft(
        id="draft-1", uploaded_file_id=uploaded.id, owner_id="owner-1", revision=7,
        fields=fields, scalar_decisions=decisions, warnings=[], status=RecordStatus.READY.value,
        template_revision_id=None if blockers else "template-revision-1", catalog_revision_id="catalog-revision-1",
        reviewed_at=NOW, reviewed_by="staff-1",
    )
    session = Session(id="session-1", owner_id="owner-1", uploaded_file_id=uploaded.id, draft_id=draft.id, status="active")
    template = OutputTemplateConfig(id="template-1", name="Master", fixed_fields={}, status="active")
    page = TemplatePageProfile(id="profile-1", profile_key="a4", name="A4", width=794, height=1123, unit="px", safe_margins={}, bleed={}, background_behavior="clip")
    config = {"version": 7, "page_profile": {"profile_key": "a4", "width": 794, "height": 1123, "unit": "px"}, "canvas": {"width": 794, "height": 1123, "elements": []}}
    revision = TemplateRevision(
        id="template-revision-1", template_id=template.id, revision_number=1, state="published",
        page_profile_id=page.id, config=config, config_hash="a" * 64, published_at=NOW,
    )
    if blockers:
        line = DraftSourceLineDecision(id="line-1", draft_id=draft.id, source_line_id="s1", disposition="unresolved")
        return uploaded, draft, session, template, page, revision, line
    return uploaded, draft, session, template, page, revision


def user(): return SimpleNamespace(id="staff-1", role="staff")


def test_request_snapshots_exact_revision_then_enqueues_one_render_job():
    db = FakeDb(objects())
    result = request_version_generation(db, user(), "session-1", draft_revision=7, idempotency_key="gen-1")
    snapshots = [item for item in db.added if isinstance(item, RenderSnapshot)]
    jobs = [item for item in db.added if isinstance(item, Job)]
    assert result["created"] is True
    assert result["job"].job_type == "render_pdf"
    assert len(snapshots) == 1
    assert len(jobs) == 1
    assert jobs[0].payload["render_snapshot_id"] == snapshots[0].id
    assert snapshots[0].draft_revision == 7
    assert snapshots[0].context["fields"]["customer_name"]["value"] == "Customer"
    assert snapshots[0].context["source_filename"] == "quote.pdf"
    assert snapshots[0].context_hash
    assert db.commits == 1
    assert "pg_advisory_xact_lock" in db.executed[0][0]
    assert db.executed[0][1] == {"lock_key": "render_pdf:gen-1"}


def test_same_key_is_idempotent_and_different_user_cannot_reuse_it():
    existing = Job(
        id="job-1", owner_id="staff-1", session_id="session-1", uploaded_file_id="file-1",
        job_type="render_pdf", idempotency_key="gen-1", state="queued", payload={"draft_revision": 7},
        result={}, safe_error={}, progress=0, attempt=0, max_attempts=3, available_at=NOW,
    )
    db = FakeDb([*objects(), existing])
    result = request_version_generation(db, user(), "session-1", draft_revision=7, idempotency_key="gen-1")
    assert result == {"created": False, "job": existing, "version": None}
    with pytest.raises(AppError, match="idempotency"):
        request_version_generation(db, SimpleNamespace(id="other", role="staff"), "session-1", draft_revision=7, idempotency_key="gen-1")


def test_request_rejects_stale_revision_and_generation_blockers():
    db = FakeDb(objects())
    with pytest.raises(AppError) as stale:
        request_version_generation(db, user(), "session-1", draft_revision=6, idempotency_key="gen-stale")
    assert stale.value.status_code == 409

    blocked_db = FakeDb(objects(blockers=True))
    with pytest.raises(AppError, match="blocker"):
        request_version_generation(blocked_db, user(), "session-1", draft_revision=7, idempotency_key="gen-blocked")


def test_existing_version_for_key_returns_without_creating_job():
    version = GeneratedPdfVersion(
        id="version-1", draft_id="draft-1", uploaded_file_id="file-1", version_number=1,
        draft_revision=7, idempotency_key="gen-1", filename="quote.pdf", storage_path="generated/quote.pdf",
        draft_snapshot={}, template_snapshot={}, render_context_snapshot={}, renderer_version="v7",
        generated_by="staff-1", generated_at=NOW,
    )
    db = FakeDb([*objects(), version])
    result = request_version_generation(db, user(), "session-1", draft_revision=7, idempotency_key="gen-1")
    assert result == {"created": False, "job": None, "version": version}
    assert not db.added
