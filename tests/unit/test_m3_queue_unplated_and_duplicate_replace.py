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


def test_chassis_first_grouping_plate_assignment_and_dated_plate_history(m3_db: Session):
    """Unregistered quotes group by bare chassis_no, assigning a plate writes VehiclePlateHistory, and future plate transfers preserve old closed tenures."""
    from app.models.tables import VehiclePlateHistory
    from app.services.tenure_identity_sync_service import sync_tenure_identity_transaction

    chassis = "LRWYHCEK6TC667999"
    start_2026 = datetime(2026, 5, 1, tzinfo=timezone.utc)
    end_2026 = datetime(2027, 4, 30, tzinfo=timezone.utc)

    # (a) 4 unregistered quotes with same chassis_no group into 1 tenure with vehicle_no == chassis
    tenures = []
    for i in range(4):
        t = resolve_or_create_tenure(
            m3_db,
            vehicle_no="",
            customer_name=f"ACME EV SDN BHD" if i == 0 else "ACME EV",
            start_date=start_2026,
            end_date=end_2026,
            chassis_no="lrwy-hcek6-tc667999" if i % 2 else chassis,
        )
        tenures.append(t)
    m3_db.commit()

    assert len({t.id for t in tenures}) == 1
    active_tenure = tenures[0]
    assert active_tenure.vehicle_no == chassis
    assert active_tenure.tracked_vehicle is not None
    assert active_tenure.tracked_vehicle.vehicle_no == chassis
    assert active_tenure.tracked_vehicle.chassis_no == chassis

    # (b) Assigning real plate VNE1234 updates active tenure + TrackedVehicle + writes open VehiclePlateHistory
    sync_tenure_identity_transaction(
        m3_db,
        active_tenure.id,
        vehicle_no="VNE 1234",
        chassis_no=chassis,
    )
    m3_db.commit()
    m3_db.expire_all()

    refreshed_2026 = m3_db.get(InsuranceTenure, active_tenure.id)
    assert refreshed_2026 is not None
    assert refreshed_2026.vehicle_no == "VNE1234"
    assert refreshed_2026.tracked_vehicle.vehicle_no == "VNE1234"

    history_rows = list(
        m3_db.scalars(
            select(VehiclePlateHistory)
            .where(VehiclePlateHistory.tracked_vehicle_id == refreshed_2026.tracked_vehicle_id)
            .order_by(VehiclePlateHistory.effective_from.asc())
        ).all()
    )
    assert len(history_rows) == 1
    assert history_rows[0].plate_no == "VNE1234"
    assert history_rows[0].chassis_no == chassis
    assert history_rows[0].effective_to is None
    assert history_rows[0].source_tenure_id == refreshed_2026.id

    # Mark 2026 tenure Close - Win (historical ledger)
    refreshed_2026.stage = "Close - Win"
    m3_db.commit()

    # (c) Next year's renewal changes plate to WXY9999 -> closes VNE1234 history, opens WXY9999, preserves 2026 tenure plate!
    start_2027 = datetime(2027, 5, 1, tzinfo=timezone.utc)
    end_2028 = datetime(2028, 4, 30, tzinfo=timezone.utc)
    renewal_2027 = resolve_or_create_tenure(
        m3_db,
        vehicle_no="WXY9999",
        customer_name="ACME EV SDN BHD",
        start_date=start_2027,
        end_date=end_2028,
        chassis_no=chassis,
    )
    m3_db.commit()
    m3_db.expire_all()

    assert renewal_2027.id != refreshed_2026.id
    assert renewal_2027.tracked_vehicle_id == refreshed_2026.tracked_vehicle_id
    assert renewal_2027.vehicle_no == "WXY9999"

    # Old 2026 ledger keeps its original plate VNE1234
    old_2026_after = m3_db.get(InsuranceTenure, refreshed_2026.id)
    assert old_2026_after is not None
    assert old_2026_after.vehicle_no == "VNE1234"

    history_after = list(
        m3_db.scalars(
            select(VehiclePlateHistory)
            .where(VehiclePlateHistory.tracked_vehicle_id == refreshed_2026.tracked_vehicle_id)
            .order_by(VehiclePlateHistory.created_at.asc())
        ).all()
    )
    assert len(history_after) == 2
    assert history_after[0].plate_no == "VNE1234"
    assert history_after[0].effective_to is not None
    assert history_after[1].plate_no == "WXY9999"
    assert history_after[1].effective_to is None
    assert history_after[1].source_tenure_id == renewal_2027.id


def test_tracking_and_tenure_ignore_blocked_plate_and_engine_labels(m3_db: Session):
    """NOTSTATED plate and 'Chassis No' engine label must never become TrackedVehicle/Tenure identifiers."""
    from app.services.vehicle_tracking_service import get_or_create_vehicle_tracking

    chassis = "LRWYHCEK6TC667999"
    veh, _alert = get_or_create_vehicle_tracking(
        m3_db,
        vehicle_no="NOTSTATED",
        customer_name="XIAO XIAO",
        validity_date="2027-01-31",
        chassis_no=chassis,
        engine_no="Chassis No",
    )
    assert veh is not None
    assert veh.vehicle_no == chassis
    assert veh.engine_no is None

    tenure = resolve_or_create_tenure(
        m3_db,
        vehicle_no="NOTSTATED",
        customer_name="XIAO XIAO",
        start_date=datetime(2026, 2, 1, tzinfo=timezone.utc),
        end_date=datetime(2027, 1, 31, tzinfo=timezone.utc),
        tracked_vehicle_id=veh.id,
        chassis_no=chassis,
        engine_no="Chassis No",
    )
    m3_db.commit()
    assert tenure.vehicle_no == chassis
    assert tenure.tracked_vehicle_id == veh.id


