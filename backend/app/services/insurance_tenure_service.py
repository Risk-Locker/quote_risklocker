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

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.tables import (
    InsuranceCompany,
    InsuranceTenure,
    QuotationActivity,
    QuotationDraft,
    Session as SessionModel,
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
) -> InsuranceTenure:
    """Find existing InsuranceTenure matching the vehicle and coverage dates or create one."""
    norm_plate = normalize_plate(vehicle_no)
    start_dt, end_dt, expiry_month = normalize_tenure_dates(start_date, end_date)

    # 1. Resolve vehicle
    veh: TrackedVehicle | None = None
    if tracked_vehicle_id:
        veh = db.get(TrackedVehicle, tracked_vehicle_id)
    if not veh and norm_plate:
        veh = db.scalar(select(TrackedVehicle).where(TrackedVehicle.vehicle_no == norm_plate))
    if not veh and norm_plate:
        veh = TrackedVehicle(vehicle_no=norm_plate)
        db.add(veh)
        db.flush()

    vehicle_id = veh.id if veh else new_id()

    # 2. Query matching tenure for this vehicle
    # Match within a +/- 35-day window around coverage start date
    window_start = start_dt - timedelta(days=35)
    window_end = start_dt + timedelta(days=35)

    existing_tenure = db.scalar(
        select(InsuranceTenure)
        .where(
            InsuranceTenure.tracked_vehicle_id == vehicle_id,
            InsuranceTenure.coverage_start_date >= window_start,
            InsuranceTenure.coverage_start_date <= window_end,
        )
        .order_by(InsuranceTenure.created_at.desc())
        .limit(1)
    )

    if existing_tenure:
        # If customer name is more informative in the new quote, update it
        if customer_name and len(customer_name.strip()) > len(existing_tenure.customer_name.strip()):
            existing_tenure.customer_name = customer_name.strip()
        if ownership_id and not existing_tenure.ownership_id:
            existing_tenure.ownership_id = ownership_id
        return existing_tenure

    # 3. Create new InsuranceTenure
    tenure = InsuranceTenure(
        tracked_vehicle_id=vehicle_id,
        ownership_id=ownership_id,
        vehicle_no=norm_plate or vehicle_no,
        customer_name=customer_name.strip() or "Valued Client",
        coverage_start_date=start_dt,
        coverage_end_date=end_dt,
        expiry_month=expiry_month,
        status="draft",
    )
    db.add(tenure)
    db.flush()
    return tenure


def evaluate_tenure_ingestion(
    db: Session,
    *,
    tenure_id: str,
    company_name: str | None,
    company_id: str | None = None,
    content_hash: str | None,
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

    # Filter for sessions belonging to this same company
    matching_sessions = [
        s for s in sessions
        if (s.detected_company and s.detected_company.strip().lower() == clean_comp)
        or (company_id and s.company_id == company_id)
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
        if s.quotation_ref and str(s.quotation_ref).startswith("RL"):
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
