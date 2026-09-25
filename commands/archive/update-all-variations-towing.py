"""Comprehensive update of AmAssurance Towing & Unlimited Towing across all variations.

Vehicles:
  - Private Car (ICE & EV)
  - Motorcycle (ICE & EV)
  - Commercial Vehicle / Lorry (ICE & EV)
  - Commercial Car & Commercial Motorcycle

Tiers:
  - auto365 Comprehensive Lite: 50 km included
  - auto365 Comprehensive Plus: 100 km included
  - auto365 Comprehensive Premier: 365 km included
  - Other Comprehensive (EV Car, EV Motor, Lorry, Despatch, etc.): specific towing limits
  - ALL Comprehensive policies: auto-assistance (Unlimited Towing Upgrade) available as addon_option.

Condition:
  - Trigger: auto-assistance (Unlimited Towing Upgrade)
  - Target: towing (Emergency Towing Assistance)
  - Action: hide_target
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
    CoverageType,
    VehicleCategory,
    new_id,
    utcnow,
)
from app.services.business_setup_service import get_active_benefit_profile
from app.rendering.render_context import canonical_context_hash
from sqlalchemy import select


def update_all_amassurance_variations():
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
        auto_assistance_concept = concepts.get("auto-assistance")

        if not towing_concept or not auto_assistance_concept:
            print("Towing or auto-assistance concept not found!")
            return

        print(f"Towing Concept: {towing_concept.id} ({towing_concept.label})")
        print(f"Auto Assistance Concept: {auto_assistance_concept.id} ({auto_assistance_concept.label})")

        # -------------------------------------------------------------
        # 1. Condition: Unlimited Towing Hides Default Towing
        # -------------------------------------------------------------
        cond = db.scalar(
            select(CompanyBenefitCondition).where(
                CompanyBenefitCondition.company_id == am.id,
                CompanyBenefitCondition.profile_id == active_prof.id,
                CompanyBenefitCondition.trigger_concept_id == auto_assistance_concept.id,
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
                trigger_concept_id=auto_assistance_concept.id,
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
        # 2. Identify All Relevant Catalogs Across Variations
        # -------------------------------------------------------------
        catalogs = db.scalars(
            select(BenefitCatalog).where(BenefitCatalog.company_id == am.id)
        ).all()

        target_configs: dict[str, dict] = {}
        for cat in catalogs:
            name_lower = cat.name.lower()
            cov = db.get(CoverageType, cat.coverage_type_id) if cat.coverage_type_id else None
            vc = db.get(VehicleCategory, cat.vehicle_category_id) if cat.vehicle_category_id else None
            cov_key = cov.coverage_key if cov else ""
            veh_key = vc.category_key if vc else ""
            eng = cat.engine_type or "ice"

            # Determine Towing text and display value based on variation
            towing_desc = None
            towing_disp = None
            include_towing = False
            include_upgrade = False

            if "lite" in name_lower and ("auto365" in name_lower or "comprehensive" in name_lower):
                towing_desc = "24/7 emergency accident and breakdown towing assistance up to 50 km."
                towing_disp = "50 km"
                include_towing = True
                include_upgrade = True
            elif "plus" in name_lower and ("auto365" in name_lower or "comprehensive" in name_lower):
                towing_desc = "24/7 emergency accident and breakdown towing assistance up to 100 km."
                towing_disp = "100 km"
                include_towing = True
                include_upgrade = True
            elif "premier" in name_lower and ("auto365" in name_lower or "comprehensive" in name_lower):
                towing_desc = "24/7 emergency accident and breakdown towing assistance up to 365 km."
                towing_disp = "365 km"
                include_towing = True
                include_upgrade = True
            elif "all-inclusive" in name_lower:
                towing_desc = "Accident emergency towing assistance up to RM200 to nearest panel repairer."
                towing_disp = "RM 200"
                include_towing = True
                include_upgrade = True
            elif eng == "ev" and "car" in name_lower and "comprehensive" in name_lower:
                towing_desc = "Emergency 24/7 towing and flatbed assistance for EV breakdown or battery depletion up to 100 km."
                towing_disp = "100 km"
                include_towing = True
                include_upgrade = True
            elif eng == "ev" and "motorcycle" in name_lower and "comprehensive" in name_lower:
                towing_desc = "Emergency 24/7 towing and flatbed assistance for EV breakdown or battery depletion up to RM 100."
                towing_disp = "RM 100"
                include_towing = True
                include_upgrade = True
            elif eng == "ev" and "commercial" in name_lower and "comprehensive" in name_lower:
                towing_desc = "Emergency 24/7 commercial flatbed towing and breakdown assistance up to policy limit."
                towing_disp = "Policy Limit"
                include_towing = True
                include_upgrade = True
            elif "motorcycle" in name_lower and (cov_key == "comprehensive" or "comprehensive" in name_lower):
                towing_desc = "24/7 emergency accident towing assistance up to RM 50."
                towing_disp = "RM 50"
                include_towing = True
                include_upgrade = True
            elif "commercial car" in name_lower and (cov_key == "comprehensive" or "comprehensive" in name_lower):
                towing_desc = "24/7 commercial car emergency accident and breakdown towing assistance up to 100 km."
                towing_disp = "100 km"
                include_towing = True
                include_upgrade = True
            elif ("lorry" in name_lower or "commercial" in name_lower) and (cov_key == "comprehensive" or "comprehensive" in name_lower):
                towing_desc = "24/7 commercial vehicle emergency breakdown and accident towing up to policy limit."
                towing_disp = "Policy Limit"
                include_towing = True
                include_upgrade = True
            elif "private car" in name_lower and (cov_key == "comprehensive" or "comprehensive" in name_lower):
                towing_desc = "24/7 emergency accident and breakdown towing assistance up to 100 km."
                towing_disp = "100 km"
                include_towing = True
                include_upgrade = True

            if include_towing or include_upgrade:
                target_configs[cat.id] = {
                    "towing_desc": towing_desc,
                    "towing_disp": towing_disp,
                    "include_towing": include_towing,
                    "include_upgrade": include_upgrade,
                }

        print(f"Total target variation catalogs: {len(target_configs)}")

        updated_count = 0
        for cat_id, cfg in target_configs.items():
            cat = db.get(BenefitCatalog, cat_id)
            if not cat:
                continue

            latest_rev = db.scalar(
                select(BenefitCatalogRevision)
                .where(BenefitCatalogRevision.catalog_id == cat.id)
                .order_by(BenefitCatalogRevision.revision_number.desc())
            )
            if not latest_rev:
                continue

            current_offerings = list(
                db.scalars(
                    select(CatalogOffering).where(CatalogOffering.catalog_revision_id == latest_rev.id)
                ).all()
            )

            # Check if towing already present
            existing_towing = next((o for o in current_offerings if o.concept_id == towing_concept.id), None)
            existing_upgrade = next((o for o in current_offerings if o.concept_id == auto_assistance_concept.id), None)

            if existing_towing and existing_towing.description_override == cfg["towing_desc"] and existing_upgrade:
                continue

            # Always fork a new revision from latest revision to respect DB immutability triggers
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

            # 1. Packages
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

            # 2. Offerings
            off_map: dict[str, str] = {}
            towing_added = False
            upgrade_added = False

            for off in current_offerings:
                new_off_id = new_id()
                off_map[off.id] = new_off_id

                off_desc = off.description_override
                off_disp = off.display_value
                off_role = off.role
                off_kind = off.offering_kind

                if off.concept_id == towing_concept.id:
                    towing_added = True
                    if cfg["include_towing"]:
                        off_desc = cfg["towing_desc"]
                        off_disp = cfg["towing_disp"]
                        off_role = "included"
                        off_kind = "base"

                if off.concept_id == auto_assistance_concept.id:
                    upgrade_added = True

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
                    offering_kind=off_kind,
                    applies_to_type=applies_type,
                    applies_to_id=applies_id,
                    role=off_role,
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

            # Add Towing if it wasn't in original offerings
            if cfg["include_towing"] and not towing_added:
                db.add(CatalogOffering(
                    id=new_id(),
                    catalog_revision_id=new_rev.id,
                    offering_key=f"offering_{cat.name[:10].lower().replace(' ', '_')}_towing_v{new_rev.revision_number}",
                    concept_id=towing_concept.id,
                    offering_kind="base",
                    role="included",
                    label_override="Emergency Towing Assistance",
                    description_override=cfg["towing_desc"],
                    display_value=cfg["towing_disp"],
                    sort_order=10,
                    status="active",
                ))

            # Add Auto Assistance (Unlimited Towing Upgrade) as addon_option
            if cfg["include_upgrade"] and not upgrade_added:
                db.add(CatalogOffering(
                    id=new_id(),
                    catalog_revision_id=new_rev.id,
                    offering_key=f"offering_{cat.name[:10].lower().replace(' ', '_')}_auto_assistance_v{new_rev.revision_number}",
                    concept_id=auto_assistance_concept.id,
                    offering_kind="optional",
                    role="addon_option",
                    label_override="Unlimited Towing Upgrade",
                    description_override="24/7 unlimited distance emergency towing assistance to any preferred workshop or repairer nationwide.",
                    display_value="Unlimited",
                    sort_order=40,
                    status="active",
                ))

            db.flush()

            # 3. Plans & Items
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

            # 4. Relations
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
            cat.status = "published"
            db.commit()
            updated_count += 1
            print(f"Forked new published revision {new_rev.revision_number} for '{cat.name}' (Towing: {cfg['towing_disp']}, Addon: Unlimited Towing)")

        print(f"\nSuccessfully configured all {updated_count} AmAssurance catalogs across all variations!")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    update_all_amassurance_variations()
