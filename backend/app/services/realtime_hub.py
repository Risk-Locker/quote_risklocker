"""In-process real-time SSE event hub and active-editor presence registry."""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

PRESENCE_TTL_SECONDS = 20.0
SUBSCRIBER_QUEUE_MAXSIZE = 100


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PresenceEntry:
    scope: str
    resource_id: str
    user_id: str
    user_email: str
    user_name: str
    field: str | None
    updated_at_mono: float
    updated_at_iso: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "resource_id": self.resource_id,
            "user_id": self.user_id,
            "user_email": self.user_email,
            "user_name": self.user_name,
            "field": self.field,
            "updated_at": self.updated_at_iso,
        }


@dataclass
class _Subscriber:
    sub_id: int
    user_id: str
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[dict[str, Any]]


class RealtimeHub:
    """Thread-safe + asyncio-safe pub/sub hub for multi-user live sync & presence."""

    def __init__(self, *, presence_ttl: float = PRESENCE_TTL_SECONDS, max_queue_size: int = SUBSCRIBER_QUEUE_MAXSIZE) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[int, _Subscriber] = {}
        self._next_sub_id = 1
        self._version = 0
        self._presence_ttl = presence_ttl
        self._max_queue_size = max_queue_size
        self._presence: dict[tuple[str, str, str], PresenceEntry] = {}

    def subscribe(self, user_id: str, loop: asyncio.AbstractEventLoop) -> tuple[int, asyncio.Queue[dict[str, Any]]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=self._max_queue_size)
        with self._lock:
            sub_id = self._next_sub_id
            self._next_sub_id += 1
            self._subscribers[sub_id] = _Subscriber(sub_id=sub_id, user_id=user_id, loop=loop, queue=queue)
        return sub_id, queue

    def unsubscribe(self, sub_id: int) -> None:
        with self._lock:
            self._subscribers.pop(sub_id, None)

    def _enqueue_on_subscriber(self, sub: _Subscriber, event: dict[str, Any]) -> None:
        if sub.loop.is_closed():
            return

        def _deliver() -> None:
            if sub.queue.full():
                try:
                    sub.queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                sub.queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

        try:
            sub.loop.call_soon_threadsafe(_deliver)
        except RuntimeError:
            # Event loop already closed during shutdown.
            pass

    def _broadcast_locked(self, event: dict[str, Any]) -> None:
        for sub in list(self._subscribers.values()):
            self._enqueue_on_subscriber(sub, event)

    def _prune_expired_locked(self, now_mono: float) -> list[tuple[str, str]]:
        expired_keys = [
            key for key, entry in self._presence.items() if (now_mono - entry.updated_at_mono) > self._presence_ttl
        ]
        affected_scopes: list[tuple[str, str]] = []
        for key in expired_keys:
            self._presence.pop(key, None)
            affected_scopes.append((key[0], key[1]))
        return affected_scopes

    def _snapshot_presence_locked(self, scope: str, resource_id: str) -> list[dict[str, Any]]:
        entries = [
            entry.to_dict()
            for (s, r, _uid), entry in self._presence.items()
            if s == scope and r == resource_id
        ]
        entries.sort(key=lambda item: item["updated_at"], reverse=True)
        return entries

    def get_presence(self, scope: str, resource_id: str) -> list[dict[str, Any]]:
        now_mono = time.monotonic()
        with self._lock:
            self._prune_expired_locked(now_mono)
            return self._snapshot_presence_locked(scope, resource_id)

    def set_presence(
        self,
        *,
        scope: str,
        resource_id: str,
        user_id: str,
        user_email: str,
        user_name: str,
        field: str | None = None,
    ) -> list[dict[str, Any]]:
        now_mono = time.monotonic()
        key = (scope, resource_id, user_id)
        entry = PresenceEntry(
            scope=scope,
            resource_id=resource_id,
            user_id=user_id,
            user_email=user_email,
            user_name=user_name,
            field=field,
            updated_at_mono=now_mono,
            updated_at_iso=_utc_iso(),
        )
        with self._lock:
            self._prune_expired_locked(now_mono)
            self._presence[key] = entry
            editors = self._snapshot_presence_locked(scope, resource_id)
            self._broadcast_locked(
                {
                    "event": "presence",
                    "data": {
                        "scope": scope,
                        "resource_id": resource_id,
                        "active_editors": editors,
                        "timestamp": entry.updated_at_iso,
                    },
                }
            )
            return editors

    def clear_presence(self, *, scope: str, resource_id: str, user_id: str) -> list[dict[str, Any]]:
        now_mono = time.monotonic()
        with self._lock:
            self._prune_expired_locked(now_mono)
            removed = self._presence.pop((scope, resource_id, user_id), None)
            editors = self._snapshot_presence_locked(scope, resource_id)
            if removed is not None:
                self._broadcast_locked(
                    {
                        "event": "presence",
                        "data": {
                            "scope": scope,
                            "resource_id": resource_id,
                            "active_editors": editors,
                            "timestamp": _utc_iso(),
                        },
                    }
                )
            return editors

    def publish_update(
        self,
        *,
        scope: str,
        resource_id: str = "all",
        actor_id: str | None = None,
        actor_email: str | None = None,
        actor_name: str | None = None,
        summary: str | None = None,
        extra_scopes: Iterable[str] | None = None,
    ) -> int:
        """Broadcast a post-commit resource_updated event to all connected tabs."""
        scopes = [scope]
        if extra_scopes:
            for s in extra_scopes:
                if s and s not in scopes:
                    scopes.append(s)

        ts = _utc_iso()
        with self._lock:
            self._version += 1
            version = self._version
            for target_scope in scopes:
                self._broadcast_locked(
                    {
                        "event": "updated",
                        "data": {
                            "scope": target_scope,
                            "resource_id": str(resource_id or "all"),
                            "actor_id": actor_id,
                            "actor_email": actor_email,
                            "actor_name": actor_name or actor_email or "Teammate",
                            "summary": summary or "Updated",
                            "version": version,
                            "timestamp": ts,
                        },
                    }
                )
            return version

    def current_version(self) -> int:
        with self._lock:
            return self._version

    def reset_for_tests(self) -> None:
        with self._lock:
            self._subscribers.clear()
            self._presence.clear()
            self._version = 0


realtime_hub = RealtimeHub()


def publish_realtime_update(
    *,
    scope: str,
    resource_id: str = "all",
    actor: Any = None,
    summary: str | None = None,
    extra_scopes: Iterable[str] | None = None,
) -> int:
    """Convenience helper for routers to emit updates right after db.commit()."""
    actor_id = getattr(actor, "id", None) if actor is not None else None
    actor_email = getattr(actor, "email", None) if actor is not None else None
    actor_name = getattr(actor, "name", None) if actor is not None else None
    return realtime_hub.publish_update(
        scope=scope,
        resource_id=str(resource_id or "all"),
        actor_id=actor_id,
        actor_email=actor_email,
        actor_name=actor_name or actor_email,
        summary=summary,
        extra_scopes=extra_scopes,
    )


def format_sse_message(event_name: str, payload: dict[str, Any]) -> str:
    """Serialize an SSE frame safely (UTF-8 JSON)."""
    return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
