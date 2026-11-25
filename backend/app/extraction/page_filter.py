"""Shared page-level Product Disclosure Sheet (PDS) classifier and PDF page slicer.

Single source of truth used across extraction, deep re-detection, token preflight,
and marketing comparison so multi-page PDS attachments never pollute quotation fields,
benefits, or AI prompt budgets while Cover Notes and endorsement schedules remain intact.
"""

from __future__ import annotations

import re
from typing import Any


ACTIVE_SCHEDULE_MARKERS: tuple[str, ...] = (
    "motor insurance quotation slip",
    "premium computation",
    "the schedule",
    "schedule / jadual",
    "only the extensions, endorsement",
    "gross contribution",
    "total contribution payable",
    "sum insured / jumlah diinsuranskan",
    "quotation schedule",
    "e-cover note",
)

PDS_FORM_CODE_RE = re.compile(r"\b(?:\d{2}/prn/pds/|pds/vc\b|pds/vp\d*\b)", re.IGNORECASE)

PDS_QA_MARKERS: tuple[str, ...] = (
    "know your coverage",
    "know your obligations",
    "as an illustration",
    "can i cancel my policy",
    "what is this product",
    "what is private car",
    "what is commercial vehicle",
    "what is e-assist",
    "apakah produk ini",
    "apakah perlindungan",
    "important information you should know",
)

_PDS_TITLE_MARKERS: tuple[str, ...] = (
    "product disclosure sheet",
    "lembaran maklumat produk",
    "lembaran pendedahan produk",
)

_STANDALONE_PDS_HEADING_RE = re.compile(
    r"(?m)^\s*(?:product\s+disclosure\s+sheet|lembaran\s+(?:maklumat|pendedahan)\s+produk)\s*$",
    re.IGNORECASE,
)


def is_pds_page_text(text: str, *, page_number: int | None = None) -> bool:
    """Return True when a page's text represents a non-operative PDS or brochure page."""
    low = (text or "").lower()
    if not low.strip():
        return False

    if any(marker in low for marker in ACTIVE_SCHEDULE_MARKERS):
        return False

    qa_hits = sum(1 for marker in PDS_QA_MARKERS if marker in low)
    has_form_code = bool(PDS_FORM_CODE_RE.search(low))

    if (
        ("refer to the product disclosure sheet at http" in low or "rujuk lembaran pendedahan produk di http" in low)
        and qa_hits == 0
        and not has_form_code
    ):
        return False

    if has_form_code:
        return True

    has_pds_title = any(title in low for title in _PDS_TITLE_MARKERS)
    has_standalone_pds_heading = bool(_STANDALONE_PDS_HEADING_RE.search(low))

    if has_pds_title and (qa_hits >= 1 or has_standalone_pds_heading):
        return True

    if qa_hits >= 2 and (page_number is None or page_number > 1):
        return True

    return False


is_pds_text = is_pds_page_text


def split_operative_pages(page_text: list[dict[str, Any]] | None) -> tuple[list[dict[str, Any]], set[int]]:
    """Split page dicts into (operative_pages, excluded_pds_page_numbers).

    Safety invariant: if all pages would be excluded (e.g. a standalone PDS upload),
    returns the original pages so extraction never blanks out completely.
    """
    if not page_text:
        return [], set()

    operative_pages: list[dict[str, Any]] = []
    excluded_page_numbers: set[int] = set()

    for idx, page in enumerate(page_text, start=1):
        if not isinstance(page, dict):
            continue
        raw_pno = page.get("page")
        try:
            page_num = int(raw_pno) if raw_pno is not None else idx
        except (TypeError, ValueError):
            page_num = idx
        txt = str(page.get("text") or "")
        if is_pds_page_text(txt, page_number=page_num):
            excluded_page_numbers.add(page_num)
        else:
            operative_pages.append(page)

    if not operative_pages:
        return list(page_text), set()

    return operative_pages, excluded_page_numbers


def extract_operative_text_from_record(
    *,
    page_text: list[dict[str, Any]] | None,
    raw_text: str | None = "",
    ocr_text: str | None = "",
) -> tuple[str, set[int]]:
    """Build operative combined text from page_text (excluding PDS pages) plus OCR fallback."""
    if isinstance(page_text, list) and page_text:
        operative_pages, pds_pages = split_operative_pages(page_text)
        parts = [str(p.get("text") or "") for p in operative_pages if isinstance(p, dict) and str(p.get("text") or "").strip()]
        if ocr_text and str(ocr_text).strip():
            parts.append(str(ocr_text).strip())
        return "\n".join(parts).strip(), pds_pages

    fallback = "\n".join(part for part in [ocr_text or "", raw_text or ""] if part and str(part).strip()).strip()
    return fallback, set()


def slice_pdf_bytes_excluding_pages(pdf_bytes: bytes, excluded_pages: set[int]) -> bytes:
    """Return PDF bytes with 1-based excluded_pages removed, or original bytes on no-op/error."""
    if not pdf_bytes or not excluded_pages:
        return pdf_bytes

    try:
        import fitz  # type: ignore

        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            keep = [i for i in range(doc.page_count) if (i + 1) not in excluded_pages]
            if not keep or len(keep) == doc.page_count:
                return pdf_bytes
            doc.select(keep)
            return doc.tobytes()
    except Exception:
        return pdf_bytes
