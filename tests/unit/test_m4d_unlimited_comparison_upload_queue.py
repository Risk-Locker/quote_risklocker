"""Hermetic TDD suite for Milestone 4d: Unlimited Comparison Upload Limit & Batch Job Status Polling."""

from __future__ import annotations

import sys
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
from app.api.routers.sessions import router as sessions_router
from app.core.errors import register_error_handlers
from app.models.tables import Base, Job, User, new_id
from app.services.admin_service import (
    get_comparison_upload_limit,
    set_comparison_upload_limit,
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


def test_comparison_upload_limit_setting_defaults_to_null_unlimited_and_supports_int(hermetic_db: Session):
    """P10: comparison_upload_limit defaults to None (unlimited) and can be set to an int or reset to None."""
    admin = User(id=new_id(), email="admin@risklocker.test", password_hash="x", role="admin", status="active")
    hermetic_db.add(admin)
    hermetic_db.commit()

    # Default is None (unlimited)
    assert get_comparison_upload_limit(hermetic_db) is None

    # Set to 150
    saved = set_comparison_upload_limit(hermetic_db, admin, 150)
    assert saved == 150
    assert get_comparison_upload_limit(hermetic_db) == 150

    # Reset to None (unlimited)
    reset = set_comparison_upload_limit(hermetic_db, admin, None)
    assert reset is None
    assert get_comparison_upload_limit(hermetic_db) is None


def test_batch_jobs_status_endpoint_routing_owner_scoping_and_200_cap(hermetic_db: Session):
    """Verify GET /jobs/status resolves before /jobs/{job_id}, enforces <=200 IDs, and scopes to owner_id."""
    user_a = User(id=new_id(), email="a@risklocker.test", password_hash="x", role="staff", status="active")
    user_b = User(id=new_id(), email="b@risklocker.test", password_hash="x", role="staff", status="active")
    job_a1 = Job(
        id=new_id(),
        owner_id=user_a.id,
        job_type="extract_pdf",
        idempotency_key="k-a1",
        state="queued",
        progress=10,
        phase="validating_source",
        payload={},
    )
    job_a2 = Job(
        id=new_id(),
        owner_id=user_a.id,
        job_type="extract_pdf",
        idempotency_key="k-a2",
        state="completed",
        progress=100,
        phase="saving_review",
        payload={},
    )
    job_b1 = Job(
        id=new_id(),
        owner_id=user_b.id,
        job_type="extract_pdf",
        idempotency_key="k-b1",
        state="processing",
        progress=50,
        phase="gemini_ai",
        payload={},
    )
    hermetic_db.add_all([user_a, user_b, job_a1, job_a2, job_b1])
    hermetic_db.commit()

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(sessions_router)
    app.dependency_overrides[get_db] = lambda: hermetic_db
    app.dependency_overrides[current_user] = lambda: user_a
    client = TestClient(app)

    # 1. Batch poll returns user_a's jobs and ignores user_b's job
    res = client.get(f"/jobs/status?ids={job_a1.id},{job_a2.id},{job_b1.id}")
    assert res.status_code == 200
    data = res.json()
    assert job_a1.id in data["jobs"]
    assert job_a2.id in data["jobs"]
    assert job_b1.id not in data["jobs"]
    assert data["jobs"][job_a1.id]["state"] == "queued"
    assert data["jobs"][job_a2.id]["state"] == "completed"

    # 2. Exceeding 200 IDs returns 422
    too_many = ",".join(f"job-{i}" for i in range(201))
    res_422 = client.get(f"/jobs/status?ids={too_many}")
    assert res_422.status_code == 422
