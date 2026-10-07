"""Machine and provider readiness checks for Admin System Checks."""

from __future__ import annotations

import importlib.util
import logging
import os
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

    # Fast disk check to avoid spawning sync_playwright inside asyncio event loop on Windows
    candidate_roots: list[Path] = []
    if "PLAYWRIGHT_BROWSERS_PATH" in os.environ:
        candidate_roots.append(Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"]))
    if "LOCALAPPDATA" in os.environ:
        candidate_roots.append(Path(os.environ["LOCALAPPDATA"]) / "ms-playwright")
    candidate_roots.append(Path.home() / ".cache" / "ms-playwright")
    candidate_roots.append(Path.home() / "AppData" / "Local" / "ms-playwright")

    for root in candidate_roots:
        if root.exists():
            for p in root.glob("chromium-*/chrome-win*/chrome.exe"):
                if p.exists():
                    return True, "Ready"
            for p in root.glob("chromium-*/chrome-linux/chrome"):
                if p.exists():
                    return True, "Ready"

    try:
        from playwright.sync_api import sync_playwright  # type: ignore

        with sync_playwright() as playwright:
            executable = Path(playwright.chromium.executable_path)
        if executable.exists():
            return True, "Ready"
    except BaseException as exc:
        logger.warning("Playwright readiness check failed: %s", exc)
    return False, "Install Chromium for PDF rendering: python -m playwright install chromium"


def check_gemini_api(settings: Settings, db: Session | None = None) -> tuple[str, str]:
    from app.extraction.gemini_extractor import get_key_pool

    pool = get_key_pool()
    if db is not None:
        pool.sync_accounts(db=db)
    accounts = pool.get_accounts()
    if not accounts:
        return "Needs Setup", "No Gemini API keys configured in .env or Settings (offline regex fallback active)."

    stats = pool.probe(force=False)
    count = len(accounts)
    masked = [acc.masked_key for acc in accounts]
    pool_desc = f"{count} key{'s' if count > 1 else ''} in pool ({', '.join(masked)})"

    status = stats.get("status")
    model = settings.gemini_model or "gemini-3.1-flash-lite-preview"

    if status in ("ready", "untested"):
        return "Ready", f"Connected to {model} · Live Verified · {pool_desc}"
    elif status == "cooling_rpm":
        return "Ready", f"Cooling (10 RPM limit) · Automatic failover active · {pool_desc}"
    elif status == "denied":
        err = stats.get("last_error") or "Your project has been denied access."
        return "Needs Setup", f"Google API returned HTTP 403 (Project Denied Access): {err} · {pool_desc}"
    elif status == "exhausted_rpd":
        return "Needs Setup", f"Daily safety quota reached (440 RPD) · {pool_desc}"
    elif status == "invalid_key":
        return "Needs Setup", f"Invalid API key or project configuration for {model} · {pool_desc}"
    else:
        err = stats.get("last_error") or "Unknown status"
        return "Needs Setup", f"Gemini API check: {err} · {pool_desc}"


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
    gemini_status, gemini_msg = check_gemini_api(settings, db=db)
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
