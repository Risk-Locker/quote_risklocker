"""Tests for 4-pass Deep Re-detect Engine, cancellable jobs, discount preservation, and RBAC."""

from __future__ import annotations

from datetime import datetime, timezone
import os
import sys
import threading
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_PROVIDER", "supabase_postgres")
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:password@db.test.supabase.co:5432/postgres")
os.environ.setdefault("AUTH_HASH_SECRET", "test-auth-hash-secret-that-is-long-enough")
os.environ.setdefault("STORAGE_DRIVER", "supabase")
os.environ.setdefault("SUPABASE_URL", "https://project-ref.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")

from app.api import routes
from app.api.deps import current_user, get_db
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.extraction.deep_redetect_engine import RedetectCancelledError, run_deep_redetect_pipeline
from app.models.enums import AccountStatus, RecordStatus, Role
from app.models.tables import (
    Base,
    Batch,
    ExtractionRecord,
    InsuranceCompany,
    InsuranceTenure,
    QuotationDraft,
    Session as QuotationSession,
    TrackedVehicle,
    UploadedFile,
    User,
    new_id,
)
from app.services.redetect_job_service import (
    cancel_redetect_job,
    get_redetect_job,
    start_comparison_redetect_job,
    start_session_redetect_job,
)
from app.services.session_rescan_service import apply_gemini_result


@pytest.fixture
def db_setup():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine)
    db = SessionFactory()
    try:
        yield db, SessionFactory
    finally:
        db.close()


class _DummyPool:
    def get_all_keys(self):
        return ["test-gemini-key"]

    def get_last_error_message(self):
        return None


def _seed_session(db, tmp_path: Path, owner_id: str | None = None):
    owner_uuid = owner_id or new_id()
    user = User(
        id=owner_uuid,
        email=f"{owner_uuid[:8]}@risklocker.test",
        name="Owner Staff",
        role=Role.STAFF.value,
        password_hash="x",
        status=AccountStatus.ACTIVE.value,
    )
    liberty = InsuranceCompany(
        id="c0000000-0000-4000-8000-000000000091",
        name="Liberty",
        slug="liberty",
        detection_phrases=["Liberty", "Liberty Insurance", "www.libertyinsurance.com.my"],
        status=AccountStatus.ACTIVE.value,
    )
    kurnia = InsuranceCompany(
        id="c0000000-0000-4000-8000-000000000002",
        name="Kurnia",
        slug="kurnia",
        detection_phrases=["Kurnia", "www.kurnia.com"],
        status=AccountStatus.ACTIVE.value,
    )
    pdf_path = tmp_path / "liberty_qbg1431.pdf"
    pdf_path.write_bytes(
        b"%PDF-1.4\n% Liberty Insurance www.libertyinsurance.com.my QBG1431 auto365 Comprehensive Premier\n%%EOF"
    )
    batch = Batch(id=new_id(), owner_id=user.id, name="Test", status=RecordStatus.READY.value)
    uploaded = UploadedFile(
        id=new_id(),
        batch_id=batch.id,
        owner_id=user.id,
        original_filename="Liberty_QBG1431.pdf",
        content_type="application/pdf",
        storage_path=str(pdf_path),
        storage_provider="local_ephemeral",
        size_bytes=pdf_path.stat().st_size,
        status=RecordStatus.READY.value,
    )
    tv = TrackedVehicle(id=new_id(), vehicle_no="QBG1431", car_brand="HONDA", car_model="WR-V E", engine_cc="1498 CC")
    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=tv.id,
        vehicle_no="QBG1431",
        customer_name="WONG SUI PENG",
        coverage_start_date=datetime(2027, 1, 2, tzinfo=timezone.utc),
        coverage_end_date=datetime(2028, 1, 1, tzinfo=timezone.utc),
        expiry_month="2028-01",
        motor_discount_pct=5.0,
        road_tax=120.0,
        runner_fee=20.0,
        include_road_tax=True,
        include_runner_fee=True,
        created_by_id=user.id,
    )
    draft = QuotationDraft(
        id=new_id(),
        uploaded_file_id=uploaded.id,
        owner_id=user.id,
        company_id=kurnia.id,
        status=RecordStatus.READY.value,
        fields={
            "quotation_reference": {"value": "RL260000900", "status": "ready"},
            "insurance_company": {"value": "Kurnia", "status": "ready"},
            "customer_name": {"value": "WONG SUI PENG", "status": "ready"},
            "vehicle_no": {"value": "QBG1431", "status": "ready"},
            "coverage_amount": {"value": "66000.00", "status": "ready"},
            "premium": {"value": "1621.00", "status": "ready"},
            "motor_discount_pct": {"value": "5.00", "status": "ready"},
            "total_amount": {"value": "1679.95", "status": "ready"},
        },
        display_options={"include_road_tax": True, "include_runner_fee": True},
        scalar_decisions={},
        warnings=[],
    )
    rec = ExtractionRecord(
        id=new_id(),
        uploaded_file_id=uploaded.id,
        raw_text="Liberty Insurance www.libertyinsurance.com.my QBG1431",
        reading_quality="ready",
    )
    session = QuotationSession(
        id=new_id(),
        owner_id=user.id,
        uploaded_file_id=uploaded.id,
        draft_id=draft.id,
        tenure_id=tenure.id,
        tracked_vehicle_id=tv.id,
        quotation_ref="RL260000900",
        detected_company="Kurnia",
        status=AccountStatus.ACTIVE.value,
    )
    db.add_all([user, liberty, kurnia, batch, uploaded, tv, tenure, draft, rec, session])
    db.commit()
    return user, session, draft, uploaded, rec, tenure, pdf_path


