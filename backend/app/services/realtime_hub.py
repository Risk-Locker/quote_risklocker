"""In-process real-time SSE event hub and active-editor presence registry."""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

PRESENCE_TTL_SECONDS = 45.0
SUBSCRIBER_QUEUE_MAXSIZE = 256


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
    entered_at_mono: float = 0.0
    entered_at_iso: str = ""
    tab_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "resource_id": self.resource_id,
            "user_id": self.user_id,
            "user_email": self.user_email,
            "user_name": self.user_name,
            "field": self.field,
            "tab_id": self.tab_id,
            "entered_at": self.entered_at_iso or self.updated_at_iso,
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
        self._resource_versions: dict[tuple[str, str], int] = {}
        self._resource_meta: dict[tuple[str, str], dict[str, Any]] = {}

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
        matched = [
            entry
            for (s, r, _uid), entry in self._presence.items()
            if s == scope and r == resource_id
        ]
        # Earliest person in workspace is Priority #1 (Primary Editor)
        matched.sort(key=lambda item: (item.entered_at_mono, item.entered_at_iso))
        return [item.to_dict() for item in matched]

    def get_presence(self, scope: str, resource_id: str) -> list[dict[str, Any]]:
        now_mono = time.monotonic()
        with self._lock:
            self._prune_expired_locked(now_mono)
            return self._snapshot_presence_locked(scope, resource_id)

    def get_resource_state(self, scope: str, resource_id: str) -> dict[str, Any]:
        key = (str(scope or "").strip(), str(resource_id or "all").strip() or "all")
        with self._lock:
            meta = self._resource_meta.get(key)
            if meta is not None:
                return dict(meta)
            return {
                "version": self._resource_versions.get(key, 0),
                "last_origin_tab_id": None,
                "last_actor_id": None,
                "last_actor_name": None,
                "last_summary": None,
                "updated_at": None,
            }

    def set_presence(
        self,
        *,
        scope: str,
        resource_id: str,
        user_id: str,
        user_email: str,
        user_name: str,
        field: str | None = None,
        tab_id: str | None = None,
    ) -> list[dict[str, Any]]:
        now_mono = time.monotonic()
        now_iso = _utc_iso()
        key = (scope, resource_id, user_id)
        with self._lock:
            self._prune_expired_locked(now_mono)
            existing = self._presence.get(key)
            entered_mono = existing.entered_at_mono if existing and existing.entered_at_mono > 0 else now_mono
            entered_iso = existing.entered_at_iso if existing and existing.entered_at_iso else now_iso
            entry = PresenceEntry(
                scope=scope,
                resource_id=resource_id,
                user_id=user_id,
                user_email=user_email,
                user_name=user_name,
                field=field,
                updated_at_mono=now_mono,
                updated_at_iso=now_iso,
                entered_at_mono=entered_mono,
                entered_at_iso=entered_iso,
                tab_id=tab_id or (existing.tab_id if existing else None),
            )
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
        targets: Sequence[tuple[str, str]] | None = None,
        origin_tab_id: str | None = None,
    ) -> int:
        """Broadcast a post-commit resource_updated event to all connected tabs & workers."""
        effective_targets: list[tuple[str, str]] = []
        seen_targets: set[tuple[str, str]] = set()

        def _add_target(t_scope: str | None, t_rid: str | None) -> None:
            s_clean = str(t_scope or "").strip()
            r_clean = str(t_rid or "all").strip() or "all"
            if s_clean and (s_clean, r_clean) not in seen_targets:
                seen_targets.add((s_clean, r_clean))
                effective_targets.append((s_clean, r_clean))

        base_rid = str(resource_id or "all")
        _add_target(scope, base_rid)
        if extra_scopes:
            for extra_s in extra_scopes:
                _add_target(extra_s, base_rid)
        if targets:
            for t_scope, t_rid in targets:
                _add_target(t_scope, t_rid)

        ts = _utc_iso()
        envelopes: list[dict[str, Any]] = []
        with self._lock:
            self._version += 1
            global_version = self._version
            for target_scope, target_rid in effective_targets:
                res_key = (target_scope, target_rid)
                res_version = self._resource_versions.get(res_key, 0) + 1
                self._resource_versions[res_key] = res_version
                resolved_actor_name = actor_name or actor_email or "Teammate"
                self._resource_meta[res_key] = {
                    "version": res_version,
                    "last_origin_tab_id": origin_tab_id,
                    "last_actor_id": actor_id,
                    "last_actor_name": resolved_actor_name,
                    "last_summary": summary or "Updated",
                    "updated_at": ts,
                }
                envelope = {
                    "event": "updated",
                    "data": {
                        "scope": target_scope,
                        "resource_id": target_rid,
                        "actor_id": actor_id,
                        "actor_email": actor_email,
                        "actor_name": resolved_actor_name,
                        "origin_tab_id": origin_tab_id,
                        "summary": summary or "Updated",
                        "version": res_version,
                        "global_version": global_version,
                        "timestamp": ts,
                    },
                }
                envelopes.append(envelope)
                self._broadcast_locked(envelope)

        from app.services.realtime_pg_bridge import notify_pg_realtime

        for env in envelopes:
            notify_pg_realtime(env)
        return global_version

    def deliver_external_event(self, envelope: dict[str, Any]) -> None:
        """Deliver an external cross-worker realtime envelope to local SSE subscribers."""
        if not isinstance(envelope, dict):
            return
        with self._lock:
            self._version += 1
            if envelope.get("event") == "updated" and isinstance(envelope.get("data"), dict):
                d = envelope["data"]
                t_scope = str(d.get("scope") or "").strip()
                t_rid = str(d.get("resource_id") or "all").strip() or "all"
                if t_scope:
                    res_key = (t_scope, t_rid)
                    res_version = self._resource_versions.get(res_key, 0) + 1
                    self._resource_versions[res_key] = res_version
                    self._resource_meta[res_key] = {
                        "version": res_version,
                        "last_origin_tab_id": d.get("origin_tab_id"),
                        "last_actor_id": d.get("actor_id"),
                        "last_actor_name": d.get("actor_name"),
                        "last_summary": d.get("summary"),
                        "updated_at": d.get("timestamp"),
                    }
            self._broadcast_locked(envelope)

    def current_version(self) -> int:
        with self._lock:
            return self._version

    def reset_for_tests(self) -> None:
        with self._lock:
            self._subscribers.clear()
            self._presence.clear()
            self._resource_versions.clear()
            self._resource_meta.clear()
            self._version = 0


