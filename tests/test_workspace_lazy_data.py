"""Lazy Staff-safe source/evidence/template reads for session workspaces."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.errors import AppError
from app.models.tables import ExtractionRecord, QuotationDraft, Session, TemplateRevision, UploadedFile
from app.services.workspace_source_service import get_source_evidence, get_source_pages, get_workspace_template_config


def values():
    uploaded = UploadedFile(
        id="file-1", batch_id="batch-1", owner_id="owner-1", original_filename="quote.pdf",
        content_type="application/pdf", storage_path="source/quote.pdf", storage_status="available",
        security_scan={"result": "clean"}, size_bytes=100, status="Check Needed",
    )
    draft = QuotationDraft(
        id="draft-1", uploaded_file_id=uploaded.id, owner_id="owner-1", revision=2,
        fields={"customer_name": {"value": "Test", "status": "check_needed"}}, scalar_decisions={}, warnings=[],
        status="Check Needed", template_revision_id="revision-1",
    )
    session = Session(id="session-1", owner_id="owner-1", uploaded_file_id=uploaded.id, draft_id=draft.id, status="active")
    extraction = ExtractionRecord(
        id="extract-1", uploaded_file_id=uploaded.id, method_summary=["SECRET ENGINE"], raw_text="PRIVATE RAW", ocr_text="OCR",
        page_text=[{"page": 1, "text": "PAGE ONE"}, {"page": 2, "text": "PAGE TWO"}, {"page": 3, "text": "PAGE THREE"}],
        words=[], blocks=[], tables=[], images=[], regions=[], candidates={
            "customer_name": [{"value": "Test", "score": 0.91, "source_method": "secret_regex", "page": 1, "evidence": "Customer: Test", "bbox": [1, 2, 3, 4]}]
        }, benefit_lines=[], company_resolution={}, warnings=[],
    )
    revision = TemplateRevision(
        id="revision-1", template_id="template-1", revision_number=4, state="published", page_profile_id="profile-1",
        config={"canvas": {"width": 794, "height": 1123, "elements": [{"id": "locked", "locked": True}]}}, config_hash="a" * 64,
    )
    return uploaded, draft, session, extraction, revision


class Rows:
    def __init__(self, rows): self.rows = rows
    def all(self): return list(self.rows)


class Db:
    def __init__(self, items): self.items = {(type(item), item.id): item for item in items}
    def get(self, model, object_id): return self.items.get((model, object_id))
    def scalars(self, statement):
        entity = statement.column_descriptions[0].get("entity") if statement.column_descriptions else None
        return Rows([item for (model, _id), item in self.items.items() if model is entity])
    def scalar(self, statement):
        rows = self.scalars(statement).all()
        return rows[0] if rows else None


def staff(): return SimpleNamespace(id="staff-1", role="staff")


def test_source_pages_are_paginated_and_do_not_include_raw_or_engine_details():
    result = get_source_pages(Db(values()), staff(), "session-1", page=2, page_size=1)
    assert result == {
        "items": [{"page": 2, "text": "PAGE TWO"}],
        "page": 2,
        "page_size": 1,
        "total": 3,
        "source_pdf_url": "/uploaded-files/file-1/content",
    }
    assert "PRIVATE RAW" not in str(result)
    assert "SECRET ENGINE" not in str(result)


def test_evidence_omits_scores_methods_coordinates_and_requires_known_field():
    result = get_source_evidence(Db(values()), staff(), "session-1", "customer_name")
    assert result == {"field": "customer_name", "items": [{"value": "Test", "page": 1, "snippet": "Customer: Test"}]}
    assert "score" not in str(result)
    assert "method" not in str(result)
    assert "bbox" not in str(result)

    with pytest.raises(AppError) as error:
        get_source_evidence(Db(values()), staff(), "session-1", "not-a-field")
    assert error.value.status_code == 404


def test_template_config_uses_override_only_for_exact_binding():
    items = list(values())
    draft = items[1]
    draft.layout_override = {"canvas": {"width": 794, "height": 1123, "elements": [{"id": "override"}]}}
    draft.layout_override_template_id = "template-1"
    draft.layout_override_template_revision_id = "revision-1"
    draft.layout_override_base_hash = "a" * 64

    result = get_workspace_template_config(Db(items), staff(), "session-1")
    assert result["source"] == "session_override"
    assert result["config"]["canvas"]["elements"][0]["id"] == "override"
    assert result["binding"] == {"template_id": "template-1", "template_revision_id": "revision-1", "base_hash": "a" * 64}

    draft.layout_override_base_hash = "b" * 64
    result = get_workspace_template_config(Db(items), staff(), "session-1")
    assert result["source"] == "template_revision"
    assert result["config"]["canvas"]["elements"][0]["id"] == "locked"


def test_template_config_requires_published_pinned_revision():
    items = list(values())
    items[1].template_revision_id = None
    with pytest.raises(AppError, match="template") as error:
        get_workspace_template_config(Db(items), staff(), "session-1")
    assert error.value.status_code == 409
