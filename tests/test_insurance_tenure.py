"""Unit tests for insurance_tenure_service."""

from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.tables import (
    Base,
    InsuranceCompany,
    InsuranceTenure,
    QuotationDraft,
    Session as SessionModel,
    TrackedVehicle,
    UploadedFile,
    User,
    new_id,
)
from app.services.insurance_tenure_service import (
    compute_quotation_content_hash,
    evaluate_tenure_ingestion,
    get_tenure_timeline,
    normalize_tenure_dates,
    resolve_or_create_tenure,
    update_tenure_status,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def test_compute_quotation_content_hash():
    fields_1 = {
        "vehicle_no": {"value": "JWK 9488"},
        "insurance_company": {"value": "Syarikat Takaful Malaysia Berhad"},
        "sum_insured": {"value": "57,000.00"},
        "premium": {"value": "890.50"},
        "total_amount": {"value": "995.00"},
        "cover_start_date": {"value": "08/09/2026"},
        "cover_end_date": {"value": "07/09/2027"},
    }
    benefits_1 = [{"concept_code": "windscreen", "cost": "150.00"}]

    hash_1 = compute_quotation_content_hash(fields_1, benefits_1)
    assert len(hash_1) == 64

    # Identical data with minor whitespace/case differences yields identical hash
    fields_2 = {
        "vehicle_no": {"value": "jwk9488"},
        "insurance_company": {"value": "SYARIKAT TAKAFUL MALAYSIA BERHAD"},
        "sum_insured": {"value": "57000.00"},
        "premium": {"value": "890.5"},
        "total_amount": {"value": "995.00"},
        "cover_start_date": {"value": "08/09/2026"},
        "cover_end_date": {"value": "07/09/2027"},
    }
    benefits_2 = [{"concept_code": "WINDSCREEN", "cost": "150.0"}]
    hash_2 = compute_quotation_content_hash(fields_2, benefits_2)
    assert hash_1 == hash_2

    # Changed value yields different hash
    fields_3 = dict(fields_1)
    fields_3["sum_insured"] = {"value": "60,000.00"}
    hash_3 = compute_quotation_content_hash(fields_3, benefits_1)
    assert hash_1 != hash_3


def test_normalize_tenure_dates():
    start_dt, end_dt, expiry_month = normalize_tenure_dates("08/09/2026", "07/09/2027")
    assert start_dt.year == 2026
    assert start_dt.month == 9
    assert start_dt.day == 8
    assert end_dt.year == 2027
    assert end_dt.month == 9
    assert end_dt.day == 7
    assert expiry_month == "2027-09"


def test_resolve_or_create_tenure(db_session: Session):
    # First creation
    t1 = resolve_or_create_tenure(
        db_session,
        vehicle_no="JWK 9488",
        customer_name="TEY SIOK BEE",
        start_date="08/09/2026",
        end_date="07/09/2027",
    )
    assert t1.id is not None
    assert t1.vehicle_no == "JWK9488"
    assert t1.customer_name == "TEY SIOK BEE"
    assert t1.expiry_month == "2027-09"

    # Second call for same vehicle and dates returns existing tenure
    t2 = resolve_or_create_tenure(
        db_session,
        vehicle_no="JWK9488",
        customer_name="TEY SIOK BEE (MRS)",
        start_date="08/09/2026",
        end_date="07/09/2027",
    )
    assert t2.id == t1.id
    assert t2.customer_name == "TEY SIOK BEE (MRS)"


def test_evaluate_tenure_ingestion_and_versioning(db_session: Session):
    # Setup user and vehicle
    user = User(email="test@user.local", name="Tester", role="admin")
    db_session.add(user)
    db_session.flush()

    tenure = resolve_or_create_tenure(
        db_session,
        vehicle_no="JWK 9488",
        customer_name="TEY SIOK BEE",
        start_date="08/09/2026",
        end_date="07/09/2027",
    )

    # 1. First quote (STMB v1)
    hash_v1 = "hash_stmb_v1"
    action_1, sess_1, ver_1 = evaluate_tenure_ingestion(
        db_session,
        tenure_id=tenure.id,
        company_name="STMB",
        content_hash=hash_v1,
    )
    assert action_1 == "CREATE_FIRST"
    assert ver_1 == 1

    # Simulate creating the session in DB
    s1 = SessionModel(
        owner_id=user.id,
        uploaded_file_id=new_id(),
        draft_id=new_id(),
        detected_company="STMB",
        tenure_id=tenure.id,
        tenure_version=1,
        is_tenure_active=True,
        content_hash=hash_v1,
    )
    db_session.add(s1)
    db_session.flush()

    # 2. Re-upload identical PDF (zero changes) -> SKIP_IDENTICAL
    action_dup, sess_dup, ver_dup = evaluate_tenure_ingestion(
        db_session,
        tenure_id=tenure.id,
        company_name="STMB",
        content_hash=hash_v1,
    )
    assert action_dup == "SKIP_IDENTICAL"
    assert sess_dup.id == s1.id
    assert ver_dup == 1

    # 3. Upload modified quote (revised pricing) -> CREATE_VERSION (v2)
    hash_v2 = "hash_stmb_v2"
    action_2, sess_2, ver_2 = evaluate_tenure_ingestion(
        db_session,
        tenure_id=tenure.id,
        company_name="STMB",
        content_hash=hash_v2,
    )
    assert action_2 == "CREATE_VERSION"
    assert ver_2 == 2
    assert s1.is_tenure_active is False

    # Simulate creating v2 in DB
    s2 = SessionModel(
        owner_id=user.id,
        uploaded_file_id=new_id(),
        draft_id=new_id(),
        detected_company="STMB",
        tenure_id=tenure.id,
        tenure_version=2,
        is_tenure_active=True,
        content_hash=hash_v2,
    )
    db_session.add(s2)
    db_session.flush()

    # 4. Another insurer (QBE) uploaded for same tenure -> CREATE_FIRST (v1)
    action_qbe, _, ver_qbe = evaluate_tenure_ingestion(
        db_session,
        tenure_id=tenure.id,
        company_name="QBE",
        content_hash="hash_qbe_1",
    )
    assert action_qbe == "CREATE_FIRST"
    assert ver_qbe == 1


def test_tenure_timeline_and_status_update(db_session: Session):
    user = User(email="test@user.local", name="Tester", role="admin")
    db_session.add(user)
    db_session.flush()

    tenure = resolve_or_create_tenure(
        db_session,
        vehicle_no="JWK 9488",
        customer_name="TEY SIOK BEE",
        start_date="08/09/2026",
        end_date="07/09/2027",
    )

    f_id = new_id()
    draft = QuotationDraft(
        uploaded_file_id=f_id,
        owner_id=user.id,
        fields={"total_amount": {"value": "995.00"}, "sum_insured": {"value": "57,000"}},
    )
    db_session.add(draft)
    db_session.flush()

    s = SessionModel(
        owner_id=user.id,
        uploaded_file_id=f_id,
        draft_id=draft.id,
        detected_company="STMB",
        tenure_id=tenure.id,
        tenure_version=1,
        is_tenure_active=True,
        quotation_ref="RL260000101",
    )
    db_session.add(s)
    db_session.flush()

    # Verify timeline output
    timeline = get_tenure_timeline(db_session, tenure.id)
    assert timeline is not None
    assert timeline["vehicle_no"] == "JWK9488"
    assert "STMB" in timeline["sourced_quotes_by_company"]
    assert len(timeline["generated_risklocker_quotations"]) == 1
    assert timeline["generated_risklocker_quotations"][0]["quotation_ref"] == "RL260000101"

    # Update status to hit
    updated = update_tenure_status(
        db_session,
        tenure.id,
        status="hit",
        user_id=user.id,
        winning_quotation_ref="RL260000101",
        won_premium=995.00,
        notes="Client approved STMB option via WhatsApp",
    )
    assert updated.status == "hit"
    assert float(updated.won_premium) == 995.00
