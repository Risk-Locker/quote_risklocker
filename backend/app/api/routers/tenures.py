"""Tenures & Timeline API router."""

from __future__ import annotations

import calendar
from collections import defaultdict
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user
from app.db.session import get_db
from app.models.tables import (
    CustomerAccount,
    InsuranceTenure,
    QuotationActivity,
    QuotationDraft,
    Session as SessionModel,
    User,
)
from app.services.customer_account_service import resolve_or_create_customer
from app.services.insurance_tenure_service import (
    auto_project_next_renewal,
    get_tenure_timeline,
    mark_tenure_lapsed,
    resolve_or_create_tenure,
    shift_tenure_dates,
    update_tenure_status,
)
from app.services.quotation_reference_service import generate_quotation_reference

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenures", tags=["tenures"])


class CreateTenureRequest(BaseModel):
    vehicle_no: str | None = Field(None, description="Vehicle registration plate")
    customer_name: str = Field(..., description="Customer / policyholder name")
    coverage_start_date: str | None = Field(None, description="Start date (YYYY-MM-DD)")
    coverage_end_date: str | None = Field(None, description="End date (YYYY-MM-DD)")
    chassis_no: str | None = Field(None, description="Chassis / VIN for new or unregistered vehicles")
    engine_no: str | None = Field(None, description="Engine number")
    engine_cc: str | None = Field(None, description="Engine capacity")
    car_model: str | None = Field(None, description="Car model")
    ic_no: str | None = Field(None, description="Customer IC or Passport")
    phone: str | None = Field(None, description="Customer phone")
    email: str | None = Field(None, description="Customer email")
    pic_id: str | None = Field(None, description="Person in charge ID")
    sub_agent_name: str | None = Field(None, description="PIC / sub-agent name")
    windscreen_target: float | None = Field(None, description="Initial windscreen target")
    notes: str | None = Field(None, description="Notes")
    road_tax: float = 0.0
    runner_fee: float = 0.0


class TenureStatusUpdateRequest(BaseModel):
    status: str = Field(..., description="Tenure status: draft, comparing, sent, hit, miss, closed")
    winning_company_id: str | None = None
    winning_quotation_ref: str | None = None
    won_premium: float | None = None
    miss_reason: str | None = None
    notes: str | None = None


class TenureGenerateQuoteRequest(BaseModel):
    session_id: str = Field(..., description="Session ID of the sourced insurer quote to generate an RL quote for")


class ShiftTenureDatesRequest(BaseModel):
    start_date: str = Field(..., description="New coverage start date (YYYY-MM-DD or DD/MM/YYYY)")
    end_date: str | None = Field(None, description="Optional new coverage end date (YYYY-MM-DD or DD/MM/YYYY)")
    force_past: bool = Field(False, description="Override locked check for historical records")


class LapseTenureRequest(BaseModel):
    reason: str | None = Field(None, description="Reason for lapse e.g. Customer sold vehicle, Competitor, Unreachable")


class UpdateTenureLedgerRequest(BaseModel):
    stage: str | None = None
    business_type: str | None = None
    comment: str | None = None
    notes: str | None = None
    client_preference_notes: str | None = None
    sub_agent_name: str | None = None
    pic_id: str | None = None
    key_in_ucd: bool | None = None
    date_of_key_in: str | None = None
    print_roadtax: str | None = None
    roadtax_receipt: str | None = None
    client_payment_received: bool | None = None
    agency_payment_done: bool | None = None
    loss_reason_category: str | None = None
    winning_company_id: str | None = None
    winning_quotation_ref: str | None = None
    won_premium: float | None = None
    customer_name: str | None = None
    customer_ic_no: str | None = None
    vehicle_no: str | None = None
    chassis_no: str | None = None
    engine_no: str | None = None
    car_brand: str | None = None
    car_model: str | None = None
    engine_cc: str | None = None
    road_tax: float | None = None
    runner_fee: float | None = None
    is_main: bool | None = None
    is_discarded: bool | None = None
    status: str | None = None
    external_policy_start_date: str | None = None
    external_policy_end_date: str | None = None


