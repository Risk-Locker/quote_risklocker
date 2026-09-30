"""Connected Client Dossier service for Insights & Analytics."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.extraction.entity_classifier import is_business_registration, is_corporate_name
from app.models.tables import Session as SessionModel, TrackedVehicle, VehicleOwnership
from app.services.vehicle_tracking_service import is_same_customer, is_valid_malaysian_plate, normalize_plate


def _parse_money(val: Any) -> float:
    if not val:
        return 0.0
    try:
        cleaned = str(val).replace("RM", "").replace(",", "").strip()
        return float(Decimal(cleaned))
    except Exception:
        return 0.0


def _safe_field_val(fields: Any, key: str) -> str:
    if not isinstance(fields, dict):
        return ""
    val = fields.get(key)
    if isinstance(val, dict):
        return str(val.get("value") or "").strip()
    if val is not None:
        return str(val).strip()
    return ""


def _resolve_session_client_identity(fields: dict) -> tuple[str, bool, str | None]:
    """
    Resolve client name, whether it is a corporate entity, and business registration number.
    Returns:
        (client_name, is_company, brn)
    """
    cust_name = _safe_field_val(fields, "customer_name")
    insured_name = _safe_field_val(fields, "insured_name")
    client_type = _safe_field_val(fields, "client_type")
    brn = _safe_field_val(fields, "ic_or_brn")

    is_comp = (
        client_type.lower() == "company"
        or is_corporate_name(cust_name)
        or is_corporate_name(insured_name)
        or is_business_registration(brn)
    )

    if is_comp:
        if is_corporate_name(insured_name):
            return insured_name, True, brn or None
        if is_corporate_name(cust_name):
            return cust_name, True, brn or None
        target_name = cust_name or insured_name
        if target_name:
            return target_name, True, brn or None
        if brn:
            return f"Company ({brn})", True, brn
        return "Unspecified Company", True, None

    final_name = cust_name or insured_name or "Unspecified Client"
    return final_name, False, brn or None


def _categorize_vehicle(vtype: str | None, model: str | None) -> str:
    """Categorize vehicle into one of: 'lorry', 'motorcycle', 'suv', 'sedan', 'ev'."""
    vt = (vtype or "").lower()
    mod = (model or "").lower()
    if "ev" in vt or "electric" in mod:
        return "ev"
    if "lorry" in vt or "truck" in vt or "commercial" in vt or any(w in mod for w in ("hino", "fuso", "canter", "isuzu", "rigid", "trailer", "tipper")):
        return "lorry"
    if "motor" in vt or "bike" in vt or "motosikal" in mod:
        return "motorcycle"
    if "nonsaloon" in vt or "non-saloon" in vt or "suv" in vt or "mpv" in vt or "4x4" in vt or "pickup" in vt:
        return "suv"
    return "sedan"


def get_client_dossiers(
    db: Session,
    search: str | None = None,
    status: str | None = None,
    client_type: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """Compile rich connected customer dossiers linking vehicles, sequential ownerships, quotation sessions, and conversion stats."""
    stmt = (
        select(SessionModel)
        .where(SessionModel.is_test.is_(False))
        .options(
            joinedload(SessionModel.draft),
            joinedload(SessionModel.tenure),
            joinedload(SessionModel.customer),
            joinedload(SessionModel.tracked_vehicle).joinedload(TrackedVehicle.ownerships),
        )
        .order_by(SessionModel.created_at.desc())
    )

    all_sessions = list(db.scalars(stmt).unique().all())

    from app.services.identity_normalization_service import (
        normalize_canonical_name,
        normalize_government_id,
    )

    # Map sessions by resolved customer account or canonical identity
    client_map: dict[str, list[SessionModel]] = defaultdict(list)
    client_meta: dict[str, dict[str, Any]] = {}

    for s in all_sessions:
        fields = s.draft.fields if s.draft and s.draft.fields else {}
        name, is_comp, brn = _resolve_session_client_identity(fields)

        # Primary grouping by linked CustomerAccount if available
        if s.customer:
            key = s.customer.id
            display_name = s.customer.canonical_name
            is_comp = s.customer.entity_type == "corporate" or s.customer.is_fleet
            brn = s.customer.id_number if s.customer.id_type in ("brn_new", "brn_old", "llp") else (brn or s.customer.id_number)
            account_obj = s.customer
        else:
            norm_id, id_type = normalize_government_id(brn)
            norm_name = normalize_canonical_name(name)
            if norm_id:
                key = f"ID:{norm_id}"
            else:
                key = f"NAME:{norm_name}"
            display_name = name or norm_name or "Valued Client"
            account_obj = None

        client_map[key].append(s)
        if key not in client_meta:
            client_meta[key] = {
                "display_name": display_name,
                "is_corporate": is_comp,
                "brn": brn,
                "customer_account": account_obj,
            }
        else:
            if is_comp:
                client_meta[key]["is_corporate"] = True
            if brn and not client_meta[key]["brn"]:
                client_meta[key]["brn"] = brn
            if account_obj and not client_meta[key]["customer_account"]:
                client_meta[key]["customer_account"] = account_obj

    # Build dossiers
    dossiers: list[dict[str, Any]] = []
    total_vehicles_set: set[str] = set()
    total_won_premium = 0.0
    total_lost_premium = 0.0
    global_hits = 0
    global_misses = 0

    for key, sessions in client_map.items():
        meta = client_meta.get(key, {})
        name = meta.get("display_name", "Valued Client")
        is_comp = meta.get("is_corporate", False)
        brn_val = meta.get("brn")
        cust_acc = meta.get("customer_account")

        # Client profile details
        client_phone = cust_acc.phone if cust_acc and cust_acc.phone else ""
        client_email = cust_acc.email if cust_acc and cust_acc.email else ""
        client_address = cust_acc.address if cust_acc and cust_acc.address else ""
        client_ic = cust_acc.id_number if cust_acc and cust_acc.id_number else ""

        # Vehicles connected to this customer
        vehicle_dict: dict[str, dict[str, Any]] = {}
        quotes_list: list[dict[str, Any]] = []
        tenure_groups: dict[str, dict[str, Any]] = {}
        c_hits = 0
        c_misses = 0
        c_pending = 0
        c_won_pm = 0.0
        c_lost_pm = 0.0

        for s in sessions:
            fields = s.draft.fields if s.draft and isinstance(s.draft.fields, dict) else {}
            if not client_phone:
                client_phone = _safe_field_val(fields, "phone_number") or _safe_field_val(fields, "phone") or _safe_field_val(fields, "contact_number") or _safe_field_val(fields, "mobile_number")
            if not client_email:
                client_email = _safe_field_val(fields, "email") or _safe_field_val(fields, "email_address")
            if not client_address:
                client_address = _safe_field_val(fields, "address") or _safe_field_val(fields, "insured_address") or _safe_field_val(fields, "location")
            if not client_ic:
                client_ic = _safe_field_val(fields, "ic_no") or _safe_field_val(fields, "customer_ic") or _safe_field_val(fields, "ic_number") or _safe_field_val(fields, "ic_or_brn")

            raw_plate = _safe_field_val(fields, "vehicle_no") or _safe_field_val(fields, "vehicle_number")
            norm_plate = normalize_plate(raw_plate)
            model = _safe_field_val(fields, "car_model")
            vtype = _safe_field_val(fields, "vehicle_type")
            cat = _categorize_vehicle(vtype, model)
            company = s.detected_company or _safe_field_val(fields, "insurance_company") or "Unknown"
            q_no = _safe_field_val(fields, "quotation_no") or f"RL-{s.id[:8].upper()}"
            pm_val = _safe_field_val(fields, "total_amount")
            pm_num = _parse_money(pm_val)
            st = (s.quotation_status or "pending").lower()

            eng_cc = _safe_field_val(fields, "engine_cc") or _safe_field_val(fields, "cubic_capacity")
            eng_no = _safe_field_val(fields, "engine_no") or _safe_field_val(fields, "engine_number")
            chassis = _safe_field_val(fields, "chassis_no") or _safe_field_val(fields, "chassis_number") or _safe_field_val(fields, "vin")
            yom = _safe_field_val(fields, "year_of_manufacture") or _safe_field_val(fields, "make_year") or _safe_field_val(fields, "yom")
            seating = _safe_field_val(fields, "seating_capacity") or _safe_field_val(fields, "seating")

            if st == "hit":
                c_hits += 1
                c_won_pm += pm_num
                global_hits += 1
                total_won_premium += pm_num
            elif st == "miss":
                c_misses += 1
                c_lost_pm += pm_num
                global_misses += 1
                total_lost_premium += pm_num
            else:
                c_pending += 1

            if norm_plate and is_valid_malaysian_plate(norm_plate):
                # Check if this customer is the active owner of this vehicle (companies co-own all fleet vehicles)
                is_active_owner = True
                is_pending = False
                if not is_comp and s.tracked_vehicle and s.tracked_vehicle.current_owner_name:
                    is_active_owner = is_same_customer(s.tracked_vehicle.current_owner_name, name)

                # Check if session has pending resolution
                resolution = fields.get("_ownership_resolution")
                if isinstance(resolution, dict) and resolution.get("type") == "pending_verification":
                    is_pending = True

                if is_active_owner or is_pending or is_comp:
                    total_vehicles_set.add(norm_plate)
                    if norm_plate not in vehicle_dict:
                        vehicle_dict[norm_plate] = {
                            "vehicle_no": norm_plate,
                            "model": model,
                            "vehicle_type": vtype,
                            "category": cat,
                            "is_current": is_active_owner or is_comp,
                            "is_pending_verification": is_pending,
                            "engine_cc": eng_cc,
                            "engine_no": eng_no,
                            "chassis_no": chassis,
                            "year_of_manufacture": yom,
                            "seating_capacity": seating,
                        }
                    else:
                        v = vehicle_dict[norm_plate]
                        if not v.get("engine_cc") and eng_cc: v["engine_cc"] = eng_cc
                        if not v.get("engine_no") and eng_no: v["engine_no"] = eng_no
                        if not v.get("chassis_no") and chassis: v["chassis_no"] = chassis
                        if not v.get("year_of_manufacture") and yom: v["year_of_manufacture"] = yom
                        if not v.get("seating_capacity") and seating: v["seating_capacity"] = seating

            q_item = {
                "session_id": s.id,
                "quotation_number": q_no,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "company": company,
                "vehicle_no": norm_plate or "—",
                "car_model": model,
                "vehicle_type": vtype,
                "category": cat,
                "gross_premium": pm_val,
                "status": st,
                "miss_reason": s.miss_reason,
                "closed_at": s.closed_at.isoformat() if s.closed_at else None,
                "pdf_download_url": f"/api/sessions/{s.id}/pdf?download=true",
            }
            quotes_list.append(q_item)

            # Group into tenure
            tenure_obj = s.tenure
            cov_start_str = _safe_field_val(fields, "coverage_start_date") or _safe_field_val(fields, "start_date")
            cov_end_str = _safe_field_val(fields, "coverage_end_date") or _safe_field_val(fields, "end_date") or _safe_field_val(fields, "expiry_date")

            if tenure_obj:
                t_key = tenure_obj.id
                t_start = tenure_obj.coverage_start_date.strftime("%Y-%m-%d") if tenure_obj.coverage_start_date else cov_start_str
                t_end = tenure_obj.coverage_end_date.strftime("%Y-%m-%d") if tenure_obj.coverage_end_date else cov_end_str
                t_status = tenure_obj.status or "draft"
                t_v_no = tenure_obj.vehicle_no or norm_plate
                t_exp_month = tenure_obj.expiry_month or (t_end[:7] if t_end else "—")
            else:
                t_key = f"{norm_plate}_{cov_start_str}_{cov_end_str}" if (cov_start_str or cov_end_str) else f"{norm_plate}_{s.created_at.year if s.created_at else 'default'}"
                t_start = cov_start_str
                t_end = cov_end_str
                t_status = st
                t_v_no = norm_plate or "—"
                t_exp_month = t_end[:7] if t_end and len(t_end) >= 7 else "—"

            if t_key not in tenure_groups:
                display_period = "—"
                if t_start and t_end:
                    display_period = f"{t_start} – {t_end}"
                elif t_end:
                    display_period = f"Expiring {t_end}"

                tenure_groups[t_key] = {
                    "tenure_id": tenure_obj.id if tenure_obj else None,
                    "vehicle_no": t_v_no,
                    "car_model": model,
                    "coverage_start_date": t_start,
                    "coverage_end_date": t_end,
                    "coverage_period": display_period,
                    "expiry_month": t_exp_month,
                    "status": t_status,
                    "raw_quotes": [],
                }
            tenure_groups[t_key]["raw_quotes"].append(q_item)

        # Process tenures and deduplicate to max 7 insurers per tenure
        processed_tenures = []
        for tg in tenure_groups.values():
            insurer_map: dict[str, dict[str, Any]] = {}
            for q in tg["raw_quotes"]:
                c_name = q["company"].strip().title()
                if any(x in c_name.lower() for x in ("amassurance", "am general", "kurnia")):
                    comp_key = "AmAssurance"
                elif any(x in c_name.lower() for x in ("berjaya", "sompo")):
                    comp_key = "Berjaya Sompo"
                elif "etiqa" in c_name.lower():
                    comp_key = "Etiqa"
                elif "lonpac" in c_name.lower():
                    comp_key = "Lonpac"
                elif "qbe" in c_name.lower():
                    comp_key = "QBE"
                elif any(x in c_name.lower() for x in ("stmb", "takaful malaysia")):
                    comp_key = "STMB"
                elif "tune" in c_name.lower():
                    comp_key = "Tune Protect"
                else:
                    comp_key = q["company"]

                existing = insurer_map.get(comp_key)
                if not existing or (q.get("created_at") or "") > (existing.get("created_at") or ""):
                    insurer_map[comp_key] = q

            preferred_order = ["AmAssurance", "Berjaya Sompo", "Etiqa", "Lonpac", "QBE", "STMB", "Tune Protect"]
            ordered_quotes = []
            for pref in preferred_order:
                if pref in insurer_map:
                    ordered_quotes.append(insurer_map.pop(pref))
            for rem_q in insurer_map.values():
                ordered_quotes.append(rem_q)

            deduped_quotes = ordered_quotes[:7]

            processed_tenures.append({
                "tenure_id": tg["tenure_id"],
                "vehicle_no": tg["vehicle_no"],
                "car_model": tg["car_model"],
                "coverage_start_date": tg["coverage_start_date"],
                "coverage_end_date": tg["coverage_end_date"],
                "coverage_period": tg["coverage_period"],
                "expiry_month": tg["expiry_month"],
                "status": tg["status"],
                "quotes": deduped_quotes,
            })

        processed_tenures.sort(key=lambda t: t.get("coverage_end_date") or "", reverse=True)

        c_closed = c_hits + c_misses
        c_hit_rate = round((c_hits / c_closed * 100), 1) if c_closed > 0 else 0.0

        fleet_counts = {
            "total_vehicles": len(vehicle_dict),
            "lorries": sum(1 for v in vehicle_dict.values() if v.get("category") == "lorry"),
            "motorcycles": sum(1 for v in vehicle_dict.values() if v.get("category") == "motorcycle"),
            "suvs": sum(1 for v in vehicle_dict.values() if v.get("category") == "suv"),
            "sedans": sum(1 for v in vehicle_dict.values() if v.get("category") == "sedan"),
            "evs": sum(1 for v in vehicle_dict.values() if v.get("category") == "ev"),
        }

        dossier = {
            "customer_name": name,
            "client_type": "Company" if is_comp else "Individual",
            "is_corporate": is_comp,
            "brn": brn_val or client_ic or None,
            "profile": {
                "ic_or_brn": brn_val or client_ic or None,
                "phone": client_phone or None,
                "email": client_email or None,
                "address": client_address or None,
            },
            "connected_vehicles": list(vehicle_dict.values()),
            "fleet_breakdown": fleet_counts,
            "quotations": quotes_list,
            "tenures": processed_tenures,
            "stats": {
                "total_quotations": len(quotes_list),
                "total_vehicles": len(vehicle_dict),
                "hits": c_hits,
                "misses": c_misses,
                "pending": c_pending,
                "hit_rate_percent": c_hit_rate,
                "won_premium_total": round(c_won_pm, 2),
                "lost_premium_total": round(c_lost_pm, 2),
            },
        }

        # Filter check: search term
        matches_search = True
        if search:
            sterm = search.strip().lower()
            name_match = sterm in name.lower()
            brn_match = bool(brn_val and sterm in brn_val.lower())
            veh_match = any(sterm in v["vehicle_no"].lower() or sterm in v["model"].lower() for v in vehicle_dict.values())
            comp_match = any(sterm in q["company"].lower() or sterm in q["quotation_number"].lower() for q in quotes_list)
            matches_search = name_match or brn_match or veh_match or comp_match

        # Filter check: quotation status
        matches_status = True
        if status and status.lower() != "all":
            req_st = status.lower()
            if req_st == "hit":
                matches_status = c_hits > 0
            elif req_st == "miss":
                matches_status = c_misses > 0
            elif req_st == "pending":
                matches_status = c_pending > 0

        # Filter check: client type (all | company | individual)
        matches_client_type = True
        if client_type and client_type.lower() != "all":
            if client_type.lower() in ("company", "corporate"):
                matches_client_type = is_comp
            elif client_type.lower() in ("individual", "private"):
                matches_client_type = not is_comp

        if matches_search and matches_status and matches_client_type:
            dossiers.append(dossier)

    # Sort by total quotations or most recent quotation
    dossiers.sort(key=lambda d: d["stats"]["total_quotations"], reverse=True)

    # Global KPI stats
    total_clients_count = len(dossiers)
    global_closed = global_hits + global_misses
    global_hit_rate = round((global_hits / global_closed * 100), 1) if global_closed > 0 else 0.0

    # Pagination
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    total_pages = (total_clients_count + page_size - 1) // page_size
    start_idx = (page - 1) * page_size
    paginated_dossiers = dossiers[start_idx : start_idx + page_size]

    return {
        "clients": paginated_dossiers,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_clients": total_clients_count,
            "total_pages": total_pages,
        },
        "summary": {
            "total_unique_clients": len(client_map),
            "total_corporate_clients": sum(1 for m in client_meta.values() if m["is_corporate"]),
            "total_individual_clients": sum(1 for m in client_meta.values() if not m["is_corporate"]),
            "total_connected_vehicles": len(total_vehicles_set),
            "total_quotations": len(all_sessions),
            "global_hit_rate_percent": global_hit_rate,
            "total_won_premium": round(total_won_premium, 2),
            "total_lost_premium": round(total_lost_premium, 2),
        },
    }
