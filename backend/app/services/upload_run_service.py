"""Server-backed Staging Batch (UploadRun) lifecycle & read-only detail views."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session as DbSession

from app.auth.rbac import can_view_owner_record
from app.core.errors import AppError
from app.models.enums import Role
from app.models.tables import (
    Job,
    QuotationDraft,
    Session as QuotationSession,
    UploadedFile,
    UploadRun,
    new_id,
)
from app.services.ai_fleet_gateway import compute_next_pt_midnight_utc, get_fleet_gateway

logger = logging.getLogger(__name__)


def _is_privileged(user: Any) -> bool:
    role = (getattr(user, "role", "") or "").lower()
    return role in {Role.SUPER_ADMIN.value, Role.ADMIN.value, Role.DEV.value}


def _load_run_with_access(db: DbSession, run_id: str, user: Any) -> UploadRun:
    run = db.get(UploadRun, run_id)
    if not run:
        raise AppError("Staging batch not found.", 404)
    if not _is_privileged(user) and not can_view_owner_record(db, user, run.owner_id):
        raise AppError("Staging batch not found.", 404)
    return run


def create_upload_run(
    db: DbSession,
    *,
    owner_id: str,
    title: str,
    mode: str = "bulk",
    tenure_id: str | None = None,
    is_test: bool = False,
    total_files: int = 0,
) -> UploadRun:
    clean_mode = (mode or "bulk").strip().lower()
    if clean_mode not in {"single", "comparison", "bulk"}:
        clean_mode = "bulk"
    clean_title = (title or "").strip()[:255] or f"{clean_mode.title()} Upload Batch"
    run = UploadRun(
        id=new_id(),
        owner_id=owner_id,
        title=clean_title,
        mode=clean_mode,
        status="active",
        tenure_id=tenure_id or None,
        is_test=bool(is_test),
        total_files=max(0, int(total_files or 0)),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def sync_upload_run_status(db: DbSession, run_id: str) -> UploadRun | None:
    """Recompute UploadRun aggregate status and total_files from SQL Job states."""
    run = db.get(UploadRun, run_id)
    if not run:
        return None
    rows = db.execute(
        select(Job.state, func.count(Job.id))
        .where(Job.upload_run_id == run_id)
        .group_by(Job.state)
    ).all()
    counts = {str(st): int(cnt or 0) for st, cnt in rows}
    total = sum(counts.values())
    if total > run.total_files:
        run.total_files = total

    queued = counts.get("queued", 0)
    processing = counts.get("processing", 0)
    paused_quota = counts.get("paused_quota", 0)
    paused_user = counts.get("paused_user", 0)
    failed = counts.get("failed", 0)
    completed = counts.get("completed", 0)
    cancelled = counts.get("cancelled", 0)

    if total == 0:
        run.status = "active"
    elif queued > 0 or processing > 0:
        run.status = "active"
    elif paused_quota > 0:
        run.status = "paused_quota"
    elif paused_user > 0:
        run.status = "paused"
    elif failed > 0:
        run.status = "completed_with_errors" if completed > 0 else "failed"
    elif completed > 0:
        run.status = "completed"
    elif cancelled > 0:
        run.status = "cancelled"
    run.updated_at = datetime.now(timezone.utc)
    return run


def _aggregate_counts_for_runs(db: DbSession, run_ids: list[str]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {
        rid: {
            "total": 0,
            "queued": 0,
            "processing": 0,
            "paused_quota": 0,
            "paused_user": 0,
            "completed": 0,
            "needs_review": 0,
            "failed": 0,
            "cancelled": 0,
        }
        for rid in run_ids
    }
    if not run_ids:
        return out

    job_rows = db.execute(
        select(Job.upload_run_id, Job.state, func.count(Job.id))
        .where(Job.upload_run_id.in_(run_ids))
        .group_by(Job.upload_run_id, Job.state)
    ).all()
    for rid, st, cnt in job_rows:
        rkey = str(rid)
        if rkey in out:
            c = int(cnt or 0)
            out[rkey]["total"] += c
            if st in out[rkey]:
                out[rkey][str(st)] = c

    review_rows = db.execute(
        select(QuotationSession.upload_run_id, func.count(QuotationSession.id))
        .join(QuotationDraft, QuotationDraft.id == QuotationSession.draft_id)
        .where(
            QuotationSession.upload_run_id.in_(run_ids),
            QuotationSession.status != "trash",
            func.lower(QuotationDraft.status).in_(["check needed", "cannot read", "check_needed", "cannot_read"]),
        )
        .group_by(QuotationSession.upload_run_id)
    ).all()
    for rid, cnt in review_rows:
        rkey = str(rid)
        if rkey in out:
            out[rkey]["needs_review"] = int(cnt or 0)

    return out


def list_upload_runs(
    db: DbSession,
    *,
    user: Any,
    mode: str | None = None,
    status: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Strictly read-only paginated listing of staging batches."""
    stmt = select(UploadRun)
    if not _is_privileged(user):
        stmt = stmt.where(UploadRun.owner_id == user.id)
    if mode and mode != "all":
        stmt = stmt.where(UploadRun.mode == mode.strip().lower())
    if status and status != "all":
        stmt = stmt.where(UploadRun.status == status.strip().lower())
    if search and search.strip():
        stmt = stmt.where(UploadRun.title.ilike(f"%{search.strip()}%"))

    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    runs = list(
        db.scalars(
            stmt.order_by(desc(UploadRun.created_at)).limit(min(max(limit, 1), 100)).offset(max(0, offset))
        ).all()
    )
    run_ids = [r.id for r in runs]
    counts_map = _aggregate_counts_for_runs(db, run_ids)

    items = []
    for run in runs:
        counts = counts_map.get(run.id, {})
        items.append(
            {
                "id": run.id,
                "owner_id": run.owner_id,
                "title": run.title,
                "mode": run.mode,
                "status": run.status,
                "tenure_id": run.tenure_id,
                "is_test": run.is_test,
                "total_files": max(run.total_files, counts.get("total", 0)),
                "counts": counts,
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "updated_at": run.updated_at.isoformat() if run.updated_at else None,
            }
        )
    return {"runs": items, "total": total}


