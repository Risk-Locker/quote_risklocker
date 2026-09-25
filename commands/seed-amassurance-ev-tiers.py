"""Seed AmAssurance EV 3-Tier auto365 Package System.

Creates/updates:
1. Product tiers (ev-lite, ev-plus, ev-premier) for AmAssurance EV Car Comprehensive.
2. 3 Catalogs (auto365 Comprehensive Lite, Plus, Premier) with engine_type='ev'.
3. 3 BenefitPackages linked to each catalog.
4. Offerings cloned from corresponding ICE auto365 tiers + 3 EV riders.
"""

import sys
from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

sys.path.insert(0, "backend")
from app.db.session import SessionLocal
from app.models.tables import (
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    BenefitPackage,
    CatalogOffering,
    InsuranceCompany,
    InsuranceProduct,
    InsuranceProductTier,
)
from sqlalchemy import select


def utcnow():
    return datetime.now(timezone.utc)


def new_id():
    return str(uuid4())


def main():
    db = SessionLocal()
    try:
        # 1. Look up AmAssurance
        company = db.scalar(
            select(InsuranceCompany).where(
                (InsuranceCompany.id == "f57e3c2e-5131-473a-bda3-eb28ab9450e5")
                | (InsuranceCompany.slug == "amassurance")
            )
        )
        if not company:
            print("AmAssurance company not found")
            return

        print(f"Company: {company.name} ({company.id})")

        # 2. Look up EV Private Car Comprehensive Product
        ev_product = db.scalar(
            select(InsuranceProduct).where(
                InsuranceProduct.company_id == company.id,
                InsuranceProduct.product_key == "ev-amassurance-car-comprehensive",
            )
        )
        if not ev_product:
            ev_product = db.scalar(
                select(InsuranceProduct).where(
                    InsuranceProduct.id == "087d9002-db55-4625-902b-a09db7ef05f7"
                )
            )
        if not ev_product:
            print("EV product not found")
            return

        print(f"EV Product: {ev_product.name} ({ev_product.id})")

        # 3. Look up ICE Product & Catalogs to copy benefits from
        ice_catalogs = {
            "lite": db.get(BenefitCatalog, "d3241bc8-160e-4aba-83bb-c88aec3a6758"),
            "plus": db.get(BenefitCatalog, "7ec7079a-ab2d-4984-97cc-bcd500c2679f"),
            "premier": db.get(BenefitCatalog, "84199f87-a803-4670-904c-3363829cdbad"),
        }

        # 4. Look up EV-specific concepts
        ev_concepts = {}
        for ckey in ["ev-wall-charger", "ev-battery-depletion-towing", "ev-home-charger-liability"]:
            concept = db.scalar(select(BenefitConcept).where(BenefitConcept.concept_key == ckey))
            if concept:
                ev_concepts[ckey] = concept
            else:
                print(f"Warning: concept {ckey} not found")

        # Tier definitions
        tier_defs = [
            {
                "tier_key": "ev-lite",
                "name": "auto365 Comprehensive Lite",
                "cat_name": "auto365 Comprehensive Lite (EV)",
                "sort_order": 1,
                "ice_key": "lite",
                "existing_cat_id": "e3a78da7-613d-4ed6-b846-4ecdc19e0380",  # Repurpose existing
            },
            {
                "tier_key": "ev-plus",
                "name": "auto365 Comprehensive Plus",
                "cat_name": "auto365 Comprehensive Plus (EV)",
                "sort_order": 2,
                "ice_key": "plus",
                "existing_cat_id": None,
            },
            {
                "tier_key": "ev-premier",
                "name": "auto365 Comprehensive Premier",
                "cat_name": "auto365 Comprehensive Premier (EV)",
                "sort_order": 3,
                "ice_key": "premier",
                "existing_cat_id": None,
            },
        ]

        car_veh_id = "b1111111-0000-4000-8000-000000000001"
        comp_cov_id = "d1111111-0000-4000-8000-000000000001"
        private_seg_id = "a1111111-0000-4000-8000-000000000001"

        created_or_updated_catalogs = []

        for tdef in tier_defs:
            print(f"\n--- Setting up {tdef['name']} (Tier {tdef['sort_order']}) ---")

            # 4a. InsuranceProductTier
            tier = db.scalar(
                select(InsuranceProductTier).where(
                    InsuranceProductTier.product_id == ev_product.id,
                    InsuranceProductTier.tier_key == tdef["tier_key"],
                )
            )
            if not tier:
                tier = InsuranceProductTier(
                    id=new_id(),
                    product_id=ev_product.id,
                    tier_key=tdef["tier_key"],
                    name=tdef["name"],
                )
                db.add(tier)
                db.flush()
                print(f"Created Product Tier: {tier.name} ({tier.id})")
            else:
                tier.name = tdef["name"]
                db.flush()
                print(f"Existing Product Tier: {tier.name} ({tier.id})")

            # 4b. Catalog
            cat = None
            if tdef["existing_cat_id"]:
                cat = db.get(BenefitCatalog, tdef["existing_cat_id"])

            if not cat:
                cat = db.scalar(
                    select(BenefitCatalog).where(
                        BenefitCatalog.company_id == company.id,
                        BenefitCatalog.product_id == ev_product.id,
                        BenefitCatalog.tier_id == tier.id,
                    )
                )

            if not cat:
                cat = BenefitCatalog(
                    id=new_id(),
                    company_id=company.id,
                    product_id=ev_product.id,
                    tier_id=tier.id,
                    segment_id=private_seg_id,
                    vehicle_category_id=car_veh_id,
                    coverage_type_id=comp_cov_id,
                    engine_type="ev",
                    name=tdef["cat_name"],
                    status="published",
                    revision=1,
                )
                db.add(cat)
                db.flush()
                print(f"Created Catalog: {cat.name} ({cat.id})")
            else:
                cat.name = tdef["cat_name"]
                cat.tier_id = tier.id
                cat.product_id = ev_product.id
                cat.segment_id = private_seg_id
                cat.vehicle_category_id = car_veh_id
                cat.coverage_type_id = comp_cov_id
                cat.engine_type = "ev"
                cat.status = "published"
                db.flush()
                print(f"Updated Catalog: {cat.name} ({cat.id})")

            # 4c. Latest Revision
            latest_rev = db.scalar(
                select(BenefitCatalogRevision)
                .where(BenefitCatalogRevision.catalog_id == cat.id)
                .order_by(BenefitCatalogRevision.revision_number.desc())
            )
            if not latest_rev:
                latest_rev = BenefitCatalogRevision(
                    id=new_id(),
                    catalog_id=cat.id,
                    revision_number=1,
                    state="published",
                    content_hash=sha256(f"{cat.id}:1:{utcnow()}".encode()).hexdigest(),
                    published_at=utcnow(),
                )
                db.add(latest_rev)
                db.flush()
                print(f"Created Revision: {latest_rev.revision_number} ({latest_rev.id})")
            else:
                latest_rev.state = "published"
                db.flush()
                print(f"Using Revision: {latest_rev.revision_number} ({latest_rev.id})")

            # 4d. BenefitPackage (comprehensive)
            pkg = db.scalar(
                select(BenefitPackage).where(
                    BenefitPackage.catalog_revision_id == latest_rev.id,
                    BenefitPackage.package_kind == "comprehensive",
                )
            )
            if not pkg:
                pkg = BenefitPackage(
                    id=new_id(),
                    catalog_revision_id=latest_rev.id,
                    package_key=tdef["tier_key"],
                    name=tdef["name"],
                    package_kind="comprehensive",
                    sort_order=tdef["sort_order"],
                    status="active",
                )
                db.add(pkg)
                db.flush()
                print(f"Created Comprehensive Package: {pkg.name} ({pkg.id})")
            else:
                pkg.name = tdef["name"]
                pkg.sort_order = tdef["sort_order"]
                pkg.package_key = tdef["tier_key"]
                pkg.status = "active"
                db.flush()
                print(f"Updated Comprehensive Package: {pkg.name} ({pkg.id})")

            # Also create addon_bundle package if not present
            bundle_pkg = db.scalar(
                select(BenefitPackage).where(
                    BenefitPackage.catalog_revision_id == latest_rev.id,
                    BenefitPackage.package_kind == "addon_bundle",
                )
            )
            if not bundle_pkg:
                bundle_pkg = BenefitPackage(
                    id=new_id(),
                    catalog_revision_id=latest_rev.id,
                    package_key=f"{tdef['tier_key']}-pack",
                    name="auto365 Protection Pack",
                    package_kind="addon_bundle",
                    sort_order=1,
                    status="active",
                )
                db.add(bundle_pkg)
                db.flush()
                print(f"Created Addon Bundle Package: {bundle_pkg.name} ({bundle_pkg.id})")

            # Link package_id to catalog
            cat.package_id = pkg.id
            db.flush()

            # 4e. Clone offerings from corresponding ICE tier
            ice_cat = ice_catalogs.get(tdef["ice_key"])
            ice_offerings = []
            if ice_cat:
                ice_rev = db.scalar(
                    select(BenefitCatalogRevision)
                    .where(BenefitCatalogRevision.catalog_id == ice_cat.id)
                    .order_by(BenefitCatalogRevision.revision_number.desc())
                )
                if ice_rev:
                    ice_offerings = list(
                        db.scalars(
                            select(CatalogOffering).where(
                                CatalogOffering.catalog_revision_id == ice_rev.id
                            )
                        ).all()
                    )
            print(f"Found {len(ice_offerings)} offerings in ICE {tdef['ice_key']}")

            # Existing offerings in this EV revision
            existing_ev_offs = {
                o.concept_id: o
                for o in db.scalars(
                    select(CatalogOffering).where(
                        CatalogOffering.catalog_revision_id == latest_rev.id
                    )
                ).all()
            }

            sort_counter = 1
            # First, replicate/update ICE offerings
            for ice_off in ice_offerings:
                if ice_off.concept_id in existing_ev_offs:
                    # Update role & details to match ICE
                    ev_off = existing_ev_offs[ice_off.concept_id]
                    ev_off.role = ice_off.role
                    ev_off.offering_kind = ice_off.offering_kind
                    ev_off.label_override = ice_off.label_override
                    ev_off.description_override = ice_off.description_override
                    ev_off.optional_price = ice_off.optional_price
                    ev_off.sort_order = sort_counter
                    ev_off.applies_to_type = "package"
                    ev_off.applies_to_id = pkg.id
                    ev_off.status = "active"
                else:
                    ev_off = CatalogOffering(
                        id=new_id(),
                        catalog_revision_id=latest_rev.id,
                        offering_key=f"ev-{tdef['tier_key']}-{ice_off.offering_key}",
                        concept_id=ice_off.concept_id,
                        applies_to_type="package",
                        applies_to_id=pkg.id,
                        role=ice_off.role,
                        offering_kind=ice_off.offering_kind,
                        label_override=ice_off.label_override,
                        description_override=ice_off.description_override,
                        optional_price=ice_off.optional_price,
                        sort_order=sort_counter,
                        status="active",
                    )
                    db.add(ev_off)
                    existing_ev_offs[ice_off.concept_id] = ev_off
                sort_counter += 1

            # Second, append EV-specific riders as addon_option
            for ev_ckey, ev_concept in ev_concepts.items():
                if ev_concept.id in existing_ev_offs:
                    ev_off = existing_ev_offs[ev_concept.id]
                    ev_off.role = "addon_option"
                    ev_off.offering_kind = "optional"
                    ev_off.applies_to_type = "package"
                    ev_off.applies_to_id = pkg.id
                    ev_off.status = "active"
                else:
                    ev_off = CatalogOffering(
                        id=new_id(),
                        catalog_revision_id=latest_rev.id,
                        offering_key=f"ev-{tdef['tier_key']}-{ev_ckey}",
                        concept_id=ev_concept.id,
                        applies_to_type="package",
                        applies_to_id=pkg.id,
                        role="addon_option",
                        offering_kind="optional",
                        label_override=ev_concept.label,
                        description_override=f"Coverage for {ev_concept.label.lower()}",
                        optional_price=None,
                        sort_order=sort_counter,
                        status="active",
                    )
                    db.add(ev_off)
                    existing_ev_offs[ev_concept.id] = ev_off
                sort_counter += 1

            db.flush()
            total_offs = db.scalar(
                select(CatalogOffering).where(CatalogOffering.catalog_revision_id == latest_rev.id)
            )
            print(f"Total offerings for {tdef['name']} now: {len(existing_ev_offs)}")
            created_or_updated_catalogs.append(cat)

        db.commit()
        print("\n[SUCCESS] Successfully seeded AmAssurance EV 3-tier auto365 package system!")
        for c in created_or_updated_catalogs:
            print(f"  - Catalog: {c.name} (id={c.id}, pkg_id={c.package_id})")

    except Exception as e:
        db.rollback()
        print(f"Error seeding EV tiers: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
