from __future__ import annotations

from typing import Any
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.tables import BenefitPackage, BenefitPackagePlan, CorrectionMemory

def get_db_packs(db: Session) -> list[dict[str, Any]]:
    """Get egress-optimized benefit packages for Gemini context."""
    packs = db.scalars(
        select(BenefitPackage)
        .where(BenefitPackage.status == "active")
    ).all()
    
    plans = db.scalars(
        select(BenefitPackagePlan)
        .where(BenefitPackagePlan.status == "active")
    ).all()
    
    plans_by_pack = {}
    for plan in plans:
        plans_by_pack.setdefault(plan.package_id, []).append(plan.name)
        
    result = []
    for pack in packs:
        result.append({
            "name": pack.name,
            "plans": plans_by_pack.get(pack.id, [])
        })
    return result

def get_correction_memory(db: Session, insurance_company_id: str | None) -> list[dict[str, Any]]:
    """Get top 15 corrections using a strict DB GROUP BY to prevent egress spikes."""
    
    query = select(
        CorrectionMemory.field_name,
        CorrectionMemory.original_value,
        CorrectionMemory.corrected_value,
        func.count(CorrectionMemory.id).label("c")
    )
    if insurance_company_id:
        query = query.where(CorrectionMemory.insurance_company_id == insurance_company_id)
        
    rows = db.execute(
        query.group_by(CorrectionMemory.field_name, CorrectionMemory.original_value, CorrectionMemory.corrected_value)
        .having(func.count(CorrectionMemory.id) >= 2)
        .order_by(func.count(CorrectionMemory.id).desc())
        .limit(15)
    ).all()
    
    return [
        {
            "field": row[0],
            "original_value": row[1],
            "corrected_value": row[2],
            "frequency": row[3]
        }
        for row in rows
    ]
