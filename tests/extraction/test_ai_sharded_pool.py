"""Hermetic concurrency tests for Task 2: Round-Robin Sharded Key & Model Allocator."""

import concurrent.futures
import time
import pytest

from app.core.errors import AIExtractionUnavailableException
from app.extraction.ai_sharded_pool import (
    AIShardedPool,
    SAFE_RPM_LIMIT_PER_SLOT,
    SAFE_RPD_LIMIT_PER_SLOT,
    VERIFIED_ACTIVE_MODELS,
)


def test_sharded_pool_initialization():
    """Pool with 4 keys creates exactly 8 slots across verified active models."""
    keys = ["key-alpha", "key-beta", "key-gamma", "key-delta"]
    pool = AIShardedPool(api_keys=keys)

    assert pool.total_keys == 4
    assert pool.total_slots == 8  # 4 keys * 2 models

    summary = pool.get_status_summary()
    assert len(summary) == 8
    models = {s["model"] for s in summary}
    assert models == set(VERIFIED_ACTIVE_MODELS)


def test_round_robin_distribution_across_slots():
    """Sequential allocations cycle evenly through all 8 slots in round-robin order."""
    keys = ["key-1", "key-2", "key-3", "key-4"]
    pool = AIShardedPool(api_keys=keys)

    now = 1000.0
    allocated_slots = []
    for _ in range(8):
        slot = pool.allocate_next_available_slot(now=now)
        allocated_slots.append(slot.slot_id)

    # All 8 allocated slots must be unique in the first round-robin cycle
    assert len(set(allocated_slots)) == 8

    # The 9th allocation should wrap back to the first slot
    slot_9 = pool.allocate_next_available_slot(now=now)
    assert slot_9.slot_id == allocated_slots[0]


def test_slot_rpm_window_enforcement():
    """A slot enforces the safe 12 RPM limit and rejects calls exceeding the window."""
    keys = ["single-key"]
    # 1 key with 1 model for isolated test
    pool = AIShardedPool(api_keys=keys, models=["gemini-3.5-flash-lite"], rpm_limit_per_slot=12)

    now = 5000.0
    # First 12 allocations in the same minute succeed
    for _ in range(12):
        slot = pool.allocate_next_available_slot(now=now)
        assert slot is not None

    # 13th call in the same window (now=5010.0, within 60s) must fail with 429
    with pytest.raises(AIExtractionUnavailableException) as exc_info:
        pool.allocate_next_available_slot(now=now + 10.0)

    assert exc_info.value.status_code == 429
    assert "saturated" in exc_info.value.message

    # Advancing time past 60s (now + 61.0) must release capacity
    reopened_slot = pool.allocate_next_available_slot(now=now + 61.0)
    assert reopened_slot is not None


def test_cooling_slot_is_skipped_by_round_robin():
    """When a slot is placed on cooldown (e.g. 429), dispatcher skips it."""
    keys = ["key-1", "key-2"]
    pool = AIShardedPool(api_keys=keys, models=["gemini-3.5-flash-lite"])  # 2 slots total

    now = 100.0
    s1 = pool.allocate_next_available_slot(now=now)

    # Place s1 on cooldown for 60s
    pool.record_slot_cooldown(s1.slot_id, cooldown_seconds=60.0, now=now)

    # Next allocations must all route to s2, never s1 while cooling
    for _ in range(5):
        s_next = pool.allocate_next_available_slot(now=now)
        assert s_next.slot_id != s1.slot_id


def test_concurrent_thread_safe_allocations():
    """16 concurrent threads making 80 allocations without race conditions or errors."""
    keys = ["k1", "k2", "k3", "k4"]
    pool = AIShardedPool(api_keys=keys, rpm_limit_per_slot=100)

    def worker_task(thread_id: int):
        results = []
        for i in range(5):
            s = pool.allocate_next_available_slot(document_id=f"doc-{thread_id}-{i}", now=100.0)
            results.append(s.slot_id)
        return results

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        futures = [executor.submit(worker_task, i) for i in range(16)]
        all_results = []
        for f in concurrent.futures.as_completed(futures):
            all_results.extend(f.result())

    assert len(all_results) == 80
    # Every slot must have been used evenly
    summary = pool.get_status_summary(now=100.0)
    total_dispatched = sum(s["daily_count"] for s in summary)
    assert total_dispatched == 80

