"""Seed curated, insurer-specific benefit short descriptions across vehicles and coverage tiers.

Also seeds:
- CompanyBenefitConfig entries (master benefit pool with baseline descriptions)
- CompanyBenefitCondition rules (e.g. QBE Driver Passenger Protector -> Unlimited Towing)
- EV Scenario Catalogs (engine_type='ev')

Usage:
    python commands/seed-company-benefits.py            # Dry-run (reports proposed overrides)
    python commands/seed-company-benefits.py --apply    # Applies overrides to database
    python commands/seed-company-benefits.py --apply --company qbe
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.tables import (
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    BenefitPackage,
    CatalogOffering,
    CompanyBenefitCondition,
    CompanyBenefitConfig,
    CoverageType,
    InsuranceCompany,
    InsuranceProduct,
    Segment,
    VehicleCategory,
    new_id,
    utcnow,
)

CURATED_INSURER_DESCRIPTIONS: dict[str, dict[str, dict[str, str]]] = {
    "qbe": {
        "car": {
            "own-damage": "Accidental collision, overturning, fire, explosion & theft protection.",
            "towing": "24/7 emergency roadside towing assistance to nearest authorized panel workshop.",
            "betterment-protection": "100% waiver of betterment cost on new replacement parts for vehicles up to 15 years.",
            "legal-costs-defense": "Legal defense representation costs and court expenses reimbursement up to RM 2,000.",
            "total-loss-theft-allowance": "Lump-sum compassionate cash allowance upon total loss or theft of the vehicle.",
            "all-drivers": "Waives unnamed driver compulsory excess for all authorized licensed drivers.",
            "key-replacement": "Replacement and reprogramming of lost, stolen, or damaged electronic smart keys up to RM 1,000.",
            "repair-allowance": "Compensation for Assessed Repair Time (CART) daily cash allowance during panel repairs.",
            "car-detailing-cleanup": "Post-repair interior vehicle detailing, cleaning, and sanitisation cost reimbursement.",
            "special-perils": "Full protection against floods, typhoons, landslides, fallen trees & tempests.",
            "legal-liability-of-passengers": "Protects you against legal liability incurred by your passengers' negligence.",
            "legal-liability-to-passengers": "Legal protection against third-party negligence lawsuits brought by passengers.",
            "ncd-relief": "Protects your No Claim Discount (NCD) against forfeiture for one own-damage claim.",
            "out-of-pocket-allowance": "Out-of-pocket and inconvenience expenses allowance during vehicle repair.",
            "first-loss-flood": "First-loss flood special perils indemnity up to selected limit without sum insured penalty.",
            "strike-riot-civil-commotion": "Full cover against malicious damage caused by strikes, riots and civil commotion.",
            "tuition-purpose": "Extension of motor policy coverage for driving tuition and instructional driving purposes.",
            "vehicle-accessories": "Endorsement covering non-standard audio, visual and custom exterior accessories.",
            "windscreen": "Repair & replacement of front, rear and all side door glass with 0% excess.",
            "driver-passenger-protector": "Personal accident medical and death coverage for driver and authorized passengers.",
            "ev-wall-charger": "Dedicated home EV wallbox charger protection against fire, electrical surge & theft.",
        },
        "motorcycle": {
            "own-damage": "QBE comprehensive motorcycle collision, accidental damage, theft, and fire protection.",
            "towing": "24/7 dedicated motorcycle breakdown towing to nearest approved panel workshop.",
            "legal-liability-to-pillion": "Covers legal liability for accidental bodily injury to authorized pillion rider.",
            "all-drivers": "Extends motorcycle comprehensive coverage to any licensed authorized rider.",
            "special-perils": "Motorcycle flood, storm, and natural catastrophe protection.",
        },
        "commercial": {
            "own-damage": "Heavy commercial vehicle own damage, accidental collision and rollover cover.",
            "towing": "Heavy-duty breakdown towing and recovery assistance for commercial fleet vehicles.",
            "cargo-protection": "Comprehensive transit protection for commercial merchandise and goods carried.",
            "legal-liability-to-passengers": "Statutory corporate crew, loader and cabin attendant legal liability protection.",
            "authorized-attendants": "Covers legal liability to authorized attendants and working personnel in transit.",
        },
    },
    "takaful-malaysia": {
        "car": {
            "own-damage": "Takaful comprehensive own damage with fast accident and collision settlement.",
            "personal-accident": "Complimentary driver and passenger personal accident protection up to RM 15,000.",
            "towing": "24/7 emergency accident and breakdown roadside towing assistance.",
            "cashback-no-claim": "15% non-claim cashback rebate reward for claim-free policy period.",
            "legal-costs-defense": "Reimbursement of legal defense representation costs and expenses up to RM 2,000.",
            "all-drivers": "All Drivers excess waiver - covers any licensed authorized driver with zero excess.",
            "agreed-value-market-value": "Agreed value sum insured payout for total loss or theft with no market depreciation.",
            "betterment-protection": "100% waiver of betterment contribution on brand new original spare parts.",
            "motor-pa-plus": "Comprehensive Motor PA Plus driver and passenger accident protection (Plan 1-4).",
            "special-perils": "Inclusion of special perils covering flood, storm, landslide and convulsion of nature.",
            "windscreen": "Repair and replacement of windscreen, rear window and door window glass.",
            "legal-liability-of-passengers": "Covers legal liability against damage caused by passenger acts of negligence.",
            "legal-liability-to-passengers": "Protects driver against legal liability for accidental injury to passengers.",
        },
    },
    "etiqa": {
        "car": {
            "own-damage": "Etiqa comprehensive own damage with zero betterment and fast claims payout.",
            "towing": "24/7 Etiqa Auto Assist nationwide roadside towing up to 200 km round-trip.",
            "windscreen": "Original factory glass replacement with tint film warranty preservation.",
            "special-perils": "Etiqa flood relief protection including water damage and mud cleanup allowance.",
            "all-drivers": "Etiqa All Drivers cover - no compulsory excess for unnamed authorized drivers.",
            "flood-relief-allowance": "Immediate compassionate cash payout upon vehicle flood damage.",
            "key-replacement": "Reimbursement for lost, stolen or broken smart key replacement.",
            "ev-wall-charger": "Home wallbox charging station coverage up to RM 12,000 against fire and surge.",
            "driver-passenger-protector": "Comprehensive personal accident protection for driver and all passengers.",
        },
        "motorcycle": {
            "own-damage": "Etiqa motorcycle own damage and total loss theft compensation.",
            "towing": "Etiqa 24/7 dedicated motorbike breakdown towing assistance.",
            "all-drivers": "Covers any authorized rider with valid motorcycle license.",
        },
    },
    "allianz": {
        "car": {
            "own-damage": "Allianz comprehensive protection with Road Rangers on-scene accident support.",
            "towing": "Allianz Road Rangers nationwide emergency towing to authorized panel workshop.",
            "windscreen": "Genuine windscreen replacement with lifetime repair warranty on workmanship.",
            "special-perils": "Allianz flood relief and full natural peril damage reimbursement.",
            "all-drivers": "Waives unnamed driver excess for all licensed authorized drivers.",
            "repair-allowance": "Compensation for assessed repair time (CART) during panel workshop repairs.",
            "ev-wall-charger": "Dedicated EV home charging unit coverage up to RM 15,000.",
            "driver-passenger-protector": "Road Warrior accident cover for driver and passenger bodily injury.",
        },
        "motorcycle": {
            "own-damage": "Allianz comprehensive motorcycle insurance with fast accident response.",
            "towing": "Allianz nationwide motorcycle roadside towing assistance.",
        },
    },
}


def seed_company_benefit_descriptions(db, dry_run: bool = True, target_company: str | None = None) -> list[str]:
    logs: list[str] = []
    companies = list(db.scalars(select(InsuranceCompany)).all())
    concepts = {c.concept_key: c for c in db.scalars(select(BenefitConcept)).all()}
    vehicles = {v.id: v.category_key for v in db.scalars(select(VehicleCategory)).all()}

    for company in companies:
        slug = (company.slug or "").lower().replace("-", "").strip()
        comp_key = None
        for k in CURATED_INSURER_DESCRIPTIONS:
            clean_k = k.replace("-", "")
            if clean_k in slug or slug in clean_k or clean_k in (company.name or "").lower().replace("-", ""):
                comp_key = k
                break

        if not comp_key:
            continue
        if target_company and target_company.lower() not in comp_key:
            continue

        company_curated = CURATED_INSURER_DESCRIPTIONS[comp_key]

        # Find catalogs for this company
        catalogs = list(
            db.scalars(
                select(BenefitCatalog).where(BenefitCatalog.company_id == company.id)
            ).all()
        )

        for cat in catalogs:
            v_key = vehicles.get(cat.vehicle_category_id, "car")
            curated_map = company_curated.get(v_key, company_curated.get("car", {}))
            if not curated_map:
                continue

            latest_rev = db.scalar(
                select(BenefitCatalogRevision)
                .where(BenefitCatalogRevision.catalog_id == cat.id)
                .order_by(BenefitCatalogRevision.revision_number.desc())
            )
            if not latest_rev:
                continue

            offerings = list(
                db.scalars(
                    select(CatalogOffering).where(CatalogOffering.catalog_revision_id == latest_rev.id)
                ).all()
            )

            updated_count = 0
            for off in offerings:
                c = next((conc for conc in concepts.values() if conc.id == off.concept_id), None)
                if not c:
                    continue

                custom_desc = curated_map.get(c.concept_key)
                if custom_desc and off.description_override != custom_desc:
                    logs.append(
                        f"[{company.name} | {cat.name}] Set '{c.label}' ({c.concept_key}): '{custom_desc[:45]}...'"
                    )
                    updated_count += 1

            if updated_count > 0 and not dry_run:
                if latest_rev.state == "published":
                    new_rev = BenefitCatalogRevision(
                        id=new_id(),
                        catalog_id=cat.id,
                        revision_number=latest_rev.revision_number + 1,
                        state="draft",
                        content_hash=latest_rev.content_hash,
                        published_by=None,
                        published_at=None,
                    )
                    db.add(new_rev)
                    db.flush()

                    package_map: dict[str, str] = {}
                    for package in db.scalars(
                        select(BenefitPackage).where(BenefitPackage.catalog_revision_id == latest_rev.id)
                    ).all():
                        copy = BenefitPackage(
                            id=new_id(),
                            catalog_revision_id=new_rev.id,
                            package_key=package.package_key,
                            name=package.name,
                            package_kind=package.package_kind,
                            sort_order=package.sort_order,
                            status=package.status,
                        )
                        db.add(copy)
                        package_map[str(package.id)] = copy.id
                        package_map[package.id] = copy.id
                    db.flush()

                    for off in offerings:
                        c = next((conc for conc in concepts.values() if conc.id == off.concept_id), None)
                        c_key = c.concept_key if c else None
                        custom_desc = curated_map.get(c_key) if c_key else None
                        new_desc = custom_desc if custom_desc is not None else off.description_override

                        target_applies_id = package_map.get(str(off.applies_to_id)) if off.applies_to_id else None
                        target_applies_type = off.applies_to_type if target_applies_id is not None else None

                        db.add(CatalogOffering(
                            id=new_id(),
                            catalog_revision_id=new_rev.id,
                            offering_key=off.offering_key,
                            concept_id=off.concept_id,
                            offering_kind=off.offering_kind,
                            applies_to_type=target_applies_type,
                            applies_to_id=target_applies_id,
                            role=off.role,
                            label_override=off.label_override,
                            description_override=new_desc,
                            typed_value=off.typed_value,
                            display_value=off.display_value,
                            optional_price=off.optional_price,
                            source_document_id=off.source_document_id,
                            source_citation=off.source_citation,
                            source_aliases=list(off.source_aliases or []),
                            presentation_facet_ids=list(off.presentation_facet_ids or []),
                            sort_order=off.sort_order,
                            status=off.status,
                        ))
                    db.flush()
                    new_rev.state = "published"
                    new_rev.published_at = utcnow()
                    cat.revision = new_rev.revision_number
                    db.flush()
                else:
                    for off in offerings:
                        c = next((conc for conc in concepts.values() if conc.id == off.concept_id), None)
                        if not c:
                            continue
                        custom_desc = curated_map.get(c.concept_key)
                        if custom_desc and off.description_override != custom_desc:
                            off.description_override = custom_desc
                    db.flush()

    if not dry_run:
        db.commit()

    return logs


EXACT_ENABLED_CONCEPTS: dict[str, set[str]] = {
    "qbe": {
        # Defaults (7)
        "own-damage",
        "towing",
        "betterment-protection",
        "legal-costs-defense",
        "total-loss-theft-allowance",
        "all-drivers",
        "key-replacement",
        # Addons (12 concepts)
        "repair-allowance",
        "car-detailing-cleanup",
        "special-perils",
        "legal-liability-of-passengers",
        "legal-liability-to-passengers",
        "ncd-relief",
        "out-of-pocket-allowance",
        "first-loss-flood",
        "strike-riot-civil-commotion",
        "tuition-purpose",
        "vehicle-accessories",
        "windscreen",
        # Package condition trigger
        "driver-passenger-protector",
    },
    "takaful-malaysia": {
        # Defaults (8)
        "own-damage",
        "personal-accident",
        "towing",
        "cashback-no-claim",
        "legal-costs-defense",
        "all-drivers",
        "agreed-value-market-value",
        "betterment-protection",
        # Addons (5 concepts)
        "motor-pa-plus",
        "special-perils",
        "windscreen",
        "legal-liability-of-passengers",
        "legal-liability-to-passengers",
    },
}

QBE_CAR_DEFAULTS = [
    ("own-damage", "Comprehensive Accidental Own Damage", "Standard", None, "Accidental collision, overturning, fire, explosion & theft protection."),
    ("towing", "Emergency Towing Assistance", "50 km / RM 300", None, "24/7 emergency roadside towing assistance to nearest authorized panel workshop."),
    ("betterment-protection", "Betterment Waiver / Scale", "100% Waived", None, "100% waiver of betterment cost on replacement parts for vehicles up to 15 years."),
    ("legal-costs-defense", "Legal Defense Costs", "RM 2,000", None, "Legal defense representation costs and court expenses reimbursement up to RM 2,000."),
    ("total-loss-theft-allowance", "Compassionate Allowance (Total Loss / Theft)", "RM 1,000", None, "Lump-sum compassionate cash allowance upon total loss or theft of the vehicle."),
    ("all-drivers", "All Drivers Excess Waiver", "Waived", None, "Waives unnamed driver compulsory excess for all authorized licensed drivers."),
    ("key-replacement", "Key Care & Replacement", "RM 1,000", None, "Replacement and reprogramming of lost, stolen, or damaged electronic smart keys up to RM 1,000."),
]

QBE_CAR_ADDONS = [
    ("repair-allowance", "qbe-add-cart-50-14d", "CART RM50/day for 14 days", "RM 50/day (14 days)", None, "Compensation for Assessed Repair Time (CART) daily cash allowance during panel repairs."),
    ("repair-allowance", "qbe-add-cart-100-14d", "CART RM100/day for 14 days", "RM 100/day (14 days)", None, "Compensation for Assessed Repair Time (CART) daily cash allowance during panel repairs."),
    ("car-detailing-cleanup", "qbe-add-cleaning-cost", "Cleaning Cost", "RM 1,000", None, "Post-repair interior vehicle detailing, cleaning, and sanitisation cost reimbursement."),
    ("special-perils", "qbe-add-special-perils", "Inclusion of Special Perils", "Full Sum Insured", None, "Full protection against floods, typhoons, landslides, fallen trees & tempests."),
    ("legal-liability-of-passengers", "qbe-add-llop", "Legal Liability of Passengers (LLOP)", None, {"type": "money", "value": 7.5, "currency": "MYR"}, "Protects you against legal liability incurred by your passengers' negligence."),
    ("legal-liability-to-passengers", "qbe-add-lltp", "Legal Liability to Passengers (LLTP)", None, None, "Legal protection against third-party negligence lawsuits brought by passengers."),
    ("ncd-relief", "qbe-add-ncd-protector", "NCD Protector", "1 Claim / Year", None, "Protects your No Claim Discount (NCD) against forfeiture for one own-damage claim."),
    ("out-of-pocket-allowance", "qbe-add-out-of-pocket", "Out of Pocket Allowance", "RM 1,000", None, "Out-of-pocket and inconvenience expenses allowance during vehicle repair."),
    ("first-loss-flood", "qbe-add-first-loss-5k", "Special Peril First Loss 5K", "RM 5,000", {"type": "money", "value": 30.0, "currency": "MYR"}, "First-loss flood special perils indemnity up to RM 5,000 without sum insured penalty."),
    ("first-loss-flood", "qbe-add-first-loss-10k", "Special Peril First Loss 10K", "RM 10,000", {"type": "money", "value": 60.0, "currency": "MYR"}, "First-loss flood special perils indemnity up to RM 10,000 without sum insured penalty."),
    ("strike-riot-civil-commotion", "qbe-add-srcc", "Strike, Riot & Civil Commotion", "Full Sum Insured", None, "Full cover against malicious damage caused by strikes, riots and civil commotion."),
    ("tuition-purpose", "qbe-add-tuition-purpose", "Tuition Purpose", "Standard", None, "Extension of motor policy coverage for driving tuition and instructional driving purposes."),
    ("vehicle-accessories", "qbe-add-vehicle-accessories", "Vehicle Accessories", "As Specified", None, "Endorsement covering non-standard audio, visual and custom exterior accessories."),
    ("windscreen", "qbe-add-windscreen", "Windscreen Damage", "RM 1,000", None, "Repair & replacement of front, rear and all side door glass with 0% excess."),
]

STMB_CAR_DEFAULTS = [
    ("own-damage", "Comprehensive Accidental Own Damage", "Standard", None, "Takaful comprehensive own damage with fast accident and collision settlement."),
    ("personal-accident", "Complimentary Personal Accident PA", "RM 15,000", None, "Complimentary driver and passenger personal accident protection up to RM 15,000."),
    ("towing", "Emergency Roadside Towing", "100 km / RM 200", None, "24/7 emergency accident and breakdown roadside towing assistance."),
    ("cashback-no-claim", "Non-Claim Cashback (15%)", "15% Cashback", None, "15% non-claim cashback rebate reward for claim-free policy period."),
    ("legal-costs-defense", "Legal Defense Costs", "RM 2,000", None, "Reimbursement of legal defense representation costs and expenses up to RM 2,000."),
    ("all-drivers", "All Drivers Excess Waiver", "Waived", None, "All Drivers excess waiver - covers any licensed authorized driver with zero excess."),
    ("agreed-value-market-value", "Agreed Value Settlement", "Agreed Value", None, "Agreed value sum insured payout for total loss or theft with no market depreciation."),
    ("betterment-protection", "Waiver of Betterment", "100% Waived", None, "100% waiver of betterment contribution on brand new original spare parts."),
]

STMB_CAR_ADDONS = [
    ("motor-pa-plus", "stmb-add-motor-pa-plus", "Motor PA PLUS Plan 1-4", "Plan 1-4", None, "Comprehensive Motor PA Plus driver and passenger accident protection (Plan 1-4)."),
    ("special-perils", "stmb-add-special-perils", "Inclusion of Special Perils", "Full Sum Insured", None, "Inclusion of special perils covering flood, storm, landslide and convulsion of nature."),
    ("windscreen", "stmb-add-windscreen", "Breakage of Glass in Windscreen", "RM 1,000", None, "Repair and replacement of windscreen, rear window and door window glass."),
    ("legal-liability-of-passengers", "stmb-add-llop", "Legal Liability of Passenger (LLOP)", None, {"type": "money", "value": 7.5, "currency": "MYR"}, "Covers legal liability against damage caused by passenger acts of negligence."),
    ("legal-liability-to-passengers", "stmb-add-lltp", "Passenger Liability Cover / Legal Liability to Passengers (LLTP)", None, None, "Protects driver against legal liability for accidental injury to passengers."),
]


def seed_company_benefit_configs(db, dry_run: bool = True, target_company: str | None = None) -> list[str]:
    """Seed CompanyBenefitConfig rows for each insurer's enabled benefits pool."""
    logs: list[str] = []
    companies = list(db.scalars(select(InsuranceCompany)).all())
    concepts = list(db.scalars(select(BenefitConcept).where(BenefitConcept.status == "active")).all())

    for company in companies:
        slug = (company.slug or "").lower().replace("-", "").strip()
        comp_key = None
        for k in CURATED_INSURER_DESCRIPTIONS:
            clean_k = k.replace("-", "")
            if clean_k in slug or slug in clean_k or clean_k in (company.name or "").lower().replace("-", ""):
                comp_key = k
                break

        if target_company and comp_key and target_company.lower() not in comp_key:
            continue

        company_curated = CURATED_INSURER_DESCRIPTIONS.get(comp_key or "", {}).get("car", {})
        exact_enabled = EXACT_ENABLED_CONCEPTS.get(comp_key or company.slug or slug)

        existing_configs = {
            cfg.concept_id: cfg
            for cfg in db.scalars(
                select(CompanyBenefitConfig).where(CompanyBenefitConfig.company_id == company.id)
            ).all()
        }

        for c in concepts:
            cfg = existing_configs.get(c.id)
            baseline = company_curated.get(c.concept_key) or c.description or ""
            is_enabled = c.concept_key in exact_enabled if exact_enabled is not None else True

            if not cfg:
                logs.append(f"[Config: {company.name}] Add benefit '{c.label}' (enabled={is_enabled}, baseline: {baseline[:35]}...)")
                if not dry_run:
                    db.add(CompanyBenefitConfig(
                        id=new_id(),
                        company_id=company.id,
                        concept_id=c.id,
                        is_enabled=is_enabled,
                        baseline_description=baseline,
                    ))
            else:
                if cfg.is_enabled != is_enabled:
                    logs.append(f"[Config: {company.name}] Update '{c.label}' enabled: {cfg.is_enabled} -> {is_enabled}")
                    if not dry_run:
                        cfg.is_enabled = is_enabled
                if not cfg.baseline_description and baseline:
                    logs.append(f"[Config: {company.name}] Populate baseline for '{c.label}': {baseline[:35]}...")
                    if not dry_run:
                        cfg.baseline_description = baseline

    if not dry_run:
        db.commit()

    return logs


