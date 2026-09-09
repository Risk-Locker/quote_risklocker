"""Session CRUD for the session-based review workflow."""

from __future__ import annotations

from typing import Any
from sqlalchemy import func, or_, select, String
from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError
from app.models.tables import Session as SessionModel, UploadedFile, QuotationDraft, User


def get_session_filter_options(db: Session) -> dict[str, Any]:
    """Return distinct available companies and users who created or edited sessions."""
    company_rows = db.scalars(
        select(SessionModel.detected_company)
        .join(UploadedFile, SessionModel.uploaded_file_id == UploadedFile.id)
        .where(UploadedFile.deleted_at.is_(None), SessionModel.detected_company.is_not(None))
        .distinct()
    ).all()
    companies = sorted([c.strip() for c in company_rows if c and c.strip()])

    owner_ids = db.scalars(
        select(SessionModel.owner_id)
        .join(UploadedFile, SessionModel.uploaded_file_id == UploadedFile.id)
        .where(UploadedFile.deleted_at.is_(None))
        .distinct()
    ).all()
    editor_ids = db.scalars(
        select(SessionModel.last_edited_by_id)
        .join(UploadedFile, SessionModel.uploaded_file_id == UploadedFile.id)
        .where(UploadedFile.deleted_at.is_(None), SessionModel.last_edited_by_id.is_not(None))
        .distinct()
    ).all()
    user_ids = set(owner_ids).union(set(editor_ids))

    user_list: list[dict[str, str]] = []
    if user_ids:
        users = db.scalars(select(User).where(User.id.in_(list(user_ids)))).all()
        for u in users:
            name = u.name or (u.email.split("@")[0].capitalize() if u.email else "User")
            user_list.append({"id": u.id, "name": name, "email": u.email, "role": u.role})
        user_list.sort(key=lambda x: x["name"])

    return {
        "companies": companies,
        "users": user_list,
        "staff": user_list,  # Backward compatibility for existing consumers
    }


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


def list_sessions(
    db: Session,
    user_id: str,
    search: str | None = None,
    company: str | None = None,
    staff_id: str | None = None,
    status: str | None = None,
    sort_by: str = "vehicle",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[SessionModel], int]:
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
                SessionModel.quotation_ref.ilike(like),
                UploadedFile.original_filename.ilike(like),
                func.cast(QuotationDraft.fields, String).ilike(like),
            )
        )
    if company and company.lower() != "all":
        base = base.where(SessionModel.detected_company.ilike(f"%{company.strip()}%"))
    if staff_id and staff_id.lower() != "all":
        base = base.where(or_(SessionModel.owner_id == staff_id, SessionModel.last_edited_by_id == staff_id))
    if status and status.lower() != "all":
        base = base.where(func.lower(QuotationDraft.status) == status.strip().lower())

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0

    bind = getattr(db, "bind", None)
    is_pg = bind is not None and getattr(bind, "dialect", None) is not None and bind.dialect.name == "postgresql"

    # Sorting
    if sort_by in ("vehicle", "plate_asc"):
        if is_pg:
            plate_expr = func.coalesce(func.jsonb_extract_path_text(QuotationDraft.fields, "vehicle_no", "value"), "")
            # Empty plates sort to the bottom, non-empty plates sort alphabetically, and within each plate newest first
            base = base.order_by(
                (plate_expr == "").asc(),
                plate_expr.asc(),
                SessionModel.created_at.desc(),
            )
        else:
            base = base.order_by(SessionModel.created_at.desc())
    elif sort_by == "date_asc":
        base = base.order_by(SessionModel.created_at.asc())
    elif sort_by == "ref_desc":
        base = base.order_by(SessionModel.quotation_ref.desc().nullslast(), SessionModel.created_at.desc())
    elif sort_by == "ref_asc":
        base = base.order_by(SessionModel.quotation_ref.asc().nullsfirst(), SessionModel.created_at.asc())
    elif sort_by == "customer_asc":
        if is_pg:
            cust_expr = func.coalesce(func.jsonb_extract_path_text(QuotationDraft.fields, "customer_name", "value"), "")
            base = base.order_by((cust_expr == "").asc(), cust_expr.asc(), SessionModel.created_at.desc())
        else:
            base = base.order_by(SessionModel.created_at.desc())
    else:  # default date_desc
        base = base.order_by(SessionModel.created_at.desc())

    rows = list(
        db.scalars(
            base.options(
                joinedload(SessionModel.uploaded_file),
                joinedload(SessionModel.draft).defer(QuotationDraft.scalar_decisions),
                joinedload(SessionModel.owner),
                joinedload(SessionModel.last_edited_by),
            )
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return rows, total


def get_session(db: Session, session_id: str) -> SessionModel:
    session = db.get(SessionModel, session_id)
    if not session:
        raise AppError("Session not found.", 404)
    return session


def serialize_session(
    session: SessionModel,
    *args: Any,
    **kwargs: Any,
) -> dict:
    filename = session.uploaded_file.original_filename if session.uploaded_file else ""
    draft_status = session.draft.status if session.draft else ""
    fields = session.draft.fields if session.draft and session.draft.fields else {}

    # Extract identifiers safely
    insured_name = fields.get("customer_name", {}).get("value")
    vehicle_plate = fields.get("vehicle_no", {}).get("value")
    vehicle_model = fields.get("car_model", {}).get("value")
    total_premium = fields.get("total_amount", {}).get("value")

    # Author and edit attribution
    created_by_name = ""
    created_by_email = ""
    if session.owner:
        created_by_name = session.owner.name or (session.owner.email.split("@")[0].capitalize() if session.owner.email else "")
        created_by_email = session.owner.email
    if not created_by_name:
        created_by_name = "System"

    last_edited_by_name = None
    last_edited_by_email = None
    if session.last_edited_by:
        last_edited_by_name = session.last_edited_by.name or (session.last_edited_by.email.split("@")[0].capitalize() if session.last_edited_by.email else "")
        last_edited_by_email = session.last_edited_by.email

    quotation_ref = session.quotation_ref or fields.get("quotation_reference", {}).get("value")

    return {
        "id": session.id,
        "owner_id": session.owner_id,
        "created_by": created_by_name,
        "created_by_email": created_by_email,
        "last_edited_by": last_edited_by_name,
        "last_edited_by_email": last_edited_by_email,
        "last_edited_at": session.last_edited_at.isoformat() if session.last_edited_at else None,
        "is_edited": session.last_edited_at is not None,
        "uploaded_file_id": session.uploaded_file_id,
        "draft_id": session.draft_id,
        "detected_company": session.detected_company,
        "quotation_ref": quotation_ref,
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
