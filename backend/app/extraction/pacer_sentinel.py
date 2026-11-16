"""Living Eye autonomous pacing sentinel and equilibrium dispatcher for Google AI Studio.

Enforces:
1. Strict S = 2N round-robin equilibrium (i % S) across all parallel model slots.
2. Adaptive breathing cadence based on queue depth (interactive 2.0s vs batch 3.5s)
   and Google API latency backoff (6.0s on congestion >4.0s).
3. Hard rolling safety ceilings per slot: <=13 RPM, <=200,000 TPM, <=480 RPD.
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from typing import Any

from app.services.gemini_account_service import get_current_pt_cycle_date

logger = logging.getLogger(__name__)

SAFE_RPM_CEILING: int = 13
SAFE_TPM_CEILING: int = 200_000
SAFE_RPD_CEILING: int = 480


class PacerSentinel:
    """Thread-safe sentinel pacing requests across multi-key, multi-model Google AI slots."""

    def __init__(self, slot_count: int = 4) -> None:
        self._lock = threading.RLock()
        self._slot_count = max(1, slot_count)
        self._ticket_seq: int = 0
        self._slot_request_times: dict[int, list[float]] = defaultdict(list)
        self._slot_token_times: dict[int, list[tuple[float, int]]] = defaultdict(list)
        self._slot_daily_counts: dict[int, int] = defaultdict(int)
        self._last_reset_date: str = get_current_pt_cycle_date()

    def _check_pt_cycle_reset(self) -> None:
        """Reset daily slot counts when Google AI Studio Pacific Time midnight cycle passes."""
        cycle = get_current_pt_cycle_date()
        if cycle != self._last_reset_date:
            self._last_reset_date = cycle
            self._slot_daily_counts.clear()

    def set_slot_count(self, count: int) -> None:
        with self._lock:
            self._slot_count = max(1, count)

    def next_slot_index(self) -> int:
        """Atomically fetch the next slot index in strict round-robin order."""
        with self._lock:
            idx = self._ticket_seq % self._slot_count
            self._ticket_seq += 1
            return idx

    def calculate_delay(
        self, staged_count: int = 1, avg_latency_sec: float = 1.5
    ) -> float:
        """Calculate dynamic breathing spacing between consecutive dispatch calls.

        - If Google AI Studio latency spikes > 4.0s, backs off to 6.0s to avoid 429 cascades.
        - If staging batch > 20 files (e.g. KFC lunch hour batch), relaxes to 3.5s spacing.
        - In snappy interactive mode (1-3 files), maintains responsive 2.0s cadence.
        """
        if avg_latency_sec > 4.0:
            return 6.0
        if staged_count > 20:
            return 3.5
        return 2.0

    def check_slot_limits(
        self,
        slot_idx: int,
        now: float,
        estimated_tokens: int = 12_000,
    ) -> tuple[bool, str | None]:
        """Check if target slot can safely accept request without violating RPM, TPM, or RPD."""
        with self._lock:
            self._check_pt_cycle_reset()
            # Clean expired timestamps older than 60 seconds
            self._slot_request_times[slot_idx] = [
                t for t in self._slot_request_times[slot_idx] if t >= now - 60.0
            ]
            self._slot_token_times[slot_idx] = [
                (t, tok)
                for t, tok in self._slot_token_times[slot_idx]
                if t >= now - 60.0
            ]

            # 1. RPM Check
            if len(self._slot_request_times[slot_idx]) >= SAFE_RPM_CEILING:
                return False, f"RPM ceiling ({SAFE_RPM_CEILING} req/min) reached"

            # 2. TPM Check
            current_tokens = sum(tok for _, tok in self._slot_token_times[slot_idx])
            if current_tokens + estimated_tokens > SAFE_TPM_CEILING:
                return False, f"TPM ceiling ({SAFE_TPM_CEILING:,} tokens/min) reached"

            # 3. RPD Check
            if self._slot_daily_counts[slot_idx] >= SAFE_RPD_CEILING:
                return False, f"RPD ceiling ({SAFE_RPD_CEILING} req/day) reached"

            return True, None

    def record_dispatch(
        self,
        slot_idx: int,
        now: float,
        tokens: int = 12_000,
    ) -> None:
        """Record dispatched request timestamp and token consumption against slot quotas."""
        with self._lock:
            self._check_pt_cycle_reset()
            self._slot_request_times[slot_idx].append(now)
            self._slot_token_times[slot_idx].append((now, tokens))
            self._slot_daily_counts[slot_idx] += 1

    def reset_daily_counters(self) -> None:
        with self._lock:
            self._slot_daily_counts.clear()

    def acquire(
        self,
        slot_idx: int | None = None,
        estimated_tokens: int = 12_000,
        staged_count: int = 1,
        avg_latency_sec: float = 1.5,
        max_wait_seconds: float = 60.0,
        sleep_fn: Any = None,
        time_fn: Any = None,
    ) -> tuple[int, float]:
        """Atomically acquire a slot and apply pacing delay according to Living Eye equilibrium.

        Returns (assigned_slot_idx, delay_applied_seconds).
        """
        import time as _time_module

        _time = time_fn or _time_module.time
        _sleep = sleep_fn or _time_module.sleep

        with self._lock:
            if slot_idx is None:
                target_slot = self.next_slot_index()
            else:
                target_slot = slot_idx % self._slot_count

        breathing_delay = self.calculate_delay(staged_count=staged_count, avg_latency_sec=avg_latency_sec)

        now = _time()
        can_proceed, reason = self.check_slot_limits(target_slot, now, estimated_tokens)

        delay_to_apply = breathing_delay
        if not can_proceed:
            with self._lock:
                req_times = self._slot_request_times.get(target_slot, [])
                if req_times:
                    oldest_req = min(req_times)
                    wait_needed = max(0.1, (oldest_req + 60.0) - now + 0.1)
                    delay_to_apply = max(breathing_delay, min(wait_needed, max_wait_seconds))

        if delay_to_apply > 0:
            _sleep(delay_to_apply)

        now_after = _time()
        self.record_dispatch(target_slot, now_after, tokens=estimated_tokens)
        return target_slot, delay_to_apply


_global_sentinel: PacerSentinel | None = None
_sentinel_lock = threading.RLock()


def get_pacer_sentinel(slot_count: int = 4) -> PacerSentinel:
    global _global_sentinel
    with _sentinel_lock:
        if _global_sentinel is None:
            _global_sentinel = PacerSentinel(slot_count=slot_count)
        else:
            _global_sentinel.set_slot_count(slot_count)
        return _global_sentinel

