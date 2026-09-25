"""Seed draft (unpublished) catalog configurations extracted from reference DOCX.

Usage:
    python commands/seed-docx-draft.py           # Dry-run report
    python commands/seed-docx-draft.py --apply   # Commit draft configurations
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import docx
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.tables import (
    BenefitAlias,
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    BenefitPackage,
    BusinessAsset,
    CatalogOffering,
    CoverageType,
    InsuranceCompany,
    InsuranceProduct,
    Segment,
    VehicleCategory,
    new_id,
)
from app.rendering.render_context import canonical_context_hash

DOCX_CANDIDATES = [
    ROOT / "fix" / "RiskLocker_Malaysia_Motor_Comprehensive_Packages_Benefits_Addons_2026.docx",
    ROOT / "Malaysia_Motor_Insurance_Quick_Benefits_Addons_2026.docx",
]

NEW_GLOBAL_BENEFITS = [
    {
        "concept_key": "roadside-assistance",
        "label": "Roadside Assistance",
        "asset_label": "Emergency Roadside Assistance",
        "description": "24/7 emergency roadside support and auto assistance services.",
        "match_dataset": ["roadside", "auto assist", "road assist", "tele bantuan", "breakdown assistance"],
        "sort_order": 7,
    },
    {
        "concept_key": "all-drivers",
        "label": "All Drivers Waiver",
        "asset_label": "All Drivers Coverage",
        "description": "Coverage for all authorised drivers with unnamed-driver excess waiver.",
        "match_dataset": ["all drivers", "unnamed driver", "all authorised drivers", "driver waiver"],
        "sort_order": 8,
    },
    {
        "concept_key": "betterment",
        "label": "Betterment Protection",
        "asset_label": "Waiver of Betterment",
        "description": "Waiver of betterment costs and brand-new spare parts replacement guarantee.",
        "match_dataset": ["betterment", "waiver of betterment", "new parts protection"],
        "sort_order": 9,
    },
    {
        "concept_key": "total-loss-theft-allowance",
        "label": "Total Loss & Theft Allowance",
        "asset_label": "Car Theft / Total Loss Assistance",
        "description": "Cash payout allowance following total loss or theft of the vehicle.",
        "match_dataset": ["total loss", "theft allowance", "convenience cash", "total loss allowance"],
        "sort_order": 10,
    },
    {
        "concept_key": "personal-accident",
        "label": "Personal Accident",
        "asset_label": "Personal Accident",
        "description": "Accidental death and permanent disablement protection for driver and passengers.",
        "match_dataset": ["personal accident", "driver passenger protector", "pa plus", "motorist pa"],
        "sort_order": 11,
    },
    {
        "concept_key": "ambulance-fees",
        "label": "Ambulance Fees",
        "asset_label": "Ambulance Fees",
        "description": "Reimbursement of emergency ambulance medical transportation charges.",
        "match_dataset": ["ambulance", "ambulance fees", "ambulance reimbursement"],
        "sort_order": 12,
    },
    {
        "concept_key": "personal-belongings-theft",
        "label": "Personal Belongings Theft",
        "asset_label": "Window Snatch Theft / Smash and Grab",
        "description": "Reimbursement for stolen personal effects from locked vehicle or snatch theft.",
        "match_dataset": ["personal belongings", "snatch theft", "belongings theft", "window snatch"],
        "sort_order": 13,
    },
    {
        "concept_key": "repair-allowance",
        "label": "Repair / CART Allowance",
        "asset_label": "Transportation Allowance",
        "description": "Daily cash compensation or transportation allowance during vehicle accident repairs.",
        "match_dataset": [
            "cart",
            "repair allowance",
            "compensation for assessed repair time",
            "transport allowance",
            "transportation of damage vehicle",
            "damage vehicle transportation",
        ],
        "sort_order": 14,
    },
    {
        "concept_key": "passenger-liability",
        "label": "Passenger Liability & Risks",
        "asset_label": "Legal Liability to Passengers",
        "description": "Legal liability coverage and protection against claims from passengers.",
        "match_dataset": [
            "passenger liability",
            "legal liability to passenger",
            "legal liability to passengers",
            "llp",
            "passenger risks",
            "passenger risks employees",
            "passenger risks commercial",
            "passenger risk",
        ],
        "sort_order": 15,
    },
    {
        "concept_key": "agreed-value",
        "label": "Agreed Value Settlement",
        "asset_label": "Agreed Value / Market Value Settlement",
        "description": "Settlement payout based on agreed sum insured value without market depreciation.",
        "match_dataset": ["agreed value", "agreed sum insured", "market value settlement"],
        "sort_order": 16,
    },
    {
        "concept_key": "bereavement-allowance",
        "label": "Bereavement Allowance",
        "asset_label": "Bereavement Allowance",
        "description": "Compassionate funeral and bereavement cash support for policyholder or family.",
        "match_dataset": ["bereavement", "funeral allowance", "compassionate cash"],
        "sort_order": 17,
    },
    {
        "concept_key": "brand-new-spare-parts",
        "label": "Brand New Spare Parts",
        "asset_label": "Brand New Spare Parts",
        "description": "Guarantee of 100% original brand-new OEM spare parts for accident repairs.",
        "match_dataset": ["brand new spare parts", "oem parts", "new parts replacement"],
        "sort_order": 18,
    },
    {
        "concept_key": "child-car-seat",
        "label": "Child Car Seat Coverage",
        "asset_label": "Child Car Seat Coverage",
        "description": "Reimbursement to replace or repair damaged child car safety seats after an accident.",
        "match_dataset": ["child car seat", "baby car seat", "child safety seat"],
        "sort_order": 19,
    },
    {
        "concept_key": "compassionate-allowance",
        "label": "Compassionate Allowance",
        "asset_label": "Compassionate Allowance for Loss of Vehicle",
        "description": "Immediate cash assistance in the event of total vehicle loss or severe accident.",
        "match_dataset": ["compassionate allowance", "loss of vehicle allowance", "compassionate relief"],
        "sort_order": 20,
    },
    {
        "concept_key": "replacement-car",
        "label": "Courtesy / Replacement Car",
        "asset_label": "Courtesy Car / Replacement Car",
        "description": "Temporary replacement vehicle provided while insured car is undergoing approved accident repair.",
        "match_dataset": ["courtesy car", "replacement car", "temporary vehicle"],
        "sort_order": 21,
    },
    {
        "concept_key": "daily-hospital-income",
        "label": "Daily Hospital Income",
        "asset_label": "Daily Hospital Income",
        "description": "Daily hospital cash income benefit for hospitalisation resulting from a motor accident.",
        "match_dataset": ["daily hospital income", "hospital cash", "hospitalisation benefit"],
        "sort_order": 22,
    },
    {
        "concept_key": "document-replacement",
        "label": "Document Replacement",
        "asset_label": "Document Replacement",
        "description": "Reimbursement of government fees to replace lost driving license, identity card, or vehicle grant.",
        "match_dataset": ["document replacement", "license replacement", "lost ic allowance"],
        "sort_order": 23,
    },
    {
        "concept_key": "driver-passenger-protection",
        "label": "Driver & Passenger Protection",
        "asset_label": "Driver and Passenger Protection Plan",
        "description": "Comprehensive personal accident protection plan for the driver and all passengers.",
        "match_dataset": ["driver and passenger protection", "driver protector", "passenger protection plan"],
        "sort_order": 24,
    },
    {
        "concept_key": "e-hailing",
        "label": "e-Hailing Extension",
        "asset_label": "e-Hailing / Private Hire Extension",
        "description": "Coverage extension for private hire and e-hailing driving operations.",
        "match_dataset": ["e-hailing", "ehailing", "grab cover", "private hire"],
        "sort_order": 25,
    },
    {
        "concept_key": "flood-coverage",
        "label": "Flood Damage Protection",
        "asset_label": "Flood Coverage / Flood Damage Protection",
        "description": "Direct vehicle repair coverage for water damage, overflow, and flood submergence.",
        "match_dataset": ["flood damage protection", "flood coverage", "water damage"],
        "sort_order": 26,
    },
    {
        "concept_key": "hotel-accommodation",
        "label": "Hotel Accommodation Allowance",
        "asset_label": "Hotel Accommodation Allowance",
        "description": "Emergency hotel lodging allowance when stranded away from home due to breakdown or accident.",
        "match_dataset": ["hotel accommodation", "hotel allowance", "emergency lodging"],
        "sort_order": 27,
    },
    {
        "concept_key": "legal-liability-of-passengers",
        "label": "Legal Liability of Passengers",
        "asset_label": "Legal Liability of Passengers",
        "description": "Indemnification against third party property damage caused by negligent acts of passengers.",
        "match_dataset": ["legal liability of passengers", "llop", "passenger negligent acts"],
        "sort_order": 28,
    },
    {
        "concept_key": "medical-expenses",
        "label": "Medical Expenses",
        "asset_label": "Medical Expenses",
        "description": "Reimbursement for emergency medical treatment and hospitalization following a road accident.",
        "match_dataset": ["medical expenses", "medical reimbursement", "clinical treatment"],
        "sort_order": 29,
    },
    {
        "concept_key": "ncd-cashback",
        "label": "No-Claim Cashback",
        "asset_label": "No-Claim Cashback / NCD / Cashback Reward",
        "description": "Cash rebate reward for maintaining a claim-free record during the policy year.",
        "match_dataset": ["ncd cashback", "cashback reward", "no claim rebate"],
        "sort_order": 30,
    },
    {
        "concept_key": "out-of-pocket-allowance",
        "label": "Out-of-Pocket Allowance",
        "asset_label": "Out-of-Pocket Allowance",
        "description": "Fixed cash allowance to cover incidental and out-of-pocket expenses during accident repair.",
        "match_dataset": ["out of pocket allowance", "incidental expenses", "out of pocket cash"],
        "sort_order": 31,
    },
    {
        "concept_key": "replacement-cost",
        "label": "Replacement Cost Benefit",
        "asset_label": "Replacement Cost Benefit",
        "description": "Option to receive a brand-new replacement vehicle in case of total loss within policy tenure.",
        "match_dataset": ["replacement cost benefit", "car replacement benefit", "new car replacement"],
        "sort_order": 32,
    },
    {
        "concept_key": "side-mirror",
        "label": "Side Mirror Coverage",
        "asset_label": "Side Mirror Coverage",
        "description": "Dedicated repair and replacement benefit for exterior wing mirrors and electronic folding units.",
        "match_dataset": ["side mirror", "wing mirror", "side mirror coverage"],
        "sort_order": 33,
    },
    {
        "concept_key": "strike-riot-civil-commotion",
        "label": "Strike, Riot & Civil Commotion",
        "asset_label": "Strike, Riot and Civil Commotion",
        "description": "Protection against vehicle damage caused by strikes, riots, demonstrations, or civil unrest.",
        "match_dataset": ["strike riot", "srcc", "civil commotion", "riots and strikes"],
        "sort_order": 34,
    },
    {
        "concept_key": "whole-car-spray-painting",
        "label": "Whole Car Spray Painting",
        "asset_label": "Whole Car Spray Painting / New Coat of Paint",
        "description": "Allowance for full vehicle re-spray painting following partial accident bodywork repairs.",
        "match_dataset": ["whole car spray", "spray painting", "new coat of paint", "full respray"],
        "sort_order": 35,
    },
]

DRAFT_CONFIGURATIONS = [
    {
        "company_slug": "liberty",
        "product_name": "Liberty Private Car Comprehensive",
        "product_key": "liberty-private-car-comprehensive",
        "catalog_name": "Liberty Private Car Comprehensive (Draft)",
        "packages": [
            {
                "package_key": "liberty-auto365-lite",
                "name": "auto365 Comprehensive Lite",
                "offerings": [
                    {"concept": "towing", "role": "included", "kind": "base", "val": "RM 200", "typed": {"type": "money", "value": "200", "currency": "MYR", "semantic_role": "insured_limit"}},
                    {"concept": "roadside-assistance", "role": "included", "kind": "base", "val": "24/7", "typed": {"type": "text", "value": "24/7"}},
                    {"concept": "repair-workmanship-warranty", "role": "included", "kind": "base", "val": "3 years", "typed": {"type": "duration", "unit": "years", "duration": 3}},
                    {"concept": "towing", "role": "addon_option", "kind": "upgrade", "val": "150 km", "typed": {"type": "distance", "unit": "km", "distance": 150}},
                    {"concept": "all-drivers", "role": "addon_option", "kind": "optional", "val": "Included", "typed": {"type": "text", "value": "Included"}},
                    {"concept": "windscreen", "role": "addon_option", "kind": "optional", "val": "RM 1,000", "typed": {"type": "money", "value": "1000", "currency": "MYR", "semantic_role": "insured_limit"}},
                    {"concept": "special-perils", "role": "addon_option", "kind": "optional", "val": "RM 50,000", "typed": {"type": "money", "value": "50000", "currency": "MYR", "semantic_role": "insured_limit"}},
                ],
            },
            {
                "package_key": "liberty-auto365-plus",
                "name": "auto365 Comprehensive Plus",
                "offerings": [
                    {"concept": "towing", "role": "included", "kind": "base", "val": "RM 200", "typed": {"type": "money", "value": "200", "currency": "MYR", "semantic_role": "insured_limit"}},
                    {"concept": "roadside-assistance", "role": "included", "kind": "base", "val": "24/7", "typed": {"type": "text", "value": "24/7"}},
                    {"concept": "repair-workmanship-warranty", "role": "included", "kind": "base", "val": "3 years", "typed": {"type": "duration", "unit": "years", "duration": 3}},
                    {"concept": "all-drivers", "role": "included", "kind": "base", "val": "Included", "typed": {"type": "text", "value": "Included"}},
                    {"concept": "flood", "role": "included", "kind": "base", "val": "RM 1,500", "typed": {"type": "money", "value": "1500", "currency": "MYR", "semantic_role": "insured_limit"}},
                    {"concept": "key-replacement", "role": "included", "kind": "base", "val": "RM 500", "typed": {"type": "money", "value": "500", "currency": "MYR", "semantic_role": "insured_limit"}},
                    {"concept": "personal-belongings-theft", "role": "included", "kind": "base", "val": "RM 500", "typed": {"type": "money", "value": "500", "currency": "MYR", "semantic_role": "insured_limit"}},
                    {"concept": "ambulance-fees", "role": "included", "kind": "base", "val": "RM 500", "typed": {"type": "money", "value": "500", "currency": "MYR", "semantic_role": "insured_limit"}},
                    {"concept": "windscreen", "role": "addon_option", "kind": "optional", "val": "RM 1,000", "typed": {"type": "money", "value": "1000", "currency": "MYR", "semantic_role": "insured_limit"}},
                    {"concept": "special-perils", "role": "addon_option", "kind": "optional", "val": "RM 50,000", "typed": {"type": "money", "value": "50000", "currency": "MYR", "semantic_role": "insured_limit"}},
                ],
            },
        ],
    },
    {
        "company_slug": "takaful-malaysia",
        "product_name": "Takaful myMotor Private Car",
        "product_key": "takaful-mymotor-private-car",
        "catalog_name": "Takaful myMotor Private Car (Draft)",
        "packages": [
            {
                "package_key": "stmb-mymotor-base",
                "name": "Takaful myMotor Base",
                "offerings": [
                    {"concept": "personal-accident", "role": "included", "kind": "base", "val": "RM 15,000", "typed": {"type": "money", "value": "15000", "currency": "MYR", "semantic_role": "insured_limit"}},
                    {"concept": "towing", "role": "included", "kind": "base", "val": "50 km", "typed": {"type": "distance", "unit": "km", "distance": 50}},
                    {"concept": "roadside-assistance", "role": "included", "kind": "base", "val": "24/7", "typed": {"type": "text", "value": "24/7"}},
                    {"concept": "windscreen", "role": "addon_option", "kind": "optional", "val": "RM 1,000", "typed": {"type": "money", "value": "1000", "currency": "MYR", "semantic_role": "insured_limit"}},
                    {"concept": "special-perils", "role": "addon_option", "kind": "optional", "val": "RM 50,000", "typed": {"type": "money", "value": "50000", "currency": "MYR", "semantic_role": "insured_limit"}},
                ],
            },
            {
                "package_key": "stmb-myclick-motor",
                "name": "Takaful myClick Motor",
                "offerings": [
                    {"concept": "personal-accident", "role": "included", "kind": "base", "val": "RM 15,000", "typed": {"type": "money", "value": "15000", "currency": "MYR", "semantic_role": "insured_limit"}},
                    {"concept": "all-drivers", "role": "included", "kind": "base", "val": "Included", "typed": {"type": "text", "value": "Included"}},
                    {"concept": "towing", "role": "included", "kind": "base", "val": "50 km", "typed": {"type": "distance", "unit": "km", "distance": 50}},
                    {"concept": "roadside-assistance", "role": "included", "kind": "base", "val": "24/7", "typed": {"type": "text", "value": "24/7"}},
                    {"concept": "repair-workmanship-warranty", "role": "included", "kind": "base", "val": "6 months", "typed": {"type": "duration", "unit": "months", "duration": 6}},
                    {"concept": "windscreen", "role": "addon_option", "kind": "optional", "val": "RM 1,000", "typed": {"type": "money", "value": "1000", "currency": "MYR", "semantic_role": "insured_limit"}},
                    {"concept": "special-perils", "role": "addon_option", "kind": "optional", "val": "RM 50,000", "typed": {"type": "money", "value": "50000", "currency": "MYR", "semantic_role": "insured_limit"}},
                    {"concept": "key-replacement", "role": "addon_option", "kind": "optional", "val": "RM 1,000", "typed": {"type": "money", "value": "1000", "currency": "MYR", "semantic_role": "insured_limit"}},
                ],
            },
        ],
    },
    {
        "company_slug": "lonpac",
        "product_name": "Lonpac Private Car Secure",
        "product_key": "lonpac-private-car-secure",
        "catalog_name": "Lonpac Private Car Secure (Draft)",
        "packages": [
            {
                "package_key": "lonpac-private-car-secure-base",
                "name": "Private Car Secure",
                "offerings": [
                    {"concept": "repair-allowance", "role": "included", "kind": "base", "val": "RM 75", "typed": {"type": "money", "value": "75", "currency": "MYR", "semantic_role": "daily_allowance"}},
                    {"concept": "all-drivers", "role": "included", "kind": "base", "val": "Included", "typed": {"type": "text", "value": "Included"}},
                    {"concept": "roadside-assistance", "role": "included", "kind": "base", "val": "Included", "typed": {"type": "text", "value": "Included"}},
                    {"concept": "windscreen", "role": "addon_option", "kind": "optional", "val": "RM 1,000", "typed": {"type": "money", "value": "1000", "currency": "MYR", "semantic_role": "insured_limit"}},
                    {"concept": "special-perils", "role": "addon_option", "kind": "optional", "val": "RM 50,000", "typed": {"type": "money", "value": "50000", "currency": "MYR", "semantic_role": "insured_limit"}},
                ],
            },
        ],
    },
    {
        "company_slug": "tune-protect",
        "product_name": "Tune Protect Motor Easy",
        "product_key": "tune-protect-motor-easy",
        "catalog_name": "Tune Protect Motor Easy (Draft)",
        "packages": [
            {
                "package_key": "tune-motor-easy-base",
                "name": "Motor Easy",
                "offerings": [
                    {"concept": "roadside-assistance", "role": "included", "kind": "base", "val": "24/7", "typed": {"type": "text", "value": "24/7"}},
                    {"concept": "repair-workmanship-warranty", "role": "included", "kind": "base", "val": "6 months", "typed": {"type": "duration", "unit": "months", "duration": 6}},
                    {"concept": "windscreen", "role": "addon_option", "kind": "optional", "val": "RM 1,000", "typed": {"type": "money", "value": "1000", "currency": "MYR", "semantic_role": "insured_limit"}},
                    {"concept": "special-perils", "role": "addon_option", "kind": "optional", "val": "RM 50,000", "typed": {"type": "money", "value": "50000", "currency": "MYR", "semantic_role": "insured_limit"}},
                ],
            },
            {
                "package_key": "tune-motor-bundle",
                "name": "Motor Easy + Motor Bundle",
                "offerings": [
                    {"concept": "roadside-assistance", "role": "included", "kind": "base", "val": "24/7", "typed": {"type": "text", "value": "24/7"}},
                    {"concept": "repair-workmanship-warranty", "role": "included", "kind": "base", "val": "6 months", "typed": {"type": "duration", "unit": "months", "duration": 6}},
                    {"concept": "all-drivers", "role": "included", "kind": "base", "val": "Included", "typed": {"type": "text", "value": "Included"}},
                    {"concept": "key-replacement", "role": "included", "kind": "base", "val": "RM 1,000", "typed": {"type": "money", "value": "1000", "currency": "MYR", "semantic_role": "insured_limit"}},
                    {"concept": "total-loss-theft-allowance", "role": "included", "kind": "base", "val": "RM 10,000", "typed": {"type": "money", "value": "10000", "currency": "MYR", "semantic_role": "insured_limit"}},
                    {"concept": "windscreen", "role": "addon_option", "kind": "optional", "val": "RM 1,000", "typed": {"type": "money", "value": "1000", "currency": "MYR", "semantic_role": "insured_limit"}},
                    {"concept": "special-perils", "role": "addon_option", "kind": "optional", "val": "RM 50,000", "typed": {"type": "money", "value": "50000", "currency": "MYR", "semantic_role": "insured_limit"}},
                ],
            },
        ],
    },
    {
        "company_slug": "berjaya-sompo",
        "product_name": "SOMPO Motor Comprehensive",
        "product_key": "sompo-motor-comprehensive",
        "catalog_name": "SOMPO Motor Comprehensive (Draft)",
        "packages": [
            {
                "package_key": "sompo-motor-base",
                "name": "SOMPO Motor Base",
                "offerings": [
                    {"concept": "roadside-assistance", "role": "included", "kind": "base", "val": "24/7", "typed": {"type": "text", "value": "24/7"}},
                    {"concept": "repair-workmanship-warranty", "role": "included", "kind": "base", "val": "12 months", "typed": {"type": "duration", "unit": "months", "duration": 12}},
                    {"concept": "towing", "role": "included", "kind": "base", "val": "RM 300", "typed": {"type": "money", "value": "300", "currency": "MYR", "semantic_role": "insured_limit"}},
                    {"concept": "all-drivers", "role": "addon_option", "kind": "optional", "val": "Included", "typed": {"type": "text", "value": "Included"}},
                    {"concept": "windscreen", "role": "addon_option", "kind": "optional", "val": "RM 1,000", "typed": {"type": "money", "value": "1000", "currency": "MYR", "semantic_role": "insured_limit"}},
                    {"concept": "special-perils", "role": "addon_option", "kind": "optional", "val": "RM 50,000", "typed": {"type": "money", "value": "50000", "currency": "MYR", "semantic_role": "insured_limit"}},
                    {"concept": "key-replacement", "role": "addon_option", "kind": "optional", "val": "RM 1,000", "typed": {"type": "money", "value": "1000", "currency": "MYR", "semantic_role": "insured_limit"}},
                ],
            },
        ],
    },
]


def seed_docx_drafts(db, dry_run: bool) -> dict:
    report = {
        "mode": "dry_run" if dry_run else "apply",
        "concepts_added": [],
        "draft_catalogs": [],
        "collisions": [],
    }

    assets_by_label = {a.label: a for a in db.scalars(select(BusinessAsset).where(BusinessAsset.asset_kind == "benefit_art")).all()}

    # 1. Seed / verify Global Benefits & link default_asset_id
    for bdata in NEW_GLOBAL_BENEFITS:
        key = bdata["concept_key"]
        existing = db.scalar(select(BenefitConcept).where(BenefitConcept.concept_key == key))
        asset = assets_by_label.get(bdata.get("asset_label", ""))
        if existing is None:
            concept = BenefitConcept(
                id=new_id(),
                concept_key=key,
                label=bdata["label"],
                description=bdata["description"],
                match_dataset=bdata["match_dataset"],
                sort_order=bdata["sort_order"],
                default_asset_id=asset.id if asset else None,
                status="active",
                revision=1,
            )
            report["concepts_added"].append(key)
            if not dry_run:
                db.add(concept)
        else:
            report["collisions"].append(f"Global benefit concept '{key}' already exists.")
            if not dry_run:
                combined = list(dict.fromkeys([*(existing.match_dataset or []), *bdata["match_dataset"]]))
                existing.match_dataset = combined
                existing.label = bdata["label"]
                existing.description = bdata["description"]
                existing.sort_order = bdata["sort_order"]
                if asset:
                    existing.default_asset_id = asset.id

    if not dry_run:
        db.flush()

    concepts = {c.concept_key: c for c in db.scalars(select(BenefitConcept)).all()}
    segment = db.scalar(select(Segment).where(Segment.segment_key == "private"))
    vehicle = db.scalar(select(VehicleCategory).where(VehicleCategory.category_key == "car"))
    coverage = db.scalar(select(CoverageType).where(CoverageType.coverage_key == "comprehensive"))

    # 2. Seed Draft Catalogs
    for config in DRAFT_CONFIGURATIONS:
        company = db.scalar(select(InsuranceCompany).where(InsuranceCompany.slug == config["company_slug"]))
        if not company:
            report["collisions"].append(f"Company {config['company_slug']} not found.")
            continue

        product = db.scalar(
            select(InsuranceProduct).where(
                InsuranceProduct.company_id == company.id,
                InsuranceProduct.product_key == config["product_key"],
            )
        )
        if product is None:
            product = InsuranceProduct(
                id=new_id(),
                company_id=company.id,
                product_key=config["product_key"],
                name=config["product_name"],
                status="active",
                revision=1,
            )
            if not dry_run:
                db.add(product)
                db.flush()

        catalog = db.scalar(
            select(BenefitCatalog).where(
                BenefitCatalog.company_id == company.id,
                BenefitCatalog.product_id == product.id,
                BenefitCatalog.status == "draft",
            )
        )
        if catalog is None:
            cat_id = new_id()
            rev_id = new_id()
            catalog = BenefitCatalog(
                id=cat_id,
                company_id=company.id,
                product_id=product.id,
                segment_id=segment.id if segment else None,
                vehicle_category_id=vehicle.id if vehicle else None,
                coverage_type_id=coverage.id if coverage else None,
                name=config["catalog_name"],
                status="draft",
                revision=1,
            )
            revision = BenefitCatalogRevision(
                id=rev_id,
                catalog_id=cat_id,
                revision_number=1,
                state="draft",
                source_document_ids=[],
                content_hash="",
            )
            if not dry_run:
                db.add(catalog)
                db.add(revision)
                db.flush()

            cat_summary = {
                "company": company.name,
                "product": product.name,
                "catalog_name": config["catalog_name"],
                "status": "draft",
                "packages": [],
            }

            for pdata in config["packages"]:
                pkg_id = new_id()
                package = BenefitPackage(
                    id=pkg_id,
                    catalog_revision_id=rev_id,
                    package_key=pdata["package_key"],
                    name=pdata["name"],
                    package_kind="comprehensive",
                    status="draft",
                    sort_order=1,
                    revision=1,
                )
                if not dry_run:
                    db.add(package)

                pkg_summary = {"package_name": pdata["name"], "offerings": len(pdata["offerings"])}
                cat_summary["packages"].append(pkg_summary)

                for idx, odata in enumerate(pdata["offerings"], start=1):
                    concept = concepts.get(odata["concept"])
                    if not concept:
                        continue
                    offering = CatalogOffering(
                        id=new_id(),
                        catalog_revision_id=rev_id,
                        offering_key=f"{pdata['package_key']}-{odata['concept']}-{idx}",
                        concept_id=concept.id,
                        offering_kind=odata["kind"],
                        applies_to_type="package",
                        applies_to_id=pkg_id,
                        role=odata["role"],
                        display_value=odata["val"],
                        typed_value=odata["typed"],
                        sort_order=idx,
                        status="draft",
                    )
                    if not dry_run:
                        db.add(offering)

            report["draft_catalogs"].append(cat_summary)
        else:
            report["collisions"].append(f"Draft catalog for {company.name} -> {product.name} already exists.")

    if not dry_run:
        db.commit()

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed draft catalog configs from reference DOCX.")
    parser.add_argument("--apply", action="store_true", help="Apply draft changes (default is dry-run)")
    args = parser.parse_args()

    dry_run = not args.apply
    print(f"=== Starting seed-docx-draft.py [{'DRY-RUN' if dry_run else 'APPLY'}] ===")

    with SessionLocal() as db:
        try:
            report = seed_docx_drafts(db, dry_run=dry_run)
            report_file = ROOT / ".qc-tmp" / "docx-seeding-report.json"
            report_file.parent.mkdir(parents=True, exist_ok=True)
            report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(f"Added {len(report['concepts_added'])} new global benefit concepts.")
            print(f"Seeded {len(report['draft_catalogs'])} draft catalogs.")
            for cat in report["draft_catalogs"]:
                print(f"  - [{cat['company']}] {cat['catalog_name']} ({len(cat['packages'])} packages)")
            print(f"Collisions/skips: {len(report['collisions'])}")
            print(f"Report saved to: {report_file}")
            if dry_run:
                print("\n[DRY-RUN COMPLETE] Run with --apply to write draft configs.")
            else:
                print("\n[APPLY COMPLETE] Draft catalog configs successfully seeded.")
        except Exception as e:
            db.rollback()
            print(f"[ERROR]: {e}")
            import traceback
            traceback.print_exc()
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
