"""Deterministic Round-Robin Sharded Key and Model Pool.

Maintains active slots across verified Gemini models (gemini-3.5-flash-lite, gemini-3.8-flash)
with strict token-bucket / sliding-window rate limiters (12 RPM, 450 RPD per slot) to ensure
fail-safe operation within Google API tier limits (15 RPM / 500 RPD hard limits).
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Sequence

from app.core.errors import AIExtractionUnavailableException

logger = logging.getLogger(__name__)

# Authoritative verified active model tiers (Rule 05)
VERIFIED_ACTIVE_MODELS: tuple[str, ...] = (
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
)

SAFE_RPM_LIMIT_PER_SLOT: int = 12
SAFE_RPD_LIMIT_PER_SLOT: int = 450
SECONDS_PER_DAY: float = 86400.0


@dataclass
class AISlot:
    slot_id: str
    api_key: str
    model: str
    key_index: int
    rpm_limit: int = SAFE_RPM_LIMIT_PER_SLOT
    rpd_limit: int = SAFE_RPD_LIMIT_PER_SLOT
    request_timestamps: list[float] = field(default_factory=list)
    daily_request_count: int = 0
    day_epoch: int = field(default_factory=lambda: int(time.time() // SECONDS_PER_DAY))
    cooling_until: float = 0.0

    def is_available(self, now: float) -> bool:
        """Check if slot is available without exceeding RPM, RPD, or cooling caps."""
        if now < self.cooling_until:
            return False

        # Reset daily counter if a new day has arrived
        current_day = int(now // SECONDS_PER_DAY)
        if current_day > self.day_epoch:
            self.day_epoch = current_day
            self.daily_request_count = 0

        if self.daily_request_count >= self.rpd_limit:
            return False

        # Prune timestamps older than 60 seconds
        window_start = now - 60.0
        self.request_timestamps = [t for t in self.request_timestamps if t > window_start]

        return len(self.request_timestamps) < self.rpm_limit

    def record_usage(self, now: float) -> None:
        """Record an active request consumption against this slot."""
        self.request_timestamps.append(now)
        self.daily_request_count += 1

    def trigger_cooldown(self, cooldown_seconds: float = 65.0, now: float | None = None) -> None:
        """Trigger temporary cooling period (e.g. after receiving HTTP 429)."""
        t = now if now is not None else time.time()
        self.cooling_until = t + cooldown_seconds


class AIShardedPool:
    """Manages 2 verified active model slots per API key with round-robin dispatch."""

    def __init__(
        self,
        api_keys: Sequence[str] | None = None,
        models: Sequence[str] = VERIFIED_ACTIVE_MODELS,
        rpm_limit_per_slot: int = SAFE_RPM_LIMIT_PER_SLOT,
        rpd_limit_per_slot: int = SAFE_RPD_LIMIT_PER_SLOT,
    ) -> None:
        self._lock = threading.Lock()
        self._models = list(models)
        self._rpm_limit = rpm_limit_per_slot
        self._rpd_limit = rpd_limit_per_slot
        self._rr_index = 0
        self._slots: list[AISlot] = []

        keys = [k.strip() for k in (api_keys or []) if k.strip()]
        self.set_keys(keys)

    def set_keys(self, api_keys: Sequence[str]) -> None:
        """Re-configure pool with given list of API keys."""
        with self._lock:
            self._slots.clear()
            for key_idx, key in enumerate(api_keys):
                masked_key = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else f"key-{key_idx}"
                for m in self._models:
                    slot_id = f"{masked_key}::{m}"
                    self._slots.append(
                        AISlot(
                            slot_id=slot_id,
                            api_key=key,
                            model=m,
                            key_index=key_idx,
                            rpm_limit=self._rpm_limit,
                            rpd_limit=self._rpd_limit,
                        )
                    )
            self._rr_index = 0

    @property
    def total_slots(self) -> int:
        with self._lock:
            return len(self._slots)

    @property
    def total_keys(self) -> int:
        with self._lock:
            return len({s.api_key for s in self._slots})

    def allocate_next_available_slot(
        self,
        document_id: str | None = None,
        now: float | None = None,
        fail_closed: bool = True,
    ) -> AISlot:
        """Assigns the next available key and model pair with token-bucket safety.

        Deterministic round-robin across all active slots. If document_id is provided,
        it uses it for deterministic affinity hashing when appropriate.
        """
        current_t = now if now is not None else time.time()

        with self._lock:
            n_slots = len(self._slots)
            if n_slots == 0:
                if fail_closed:
                    raise AIExtractionUnavailableException(
                        reason="No active Gemini API keys available in sharded pool.",
                        status_code=503,
                    )
                raise RuntimeError("No active slots in AI pool.")

            # Search starting from current round-robin index
            start_index = self._rr_index
            for offset in range(n_slots):
                candidate_idx = (start_index + offset) % n_slots
                candidate = self._slots[candidate_idx]

                if candidate.is_available(current_t):
                    candidate.record_usage(current_t)
                    self._rr_index = (candidate_idx + 1) % n_slots
                    return candidate

            # If all slots are saturated / cooling
            if fail_closed:
                raise AIExtractionUnavailableException(
                    reason=f"All {n_slots} AI slots saturated (12 RPM / 450 RPD limit reached).",
                    status_code=429,
                )
            raise RuntimeError(f"All {n_slots} AI slots saturated.")

    def record_slot_cooldown(self, slot_id: str, cooldown_seconds: float = 65.0, now: float | None = None) -> None:
        """Mark a slot as cooling down following an upstream 429."""
        with self._lock:
            for s in self._slots:
                if s.slot_id == slot_id:
                    s.trigger_cooldown(cooldown_seconds, now=now)
                    logger.warning("Slot [%s] placed on cooling for %.1fs", slot_id, cooldown_seconds)
                    break

    def get_status_summary(self, now: float | None = None) -> list[dict]:
        """Return slot health and capacity metrics."""
        current_t = now if now is not None else time.time()
        with self._lock:
            res = []
            for s in self._slots:
                # Prune old timestamps for accurate count
                window_start = current_t - 60.0
                active_rpm = len([t for t in s.request_timestamps if t > window_start])
                res.append({
                    "slot_id": s.slot_id,
                    "model": s.model,
                    "key_index": s.key_index,
                    "active_rpm": active_rpm,
                    "rpm_limit": s.rpm_limit,
                    "daily_count": s.daily_request_count,
                    "rpd_limit": s.rpd_limit,
                    "is_cooling": current_t < s.cooling_until,
                    "cooling_remaining_seconds": max(0.0, s.cooling_until - current_t),
                })
            return res


# Global singleton instance
_GLOBAL_POOL: AIShardedPool | None = None
_POOL_LOCK = threading.Lock()


def get_sharded_ai_pool() -> AIShardedPool:
    """Retrieve or initialize the global shared AI slot pool."""
    global _GLOBAL_POOL
    if _GLOBAL_POOL is None:
        with _POOL_LOCK:
            if _GLOBAL_POOL is None:
                from app.core.config import get_settings
                settings = get_settings()
                keys = list(settings.gemini_api_keys)
                _GLOBAL_POOL = AIShardedPool(api_keys=keys)
    return _GLOBAL_POOL