realtime_hub = RealtimeHub()


def build_tenure_sync_targets(db: Any, tenure_id: str | None) -> list[tuple[str, str]]:
    """Build exact multi-scope SSE targets for a Tenure and every linked Session + Draft."""
    tid = str(tenure_id or "").strip()
    if not tid:
        return []
    targets: list[tuple[str, str]] = [("comparison", tid), ("ledger", tid), ("ledger", "all")]
    try:
        from sqlalchemy import select
        from app.models.tables import Session as SessionModel

        rows = db.execute(
            select(SessionModel.id, SessionModel.draft_id).where(
                SessionModel.tenure_id == tid,
                SessionModel.status != "trash",
            )
        ).all()
        for sid, did in rows:
            if sid:
                targets.append(("workspace", str(sid)))
                targets.append(("sessions", str(sid)))
            if did:
                targets.append(("workspace", str(did)))
    except Exception:
        pass
    return targets


def build_session_sync_targets(session: Any) -> list[tuple[str, str]]:
    """Build exact multi-scope SSE targets for a Session, its Draft, and its linked Tenure."""
    if session is None:
        return []
    targets: list[tuple[str, str]] = []
    sid = getattr(session, "id", None)
    did = getattr(session, "draft_id", None)
    tid = getattr(session, "tenure_id", None)
    if sid:
        targets.append(("workspace", str(sid)))
        targets.append(("sessions", str(sid)))
    if did:
        targets.append(("workspace", str(did)))
    targets.append(("sessions", "all"))
    if tid:
        targets.append(("comparison", str(tid)))
        targets.append(("ledger", str(tid)))
        targets.append(("ledger", "all"))
    return targets


def publish_realtime_update(
    *,
    scope: str,
    resource_id: str = "all",
    actor: Any = None,
    summary: str | None = None,
    extra_scopes: Iterable[str] | None = None,
    targets: Sequence[tuple[str, str]] | None = None,
    origin_tab_id: str | None = None,
) -> int:
    """Convenience helper for routers to emit updates right after db.commit()."""
    actor_id = getattr(actor, "id", None) if actor is not None else None
    actor_email = getattr(actor, "email", None) if actor is not None else None
    actor_name = getattr(actor, "name", None) if actor is not None else None
    clean_tab = origin_tab_id.strip() if isinstance(origin_tab_id, str) and origin_tab_id.strip() else None
    return realtime_hub.publish_update(
        scope=scope,
        resource_id=str(resource_id or "all"),
        actor_id=actor_id,
        actor_email=actor_email,
        actor_name=actor_name or actor_email,
        summary=summary,
        extra_scopes=extra_scopes,
        targets=targets,
        origin_tab_id=clean_tab,
    )


def format_sse_message(event_name: str, payload: dict[str, Any]) -> str:
    """Serialize an SSE frame safely (UTF-8 JSON)."""
    return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
