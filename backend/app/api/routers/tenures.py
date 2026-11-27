"""Tenures & Timeline API router."""

from __future__ import annotations

import calendar
from collections import defaultdict
from decimal import Decimal
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user, settings_dep
from app.auth.rbac import require_role
from app.core.config import Settings
from app.db.session import get_db
from app.models.enums import Role
from app.services.realtime_hub import publish_realtime_update
from app.models.tables import (
    CustomerAccount,
    InsuranceTenure,
    QuotationActivity,
    QuotationDraft,
    Session as SessionModel,
    TrackedVehicle,
    User,
)
from app.services.customer_account_service import resolve_or_create_customer
from app.services.insurance_tenure_service import (
    _calculate_policy_end_date,
    auto_project_next_renewal,
    ensure_next_year_renewal_tenures,
    get_tenure_timeline,
    mark_tenure_lapsed,
    resolve_or_create_tenure,
    shift_tenure_dates,
    update_tenure_status,
)
from app.services.ledger_query_service import (
    LedgerFilterSpec,
    apply_ledger_filters,
    compute_months_summary,
    compute_stage_summary,
    compute_yoy_stats,
    format_decimal_amount,
    load_authoritative_comparison_map,
    normalize_anchor,
    normalize_policy_status,
    parse_year_month,
)
from app.services.quotation_reference_service import generate_quotation_reference
from app.services.trash_service import soft_delete_tenure

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenures", tags=["tenures"])


class CreateTenureRequest(BaseModel):
    vehicle_no: str | None = Field(None, description="Vehicle registration plate")
    customer_name: str = Field(..., description="Customer / policyholder name")
    stage: str | None = Field(None, description="Initial pipeline stage")
    coverage_start_date: str | None = Field(None, description="Start date (YYYY-MM-DD)")
    coverage_end_date: str | None = Field(None, description="End date (YYYY-MM-DD)")
    chassis_no: str | None = Field(None, description="Chassis / VIN for new or unregistered vehicles")
    engine_no: str | None = Field(None, description="Engine number")
    engine_cc: str | None = Field(None, description="Engine capacity")
    car_brand: str | None = Field(None, description="Car brand / make (e.g. Honda, Toyota, Proton)")
    car_model: str | None = Field(None, description="Car model")
    manufacture_year: int | None = Field(None, description="Year of make (YOM)")
    ic_no: str | None = Field(None, description="Customer IC or Passport")
    phone: str | None = Field(None, description="Customer phone")
    email: str | None = Field(None, description="Customer email")
    pic_id: str | None = Field(None, description="Person in charge ID")
    sub_agent_name: str | None = Field(None, description="PIC / sub-agent name")
    windscreen_target: float | None = Field(None, description="Initial windscreen target")
    notes: str | None = Field(None, description="Notes")
    road_tax: float = 0.0
    runner_fee: float = 0.0
    include_road_tax: bool = True
    include_runner_fee: bool = True


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


import re
from pydantic import field_validator

def _parse_flexible_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).lower()
    if any(k in s for k in ("included", "free", "yes", "na", "n/a", "nil", "none")):
        return 0.0
    s = re.sub(r'[^\d\.\-]', '', str(v))
    try:
        return float(s) if s else 0.0
    except Exception:
        return 0.0

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

    @field_validator("won_premium", "road_tax", "runner_fee", mode="before")
    def parse_floats(cls, v):
        return _parse_flexible_float(v)
    status: str | None = None
    external_policy_start_date: str | None = None
    external_policy_end_date: str | None = None
    coverage_start_date: str | None = None
    coverage_end_date: str | None = None
    winning_company_name: str | None = None
    miss_reason: str | None = None
    external_insurer: str | None = None
    create_next_year_deal: bool | None = None


class BulkConfirmHitRequest(BaseModel):
    tenure_ids: list[str] = Field(default_factory=list, description="List of tenure IDs to confirm as hit/won")


