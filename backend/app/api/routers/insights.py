"""Insights API router."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import current_user, settings_dep
from app.api.schemas import (
    BackfillConfirmRequest,
    BulkClientRecordDeleteRequest,
    BulkUploadedFileDeleteRequest,
    ClientRecordUpdateRequest,
    QuotationActivityCreateRequest,
    QuotationStatusUpdateRequest,
    RecordBulkActionRequest,
    RecordSavedViewRequest,
)
from app.core.config import Settings
from app.core.errors import AppError
from app.db.session import get_db
from app.models.tables import User
from app.services.realtime_hub import publish_realtime_update
from app.services.client_dossier_service import get_client_dossiers
from app.services.client_record_service import (
    delete_view as delete_record_view,
    export_csv_bytes,
    get_record,
    list_records_page,
    list_saved_views,
    records_matching_ids,
    save_view as save_record_view,
    serialize_record,
    serialize_saved_view,
    set_records_archived,
    update_record,
)
from app.services.quotation_activity_service import (
    backfill_existing_sessions,
    get_calendar_activities,
    get_insights_analytics,
    log_quotation_activity,
    preview_backfill_sessions,
    update_quotation_status,
)
from app.services.review_service import move_to_trash
from app.services.session_service import get_session
from app.services.vehicle_tracking_service import get_upcoming_renewals, get_vehicle_history

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/client-records")
def client_records_list(
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    company: str | None = None,
    state: str = "active",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    result = list_records_page(
        db, search=search, date_from=date_from, date_to=date_to, sort_by=sort_by,
        sort_dir=sort_dir, company=company, state=state, page=page, page_size=page_size,
    )
    return {
        "records": [serialize_record(item) for item in result["items"]],
        "page": result["page"], "page_size": result["page_size"], "total": result["total"],
        "companies": result["companies"],
    }


@router.get("/client-records/saved-views")
def client_record_saved_views(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    return {"views": [serialize_saved_view(item) for item in list_saved_views(db, user)]}


@router.post("/client-records/saved-views")
def client_record_saved_view_save(payload: RecordSavedViewRequest, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    return {"view": serialize_saved_view(save_record_view(db, user, payload.model_dump()))}


@router.delete("/client-records/saved-views/{view_id}")
def client_record_saved_view_delete(view_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    delete_record_view(db, user, view_id)
    return {"deleted": True}


@router.get("/client-records/export")
def client_records_export(
    search: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    from fastapi.responses import Response as FastAPIResponse
    csv_data = export_csv_bytes(db, search=search)
    return FastAPIResponse(csv_data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=client_records.csv"})


@router.get("/client-records/{record_id}")
def client_record_detail(record_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    return {"record": serialize_record(get_record(db, record_id))}


@router.patch("/client-records/{record_id}")
def client_record_update(record_id: str, payload: ClientRecordUpdateRequest, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    record = update_record(db, record_id, payload.model_dump(exclude_none=True))
    publish_realtime_update(scope="clients", resource_id=record_id, actor=user, summary="Client record updated", extra_scopes=("ledger",))
    return {"record": serialize_record(record)}


@router.delete("/client-records/{record_id}")
def client_record_delete(record_id: str, db: Session = Depends(get_db), settings: Settings = Depends(settings_dep), user: User = Depends(current_user)) -> dict:
    from app.services.trash_service import delete_client_record
    delete_client_record(db, settings, user, record_id)
    publish_realtime_update(scope="clients", resource_id=record_id, actor=user, summary="Client record deleted", extra_scopes=("ledger",))
    return {"deleted": True}


@router.post("/client-records/bulk-delete")
def client_records_bulk_delete(payload: BulkClientRecordDeleteRequest, db: Session = Depends(get_db), settings: Settings = Depends(settings_dep), user: User = Depends(current_user)) -> dict:
    from app.services.trash_service import delete_client_record
    deleted: list[str] = []
    failed: list[dict] = []
    for record_id in payload.record_ids:
        try:
            delete_client_record(db, settings, user, record_id)
            deleted.append(record_id)
        except AppError as exc:
            failed.append({"id": record_id, "message": str(exc)})
    if deleted:
        publish_realtime_update(scope="clients", resource_id="all", actor=user, summary="Client records deleted", extra_scopes=("ledger",))
    return {"deleted": deleted, "failed": failed}


@router.post("/client-records/bulk-action")
def client_records_bulk_action(payload: RecordBulkActionRequest, db: Session = Depends(get_db), settings: Settings = Depends(settings_dep), user: User = Depends(current_user)) -> dict:
    record_ids = records_matching_ids(db, payload.filters) if payload.all_matching else list(dict.fromkeys(payload.record_ids))
    if not record_ids:
        raise AppError("Choose at least one matching record.", 422)
    if payload.action in {"archive", "unarchive"}:
        changed = set_records_archived(db, user, record_ids, archived=payload.action == "archive")
        if changed:
            publish_realtime_update(scope="clients", resource_id="all", actor=user, summary="Client records updated", extra_scopes=("ledger",))
        return {"changed": changed, "failed": []}
    from app.services.trash_service import delete_client_record
    changed: list[str] = []
    failed: list[dict] = []
    for record_id in record_ids:
        try:
            delete_client_record(db, settings, user, record_id)
            changed.append(record_id)
        except AppError as exc:
            failed.append({"id": record_id, "message": str(exc)})
    if changed:
        publish_realtime_update(scope="clients", resource_id="all", actor=user, summary="Client records updated", extra_scopes=("ledger",))
    return {"changed": changed, "failed": failed}


@router.delete("/records/{uploaded_file_id}")
def delete_record(uploaded_file_id: str, db: Session = Depends(get_db), settings: Settings = Depends(settings_dep), user: User = Depends(current_user)) -> dict:
    move_to_trash(db, settings, user, uploaded_file_id)
    return {"status": "Deleted"}


@router.post("/records/bulk-delete")
def delete_records_bulk(payload: BulkUploadedFileDeleteRequest, db: Session = Depends(get_db), settings: Settings = Depends(settings_dep), user: User = Depends(current_user)) -> dict:
    deleted: list[str] = []
    failed: list[dict] = []
    for uploaded_file_id in payload.uploaded_file_ids:
        try:
            move_to_trash(db, settings, user, uploaded_file_id)
            deleted.append(uploaded_file_id)
        except AppError as exc:
            failed.append({"id": uploaded_file_id, "message": str(exc)})
    return {"deleted": deleted, "failed": failed}


@router.get("/insights/calendar")
def insights_calendar(
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    search: str | None = Query(None),
    status: str | None = Query(None),
    sent_only: bool = Query(False),
    vehicle_no: str | None = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return get_calendar_activities(
        db=db,
        date_from=date_from,
        date_to=date_to,
        search=search,
        status=status,
        sent_only=sent_only,
        vehicle_no=vehicle_no,
        limit=limit,
    )


@router.post("/insights/sessions/{session_id}/activity")
def create_session_activity(
    session_id: str,
    payload: QuotationActivityCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    session = get_session(db, session_id)
    if getattr(session, "is_test", False):
        return {
            "id": "test",
            "session_id": session.id,
            "action_type": payload.action_type,
            "sent_to_client": payload.sent_to_client,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    activity = log_quotation_activity(
        db=db,
        session_id=session.id,
        action_type=payload.action_type,
        user_id=user.id,
        sent_to_client=payload.sent_to_client,
        summary=payload.summary or "",
        addons_snapshot=payload.addons_snapshot,
        version_number=payload.version_number,
        status=payload.status or session.quotation_status or "pending",
        won_premium=payload.won_premium,
        miss_reason=payload.miss_reason,
        notes=payload.notes,
    )
    db.commit()
    if not activity:
        return {
            "id": "test",
            "session_id": session.id,
            "action_type": payload.action_type,
            "sent_to_client": payload.sent_to_client,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    return {
        "id": activity.id,
        "session_id": activity.session_id,
        "action_type": activity.action_type,
        "sent_to_client": activity.sent_to_client,
        "timestamp": activity.timestamp.isoformat() if activity.timestamp else None,
    }


@router.post("/insights/sessions/{session_id}/status")
def update_session_status(
    session_id: str,
    payload: QuotationStatusUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    get_session(db, session_id)
    result = update_quotation_status(
        db=db,
        session_id=session_id,
        status=payload.status,
        miss_reason=payload.miss_reason,
        won_premium=payload.won_premium,
        notes=payload.notes,
        user_id=user.id,
        coverage_start_date=payload.coverage_start_date,
        coverage_end_date=payload.coverage_end_date,
    )
    db.commit()
    return result


@router.get("/insights/analytics")
def insights_analytics(
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return get_insights_analytics(db=db, date_from=date_from, date_to=date_to)


@router.get("/insights/vehicles/{vehicle_no}/history")
def vehicle_history(
    vehicle_no: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return get_vehicle_history(db=db, vehicle_no=vehicle_no)


@router.get("/insights/renewals")
def upcoming_renewals(
    days_ahead: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    renewals = get_upcoming_renewals(db=db, days_ahead=days_ahead)
    return {"renewals": renewals, "total": len(renewals)}


@router.post("/insights/backfill")
def run_insights_backfill(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    res = backfill_existing_sessions(db)
    db.commit()
    return res


@router.get("/insights/backfill/preview")
def preview_insights_backfill(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return preview_backfill_sessions(db=db)


@router.post("/insights/backfill/confirm")
def confirm_insights_backfill(
    payload: BackfillConfirmRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    res = backfill_existing_sessions(
        db=db,
        session_ids=payload.session_ids if payload.session_ids else None,
        manual_overrides=payload.manual_overrides,
    )
    db.commit()
    return res


@router.get("/insights/clients")
def insights_clients(
    search: str | None = Query(None),
    status: str | None = Query(None),
    client_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return get_client_dossiers(
        db=db,
        search=search,
        status=status,
        client_type=client_type,
        page=page,
        page_size=page_size,
    )


@router.get("/insights/customers/{customer_id}")
def get_customer_detail(
    customer_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    from app.services.customer_account_service import get_customer_account
    from app.core.errors import AppError

    cust = get_customer_account(db, customer_id)
    if not cust:
        raise AppError("Customer not found.", 404)
    return {
        "customer": {
            "id": cust.id,
            "entity_type": cust.entity_type,
            "id_type": cust.id_type,
            "id_number": cust.id_number,
            "canonical_name": cust.canonical_name,
            "name_aliases": cust.name_aliases,
            "phone": cust.phone,
            "email": cust.email,
            "address": cust.address,
            "alternate_contacts": cust.alternate_contacts,
            "is_fleet": cust.is_fleet,
            "vehicles": [
                {
                    "id": v.id,
                    "vehicle_no": v.vehicle_no,
                    "brand": v.car_brand,
                    "model": v.car_model,
                    "chassis_no": v.chassis_no,
                    "engine_no": v.engine_no,
                }
                for v in (cust.vehicles or [])
            ],
            "tenures_count": len(cust.tenures or []),
            "sessions_count": len(cust.sessions or []),
        }
    }


class CustomerUpdateRequest(BaseModel):
    canonical_name: str | None = None
    id_number: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    notes: str | None = None


@router.patch("/insights/customers/{customer_id}")
def update_customer_endpoint(
    customer_id: str,
    payload: CustomerUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    """Update master customer account and propagate name/IC to all tenures and quotation drafts."""
    from app.services.customer_account_service import get_customer_account
    from app.services.identity_normalization_service import normalize_government_id
    from app.core.errors import AppError
    from app.models.tables import InsuranceTenure, Session as SessionModel
    from sqlalchemy import select, update

    cust = get_customer_account(db, customer_id)
    if not cust:
        raise AppError("Customer not found.", 404)

    if payload.canonical_name and payload.canonical_name.strip():
        cust.canonical_name = payload.canonical_name.strip()
    if payload.id_number and payload.id_number.strip():
        norm_id, norm_type = normalize_government_id(payload.id_number.strip())
        cust.id_number = norm_id or payload.id_number.strip()
        if norm_type:
            cust.id_type = norm_type
    if payload.phone is not None:
        cust.phone = payload.phone.strip() if payload.phone else None
    if payload.email is not None:
        cust.email = payload.email.strip().lower() if payload.email else None
    if payload.address is not None:
        cust.address = payload.address.strip() if payload.address else None
    if payload.notes is not None:
        cust.notes = payload.notes.strip() if payload.notes else None

    # Propagate canonical_name across all tenures
    db.execute(
        update(InsuranceTenure)
        .where(InsuranceTenure.customer_id == cust.id)
        .values(customer_name=cust.canonical_name)
    )

    # Propagate name and IC to all quotation drafts under this customer
    sessions_to_sync = list(
        db.scalars(
            select(SessionModel).where(SessionModel.customer_id == cust.id)
        ).all()
    )
    for s in sessions_to_sync:
        if s.draft and isinstance(s.draft.fields, dict):
            f = dict(s.draft.fields)
            if payload.canonical_name:
                for name_k in ["customer_name", "policyholder_name", "client_name"]:
                    if name_k in f:
                        if isinstance(f[name_k], dict):
                            f[name_k] = {**f[name_k], "value": cust.canonical_name}
                        else:
                            f[name_k] = cust.canonical_name
            if payload.id_number:
                for ic_k in ["customer_ic_no", "ic_no", "nric_no", "id_number"]:
                    if ic_k in f:
                        if isinstance(f[ic_k], dict):
                            f[ic_k] = {**f[ic_k], "value": cust.id_number}
                        else:
                            f[ic_k] = cust.id_number
            s.draft.fields = f

    db.commit()
    db.refresh(cust)
    publish_realtime_update(scope="clients", resource_id=cust.id, actor=user, summary="Customer updated", extra_scopes=("ledger", "sessions"))
    return {
        "success": True,
        "customer": {
            "id": cust.id,
            "canonical_name": cust.canonical_name,
            "id_number": cust.id_number,
            "phone": cust.phone,
            "email": cust.email,
            "address": cust.address,
            "notes": cust.notes,
        },
    }
