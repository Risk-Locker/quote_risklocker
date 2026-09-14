"""Seed comprehensive EV catalogs across all 7 insurers and de-duplicate Berjaya Sompo products.

Target Profile: 'Main Unified Baseline (14/09/2026) (v2)' (94f56a3a-3ea1-4532-8ae7-34dda7c60a62)
"""

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from hashlib import sha256
from sqlalchemy import select, update
from app.db.session import SessionLocal
from app.models.tables import (
    InsuranceCompany,
    InsuranceProduct,
    BenefitCatalog,
    BenefitCatalogRevision,
    CatalogOffering,
    BenefitConcept,
    CompanyBenefitConfig,
    VehicleCategory,
    CoverageType,
    QuotationDraft,
    new_id,
    utcnow,
)

TARGET_PROFILE_ID = "94f56a3a-3ea1-4532-8ae7-34dda7c60a62"

VEHICLE_CAT_CAR = "b1111111-0000-4000-8000-000000000001"
VEHICLE_CAT_BIKE = "b1111111-0000-4000-8000-000000000002"
VEHICLE_CAT_COMM = "b1111111-0000-4000-8000-000000000003"

COV_COMPREHENSIVE = "d1111111-0000-4000-8000-000000000001"
COV_TPFT = "d1111111-0000-4000-8000-000000000002"
COV_TPO = "d1111111-0000-4000-8000-000000000003"

# Car-only concepts (exclude from motorcycle)
CAR_ONLY_CONCEPTS = {
    "windscreen", "child-car-seat", "child-seat", "car-detailing-cleanup",
    "tuition-purpose", "repair-allowance", "repair-allowance-cart",
}

# Own-Damage only concepts (exclude from TPFT and TPO)
OWN_DAMAGE_CONCEPTS = {
    "repair-allowance", "repair-allowance-cart", "betterment-protection",
    "repaint-spray-paint", "vehicle-respray", "car-detailing-cleanup",
    "windscreen", "key-replacement", "gas-conversion-kit", "tuition-purpose",
    "vehicle-accessories",
}

# Third-party only concepts (allowed in TPO)
TPO_ALLOWED_CONCEPTS = {
    "legal-liability-to-passengers", "legal-liability-of-passengers",
    "legal-defense-costs", "personal-accident", "accidental-death",
    "roadside-assistance", "emergency-towing", "towing-assistance",
    "all-drivers",
}

DEFAULT_INCLUDED_CONCEPTS = {
    "roadside-assistance", "emergency-towing", "towing-assistance",
    "panel-workmanship-warranty", "repair-workmanship-warranty",
    "legal-defense-costs",
}

SOMPO_COMPLIMENTARY_CONCEPTS = {
    "special-perils", "all-drivers", "roadside-assistance",
    "repair-workmanship-warranty", "emergency-towing",
}

def parse_cost_to_dict(cost_val: any) -> dict | None:
    if not cost_val:
        return None
    if isinstance(cost_val, dict):
        return cost_val
    cost_str = str(cost_val).strip()
    if "%" in cost_str:
        return {"rate": cost_str, "currency": "MYR"}
    clean_num = cost_str.replace("RM", "").replace(",", "").strip()
    try:
        val = float(clean_num)
        return {"amount": val, "currency": "MYR"}
    except ValueError:
        return {"raw": cost_str, "currency": "MYR"}


