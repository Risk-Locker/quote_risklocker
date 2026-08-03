"""Optional enhanced reading hooks."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path


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


def run_enhanced_reading(_: Path) -> tuple[str, list[str], list[str]]:
    engines = available_engines()
    warnings: list[str] = []
    methods: list[str] = []
    if engines["paddleocr"]:
        methods.append("Enhanced reading with PaddleOCR available")
    if engines["tesseract"]:
        methods.append("Enhanced reading with Tesseract available")
    if engines["ocrmypdf"]:
        methods.append("Enhanced reading with OCRmyPDF available")
    if not methods:
        warnings.append("Enhanced reading unavailable on this machine.")
    return "", methods, warnings
