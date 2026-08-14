"""Optional enhanced reading hooks."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

import fitz

from app.core.workspace import qc_temp_directory


logger = logging.getLogger(__name__)


def available_engines() -> dict[str, bool]:
    engines = {
        "paddleocr": False,
        "tesseract": shutil.which("tesseract") is not None,
        "ocrmypdf": shutil.which("ocrmypdf") is not None,
    }
    try:
        import paddleocr  # type: ignore  # noqa: F401

        engines["paddleocr"] = True
    except Exception as exc:
        logger.warning("PaddleOCR is not available: %s", exc)
    return engines


def _tesseract_page_text(page: fitz.Page, page_number: int) -> str:
    """Render one page and send it to Tesseract without an external temp file."""

    pixmap = page.get_pixmap(matrix=fitz.Matrix(300 / 72, 300 / 72), alpha=False, colorspace=fitz.csRGB)
    try:
        result = subprocess.run(
            ["tesseract", "stdin", "stdout", "--dpi", "300", "-l", "eng"],
            input=pixmap.tobytes("png"),
            capture_output=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"OCR failed on page {page_number}.") from exc
    if result.returncode != 0:
        raise RuntimeError(f"OCR failed on page {page_number}.")
    return result.stdout.decode("utf-8", errors="replace").strip()


def _run_tesseract(path: Path) -> tuple[str, int]:
    pages: list[str] = []
    with fitz.open(path) as document:
        page_count = document.page_count
        for page_number, page in enumerate(document, start=1):
            text = _tesseract_page_text(page, page_number)
            if text:
                pages.append(text)
    return "\n\n".join(pages), page_count


def _run_ocrmypdf(path: Path) -> tuple[str, int]:
    """Use OCRmyPDF as a bounded fallback and extract its new text layer."""

    with qc_temp_directory("ocrmypdf-") as directory:
        output = directory / "ocr.pdf"
        result = subprocess.run(
            ["ocrmypdf", "--skip-text", "--deskew", "--output-type", "pdf", str(path), str(output)],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        if result.returncode not in {0, 6} or not output.exists():
            raise RuntimeError("OCRmyPDF failed.")
        pages: list[str] = []
        with fitz.open(output) as document:
            page_count = document.page_count
            for page in document:
                page_text = (page.get_text("text") or "").strip()
                if page_text:
                    pages.append(page_text)
        return "\n\n".join(pages), page_count


def run_enhanced_reading(path: Path) -> tuple[str, list[str], list[str]]:
    engines = available_engines()
    if not any(engines.values()):
        return "", [], ["Enhanced reading is unavailable. Review this document manually or retry on the extraction worker."]
    try:
        if engines["tesseract"]:
            text, pages = _run_tesseract(path)
            if text:
                return text, [f"Tesseract OCR ({pages} pages)"], []
        if engines["ocrmypdf"]:
            text, pages = _run_ocrmypdf(path)
            if text:
                return text, [f"OCRmyPDF ({pages} pages)"], []
    except Exception:
        logger.exception("Enhanced reading failed")
        return "", [], ["Enhanced reading failed. Review this document manually or retry."]
    return "", [], ["Enhanced reading produced no readable text. Review this document manually."]
