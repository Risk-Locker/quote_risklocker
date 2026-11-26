"""
Tenure Identity & Cross-Workspace Synchronization Service.

Single source of truth for synchronizing vehicle specifications, customer identity,
coverage periods, and shared fixed fees across:
  - TrackedVehicle
  - InsuranceTenure
  - CustomerAccount
  - Linked Sessions and QuotationDraft.fields
  - Linked TenureComparisonEntry rows
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.orm.attributes import flag_modified

from app.models.tables import (
    CustomerAccount,
    InsuranceTenure,
    Session as SessionModel,
    TenureComparisonEntry,
    TrackedVehicle,
)
from app.services.identity_normalization_service import normalize_government_id
from app.services.vehicle_simplifier_service import CANONICAL_BRANDS
from app.services.vehicle_tracking_service import normalize_plate

logger = logging.getLogger(__name__)

UNIVERSAL_RUNNER_FEE = Decimal("20.00")
TWO_PLACES = Decimal("0.01")


def _to_decimal(val: Any) -> Decimal:
    """Safely convert any numeric or formatted money string into a 2-decimal Decimal."""
    if val is None:
        return Decimal("0.00")
    if isinstance(val, Decimal):
        return val.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    if isinstance(val, (int, float)):
        return Decimal(str(val)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    cleaned = re.sub(r"[^\d.\-]", "", str(val).strip())
    if not cleaned or cleaned in {"-", ".", "-."}:
        return Decimal("0.00")
    try:
        return Decimal(cleaned).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0.00")


def _parse_date(val: Any) -> datetime | None:
    if not val:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    s = str(val).split("T")[0].strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _set_draft_field(fields: dict[str, Any], key: str, value: Any, status: str = "manual_override") -> None:
    if key in fields and isinstance(fields[key], dict):
        fields[key] = {**fields[key], "value": value, "status": status}
    else:
        fields[key] = value


def _update_existing_aliases(fields: dict[str, Any], aliases: tuple[str, ...], value: Any) -> None:
    """Update alias keys only when already present in fields (never bloat drafts with new mirror keys)."""
    for alias in aliases:
        if alias in fields:
            _set_draft_field(fields, alias, value)


def _apply_tenure_fees_and_ncd(
    tenure: InsuranceTenure,
    *,
    road_tax: float | Decimal | None,
    runner_fee: float | Decimal | None,
    include_road_tax: bool | None,
    include_runner_fee: bool | None,
    windscreen_target: float | Decimal | None,
    ncd_percentage: float | Decimal | None,
    current_ncd: float | Decimal | None,
    quotation_discount: float | Decimal | None,
    motor_discount_pct: float | Decimal | None = None,
) -> None:
    """Apply fixed fee toggles, Decimal fee amounts, and NCD percentages onto InsuranceTenure."""
    if include_road_tax is not None:
        tenure.include_road_tax = include_road_tax
    elif road_tax is not None and _to_decimal(road_tax) == Decimal("0.00"):
        tenure.include_road_tax = False

    if include_runner_fee is not None:
        tenure.include_runner_fee = include_runner_fee
    elif runner_fee is not None and _to_decimal(runner_fee) == Decimal("0.00"):
        tenure.include_runner_fee = False

    if road_tax is not None:
        tenure.road_tax = float(max(Decimal("0.00"), _to_decimal(road_tax)))

    if runner_fee is not None and _to_decimal(runner_fee) > Decimal("0.00"):
        tenure.runner_fee = float(_to_decimal(runner_fee))
    elif tenure.runner_fee is None or _to_decimal(tenure.runner_fee) == Decimal("0.00"):
        tenure.runner_fee = float(UNIVERSAL_RUNNER_FEE)

    if quotation_discount is not None:
        tenure.quotation_discount = float(max(Decimal("0.00"), _to_decimal(quotation_discount)))
    if motor_discount_pct is not None:
        from app.domain.motor.discount_calculator import clamp_discount_pct

        tenure.motor_discount_pct = float(clamp_discount_pct(motor_discount_pct))
    if windscreen_target is not None:
        tenure.windscreen_target = float(max(Decimal("0.00"), _to_decimal(windscreen_target)))
    if ncd_percentage is not None:
        tenure.ncd_percentage = float(_to_decimal(ncd_percentage))

    if current_ncd is not None:
        c_ncd_val = _to_decimal(current_ncd)
        if tenure.previous_tenure:
            tenure.previous_tenure.ncd_percentage = float(c_ncd_val)
        cur_json = dict(tenure.recommended_sum_insured_json or {})
        cur_json["current_ncd"] = float(c_ncd_val)
        tenure.recommended_sum_insured_json = cur_json


def _sync_tenure_customer(
    db: Session,
    tenure: InsuranceTenure,
    customer_name: str | None,
    ic_or_brn: str | None,
) -> CustomerAccount | None:
    """Resolve or update CustomerAccount and link to InsuranceTenure."""
    clean_cust_name = customer_name.strip() if (customer_name and customer_name.strip()) else None
    clean_ic = ic_or_brn.strip() if (ic_or_brn and ic_or_brn.strip()) else None

    if clean_cust_name:
        tenure.customer_name = clean_cust_name
    if not clean_cust_name and not clean_ic:
        return tenure.customer

    cust = tenure.customer or (db.get(CustomerAccount, tenure.customer_id) if tenure.customer_id else None)
    if not cust:
        from app.services.marketing_comparison_service import resolve_or_create_customer
        cust, _ = resolve_or_create_customer(
            db,
            raw_name=clean_cust_name or tenure.customer_name,
            raw_id=clean_ic,
        )
    if not cust:
        return None

    tenure.customer_id = cust.id
    if clean_cust_name:
        cust.canonical_name = clean_cust_name
    if clean_ic:
        norm_id, norm_type = normalize_government_id(clean_ic)
        cust.id_number = norm_id or clean_ic
        if norm_type:
            cust.id_type = norm_type

    db.execute(
        update(InsuranceTenure)
        .where(InsuranceTenure.customer_id == cust.id)
        .values(customer_name=cust.canonical_name)
    )
    return cust


def _infer_brand_from_model(car_model: str) -> str | None:
    model_upper = car_model.strip().upper()
    for key, canonical_brand in CANONICAL_BRANDS.items():
        if model_upper == key or model_upper.startswith(key + " "):
            return canonical_brand
    return None


def _sync_tenure_vehicle(
    db: Session,
    tenure: InsuranceTenure,
    *,
    vehicle_no: str | None,
    car_brand: str | None,
    car_model: str | None,
    engine_cc: str | None,
    manufacture_year: int | None,
    chassis_no: str | None,
    engine_no: str | None,
    powertrain: str | None,
) -> TrackedVehicle | None:
    """Resolve or update TrackedVehicle specifications for this tenure (chassis-first + plate history)."""
    from app.services.insurance_tenure_service import (
        is_valid_chassis,
        normalize_chassis,
        record_vehicle_plate_history,
    )
    from app.services.vehicle_tracking_service import is_valid_malaysian_plate

    clean_chassis = normalize_chassis(chassis_no)
    norm_plate = normalize_plate(vehicle_no.strip()) if (vehicle_no and vehicle_no.strip()) else None
    has_valid_plate = bool(norm_plate and is_valid_malaysian_plate(norm_plate))
    if not has_valid_plate and is_valid_chassis(clean_chassis):
        norm_plate = clean_chassis

    if norm_plate:
        tenure.vehicle_no = norm_plate

    tv = tenure.tracked_vehicle or (
        db.get(TrackedVehicle, tenure.tracked_vehicle_id) if tenure.tracked_vehicle_id else None
    )

    # Prefer matching by normalized chassis_no first
    if clean_chassis and (not tv or normalize_chassis(tv.chassis_no) != clean_chassis):
        chassis_tv = db.scalar(
            select(TrackedVehicle).where(
                or_(
                    TrackedVehicle.chassis_no == clean_chassis,
                    func.replace(func.upper(TrackedVehicle.chassis_no), "-", "") == clean_chassis,
                    TrackedVehicle.vehicle_no == clean_chassis,
                )
            )
        )
        if chassis_tv:
            tv = chassis_tv

    target_plate = norm_plate or tenure.vehicle_no
    if target_plate and not tv:
        existing_tv = db.scalar(select(TrackedVehicle).where(TrackedVehicle.vehicle_no == target_plate))
        if existing_tv:
            ex_chassis = normalize_chassis(existing_tv.chassis_no)
            if not clean_chassis or not ex_chassis or ex_chassis == clean_chassis:
                tv = existing_tv
        if not tv:
            tv = TrackedVehicle(
                vehicle_no=target_plate,
                chassis_no=chassis_no.strip() if (chassis_no and chassis_no.strip()) else None,
            )
            db.add(tv)
            db.flush()

    if not tv:
        return None

    tenure.tracked_vehicle = tv
    tenure.tracked_vehicle_id = tv.id

    if car_brand and car_brand.strip():
        tv.car_brand = car_brand.strip()
    if manufacture_year and manufacture_year > 1900:
        tv.manufacture_year = manufacture_year
    if engine_cc and engine_cc.strip():
        tv.engine_cc = engine_cc.strip()
    if car_model and car_model.strip():
        tv.car_model = car_model.strip()
        if not (car_brand and car_brand.strip()):
            tv.car_brand = _infer_brand_from_model(car_model) or tv.car_brand
    if engine_no and engine_no.strip():
        tv.engine_no = engine_no.strip()
    if chassis_no and chassis_no.strip():
        tv.chassis_no = chassis_no.strip()
    if hasattr(tv, "powertrain") and powertrain and powertrain.strip():
        setattr(tv, "powertrain", powertrain.strip().upper())

    if has_valid_plate and norm_plate:
        if normalize_plate(tv.vehicle_no) != norm_plate:
            tv.vehicle_no = norm_plate
        record_vehicle_plate_history(
            db,
            tracked_vehicle=tv,
            new_plate=norm_plate,
            source_tenure_id=tenure.id,
        )
    elif is_valid_chassis(clean_chassis) and not is_valid_malaysian_plate(tv.vehicle_no):
        tv.vehicle_no = clean_chassis
        tenure.vehicle_no = clean_chassis

    return tv


def _update_single_draft_fields(
    fields: dict[str, Any],
    *,
    tenure: InsuranceTenure,
    cust: CustomerAccount | None,
    tv: TrackedVehicle | None,
    vehicle_type: str | None,
    powertrain: str | None,
    dt_start: datetime | None,
    dt_end: datetime | None,
    eff_rt: Decimal,
    eff_rf: Decimal,
) -> dict[str, Any]:
    """Return updated draft fields dictionary with canonical identity and fee totals."""
    f = dict(fields)
    canonical_name = cust.canonical_name if cust else tenure.customer_name
    if canonical_name:
        _set_draft_field(f, "customer_name", canonical_name)
        _update_existing_aliases(f, ("insured_name", "policyholder_name", "client_name"), canonical_name)
    if cust and cust.id_number:
        _set_draft_field(f, "ic_or_brn", cust.id_number)
        _update_existing_aliases(f, ("customer_ic_no", "ic_no", "nric_no", "id_number"), cust.id_number)
    if tenure.vehicle_no:
        _set_draft_field(f, "vehicle_no", tenure.vehicle_no)
        _update_existing_aliases(f, ("registration_no", "veh_reg_no"), tenure.vehicle_no)

    if tv:
        if tv.car_brand:
            _set_draft_field(f, "car_brand", tv.car_brand)
            _update_existing_aliases(f, ("make",), tv.car_brand)
        if tv.car_model:
            _set_draft_field(f, "car_model", tv.car_model)
            _update_existing_aliases(f, ("vehicle_model",), tv.car_model)
        if tv.engine_cc:
            _set_draft_field(f, "engine_cc", tv.engine_cc)
        if tv.manufacture_year:
            _set_draft_field(f, "vehicle_year", str(tv.manufacture_year))
        if tv.chassis_no:
            _set_draft_field(f, "chassis_no", tv.chassis_no)
            _update_existing_aliases(f, ("chassis_number",), tv.chassis_no)
        if tv.engine_no:
            _set_draft_field(f, "engine_no", tv.engine_no)
            _update_existing_aliases(f, ("engine_number",), tv.engine_no)
        pt_val = getattr(tv, "powertrain", None) or (powertrain.strip().upper() if powertrain and powertrain.strip() else None)
        if pt_val:
            _set_draft_field(f, "powertrain", pt_val)
    elif powertrain and powertrain.strip():
        _set_draft_field(f, "powertrain", powertrain.strip().upper())

    if vehicle_type and vehicle_type.strip():
        _set_draft_field(f, "vehicle_type", vehicle_type.strip())
    if dt_start:
        _set_draft_field(f, "cover_start_date", dt_start.strftime("%Y-%m-%d"))
        _set_draft_field(f, "coverage_start_date", dt_start.isoformat())
    if dt_end:
        _set_draft_field(f, "cover_end_date", dt_end.strftime("%Y-%m-%d"))
        _set_draft_field(f, "coverage_end_date", dt_end.isoformat())
    if dt_start and dt_end:
        _set_draft_field(f, "cover_period", f"{dt_start.strftime('%d/%m/%Y')} - {dt_end.strftime('%d/%m/%Y')}")
    if tenure.ncd_percentage is not None:
        _set_draft_field(f, "ncd_percent", str(float(tenure.ncd_percentage)))

    _set_draft_field(f, "roadtax", f"{eff_rt:.2f}")
    _set_draft_field(f, "service_fee", f"{eff_rf:.2f}")

    from app.domain.motor.discount_calculator import calculate_motor_discount

    raw_prem = f.get("premium") or f.get("premium_due") or f.get("basic_premium_vehicle")
    val_prem = raw_prem.get("value") if isinstance(raw_prem, dict) else raw_prem
    prem_dec = _to_decimal(val_prem)
    pct_val = getattr(tenure, "motor_discount_pct", Decimal("0.00")) or Decimal("0.00")
    flat_val = getattr(tenure, "quotation_discount", Decimal("0.00")) or Decimal("0.00")
    disc_bd = calculate_motor_discount(prem_dec, pct_val, flat_val)
    _set_draft_field(f, "motor_discount_pct", f"{disc_bd.motor_discount_pct:.2f}", status="ready")
    if not isinstance(f.get("motor_discount_pct"), dict):
        f["motor_discount_pct"] = {"value": f"{disc_bd.motor_discount_pct:.2f}", "status": "ready"}
    _set_draft_field(f, "motor_discount_amount", f"{disc_bd.pct_discount_amount:.2f}", status="ready")
    if not isinstance(f.get("motor_discount_amount"), dict):
        f["motor_discount_amount"] = {"value": f"{disc_bd.pct_discount_amount:.2f}", "status": "ready"}
    _set_draft_field(f, "quotation_discount", f"{disc_bd.flat_discount_amount:.2f}", status="ready")
    if not isinstance(f.get("quotation_discount"), dict):
        f["quotation_discount"] = {"value": f"{disc_bd.flat_discount_amount:.2f}", "status": "ready"}
    _set_draft_field(f, "effective_discount", f"{disc_bd.effective_discount:.2f}", status="ready")
    if not isinstance(f.get("effective_discount"), dict):
        f["effective_discount"] = {"value": f"{disc_bd.effective_discount:.2f}", "status": "ready"}
    _set_draft_field(f, "net_motor_premium", f"{disc_bd.net_motor_premium:.2f}", status="ready")
    if not isinstance(f.get("net_motor_premium"), dict):
        f["net_motor_premium"] = {"value": f"{disc_bd.net_motor_premium:.2f}", "status": "ready"}
    tot_dec = disc_bd.net_total_payable(eff_rt, eff_rf)
    _set_draft_field(f, "total_amount", f"{tot_dec:.2f}")
    return f


def _sync_customer_identity_draft_fields(
    fields: dict[str, Any],
    cust: CustomerAccount | None,
) -> dict[str, Any]:
    """Update only policyholder/customer identity keys on a linked sibling draft."""
    if not cust:
        return fields
    f = dict(fields)
    if cust.canonical_name:
        _set_draft_field(f, "customer_name", cust.canonical_name)
        for alias in ("insured_name", "policyholder_name", "client_name"):
            if alias in f:
                _set_draft_field(f, alias, cust.canonical_name)
    if cust.id_number:
        _set_draft_field(f, "ic_or_brn", cust.id_number)
        for alias in ("customer_ic_no", "ic_no", "nric_no", "id_number"):
            if alias in f:
                _set_draft_field(f, alias, cust.id_number)
    return f


def _sync_vehicle_spec_draft_fields(
    fields: dict[str, Any],
    tv: TrackedVehicle | None,
    *,
    vehicle_type: str | None,
    powertrain: str | None,
    sync_plate: bool = True,
) -> dict[str, Any]:
    """Update only physical vehicle specifications on a draft (never dates/fees)."""
    f = dict(fields)
    if tv:
        if sync_plate and tv.vehicle_no:
            _set_draft_field(f, "vehicle_no", tv.vehicle_no)
        if tv.car_brand:
            _set_draft_field(f, "car_brand", tv.car_brand)
        if tv.car_model:
            _set_draft_field(f, "car_model", tv.car_model)
        if tv.engine_cc:
            _set_draft_field(f, "engine_cc", tv.engine_cc)
        if tv.chassis_no:
            _set_draft_field(f, "chassis_no", tv.chassis_no)
        if tv.engine_no:
            _set_draft_field(f, "engine_no", tv.engine_no)
        if tv.manufacture_year:
            _set_draft_field(f, "vehicle_year", str(tv.manufacture_year))
            if "manufacture_year" in f:
                _set_draft_field(f, "manufacture_year", str(tv.manufacture_year))
    if vehicle_type:
        _set_draft_field(f, "vehicle_type", vehicle_type)
    if powertrain:
        _set_draft_field(f, "powertrain", powertrain)
    return f


def _propagate_to_session_drafts(
    db: Session,
    tenure: InsuranceTenure,
    cust: CustomerAccount | None,
    tv: TrackedVehicle | None,
    *,
    vehicle_type: str | None,
    powertrain: str | None,
    dt_start: datetime | None,
    dt_end: datetime | None,
    eff_rt: Decimal,
    eff_rf: Decimal,
) -> None:
    """Propagate canonical changes with strict vehicle/tenure vs customer-only isolation."""
    session_conditions = [SessionModel.tenure_id == tenure.id]
    if tv is not None:
        session_conditions.append(SessionModel.tracked_vehicle_id == tv.id)
    if cust is not None:
        session_conditions.append(SessionModel.customer_id == cust.id)

    linked_sessions = list(
        db.scalars(
            select(SessionModel).where(
                or_(*session_conditions),
                or_(SessionModel.tenure_id == tenure.id, SessionModel.is_test.is_(False)),
            )
        ).all()
    )
    for s in linked_sessions:
        if getattr(s, "is_test", False) and s.tenure_id != tenure.id:
            continue

        same_tenure = s.tenure_id == tenure.id
        same_vehicle = tv is not None and s.tracked_vehicle_id == tv.id

        if same_tenure:
            if cust and s.customer_id != cust.id:
                s.customer_id = cust.id
            if tv and s.tracked_vehicle_id != tv.id:
                s.tracked_vehicle_id = tv.id
            if dt_start:
                s.coverage_start_date = dt_start
            if dt_end:
                s.coverage_end_date = dt_end
            if s.draft and isinstance(s.draft.fields, dict):
                s.draft.fields = _update_single_draft_fields(
                    s.draft.fields,
                    tenure=tenure,
                    cust=cust,
                    tv=tv,
                    vehicle_type=vehicle_type,
                    powertrain=powertrain,
                    dt_start=dt_start,
                    dt_end=dt_end,
                    eff_rt=eff_rt,
                    eff_rf=eff_rf,
                )
                flag_modified(s.draft, "fields")
            continue

        if not s.draft or not isinstance(s.draft.fields, dict):
            continue

        if same_vehicle:
            sib_tenure = db.get(InsuranceTenure, s.tenure_id) if s.tenure_id else None
            is_historical_or_closed = False
            if sib_tenure is not None:
                is_historical_or_closed = (
                    sib_tenure.stage == "Close - Win"
                    or bool(getattr(sib_tenure, "covernote_session_id", None))
                    or (
                        sib_tenure.coverage_start_date is not None
                        and tenure.coverage_start_date is not None
                        and sib_tenure.coverage_start_date.year < tenure.coverage_start_date.year
                    )
                )
            updated = _sync_customer_identity_draft_fields(s.draft.fields, cust)
            updated = _sync_vehicle_spec_draft_fields(
                updated,
                tv,
                vehicle_type=vehicle_type,
                powertrain=powertrain,
                sync_plate=not is_historical_or_closed,
            )
            s.draft.fields = updated
            flag_modified(s.draft, "fields")
        elif cust is not None and s.customer_id == cust.id:
            # Different vehicle/tenure owned by the same customer: sync ONLY customer identity
            s.draft.fields = _sync_customer_identity_draft_fields(s.draft.fields, cust)
            flag_modified(s.draft, "fields")


def _propagate_to_comparison_entries(
    db: Session,
    tenure: InsuranceTenure,
    eff_rt: Decimal,
    eff_rf: Decimal,
) -> None:
    """Propagate effective road tax and runner fee to all TenureComparisonEntry rows."""
    all_entries = list(
        db.scalars(
            select(TenureComparisonEntry).where(TenureComparisonEntry.tenure_id == tenure.id)
        ).all()
    )
    for ce in all_entries:
        prem_dec = _to_decimal(ce.motor_premium)
        ce.road_tax = float(eff_rt)
        ce.runner_fee = float(eff_rf)
        ce.include_road_tax = tenure.include_road_tax is not False
        ce.include_runner_fee = tenure.include_runner_fee is not False
        ce.total_payable = float(prem_dec + eff_rt + eff_rf)
        ce.version = (ce.version or 1) + 1

    from app.domain.motor.discount_calculator import calculate_motor_discount

    pct_val = getattr(tenure, "motor_discount_pct", Decimal("0.00")) or Decimal("0.00")
    flat_val = getattr(tenure, "quotation_discount", Decimal("0.00")) or Decimal("0.00")

    if getattr(tenure, "covernote_session_id", None):
        cn_sess = db.get(SessionModel, tenure.covernote_session_id)
        if cn_sess and cn_sess.draft and isinstance(cn_sess.draft.fields, dict):
            raw_prem = cn_sess.draft.fields.get("premium") or cn_sess.draft.fields.get("premium_due")
            val_prem = raw_prem.get("value") if isinstance(raw_prem, dict) else raw_prem
            if val_prem is not None and str(val_prem).strip():
                cn_prem_dec = _to_decimal(val_prem)
                if cn_prem_dec > Decimal("0.00"):
                    cn_bd = calculate_motor_discount(cn_prem_dec, pct_val, flat_val)
                    tenure.won_premium = float(cn_bd.net_total_payable(eff_rt, eff_rf))
    elif getattr(tenure, "winning_company_id", None) or any(getattr(ce, "is_recommended", False) for ce in all_entries):
        rec_ce = next((ce for ce in all_entries if getattr(ce, "is_recommended", False)), None)
        if rec_ce is not None:
            ce_flat = rec_ce.discount if rec_ce.discount is not None else flat_val
            ce_bd = calculate_motor_discount(rec_ce.motor_premium, pct_val, ce_flat)
            tenure.won_premium = float(ce_bd.net_total_payable(eff_rt, eff_rf))


def sync_tenure_identity_transaction(
    db: Session,
    tenure_id: str,
    *,
    customer_name: str | None = None,
    ic_or_brn: str | None = None,
    vehicle_no: str | None = None,
    car_brand: str | None = None,
    car_model: str | None = None,
    engine_cc: str | None = None,
    manufacture_year: int | None = None,
    vehicle_type: str | None = None,
    powertrain: str | None = None,
    chassis_no: str | None = None,
    engine_no: str | None = None,
    coverage_start_date: str | datetime | None = None,
    coverage_end_date: str | datetime | None = None,
    road_tax: float | Decimal | None = None,
    runner_fee: float | Decimal | None = None,
    include_road_tax: bool | None = None,
    include_runner_fee: bool | None = None,
    windscreen_target: float | Decimal | None = None,
    ncd_percentage: float | Decimal | None = None,
    current_ncd: float | Decimal | None = None,
    quotation_discount: float | Decimal | None = None,
    motor_discount_pct: float | Decimal | None = None,
) -> InsuranceTenure:
    """Synchronize tenure identity, vehicle specs, customer record, and fees across all linked entities atomically."""
    tenure = db.scalars(
        select(InsuranceTenure)
        .options(
            joinedload(InsuranceTenure.tracked_vehicle),
            joinedload(InsuranceTenure.customer),
            joinedload(InsuranceTenure.previous_tenure),
        )
        .where(InsuranceTenure.id == tenure_id)
    ).first()
    if not tenure:
        raise ValueError(f"Tenure {tenure_id} not found")

    _apply_tenure_fees_and_ncd(
        tenure,
        road_tax=road_tax,
        runner_fee=runner_fee,
        include_road_tax=include_road_tax,
        include_runner_fee=include_runner_fee,
        windscreen_target=windscreen_target,
        ncd_percentage=ncd_percentage,
        current_ncd=current_ncd,
        quotation_discount=quotation_discount,
        motor_discount_pct=motor_discount_pct,
    )
    cust = _sync_tenure_customer(db, tenure, customer_name, ic_or_brn)
    tv = _sync_tenure_vehicle(
        db,
        tenure,
        vehicle_no=vehicle_no,
        car_brand=car_brand,
        car_model=car_model,
        engine_cc=engine_cc,
        manufacture_year=manufacture_year,
        chassis_no=chassis_no,
        engine_no=engine_no,
        powertrain=powertrain,
    )

    dt_start = _parse_date(coverage_start_date)
    dt_end = _parse_date(coverage_end_date)
    if dt_start:
        tenure.coverage_start_date = dt_start
    if dt_end:
        tenure.coverage_end_date = dt_end
        tenure.expiry_month = dt_end.strftime("%Y-%m")

    eff_rt = _to_decimal(tenure.road_tax) if (tenure.include_road_tax is not False) else Decimal("0.00")
    eff_rf = _to_decimal(tenure.runner_fee) if (tenure.include_runner_fee is not False) else Decimal("0.00")

    _propagate_to_session_drafts(
        db,
        tenure,
        cust,
        tv,
        vehicle_type=vehicle_type,
        powertrain=powertrain,
        dt_start=dt_start,
        dt_end=dt_end,
        eff_rt=eff_rt,
        eff_rf=eff_rf,
    )
    _propagate_to_comparison_entries(db, tenure, eff_rt, eff_rf)
    return tenure
