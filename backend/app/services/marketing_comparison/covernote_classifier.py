"""Cover Note Classifier.

Provides logic to classify whether an intake document is an official Cover Note,
Policy Schedule, or Certificate of Insurance versus a marketing quotation.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session
from app.models.tables import Session as SessionModel


def is_covernote_document(session: SessionModel | None, db: Session | None = None) -> bool:
    """Classify whether a session is an official Cover Note / Policy Schedule / Certificate of Insurance.
    Cover Notes and issued Policies are the bound contract and must NEVER appear as quotation comparison columns.
    """
    if not session:
        return False
    doc_t = getattr(session, "document_type", "quotation") or "quotation"
    if doc_t in ("covernote", "unlinked_covernote"):
        return True

    # 1. Inspect original filename
    fn = ""
    if session.uploaded_file:
        fn = (session.uploaded_file.original_filename or "").lower()
    if not fn and getattr(session, "display_options", None) and isinstance(session.display_options, dict):
        fn = str(session.display_options.get("filename") or "").lower()
    if not fn and session.draft and getattr(session.draft, "display_options", None) and isinstance(session.draft.display_options, dict):
        fn = str(session.draft.display_options.get("filename") or "").lower()

    cn_fn_terms = (
        "covernote", "cover_note", "cover note", "cover-note",
        "e-cover", "ecover", "notaperlindungan", "nota perlindungan",
        "sijil insurans", "sijil_insurans", "cert of insurance",
        "certificate of insurance", "policy_schedule", "policyschedule",
        "jadual polisi", "jadual_polisi"
    )
    if any(term in fn for term in cn_fn_terms) or re.search(r"(?:^|[\s_\-])cn(?:[\s_\-0-9]|$)", fn):
        session.document_type = "covernote"
        return True

    # 2. Inspect extracted OCR / raw text
    raw_text = ""
    if session.draft:
        full_ext = getattr(session.draft, "full_extraction", None)
        if full_ext and isinstance(full_ext, dict):
            raw_text = str(full_ext.get("raw_text") or full_ext.get("ocr_text") or "")
        if not raw_text:
            ext_data = getattr(session.draft, "extracted_data", None)
            if ext_data and isinstance(ext_data, dict):
                raw_text = str(ext_data.get("raw_text") or ext_data.get("ocr_text") or "")
    if not raw_text and session.uploaded_file and getattr(session.uploaded_file, "extraction_record", None):
        rec = session.uploaded_file.extraction_record
        raw_text = rec.raw_text or rec.ocr_text or ""

    from app.extraction.candidate_finder import detect_is_covernote
    if raw_text and detect_is_covernote(text=raw_text, filename=fn):
        session.document_type = "covernote"
        return True

    return False
