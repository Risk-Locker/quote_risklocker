"""Multi-User "Elevator" Weighted Fair-Share Job Queue.

Implements an interleaved round-robin fair-share queue preventing single-user
starvation. When User C uploads 30 bulk fleet PDFs and User A uploads 2 PDFs,
the dispatcher interleaves processing:
    User C [1] -> User A [1] -> User C [2] -> User A [2] -> User C [3] ...

This guarantees User A finishes in slot 4 rather than waiting behind 30 jobs.
"""

from __future__ import annotations

import collections
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Sequence

logger = logging.getLogger(__name__)


@dataclass
class QueueItem:
    job_id: str
    user_id: str
    document_id: str
    created_at: float
    payload: dict[str, Any] = field(default_factory=dict)
    priority: int = 100


class FairShareJobQueue:
    """Thread-safe multi-user interleaved fair-share queue."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Mapping: user_id -> deque of QueueItem
        self._user_queues: dict[str, collections.deque[QueueItem]] = collections.defaultdict(collections.deque)
        # Active user order cycle (Elevator round-robin)
        self._active_users: collections.deque[str] = collections.deque()
        self._total_jobs_count: int = 0

    def enqueue(
        self,
        user_id: str,
        document_id: str,
        payload: dict[str, Any] | None = None,
        job_id: str | None = None,
        created_at: float | None = None,
        priority: int = 100,
    ) -> QueueItem:
        """Enqueue a new job under the specified user's bucket."""
        jid = job_id or str(uuid.uuid4())
        t = created_at if created_at is not None else time.time()
        item = QueueItem(
            job_id=jid,
            user_id=user_id,
            document_id=document_id,
            created_at=t,
            payload=payload or {},
            priority=priority,
        )

        with self._lock:
            user_q = self._user_queues[user_id]
            if not user_q:
                # First job for this user, register in round-robin active cycle
                self._active_users.append(user_id)
            user_q.append(item)
            self._total_jobs_count += 1

        return item

    def pop_next_job(self) -> QueueItem | None:
        """Pop the next job according to fair-share round-robin across active users."""
        with self._lock:
            if not self._active_users:
                return None

            # Get the next user in the round-robin cycle
            user_id = self._active_users.popleft()
            user_q = self._user_queues[user_id]

            if not user_q:
                # Safety check if user had no jobs
                del self._user_queues[user_id]
                return self.pop_next_job()

            item = user_q.popleft()
            self._total_jobs_count -= 1

            # If user still has pending jobs, requeue user at the back of the cycle
            if user_q:
                self._active_users.append(user_id)
            else:
                del self._user_queues[user_id]

            return item

    def get_queue_position(self, user_id: str, job_id: str) -> dict[str, Any]:
        """Calculate the exact interleaved position of a given job in the fair-share cycle.

        Simulates future fair-share dispatch order to provide a 1-indexed overall queue position.
        """
        with self._lock:
            user_q = self._user_queues.get(user_id)
            if not user_q:
                return {
                    "position": -1,
                    "active_users_count": len(self._active_users),
                    "items_ahead_for_user": 0,
                    "total_pending_jobs": self._total_jobs_count,
                    "other_users_count": max(0, len(self._active_users) - 1),
                }

            # Find user index within this user's queue
            user_job_idx = -1
            for idx, q_item in enumerate(user_q):
                if q_item.job_id == job_id:
                    user_job_idx = idx
                    break

            if user_job_idx == -1:
                return {
                    "position": -1,
                    "active_users_count": len(self._active_users),
                    "items_ahead_for_user": 0,
                    "total_pending_jobs": self._total_jobs_count,
                    "other_users_count": max(0, len(self._active_users) - 1),
                }

            # Simulate round-robin turns until this job is reached
            temp_users = collections.deque(self._active_users)
            temp_counts = {u: len(self._user_queues[u]) for u in self._user_queues}
            
            position = 0
            found = False

            while temp_users:
                u = temp_users.popleft()
                rem = temp_counts[u]
                if rem <= 0:
                    continue

                position += 1
                temp_counts[u] -= 1

                # If this turn is for our target user and corresponds to our job index
                target_consumed = len(self._user_queues[user_id]) - temp_counts[u]
                if u == user_id and target_consumed == (user_job_idx + 1):
                    found = True
                    break

                if temp_counts[u] > 0:
                    temp_users.append(u)

            other_users = max(0, len(self._active_users) - 1) if user_id in self._active_users else len(self._active_users)

            return {
                "position": position if found else -1,
                "active_users_count": len(self._active_users),
                "items_ahead_for_user": user_job_idx,
                "total_pending_jobs": self._total_jobs_count,
                "other_users_count": other_users,
            }

    @property
    def total_pending(self) -> int:
        with self._lock:
            return self._total_jobs_count

    @property
    def active_users_count(self) -> int:
        with self._lock:
            return len(self._active_users)

    def clear(self) -> None:
        """Clear all queued items."""
        with self._lock:
            self._user_queues.clear()
            self._active_users.clear()
            self._total_jobs_count = 0


# Global singleton instance for in-memory fair queue
_GLOBAL_FAIR_QUEUE = FairShareJobQueue()


def get_fair_share_queue() -> FairShareJobQueue:
    """Retrieve the global fair-share job queue."""
    return _GLOBAL_FAIR_QUEUE

