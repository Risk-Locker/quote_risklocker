"""Hermetic TDD suite for Milestone 4a: Comparison Edit Persistence & Special Perils Truth."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.api.deps import current_user, get_db
from app.api.routers.comparison import router as comparison_router
from app.core.errors import register_error_handlers
from app.models.tables import (
    Base,
    InsuranceCompany,
    InsuranceTenure,
    QuotationDraft,
    Session as SessionModel,
    TenureComparisonEntry,
    TrackedVehicle,
    UploadedFile,
    User,
    new_id,
)
from app.services.marketing_comparison.special_perils import (
    has_special_perils_evidence,
    resolve_special_perils,
)
from app.services.marketing_comparison.materialize import (
    is_field_overridden,
    materialize_comparison_entries,
    record_manual_overrides,
)
from app.services.marketing_comparison_service import (
    get_marketing_comparison,
    rescan_comparison_tenure,
    save_comparison_entry,
)


@pytest.fixture()
def hermetic_db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()


def test_special_perils_resolver_rejects_takaful_contribution_substring():
    """P2: 'Basic Contribution' in Takaful quotes must NEVER match 'ribut' substring."""
    takaful_text = (
        "Etiqa General Takaful Berhad\n"
        "Basic Contribution: RM 1,450.00\n"
        "Gross Contribution: RM 1,450.00\n"
        "Total Contribution Payable: RM 1,576.00\n"
    )
    assert has_special_perils_evidence(text=takaful_text) is False
    assert resolve_special_perils(text=takaful_text) == "Not Included"


def test_special_perils_resolver_detects_real_flood_and_endorsement_57_and_negations():
    """Verify word-boundary flood/ribut/Endorsement 57 detection and negative phrase rejection."""
    assert resolve_special_perils(text="Additional Cover: Inclusion of Special Perils (Flood & Storm) RM 120.00") == "Included"
    assert resolve_special_perils(text="Perlindungan Tambahan: Banjir dan Ribut RM 95.00") == "Included"
    assert resolve_special_perils(text="Endorsements Attached: 57, 89, 100") == "Included"
    assert resolve_special_perils(endorsements=["57a"]) == "Included"

    # Negative phrasing must return Not Included
    assert resolve_special_perils(text="Special Perils (Flood): Not Covered") == "Not Included"
    assert resolve_special_perils(text="Peril Khas / Banjir: Tidak Termasuk") == "Not Included"
    assert resolve_special_perils(text="Inclusion of Special Perils: Not Included") == "Not Included"


def test_comparison_edit_persists_across_get_and_rescan_with_field_overrides(hermetic_db: Session):
    """P1 & P3: Inline/modal edits on Towing, Special Perils, LLP persist across GET and rescan."""
    user = User(id=new_id(), email="staff@risklocker.test", password_hash="x", role="staff", status="active")
    veh = TrackedVehicle(id=new_id(), vehicle_no="JPJ5336", car_brand="Perodua", car_model="Myvi", manufacture_year=2021)
    comp = InsuranceCompany(id=new_id(), name="Takaful Malaysia", slug="takaful-malaysia")
    hermetic_db.add_all([user, veh, comp])
    hermetic_db.flush()

    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=veh.id,
        vehicle_no="JPJ5336",
        customer_name="Ahmad",
        road_tax=Decimal("90.00"),
        runner_fee=Decimal("20.00"),
        include_road_tax=True,
        include_runner_fee=True,
        coverage_start_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 4, 30, tzinfo=timezone.utc),
        expiry_month="2027-04",
    )
    file_id = new_id()
    draft = QuotationDraft(
        id=new_id(),
        uploaded_file_id=file_id,
        owner_id=user.id,
        company_id=comp.id,
        fields={
            "sum_insured": {"value": "45000.00"},
            "premium": {"value": "1200.00"},
            "basic_contribution": {"value": "1200.00"},
            "towing_limit": {"value": "100 KM"},
            "windscreen_sum_insured": {"value": "1500.00"},
        },
        display_options={},
    )
    sess = SessionModel(
        id=new_id(),
        owner_id=user.id,
        uploaded_file_id=file_id,
        draft_id=draft.id,
        tenure_id=tenure.id,
        detected_company="Takaful Malaysia",
        document_type="quotation",
        status="active",
        is_tenure_active=True,
    )
    hermetic_db.add_all([tenure, draft, sess])
    hermetic_db.commit()

    # 1. Materialize entries at write time
    mat = materialize_comparison_entries(hermetic_db, tenure.id)
    assert len(mat["entries"]) == 1
    entry_data = mat["entries"][0]
    entry_id = entry_data["id"]
    assert entry_id is not None
    # Takaful 'Basic Contribution' must NOT trigger Special Perils Included
    assert entry_data["special_perils"] in (None, "Not Included")

    # 2. Edit Towing -> Unlimited, Special Perils -> Included, LLP -> Included
    saved = save_comparison_entry(
        hermetic_db,
        tenure.id,
        {
            "id": entry_id,
            "towing_limit": "Unlimited",
            "special_perils": "Included",
            "llp_llop": "Included",
        },
    )
    updated_card = next(e for e in saved["entries"] if e["id"] == entry_id)
    assert updated_card["towing_limit"] == "Unlimited"
    assert updated_card["special_perils"] == "Included"
    assert updated_card["llp_llop"] == "Included"
    assert "towing_limit" in updated_card["manual_overrides"]
    assert "special_perils" in updated_card["manual_overrides"]
    assert "llp_llop" in updated_card["manual_overrides"]

    # 3. Subsequent GET and rescan MUST preserve manual overrides while updating untouched fields
    draft.fields = {
        **draft.fields,
        "windscreen_sum_insured": {"value": "2500.00"},
    }
    hermetic_db.commit()

    after_rescan = rescan_comparison_tenure(hermetic_db, tenure.id)
    rescan_card = next(e for e in after_rescan["entries"] if e["id"] == entry_id)
    assert rescan_card["towing_limit"] == "Unlimited"
    assert rescan_card["special_perils"] == "Included"
    assert rescan_card["llp_llop"] == "Included"
    # Untouched windscreen field refreshed during rescan
    assert rescan_card["windscreen_sum_insured"] == 2500.0


def test_patch_endpoint_inline_edit_revert_version_conflict_and_rbac(hermetic_db: Session):
    """Verify PATCH /comparison/{tenure_id}/entries/{entry_id} enforces RBAC, version 409, inline edit, and revert."""
    staff_user = User(id=new_id(), email="staff2@risklocker.test", password_hash="x", role="staff", status="active")
    guest_user = User(id=new_id(), email="guest@risklocker.test", password_hash="x", role="guest", status="active")
    veh = TrackedVehicle(id=new_id(), vehicle_no="VAA1111", car_brand="Honda", car_model="City", manufacture_year=2022)
    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=veh.id,
        vehicle_no="VAA1111",
        customer_name="Siti",
        road_tax=Decimal("70.00"),
        runner_fee=Decimal("20.00"),
        include_road_tax=True,
        include_runner_fee=True,
        coverage_start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
        expiry_month="2026-12",
    )
    entry = TenureComparisonEntry(
        id=new_id(),
        tenure_id=tenure.id,
        company_name="Lonpac Insurance",
        sum_insured=55000.0,
        motor_premium=1400.0,
        total_payable=1490.0,
        towing_limit="RM 400",
        towing_km="RM 400",
        special_perils=None,
        llp_llop=None,
        excess=0.0,
        version=1,
        is_manual=False,
        manual_overrides=[],
    )
    hermetic_db.add_all([staff_user, guest_user, veh, tenure, entry])
    hermetic_db.commit()

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(comparison_router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: hermetic_db

    # 1. Guest role rejected with 403
    app.dependency_overrides[current_user] = lambda: guest_user
    client = TestClient(app)
    res_403 = client.patch(
        f"/api/comparison/{tenure.id}/entries/{entry.id}",
        json={"towing_limit": "Unlimited"},
    )
    assert res_403.status_code == 403

    # 2. Staff inline PATCH succeeds and increments version
    app.dependency_overrides[current_user] = lambda: staff_user
    res_ok = client.patch(
        f"/api/comparison/{tenure.id}/entries/{entry.id}",
        json={
            "towing_limit": "Unlimited",
            "special_perils": "Included",
            "expected_version": 1,
        },
    )
    assert res_ok.status_code == 200
    body = res_ok.json()
    assert body["towing_limit"] == "Unlimited"
    assert body["special_perils"] == "Included"
    assert "towing_limit" in body["manual_overrides"]
    assert "special_perils" in body["manual_overrides"]
    assert body["version"] == 2

    # 3. Stale expected_version returns 409 Conflict
    res_409 = client.patch(
        f"/api/comparison/{tenure.id}/entries/{entry.id}",
        json={"towing_limit": "200 KM", "expected_version": 1},
    )
    assert res_409.status_code == 409

    # 4. Revert single field override
    res_rev = client.patch(
        f"/api/comparison/{tenure.id}/entries/{entry.id}",
        json={"clear_override_field": "special_perils"},
    )
    assert res_rev.status_code == 200
    rev_body = res_rev.json()
    assert "special_perils" not in rev_body["manual_overrides"]
    assert "towing_limit" in rev_body["manual_overrides"]
