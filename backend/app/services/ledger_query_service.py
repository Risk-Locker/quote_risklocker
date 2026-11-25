"""Unified Single-Source-of-Truth (SSOT) query & aggregation service for the Motor Renewal Ledger."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import and_, exists, extract, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.models.tables import (
    CustomerAccount,
    InsuranceTenure,
    Session as SessionModel,
    TenureComparisonEntry,
    TrackedVehicle,
)

LedgerAnchor = Literal["all", "expiring", "starting"]
PolicyStatusFilter = Literal["all", "issued", "pending"]


@dataclass(frozen=True)
class LedgerFilterSpec:
    year: int | None = None
    month: int | None = None
    anchor: LedgerAnchor = "all"
    category: str | None = None
    stage: str | None = None
    status: str | None = None
    policy_status: PolicyStatusFilter = "all"
    sub_agent: str | None = None
    search: str | None = None
    show_hidden: bool = False
    show_discarded: bool = False


def _unwrap_param(val: Any, default: Any = None) -> Any:
    """Unwrap fastapi.params.Query objects when router functions are invoked directly in unit tests."""
    if val is None or isinstance(val, (str, int, bool)):
        return val
    if hasattr(val, "default"):
        return val.default
    return default


def normalize_anchor(anchor: Any) -> LedgerAnchor:
    raw = _unwrap_param(anchor, "all")
    val = (str(raw) if raw is not None else "all").strip().lower()
    if val in ("expiring", "starting", "all"):
        return val  # type: ignore[return-value]
    return "all"


def normalize_policy_status(policy_status: Any) -> PolicyStatusFilter:
    raw = _unwrap_param(policy_status, "all")
    val = (str(raw) if raw is not None else "all").strip().lower()
    if val in ("issued", "pending", "all"):
        return val  # type: ignore[return-value]
    return "all"


def parse_year_month(year: Any, month: Any) -> tuple[int | None, int | None]:
    """Parse ledger year and month parameters consistently across all endpoints."""
    year = _unwrap_param(year, None)
    month = _unwrap_param(month, None)
    parsed_year: int | None = None
    if year is not None and str(year).strip().lower() not in ("", "all", "none"):
        try:
            parsed_year = int(year)
        except (TypeError, ValueError):
            parsed_year = None

    parsed_month: int | None = None
    if month is not None:
        m_str = str(month).strip()
        if m_str and m_str.lower() not in ("all", "none"):
            if "-" in m_str:
                parts = m_str.split("-", 1)
                if parts[0].isdigit() and parts[1].isdigit():
                    parsed_year = int(parts[0])
                    m_candidate = int(parts[1])
                    if 1 <= m_candidate <= 12:
                        parsed_month = m_candidate
            elif m_str.isdigit():
                m_candidate = int(m_str)
                if 1 <= m_candidate <= 12:
                    parsed_month = m_candidate

    return parsed_year, parsed_month


def _has_covernote_session_expr():
    return exists(
        select(SessionModel.id).where(
            SessionModel.tenure_id == InsuranceTenure.id,
            SessionModel.document_type == "covernote",
            SessionModel.status != "trash",
        )
    )


def can_project_expiry_expr():
    """Only officially issued/bound policies OR original intake deals can project expiry."""
    return or_(
        InsuranceTenure.previous_tenure_id.is_(None),
        InsuranceTenure.covernote_session_id.is_not(None),
        and_(
            InsuranceTenure.policy_number.is_not(None),
            func.trim(InsuranceTenure.policy_number) != "",
        ),
        InsuranceTenure.stage.in_(["Issue Policy", "Close - Win"]),
        InsuranceTenure.status.in_(["hit", "bound"]),
        _has_covernote_session_expr(),
    )


def is_issued_policy_expr():
    """True only when a real cover note / policy number exists or deal is Close - Win / HIT."""
    return or_(
        InsuranceTenure.covernote_session_id.is_not(None),
        and_(
            InsuranceTenure.policy_number.is_not(None),
            func.trim(InsuranceTenure.policy_number) != "",
        ),
        InsuranceTenure.stage == "Close - Win",
        InsuranceTenure.status == "hit",
        _has_covernote_session_expr(),
    )


def _period_bounds(year: int, month: int | None) -> tuple[datetime, datetime]:
    if month is not None:
        start = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)
        if month == 12:
            next_start = datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        else:
            next_start = datetime(year, month + 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        return start, next_start
    start = datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    next_start = datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    return start, next_start


def apply_period_anchor_filter(
    query: Any,
    *,
    year: int | None,
    month: int | None,
    anchor: LedgerAnchor,
) -> Any:
    """Apply the single shared period + anchor filter predicate."""
    if year is not None:
        period_start, next_period_start = _period_bounds(year, month)
        start_in_period = and_(
            InsuranceTenure.coverage_start_date.is_not(None),
            InsuranceTenure.coverage_start_date >= period_start,
            InsuranceTenure.coverage_start_date < next_period_start,
        )
        end_in_period = and_(
            InsuranceTenure.coverage_end_date.is_not(None),
            InsuranceTenure.coverage_end_date >= period_start,
            InsuranceTenure.coverage_end_date < next_period_start,
        )
        if anchor == "starting":
            return query.where(start_in_period)
        if anchor == "expiring":
            return query.where(and_(can_project_expiry_expr(), end_in_period))

        child = aliased(InsuranceTenure)
        has_child_starting_in_period = exists(
            select(child.id).where(
                child.previous_tenure_id == InsuranceTenure.id,
                child.deleted_at.is_(None),
                child.is_projected == False,
                child.is_discarded == False,
                child.coverage_start_date.is_not(None),
                child.coverage_start_date >= period_start,
                child.coverage_start_date < next_period_start,
            )
        )
        return query.where(
            or_(
                start_in_period,
                and_(
                    can_project_expiry_expr(),
                    end_in_period,
                    ~has_child_starting_in_period,
                ),
            )
        )

    if month is not None:
        start_in_month = and_(
            InsuranceTenure.coverage_start_date.is_not(None),
            extract("month", InsuranceTenure.coverage_start_date) == month,
        )
        end_in_month = and_(
            InsuranceTenure.coverage_end_date.is_not(None),
            extract("month", InsuranceTenure.coverage_end_date) == month,
        )
        if anchor == "starting":
            return query.where(start_in_month)
        if anchor == "expiring":
            return query.where(and_(can_project_expiry_expr(), end_in_month))

        child = aliased(InsuranceTenure)
        has_child_starting_in_month = exists(
            select(child.id).where(
                child.previous_tenure_id == InsuranceTenure.id,
                child.deleted_at.is_(None),
                child.is_projected == False,
                child.is_discarded == False,
                child.coverage_start_date.is_not(None),
                extract("month", child.coverage_start_date) == month,
                extract("year", child.coverage_start_date)
                == extract("year", InsuranceTenure.coverage_end_date),
            )
        )
        return query.where(
            or_(
                start_in_month,
                and_(
                    can_project_expiry_expr(),
                    end_in_month,
                    ~has_child_starting_in_month,
                ),
            )
        )

    return query


def apply_base_ledger_filters(query: Any, spec: LedgerFilterSpec) -> Any:
    """Apply non-period filters (soft-delete, visibility, category, stage, policy_status, search)."""
    category = _unwrap_param(spec.category, None)
    stage = _unwrap_param(spec.stage, None)
    status = _unwrap_param(spec.status, None)
    sub_agent = _unwrap_param(spec.sub_agent, None)
    search = _unwrap_param(spec.search, None)

    query = query.where(
        InsuranceTenure.deleted_at.is_(None),
        InsuranceTenure.is_projected == False,
    )
    if not spec.show_hidden:
        query = query.where(InsuranceTenure.is_hidden == False)
    if not spec.show_discarded:
        query = query.where(InsuranceTenure.is_discarded == False)

    if category == "active":
        query = query.where(
            or_(
                InsuranceTenure.stage.is_(None),
                ~InsuranceTenure.stage.in_(["Close - Lose", "Others"]),
            )
        )
    elif category == "lost":
        query = query.where(InsuranceTenure.stage.in_(["Close - Lose", "Others"]))

    if stage and str(stage) != "all":
        query = query.where(InsuranceTenure.stage == str(stage).strip())

    if status and str(status) != "all":
        query = query.where(InsuranceTenure.status == str(status).strip())

    if spec.policy_status == "issued":
        query = query.where(is_issued_policy_expr())
    elif spec.policy_status == "pending":
        query = query.where(~is_issued_policy_expr())

    if sub_agent and str(sub_agent).strip():
        query = query.where(InsuranceTenure.sub_agent_name.ilike(f"%{str(sub_agent).strip()}%"))

    if search and str(search).strip():
        term = f"%{str(search).strip()}%"
        veh_match = exists(
            select(TrackedVehicle.id).where(
                TrackedVehicle.id == InsuranceTenure.tracked_vehicle_id,
                or_(
                    TrackedVehicle.chassis_no.ilike(term),
                    TrackedVehicle.car_brand.ilike(term),
                    TrackedVehicle.car_model.ilike(term),
                ),
            )
        )
        cust_match = exists(
            select(CustomerAccount.id).where(
                CustomerAccount.id == InsuranceTenure.customer_id,
                CustomerAccount.id_number.ilike(term),
            )
        )
        query = query.where(
            or_(
                InsuranceTenure.vehicle_no.ilike(term),
                InsuranceTenure.customer_name.ilike(term),
                InsuranceTenure.comment.ilike(term),
                InsuranceTenure.sub_agent_name.ilike(term),
                InsuranceTenure.policy_number.ilike(term),
                veh_match,
                cust_match,
            )
        )

    return query


def apply_ledger_filters(query: Any, spec: LedgerFilterSpec, *, include_period: bool = True) -> Any:
    """Apply the complete shared ledger filter specification."""
    query = apply_base_ledger_filters(query, spec)
    if include_period:
        query = apply_period_anchor_filter(
            query,
            year=spec.year,
            month=spec.month,
            anchor=spec.anchor,
        )
    return query


def compute_stage_summary(db: Session, spec: LedgerFilterSpec) -> dict[str, int]:
    """Compute stage KPI counts using the exact same filter predicate as GET /tenures."""
    query = select(InsuranceTenure.stage)
    # Stage summary never filters by spec.stage itself (so clicking a card keeps all card counts visible)
    effective_spec = LedgerFilterSpec(
        year=spec.year,
        month=spec.month,
        anchor=spec.anchor,
        category=spec.category,
        stage=None,
        status=spec.status,
        policy_status=spec.policy_status,
        sub_agent=spec.sub_agent,
        search=spec.search,
        show_hidden=spec.show_hidden,
        show_discarded=spec.show_discarded,
    )
    query = apply_ledger_filters(query, effective_spec, include_period=True)
    rows = db.scalars(query).all()

    stage_counts: dict[str, int] = defaultdict(int)
    for stg in rows:
        if stg:
            stage_counts[stg] += 1

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


def _load_aggregation_rows(
    db: Session,
    spec: LedgerFilterSpec,
) -> tuple[list[Any], set[str], set[tuple[str, int]], set[tuple[str, int, int]]]:
    """Load base-filtered tenures + covernote session flags + active child renewal coordinates."""
    base_spec = LedgerFilterSpec(
        year=None,
        month=None,
        anchor=spec.anchor,
        category=spec.category,
        stage=spec.stage,
        status=spec.status,
        policy_status=spec.policy_status,
        sub_agent=spec.sub_agent,
        search=spec.search,
        show_hidden=spec.show_hidden,
        show_discarded=spec.show_discarded,
    )
    stmt = select(
        InsuranceTenure.id,
        InsuranceTenure.vehicle_no,
        InsuranceTenure.coverage_start_date,
        InsuranceTenure.coverage_end_date,
        InsuranceTenure.expiry_month,
        InsuranceTenure.status,
        InsuranceTenure.stage,
        InsuranceTenure.covernote_session_id,
        InsuranceTenure.policy_number,
        InsuranceTenure.previous_tenure_id,
    )
    stmt = apply_base_ledger_filters(stmt, base_spec)
    rows = db.execute(stmt).all()

    cn_tenure_ids: set[str] = set(
        db.scalars(
            select(SessionModel.tenure_id).where(
                SessionModel.tenure_id.is_not(None),
                SessionModel.document_type == "covernote",
                SessionModel.status != "trash",
            )
        ).all()
    )

    # Active non-deleted, non-discarded child renewals (for deduplicating anchor="all")
    child_rows = db.execute(
        select(
            InsuranceTenure.previous_tenure_id,
            InsuranceTenure.coverage_start_date,
        ).where(
            InsuranceTenure.previous_tenure_id.is_not(None),
            InsuranceTenure.deleted_at.is_(None),
            InsuranceTenure.is_projected == False,
            InsuranceTenure.is_discarded == False,
            InsuranceTenure.coverage_start_date.is_not(None),
        )
    ).all()

    child_start_years: set[tuple[str, int]] = set()
    child_start_yms: set[tuple[str, int, int]] = set()
    for prev_id, c_start in child_rows:
        if prev_id and c_start:
            child_start_years.add((prev_id, c_start.year))
            child_start_yms.add((prev_id, c_start.year, c_start.month))

    return rows, cn_tenure_ids, child_start_years, child_start_yms


def _row_can_project_expiry(
    t_id: str,
    t_status: str | None,
    stage: str | None,
    cn_sess_id: str | None,
    pol_no: str | None,
    prev_tenure_id: str | None,
    cn_tenure_ids: set[str],
) -> bool:
    has_pol = bool(pol_no and pol_no.strip())
    return bool(
        prev_tenure_id is None
        or cn_sess_id is not None
        or has_pol
        or stage in ("Issue Policy", "Close - Win")
        or t_status in ("hit", "bound")
        or t_id in cn_tenure_ids
    )


def compute_months_summary(db: Session, spec: LedgerFilterSpec) -> dict[str, Any]:
    """Compute per-month counts matching the exact active anchor lens + start/end breakdown."""
    rows, cn_tenure_ids, _, child_start_yms = _load_aggregation_rows(db, spec)

    month_data: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "start_count": 0,
            "end_count": 0,
            "tenure_ids": set(),
            "vehicles": set(),
            "hit": 0,
            "miss": 0,
        }
    )
    by_month_num: dict[int, dict[str, Any]] = {
        m: {
            "start_count": 0,
            "end_count": 0,
            "tenure_ids": set(),
            "vehicles": set(),
            "hit": 0,
            "miss": 0,
        }
        for m in range(1, 13)
    }

    for t_id, veh, start_dt, end_dt, _exp_m, t_status, stage, cn_sess_id, pol_no, prev_tenure_id in rows:
        can_project = _row_can_project_expiry(
            t_id, t_status, stage, cn_sess_id, pol_no, prev_tenure_id, cn_tenure_ids
        )
        veh_key = (veh or "").strip().upper() or t_id

        s_ym = start_dt.strftime("%Y-%m") if start_dt else None
        e_ym = end_dt.strftime("%Y-%m") if (can_project and end_dt) else None

        if s_ym and start_dt:
            month_data[s_ym]["start_count"] += 1
            by_month_num[start_dt.month]["start_count"] += 1
        if e_ym and end_dt:
            month_data[e_ym]["end_count"] += 1
            by_month_num[end_dt.month]["end_count"] += 1

        # Determine matched YYYY-MM buckets under spec.anchor
        matched_yms: set[str] = set()
        if spec.anchor == "starting":
            if s_ym:
                matched_yms.add(s_ym)
        elif spec.anchor == "expiring":
            if e_ym:
                matched_yms.add(e_ym)
        else:
            if s_ym:
                matched_yms.add(s_ym)
            if e_ym and end_dt and (t_id, end_dt.year, end_dt.month) not in child_start_yms:
                matched_yms.add(e_ym)

        for ym in matched_yms:
            bucket = month_data[ym]
            bucket["tenure_ids"].add(t_id)
            bucket["vehicles"].add(veh_key)
            if t_status == "hit":
                bucket["hit"] += 1
            elif t_status == "miss":
                bucket["miss"] += 1

        # Determine matched calendar months (1..12 across all years) under spec.anchor
        matched_m_nums: set[int] = set()
        if spec.anchor == "starting":
            if start_dt:
                matched_m_nums.add(start_dt.month)
        elif spec.anchor == "expiring":
            if can_project and end_dt:
                matched_m_nums.add(end_dt.month)
        else:
            if start_dt:
                matched_m_nums.add(start_dt.month)
            if can_project and end_dt and (t_id, end_dt.year, end_dt.month) not in child_start_yms:
                matched_m_nums.add(end_dt.month)

        for m_num in matched_m_nums:
            m_bucket = by_month_num[m_num]
            m_bucket["tenure_ids"].add(t_id)
            m_bucket["vehicles"].add(veh_key)
            if t_status == "hit":
                m_bucket["hit"] += 1
            elif t_status == "miss":
                m_bucket["miss"] += 1

    min_y, max_y = 2024, 2030
    for ym_key in month_data:
        try:
            yy = int(ym_key.split("-")[0])
            min_y = min(min_y, yy)
            max_y = max(max_y, yy)
        except Exception:
            pass

    result: list[dict[str, Any]] = []
    for y in range(min_y, max_y + 1):
        for m in range(1, 13):
            key = f"{y:04d}-{m:02d}"
            info = month_data.get(key)
            if info:
                tot = len(info["tenure_ids"])
                hit_cnt = info["hit"]
                miss_cnt = info["miss"]
                result.append(
                    {
                        "month": key,
                        "total": tot,
                        "start_count": info["start_count"],
                        "end_count": info["end_count"],
                        "cars": len(info["vehicles"]),
                        "hit": hit_cnt,
                        "miss": miss_cnt,
                        "pending": max(0, tot - hit_cnt - miss_cnt),
                    }
                )
            else:
                result.append(
                    {
                        "month": key,
                        "total": 0,
                        "start_count": 0,
                        "end_count": 0,
                        "cars": 0,
                        "hit": 0,
                        "miss": 0,
                        "pending": 0,
                    }
                )

    result.sort(key=lambda x: x["month"])

    summary_by_month = []
    for m_num in range(1, 13):
        info = by_month_num[m_num]
        tot = len(info["tenure_ids"])
        hit_cnt = info["hit"]
        miss_cnt = info["miss"]
        summary_by_month.append(
            {
                "month_num": m_num,
                "month": f"{m_num:02d}",
                "total": tot,
                "start_count": info["start_count"],
                "end_count": info["end_count"],
                "cars": len(info["vehicles"]),
                "hit": hit_cnt,
                "miss": miss_cnt,
                "pending": max(0, tot - hit_cnt - miss_cnt),
            }
        )

    return {"months": result, "summary_by_month": summary_by_month, "anchor": spec.anchor}


def compute_yoy_stats(db: Session, spec: LedgerFilterSpec) -> dict[str, Any]:
    """Compute year-over-year tenure counts guaranteed to equal GET /tenures totals per year."""
    rows, cn_tenure_ids, child_start_years, _ = _load_aggregation_rows(db, spec)

    year_data: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "active": 0,
            "lost": 0,
            "starting": 0,
            "expiring": 0,
            "tenure_ids": set(),
            "vehicles": set(),
        }
    )

    all_years_tenures: set[str] = set()
    all_years_vehicles: set[str] = set()
    all_active = 0
    all_lost = 0

    for t_id, veh, start_dt, end_dt, _exp_m, t_status, stage, cn_sess_id, pol_no, prev_tenure_id in rows:
        can_project = _row_can_project_expiry(
            t_id, t_status, stage, cn_sess_id, pol_no, prev_tenure_id, cn_tenure_ids
        )
        veh_key = (veh or "").strip().upper() or t_id
        is_lost = stage in ("Close - Lose", "Others")

        all_years_tenures.add(t_id)
        all_years_vehicles.add(veh_key)
        if is_lost:
            all_lost += 1
        else:
            all_active += 1

        s_yr = start_dt.year if start_dt else None
        e_yr = end_dt.year if (can_project and end_dt) else None

        if s_yr is not None:
            year_data[str(s_yr)]["starting"] += 1
        if e_yr is not None:
            year_data[str(e_yr)]["expiring"] += 1

        matched_years: set[int] = set()
        if spec.anchor == "starting":
            if s_yr is not None:
                matched_years.add(s_yr)
        elif spec.anchor == "expiring":
            if e_yr is not None:
                matched_years.add(e_yr)
        else:
            if s_yr is not None:
                matched_years.add(s_yr)
            if e_yr is not None and (t_id, e_yr) not in child_start_years:
                matched_years.add(e_yr)

        for yr in matched_years:
            bucket = year_data[str(yr)]
            bucket["tenure_ids"].add(t_id)
            bucket["vehicles"].add(veh_key)
            if is_lost:
                bucket["lost"] += 1
            else:
                bucket["active"] += 1

    sorted_years = sorted(year_data.keys())
    result_list: list[dict[str, Any]] = []
    prev_total: int | None = None
    for y in sorted_years:
        bucket = year_data[y]
        tot = len(bucket["tenure_ids"])
        growth = None
        if prev_total is not None and prev_total > 0:
            growth = round(((tot - prev_total) / prev_total) * 100, 1)
        prev_total = tot
        result_list.append(
            {
                "year": y,
                "total": tot,
                "cars": len(bucket["vehicles"]),
                "active": bucket["active"],
                "lost": bucket["lost"],
                "starting": bucket["starting"],
                "expiring": bucket["expiring"],
                "growth_percentage": growth,
            }
        )

    all_summary = {
        "total": len(all_years_tenures),
        "cars": len(all_years_vehicles),
        "active": all_active,
        "lost": all_lost,
    }
    return {
        "years": result_list,
        "all_years": all_summary,
        "all_years_summary": all_summary,
        "anchor": spec.anchor,
    }


def load_authoritative_comparison_map(
    db: Session,
    tenure_ids: list[str],
) -> tuple[dict[tuple[str, str], TenureComparisonEntry], dict[tuple[str, str], TenureComparisonEntry]]:
    """Batch-load non-hidden TenureComparisonEntry rows for authoritative Decimal total_payable parity."""
    if not tenure_ids:
        return {}, {}

    entries = list(
        db.scalars(
            select(TenureComparisonEntry).where(
                TenureComparisonEntry.tenure_id.in_(tenure_ids),
                TenureComparisonEntry.is_hidden == False,
            )
        ).all()
    )
    by_session: dict[tuple[str, str], TenureComparisonEntry] = {}
    by_company: dict[tuple[str, str], TenureComparisonEntry] = {}
    for entry in entries:
        if entry.session_id:
            by_session[(entry.tenure_id, entry.session_id)] = entry
        if entry.company_id:
            existing = by_company.get((entry.tenure_id, entry.company_id))
            if existing is None or (entry.is_recommended and not existing.is_recommended):
                by_company[(entry.tenure_id, entry.company_id)] = entry
    return by_session, by_company


def format_decimal_amount(value: Any) -> str | None:
    """Format monetary values deterministically with 2 decimal places using Decimal."""
    if value is None or value == "":
        return None
    try:
        dec = Decimal(str(value).replace(",", "").strip())
        return f"{dec:.2f}"
    except Exception:
        return str(value)
