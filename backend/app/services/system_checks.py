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


def check_gemini_api(settings: Settings) -> tuple[str, str]:
    keys = settings.gemini_api_keys
    if not keys:
        return "Needs Setup", "No GEMINI_API_KEY set in .env (offline regex fallback active)."

    model = settings.gemini_model or "gemini-3.5-flash"
    if model in {"gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.5-flash-lite"}:
        model = "gemini-3.5-flash"
    count = len(keys)
    masked = [f"{k[:6]}...{k[-4:]}" if len(k) > 10 else "***" for k in keys]
    pool_desc = f"{count} key{'s' if count > 1 else ''} in pool ({', '.join(masked)})"

    try:
        import httpx

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}?key={keys[0]}"
        with httpx.Client(timeout=4.0) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                return "Ready", f"Connected to {model} Free Tier · {pool_desc}"
            elif resp.status_code == 400:
                return "Needs Setup", f"Invalid API key or project configuration for {model} · {pool_desc}"
            elif resp.status_code == 429:
                return "Ready", f"Rate limited on key 1 (pool will auto-failover to backup keys) · {pool_desc}"
            else:
                return "Needs Setup", f"Gemini API returned HTTP {resp.status_code} · {pool_desc}"
    except Exception as exc:
        return "Unavailable", f"Could not reach Google Gemini API ({exc.__class__.__name__}) · {pool_desc}"


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

    # Gemini AI Extraction Check
    gemini_status, gemini_msg = check_gemini_api(settings)
    checks.append(
        {
            "name": "Gemini AI Multimodal Extraction",
            "status": gemini_status,
            "message": gemini_msg,
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
    scan_ready, scan_message = scanner_status(settings)
    checks.append(
        {
            "name": "PDF malware scanner",
            "status": "Ready" if scan_ready else "Needs Setup",
            "message": scan_message,
            "group": "Required Setup",
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
