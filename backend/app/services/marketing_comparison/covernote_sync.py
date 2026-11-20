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
from app.services.marketing_comparison.dynamic_addons import sanitize_extra_addons_map
from app.services.marketing_comparison.ncd_evaluator import (
    check_has_betterment_peril,
    evaluate_betterment_rules,
    get_standard_betterment_rate,
)
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
            if cn_session and cn_session.draft:
                cn_session.draft.company_id = matched_comp.id
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

    # 3b. Vehicle Model & YOM Updates on TrackedVehicle
    tv = getattr(tenure, "tracked_vehicle", None)
    if payload.get("vehicle_model") is not None and tv is not None:
        clean_vm = str(payload["vehicle_model"]).strip()
        if clean_vm:
            tv.car_model = clean_vm
    if payload.get("manufacture_year") is not None and tv is not None:
        yom_int = int(payload["manufacture_year"])
        if yom_int > 1900:
            tv.manufacture_year = yom_int

    # 3c. Fixed Costs (Road Tax & Runner Fee + Toggles)
    if payload.get("road_tax") is not None:
        tenure.road_tax = float(_q2(payload["road_tax"]))
    if payload.get("runner_fee") is not None:
        tenure.runner_fee = float(_q2(payload["runner_fee"]))
    if payload.get("include_road_tax") is not None:
        tenure.include_road_tax = bool(payload["include_road_tax"])
    if payload.get("include_runner_fee") is not None:
        tenure.include_runner_fee = bool(payload["include_runner_fee"])

    eff_rt = _q2(tenure.road_tax) if (tenure.include_road_tax is not False) else _ZERO
    eff_rf = _q2(tenure.runner_fee) if (tenure.include_runner_fee is not False) else _ZERO

    # 3d. Bidirectional Total Payable <-> Motor Premium sync
    sync_payload = dict(payload)
    if sync_payload.get("total_payable") is not None:
        tot_dec = _q2(sync_payload["total_payable"])
        tenure.won_premium = float(tot_dec)
        if sync_payload.get("motor_premium") is None:
            sync_payload["motor_premium"] = float(max(_ZERO, (tot_dec - eff_rt - eff_rf).quantize(_CENT, rounding=ROUND_HALF_UP)))

    # Normalize Betterment mode ('auto' | 'waived' | 'copay') & explicit betterment_rate
    b_mode = str(sync_payload.get("betterment_mode") or "").strip().lower()
    if b_mode == "auto":
        sync_payload.pop("waiver_betterment", None)
        sync_payload.pop("betterment_rate", None)
        if cn_session and cn_session.draft and isinstance(cn_session.draft.fields, dict):
            df_auto = dict(cn_session.draft.fields)
            df_auto.pop("waiver_of_betterment", None)
            df_auto.pop("betterment_rate", None)
            cn_session.draft.fields = df_auto
            flag_modified(cn_session.draft, "fields")
    elif sync_payload.get("betterment_rate") is not None:
        br_val = float(sync_payload["betterment_rate"])
        sync_payload["waiver_betterment"] = br_val == 0.0
    elif b_mode == "waived":
        sync_payload["waiver_betterment"] = True
        sync_payload["betterment_rate"] = 0.0
    elif b_mode == "copay":
        sync_payload["waiver_betterment"] = False
        veh_yom_cur = getattr(tv, "manufacture_year", None) if tv else None
        q_yr_cur = (tenure.coverage_start_date.year if tenure.coverage_start_date else datetime.now(timezone.utc).year)
        reg_dt = None
        if cn_session and cn_session.draft and isinstance(cn_session.draft.fields, dict):
            reg_raw = cn_session.draft.fields.get("registration_date") or cn_session.draft.fields.get("date_of_registration")
            reg_dt = reg_raw.get("value") if isinstance(reg_raw, dict) else reg_raw
        if reg_dt:
            from app.domain.betterment_engine import calculate_exact_vehicle_age

            veh_age_copay = calculate_exact_vehicle_age(reg_dt, tenure.coverage_start_date or f"{q_yr_cur}-01-01")
        else:
            veh_age_copay = max(0, q_yr_cur - (veh_yom_cur or q_yr_cur))
        calc_rate, _ = get_standard_betterment_rate(veh_age_copay)
        if sync_payload.get("betterment_rate") is None:
            sync_payload["betterment_rate"] = calc_rate

    # Normalize dynamic add-on map if passed
    if isinstance(sync_payload.get("extra_addons"), dict):
        sync_payload["extra_addons"] = sanitize_extra_addons_map(sync_payload["extra_addons"])

    # Sync scalar peril states when Included Perils checklist is explicitly saved
    if isinstance(sync_payload.get("included_perils"), list):
        peril_set = {str(p).strip().upper() for p in sync_payload["included_perils"] if str(p).strip()}
        if "special_perils" not in sync_payload:
            sync_payload["special_perils"] = "Included" if ("FLOOD" in peril_set or "SPECIAL PERILS" in peril_set) else "Not Included"
        if "llp_llop" not in sync_payload:
            sync_payload["llp_llop"] = "Included" if ("LLP" in peril_set or "LLOP" in peril_set) else "Not Included"
        if "towing_limit" not in sync_payload and "TOWING" not in peril_set:
            sync_payload["towing_limit"] = "No towing"
        if "windscreen_sum_insured" not in sync_payload and "WINDSCREEN" not in peril_set:
            sync_payload["windscreen_sum_insured"] = 0.0
        if "waiver_betterment" not in sync_payload and "betterment_rate" not in sync_payload and "betterment_mode" not in sync_payload:
            if "BETTERMENT" in peril_set:
                sync_payload["waiver_betterment"] = True
                sync_payload["betterment_rate"] = 0.0
            else:
                sync_payload["waiver_betterment"] = False
        from app.services.marketing_comparison.dynamic_addons import DYNAMIC_ADDON_DEFINITIONS

        ea_cur = dict(sync_payload.get("extra_addons") or {})
        for defn in DYNAMIC_ADDON_DEFINITIONS:
            if defn["key"] not in ea_cur:
                ea_cur[defn["key"]] = "Yes" if defn["peril_tag"] in peril_set else "No"
        sync_payload["extra_addons"] = ea_cur

    # 4. Sync financial, vehicle & benefit fields ONLY into cn_session.draft + its DraftBenefitSelections
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
            "betterment_rate",
            "extra_addons",
            "included_perils",
            "vehicle_model",
            "manufacture_year",
        )
        if k in sync_payload and sync_payload[k] is not None
    ]
    if b_mode == "auto" and "betterment_rate" not in sync_keys:
        sync_keys.append("betterment_rate")
        sync_payload["betterment_rate"] = None

    if cn_session and sync_keys:
        sync_session_draft_from_comparison(
            db,
            tenure,
            cn_session.id,
            edited_fields=sync_keys,
            field_values=sync_payload,
            explicit_motor_premium=(sync_payload.get("motor_premium") is not None),
            user_id=user_id,
        )

    # 5. Recompute tenure.won_premium = discounted motor_premium + eff_rt + eff_rf (unless explicit total_payable took precedence cleanly)
    from app.domain.motor.discount_calculator import calculate_motor_discount

    pct_val = getattr(tenure, "motor_discount_pct", 0.0) or 0.0
    flat_val = getattr(tenure, "quotation_discount", 0.0) or 0.0
    if sync_payload.get("total_payable") is not None:
        tenure.won_premium = float(_q2(sync_payload["total_payable"]))
    elif sync_payload.get("motor_premium") is not None:
        new_mp = _q2(sync_payload["motor_premium"])
        disc_bd = calculate_motor_discount(new_mp, pct_val, flat_val)
        tenure.won_premium = float(disc_bd.net_total_payable(eff_rt, eff_rf))
    elif any(k in payload for k in ("road_tax", "runner_fee", "include_road_tax", "include_runner_fee")) and cn_session and cn_session.draft and isinstance(cn_session.draft.fields, dict):
        prem_dec = _q2(cn_session.draft.fields.get("premium"))
        if prem_dec > _ZERO:
            disc_bd = calculate_motor_discount(prem_dec, pct_val, flat_val)
            tenure.won_premium = float(disc_bd.net_total_payable(eff_rt, eff_rf))
    elif cn_session and cn_session.draft and isinstance(cn_session.draft.fields, dict) and tenure.won_premium is None:
        prem_dec = _q2(cn_session.draft.fields.get("premium"))
        if prem_dec > _ZERO:
            disc_bd = calculate_motor_discount(prem_dec, pct_val, flat_val)
            tenure.won_premium = float(disc_bd.net_total_payable(eff_rt, eff_rf))

    # 6. Mirror edits strictly if cn_session itself owns a TenureComparisonEntry row (never alter other underwriters!)
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
            if sync_payload.get("sum_insured") is not None:
                ce.sum_insured = _q2(sync_payload["sum_insured"])
            if sync_payload.get("motor_premium") is not None:
                ce.motor_premium = _q2(sync_payload["motor_premium"])
            elif tenure.won_premium is not None:
                ce.motor_premium = max(_ZERO, (_q2(tenure.won_premium) - eff_rt - eff_rf).quantize(_CENT, rounding=ROUND_HALF_UP))
            if sync_payload.get("agreed_value") is not None or sync_payload.get("valuation_type") is not None:
                vt_raw = sync_payload.get("valuation_type")
                if vt_raw is not None and str(vt_raw).strip() != "":
                    is_ag = str(vt_raw).strip().lower() in {"agreed value", "agreed_value"}
                else:
                    is_ag = bool(sync_payload.get("agreed_value"))
                ce.agreed_value = is_ag
                ce.valuation_type = "agreed_value" if is_ag else "market_value"
            if sync_payload.get("excess") is not None:
                ce.excess = _q2(sync_payload["excess"])
            if sync_payload.get("towing_limit") is not None:
                raw_tow_cn = str(sync_payload["towing_limit"]).strip()
                if raw_tow_cn.lower() in {"0", "0.0", "0 km", "rm 0", "no towing", "without towing", "not included", "none", "tiada", "nil"}:
                    ce.towing_limit = "No towing"
                else:
                    ce.towing_limit = raw_tow_cn or "Unlimited"
                ce.towing_km = ce.towing_limit
            if sync_payload.get("windscreen_sum_insured") is not None:
                ws_dec = _q2(sync_payload["windscreen_sum_insured"])
                ce.windscreen_sum_insured = ws_dec if ws_dec > _ZERO else None
            if sync_payload.get("special_perils") is not None:
                sp_s = str(sync_payload["special_perils"]).strip()
                ce.special_perils = None if sp_s.lower() in {"not included", "no", "none", "excluded", "-", ""} else sp_s
            if sync_payload.get("llp_llop") is not None:
                llp_s = str(sync_payload["llp_llop"]).strip()
                ce.llp_llop = None if llp_s.lower() in {"not included", "no", "none", "excluded", "-", ""} else llp_s
            if isinstance(sync_payload.get("extra_addons"), dict):
                ce.extra_addons = {**dict(getattr(ce, "extra_addons", None) or {}), **sync_payload["extra_addons"]}
            if b_mode == "auto":
                veh_yom = getattr(tv, "manufacture_year", None) if tv else None
                q_year = (tenure.coverage_start_date.year if tenure.coverage_start_date else datetime.now(timezone.utc).year)
                cn_f_now = cn_session.draft.fields if cn_session.draft and isinstance(cn_session.draft.fields, dict) else {}
                has_p = check_has_betterment_peril(cn_f_now)
                comp_obj_cn = db.get(InsuranceCompany, tenure.winning_company_id) if tenure.winning_company_id else None
                reg_raw_auto = cn_f_now.get("registration_date") or cn_f_now.get("date_of_registration")
                reg_dt_auto = reg_raw_auto.get("value") if isinstance(reg_raw_auto, dict) else reg_raw_auto
                w_auto, r_auto, d_auto = evaluate_betterment_rules(
                    yom=veh_yom,
                    quote_year=q_year,
                    company_name=ce.company_name,
                    has_betterment_peril=has_p,
                    registration_date=reg_dt_auto,
                    coverage_start_date=tenure.coverage_start_date,
                    company_obj=comp_obj_cn,
                )
                ce.waiver_betterment = w_auto
                ce.betterment_rate = r_auto
                ce.betterment_display = d_auto
            elif sync_payload.get("betterment_rate") is not None:
                b_r = float(sync_payload["betterment_rate"])
                ce.waiver_betterment = b_r == 0.0
                ce.betterment_rate = b_r
                ce.betterment_display = "No (0%)" if b_r == 0.0 else f"Yes ({int(b_r) if b_r.is_integer() else b_r}%)"
            elif sync_payload.get("waiver_betterment") is not None:
                ce.waiver_betterment = bool(sync_payload["waiver_betterment"])
                if ce.waiver_betterment:
                    ce.betterment_rate = _ZERO
                    ce.betterment_display = "No (0%)"
                else:
                    veh_yom = getattr(tv, "manufacture_year", None) if tv else None
                    q_year = (tenure.coverage_start_date.year if tenure.coverage_start_date else datetime.now(timezone.utc).year)
                    _, b_rate, b_disp = evaluate_betterment_rules(
                        yom=veh_yom,
                        quote_year=q_year,
                        company_name=ce.company_name,
                        has_betterment_peril=False,
                        coverage_start_date=tenure.coverage_start_date,
                    )
                    ce.betterment_rate = b_rate
                    ce.betterment_display = b_disp
            mp_dec = _q2(ce.motor_premium)
            si_dec = _q2(ce.sum_insured)
            ce.road_tax = float(eff_rt)
            ce.runner_fee = float(eff_rf)
            ce.include_road_tax = (tenure.include_road_tax is not False)
            ce.include_runner_fee = (tenure.include_runner_fee is not False)
            ce.total_payable = float((mp_dec + eff_rt + eff_rf).quantize(_CENT, rounding=ROUND_HALF_UP))
            if si_dec > _ZERO and mp_dec > _ZERO:
                ce.rate_percentage = ((mp_dec / si_dec) * _HUNDRED).quantize(_RATE_QUANT, rounding=ROUND_HALF_UP)

    db.commit()
    return get_marketing_comparison(db, tenure_id)
