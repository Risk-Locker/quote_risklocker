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
    """Decommissioned: returns empty list to prevent ungrounded value-swapping in LLM prompts.
    // RL-DISABLED correction_memory — disabled 2026-09-08; restore when semantic provenance and context-aware learning are implemented
    """
    return []