def dedup_berjaya_sompo_products(db) -> None:
    print("=== Consolidating Berjaya Sompo Products ===")
    sompo = db.scalar(select(InsuranceCompany).where(InsuranceCompany.slug == "berjaya-sompo"))
    if not sompo:
        print("Berjaya Sompo not found!")
        return

    # Products:
    # 1. SOMPO Motor (Private Car Non-Tariff) -> rename to SOMPO Motor (Private Car)
    main_car_prod = db.scalar(
        select(InsuranceProduct).where(
            InsuranceProduct.company_id == sompo.id,
            InsuranceProduct.product_key == "sompo-motor-private-car",
        )
    )
    if main_car_prod:
        main_car_prod.name = "SOMPO Motor (Private Car)"
        print(f"Renamed primary car product {main_car_prod.id} to '{main_car_prod.name}'")

    # Stale/duplicate products:
    dup_keys = ["sompo-motor-comprehensive", "berjayasompo-private-car"]
    dup_prods = db.scalars(
        select(InsuranceProduct).where(
            InsuranceProduct.company_id == sompo.id,
            InsuranceProduct.product_key.in_(dup_keys),
        )
    ).all()

    for dup in dup_prods:
        print(f"Archiving duplicate product: {dup.name} (id={dup.id}, key={dup.product_key})")
        dup.status = "archived"
        # Repin any drafts that used this product
        if main_car_prod:
            db.execute(
                update(QuotationDraft)
                .where(QuotationDraft.product_id == dup.id)
                .values(product_id=main_car_prod.id)
            )

    db.flush()
    print("Berjaya Sompo products successfully consolidated.")


