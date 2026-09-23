"""Quotation Activity and Hit & Miss Tracking Service."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, defer, joinedload

from app.core.cache import _memory_cache, invalidate_cache

from app.models.tables import (
    GeneratedPdfVersion,
    QuotationActivity,
    QuotationDraft,
    Session as SessionModel,
    TrackedVehicle,
    User,
    new_id,
    utcnow,
)
from app.services.vehicle_tracking_service import get_or_create_vehicle_tracking, normalize_plate, parse_date_safe

CANONICAL_MISS_REASONS = [
    "Price too high / Competitor cheaper",
    "Client renewed elsewhere",
    "Delay in decision / Thinking over",
    "Vehicle sold / Transfer of ownership",
    "Client unreachable / No response",
    "Purchased directly with insurer",
    "Other",
]


def log_quotation_activity(
    db: Session,
    session_id: str,
    action_type: str,
    user_id: str | None = None,
    sent_to_client: bool = False,
    summary: str = "",
    addons_snapshot: list[dict] | None = None,
    version_number: int = 1,
    status: str = "pending",
    won_premium: float | None = None,
    miss_reason: str | None = None,
    notes: str | None = None,
    timestamp: datetime | None = None,
) -> QuotationActivity | None:
    """Log an activity event for a quotation session in the calendar ledger."""
    session = db.get(SessionModel, session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found.")

    if getattr(session, "is_test", False):
        # Test sessions are isolated from Hit & Miss activities and vehicle tracking
        return None

    draft_fields = session.draft.fields if session.draft and session.draft.fields else {}
    plate = normalize_plate(draft_fields.get("vehicle_no", {}).get("value") or "")
    customer = (draft_fields.get("customer_name", {}).get("value") or "").strip()

    # Link tracked vehicle if not already linked
    if not session.tracked_vehicle_id and plate:
        valid_until = draft_fields.get("valid_until", {}).get("value") or draft_fields.get("cover_end_date", {}).get("value")
        veh, _ = get_or_create_vehicle_tracking(db, plate, customer, valid_until, session.id)
        if veh:
            session.tracked_vehicle_id = veh.id

    now_ts = timestamp or utcnow()

    activity = QuotationActivity(
        id=new_id(),
        session_id=session.id,
        vehicle_no=plate or "UNKNOWN",
        customer_name=customer or None,
        action_type=action_type,
        timestamp=now_ts,
        version_number=version_number,
        sent_to_client=sent_to_client,
        summary=summary or f"Quotation {action_type.replace('_', ' ').capitalize()}",
        addons_snapshot=addons_snapshot or [],
        status=status or session.quotation_status or "pending",
        miss_reason=miss_reason or session.miss_reason,
        won_premium=won_premium,
        notes=notes,
        user_id=user_id,
    )
    db.add(activity)
    db.flush()
    invalidate_cache("calendar:")
    return activity


def get_calendar_activities(
    db: Session,
    date_from: str | None = None,
    date_to: str | None = None,
    search: str | None = None,
    status: str | None = None,
    sent_only: bool = False,
    vehicle_no: str | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    """Retrieve activities grouped by date (YYYY-MM-DD) for the Hit & Miss calendar view."""
    cache_key = f"calendar:{date_from}:{date_to}:{search}:{status}:{sent_only}:{vehicle_no}:{limit}"
    cached = _memory_cache.get(cache_key)
    if cached is not None:
        return cached

    stmt = (
        select(QuotationActivity)
        .join(SessionModel, QuotationActivity.session_id == SessionModel.id)
        .where(SessionModel.is_test.is_(False))
        .options(
            joinedload(QuotationActivity.user),
            joinedload(QuotationActivity.session)
            .joinedload(SessionModel.draft)
            .defer(QuotationDraft.scalar_decisions)
            .defer(QuotationDraft.warnings)
            .defer(QuotationDraft.layout_override)
            .defer(QuotationDraft.display_options),
        )
        .order_by(QuotationActivity.timestamp.desc())
    )

    if date_from:
        dt_from = parse_date_safe(date_from)
        if dt_from:
            stmt = stmt.where(QuotationActivity.timestamp >= dt_from.replace(tzinfo=timezone.utc))
    if date_to:
        dt_to = parse_date_safe(date_to)
        if dt_to:
            stmt = stmt.where(QuotationActivity.timestamp <= dt_to.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc))

    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                QuotationActivity.vehicle_no.ilike(term),
                QuotationActivity.customer_name.ilike(term),
                QuotationActivity.summary.ilike(term),
            )
        )

    if status and status.lower() != "all":
        stmt = stmt.where(QuotationActivity.status == status.lower())

    if sent_only:
        stmt = stmt.where(QuotationActivity.sent_to_client.is_(True))

    if vehicle_no:
        norm = normalize_plate(vehicle_no)
        stmt = stmt.where(QuotationActivity.vehicle_no == norm)

    stmt = stmt.limit(limit)
    rows = list(db.scalars(stmt).all())

    # Group by date string YYYY-MM-DD
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for a in rows:
        d_str = a.timestamp.strftime("%Y-%m-%d") if a.timestamp else "Undated"
        time_str = a.timestamp.strftime("%I:%M %p") if a.timestamp else "--:--"

        # Get detected company & premium from session if available
        company = a.session.detected_company if a.session else ""
        draft_fields = a.session.draft.fields if a.session and a.session.draft else {}
        total_premium = draft_fields.get("total_amount", {}).get("value") or ""

        grouped[d_str].append(
            {
                "id": a.id,
                "session_id": a.session_id,
                "vehicle_no": a.vehicle_no,
                "customer_name": a.customer_name or "Unknown",
                "action_type": a.action_type,
                "timestamp": a.timestamp.isoformat() if a.timestamp else None,
                "time_display": time_str,
                "version_number": a.version_number,
                "sent_to_client": a.sent_to_client,
                "summary": a.summary,
                "addons_snapshot": a.addons_snapshot or [],
                "status": a.status,
                "miss_reason": a.miss_reason,
                "won_premium": float(a.won_premium) if a.won_premium is not None else None,
                "total_premium": total_premium,
                "company": company,
                "notes": a.notes,
                "user_email": a.user.email if a.user else None,
            }
        )

    result = {
        "dates": dict(grouped),
        "total_activities": len(rows),
    }
    _memory_cache.set(cache_key, result, ttl_seconds=60.0)
    return result


def update_quotation_status(
    db: Session,
    session_id: str,
    status: str,
    miss_reason: str | None = None,
    won_premium: float | None = None,
    notes: str | None = None,
    user_id: str | None = None,
    coverage_start_date: str | None = None,
    coverage_end_date: str | None = None,
    require_won_premium: bool = True,
) -> dict[str, Any]:
    """Update quotation outcome status to Hit, Miss, or Superseded with closing audit trail and policy period tracking."""
    from datetime import timedelta
    from app.models.tables import VehicleOwnership, TrackedVehicle

    session = db.get(SessionModel, session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found.")

    clean_status = status.strip().lower()
    if clean_status not in ("pending", "hit", "miss", "superseded"):
        raise ValueError("Invalid status: must be 'pending', 'hit', 'miss', or 'superseded'.")

    # Completeness Validation Gate: Incomplete sessions cannot be closed as Hit or Miss
    if clean_status in ("hit", "miss"):
        draft_fields = session.draft.fields if session.draft and session.draft.fields else {}
        plate = normalize_plate(
            draft_fields.get("vehicle_no", {}).get("value")
            or draft_fields.get("vehicle_registration_no", {}).get("value")
            or draft_fields.get("plate_number", {}).get("value")
            or draft_fields.get("car_plate", {}).get("value")
            or ""
        )
        if not plate or plate.upper() == "UNKNOWN":
            tracked_veh = session.tracked_vehicle or (db.get(TrackedVehicle, session.tracked_vehicle_id) if session.tracked_vehicle_id else None)
            if tracked_veh and tracked_veh.vehicle_no:
                plate = normalize_plate(tracked_veh.vehicle_no)

        customer = (
            draft_fields.get("customer_name", {}).get("value")
            or draft_fields.get("client_name", {}).get("value")
            or draft_fields.get("insured_name", {}).get("value")
            or draft_fields.get("company_name", {}).get("value")
            or draft_fields.get("name", {}).get("value")
            or ""
        ).strip()

        if not customer or customer.lower() == "unknown":
            ownership = None
            if session.tracked_vehicle_id:
                ownership = db.scalar(
                    select(VehicleOwnership)
                    .where(VehicleOwnership.vehicle_id == session.tracked_vehicle_id, VehicleOwnership.is_current.is_(True))
                    .order_by(VehicleOwnership.sequence_order.desc())
                )
            if not ownership:
                ownership = db.scalar(
                    select(VehicleOwnership)
                    .where(VehicleOwnership.source_session_id == session.id)
                    .order_by(VehicleOwnership.created_at.desc())
                )
            if ownership and ownership.customer_name:
                customer = ownership.customer_name.strip()

        if not plate or plate.upper() == "UNKNOWN":
            raise ValueError("Cannot finalize quotation status: Missing vehicle registration number (plate). Please review and enter vehicle plate.")
        if not customer or customer.lower() == "unknown":
            raise ValueError("Cannot finalize quotation status: Missing customer name. Please review and enter customer name.")

        if clean_status == "hit" and require_won_premium:
            parsed_prem = won_premium
            if parsed_prem is None:
                prem_candidates = [
                    draft_fields.get("won_premium", {}).get("value"),
                    draft_fields.get("total_amount", {}).get("value"),
                    draft_fields.get("gross_premium", {}).get("value"),
                    draft_fields.get("total_premium", {}).get("value"),
                    draft_fields.get("total_premium_adjusted", {}).get("value"),
                    draft_fields.get("premium", {}).get("value"),
                    draft_fields.get("net_premium", {}).get("value"),
                ]

                import re
                for cand in prem_candidates:
                    if cand is not None:
                        try:
                            cleaned = re.sub(r"[^0-9.]", "", str(cand))
                            val = float(cleaned) if cleaned else None
                            if val is not None and val > 0:
                                parsed_prem = val
                                break
                        except (ValueError, TypeError):
                            pass

            if parsed_prem is None or parsed_prem <= 0:
                raise ValueError("Cannot mark as HIT: Winning policy premium amount is required.")

    session.quotation_status = clean_status
    if clean_status in ("hit", "miss", "superseded"):
        session.closed_at = utcnow()
        if clean_status == "miss":
            session.miss_reason = (miss_reason or "").strip() or "Client did not take up policy"
        else:
            session.miss_reason = None
    else:
        session.closed_at = None
        session.miss_reason = None

    if getattr(session, "is_test", False):
        # Test sessions update status locally without vehicle tracking, ownership mutation, or activity logs
        db.flush()
        return {
            "session_id": session.id,
            "quotation_status": session.quotation_status,
            "closed_at": session.closed_at.isoformat() if session.closed_at else None,
            "miss_reason": session.miss_reason,
            "coverage_start_date": None,
            "coverage_end_date": None,
        }

    # Coverage period update on Session & VehicleOwnership
    parsed_start = parse_date_safe(coverage_start_date) if coverage_start_date else None
    parsed_end = parse_date_safe(coverage_end_date) if coverage_end_date else None

    if clean_status == "hit":
        if parsed_start:
            session.coverage_start_date = parsed_start.replace(tzinfo=timezone.utc)
        if parsed_end:
            session.coverage_end_date = parsed_end.replace(tzinfo=timezone.utc)

        # Ensure tracked vehicle linkage
        draft_fields = session.draft.fields if session.draft and session.draft.fields else {}
        plate = normalize_plate(draft_fields.get("vehicle_no", {}).get("value") or "")
        customer = (draft_fields.get("customer_name", {}).get("value") or "").strip()

        if not session.tracked_vehicle_id and plate:
            veh, _ = get_or_create_vehicle_tracking(db, plate, customer, None, session.id)
            if veh:
                session.tracked_vehicle_id = veh.id

        # Update VehicleOwnership policy duration & 9-month renewal reminder date
        if session.tracked_vehicle_id:
            ownership = db.scalar(
                select(VehicleOwnership)
                .where(VehicleOwnership.vehicle_id == session.tracked_vehicle_id, VehicleOwnership.is_current.is_(True))
                .order_by(VehicleOwnership.sequence_order.desc())
            )
            if ownership:
                if session.coverage_start_date:
                    ownership.coverage_start_date = session.coverage_start_date
                if session.coverage_end_date:
                    ownership.coverage_end_date = session.coverage_end_date
                    ownership.renewal_alert_date = session.coverage_end_date - timedelta(days=90)
                ownership.policy_status = "active"
                ownership.source_session_id = session.id

        # Multi-Quote Resolution: Mark sibling sessions for same vehicle in same deal cycle/renewal as superseded
        siblings: list[SessionModel] = []
        if session.tracked_vehicle_id:
            sibling_stmt = (
                select(SessionModel)
                .where(
                    SessionModel.tracked_vehicle_id == session.tracked_vehicle_id,
                    SessionModel.id != session.id,
                    SessionModel.quotation_status == "pending",
                    SessionModel.status != "trash",
                )
            )
            # Limit to 60-day window around this quotation
            if session.created_at:
                sibling_stmt = sibling_stmt.where(
                    SessionModel.created_at >= session.created_at - timedelta(days=60),
                    SessionModel.created_at <= session.created_at + timedelta(days=60),
                )
            siblings = list(db.scalars(sibling_stmt).all())

        # Also search for pending sessions matching the same vehicle plate whose tracked_vehicle_id wasn't linked yet
        if plate:
            seen_ids = {s.id for s in siblings}
            seen_ids.add(session.id)
            unlinked_query = (
                select(SessionModel)
                .where(
                    SessionModel.id.notin_(seen_ids),
                    SessionModel.quotation_status == "pending",
                    SessionModel.status != "trash",
                )
            )
            if session.created_at:
                unlinked_query = unlinked_query.where(
                    SessionModel.created_at >= session.created_at - timedelta(days=60),
                    SessionModel.created_at <= session.created_at + timedelta(days=60),
                )
            for candidate in db.scalars(unlinked_query).all():
                c_fields = candidate.draft.fields if candidate.draft and candidate.draft.fields else {}
                c_plate = normalize_plate(c_fields.get("vehicle_no", {}).get("value") or "")
                if c_plate == plate:
                    if session.tracked_vehicle_id:
                        candidate.tracked_vehicle_id = session.tracked_vehicle_id
                    siblings.append(candidate)

        for sib in siblings:
            sib.quotation_status = "superseded"
            sib.closed_at = utcnow()
            log_quotation_activity(
                db=db,
                session_id=sib.id,
                action_type="status_superseded",
                user_id=user_id,
                sent_to_client=False,
                summary=f"Superceded by winning {session.detected_company or 'Insurer'} quotation",
                status="superseded",
                notes=f"Vehicle deal won via session {session.id[:8]} ({session.detected_company or 'Insurer'})",
            )

    # Log activity for this status change
    action_type = f"status_{clean_status}"
    summary_text = (
        f"Marked quotation as HIT (Won Policy)"
        if clean_status == "hit"
        else f"Marked quotation as MISS ({session.miss_reason})"
        if clean_status == "miss"
        else f"Marked quotation as Superceded"
        if clean_status == "superseded"
        else "Reopened quotation as Pending"
    )

    log_quotation_activity(
        db=db,
        session_id=session.id,
        action_type=action_type,
        user_id=user_id,
        sent_to_client=False,
        summary=summary_text,
        status=clean_status,
        won_premium=won_premium,
        miss_reason=session.miss_reason,
        notes=notes,
    )
    db.flush()

    return {
        "session_id": session.id,
        "quotation_status": session.quotation_status,
        "closed_at": session.closed_at.isoformat() if session.closed_at else None,
        "miss_reason": session.miss_reason,
        "coverage_start_date": session.coverage_start_date.isoformat() if session.coverage_start_date else None,
        "coverage_end_date": session.coverage_end_date.isoformat() if session.coverage_end_date else None,
    }


def bulk_update_quotation_status(
    db: Session,
    session_ids: list[str],
    status: str,
    miss_reason: str | None = None,
    won_premium: float | None = None,
    notes: str | None = None,
    user_id: str | None = None,
    coverage_start_date: str | None = None,
    coverage_end_date: str | None = None,
) -> dict[str, Any]:
    """Bulk update quotation status across multiple sessions (e.g. corporate fleet wins or losses)."""
    updated: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for sid in session_ids:
        try:
            res = update_quotation_status(
                db=db,
                session_id=sid,
                status=status,
                miss_reason=miss_reason,
                won_premium=won_premium,
                notes=notes,
                user_id=user_id,
                coverage_start_date=coverage_start_date,
                coverage_end_date=coverage_end_date,
                require_won_premium=(won_premium is not None),
            )
            updated.append(res)
        except Exception as exc:
            errors.append({"session_id": sid, "error": str(exc)})

    db.commit()
    return {
        "updated_count": len(updated),
        "error_count": len(errors),
        "target_status": status,
        "results": updated,
        "errors": errors,
    }


def get_insights_analytics(
    db: Session,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """Compute high-signal conversion metrics, hit rate, won/lost premium, and loss reasons."""
    stmt = select(SessionModel).options(joinedload(SessionModel.draft)).where(SessionModel.is_test.is_(False))
    if date_from:
        dt_from = parse_date_safe(date_from)
        if dt_from:
            stmt = stmt.where(SessionModel.created_at >= dt_from.replace(tzinfo=timezone.utc))
    if date_to:
        dt_to = parse_date_safe(date_to)
        if dt_to:
            stmt = stmt.where(SessionModel.created_at <= dt_to.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc))

    sessions = list(db.scalars(stmt).all())
    total_sessions = len(sessions)

    hits = [s for s in sessions if (s.quotation_status or "").lower() == "hit"]
    misses = [s for s in sessions if (s.quotation_status or "").lower() == "miss"]
    superseded = [s for s in sessions if (s.quotation_status or "").lower() == "superseded"]
    pending = [s for s in sessions if (s.quotation_status or "").lower() not in ("hit", "miss", "superseded")]

    closed_count = len(hits) + len(misses)
    hit_rate = round((len(hits) / closed_count * 100), 1) if closed_count > 0 else 0.0

    # Calculate won and lost premiums
    def parse_money(val: Any) -> float:
        if not val:
            return 0.0
        try:
            cleaned = str(val).replace("RM", "").replace(",", "").strip()
            return float(Decimal(cleaned))
        except Exception:
            return 0.0

    won_premium_total = sum(
        parse_money((s.draft.fields.get("total_amount", {}).get("value") if s.draft else 0))
        for s in hits
    )

    lost_premium_total = sum(
        parse_money((s.draft.fields.get("total_amount", {}).get("value") if s.draft else 0))
        for s in misses
    )

    # Miss reasons breakdown
    reason_counts: dict[str, int] = defaultdict(int)
    for m in misses:
        r = m.miss_reason or "Unspecified"
        reason_counts[r] += 1

    # Insurer distribution for Hits
    company_hits: dict[str, int] = defaultdict(int)
    for h in hits:
        c = h.detected_company or "Other"
        company_hits[c] += 1

    # Sent to client count from activities
    sent_sessions_count = db.scalar(
        select(func.count(func.distinct(QuotationActivity.session_id))).where(QuotationActivity.sent_to_client.is_(True))
    ) or 0

    from app.services.vehicle_tracking_service import get_upcoming_renewals
    upcoming_renewals = get_upcoming_renewals(db, days_ahead=90)

    # Monthly breakdown aggregation (YYYY-MM)
    monthly_map: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "month_key": "",
            "month_label": "",
            "total_quotations": 0,
            "hits_count": 0,
            "misses_count": 0,
            "superseded_count": 0,
            "pending_count": 0,
            "won_premium_total": 0.0,
            "lost_premium_total": 0.0,
            "hit_rate_percent": 0.0,
        }
    )

    for s in sessions:
        ts = s.created_at or utcnow()
        m_key = ts.strftime("%Y-%m")
        m_label = ts.strftime("%B %Y")
        st = (s.quotation_status or "").lower()
        amt = parse_money(s.draft.fields.get("total_amount", {}).get("value") if s.draft and s.draft.fields else 0)

        entry = monthly_map[m_key]
        entry["month_key"] = m_key
        entry["month_label"] = m_label
        entry["total_quotations"] += 1
        if st == "hit":
            entry["hits_count"] += 1
            entry["won_premium_total"] += amt
        elif st == "miss":
            entry["misses_count"] += 1
            entry["lost_premium_total"] += amt
        elif st == "superseded":
            entry["superseded_count"] += 1
        else:
            entry["pending_count"] += 1

    monthly_breakdown: list[dict[str, Any]] = []
    for m_key in sorted(monthly_map.keys(), reverse=True):
        m = monthly_map[m_key]
        m_closed = m["hits_count"] + m["misses_count"]
        m["hit_rate_percent"] = round((m["hits_count"] / m_closed * 100), 1) if m_closed > 0 else 0.0
        m["won_premium_total"] = round(m["won_premium_total"], 2)
        m["lost_premium_total"] = round(m["lost_premium_total"], 2)
        monthly_breakdown.append(m)

    return {
        "total_quotations": total_sessions,
        "hits_count": len(hits),
        "misses_count": len(misses),
        "superseded_count": len(superseded),
        "pending_count": len(pending),
        "hit_rate_percent": hit_rate,
        "sent_to_client_count": sent_sessions_count,
        "upcoming_renewals_count": len(upcoming_renewals),
        "won_premium_total": round(won_premium_total, 2),
        "lost_premium_total": round(lost_premium_total, 2),
        "miss_reasons": dict(reason_counts),
        "company_hits": dict(company_hits),
        "monthly_breakdown": monthly_breakdown,
    }


def preview_backfill_sessions(db: Session) -> dict[str, Any]:
    """Inspect all database sessions and classify them into ready vs ambiguous for user review."""
    sessions = list(
        db.scalars(
            select(SessionModel)
            .where(SessionModel.is_test.is_(False))
            .options(
                joinedload(SessionModel.draft),
                joinedload(SessionModel.uploaded_file),
            )
            .order_by(SessionModel.created_at.desc())
        ).all()
    )

    items: list[dict[str, Any]] = []
    ready_count = 0
    ambiguous_count = 0

    for s in sessions:
        draft_fields = s.draft.fields if s.draft and s.draft.fields else {}
        raw_plate = draft_fields.get("vehicle_no", {}).get("value")
        norm_plate = normalize_plate(raw_plate)
        customer = (draft_fields.get("customer_name", {}).get("value") or "").strip()
        valid_until = draft_fields.get("valid_until", {}).get("value") or draft_fields.get("cover_end_date", {}).get("value")
        model = draft_fields.get("car_model", {}).get("value")
        company = s.detected_company or draft_fields.get("insurance_company", {}).get("value") or "Unknown"
        premium = draft_fields.get("total_amount", {}).get("value") or ""
        created_str = s.created_at.strftime("%Y-%m-%d %I:%M %p") if s.created_at else ""

        issues: list[str] = []
        if not norm_plate:
            issues.append("Missing or unreadable vehicle registration plate")
        if not customer:
            issues.append("Missing customer name")

        is_ready = len(issues) == 0
        if is_ready:
            ready_count += 1
            existing_veh = db.scalar(select(TrackedVehicle).where(TrackedVehicle.vehicle_no == norm_plate))
            if existing_veh:
                if existing_veh.current_owner and existing_veh.current_owner.customer_name != customer:
                    proposed_action = f"Sequential Reassignment: Reassign {norm_plate} to {customer}"
                else:
                    proposed_action = f"Link to existing vehicle ({norm_plate})"
            else:
                proposed_action = f"Create new tracked vehicle ({norm_plate})"
        else:
            ambiguous_count += 1
            proposed_action = "Requires manual correction or omission"

        items.append(
            {
                "session_id": s.id,
                "quotation_number": (s.draft.fields.get("quotation_no", {}).get("value") if s.draft and s.draft.fields else None)
                or f"RL-{s.id[:8].upper()}",
                "created_at": created_str,
                "raw_plate": raw_plate or "",
                "normalized_plate": norm_plate or "",
                "customer_name": customer,
                "validity_date": valid_until or "",
                "model": model or "",
                "company": company,
                "premium": premium,
                "status": s.quotation_status or "pending",
                "is_ready": is_ready,
                "issues": issues,
                "proposed_action": proposed_action,
            }
        )

    return {
        "total_detected": len(sessions),
        "ready_count": ready_count,
        "ambiguous_count": ambiguous_count,
        "sessions": items,
    }


def backfill_existing_sessions(
    db: Session,
    session_ids: list[str] | None = None,
    manual_overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, int]:
    """Scan database sessions (optionally filtered to confirmed session_ids) and track vehicles, ownerships, and activities."""
    stmt = (
        select(SessionModel)
        .where(SessionModel.is_test.is_(False))
        .options(
            joinedload(SessionModel.draft),
            joinedload(SessionModel.uploaded_file),
        )
        .order_by(SessionModel.created_at.asc())
    )
    if session_ids is not None:
        stmt = stmt.where(SessionModel.id.in_(session_ids))

    sessions = list(db.scalars(stmt).all())
    manual_overrides = manual_overrides or {}

    processed = 0
    vehicles_tracked = 0
    activities_created = 0

    for s in sessions:
        processed += 1
        draft_fields = s.draft.fields if s.draft and s.draft.fields else {}
        overrides = manual_overrides.get(s.id, {})

        raw_plate = overrides.get("vehicle_no") or draft_fields.get("vehicle_no", {}).get("value")
        norm_plate = normalize_plate(raw_plate)
        customer = (overrides.get("customer_name") or draft_fields.get("customer_name", {}).get("value") or "").strip()
        valid_until = (
            overrides.get("validity_date")
            or draft_fields.get("valid_until", {}).get("value")
            or draft_fields.get("cover_end_date", {}).get("value")
        )
        model = draft_fields.get("car_model", {}).get("value")
        brand = draft_fields.get("car_brand", {}).get("value")

        if norm_plate:
            veh, _ = get_or_create_vehicle_tracking(
                db=db,
                vehicle_no=norm_plate,
                customer_name=customer,
                validity_date=valid_until,
                session_id=s.id,
                brand=brand,
                model=model,
            )
            if veh:
                vehicles_tracked += 1
                s.tracked_vehicle_id = veh.id

        # Check if activities already exist
        existing_act = db.scalar(select(func.count(QuotationActivity.id)).where(QuotationActivity.session_id == s.id)) or 0
        if existing_act == 0:
            created_ts = s.created_at or utcnow()
            # 1. Initial scan activity
            a1 = QuotationActivity(
                id=new_id(),
                session_id=s.id,
                vehicle_no=norm_plate or "UNKNOWN",
                customer_name=customer or None,
                action_type="upload_scan",
                timestamp=created_ts,
                version_number=1,
                sent_to_client=False,
                summary=f"Scanned quotation for {norm_plate or 'vehicle'}" + (f" ({customer})" if customer else ""),
                status=s.quotation_status or "pending",
                user_id=s.owner_id,
            )
            db.add(a1)
            activities_created += 1

            # 2. Check generated pdf versions
            pdf_versions = list(
                db.scalars(
                    select(GeneratedPdfVersion)
                    .where(GeneratedPdfVersion.draft_id == s.draft_id)
                    .order_by(GeneratedPdfVersion.version_number.asc())
                ).all()
            )
            for v in pdf_versions:
                v_ts = v.created_at or created_ts
                a_v = QuotationActivity(
                    id=new_id(),
                    session_id=s.id,
                    vehicle_no=norm_plate or "UNKNOWN",
                    customer_name=customer or None,
                    action_type="quote_generated",
                    timestamp=v_ts,
                    version_number=v.version_number,
                    sent_to_client=True,
                    summary=f"Generated PDF version {v.version_number}",
                    status=s.quotation_status or "pending",
                    user_id=s.owner_id,
                )
                db.add(a_v)
                activities_created += 1

    db.flush()
    return {
        "sessions_processed": processed,
        "vehicles_tracked": vehicles_tracked,
        "activities_created": activities_created,
    }
