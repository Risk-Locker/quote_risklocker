"""Hermetic API tests for /comparison endpoints."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_PROVIDER": "supabase_postgres",
        "DATABASE_URL": "postgresql://postgres:password@db.test.supabase.co:5432/postgres",
        "AUTH_HASH_SECRET": "test-auth-hash-secret-that-is-long-enough",
        "STORAGE_DRIVER": "supabase",
        "SUPABASE_URL": "https://project-ref.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
    }
)

from app.api import routes
from app.api.deps import current_user, get_db
from app.models.tables import (
    Base,
    InsuranceTenure,
    QuotationDraft,
    Session as SessionModel,
    TrackedVehicle,
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
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session):
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")

    admin = User(
        id=str(uuid4()),
        name="Admin Tester",
        email="admin@risklocker.local",
        password_hash="mock",
        role="admin",
    )
    db_session.add(admin)
    db_session.flush()

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[current_user] = lambda: admin

    with TestClient(app) as test_client:
        yield test_client


def test_comparison_api_crud_and_teaser(client: TestClient, db_session: Session):
    vehicle = TrackedVehicle(
        id=new_id(),
        vehicle_no="JWK9488",
        car_brand="Perodua",
        car_model="Aruz 1.5 AV",
        engine_cc="1496 CC",
    )
    db_session.add(vehicle)

    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=vehicle.id,
        vehicle_no="JWK9488",
        customer_name="TEY SIOK BEE",
        coverage_start_date=datetime(2026, 9, 8, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 9, 7, tzinfo=timezone.utc),
        expiry_month="2027-09",
        status="sourced",
        road_tax=70.0,
        runner_fee=50.0,
    )
    db_session.add(tenure)
    db_session.commit()

    # 1. GET /api/comparison/{tenure_id}
    res = client.get(f"/api/comparison/{tenure.id}")
    assert res.status_code == 200
    data = res.json()
    assert data["tenure"]["vehicle_no"] == "JWK9488"
    assert data["tenure"]["fixed_costs_total"] == 120.0

    # 2. POST /api/comparison/{tenure_id}/entry (Add manual quote)
    entry_payload = {
        "company_name": "Etiqa Insurance",
        "sum_insured": 56000.0,
        "valuation_type": "market_value",
        "motor_premium": 1110.40,
        "towing_limit": "Unlimited",
        "agreed_value": False,
        "waiver_betterment": False,
        "excess": 0.0,
        "is_recommended": False,
        "is_manual": True,
    }
    res_entry = client.post(f"/api/comparison/{tenure.id}/entry", json=entry_payload)
    assert res_entry.status_code == 200
    data_entry = res_entry.json()
    assert len(data_entry["entries"]) == 1
    added_entry = data_entry["entries"][0]
    assert added_entry["company_name"] == "Etiqa Insurance"
    assert added_entry["total_payable"] == 1110.40 + 120.0  # 1230.40

    # 3. POST /api/comparison/{tenure_id}/fixed-costs
    res_fixed = client.post(
        f"/api/comparison/{tenure.id}/fixed-costs",
        json={"road_tax": 80.0, "runner_fee": 60.0},
    )
    assert res_fixed.status_code == 200
    data_fixed = res_fixed.json()
    assert data_fixed["tenure"]["fixed_costs_total"] == 140.0
    assert data_fixed["entries"][0]["total_payable"] == 1110.40 + 140.0

    # 4. GET /api/comparison/{tenure_id}/whatsapp-teaser
    res_teaser = client.get(f"/api/comparison/{tenure.id}/whatsapp-teaser")
    assert res_teaser.status_code == 200
    teaser_data = res_teaser.json()
    assert "JWK9488" in teaser_data["teaser_text"]
    assert "Etiqa Insurance" in teaser_data["teaser_text"]

    # 5. POST /api/comparison/{tenure_id}/winner (Select winner)
    res_winner = client.post(
        f"/api/comparison/{tenure.id}/winner",
        json={"entry_id": added_entry["id"]},
    )
    assert res_winner.status_code == 200
    winner_data = res_winner.json()
    assert winner_data["status"] == "success"
    assert winner_data["is_recommended"] is True
    assert winner_data["winning_company"] == "Etiqa Insurance"
    assert winner_data["draft_id"] is not None

    # 5b. POST /api/comparison/{tenure_id}/winner (Deselect/unclick winner)
    res_unpick = client.post(
        f"/api/comparison/{tenure.id}/winner",
        json={"entry_id": added_entry["id"]},
    )
    assert res_unpick.status_code == 200
    assert res_unpick.json()["is_recommended"] is False
    assert res_unpick.json()["selected_count"] == 0

    # 6. DELETE /api/comparison/{tenure_id}/entry/{entry_id}
    res_del = client.delete(f"/api/comparison/{tenure.id}/entry/{added_entry['id']}")
    assert res_del.status_code == 200
    assert len(res_del.json()["entries"]) == 0


def test_comparison_upload_quote_api(client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch):
    vehicle = TrackedVehicle(vehicle_no="WXY9999", car_model="Toyota Camry")
    db_session.add(vehicle)
    db_session.flush()

    tenure = InsuranceTenure(
        tracked_vehicle_id=vehicle.id,
        vehicle_no="WXY9999",
        customer_name="TEST CLIENT",
        coverage_start_date=datetime(2026, 9, 28, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 9, 27, tzinfo=timezone.utc),
        expiry_month="2027-09",
        status="draft",
        road_tax=200.0,
        runner_fee=10.0,
    )
    db_session.add(tenure)
    db_session.commit()

    # Upload quote to non-existent tenure returns 404
    res_404 = client.post(
        f"/api/comparison/{uuid4().hex}/upload-quote",
        files={"file": ("sample.pdf", b"%PDF-1.4 test bytes", "application/pdf")},
    )
    assert res_404.status_code == 404

    # Fake create_queued_upload that creates a real session in db_session
    async def fake_create(db, settings, **kwargs):
        sess = SessionModel(
            id=new_id(),
            owner_id=kwargs.get("owner_id", "user-1"),
            uploaded_file_id=new_id(),
            draft_id=new_id(),
            status="active",
            is_test=kwargs.get("is_test", False),
        )
        db.add(sess)
        db.commit()
        return SimpleNamespace(
            created=True,
            session=sess,
            job=SimpleNamespace(id="job-1"),
            uploaded_file=SimpleNamespace(id="file-1"),
            draft=SimpleNamespace(id="draft-1"),
        )

    from app.api.routers import comparison
    monkeypatch.setattr(comparison, "create_queued_upload", fake_create)

    # Upload quote with is_test=True
    res_test = client.post(
        f"/api/comparison/{tenure.id}/upload-quote",
        files={"file": ("sample.pdf", b"%PDF-1.4 test bytes", "application/pdf")},
        data={"is_test": "true"},
    )
    assert res_test.status_code == 200
    assert res_test.json()["status"] == "success"
    sess_id = res_test.json()["session_id"]
    sess = db_session.get(SessionModel, sess_id)
    assert sess is not None
    assert sess.is_test is True
    assert sess.tenure_id == tenure.id


