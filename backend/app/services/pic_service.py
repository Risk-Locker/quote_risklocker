"""Person In Charge (PIC) & SubAgent Management Service.
Handles directory, agency groupings (e.g. BNI), commission rates, and client roster associations.
"""

from __future__ import annotations

from typing import Any
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.tables import InsuranceTenure, PersonInCharge, new_id


def list_pics(
    db: Session,
    pic_type: str | None = None,
    agency_group: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """List all Persons In Charge and SubAgents with metrics on managed policies."""
    query = select(PersonInCharge).order_by(PersonInCharge.name.asc())

    if pic_type and pic_type != "all":
        query = query.where(PersonInCharge.type == pic_type)
    if agency_group:
        query = query.where(PersonInCharge.agency_group.ilike(f"%{agency_group}%"))
    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                PersonInCharge.name.ilike(search_pattern),
                PersonInCharge.agency_group.ilike(search_pattern),
                PersonInCharge.phone.ilike(search_pattern),
            )
        )

    pics = list(db.scalars(query).all())

    # Aggregate tenure count and client count per PIC
    results: list[dict[str, Any]] = []
    for p in pics:
        tenure_count = db.scalar(
            select(func.count(InsuranceTenure.id)).where(InsuranceTenure.pic_id == p.id)
        ) or 0
        distinct_clients = db.scalar(
            select(func.count(func.distinct(InsuranceTenure.customer_name))).where(
                InsuranceTenure.pic_id == p.id
            )
        ) or 0

        results.append(
            {
                "id": p.id,
                "name": p.name,
                "type": p.type,
                "agency_group": p.agency_group,
                "commission_rate": float(p.commission_rate or 0.0),
                "phone": p.phone,
                "whatsapp_number": p.whatsapp_number or p.phone,
                "email": p.email,
                "is_owner": bool(p.is_owner),
                "notes": p.notes,
                "tenures_count": tenure_count,
                "clients_count": distinct_clients,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
        )

    return results


def get_pic_detail(db: Session, pic_id: str) -> dict[str, Any] | None:
    """Retrieve detailed info for a single PIC including assigned tenures."""
    pic = db.scalar(select(PersonInCharge).where(PersonInCharge.id == pic_id))
    if not pic:
        return None

    tenures = list(
        db.scalars(
            select(InsuranceTenure)
            .where(InsuranceTenure.pic_id == pic.id)
            .order_by(InsuranceTenure.coverage_end_date.desc())
        ).all()
    )

    return {
        "id": pic.id,
        "name": pic.name,
        "type": pic.type,
        "agency_group": pic.agency_group,
        "commission_rate": float(pic.commission_rate or 0.0),
        "phone": pic.phone,
        "whatsapp_number": pic.whatsapp_number or pic.phone,
        "email": pic.email,
        "is_owner": bool(pic.is_owner),
        "notes": pic.notes,
        "tenures": [
            {
                "id": t.id,
                "vehicle_no": t.vehicle_no,
                "customer_name": t.customer_name,
                "expiry_month": t.expiry_month,
                "coverage_end_date": t.coverage_end_date.isoformat(),
                "stage": t.stage,
                "won_premium": float(t.won_premium) if t.won_premium is not None else None,
                "status": t.status,
            }
            for t in tenures
        ],
    }


def create_pic(
    db: Session,
    name: str,
    pic_type: str = "subagent",
    agency_group: str | None = None,
    commission_rate: float = 0.0,
    phone: str | None = None,
    whatsapp_number: str | None = None,
    email: str | None = None,
    is_owner: bool = False,
    notes: str | None = None,
) -> PersonInCharge:
    """Create a new Person In Charge or SubAgent record."""
    if is_owner:
        # Unset other owners to ensure default owner PIC is unique
        existing_owners = list(db.scalars(select(PersonInCharge).where(PersonInCharge.is_owner == True)).all())
        for o in existing_owners:
            o.is_owner = False

    pic = PersonInCharge(
        id=new_id(),
        name=name.strip(),
        type=pic_type,
        agency_group=agency_group.strip() if agency_group else None,
        commission_rate=commission_rate if pic_type == "subagent" else 0.0,
        phone=phone.strip() if phone else None,
        whatsapp_number=whatsapp_number.strip() if whatsapp_number else (phone.strip() if phone else None),
        email=email.strip() if email else None,
        is_owner=is_owner,
        notes=notes.strip() if notes else None,
    )
    db.add(pic)
    db.commit()
    db.refresh(pic)
    return pic


def update_pic(
    db: Session,
    pic_id: str,
    name: str | None = None,
    pic_type: str | None = None,
    agency_group: str | None = None,
    commission_rate: float | None = None,
    phone: str | None = None,
    whatsapp_number: str | None = None,
    email: str | None = None,
    is_owner: bool | None = None,
    notes: str | None = None,
) -> PersonInCharge | None:
    """Update fields of an existing Person In Charge."""
    pic = db.scalar(select(PersonInCharge).where(PersonInCharge.id == pic_id))
    if not pic:
        return None

    if name is not None:
        pic.name = name.strip()
    if pic_type is not None:
        pic.type = pic_type
        if pic_type != "subagent":
            pic.commission_rate = 0.0
    if agency_group is not None:
        pic.agency_group = agency_group.strip() or None
    if commission_rate is not None and pic.type == "subagent":
        pic.commission_rate = commission_rate
    if phone is not None:
        pic.phone = phone.strip() or None
    if whatsapp_number is not None:
        pic.whatsapp_number = whatsapp_number.strip() or None
    if email is not None:
        pic.email = email.strip() or None
    if is_owner is not None:
        if is_owner:
            other_owners = list(db.scalars(select(PersonInCharge).where(PersonInCharge.id != pic.id, PersonInCharge.is_owner == True)).all())
            for o in other_owners:
                o.is_owner = False
        pic.is_owner = is_owner
    if notes is not None:
        pic.notes = notes.strip() or None

    db.commit()
    db.refresh(pic)
    return pic


def delete_pic(db: Session, pic_id: str) -> bool:
    """Safely delete a PIC (nulls out tenure references first)."""
    pic = db.scalar(select(PersonInCharge).where(PersonInCharge.id == pic_id))
    if not pic:
        return False

    # Nullify references in insurance_tenures
    tenures = list(db.scalars(select(InsuranceTenure).where(InsuranceTenure.pic_id == pic_id)).all())
    for t in tenures:
        t.pic_id = None

    db.delete(pic)
    db.commit()
    return True
