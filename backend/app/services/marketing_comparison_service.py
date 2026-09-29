"""Marketing Comparison Service

Provides side-by-side multi-underwriter comparison, rate computation,
Excel 1:1 parity financial modeling, manual quote sourcing, WhatsApp teaser formatting,
and winner handoff to the Risk-Locker Quotation Builder.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.tables import (
    InsuranceCompany,
    InsuranceTenure,
    QuotationDraft,
    Session as SessionModel,
    TenureComparisonEntry,
    TrackedVehicle,
    User,
    new_id,
)

logger = logging.getLogger(__name__)


def _extract_val(val: Any) -> Any:
    """Recursively unwrap ExtractionField dictionary objects."""
    if isinstance(val, dict):
        return _extract_val(val.get("value"))
    return val


def _to_float(val: Any) -> float:
    raw = _extract_val(val)
    if raw is None:
        return 0.0
    if isinstance(raw, (int, float, Decimal)):
        return float(raw)
    try:
        # Strip currency symbols, commas, and whitespace
        s = str(raw).replace("RM", "").replace("rm", "").replace(",", "").strip()
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _safe_str(val: Any) -> str:
    raw = _extract_val(val)
    if raw is None:
        return ""
    return str(raw).strip()


def detect_runner_fee_from_id(ic_or_passport: str | None) -> float:
    """Auto-detect runner fee based on Malaysian IC vs International Passport.

    Rules:
    - Customer ID starts with letters (e.g. K1584766Z, A12345678) -> International Passport -> RM 20.00.
    - Customer ID starts with digits (YYMMDD...) -> Malaysian National ID (MyKad) -> RM 10.00.
    - Missing / undetectable -> Default = RM 10.00.
    """
    if not ic_or_passport:
        return 10.0
    cleaned = ic_or_passport.strip().upper()
    if not cleaned:
        return 10.0
    if cleaned[0].isalpha():
        return 20.0
    return 10.0


def _extract_vehicle_sum_insured(f: dict[str, Any]) -> float:
    """Disambiguate vehicle sum insured from accessory endorsement limits (e.g. windscreen RM 4,000)."""
    c_cov = _to_float(f.get("coverage_amount"))
    c_sum = _to_float(f.get("sum_insured"))
    c_mkt = _to_float(f.get("market_value"))
    c_agr = _to_float(f.get("agreed_value"))

    # Malaysian motor vehicles typically have sum insured >= RM 10,000.
    # Exclude add-on sub-limits (like windscreen RM 4,000) when vehicle-level coverage is available.
    major_candidates = [c for c in [c_cov, c_mkt, c_agr, c_sum] if c >= 10000.0]
    if major_candidates:
        if c_cov >= 10000.0:
            return c_cov
        return max(major_candidates)

    all_candidates = [c for c in [c_sum, c_cov, c_mkt, c_agr] if c > 0.0]
    return max(all_candidates) if all_candidates else 0.0


def _extract_vehicle_motor_premium(f: dict[str, Any]) -> float:
    """Extract motor insurance premium payable to underwriter (including SST and stamp duty)."""
    total_amt = _to_float(f.get("total_amount") or f.get("total_payable"))
    if total_amt > 0.0:
        return total_amt
    gross = _to_float(f.get("gross_premium"))
    if gross > 0.0:
        return gross
    return _to_float(f.get("basic_premium") or f.get("premium") or f.get("insurance_premium"))


def _extract_valuation_type(f: dict[str, Any]) -> tuple[str, bool]:
    """Determine agreed value vs market value."""
    val_type_str = _safe_str(f.get("valuation_type")).lower()
    agr_val = _extract_val(f.get("agreed_value"))
    is_agreed = (
        "agreed" in val_type_str
        or agr_val in [True, "Yes", "yes", "true", "True", "1"]
    )
    if is_agreed:
        return "agreed_value", True
    return "market_value", False


def _extract_excess(f: dict[str, Any]) -> float:
    return _to_float(f.get("excess_amount")) or _to_float(f.get("compulsory_excess")) or _to_float(f.get("excess"))


def _extract_llp_llop(f: dict[str, Any]) -> str | None:
    """Format and bound LLP / LLOP endorsement string to 50 chars."""
    raw = _safe_str(f.get("llp_llop") or f.get("legal_liability_to_passengers") or f.get("optional_covers") or f.get("all_drivers"))
    if not raw:
        return None
    raw_lower = raw.lower()
    if "passenger" in raw_lower or "llp" in raw_lower:
        return "Included"
    return raw[:50].strip() or None


def _extract_special_perils(f: dict[str, Any]) -> str | None:
    """Format and bound Special Perils endorsement string to 50 chars."""
    raw = _safe_str(f.get("special_perils") or f.get("optional_covers"))
    if not raw:
        return None
    raw_lower = raw.lower()
    if "special perils" in raw_lower or "flood" in raw_lower:
        return "Included"
    return raw[:50].strip() or None


def get_marketing_comparison(db: Session, tenure_id: str) -> dict[str, Any]:
    """Retrieve or auto-hydrate the full marketing comparison matrix for an insurance tenure.
    
    Returns:
        Structured comparison payload containing:
        - tenure metadata & fixed costs (road tax + runner fee)
        - side-by-side underwriter comparison columns
        - previous policy year reference card (Year - 1)
        - recommended sum insured / valuation matrix
        - NCD status
    """
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise ValueError(f"Tenure {tenure_id} not found")

    # 1. Inspect existing comparison entries
    entries = list(
        db.scalars(
            select(TenureComparisonEntry)
            .where(TenureComparisonEntry.tenure_id == tenure_id)
            .order_by(TenureComparisonEntry.sort_order.asc(), TenureComparisonEntry.created_at.asc())
        ).all()
    )

    needs_commit = False

    # 2. Query all linked sessions under this tenure
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

    # Gather candidate customer IC / passport for runner fee detection
    cand_ic = ""
    for s in sessions:
        if s.draft and isinstance(s.draft.fields, dict):
            f = s.draft.fields
            if not cand_ic:
                cand_ic = _safe_str(f.get("ic_no") or f.get("nric") or f.get("ic_or_brn") or f.get("passport_no"))

    # Detect road tax and runner fee from available drafts or Malaysian IC vs Passport rules
    road_tax_val = float(tenure.road_tax)
    runner_fee_val = float(tenure.runner_fee)

    for s in sessions:
        if s.draft and s.draft.fields:
            f = s.draft.fields
            cand_rt = _to_float(f.get("road_tax") or f.get("roadtax"))
            if cand_rt > 0.0 and (road_tax_val == 0.0 or cand_rt > road_tax_val):
                road_tax_val = cand_rt
            cand_rf = _to_float(f.get("runner_fee") or f.get("runner"))
            if cand_rf > 0.0 and runner_fee_val == 0.0:
                runner_fee_val = cand_rf

    # Auto-detect runner fee from Malaysian MyKad vs International Passport if 0.0
    if runner_fee_val == 0.0:
        runner_fee_val = detect_runner_fee_from_id(cand_ic)

    if road_tax_val != float(tenure.road_tax) or runner_fee_val != float(tenure.runner_fee):
        tenure.road_tax = road_tax_val
        tenure.runner_fee = runner_fee_val
        needs_commit = True

    # 3. If no entries exist yet, auto-hydrate from sessions under this tenure
    if not entries:
        for idx, s in enumerate(sessions):
            comp_name = s.detected_company or (s.uploaded_file.original_filename if s.uploaded_file else f"Quote #{idx+1}")
            f = s.draft.fields if s.draft and s.draft.fields else {}

            sum_ins = _extract_vehicle_sum_insured(f)
            motor_prem = _extract_vehicle_motor_premium(f)
            val_type, agreed = _extract_valuation_type(f)
            towing = _safe_str(f.get("towing_limit") or f.get("towing") or "Unlimited")[:100]
            betterment = _extract_val(f.get("waiver_of_betterment")) in [True, "Yes", "yes", "true", "True", "1"]
            excess_val = _extract_excess(f)
            rate_val = round((motor_prem / sum_ins) * 100, 4) if sum_ins > 0 else None
            tot_pay = motor_prem + float(tenure.road_tax) + float(tenure.runner_fee)

            entry = TenureComparisonEntry(
                tenure_id=tenure_id,
                session_id=s.id,
                company_name=comp_name,
                company_id=getattr(s, "company_id", None),
                sum_insured=sum_ins,
                valuation_type=val_type,
                motor_premium=motor_prem,
                road_tax=float(tenure.road_tax),
                runner_fee=float(tenure.runner_fee),
                total_payable=tot_pay,
                towing_limit=towing or "Unlimited",
                agreed_value=agreed,
                waiver_betterment=betterment,
                excess=excess_val,
                rate_percentage=rate_val,
                windscreen_sum_insured=_to_float(f.get("windscreen_coverage") or f.get("windscreen_sum_insured")) or None,
                special_perils=_extract_special_perils(f),
                llp_llop=_extract_llp_llop(f),
                sort_order=idx,
                is_recommended=bool(
                    (tenure.winning_quotation_ref and s.quotation_ref == tenure.winning_quotation_ref)
                    or (tenure.winning_company_id and getattr(s, "company_id", None) == tenure.winning_company_id)
                ),
            )
            db.add(entry)
            entries.append(entry)

        needs_commit = True
    else:
        # Synchronize any sessions under this tenure that don't have a comparison entry yet
        existing_sess_ids = {e.session_id for e in entries if e.session_id}
        unlinked_sessions = [s for s in sessions if s.id not in existing_sess_ids]
        if unlinked_sessions:
            for idx, s in enumerate(unlinked_sessions):
                comp_name = s.detected_company or (s.uploaded_file.original_filename if s.uploaded_file else f"Quote #{len(entries)+idx+1}")
                f = s.draft.fields if s.draft and s.draft.fields else {}

                sum_ins = _extract_vehicle_sum_insured(f)
                motor_prem = _extract_vehicle_motor_premium(f)
                val_type, agreed = _extract_valuation_type(f)
                towing = _safe_str(f.get("towing_limit") or f.get("towing") or "Unlimited")[:100]
                betterment = _extract_val(f.get("waiver_of_betterment")) in [True, "Yes", "yes", "true", "True", "1"]
                excess_val = _extract_excess(f)
                rate_val = round((motor_prem / sum_ins) * 100, 4) if sum_ins > 0 else None
                tot_pay = motor_prem + float(tenure.road_tax) + float(tenure.runner_fee)

                new_entry = TenureComparisonEntry(
                    tenure_id=tenure_id,
                    session_id=s.id,
                    company_name=comp_name,
                    company_id=getattr(s, "company_id", None),
                    sum_insured=sum_ins,
                    valuation_type=val_type,
                    motor_premium=motor_prem,
                    road_tax=float(tenure.road_tax),
                    runner_fee=float(tenure.runner_fee),
                    total_payable=tot_pay,
                    towing_limit=towing or "Unlimited",
                    agreed_value=agreed,
                    waiver_betterment=betterment,
                    excess=excess_val,
                    rate_percentage=rate_val,
                    windscreen_sum_insured=_to_float(f.get("windscreen_coverage") or f.get("windscreen_sum_insured")) or None,
                    special_perils=_extract_special_perils(f),
                    llp_llop=_extract_llp_llop(f),
                    sort_order=len(entries) + idx,
                    is_recommended=bool(
                        (tenure.winning_quotation_ref and s.quotation_ref == tenure.winning_quotation_ref)
                        or (tenure.winning_company_id and getattr(s, "company_id", None) == tenure.winning_company_id)
                    ),
                )
                db.add(new_entry)
                entries.append(new_entry)
            needs_commit = True

        # Auto-healing: If existing entries hold zeroed sum_insured, motor_premium, or zeroed runner_fee
        for e in entries:
            # Sync runner fee from tenure if entry is 0.0
            if float(e.runner_fee) == 0.0 and float(tenure.runner_fee) > 0.0:
                e.runner_fee = float(tenure.runner_fee)
                e.total_payable = float(e.motor_premium) + float(e.road_tax) + float(e.runner_fee)
                needs_commit = True

            if (e.sum_insured == 0.0 or e.motor_premium == 0.0) and e.session_id:
                s = db.get(SessionModel, e.session_id)
                if s and s.draft and s.draft.fields:
                    f = s.draft.fields
                    h_sum = _extract_vehicle_sum_insured(f)
                    h_prem = _extract_vehicle_motor_premium(f)
                    val_type, is_agr = _extract_valuation_type(f)

                    if h_sum > 0.0:
                        e.sum_insured = h_sum
                    if h_prem > 0.0:
                        e.motor_premium = h_prem
                    e.valuation_type = val_type
                    e.agreed_value = is_agr
                    e.excess = _extract_excess(f)
                    e.towing_limit = _safe_str(f.get("towing_limit") or f.get("towing") or "Unlimited")[:100]
                    e.waiver_betterment = _extract_val(f.get("waiver_of_betterment")) in [True, "Yes", "yes", "true", "True", "1"]
                    e.windscreen_sum_insured = _to_float(f.get("windscreen_coverage") or f.get("windscreen_sum_insured")) or None
                    e.special_perils = _extract_special_perils(f)
                    e.llp_llop = _extract_llp_llop(f)

                    e.road_tax = float(tenure.road_tax)
                    e.runner_fee = float(tenure.runner_fee)
                    e.total_payable = float(e.motor_premium) + e.road_tax + e.runner_fee
                    if e.sum_insured > 0.0:
                        e.rate_percentage = round((float(e.motor_premium) / float(e.sum_insured)) * 100, 4)
                    needs_commit = True

        # Sync road tax from session drafts if tenure fixed road tax is 0 or needs update
        for e in entries:
            if e.session_id:
                s = db.get(SessionModel, e.session_id)
                if s and s.draft and s.draft.fields:
                    cand_rt = _to_float(s.draft.fields.get("road_tax") or s.draft.fields.get("roadtax"))
                    if cand_rt > 0.0 and (float(tenure.road_tax) == 0.0 or cand_rt > float(tenure.road_tax)):
                        tenure.road_tax = cand_rt
                        for item in entries:
                            item.road_tax = cand_rt
                            item.total_payable = float(item.motor_premium) + cand_rt + float(item.runner_fee)
                        needs_commit = True
                        break

    if needs_commit:
        db.commit()


    # 3. Retrieve Previous Policy (Year - 1 / 365 Days Prior)
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

    prev_policy_data = None
    if prev_tenure:
        prev_entries = list(
            db.scalars(
                select(TenureComparisonEntry)
                .where(TenureComparisonEntry.tenure_id == prev_tenure.id)
                .order_by(TenureComparisonEntry.is_recommended.desc(), TenureComparisonEntry.total_payable.asc())
            ).all()
        )
        best_prev = prev_entries[0] if prev_entries else None
        prev_policy_data = {
            "year": prev_tenure.coverage_start_date.year,
            "period": f"{prev_tenure.coverage_start_date.strftime('%d/%m/%Y')} - {prev_tenure.coverage_end_date.strftime('%d/%m/%Y')}",
            "insurer": (prev_tenure.winning_company.name if prev_tenure.winning_company else None) or (best_prev.company_name if best_prev else "Previous Insurer"),
            "sum_insured": float(best_prev.sum_insured) if best_prev else 0.0,
            "insurance_premium": float(prev_tenure.won_premium) if prev_tenure.won_premium is not None else (float(best_prev.motor_premium) if best_prev else 0.0),
            "perils": "LLP, LLOP, PA",
            "model": tenure.tracked_vehicle.car_model if tenure.tracked_vehicle else "Standard Model",
            "yom": getattr(tenure.tracked_vehicle, "manufacture_year", None) or 2023,
            "sub_agent": "RM_01_EugeneLee",
        }

    # 4. Formulate Recommended Sum Insured matrix
    # 4. Formulate Recommended Sum Insured matrix (genuine underwriter figures only)
    rec_sum_insured = tenure.recommended_sum_insured_json or {}
    if (not rec_sum_insured or all(v == 0.0 for v in rec_sum_insured.values())) and entries:
        rec_sum_insured = {}
        for e in entries:
            clean_c = e.company_name.split()[0]
            if float(e.sum_insured) > 0.0:
                rec_sum_insured[clean_c] = float(e.sum_insured)

    # Aggregate customer & vehicle metadata from linked sessions
    linked_sessions = list(
        db.scalars(
            select(SessionModel)
            .where(
                SessionModel.tenure_id == tenure_id,
                SessionModel.status != "trash",
            )
            .order_by(SessionModel.created_at.desc())
        ).all()
    )

    cust_ic = ""
    cust_phone = ""
    cust_email = ""
    cust_address = ""
    veh_engine_no = ""
    veh_chassis_no = ""
    veh_yom = getattr(tenure.tracked_vehicle, "manufacture_year", None) if tenure.tracked_vehicle else None
    veh_seating = ""
    veh_engine_cc = tenure.tracked_vehicle.engine_cc if tenure.tracked_vehicle else ""
    veh_model = tenure.tracked_vehicle.car_model if tenure.tracked_vehicle else ""

    for s in linked_sessions:
        if s.draft and isinstance(s.draft.fields, dict):
            f = s.draft.fields
            if not cust_ic:
                cust_ic = _safe_str(f.get("ic_no") or f.get("nric") or f.get("ic_or_brn") or f.get("passport_no"))
            if not cust_phone:
                cust_phone = _safe_str(f.get("phone_number") or f.get("contact_no") or f.get("mobile"))
            if not cust_email:
                cust_email = _safe_str(f.get("email"))
            if not cust_address:
                cust_address = _safe_str(f.get("address") or f.get("location"))
            if not veh_engine_no:
                veh_engine_no = _safe_str(f.get("engine_number") or f.get("engine_no"))
            if not veh_chassis_no:
                veh_chassis_no = _safe_str(f.get("chassis_number") or f.get("chassis_no") or f.get("vin"))
            if not veh_engine_cc:
                veh_engine_cc = _safe_str(f.get("engine_cc") or f.get("capacity"))
            if not veh_model:
                veh_model = _safe_str(f.get("car_model") or f.get("vehicle_model"))
            if not veh_yom:
                raw_yom = f.get("manufacture_year") or f.get("year_of_manufacture") or f.get("yom")
                if raw_yom:
                    try:
                        veh_yom = int(_safe_str(raw_yom))
                    except (ValueError, TypeError):
                        pass
            if not veh_seating:
                veh_seating = _safe_str(f.get("seating_capacity") or f.get("seat_capacity"))

    # 5. Format Entry Payloads
    entry_dicts = []
    for e in entries:
        entry_dicts.append({
            "id": e.id,
            "tenure_id": e.tenure_id,
            "session_id": e.session_id,
            "company_name": e.company_name,
            "company_id": e.company_id,
            "sum_insured": float(e.sum_insured),
            "valuation_type": e.valuation_type,
            "motor_premium": float(e.motor_premium),
            "road_tax": float(e.road_tax),
            "runner_fee": float(e.runner_fee),
            "total_payable": float(e.total_payable),
            "towing_limit": e.towing_limit,
            "agreed_value": e.agreed_value,
            "waiver_betterment": e.waiver_betterment,
            "excess": float(e.excess),
            "rate_percentage": float(e.rate_percentage) if e.rate_percentage is not None else None,
            "windscreen_sum_insured": float(e.windscreen_sum_insured) if e.windscreen_sum_insured else None,
            "special_perils": e.special_perils,
            "llp_llop": e.llp_llop,
            "personal_accident": e.personal_accident,
            "is_recommended": e.is_recommended,
            "is_manual": e.is_manual,
            "sort_order": e.sort_order,
            "notes": e.notes,
        })

    return {
        "tenure": {
            "id": tenure.id,
            "vehicle_no": tenure.vehicle_no,
            "customer_name": tenure.customer_name,
            "ic_no": cust_ic,
            "phone": cust_phone,
            "email": cust_email,
            "address": cust_address,
            "engine_cc": veh_engine_cc or "1496 CC",
            "engine_no": veh_engine_no,
            "chassis_no": veh_chassis_no,
            "manufacture_year": veh_yom or 2023,
            "seating_capacity": veh_seating or "5",
            "coverage_start_date": tenure.coverage_start_date.isoformat(),
            "coverage_end_date": tenure.coverage_end_date.isoformat(),
            "coverage_period_formatted": f"{tenure.coverage_start_date.strftime('%d/%m/%Y')} - {tenure.coverage_end_date.strftime('%d/%m/%Y')}",
            "expiry_month": tenure.expiry_month,
            "status": tenure.status,
            "road_tax": float(tenure.road_tax),
            "runner_fee": float(tenure.runner_fee),
            "runner_fee_type": "passport" if ((cust_ic or cand_ic).strip() and (cust_ic or cand_ic).strip()[0].isalpha()) else "mykad",
            "fixed_costs_total": float(tenure.road_tax + tenure.runner_fee),
            "windscreen_target": float(tenure.windscreen_target) if tenure.windscreen_target else None,
            "ncd_percentage": float(tenure.ncd_percentage or 55.0),
            "vehicle_model": veh_model or "Motor Vehicle",
            "vehicle_type": "Comprehensive (综合险)",
        },
        "entries": entry_dicts,
        "previous_policy": prev_policy_data,
        "recommended_sum_insured": rec_sum_insured,
        "ncd": {
            "current": float(tenure.ncd_percentage or 55.0),
            "next": float(tenure.ncd_percentage or 55.0),
        },
    }


def update_tenure_fixed_costs(
    db: Session,
    tenure_id: str,
    *,
    road_tax: float,
    runner_fee: float,
    windscreen_target: float | None = None,
    ncd_percentage: float | None = None,
    coverage_start_date: str | None = None,
    coverage_end_date: str | None = None,
    customer_name: str | None = None,
    ic_no: str | None = None,
    engine_cc: str | None = None,
    engine_no: str | None = None,
    chassis_no: str | None = None,
    vehicle_model: str | None = None,
) -> dict[str, Any]:
    """Update fixed tenure expenses (Road Tax & Runner Fee), coverage dates, vehicle specs, and recalculate total payables for all columns."""
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise ValueError(f"Tenure {tenure_id} not found")

    tenure.road_tax = road_tax
    if runner_fee > 0.0:
        tenure.runner_fee = runner_fee
    elif ic_no and ic_no.strip():
        tenure.runner_fee = detect_runner_fee_from_id(ic_no.strip())
    else:
        tenure.runner_fee = runner_fee
    if windscreen_target is not None:
        tenure.windscreen_target = windscreen_target
    if ncd_percentage is not None:
        tenure.ncd_percentage = ncd_percentage

    if customer_name and customer_name.strip():
        tenure.customer_name = customer_name.strip()

    if tenure.tracked_vehicle:
        if engine_cc and engine_cc.strip():
            tenure.tracked_vehicle.engine_cc = engine_cc.strip()
        if vehicle_model and vehicle_model.strip():
            tenure.tracked_vehicle.car_model = vehicle_model.strip()

    # Date manipulation & synchronization
    dt_start = None
    dt_end = None
    if coverage_start_date:
        try:
            clean_s = coverage_start_date.split("T")[0].strip()
            if clean_s:
                dt_start = datetime.strptime(clean_s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                tenure.coverage_start_date = dt_start
        except Exception as e:
            logger.warning("Could not parse coverage_start_date '%s': %s", coverage_start_date, e)

    if coverage_end_date:
        try:
            clean_e = coverage_end_date.split("T")[0].strip()
            if clean_e:
                dt_end = datetime.strptime(clean_e, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                tenure.coverage_end_date = dt_end
                tenure.expiry_month = dt_end.strftime("%Y-%m")
        except Exception as e:
            logger.warning("Could not parse coverage_end_date '%s': %s", coverage_end_date, e)

    # Propagate updated coverage dates and metadata to linked sessions
    linked_sessions = list(
        db.scalars(
            select(SessionModel).where(SessionModel.tenure_id == tenure_id)
        ).all()
    )
    for s in linked_sessions:
        if dt_start:
            s.coverage_start_date = dt_start
        if dt_end:
            s.coverage_end_date = dt_end
        if s.draft and isinstance(s.draft.fields, dict):
            f = dict(s.draft.fields)
            if dt_start:
                f["coverage_start_date"] = dt_start.isoformat()
            if dt_end:
                f["coverage_end_date"] = dt_end.isoformat()
            if customer_name:
                f["customer_name"] = customer_name.strip()
            if ic_no:
                f["ic_no"] = ic_no.strip()
            if engine_cc:
                f["engine_cc"] = engine_cc.strip()
            if engine_no:
                f["engine_number"] = engine_no.strip()
            if chassis_no:
                f["chassis_number"] = chassis_no.strip()
            if vehicle_model:
                f["car_model"] = vehicle_model.strip()
            s.draft.fields = f

    # Update all comparison entries under this tenure
    entries = list(
        db.scalars(
            select(TenureComparisonEntry).where(TenureComparisonEntry.tenure_id == tenure_id)
        ).all()
    )
    for e in entries:
        e.road_tax = road_tax
        e.runner_fee = float(tenure.runner_fee)
        e.total_payable = float(e.motor_premium) + road_tax + float(tenure.runner_fee)

    db.commit()
    return get_marketing_comparison(db, tenure_id)



def save_comparison_entry(
    db: Session,
    tenure_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Save or update a single underwriter column in the comparison matrix."""
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise ValueError(f"Tenure {tenure_id} not found")

    entry_id = payload.get("id")
    entry = db.get(TenureComparisonEntry, entry_id) if entry_id else None

    if not entry:
        entry = TenureComparisonEntry(
            tenure_id=tenure_id,
            company_name=_safe_str(payload.get("company_name") or "New Insurer"),
            is_manual=bool(payload.get("is_manual", True)),
        )
        db.add(entry)

    # Update fields
    if "company_name" in payload:
        entry.company_name = _safe_str(payload["company_name"])
    if "sum_insured" in payload:
        entry.sum_insured = _to_float(payload["sum_insured"])
    if "valuation_type" in payload:
        entry.valuation_type = _safe_str(payload["valuation_type"])
        entry.agreed_value = entry.valuation_type == "agreed_value"
    if "motor_premium" in payload:
        entry.motor_premium = _to_float(payload["motor_premium"])
    if "towing_limit" in payload:
        entry.towing_limit = _safe_str(payload["towing_limit"])
    if "agreed_value" in payload:
        entry.agreed_value = bool(payload["agreed_value"])
        if entry.agreed_value:
            entry.valuation_type = "agreed_value"
    if "waiver_betterment" in payload:
        entry.waiver_betterment = bool(payload["waiver_betterment"])
    if "excess" in payload:
        entry.excess = _to_float(payload["excess"])
    if "windscreen_sum_insured" in payload:
        entry.windscreen_sum_insured = _to_float(payload["windscreen_sum_insured"]) or None
    if "special_perils" in payload:
        entry.special_perils = _safe_str(payload["special_perils"]) or None
    if "is_recommended" in payload:
        entry.is_recommended = bool(payload["is_recommended"])

    # Recompute fixed costs and total payable
    entry.road_tax = float(tenure.road_tax)
    entry.runner_fee = float(tenure.runner_fee)
    entry.total_payable = float(entry.motor_premium) + entry.road_tax + entry.runner_fee

    if float(entry.sum_insured) > 0:
        entry.rate_percentage = round((float(entry.motor_premium) / float(entry.sum_insured)) * 100, 4)

    db.commit()
    return get_marketing_comparison(db, tenure_id)


