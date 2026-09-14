"""Seed active benefit profile v2 and synchronize company catalogs.

Target Profile: 'Main Unified Baseline (14/09/2026) (v2)' (94f56a3a-3ea1-4532-8ae7-34dda7c60a62)
Source Data: docs/benefits/concise/current_all_benefits_12092026.md
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add backend directory to sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.session import SessionLocal
from app.models.tables import (
    BenefitConcept,
    BenefitProfile,
    CompanyBenefitConfig,
    InsuranceCompany,
    new_id,
    utcnow,
)
from app.services.business_setup_service import sync_company_catalogs_to_profile
from sqlalchemy import select

TARGET_PROFILE_ID = "94f56a3a-3ea1-4532-8ae7-34dda7c60a62"

COMPANIES_BENEFITS: dict[str, dict[str, dict[str, str]]] = {
    "qbe": {
        "defaults": {
            "all-drivers": "Waives RM400 compulsory excess for unnamed licensed drivers/riders.",
            "betterment-protection": "Waives betterment cost-sharing on older vehicles repaired with parts.",
            "total-loss-theft-allowance": "Immediate emergency cash payout (RM1,000-RM3,000) upon vehicle flood / total loss.",
            "key-replacement": "Reimburses replacement and reprogramming of lost or stolen keys.",
            "legal-costs-defense": "Reimburses court legal representation and defense fees up to RM2,000.",
            "towing": "24/7 accidental Towing service to nearest approved repairer upto RM500.",
        },
        "addons": {
            "repair-allowance": "RM50/day for 14 days or RM100/day for 14 days.",
            "car-detailing-cleanup": "Water damage interior car cleaning reimbursement after flood.",
            "special-perils": "Full cover for flood, storm, landslide & natural convulsions.",
            "legal-liability-of-passengers": "Protects against third-party claims caused by passenger negligence.",
            "legal-liability-to-passengers": "Protects driver from lawsuits for injury/death caused to passengers.",
            "ncd-relief": "Protects accumulated No Claim Discount from loss following an own-damage claim.",
            "out-of-pocket-allowance": "Daily cash allowance for transit and expenses during repairs.",
            "first-loss-flood": "Standalone first loss flood/disaster cover (5k/10k).",
            "strike-riot-civil-commotion": "Covers damage directly caused by strikes, riots, or civil commotion.",
            "tuition-purpose": "Extends coverage while vehicle is used for driving tuition or instruction.",
            "vehicle-accessories": "Covers fitted aftermarket accessories, multimedia, dashcams, and rims.",
            "windscreen": "Covers windscreen, window glass & sunroof repair without affecting NCD.",
            "personal-accident": "Driver & passenger PA for death, disability & hospital.",
        },
    },
    "takaful-malaysia": {
        "defaults": {
            "agreed-value-market-value": "Settles total loss or theft on agreed value without depreciation disputes.",
            "all-drivers": "Waives RM400 compulsory excess penalty for all authorized licensed drivers.",
            "betterment-protection": "Waives betterment deductions on new original parts for vehicles up to 12 years.",
            "personal-accident": "Complimentary accidental death cover for participant with bereavement allowance.",
            "legal-costs-defense": "Reimburses court legal representation and defense fees up to RM2,000.",
            "cashback-no-claim": "15% surplus cashback return if no claims are incurred during the year.",
            "towing": "24/7 breakdown and accident towing assistance up to 100 km round trip.",
        },
        "addons": {
            "motor-pa-plus": "Motor PA PLUS (Plans 1, 2, 3, and 4) personal accident rider for driver and passengers.",
            "special-perils": "Full cover for flood, storm, landslide, earthquake & fallen trees.",
            "windscreen": "Covers windscreen, window glass & tint repair without affecting NCD.",
            "legal-liability-of-passengers": "Protects against third-party claims caused by passenger negligence.",
            "legal-liability-to-passengers": "Protects driver from lawsuits for injury/death caused to passengers.",
        },
    },
    "etiqa": {
        "defaults": {
            "towing": "24/7 accidental Towing service to nearest approved repairer upto RM200.",
            "legal-costs-defense": "Reimburses court legal representation and defense fees up to RM2,000.",
        },
        "addons": {
            "payd-telematics": "Drive-Less Save-More cash rebate up to 30% of base premium for low mileage.",
            "windscreen": "Covers windscreen, window glass & tint repair without affecting NCD.",
            "all-drivers": "Waives RM400 compulsory excess penalty for unnamed authorized drivers.",
            "special-perils": "Full cover for flood, storm, landslide, earthquake & fallen trees.",
            "legal-liability-to-passengers": "Protects driver from lawsuits for injury/death caused to passengers.",
            "legal-liability-of-passengers": "Protects against third-party claims caused by passenger negligence.",
            "strike-riot-civil-commotion": "Covers damage directly caused by strikes, riots, or civil commotion.",
            "vehicle-accessories": "Covers fitted aftermarket accessories, multimedia, dashcams, and rims.",
            "gas-conversion-kit": "Dedicated damage cover for installed NGV gas conversion tanks and kits.",
            "ncd-relief": "15% of NCD Value / (10 days x 50) (10 days x 100) (10 days x 150) (10 days x 200).",
            "betterment-protection": "Waives betterment deduction on new replacement parts for vehicles up to 10 yrs.",
            "key-replacement": "Reimburses car key and lock replacement up to RM1,000 following loss or theft.",
            "child-car-seat": "Reimburses replacement or repair of child safety seats damaged in a crash.",
            "repaint-spray-paint": "Reimburses full exterior vehicle spray painting after an accident repair (limit up to RM1,000).",
            "repair-allowance": "Daily cash allowance for workshop repair days assessed by loss adjuster (7 days x RM50).",
        },
    },
    "lonpac": {
        "defaults": {
            "towing": "24/7 accidental Towing service to nearest approved repairer upto RM200.",
            "out-of-pocket-allowance": "PC Privilege 1 lump-sum transportation allowance of RM75 per own damage claim.",
        },
        "addons": {
            "vehicle-accessories": "Covers fitted aftermarket accessories, multimedia, dashcams, and rims.",
            "betterment-protection": "Waives betterment cost-sharing on new original parts for cars aged 5-10 yrs.",
            "repair-allowance": "Daily cash allowance for workshop repair days assessed by loss adjuster.",
            "car-detailing-cleanup": "Professional car interior cleaning up to RM5,000 after a flood.",
            "ncd-relief": "Compensates for lost No Claim Discount (NCD) after an own-damage claim.",
            "e-hailing-extension": "Comprehensive motor insurance coverage during commercial e-hailing work.",
            "special-perils": "Full cover for flood, storm, landslide, earthquake & fallen trees.",
            "repaint-spray-paint": "Reimburses complete exterior vehicle spray painting up to RM2,000 after repair.",
            "gas-conversion-kit": "Dedicated damage cover for installed NGV gas conversion tanks and kits.",
            "legal-liability-of-passengers": "Protects against third-party claims caused by passenger negligence.",
            "legal-liability-to-passengers": "Protects driver from lawsuits for injury/death caused to passengers.",
            "key-replacement": "Reimburses key and lock replacement up to RM2,000 due to theft or break-in.",
            "strike-riot-civil-commotion": "Covers damage directly caused by strikes, riots, or civil commotion.",
            "windscreen": "Covers windscreen, window glass & tint repair without affecting NCD.",
            "personal-accident": "Plan 1 (Limited Towing) & Plan 2 (Unlimited Towing) driver & passenger PA.",
        },
    },
    "berjaya-sompo": {
        "defaults": {
            "agreed-value-market-value": "Settles total loss or theft on agreed value for car models up to 3 years old.",
            "all-drivers": "Waives RM400 compulsory excess for all authorized licensed drivers aged 21+.",
            "towing": "24/7 unlimited distance towing to panel workshops and minor roadside repairs.",
            "legal-costs-defense": "Reimburses court legal representation and defense fees up to RM2,000.",
            "repair-workmanship-warranty": "12-month warranty on repair workmanship and replacement parts from panel shops.",
            "accidental-death": "Lump-sum cash benefit paid to beneficiaries upon accidental road death.",
            "special-perils": "Built-in full protection against flood, typhoon, storm, and natural disasters.",
        },
        "addons": {
            "boom-damage": "Endorsement 38A covering accidental and unforeseen structural damage to mobile crane booms, jibs, outriggers, and hydraulic apparatus during work operations.",
            "attached-trailers": "Endorsement 54 extending third-party liability and comprehensive damage cover to unspecified attached trailers, boat haulers, or commercial couplings.",
            "betterment-protection": "Waives standard tariff betterment contribution percentages (deductible) when older vehicles aged 5 to 15 years are repaired with new original replacement parts.",
            "repair-allowance": "Endorsement 112 daily cash payout for the workshop repair period assessed by the insurance claims loss adjuster (e.g. 7, 14, or 21 days at RM50 to RM200 per day).",
            "driver-passenger-protector": "Pre-packaged multi-plan personal accident rider protecting driver and passengers across tiered coverage schedules.",
            "e-hailing-extension": "Endorsement A008 permitting comprehensive motor insurance coverage during commercial ride-hailing and e-hailing app operations (e.g. Grab).",
            "auto-assistance": "Optional upgrade rider extending towing assistance distance or providing unlimited nationwide breakdown and accident towing service.",
            "legal-liability-of-passengers": "Endorsement 72 protecting the vehicle owner against third-party liability claims resulting from negligent acts committed by vehicle passengers (e.g. opening a car door into oncoming traffic).",
            "legal-liability-to-passengers": "Endorsement 100/108 protecting the insured driver/rider against legal liability lawsuits for death or bodily injury caused to authorized passengers in passenger cars or pillion riders on motorcycles.",
            "motorcycle-pa-bundle": "Pre-packaged personal accident rider with roadside towing tailored specifically for motorcycle riders and pillion passengers.",
            "ncd-relief": "Endorsement 111 reimbursing or preserving the financial value of the forfeited No Claim Discount (NCD) percentage following an own-damage accident claim.",
            "sompo-motor-nhancer": "Berjaya Sompo proprietary multi-benefit bundle combining e-hailing CART, passenger liability, and enhanced personal accident.",
            "strike-riot-civil-commotion": "Endorsement 25 protection against physical loss or damage directly caused by strikers, locked-out workers, public civil unrest, or malicious riots.",
            "tool-of-trade": "Endorsement 41/42 extending third-party bodily injury and property liability while excavators, loaders, or mobile machinery operate as working tools of trade.",
            "windscreen": "Repair and replacement coverage for broken windscreen, front, rear, side window glass, and solar tint film without penalty or forfeiture of accumulated No Claim Discount (NCD).",
        },
    },
    "tune-protect": {
        "defaults": {
            "payd-telematics": "Pay-As-You-Drive cash rebate up to 30% of premium for low annual mileage.",
            "towing": "24/7 emergency accident towing assistance to nearest workshop up to RM200.",
            "legal-costs-defense": "Reimburses court legal representation and defense fees up to RM2,000.",
        },
        "addons": {
            "all-drivers": "Waives RM400 compulsory excess penalty for unnamed authorized drivers.",
            "windscreen": "Covers windscreen, window glass & tint repair without affecting NCD.",
            "special-perils": "Full cover for flood, storm, landslide, earthquake & fallen trees.",
            "legal-liability-to-passengers": "Protects driver from lawsuits for injury/death caused to passengers.",
            "legal-liability-of-passengers": "Protects against third-party claims caused by passenger negligence.",
            "vehicle-accessories": "Covers fitted aftermarket accessories, multimedia, dashcams, and rims.",
            "gas-conversion-kit": "Dedicated damage cover for installed NGV gas conversion tanks and kits.",
            "attached-trailers": "Extends damage and liability coverage to attached luggage or caravan trailers.",
            "repair-allowance": "Daily cash allowance for workshop repair days assessed by loss adjuster.",
            "ferry-transit": "Covers loss or damage while vehicle is transported by ferry or vessel.",
            "strike-riot-civil-commotion": "Covers damage directly caused by strikes, riots, or civil commotion.",
            "cross-border": "Extends comprehensive insurance coverage into Thailand, Kalimantan, and Indonesia.",
            "personal-accident": "Personal accident, medical, and hospital income protection bundle.",
            "betterment-protection": "Waives betterment cost-sharing on new replacement parts for cars up to 10 yrs.",
            "motorshield-bundle": "Bundles personal accident, excess waiver, side mirror, keys, and towing.",
        },
    },
    "amassurance": {
        "defaults": {
            "betterment-scale": "Tariff-mandated partial cost-sharing scale applied when repairing damaged components with brand-new original items.",
            "towing": "Built-in 24/7 emergency accident towing assistance to nearest approved repairer up to policy limit.",
            "legal-costs-defense": "Reimbursement of court legal defense representation costs up to RM2,000 limit.",
            "repair-workmanship-warranty": "Guaranteed warranty covering repair workmanship and genuine replacement parts from panel workshops.",
        },
        "addons": {
            "e-hailing-extension": "Permits comprehensive motor insurance coverage during commercial ride-hailing operations.",
            "repair-allowance": "Daily cash payout for the workshop repair period assessed by loss adjuster.",
            "ncd-relief": "Preserves the financial value of forfeited No Claim Discount (NCD) after an own-damage claim.",
            "special-perils": "Full cover for flood, storm, landslide, earthquake & convulsions of nature.",
            "legal-liability-of-passengers": "Protects against third-party claims caused by passenger negligence.",
            "legal-liability-to-passengers": "Protects driver from lawsuits for injury/death caused to passengers.",
            "gas-conversion-kit": "Dedicated damage cover for installed NGV gas conversion tanks and kits.",
            "strike-riot-civil-commotion": "Covers physical loss or damage directly caused by strikes, riots, or civil commotion.",
            "betterment-protection": "Waives betterment contribution on new original parts for vehicles 5+ years old.",
            "windscreen": "Repair and replacement of windscreen and glass without affecting NCD.",
            "windscreen-auto-reinstatement": "Repair and replacement of solar tint film inclusive of labour cost.",
            "driver-passenger-protector": "Multi-plan personal accident rider protecting driver and passengers across tiered schedules.",
        },
    },
}


def main():
    db = SessionLocal()
    try:
        profile = db.get(BenefitProfile, TARGET_PROFILE_ID)
        if not profile:
            print(f"Target profile {TARGET_PROFILE_ID} not found!")
            return

        print(f"Seeding Profile: {profile.name} (v{profile.version_number}) [ID: {profile.id}]")
        concepts = {c.concept_key: c for c in db.scalars(select(BenefitConcept)).all()}
        all_concepts_list = list(concepts.values())

        for slug, sections in COMPANIES_BENEFITS.items():
            company = db.scalar(select(InsuranceCompany).where(InsuranceCompany.slug == slug))
            if not company:
                print(f"Company {slug} not found, skipping...")
                continue

            active_dict = {}
            for k, desc in sections["defaults"].items():
                active_dict[k] = desc
            for k, desc in sections["addons"].items():
                active_dict[k] = desc

            enabled_count = 0
            disabled_count = 0

            for concept in all_concepts_list:
                cfg = db.scalar(
                    select(CompanyBenefitConfig).where(
                        CompanyBenefitConfig.company_id == company.id,
                        CompanyBenefitConfig.profile_id == profile.id,
                        CompanyBenefitConfig.concept_id == concept.id,
                    )
                )

                if concept.concept_key in active_dict:
                    desc = active_dict[concept.concept_key]
                    is_enabled = True
                    enabled_count += 1
                else:
                    desc = None
                    is_enabled = False
                    disabled_count += 1

                if cfg is not None:
                    cfg.is_enabled = is_enabled
                    cfg.baseline_description = desc
                    cfg.updated_at = utcnow()
                else:
                    cfg = CompanyBenefitConfig(
                        id=new_id(),
                        company_id=company.id,
                        profile_id=profile.id,
                        concept_id=concept.id,
                        is_enabled=is_enabled,
                        baseline_description=desc,
                        created_at=utcnow(),
                        updated_at=utcnow(),
                    )
                    db.add(cfg)

            db.flush()

            # Run catalog cascade for this company
            cascade_res = sync_company_catalogs_to_profile(db, company.id, profile.id)

            print(
                f"[{company.slug:18}] Enabled: {enabled_count:2} | Disabled: {disabled_count:2} | "
                f"Purged Offerings: {cascade_res['purged_offerings']:3} | Purged Plan Items: {cascade_res['purged_plan_items']:2}"
            )

        db.commit()
        print("\nAll 7 companies successfully seeded and catalogs synchronized!")

    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
