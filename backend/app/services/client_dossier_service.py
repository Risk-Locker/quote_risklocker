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


def _resolve_session_client_identity(fields: dict) -> tuple[str, bool, str | None]:
    """
    Resolve client name, whether it is a corporate entity, and business registration number.
    Returns:
        (client_name, is_company, brn)
    """
    cust_name = (fields.get("customer_name", {}).get("value") or "").strip()
    insured_name = (fields.get("insured_name", {}).get("value") or "").strip()
    client_type = (fields.get("client_type", {}).get("value") or "").strip()
    brn = (fields.get("ic_or_brn", {}).get("value") or "").strip()

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
            joinedload(SessionModel.tracked_vehicle).joinedload(TrackedVehicle.ownerships),
        )
        .order_by(SessionModel.created_at.desc())
    )

    all_sessions = list(db.scalars(stmt).unique().all())

    # Map sessions by resolved client name and track client metadata
    client_map: dict[str, list[SessionModel]] = defaultdict(list)
    client_meta: dict[str, dict[str, Any]] = {}

    for s in all_sessions:
        fields = s.draft.fields if s.draft and s.draft.fields else {}
        name, is_comp, brn = _resolve_session_client_identity(fields)
        client_map[name].append(s)
        if name not in client_meta:
            client_meta[name] = {"is_corporate": is_comp, "brn": brn}
        else:
            if is_comp:
                client_meta[name]["is_corporate"] = True
            if brn and not client_meta[name]["brn"]:
                client_meta[name]["brn"] = brn

    # Build dossiers
    dossiers: list[dict[str, Any]] = []
    total_vehicles_set: set[str] = set()
    total_won_premium = 0.0
    total_lost_premium = 0.0
    global_hits = 0
    global_misses = 0

    for name, sessions in client_map.items():
        is_comp = client_meta.get(name, {}).get("is_corporate", False)
        brn_val = client_meta.get(name, {}).get("brn")

        # Vehicles connected to this customer
        vehicle_dict: dict[str, dict[str, Any]] = {}
        quotes_list: list[dict[str, Any]] = []
        c_hits = 0
        c_misses = 0
        c_pending = 0
        c_won_pm = 0.0
        c_lost_pm = 0.0

        for s in sessions:
            fields = s.draft.fields if s.draft and s.draft.fields else {}
            raw_plate = fields.get("vehicle_no", {}).get("value")
            norm_plate = normalize_plate(raw_plate)
            model = fields.get("car_model", {}).get("value") or ""
            vtype = fields.get("vehicle_type", {}).get("value") or ""
            cat = _categorize_vehicle(vtype, model)
            company = s.detected_company or fields.get("insurance_company", {}).get("value") or "Unknown"
            q_no = fields.get("quotation_no", {}).get("value") or f"RL-{s.id[:8].upper()}"
            pm_val = fields.get("total_amount", {}).get("value") or ""
            pm_num = _parse_money(pm_val)
            st = (s.quotation_status or "pending").lower()

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
                        }

            quotes_list.append(
                {
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
            )

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
            "brn": brn_val,
            "connected_vehicles": list(vehicle_dict.values()),
            "fleet_breakdown": fleet_counts,
            "quotations": quotes_list,
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
