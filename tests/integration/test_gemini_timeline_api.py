import pytest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from fastapi import FastAPI
from fastapi.testclient import TestClient
from types import SimpleNamespace
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routers.system import router as system_router
from app.api.deps import current_user
from app.db.session import get_db
from app.core.errors import register_error_handlers
from app.models.tables import Base, GeminiApiCallLog
from app.services.gemini_account_service import get_current_pt_cycle_date

from sqlalchemy.pool import StaticPool

@pytest.fixture
def test_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed a couple of call logs
    now = datetime.now(timezone.utc)
    cycle_date = get_current_pt_cycle_date()
    log1 = GeminiApiCallLog(
        account_id="env_0",
        api_key_masked="AIza...1234",
        model="gemini-3.1-flash-lite",
        endpoint_slot="slot_0",
        status_code=200,
        is_success=True,
        prompt_tokens=12000,
        candidate_tokens=1500,
        total_tokens=13500,
        latency_ms=1450,
        local_date=cycle_date,
        created_at=now,
    )
    session.add(log1)
    session.commit()

    test_app = FastAPI()
    register_error_handlers(test_app)
    test_app.include_router(system_router, prefix="/api")

    admin_user = SimpleNamespace(id="admin-1", role="admin")
    test_app.dependency_overrides[get_db] = lambda: session
    test_app.dependency_overrides[current_user] = lambda: admin_user

    client = TestClient(test_app)
    yield client
    session.close()

def test_gemini_timeline_endpoint_returns_cycle_and_logs(test_client):
    response = test_client.get("/api/settings/gemini/timeline")
    assert response.status_code == 200
    data = response.json()
    assert "current_cycle" in data
    assert "pt_date" in data["current_cycle"]
    assert "next_reset_myt" in data["current_cycle"]
    assert "seconds_until_reset" in data["current_cycle"]
    assert "timeline" in data
    assert len(data["timeline"]) >= 1
    assert "minute_buckets" in data
    assert "daily_history" in data