@router.post("")
def create_tenure(
    payload: CreateTenureRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Create a new insurance tenure directly from staff comparison ledger input."""
    # Resolve or create customer if IC or name given
    cust_id = None
    if payload.ic_no or payload.customer_name:
        cust, _ = resolve_or_create_customer(
            db,
            raw_name=payload.customer_name,
            raw_id=payload.ic_no,
            phone=payload.phone,
            email=payload.email,
        )
        if cust:
            cust_id = cust.id

    effective_veh = (payload.vehicle_no or "").strip()
    if not effective_veh and payload.chassis_no:
        effective_veh = payload.chassis_no.strip().upper()

    tenure = resolve_or_create_tenure(
        db,
        vehicle_no=effective_veh or "UNPLATED",
        customer_name=payload.customer_name,
        start_date=payload.coverage_start_date,
        end_date=payload.coverage_end_date,
        customer_id=cust_id,
        chassis_no=payload.chassis_no,
        engine_no=payload.engine_no,
        created_by_id=user.id,
    )
    if not tenure.created_by_id:
        tenure.created_by_id = user.id
    if payload.road_tax > 0.0:
        tenure.road_tax = payload.road_tax
    if payload.runner_fee > 0.0:
        tenure.runner_fee = payload.runner_fee
    if payload.windscreen_target is not None:
        tenure.windscreen_target = payload.windscreen_target
    if payload.pic_id:
        tenure.pic_id = payload.pic_id
    if payload.sub_agent_name:
        tenure.sub_agent_name = payload.sub_agent_name
    if payload.notes:
        tenure.notes = payload.notes

    if tenure.tracked_vehicle:
        if payload.car_model:
            tenure.tracked_vehicle.car_model = payload.car_model
        if payload.engine_cc:
            tenure.tracked_vehicle.engine_cc = payload.engine_cc
        if payload.chassis_no:
            tenure.tracked_vehicle.chassis_no = payload.chassis_no
        if payload.engine_no:
            tenure.tracked_vehicle.engine_no = payload.engine_no

    db.commit()
    return {
        "id": tenure.id,
        "tenure": {
            "id": tenure.id,
            "vehicle_no": tenure.vehicle_no,
            "customer_name": tenure.customer_name,
        },
        "vehicle_no": tenure.vehicle_no,
        "customer_name": tenure.customer_name,
        "chassis_no": tenure.tracked_vehicle.chassis_no if tenure.tracked_vehicle else None,
        "expiry_month": tenure.expiry_month,
        "coverage_start_date": tenure.coverage_start_date.isoformat(),
        "coverage_end_date": tenure.coverage_end_date.isoformat(),
    }


@router.get("/calendar-sessions")
def list_calendar_sessions(
    year: int | None = Query(None, description="Filter by quotation year e.g. 2026"),
    month: int | None = Query(None, ge=1, le=12, description="Filter by quotation month 1-12"),
    vehicle_no: str | None = Query(None, description="Filter by vehicle registration plate"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Retrieve all uploaded quotation sessions plotted by quotation date for the calendar view."""
    stmt = (
        select(SessionModel)
        .options(
            selectinload(SessionModel.draft),
            selectinload(SessionModel.tenure),
        )
        .where(SessionModel.status != "trash")
    )

    if vehicle_no and vehicle_no.strip():
        veh = vehicle_no.strip().upper()
        stmt = stmt.join(SessionModel.tenure).where(InsuranceTenure.vehicle_no == veh)

    sessions = list(db.scalars(stmt).all())

    events = []
    for s in sessions:
        draft = s.draft
        f = draft.fields if draft else {}

        def _val(k: str) -> Any:
            item = f.get(k)
            return item.get("value") if isinstance(item, dict) else item

        raw_q_date = _val("quotation_date") or _val("quotation_issue_date") or _val("issue_date")
        q_date_str = None
        if raw_q_date:
            try:
                s_raw = str(raw_q_date).strip()
                if "-" in s_raw:
                    q_date_str = s_raw[:10]
                elif "/" in s_raw:
                    parts = s_raw.split("/")
                    if len(parts) == 3:
                        q_date_str = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
            except Exception:
                pass

        if not q_date_str and s.created_at:
            q_date_str = s.created_at.strftime("%Y-%m-%d")

        if not q_date_str:
            continue

        if year:
            try:
                ev_year = int(q_date_str.split("-")[0])
                if ev_year != year:
                    continue
            except Exception:
                continue

        if month:
            try:
                ev_month = int(q_date_str.split("-")[1])
                if ev_month != month:
                    continue
            except Exception:
                continue

        tot = _val("total_amount") or _val("total_payable")
        sum_ins = _val("sum_insured") or _val("coverage_amount")
        t_veh = s.tenure.vehicle_no if s.tenure else _val("vehicle_no") or "Unknown"
        t_cust = s.tenure.customer_name if s.tenure else _val("customer_name") or "Unknown"

        events.append({
            "session_id": s.id,
            "tenure_id": s.tenure_id,
            "vehicle_no": t_veh,
            "customer_name": t_cust,
            "quotation_date": q_date_str,
            "detected_company": s.detected_company or "Unknown",
            "total_payable": tot,
            "sum_insured": sum_ins,
            "tenure_version": s.tenure_version,
            "status": s.status,
            "is_tenure_active": s.is_tenure_active,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })

    events.sort(key=lambda x: (x["quotation_date"], x["vehicle_no"]))
    return {"sessions": events, "total": len(events)}


@router.get("/stage-summary")
def get_tenure_stage_summary(
    year: int | None = Query(None, description="Year to filter e.g. 2026"),
    month: int | None = Query(None, ge=1, le=12, description="Month 1-12"),
    show_hidden: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Retrieve live counts for the 10 stage KPI summary cards matching active filter."""
    query = select(InsuranceTenure.stage, func.count(InsuranceTenure.id))

    query = query.where(InsuranceTenure.is_projected == False)
    if not show_hidden:
        query = query.where(InsuranceTenure.is_hidden == False)

    if year and month:
        _, last_day = calendar.monthrange(year, month)
        start_of_month = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_of_month = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)
        pattern = f"{year:04d}-{month:02d}"
        query = query.where(
            InsuranceTenure.coverage_start_date.between(start_of_month, end_of_month)
        )
    elif year:
        start_of_year = datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_of_year = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        query = query.where(
            InsuranceTenure.coverage_start_date.between(start_of_year, end_of_year)
        )

    rows = db.execute(query.group_by(InsuranceTenure.stage)).all()
    stage_counts = {r[0]: int(r[1]) for r in rows}

    return {
        "quotations": stage_counts.get("Quotations", 0),
        "material_to_client": stage_counts.get("Material to Client", 0),
        "issue_policy": stage_counts.get("Issue Policy", 0),
        "ucd_invoice_to_client": stage_counts.get("UCD Invoice to Client", 0),
        "ucd_receipt_to_client": stage_counts.get("UCD Receipt to Client", 0),
        "pending_payment": stage_counts.get("Pending Payment", 0),
        "pending_delivery": stage_counts.get("Pending Delivery", 0),
        "close_win": stage_counts.get("Close - Win", 0),
        "close_lose": stage_counts.get("Close - Lose", 0),
        "others": stage_counts.get("Others", 0),
        "total": sum(stage_counts.values()),
    }


@router.get("/months")
def list_tenure_months(
    show_hidden: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Retrieve list of available months with start, end, and total tenure statistics."""
    stmt = select(
        InsuranceTenure.id,
        InsuranceTenure.vehicle_no,
        InsuranceTenure.coverage_start_date,
        InsuranceTenure.coverage_end_date,
        InsuranceTenure.expiry_month,
        InsuranceTenure.status,
    )
    stmt = stmt.where(InsuranceTenure.is_projected == False)
    if not show_hidden:
        stmt = stmt.where(InsuranceTenure.is_hidden == False)

    all_tenures = db.execute(stmt).all()

    month_data: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "start_count": 0,
        "end_count": 0,
        "tenure_ids": set(),
        "vehicles": set(),
        "hit": 0,
        "miss": 0,
    })

    for t_id, veh, start_dt, end_dt, exp_m, t_status in all_tenures:
        # Start month
        if start_dt:
            s_ym = start_dt.strftime("%Y-%m")
            month_data[s_ym]["start_count"] += 1
            month_data[s_ym]["tenure_ids"].add(t_id)
            if veh:
                month_data[s_ym]["vehicles"].add(veh)

            if t_status == "hit":
                month_data[s_ym]["hit"] += 1
            elif t_status == "miss":
                month_data[s_ym]["miss"] += 1

        # End / Expiry month
        e_ym = None
        if end_dt:
            e_ym = end_dt.strftime("%Y-%m")
        elif exp_m:
            e_ym = exp_m[:7]

        if e_ym:
            month_data[e_ym]["end_count"] += 1
            month_data[e_ym]["tenure_ids"].add(t_id)
            if veh:
                month_data[e_ym]["vehicles"].add(veh)
            if t_status == "hit":
                month_data[e_ym]["hit"] += 1
            elif t_status == "miss":
                month_data[e_ym]["miss"] += 1

    result: list[dict[str, Any]] = []
    for y in range(2024, 2031):
        for m in range(1, 13):
            key = f"{y:04d}-{m:02d}"
            info = month_data.get(key)
            if info:
                tot = len(info["tenure_ids"])
                hit_cnt = info["hit"]
                miss_cnt = info["miss"]
                pending_cnt = max(0, tot - hit_cnt - miss_cnt)
                result.append({
                    "month": key,
                    "total": tot,
                    "start_count": info["start_count"],
                    "end_count": info["end_count"],
                    "cars": len(info["vehicles"]),
                    "hit": hit_cnt,
                    "miss": miss_cnt,
                    "pending": pending_cnt,
                })
            else:
                result.append({
                    "month": key,
                    "total": 0,
                    "start_count": 0,
                    "end_count": 0,
                    "cars": 0,
                    "hit": 0,
                    "miss": 0,
                    "pending": 0,
                })

    result.sort(key=lambda x: x["month"])
    return {"months": result}


