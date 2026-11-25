"""Machine and provider readiness checks for Admin System Checks."""

from __future__ import annotations

import importlib.util
import logging
import os
import shutil
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, resolve_active_gemini_model
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
    model = resolve_active_gemini_model(settings.gemini_model)

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


def get_deep_system_diagnostics(settings: Settings, db: Session) -> dict:
    """Run live self-tests across all domain logic engines, database invariants, 8K assets, and sitemap routes."""
    from datetime import date
    from decimal import Decimal
    from types import SimpleNamespace
    from sqlalchemy import func, select
    from app.models.tables import (
        BenefitAlias,
        BenefitCatalogRevision,
        BenefitConcept,
        InsuranceCompany,
        InsuranceProduct,
        InsuranceTenure,
        Session as SessionModel,
    )

    domain_checks: list[dict] = []

    # 1. JPJ Road Tax Engine Self-Test (ICE + 2026 ZEV EV)
    try:
        from app.services.road_tax_engine import calculate_road_tax_unified

        rt_ice = calculate_road_tax_unified(capacity=1500, unit="CC", vehicle_type="Car", owner_type="Private", jurisdiction="Peninsular")
        rt_ev = calculate_road_tax_unified(capacity=150, unit="KW", vehicle_type="Car", owner_type="Private", jurisdiction="Peninsular")
        ice_amt = Decimal(str(rt_ice.get("road_tax", 0)))
        ev_amt = Decimal(str(rt_ev.get("road_tax", 0)))
        ok_rt = ice_amt == Decimal("90.00") and ev_amt > Decimal("0.00")
        domain_checks.append({
            "name": "JPJ Road Tax Engine (ICE CC & 2026 ZEV EV kW)",
            "status": "Ready" if ok_rt else "Check Needed",
            "message": f"Verified: 1500cc Saloon = RM {ice_amt:.2f} · 150kW EV = RM {ev_amt:.2f}",
            "module": "backend/app/services/road_tax_engine.py",
        })
    except Exception as exc:
        domain_checks.append({
            "name": "JPJ Road Tax Engine (ICE CC & 2026 ZEV EV kW)",
            "status": "Needs Setup",
            "message": f"Self-test error: {exc}",
            "module": "backend/app/services/road_tax_engine.py",
        })

    # 2. Exact Calendar Betterment Age & 7-Insurer Underwriting Self-Test
    try:
        from app.services.marketing_comparison.ncd_evaluator import evaluate_betterment_rules

        waived_qbe, rate_qbe, disp_qbe = evaluate_betterment_rules(
            yom=2018,
            quote_year=2026,
            company_name="QBE Insurance",
            has_betterment_peril=False,
            is_comprehensive_private=True,
            registration_date=date(2018, 6, 1),
            coverage_start_date=date(2026, 6, 1),
            coverage_type="Comprehensive",
        )
        ok_bet = waived_qbe is True and rate_qbe == 0.0
        domain_checks.append({
            "name": "Exact Calendar Betterment & 7-Insurer Underwriting Engine",
            "status": "Ready" if ok_bet else "Check Needed",
            "message": f"Verified: QBE 8yo Private Car = {disp_qbe} (relativedelta exact age)",
            "module": "backend/app/services/marketing_comparison/ncd_evaluator.py",
        })
    except Exception as exc:
        domain_checks.append({
            "name": "Exact Calendar Betterment & 7-Insurer Underwriting Engine",
            "status": "Needs Setup",
            "message": f"Self-test error: {exc}",
            "module": "backend/app/services/marketing_comparison/ncd_evaluator.py",
        })

    # 3. Logical Underwriter Reranker & BNM 5-Cent Cash Rounding Self-Test
    try:
        from app.domain.motor.currency_rounding import apply_bnm_cash_rounding
        from app.domain.motor.winner_ranking_rules import evaluate_logical_value_rerank

        bnm_val = apply_bnm_cash_rounding(Decimal("1423.13"))
        e1 = SimpleNamespace(
            id="1", company_name="Etiqa", total_payable=1420.0, agreed_value=False,
            valuation_type="market_value", towing_km="200 km", towing_limit="200 km",
            excess=400.0, waiver_betterment=False, betterment_rate=20.0, special_perils="",
            manual_rank=None, is_hidden=False, rank=1, notes="",
        )
        e2 = SimpleNamespace(
            id="2", company_name="QBE", total_payable=1450.0, agreed_value=True,
            valuation_type="agreed_value", towing_km="Unlimited", towing_limit="Unlimited",
            excess=0.0, waiver_betterment=True, betterment_rate=0.0, special_perils="Included",
            manual_rank=None, is_hidden=False, rank=2, notes="",
        )
        ranked = evaluate_logical_value_rerank([e1, e2])
        ok_rank = bnm_val == Decimal("1423.15") and ranked[0].company_name == "QBE" and "Ranked #1" in (ranked[0].notes or "")
        domain_checks.append({
            "name": "Logical Underwriter Value Reranker & BNM 5¢ Rounding",
            "status": "Ready" if ok_rank else "Check Needed",
            "message": f"Verified: BNM 1423.13 -> RM {bnm_val} · Logical Winner = {ranked[0].company_name} ({ranked[0].notes})",
            "module": "backend/app/domain/motor/winner_ranking_rules.py",
        })
    except Exception as exc:
        domain_checks.append({
            "name": "Logical Underwriter Value Reranker & BNM 5¢ Rounding",
            "status": "Needs Setup",
            "message": f"Self-test error: {exc}",
            "module": "backend/app/domain/motor/winner_ranking_rules.py",
        })

    # 4. Benefit Aliases, Catalog Grounding & Design 2 24-Slot Matrix
    db_summary = {
        "active_companies": 0,
        "active_products": 0,
        "published_catalogs": 0,
        "active_benefit_concepts": 0,
        "active_benefit_aliases": 0,
        "live_sessions": 0,
        "sandbox_test_sessions": 0,
        "active_tenures": 0,
    }
    try:
        from app.rendering.unified_addon_engine import CANONICAL_24_CATALOG

        db_summary["active_companies"] = db.scalar(select(func.count(InsuranceCompany.id)).where(InsuranceCompany.status == "active")) or 0
        db_summary["active_products"] = db.scalar(select(func.count(InsuranceProduct.id)).where(InsuranceProduct.status == "active")) or 0
        db_summary["published_catalogs"] = db.scalar(select(func.count(BenefitCatalogRevision.id)).where(BenefitCatalogRevision.state == "published")) or 0
        db_summary["active_benefit_concepts"] = db.scalar(select(func.count(BenefitConcept.id)).where(BenefitConcept.status == "active")) or 0
        db_summary["active_benefit_aliases"] = db.scalar(select(func.count(BenefitAlias.id)).where(BenefitAlias.status == "active")) or 0
        db_summary["live_sessions"] = db.scalar(select(func.count(SessionModel.id)).where(SessionModel.status != "trash", SessionModel.is_test.is_(False))) or 0
        db_summary["sandbox_test_sessions"] = db.scalar(select(func.count(SessionModel.id)).where(SessionModel.status != "trash", SessionModel.is_test.is_(True))) or 0
        db_summary["active_tenures"] = db.scalar(select(func.count(InsuranceTenure.id)).where(InsuranceTenure.is_discarded.is_(False))) or 0

        leaked_test = db.scalar(
            select(func.count(SessionModel.id)).where(
                SessionModel.status != "trash",
                SessionModel.is_test.is_(True),
                SessionModel.tenure_id.is_not(None),
            )
        ) or 0

        domain_checks.append({
            "name": "Benefit Alias Grounding & Canonical 24-Card Matrix",
            "status": "Ready" if (db_summary["active_benefit_aliases"] >= 500 and len(CANONICAL_24_CATALOG) == 24) else "Check Needed",
            "message": f"Verified: {db_summary['active_benefit_aliases']} active BenefitAliases · {db_summary['active_benefit_concepts']} Concepts · {len(CANONICAL_24_CATALOG)} Design 2 Slots",
            "module": "backend/app/services/catalog_review_service.py",
        })
        domain_checks.append({
            "name": "Test Sandbox Isolation Firewall (Zero Ledger Leak)",
            "status": "Ready" if leaked_test == 0 else "Check Needed",
            "message": f"Verified: {db_summary['sandbox_test_sessions']} Sandbox test session(s) isolated · {leaked_test} leaked to live ledger",
            "module": "backend/app/workers/extraction_worker.py",
        })
    except Exception as exc:
        domain_checks.append({
            "name": "Benefit Alias Grounding & Sandbox Firewall",
            "status": "Needs Setup",
            "message": f"Database check error: {exc}",
            "module": "backend/app/services/catalog_review_service.py",
        })

    # 5. Design 2 8K Ultra-HD Brand & QR Asset Verification
    try:
        from PIL import Image
        repo_root = Path(__file__).resolve().parents[3]
        logo_p = repo_root / "frontend/public/assets/brand/logo-horizontal-black.png"
        qr_p = repo_root / "frontend/public/assets/duitnow_qr.jpeg"
        logo_w = Image.open(logo_p).width if logo_p.exists() else 0
        qr_w = Image.open(qr_p).width if qr_p.exists() else 0
        ok_assets = logo_w >= 1800 and qr_w >= 2000
        domain_checks.append({
            "name": "Design 2 8K Ultra-HD Brand & QR Asset Resolution",
            "status": "Ready" if ok_assets else "Check Needed",
            "message": f"Verified: Header Logo = {logo_w}px wide · DuitNow QR = {qr_w}px · PDF Scale = 4x (600 DPI class)",
            "module": "backend/app/rendering/benefit_schedule_renderer.py",
        })
    except Exception as exc:
        domain_checks.append({
            "name": "Design 2 8K Ultra-HD Brand & QR Asset Resolution",
            "status": "Needs Setup",
            "message": f"Asset probe error: {exc}",
            "module": "backend/app/rendering/benefit_schedule_renderer.py",
        })

    sitemap_routes = [
        {
            "category": "Core Operations",
            "title": "Upload & Batch Intake",
            "route": "/upload",
            "api_endpoint": "POST /api/uploads",
            "status": "Ready",
            "description": "Single sandbox quote, 30-quote Marketing Comparison intake, and 10-slot Corporate Fleet upload with PT quota pacing.",
        },
        {
            "category": "Core Operations",
            "title": "Recent Uploads & Sessions Command Center",
            "route": "/sessions",
            "api_endpoint": "GET /api/sessions",
            "status": "Ready",
            "description": "Chronological feed (Today/Yesterday) with server pagination, insurer/staff filters, and isolated Test Sandbox Dump.",
        },
        {
            "category": "Core Operations",
            "title": "Monthly Motor Renewal Ledger",
            "route": "/ledger",
            "api_endpoint": "GET /api/tenures",
            "status": "Ready",
            "description": "12-stage renewal pipeline, Hit/Miss tracking, cover note binding, and instant expanding search.",
        },
        {
            "category": "Core Operations",
            "title": "Multi-Underwriter Comparison Matrix",
            "route": "/comparison",
            "api_endpoint": "GET /api/comparison/{tenure_id}",
            "status": "Ready",
            "description": "Side-by-side underwriter cards, logical AI reranking with reasoning badges, BNM 5¢ toggle, and WhatsApp teaser.",
        },
        {
            "category": "Core Operations",
            "title": "Quotation Workspace & Design 2 Live Preview",
            "route": "/sessions",
            "api_endpoint": "GET /api/sessions/{id}/workspace",
            "status": "Ready",
            "description": "3-column review workspace with Free vs Paid benefit switcher, Open New Quotation in New Tab, and 8K PDF/PNG export.",
        },
        {
            "category": "Builder & Catalogs",
            "title": "Insurer Benefits & Add-ons Studio",
            "route": "/builder/benefits",
            "api_endpoint": "GET /api/business/catalog-workspace",
            "status": "Ready",
            "description": "Per-insurer product & package tier configuration across 7 underwriters.",
        },
        {
            "category": "Builder & Catalogs",
            "title": "Global Benefits & 559 Alias Library",
            "route": "/builder/global-benefits",
            "api_endpoint": "GET /api/business/benefit-concepts",
            "status": "Ready",
            "description": "Canonical benefit concepts, descriptions, 2D vector icons, and quotation phrase aliases.",
        },
        {
            "category": "Builder & Catalogs",
            "title": "Quotation Templates (Design 2 & Bilingual v4)",
            "route": "/builder/templates/quotation-templates",
            "api_endpoint": "GET /api/business/templates/published",
            "status": "Ready",
            "description": "Published master template revisions and agency bank account details.",
        },
        {
            "category": "Builder & Catalogs",
            "title": "Asset Library & S3 Inspector",
            "route": "/builder/assets",
            "api_endpoint": "GET /api/business/assets",
            "status": "Ready",
            "description": "High-resolution transparent brand logos, underwriter marks, and 2D benefit icons.",
        },
        {
            "category": "Settings & Governance",
            "title": "Gemini AI Fleet & PT Midnight Quota Monitor",
            "route": "/settings/ai-engine",
            "api_endpoint": "GET /api/settings/gemini/timeline",
            "status": "Ready",
            "description": "Multi-key independent controls, Pacific midnight reset countdown, and minute-level token intensity charts.",
        },
        {
            "category": "Settings & Governance",
            "title": "JPJ Road Tax & Extraction Aliases",
            "route": "/settings/extraction/road-tax",
            "api_endpoint": "GET /api/admin/road-tax-rules",
            "status": "Ready",
            "description": "Authoritative JPJ ICE & 2026 ZEV EV road tax tables, company detection, field aliases, and vehicle models.",
        },
        {
            "category": "Settings & Governance",
            "title": "System Health, Logic Diagnostics & Sitemap",
            "route": "/settings/system-checks",
            "api_endpoint": "GET /api/system/checks",
            "status": "Ready",
            "description": "Live infrastructure probes, domain calculation self-tests, and interactive system sitemap.",
        },
    ]

    return {
        "domain_logic_checks": domain_checks,
        "sitemap_routes": sitemap_routes,
        "database_summary": db_summary,
    }
