"""Tenures & Timeline API router."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.db.session import get_db
from app.models.tables import (
    InsuranceTenure,
    QuotationActivity,
    QuotationDraft,
    Session as SessionModel,
    User,
)
from app.services.insurance_tenure_service import (
    get_tenure_timeline,
    resolve_or_create_tenure,
    update_tenure_status,
)
from app.services.quotation_reference_service import generate_quotation_reference

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenures", tags=["tenures"])


class CreateTenureRequest(BaseModel):
    vehicle_no: str = Field(..., description="Vehicle registration plate")
    customer_name: str = Field(..., description="Customer / policyholder name")
    coverage_start_date: str | None = Field(None, description="Start date (YYYY-MM-DD)")
    coverage_end_date: str | None = Field(None, description="End date (YYYY-MM-DD)")
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


@router.post("")
def create_tenure(
    payload: CreateTenureRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Create a new insurance tenure directly from staff comparison ledger input."""
    tenure = resolve_or_create_tenure(
        db,
        vehicle_no=payload.vehicle_no,
        customer_name=payload.customer_name,
        start_date=payload.coverage_start_date,
        end_date=payload.coverage_end_date,
    )
    if payload.road_tax > 0.0:
        tenure.road_tax = payload.road_tax
    if payload.runner_fee > 0.0:
        tenure.runner_fee = payload.runner_fee
    db.commit()
    return {"id": tenure.id, "vehicle_no": tenure.vehicle_no, "customer_name": tenure.customer_name}


@router.get("/months")
def list_tenure_months(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Retrieve list of available expiry months with tenure statistics."""
    # Query aggregated stats from DB
    stmt = (
        select(
            InsuranceTenure.expiry_month,
            func.count(InsuranceTenure.id).label("total"),
            func.count(func.nullif(InsuranceTenure.status != "hit", True)).label("hit"),
            func.count(func.nullif(InsuranceTenure.status != "miss", True)).label("miss"),
        )
        .group_by(InsuranceTenure.expiry_month)
        .order_by(InsuranceTenure.expiry_month.asc())
    )
    rows = db.execute(stmt).all()

    month_map: dict[str, dict[str, Any]] = {}
    for r in rows:
        month_str = r[0]
        total_cnt = int(r[1] or 0)
        hit_cnt = int(r[2] or 0)
        miss_cnt = int(r[3] or 0)
        pending_cnt = max(0, total_cnt - hit_cnt - miss_cnt)
        month_map[month_str] = {
            "month": month_str,
            "total": total_cnt,
            "hit": hit_cnt,
            "miss": miss_cnt,
            "pending": pending_cnt,
        }

    # Pre-populate active window (from 3 months prior to 12 months in the future)
    now = datetime.now(timezone.utc)
    cur_year = now.year
    cur_month = now.month

    for offset in range(-3, 13):
        m = (cur_month - 1 + offset) % 12 + 1
        y = cur_year + ((cur_month - 1 + offset) // 12)
        key = f"{y:04d}-{m:02d}"
        if key not in month_map:
            month_map[key] = {
                "month": key,
                "total": 0,
                "hit": 0,
                "miss": 0,
                "pending": 0,
            }

    sorted_months = sorted(month_map.values(), key=lambda x: x["month"])
    return {"months": sorted_months}


@router.get("")
def list_tenures(
    month: str | None = None,
    search: str | None = None,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Retrieve customer-vehicle tenures for the monthly ledger with search and filters."""
    query = select(InsuranceTenure)

    if month and month.strip() != "all":
        m_str = month.strip()
        if len(m_str) == 4:
            query = query.where(InsuranceTenure.expiry_month.startswith(m_str))
        else:
            query = query.where(InsuranceTenure.expiry_month == m_str)

    if status:
        query = query.where(InsuranceTenure.status == status.strip())

    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                InsuranceTenure.vehicle_no.ilike(term),
                InsuranceTenure.customer_name.ilike(term),
            )
        )

    # Order by expiry month, then customer name
    query = query.order_by(InsuranceTenure.coverage_start_date.desc(), InsuranceTenure.created_at.desc())

    # Count total
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    # Paginate
    offset = (page - 1) * page_size
    tenures = list(db.scalars(query.offset(offset).limit(page_size)).all())

    items = []
    for t in tenures:
        # Load active child sessions for this tenure
        sessions = list(
            db.scalars(
                select(SessionModel)
                .where(
                    SessionModel.tenure_id == t.id,
                    SessionModel.is_tenure_active,
                    SessionModel.status != "trash",
                )
            ).all()
        )

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

            if s.quotation_ref and str(s.quotation_ref).startswith("RL"):
                gen_quotes.append({
                    "session_id": s.id,
                    "quotation_ref": s.quotation_ref,
                    "company": comp,
                    "status": s.quotation_status,
                })

        items.append({
            "id": t.id,
            "vehicle_no": t.vehicle_no,
            "customer_name": t.customer_name,
            "coverage_start_date": t.coverage_start_date.isoformat(),
            "coverage_end_date": t.coverage_end_date.isoformat(),
            "expiry_month": t.expiry_month,
            "status": t.status,
            "winning_company_id": t.winning_company_id,
            "winning_quotation_ref": t.winning_quotation_ref,
            "won_premium": float(t.won_premium) if t.won_premium is not None else None,
            "miss_reason": t.miss_reason,
            "sourced_quotes": sourced,
            "generated_quotations": gen_quotes,
            "created_at": t.created_at.isoformat(),
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


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

    if not sess.quotation_ref or not str(sess.quotation_ref).startswith("RL"):
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