@router.post("")
def create_tenure(
    payload: CreateTenureRequest,
    x_client_tab_id: str | None = Header(default=None, alias="X-Client-Tab-Id"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Create a new insurance tenure directly from staff comparison ledger input."""
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
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
    if payload.stage:
        tenure.stage = payload.stage.strip()
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
        if payload.car_brand:
            tenure.tracked_vehicle.car_brand = payload.car_brand.strip()
        if payload.car_model:
            tenure.tracked_vehicle.car_model = payload.car_model.strip()
        if payload.manufacture_year:
            tenure.tracked_vehicle.manufacture_year = payload.manufacture_year
        if payload.engine_cc:
            tenure.tracked_vehicle.engine_cc = payload.engine_cc.strip()
        if payload.chassis_no:
            tenure.tracked_vehicle.chassis_no = payload.chassis_no.strip()
        if payload.engine_no:
            tenure.tracked_vehicle.engine_no = payload.engine_no.strip()

    db.commit()
    publish_realtime_update(
        scope="ledger",
        resource_id=tenure.id,
        actor=user,
        summary="Tenure created",
        origin_tab_id=x_client_tab_id if isinstance(x_client_tab_id, str) else None,
    )
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


@router.post("/{tenure_id}/prune-superseded")
def prune_tenure_superseded_quotations(
    tenure_id: str,
    dry_run: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Maintenance endpoint to prune superseded quotation files for a tenure."""
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure or tenure.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Tenure not found")
    from app.services.storage_janitor_service import prune_superseded_quotations
    return prune_superseded_quotations(db=db, tenure_id=tenure_id, dry_run=dry_run)



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
        .outerjoin(SessionModel.tenure)
        .where(
            SessionModel.status != "trash",
            or_(SessionModel.tenure_id.is_(None), InsuranceTenure.deleted_at.is_(None)),
        )
    )

    if vehicle_no and vehicle_no.strip():
        veh = vehicle_no.strip().upper()
        stmt = stmt.where(InsuranceTenure.vehicle_no == veh)

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
    month: str | None = Query(None, description="Month 1-12 or YYYY-MM"),
    anchor: str = Query("all", description="Anchor lens: all, expiring, or starting"),
    category: str | None = Query(None, description="active, lost, or all"),
    status: str | None = Query(None),
    policy_status: str = Query("all", description="all, issued, or pending"),
    search: str | None = Query(None),
    show_hidden: bool = False,
    show_discarded: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Retrieve live counts for the stage KPI summary cards matching active filter."""
    _ = user
    parsed_year, parsed_month = parse_year_month(year, month)
    spec = LedgerFilterSpec(
        year=parsed_year,
        month=parsed_month,
        anchor=normalize_anchor(anchor),
        category=category,
        status=status,
        policy_status=normalize_policy_status(policy_status),
        search=search,
        show_hidden=show_hidden,
        show_discarded=show_discarded,
    )
    return compute_stage_summary(db, spec)


@router.get("/months")
def list_tenure_months(
    anchor: str = Query("all", description="Anchor lens: all, expiring, or starting"),
    category: str | None = Query(None, description="active, lost, or all"),
    stage: str | None = Query(None),
    status: str | None = Query(None),
    policy_status: str = Query("all", description="all, issued, or pending"),
    search: str | None = Query(None),
    show_hidden: bool = False,
    show_discarded: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Retrieve list of available months with start, end, and anchor-matched total statistics."""
    _ = user
    spec = LedgerFilterSpec(
        anchor=normalize_anchor(anchor),
        category=category,
        stage=stage,
        status=status,
        policy_status=normalize_policy_status(policy_status),
        search=search,
        show_hidden=show_hidden,
        show_discarded=show_discarded,
    )
    return compute_months_summary(db, spec)


@router.get("")
def list_tenures(
    month: str | None = None,
    year: int | None = None,
    anchor: str = Query("all", description="Anchor lens: all, expiring, or starting"),
    search: str | None = None,
    status: str | None = None,
    stage: str | None = None,
    category: str | None = None,
    policy_status: str = Query("all", description="all, issued, or pending"),
    sub_agent: str | None = None,
    tenure_ids: str | None = Query(default=None, description="Comma-separated tenure UUIDs to isolate"),
    show_hidden: bool = False,
    show_discarded: bool = False,
    sort_by: str | None = Query("last_activity", description="Sort by last_activity, vehicle_no, customer_name, stage, coverage_end_date, coverage_period, created_at, pic"),
    sort_dir: str | None = Query("desc", description="Sort direction asc or desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    _ = user
    norm_anchor = normalize_anchor(anchor)
    parsed_year, parsed_month = parse_year_month(year, month)
    target_year = parsed_year
    raw_tids = tenure_ids if isinstance(tenure_ids, str) else None
    parsed_tenure_ids = tuple(t.strip() for t in (raw_tids or "").split(",") if t.strip()) or None

    spec = LedgerFilterSpec(
        year=parsed_year,
        month=parsed_month,
        anchor=norm_anchor,
        category=category,
        stage=stage,
        status=status,
        policy_status=normalize_policy_status(policy_status),
        sub_agent=sub_agent,
        search=search,
        tenure_ids=parsed_tenure_ids,
        show_hidden=show_hidden,
        show_discarded=show_discarded,
    )
    query = apply_ledger_filters(select(InsuranceTenure), spec, include_period=True)

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
    elif s_by in ("coverage_end_date", "coverage_period"):
        sort_col = InsuranceTenure.coverage_end_date if s_by == "coverage_end_date" else InsuranceTenure.coverage_start_date
        query = query.order_by(sort_col.desc().nullslast() if is_desc else sort_col.asc().nullsfirst(), InsuranceTenure.vehicle_no.asc())
    elif s_by == "created_at":
        sort_col = InsuranceTenure.created_at
        query = query.order_by(sort_col.desc().nullslast() if is_desc else sort_col.asc().nullsfirst(), InsuranceTenure.vehicle_no.asc())
    elif s_by == "pic":
        sort_col = InsuranceTenure.sub_agent_name
        query = query.order_by(sort_col.desc().nullslast() if is_desc else sort_col.asc().nullsfirst(), InsuranceTenure.vehicle_no.asc())
    else:
        if is_desc:
            query = query.order_by(InsuranceTenure.last_activity_at.desc().nullslast(), InsuranceTenure.coverage_end_date.asc())
        else:
            query = query.order_by(InsuranceTenure.last_activity_at.asc().nullsfirst(), InsuranceTenure.coverage_end_date.asc())

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    from app.services.ledger_query_service import is_issued_policy_expr

    tab_base_spec = LedgerFilterSpec(
        year=parsed_year,
        month=parsed_month,
        anchor=norm_anchor,
        category="active",
        stage=stage,
        status=status,
        policy_status="all",
        sub_agent=sub_agent,
        search=search,
        tenure_ids=parsed_tenure_ids,
        show_hidden=show_hidden,
        show_discarded=show_discarded,
    )
    tab_base_query = apply_ledger_filters(select(InsuranceTenure.id), tab_base_spec, include_period=True)
    active_total = db.scalar(select(func.count()).select_from(tab_base_query.subquery())) or 0
    issued_count = db.scalar(
        select(func.count()).select_from(tab_base_query.where(is_issued_policy_expr()).subquery())
    ) or 0
    pending_count = max(0, active_total - issued_count)

    p = page if isinstance(page, int) else 1
    ps = page_size if isinstance(page_size, int) else 50
    offset = (p - 1) * ps
    paged_query = (
        query.options(
            selectinload(InsuranceTenure.pic),
            selectinload(InsuranceTenure.winning_company),
            selectinload(InsuranceTenure.customer),
            selectinload(InsuranceTenure.tracked_vehicle),
            selectinload(InsuranceTenure.created_by),
        )
        .offset(offset)
        .limit(ps)
    )
    tenures = list(db.scalars(paged_query).all())

    tenure_ids = [t.id for t in tenures]
    comp_by_session, comp_by_company = load_authoritative_comparison_map(db, tenure_ids)
    cn_session_ids = [t.covernote_session_id for t in tenures if t.covernote_session_id]
    sessions_by_tenure: dict[str, list[SessionModel]] = defaultdict(list)
    if tenure_ids:
        where_cond = SessionModel.tenure_id.in_(tenure_ids)
        if cn_session_ids:
            where_cond = or_(where_cond, SessionModel.id.in_(cn_session_ids))
        all_sessions = list(
            db.scalars(
                select(SessionModel)
                .options(selectinload(SessionModel.draft), selectinload(SessionModel.uploaded_file))
                .where(
                    where_cond,
                    SessionModel.status != "trash",
                )
            ).all()
        )
        for s in all_sessions:
            if s.tenure_id:
                if s.is_tenure_active or getattr(s, "document_type", "quotation") == "covernote" or any(t.covernote_session_id == s.id for t in tenures):
                    sessions_by_tenure[s.tenure_id].append(s)
            for t in tenures:
                if t.covernote_session_id == s.id and s not in sessions_by_tenure[t.id]:
                    sessions_by_tenure[t.id].append(s)

    now = datetime.now(timezone.utc)
    items = []
    for t in tenures:
        sessions = sessions_by_tenure.get(t.id, [])

        is_upcoming_renewal = False
        if target_year and t.coverage_start_date and t.coverage_start_date.year < target_year:
            is_upcoming_renewal = True

        sourced = []
        gen_quotes = []
        for s in sessions:
            if getattr(s, "document_type", "quotation") == "covernote" or s.id == t.covernote_session_id:
                continue

            draft = s.draft
            f = draft.fields if draft else {}

            def _val(k: str) -> Any:
                item = f.get(k)
                return item.get("value") if isinstance(item, dict) else item

            s_comp_id = getattr(s, "company_id", None) or (getattr(draft, "company_id", None) if draft else None)
            comp_entry = comp_by_session.get((t.id, s.id))
            if comp_entry is None and s_comp_id:
                comp_entry = comp_by_company.get((t.id, s_comp_id))

            raw_tot = comp_entry.total_payable if comp_entry is not None else (_val("total_amount") or _val("total_payable"))
            tot = format_decimal_amount(raw_tot)
            raw_sum_ins = (
                comp_entry.sum_insured
                if (comp_entry is not None and comp_entry.sum_insured)
                else (_val("sum_insured") or _val("coverage_amount"))
            )
            sum_ins = format_decimal_amount(raw_sum_ins)
            comp = (comp_entry.company_name if comp_entry and comp_entry.company_name else None) or s.detected_company or "Unknown"

            is_win = bool(
                (comp_entry is not None and comp_entry.is_recommended)
                or (t.winning_quotation_ref and s.quotation_ref == t.winning_quotation_ref)
                or (t.winning_company_id and s_comp_id == t.winning_company_id)
            )
            s_fn = s.uploaded_file.original_filename if s.uploaded_file else f"{comp}.pdf"
            s_start = s.coverage_start_date.isoformat() if s.coverage_start_date else None
            s_end = s.coverage_end_date.isoformat() if s.coverage_end_date else None
            s_period = (
                f"{s.coverage_start_date.strftime('%d/%m/%Y')} - {s.coverage_end_date.strftime('%d/%m/%Y')}"
                if (s.coverage_start_date and s.coverage_end_date)
                else None
            )

            try:
                sort_payable = Decimal(str(tot).replace(",", "").strip()) if tot is not None else Decimal("999999999")
            except Exception:
                sort_payable = Decimal("999999999")
            sort_rank = (
                (comp_entry.manual_rank or comp_entry.rank or 999)
                if comp_entry is not None
                else 999
            )

            sourced.append({
                "session_id": s.id,
                "company": comp,
                "version": s.tenure_version,
                "total_payable": tot,
                "sum_insured": sum_ins,
                "uploaded_file_id": s.uploaded_file_id,
                "file_name": s_fn,
                "coverage_start_date": s_start,
                "coverage_end_date": s_end,
                "coverage_period_formatted": s_period,
                "document_type": getattr(s, "document_type", "quotation"),
                "policy_number": getattr(s, "policy_number", None),
                "is_winner": is_win,
                "_sort_rank": sort_rank,
                "_sort_payable": sort_payable,
            })

            if s.quotation_ref and s.quotation_ref.startswith("RL"):
                gen_quotes.append({
                    "session_id": s.id,
                    "quotation_ref": s.quotation_ref,
                    "company": comp,
                    "status": s.quotation_status,
                })

        sourced.sort(key=lambda q: (not q["is_winner"], q["_sort_rank"], q["_sort_payable"]))
        for q in sourced:
            q.pop("_sort_rank", None)
            q.pop("_sort_payable", None)

        stage_up = t.stage_updated_at if t.stage_updated_at.tzinfo else t.stage_updated_at.replace(tzinfo=timezone.utc)
        days_in_stage = max(0, (now - stage_up).days) if t.stage_updated_at else 0

        cn_sess = next((s for s in sessions if s.id == t.covernote_session_id), None)
        if not cn_sess:
            cn_sess = next((s for s in sessions if getattr(s, "document_type", "quotation") == "covernote"), None)

        has_real_policy_number = bool(t.policy_number and t.policy_number.strip())
        covernote_info = None
        if cn_sess:
            f_cn = cn_sess.draft.fields if cn_sess.draft and isinstance(cn_sess.draft.fields, dict) else {}

            def _cn_val(k: str) -> Any:
                item = f_cn.get(k)
                return item.get("value") if isinstance(item, dict) else item

            s_date = cn_sess.coverage_start_date or t.coverage_start_date
            e_date = cn_sess.coverage_end_date or t.coverage_end_date
            s_fmt = s_date.strftime("%d/%m/%Y") if s_date else ""
            e_fmt = e_date.strftime("%d/%m/%Y") if e_date else ""
            cov_period_str = f"{s_fmt} - {e_fmt}" if s_fmt and e_fmt else (s_fmt or "—")

            ws_val = _cn_val("windscreen_sum_insured") or _cn_val("windscreen")
            tow_val = _cn_val("towing_km") or _cn_val("towing") or _cn_val("towing_limit") or "Unlimited"
            cov_type = str(_cn_val("coverage_type") or "Comprehensive").title()

            covernote_info = {
                "session_id": cn_sess.id,
                "company": cn_sess.detected_company or (t.winning_company.name if t.winning_company else "Underwriter"),
                "policy_number": cn_sess.policy_number or t.policy_number,
                "total_payable": _cn_val("total_amount") or _cn_val("total_payable") or (float(t.won_premium) if t.won_premium is not None else None),
                "sum_insured": _cn_val("sum_insured") or _cn_val("coverage_amount"),
                "coverage_start_date": s_date.isoformat() if s_date else None,
                "coverage_end_date": e_date.isoformat() if e_date else None,
                "coverage_period_formatted": cov_period_str,
                "perils": f"{cov_type} Policy",
                "windscreen": ws_val,
                "towing": tow_val,
                "uploaded_file_id": cn_sess.uploaded_file_id,
                "file_name": cn_sess.uploaded_file.original_filename if cn_sess.uploaded_file else f"{cn_sess.detected_company or 'Policy'}.pdf",
            }
        elif has_real_policy_number or t.stage == "Close - Win" or t.status == "hit":
            s_date = t.coverage_start_date
            e_date = t.coverage_end_date
            s_fmt = s_date.strftime("%d/%m/%Y") if s_date else ""
            e_fmt = e_date.strftime("%d/%m/%Y") if e_date else ""
            cov_period_str = f"{s_fmt} - {e_fmt}" if s_fmt and e_fmt else (s_fmt or "—")
            covernote_info = {
                "session_id": None,
                "company": t.winning_company.name if t.winning_company else "Underwriter",
                "policy_number": t.policy_number,
                "total_payable": float(t.won_premium) if t.won_premium is not None else None,
                "sum_insured": None,
                "coverage_start_date": s_date.isoformat() if s_date else None,
                "coverage_end_date": e_date.isoformat() if e_date else None,
                "coverage_period_formatted": cov_period_str,
                "perils": "Comprehensive Policy",
                "windscreen": None,
                "towing": "Unlimited",
                "uploaded_file_id": None,
                "file_name": None,
            }

        win_quote = next((sq for sq in sourced if sq.get("is_winner")), None)
        has_selected_winner = bool(t.winning_company_id or t.won_premium is not None or win_quote)
        winning_file_id = (cn_sess.uploaded_file_id if cn_sess else None) or (win_quote.get("uploaded_file_id") if win_quote else None)
        winning_file_name = (cn_sess.uploaded_file.original_filename if cn_sess and cn_sess.uploaded_file else None) or (win_quote.get("file_name") if win_quote else None)

        latest_act = t.last_activity_at or t.updated_at or t.created_at
        for s in sessions:
            s_act = s.updated_at or s.created_at
            if s_act:
                s_act_tz = s_act if s_act.tzinfo else s_act.replace(tzinfo=timezone.utc)
                l_act_tz = latest_act if (latest_act and latest_act.tzinfo) else (latest_act.replace(tzinfo=timezone.utc) if latest_act else None)
                if not l_act_tz or s_act_tz > l_act_tz:
                    latest_act = s_act_tz

        upcoming_renewal_start = None
        upcoming_renewal_end = None
        if is_upcoming_renewal and t.coverage_end_date:
            renew_start = t.coverage_end_date + timedelta(days=1)
            renew_end = _calculate_policy_end_date(renew_start)
            upcoming_renewal_start = renew_start.isoformat()
            upcoming_renewal_end = renew_end.isoformat()

        out_stage = t.stage or "Quotations"
        out_status = t.status
        out_covernote_policy = covernote_info
        out_is_covernote_issued = bool(covernote_info)
        out_winning_file_id = winning_file_id
        out_winning_file_name = winning_file_name
        out_won_premium = float(t.won_premium) if t.won_premium is not None else None
        out_cov_start = t.coverage_start_date.isoformat()
        out_cov_end = t.coverage_end_date.isoformat()
        out_exp_month = t.expiry_month

        items.append({
            "id": t.id,
            "vehicle_no": t.vehicle_no,
            "customer_name": t.customer_name,
            "chassis_no": t.tracked_vehicle.chassis_no if t.tracked_vehicle else None,
            "engine_no": t.tracked_vehicle.engine_no if t.tracked_vehicle else None,
            "car_brand": t.tracked_vehicle.car_brand if t.tracked_vehicle else None,
            "car_model": t.tracked_vehicle.car_model if t.tracked_vehicle else None,
            "engine_cc": t.tracked_vehicle.engine_cc if t.tracked_vehicle else None,
            "coverage_start_date": out_cov_start,
            "coverage_end_date": out_cov_end,
            "expiry_month": out_exp_month,
            "previous_coverage_start_date": t.coverage_start_date.isoformat(),
            "previous_coverage_end_date": t.coverage_end_date.isoformat(),
            "is_upcoming_renewal": is_upcoming_renewal,
            "upcoming_renewal_start": upcoming_renewal_start,
            "upcoming_renewal_end": upcoming_renewal_end,
            "has_selected_winner": has_selected_winner,
            "previous_tenure_id": t.previous_tenure_id,
            "status": out_status,
            "stage": out_stage,
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
            "winning_file_id": out_winning_file_id,
            "winning_file_name": out_winning_file_name,
            "covernote_session_id": t.covernote_session_id,
            "policy_number": t.policy_number or (cn_sess.policy_number if cn_sess else None),
            "covernote_policy": out_covernote_policy,
            "previous_covernote_policy": covernote_info if is_upcoming_renewal else None,
            "is_covernote_issued": out_is_covernote_issued,
            "won_premium": out_won_premium,
            "miss_reason": t.miss_reason,
            "loss_reason_category": t.loss_reason_category,
            "road_tax": float(t.road_tax or 0.0),
            "runner_fee": float(t.runner_fee or 0.0),
            "include_road_tax": t.include_road_tax if t.include_road_tax is not None else True,
            "include_runner_fee": t.include_runner_fee if t.include_runner_fee is not None else True,
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
            "last_activity_at": latest_act.isoformat() if latest_act else None,
            "created_at": t.created_at.isoformat(),
            "created_by_id": t.created_by_id,
            "created_by_email": t.created_by.email if t.created_by else None,
            "created_by_name": t.created_by.name if t.created_by else None,
        })

    return {
        "items": items,
        "total": total,
        "active_total": active_total,
        "issued_count": issued_count,
        "pending_count": pending_count,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/{tenure_id}/ledger-fields")
def update_tenure_ledger_fields(
    tenure_id: str,
    payload: UpdateTenureLedgerRequest,
    x_client_tab_id: str | None = Header(default=None, alias="X-Client-Tab-Id"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Inline update operational fields on a tenure directly from the Motor Renewal Ledger."""
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure or tenure.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Tenure not found")

    now = datetime.now(timezone.utc)
    old_stage = tenure.stage
    old_status = tenure.status

    if payload.stage is not None and payload.stage != tenure.stage:
        # Pipeline Lock Invariant:
        # If an official Cover Note is active, do not allow reverting to Quotations or Material to Client
        if payload.stage in ("Quotations", "Material to Client") and tenure.covernote_session_id:
            raise HTTPException(
                status_code=400,
                detail="Cannot revert stage to Quotations or Material to Client while an official Cover Note is linked. Unlink the Cover Note in the Marketing Comparison table first."
            )
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
    elif payload.winning_company_name is not None and payload.winning_company_name.strip():
        from app.models.tables import InsuranceCompany
        comp = db.scalar(
            select(InsuranceCompany).where(
                or_(
                    InsuranceCompany.name.ilike(payload.winning_company_name.strip()),
                    InsuranceCompany.slug.ilike(payload.winning_company_name.strip()),
                )
            )
        )
        if comp:
            tenure.winning_company_id = comp.id

    if payload.coverage_start_date is not None and payload.coverage_start_date.strip():
        try:
            s_dt = datetime.strptime(payload.coverage_start_date.strip()[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            tenure.coverage_start_date = s_dt
            if not (payload.coverage_end_date and payload.coverage_end_date.strip()) and tenure.coverage_end_date:
                tenure.expiry_month = f"{tenure.coverage_end_date.year}-{tenure.coverage_end_date.month:02d}"
        except Exception:
            pass
    if payload.coverage_end_date is not None and payload.coverage_end_date.strip():
        try:
            e_dt = datetime.strptime(payload.coverage_end_date.strip()[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            tenure.coverage_end_date = e_dt
            tenure.expiry_month = f"{e_dt.year}-{e_dt.month:02d}"
        except Exception:
            pass
    if payload.winning_quotation_ref is not None:
        tenure.winning_quotation_ref = payload.winning_quotation_ref
    if payload.won_premium is not None:
        tenure.won_premium = payload.won_premium
    if payload.road_tax is not None:
        tenure.road_tax = payload.road_tax
    if payload.runner_fee is not None:
        tenure.runner_fee = payload.runner_fee
    if payload.vehicle_no is not None and payload.vehicle_no.strip():
        clean_v = payload.vehicle_no.replace(" ", "").upper()
        tenure.vehicle_no = clean_v
        if tenure.tracked_vehicle:
            tv_clean = (tenure.tracked_vehicle.vehicle_no or "").replace(" ", "").upper()
            if tv_clean != clean_v:
                existing_veh = db.scalar(
                    select(TrackedVehicle).where(
                        or_(
                            TrackedVehicle.vehicle_no == clean_v,
                            func.replace(TrackedVehicle.vehicle_no, " ", "") == clean_v,
                        ),
                        TrackedVehicle.id != tenure.tracked_vehicle.id,
                    )
                )
                if existing_veh:
                    tenure.tracked_vehicle = existing_veh
                    tenure.tracked_vehicle_id = existing_veh.id
                else:
                    tenure.tracked_vehicle.vehicle_no = clean_v

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

            # Propagate customer name and IC to non-sandbox quotation drafts under this customer or tenure
            from sqlalchemy.orm.attributes import flag_modified
            sessions_to_sync = list(
                db.scalars(
                    select(SessionModel).where(
                        or_(
                            SessionModel.customer_id == cust.id,
                            SessionModel.tenure_id == tenure.id,
                        ),
                        or_(
                            SessionModel.tenure_id == tenure.id,
                            SessionModel.is_test.is_(False),
                        ),
                    )
                ).all()
            )
            for s in sessions_to_sync:
                if getattr(s, "is_test", False) and s.tenure_id != tenure.id:
                    continue
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
                    flag_modified(s.draft, "fields")

    if payload.is_discarded is not None:
        tenure.is_discarded = payload.is_discarded
    if payload.miss_reason is not None:
        tenure.miss_reason = payload.miss_reason.strip() or None
    if payload.external_insurer is not None and payload.external_insurer.strip():
        ext_txt = f"External insurer: {payload.external_insurer.strip()}"
        if not tenure.miss_reason:
            tenure.miss_reason = ext_txt
        elif ext_txt not in tenure.miss_reason:
            tenure.miss_reason = f"{tenure.miss_reason} ({ext_txt})"
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
    from app.services.insurance_tenure_service import (
        create_next_year_renewal_tenure,
        remove_auto_created_next_year_tenure,
    )
    is_hit = (tenure.stage == "Close - Win" or tenure.status == "hit") and not tenure.is_discarded
    is_miss = (tenure.stage == "Close - Lose" or tenure.status == "miss") and not tenure.is_discarded
    was_hit = (old_stage == "Close - Win" or old_status == "hit")

    if payload.is_discarded or tenure.is_discarded:
        remove_auto_created_next_year_tenure(db, tenure)
    elif is_hit:
        create_next_year_renewal_tenure(db, tenure, user_id=user.id)
    elif is_miss:
        if payload.create_next_year_deal is not False:
            create_next_year_renewal_tenure(db, tenure, user_id=user.id)
        else:
            remove_auto_created_next_year_tenure(db, tenure)
    elif was_hit and not is_hit:
        remove_auto_created_next_year_tenure(db, tenure)

    tenure.last_activity_at = now
    db.commit()
    publish_realtime_update(
        scope="ledger",
        resource_id=tenure.id,
        actor=user,
        summary="Ledger fields updated",
        extra_scopes=("comparison",),
        origin_tab_id=x_client_tab_id if isinstance(x_client_tab_id, str) else None,
    )
    return {"success": True, "id": tenure.id, "stage": tenure.stage, "is_main": tenure.is_main}


@router.post("/bulk-confirm-hit")
def bulk_confirm_hit(
    payload: BulkConfirmHitRequest,
    x_client_tab_id: str | None = Header(default=None, alias="X-Client-Tab-Id"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Bulk confirm multiple tenures as won (Hit / Issued Policy) and roll forward next year renewals."""
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    from app.services.insurance_tenure_service import (
        create_next_year_renewal_tenure,
        record_stage_timestamp,
    )
    now = datetime.now(timezone.utc)
    updated_ids: list[str] = []
    for tid in payload.tenure_ids:
        t = db.get(InsuranceTenure, tid)
        if t and not t.is_discarded and t.deleted_at is None:
            t.stage = "Close - Win"
            t.status = "hit"
            record_stage_timestamp(t, "Close - Win")
            t.last_activity_at = now
            create_next_year_renewal_tenure(db, t, user_id=user.id)
            updated_ids.append(t.id)

    db.commit()
    publish_realtime_update(
        scope="ledger",
        resource_id="all",
        actor=user,
        summary="Bulk confirmed hit",
        origin_tab_id=x_client_tab_id if isinstance(x_client_tab_id, str) else None,
    )
    return {"success": True, "updated_count": len(updated_ids), "updated_ids": updated_ids}


@router.post("/{tenure_id}/set-main")
def set_tenure_as_main(
    tenure_id: str,
    x_client_tab_id: str | None = Header(default=None, alias="X-Client-Tab-Id"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Mark this tenure as the approved/main policy for this vehicle and cohort."""
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure or tenure.deleted_at is not None:
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
    publish_realtime_update(
        scope="ledger",
        resource_id=tenure.id,
        actor=user,
        summary="Main policy updated",
        origin_tab_id=x_client_tab_id if isinstance(x_client_tab_id, str) else None,
    )
    return {"status": "success", "tenure_id": tenure.id, "is_main": tenure.is_main}


@router.get("/stats/yoy")
def get_tenure_yoy_stats(
    anchor: str = Query("all", description="Anchor lens: all, expiring, or starting"),
    category: str | None = Query(None, description="active, lost, or all"),
    show_hidden: bool = False,
    show_discarded: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Retrieve year-over-year tenure statistics matching the shared ledger filter predicate."""
    _ = user
    spec = LedgerFilterSpec(
        anchor=normalize_anchor(anchor),
        category=category,
        show_hidden=show_hidden,
        show_discarded=show_discarded,
    )
    return compute_yoy_stats(db, spec)


@router.post("/sync-next-year-renewals")
def sync_next_year_renewals(
    target_year: int = Query(default=2027, ge=2024, le=2035),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Admin endpoint to ensure next-year renewals are synced for all active vehicles."""
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    created = ensure_next_year_renewal_tenures(db, target_year=target_year, user_id=user.id)
    return {
        "status": "success",
        "target_year": target_year,
        "created_count": len(created),
        "created_ids": [t.id for t in created],
    }


class BulkDeleteTenuresRequest(BaseModel):
    tenure_ids: list[str] = Field(..., min_length=1, description="List of tenure IDs to delete")


@router.delete("/bulk")
def bulk_delete_tenures(
    payload: BulkDeleteTenuresRequest,
    x_client_tab_id: str | None = Header(default=None, alias="X-Client-Tab-Id"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Soft-delete multiple vehicle renewal policy tenures into 30-day Trash in bulk."""
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    deleted_ids: list[str] = []
    for tid in payload.tenure_ids:
        tenure = db.get(InsuranceTenure, tid)
        if not tenure or tenure.deleted_at is not None:
            continue
        soft_delete_tenure(db, settings, user, tenure, commit=False)
        deleted_ids.append(tid)

    db.commit()
    publish_realtime_update(
        scope="ledger",
        resource_id="all",
        actor=user,
        summary="Tenures moved to Trash",
        extra_scopes=("comparison",),
        origin_tab_id=x_client_tab_id if isinstance(x_client_tab_id, str) else None,
    )
    return {"success": True, "deleted_count": len(deleted_ids), "deleted_ids": deleted_ids}


@router.delete("/{tenure_id}")
def delete_tenure_endpoint(
    tenure_id: str,
    x_client_tab_id: str | None = Header(default=None, alias="X-Client-Tab-Id"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Soft-delete a vehicle renewal policy tenure into 30-day Trash."""
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure or tenure.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Tenure not found")

    soft_delete_tenure(db, settings, user, tenure, commit=True)
    publish_realtime_update(
        scope="ledger",
        resource_id=tenure_id,
        actor=user,
        summary="Tenure moved to Trash",
        extra_scopes=("comparison",),
        origin_tab_id=x_client_tab_id if isinstance(x_client_tab_id, str) else None,
    )
    return {"success": True, "deleted_tenure_id": tenure_id}


@router.get("/yoy-stats")
def get_tenure_yoy_stats_alias(
    anchor: str = Query("all", description="Anchor lens: all, expiring, or starting"),
    category: str | None = Query(None, description="active, lost, or all"),
    show_hidden: bool = False,
    show_discarded: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Alias for /stats/yoy to satisfy ledger statistics queries."""
    return get_tenure_yoy_stats(
        anchor=anchor,
        category=category,
        show_hidden=show_hidden,
        show_discarded=show_discarded,
        db=db,
        user=user,
    )


@router.get("/pics")
def get_tenure_pics_alias(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Retrieve person-in-charge directory for tenure filtering."""
    from app.services.pic_service import list_pics
    return {"pics": list_pics(db)}


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
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure or tenure.deleted_at is not None:
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
    x_client_tab_id: str | None = Header(default=None, alias="X-Client-Tab-Id"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Update status, winning quote, won premium, or hit/miss notes for this tenure."""
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
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

    publish_realtime_update(
        scope="ledger",
        resource_id=tenure_id,
        actor=user,
        summary="Tenure outcome updated",
        extra_scopes=("comparison",),
        origin_tab_id=x_client_tab_id if isinstance(x_client_tab_id, str) else None,
    )
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
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    return {
        "success": True,
        "message": "Auto-projection disabled. Policies are created when uploaded by staff.",
        "projected_tenure": get_tenure_timeline(db, tenure_id),
    }


@router.post("/{tenure_id}/shift-dates")
def shift_tenure_coverage_dates(
    tenure_id: str,
    payload: ShiftTenureDatesRequest,
    x_client_tab_id: str | None = Header(default=None, alias="X-Client-Tab-Id"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Shift tenure coverage dates (+1yr -1d sync) for late renewals or customer adjustments."""
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
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

    publish_realtime_update(
        scope="ledger",
        resource_id=updated.id,
        actor=user,
        summary="Coverage dates shifted",
        extra_scopes=("comparison",),
        origin_tab_id=x_client_tab_id if isinstance(x_client_tab_id, str) else None,
    )
    return {
        "success": True,
        "tenure": get_tenure_timeline(db, updated.id),
    }


@router.post("/{tenure_id}/lapse")
def lapse_tenure(
    tenure_id: str,
    payload: LapseTenureRequest,
    x_client_tab_id: str | None = Header(default=None, alias="X-Client-Tab-Id"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Mark tenure as lapsed (unrenewed/customer discontinued) while preserving historical record."""
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
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

    publish_realtime_update(
        scope="ledger",
        resource_id=lapsed.id,
        actor=user,
        summary="Tenure marked lapsed",
        extra_scopes=("comparison",),
        origin_tab_id=x_client_tab_id if isinstance(x_client_tab_id, str) else None,
    )
    return {
        "success": True,
        "tenure": get_tenure_timeline(db, lapsed.id),
    }