def delete_comparison_entry(db: Session, tenure_id: str, entry_id: str) -> dict[str, Any]:
    """Delete a comparison column."""
    entry = db.get(TenureComparisonEntry, entry_id)
    if entry and entry.tenure_id == tenure_id:
        db.delete(entry)
        db.commit()
    return get_marketing_comparison(db, tenure_id)


def select_winner_and_generate_draft(
    db: Session,
    tenure_id: str,
    entry_id: str,
    user_id: str,
    *,
    force_state: bool | None = None,
) -> dict[str, Any]:
    """Toggle or set winning underwriter recommendation state, update tenure status,
    and prepare the Quotation Builder draft.
    Allows multiple winners (e.g. 2 or 3 quotes) and clicking to deselect/unpick.
    """
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise ValueError(f"Tenure {tenure_id} not found")

    entry = db.get(TenureComparisonEntry, entry_id)
    if not entry or entry.tenure_id != tenure_id:
        raise ValueError(f"Comparison entry {entry_id} not found under tenure {tenure_id}")

    # Determine target recommendation state (toggle if force_state is None)
    new_state = (not entry.is_recommended) if force_state is None else force_state
    entry.is_recommended = new_state

    session_id = entry.session_id
    draft_id = None

    if new_state:
        # If newly selected, ensure linked session has an official RL reference
        if session_id:
            s = db.get(SessionModel, session_id)
            if s:
                if not s.quotation_ref or not s.quotation_ref.startswith("RL"):
                    ref_num = f"RL-{tenure.vehicle_no}-{datetime.now(timezone.utc).strftime('%y%m%d%H%M')}"
                    s.quotation_ref = ref_num
                draft_id = s.draft_id
        else:
            # For manual quotes without a session, create a pre-filled draft
            new_draft = QuotationDraft(
                id=new_id(),
                uploaded_file_id=new_id(),
                owner_id=user_id,
                fields={
                    "vehicle_no": tenure.vehicle_no,
                    "customer_name": tenure.customer_name,
                    "insurance_company": entry.company_name,
                    "sum_insured": float(entry.sum_insured),
                    "basic_premium": float(entry.motor_premium),
                    "road_tax": float(entry.road_tax),
                    "runner_fee": float(entry.runner_fee),
                    "total_payable": float(entry.total_payable),
                    "towing_limit": entry.towing_limit,
                    "agreed_value": entry.agreed_value,
                    "waiver_of_betterment": entry.waiver_betterment,
                    "excess": float(entry.excess),
                    "coverage_start_date": tenure.coverage_start_date.isoformat(),
                    "coverage_end_date": tenure.coverage_end_date.isoformat(),
                },
            )
            db.add(new_draft)
            db.flush()
            draft_id = new_draft.id

    # Query all currently recommended entries under this tenure
    all_entries = list(
        db.scalars(
            select(TenureComparisonEntry).where(TenureComparisonEntry.tenure_id == tenure_id)
        ).all()
    )
    rec_entries = [e for e in all_entries if e.is_recommended]

    if rec_entries:
        primary = entry if new_state else rec_entries[0]
        tenure.status = "quoted"
        tenure.winning_company_id = primary.company_id
        tenure.won_premium = primary.total_payable
        if primary.session_id:
            s_primary = db.get(SessionModel, primary.session_id)
            if s_primary and s_primary.quotation_ref:
                tenure.winning_quotation_ref = s_primary.quotation_ref
    else:
        tenure.winning_company_id = None
        tenure.won_premium = None
        tenure.winning_quotation_ref = None

    db.commit()

    return {
        "status": "success",
        "tenure_id": tenure.id,
        "entry_id": entry.id,
        "is_recommended": entry.is_recommended,
        "selected_count": len(rec_entries),
        "winning_company": entry.company_name,
        "total_payable": float(entry.total_payable),
        "session_id": session_id,
        "draft_id": draft_id,
        "quotation_ref": tenure.winning_quotation_ref,
    }


