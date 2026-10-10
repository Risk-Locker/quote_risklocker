import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from app.models.tables import Base, Session as SessionModel, UploadedFile, QuotationDraft, InsuranceTenure, TrackedVehicle, Batch, User, new_id
from app.services.session_service import list_sessions


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_user(db_session: Session):
    user = User(
        id=new_id(),
        email="staff@risklocker.local",
        password_hash="dummy_hash",
        name="Staff Member",
        role="staff",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_session_listing_isolates_to_ledger_and_test_sessions(db_session: Session, test_user: User):
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=364)

    batch = Batch(id=new_id(), owner_id=test_user.id, name="Test Batch")
    db_session.add(batch)

    tv_active = TrackedVehicle(id=new_id(), vehicle_no="ACT1234", car_brand="Honda", car_model="Civic")
    tv_discarded = TrackedVehicle(id=new_id(), vehicle_no="DIS5678", car_brand="Toyota", car_model="Vios")
    db_session.add_all([tv_active, tv_discarded])
    db_session.flush()

    # 1. Active tenure
    tenure_active = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=tv_active.id,
        vehicle_no="ACT1234",
        customer_name="Active Client",
        coverage_start_date=now,
        coverage_end_date=end,
        expiry_month="2027-10",
        is_discarded=False,
    )
    # 2. Discarded tenure
    tenure_discarded = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=tv_discarded.id,
        vehicle_no="DIS5678",
        customer_name="Discarded Client",
        coverage_start_date=now,
        coverage_end_date=end,
        expiry_month="2027-10",
        is_discarded=True,
    )
    db_session.add_all([tenure_active, tenure_discarded])
    db_session.flush()

    def make_file_and_draft(name: str):
        uf = UploadedFile(id=new_id(), batch_id=batch.id, owner_id=test_user.id, original_filename=f"{name}.pdf", content_type="application/pdf", storage_path=f"/test/{name}.pdf")
        qd = QuotationDraft(id=new_id(), uploaded_file_id=uf.id, owner_id=test_user.id, fields={})
        db_session.add_all([uf, qd])
        db_session.flush()
        return uf, qd

    # Session A: Linked to active ledger tenure -> SHOULD appear
    uf_a, qd_a = make_file_and_draft("session_a")
    sess_a = SessionModel(
        id=new_id(),
        owner_id=test_user.id,
        uploaded_file_id=uf_a.id,
        draft_id=qd_a.id,
        tenure_id=tenure_active.id,
        is_test=False,
        status="active",
    )

    # Session B: Test session (unlinked) -> SHOULD appear
    uf_b, qd_b = make_file_and_draft("session_b")
    sess_b = SessionModel(
        id=new_id(),
        owner_id=test_user.id,
        uploaded_file_id=uf_b.id,
        draft_id=qd_b.id,
        tenure_id=None,
        is_test=True,
        status="active",
    )

    # Session C: Stray unlinked session -> SHOULD NOT appear
    uf_c, qd_c = make_file_and_draft("session_c")
    sess_c = SessionModel(
        id=new_id(),
        owner_id=test_user.id,
        uploaded_file_id=uf_c.id,
        draft_id=qd_c.id,
        tenure_id=None,
        is_test=False,
        status="active",
    )

    # Session D: Linked to discarded tenure -> SHOULD NOT appear
    uf_d, qd_d = make_file_and_draft("session_d")
    sess_d = SessionModel(
        id=new_id(),
        owner_id=test_user.id,
        uploaded_file_id=uf_d.id,
        draft_id=qd_d.id,
        tenure_id=tenure_discarded.id,
        is_test=False,
        status="active",
    )

    # Session E: Trashed session on active tenure -> SHOULD NOT appear
    uf_e, qd_e = make_file_and_draft("session_e")
    sess_e = SessionModel(
        id=new_id(),
        owner_id=test_user.id,
        uploaded_file_id=uf_e.id,
        draft_id=qd_e.id,
        tenure_id=tenure_active.id,
        is_test=False,
        status="trash",
    )

    db_session.add_all([sess_a, sess_b, sess_c, sess_d, sess_e])
    db_session.commit()

    items, total = list_sessions(db_session, user_id=test_user.id, limit=50)
    returned_ids = {s.id for s in items}

    assert sess_a.id in returned_ids, "Active ledger session must appear"
    assert sess_b.id in returned_ids, "Test session must appear"
    assert sess_c.id not in returned_ids, "Stray unlinked session must NOT appear"
    assert sess_d.id not in returned_ids, "Session on discarded tenure must NOT appear"
    assert sess_e.id not in returned_ids, "Trashed session must NOT appear"