def _extract_field_val(fields: dict | None, key: str) -> Any:
    if not isinstance(fields, dict):
        return None
    raw = fields.get(key)
    if isinstance(raw, dict):
        return raw.get("value")
    return raw


def get_upload_run_detail(db: DbSession, *, run_id: str, user: Any) -> dict[str, Any]:
    """Strictly read-only full staging arena snapshot for a batch run."""
    run = _load_run_with_access(db, run_id, user)
    counts = _aggregate_counts_for_runs(db, [run.id]).get(run.id, {})

    rows = db.execute(
        select(Job, UploadedFile, QuotationSession, QuotationDraft)
        .outerjoin(UploadedFile, UploadedFile.id == Job.uploaded_file_id)
        .outerjoin(QuotationSession, QuotationSession.id == Job.session_id)
        .outerjoin(QuotationDraft, QuotationDraft.id == QuotationSession.draft_id)
        .where(Job.upload_run_id == run.id)
        .order_by(Job.created_at.asc())
    ).all()

    items: list[dict[str, Any]] = []
    for job, ufile, sess, draft in rows:
        if sess is not None and sess.status == "trash":
            continue
        fields = (draft.fields if draft and isinstance(draft.fields, dict) else {})
        plate = _extract_field_val(fields, "vehicle_no")
        premium = _extract_field_val(fields, "total_amount") or _extract_field_val(fields, "premium")
        items.append(
            {
                "job_id": job.id,
                "session_id": job.session_id,
                "uploaded_file_id": job.uploaded_file_id,
                "filename": ufile.original_filename if ufile else "quotation.pdf",
                "size_bytes": ufile.size_bytes if ufile else 0,
                "state": job.state,
                "progress": job.progress,
                "phase": job.phase,
                "paused_reason": job.paused_reason,
                "available_at": job.available_at.isoformat() if job.available_at else None,
                "attempt": job.attempt,
                "max_attempts": job.max_attempts,
                "error": (job.safe_error or {}).get("message") if isinstance(job.safe_error, dict) else None,
                "tenure_id": sess.tenure_id if sess else run.tenure_id,
                "document_type": sess.document_type if sess else None,
                "insurer": sess.detected_company if sess else None,
                "plate": plate,
                "premium": premium,
                "ref": sess.quotation_ref if sess else None,
                "draft_status": draft.status if draft else None,
                "created_at": job.created_at.isoformat() if job.created_at else None,
            }
        )

    telemetry = get_fleet_gateway().get_fleet_telemetry(db, upload_run_id=run.id, limit=25)
    now_utc = datetime.now(timezone.utc)
    next_reset = compute_next_pt_midnight_utc(now_utc)
    seconds_until_reset = max(0, int((next_reset - now_utc).total_seconds()))

    return {
        "run": {
            "id": run.id,
            "owner_id": run.owner_id,
            "title": run.title,
            "mode": run.mode,
            "status": run.status,
            "tenure_id": run.tenure_id,
            "is_test": run.is_test,
            "total_files": max(run.total_files, len(items)),
            "counts": counts,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "updated_at": run.updated_at.isoformat() if run.updated_at else None,
        },
        "items": items,
        "eta_seconds": telemetry.get("estimated_remaining_seconds", 0),
        "active_lanes_count": telemetry.get("active_lanes_count", 0),
        "total_lanes_count": telemetry.get("total_lanes_count", 0),
        "next_pt_reset_utc": next_reset.isoformat(),
        "seconds_until_pt_reset": seconds_until_reset,
    }


