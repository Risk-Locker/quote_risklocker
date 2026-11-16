"""Catalog Diff and Underwriter Cloning Engine (Milestone 4).

Allows comparing underwriter benefit catalogs side-by-side, identifying
coverage gaps (e.g. unique perils or differing towing limits), generating
structured diff plans, and transactionally applying clone/diff proposals.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.enums import Role
from app.models.tables import (
    AuditEvent,
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    CatalogOffering,
    InsuranceCompany,
    User,
    new_id,
)

logger = logging.getLogger(__name__)

BUSINESS_ROLES = frozenset({Role.STAFF.value, Role.ADMIN.value, Role.SUPER_ADMIN.value})


def _require_business(user: User) -> None:
    if user.role not in BUSINESS_ROLES:
        raise AppError("You do not have permission to modify benefit catalogs.", 403)


def _get_active_offerings_map(
    db: Session, company_id: str
) -> tuple[BenefitCatalog | None, BenefitCatalogRevision | None, dict[str, dict[str, Any]]]:
    """Retrieve catalog, latest revision, and map of {concept_id: offering_data} for a company."""
    catalog = db.scalar(
        select(BenefitCatalog)
        .where(BenefitCatalog.company_id == company_id)
        .order_by(BenefitCatalog.created_at.desc())
    )
    if not catalog:
        return None, None, {}

    revision = db.scalar(
        select(BenefitCatalogRevision)
        .where(BenefitCatalogRevision.catalog_id == catalog.id)
        .order_by(BenefitCatalogRevision.revision_number.desc())
    )
    if not revision:
        return catalog, None, {}

    offerings = db.scalars(
        select(CatalogOffering)
        .where(
            CatalogOffering.catalog_revision_id == revision.id,
            CatalogOffering.status == "active",
        )
        .order_by(CatalogOffering.sort_order)
    ).all()

    offerings_map: dict[str, dict[str, Any]] = {}
    for off in offerings:
        concept = db.get(BenefitConcept, off.concept_id)
        concept_key = concept.concept_key if concept else off.offering_key
        concept_name = concept.label if concept else off.offering_key

        offerings_map[off.concept_id] = {
            "offering_id": off.id,
            "offering_key": off.offering_key,
            "concept_id": off.concept_id,
            "concept_key": concept_key,
            "concept_name": concept_name,
            "role": off.role,
            "offering_kind": off.offering_kind,
            "display_value": off.display_value or ("Included" if off.role == "included" else "Optional"),
            "sort_order": off.sort_order,
        }

    return catalog, revision, offerings_map


def compare_underwriter_catalogs(
    db: Session, source_company_id: str, target_company_id: str
) -> dict[str, Any]:
    """Compare two insurer catalogs and categorize common, missing, and differing benefits."""
    source_comp = db.get(InsuranceCompany, source_company_id)
    target_comp = db.get(InsuranceCompany, target_company_id)
    if not source_comp or not target_comp:
        raise AppError("One or both insurance companies could not be found.", 404)

    _, _, source_map = _get_active_offerings_map(db, source_company_id)
    _, _, target_map = _get_active_offerings_map(db, target_company_id)

    source_concept_ids = set(source_map.keys())
    target_concept_ids = set(target_map.keys())

    common_ids = source_concept_ids & target_concept_ids
    missing_in_target_ids = source_concept_ids - target_concept_ids
    unique_to_target_ids = target_concept_ids - source_concept_ids

    common_benefits = []
    for cid in common_ids:
        s_off = source_map[cid]
        t_off = target_map[cid]
        common_benefits.append({
            "concept_id": cid,
            "concept_key": s_off["concept_key"],
            "concept_name": s_off["concept_name"],
            "source_value": s_off["display_value"],
            "target_value": t_off["display_value"],
            "values_match": s_off["display_value"] == t_off["display_value"],
        })

    missing_in_target = [source_map[cid] for cid in missing_in_target_ids]
    unique_to_target = [target_map[cid] for cid in unique_to_target_ids]

    return {
        "source_company": {
            "id": source_comp.id,
            "name": source_comp.name,
            "slug": source_comp.slug,
        },
        "target_company": {
            "id": target_comp.id,
            "name": target_comp.name,
            "slug": target_comp.slug,
        },
        "summary": {
            "total_source_benefits": len(source_map),
            "total_target_benefits": len(target_map),
            "common_count": len(common_benefits),
            "missing_in_target_count": len(missing_in_target),
            "unique_to_target_count": len(unique_to_target),
        },
        "common_benefits": common_benefits,
        "missing_in_target": missing_in_target,
        "unique_to_target": unique_to_target,
    }


def generate_clone_diff_plan(
    db: Session, source_company_id: str, target_company_id: str, options: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Generate a structured diff plan proposing to clone missing benefits from source to target."""
    comparison = compare_underwriter_catalogs(db, source_company_id, target_company_id)
    plan_id = new_id()

    actions = []
    for item in comparison["missing_in_target"]:
        actions.append({
            "action": "add",
            "concept_id": item["concept_id"],
            "concept_key": item["concept_key"],
            "concept_name": item["concept_name"],
            "role": item["role"],
            "offering_kind": item["offering_kind"],
            "source_value": item["display_value"],
            "target_value": None,
            "proposed_value": item["display_value"],
            "sort_order": item.get("sort_order", 0),
        })

    return {
        "plan_id": plan_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_company": comparison["source_company"],
        "target_company": comparison["target_company"],
        "summary": {
            "common_count": comparison["summary"]["common_count"],
            "to_add_count": len(actions),
            "to_update_count": 0,
        },
        "actions": actions,
    }