def sync_exact_catalog_offerings(db, dry_run: bool = True, target_company: str | None = None) -> list[str]:
    """Synchronize exact defaults and add-ons for QBE and STMB Private Car Comprehensive catalogs."""
    logs: list[str] = []
    concepts = {c.concept_key: c for c in db.scalars(select(BenefitConcept)).all()}

    for slug in ["qbe", "takaful-malaysia"]:
        if target_company and slug not in target_company.lower() and (slug == "takaful-malaysia" and "stmb" not in target_company.lower()):
            continue

        co = db.query(InsuranceCompany).filter_by(slug=slug).first()
        if not co:
            continue

        target_defaults = QBE_CAR_DEFAULTS if slug == "qbe" else STMB_CAR_DEFAULTS
        target_addons = QBE_CAR_ADDONS if slug == "qbe" else STMB_CAR_ADDONS

        if slug == "qbe":
            catalogs = db.query(BenefitCatalog).filter_by(company_id=co.id).filter(
                (BenefitCatalog.name.ilike("%Private Car%")) | (BenefitCatalog.name.ilike("%Car Protector%"))
            ).all()
        else:
            catalogs = db.query(BenefitCatalog).filter_by(company_id=co.id).filter(
                (BenefitCatalog.name.ilike("%Private Car%")) | (BenefitCatalog.name.ilike("%myMotor%")) | (BenefitCatalog.name.ilike("%Takaful Car%"))
            ).all()

        for cat in catalogs:
            if "tpft" in cat.name.lower() or "third party" in cat.name.lower():
                continue

            rev = db.query(BenefitCatalogRevision).filter_by(catalog_id=cat.id).order_by(BenefitCatalogRevision.revision_number.desc()).first()
            if not rev:
                continue

            existing_offerings = db.query(CatalogOffering).filter_by(catalog_revision_id=rev.id).all()
            existing_keys = sorted([o.offering_key for o in existing_offerings])
            target_keys = sorted([f"{slug[:4]}-def-{c[0]}" for c in target_defaults] + [c[1] for c in target_addons])
            if existing_keys == target_keys:
                continue

            logs.append(f"[Sync Catalog: {co.name}] Syncing '{cat.name}' with {len(target_defaults)} defaults and {len(target_addons)} add-ons")
            if not dry_run:
                if rev.state == "published":
                    target_rev = BenefitCatalogRevision(
                        id=new_id(),
                        catalog_id=cat.id,
                        revision_number=rev.revision_number + 1,
                        state="draft",
                        source_document_ids=list(rev.source_document_ids or []),
                        content_hash=f"seed-{new_id()[:8]}",
                    )
                    db.add(target_rev)
                    db.flush()
                else:
                    target_rev = rev
                    for o in db.query(CatalogOffering).filter_by(catalog_revision_id=target_rev.id).all():
                        db.delete(o)
                    db.flush()

                sort_idx = 1
                for c_key, label, val, price, desc in target_defaults:
                    c = concepts.get(c_key)
                    if not c:
                        continue
                    db.add(CatalogOffering(
                        id=new_id(),
                        catalog_revision_id=target_rev.id,
                        offering_key=f"{slug[:4]}-def-{c_key}",
                        concept_id=c.id,
                        offering_kind="base",
                        applies_to_type="product" if cat.product_id else None,
                        applies_to_id=cat.product_id if cat.product_id else None,
                        role="included",
                        label_override=label,
                        description_override=desc,
                        display_value=val,
                        optional_price=price,
                        sort_order=sort_idx,
                        status="active",
                        source_citation={},
                        source_aliases=[],
                        presentation_facet_ids=[],
                    ))
                    sort_idx += 1

                for item in target_addons:
                    c_key, off_key, label, val, price, desc = item
                    c = concepts.get(c_key)
                    if not c:
                        continue
                    db.add(CatalogOffering(
                        id=new_id(),
                        catalog_revision_id=target_rev.id,
                        offering_key=off_key,
                        concept_id=c.id,
                        offering_kind="optional",
                        applies_to_type="product" if cat.product_id else None,
                        applies_to_id=cat.product_id if cat.product_id else None,
                        role="addon_option",
                        label_override=label,
                        description_override=desc,
                        display_value=val,
                        optional_price=price,
                        sort_order=sort_idx,
                        status="active",
                        source_citation={},
                        source_aliases=[],
                        presentation_facet_ids=[],
                    ))
                    sort_idx += 1

                target_rev.state = "published"
                target_rev.published_at = utcnow()
                cat.revision = target_rev.revision_number
                cat.status = "published"
                db.flush()

    if not dry_run:
        db.commit()

    return logs