def test_deep_redetect_pipeline_runs_verification_on_conflict_and_skips_when_clean():
    steps_seen: list[str] = []
    call_counter = {"n": 0}

    def fake_gemini(*_args, **_kwargs):
        call_counter["n"] += 1
        if call_counter["n"] == 1:
            # Deliberate mismatch vs logo ("Liberty") and optional_covers_sum (100 != 418.05) to trigger Pass 4
            return {
                "insurance_company": "Kurnia",
                "customer_name": "WONG SUI PENG",
                "vehicle_no": "QBG1431",
                "coverage_type": "Comprehensive",
                "coverage_amount": "66000.00",
                "total_optional_cover_amount": "418.05",
                "premium": "1621.00",
                "total_amount": "1621.00",
                "detected_benefits": [
                    {"label": "Windscreen", "premium_cost": "100.00", "is_optional_cover": True},
                ],
            }
        return {
            "insurance_company": "Liberty",
            "total_optional_cover_amount": "418.05",
            "detected_benefits": [
                {"label": "Windscreen", "premium_cost": "150.00", "is_optional_cover": True},
                {"label": "Special Perils", "premium_cost": "268.05", "is_optional_cover": True},
            ],
        }

    fake_pass1 = {
        "raw_text": "Liberty Insurance\nwww.libertyinsurance.com.my\nQBG1431\nauto365 Comprehensive Premier",
        "page1_text": "Liberty Insurance www.libertyinsurance.com.my",
        "native_fields": {"vehicle_no": {"value": "QBG1431"}},
        "candidates": {},
        "logo_crop_png": b"fake-png",
        "logo_color_meta": {"color_hint": "dark_blue_liberty_or_kurnia"},
        "p1_signals": {"winning_brand": "Liberty"},
    }
    fake_verdict = {"canonical_company": "Liberty", "confidence": 0.96, "reasoning": "Dark blue torch + libertyinsurance.com.my"}

    with patch("app.extraction.deep_redetect_engine._run_pass1_native_and_logo_crop", return_value=fake_pass1), \
         patch("app.extraction.deep_redetect_engine.gemini_extractor.get_key_pool", return_value=_DummyPool()), \
         patch("app.extraction.deep_redetect_engine.verify_brand_logo_with_vision", return_value=fake_verdict), \
         patch("app.extraction.deep_redetect_engine.gemini_extractor.extract_with_gemini_sync", side_effect=fake_gemini):
        res = run_deep_redetect_pipeline(
            pdf_bytes=b"%PDF-1.4 mock",
            source_filename="Liberty.pdf",
            current_fields={"insurance_company": "Kurnia", "vehicle_no": "QBG1431"},
            on_progress=lambda sk, _sl, _ww, _pct, _det: steps_seen.append(sk),
        )

    assert call_counter["n"] == 2  # Pass 3 + Pass 4 reconciliation executed
    assert steps_seen == [
        "native_and_logo_crop",
        "brand_logo_vision",
        "fresh_multimodal_extraction",
        "cross_verify_and_audit",
        "cross_verify_and_audit",
    ]
    assert res.gemini_res["insurance_company"] == "Liberty"
    assert len(res.gemini_res["detected_benefits"]) == 2
    assert res.passes_used == 4

    # Clean case: passes agree & math clean -> Pass 4 extra AI call is skipped
    clean_calls = {"n": 0}

    def fake_clean_gemini(*_args, **_kwargs):
        clean_calls["n"] += 1
        return {
            "insurance_company": "Allianz",
            "customer_name": "ALICE TAN",
            "vehicle_no": "VAA1234",
            "coverage_type": "Comprehensive",
            "coverage_amount": "55000.00",
            "premium": "1200.00",
            "total_amount": "1200.00",
            "detected_benefits": [],
        }

    clean_pass1 = {
        "raw_text": "Allianz General Insurance Company (Malaysia) Berhad VAA1234",
        "page1_text": "Allianz General Insurance VAA1234",
        "native_fields": {"insurance_company": {"value": "Allianz"}, "vehicle_no": {"value": "VAA1234"}},
        "candidates": {},
        "logo_crop_png": b"fake-png",
        "logo_color_meta": {},
        "p1_signals": {},
    }
    with patch("app.extraction.deep_redetect_engine._run_pass1_native_and_logo_crop", return_value=clean_pass1), \
         patch("app.extraction.deep_redetect_engine.gemini_extractor.get_key_pool", return_value=_DummyPool()), \
         patch("app.extraction.deep_redetect_engine.gemini_extractor.extract_with_gemini_sync", side_effect=fake_clean_gemini):
        clean_res = run_deep_redetect_pipeline(
            pdf_bytes=b"%PDF-1.4 mock",
            source_filename="Allianz.pdf",
            current_fields={"insurance_company": "Allianz", "vehicle_no": "VAA1234"},
        )
    assert clean_calls["n"] == 1
    assert clean_res.audit_conflicts == []
    assert clean_res.math_issues == []


