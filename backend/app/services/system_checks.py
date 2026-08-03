"""Machine and provider readiness checks for Admin System Checks."""

from __future__ import annotations

import importlib.util
import logging
import shutil
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.services.document_security import scanner_status
from app.storage.supabase import SupabaseStorage


logger = logging.getLogger(__name__)


def package_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def playwright_ready() -> tuple[bool, str]:
    if not package_available("playwright"):
        return False, "Install Playwright and Chromium: python -m playwright install chromium"
    try:
        from playwright.sync_api import sync_playwright  # type: ignore

        with sync_playwright() as playwright:
            executable = Path(playwright.chromium.executable_path)
        if executable.exists():
            return True, "Ready"
    except Exception as exc:
        logger.warning("Playwright readiness check failed: %s", exc)
    return False, "Install Chromium for PDF rendering: python -m playwright install chromium"


def get_system_checks(settings: Settings, db: Session) -> list[dict]:
    checks: list[dict] = [
        {"name": "Database provider", "status": "Ready", "message": "Supabase/Postgres", "group": "Required Setup"}
    ]
    for label, module in [("FastAPI", "fastapi"), ("SQLAlchemy", "sqlalchemy"), ("PyMuPDF", "fitz"), ("pdfplumber", "pdfplumber"), ("pikepdf", "pikepdf")]:
        available = package_available(module)
        checks.append(
            {
                "name": label,
                "status": "Ready" if available else "Needs Setup",
                "message": "Ready" if available else "Install required dependency.",
                "group": "Required Setup",
            }
        )

    playwright_available, playwright_message = playwright_ready()
    checks.append(
        {
            "name": "Playwright PDF rendering",
            "status": "Ready" if playwright_available else "Needs Setup",
            "message": playwright_message,
            "group": "Required Setup",
        }
    )
    storage_ready, storage_message = SupabaseStorage(settings).check()
    checks.append(
        {
            "name": "Supabase PDF storage",
            "status": "Ready" if storage_ready else "Needs Setup",
            "message": storage_message,
            "group": "Required Setup",
        }
    )
    scan_ready, scan_message = scanner_status()
    scanner_required = settings.require_malware_scanner
    checks.append(
        {
            "name": "PDF malware scanner",
            "status": "Ready" if scan_ready else "Needs Setup" if scanner_required else "Unavailable",
            "message": scan_message,
            "group": "Required Setup" if scanner_required else "Advanced Enhanced Reading",
        }
    )

    for label, module in [("PaddleOCR enhanced reading", "paddleocr"), ("OpenCV visual checks", "cv2")]:
        available = package_available(module)
        checks.append(
            {
                "name": label,
                "status": "Ready" if available else "Unavailable",
                "message": "Ready" if available else "Optional enhanced reading feature unavailable.",
                "group": "Advanced Enhanced Reading",
            }
        )
    for label, executable in [("Tesseract enhanced reading", "tesseract"), ("OCRmyPDF enhanced reading", "ocrmypdf")]:
        available = shutil.which(executable) is not None
        checks.append(
            {
                "name": label,
                "status": "Ready" if available else "Unavailable",
                "message": "Ready" if available else "Optional enhanced reading feature unavailable.",
                "group": "Advanced Enhanced Reading",
            }
        )

    try:
        db.execute(text("select 1"))
        checks.append({"name": "Database", "status": "Ready", "message": "Database connection is working.", "group": "Required Setup"})
    except Exception as exc:
        logger.warning("Database health check failed: %s", exc)
        checks.append({"name": "Database", "status": "Needs Setup", "message": "Database connection failed.", "group": "Required Setup"})
    return checks