def seed_company_conditions(db, dry_run: bool = True, target_company: str | None = None) -> list[str]:
    """Seed dynamic conditional rules (e.g., Driver Protector purchase -> Unlimited Towing)."""
    logs: list[str] = []
    companies = list(db.scalars(select(InsuranceCompany)).all())
    concepts = {c.concept_key: c for c in db.scalars(select(BenefitConcept)).all()}

    # Target: QBE
    qbe = next((c for c in companies if "qbe" in (c.slug or "").lower() or "qbe" in (c.name or "").lower()), None)
    if qbe and (not target_company or "qbe" in target_company.lower()):
        trig_concept = concepts.get("driver-passenger-protector")
        target_concept = concepts.get("towing")

        if trig_concept and target_concept:
            rule_name = "QBE Driver Passenger Protector -> Unlimited Towing Upgrade"
            existing = db.scalar(
                select(CompanyBenefitCondition).where(
                    CompanyBenefitCondition.company_id == qbe.id,
                    CompanyBenefitCondition.name == rule_name,
                )
            )
            if not existing:
                logs.append(
                    f"[Condition: {qbe.name}] Add rule: '{rule_name}' "
                    f"({trig_concept.label} -> {target_concept.label} = 'Unlimited towing')"
                )
                if not dry_run:
                    db.add(CompanyBenefitCondition(
                        id=new_id(),
                        company_id=qbe.id,
                        name=rule_name,
                        trigger_concept_id=trig_concept.id,
                        trigger_plan_filter=None,
                        target_concept_id=target_concept.id,
                        replacement_description="Unlimited breakdown roadside towing across Peninsular Malaysia",
                        is_active=True,
                    ))
                    db.commit()

    return logs


