"""Seed verified demo data and clean up junk test rows.

Usage:
    python commands/seed-demo.py           # Dry-run (reports proposed changes)
    python commands/seed-demo.py --apply   # Commits changes to the database
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import delete, or_, select, text, update
from app.db.session import SessionLocal
from app.models.tables import (
    BenefitAlias,
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    BenefitPackage,
    BenefitPackagePlan,
    BenefitPackagePlanItem,
    BenefitRelation,
    BusinessAsset,
    CatalogOffering,
    CompanyAlias,
    CoverageType,
    InsuranceCompany,
    InsuranceProduct,
    InsuranceProductTier,
    QuotationDraft,
    Segment,
    TrashRecord,
    VehicleCategory,
    new_id,
)
from app.rendering.render_context import canonical_context_hash
from app.services.business_setup_service import _derive_description_variant, _revision_content_payload


def _normalize_phrase(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


BENEFIT_CONCEPTS_DATA = [
    # ── Category 1: Default / Global Benefits (11) ─────────────────────────
    {
        "concept_key": "towing",
        "label": "Towing",
        "category": "default",
        "asset_label": "Towing",
        "description": "24/7 emergency roadside towing assistance.",
        "match_dataset": ["towing", "emergency towing", "breakdown towing"],
        "sort_order": 1,
    },
    {
        "concept_key": "roadside-assistance",
        "label": "Roadside Assistance",
        "category": "default",
        "asset_label": "Emergency Roadside Assistance",
        "description": "24-hour on-site roadside emergency repair, battery jumpstart, and minor assistance.",
        "match_dataset": ["roadside assistance", "road assist", "emergency roadside", "breakdown assist"],
        "sort_order": 2,
    },
    {
        "concept_key": "repair-workmanship-warranty",
        "label": "Workmanship Warranty",
        "category": "default",
        "asset_label": "Repair Workmanship Warranty",
        "description": "Warranty on motor body and paint repairs carried out by panel workshops.",
        "match_dataset": ["workmanship warranty", "repair warranty", "panel warranty", "workmanship"],
        "sort_order": 3,
    },
    {
        "concept_key": "all-drivers",
        "label": "All Drivers",
        "category": "default",
        "asset_label": "All Drivers Coverage",
        "description": "Coverage for all authorised drivers without naming individual drivers in the policy schedule.",
        "match_dataset": ["all drivers", "unnamed drivers", "all drivers waiver", "any driver"],
        "sort_order": 4,
    },
    {
        "concept_key": "personal-accident",
        "label": "Personal Accident",
        "category": "default",
        "asset_label": "Personal Accident",
        "description": "Personal Accident coverage (includes Takaful's Accidental Death / TPD concept).",
        "match_dataset": ["personal accident", "accidental death", "tpd", "pa coverage"],
        "sort_order": 5,
    },
    {
        "concept_key": "betterment-protection",
        "label": "Betterment / New Parts Protection",
        "category": "default",
        "asset_label": "Brand New Spare Parts",
        "description": "Waiver of betterment costs when replacing damaged parts with brand new original parts.",
        "match_dataset": ["betterment", "waiver of betterment", "new parts protection", "brand new parts"],
        "sort_order": 6,
    },
    {
        "concept_key": "total-loss-theft-allowance",
        "label": "Total Loss / Theft Allowance",
        "category": "default",
        "asset_label": "Car Theft / Total Loss Assistance",
        "description": "Lump sum compassionate assistance upon total loss or constructive total theft of the vehicle.",
        "match_dataset": ["total loss", "theft allowance", "loss of vehicle", "total loss allowance"],
        "sort_order": 7,
    },
    {
        "concept_key": "key-replacement",
        "label": "Key Replacement",
        "category": "default",
        "asset_label": "Key Replacement / Key Care",
        "description": "Reimbursement for lost, stolen, or damaged vehicle transmitter keys.",
        "match_dataset": ["key replacement", "key care", "smart key", "lost key"],
        "sort_order": 8,
    },
    {
        "concept_key": "flood-relief-allowance",
        "label": "Flood Relief Allowance",
        "category": "default",
        "asset_label": "Flood Relief Allowance / Cash Assistance",
        "description": "Immediate cash relief assistance in the event of flood inundation damage.",
        "match_dataset": ["flood relief", "flood relief allowance", "flood cash assistance", "flood allowance"],
        "sort_order": 9,
    },
    {
        "concept_key": "personal-belongings-theft",
        "label": "Personal Belongings Theft",
        "category": "default",
        "asset_label": "Window Snatch Theft / Smash and Grab",
        "description": "Compensation for loss or theft of personal items from the vehicle resulting from forcible entry.",
        "match_dataset": ["personal belongings", "snatch theft", "smash and grab", "personal effects"],
        "sort_order": 10,
    },
    {
        "concept_key": "ambulance-fees",
        "label": "Ambulance Fees",
        "category": "default",
        "asset_label": "Ambulance Fees",
        "description": "Reimbursement for emergency ambulance transport fees following an accident.",
        "match_dataset": ["ambulance fees", "ambulance", "emergency transport fees"],
        "sort_order": 11,
    },

    # ── Category 2: Unique Add-ons (23) ───────────────────────────────────
    {
        "concept_key": "windscreen",
        "label": "Windscreen",
        "category": "addon",
        "asset_label": "Windscreen Coverage",
        "description": "Coverage for repair or replacement of broken windscreens, windows, or sunroof glass.",
        "match_dataset": ["windscreen", "cermin depan", "windshield", "glass damage"],
        "sort_order": 12,
    },
    {
        "concept_key": "special-perils",
        "label": "Special Perils",
        "category": "addon",
        "asset_label": "Special Perils",
        "description": "Protection against natural disasters including flood, typhoon, tempest, storm, landslide, and subsidence.",
        "match_dataset": ["special perils", "convulsion of nature", "flood damage", "landslide", "bencana alam"],
        "sort_order": 13,
    },
    {
        "concept_key": "strike-riot-civil-commotion",
        "label": "Strike, Riot & Civil Commotion",
        "category": "addon",
        "asset_label": "Strike, Riot and Civil Commotion",
        "description": "Indemnification against loss or damage caused by strikes, riots, or civil unrest.",
        "match_dataset": ["srcc", "strike riot", "civil commotion", "rusuhan"],
        "sort_order": 14,
    },
    {
        "concept_key": "legal-liability-to-passengers",
        "label": "Legal Liability to Passengers",
        "category": "addon",
        "asset_label": "Legal Liability to Passengers",
        "description": "Covers legal liability against claims from passengers for accidental bodily injury or death.",
        "match_dataset": ["llp", "legal liability to passengers", "liability to passenger"],
        "sort_order": 15,
    },
    {
        "concept_key": "legal-liability-of-passengers",
        "label": "Legal Liability of Passengers",
        "category": "addon",
        "asset_label": "Legal Liability of Passengers",
        "description": "Protects against legal liability for negligent acts caused by your passengers to third parties.",
        "match_dataset": ["llop", "legal liability of passengers", "negligent act of passenger"],
        "sort_order": 16,
    },
    {
        "concept_key": "legal-liability-to-pillion",
        "label": "Legal Liability to Pillion",
        "category": "addon",
        "asset_label": "Legal Liability to Passengers",
        "description": "Covers legal liability for accidental bodily injury or death to pillion riders.",
        "match_dataset": ["pillion liability", "legal liability to pillion", "pillion rider"],
        "sort_order": 17,
    },
    {
        "concept_key": "medical-expenses",
        "label": "Medical Expenses",
        "category": "addon",
        "asset_label": "Medical Expenses",
        "description": "Reimbursement for reasonable medical and hospitalisation expenses incurred due to a motor accident.",
        "match_dataset": ["medical expenses", "medical reimbursement", "hospitalisation expenses"],
        "sort_order": 18,
    },
    {
        "concept_key": "hospital-income",
        "label": "Hospital Income",
        "category": "addon",
        "asset_label": "Daily Hospital Income",
        "description": "Daily cash allowance for each day of hospital confinement resulting from an accident.",
        "match_dataset": ["hospital income", "daily hospital cash", "hospital cash allowance"],
        "sort_order": 19,
    },
    {
        "concept_key": "bereavement-allowance",
        "label": "Bereavement Allowance",
        "category": "addon",
        "asset_label": "Bereavement Allowance",
        "description": "Lump sum compassionate bereavement benefit payable to the next-of-kin upon accidental death.",
        "match_dataset": ["bereavement allowance", "funeral allowance", "compassionate allowance"],
        "sort_order": 20,
    },
    {
        "concept_key": "replacement-car",
        "label": "Replacement Car",
        "category": "addon",
        "asset_label": "Courtesy Car / Replacement Car",
        "description": "Provision of a temporary courtesy or rental replacement vehicle while your car is under accident repair.",
        "match_dataset": ["replacement car", "courtesy car", "rental car assistance"],
        "sort_order": 21,
    },
    {
        "concept_key": "repaint-spray-paint",
        "label": "Repaint / Spray Paint",
        "category": "addon",
        "asset_label": "Whole Car Spray Painting / New Coat of Paint",
        "description": "Coverage for full body respray or paint refinishing after panel repairs.",
        "match_dataset": ["repaint", "spray paint", "whole body paint", "spray painting"],
        "sort_order": 22,
    },
    {
        "concept_key": "side-mirror-protection",
        "label": "Side Mirror Protection",
        "category": "addon",
        "asset_label": "Side Mirror Coverage",
        "description": "Repair or replacement of broken exterior wing mirrors and electronic side mirror housings.",
        "match_dataset": ["side mirror", "wing mirror", "side mirror coverage"],
        "sort_order": 23,
    },
    {
        "concept_key": "child-car-seat",
        "label": "Child Car Seat",
        "category": "addon",
        "asset_label": "Child Car Seat Coverage",
        "description": "Reimbursement for replacement of damaged or stolen child safety car seats.",
        "match_dataset": ["child car seat", "baby seat", "child safety seat"],
        "sort_order": 24,
    },
    {
        "concept_key": "replacement-cost",
        "label": "Replacement Cost",
        "category": "addon",
        "asset_label": "Replacement Cost Benefit",
        "description": "Replacement cost compensation ensuring market value uplift or total replacement value.",
        "match_dataset": ["replacement cost", "cost of replacement", "replacement value"],
        "sort_order": 25,
    },
    {
        "concept_key": "vehicle-accessories",
        "label": "Vehicle Accessories",
        "category": "addon",
        "asset_label": "Side Mirror Coverage",
        "description": "Protection for non-standard factory vehicle accessories, dashcams, sound systems, and rims.",
        "match_dataset": ["accessories", "vehicle accessories", "audio system", "dashcam"],
        "sort_order": 26,
    },
    {
        "concept_key": "e-hailing-extension",
        "label": "E-Hailing / Private Hire Extension",
        "category": "addon",
        "asset_label": "e-Hailing / Private Hire Extension",
        "description": "Endorsement permitting commercial e-hailing / ride-hailing services (e.g. Grab, AirAsia Ride).",
        "match_dataset": ["e-hailing", "ehailing", "private hire", "grab endorsement"],
        "sort_order": 27,
    },
    {
        "concept_key": "agreed-value-market-value",
        "label": "Agreed Value / Market Value",
        "category": "addon",
        "asset_label": "Agreed Value / Market Value Settlement",
        "description": "Guaranteed agreed sum insured settlement with zero market depreciation disputes upon total loss.",
        "match_dataset": ["agreed value", "market value", "agreed sum insured"],
        "sort_order": 28,
    },
    {
        "concept_key": "cashback-no-claim",
        "label": "Cashback / No-Claim Cashback",
        "category": "addon",
        "asset_label": "No-Claim Cashback / NCD / Cashback Reward",
        "description": "Cashback reward incentive upon policy renewal if no insurance claims were made during the term.",
        "match_dataset": ["cashback", "no claim cashback", "ncd reward", "rebate"],
        "sort_order": 29,
    },
    {
        "concept_key": "out-of-pocket-allowance",
        "label": "Out-of-Pocket Allowance",
        "category": "addon",
        "asset_label": "Out-of-Pocket Allowance",
        "description": "Incidental allowance covering minor unexpected travel, transit, or towing expenses.",
        "match_dataset": ["out of pocket", "incidental expenses", "miscellaneous allowance"],
        "sort_order": 30,
    },
    {
        "concept_key": "driver-passenger-protector",
        "label": "Driver Passenger Protector",
        "category": "addon",
        "asset_label": "Driver and Passenger Protection Plan",
        "description": "Comprehensive personal accident protection bundle for driver and passengers with tiered sum insured plans.",
        "variants": ["Plan A", "Plan B", "Plan C", "Plan D"],
        "match_dataset": ["driver passenger protector", "dpp", "driver and passenger protection plan"],
        "sort_order": 31,
    },
    {
        "concept_key": "private-car-365",
        "label": "Private Car 365 Plan",
        "category": "addon",
        "asset_label": "Driver and Passenger Protection Plan",
        "description": "All-in-one 365 days emergency and personal accident motor protection packages.",
        "variants": ["Plan 1", "Plan 2", "Plan 3", "Plan 4", "Plan Ezy"],
        "match_dataset": ["private car 365", "car 365", "etiqa 365", "plan ezy"],
        "sort_order": 32,
    },
    {
        "concept_key": "motor-pa-plus",
        "label": "Motor PA Plus",
        "category": "addon",
        "asset_label": "Personal Accident",
        "description": "Tiered accidental death, disability, and hospital income coverage for driver and occupants.",
        "variants": ["Plan 1", "Plan 2", "Plan 3"],
        "match_dataset": ["motor pa plus", "pa plus", "takaful motor pa"],
        "sort_order": 33,
    },
    {
        "concept_key": "oto-360",
        "label": "OTO 360",
        "category": "addon",
        "asset_label": "Driver and Passenger Protection Plan",
        "description": "Comprehensive motor takaful coverage package with enhanced death and disability protection.",
        "variants": ["Plan 1", "Plan 2", "Plan 3"],
        "match_dataset": ["oto 360", "oto360", "takaful oto"],
        "sort_order": 34,
    },
]

GLOBAL_ALIASES = [
    ("24/7 Towing Assistance", "towing"),
    ("Emergency Towing Service", "towing"),
    ("Emergency Roadside Towing", "towing"),
    ("24-Hour Roadside Assistance", "roadside-assistance"),
    ("Emergency Roadside Assistance", "roadside-assistance"),
    ("Road Assist", "roadside-assistance"),
    ("Workmanship Warranty", "repair-workmanship-warranty"),
    ("Repair Workmanship Warranty", "repair-workmanship-warranty"),
    ("Panel Workshop Warranty", "repair-workmanship-warranty"),
    ("All Drivers", "all-drivers"),
    ("All Drivers Coverage", "all-drivers"),
    ("Unnamed Drivers Waiver", "all-drivers"),
    ("Personal Accident", "personal-accident"),
    ("Accidental Death / TPD", "personal-accident"),
    ("Takaful Accidental Death", "personal-accident"),
    ("Betterment Protection", "betterment-protection"),
    ("Waiver of Betterment", "betterment-protection"),
    ("New Parts Protection", "betterment-protection"),
    ("Brand New Spare Parts", "betterment-protection"),
    ("Total Loss / Theft Allowance", "total-loss-theft-allowance"),
    ("Car Theft Assistance", "total-loss-theft-allowance"),
    ("Loss of Vehicle Compassionate Allowance", "total-loss-theft-allowance"),
    ("Key Care", "key-replacement"),
    ("Car Key Replacement", "key-replacement"),
    ("Smart Key Replacement", "key-replacement"),
    ("Flood Relief Allowance", "flood-relief-allowance"),
    ("Flood Cash Relief", "flood-relief-allowance"),
    ("Flood Inconvenience Relief", "flood-relief-allowance"),
    ("Personal Belongings Theft", "personal-belongings-theft"),
    ("Snatch Theft & Smash Grab", "personal-belongings-theft"),
    ("Ambulance Fees", "ambulance-fees"),
    ("Emergency Ambulance Transport", "ambulance-fees"),
    ("Windscreen", "windscreen"),
    ("Windshield Damage", "windscreen"),
    ("Cermin Depan", "windscreen"),
    ("Special Perils", "special-perils"),
    ("Flood and Storm Damage", "special-perils"),
    ("Convulsion of Nature", "special-perils"),
    ("Strike, Riot & Civil Commotion", "strike-riot-civil-commotion"),
    ("SRCC", "strike-riot-civil-commotion"),
    ("Legal Liability to Passengers", "legal-liability-to-passengers"),
    ("LLP", "legal-liability-to-passengers"),
    ("Legal Liability of Passengers", "legal-liability-of-passengers"),
    ("LLOP", "legal-liability-of-passengers"),
    ("Legal Liability to Pillion", "legal-liability-to-pillion"),
    ("Medical Expenses", "medical-expenses"),
    ("Hospital Income", "hospital-income"),
    ("Daily Hospital Cash", "hospital-income"),
    ("Bereavement Allowance", "bereavement-allowance"),
    ("Funeral Expenses", "bereavement-allowance"),
    ("Replacement Car", "replacement-car"),
    ("Courtesy Car", "replacement-car"),
    ("Repaint / Spray Paint", "repaint-spray-paint"),
    ("Whole Car Spray Painting", "repaint-spray-paint"),
    ("Side Mirror Protection", "side-mirror-protection"),
    ("Wing Mirror", "side-mirror-protection"),
    ("Child Car Seat", "child-car-seat"),
    ("Baby Car Seat", "child-car-seat"),
    ("Replacement Cost", "replacement-cost"),
    ("Vehicle Accessories", "vehicle-accessories"),
    ("Audio / Sound System", "vehicle-accessories"),
    ("E-Hailing Extension", "e-hailing-extension"),
    ("Private Hire Endorsement", "e-hailing-extension"),
    ("Agreed Value / Market Value", "agreed-value-market-value"),
    ("Agreed Sum Insured", "agreed-value-market-value"),
    ("Cashback / No-Claim Cashback", "cashback-no-claim"),
    ("No-Claim Cashback", "cashback-no-claim"),
    ("Out-of-Pocket Allowance", "out-of-pocket-allowance"),
    ("Driver Passenger Protector", "driver-passenger-protector"),
    ("Driver Passenger Protector (Plan A)", "driver-passenger-protector"),
    ("Driver Passenger Protector (Plan B)", "driver-passenger-protector"),
    ("Driver Passenger Protector (Plan C)", "driver-passenger-protector"),
    ("Driver Passenger Protector (Plan D)", "driver-passenger-protector"),
    ("Private Car 365 Plan", "private-car-365"),
    ("Private Car 365 (Plan 1)", "private-car-365"),
    ("Private Car 365 (Plan 2)", "private-car-365"),
    ("Private Car 365 (Plan 3)", "private-car-365"),
    ("Private Car 365 (Plan 4)", "private-car-365"),
    ("Private Car 365 (Plan Ezy)", "private-car-365"),
    ("Motor PA Plus", "motor-pa-plus"),
    ("Motor PA Plus (Plan 1)", "motor-pa-plus"),
    ("Motor PA Plus (Plan 2)", "motor-pa-plus"),
    ("Motor PA Plus (Plan 3)", "motor-pa-plus"),
    ("OTO 360", "oto-360"),
    ("OTO 360 (Plan 1)", "oto-360"),
    ("OTO 360 (Plan 2)", "oto-360"),
    ("OTO 360 (Plan 3)", "oto-360"),
]


def cleanup_junk(db, dry_run: bool) -> list[str]:
    logs = []

    # 1. Clean junk / obsolete catalogs
    junk_catalogs = db.scalars(
        select(BenefitCatalog).where(
            BenefitCatalog.name.in_([
                "Towing",
                "Q-Drive Standard",
                "QBE Private Car",
                "AmAssurance Private Car",
                "Etiqa Motor Comprehensive",
                "Takaful myMotor Private Car (Draft)",
                "Takaful myMotor Private Car",
            ])
        )
    ).all()

    cat_ids = [c.id for c in junk_catalogs]
    if cat_ids:
        revisions = db.scalars(
            select(BenefitCatalogRevision).where(BenefitCatalogRevision.catalog_id.in_(cat_ids))
        ).all()
        rev_ids = [r.id for r in revisions]

        packages = (
            db.scalars(select(BenefitPackage).where(BenefitPackage.catalog_revision_id.in_(rev_ids))).all()
            if rev_ids
            else []
        )
        pkg_ids = [p.id for p in packages]

        for cat in junk_catalogs:
            logs.append(f"Hard-delete junk catalog '{cat.name}' (id={cat.id})")

        if not dry_run:
            db.execute(text("SET session_replication_role = 'replica'"))
            try:
                db.execute(
                    update(QuotationDraft)
                    .where(QuotationDraft.catalog_revision_id.in_(rev_ids))
                    .values(catalog_revision_id=None)
                )
                db.execute(
                    delete(TrashRecord).where(
                        TrashRecord.entity_type == "benefit_catalog",
                        TrashRecord.entity_id.in_(cat_ids),
                    )
                )
                if pkg_ids:
                    db.execute(delete(BenefitAlias).where(BenefitAlias.package_id.in_(pkg_ids)))
                    plans = db.scalars(
                        select(BenefitPackagePlan).where(BenefitPackagePlan.package_id.in_(pkg_ids))
                    ).all()
                    plan_ids = [pl.id for pl in plans]
                    if plan_ids:
                        db.execute(delete(BenefitPackagePlanItem).where(BenefitPackagePlanItem.plan_id.in_(plan_ids)))
                        db.execute(delete(BenefitPackagePlan).where(BenefitPackagePlan.id.in_(plan_ids)))

                if rev_ids:
                    db.execute(delete(BenefitPackage).where(BenefitPackage.catalog_revision_id.in_(rev_ids)))
                    db.execute(delete(BenefitRelation).where(BenefitRelation.catalog_revision_id.in_(rev_ids)))
                    db.execute(delete(CatalogOffering).where(CatalogOffering.catalog_revision_id.in_(rev_ids)))
                    db.execute(delete(BenefitCatalogRevision).where(BenefitCatalogRevision.id.in_(rev_ids)))

                for cat in junk_catalogs:
                    db.delete(cat)
                db.flush()
            finally:
                db.execute(text("SET session_replication_role = 'origin'"))

    # 2. Clean junk tiers (e.g. "Standard", "Towing 50km", "Towing Unlimited")
    junk_tiers = db.scalars(
        select(InsuranceProductTier).where(
            or_(
                InsuranceProductTier.name.in_(["Standard", "Towing 50km", "Towing Unlimited"]),
                InsuranceProductTier.tier_key.in_(["standard", "towing-50km", "towing-unlimited"]),
            )
        )
    ).all()
    if junk_tiers:
        tier_ids = [t.id for t in junk_tiers]
        for t in junk_tiers:
            logs.append(f"Hard-delete junk product tier '{t.name}' (key={t.tier_key})")
        if not dry_run:
            db.execute(text("SET session_replication_role = 'replica'"))
            try:
                db.execute(
                    update(QuotationDraft)
                    .where(QuotationDraft.tier_id.in_(tier_ids))
                    .values(tier_id=None)
                )
                db.execute(
                    delete(TrashRecord).where(
                        TrashRecord.entity_type == "product_tier",
                        TrashRecord.entity_id.in_(tier_ids),
                    )
                )
                for t in junk_tiers:
                    db.delete(t)
                db.flush()
            finally:
                db.execute(text("SET session_replication_role = 'origin'"))

    # 3. Clean junk / obsolete products
    junk_products = db.scalars(
        select(InsuranceProduct).where(
            or_(
                InsuranceProduct.product_key.in_([
                    "towing",
                    "q-drive",
                    "amassurance-private-car",
                    "etiqa-motor-comprehensive",
                    "qbe-private-car",
                    "takaful-mymotor-private-car",
                ]),
                InsuranceProduct.name.in_([
                    "Towing",
                    "Q-Drive",
                    "AmAssurance Private Car",
                    "Etiqa Motor Comprehensive",
                    "QBE Private Car",
                    "Takaful myMotor Private Car",
                ]),
            )
        )
    ).all()
    if junk_products:
        prod_ids = [p.id for p in junk_products]
        for prod in junk_products:
            logs.append(f"Hard-delete junk product '{prod.name}' (key={prod.product_key})")
        if not dry_run:
            db.execute(text("SET session_replication_role = 'replica'"))
            try:
                db.execute(
                    update(QuotationDraft)
                    .where(QuotationDraft.product_id.in_(prod_ids))
                    .values(product_id=None)
                )
                db.execute(
                    delete(TrashRecord).where(
                        TrashRecord.entity_type == "insurance_product",
                        TrashRecord.entity_id.in_(prod_ids),
                    )
                )
                db.execute(delete(BenefitAlias).where(BenefitAlias.product_id.in_(prod_ids)))
                db.execute(delete(InsuranceProductTier).where(InsuranceProductTier.product_id.in_(prod_ids)))
                for prod in junk_products:
                    db.delete(prod)
                db.flush()
            finally:
                db.execute(text("SET session_replication_role = 'origin'"))

    return logs


def seed_global_benefits(db, dry_run: bool) -> dict[str, BenefitConcept]:
    assets_by_label = {a.label: a for a in db.scalars(select(BusinessAsset).where(BusinessAsset.asset_kind == "benefit_art")).all()}
    concepts_by_key = {}

    for data in BENEFIT_CONCEPTS_DATA:
        key = data["concept_key"]
        concept = db.scalar(select(BenefitConcept).where(BenefitConcept.concept_key == key))
        asset = assets_by_label.get(data["asset_label"])

        if concept is None:
            concept = BenefitConcept(
                id=new_id(),
                concept_key=key,
                label=data["label"],
                status="active",
                revision=1,
            )
            if not dry_run:
                db.add(concept)

        if not dry_run:
            concept.label = data["label"]
            concept.description = data["description"]
            concept.default_asset_id = asset.id if asset else None
            concept.match_dataset = data["match_dataset"]
            concept.sort_order = data["sort_order"]
            concept.status = "active"
            concept.value_schema = {
                "category": data.get("category", "default" if data["sort_order"] <= 11 else "addon"),
                "variants": data.get("variants", []),
            }
            concept.description_variants = _derive_description_variant(data["description"])
        concepts_by_key[key] = concept

    # Purge any obsolete concepts not in the canonical 34 list
    valid_keys = {d["concept_key"] for d in BENEFIT_CONCEPTS_DATA}
    if not dry_run:
        for old_concept in db.scalars(select(BenefitConcept).where(~BenefitConcept.concept_key.in_(valid_keys))).all():
            db.execute(delete(BenefitAlias).where(BenefitAlias.benefit_id == old_concept.id))
            db.delete(old_concept)
        db.flush()
        db.commit()

    # Seed aliases
    for raw_phrase, ckey in GLOBAL_ALIASES:
        target_concept = concepts_by_key.get(ckey)
        if not target_concept:
            continue
        norm = _normalize_phrase(raw_phrase)
        existing = db.scalar(
            select(BenefitAlias).where(
                BenefitAlias.normalized_phrase == norm,
                BenefitAlias.scope == "global",
            )
        )
        if existing is None and not dry_run:
            alias = BenefitAlias(
                id=new_id(),
                scope="global",
                company_id=None,
                product_id=None,
                package_id=None,
                benefit_id=target_concept.id,
                phrase=raw_phrase.strip(),
                normalized_phrase=norm,
                status="active",
            )
            db.add(alias)

    if not dry_run:
        db.commit()

    return concepts_by_key


def seed_company_package_chains(db, dry_run: bool) -> list[str]:
    logs = []
    concepts = {bc.concept_key: bc for bc in db.scalars(select(BenefitConcept)).all()}
    segment = db.scalar(select(Segment).where(Segment.segment_key == "private"))
    vehicle = db.scalar(select(VehicleCategory).where(VehicleCategory.category_key == "car"))
    coverage = db.scalar(select(CoverageType).where(CoverageType.coverage_key == "comprehensive"))

    from app.models.tables import utcnow

    insurer_configs = [
        # ── 1. QBE (Add-on System) ───────────────────────────────────────────
        {
            "company_slug": "qbe",
            "company_name": "QBE",
            "products": [
                {
                    "product_key": "qbe-private-car-protector",
                    "product_name": "Private Car Protector",
                    "is_package_system": False,
                    "default_benefits": [
                        {"concept_key": "towing", "display_value": "As per policy"},
                        {"concept_key": "roadside-assistance", "display_value": "RM500"},
                        {"concept_key": "betterment-protection", "display_value": "Up to 10 years old vehicle age"},
                        {"concept_key": "total-loss-theft-allowance", "display_value": "5% or up to RM5,000 coverage, whichever is lower"},
                        {"concept_key": "key-replacement", "display_value": "Up to RM500"},
                    ],
                    "addons": [
                        {"concept_key": "windscreen"},
                        {"concept_key": "special-perils"},
                        {"concept_key": "strike-riot-civil-commotion"},
                        {"concept_key": "legal-liability-to-passengers"},
                        {"concept_key": "vehicle-accessories"},
                        {"concept_key": "out-of-pocket-allowance"},
                        {"concept_key": "driver-passenger-protector"},
                        {"concept_key": "flood-relief-allowance"},
                    ],
                }
            ],
        },

        # ── 2. AmAssurance / Liberty (Package System) ────────────────────────
        {
            "company_slug": "amassurance",
            "company_name": "AmAssurance",
            "products": [
                {
                    "product_key": "amassurance-private-car-comprehensive",
                    "product_name": "Private Car Comprehensive",
                    "is_package_system": True,
                    "packages": [
                        {
                            "package_key": "lite",
                            "name": "auto365 Comprehensive Lite",
                            "sort_order": 1,
                            "default_benefits": [
                                {"concept_key": "towing"},
                                {"concept_key": "roadside-assistance"},
                                {"concept_key": "repair-workmanship-warranty"},
                            ],
                            "addons": [
                                {"concept_key": "all-drivers"},
                                {"concept_key": "personal-accident"},
                                {"concept_key": "betterment-protection"},
                                {"concept_key": "total-loss-theft-allowance"},
                                {"concept_key": "key-replacement"},
                                {"concept_key": "flood-relief-allowance"},
                                {"concept_key": "personal-belongings-theft"},
                                {"concept_key": "ambulance-fees"},
                                {"concept_key": "windscreen"},
                                {"concept_key": "special-perils"},
                                {"concept_key": "legal-liability-to-passengers"},
                                {"concept_key": "legal-liability-of-passengers"},
                                {"concept_key": "strike-riot-civil-commotion"},
                                {"concept_key": "e-hailing-extension"},
                                {"concept_key": "private-car-365"},
                            ],
                        },
                        {
                            "package_key": "plus",
                            "name": "auto365 Comprehensive Plus",
                            "sort_order": 2,
                            "default_benefits": [
                                {"concept_key": "towing"},
                                {"concept_key": "roadside-assistance"},
                                {"concept_key": "repair-workmanship-warranty"},
                                {"concept_key": "all-drivers"},
                                {"concept_key": "flood-relief-allowance"},
                                {"concept_key": "key-replacement"},
                                {"concept_key": "personal-belongings-theft"},
                                {"concept_key": "ambulance-fees"},
                            ],
                            "addons": [
                                {"concept_key": "personal-accident"},
                                {"concept_key": "betterment-protection"},
                                {"concept_key": "total-loss-theft-allowance"},
                                {"concept_key": "windscreen"},
                                {"concept_key": "special-perils"},
                                {"concept_key": "legal-liability-to-passengers"},
                                {"concept_key": "legal-liability-of-passengers"},
                                {"concept_key": "strike-riot-civil-commotion"},
                                {"concept_key": "e-hailing-extension"},
                                {"concept_key": "private-car-365"},
                            ],
                        },
                        {
                            "package_key": "premier",
                            "name": "auto365 Comprehensive Premier",
                            "sort_order": 3,
                            "default_benefits": [
                                {"concept_key": "towing"},
                                {"concept_key": "roadside-assistance"},
                                {"concept_key": "repair-workmanship-warranty"},
                                {"concept_key": "all-drivers"},
                                {"concept_key": "flood-relief-allowance"},
                                {"concept_key": "key-replacement"},
                                {"concept_key": "personal-belongings-theft"},
                                {"concept_key": "ambulance-fees"},
                                {"concept_key": "total-loss-theft-allowance"},
                                {"concept_key": "betterment-protection"},
                            ],
                            "addons": [
                                {"concept_key": "personal-accident"},
                                {"concept_key": "windscreen"},
                                {"concept_key": "special-perils"},
                                {"concept_key": "legal-liability-to-passengers"},
                                {"concept_key": "legal-liability-of-passengers"},
                                {"concept_key": "strike-riot-civil-commotion"},
                                {"concept_key": "e-hailing-extension"},
                                {"concept_key": "private-car-365"},
                            ],
                        },
                        {
                            "package_key": "all-inclusive",
                            "name": "Comprehensive All-Inclusive",
                            "sort_order": 4,
                            "default_benefits": [
                                {"concept_key": "towing"},
                                {"concept_key": "roadside-assistance"},
                                {"concept_key": "repair-workmanship-warranty"},
                                {"concept_key": "all-drivers"},
                                {"concept_key": "personal-accident"},
                                {"concept_key": "betterment-protection"},
                                {"concept_key": "total-loss-theft-allowance"},
                                {"concept_key": "key-replacement"},
                                {"concept_key": "flood-relief-allowance"},
                                {"concept_key": "personal-belongings-theft"},
                                {"concept_key": "ambulance-fees"},
                            ],
                            "addons": [],
                        },
                    ],
                }
            ],
        },

        # ── 3. Takaful Malaysia (Add-on System) ──────────────────────────────
        {
            "company_slug": "takaful-malaysia",
            "company_name": "Takaful Malaysia",
            "products": [
                {
                    "product_key": "takaful-mymotor-private-motor",
                    "product_name": "Takaful myMotor - Private Motor",
                    "is_package_system": False,
                    "default_benefits": [
                        {"concept_key": "personal-accident", "label_override": "Accidental Death / Total Permanent Disability", "display_value": "RM15,000 per life"},
                        {"concept_key": "towing", "display_value": "RM200"},
                        {"concept_key": "roadside-assistance", "display_value": "24/7"},
                    ],
                    "addons": [
                        {"concept_key": "windscreen"},
                        {"concept_key": "special-perils"},
                        {"concept_key": "legal-liability-to-passengers"},
                        {"concept_key": "legal-liability-of-passengers"},
                        {"concept_key": "strike-riot-civil-commotion"},
                        {"concept_key": "cashback-no-claim"},
                        {"concept_key": "motor-pa-plus"},
                        {"concept_key": "betterment-protection", "label_override": "Waiver of Betterment"},
                    ],
                },
                {
                    "product_key": "myclick-takaful-car",
                    "product_name": "myClick Takaful Car",
                    "is_package_system": False,
                    "default_benefits": [
                        {"concept_key": "personal-accident"},
                        {"concept_key": "all-drivers"},
                        {"concept_key": "towing"},
                        {"concept_key": "roadside-assistance"},
                        {"concept_key": "repair-workmanship-warranty"},
                    ],
                    "addons": [
                        {"concept_key": "windscreen"},
                        {"concept_key": "special-perils"},
                        {"concept_key": "flood-relief-allowance"},
                        {"concept_key": "repair-allowance-cart"},
                        {"concept_key": "key-replacement"},
                        {"concept_key": "legal-liability-to-passengers"},
                        {"concept_key": "legal-liability-of-passengers"},
                        {"concept_key": "strike-riot-civil-commotion"},
                        {"concept_key": "betterment-protection"},
                        {"concept_key": "agreed-value-market-value"},
                        {"concept_key": "cashback-no-claim"},
                        {"concept_key": "motor-pa-plus"},
                    ],
                },
            ],
        },

        # ── 4. Etiqa (Add-on System) ─────────────────────────────────────────
        {
            "company_slug": "etiqa",
            "company_name": "Etiqa",
            "products": [
                {
                    "product_key": "etiqa-comprehensive-private-car",
                    "product_name": "Comprehensive Private Car Insurance / Takaful",
                    "is_package_system": False,
                    "default_benefits": [
                        {"concept_key": "towing", "display_value": "Up to 200 km"},
                        {"concept_key": "roadside-assistance", "display_value": "24/7"},
                        {"concept_key": "all-drivers", "display_value": "Any Authorised Driver"},
                    ],
                    "addons": [
                        {"concept_key": "windscreen"},
                        {"concept_key": "special-perils"},
                        {"concept_key": "repair-allowance-cart", "label_override": "Repair Allowance / Cash Assistance"},
                        {"concept_key": "oto-360"},
                        {"concept_key": "child-car-seat"},
                        {"concept_key": "repaint-spray-paint"},
                        {"concept_key": "replacement-cost"},
                        {"concept_key": "betterment-protection"},
                        {"concept_key": "strike-riot-civil-commotion"},
                        {"concept_key": "cashback-no-claim"},
                    ],
                }
            ],
        },
    ]

    for conf in insurer_configs:
        c_slug = conf["company_slug"]
        c_name = conf["company_name"]
        company = db.scalar(select(InsuranceCompany).where(InsuranceCompany.slug == c_slug))
        if not company:
            logs.append(f"Company {c_name} not found, skipping")
            continue

        for p_data in conf["products"]:
            p_key = p_data["product_key"]
            p_name = p_data["product_name"]

            product = db.scalar(select(InsuranceProduct).where(
                InsuranceProduct.company_id == company.id,
                InsuranceProduct.product_key == p_key,
            ))
            if not product:
                product = InsuranceProduct(
                    id=new_id(),
                    company_id=company.id,
                    product_key=p_key,
                    name=p_name,
                    status="active",
                    revision=1,
                )
                if not dry_run:
                    db.add(product)
                    db.flush()
                logs.append(f"Created product '{p_name}' for {c_name}")
            elif not dry_run:
                product.name = p_name
                product.status = "active"
                db.flush()

            # Ensure Catalog exists and is populated
            catalog = db.scalar(select(BenefitCatalog).where(BenefitCatalog.product_id == product.id)) if product else None
            if not catalog:
                logs.append(f"Create canonical configuration for {c_name} -> '{p_name}'")
                if not dry_run:
                    catalog = BenefitCatalog(
                        id=new_id(),
                        company_id=company.id,
                        product_id=product.id,
                        segment_id=segment.id if segment else None,
                        vehicle_category_id=vehicle.id if vehicle else None,
                        coverage_type_id=coverage.id if coverage else None,
                        name=p_name,
                        status="active",
                        revision=1,
                    )
                    db.add(catalog)
                    db.flush()

                    rev_id = new_id()
                    rev = BenefitCatalogRevision(
                        id=rev_id,
                        catalog_id=catalog.id,
                        revision_number=1,
                        state="draft",
                        content_hash="",
                        published_by=None,
                    )
                    db.add(rev)
                    db.flush()

                    if p_data.get("is_package_system"):
                        # Package System with named tiers (AmAssurance)
                        first_pkg_id = None
                        for pkg_data in p_data["packages"]:
                            pkg_id = new_id()
                            if first_pkg_id is None:
                                first_pkg_id = pkg_id
                            pkg = BenefitPackage(
                                id=pkg_id,
                                catalog_revision_id=rev_id,
                                package_key=pkg_data["package_key"],
                                name=pkg_data["name"],
                                package_kind="comprehensive",
                                sort_order=pkg_data["sort_order"],
                                status="active",
                                revision=1,
                            )
                            db.add(pkg)
                            db.flush()

                            order_idx = 1
                            # Default Benefits
                            for def_b in pkg_data.get("default_benefits", []):
                                c_key = def_b["concept_key"]
                                if c_key not in concepts:
                                    continue
                                off = CatalogOffering(
                                    id=new_id(),
                                    catalog_revision_id=rev_id,
                                    offering_key=f"{pkg_data['package_key']}-{c_key}",
                                    concept_id=concepts[c_key].id,
                                    offering_kind="base",
                                    applies_to_type="package",
                                    applies_to_id=pkg_id,
                                    role="included",
                                    label_override=def_b.get("label_override"),
                                    display_value=def_b.get("display_value") or "Included",
                                    typed_value={"type": "text", "value": def_b.get("display_value") or "Included"},
                                    sort_order=order_idx,
                                    status="active",
                                )
                                db.add(off)
                                order_idx += 1

                            # Add-ons
                            for add_b in pkg_data.get("addons", []):
                                c_key = add_b["concept_key"]
                                if c_key not in concepts:
                                    continue
                                off = CatalogOffering(
                                    id=new_id(),
                                    catalog_revision_id=rev_id,
                                    offering_key=f"{pkg_data['package_key']}-addon-{c_key}-{order_idx}",
                                    concept_id=concepts[c_key].id,
                                    offering_kind="optional",
                                    applies_to_type="package",
                                    applies_to_id=pkg_id,
                                    role="addon_option",
                                    label_override=add_b.get("label_override"),
                                    display_value=add_b.get("display_value") or "Optional",
                                    typed_value={"type": "text", "value": add_b.get("display_value") or "Optional"},
                                    sort_order=order_idx,
                                    status="active",
                                )
                                db.add(off)
                                order_idx += 1

                        catalog.package_id = first_pkg_id
                        db.flush()

                    else:
                        # Add-on System (Single Product mode)
                        order_idx = 1
                        # Default Benefits
                        for def_b in p_data.get("default_benefits", []):
                            c_key = def_b["concept_key"]
                            if c_key not in concepts:
                                continue
                            off = CatalogOffering(
                                id=new_id(),
                                catalog_revision_id=rev_id,
                                offering_key=f"{p_key}-def-{c_key}",
                                concept_id=concepts[c_key].id,
                                offering_kind="base",
                                applies_to_type=None,
                                applies_to_id=None,
                                role="included",
                                label_override=def_b.get("label_override"),
                                display_value=def_b.get("display_value") or "Included",
                                typed_value={"type": "text", "value": def_b.get("display_value") or "Included"},
                                sort_order=order_idx,
                                status="active",
                            )
                            db.add(off)
                            order_idx += 1

                        # Add-ons
                        for add_b in p_data.get("addons", []):
                            c_key = add_b["concept_key"]
                            if c_key not in concepts:
                                continue
                            off = CatalogOffering(
                                id=new_id(),
                                catalog_revision_id=rev_id,
                                offering_key=f"{p_key}-addon-{c_key}",
                                concept_id=concepts[c_key].id,
                                offering_kind="optional",
                                applies_to_type=None,
                                applies_to_id=None,
                                role="addon_option",
                                label_override=add_b.get("label_override"),
                                display_value=add_b.get("display_value") or "Optional",
                                typed_value={"type": "text", "value": add_b.get("display_value") or "Optional"},
                                sort_order=order_idx,
                                status="active",
                            )
                            db.add(off)
                            order_idx += 1

                    db.flush()
                    content_payload = _revision_content_payload(db, rev)
                    rev.content_hash = canonical_context_hash(content_payload)
                    rev.state = "published"
                    rev.published_at = utcnow()
                    db.flush()
                    logs.append(f"Published catalog configuration for {c_name} -> '{p_name}'")

    return logs


COMPANY_ALIASES_MAP = {
    "takaful-malaysia": [
        "STMB",
        "Syarikat Takaful Malaysia Am Berhad",
        "Syarikat Takaful Malaysia",
        "Takaful Malaysia Am",
        "Takaful Malaysia",
        "Takaful myMotor",
        "Takaful myClick",
    ],
    "amassurance": [
        "AmAssurance",
        "AmGen",
        "AmGeneral",
        "AmGeneral Insurance",
        "Kurnia",
        "auto365",
    ],
    "lonpac": [
        "Lonpac",
        "Lonpac Insurance",
        "Lonpac Insurance Bhd",
        "Lonpac Insurance Berhad",
    ],
    "liberty": [
        "Liberty",
        "Liberty Insurance",
        "Liberty General Insurance",
        "Liberty General Insurance Berhad",
    ],
    "tune-protect": [
        "Tune",
        "Tune Protect",
        "Tune Insurance",
        "Motor Easy",
    ],
    "etiqa": [
        "Etiqa",
        "Etiqa General Insurance",
        "Etiqa General Takaful",
        "Etiqa Takaful",
        "Etiqa Insurance",
    ],
    "qbe": [
        "QBE",
        "QBE Insurance",
        "QBE Insurance (Malaysia) Berhad",
    ],
    "berjaya-sompo": [
        "Berjaya Sompo",
        "Berjaya Sompo Insurance",
        "Sompo",
    ],
}


def seed_company_aliases(db, dry_run: bool) -> list[str]:
    logs = []
    for slug, aliases in COMPANY_ALIASES_MAP.items():
        company = db.scalar(select(InsuranceCompany).where(InsuranceCompany.slug == slug))
        if not company:
            continue
        for raw_alias in aliases:
            norm = re.sub(r"[^a-z0-9]+", " ", raw_alias.lower()).strip()
            existing = db.scalar(select(CompanyAlias).where(CompanyAlias.normalized_alias == norm))
            if existing is None:
                alias_obj = CompanyAlias(
                    id=new_id(),
                    company_id=company.id,
                    alias=raw_alias,
                    normalized_alias=norm,
                    alias_kind="detection",
                    status="active",
                )
                if not dry_run:
                    db.add(alias_obj)
                logs.append(f"Added alias '{raw_alias}' -> {company.name}")
    if not dry_run:
        db.flush()
    return logs


def main():
    parser = argparse.ArgumentParser(description="Seed demo benefits and configurations.")
    parser.add_argument("--apply", action="store_true", help="Apply changes to the database (default is dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="Perform a trial run with no changes committed (default)")
    args = parser.parse_args()

    dry_run = not args.apply
    mode_str = "DRY-RUN" if dry_run else "APPLY"
    print(f"=== Starting seed-demo.py [{mode_str}] ===")

    with SessionLocal() as db:
        try:
            cleanup_logs = cleanup_junk(db, dry_run=dry_run)
            for log in cleanup_logs:
                print(f"[CLEANUP] {log}")

            concepts = seed_global_benefits(db, dry_run=dry_run)
            print(f"[BENEFITS] Upserted {len(concepts)} Global Benefits with assets and {len(GLOBAL_ALIASES)} scoped aliases.")

            alias_logs = seed_company_aliases(db, dry_run=dry_run)
            print(f"[ALIASES] Added {len(alias_logs)} company aliases.")

            chain_logs = seed_company_package_chains(db, dry_run=dry_run)
            for log in chain_logs:
                print(f"[CONFIG] {log}")

            if dry_run:
                print("\n[DRY-RUN COMPLETE] No database changes committed. Run with --apply to commit.")
            else:
                db.commit()
                print("\n[APPLY COMPLETE] Database changes successfully committed.")
        except Exception as e:
            db.rollback()
            print(f"\n[ERROR in seed-demo]: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()
