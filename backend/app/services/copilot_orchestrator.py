"""Work-Conserving Multi-User Fair-Queue & Anti-Starvation Copilot Orchestrator."""

from __future__ import annotations

import collections
from contextlib import contextmanager
from dataclasses import dataclass, field
import threading
import time
from typing import Any, Callable, Iterator
import uuid


@dataclass
class _QueuedTurn:
    ticket_id: str
    user_id: str
    estimated_tokens: int
    enqueued_at: float = field(default_factory=time.monotonic)


class CopilotFairQueueOrchestrator:
    """Interleaves concurrent Copilot turns across active users without idle-user throttling.

    Properties:
    1. Work-conserving: If only 1 user is actively sending messages (even if 7 users are
       logged in), that user receives 100% of the 26 RPM / 440k TPM dual-barrel capacity.
    2. Fair-share under contention: When multiple users send turns concurrently while
       barrels are busy/reloading, turns dispatch in elevator round-robin across active users.
    3. Big-prompt anti-starvation: When a head-of-line user has a heavy prompt waiting
       for barrel reload (>80k tok or >2s wait), small prompts cannot starve it indefinitely.
    """

    def __init__(self, *, max_concurrent_turns: int = 2) -> None:
        self._cond = threading.Condition()
        self._max_concurrent_turns = max(1, int(max_concurrent_turns))
        self._user_queues: dict[str, collections.deque[_QueuedTurn]] = collections.defaultdict(collections.deque)
        self._active_users: collections.deque[str] = collections.deque()
        self._inflight_tickets: dict[str, str] = {}  # ticket_id -> user_id
        self._reserved_heavy_user: str | None = None

    def _next_ready_user_locked(self) -> str | None:
        while self._active_users:
            uid = self._active_users[0]
            q = self._user_queues.get(uid)
            if not q:
                self._active_users.popleft()
                self._user_queues.pop(uid, None)
                continue
            return uid
        return None

    def _queue_position_locked(self, user_id: str, ticket_id: str) -> tuple[int, int]:
        """Return (1-indexed position, active_users_count) in simulated elevator order."""
        q = self._user_queues.get(user_id)
        if not q:
            return 1, len(self._active_users)
        target_idx = -1
        for idx, item in enumerate(q):
            if item.ticket_id == ticket_id:
                target_idx = idx
                break
        if target_idx < 0:
            return 1, len(self._active_users)

        temp_users = collections.deque(self._active_users)
        temp_counts = {u: len(self._user_queues[u]) for u in self._user_queues}
        pos = 0
        while temp_users:
            u = temp_users.popleft()
            if temp_counts.get(u, 0) <= 0:
                continue
            pos += 1
            temp_counts[u] -= 1
            consumed = len(self._user_queues[u]) - temp_counts[u]
            if u == user_id and consumed == (target_idx + 1):
                return pos, len(self._active_users)
            if temp_counts[u] > 0:
                temp_users.append(u)
        return max(1, pos), len(self._active_users)

    def _remove_ticket_locked(self, user_id: str, ticket_id: str) -> None:
        q = self._user_queues.get(user_id)
        if q:
            filtered = collections.deque(item for item in q if item.ticket_id != ticket_id)
            if filtered:
                self._user_queues[user_id] = filtered
            else:
                self._user_queues.pop(user_id, None)
                try:
                    self._active_users.remove(user_id)
                except ValueError:
                    pass
        if self._reserved_heavy_user == user_id and user_id not in self._user_queues:
            self._reserved_heavy_user = None

    def get_queue_snapshot(self) -> dict[str, Any]:
        with self._cond:
            waiting = sum(len(q) for q in self._user_queues.values())
            return {
                "active_users": len(self._active_users),
                "waiting_turns": waiting,
                "inflight_turns": len(self._inflight_tickets),
                "max_concurrent_turns": self._max_concurrent_turns,
            }

    @contextmanager
    def acquire_turn_slot(
        self,
        *,
        user_id: str,
        estimated_tokens: int,
        cancel_event: threading.Event | None = None,
        on_status: Callable[[dict[str, Any]], None] | None = None,
        max_wait_seconds: float = 95.0,
    ) -> Iterator[dict[str, Any]]:
        """Acquire a fair-share execution slot for a Copilot LLM turn."""
        ticket_id = uuid.uuid4().hex[:12]
        item = _QueuedTurn(ticket_id=ticket_id, user_id=user_id, estimated_tokens=max(1, int(estimated_tokens)))
        deadline = time.monotonic() + max(1.0, float(max_wait_seconds))
        acquired = False
        last_status_emit = 0.0

        with self._cond:
            if not self._user_queues[user_id]:
                self._active_users.append(user_id)
            self._user_queues[user_id].append(item)

            try:
                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        raise InterruptedError("Copilot request cancelled by user.")

                    head_uid = self._next_ready_user_locked()
                    head_item = self._user_queues[head_uid][0] if head_uid and self._user_queues.get(head_uid) else None
                    now_mono = time.monotonic()

                    # Anti-starvation: reserve 1 of the 2 barrel lanes if head user is heavy or waited >2.5s
                    if head_item and (head_item.estimated_tokens >= 80_000 or (now_mono - head_item.enqueued_at) >= 2.5):
                        self._reserved_heavy_user = head_item.user_id
                    elif head_uid == user_id:
                        self._reserved_heavy_user = None

                    capacity_available = len(self._inflight_tickets) < self._max_concurrent_turns
                    # If another user holds the heavy head-of-line reservation, allow at most 1 non-heavy runner
                    if (
                        self._reserved_heavy_user
                        and self._reserved_heavy_user != user_id
                        and len(self._inflight_tickets) >= max(1, self._max_concurrent_turns - 1)
                    ):
                        capacity_available = False

                    is_my_turn = head_uid == user_id and head_item is not None and head_item.ticket_id == ticket_id
                    # Work-conserving bypass: if heavy user is waiting at head with 1 slot reserved for reload,
                    # a small prompt (<40k) from another user can use the OTHER barrel immediately
                    can_use_second_barrel = (
                        not is_my_turn
                        and self._reserved_heavy_user == head_uid
                        and head_uid != user_id
                        and item.estimated_tokens < 40_000
                        and len(self._inflight_tickets) == 0
                        and self._max_concurrent_turns >= 2
                    )

                    if capacity_available and (is_my_turn or can_use_second_barrel):
                        # Pop from this user's queue and rotate user to back if more queued
                        q = self._user_queues[user_id]
                        if q and q[0].ticket_id == ticket_id:
                            q.popleft()
                        else:
                            self._remove_ticket_locked(user_id, ticket_id)
                        if is_my_turn and self._active_users and self._active_users[0] == user_id:
                            self._active_users.popleft()
                            if q:
                                self._active_users.append(user_id)
                            else:
                                self._user_queues.pop(user_id, None)
                        elif not q:
                            self._user_queues.pop(user_id, None)
                            try:
                                self._active_users.remove(user_id)
                            except ValueError:
                                pass

                        if self._reserved_heavy_user == user_id:
                            self._reserved_heavy_user = None
                        self._inflight_tickets[ticket_id] = user_id
                        acquired = True
                        break

                    remaining = deadline - now_mono
                    if remaining <= 0:
                        raise TimeoutError("Copilot fair-queue wait budget exceeded; please retry shortly.")

                    if on_status and (now_mono - last_status_emit) >= 0.8:
                        last_status_emit = now_mono
                        pos, active_u = self._queue_position_locked(user_id, ticket_id)
                        on_status(
                            {
                                "reason": "fair_queue",
                                "position": pos,
                                "active_users": active_u,
                                "inflight_turns": len(self._inflight_tickets),
                                "wait_seconds": round(min(remaining, 15.0), 1),
                            }
                        )

                    self._cond.wait(timeout=min(0.5, remaining))
            except Exception:
                if not acquired:
                    self._remove_ticket_locked(user_id, ticket_id)
                    self._cond.notify_all()
                raise

        try:
            yield {
                "ticket_id": ticket_id,
                "user_id": user_id,
                "waited_seconds": round(max(0.0, time.monotonic() - item.enqueued_at), 2),
            }
        finally:
            with self._cond:
                self._inflight_tickets.pop(ticket_id, None)
                self._cond.notify_all()


_GLOBAL_ORCHESTRATOR: CopilotFairQueueOrchestrator | None = None
_ORCH_LOCK = threading.Lock()


def get_copilot_orchestrator() -> CopilotFairQueueOrchestrator:
    global _GLOBAL_ORCHESTRATOR
    if _GLOBAL_ORCHESTRATOR is None:
        with _ORCH_LOCK:
            if _GLOBAL_ORCHESTRATOR is None:
                _GLOBAL_ORCHESTRATOR = CopilotFairQueueOrchestrator(max_concurrent_turns=2)
    return _GLOBAL_ORCHESTRATOR
