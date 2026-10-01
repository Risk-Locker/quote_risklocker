"""Person In Charge (PIC) & SubAgents API router."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.db.session import get_db
from app.models.tables import User
from app.services.pic_service import (
    create_pic,
    delete_pic,
    get_pic_detail,
    list_pics,
    update_pic,
)

router = APIRouter(prefix="/pics", tags=["person-in-charge"])


class CreatePicRequest(BaseModel):
    name: str = Field(..., description="Full Name of the Person in Charge or SubAgent")
    type: str = Field("subagent", description="Role: subagent, client_self, company_personnel, external_contact")
    agency_group: str | None = Field(None, description="Agency team or group e.g. BNI, BNI_DJ")
    commission_rate: float = Field(0.0, description="Commission percentage (applicable to subagents)")
    phone: str | None = None
    email: str | None = None
    notes: str | None = None


class UpdatePicRequest(BaseModel):
    name: str | None = None
    type: str | None = None
    agency_group: str | None = None
    commission_rate: float | None = None
    phone: str | None = None
    email: str | None = None
    notes: str | None = None


@router.get("", response_model=list[dict[str, Any]])
def get_pics(
    type: str | None = Query(None, description="Filter by role type"),
    agency_group: str | None = Query(None, description="Filter by agency group"),
    search: str | None = Query(None, description="Search by name, agency, or phone"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """List all Persons In Charge / SubAgents with managed policy metrics."""
    return list_pics(db, pic_type=type, agency_group=agency_group, search=search)


@router.post("", status_code=status.HTTP_201_CREATED)
def add_pic(
    payload: CreatePicRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Create a new Person In Charge or SubAgent."""
    pic = create_pic(
        db,
        name=payload.name,
        pic_type=payload.type,
        agency_group=payload.agency_group,
        commission_rate=payload.commission_rate,
        phone=payload.phone,
        email=payload.email,
        notes=payload.notes,
    )
    return {
        "id": pic.id,
        "name": pic.name,
        "type": pic.type,
        "agency_group": pic.agency_group,
        "commission_rate": float(pic.commission_rate or 0.0),
        "phone": pic.phone,
        "email": pic.email,
        "notes": pic.notes,
    }


@router.get("/{pic_id}")
def get_single_pic(
    pic_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Get single PIC detail with assigned vehicle tenures."""
    data = get_pic_detail(db, pic_id)
    if not data:
        raise HTTPException(status_code=404, detail="Person in charge not found")
    return data


@router.patch("/{pic_id}")
def update_single_pic(
    pic_id: str,
    payload: UpdatePicRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Update Person In Charge fields."""
    pic = update_pic(
        db,
        pic_id,
        name=payload.name,
        pic_type=payload.type,
        agency_group=payload.agency_group,
        commission_rate=payload.commission_rate,
        phone=payload.phone,
        email=payload.email,
        notes=payload.notes,
    )
    if not pic:
        raise HTTPException(status_code=404, detail="Person in charge not found")
    return {
        "id": pic.id,
        "name": pic.name,
        "type": pic.type,
        "agency_group": pic.agency_group,
        "commission_rate": float(pic.commission_rate or 0.0),
        "phone": pic.phone,
        "email": pic.email,
        "notes": pic.notes,
    }


@router.delete("/{pic_id}")
def remove_pic(
    pic_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Delete a Person In Charge record."""
    success = delete_pic(db, pic_id)
    if not success:
        raise HTTPException(status_code=404, detail="Person in charge not found")
    return {"ok": True}
