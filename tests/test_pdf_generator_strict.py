"""Production PDF rendering must never emit a fallback document."""

from __future__ import annotations

import builtins
import os
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
os.environ.setdefault("APP_ENV", "test")

from app.rendering.pdf_generator import PdfRendererUnavailable, html_to_pdf  # noqa: E402


def test_missing_playwright_fails_retryably_without_creating_pdf(monkeypatch, tmp_path):
    original_import = builtins.__import__

    def fail_playwright(name, *args, **kwargs):
        if name.startswith("playwright"):
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_playwright)
    output = tmp_path / "quotation.pdf"
    with pytest.raises(PdfRendererUnavailable):
        html_to_pdf("<html><body>Quotation</body></html>", output, width=794, height=1123)
    assert not output.exists()


def test_fallback_pdf_implementation_is_not_present():
    source = (BACKEND / "app/rendering/pdf_generator.py").read_text(encoding="utf-8")
    assert "_minimal_pdf_from_text" not in source
    assert "warnings.append" not in source
