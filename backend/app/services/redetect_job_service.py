"""Thread-safe cancellable background job coordinator for unified Re-detect."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import logging
import threading
import time
from typing import Any, Callable, Literal

from sqlalchemy import or_, select

from app.auth.rbac import can_view_owner_record
from app.core.config import Settings
from app.core.errors import AppError
from app.db.session import SessionLocal
from app.extraction.deep_redetect_engine import RedetectCancelledError, run_deep_redetect_pipeline
from app.models.enums import Role
from app.models.tables import (
    AppSetting,
    ExtractionRecord,
    InsuranceTenure,
    QuotationDraft,
    Session as QuotationSession,
    UploadedFile,
    User,
    new_id,
)
from app.services.pdf_content import load_pdf_bytes
from app.services.quotation_reference_service import generate_quotation_reference
from app.workers.extraction_worker import load_extraction_context

logger = logging.getLogger(__name__)

_JOB_LOCK = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}
_CANCEL_EVENTS: dict[str, threading.Event] = {}
_JOB_TTL_SECONDS = 1800.0

_STEP_DEFS: tuple[tuple[str, str], ...] = (
    ("native_and_logo_crop", "PDF & Logo Crop"),
    ("brand_logo_vision", "Brand Logo Scan"),
    ("fresh_multimodal_extraction", "Multimodal AI"),
    ("cross_verify_and_audit", "Cross-Check Audit"),
    ("apply_and_sync", "Apply & Sync"),
)


def _prune_expired_jobs() -> None:
    now = time.time()
    stale = [
        jid
        for jid, j in _JOBS.items()
        if j.get("status") in {"completed", "cancelled", "failed"}
        and (now - float(j.get("_finished_ts") or now)) > _JOB_TTL_SECONDS
    ]
    for jid in stale:
        _JOBS.pop(jid, None)
        _CANCEL_EVENTS.pop(jid, None)


def _initial_steps() -> list[dict[str, str]]:
    return [{"key": k, "label": lbl, "status": "pending"} for k, lbl in _STEP_DEFS]


def _serialize_job(job: dict[str, Any]) -> dict[str, Any]:
    return {k: deepcopy(v) for k, v in job.items() if not k.startswith("_")}


def _update_job_progress(
    job_id: str,
    *,
    step_key: str,
    step_label: str,
    why_waiting: str,
    pct: int,
    detail: dict[str, Any] | None = None,
    quote_idx: int | None = None,
    quote_total: int | None = None,
    quote_name: str | None = None,
) -> None:
    with _JOB_LOCK:
        job = _JOBS.get(job_id)
        if not job or job.get("status") in {"cancelled", "failed", "completed"}:
            return
        job["progress_pct"] = max(0, min(99, pct))
        job["current_step_key"] = step_key
        job["current_step_label"] = step_label
        job["why_waiting"] = why_waiting
        if quote_idx is not None:
            job["current_quote_index"] = quote_idx
        if quote_total is not None:
            job["total_quotes"] = quote_total
        if quote_name is not None:
            job["current_quote_name"] = quote_name
        if detail:
            job["detail"] = detail

        active_idx = next((i for i, s in enumerate(job["steps"]) if s["key"] == step_key), -1)
        for idx, step in enumerate(job["steps"]):
            if idx < active_idx:
                if step["status"] == "pending":
                    step["status"] = "skipped" if step["key"] == "brand_logo_vision" else "done"
                elif step["status"] == "active":
                    step["status"] = "done"
            elif idx == active_idx:
                step["status"] = "active"


def _mark_job_terminal(
    job_id: str,
    status: Literal["completed", "cancelled", "failed"],
    *,
    why_waiting: str,
    result_summary: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    with _JOB_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        job["status"] = status
        job["finished_at"] = datetime.now(timezone.utc).isoformat()
        job["_finished_ts"] = time.time()
        job["why_waiting"] = why_waiting
        if status == "completed":
            job["progress_pct"] = 100
            for step in job["steps"]:
                if step["status"] in {"pending", "active"}:
                    step["status"] = "done"
        if result_summary is not None:
            job["result_summary"] = result_summary
        if error is not None:
            job["error"] = error


def _load_prompt_override(db) -> str | None:
    setting = db.get(AppSetting, "ai_system_prompt")
    if setting and isinstance(setting.value, dict) and str(setting.value.get("text") or "").strip():
        return str(setting.value["text"]).strip()
    return None


def _execute_single_session_redetect(
    db,
    *,
    session_id: str,
    user: User,
    settings: Settings,
    cancel_event: threading.Event,
    on_step: Callable[[str, str, str, int, dict[str, Any] | None], None],
    sync_comparison: bool = True,
) -> dict[str, Any]:
    from app.services.session_rescan_service import (
        _clear_draft_dependents,
        _extract_scalar_values_map,
        apply_gemini_result,
    )

    session = db.get(QuotationSession, session_id)
    if not session or not can_view_owner_record(db, user, session.owner_id):
        raise AppError("Session not found.", 404)
    uploaded = db.get(UploadedFile, session.uploaded_file_id)
    if not uploaded or uploaded.deleted_at is not None:
        raise AppError("Uploaded file not found or deleted.", 404)
    draft = db.get(QuotationDraft, session.draft_id)
    if not draft:
        raise AppError("Quotation draft not found.", 404)

    source_bytes = load_pdf_bytes(uploaded, settings)
    old_scalars = _extract_scalar_values_map(draft.fields)
    context = load_extraction_context(db)
    prompt_override = _load_prompt_override(db)

    result = run_deep_redetect_pipeline(
        pdf_bytes=source_bytes,
        source_filename=uploaded.original_filename or "quotation.pdf",
        current_fields=old_scalars,
        db_context=context,
        prompt_override=prompt_override,
        on_progress=on_step,
        cancel_event=cancel_event,
        batch_item_index=abs(hash(session.id)) % 100,
    )
    if cancel_event.is_set():
        raise RedetectCancelledError("Re-detection cancelled by user.")

    on_step(
        "apply_and_sync",
        "Pass 5/5 · Saving & syncing catalogs",
        "Applying verified values, preserving active discounts, pinning insurer catalog, and syncing linked comparison.",
        95,
        None,
    )

    now = datetime.now(timezone.utc)
    existing_ref = (draft.fields or {}).get("quotation_reference") or session.quotation_ref
    ref_val = existing_ref.get("value") if isinstance(existing_ref, dict) else existing_ref
    quotation_ref = str(ref_val) if ref_val else generate_quotation_reference(db, when=now)

    rec = db.scalar(select(ExtractionRecord).where(ExtractionRecord.uploaded_file_id == uploaded.id))
    _clear_draft_dependents(db, draft.id, rec.id if rec else None)
    draft.product_id = None
    draft.package_id = None
    draft.scalar_decisions = {}
    draft.warnings = []

    if rec is None:
        rec = ExtractionRecord(
            id=new_id(),
            uploaded_file_id=uploaded.id,
            method_summary=["gemini_deep_redetect"],
            raw_text=result.native_raw_text or "",
            ocr_text="",
            page_text=[],
            words=[],
            blocks=[],
            tables=[],
            images=[],
            regions=[],
            candidates={},
            benefit_lines=[],
            company_resolution={},
            warnings=[],
            reading_quality="ready",
        )
        db.add(rec)
        db.flush()

    apply_gemini_result(
        db=db,
        settings=settings,
        draft=draft,
        session=session,
        uploaded=uploaded,
        extraction=rec,
        gemini_res=result.gemini_res,
        quotation_ref=quotation_ref,
        db_companies=context.get("db_companies") or [],
        db_benefit_concepts=context.get("db_benefit_concepts") or [],
        raw_text=result.native_raw_text or "",
        brand_verdict=result.brand_verdict,
    )
    session.last_edited_by_id = user.id
    session.last_edited_at = now

    if sync_comparison and getattr(session, "tenure_id", None):
        from app.services.marketing_comparison_service import rescan_comparison_tenure

        rescan_comparison_tenure(db, session.tenure_id, deep=False)

    new_scalars = _extract_scalar_values_map(draft.fields)
    changed = sorted(
        k for k in (set(old_scalars) | set(new_scalars))
        if old_scalars.get(k, "") != new_scalars.get(k, "")
    )
    return {
        "session_id": session.id,
        "detected_company": session.detected_company,
        "changed_fields": changed,
        "passes_used": result.passes_used,
        "tenure_id": getattr(session, "tenure_id", None),
    }


def _create_job_record(
    *,
    owner_id: str,
    scope: Literal["session", "comparison"],
    target_id: str,
    total_quotes: int = 1,
) -> tuple[str, threading.Event]:
    job_id = new_id()
    cancel_event = threading.Event()
    job = {
        "job_id": job_id,
        "owner_id": owner_id,
        "scope": scope,
        "target_id": target_id,
        "status": "running",
        "progress_pct": 5,
        "current_step_key": "native_and_logo_crop",
        "current_step_label": "Initializing deep re-detection...",
        "why_waiting": "Preparing multi-pass PDF & logo verification pipeline.",
        "current_quote_index": 1,
        "total_quotes": total_quotes,
        "current_quote_name": "",
        "steps": _initial_steps(),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "result_summary": None,
        "error": None,
    }
    with _JOB_LOCK:
        _prune_expired_jobs()
        _JOBS[job_id] = job
        _CANCEL_EVENTS[job_id] = cancel_event
    return job_id, cancel_event


def _run_session_worker(
    job_id: str,
    cancel_event: threading.Event,
    session_id: str,
    user_id: str,
    user_role: str,
    user_name: str,
    settings: Settings,
    session_factory: Any,
) -> None:
    db = session_factory()
    try:
        user_obj = db.get(User, user_id) or User(id=user_id, role=user_role, name=user_name)
        summary = _execute_single_session_redetect(
            db,
            session_id=session_id,
            user=user_obj,
            settings=settings,
            cancel_event=cancel_event,
            on_step=lambda sk, sl, ww, pct, det: _update_job_progress(
                job_id, step_key=sk, step_label=sl, why_waiting=ww, pct=pct, detail=det
            ),
            sync_comparison=True,
        )
        if cancel_event.is_set():
            db.rollback()
            _mark_job_terminal(job_id, "cancelled", why_waiting="Re-detection cancelled. Existing quotation data left unchanged.")
            return
        db.commit()
        _mark_job_terminal(
            job_id,
            "completed",
            why_waiting=f"Completed {summary['passes_used']}-pass verification ({len(summary['changed_fields'])} field(s) updated).",
            result_summary=summary,
        )
    except RedetectCancelledError:
        db.rollback()
        _mark_job_terminal(job_id, "cancelled", why_waiting="Re-detection cancelled. Existing quotation data left unchanged.")
    except Exception as exc:
        db.rollback()
        logger.exception("Session deep redetect job %s failed: %s", job_id, exc)
        _mark_job_terminal(job_id, "failed", why_waiting="Re-detection stopped due to an error.", error=str(exc))
    finally:
        db.close()


def _run_comparison_worker(
    job_id: str,
    cancel_event: threading.Event,
    tenure_id: str,
    session_ids: list[str],
    quote_names: dict[str, str],
    user_id: str,
    user_role: str,
    user_name: str,
    settings: Settings,
    session_factory: Any,
) -> None:
    db = session_factory()
    try:
        user_obj = db.get(User, user_id) or User(id=user_id, role=user_role, name=user_name)
        total = max(len(session_ids), 1)
        updated_quotes: list[dict[str, Any]] = []
        for idx, sid in enumerate(session_ids, start=1):
            if cancel_event.is_set():
                raise RedetectCancelledError("Re-detection cancelled by user.")
            q_name = quote_names.get(sid) or f"Quote {idx}"

            def _on_step(sk: str, sl: str, ww: str, pct: int, det: dict[str, Any] | None, _idx: int = idx, _qn: str = q_name) -> None:
                overall_pct = int(((_idx - 1) / total) * 90 + (pct / 100.0) * (90 / total))
                _update_job_progress(
                    job_id,
                    step_key=sk,
                    step_label=f"Quote {_idx}/{total} ({_qn}) · {sl}",
                    why_waiting=ww,
                    pct=overall_pct,
                    detail=det,
                    quote_idx=_idx,
                    quote_total=total,
                    quote_name=_qn,
                )

            res = _execute_single_session_redetect(
                db,
                session_id=sid,
                user=user_obj,
                settings=settings,
                cancel_event=cancel_event,
                on_step=_on_step,
                sync_comparison=False,
            )
            updated_quotes.append(res)

        if cancel_event.is_set():
            db.rollback()
            _mark_job_terminal(job_id, "cancelled", why_waiting="Re-detection cancelled. Existing comparison data left unchanged.")
            return

        _update_job_progress(
            job_id,
            step_key="apply_and_sync",
            step_label="Refreshing comparison matrix & rankings",
            why_waiting="Re-calculating towing entitlements, betterment caps, discounts, and winner ranking.",
            pct=95,
        )
        from app.services.marketing_comparison_service import rescan_comparison_tenure

        rescan_comparison_tenure(db, tenure_id, deep=False)
        db.commit()
        _mark_job_terminal(
            job_id,
            "completed",
            why_waiting=f"Completed deep verification across {len(updated_quotes)} quotation(s).",
            result_summary={"tenure_id": tenure_id, "updated_quotes": updated_quotes},
        )
    except RedetectCancelledError:
        db.rollback()
        _mark_job_terminal(job_id, "cancelled", why_waiting="Re-detection cancelled. Existing comparison data left unchanged.")
    except Exception as exc:
        db.rollback()
        logger.exception("Comparison deep redetect job %s failed: %s", job_id, exc)
        _mark_job_terminal(job_id, "failed", why_waiting="Re-detection stopped due to an error.", error=str(exc))
    finally:
        db.close()


def start_session_redetect_job(
    db,
    session_id: str,
    user: User,
    settings: Settings,
    *,
    session_factory: Any = SessionLocal,
    run_sync: bool = False,
) -> dict[str, Any]:
    session = db.get(QuotationSession, session_id)
    if not session or not can_view_owner_record(db, user, session.owner_id):
        raise AppError("Session not found.", 404)
    uploaded = db.get(UploadedFile, session.uploaded_file_id)
    if not uploaded or uploaded.deleted_at is not None:
        raise AppError("Uploaded file not found or deleted.", 404)

    job_id, cancel_event = _create_job_record(
        owner_id=user.id,
        scope="session",
        target_id=session_id,
        total_quotes=1,
    )
    _update_job_progress(
        job_id,
        step_key="native_and_logo_crop",
        step_label="Pass 1/4 · Reading PDF text & cropping logo",
        why_waiting="Preparing multi-pass PDF & logo verification pipeline.",
        pct=8,
        quote_idx=1,
        quote_total=1,
        quote_name=session.detected_company or uploaded.original_filename or "Quotation",
    )
    args = (job_id, cancel_event, session_id, user.id, user.role, user.name or "User", settings, session_factory)
    if run_sync:
        _run_session_worker(*args)
    else:
        threading.Thread(target=_run_session_worker, args=args, daemon=True).start()
    return {"job_id": job_id, "job": get_redetect_job(job_id, user)}


def start_comparison_redetect_job(
    db,
    tenure_id: str,
    user: User,
    settings: Settings,
    *,
    session_id: str | None = None,
    session_factory: Any = SessionLocal,
    run_sync: bool = False,
) -> dict[str, Any]:
    from app.services.marketing_comparison.covernote_classifier import is_covernote_document

    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise AppError("Comparison tenure not found.", 404)
    sessions = list(
        db.scalars(
            select(QuotationSession).where(
                or_(
                    QuotationSession.tenure_id == tenure.id,
                    QuotationSession.tracked_vehicle_id == tenure.tracked_vehicle_id,
                )
            )
        ).all()
    )
    targets = [
        s for s in sessions
        if s.status != "trash"
        and not is_covernote_document(s, db)
        and s.is_tenure_active is not False
        and getattr(s, "uploaded_file_id", None)
        and (session_id is None or s.id == session_id)
    ]
    if not targets:
        raise AppError("No active quotation PDFs available to re-detect under this comparison.", 400)

    session_ids = [s.id for s in targets]
    quote_names = {s.id: (s.detected_company or s.quotation_ref or "Quotation") for s in targets}

    job_id, cancel_event = _create_job_record(
        owner_id=user.id,
        scope="comparison",
        target_id=tenure_id,
        total_quotes=len(session_ids),
    )
    args = (job_id, cancel_event, tenure_id, session_ids, quote_names, user.id, user.role, user.name or "User", settings, session_factory)
    if run_sync:
        _run_comparison_worker(*args)
    else:
        threading.Thread(target=_run_comparison_worker, args=args, daemon=True).start()
    return {"job_id": job_id, "job": get_redetect_job(job_id, user)}


def _require_job_access(job: dict[str, Any], user: User) -> None:
    is_admin = (getattr(user, "role", "") or "").lower() in {
        Role.SUPER_ADMIN.value,
        Role.ADMIN.value,
        Role.DEV.value,
    }
    if not is_admin and job.get("owner_id") != getattr(user, "id", None):
        raise AppError("Redetect job not found.", 404)


def get_redetect_job(job_id: str, user: User) -> dict[str, Any]:
    with _JOB_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            raise AppError("Redetect job not found.", 404)
        _require_job_access(job, user)
        return _serialize_job(job)


def cancel_redetect_job(job_id: str, user: User) -> dict[str, Any]:
    with _JOB_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            raise AppError("Redetect job not found.", 404)
        _require_job_access(job, user)
        ev = _CANCEL_EVENTS.get(job_id)
        if ev is not None:
            ev.set()
        if job.get("status") == "running":
            job["why_waiting"] = "Cancelling safely — existing values will remain untouched..."
        return {"cancelled": True, "job": _serialize_job(job)}