def format_whatsapp_teaser(db: Session, tenure_id: str) -> str:
    """Format a clean, executive WhatsApp teaser message comparing all underwriters for client messaging."""
    data = get_marketing_comparison(db, tenure_id)
    tenure = data["tenure"]
    entries = data["entries"]

    plate = tenure["vehicle_no"]
    customer = tenure["customer_name"]
    model = tenure["vehicle_model"]
    period = tenure["coverage_period_formatted"]
    ncd = tenure["ncd_percentage"]

    lines = [
        f"🚗 *Insurance Renewal Comparison for {plate}*",
        f"👤 Customer: {customer}",
        f"🚘 Vehicle: {model} ({tenure['engine_cc']})",
        f"📅 Period: {period} | NCD: {ncd:.0f}%",
        f"🛣️ Road Tax & Runner Fee: RM {tenure['fixed_costs_total']:.2f}",
        "",
        "📋 *UNDERWRITER COMPARISON:*",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for idx, e in enumerate(entries, 1):
        rec_tag = " ★ (RECOMMENDED)" if e["is_recommended"] else ""
        val_tag = "Agreed Value" if e["agreed_value"] else "Market Value"
        betterment_tag = "Yes" if e["waiver_betterment"] else "No"

        lines.extend([
            f"*{idx}. {e['company_name']}{rec_tag}*",
            f"   • Sum Insured: RM {e['sum_insured']:,.2f} ({val_tag})",
            f"   • Motor Insurance: RM {e['motor_premium']:,.2f}",
            f"   • *TOTAL PAYABLE: RM {e['total_payable']:,.2f}*",
            f"   • Towing: {e['towing_limit']}",
            f"   • Waiver of Betterment: {betterment_tag} | Excess: RM {e['excess']:.2f}",
            "",
        ])

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")

    rec_winners = [e for e in entries if e.get("is_recommended")]
    if len(rec_winners) == 1:
        lines.append(f"🏆 *Recommended Choice:* {rec_winners[0]['company_name']} (Total: RM {rec_winners[0]['total_payable']:,.2f})\n")
    elif len(rec_winners) > 1:
        winner_items = ", ".join(f"{w['company_name']} (RM {w['total_payable']:,.2f})" for w in rec_winners)
        lines.append(f"🏆 *Shortlisted Options ({len(rec_winners)}):* {winner_items}\n")

    lines.append("💡 *Please let us know your preferred insurer so we can issue your official Risk-Locker quotation!*")

    return "\n".join(lines)

