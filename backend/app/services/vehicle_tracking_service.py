"""Vehicle tracking and ownership sequencing service for Risklocker."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import Session as SessionModel, TrackedVehicle, VehicleOwnership, new_id


def normalize_plate(plate: str | None) -> str:
    """Normalize vehicle registration plate to standard uppercase with single space."""
    if not plate:
        return ""
    cleaned = re.sub(r"[-_.]+", " ", plate.strip().upper())
    cleaned = re.sub(r"[^A-Za-z0-9\s]", "", cleaned)
    cleaned = re.sub(r"([A-Z]+)(\d+)", r"\1 \2", cleaned)
    cleaned = re.sub(r"(\d+)([A-Z]+)", r"\1 \2", cleaned)
    parts = cleaned.split()
    return " ".join(parts)


def parse_date_safe(date_str: str | None) -> datetime | None:
    """Safely parse common date formats (DD-MM-YYYY, YYYY-MM-DD, DD/MM/YYYY)."""
    if not date_str:
        return None
    cleaned = date_str.strip()
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%d %b %Y", "%d %B %Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    # Try finding 4-digit year and components via regex
    m = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", cleaned)
    if m:
        try:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return datetime(y, mo, d)
        except Exception:
            pass
    return None


def is_valid_malaysian_plate(plate: str | None) -> bool:
    """Validate whether plate follows standard Malaysian vehicle registration format.
    Rejects OCR table headers, placeholder words, and currency leaks."""
    if not plate:
        return False
    norm = normalize_plate(plate)
    if not norm:
        return False
    upper = norm.upper()
    bad_keywords = (
        "RM", "TRAILER", "VEHICLE", "MAKE", "UNREGISTERED",
        "UNKNOWN", "CHASSIS", "ENGINE", "POLICY", "PREMIUM",
        "TOTAL", "INSURER", "YEAR", "MODEL", "COVER", "AMOUNT",
    )
    for kw in bad_keywords:
        if kw in upper.split() or upper.startswith(f"{kw} ") or upper in ("VEHICLEMAKE", "UNREGISTERED"):
            return False
    has_letter = bool(re.search(r"[A-Z]", upper))
    has_digit = bool(re.search(r"\d", upper))
    if not (has_letter and has_digit):
        return False
    clean_no_space = upper.replace(" ", "")
    if len(clean_no_space) < 3 or len(clean_no_space) > 10:
        return False
    return bool(re.match(r"^[A-Z]{1,3}\s*\d{1,4}\s*[A-Z]?$", norm)) or bool(re.match(r"^[A-Z]+\s*\d+$", norm))


def is_same_customer(name1: str | None, name2: str | None) -> bool:
    """Intelligent entity matching for Malaysian customer names.
    Strips honorifics, corporate legal suffixes, and punctuation."""
    if not name1 or not name2:
        return True

    def _clean_tokens(name: str) -> set[str]:
        n = re.sub(r"[\(\)\[\],.\-_/]", " ", name.upper())
        stop_words = {
            "MR", "MRS", "MS", "DR", "DATO", "DATUK", "SERI", "TAN", "SRI",
            "PUAN", "ENCIK", "CIK", "HAJI", "HAJAH",
            "SDN", "BHD", "ENTERPRISE", "TRADING", "CORP", "CORPORATION",
            "CO", "LTD", "LIMITED", "SERVICES", "HOLDINGS", "GROUP", "TRANSPORTATION",
        }
        return set(t for t in n.split() if t not in stop_words and len(t) > 1)

    t1 = _clean_tokens(name1)
    t2 = _clean_tokens(name2)
    if not t1 or not t2:
        a1 = re.sub(r"[^A-Za-z0-9]", "", name1.upper())
        a2 = re.sub(r"[^A-Za-z0-9]", "", name2.upper())
        return a1 == a2

    if t1 == t2:
        return True
    overlap = len(t1.intersection(t2))
    total = max(len(t1), len(t2))
    if total > 0 and (overlap / total) >= 0.75:
        return True
    return False


def _names_match(name1: str | None, name2: str | None) -> bool:
    """Backward compatibility alias for is_same_customer."""
    return is_same_customer(name1, name2)


def get_or_create_vehicle_tracking(
    db: Session,
    vehicle_no: str | None,
    customer_name: str | None,
    validity_date: str | None,
    session_id: str | None = None,
    brand: str | None = None,
    model: str | None = None,
    engine_cc: str | None = None,
) -> tuple[TrackedVehicle | None, dict[str, Any] | None]:
    """Retrieve or register a tracked vehicle, sequencing owner transfers based on validity date."""
    if not is_valid_malaysian_plate(vehicle_no):
        return None, None
    norm_plate = normalize_plate(vehicle_no)
    if not norm_plate:
        return None, None

    if session_id:
        sess = db.get(SessionModel, session_id)
        if sess and getattr(sess, "is_test", False):
            return None, None

    clean_customer = (customer_name or "").strip()
    veh = db.scalar(select(TrackedVehicle).where(TrackedVehicle.vehicle_no == norm_plate))

    if not veh:
        veh = TrackedVehicle(
            id=new_id(),
            vehicle_no=norm_plate,
            car_brand=brand,
            car_model=model,
            engine_cc=engine_cc,
        )
        db.add(veh)
        db.flush()

    if session_id:
        sess_obj = db.get(SessionModel, session_id)
        if sess_obj and sess_obj.tracked_vehicle_id != veh.id:
            sess_obj.tracked_vehicle_id = veh.id

    # Check active owner
    current_owner = db.scalar(
        select(VehicleOwnership)
        .where(VehicleOwnership.vehicle_id == veh.id, VehicleOwnership.is_current.is_(True))
        .order_by(VehicleOwnership.sequence_order.desc())
    )

    if not current_owner:
        new_ownership = VehicleOwnership(
            id=new_id(),
            vehicle_id=veh.id,
            customer_name=clean_customer or "Unknown Customer",
            valid_until=validity_date,
            is_current=True,
            sequence_order=1,
            source_session_id=session_id,
        )
        db.add(new_ownership)
        db.flush()
        return veh, None

    # Vehicle already exists: update vehicle metadata if missing
    if brand and not veh.car_brand:
        veh.car_brand = brand
    if model and not veh.car_model:
        veh.car_model = model
    if engine_cc and not veh.engine_cc:
        veh.engine_cc = engine_cc

    if not current_owner:
        new_ownership = VehicleOwnership(
            id=new_id(),
            vehicle_id=veh.id,
            customer_name=clean_customer or "Unknown Customer",
            valid_until=validity_date,
            is_current=True,
            sequence_order=1,
            source_session_id=session_id,
        )
        db.add(new_ownership)
        db.flush()
        return veh, None

    # Check if owner name is unchanged
    if not clean_customer or _names_match(current_owner.customer_name, clean_customer):
        new_dt = parse_date_safe(validity_date)
        curr_dt = parse_date_safe(current_owner.valid_until)
        if validity_date and (not current_owner.valid_until or (new_dt and curr_dt and new_dt > curr_dt)):
            current_owner.valid_until = validity_date
        return veh, None

    # Owner name has changed: compare validity dates
    new_dt = parse_date_safe(validity_date)
    curr_dt = parse_date_safe(current_owner.valid_until)

    # If new quotation date is newer or no prior date, reassign active owner
    if (new_dt and curr_dt and new_dt >= curr_dt) or (new_dt and not curr_dt) or (not curr_dt and not new_dt):
        current_owner.is_current = False
        new_seq = (current_owner.sequence_order or 1) + 1
        new_owner = VehicleOwnership(
            id=new_id(),
            vehicle_id=veh.id,
            customer_name=clean_customer,
            valid_until=validity_date,
            is_current=True,
            sequence_order=new_seq,
            source_session_id=session_id,
        )
        db.add(new_owner)
        db.flush()

        alert = {
            "owner_changed": True,
            "previous_owner": current_owner.customer_name,
            "new_owner": clean_customer,
            "vehicle_no": veh.vehicle_no,
            "sequence_order": new_seq,
            "message": f"Owner changed: Reassigning owner of vehicle {veh.vehicle_no} from {current_owner.customer_name} to {clean_customer}.",
        }
        return veh, alert

    # Older quotation uploaded retroactively: record as historical ownership
    historical_seq = max(1, (current_owner.sequence_order or 2) - 1)
    past_owner = VehicleOwnership(
        id=new_id(),
        vehicle_id=veh.id,
        customer_name=clean_customer,
        valid_until=validity_date,
        is_current=False,
        sequence_order=historical_seq,
        source_session_id=session_id,
    )
    db.add(past_owner)
    db.flush()
    return veh, None


def _sequence_label(seq: int) -> str:
    if seq == 1:
        return "1st Owner"
    elif seq == 2:
        return "2nd Owner"
    elif seq == 3:
        return "3rd Owner"
    return f"{seq}th Owner"


def get_vehicle_history(db: Session, vehicle_no: str) -> dict[str, Any]:
    """Retrieve full vehicle history with all past and current owners and linked sessions."""
    norm_plate = normalize_plate(vehicle_no)
    veh = db.scalar(select(TrackedVehicle).where(TrackedVehicle.vehicle_no == norm_plate))
    if not veh:
        return {"found": False, "vehicle": None, "ownerships": [], "sessions_count": 0}

    ownerships = list(
        db.scalars(
            select(VehicleOwnership)
            .where(VehicleOwnership.vehicle_id == veh.id)
            .order_by(VehicleOwnership.sequence_order.asc(), VehicleOwnership.created_at.asc())
        ).all()
    )

    sessions = list(
        db.scalars(
            select(SessionModel)
            .where(SessionModel.tracked_vehicle_id == veh.id)
            .order_by(SessionModel.created_at.desc())
        ).all()
    )

    return {
        "found": True,
        "vehicle": {
            "id": veh.id,
            "vehicle_no": veh.vehicle_no,
            "car_brand": veh.car_brand,
            "car_model": veh.car_model,
            "engine_cc": veh.engine_cc,
            "current_owner_name": veh.current_owner_name,
            "created_at": veh.created_at.isoformat() if veh.created_at else None,
        },
        "ownerships": [
            {
                "id": o.id,
                "customer_name": o.customer_name,
                "valid_until": o.valid_until,
                "coverage_start_date": o.coverage_start_date.isoformat() if o.coverage_start_date else None,
                "coverage_end_date": o.coverage_end_date.isoformat() if o.coverage_end_date else None,
                "renewal_alert_date": o.renewal_alert_date.isoformat() if o.renewal_alert_date else None,
                "policy_status": o.policy_status or "active",
                "is_current": o.is_current,
                "sequence_order": o.sequence_order,
                "sequence_label": _sequence_label(o.sequence_order),
                "source_session_id": o.source_session_id,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in ownerships
        ],
        "sessions_count": len(sessions),
    }


def assign_or_get_deal_cycle(
    db: Session,
    session: SessionModel | str,
    vehicle_no: str,
    created_at: datetime | None = None,
) -> str:
    """Cluster 3-5 competitor quotations for the same vehicle renewal within a 60-day window into one deal cycle."""
    sess = db.get(SessionModel, session) if isinstance(session, str) else session
    if not sess:
        return ""

    if sess.deal_cycle_id:
        return sess.deal_cycle_id

    norm_plate = normalize_plate(vehicle_no)
    if not norm_plate:
        cycle_id = f"DEAL-GEN-{new_id()[:8]}"
        sess.deal_cycle_id = cycle_id
        return cycle_id

    ref_time = created_at or sess.created_at or datetime.now(timezone.utc)
    from datetime import timedelta
    window_start = ref_time - timedelta(days=60)
    window_end = ref_time + timedelta(days=60)

    # Check for existing deal cycle in this window for same vehicle
    query = (
        select(SessionModel.deal_cycle_id)
        .join(TrackedVehicle, SessionModel.tracked_vehicle_id == TrackedVehicle.id)
        .where(
            TrackedVehicle.vehicle_no == norm_plate,
            SessionModel.id != sess.id,
            SessionModel.deal_cycle_id.is_not(None),
            SessionModel.status != "trash",
        )
    )
    if sess.created_at:
        query = query.where(
            SessionModel.created_at >= window_start,
            SessionModel.created_at <= window_end,
        )
    existing = db.scalar(query.limit(1))

    if existing:
        sess.deal_cycle_id = existing
        return existing

    clean_tag = norm_plate.replace(" ", "")
    year_tag = ref_time.strftime("%Y")
    new_cycle = f"DEAL-{clean_tag}-{year_tag}-{new_id()[:6]}"
    sess.deal_cycle_id = new_cycle
    return new_cycle


def get_upcoming_renewals(
    db: Session,
    days_ahead: int = 90,
) -> list[dict[str, Any]]:
    """Retrieve policies expiring within the next `days_ahead` days (default 90 days / 9-month follow-up window)."""
    now = datetime.now(timezone.utc)
    from datetime import timedelta
    cutoff = now + timedelta(days=days_ahead)
    past_buffer = now - timedelta(days=30)  # include recently expired within 30 days

    ownerships = list(
        db.scalars(
            select(VehicleOwnership)
            .join(TrackedVehicle, VehicleOwnership.vehicle_id == TrackedVehicle.id)
            .where(
                VehicleOwnership.is_current.is_(True),
                VehicleOwnership.coverage_end_date.is_not(None),
                VehicleOwnership.coverage_end_date >= past_buffer,
                VehicleOwnership.coverage_end_date <= cutoff,
            )
            .order_by(VehicleOwnership.coverage_end_date.asc())
        ).all()
    )

    results: list[dict[str, Any]] = []
    for o in ownerships:
        v = o.vehicle
        end_dt = o.coverage_end_date
        days_remaining = (end_dt.date() - now.date()).days if end_dt else 0

        # Find latest winning session for insurer info
        source_session = db.get(SessionModel, o.source_session_id) if o.source_session_id else None
        company = source_session.detected_company if source_session else "Insurer"

        results.append({
            "ownership_id": o.id,
            "vehicle_no": v.vehicle_no if v else "UNKNOWN",
            "car_brand": v.car_brand if v else None,
            "car_model": v.car_model if v else None,
            "customer_name": o.customer_name,
            "coverage_start_date": o.coverage_start_date.isoformat() if o.coverage_start_date else None,
            "coverage_end_date": end_dt.isoformat() if end_dt else None,
            "renewal_alert_date": o.renewal_alert_date.isoformat() if o.renewal_alert_date else None,
            "policy_status": o.policy_status or "active",
            "days_remaining": days_remaining,
            "is_expiring_soon": 0 <= days_remaining <= 90,
            "is_expired": days_remaining < 0,
            "insurer": company,
            "source_session_id": o.source_session_id,
        })

    return results


def check_vehicle_ownership_conflict(
    db: Session,
    session_id: str,
) -> dict[str, Any]:
    """Check if the vehicle in session has an ownership conflict with a prior customer from an earlier policy period."""
    session = db.get(SessionModel, session_id)
    if not session or not session.draft:
        return {"has_conflict": False, "reason": "Session or draft not found"}

    fields = session.draft.fields or {}

    # If already resolved by agent, return resolved status
    resolution = fields.get("_ownership_resolution")
    if resolution:
        return {
            "has_conflict": False,
            "resolved": True,
            "resolution": resolution,
        }

    # Extract vehicle plate
    v_val = fields.get("vehicle_no", {})
    raw_plate = v_val.get("value") if isinstance(v_val, dict) else v_val
    if not is_valid_malaysian_plate(raw_plate):
        return {"has_conflict": False, "reason": "No valid Malaysian plate"}

    norm_plate = normalize_plate(raw_plate)

    # Extract customer name from fields
    def _extract_val(key: str) -> str | None:
        item = fields.get(key)
        if isinstance(item, dict):
            return str(item.get("value") or "").strip() or None
        return str(item or "").strip() or None

    new_customer = _extract_val("client_name") or _extract_val("insured_name") or _extract_val("customer_name")
    if not new_customer:
        return {"has_conflict": False, "reason": "No customer name extracted"}

    # Extract policy validity start date (period inception, NOT upload date)
    policy_date_str = (
        _extract_val("period_of_insurance_from")
        or _extract_val("period_from")
        or _extract_val("effective_date")
        or _extract_val("inception_date")
        or _extract_val("validity_date")
    )

    # Find existing tracked vehicle
    veh = db.scalar(select(TrackedVehicle).where(TrackedVehicle.vehicle_no == norm_plate))
    if not veh or not veh.current_owner_name:
        return {"has_conflict": False, "reason": "Vehicle has no prior recorded owner"}

    prev_owner_name = veh.current_owner_name
    if is_same_customer(prev_owner_name, new_customer):
        return {"has_conflict": False, "reason": "Same customer"}

    # Conflict confirmed: Different customer name for the same vehicle
    prev_own = veh.current_owner
    prev_session = db.get(SessionModel, prev_own.source_session_id) if prev_own and prev_own.source_session_id else None
    prev_policy_date = (
        prev_own.valid_until
        or prev_own.valid_from
        or (prev_session.created_at.strftime("%d %b %Y") if prev_session and prev_session.created_at else "Earlier Record")
    ) if prev_own else "Earlier Record"

    return {
        "has_conflict": True,
        "resolved": False,
        "vehicle_no": veh.vehicle_no,
        "car_brand": veh.car_brand,
        "car_model": veh.car_model,
        "engine_cc": veh.engine_cc,
        "previous_owner": prev_owner_name,
        "previous_policy_date": prev_policy_date,
        "previous_session_id": prev_session.id if prev_session else None,
        "previous_session_ref": prev_session.quotation_ref if prev_session else None,
        "new_customer": new_customer,
        "new_policy_date": policy_date_str or "Current Quotation",
        "new_session_id": session.id,
        "new_session_ref": session.quotation_ref or f"RL-{session.id[:8].upper()}",
    }


def resolve_vehicle_ownership(
    db: Session,
    session_id: str,
    resolution_type: str,
    user_id: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Execute the user's selected resolution for a vehicle ownership conflict."""
    from sqlalchemy.orm.attributes import flag_modified
    from app.services.quotation_activity_service import log_quotation_activity

    session = db.get(SessionModel, session_id)
    if not session or not session.draft:
        raise ValueError(f"Session {session_id} or draft not found")

    fields = dict(session.draft.fields or {})
    v_val = fields.get("vehicle_no", {})
    raw_plate = v_val.get("value") if isinstance(v_val, dict) else v_val
    norm_plate = normalize_plate(raw_plate)

    def _extract_val(key: str) -> str | None:
        item = fields.get(key)
        if isinstance(item, dict):
            return str(item.get("value") or "").strip() or None
        return str(item or "").strip() or None

    new_customer = _extract_val("client_name") or _extract_val("insured_name") or _extract_val("customer_name") or "Unknown Customer"
    policy_date = (
        _extract_val("period_of_insurance_from")
        or _extract_val("period_from")
        or _extract_val("effective_date")
        or _extract_val("validity_date")
    )

    veh = db.scalar(select(TrackedVehicle).where(TrackedVehicle.vehicle_no == norm_plate)) if norm_plate else None

    resolution_data = {
        "type": resolution_type,
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "resolved_by_user_id": user_id,
        "notes": notes,
        "new_customer": new_customer,
        "vehicle_no": norm_plate,
    }

    if resolution_type == "car_sold_new_owner":
        # Option 1: Car Sold / Ownership Transfer
        if veh:
            # Deactivate previous ownership records
            for o in veh.ownerships:
                o.is_current = False
            # Add new ownership record for the new customer
            new_own = VehicleOwnership(
                id=new_id(),
                vehicle_id=veh.id,
                customer_name=new_customer,
                valid_from=policy_date,
                is_current=True,
                sequence_order=len(veh.ownerships) + 1,
                source_session_id=session.id,
            )
            db.add(new_own)
            session.tracked_vehicle_id = veh.id

        log_quotation_activity(
            db=db,
            session_id=session.id,
            action_type="ownership_transfer_confirmed",
            user_id=user_id,
            summary=f"Ownership Transfer: Vehicle {norm_plate} reassigned to new owner {new_customer}.",
            notes=notes,
        )

    elif resolution_type == "old_quote_mistake":
        # Option 2: Data Correction / Old Quote Was Mistake
        if veh:
            # Deactivate old mistaken ownerships
            for o in veh.ownerships:
                o.is_current = False
            # Add or update new ownership as the sole active owner
            new_own = VehicleOwnership(
                id=new_id(),
                vehicle_id=veh.id,
                customer_name=new_customer,
                valid_from=policy_date,
                is_current=True,
                sequence_order=1,
                source_session_id=session.id,
            )
            db.add(new_own)
            session.tracked_vehicle_id = veh.id

        log_quotation_activity(
            db=db,
            session_id=session.id,
            action_type="ownership_mistake_corrected",
            user_id=user_id,
            summary=f"Ownership Corrected: {new_customer} confirmed as sole owner of {norm_plate}; detached old record.",
            notes=notes,
        )

    elif resolution_type == "pending_verification":
        # Option 3: Keep on Pending / Unverified
        if veh:
            session.tracked_vehicle_id = veh.id

        log_quotation_activity(
            db=db,
            session_id=session.id,
            action_type="ownership_pending_verification",
            user_id=user_id,
            summary=f"Vehicle ownership for {norm_plate} kept pending verification under {new_customer}.",
            notes=notes,
        )

    else:
        raise ValueError(f"Invalid resolution_type: {resolution_type}")

    # Store resolution in draft fields so gate stays resolved
    fields["_ownership_resolution"] = resolution_data
    session.draft.fields = fields
    flag_modified(session.draft, "fields")
    db.commit()

    return {
        "success": True,
        "session_id": session.id,
        "resolution": resolution_data,
    }


