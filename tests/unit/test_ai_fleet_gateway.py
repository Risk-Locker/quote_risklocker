"""Hermetic unit tests for GeminiFleetGateway, cooldown modes, PT reset, and Proof-First escalation."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import time
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.extraction import multi_zoom_pipeline
from app.models.tables import AIFleetEvent, AIFleetLane, Base
from app.services import ai_fleet_gateway as gw_mod
from app.services.ai_fleet_gateway import (
    GeminiFleetGateway,
    QuotaExhaustedError,
    compute_next_pt_midnight_utc,
)
from app.services.gemini_account_service import GeminiAccount


@pytest.fixture()
def sqlite_session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _mock_pool_accounts(monkeypatch, accounts: list[GeminiAccount]):
    fake_pool = SimpleNamespace(
        _parallel_models=("gemini-3.1-flash-lite", "gemini-3.5-flash-lite"),
        sync_accounts=lambda db=None: None,
        get_accounts=lambda: list(accounts),
        get_all_keys=lambda: [a.key for a in accounts if not a.is_paused and a.status not in ("denied", "invalid_key")],
        record_success=lambda **kwargs: None,
        record_failure=lambda *args, **kwargs: None,
        get_last_error_message=lambda: None,
    )
    monkeypatch.setattr(gw_mod, "get_key_pool", lambda: fake_pool)
    return fake_pool


def test_atomic_inflight_and_strict_same_key_spacing(monkeypatch):
    acc = GeminiAccount(id="env_0", key="AIzaKeyOne1234567890", label="Key 1", status="ready")
    _mock_pool_accounts(monkeypatch, [acc])
    gateway = GeminiFleetGateway(force_memory=True)

    res1, wait1, daily1 = gateway.reserve_lane(filename="quote1.pdf", purpose="extraction")
    assert res1 is not None
    assert wait1 == 0.0
    assert daily1 is False
    assert gateway._mem_lanes[res1.lane_id].in_flight_count == 1

    # Immediate second request on sibling model sharing the same API key MUST wait >= 1.8s (never cheat!)
    res2, wait2, daily2 = gateway.reserve_lane(filename="quote2.pdf", purpose="extraction")
    assert res2 is None
    assert daily2 is False
    assert wait2 > 1.0


def test_four_mode_cooldowns_and_daily_exhaustion(monkeypatch):
    acc1 = GeminiAccount(id="env_0", key="AIzaKeyOne1234567890", label="Key 1", status="ready")
    acc2 = GeminiAccount(id="env_1", key="AIzaKeyTwo1234567890", label="Key 2", status="ready")
    _mock_pool_accounts(monkeypatch, [acc1, acc2])
    gateway = GeminiFleetGateway(force_memory=True)

    # 1. 429 cooldown: 65s on failing lane + 6s global pause across fleet
    r1, _, _ = gateway.reserve_lane(requested_model="gemini-3.1-flash-lite")
    assert r1 is not None
    gateway.release_lane(r1, status_code=429, error_message="Rate limit per minute exceeded")
    lane1 = gateway._mem_lanes[r1.lane_id]
    assert lane1.status == "cooling_429"
    assert lane1.cooling_until is not None and lane1.cooling_until > time.time() + 50.0
    assert lane1.global_pause_until is not None and lane1.global_pause_until > time.time() + 3.0

    # 2. 5xx error cooldown: 15s on failing lane only
    gateway._mem_lanes[r1.lane_id].cooling_until = None
    gateway._mem_lanes[r1.lane_id].status = "ready"
    for l in gateway._mem_lanes.values():
        l.global_pause_until = None
        l.last_dispatched_at = 0.0
    r2, _, _ = gateway.reserve_lane(requested_model="gemini-3.5-flash-lite")
    assert r2 is not None
    gateway.release_lane(r2, status_code=503, error_message="Upstream unavailable")
    assert gateway._mem_lanes[r2.lane_id].status == "cooling_err"
    assert gateway._mem_lanes[r2.lane_id].cooling_until is not None

    # 3. 401/403 auth quarantine: 3600s across ALL sibling model lanes sharing the same account_id
    for l in gateway._mem_lanes.values():
        l.global_pause_until = None
        l.cooling_until = None
        l.status = "ready"
        l.last_dispatched_at = 0.0
    r3, _, _ = gateway.reserve_lane(requested_model="gemini-3.1-flash-lite")
    assert r3 is not None
    gateway.release_lane(r3, status_code=403, error_message="PERMISSION_DENIED")
    for l in gateway._mem_lanes.values():
        if l.account_id == r3.account_id:
            assert l.status == "quarantined_auth"
            assert l.cooling_until is not None and l.cooling_until > time.time() + 3000.0

    # 4. Daily RPD exhaustion across remaining active lanes raises QuotaExhaustedError(is_daily_exhausted=True)
    for l in gateway._mem_lanes.values():
        if l.account_id != r3.account_id:
            l.rpd_used = l.rpd_limit
    with pytest.raises(QuotaExhaustedError) as exc_info:
        gateway.execute_gemini_request(
            payload={"contents": [{"role": "user", "parts": [{"text": "hello"}]}]},
            allow_quota_raise=True,
        )
    assert exc_info.value.is_daily_exhausted is True
    assert exc_info.value.wait_seconds == float("inf")
    assert exc_info.value.resume_at_utc is not None


def test_stale_inflight_recovery_and_pt_midnight(monkeypatch):
    acc = GeminiAccount(id="env_0", key="AIzaKeyOne1234567890", label="Key 1", status="ready")
    _mock_pool_accounts(monkeypatch, [acc])
    gateway = GeminiFleetGateway(force_memory=True)

    r1, _, _ = gateway.reserve_lane(filename="stuck.pdf")
    assert r1 is not None
    # Age the in_flight entry past STALE_IN_FLIGHT_SECONDS and clear dispatch spacing
    lane = gateway._mem_lanes[r1.lane_id]
    lane.in_flight_meta[r1.reservation_id]["ts"] = time.time() - 200.0
    lane.last_dispatched_at = time.time() - 10.0

    r2, wait2, daily2 = gateway.reserve_lane(filename="fresh.pdf")
    assert r2 is not None
    assert wait2 == 0.0
    assert daily2 is False

    # Verify PT midnight computation (00:00:10 America/Los_Angeles -> 08:00:10 UTC in Nov PST)
    sample_utc = datetime(2026, 11, 25, 15, 0, 0, tzinfo=timezone.utc)
    next_pt = compute_next_pt_midnight_utc(sample_utc)
    assert next_pt == datetime(2026, 11, 26, 8, 0, 10, tzinfo=timezone.utc)


def test_db_backed_lanes_events_and_readonly_telemetry(monkeypatch, sqlite_session_factory):
    acc = GeminiAccount(id="env_0", key="AIzaKeyOne1234567890", label="Key 1", status="ready")
    _mock_pool_accounts(monkeypatch, [acc])
    gateway = GeminiFleetGateway(session_factory=sqlite_session_factory)

    res, wait_s, daily = gateway.reserve_lane(filename="db_quote.pdf", purpose="extraction")
    assert res is not None
    assert wait_s == 0.0
    assert daily is False

    gateway.commit_lane(res, prompt_tokens=100, candidate_tokens=50, total_tokens=150, latency_ms=420, filename="db_quote.pdf")

    with sqlite_session_factory() as db:
        lanes = db.query(AIFleetLane).all()
        events = db.query(AIFleetEvent).all()
        assert len(lanes) == 2
        assert any(l.rpd_used == 1 for l in lanes)
        assert len(events) >= 2

        # Telemetry getter must remain strictly read-only
        writes = []
        orig_commit = db.commit
        db.commit = lambda: writes.append("commit") or orig_commit()
        telemetry = gateway.get_fleet_telemetry(db, limit=50)
        assert writes == []
        assert telemetry["total_lanes_count"] == 2
        assert len(telemetry["events"]) >= 2


def test_proof_first_bulk_mode_skips_second_call_when_math_passes_and_escalates_on_mismatch(monkeypatch):
    import fitz

    doc = fitz.open()
    p = doc.new_page()
    p.insert_text((20, 20), "Etiqa Private Car Comprehensive ABC1234 Basic 1000.00 NCD 0.00 Gross 1000.00 SST 80.00 Stamp 10.00 Total 1090.00")
    pdf_bytes = doc.tobytes()
    doc.close()

    monkeypatch.setattr(multi_zoom_pipeline, "_has_multi_slot_consensus_fleet", lambda _pool: True)
    monkeypatch.setattr(multi_zoom_pipeline, "render_header_footer_crops", lambda *a, **kw: [])
    monkeypatch.setattr(multi_zoom_pipeline, "render_schedule_and_pricing_crops", lambda *a, **kw: [])
    monkeypatch.setattr(multi_zoom_pipeline, "_should_verify_brand_visually", lambda *a, **kw: False)

    fake_pool = SimpleNamespace(
        get_all_keys=lambda: ["key-1"],
        get_last_error_message=lambda: None,
    )
    monkeypatch.setattr(multi_zoom_pipeline.gemini_extractor, "get_key_pool", lambda: fake_pool)

    # Case 1: Clean accounting identity -> 1 Vision pass total in Proof-First bulk mode
    calls_clean: list[str] = []

    def fake_extract_clean(*args, **kwargs):
        calls_clean.append(kwargs.get("extra_prompt_guidance") or "pass1")
        return {
            "insurance_company": "Etiqa",
            "customer_name": "ALI BIN ABU",
            "vehicle_no": "ABC1234",
            "car_model": "Myvi",
            "vehicle_year": "2022",
            "engine_cc": "1500",
            "vehicle_type": "Car",
            "cover_start_date": "2026-01-01",
            "cover_end_date": "2026-12-31",
            "valuation_type": "Market Value",
            "coverage_amount": "50000.00",
            "basic_premium": "1000.00",
            "ncd_percent": "0.00",
            "ncd_amount": "0.00",
            "gross_premium": "1000.00",
            "service_tax": "80.00",
            "stamp_duty": "10.00",
            "excess_amount": "0.00",
            "premium": "1090.00",
            "total_amount": "1090.00",
            "detected_package_name": "Comprehensive",
            "detected_benefits": [],
        }

    monkeypatch.setattr(multi_zoom_pipeline.gemini_extractor, "extract_with_gemini_sync", fake_extract_clean)
    res_clean = multi_zoom_pipeline.run_multi_zoom_vision_pipeline(
        pdf_bytes=pdf_bytes,
        source_filename="Etiqa_ABC1234.pdf",
        enable_dual_model_consensus=False,
    )
    assert len(calls_clean) == 1
    assert res_clean.passes_used == 2
    assert res_clean.accounting_verdict is not None
    assert res_clean.accounting_verdict.passed is True
    assert Decimal(res_clean.gemini_res["total_amount"]) == Decimal("1090.00")

    # Case 2: Math discrepancy in Pass 1 -> automatic Referee escalation (2 calls)
    calls_bad: list[str] = []

    def fake_extract_bad(*args, **kwargs):
        calls_bad.append(kwargs.get("extra_prompt_guidance") or "pass1")
        if len(calls_bad) == 1:
            return {
                "insurance_company": "Etiqa",
                "vehicle_no": "ABC1234",
                "coverage_amount": "50000.00",
                "basic_premium": "1000.00",
                "ncd_percent": "0",
                "ncd_amount": "0.00",
                "gross_premium": "1000.00",
                "service_tax": "80.00",
                "stamp_duty": "10.00",
                "premium": "999.00",
                "total_amount": "999.00",
                "detected_benefits": [],
            }
        return {
            "insurance_company": "Etiqa",
            "vehicle_no": "ABC1234",
            "coverage_amount": "50000.00",
            "basic_premium": "1000.00",
            "ncd_percent": "0",
            "ncd_amount": "0.00",
            "gross_premium": "1000.00",
            "service_tax": "80.00",
            "stamp_duty": "10.00",
            "premium": "1090.00",
            "total_amount": "1090.00",
            "detected_benefits": [],
        }

    monkeypatch.setattr(multi_zoom_pipeline.gemini_extractor, "extract_with_gemini_sync", fake_extract_bad)
    res_bad = multi_zoom_pipeline.run_multi_zoom_vision_pipeline(
        pdf_bytes=pdf_bytes,
        source_filename="Etiqa_ABC1234.pdf",
        enable_dual_model_consensus=False,
    )
    assert len(calls_bad) == 2
    assert "REFEREE PASS" in calls_bad[1]
    assert Decimal(res_bad.gemini_res["total_amount"]) == Decimal("1090.00")