def apply_catalog_diff_plan(
    db: Session, user: User, plan: dict[str, Any]
) -> dict[str, Any]:
    """Apply a verified catalog diff plan transactionally to the target company's catalog."""
    _require_business(user)

    target_data = plan.get("target_company", {})
    target_id = target_data.get("id")
    target_slug = target_data.get("slug") or "target"
    if not target_id:
        raise AppError("Plan target company is missing.", 400)

    target_comp = db.get(InsuranceCompany, target_id)
    if not target_comp:
        raise AppError("Target insurance company not found.", 404)

    catalog, revision, _ = _get_active_offerings_map(db, target_id)
    if not catalog:
        # Create initial catalog for company
        catalog = BenefitCatalog(
            id=new_id(),
            company_id=target_id,
            name=f"{target_comp.name} Motor Comprehensive",
            revision=1,
        )
        db.add(catalog)
        db.flush()

    if not revision or revision.state == "published":
        # Create a new draft revision to receive additions
        next_rev = (revision.revision_number + 1) if revision else 1
        revision = BenefitCatalogRevision(
            id=new_id(),
            catalog_id=catalog.id,
            revision_number=next_rev,
            state="draft",
            content_hash=f"draft_{new_id()[:12]}",
        )
        db.add(revision)
        db.flush()

    actions = plan.get("actions", [])
    applied_count = 0

    for act in actions:
        action_type = act.get("action")
        concept_id = act.get("concept_id")
        if not concept_id:
            continue

        if action_type == "add":
            offering_key = f"{target_slug}:{act.get('concept_key', concept_id)}"[:160]
            # Check for existing offering in this revision
            existing = db.scalar(
                select(CatalogOffering).where(
                    CatalogOffering.catalog_revision_id == revision.id,
                    CatalogOffering.concept_id == concept_id,
                )
            )
            if not existing:
                new_offering = CatalogOffering(
                    id=new_id(),
                    catalog_revision_id=revision.id,
                    offering_key=offering_key,
                    concept_id=concept_id,
                    offering_kind=act.get("offering_kind", "addon"),
                    role=act.get("role", "optional"),
                    display_value=act.get("proposed_value") or act.get("source_value") or "Included",
                    sort_order=act.get("sort_order", 0),
                    status="active",
                )
                db.add(new_offering)
                applied_count += 1
        elif action_type == "update":
            existing = db.scalar(
                select(CatalogOffering).where(
                    CatalogOffering.catalog_revision_id == revision.id,
                    CatalogOffering.concept_id == concept_id,
                )
            )
            if existing:
                if act.get("proposed_value"):
                    existing.display_value = act["proposed_value"]
                if act.get("role"):
                    existing.role = act["role"]
                applied_count += 1

    catalog.revision += 1

    audit = AuditEvent(
        id=new_id(),
        actor_id=user.id,
        action="catalog.diff.applied",
        entity_type="insurance_company",
        entity_id=target_id,
        details={
            "plan_id": plan.get("plan_id"),
            "source_company_id": plan.get("source_company", {}).get("id"),
            "applied_count": applied_count,
        },
    )
    db.add(audit)
    db.commit()

    return {
        "ok": True,
        "applied_actions_count": applied_count,
        "target_company_id": target_id,
        "catalog_id": catalog.id,
        "revision_id": revision.id,
    }