def seed_ev_catalogs(db, dry_run: bool = True, target_company: str | None = None) -> list[str]:
    """Seed EV catalogs (engine_type='ev') cloned from Comprehensive Car catalogs."""
    logs: list[str] = []
    companies = list(db.scalars(select(InsuranceCompany)).all())
    ev_charger_concept = db.scalar(
        select(BenefitConcept).where(BenefitConcept.concept_key == "ev-wall-charger")
    )
    car_vehicle = db.scalar(
        select(VehicleCategory).where(VehicleCategory.category_key == "car")
    )

    for company in companies:
        slug = (company.slug or "").lower().replace("-", "").strip()
        comp_key = None
        for k in CURATED_INSURER_DESCRIPTIONS:
            clean_k = k.replace("-", "")
            if clean_k in slug or slug in clean_k or clean_k in (company.name or "").lower().replace("-", ""):
                comp_key = k
                break

        if not comp_key:
            continue
        if target_company and target_company.lower() not in comp_key:
            continue

        # Check if an EV catalog already exists for this company
        existing_ev = db.scalar(
            select(BenefitCatalog).where(
                BenefitCatalog.company_id == company.id,
                BenefitCatalog.engine_type == "ev",
            )
        )
        if existing_ev:
            continue

        # Find Private Car Comprehensive catalog (ICE)
        ice_cat = db.scalar(
            select(BenefitCatalog).where(
                BenefitCatalog.company_id == company.id,
                BenefitCatalog.vehicle_category_id == (car_vehicle.id if car_vehicle else BenefitCatalog.vehicle_category_id),
                BenefitCatalog.name.ilike("%Comprehensive%"),
            )
        )
        if not ice_cat:
            continue

        latest_ice_rev = db.scalar(
            select(BenefitCatalogRevision)
            .where(BenefitCatalogRevision.catalog_id == ice_cat.id)
            .order_by(BenefitCatalogRevision.revision_number.desc())
        )
        if not latest_ice_rev:
            continue

        ev_cat_name = f"{company.name} Private Car Comprehensive (EV)"
        logs.append(f"[EV Catalog: {company.name}] Create EV catalog: '{ev_cat_name}'")

        if not dry_run:
            ev_prod_key = f"ev-{company.slug or 'comp'}-car-comprehensive"
            ev_product = db.scalar(
                select(InsuranceProduct).where(
                    InsuranceProduct.company_id == company.id,
                    InsuranceProduct.product_key == ev_prod_key,
                )
            )
            if not ev_product:
                ev_product = InsuranceProduct(
                    id=new_id(),
                    company_id=company.id,
                    product_key=ev_prod_key,
                    name=ev_cat_name,
                    status="active",
                )
                db.add(ev_product)
                db.flush()

            new_cat_id = new_id()
            ev_catalog = BenefitCatalog(
                id=new_cat_id,
                company_id=company.id,
                product_id=ev_product.id,
                tier_id=None,
                package_id=None,
                segment_id=ice_cat.segment_id,
                vehicle_category_id=ice_cat.vehicle_category_id,
                vehicle_subcategory_id=ice_cat.vehicle_subcategory_id,
                coverage_type_id=ice_cat.coverage_type_id,
                engine_type="ev",
                name=ev_cat_name,
                revision=1,
                status="active",
            )
            db.add(ev_catalog)
            db.flush()

            ev_rev_id = new_id()
            ev_rev = BenefitCatalogRevision(
                id=ev_rev_id,
                catalog_id=new_cat_id,
                revision_number=1,
                state="published",
                content_hash=latest_ice_rev.content_hash,
                published_at=utcnow(),
            )
            db.add(ev_rev)
            db.flush()

            # Copy offerings from ICE catalog
            ice_offerings = list(
                db.scalars(
                    select(CatalogOffering).where(
                        CatalogOffering.catalog_revision_id == latest_ice_rev.id
                    )
                ).all()
            )

            has_ev_charger = False
            for off in ice_offerings:
                if ev_charger_concept and off.concept_id == ev_charger_concept.id:
                    has_ev_charger = True
                db.add(CatalogOffering(
                    id=new_id(),
                    catalog_revision_id=ev_rev_id,
                    offering_key=f"ev-{off.offering_key}",
                    concept_id=off.concept_id,
                    offering_kind=off.offering_kind,
                    applies_to_type=None,
                    applies_to_id=None,
                    role=off.role,
                    label_override=off.label_override,
                    description_override=off.description_override,
                    typed_value=off.typed_value,
                    display_value=off.display_value,
                    optional_price=off.optional_price,
                    presentation_facet_ids=list(off.presentation_facet_ids or []),
                    sort_order=off.sort_order,
                    status=off.status,
                ))

            # Add EV Wall Charger if missing
            if not has_ev_charger and ev_charger_concept:
                db.add(CatalogOffering(
                    id=new_id(),
                    catalog_revision_id=ev_rev_id,
                    offering_key=f"ev-{company.slug or 'comp'}-wall-charger",
                    concept_id=ev_charger_concept.id,
                    offering_kind="optional",
                    applies_to_type=None,
                    applies_to_id=None,
                    role="addon_option",
                    label_override="EV Charger & Wallbox Cover",
                    description_override="Dedicated home EV wallbox charger protection against fire, electrical surge & theft.",
                    typed_value={"type": "money", "value": 12000, "currency": "MYR"},
                    display_value="RM 12,000",
                    optional_price={"amount": 120.0, "currency": "MYR"},
                    presentation_facet_ids=[],
                    sort_order=25,
                    status="active",
                ))

            db.flush()
            db.commit()

    return logs


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed company-specific benefit descriptions, configs, conditions, and EV catalogs.")
    parser.add_argument("--apply", action="store_true", help="Commit changes to database")
    parser.add_argument("--company", type=str, default=None, help="Filter to specific company (e.g. qbe, etiqa)")
    args = parser.parse_args()

    mode_str = "APPLY" if args.apply else "DRY-RUN"
    print(f"Running seed-company-benefits in {mode_str} mode...")

    with SessionLocal() as db:
        desc_logs = seed_company_benefit_descriptions(db, dry_run=not args.apply, target_company=args.company)
        config_logs = seed_company_benefit_configs(db, dry_run=not args.apply, target_company=args.company)
        sync_logs = sync_exact_catalog_offerings(db, dry_run=not args.apply, target_company=args.company)
        cond_logs = seed_company_conditions(db, dry_run=not args.apply, target_company=args.company)
        ev_logs = seed_ev_catalogs(db, dry_run=not args.apply, target_company=args.company)

    all_logs = desc_logs + config_logs + sync_logs + cond_logs + ev_logs
    if not all_logs:
        print("No changes to apply. Everything is up to date.")
    else:
        print(f"\n{len(all_logs)} operations processed:")
        for log in all_logs:
            print(f"  {log}")

    if not args.apply:
        print("\nDry-run complete. Run with --apply to commit.")
    else:
        print("\nSuccessfully applied all configurations and rules to database.")


if __name__ == "__main__":
    main()
