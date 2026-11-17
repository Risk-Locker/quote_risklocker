import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.models.tables import Base, GeminiApiCallLog, new_id
from app.services.gemini_account_service import (
    get_historical_analytics,
    GeminiAccountManager,
    get_current_pt_cycle_date,
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


def test_historical_analytics_grouping_and_metrics(db_session: Session):
    """Verify get_historical_analytics groups by (account_id, model) and aggregates peak RPM/TPM matching Google AI Studio."""
    now = datetime.now(timezone.utc).replace(second=30, microsecond=0)
    local_date = get_current_pt_cycle_date()

    # Insert 3 calls for (acc_1, gemini-3.1-flash-lite) within 10 seconds of each other
    for i in range(3):
        db_session.add(
            GeminiApiCallLog(
                id=new_id(),
                account_id="acc_1",
                api_key_masked="AIzaSy...1111",
                model="gemini-3.1-flash-lite",
                status_code=200,
                is_success=True,
                prompt_tokens=10_000,
                candidate_tokens=1_000,
                total_tokens=11_000,
                latency_ms=1200,
                local_date=local_date,
                created_at=now - timedelta(seconds=i * 2),
            )
        )

    # Insert 2 calls for (acc_1, gemini-3.5-flash-lite)
    for i in range(2):
        db_session.add(
            GeminiApiCallLog(
                id=new_id(),
                account_id="acc_1",
                api_key_masked="AIzaSy...1111",
                model="gemini-3.5-flash-lite",
                status_code=200,
                is_success=True,
                prompt_tokens=15_000,
                candidate_tokens=2_000,
                total_tokens=17_000,
                latency_ms=1500,
                local_date=local_date,
                created_at=now - timedelta(seconds=i * 3),
            )
        )

    # Insert 1 call for (acc_2, gemini-3.1-flash-lite)
    db_session.add(
        GeminiApiCallLog(
            id=new_id(),
            account_id="acc_2",
            api_key_masked="AIzaSy...2222",
            model="gemini-3.1-flash-lite",
            status_code=200,
            is_success=True,
            prompt_tokens=8_000,
            candidate_tokens=500,
            total_tokens=8_500,
            latency_ms=900,
            local_date=local_date,
            created_at=now,
        )
    )
    db_session.commit()

    analytics = get_historical_analytics(db_session, time_range="today")

    assert analytics["time_range"] == "today"
    assert analytics["summary"]["total_calls"] == 6
    assert analytics["summary"]["total_tokens"] == (3 * 11_000) + (2 * 17_000) + 8_500

    # Table rows must mirror Google AI Studio Rate Limit page:
    # Model, Category, RPM (Peak / Limit), TPM (Peak / Limit), RPD (Used / Limit)
    rows = analytics["table"]
    assert len(rows) >= 3

    acc1_lite31 = next(r for r in rows if r["account_id"] == "acc_1" and r["model"] == "gemini-3.1-flash-lite")
    assert acc1_lite31["call_count"] == 3
    assert acc1_lite31["total_tokens"] == 33_000
    assert acc1_lite31["peak_rpm"] >= 3
    assert acc1_lite31["peak_tpm"] >= 33_000
    assert acc1_lite31["rpm_limit"] == 13
    assert acc1_lite31["tpm_limit"] == 200_000
    assert acc1_lite31["rpd_limit"] == 480


def test_historical_analytics_time_ranges(db_session: Session):
    """Verify analytics supports today, last-1-day, last-7-days, and last-28-days filtering."""
    now = datetime.now(timezone.utc)

    # Old log from 10 days ago
    db_session.add(
        GeminiApiCallLog(
            id=new_id(),
            account_id="acc_1",
            model="gemini-3.1-flash-lite",
            status_code=200,
            is_success=True,
            total_tokens=5_000,
            local_date=(now - timedelta(days=10)).strftime("%Y-%m-%d"),
            created_at=now - timedelta(days=10),
        )
    )
    # Recent log from 2 hours ago
    db_session.add(
        GeminiApiCallLog(
            id=new_id(),
            account_id="acc_1",
            model="gemini-3.1-flash-lite",
            status_code=200,
            is_success=True,
            total_tokens=5_000,
            local_date=get_current_pt_cycle_date(),
            created_at=now - timedelta(hours=2),
        )
    )
    db_session.commit()

    res_today = get_historical_analytics(db_session, time_range="today")
    assert res_today["summary"]["total_calls"] == 1

    res_7d = get_historical_analytics(db_session, time_range="last-7-days")
    assert res_7d["summary"]["total_calls"] == 1

    res_28d = get_historical_analytics(db_session, time_range="last-28-days")
    assert res_28d["summary"]["total_calls"] == 2


def test_pause_toggle_stops_account_without_credential_deletion():
    """Verify non-destructive Pause / Rest toggle deactivates an account safely."""
    manager = GeminiAccountManager(keys=("AIzaSyKeyA1234567890", "AIzaSyKeyB1234567890"))
    assert len(manager.get_accounts()) == 2

    # Pause first account
    acc0_id = manager.get_accounts()[0].id
    success = manager.set_account_paused(acc0_id, paused=True)
    assert success is True
    assert manager.get_accounts()[0].is_paused is True

    # Acquiring slot must strictly yield account 1 (since account 0 is resting)
    for _ in range(4):
        slot = manager.acquire_parallel_slot()
        assert slot is not None
        key, model, slot_id = slot
        assert key == "AIzaSyKeyB1234567890"

    # Unpause account 0
    manager.set_account_paused(acc0_id, paused=False)
    assert manager.get_accounts()[0].is_paused is False

