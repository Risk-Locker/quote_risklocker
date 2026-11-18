import time
import pytest
from app.extraction.pacer_sentinel import PacerSentinel


def test_strict_round_robin_mesh_equilibrium():
    """Verify that requests are distributed strictly evenly across all S = 2N slots using i % S."""
    # Scenario A: 2 accounts (4 slots) with 20 requests -> exactly 5 per slot
    sentinel_4 = PacerSentinel(slot_count=4)
    assigned_slots_4 = [sentinel_4.next_slot_index() for _ in range(20)]
    
    assert assigned_slots_4 == [0, 1, 2, 3] * 5
    for s_idx in range(4):
        assert assigned_slots_4.count(s_idx) == 5

    # Scenario B: 4 accounts (8 slots) with 24 requests -> exactly 3 per slot
    sentinel_8 = PacerSentinel(slot_count=8)
    assigned_slots_8 = [sentinel_8.next_slot_index() for _ in range(24)]
    
    assert assigned_slots_8 == list(range(8)) * 3
    for s_idx in range(8):
        assert assigned_slots_8.count(s_idx) == 3


def test_adaptive_living_eye_breathing_delay():
    """Verify dynamic delay adaptation based on queue depth and Google AI Studio latency."""
    sentinel = PacerSentinel(slot_count=4)

    # 1. Interactive mode (1-3 files): snappy 2.0s spacing
    assert sentinel.calculate_delay(staged_count=2, avg_latency_sec=1.2) == 2.0

    # 2. Batch / KFC mode (e.g. 50 staged files): relaxed 3.5s spacing
    assert sentinel.calculate_delay(staged_count=50, avg_latency_sec=1.5) == 3.5

    # 3. High latency congestion (> 4.0s from Google API): safety backoff to 6.0s
    assert sentinel.calculate_delay(staged_count=2, avg_latency_sec=4.5) == 6.0
    assert sentinel.calculate_delay(staged_count=50, avg_latency_sec=5.2) == 6.0


def test_rolling_safety_ceilings_enforced():
    """Verify that no slot can exceed 13 RPM or 200,000 TPM in a rolling 60s window."""
    sentinel = PacerSentinel(slot_count=4)
    now = 1000.0

    # Simulate 13 rapid requests on slot 0 (at safe limit)
    for _ in range(13):
        can_proceed, reason = sentinel.check_slot_limits(
            slot_idx=0,
            now=now,
            estimated_tokens=10_000,
        )
        assert can_proceed is True
        sentinel.record_dispatch(slot_idx=0, now=now, tokens=10_000)

    # 14th request in same minute must be blocked by RPM ceiling
    can_proceed, reason = sentinel.check_slot_limits(
        slot_idx=0,
        now=now + 5.0,
        estimated_tokens=10_000,
    )
    assert can_proceed is False
    assert reason is not None
    assert "RPM ceiling (13 req/min) reached" in reason

    # Slot 1: Test TPM ceiling (200k tokens)
    can_proceed, _ = sentinel.check_slot_limits(
        slot_idx=1,
        now=now,
        estimated_tokens=120_000,
    )
    assert can_proceed is True
    sentinel.record_dispatch(slot_idx=1, now=now, tokens=120_000)

    # Second request with 90k tokens would push rolling total to 210k > 200k TPM ceiling
    can_proceed, reason = sentinel.check_slot_limits(
        slot_idx=1,
        now=now + 5.0,
        estimated_tokens=90_000,
    )
    assert can_proceed is False
    assert reason is not None
    assert "TPM ceiling (200,000 tokens/min) reached" in reason


def test_acquire_pacing_and_slot_round_robin():
    """Verify sentinel acquire() round-robins slots, calculates delays, and records dispatches."""
    sentinel = PacerSentinel(slot_count=4)
    sleep_calls: list[float] = []
    fake_now = [1000.0]

    def mock_sleep(d: float):
        sleep_calls.append(d)
        fake_now[0] += d

    def mock_time():
        return fake_now[0]

    # Acquire 4 slots sequentially
    for expected_slot in range(4):
        slot_idx, delay = sentinel.acquire(
            estimated_tokens=15_000,
            staged_count=2,
            avg_latency_sec=1.5,
            sleep_fn=mock_sleep,
            time_fn=mock_time,
        )
        assert slot_idx == expected_slot
        assert delay == 2.0  # Interactive mode delay

    assert len(sleep_calls) == 4
    assert sleep_calls == [2.0, 2.0, 2.0, 2.0]


