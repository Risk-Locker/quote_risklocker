"""Session CRUD for the session-based review workflow."""

from __future__ import annotations

from sqlalchemy import func, or_, select, String
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.tables import Session as SessionModel, UploadedFile, QuotationDraft


def create_session(
    db: Session,
    owner_id: str,
    uploaded_file_id: str,
    draft_id: str,
    detected_company: str | None = None,
) -> SessionModel:
    session = SessionModel(
        owner_id=owner_id,
        uploaded_file_id=uploaded_file_id,
        draft_id=draft_id,
        detected_company=detected_company,
    )
    db.add(session)
    db.flush()
    db.refresh(session)
    return session


def list_sessions(db: Session, user_id: str, search: str | None = None, limit: int = 25, offset: int = 0) -> tuple[list[SessionModel], int]:
    base = (
        select(SessionModel)
        .join(UploadedFile, SessionModel.uploaded_file_id == UploadedFile.id)
        .outerjoin(QuotationDraft, SessionModel.draft_id == QuotationDraft.id)
        .where(UploadedFile.deleted_at.is_(None))
    )
    if search:
        like = f"%{search.strip()}%"
        base = base.where(
            or_(
                SessionModel.detected_company.ilike(like),
                UploadedFile.original_filename.ilike(like),
                func.cast(QuotationDraft.fields, String).ilike(like),
            )
        )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(
        db.scalars(
            base.order_by(SessionModel.created_at.desc()).limit(limit).offset(offset)
        ).all()
    )
    return rows, total


def get_session(db: Session, session_id: str) -> SessionModel:
    session = db.get(SessionModel, session_id)
    if not session:
        raise AppError("Session not found.", 404)
    return session


def serialize_session(session: SessionModel) -> dict:
    filename = session.uploaded_file.original_filename if session.uploaded_file else ""
    draft_status = session.draft.status if session.draft else ""
    fields = session.draft.fields if session.draft and session.draft.fields else {}
    
    # Extract identifiers safely
    insured_name = fields.get("customer_name", {}).get("value")
    vehicle_plate = fields.get("vehicle_no", {}).get("value")
    vehicle_model = fields.get("car_model", {}).get("value")
    total_premium = fields.get("total_amount", {}).get("value")
    
    return {
        "id": session.id,
        "owner_id": session.owner_id,
        "uploaded_file_id": session.uploaded_file_id,
        "draft_id": session.draft_id,
        "detected_company": session.detected_company,
        "filename": filename,
        "status": session.status,
        "draft_status": draft_status,
        "insured_name": insured_name,
        "vehicle_plate": vehicle_plate,
        "vehicle_model": vehicle_model,
        "total_premium": total_premium,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
    }
