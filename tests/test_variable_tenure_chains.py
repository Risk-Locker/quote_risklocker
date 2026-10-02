"""Hermetic unit tests for variable tenure chains and date modularity."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.tables import (
    Base,
    CustomerAccount,
    InsuranceTenure,
    QuotationDraft,
    Session as SessionModel,
    TrackedVehicle,
    UploadedFile,
    User,
    new_id,
)
from app.services.insurance_tenure_service import (
    auto_project_next_renewal,
    mark_tenure_lapsed,
    resolve_or_create_tenure,
    shift_tenure_dates,
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


def test_tenure_chaining_on_creation(db_session: Session):
    # Year 1 tenure: 2025-01-01 to 2025-12-31
    start_1 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end_1 = datetime(2025, 12, 31, tzinfo=timezone.utc)
    tenure_1 = resolve_or_create_tenure(
        db_session,
        vehicle_no="WYY1234",
        customer_name="PL INKJET SDN BHD",
        start_date=start_1,
        end_date=end_1,
    )
    db_session.commit()

    assert tenure_1.previous_tenure_id is None
    assert tenure_1.tenure_chain_id is not None
    assert tenure_1.reminder_window_start is not None
    assert tenure_1.reminder_window_start.date() == (start_1 - timedelta(days=90)).date()

    # Year 2 tenure: 2026-01-01 to 2026-12-31 on same vehicle
    start_2 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_2 = datetime(2026, 12, 31, tzinfo=timezone.utc)
    tenure_2 = resolve_or_create_tenure(
        db_session,
        vehicle_no="WYY1234",
        customer_name="PL INKJET SDN BHD",
        start_date=start_2,
        end_date=end_2,
    )
    db_session.commit()

    # Automatically chained!
    assert tenure_2.previous_tenure_id == tenure_1.id
    assert tenure_2.tenure_chain_id == tenure_1.tenure_chain_id
    assert tenure_2.delay_days == 0


def test_auto_project_next_renewal(db_session: Session):
    start = datetime(2026, 5, 10, tzinfo=timezone.utc)
    end = datetime(2027, 5, 9, tzinfo=timezone.utc)
    t = resolve_or_create_tenure(
        db_session,
        vehicle_no="VAA8888",
        customer_name="Tan Ah Kow",
        start_date=start,
        end_date=end,
    )
    t.road_tax = 90.00
    t.runner_fee = 10.00
    db_session.commit()

    # auto_project_next_renewal was permanently disabled (STATE.md:66)
    # Policies are created when uploaded by staff; no dummy projections created.
    projected = auto_project_next_renewal(db_session, t.id)
    db_session.commit()

    assert projected is not None
    assert projected.id == t.id
    assert projected.is_projected is False

    # Calling it again returns the same tenure idempotently
    projected2 = auto_project_next_renewal(db_session, t.id)
    assert projected2.id == t.id


def test_auto_project_triggered_on_won_status(db_session: Session):
    user = User(
        id=new_id(),
        email="staff@risklocker.com",
        name="Staff User",
        role="editor",
        password_hash="mock",
    )
    db_session.add(user)
    db_session.commit()

    start = datetime(2026, 3, 1, tzinfo=timezone.utc)
    end = datetime(2027, 2, 28, tzinfo=timezone.utc)
    t = resolve_or_create_tenure(
        db_session,
        vehicle_no="ABC1111",
        customer_name="Alice Smith",
        start_date=start,
        end_date=end,
    )
    db_session.commit()

    # Update status to hit
    update_tenure_status(
        db_session,
        t.id,
        status="hit",
        user_id=user.id,
        won_premium=1850.50,
    )
    db_session.commit()

    # Auto-projection on won status is disabled; no dummy upcoming tenure is generated
    projected = db_session.query(InsuranceTenure).filter(
        InsuranceTenure.previous_tenure_id == t.id
    ).first()
    assert projected is None


def test_shift_tenure_dates_modular_sync(db_session: Session):
    from app.models.tables import Batch
    user = User(
        id=new_id(),
        email="admin@risklocker.com",
        name="Admin",
        role="admin",
        password_hash="mock",
    )
    db_session.add(user)
    db_session.commit()

    # Tenure 1: 2025-01-01 to 2025-12-31
    t1 = resolve_or_create_tenure(
        db_session,
        vehicle_no="BEE9999",
        customer_name="Late Renewal Corp",
        start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2025, 12, 31, tzinfo=timezone.utc),
    )
    db_session.commit()

    # Renewal Tenure 2 originally expected on 2026-01-01
    t2 = resolve_or_create_tenure(
        db_session,
        vehicle_no="BEE9999",
        customer_name="Late Renewal Corp",
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
    )
    t2.previous_tenure_id = t1.id
    db_session.commit()

    batch = Batch(id=new_id(), owner_id=user.id, name="Test Batch")
    db_session.add(batch)
    db_session.flush()

    # Attach a session and draft to t2
    u_file = UploadedFile(
        id=new_id(),
        batch_id=batch.id,
        owner_id=user.id,
        original_filename="q.pdf",
        content_type="application/pdf",
        storage_path="/tmp/q.pdf",
    )
    db_session.add(u_file)
    db_session.flush()

    draft = QuotationDraft(
        id=new_id(),
        uploaded_file_id=u_file.id,
        owner_id=user.id,
        fields={},
    )
    db_session.add(draft)
    db_session.flush()

    sess = SessionModel(
        id=new_id(),
        owner_id=user.id,
        uploaded_file_id=u_file.id,
        draft_id=draft.id,
        tenure_id=t2.id,
        coverage_start_date=t2.coverage_start_date,
        coverage_end_date=t2.coverage_end_date,
    )
    db_session.add(sess)
    db_session.commit()

    # Customer was late by 15 days, renewing on 2026-01-16
    new_start = datetime(2026, 1, 16, tzinfo=timezone.utc)
    shifted = shift_tenure_dates(
        db_session,
        t2.id,
        new_start_date=new_start,
        user_id=user.id,
    )
    db_session.commit()

    # Delay days calculated from expected 2026-01-01
    assert shifted.delay_days == 15
    assert shifted.coverage_start_date is not None
    assert shifted.coverage_start_date.date() == new_start.date()
    # End date automatically synchronized to +1 year - 1 day
    assert shifted.coverage_end_date is not None
    assert shifted.coverage_end_date.date() == datetime(2027, 1, 15).date()
    assert shifted.is_projected is False
    assert shifted.status == "draft"

    # Child session and draft dates were synchronized
    db_session.refresh(sess)
    db_session.refresh(draft)
    assert sess.coverage_start_date is not None
    assert sess.coverage_start_date.date() == new_start.date()
    assert sess.coverage_end_date is not None
    assert sess.coverage_end_date.date() == datetime(2027, 1, 15).date()
    assert draft.fields["cover_start_date"]["value"] == "16/01/2026"
    assert draft.fields["cover_end_date"]["value"] == "15/01/2027"


def test_locked_past_policy_dates(db_session: Session):
    # Past won tenure from 2024
    t = resolve_or_create_tenure(
        db_session,
        vehicle_no="OLD123",
        customer_name="Historical Client",
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 12, 31, tzinfo=timezone.utc),
    )
    t.status = "hit"
    db_session.commit()

    # Attempting to shift historical completed dates without force_past must raise ValueError
    with pytest.raises(ValueError, match="Past completed policy dates are locked"):
        shift_tenure_dates(
            db_session,
            t.id,
            new_start_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
        )

    # But with force_past=True (admin override), it succeeds
    shifted = shift_tenure_dates(
        db_session,
        t.id,
        new_start_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
        force_past=True,
    )
    assert shifted.coverage_start_date.date() == datetime(2024, 1, 15).date()


def test_mark_tenure_lapsed(db_session: Session):
    t = resolve_or_create_tenure(
        db_session,
        vehicle_no="BYE888",
        customer_name="Leaving Client",
        start_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        end_date=datetime(2027, 5, 31, tzinfo=timezone.utc),
    )
    db_session.commit()

    lapsed = mark_tenure_lapsed(
        db_session,
        t.id,
        reason="Sold vehicle to dealer",
    )
    db_session.commit()

    assert lapsed.status == "lapsed"
    assert lapsed.lapsed_at is not None
    assert lapsed.miss_reason == "Sold vehicle to dealer"
