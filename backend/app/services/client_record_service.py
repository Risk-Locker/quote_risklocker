"""Client record CRUD for CRM dashboard."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.tables import ClientRecord


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


def list_records(
    db: Session,
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> list[ClientRecord]:
    q = select(ClientRecord)
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
    col = getattr(ClientRecord, sort_by, ClientRecord.created_at)
    q = q.order_by(col.desc() if sort_dir == "desc" else col.asc()).limit(200)
    return list(db.scalars(q).all())


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
    records = list_records(db, search=search, sort_by="created_at", sort_dir="desc")
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
    data["created_at"] = r.created_at.isoformat()
    data["updated_at"] = r.updated_at.isoformat()
    return data