def test_deep_redetect_cooperative_cancel_leaves_draft_untouched(db_setup, tmp_path):
    db, _ = db_setup
    user, session, draft, uploaded, rec, _, pdf_path = _seed_session(db, tmp_path)
    cancel_ev = threading.Event()
    cancel_ev.set()

    with pytest.raises(RedetectCancelledError):
        run_deep_redetect_pipeline(
            pdf_bytes=pdf_path.read_bytes(),
            source_filename=uploaded.original_filename,
            current_fields={"insurance_company": "Kurnia"},
            cancel_event=cancel_ev,
        )

    db.refresh(draft)
    assert draft.fields["insurance_company"]["value"] == "Kurnia"
    assert draft.fields["motor_discount_pct"]["value"] == "5.00"


def test_apply_gemini_result_preserves_active_motor_discount(db_setup, tmp_path):
    db, _ = db_setup
    _, session, draft, uploaded, rec, _, _ = _seed_session(db, tmp_path)
    settings = get_settings()
    draft.fields["quotation_discount"] = {"value": "0.00", "status": "ready"}
    draft.fields["roadtax"] = {"value": "120.00", "status": "ready"}
    draft.fields["service_fee"] = {"value": "20.00", "status": "ready"}
    db.commit()

    apply_gemini_result(
        db,
        settings,
        draft,
        session,
        uploaded,
        rec,
        {
            "insurance_company": "Liberty",
            "customer_name": "WONG SUI PENG",
            "vehicle_no": "QBG1431",
            "coverage_amount": "66000.00",
            "premium": "1000.00",
            "total_amount": "1000.00",
            "motor_discount_pct": "0.00",
            "detected_benefits": [],
        },
        "RL260000900",
        [
            {"company_id": "c0000000-0000-4000-8000-000000000091", "name": "Liberty", "aliases": ["Liberty", "Liberty Insurance"]},
            {"company_id": "c0000000-0000-4000-8000-000000000002", "name": "Kurnia", "aliases": ["Kurnia"]},
        ],
        [],
        brand_verdict={"canonical_company": "Liberty", "confidence": 0.96},
    )
    assert draft.fields["insurance_company"]["value"] == "Liberty"
    assert draft.fields["motor_discount_pct"]["value"] == "5.00"
    assert draft.fields["effective_discount"]["value"] == "50.00"
    assert draft.fields["net_motor_premium"]["value"] == "950.00"
    # 950.00 net + 20.00 default runner fee (no CC/roadtax table row seeded here -> roadtax 0.00) = 970.00
    assert draft.fields["total_amount"]["value"] == "970.00"


