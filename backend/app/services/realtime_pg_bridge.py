"""PostgreSQL LISTEN/NOTIFY bridge for multi-worker & cross-process realtime sync.

Complements the in-process `RealtimeHub` so SSE clients connected to Uvicorn
worker A or background job runner B still receive instant updates whenever any
other worker commits a Quotation, Comparison Matrix, Cover Note, or Ledger write.
No-ops cleanly under SQLite / hermetic unit test environments.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from typing import Any
from uuid import uuid4

from sqlalchemy import text

logger = logging.getLogger(__name__)

WORKER_INSTANCE_ID = str(uuid4())
PG_REALTIME_CHANNEL = "risklocker_realtime"
_MAX_NOTIFY_BYTES = 7500


def _is_postgres_enabled() -> bool:
    if os.environ.get("RISKLOCKER_SKIP_DOTENV") == "1":
        return False
    if os.environ.get("APP_ENV", "").strip().lower() == "test":
        return False
    try:
        from app.core.config import get_settings

        url = str(get_settings().database_url or "").strip().lower()
        return url.startswith("postgresql")
    except Exception:
        return False


def _libpq_dsn(sqlalchemy_url: str) -> str:
    return re.sub(r"^postgresql\+[a-z0-9_]+://", "postgresql://", sqlalchemy_url, flags=re.IGNORECASE)


def notify_pg_realtime(envelope: dict[str, Any]) -> None:
    """Publish a realtime SSE envelope across all backend processes via pg_notify."""
    if not _is_postgres_enabled():
        return
    try:
        payload = json.dumps(
            {"instance_id": WORKER_INSTANCE_ID, "envelope": envelope},
            ensure_ascii=False,
        )
        if len(payload.encode("utf-8")) > _MAX_NOTIFY_BYTES:
            return
        from app.db.session import engine

        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(
                text("SELECT pg_notify(:chan, :payload)"),
                {"chan": PG_REALTIME_CHANNEL, "payload": payload},
            )
    except Exception as exc:
        logger.debug("pg_notify realtime publish skipped: %s", exc)


def start_pg_realtime_listener(hub: Any) -> threading.Event | None:
    """Start a background daemon thread listening on PostgreSQL NOTIFY events."""
    if not _is_postgres_enabled():
        return None
    try:
        from app.core.config import get_settings

        pg_dsn = _libpq_dsn(str(get_settings().database_url or ""))
        if not pg_dsn.lower().startswith("postgresql"):
            return None
    except Exception:
        return None

    stop_event = threading.Event()

    def _listener_loop() -> None:
        while not stop_event.is_set():
            try:
                import psycopg

                with psycopg.connect(pg_dsn, autocommit=True) as conn:
                    conn.execute("LISTEN risklocker_realtime")
                    while not stop_event.is_set():
                        for notify in conn.notifies(timeout=2.0):
                            if stop_event.is_set():
                                break
                            raw = getattr(notify, "payload", None)
                            if not raw:
                                continue
                            try:
                                msg = json.loads(raw)
                            except ValueError:
                                continue
                            if msg.get("instance_id") == WORKER_INSTANCE_ID:
                                continue
                            envelope = msg.get("envelope")
                            if isinstance(envelope, dict):
                                hub.deliver_external_event(envelope)
            except Exception as exc:
                if not stop_event.is_set():
                    logger.debug("PG realtime listener reconnecting: %s", exc)
                    stop_event.wait(3.0)

    thread = threading.Thread(
        target=_listener_loop,
        name="risklocker-pg-realtime-listener",
        daemon=True,
    )
    thread.start()
    return stop_event
