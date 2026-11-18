"""Hermetic Red-First TDD suite for Milestone 3:
- Placeholder 'UNPLATED' never hijacks historical blank UNPLATED tenures
- Duplicate session replacement atomically updates entry values AND materializes missing insurer columns
"""

from __future__ import annotations

import sys
from collections.abc import Generator
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
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
    Batch,
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    CatalogOffering,
    ExtractionRecord,
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
from app.services.insurance_tenure_service import resolve_or_create_tenure


@pytest.fixture()
def m3_db() -> Generator[Session, None, None]:
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


def test_resolve_or_create_tenure_never_hijacks_historical_unplated_tenure(m3_db: Session):
    """Creating a new blank UNPLATED tenure without chassis/engine must NEVER return a pre-existing UNPLATED row."""
    start = datetime(2026, 11, 18, tzinfo=timezone.utc)
    end = datetime(2027, 11, 17, tzinfo=timezone.utc)

    old_tv = TrackedVehicle(id=new_id(), vehicle_no="UNPLATED")
    m3_db.add(old_tv)
    m3_db.flush()
    old_tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=old_tv.id,
        vehicle_no="UNPLATED",
        customer_name="Old Historical Blank",
        coverage_start_date=start,
        coverage_end_date=end,
        expiry_month="2027-11",
        status="draft",
    )
    m3_db.add(old_tenure)
    m3_db.commit()

    new_t = resolve_or_create_tenure(
        m3_db,
        vehicle_no="UNPLATED",
        customer_name="New Quotation Intake",
        start_date=start,
        end_date=end,
    )
    assert new_t.id != old_tenure.id


def test_resolve_duplicate_replace_syncs_stale_entry_and_materializes_missing(m3_db: Session):
    """Replacing duplicate sessions updates existing entry metrics from new PDF AND creates missing columns."""
    admin = User(id=new_id(), email="m3@risklocker.test", name="Admin", password_hash="x", role="admin")
    etiqa = InsuranceCompany(id=new_id(), slug="etiqa", name="Etiqa", category="Motor", status="active")
    amgen = InsuranceCompany(id=new_id(), slug="amassurance", name="AmAssurance", category="Motor", status="active")
    c_towing = BenefitConcept(id=new_id(), concept_key="towing", label="Emergency Towing Assistance", status="active")
    tv = TrackedVehicle(id=new_id(), vehicle_no="JPQ6655", car_brand="HONDA", car_model="CR-V")
    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=tv.id,
        vehicle_no="JPQ6655",
        customer_name="HOW YEOK CHIAN",
        coverage_start_date=datetime(2027, 1, 5, tzinfo=timezone.utc),
        coverage_end_date=datetime(2028, 1, 4, tzinfo=timezone.utc),
        expiry_month="2028-01",
        status="draft",
        road_tax=Decimal("200.00"),
        runner_fee=Decimal("20.00"),
    )
    batch = Batch(id=new_id(), owner_id=admin.id, name="M3 Batch")

    def _mk_session(comp: InsuranceCompany, filename: str, premium: str, sum_ins: str, *, active: bool, dup_res: str, dup_of: str | None = None):
        uf = UploadedFile(id=new_id(), batch_id=batch.id, owner_id=admin.id, original_filename=filename, content_type="application/pdf", storage_path=f"s/{filename}")
        rec = ExtractionRecord(
            id=new_id(),
            uploaded_file_id=uf.id,
            raw_text=f"QUOTATION {comp.name}\nVehicle No: JPQ6655\nBasic Premium: {premium}\nSum Insured: {sum_ins}",
            ocr_text="",
            words=[],
            blocks=[],
            tables=[],
            images=[],
            regions=[],
            candidates={},
            benefit_lines=[],
            company_resolution={"company_id": comp.id},
            warnings=[],
            reading_quality="ready",
        )
        draft = QuotationDraft(
            id=new_id(),
            uploaded_file_id=uf.id,
            owner_id=admin.id,
            company_id=comp.id,
            fields={
                "vehicle_no": {"value": "JPQ6655"},
                "insurance_company": {"value": comp.name},
                "coverage_type": {"value": "Comprehensive"},
                "sum_insured": {"value": sum_ins},
                "premium": {"value": premium},
                "motor_premium": {"value": premium},
            },
            scalar_decisions={},
            warnings=[],
        )
        sess = SessionModel(
            id=new_id(),
            owner_id=admin.id,
            uploaded_file_id=uf.id,
            draft_id=draft.id,
            tenure_id=tenure.id,
            tracked_vehicle_id=tv.id,
            detected_company=comp.name,
            document_type="quotation",
            status="active",
            is_tenure_active=active,
            duplicate_resolution=dup_res,
            duplicate_of_session_id=dup_of,
            tenure_version=2 if dup_of else 1,
        )
        m3_db.add_all([uf, rec, draft, sess])
        return sess

    m3_db.add_all([admin, etiqa, amgen, c_towing, tv, tenure, batch])
    m3_db.flush()

    s_etiqa_old = _mk_session(etiqa, "etiqa_old.pdf", "1200.00", "35000.00", active=True, dup_res="original")
    s_etiqa_new = _mk_session(etiqa, "etiqa_new.pdf", "1765.83", "37000.00", active=False, dup_res="pending", dup_of=s_etiqa_old.id)
    s_amg_old = _mk_session(amgen, "amg_old.pdf", "1500.00", "36000.00", active=False, dup_res="replaced_by_newer")
    s_amg_new = _mk_session(amgen, "amg_new.pdf", "1897.11", "38000.00", active=False, dup_res="pending", dup_of=s_amg_old.id)

    # Pre-existing Etiqa entry with old stale premium; AmAssurance entry missing completely
    stale_entry = TenureComparisonEntry(
        id=new_id(),
        tenure_id=tenure.id,
        session_id=s_etiqa_old.id,
        company_id=etiqa.id,
        company_name="Etiqa",
        sum_insured=Decimal("35000.00"),
        motor_premium=Decimal("1200.00"),
        road_tax=Decimal("200.00"),
        runner_fee=Decimal("20.00"),
        total_payable=Decimal("1420.00"),
        manual_overrides=[],
    )
    m3_db.add(stale_entry)
    m3_db.commit()

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(comparison_router)
    app.dependency_overrides[get_db] = lambda: m3_db
    app.dependency_overrides[current_user] = lambda: admin
    client = TestClient(app)

    r1 = client.post(f"/comparison/{tenure.id}/duplicates/{s_etiqa_new.id}/resolve", json={"action": "replace"})
    assert r1.status_code == 200
    r2 = client.post(f"/comparison/{tenure.id}/duplicates/{s_amg_new.id}/resolve", json={"action": "replace"})
    assert r2.status_code == 200

    m3_db.expire_all()
    entries = list(m3_db.scalars(select(TenureComparisonEntry).where(TenureComparisonEntry.tenure_id == tenure.id)).all())
    by_comp = {e.company_name: e for e in entries}
    assert "Etiqa" in by_comp
    assert by_comp["Etiqa"].session_id == s_etiqa_new.id
    assert float(by_comp["Etiqa"].motor_premium) == pytest.approx(1765.83, abs=0.01)
    assert "AmAssurance" in by_comp
    assert by_comp["AmAssurance"].session_id == s_amg_new.id
    assert float(by_comp["AmAssurance"].motor_premium) == pytest.approx(1897.11, abs=0.01)
