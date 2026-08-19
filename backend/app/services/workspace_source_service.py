"""Lazy, Staff-safe reads separated from the canonical workspace snapshot."""

from __future__ import annotations

from copy import deepcopy

from sqlalchemy import select

from app.core.errors import AppError
from app.models.enums import StorageStatus
from app.models.tables import ExtractionRecord, QuotationDraft, Session, TemplateRevision, UploadedFile
from app.services.workspace_service import BUSINESS_ROLES


def _records(db, user, session_id: str) -> tuple[Session, QuotationDraft, UploadedFile, ExtractionRecord | None]:
    if user.role not in BUSINESS_ROLES:
        raise AppError("You do not have permission to view quotation source data.", 403)
    session = db.get(Session, session_id)
    if not session:
        raise AppError("Session not found.", 404)
    draft = db.get(QuotationDraft, session.draft_id)
    uploaded = db.get(UploadedFile, session.uploaded_file_id)
    if not draft or draft.deleted_at or not uploaded or uploaded.deleted_at:
        raise AppError("Quotation not found.", 404)
    extraction = db.scalar(
        select(ExtractionRecord).where(ExtractionRecord.uploaded_file_id == uploaded.id)
    )
    return session, draft, uploaded, extraction


def get_source_pages(db, user, session_id: str, *, page: int = 1, page_size: int = 20) -> dict:
    if page < 1 or page_size < 1 or page_size > 20:
        raise AppError("Source-page pagination is invalid.", 422)
    _session, _draft, uploaded, extraction = _records(db, user, session_id)
    pages = sorted(list(extraction.page_text or []) if extraction else [], key=lambda item: int(item.get("page", 0)))
    start = (page - 1) * page_size
    items = [
        {"page": int(item.get("page") or index + 1), "text": str(item.get("text") or "")}
        for index, item in enumerate(pages[start : start + page_size], start=start)
    ]
    source_available = uploaded.storage_status not in {StorageStatus.EXPIRED.value, StorageStatus.DELETED.value}
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": len(pages),
        "source_pdf_url": f"/uploaded-files/{uploaded.id}/content" if source_available else None,
    }


def get_source_evidence(db, user, session_id: str, field_name: str) -> dict:
    _session, draft, _uploaded, extraction = _records(db, user, session_id)
    if field_name not in (draft.fields or {}):
        raise AppError("Field evidence not found.", 404)
    candidates = list((extraction.candidates or {}).get(field_name, [])) if extraction else []
    return {
        "field": field_name,
        "items": [
            {
                "value": str(item.get("value") or ""),
                "page": item.get("page"),
                "snippet": str(item.get("evidence") or "")[:1_000],
            }
            for item in candidates[:20]
        ],
    }


def get_workspace_template_config(db, user, session_id: str) -> dict:
    _session, draft, _uploaded, _extraction = _records(db, user, session_id)
    revision_id = draft.template_revision_id
    if not revision_id:
        from app.services.template_revision_service import list_published_templates
        published = list_published_templates(db, user)
        if published:
            revision_id = published[0]["template_revision_id"]
    if not revision_id:
        raise AppError("Choose a published template before opening Preview.", 409)
    revision = db.get(TemplateRevision, revision_id)
    if not revision or revision.state not in {"published", "compatibility"}:
        raise AppError("The pinned template revision is unavailable.", 409)
    exact_binding = (
        draft.layout_override is not None
        and draft.layout_override_template_id == revision.template_id
        and draft.layout_override_template_revision_id == revision.id
        and draft.layout_override_base_hash == revision.config_hash
    )
    config = draft.layout_override if exact_binding else revision.config
    return {
        "template_id": revision.template_id,
        "template_revision_id": revision.id,
        "revision_number": revision.revision_number,
        "config_hash": revision.config_hash,
        "source": "session_override" if exact_binding else "template_revision",
        "config": deepcopy(config),
        "binding": {
            "template_id": revision.template_id,
            "template_revision_id": revision.id,
            "base_hash": revision.config_hash,
        },
    }
