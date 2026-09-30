"""Customer Account Management Service.
Handles Master Customer & Corporate Fleet records, government ID deduplication (SSM BRN, NRIC, Passport),
and non-destructive profile enrichment with discrepancy reporting.
"""

from __future__ import annotations

from typing import Any
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.tables import CustomerAccount, new_id
from app.services.identity_normalization_service import (
    is_corporate_entity,
    normalize_canonical_name,
    normalize_government_id,
)


def resolve_or_create_customer(
    db: Session,
    raw_name: str | None,
    raw_id: str | None,
    phone: str | None = None,
    email: str | None = None,
    address: str | None = None,
) -> tuple[CustomerAccount | None, list[dict[str, Any]]]:
    """
    Resolve an existing customer or register a new one.
    - Matches primarily by immutable government ID (NRIC, Passport, SSM BRN).
    - Falls back to canonical normalized name.
    - Automatically enriches empty master profile fields.
    - Detects and reports conflicting contact info without blind-overwriting.
    - Appends raw name spelling to customer.name_aliases.
    Returns:
        (CustomerAccount, list[DiscrepancyDict])
    """
    id_number, id_type = normalize_government_id(raw_id)
    canonical_name = normalize_canonical_name(raw_name)
    discrepancies: list[dict[str, Any]] = []

    customer: CustomerAccount | None = None

    # 1. Primary lookup by normalized government ID
    if id_number:
        customer = db.scalar(
            select(CustomerAccount).where(CustomerAccount.id_number == id_number)
        )

    # 2. Secondary fallback lookup by canonical name (only if no government ID was found)
    if not customer and canonical_name:
        customer = db.scalar(
            select(CustomerAccount).where(CustomerAccount.canonical_name == canonical_name)
        )

    # 3. Existing Customer Found -> Non-destructive enrichment & discrepancy check
    if customer:
        # Alias tracking: append new spelling variant if not already recorded
        raw_name_clean = (raw_name or "").strip()
        if raw_name_clean and raw_name_clean not in customer.name_aliases:
            aliases = list(customer.name_aliases or [])
            if raw_name_clean not in aliases:
                aliases.append(raw_name_clean)
                customer.name_aliases = aliases

        # Name variation alert
        if canonical_name and customer.canonical_name != canonical_name:
            discrepancies.append({
                "field": "name",
                "current": customer.canonical_name,
                "detected": canonical_name,
                "message": f"Alternative name spelling detected: '{canonical_name}'",
            })

        # Phone: non-destructive fill or conflict recording
        if phone and phone.strip():
            clean_phone = phone.strip()
            if not customer.phone:
                customer.phone = clean_phone
            elif customer.phone != clean_phone:
                discrepancies.append({
                    "field": "phone",
                    "current": customer.phone,
                    "detected": clean_phone,
                    "message": f"New phone detected: {clean_phone} (existing: {customer.phone})",
                })
                # Store in alternate contacts
                alt = list(customer.alternate_contacts or [])
                existing_phones = {c.get("value") for c in alt if isinstance(c, dict) and c.get("type") == "phone"}
                if clean_phone not in existing_phones:
                    alt.append({"type": "phone", "value": clean_phone, "source": "quotation"})
                    customer.alternate_contacts = alt

        # Email: non-destructive fill or conflict recording
        if email and email.strip():
            clean_email = email.strip().lower()
            if not customer.email:
                customer.email = clean_email
            elif customer.email.lower() != clean_email:
                discrepancies.append({
                    "field": "email",
                    "current": customer.email,
                    "detected": clean_email,
                    "message": f"New email detected: {clean_email} (existing: {customer.email})",
                })

        # Address: non-destructive fill or conflict recording
        if address and address.strip():
            clean_addr = address.strip()
            if not customer.address:
                customer.address = clean_addr
            elif customer.address.strip().lower() != clean_addr.lower():
                discrepancies.append({
                    "field": "address",
                    "current": customer.address,
                    "detected": clean_addr,
                    "message": "Updated address detected in quotation",
                })

        # If customer lacked government ID and this quote provides one, upgrade it
        if id_number and customer.id_number.startswith("PENDING-"):
            customer.id_number = id_number
            customer.id_type = id_type

        db.flush()
        return customer, discrepancies

    # 4. New Customer Registration
    if not id_number and not canonical_name:
        return None, []

    is_corp = is_corporate_entity(canonical_name, id_type)
    assigned_id_number = id_number if id_number else f"PENDING-{new_id()[:8].upper()}"
    assigned_name = canonical_name if canonical_name else (raw_name.strip().upper() if raw_name else "VALUED CLIENT")

    initial_aliases = []
    if raw_name and raw_name.strip():
        initial_aliases.append(raw_name.strip())

    customer = CustomerAccount(
        id=new_id(),
        entity_type="corporate" if is_corp else "individual",
        id_type=id_type,
        id_number=assigned_id_number,
        canonical_name=assigned_name,
        name_aliases=initial_aliases,
        phone=phone.strip() if phone else None,
        email=email.strip().lower() if email else None,
        address=address.strip() if address else None,
        is_fleet=is_corp,
    )
    db.add(customer)
    db.flush()
    return customer, []


def get_customer_account(db: Session, customer_id: str) -> CustomerAccount | None:
    """Retrieve customer account by ID."""
    return db.get(CustomerAccount, customer_id)


def list_customers(
    db: Session,
    search: str | None = None,
    is_fleet: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[CustomerAccount], int]:
    """List customer accounts with optional search by name, ID number, or fleet status."""
    stmt = select(CustomerAccount)
    if is_fleet is not None:
        stmt = stmt.where(CustomerAccount.is_fleet.is_(is_fleet))

    if search and search.strip():
        term = f"%{search.strip().upper()}%"
        stmt = stmt.where(
            or_(
                CustomerAccount.canonical_name.ilike(term),
                CustomerAccount.id_number.ilike(term),
                CustomerAccount.phone.ilike(term),
                CustomerAccount.email.ilike(term),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = list(db.scalars(stmt.order_by(CustomerAccount.canonical_name.asc()).offset(offset).limit(limit)).all())
    return items, total