def seed_ev_catalogs_all_insurers(db) -> None:
    print("\n=== Seeding EV Catalogs across all 7 Insurers ===")
    companies = db.scalars(select(InsuranceCompany).order_by(InsuranceCompany.name)).all()

    # Load all concepts
    all_concepts = {c.id: c for c in db.scalars(select(BenefitConcept)).all()}
    concept_by_key = {c.concept_key: c for c in all_concepts.values()}

    # Check dedicated EV concepts
    ev_wall_charger = concept_by_key.get("ev-wall-charger")
    ev_battery_towing = concept_by_key.get("ev-battery-depletion-towing")
    ev_charger_liability = concept_by_key.get("ev-home-charger-liability")

    cat_matrix = [
        (VEHICLE_CAT_CAR, "Car", "car", "Private Car"),
        (VEHICLE_CAT_BIKE, "Motorcycle", "motorcycle", "Motorcycle"),
        (VEHICLE_CAT_COMM, "Commercial Vehicle", "commercial", "Commercial Vehicle"),
    ]

    cov_matrix = [
        (COV_COMPREHENSIVE, "Comprehensive", "comprehensive"),
        (COV_TPFT, "Third Party Fire & Theft", "tpft"),
        (COV_TPO, "Third Party", "tpo"),
    ]

    for company in companies:
        print(f"\nProcessing Insurer: {company.name} (slug={company.slug})")

        # Load active profile configs for this company
        configs = list(
            db.scalars(
                select(CompanyBenefitConfig).where(
                    CompanyBenefitConfig.company_id == company.id,
                    CompanyBenefitConfig.profile_id == TARGET_PROFILE_ID,
                    CompanyBenefitConfig.is_enabled.is_(True),
                )
            ).all()
        )
        print(f"  Found {len(configs)} enabled benefits in active profile.")

        for vcat_id, vcat_name, vcat_slug, vcat_display in cat_matrix:
            for cov_id, cov_name, cov_slug in cov_matrix:
                prod_key = f"ev-{company.slug}-{vcat_slug}-{cov_slug}"
                prod_name = f"{company.name} {vcat_display} {cov_name} (EV)"

                ev_product = db.scalar(
                    select(InsuranceProduct).where(
                        InsuranceProduct.company_id == company.id,
                        InsuranceProduct.product_key == prod_key,
                    )
                )
                if not ev_product and cov_slug == "comprehensive":
                    legacy_keys = [
                        f"ev-{company.slug}-{vcat_slug}",
                        f"ev-{company.slug}-{vcat_slug}-comprehensive",
                    ]
                    ev_product = db.scalar(
                        select(InsuranceProduct).where(
                            InsuranceProduct.company_id == company.id,
                            InsuranceProduct.product_key.in_(legacy_keys),
                        )
                    )

                if not ev_product:
                    ev_product = InsuranceProduct(
                        id=new_id(),
                        company_id=company.id,
                        product_key=prod_key,
                        name=prod_name,
                        status="active",
                    )
                    db.add(ev_product)
                    db.flush()
                    print(f"  [NEW PRODUCT] {ev_product.name} (id={ev_product.id})")
                else:
                    ev_product.name = prod_name
                    ev_product.status = "active"

                cat_name = f"{company.name} {vcat_display} {cov_name} (EV)"

                # Look for existing EV catalog for this exact product
                ev_catalog = db.scalar(
                    select(BenefitCatalog).where(
                        BenefitCatalog.company_id == company.id,
                        BenefitCatalog.product_id == ev_product.id,
                    )
                )

                if not ev_catalog:
                    ev_catalog = BenefitCatalog(
                        id=new_id(),
                        company_id=company.id,
                        product_id=ev_product.id,
                        tier_id=None,
                        package_id=None,
                        segment_id=None,
                        vehicle_category_id=vcat_id,
                        vehicle_subcategory_id=None,
                        coverage_type_id=cov_id,
                        engine_type="ev",
                        name=cat_name,
                        revision=1,
                        status="published",
                    )
                    db.add(ev_catalog)
                    db.flush()
                    print(f"    [NEW CATALOG] {cat_name} (id={ev_catalog.id})")
                else:
                    ev_catalog.product_id = ev_product.id
                    ev_catalog.name = cat_name
                    ev_catalog.status = "published"

                # Find latest revision or create new revision
                latest_rev = db.scalar(
                    select(BenefitCatalogRevision)
                    .where(BenefitCatalogRevision.catalog_id == ev_catalog.id)
                    .order_by(BenefitCatalogRevision.revision_number.desc())
                )

                next_rev_num = (latest_rev.revision_number + 1) if latest_rev else 1
                content_hash = sha256(f"{ev_catalog.id}:{next_rev_num}:{utcnow()}".encode()).hexdigest()

                new_rev = BenefitCatalogRevision(
                    id=new_id(),
                    catalog_id=ev_catalog.id,
                    revision_number=next_rev_num,
                    state="published",
                    content_hash=content_hash,
                    published_at=utcnow(),
                )
                db.add(new_rev)
                db.flush()

                # Build offerings
                sort_counter = 1
                offering_keys_added = set()
                offering_concept_ids_added = set()

                for cfg in configs:
                    concept = all_concepts.get(cfg.concept_id)
                    if not concept:
                        continue

                    ckey = concept.concept_key

                    # Filter: Motorcycle
                    if vcat_id == VEHICLE_CAT_BIKE and ckey in CAR_ONLY_CONCEPTS:
                        continue

                    # Filter: TPFT
                    if cov_id == COV_TPFT and ckey in OWN_DAMAGE_CONCEPTS:
                        continue

                    # Filter: TPO
                    if cov_id == COV_TPO and ckey not in TPO_ALLOWED_CONCEPTS:
                        continue

                    # Determine offering kind & cost
                    is_sompo = company.slug == "berjaya-sompo"
                    if is_sompo and ckey in SOMPO_COMPLIMENTARY_CONCEPTS:
                        offering_kind = "base"
                        cost_dict = None
                    elif ckey in DEFAULT_INCLUDED_CONCEPTS:
                        offering_kind = "base"
                        cost_dict = None
                    else:
                        offering_kind = "optional"
                        cost_dict = parse_cost_to_dict(cfg.baseline_cost)

                    desc = cfg.baseline_description or concept.description or ""
                    if len(desc) > 80:
                        desc = desc[:77] + "..."

                    off_key = f"ev-{cov_slug}-{ckey}"
                    if off_key in offering_keys_added or concept.id in offering_concept_ids_added:
                        continue
                    offering_keys_added.add(off_key)
                    offering_concept_ids_added.add(concept.id)

                    offering = CatalogOffering(
                        id=new_id(),
                        catalog_revision_id=new_rev.id,
                        offering_key=off_key,
                        concept_id=concept.id,
                        offering_kind=offering_kind,
                        role="included" if offering_kind == "base" else "addon_option",
                        label_override=concept.label,
                        description_override=desc,
                        typed_value=None,
                        display_value=None,
                        optional_price=cost_dict,
                        presentation_facet_ids=[],
                        sort_order=sort_counter,
                        status="active",
                    )
                    db.add(offering)
                    sort_counter += 1

                # Dedicated EV Add-ons (Car & Commercial only, Comprehensive & TPFT)
                if vcat_id in [VEHICLE_CAT_CAR, VEHICLE_CAT_COMM]:
                    # 1. EV Wall Charger
                    if ev_wall_charger and ev_wall_charger.id not in offering_concept_ids_added:
                        off_key = f"ev-{cov_slug}-ev-wall-charger"
                        if off_key not in offering_keys_added:
                            offering_keys_added.add(off_key)
                            offering_concept_ids_added.add(ev_wall_charger.id)
                            db.add(
                                CatalogOffering(
                                    id=new_id(),
                                    catalog_revision_id=new_rev.id,
                                    offering_key=off_key,
                                    concept_id=ev_wall_charger.id,
                                    offering_kind="optional",
                                    role="addon_option",
                                    label_override="EV Wall Charger Cover",
                                    description_override="Covers accidental damage or theft of home EV wall charger up to RM 12,000.",
                                    typed_value={"type": "money", "value": 12000, "currency": "MYR"},
                                    display_value="RM 12,000",
                                    optional_price={"amount": 120.0, "currency": "MYR"},
                                    presentation_facet_ids=[],
                                    sort_order=sort_counter,
                                    status="active",
                                )
                            )
                            sort_counter += 1

                    # 2. EV Battery Towing
                    if ev_battery_towing and ev_battery_towing.id not in offering_concept_ids_added:
                        off_key = f"ev-{cov_slug}-ev-battery-towing"
                        if off_key not in offering_keys_added:
                            offering_keys_added.add(off_key)
                            offering_concept_ids_added.add(ev_battery_towing.id)
                            db.add(
                                CatalogOffering(
                                    id=new_id(),
                                    catalog_revision_id=new_rev.id,
                                    offering_key=off_key,
                                    concept_id=ev_battery_towing.id,
                                    offering_kind="base",
                                    role="included",
                                    label_override="EV Battery Towing",
                                    description_override="Emergency towing to nearest EV charging point on battery depletion.",
                                    typed_value={"type": "text", "value": "Unlimited"},
                                    display_value="Unlimited",
                                    optional_price=None,
                                    presentation_facet_ids=[],
                                    sort_order=sort_counter,
                                    status="active",
                                )
                            )
                            sort_counter += 1

                    # 3. EV Charger Liability
                    if ev_charger_liability and ev_charger_liability.id not in offering_concept_ids_added:
                        off_key = f"ev-{cov_slug}-ev-charger-liability"
                        if off_key not in offering_keys_added:
                            offering_keys_added.add(off_key)
                            offering_concept_ids_added.add(ev_charger_liability.id)
                            db.add(
                                CatalogOffering(
                                    id=new_id(),
                                    catalog_revision_id=new_rev.id,
                                    offering_key=off_key,
                                    concept_id=ev_charger_liability.id,
                                    offering_kind="optional",
                                    role="addon_option",
                                    label_override="EV Charger Liability",
                                    description_override="Third-party bodily injury and property damage from home charging.",
                                    typed_value={"type": "money", "value": 50000, "currency": "MYR"},
                                    display_value="RM 50,000",
                                    optional_price={"amount": 50.0, "currency": "MYR"},
                                    presentation_facet_ids=[],
                                    sort_order=sort_counter,
                                    status="active",
                                )
                            )
                            sort_counter += 1

                db.flush()
                print(f"    -> Created revision {new_rev.revision_number} with {sort_counter - 1} offerings.")

    db.commit()
    print("\n=== All EV Catalogs successfully seeded and published! ===")


def main() -> None:
    db = SessionLocal()
    try:
        dedup_berjaya_sompo_products(db)
        seed_ev_catalogs_all_insurers(db)
    except Exception as e:
        print("EXCEPTION CAUGHT MESSAGE:", str(e).split("[parameters:")[0].strip())
        if hasattr(e, "orig"):
            print("ORIG:", e.orig)
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
