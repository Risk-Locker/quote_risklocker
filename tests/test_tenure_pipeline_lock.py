"""Test that tenure pipeline is locked once an official cover note is linked."""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db, current_user
from app.api.routers import tenures as routes
from app.models.tables import (
    Base,
    Batch,
    InsuranceTenure,
    QuotationDraft,
    Session as SessionModel,
    TrackedVehicle,
    UploadedFile,
    User,
    new_id,
)


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


@pytest.fixture
def client(db_session: Session, test_user: User):
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[current_user] = lambda: test_user
    with TestClient(app) as test_client:
        yield test_client


def test_pipeline_locked_when_covernote_linked(client: TestClient, db_session: Session, test_user: User):
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=364)

    batch = Batch(id=new_id(), owner_id=test_user.id, name="Test Batch")
    db_session.add(batch)

    tv = TrackedVehicle(id=new_id(), vehicle_no="LOCK1234", car_brand="Honda", car_model="Civic")
    db_session.add(tv)
    db_session.flush()

    uf = UploadedFile(id=new_id(), batch_id=batch.id, owner_id=test_user.id, original_filename="covernote.pdf", content_type="application/pdf", storage_path="/test/cn.pdf")
    qd = QuotationDraft(id=new_id(), uploaded_file_id=uf.id, owner_id=test_user.id, fields={})
    db_session.add_all([uf, qd])
    db_session.flush()

    cn_session = SessionModel(
        id=new_id(),
        owner_id=test_user.id,
        uploaded_file_id=uf.id,
        draft_id=qd.id,
        document_type="covernote",
        status="active",
    )
    db_session.add(cn_session)
    db_session.flush()

    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=tv.id,
        vehicle_no="LOCK1234",
        customer_name="Lock Client",
        coverage_start_date=now,
        coverage_end_date=end,
        expiry_month="2027-10",
        stage="Issue Policy",
        status="draft",
        covernote_session_id=cn_session.id,
        is_discarded=False,
    )
    db_session.add(tenure)
    db_session.commit()

    # 1. Attempting to regress to 'Quotations' MUST be rejected with HTTP 400
    res_quote = client.patch(
        f"/api/tenures/{tenure.id}/ledger-fields",
        json={"stage": "Quotations"},
    )
    assert res_quote.status_code == 400
    assert "Cannot revert stage to Quotations or Material to Client while an official Cover Note is linked" in res_quote.json()["detail"]

    # 2. Attempting to regress to 'Material to Client' MUST also be rejected with HTTP 400
    res_mat = client.patch(
        f"/api/tenures/{tenure.id}/ledger-fields",
        json={"stage": "Material to Client"},
    )
    assert res_mat.status_code == 400
    assert "Cannot revert stage to Quotations or Material to Client while an official Cover Note is linked" in res_mat.json()["detail"]

    # 3. Advancing to 'Close - Win' is allowed
    res_win = client.patch(
        f"/api/tenures/{tenure.id}/ledger-fields",
        json={"stage": "Close - Win"},
    )
    assert res_win.status_code == 200

    # 4. Once covernote is unlinked, reverting to Quotations is allowed
    tenure.covernote_session_id = None
    db_session.commit()

    res_quote_after_unlink = client.patch(
        f"/api/tenures/{tenure.id}/ledger-fields",
        json={"stage": "Quotations"},
    )
    assert res_quote_after_unlink.status_code == 200
