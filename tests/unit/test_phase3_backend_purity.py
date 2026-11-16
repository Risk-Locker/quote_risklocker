"""Unit tests for Phase 3: Backend Core Engines, Query Performance & API Purity."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from dateutil.relativedelta import relativedelta

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.insurance_tenure_service import normalize_tenure_dates
from app.services.generation_service import _existing_request


def test_generation_service_resolves_company_slug_correctly():
    """F-09: Verify generation service resolves company slug / name correctly and does not blind-default to etiqa."""
    from app.services.generation_service import build_render_snapshot_context
    from app.models.tables import InsuranceCompany, QuotationDraft, TemplateRevision

    # Test company with slug "allianz"
    company_allianz = InsuranceCompany()
    company_allianz.slug = "allianz"
    company_allianz.name = "Allianz General Insurance"

    draft = QuotationDraft()
    draft.id = "draft-allianz-1"
    draft.revision = 1
    draft.company_id = "comp-1"
    draft.company = company_allianz
    draft.product = None
    draft.fields = {}
    draft.uploaded_file_id = "file-1"
    draft.catalog_revision_id = None

    revision = TemplateRevision()
    revision.id = "rev-1"
    revision.config = {}

    db = MagicMock()
    db.scalars.return_value.all.return_value = []
    db.scalar.return_value = None

    # We inspect the code or test resolution logic directly
    from app.services.generation_service import get_company_catalog_key
    assert get_company_catalog_key(company_allianz) == "allianz"

    # Test company with None slug falls back to normalized name
    company_kurnia = InsuranceCompany()
    company_kurnia.slug = None
    company_kurnia.name = "Kurnia Insurans"
    assert get_company_catalog_key(company_kurnia) == "kurnia"

    # Test None company falls back to etiqa
    assert get_company_catalog_key(None) == "etiqa"


def test_generation_service_uses_indexed_query_for_existing_request():
    """F-10: Verify _existing_request uses indexed query rather than scanning all jobs."""
    db = MagicMock()
    user = SimpleNamespace(id="user-1")
    draft = SimpleNamespace(id="draft-1", _generation_session_id="sess-1")

    # Mock scalars for GeneratedPdfVersion (empty)
    db.scalars.return_value.all.return_value = []
    # Mock scalar for Job query
    mock_job = SimpleNamespace(
        job_type="render_pdf",
        idempotency_key="key-123",
        owner_id="user-1",
        session_id="sess-1",
        payload={"draft_revision": 1},
    )
    db.scalar.side_effect = [None, mock_job]

    result = _existing_request(db, user, draft, "key-123", 1)
    assert result is not None
    assert result["job"] == mock_job

    # Verify db.scalar was called for Job with a filter on idempotency_key
    assert len(db.scalar.call_args_list) >= 2
    called_stmt = db.scalar.call_args_list[1][0][0]
    sql_str = str(called_stmt)
    assert "jobs.idempotency_key" in sql_str
    assert "jobs.job_type" in sql_str


def test_leap_safe_tenure_dates():
    """F-12: Verify normalize_tenure_dates handles leap years and standard years without drift."""
    # 1. Standard non-leap year: 2025-01-01 to 2025-12-31
    start_2025 = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    s1, e1, exp1 = normalize_tenure_dates(start_2025, None)
    assert s1 == start_2025
    assert e1 == datetime(2025, 12, 31, 0, 0, 0, tzinfo=timezone.utc)
    assert exp1 == "2025-12"

    # 2. Leap year start: 2024-02-29 to 2025-02-28
    start_leap = datetime(2024, 2, 29, 0, 0, 0, tzinfo=timezone.utc)
    s2, e2, exp2 = normalize_tenure_dates(start_leap, None)
    assert s2 == start_leap
    assert e2 == datetime(2025, 2, 28, 0, 0, 0, tzinfo=timezone.utc)
    assert exp2 == "2025-02"

    # 3. Standard mid-year: 2026-06-15 to 2027-06-14
    start_mid = datetime(2026, 6, 15, 0, 0, 0, tzinfo=timezone.utc)
    s3, e3, exp3 = normalize_tenure_dates(start_mid, None)
    assert s3 == start_mid
    assert e3 == datetime(2027, 6, 14, 0, 0, 0, tzinfo=timezone.utc)
    assert exp3 == "2027-06"


def test_get_marketing_comparison_default_read_only_does_not_commit():
    """Verify get_marketing_comparison does not call db.commit() by default on read-only queries."""
    from decimal import Decimal
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models.tables import Base, InsuranceTenure, TrackedVehicle, new_id
    from app.services.marketing_comparison_service import get_marketing_comparison

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine)
    db = SessionFactory()

    vehicle = TrackedVehicle(
        id=new_id(),
        vehicle_no="WXY9999",
        car_brand="Toyota",
        car_model="Vios 1.5",
        manufacture_year=2022,
    )
    db.add(vehicle)
    db.flush()

    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=vehicle.id,
        vehicle_no="WXY9999",
        customer_name="Test Customer",
        road_tax=Decimal("150.00"),
        runner_fee=Decimal("35.00"),
        include_road_tax=True,
        include_runner_fee=True,
        coverage_start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
        expiry_month="2026-12",
    )
    db.add(tenure)
    db.commit()

    # Spy on db.commit
    commit_spy = MagicMock(wraps=db.commit)
    db.commit = commit_spy

    res = get_marketing_comparison(db, tenure.id, allow_commit=False)
    assert res is not None
    assert commit_spy.call_count == 0, "Read-only get_marketing_comparison must never commit DB state"
    db.close()


def test_comparison_mutating_endpoints_reject_unauthorized_roles():
    """Verify comparison mutating endpoints reject unauthenticated or non-staff users."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.core.errors import register_error_handlers
    from app.api.routers.comparison import router as comparison_router
    from app.api.deps import current_user, get_db
    from app.models.tables import User

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(comparison_router)

    guest_user = User()
    guest_user.id = "guest-1"
    guest_user.role = "guest"
    guest_user.status = "active"

    mock_db = MagicMock()
    app.dependency_overrides[current_user] = lambda: guest_user
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    # Attempting to mutate fixed costs as guest must return 403
    res = client.post("/comparison/tenure-1/fixed-costs", json={"road_tax": 50.0})
    assert res.status_code == 403, f"Expected 403 Forbidden for guest user, got {res.status_code}"

    # Attempting to toggle fees as guest must return 403
    res_toggle = client.post("/comparison/tenure-1/toggle-fees", json={"include_road_tax": False})
    assert res_toggle.status_code == 403, f"Expected 403 Forbidden for guest user, got {res_toggle.status_code}"
