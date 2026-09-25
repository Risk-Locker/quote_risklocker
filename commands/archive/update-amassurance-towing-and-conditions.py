"""Update AmAssurance towing tiers and register the Unlimited Towing hide_target condition.

Vehicles covered: Car (ICE & EV), Motorcycle (ICE), Commercial/Lorry.
Profile: Active Profile v2 (94f56a3a-3ea1-4532-8ae7-34dda7c60a62)
"""

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.session import SessionLocal
from app.models.tables import (
    BenefitConcept,
    CompanyBenefitCondition,
    InsuranceCompany,
    BenefitCatalog,
    BenefitPackage,
    CatalogOffering,
    BenefitCatalogRevision,
    BenefitPackagePlan,
    BenefitPackagePlanItem,
    BenefitRelation,
    new_id,
    utcnow,
)
from app.services.business_setup_service import get_active_benefit_profile
from app.rendering.render_context import canonical_context_hash
from sqlalchemy import select

def update_amassurance():
    db = SessionLocal()
    try:
        am = db.scalar(select(InsuranceCompany).where(InsuranceCompany.slug == "amassurance"))
        if not am:
            print("AmAssurance not found!")
            return

        active_prof = get_active_benefit_profile(db)
        print(f"Active Profile: {active_prof.name} ({active_prof.id})")

        concepts = {c.concept_key: c for c in db.scalars(select(BenefitConcept)).all()}
        towing_concept = concepts.get("towing")
        towing_upgrade_concept = concepts.get("towing-upgrade") or concepts.get("auto-assistance")

        if not towing_concept or not towing_upgrade_concept:
            print("Towing or Towing Upgrade concept not found!")
            return

        # -------------------------------------------------------------
        # 1. Update/Create Condition: Unlimited Towing Hides Default Towing
        # -------------------------------------------------------------
        cond = db.scalar(
            select(CompanyBenefitCondition).where(
                CompanyBenefitCondition.company_id == am.id,
                CompanyBenefitCondition.profile_id == active_prof.id,
                CompanyBenefitCondition.trigger_concept_id == towing_upgrade_concept.id,
                CompanyBenefitCondition.target_concept_id == towing_concept.id,
            )
        )
        if cond:
            cond.name = "AmAssurance: Unlimited Towing Hides Default Towing"
            cond.action_type = "hide_target"
            cond.replacement_description = "[Hidden by condition rule]"
            cond.is_active = True
            cond.updated_at = utcnow()
            print("Updated existing AmAssurance Unlimited Towing condition to 'hide_target'!")
        else:
            cond = CompanyBenefitCondition(
                id=new_id(),
                company_id=am.id,
                profile_id=active_prof.id,
                name="AmAssurance: Unlimited Towing Hides Default Towing",
                trigger_concept_id=towing_upgrade_concept.id,
                trigger_plan_filter=None,
                target_concept_id=towing_concept.id,
                action_type="hide_target",
                replacement_description="[Hidden by condition rule]",
                is_active=True,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            db.add(cond)
            print("Created new AmAssurance Unlimited Towing condition with 'hide_target'!")
        db.commit()

        # -------------------------------------------------------------
        # 2. Update AmAssurance Catalogs & Tiers (Car, Motor, Lorry, EV)
        # -------------------------------------------------------------
        catalogs = db.scalars(
            select(BenefitCatalog).where(BenefitCatalog.company_id == am.id)
        ).all()

        updated_catalogs_count = 0

        for cat in catalogs:
            latest_rev = db.scalar(
                select(BenefitCatalogRevision)
                .where(BenefitCatalogRevision.catalog_id == cat.id)
                .order_by(BenefitCatalogRevision.revision_number.desc())
            )
            if not latest_rev:
                continue

            cat_name_lower = cat.name.lower()
            
            # Determine towing override text and display value for this catalog
            new_desc = None
            new_disp = None
            if "auto365" in cat_name_lower or "private car comprehensive" in cat_name_lower:
                if "lite" in cat_name_lower:
                    new_desc = "24/7 emergency accident and breakdown towing assistance up to 50 km."
                    new_disp = "50 km"
                elif "plus" in cat_name_lower:
                    new_desc = "24/7 emergency accident and breakdown towing assistance up to 100 km."
                    new_disp = "100 km"
                elif "premier" in cat_name_lower:
                    new_desc = "24/7 emergency accident and breakdown towing assistance up to 365 km."
                    new_disp = "365 km"
                else:
                    new_desc = "24/7 emergency accident and breakdown towing assistance up to policy limit."
            elif "ev" in cat_name_lower or cat.engine_type == "ev":
                new_desc = "Emergency 24/7 towing and flatbed assistance for EV breakdown or battery depletion."
            elif "motorcycle" in cat_name_lower or "motor" in cat_name_lower:
                new_desc = "24/7 emergency accident towing assistance up to policy limit."
            elif "commercial" in cat_name_lower or "lorry" in cat_name_lower:
                new_desc = "24/7 commercial vehicle emergency accident towing assistance up to policy limit."

            if not new_desc:
                continue

            current_offerings = list(
                db.scalars(
                    select(CatalogOffering).where(CatalogOffering.catalog_revision_id == latest_rev.id)
                ).all()
            )

            has_towing = any(o.concept_id == towing_concept.id for o in current_offerings)
            if not has_towing:
                continue

            if latest_rev.state == "draft":
                for o in current_offerings:
                    if o.concept_id == towing_concept.id:
                        o.description_override = new_desc
                        if new_disp:
                            o.display_value = new_disp
                db.commit()
                updated_catalogs_count += 1
            else:
                # Fork a new published revision from latest published revision
                new_rev = BenefitCatalogRevision(
                    id=new_id(),
                    catalog_id=cat.id,
                    revision_number=latest_rev.revision_number + 1,
                    state="published",
                    source_document_ids=list(latest_rev.source_document_ids or []),
                    content_hash=canonical_context_hash({}),
                    published_at=utcnow(),
                    created_at=utcnow(),
                    updated_at=utcnow(),
                )
                db.add(new_rev)
                db.flush()

                # 1. Copy forward packages
                pkg_map: dict[str, str] = {}
                for pkg in db.scalars(
                    select(BenefitPackage).where(BenefitPackage.catalog_revision_id == latest_rev.id)
                ).all():
                    new_pkg_id = new_id()
                    pkg_map[pkg.id] = new_pkg_id
                    db.add(BenefitPackage(
                        id=new_pkg_id,
                        catalog_revision_id=new_rev.id,
                        package_key=pkg.package_key,
                        name=pkg.name,
                        package_kind=pkg.package_kind,
                        sort_order=pkg.sort_order,
                        status=pkg.status,
                    ))
                db.flush()

                # 2. Copy forward offerings with updated towing description
                off_map: dict[str, str] = {}
                for off in current_offerings:
                    new_off_id = new_id()
                    off_map[off.id] = new_off_id
                    
                    off_desc = new_desc if off.concept_id == towing_concept.id else off.description_override
                    off_disp = new_disp if (off.concept_id == towing_concept.id and new_disp) else off.display_value

                    applies_id = pkg_map.get(off.applies_to_id) if off.applies_to_id else None
                    applies_type = off.applies_to_type
                    if applies_id is None:
                        applies_type = None
                    elif applies_type is None:
                        applies_id = None

                    db.add(CatalogOffering(
                        id=new_off_id,
                        catalog_revision_id=new_rev.id,
                        offering_key=off.offering_key,
                        concept_id=off.concept_id,
                        offering_kind=off.offering_kind,
                        applies_to_type=applies_type,
                        applies_to_id=applies_id,
                        role=off.role,
                        label_override=off.label_override,
                        description_override=off_desc,
                        typed_value=off.typed_value,
                        display_value=off_disp,
                        optional_price=off.optional_price,
                        source_document_id=off.source_document_id,
                        source_citation=off.source_citation,
                        source_aliases=list(off.source_aliases or []),
                        presentation_facet_ids=list(off.presentation_facet_ids or []),
                        sort_order=off.sort_order,
                        status=off.status,
                    ))
                db.flush()

                # 3. Copy forward package plans & items
                plan_map: dict[str, str] = {}
                for plan in db.scalars(
                    select(BenefitPackagePlan).where(BenefitPackagePlan.package_id.in_(list(pkg_map.keys())))
                ).all():
                    new_plan_id = new_id()
                    plan_map[plan.id] = new_plan_id
                    db.add(BenefitPackagePlan(
                        id=new_plan_id,
                        package_id=pkg_map[plan.package_id],
                        plan_key=plan.plan_key,
                        name=plan.name,
                        sort_order=plan.sort_order,
                        status=plan.status,
                    ))
                db.flush()

                for item in db.scalars(
                    select(BenefitPackagePlanItem).where(BenefitPackagePlanItem.offering_id.in_(list(off_map.keys())))
                ).all():
                    if item.plan_id in plan_map:
                        db.add(BenefitPackagePlanItem(
                            id=new_id(),
                            plan_id=plan_map[item.plan_id],
                            offering_id=off_map[item.offering_id],
                            typed_value_override=item.typed_value_override,
                            sort_order=item.sort_order,
                        ))
                db.flush()

                # 4. Copy forward relations
                for rel in db.scalars(
                    select(BenefitRelation).where(BenefitRelation.from_offering_id.in_(list(off_map.keys())))
                ).all():
                    if rel.to_offering_id in off_map:
                        db.add(BenefitRelation(
                            id=new_id(),
                            from_offering_id=off_map[rel.from_offering_id],
                            to_offering_id=off_map[rel.to_offering_id],
                            relation_kind=rel.relation_kind,
                            branch_key=rel.branch_key,
                            sort_order=rel.sort_order,
                        ))

                if cat.package_id and cat.package_id in pkg_map:
                    cat.package_id = pkg_map[cat.package_id]
                cat.revision = new_rev.revision_number
                db.commit()
                updated_catalogs_count += 1
                print(f"Forked new published revision {new_rev.revision_number} for '{cat.name}' with towing: '{new_desc}'")

        print(f"\nSuccessfully updated {updated_catalogs_count} catalogs across all AmAssurance vehicle/engine variations!")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    update_amassurance()
