"""Insurance Tenure Service.

Manages the core lifecycle of motor insurance tenures:
- Identifies and groups quotations by customer, vehicle, and 1-year coverage window.
- Computes deterministic quotation content hashes for zero-change deduplication.
- Progresses insurer quotation versions (v1 -> v2) when modifications occur.
- Compiles the timeline ledger (sourced insurer quotes, generated RL quotes, sent tracking, hit/miss).
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.tables import (
    InsuranceCompany,
    InsuranceTenure,
    QuotationActivity,
    QuotationDraft,
    Session as SessionModel,
    TenureComparisonEntry,
    TrackedVehicle,
    VehicleOwnership,
    new_id,
)
from app.services.vehicle_tracking_service import normalize_plate, parse_date_safe


def compute_quotation_content_hash(
    fields: dict[str, Any] | None,
    benefits: list[Any] | None = None,
    costing: dict[str, Any] | None = None,
) -> str:
    """Compute a deterministic SHA-256 hash of core quotation figures and perils.

    Two quotes with identical price, sum insured, company, dates, and benefits
    yield the exact same hash, allowing 100% zero-change deduplication.
    """
    if not fields:
        return ""

    def _val(key: str) -> str:
        f = fields.get(key)
        if isinstance(f, dict):
            return str(f.get("value") or "").strip()
        return str(f or "").strip()

    def _clean_num(val_str: str) -> str:
        cleaned = re.sub(r"[^\d.]", "", val_str)
        try:
            return f"{float(cleaned):.2f}"
        except Exception:
            return val_str.lower().strip()

    norm_company = _val("insurance_company").lower()
    norm_plate = normalize_plate(_val("vehicle_no") or _val("vehicle_number"))
    norm_premium = _clean_num(_val("premium") or _val("insurance_premium"))
    norm_total = _clean_num(_val("total_amount") or _val("total_payable") or _val("final_payable"))
    norm_sum_insured = _clean_num(_val("sum_insured") or _val("coverage_amount"))
    norm_start = _val("cover_start_date") or _val("issue_date")
    norm_end = _val("cover_end_date") or _val("valid_until")

    # Normalized benefit identifiers and costs
    norm_benefits: list[str] = []
    if benefits:
        for b in benefits:
            if isinstance(b, dict):
                code = str(b.get("concept_code") or b.get("benefit_code") or b.get("title") or "").strip().lower()
                cost = _clean_num(str(b.get("cost") or b.get("price") or "0"))
                if code:
                    norm_benefits.append(f"{code}:{cost}")
            elif isinstance(b, str):
                norm_benefits.append(b.strip().lower())
    norm_benefits.sort()

    payload = {
        "company": norm_company,
        "plate": norm_plate,
        "premium": norm_premium,
        "total": norm_total,
        "sum_insured": norm_sum_insured,
        "start": norm_start,
        "end": norm_end,
        "benefits": norm_benefits,
    }
    raw_str = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()


def normalize_tenure_dates(
    start_date: datetime | str | None,
    end_date: datetime | str | None,
) -> tuple[datetime, datetime, str]:
    """Resolve normalized coverage start date, end date (+1 year), and expiry month.

    Example:
        Start 08/09/2026 -> End 07/09/2027 -> Expiry Month: '2027-09'
    """
    now = datetime.now(timezone.utc)
    start_dt: datetime | None = None
    end_dt: datetime | None = None

    if isinstance(start_date, datetime):
        start_dt = start_date
    elif isinstance(start_date, str):
        start_dt = parse_date_safe(start_date)

    if isinstance(end_date, datetime):
        end_dt = end_date
    elif isinstance(end_date, str):
        end_dt = parse_date_safe(end_date)

    # Ensure timezone awareness
    if start_dt and start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)
    if end_dt and end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)

    if start_dt and not end_dt:
        end_dt = start_dt + timedelta(days=364)
    elif end_dt and not start_dt:
        start_dt = end_dt - timedelta(days=364)
    elif not start_dt and not end_dt:
        start_dt = now
        end_dt = now + timedelta(days=364)

    assert start_dt is not None
    assert end_dt is not None

    # Expiry month is anchored on policy end date (e.g. '2027-09')
    expiry_month = end_dt.strftime("%Y-%m")
    return start_dt, end_dt, expiry_month


def resolve_or_create_tenure(
    db: Session,
    *,
    vehicle_no: str,
    customer_name: str,
    start_date: datetime | str | None,
    end_date: datetime | str | None,
    tracked_vehicle_id: str | None = None,
    ownership_id: str | None = None,
    customer_id: str | None = None,
    chassis_no: str | None = None,
    engine_no: str | None = None,
    created_by_id: str | None = None,
) -> InsuranceTenure:
    """Find existing InsuranceTenure matching the vehicle and coverage dates or create one."""
    clean_v = (vehicle_no or "").strip()
    clean_chassis = (chassis_no or "").strip()
    norm_plate = normalize_plate(clean_v) if clean_v else ""

    # If vehicle_no is missing or unplated, anchor on chassis_no
    if not norm_plate and clean_chassis:
        norm_plate = clean_chassis.upper()

    start_dt, end_dt, expiry_month = normalize_tenure_dates(start_date, end_date)

    # 1. Resolve vehicle
    veh: TrackedVehicle | None = None
    if tracked_vehicle_id:
        veh = db.get(TrackedVehicle, tracked_vehicle_id)
    if not veh and norm_plate:
        veh = db.scalar(select(TrackedVehicle).where(TrackedVehicle.vehicle_no == norm_plate))
    if not veh and clean_chassis:
        veh = db.scalar(select(TrackedVehicle).where(TrackedVehicle.chassis_no == clean_chassis))
    if not veh and (norm_plate or clean_chassis):
        primary_veh_no = norm_plate or clean_chassis.upper()
        veh = TrackedVehicle(
            vehicle_no=primary_veh_no,
            chassis_no=clean_chassis or None,
            engine_no=engine_no.strip() if engine_no else None,
            customer_id=customer_id,
        )
        db.add(veh)
        db.flush()
    elif veh:
        if clean_chassis and not veh.chassis_no:
            veh.chassis_no = clean_chassis
        if engine_no and not veh.engine_no:
            veh.engine_no = engine_no.strip()
        if customer_id and not veh.customer_id:
            veh.customer_id = customer_id

    vehicle_id = veh.id if veh else new_id()

    # 2. Query matching tenure for this vehicle: ONE locker per vehicle per calendar year
    start_of_year = datetime(start_dt.year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end_of_year = datetime(start_dt.year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

    vehicle_match_clauses = [InsuranceTenure.tracked_vehicle_id == vehicle_id]
    if norm_plate:
        vehicle_match_clauses.append(InsuranceTenure.vehicle_no == norm_plate)

    existing_tenure = db.scalar(
        select(InsuranceTenure)
        .where(
            or_(*vehicle_match_clauses),
            InsuranceTenure.coverage_start_date >= start_of_year,
            InsuranceTenure.coverage_start_date <= end_of_year,
            InsuranceTenure.is_discarded == False,
        )
        .order_by(InsuranceTenure.created_at.desc())
        .limit(1)
    )

    if existing_tenure:
        # Link vehicle id if missing
        if veh and not existing_tenure.tracked_vehicle_id:
            existing_tenure.tracked_vehicle_id = veh.id
        # If customer name is more informative in the new quote, update it
        if customer_name and len(customer_name.strip()) > len(existing_tenure.customer_name.strip()):
            existing_tenure.customer_name = customer_name.strip()
        if ownership_id and not existing_tenure.ownership_id:
            existing_tenure.ownership_id = ownership_id
        if customer_id and not existing_tenure.customer_id:
            existing_tenure.customer_id = customer_id
        if existing_tenure.is_projected:
            existing_tenure.is_projected = False
            if existing_tenure.status in ("upcoming", "untracked"):
                existing_tenure.status = "draft"
        return existing_tenure

    # Look for previous tenure on this vehicle ending before start_dt to chain them
    prev_tenure = db.scalar(
        select(InsuranceTenure)
        .where(
            InsuranceTenure.tracked_vehicle_id == vehicle_id,
            InsuranceTenure.coverage_end_date < start_dt,
        )
        .order_by(InsuranceTenure.coverage_end_date.desc())
        .limit(1)
    )
    prev_id = prev_tenure.id if prev_tenure else None
    chain_id = prev_tenure.tenure_chain_id if prev_tenure else new_id()
    delay_days = 0
    if prev_tenure:
        prev_end = prev_tenure.coverage_end_date if prev_tenure.coverage_end_date.tzinfo else prev_tenure.coverage_end_date.replace(tzinfo=timezone.utc)
        expected_start = prev_end + timedelta(days=1)
        delay_days = max(0, (start_dt - expected_start).days)

    # 3. Create new InsuranceTenure
    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=vehicle_id,
        ownership_id=ownership_id,
        customer_id=customer_id,
        vehicle_no=norm_plate or vehicle_no,
        customer_name=customer_name.strip() or "Valued Client",
        coverage_start_date=start_dt,
        coverage_end_date=end_dt,
        expiry_month=expiry_month,
        status="draft",
        previous_tenure_id=prev_id,
        tenure_chain_id=chain_id,
        delay_days=delay_days,
        reminder_window_start=start_dt - timedelta(days=90),
        created_by_id=created_by_id,
    )
    db.add(tenure)
    db.flush()

    # RL-DISABLED superseding_overlap — disabled 2026-10-09; each calendar year ledger remains independent; quotes uploaded for upcoming years do not hide active tenures.
    # overlapping = list(
    #     db.scalars(
    #         select(InsuranceTenure)
    #         .where(
    #             InsuranceTenure.tracked_vehicle_id == vehicle_id,
    #             InsuranceTenure.id != tenure.id,
    #             InsuranceTenure.is_hidden == False,
    #             InsuranceTenure.coverage_start_date < end_dt,
    #             InsuranceTenure.coverage_end_date > start_dt,
    #         )
    #     ).all()
    # )
    # for old_t in overlapping:
    #     old_t.is_hidden = True
    #     old_t.superseded_by_tenure_id = tenure.id

    return tenure


def ensure_vehicle_tenure_chain(
    db: Session,
    tenure: InsuranceTenure,
    target_years: tuple[int, ...] | None = None,
) -> list[InsuranceTenure]:
    """Disabled: Policies are strictly created when uploaded by staff.
    No automatic past or future policies are created.
    """
    return []


def evaluate_tenure_ingestion(
    db: Session,
    *,
    tenure_id: str,
    company_name: str | None,
    company_id: str | None = None,
    content_hash: str | None,
    current_session_id: str | None = None,
) -> tuple[str, SessionModel | None, int]:
    """Evaluate whether an incoming quotation PDF is identical, a revised version, or a new insurer.

    Returns:
        (action, existing_session, version_number)
        action:
            "SKIP_IDENTICAL" -> Exact 100% duplicate detected. Do NOT create duplicate records.
            "CREATE_VERSION" -> Replaces active session with a higher version (v2, v3).
            "CREATE_FIRST"   -> First quote for this insurer in this tenure (v1).
    """
    if not tenure_id:
        return "CREATE_FIRST", None, 1

    clean_comp = (company_name or "").strip().lower()
    if not clean_comp and company_id:
        comp_record = db.get(InsuranceCompany, company_id)
        if comp_record and comp_record.name:
            clean_comp = comp_record.name.strip().lower()

    # Query all active or historical sessions under this tenure
    sessions = list(
        db.scalars(
            select(SessionModel)
            .where(
                SessionModel.tenure_id == tenure_id,
                SessionModel.status != "trash",
            )
            .order_by(SessionModel.tenure_version.desc())
        ).all()
    )

    # Filter for sessions belonging to this same company (excluding current in-flight session)
    matching_sessions = [
        s for s in sessions
        if (not current_session_id or s.id != current_session_id)
        and s.detected_company and s.detected_company.strip().lower() == clean_comp
    ]

    if not matching_sessions:
        return "CREATE_FIRST", None, 1

    # Check for active session
    active_session = next((s for s in matching_sessions if s.is_tenure_active), matching_sessions[0])

    # Check zero-change deduplication
    if content_hash and active_session.content_hash == content_hash:
        return "SKIP_IDENTICAL", active_session, active_session.tenure_version

    # Found changes: calculate next version
    max_ver = max(s.tenure_version for s in matching_sessions)
    next_ver = max_ver + 1

    # Demote active session
    active_session.is_tenure_active = False
    return "CREATE_VERSION", active_session, next_ver


def get_tenure_timeline(db: Session, tenure_id: str) -> dict[str, Any] | None:
    """Compile the comprehensive lifecycle timeline for an Insurance Tenure."""
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        return None

    # Load sessions under tenure
    sessions = list(
        db.scalars(
            select(SessionModel)
            .where(
                SessionModel.tenure_id == tenure_id,
                SessionModel.status != "trash",
            )
            .order_by(SessionModel.created_at.asc())
        ).all()
    )

    # Group sourced quotes by insurer
    company_groups: dict[str, list[dict[str, Any]]] = {}
    generated_quotes: list[dict[str, Any]] = []

    for s in sessions:
        comp_name = s.detected_company or "Unknown Insurer"
        draft = s.draft
        fields = draft.fields if draft else {}

        def _get_val(k: str) -> Any:
            f = fields.get(k)
            return f.get("value") if isinstance(f, dict) else f

        quote_info = {
            "session_id": s.id,
            "version": s.tenure_version,
            "is_active": s.is_tenure_active,
            "company": comp_name,
            "sum_insured": _get_val("sum_insured") or _get_val("coverage_amount"),
            "premium": _get_val("premium") or _get_val("insurance_premium"),
            "total_payable": _get_val("total_amount") or _get_val("total_payable"),
            "quotation_ref": s.quotation_ref,
            "quotation_status": s.quotation_status,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }

        company_groups.setdefault(comp_name, []).append(quote_info)

        # If an official Risklocker quotation reference was generated, add to generated list
        if s.quotation_ref and s.quotation_ref.startswith("RL"):
            generated_quotes.append({
                "session_id": s.id,
                "quotation_ref": s.quotation_ref,
                "company": comp_name,
                "total_payable": quote_info["total_payable"],
                "status": s.quotation_status,
                "created_at": quote_info["created_at"],
            })

    # Fetch activities for sessions in this tenure
    session_ids = [s.id for s in sessions]
    activities: list[dict[str, Any]] = []
    if session_ids:
        act_rows = list(
            db.scalars(
                select(QuotationActivity)
                .where(QuotationActivity.session_id.in_(session_ids))
                .order_by(QuotationActivity.created_at.asc())
            ).all()
        )
        for act in act_rows:
            activities.append({
                "id": act.id,
                "session_id": act.session_id,
                "action_type": act.action_type,
                "user_id": act.user_id,
                "sent_to_client": act.sent_to_client,
                "status": act.status,
                "summary": act.summary,
                "created_at": act.created_at.isoformat() if act.created_at else None,
            })

    # Previous policy year reference
    prev_tenure = db.scalar(
        select(InsuranceTenure)
        .where(
            InsuranceTenure.tracked_vehicle_id == tenure.tracked_vehicle_id,
            InsuranceTenure.id != tenure.id,
            InsuranceTenure.coverage_start_date < tenure.coverage_start_date,
        )
        .order_by(InsuranceTenure.coverage_start_date.desc())
        .limit(1)
    )

    prev_info = None
    if prev_tenure:
        prev_info = {
            "id": prev_tenure.id,
            "coverage_start_date": prev_tenure.coverage_start_date.isoformat(),
            "coverage_end_date": prev_tenure.coverage_end_date.isoformat(),
            "expiry_month": prev_tenure.expiry_month,
            "status": prev_tenure.status,
            "won_premium": float(prev_tenure.won_premium) if prev_tenure.won_premium is not None else None,
            "winning_quotation_ref": prev_tenure.winning_quotation_ref,
        }

    return {
        "id": tenure.id,
        "vehicle_no": tenure.vehicle_no,
        "customer_name": tenure.customer_name,
        "coverage_start_date": tenure.coverage_start_date.isoformat(),
        "coverage_end_date": tenure.coverage_end_date.isoformat(),
        "expiry_month": tenure.expiry_month,
        "status": tenure.status,
        "stage": tenure.stage or "Quotations",
        "stage_updated_at": tenure.stage_updated_at.isoformat() if tenure.stage_updated_at else None,
        "is_main": tenure.is_main,
        "is_projected": tenure.is_projected,
        "reminder_window_start": tenure.reminder_window_start.isoformat() if tenure.reminder_window_start else None,
        "lapsed_at": tenure.lapsed_at.isoformat() if tenure.lapsed_at else None,
        "delay_days": tenure.delay_days,
        "tenure_chain_id": tenure.tenure_chain_id,
        "previous_tenure_id": tenure.previous_tenure_id,
        "winning_company_id": tenure.winning_company_id,
        "winning_quotation_ref": tenure.winning_quotation_ref,
        "won_premium": float(tenure.won_premium) if tenure.won_premium is not None else None,
        "miss_reason": tenure.miss_reason,
        "notes": tenure.notes,
        "sourced_quotes_by_company": company_groups,
        "generated_risklocker_quotations": generated_quotes,
        "previous_tenure": prev_info,
        "activities": activities,
    }


def auto_project_next_renewal(
    db: Session,
    completed_tenure_id: str,
    *,
    user_id: str | None = None,
) -> InsuranceTenure:
    """Disabled: Policies are strictly created when uploaded by staff.
    No automatic future renewal slots are projected.
    """
    tenure = db.get(InsuranceTenure, completed_tenure_id)
    if not tenure:
        raise ValueError(f"Tenure {completed_tenure_id} not found")
    return tenure


def shift_tenure_dates(
    db: Session,
    tenure_id: str,
    *,
    new_start_date: datetime | str,
    new_end_date: datetime | str | None = None,
    force_past: bool = False,
    user_id: str | None = None,
) -> InsuranceTenure:
    """Shift tenure dates when a customer renews late or adjusts policy periods."""
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise ValueError(f"Tenure {tenure_id} not found")

    now = datetime.now(timezone.utc)
    end_date_utc = tenure.coverage_end_date if tenure.coverage_end_date.tzinfo else tenure.coverage_end_date.replace(tzinfo=timezone.utc)
    # Locked rule: past completed policy dates are historical records and cannot be shifted
    if not force_past and tenure.status in ("hit", "won", "closed") and end_date_utc < now:
        raise ValueError("Past completed policy dates are locked as historical records and cannot be shifted.")

    start_dt, end_dt, expiry_month = normalize_tenure_dates(new_start_date, new_end_date)

    delay_days = 0
    if tenure.previous_tenure_id:
        prev = db.get(InsuranceTenure, tenure.previous_tenure_id)
        if prev:
            prev_end = prev.coverage_end_date if prev.coverage_end_date.tzinfo else prev.coverage_end_date.replace(tzinfo=timezone.utc)
            expected_start = prev_end + timedelta(days=1)
            delay = (start_dt - expected_start).days
            delay_days = max(0, delay)

    tenure.coverage_start_date = start_dt
    tenure.coverage_end_date = end_dt
    tenure.expiry_month = expiry_month
    tenure.reminder_window_start = start_dt - timedelta(days=90)
    tenure.delay_days = delay_days
    if tenure.is_projected and tenure.status == "upcoming":
        tenure.is_projected = False
        tenure.status = "draft"

    # Sync linked sessions and drafts
    active_sessions = list(db.scalars(select(SessionModel).where(SessionModel.tenure_id == tenure.id)).all())
    for sess in active_sessions:
        sess.coverage_start_date = start_dt
        sess.coverage_end_date = end_dt
        if sess.draft:
            f = dict(sess.draft.fields or {})
            f["cover_start_date"] = {"value": start_dt.strftime("%d/%m/%Y"), "status": "ready", "message": ""}
            f["cover_end_date"] = {"value": end_dt.strftime("%d/%m/%Y"), "status": "ready", "message": ""}
            sess.draft.fields = f


    if user_id and active_sessions:
        act = QuotationActivity(
            session_id=active_sessions[0].id,
            vehicle_no=tenure.vehicle_no,
            customer_name=tenure.customer_name,
            action_type="tenure_dates_shifted",
            user_id=user_id,
            summary=f"Coverage dates shifted: {start_dt.strftime('%d/%m/%Y')} -> {end_dt.strftime('%d/%m/%Y')} (Delay: {delay_days} days)",
        )
        db.add(act)

    db.flush()
    return tenure


def mark_tenure_lapsed(
    db: Session,
    tenure_id: str,
    *,
    reason: str | None = None,
    user_id: str | None = None,
) -> InsuranceTenure:
    """Mark a tenure as lapsed when a customer chooses not to renew or is unreachable."""
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise ValueError(f"Tenure {tenure_id} not found")

    tenure.status = "lapsed"
    tenure.lapsed_at = datetime.now(timezone.utc)
    if reason:
        tenure.miss_reason = reason

    active_sess = db.scalar(
        select(SessionModel)
        .where(SessionModel.tenure_id == tenure.id)
        .limit(1)
    )
    if active_sess and user_id:
        act = QuotationActivity(
            session_id=active_sess.id,
            vehicle_no=tenure.vehicle_no,
            customer_name=tenure.customer_name,
            action_type="status_change",
            user_id=user_id,
            status="lapsed",
            miss_reason=reason,
            summary=f"Tenure marked LAPSED: {reason or 'Customer discontinued'}",
        )
        db.add(act)

    db.flush()
    return tenure


def record_stage_timestamp(tenure: InsuranceTenure, stage: str) -> None:
    """Record an ISO timestamp for a stage update into tenure.stage_history."""
    now = datetime.now(timezone.utc)
    history = dict(tenure.stage_history or {})
    history[stage] = now.isoformat()
    tenure.stage_history = history
    tenure.stage_updated_at = now
    tenure.last_activity_at = now


def create_next_year_renewal_tenure(
    db: Session,
    tenure: InsuranceTenure,
    user_id: str | None = None,
) -> InsuranceTenure:
    """Automatically create the next year's renewal tenure with an empty marketing comparison.

    Triggers upon next-year roll-forward or HIT (Close - Win).
    """
    # Check if an active next-year renewal already exists for this tenure
    existing = db.scalar(
        select(InsuranceTenure).where(
            InsuranceTenure.previous_tenure_id == tenure.id,
            InsuranceTenure.is_discarded == False,
        )
    )
    if existing:
        return existing

    # Calculate next year's 1-year coverage window
    if tenure.coverage_end_date:
        start_date = tenure.coverage_end_date + timedelta(days=1)
    elif tenure.coverage_start_date:
        start_date = tenure.coverage_start_date + timedelta(days=365)
    else:
        start_date = datetime.now(timezone.utc)

    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=timezone.utc)

    end_date = start_date + timedelta(days=364)
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=timezone.utc)
    expiry_month = end_date.strftime("%Y-%m")

    # Check if vehicle already has an active tenure covering this start_date window
    vehicle_match = db.scalar(
        select(InsuranceTenure).where(
            InsuranceTenure.vehicle_no == tenure.vehicle_no,
            InsuranceTenure.coverage_start_date >= start_date - timedelta(days=60),
            InsuranceTenure.coverage_start_date <= start_date + timedelta(days=60),
            InsuranceTenure.is_discarded == False,
        )
    )
    if vehicle_match:
        if not vehicle_match.previous_tenure_id:
            vehicle_match.previous_tenure_id = tenure.id
            db.flush()
        return vehicle_match

    now = datetime.now(timezone.utc)
    next_tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=tenure.tracked_vehicle_id,
        ownership_id=tenure.ownership_id,
        vehicle_no=tenure.vehicle_no,
        customer_name=tenure.customer_name,
        customer_id=tenure.customer_id,
        coverage_start_date=start_date,
        coverage_end_date=end_date,
        expiry_month=expiry_month,
        status="draft",
        stage="Quotations",
        business_type="Renewal",
        previous_tenure_id=tenure.id,
        tenure_chain_id=tenure.tenure_chain_id,
        road_tax=float(tenure.road_tax or 0.0),
        runner_fee=float(tenure.runner_fee or 0.0),
        pic_id=tenure.pic_id,
        sub_agent_name=tenure.sub_agent_name,
        created_by_id=user_id or tenure.created_by_id,
        is_main=True,
        is_projected=False,
        is_discarded=False,
        is_hidden=False,
        stage_history={"Quotations": now.isoformat()},
        stage_updated_at=now,
        last_activity_at=now,
    )
    db.add(next_tenure)
    db.flush()
    return next_tenure


def ensure_next_year_renewal_tenures(
    db: Session,
    target_year: int = 2027,
    user_id: str | None = None,
) -> list[InsuranceTenure]:
    """Ensure all active non-dropped and non-missed vehicles have a next-year renewal tenure."""
    target_cutoff = datetime(target_year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    target_end_cutoff = datetime(target_year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

    # 1. Gather all vehicles that ALREADY have an active tenure in target_year
    existing_in_target = set(
        db.scalars(
            select(InsuranceTenure.vehicle_no).where(
                InsuranceTenure.coverage_start_date.between(target_cutoff, target_end_cutoff),
                InsuranceTenure.is_discarded == False,
            )
        ).all()
    )

    # 2. Query all active tenures before target_cutoff that are not missed and not dropped
    candidates = list(
        db.scalars(
            select(InsuranceTenure).where(
                InsuranceTenure.coverage_start_date < target_cutoff,
                InsuranceTenure.is_discarded == False,
                InsuranceTenure.is_projected == False,
                InsuranceTenure.status != "miss",
                or_(
                    InsuranceTenure.status == "hit",
                    InsuranceTenure.stage == "Close - Win",
                    InsuranceTenure.covernote_session_id.isnot(None),
                ),
            ).order_by(InsuranceTenure.coverage_start_date.desc())
        ).all()
    )

    # Group candidates by vehicle_no and take the latest active tenure
    latest_by_vehicle: dict[str, InsuranceTenure] = {}
    for t in candidates:
        v_no = (t.vehicle_no or "").strip().upper()
        if not v_no or v_no in ("UNPLATED", "UNKNOWN"):
            chassis = (getattr(t.tracked_vehicle, "chassis_no", None) or "").strip().upper()
            if chassis:
                v_no = chassis
            else:
                continue
        if v_no not in latest_by_vehicle:
            latest_by_vehicle[v_no] = t

    created_tenures: list[InsuranceTenure] = []
    for v_no, prev_tenure in latest_by_vehicle.items():
        if v_no in existing_in_target:
            continue
        new_t = create_next_year_renewal_tenure(db, prev_tenure, user_id=user_id)
        created_tenures.append(new_t)
        existing_in_target.add(v_no)

    if created_tenures:
        db.flush()
        db.commit()

    return created_tenures



def remove_auto_created_next_year_tenure(db: Session, tenure: InsuranceTenure) -> bool:
    """Delete an auto-created next-year renewal tenure if reverted or dropped, provided it has no user quotes."""
    children = list(
        db.scalars(
            select(InsuranceTenure).where(
                InsuranceTenure.previous_tenure_id == tenure.id
            )
        ).all()
    )
    removed = False
    for child in children:
        # Only delete if child is empty (no sessions, no comparison entries) and still in draft/Quotations
        has_sessions = db.scalar(
            select(func.count(SessionModel.id)).where(SessionModel.tenure_id == child.id)
        ) or 0
        has_entries = db.scalar(
            select(func.count(TenureComparisonEntry.id)).where(TenureComparisonEntry.tenure_id == child.id)
        ) or 0
        if has_sessions == 0 and has_entries == 0 and child.status == "draft":
            db.delete(child)
            removed = True
    if removed:
        db.flush()
    return removed


def update_tenure_status(
    db: Session,
    tenure_id: str,
    *,
    status: str,
    user_id: str,
    winning_company_id: str | None = None,
    winning_quotation_ref: str | None = None,
    won_premium: float | None = None,
    miss_reason: str | None = None,
    notes: str | None = None,
) -> InsuranceTenure:
    """Update status, conversion outcome, or win/loss notes for a tenure."""
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise ValueError(f"Tenure {tenure_id} not found")

    old_status = tenure.status
    tenure.status = status
    if winning_company_id is not None:
        tenure.winning_company_id = winning_company_id
    if winning_quotation_ref is not None:
        tenure.winning_quotation_ref = winning_quotation_ref
    if won_premium is not None:
        tenure.won_premium = won_premium
    if miss_reason is not None:
        tenure.miss_reason = miss_reason
    if notes is not None:
        tenure.notes = notes

    if status == "hit":
        tenure.stage = "Close - Win"
        record_stage_timestamp(tenure, "Close - Win")
        if not tenure.is_discarded:
            create_next_year_renewal_tenure(db, tenure, user_id=user_id)
    elif status == "miss":
        tenure.stage = "Close - Lose"
        record_stage_timestamp(tenure, "Close - Lose")
        remove_auto_created_next_year_tenure(db, tenure)
    elif old_status == "hit" and status != "hit":
        remove_auto_created_next_year_tenure(db, tenure)

    # Log activity on active session if available
    active_sess = db.scalar(
        select(SessionModel)
        .where(SessionModel.tenure_id == tenure_id, SessionModel.is_tenure_active)
        .limit(1)
    )
    if active_sess:
        act = QuotationActivity(
            session_id=active_sess.id,
            vehicle_no=tenure.vehicle_no,
            customer_name=tenure.customer_name,
            action_type="status_change",
            user_id=user_id,
            status=status,
            won_premium=won_premium,
            miss_reason=miss_reason,
            notes=notes,
            summary=f"Tenure status updated to {status.upper()}" + (f": {notes}" if notes else ""),
        )
        db.add(act)

    db.flush()
    return tenure

