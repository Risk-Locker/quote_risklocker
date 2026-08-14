"""Client record CRUD for CRM dashboard."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.tables import AuditEvent, ClientRecord, RecordSavedView, new_id


SORT_COLUMNS = {
    "insurer_no": ClientRecord.insurer_no,
    "customer_name": ClientRecord.customer_name,
    "vehicle_no": ClientRecord.vehicle_no,
    "insurance_company": ClientRecord.insurance_company,
    "created_at": ClientRecord.created_at,
    "generated_at": ClientRecord.generated_at,
}


def _field(draft_fields: dict, key: str) -> str | None:
    f = draft_fields.get(key, {})
    if isinstance(f, dict):
        val = f.get("value")
        return str(val).strip() if val is not None else None
    return None


def _insurer_no(db: Session, company: str, vehicle: str) -> str:
    prefix = (company or "RL").strip().upper().replace(" ", "_")[:20]
    plate = (vehicle or "NOVIN").strip().upper().replace(" ", "").replace("/", "")[:20]
    base = f"{prefix}_{plate}"
    if not db.scalar(select(func.count()).select_from(ClientRecord).where(ClientRecord.insurer_no == base)):
        return base
    seq = 2
    while True:
        candidate = f"{base}-{seq}"
        if not db.scalar(select(func.count()).select_from(ClientRecord).where(ClientRecord.insurer_no == candidate)):
            return candidate
        seq += 1


BASIC_FIELDS = [
    "insurance_company", "vehicle_no", "customer_name", "coverage_type", "cover_period",
    "car_model", "ncd_percent", "ncd", "coverage_amount", "premium", "roadtax", "service_fee",
    "total_premium", "issue_date", "valid_until", "vehicle_year", "capacity", "engine_no",
    "chassis_no", "market_value", "agreed_value", "excess_amount", "basic_premium", "ncd_amount",
    "service_tax", "stamp_duty", "gross_premium", "optional_covers", "notes",
]


def upsert_from_draft(
    db: Session,
    draft_fields: dict,
    session_id: str | None = None,
    draft_id: str | None = None,
    uploaded_file_id: str | None = None,
) -> ClientRecord:
    company = _field(draft_fields, "insurance_company") or ""
    vehicle = _field(draft_fields, "vehicle_no") or ""
    insurer_no = _insurer_no(db, company, vehicle)

    existing = db.scalar(select(ClientRecord).where(ClientRecord.draft_id == draft_id)) if draft_id else None
    if existing:
        for field_name in BASIC_FIELDS:
            val = _field(draft_fields, field_name)
            if val is not None:
                setattr(existing, field_name, val)
        existing.raw_values = draft_fields
        existing.generated_at = datetime.now(timezone.utc)
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        return existing

    record = ClientRecord(
        insurer_no=insurer_no,
        session_id=session_id,
        draft_id=draft_id,
        uploaded_file_id=uploaded_file_id,
        raw_values=draft_fields,
        generated_at=datetime.now(timezone.utc),
    )
    for field_name in BASIC_FIELDS:
        val = _field(draft_fields, field_name)
        if val is not None:
            setattr(record, field_name, val)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _records_query(
    db: Session,
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    company: str | None = None,
    state: str = "active",
):
    q = select(ClientRecord).where(ClientRecord.deleted_at.is_(None))
    if search:
        term = f"%{search}%"
        q = q.where(
            or_(
                ClientRecord.insurer_no.ilike(term),
                ClientRecord.customer_name.ilike(term),
                ClientRecord.vehicle_no.ilike(term),
                ClientRecord.insurance_company.ilike(term),
                ClientRecord.notes.ilike(term),
            )
        )
    if date_from:
        q = q.where(ClientRecord.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        q = q.where(ClientRecord.created_at <= datetime.fromisoformat(date_to))
    if company:
        q = q.where(ClientRecord.insurance_company == company)
    if state == "active":
        q = q.where(ClientRecord.archived_at.is_(None))
    elif state == "archived":
        q = q.where(ClientRecord.archived_at.is_not(None))
    elif state != "all":
        raise AppError("Record state filter is invalid.", 422)
    col = SORT_COLUMNS.get(sort_by, ClientRecord.created_at)
    return q.order_by(col.desc() if sort_dir == "desc" else col.asc(), ClientRecord.id.asc())


def list_records(
    db: Session,
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    company: str | None = None,
    state: str = "active",
    page: int = 1,
    page_size: int = 50,
) -> list[ClientRecord]:
    page = max(1, int(page))
    page_size = min(100, max(1, int(page_size)))
    query = _records_query(db, search, date_from, date_to, sort_by, sort_dir, company, state)
    return list(db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all())


def list_records_page(db: Session, **filters) -> dict:
    page = max(1, int(filters.pop("page", 1)))
    page_size = min(100, max(1, int(filters.pop("page_size", 50))))
    query = _records_query(db, **filters)
    total = int(db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0)
    items = list(db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all())
    companies = [item for item in db.scalars(select(ClientRecord.insurance_company).where(ClientRecord.deleted_at.is_(None), ClientRecord.insurance_company.is_not(None)).distinct().order_by(ClientRecord.insurance_company)).all() if item]
    return {"items": items, "page": page, "page_size": page_size, "total": total, "companies": companies}


def records_matching_ids(db: Session, filters: dict, *, limit: int = 5_000) -> list[str]:
    allowed = {key: filters.get(key) for key in ("search", "date_from", "date_to", "sort_by", "sort_dir", "company", "state") if filters.get(key) is not None}
    return [item.id for item in db.scalars(_records_query(db, **allowed).limit(limit + 1)).all()][:limit]


def set_records_archived(db: Session, user, record_ids: list[str], *, archived: bool) -> list[str]:
    changed: list[str] = []
    now = datetime.now(timezone.utc)
    for record_id in dict.fromkeys(record_ids):
        record = db.get(ClientRecord, record_id)
        if not record or record.deleted_at:
            continue
        record.archived_at = now if archived else None
        changed.append(record.id)
    if changed:
        db.add(AuditEvent(
            id=new_id(), actor_id=user.id, action="records.archive" if archived else "records.unarchive",
            entity_type="client_record_set", entity_id=None, details={"record_ids": changed, "count": len(changed)},
        ))
        db.commit()
    return changed


def list_saved_views(db: Session, user) -> list[RecordSavedView]:
    return list(db.scalars(select(RecordSavedView).where((RecordSavedView.owner_id == user.id) | (RecordSavedView.is_shared.is_(True))).order_by(RecordSavedView.name)).all())


def save_view(db: Session, user, payload: dict) -> RecordSavedView:
    view = db.get(RecordSavedView, payload.get("id")) if payload.get("id") else None
    if view and view.owner_id != user.id:
        raise AppError("Only the owner can change this saved view.", 403)
    if view and payload.get("base_revision") != view.revision:
        raise AppError("This saved view changed elsewhere. Reload before saving.", 409)
    if view is None:
        view = RecordSavedView(id=new_id(), owner_id=user.id, name=payload["name"].strip())
        db.add(view)
    else:
        view.revision += 1
        view.name = payload["name"].strip()
    view.filters = payload.get("filters") or {}
    view.is_shared = bool(payload.get("is_shared", True))
    db.commit()
    db.refresh(view)
    return view


def delete_view(db: Session, user, view_id: str) -> None:
    view = db.get(RecordSavedView, view_id)
    if not view:
        raise AppError("Saved view not found.", 404)
    if view.owner_id != user.id:
        raise AppError("Only the owner can delete this saved view.", 403)
    db.delete(view)
    db.commit()


def get_record(db: Session, record_id: str) -> ClientRecord:
    record = db.get(ClientRecord, record_id)
    if not record:
        raise AppError("Client record not found.", 404)
    return record


def update_record(db: Session, record_id: str, payload: dict) -> ClientRecord:
    record = get_record(db, record_id)
    if "insurer_no" in payload:
        if payload["insurer_no"] != record.insurer_no:
            exists = db.scalar(
                select(func.count()).select_from(ClientRecord).where(
                    ClientRecord.insurer_no == payload["insurer_no"],
                    ClientRecord.id != record_id,
                )
            )
            if exists:
                raise AppError("This insurer number is already in use.", 409)
        record.insurer_no = payload["insurer_no"]
    if "notes" in payload:
        record.notes = payload["notes"]
    db.commit()
    db.refresh(record)
    return record


def export_csv_bytes(db: Session, search: str | None = None) -> bytes:
    records = list(db.scalars(_records_query(db, search=search, sort_by="created_at", sort_dir="desc").limit(5_000)).all())
    buf = io.StringIO()
    writer = csv.writer(buf)
    headers = ["insurer_no", "insurance_company", "vehicle_no", "customer_name"] + [
        f for f in BASIC_FIELDS if f not in ("insurance_company", "vehicle_no", "customer_name", "notes")
    ] + ["notes", "generated_at"]
    writer.writerow(headers)
    for r in records:
        writer.writerow([getattr(r, h, "") for h in headers])
    return buf.getvalue().encode("utf-8-sig")


def serialize_record(r: ClientRecord) -> dict:
    data = {"id": r.id, "insurer_no": r.insurer_no}
    for f in BASIC_FIELDS:
        data[f] = getattr(r, f, None)
    data["raw_values"] = r.raw_values
    data["extracted_at"] = r.extracted_at.isoformat() if r.extracted_at else None
    data["confirmed_at"] = r.confirmed_at.isoformat() if r.confirmed_at else None
    data["generated_at"] = r.generated_at.isoformat() if r.generated_at else None
    data["archived_at"] = r.archived_at.isoformat() if r.archived_at else None
    data["created_at"] = r.created_at.isoformat()
    data["updated_at"] = r.updated_at.isoformat()
    return data


def serialize_saved_view(view: RecordSavedView) -> dict:
    return {
        "id": view.id,
        "owner_id": view.owner_id,
        "name": view.name,
        "filters": view.filters or {},
        "is_shared": view.is_shared,
        "revision": view.revision,
        "updated_at": view.updated_at.isoformat(),
    }
