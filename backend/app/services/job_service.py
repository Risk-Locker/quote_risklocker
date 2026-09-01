"""Durable Postgres job queue with leases, retries, and safe status data."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select

from app.core.errors import AppError
from app.models.tables import Job


TERMINAL_STATES = frozenset({"completed", "failed", "cancelled"})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _transition_phase(job: Job, phase: str, now: datetime) -> None:
    clean_phase = phase.strip().lower()[:80]
    if not clean_phase:
        raise AppError("Job phase is invalid.", 500)
    timestamps = dict(job.phase_timestamps or {})
    if job.phase != clean_phase:
        job.phase = clean_phase
        job.phase_started_at = now
        timestamps.setdefault(clean_phase, now.isoformat())
    job.phase_timestamps = timestamps


def _elapsed_seconds(job: Job, now: datetime) -> float:
    started = job.created_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    finished = job.completed_at or now
    if finished.tzinfo is None:
        finished = finished.replace(tzinfo=timezone.utc)
    return max(0.0, round((finished - started).total_seconds(), 3))


def claim_query(now: datetime):
    return (
        select(Job)
        .where(
            Job.attempt < Job.max_attempts,
            Job.cancelled_at.is_(None),
            or_(
                and_(Job.state == "queued", Job.available_at <= now),
                and_(Job.state == "processing", Job.lease_expires_at.is_not(None), Job.lease_expires_at <= now),
            ),
        )
        .order_by(Job.priority.asc(), Job.available_at.asc(), Job.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )


def enqueue_job(
    db,
    *,
    job_type: str,
    idempotency_key: str,
    owner_id: str,
    session_id: str | None,
    uploaded_file_id: str | None,
    payload: dict,
    priority: int = 100,
    max_attempts: int = 3,
) -> tuple[Job, bool]:
    existing = db.scalar(
        select(Job).where(Job.job_type == job_type, Job.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if existing.owner_id != owner_id:
            raise AppError("This idempotency key is already in use.", 409)
        return existing, False
    if max_attempts < 1 or max_attempts > 10:
        raise AppError("Job attempt policy is invalid.", 500)
    job = Job(
        job_type=job_type,
        idempotency_key=idempotency_key,
        owner_id=owner_id,
        session_id=session_id,
        uploaded_file_id=uploaded_file_id,
        state="queued",
        priority=priority,
        payload=payload,
        result={},
        safe_error={},
        progress=0,
        phase="queued",
        phase_started_at=_utcnow(),
        phase_timestamps={"queued": _utcnow().isoformat()},
        attempt=0,
        max_attempts=max_attempts,
        available_at=_utcnow(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job, True


def claim_next_job(db, *, worker_id: str, lease_seconds: int = 180) -> Job | None:
    if lease_seconds < 30 or lease_seconds > 3_600:
        raise AppError("Job lease duration is invalid.", 500)
    now = _utcnow()
    job = db.scalar(claim_query(now))
    if job is None:
        return None
    job.state = "processing"
    job.attempt += 1
    job.lease_owner = worker_id
    job.heartbeat_at = now
    _transition_phase(job, "starting", now)
    job.lease_expires_at = now + timedelta(seconds=lease_seconds)
    job.safe_error = {}
    db.commit()
    db.refresh(job)
    return job


def _require_lease(job: Job, worker_id: str) -> None:
    if job.state != "processing" or job.lease_owner != worker_id:
        raise AppError("The worker no longer owns this job lease.", 409)


def heartbeat_job(
    db,
    job: Job,
    *,
    worker_id: str,
    progress: int,
    phase: str | None = None,
    lease_seconds: int = 180,
) -> None:
    _require_lease(job, worker_id)
    if progress < 0 or progress > 99:
        raise AppError("Job progress must be between 0 and 99 before completion.", 400)
    now = _utcnow()
    job.progress = progress
    job.heartbeat_at = now
    if phase is not None:
        _transition_phase(job, phase, now)
    job.lease_expires_at = now + timedelta(seconds=lease_seconds)
    db.commit()


def complete_job(db, job: Job, worker_id: str, result: dict) -> None:
    _require_lease(job, worker_id)
    now = _utcnow()
    job.state = "completed"
    job.progress = 100
    job.result = result
    job.safe_error = {}
    job.completed_at = now
    job.heartbeat_at = now
    _transition_phase(job, "completed", now)
    job.lease_owner = None
    job.lease_expires_at = None
    db.commit()


def fail_job(db, job: Job, *, worker_id: str, code: str, message: str) -> None:
    _require_lease(job, worker_id)
    now = _utcnow()
    job.safe_error = {"code": code[:80], "message": message[:500]}
    job.lease_owner = None
    job.lease_expires_at = None
    job.heartbeat_at = now
    if job.attempt < job.max_attempts:
        job.state = "queued"
        _transition_phase(job, "retry_wait", now)
        job.available_at = now + timedelta(seconds=min(300, 15 * (2 ** max(0, job.attempt - 1))))
    else:
        job.state = "failed"
        _transition_phase(job, "failed", now)
        job.completed_at = now
    db.commit()


def cancel_job(db, job: Job) -> None:
    if job.state in TERMINAL_STATES:
        raise AppError("This job cannot be cancelled.", 409)
    now = _utcnow()
    job.state = "cancelled"
    job.cancelled_at = now
    job.completed_at = now
    job.heartbeat_at = now
    _transition_phase(job, "cancelled", now)
    job.lease_owner = None
    job.lease_expires_at = None

    # Clean up any local ephemeral upload files
    if job.uploaded_file_id:
        from app.core.workspace import QC_TEMP_ROOT, REPOSITORY_ROOT
        for search_dir in [QC_TEMP_ROOT / "stateless_uploads", REPOSITORY_ROOT / "backend" / ".qc-tmp" / "stateless_uploads"]:
            if search_dir.exists():
                for candidate in search_dir.glob(f"{job.uploaded_file_id}.pdf"):
                    candidate.unlink(missing_ok=True)

    # Clean up orphan preparing session/draft if cancelled before completion
    if job.session_id and hasattr(db, "get"):
        from app.models.tables import Batch, QuotationDraft, Session, UploadedFile
        session = db.get(Session, job.session_id)
        if session:
            draft_id = session.draft_id
            uploaded_id = session.uploaded_file_id
            db.delete(session)
            db.flush()
            if draft_id:
                draft = db.get(QuotationDraft, draft_id)
                if draft and draft.revision == 1:
                    db.delete(draft)
                    db.flush()
            if uploaded_id:
                uf = db.get(UploadedFile, uploaded_id)
                if uf:
                    batch_id = uf.batch_id
                    db.delete(uf)
                    db.flush()
                    if batch_id:
                        batch = db.get(Batch, batch_id)
                        if batch and not getattr(batch, "files", []):
                            db.delete(batch)
                            db.flush()
    db.commit()




def serialize_job(job: Job) -> dict:
    now = _utcnow()
    return {
        "id": job.id,
        "job_type": job.job_type,
        "session_id": job.session_id,
        "state": job.state,
        "attempt": job.attempt,
        "max_attempts": job.max_attempts,
        "progress": job.progress,
        "phase": job.phase,
        "phase_started_at": job.phase_started_at.isoformat() if job.phase_started_at else None,
        "phase_timestamps": job.phase_timestamps or {},
        "heartbeat_at": job.heartbeat_at.isoformat() if job.heartbeat_at else None,
        "elapsed_seconds": _elapsed_seconds(job, now),
        "result": job.result or {},
        "error": job.safe_error or None,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
