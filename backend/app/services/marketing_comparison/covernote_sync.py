"""Cover Note atomic update and bidirectional synchronization helper.

Updates issued Cover Note fields across `InsuranceTenure`, Cover Note `Session`,
`QuotationDraft`, `DraftBenefitSelection`s, auto-created renewal windows, and
any mirroring `TenureComparisonEntry` using pure Decimal precision.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.domain.benefit_pricing import parse_money_decimal
from app.models.tables import (
    InsuranceCompany,
    InsuranceTenure,
    Session as SessionModel,
    TenureComparisonEntry,
)
from app.services.marketing_comparison.ncd_evaluator import get_standard_betterment_rate
from app.services.marketing_comparison.workspace_sync import sync_session_draft_from_comparison

_ZERO = Decimal("0.00")
_CENT = Decimal("0.01")
_RATE_QUANT = Decimal("0.0001")
_HUNDRED = Decimal("100")


def _parse_covernote_date(raw: Any) -> datetime | None:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    txt = str(raw or "").strip()
    if not txt:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            dt = datetime.strptime(txt[:10], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(txt.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _q2(value: Any) -> Decimal:
    return parse_money_decimal(value).quantize(_CENT, rounding=ROUND_HALF_UP)


def sync_and_update_covernote(
    db: Session,
    tenure_id: str,
    payload: dict[str, Any],
    *,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Update Cover Note details atomically across InsuranceTenure, Session, Draft, Benefits, and won_premium."""
    from app.services.insurance_tenure_service import _calculate_policy_end_date
    from app.services.marketing_comparison_service import get_marketing_comparison

    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise ValueError("Tenure not found")

    cn_session = (
        db.get(SessionModel, tenure.covernote_session_id)
        if tenure.covernote_session_id
        else db.scalar(
            select(SessionModel).where(
                SessionModel.tenure_id == tenure.id,
                SessionModel.document_type == "covernote",
            )
        )
    )
    has_bound_meta = bool(
        tenure.policy_number
        or tenure.won_premium is not None
        or tenure.winning_company_id
        or tenure.stage in ("Issue Policy", "Close - Win")
    )
    if not cn_session and not has_bound_meta:
        raise ValueError("No active Cover Note is attached to this tenure.")

    if cn_session and tenure.covernote_session_id != cn_session.id:
        tenure.covernote_session_id = cn_session.id

    # 1. Policy Number
    if payload.get("policy_number") is not None:
        clean_pno = str(payload["policy_number"]).strip()
        tenure.policy_number = clean_pno or None
        if cn_session:
            cn_session.policy_number = clean_pno or None
            if cn_session.draft:
                d_f = dict(cn_session.draft.fields or {})
                d_f["policy_number"] = {"value": clean_pno, "status": "manual_override"}
                d_f["covernote_no"] = {"value": clean_pno, "status": "manual_override"}
                cn_session.draft.fields = d_f
                flag_modified(cn_session.draft, "fields")

    # 2. Insurer / Winning Company resolution
    comp_id = str(payload.get("company_id") or "").strip() or None
    comp_name = str(payload.get("company_name") or "").strip() or None
    if comp_id or comp_name:
        matched_comp = db.get(InsuranceCompany, comp_id) if comp_id else None
        if not matched_comp and comp_name:
            all_comps = list(db.scalars(select(InsuranceCompany)).all())
            low = comp_name.lower()
            matched_comp = next(
                (c for c in all_comps if (c.name or "").lower() == low or (c.slug or "").lower() == low),
                None,
            ) or next(
                (c for c in all_comps if low in (c.name or "").lower() or (c.name or "").lower() in low),
                None,
            )
        if matched_comp:
            tenure.winning_company_id = matched_comp.id
            comp_name = comp_name or matched_comp.name
            if cn_session:
                cn_session.company_id = matched_comp.id
        if cn_session and comp_name:
            cn_session.detected_company = comp_name

    # 3. Coverage Dates (leap-safe) & Child Renewal Window Sync
    dt_start = _parse_covernote_date(payload.get("coverage_start_date")) if payload.get("coverage_start_date") else None
    dt_end = _parse_covernote_date(payload.get("coverage_end_date")) if payload.get("coverage_end_date") else None
    if payload.get("coverage_start_date") and not dt_start:
        raise ValueError("Invalid coverage_start_date format")
    if payload.get("coverage_end_date") and not dt_end:
        raise ValueError("Invalid coverage_end_date format")

    eff_start = dt_start or (cn_session.coverage_start_date if cn_session else None) or tenure.coverage_start_date
    eff_end = dt_end or (cn_session.coverage_end_date if cn_session else None) or tenure.coverage_end_date
    if dt_start and not dt_end and eff_end and dt_start > eff_end:
        eff_end = _calculate_policy_end_date(dt_start)
        dt_end = eff_end
    if eff_start and eff_end and eff_end < eff_start:
        raise ValueError("Cover end date cannot be earlier than cover start date")

    if dt_start:
        tenure.coverage_start_date = dt_start
        if cn_session:
            cn_session.coverage_start_date = dt_start
    if dt_end:
        tenure.coverage_end_date = dt_end
        tenure.expiry_month = dt_end.strftime("%Y-%m")
        if cn_session:
            cn_session.coverage_end_date = dt_end

    if (dt_start or dt_end) and cn_session and cn_session.draft:
        d_f = dict(cn_session.draft.fields or {})
        if dt_start:
            d_f["cover_start_date"] = {"value": dt_start.strftime("%d-%m-%Y"), "status": "manual_override"}
        if dt_end:
            d_f["cover_end_date"] = {"value": dt_end.strftime("%d-%m-%Y"), "status": "manual_override"}
        s_eff = dt_start or cn_session.coverage_start_date or tenure.coverage_start_date
        e_eff = dt_end or cn_session.coverage_end_date or tenure.coverage_end_date
        if s_eff and e_eff:
            d_f["cover_period"] = {
                "value": f"{s_eff.strftime('%d-%m-%Y')} TO {e_eff.strftime('%d-%m-%Y')}",
                "status": "manual_override",
            }
        cn_session.draft.fields = d_f
        flag_modified(cn_session.draft, "fields")

    if dt_end:
        child_tenures = list(
            db.scalars(
                select(InsuranceTenure).where(
                    InsuranceTenure.previous_tenure_id == tenure.id,
                    InsuranceTenure.is_discarded.is_(False),
                )
            ).all()
        )
        for child in child_tenures:
            if not child.covernote_session_id and child.stage in ("Prospecting", "Quotations", None):
                next_s = dt_end + timedelta(days=1)
                if next_s.tzinfo is None:
                    next_s = next_s.replace(tzinfo=timezone.utc)
                next_e = _calculate_policy_end_date(next_s)
                if next_e.tzinfo is None:
                    next_e = next_e.replace(tzinfo=timezone.utc)
                child.coverage_start_date = next_s
                child.coverage_end_date = next_e
                child.expiry_month = next_e.strftime("%Y-%m")

    # 4. Sync financial & benefit fields into cn_session.draft + DraftBenefitSelections
    sync_keys = [
        k for k in (
            "company_name",
            "sum_insured",
            "motor_premium",
            "agreed_value",
            "valuation_type",
            "windscreen_sum_insured",
            "towing_limit",
            "special_perils",
            "llp_llop",
            "excess",
            "waiver_betterment",
        )
        if k in payload and payload[k] is not None
    ]
    if cn_session and sync_keys:
        sync_session_draft_from_comparison(
            db,
            tenure,
            cn_session.id,
            edited_fields=sync_keys,
            field_values=payload,
            explicit_motor_premium=(payload.get("motor_premium") is not None),
            user_id=user_id,
        )

    # 5. Recompute tenure.won_premium = motor_premium + eff_rt + eff_rf
    eff_rt = _q2(tenure.road_tax) if (tenure.include_road_tax is not False) else _ZERO
    eff_rf = _q2(tenure.runner_fee) if (tenure.include_runner_fee is not False) else _ZERO
    if payload.get("motor_premium") is not None:
        new_mp = _q2(payload["motor_premium"])
        tenure.won_premium = (new_mp + eff_rt + eff_rf).quantize(_CENT, rounding=ROUND_HALF_UP)
    elif cn_session and cn_session.draft and isinstance(cn_session.draft.fields, dict):
        prem_dec = _q2(cn_session.draft.fields.get("premium"))
        if prem_dec > _ZERO:
            tenure.won_premium = (prem_dec + eff_rt + eff_rf).quantize(_CENT, rounding=ROUND_HALF_UP)

    # 6. Mirror edits if cn_session also happens to have a TenureComparisonEntry row
    if cn_session:
        cn_entries = list(
            db.scalars(
                select(TenureComparisonEntry).where(
                    TenureComparisonEntry.tenure_id == tenure.id,
                    TenureComparisonEntry.session_id == cn_session.id,
                )
            ).all()
        )
        for ce in cn_entries:
            if comp_name:
                ce.company_name = comp_name
            if tenure.winning_company_id:
                ce.company_id = tenure.winning_company_id
            if payload.get("sum_insured") is not None:
                ce.sum_insured = _q2(payload["sum_insured"])
            if payload.get("motor_premium") is not None:
                ce.motor_premium = _q2(payload["motor_premium"])
            elif tenure.won_premium is not None:
                ce.motor_premium = max(_ZERO, (_q2(tenure.won_premium) - eff_rt - eff_rf).quantize(_CENT, rounding=ROUND_HALF_UP))
            if payload.get("agreed_value") is not None or payload.get("valuation_type") is not None:
                is_ag = bool(payload.get("agreed_value")) or str(payload.get("valuation_type") or "").lower() == "agreed_value"
                ce.agreed_value = is_ag
                ce.valuation_type = "agreed_value" if is_ag else "market_value"
            if payload.get("excess") is not None:
                ce.excess = _q2(payload["excess"])
            if payload.get("towing_limit") is not None:
                ce.towing_limit = str(payload["towing_limit"]).strip() or "Unlimited"
                ce.towing_km = ce.towing_limit
            if payload.get("windscreen_sum_insured") is not None:
                ws_dec = _q2(payload["windscreen_sum_insured"])
                ce.windscreen_sum_insured = ws_dec if ws_dec > _ZERO else None
            if payload.get("special_perils") is not None:
                sp_s = str(payload["special_perils"]).strip()
                ce.special_perils = None if sp_s.lower() in {"not included", "no", "none", "excluded", "-", ""} else sp_s
            if payload.get("llp_llop") is not None:
                llp_s = str(payload["llp_llop"]).strip()
                ce.llp_llop = None if llp_s.lower() in {"not included", "no", "none", "excluded", "-", ""} else llp_s
            if payload.get("waiver_betterment") is not None:
                ce.waiver_betterment = bool(payload["waiver_betterment"])
                if ce.waiver_betterment:
                    ce.betterment_rate = _ZERO
                    ce.betterment_display = "No (0%)"
                else:
                    veh_yom = getattr(tenure.tracked_vehicle, "manufacture_year", None) if getattr(tenure, "tracked_vehicle", None) else None
                    q_year = (tenure.coverage_start_date.year if tenure.coverage_start_date else datetime.now(timezone.utc).year)
                    b_rate, b_disp = get_standard_betterment_rate(max(0, q_year - (veh_yom or q_year)))
                    ce.betterment_rate = b_rate
                    ce.betterment_display = b_disp
            mp_dec = _q2(ce.motor_premium)
            si_dec = _q2(ce.sum_insured)
            ce.total_payable = (mp_dec + eff_rt + eff_rf).quantize(_CENT, rounding=ROUND_HALF_UP)
            if si_dec > _ZERO and mp_dec > _ZERO:
                ce.rate_percentage = ((mp_dec / si_dec) * _HUNDRED).quantize(_RATE_QUANT, rounding=ROUND_HALF_UP)

    db.commit()
    return get_marketing_comparison(db, tenure_id)