@router.get("")
def list_tenures(
    month: str | None = None,
    year: int | None = None,
    search: str | None = None,
    status: str | None = None,
    stage: str | None = None,
    category: str | None = None,
    sub_agent: str | None = None,
    show_hidden: bool = False,
    show_discarded: bool = False,
    sort_by: str | None = Query("last_activity", description="Sort by last_activity, vehicle_no, customer_name, stage, coverage_end_date"),
    sort_dir: str | None = Query("desc", description="Sort direction asc or desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Retrieve customer-vehicle tenures for the Motor Renewal Ledger with search and filters."""
    query = select(InsuranceTenure).where(InsuranceTenure.is_projected == False)

    if not show_hidden:
        query = query.where(InsuranceTenure.is_hidden == False)

    if not show_discarded:
        query = query.where(InsuranceTenure.is_discarded == False)

    # 1. Year and Month filtering
    if month and month.strip() != "all":
        m_str = month.strip()
        y_val: int | None = None
        m_val: int | None = None
        if "-" in m_str:
            parts = m_str.split("-")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                y_val = int(parts[0])
                m_val = int(parts[1])
        elif m_str.isdigit() and year:
            y_val = year
            m_val = int(m_str)

        if y_val and m_val:
            _, last_day = calendar.monthrange(y_val, m_val)
            start_of_month = datetime(y_val, m_val, 1, 0, 0, 0, tzinfo=timezone.utc)
            end_of_month = datetime(y_val, m_val, last_day, 23, 59, 59, tzinfo=timezone.utc)
            ym_pattern = f"{y_val:04d}-{m_val:02d}"

            query = query.where(
                or_(
                    InsuranceTenure.coverage_start_date.between(start_of_month, end_of_month),
                    InsuranceTenure.coverage_end_date.between(start_of_month, end_of_month),
                    InsuranceTenure.expiry_month == ym_pattern,
                )
            )
        else:
            query = query.where(InsuranceTenure.coverage_start_date.isnot(None))

    elif year and str(year) != "all":
        start_of_year = datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_of_year = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

        query = query.where(
            InsuranceTenure.coverage_start_date.between(start_of_year, end_of_year)
        )

    # 2. Category filtering: active (exclude Close - Lose & Others) vs lost vs all
    if category == "active":
        query = query.where(~InsuranceTenure.stage.in_(["Close - Lose", "Others"]))
    elif category == "lost":
        query = query.where(InsuranceTenure.stage.in_(["Close - Lose", "Others"]))

    # 3. Specific stage filter
    if stage and stage != "all":
        query = query.where(InsuranceTenure.stage == stage.strip())

    if status and status != "all":
        query = query.where(InsuranceTenure.status == status.strip())

    if sub_agent:
        query = query.where(InsuranceTenure.sub_agent_name.ilike(f"%{sub_agent.strip()}%"))

    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                InsuranceTenure.vehicle_no.ilike(term),
                InsuranceTenure.customer_name.ilike(term),
                InsuranceTenure.comment.ilike(term),
                InsuranceTenure.sub_agent_name.ilike(term),
            )
        )

    # Dynamic sorting
    actual_sort_by = (
        sort_by if isinstance(sort_by, str)
        else getattr(sort_by, "default", "last_activity")
    ) or "last_activity"
    actual_sort_dir = (
        sort_dir if isinstance(sort_dir, str)
        else getattr(sort_dir, "default", "desc")
    ) or "desc"

    is_desc = str(actual_sort_dir).lower() == "desc"
    s_by = str(actual_sort_by).lower()

    if s_by == "vehicle_no":
        sort_col = InsuranceTenure.vehicle_no
        query = query.order_by(sort_col.desc().nullslast() if is_desc else sort_col.asc().nullsfirst(), InsuranceTenure.coverage_end_date.asc())
    elif s_by == "customer_name":
        sort_col = InsuranceTenure.customer_name
        query = query.order_by(sort_col.desc().nullslast() if is_desc else sort_col.asc().nullsfirst(), InsuranceTenure.vehicle_no.asc())
    elif s_by == "stage":
        sort_col = InsuranceTenure.stage
        query = query.order_by(sort_col.desc().nullslast() if is_desc else sort_col.asc().nullsfirst(), InsuranceTenure.vehicle_no.asc())
    elif s_by == "coverage_end_date":
        sort_col = InsuranceTenure.coverage_end_date
        query = query.order_by(sort_col.desc().nullslast() if is_desc else sort_col.asc().nullsfirst(), InsuranceTenure.vehicle_no.asc())
    else:
        # Default: last_activity
        if is_desc:
            query = query.order_by(InsuranceTenure.last_activity_at.desc().nullslast(), InsuranceTenure.coverage_end_date.asc())
        else:
            query = query.order_by(InsuranceTenure.last_activity_at.asc().nullsfirst(), InsuranceTenure.coverage_end_date.asc())

    # Count total
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    # Paginate and pre-load relations
    p = page if isinstance(page, int) else 1
    ps = page_size if isinstance(page_size, int) else 50
    offset = (p - 1) * ps
    paged_query = (
        query.options(
            selectinload(InsuranceTenure.pic),
            selectinload(InsuranceTenure.winning_company),
            selectinload(InsuranceTenure.customer),
            selectinload(InsuranceTenure.tracked_vehicle),
        )
        .offset(offset)
        .limit(ps)
    )
    tenures = list(db.scalars(paged_query).all())

    # Batch-load all active sessions and pre-load drafts for all page tenures in one query
    tenure_ids = [t.id for t in tenures]
    sessions_by_tenure: dict[str, list[SessionModel]] = defaultdict(list)
    if tenure_ids:
        all_sessions = list(
            db.scalars(
                select(SessionModel)
                .options(selectinload(SessionModel.draft))
                .where(
                    SessionModel.tenure_id.in_(tenure_ids),
                    SessionModel.is_tenure_active,
                    SessionModel.status != "trash",
                )
            ).all()
        )
        for s in all_sessions:
            if s.tenure_id:
                sessions_by_tenure[s.tenure_id].append(s)

    now = datetime.now(timezone.utc)
    items = []
    for t in tenures:
        # Use pre-loaded active child sessions for this tenure
        sessions = sessions_by_tenure.get(t.id, [])

        sourced = []
        gen_quotes = []
        for s in sessions:
            draft = s.draft
            f = draft.fields if draft else {}
            def _val(k: str) -> Any:
                item = f.get(k)
                return item.get("value") if isinstance(item, dict) else item

            tot = _val("total_amount") or _val("total_payable")
            sum_ins = _val("sum_insured") or _val("coverage_amount")
            comp = s.detected_company or "Unknown"

            sourced.append({
                "session_id": s.id,
                "company": comp,
                "version": s.tenure_version,
                "total_payable": tot,
                "sum_insured": sum_ins,
            })

            if s.quotation_ref and s.quotation_ref.startswith("RL"):
                gen_quotes.append({
                    "session_id": s.id,
                    "quotation_ref": s.quotation_ref,
                    "company": comp,
                    "status": s.quotation_status,
                })

        stage_up = t.stage_updated_at if t.stage_updated_at.tzinfo else t.stage_updated_at.replace(tzinfo=timezone.utc)
        days_in_stage = max(0, (now - stage_up).days) if t.stage_updated_at else 0

        items.append({
            "id": t.id,
            "vehicle_no": t.vehicle_no,
            "customer_name": t.customer_name,
            "chassis_no": t.tracked_vehicle.chassis_no if t.tracked_vehicle else None,
            "engine_no": t.tracked_vehicle.engine_no if t.tracked_vehicle else None,
            "car_brand": t.tracked_vehicle.car_brand if t.tracked_vehicle else None,
            "car_model": t.tracked_vehicle.car_model if t.tracked_vehicle else None,
            "engine_cc": t.tracked_vehicle.engine_cc if t.tracked_vehicle else None,
            "coverage_start_date": t.coverage_start_date.isoformat(),
            "coverage_end_date": t.coverage_end_date.isoformat(),
            "expiry_month": t.expiry_month,
            "status": t.status,
            "stage": t.stage or "Quotations",
            "business_type": t.business_type or "Renewal",
            "pic_id": t.pic_id,
            "sub_agent_name": t.sub_agent_name or (t.pic.name if t.pic else ""),
            "pic_agency": t.pic.agency_group if t.pic else "",
            "key_in_ucd": t.key_in_ucd,
            "date_of_key_in": t.date_of_key_in.isoformat() if t.date_of_key_in else None,
            "print_roadtax": t.print_roadtax or "No",
            "roadtax_receipt": t.roadtax_receipt or "None",
            "client_payment_received": t.client_payment_received,
            "agency_payment_done": t.agency_payment_done,
            "comment": t.comment or "",
            "notes": t.notes or "",
            "client_preference_notes": t.client_preference_notes or "",
            "days_in_stage": days_in_stage,
            "winning_company_id": t.winning_company_id,
            "winning_company_name": t.winning_company.name if t.winning_company else "",
            "winning_quotation_ref": t.winning_quotation_ref,
            "won_premium": float(t.won_premium) if t.won_premium is not None else None,
            "miss_reason": t.miss_reason,
            "loss_reason_category": t.loss_reason_category,
            "road_tax": float(t.road_tax or 0.0),
            "sourced_quotes": sourced,
            "generated_quotations": gen_quotes,
            "is_projected": t.is_projected,
            "is_hidden": t.is_hidden,
            "is_main": t.is_main,
            "superseded_by_tenure_id": t.superseded_by_tenure_id,
            "tenure_type": t.tenure_type,
            "manufacture_year": getattr(t.tracked_vehicle, "manufacture_year", None) if t.tracked_vehicle else None,
            "tenure_chain_id": t.tenure_chain_id,
            "customer_id": t.customer_id,
            "customer_ic_no": t.customer.id_number if t.customer else None,
            "is_discarded": t.is_discarded,
            "stage_history": t.stage_history or {},
            "stage_updated_at": (t.stage_updated_at or t.updated_at or t.created_at).isoformat() if (t.stage_updated_at or t.updated_at or t.created_at) else None,
            "external_policy_start_date": t.external_policy_start_date.isoformat() if t.external_policy_start_date else None,
            "external_policy_end_date": t.external_policy_end_date.isoformat() if t.external_policy_end_date else None,
            "last_activity_at": (t.last_activity_at or t.updated_at or t.created_at).isoformat() if (t.last_activity_at or t.updated_at or t.created_at) else None,
            "created_at": t.created_at.isoformat(),
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/{tenure_id}/ledger-fields")
def update_tenure_ledger_fields(
    tenure_id: str,
    payload: UpdateTenureLedgerRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Inline update operational fields on a tenure directly from the Motor Renewal Ledger."""
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise HTTPException(status_code=404, detail="Tenure not found")

    now = datetime.now(timezone.utc)
    old_stage = tenure.stage
    old_status = tenure.status

    if payload.stage is not None and payload.stage != tenure.stage:
        tenure.stage = payload.stage
        if payload.stage == "Close - Win":
            tenure.status = "hit"
        elif payload.stage == "Close - Lose":
            tenure.status = "miss"
        from app.services.insurance_tenure_service import record_stage_timestamp
        record_stage_timestamp(tenure, payload.stage)

    if payload.status is not None and payload.status != tenure.status:
        tenure.status = payload.status
        if payload.status == "hit" and tenure.stage != "Close - Win":
            tenure.stage = "Close - Win"
            from app.services.insurance_tenure_service import record_stage_timestamp
            record_stage_timestamp(tenure, "Close - Win")
        elif payload.status != "hit" and tenure.stage == "Close - Win":
            tenure.stage = payload.stage if payload.stage else "Issue Policy"

    if payload.business_type is not None:
        tenure.business_type = payload.business_type
    if payload.comment is not None:
        tenure.comment = payload.comment
    if payload.notes is not None:
        tenure.notes = payload.notes
    if payload.client_preference_notes is not None:
        tenure.client_preference_notes = payload.client_preference_notes
    if payload.sub_agent_name is not None:
        tenure.sub_agent_name = payload.sub_agent_name
    if payload.pic_id is not None:
        tenure.pic_id = payload.pic_id
    if payload.key_in_ucd is not None:
        tenure.key_in_ucd = payload.key_in_ucd
    if payload.date_of_key_in is not None:
        try:
            tenure.date_of_key_in = (
                datetime.strptime(payload.date_of_key_in, "%Y-%m-%d").date()
                if payload.date_of_key_in
                else None
            )
        except Exception:
            pass
    if payload.print_roadtax is not None:
        tenure.print_roadtax = payload.print_roadtax
    if payload.roadtax_receipt is not None:
        tenure.roadtax_receipt = payload.roadtax_receipt
    if payload.client_payment_received is not None:
        tenure.client_payment_received = payload.client_payment_received
    if payload.agency_payment_done is not None:
        tenure.agency_payment_done = payload.agency_payment_done
    if payload.loss_reason_category is not None:
        tenure.loss_reason_category = payload.loss_reason_category
    if payload.winning_company_id is not None:
        tenure.winning_company_id = payload.winning_company_id
    if payload.winning_quotation_ref is not None:
        tenure.winning_quotation_ref = payload.winning_quotation_ref
    if payload.won_premium is not None:
        tenure.won_premium = payload.won_premium
    if payload.road_tax is not None:
        tenure.road_tax = payload.road_tax
    if payload.runner_fee is not None:
        tenure.runner_fee = payload.runner_fee
    if payload.vehicle_no is not None and payload.vehicle_no.strip():
        tenure.vehicle_no = payload.vehicle_no.strip().upper()
        if tenure.tracked_vehicle:
            tenure.tracked_vehicle.vehicle_no = tenure.vehicle_no

    if tenure.tracked_vehicle:
        if payload.chassis_no is not None:
            tenure.tracked_vehicle.chassis_no = payload.chassis_no.strip() or None
        if payload.engine_no is not None:
            tenure.tracked_vehicle.engine_no = payload.engine_no.strip() or None
        if payload.car_brand is not None:
            tenure.tracked_vehicle.car_brand = payload.car_brand.strip() or None
        if payload.car_model is not None:
            tenure.tracked_vehicle.car_model = payload.car_model.strip() or None
        if payload.engine_cc is not None:
            tenure.tracked_vehicle.engine_cc = payload.engine_cc.strip() or None

    # Customer Name / IC updates with full propagation across all tenures and drafts
    if (payload.customer_name and payload.customer_name.strip()) or (payload.customer_ic_no and payload.customer_ic_no.strip()):
        clean_name = payload.customer_name.strip() if payload.customer_name else None
        clean_ic = payload.customer_ic_no.strip() if payload.customer_ic_no else None
        if clean_name:
            tenure.customer_name = clean_name

        cust = tenure.customer or (db.get(CustomerAccount, tenure.customer_id) if tenure.customer_id else None)
        if not cust and (clean_name or clean_ic):
            cust, _ = resolve_or_create_customer(
                db,
                raw_name=clean_name or tenure.customer_name,
                raw_id=clean_ic,
            )
        if cust:
            tenure.customer_id = cust.id
            if clean_name:
                cust.canonical_name = clean_name
            if clean_ic:
                from app.services.identity_normalization_service import normalize_government_id
                norm_id, norm_type = normalize_government_id(clean_ic)
                cust.id_number = norm_id or clean_ic
                if norm_type:
                    cust.id_type = norm_type

            # Propagate customer_name to all tenures for this customer
            from sqlalchemy import update
            db.execute(
                update(InsuranceTenure)
                .where(InsuranceTenure.customer_id == cust.id)
                .values(customer_name=cust.canonical_name)
            )

            # Propagate customer name and IC to all quotation drafts under this customer or tenure
            sessions_to_sync = list(
                db.scalars(
                    select(SessionModel).where(
                        or_(
                            SessionModel.customer_id == cust.id,
                            SessionModel.tenure_id == tenure.id,
                        )
                    )
                ).all()
            )
            for s in sessions_to_sync:
                if s.customer_id != cust.id:
                    s.customer_id = cust.id
                if s.draft and isinstance(s.draft.fields, dict):
                    f = dict(s.draft.fields)
                    if clean_name:
                        for name_k in ["customer_name", "policyholder_name", "client_name"]:
                            if name_k in f:
                                if isinstance(f[name_k], dict):
                                    f[name_k] = {**f[name_k], "value": cust.canonical_name}
                                else:
                                    f[name_k] = cust.canonical_name
                    if clean_ic:
                        for ic_k in ["customer_ic_no", "ic_no", "nric_no", "id_number"]:
                            if ic_k in f:
                                if isinstance(f[ic_k], dict):
                                    f[ic_k] = {**f[ic_k], "value": cust.id_number}
                                else:
                                    f[ic_k] = cust.id_number
                    s.draft.fields = f

    if payload.is_discarded is not None:
        tenure.is_discarded = payload.is_discarded
    if payload.external_policy_start_date is not None:
        try:
            tenure.external_policy_start_date = (
                datetime.strptime(payload.external_policy_start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if payload.external_policy_start_date
                else None
            )
        except Exception:
            pass
    if payload.external_policy_end_date is not None:
        try:
            tenure.external_policy_end_date = (
                datetime.strptime(payload.external_policy_end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if payload.external_policy_end_date
                else None
            )
        except Exception:
            pass

    if payload.is_main is not None:
        tenure.is_main = payload.is_main
        if payload.is_main:
            cohort_year = tenure.coverage_start_date.year if tenure.coverage_start_date else None
            other_tenures = db.scalars(
                select(InsuranceTenure).where(
                    InsuranceTenure.vehicle_no == tenure.vehicle_no,
                    InsuranceTenure.id != tenure.id,
                )
            ).all()
            for ot in other_tenures:
                ot_year = ot.coverage_start_date.year if ot.coverage_start_date else None
                if ot_year == cohort_year:
                    ot.is_main = False

    # Auto renewal lifecycle:
    # 1. When marked HIT (Close - Win), auto-create the next year renewal tenure with empty comparison
    from app.services.insurance_tenure_service import (
        create_next_year_renewal_tenure,
        remove_auto_created_next_year_tenure,
    )
    is_hit = (tenure.stage == "Close - Win" or tenure.status == "hit") and not tenure.is_discarded
    was_hit = (old_stage == "Close - Win" or old_status == "hit")

    if is_hit:
        create_next_year_renewal_tenure(db, tenure, user_id=user.id)
    elif was_hit and not is_hit:
        remove_auto_created_next_year_tenure(db, tenure)
    elif payload.is_discarded or tenure.stage == "Close - Lose" or tenure.status == "miss":
        remove_auto_created_next_year_tenure(db, tenure)

    tenure.last_activity_at = now
    db.commit()
    db.refresh(tenure)
    return {"success": True, "id": tenure.id, "stage": tenure.stage, "is_main": tenure.is_main}


@router.post("/{tenure_id}/set-main")
def set_tenure_as_main(
    tenure_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Mark this tenure as the approved/main policy for this vehicle and cohort."""
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise HTTPException(status_code=404, detail="Tenure not found")

    tenure.is_main = True
    cohort_year = tenure.coverage_start_date.year if tenure.coverage_start_date else None

    # Unset other tenures for the same vehicle in the same cohort year
    other_tenures = db.scalars(
        select(InsuranceTenure).where(
            InsuranceTenure.vehicle_no == tenure.vehicle_no,
            InsuranceTenure.id != tenure.id,
        )
    ).all()
    for ot in other_tenures:
        ot_year = ot.coverage_start_date.year if ot.coverage_start_date else None
        if ot_year == cohort_year:
            ot.is_main = False

    db.commit()
    db.refresh(tenure)
    return {"status": "success", "tenure_id": tenure.id, "is_main": tenure.is_main}


@router.get("/stats/yoy")
def get_tenure_yoy_stats(
    show_hidden: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Retrieve year-over-year tenure statistics (counts, cars, growth, active vs lost)."""
    stmt = select(
        InsuranceTenure.id,
        InsuranceTenure.vehicle_no,
        InsuranceTenure.coverage_start_date,
        InsuranceTenure.coverage_end_date,
        InsuranceTenure.expiry_month,
        InsuranceTenure.stage,
    )
    stmt = stmt.where(InsuranceTenure.is_projected == False)
    if not show_hidden:
        stmt = stmt.where(InsuranceTenure.is_hidden == False)

    rows = db.execute(stmt).all()

    year_data: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "active": 0,
        "lost": 0,
        "tenure_ids": set(),
        "vehicles": set(),
    })

    all_years_tenures: set[str] = set()
    all_years_vehicles: set[str] = set()
    all_active = 0
    all_lost = 0

    for t_id, veh, start_dt, end_dt, exp_m, stage in rows:
        all_years_tenures.add(t_id)
        if veh:
            all_years_vehicles.add(veh)
        is_lost = stage in ("Close - Lose", "Others")
        if is_lost:
            all_lost += 1
        else:
            all_active += 1

        # Determine year(s) - strictly based on deal start date
        years_for_item = set()
        if start_dt:
            years_for_item.add(str(start_dt.year))

        for y_str in years_for_item:
            year_data[y_str]["tenure_ids"].add(t_id)
            if veh:
                year_data[y_str]["vehicles"].add(veh)
            if is_lost:
                year_data[y_str]["lost"] += 1
            else:
                year_data[y_str]["active"] += 1

    sorted_years = sorted(year_data.keys())
    result_list = []
    prev_total = None
    for y in sorted_years:
        tot = len(year_data[y]["tenure_ids"])
        growth = None
        if prev_total is not None and prev_total > 0:
            growth = round(((tot - prev_total) / prev_total) * 100, 1)
        prev_total = tot
        result_list.append({
            "year": y,
            "total": tot,
            "cars": len(year_data[y]["vehicles"]),
            "active": year_data[y]["active"],
            "lost": year_data[y]["lost"],
            "growth_percentage": growth,
        })

    return {
        "years": result_list,
        "all_years": {
            "total": len(all_years_tenures),
            "cars": len(all_years_vehicles),
            "active": all_active,
            "lost": all_lost,
        },
    }


class BulkDeleteTenuresRequest(BaseModel):
    tenure_ids: list[str] = Field(..., min_length=1, description="List of tenure IDs to delete")


@router.delete("/bulk")
def bulk_delete_tenures(
    payload: BulkDeleteTenuresRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Delete multiple vehicle renewal policy tenures from the ledger in bulk."""
    deleted_ids: list[str] = []
    for tid in payload.tenure_ids:
        tenure = db.get(InsuranceTenure, tid)
        if not tenure:
            continue
        child_sessions = db.scalars(
            select(SessionModel).where(SessionModel.tenure_id == tid)
        ).all()
        for s in child_sessions:
            s.tenure_id = None
            s.is_tenure_active = False
            s.status = "trash"
        db.delete(tenure)
        deleted_ids.append(tid)

    db.commit()
    return {"success": True, "deleted_count": len(deleted_ids), "deleted_ids": deleted_ids}


@router.delete("/{tenure_id}")
def delete_tenure_endpoint(
    tenure_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Delete a vehicle renewal policy tenure from the ledger."""
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise HTTPException(status_code=404, detail="Tenure not found")

    # Unlink or trash child sessions safely
    child_sessions = db.scalars(
        select(SessionModel).where(SessionModel.tenure_id == tenure_id)
    ).all()
    for s in child_sessions:
        s.tenure_id = None
        s.is_tenure_active = False
        s.status = "trash"

    db.delete(tenure)
    db.commit()
    return {"success": True, "deleted_tenure_id": tenure_id}


@router.get("/{tenure_id}")
def get_tenure(
    tenure_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Retrieve full lifecycle timeline, sourced quotes, and outcome for a tenure."""
    timeline = get_tenure_timeline(db, tenure_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Tenure not found")
    return timeline


@router.post("/{tenure_id}/generate-quote")
def generate_tenure_quote(
    tenure_id: str,
    payload: TenureGenerateQuoteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Generate or assign an official Risklocker quotation reference for an insurer under this tenure."""
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise HTTPException(status_code=404, detail="Tenure not found")

    sess = db.get(SessionModel, payload.session_id)
    if not sess or sess.tenure_id != tenure_id:
        raise HTTPException(status_code=400, detail="Invalid session for this tenure")

    if not sess.quotation_ref or not sess.quotation_ref.startswith("RL"):
        qref = generate_quotation_reference(db)
        sess.quotation_ref = qref
        sess.quotation_status = "ready"
        if sess.draft:
            fields = dict(sess.draft.fields or {})
            fields["quotation_reference"] = {"value": qref, "status": "ready", "message": ""}
            sess.draft.fields = fields
        db.flush()

    return {
        "tenure_id": tenure_id,
        "session_id": sess.id,
        "quotation_ref": sess.quotation_ref,
        "company": sess.detected_company,
        "status": sess.quotation_status,
    }


@router.post("/{tenure_id}/status")
def update_tenure_outcome(
    tenure_id: str,
    payload: TenureStatusUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Update status, winning quote, won premium, or hit/miss notes for this tenure."""
    try:
        updated = update_tenure_status(
            db,
            tenure_id,
            status=payload.status,
            user_id=user.id,
            winning_company_id=payload.winning_company_id,
            winning_quotation_ref=payload.winning_quotation_ref,
            won_premium=payload.won_premium,
            miss_reason=payload.miss_reason,
            notes=payload.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "success": True,
        "tenure": get_tenure_timeline(db, tenure_id),
    }


@router.post("/{tenure_id}/project-renewal")
def project_tenure_renewal(
    tenure_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Auto-projecting renewal slots is disabled. Policies strictly follow uploaded quotes."""
    return {
        "success": True,
        "message": "Auto-projection disabled. Policies are created when uploaded by staff.",
        "projected_tenure": get_tenure_timeline(db, tenure_id),
    }


@router.post("/{tenure_id}/shift-dates")
def shift_tenure_coverage_dates(
    tenure_id: str,
    payload: ShiftTenureDatesRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Shift tenure coverage dates (+1yr -1d sync) for late renewals or customer adjustments."""
    try:
        updated = shift_tenure_dates(
            db,
            tenure_id,
            new_start_date=payload.start_date,
            new_end_date=payload.end_date,
            force_past=payload.force_past,
            user_id=user.id,
        )
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "success": True,
        "tenure": get_tenure_timeline(db, updated.id),
    }


@router.post("/{tenure_id}/lapse")
def lapse_tenure(
    tenure_id: str,
    payload: LapseTenureRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Mark tenure as lapsed (unrenewed/customer discontinued) while preserving historical record."""
    try:
        lapsed = mark_tenure_lapsed(
            db,
            tenure_id,
            reason=payload.reason,
            user_id=user.id,
        )
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "success": True,
        "tenure": get_tenure_timeline(db, lapsed.id),
    }

