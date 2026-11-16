"""Pre-flight PDF token estimation service for Gemini multi-model extraction.

Calculates token weights as staff stage PDFs and disqualifies over-capacity files
(>200,000 tokens) before dispatch to Google AI Studio to prevent quota breaches.
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

logger = logging.getLogger(__name__)

# Hard safe ceilings for Google AI Studio Flash-Lite models (250k TPM raw)
SAFE_TPM_CEILING: int = 200_000
BASE_SYSTEM_RAG_TOKENS: int = 8_500
TOKENS_PER_IMAGE_PAGE: int = 2_000
CHAR_DIVISOR: float = 3.8


class TokenPreflightResult(TypedDict):
    estimated_tokens: int
    is_eligible: bool
    page_count: int
    warning: str | None


def estimate_pdf_tokens(
    pdf_bytes: bytes,
    filename: str | None = None,
) -> TokenPreflightResult:
    """Estimate token consumption for a PDF payload before sending to Google AI Studio.

    Combines:
    1. Base RAG system prompt & company aliases schema (~8,500 tokens)
    2. Multimodal high-res page image encoding (~2,000 tokens per page)
    3. Extracted digital text characters (~3.8 characters per token)
    """
    if not pdf_bytes:
        return {
            "estimated_tokens": BASE_SYSTEM_RAG_TOKENS,
            "is_eligible": True,
            "page_count": 0,
            "warning": None,
        }

    try:
        import fitz  # PyMuPDF

        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            page_count = doc.page_count
            total_chars = 0
            for page in doc:
                total_chars += len(page.get_text())

    except Exception as exc:
        logger.warning("Fast pre-flight PDF parse failed for %s: %s; using size heuristic", filename, exc)
        page_count = max(1, len(pdf_bytes) // 50_000)
        total_chars = len(pdf_bytes) // 2

    text_tokens = int(total_chars / CHAR_DIVISOR)
    image_tokens = page_count * TOKENS_PER_IMAGE_PAGE
    estimated_tokens = BASE_SYSTEM_RAG_TOKENS + image_tokens + text_tokens

    if estimated_tokens > SAFE_TPM_CEILING:
        warning_msg = (
            f"Exceeds safe 200k TPM quota window (~{estimated_tokens:,} tokens across "
            f"{page_count} pages). Disqualified from automated AI extraction to protect "
            f"Google AI Studio fleet from suspension."
        )
        return {
            "estimated_tokens": estimated_tokens,
            "is_eligible": False,
            "page_count": page_count,
            "warning": warning_msg,
        }

    return {
        "estimated_tokens": estimated_tokens,
        "is_eligible": True,
        "page_count": page_count,
        "warning": None,
    }
