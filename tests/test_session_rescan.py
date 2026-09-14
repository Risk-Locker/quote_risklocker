"""Hermetic tests for session rescan endpoint and service."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.api import routes
from app.api.deps import current_user
from app.core.config import Settings, get_settings
from app.core.errors import AppError, register_error_handlers
from app.db.session import get_db
from app.models.tables import (
    Batch,
    DraftBenefitSelection,
    DraftSourceLineDecision,
    ExtractionBenefitLine,
    ExtractionRecord,
    QuotationDraft,
    Session as QuotationSession,
    UploadedFile,
    User,
)
from app.services.session_rescan_service import _clear_draft_dependents, rescan_session


def test_clear_draft_dependents():
    """Verify child benefit selections, decisions, and extraction lines are purged."""
    db = MagicMock()
    _clear_draft_dependents(db, "draft-101", "extract-rec-101")
    assert db.execute.call_count == 3
    assert db.flush.call_count == 1


def test_rescan_session_not_found():
    db = MagicMock()
    db.get.return_value = None
    user = User(id="u1", role="staff")
    settings = get_settings()

    try:
        rescan_session(db, "non-existent", user, settings)
        assert False, "Expected AppError 404"
    except AppError as err:
        assert err.status_code == 404
        assert "Session not found" in str(err)


def test_rescan_session_pdf_expired(monkeypatch):
    db = MagicMock()
    session = QuotationSession(id="s1", owner_id="u1", uploaded_file_id="up1", draft_id="d1")
    uploaded = UploadedFile(id="up1", owner_id="u1", original_filename="test.pdf", deleted_at=None)
    draft = QuotationDraft(id="d1", uploaded_file_id="up1", owner_id="u1")

    def mock_get(model, obj_id):
        if model == QuotationSession:
            return session
        if model == UploadedFile:
            return uploaded
        if model == QuotationDraft:
            return draft
        return None

    db.get.side_effect = mock_get
    user = User(id="u1", role="staff")
    settings = get_settings()

    def mock_load_pdf_bytes(_uploaded, _settings):
        raise AppError("PDF Expired", 410)

    monkeypatch.setattr("app.services.session_rescan_service.load_pdf_bytes", mock_load_pdf_bytes)

    try:
        rescan_session(db, "s1", user, settings)
        assert False, "Expected AppError 410"
    except AppError as err:
        assert err.status_code == 410
        assert "PDF Expired" in str(err)


def test_rescan_session_in_place_success(monkeypatch):
    session = QuotationSession(id="s1", owner_id="u1", uploaded_file_id="up1", draft_id="d1", quotation_ref="RL260000148")
    uploaded = UploadedFile(id="up1", owner_id="u1", original_filename="test.pdf", deleted_at=None, enhanced_reading=False)
    draft = QuotationDraft(
        id="d1",
        uploaded_file_id="up1",
        owner_id="u1",
        fields={"quotation_reference": {"value": "RL260000148"}},
        status="check_needed",
    )
    rec = ExtractionRecord(id="rec1", uploaded_file_id="up1")

    db = MagicMock()

    def mock_get(model, obj_id):
        if model == QuotationSession:
            return session
        if model == UploadedFile:
            return uploaded
        if model == QuotationDraft:
            return draft
        return None

    db.get.side_effect = mock_get
    db.scalar.return_value = rec

    monkeypatch.setattr("app.services.session_rescan_service.load_pdf_bytes", lambda _u, _s: b"%PDF-1.4 mock")
    monkeypatch.setattr("app.services.session_rescan_service.load_extraction_context", lambda _db: {
        "db_companies": [{"company_id": "c1", "name": "Allianz"}],
        "db_benefit_concepts": [],
        "db_packs": [],
        "db_corrections": [],
    })

    def mock_extract_with_limits(*args, **kwargs):
        return {
            "full_record": {"benefit_lines": [], "company_resolution": {"company_id": "c1"}},
            "draft": {
                "status": "ready",
                "fields": {
                    "customer_name": {"value": "Alice Tan", "status": "ready"},
                    "vehicle_no": {"value": "VAA1234", "status": "ready"},
                    "total_amount": {"value": "1500.00", "status": "ready"},
                },
                "warnings": [],
            },
        }

    monkeypatch.setattr("app.services.session_rescan_service.extract_with_limits", mock_extract_with_limits)
    monkeypatch.setattr("app.services.session_rescan_service.initialize_catalog_review", lambda _db, _draft: {})
    monkeypatch.setattr("app.services.session_rescan_service.auto_apply_extracted_benefits", lambda _db, _draft: 0)

    user = User(id="u1", role="staff")
    settings = get_settings()

    res = rescan_session(db, "s1", user, settings, mode="in_place", engine="native")

    assert res["success"] is True
    assert res["session_id"] == "s1"
    assert res["quotation_ref"] == "RL260000148"
    assert res["mode"] == "in_place"
    assert res["engine_used"] == "native"
    assert draft.fields["customer_name"]["value"] == "Alice Tan"
    assert draft.fields["quotation_reference"]["value"] == "RL260000148"
    assert db.commit.call_count == 1


def test_rescan_session_new_session_success(monkeypatch):
    session = QuotationSession(id="s1", owner_id="u1", uploaded_file_id="up1", draft_id="d1", quotation_ref="RL260000148")
    uploaded = UploadedFile(id="up1", owner_id="u1", original_filename="test.pdf", deleted_at=None, enhanced_reading=False)
    draft = QuotationDraft(
        id="d1",
        uploaded_file_id="up1",
        owner_id="u1",
        fields={"quotation_reference": {"value": "RL260000148"}},
    )

    db = MagicMock()

    def mock_get(model, obj_id):
        if model == QuotationSession:
            return session
        if model == UploadedFile:
            return uploaded
        if model == QuotationDraft:
            return draft
        return None

    db.get.side_effect = mock_get
    monkeypatch.setattr("app.services.session_rescan_service.load_pdf_bytes", lambda _u, _s: b"%PDF-1.4 mock")
    monkeypatch.setattr("app.services.session_rescan_service.generate_quotation_reference", lambda _db, when=None: "RL260000999")
    monkeypatch.setattr("app.services.session_rescan_service.load_extraction_context", lambda _db: {
        "db_companies": [],
        "db_benefit_concepts": [],
        "db_packs": [],
        "db_corrections": [],
    })
    monkeypatch.setattr("app.services.session_rescan_service.extract_with_limits", lambda *a, **k: {
        "full_record": {"benefit_lines": [], "company_resolution": {}},
        "draft": {
            "status": "ready",
            "fields": {
                "customer_name": {"value": "Bob Lee", "status": "ready"},
                "vehicle_no": {"value": "WXX8888", "status": "ready"},
            },
            "warnings": [],
        },
    })
    monkeypatch.setattr("app.services.session_rescan_service.initialize_catalog_review", lambda _db, _draft: {})
    monkeypatch.setattr("app.services.session_rescan_service.auto_apply_extracted_benefits", lambda _db, _draft: 0)

    user = User(id="u1", role="staff")
    settings = get_settings()

    res = rescan_session(db, "s1", user, settings, mode="new_session", engine="native")

    assert res["success"] is True
    assert res["mode"] == "new_session"
    assert res["session_id"] != "s1"
    assert res["quotation_ref"] == "RL260000999"
    # Verify original session ref remained unchanged
    assert session.quotation_ref == "RL260000148"


def test_api_session_rescan_route(monkeypatch):
    """Verify HTTP endpoint handles request body and delegates to service."""
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(routes.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()
    app.dependency_overrides[current_user] = lambda: User(id="staff-1", role="staff")

    monkeypatch.setattr("app.services.session_rescan_service.rescan_session", lambda _db, session_id, user, settings, mode, engine: {
        "success": True,
        "session_id": session_id,
        "quotation_ref": "RL260000148",
        "mode": mode,
        "engine_used": engine,
        "message": "Rescanned successfully",
    })

    client = TestClient(app)
    resp = client.post("/api/sessions/s101/rescan", json={"mode": "in_place", "engine": "ai"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["session_id"] == "s101"
    assert data["mode"] == "in_place"
    assert data["engine_used"] == "ai"
