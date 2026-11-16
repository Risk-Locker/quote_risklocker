import pytest
from app.services.token_preflight_service import (
    estimate_pdf_tokens,
    SAFE_TPM_CEILING,
)


def _create_mock_pdf_bytes(page_count: int, lines_per_page: int, line_text: str) -> bytes:
    """Generate a valid in-memory PDF with specified pages and text lines using PyMuPDF."""
    import fitz

    doc = fitz.open()
    for _ in range(page_count):
        page = doc.new_page()
        for i in range(lines_per_page):
            # Using small font allows multi-line text to render without clipping
            page.insert_text((5, 5 + i * 2.0), f"{i:03d} {line_text}", fontsize=2)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_single_page_pdf_token_estimation_eligible():
    """1-page PDF (~300 words) should estimate between 8,000 and 15,000 tokens (including base RAG system context)."""
    # 15 lines of ~20 words each ≈ 300 words (~2,000 chars)
    pdf_bytes = _create_mock_pdf_bytes(1, 15, "insurance quotation motor policy premium coverage breakdown RM 1500 ")

    result = estimate_pdf_tokens(pdf_bytes)

    assert result["is_eligible"] is True
    assert 8_000 <= result["estimated_tokens"] <= 15_000
    assert result["page_count"] == 1
    assert result["warning"] is None


def test_four_page_pdf_dense_estimation_eligible():
    """4-page PDF with dense table text should estimate between 45,000 and 60,000 tokens and remain eligible."""
    # 300 lines of ~110 chars on each of the 4 pages ≈ 132,000 chars total
    # 132,000 / 3.8 = ~34,700 text tokens + 4*2,000 image tokens + 8,500 base = ~51,200 tokens
    dense_line = "Comprehensive policy schedule endorsement terms breakdown premium itemization excess discount "
    pdf_bytes = _create_mock_pdf_bytes(4, 300, dense_line)

    result = estimate_pdf_tokens(pdf_bytes)

    assert result["is_eligible"] is True
    assert 45_000 <= result["estimated_tokens"] <= 60_000
    assert result["page_count"] == 4
    assert result["warning"] is None


def test_150_page_pdf_exceeds_quota_disqualified():
    """150-page PDF should estimate ~350,000 tokens and be rejected before reaching Google AI Studio."""
    # 150 pages * 2,000 = 300,000 base image tokens + text tokens
    pdf_bytes = _create_mock_pdf_bytes(150, 10, "Schedule details endorsement table row verification entry ")

    result = estimate_pdf_tokens(pdf_bytes)

    assert result["is_eligible"] is False
    assert result["estimated_tokens"] > SAFE_TPM_CEILING  # > 200,000
    assert 300_000 <= result["estimated_tokens"] <= 400_000
    assert result["page_count"] == 150
    assert "Exceeds safe 200k TPM quota window" in result["warning"]