def test_redetect_jobs_sync_and_http_rbac_ownership(db_setup, tmp_path):
    db, SessionFactory = db_setup
    user, session, draft, _, _, tenure, _ = _seed_session(db, tmp_path)
    other_staff = User(
        id=new_id(),
        email="other@risklocker.test",
        name="Other Staff",
        role=Role.STAFF.value,
        password_hash="x",
        status=AccountStatus.ACTIVE.value,
    )
    unauthorized_dev = User(
        id=new_id(),
        email="dev@risklocker.test",
        name="Dev User",
        role=Role.DEV.value,
        password_hash="x",
        status=AccountStatus.ACTIVE.value,
    )
    db.add_all([other_staff, unauthorized_dev])
    db.commit()

    settings = get_settings()
    fake_res = {
        "insurance_company": "Liberty",
        "customer_name": "WONG SUI PENG",
        "vehicle_no": "QBG1431",
        "coverage_type": "Comprehensive",
        "coverage_amount": "66000.00",
        "premium": "1621.00",
        "total_amount": "1621.00",
        "detected_benefits": [],
    }

    with patch("app.extraction.deep_redetect_engine.gemini_extractor.get_key_pool", return_value=_DummyPool()), \
         patch("app.extraction.deep_redetect_engine.verify_brand_logo_with_vision", return_value={"canonical_company": "Liberty", "confidence": 0.98}), \
         patch("app.extraction.deep_redetect_engine.gemini_extractor.extract_with_gemini_sync", return_value=fake_res):
        started = start_session_redetect_job(
            db,
            session.id,
            user,
            settings,
            session_factory=SessionFactory,
            run_sync=True,
        )
        assert started["job"]["status"] == "completed"
        assert started["job"]["progress_pct"] == 100
        assert started["job"]["result_summary"]["detected_company"] == "Liberty"

        # Comparison-scoped re-detect syncs tenure entries cleanly too
        comp_started = start_comparison_redetect_job(
            db,
            tenure.id,
            user,
            settings,
            session_factory=SessionFactory,
            run_sync=True,
        )
        assert comp_started["job"]["status"] == "completed"

    # Non-admin user cannot view or cancel another staff user's redetect job (404 zero data leak)
    active_user = {"u": other_staff}
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(routes.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[current_user] = lambda: active_user["u"]
    client = TestClient(app)

    r_status = client.get(f"/api/redetect-jobs/{started['job_id']}")
    assert r_status.status_code == 404
    r_cancel = client.post(f"/api/redetect-jobs/{started['job_id']}/cancel")
    assert r_cancel.status_code == 404

    # Owner can view and invoke /sessions/{id}/redetect and /comparison/{id}/redetect
    active_user["u"] = user
    r_owner = client.get(f"/api/redetect-jobs/{started['job_id']}")
    assert r_owner.status_code == 200
    assert r_owner.json()["job"]["job_id"] == started["job_id"]
    assert get_redetect_job(started["job_id"], user)["status"] == "completed"
    assert cancel_redetect_job(started["job_id"], user)["cancelled"] is True

    # HTTP POST routes enforce RBAC/owner checks and return {job_id, job}
    active_user["u"] = unauthorized_dev
    assert client.post(f"/api/sessions/{session.id}/redetect").status_code == 404

    active_user["u"] = user
    with patch("app.services.redetect_job_service.threading.Thread") as mock_thread:
        r_sess_post = client.post(f"/api/sessions/{session.id}/redetect")
        assert r_sess_post.status_code == 200
        assert "job_id" in r_sess_post.json()
        assert mock_thread.called

        r_comp_post = client.post(f"/api/comparison/{tenure.id}/redetect", json={"deep": True})
        assert r_comp_post.status_code == 200
        assert "job_id" in r_comp_post.json()
