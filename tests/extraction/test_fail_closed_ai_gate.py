"""Hermetic tests for Task 1: Strict Fail-Closed AI Gate."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from app.core.errors import AIExtractionUnavailableException
from app.extraction.orchestrator import ExtractionOrchestrator


def test_fail_closed_raises_when_no_api_keys(tmp_path: Path):
    """When no Gemini API keys exist and fail_closed=True, must raise 503 rather than corrupting."""
    dummy_pdf = tmp_path / "test.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 " + b"X" * 600)

    orchestrator = ExtractionOrchestrator()

    mock_pool = MagicMock()
    mock_pool.get_all_keys.return_value = ()

    with patch("app.extraction.gemini_extractor.get_key_pool", return_value=mock_pool):
        with pytest.raises(AIExtractionUnavailableException) as exc_info:
            orchestrator.extract_file(dummy_pdf, fail_closed=True)

        assert exc_info.value.status_code == 503
        assert "No GEMINI_API_KEY configured" in exc_info.value.message


def test_fail_closed_raises_when_quota_exhausted_429(tmp_path: Path):
    """When Gemini returns None / rate-limited 429, fail_closed=True raises AIExtractionUnavailableException."""
    dummy_pdf = tmp_path / "test.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 " + b"X" * 600)

    orchestrator = ExtractionOrchestrator()

    mock_pool = MagicMock()
    mock_pool.get_all_keys.return_value = ("AIzaSyMockKey",)
    mock_pool.get_last_error_message.return_value = "RESOURCE_EXHAUSTED: Rate limit exceeded (429)"

    with patch("app.extraction.gemini_extractor.get_key_pool", return_value=mock_pool), \
         patch("app.extraction.gemini_extractor.extract_with_gemini_sync", return_value=None):
        with pytest.raises(AIExtractionUnavailableException) as exc_info:
            orchestrator.extract_file(dummy_pdf, fail_closed=True)

        assert exc_info.value.status_code == 429
        assert "AI Extraction Unavailable" in exc_info.value.message


def test_fail_closed_false_falls_back_with_warning(tmp_path: Path):
    """When fail_closed=False is explicitly passed, extraction degrades gracefully to native fallback."""
    dummy_pdf = tmp_path / "test.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 " + b"X" * 600)

    orchestrator = ExtractionOrchestrator()

    mock_pool = MagicMock()
    mock_pool.get_all_keys.return_value = ()

    with patch("app.extraction.gemini_extractor.get_key_pool", return_value=mock_pool):
        res = orchestrator.extract_file(dummy_pdf, fail_closed=False)
        assert res is not None
        assert "draft" in res
        # Must have recorded warning
        full_rec = res.get("full_record") or {}
        warnings = full_rec.get("warnings") or []
        assert any("No GEMINI_API_KEY configured" in w for w in warnings)