def pause_upload_run(db: DbSession, *, run_id: str, user: Any) -> dict[str, Any]:
    run = _load_run_with_access(db, run_id, user)
    now = datetime.now(timezone.utc)
    jobs = list(
        db.scalars(
            select(Job).where(
                Job.upload_run_id == run.id,
                Job.state.in_(["queued", "paused_quota"]),
                Job.cancelled_at.is_(None),
            )
        ).all()
    )
    for job in jobs:
        job.state = "paused_user"
        job.phase = "paused_by_user"
        job.paused_reason = "Paused by user"
    run.status = "paused"
    run.updated_at = now
    db.commit()
    get_fleet_gateway().record_fleet_event(
        level="info",
        event_type="batch_paused",
        upload_run_id=run.id,
        message=f"Paused staging batch '{run.title}' ({len(jobs)} queued job(s) paused)",
        db=db,
    )
    db.commit()
    return {"ok": True, "paused_count": len(jobs), "status": run.status}


def resume_upload_run(db: DbSession, *, run_id: str, user: Any) -> dict[str, Any]:
    run = _load_run_with_access(db, run_id, user)
    now = datetime.now(timezone.utc)
    jobs = list(
        db.scalars(
            select(Job).where(
                Job.upload_run_id == run.id,
                Job.state.in_(["paused_user", "paused_quota"]),
                Job.cancelled_at.is_(None),
            )
        ).all()
    )
    for job in jobs:
        job.state = "queued"
        job.phase = "queued"
        job.available_at = now
        job.paused_reason = None
    run.status = "active"
    run.updated_at = now
    db.commit()
    get_fleet_gateway().record_fleet_event(
        level="info",
        event_type="batch_resumed",
        upload_run_id=run.id,
        message=f"Resumed staging batch '{run.title}' ({len(jobs)} job(s) queued)",
        db=db,
    )
    db.commit()
    return {"ok": True, "resumed_count": len(jobs), "status": run.status}


def retry_failed_upload_run(db: DbSession, *, run_id: str, user: Any) -> dict[str, Any]:
    run = _load_run_with_access(db, run_id, user)
    now = datetime.now(timezone.utc)
    jobs = list(
        db.scalars(
            select(Job).where(
                Job.upload_run_id == run.id,
                Job.state.in_(["failed", "cancelled"]),
            )
        ).all()
    )
    for job in jobs:
        job.state = "queued"
        job.phase = "queued"
        job.attempt = 0
        job.progress = 0
        job.cancelled_at = None
        job.completed_at = None
        job.lease_owner = None
        job.lease_expires_at = None
        job.available_at = now
        job.safe_error = {}
        job.paused_reason = None
    if jobs:
        run.status = "active"
        run.updated_at = now
    db.commit()
    get_fleet_gateway().record_fleet_event(
        level="info",
        event_type="batch_retry_failed",
        upload_run_id=run.id,
        message=f"Re-queued {len(jobs)} failed job(s) in staging batch '{run.title}'",
        db=db,
    )
    db.commit()
    return {"ok": True, "retried_count": len(jobs), "status": run.status}


def delete_upload_run(db: DbSession, *, run_id: str, user: Any) -> dict[str, Any]:
    run = _load_run_with_access(db, run_id, user)
    now = datetime.now(timezone.utc)
    jobs = list(
        db.scalars(
            select(Job).where(
                Job.upload_run_id == run.id,
                Job.state.in_(["queued", "paused_quota", "paused_user"]),
                Job.cancelled_at.is_(None),
            )
        ).all()
    )
    for job in jobs:
        job.state = "cancelled"
        job.phase = "cancelled"
        job.cancelled_at = now
        job.completed_at = now
    run.status = "cancelled"
    run.updated_at = now
    db.commit()
    return {"ok": True, "cancelled_count": len(jobs), "status": run.status}
