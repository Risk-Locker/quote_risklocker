"""Durable worker heartbeat and bounded readiness checks."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.models.tables import WorkerHeartbeat


WORKER_STALE_SECONDS = 15


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def heartbeat_worker(db, *, worker_id: str, process_id: int, state: str, release_id: str | None = None) -> WorkerHeartbeat:
    record = db.get(WorkerHeartbeat, worker_id)
    if record is None:
        record = WorkerHeartbeat(worker_id=worker_id, started_at=_utcnow(), process_id=process_id)
        db.add(record)
    record.heartbeat_at = _utcnow()
    record.state = state
    record.release_id = release_id
    db.commit()
    return record


def worker_readiness(db, *, now: datetime | None = None) -> dict:
    current_time = now or _utcnow()
    record = db.scalar(select(WorkerHeartbeat).order_by(WorkerHeartbeat.heartbeat_at.desc()).limit(1))
    if record is None:
        return {"ready": False, "status": "Unavailable", "reason": "No worker heartbeat has been recorded."}
    heartbeat = record.heartbeat_at
    if heartbeat.tzinfo is None:
        heartbeat = heartbeat.replace(tzinfo=timezone.utc)
    age_seconds = max(0.0, (current_time - heartbeat).total_seconds())
    ready = age_seconds <= WORKER_STALE_SECONDS
    return {
        "ready": ready,
        "status": "Ready" if ready else "Unavailable",
        "reason": "Worker heartbeat is current." if ready else "Worker heartbeat is stale.",
        "worker_id": record.worker_id,
        "state": record.state,
        "heartbeat_age_seconds": round(age_seconds, 3),
    }
