"""Integration tests for dynamic eligible models and radar sentinel API endpoints."""

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

from app.api.routers.system import router as system_router
from app.api.deps import current_user
from app.core.errors import register_error_handlers
from app.db.session import get_db
from app.models.tables import Base, Role, User, new_id


@pytest.fixture
def api_test_env():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    session = TestingSessionLocal()

    admin_user = User(
        id=new_id(),
        email="superadmin@risklocker.local",
        name="Super Admin",
        password_hash="mock",
        role=Role.SUPER_ADMIN.value,
    )
    session.add(admin_user)
    session.commit()

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(system_router)

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[current_user] = lambda: admin_user

    client = TestClient(app)
    try:
        yield client, session, admin_user
    finally:
        session.close()


def test_get_eligible_models_endpoint(api_test_env):
    client, session, _ = api_test_env

    resp = client.get("/settings/gemini/eligible-models")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "eligible_models" in data
    assert "banned_models" in data

    eligible_ids = [m["id"] for m in data["eligible_models"]]
    assert "gemini-3.1-flash-lite" in eligible_ids
    assert "gemini-3.5-flash-lite" in eligible_ids

    banned_ids = [m["id"] for m in data["banned_models"]]
    assert "gemini-3.8-flash" in banned_ids


def test_update_model_config_rejects_banned_model(api_test_env):
    client, session, _ = api_test_env

    # 1. Attempting to set banned gemini-3.8-flash should fail with 400
    resp = client.post(
        "/settings/gemini/model-config",
        json={"primary_model": "gemini-3.8-flash"},
    )
    assert resp.status_code == 400
    assert "not in verified production tier" in resp.text

    # 2. Setting valid production model succeeds
    resp = client.post(
        "/settings/gemini/model-config",
        json={
            "primary_model": "gemini-3.5-flash-lite",
            "parallel_models": ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["primary_model"] == "gemini-3.5-flash-lite"


def test_trigger_radar_sentinel_endpoint(api_test_env):
    client, session, _ = api_test_env

    resp = client.post("/settings/gemini/radar-sentinel/trigger?force=true")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["sentinel"]["ran"] is True
