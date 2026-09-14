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

CLEAN_CONCEPT_LABELS: dict[str, str] = {
    "repair-allowance": "Compensation for Assessed Repair Time",
    "betterment-protection": "Betterment Waiver",
    "legal-liability-of-passengers": "Legal Liability of Passengers",
    "legal-liability-to-passengers": "Legal Liability to Passengers",
    "special-perils": "Special Perils",
    "all-drivers": "All Drivers Excess Waiver",
    "windscreen": "Windscreen Coverage",
    "ncd-relief": "NCD Relief",
    "total-loss-theft-allowance": "Compassionate Allowance",
    "key-replacement": "Key Care Replacement",
    "repaint-spray-paint": "Vehicle Respray Cover",
    "vehicle-respray": "Vehicle Respray Cover",
    "personal-accident": "Personal Accident Cover",
    "accidental-death": "Personal Accident Cover",
    "car-detailing-cleanup": "Car Detailing & Cleaning",
    "out-of-pocket-allowance": "Out of Pocket Allowance",
    "first-loss-flood": "First Loss Special Perils",
    "strike-riot-civil-commotion": "Strike, Riot & Civil Commotion",
    "tuition-purpose": "Tuition Purpose Cover",
    "vehicle-accessories": "Vehicle Accessories Cover",
    "motor-pa-plus": "Motor PA Plus",
    "drive-less-save-more": "Drive-Less Save-More",
    "payd-telematics": "Drive-Less Save-More",
    "gas-conversion-kit": "Gas Conversion Kit Cover",
    "child-car-seat": "Child Car Safety Seat",
    "agreed-value-market-value": "Agreed Value Settlement",
    "cashback-no-claim": "Non-Claim Cashback",
    "repair-workmanship-warranty": "Panel Workmanship Warranty",
    "repair-warranty": "Panel Workmanship Warranty",
    "towing": "Emergency Towing Assistance",
    "legal-costs-defense": "Legal Defense Costs",
    "e-hailing-extension": "E-Hailing Cover",
    "ev-wall-charger": "EV Wall Charger Cover",
    "ev-battery-depletion-towing": "EV Battery Towing",
    "ev-home-charger-liability": "EV Charger Liability",
    "boom-damage": "Accidental Boom Damage",
    "attached-trailers": "Attached Trailers Cover",
    "driver-passenger-protector": "Driver & Passenger PA",
    "auto-assistance": "Unlimited Towing Upgrade",
    "towing-upgrade": "Unlimited Towing Upgrade",
    "motorcycle-pa-bundle": "Motorcycle PA Protection",
    "sompo-motor-nhancer": "SOMPO Motor N-hancer Pack",
    "tool-of-trade": "Tool of Trade Risks",
    "ferry-transit": "Ferry Transit Cover",
    "cross-border": "Cross-Border Extension",
    "tune-drive-protect": "Tune Drive Protect",
    "motorshield-bundle": "MotorShield Multi-Pack",
    "betterment-scale": "Betterment Scale",
    "windscreen-auto-reinstatement": "Solar Tint Film Coverage",
    "windscreen-tint": "Solar Tint Film Coverage",
    "own-damage": "Comprehensive Own Damage",
    "fire-theft": "Fire & Theft Cover",
    "third-party-bi": "Third Party Bodily Injury",
    "third-party-property": "Third Party Property Damage",
    "roadside-assistance": "Roadside Assistance Helpline",
    "side-mirror-protection": "Side Mirror Damage Cover",
    "lonpac-ev-smart-pack": "Lonpac EV Smart Pack",
    "natural-falling-objects": "Natural Falling Objects Cover",
    "private-car-365": "Auto365 Multi-Rider Pack",
    "document-replacement": "Document Replacement Cover",
    "increased-tppd": "Increased Third Party Property",
    "legal-liability-to-pillion": "Legal Liability to Pillion",
    "daily-hospital-income": "Daily Hospital Income",
    "medical-expenses": "Accidental Medical Expenses",
}

COMPANIES_BENEFITS: dict[str, dict[str, dict[str, str]]] = {
    "qbe": {
        "defaults": {
            "all-drivers": "Waives RM400 compulsory excess for unnamed licensed drivers.",
            "betterment-protection": "Waives betterment cost-sharing on older vehicles repaired with parts.",
            "total-loss-theft-allowance": "Emergency cash payout upon vehicle flood loss or total loss.",
            "key-replacement": "Reimburses replacement and reprogramming of lost or stolen keys.",
            "legal-costs-defense": "Reimburses court legal representation and defense fees up to RM2,000.",
            "towing": "24/7 accidental towing assistance to nearest approved panel workshop.",
        },
        "addons": {
            "repair-allowance": "Daily cash allowance during workshop accident repair days.",
            "car-detailing-cleanup": "Interior water damage and sanitization cleaning after floods.",
            "special-perils": "Full protection against flood, storm, landslide and natural disasters.",
            "legal-liability-of-passengers": "Protects against third-party claims caused by passenger negligence.",
            "legal-liability-to-passengers": "Protects driver from lawsuits for injury or death to passengers.",
            "ncd-relief": "Protects accumulated No Claim Discount from loss after an own-damage claim.",
            "out-of-pocket-allowance": "Daily cash allowance for transit and daily expenses during repairs.",
            "first-loss-flood": "Dedicated flood and natural storm damage cover up to selected limit.",
            "strike-riot-civil-commotion": "Covers physical loss or damage caused by strikes, riots or unrest.",
            "tuition-purpose": "Extends vehicle coverage while used for driving tuition or instruction.",
            "vehicle-accessories": "Covers fitted aftermarket multimedia, dashcams and accessories.",
            "windscreen": "Covers windscreen, window glass and solar tint without losing NCD.",
            "personal-accident": "Personal accident cash benefits for driver and passengers.",
            "ev-wall-charger": "Covers accidental damage, fire or theft of home EV wallbox charger.",
            "ev-battery-depletion-towing": "Emergency flatbed towing to nearest public EV charging station.",
            "ev-home-charger-liability": "Third-party injury and property liability from home EV charger.",
        },
    },
    "takaful-malaysia": {
        "defaults": {
            "agreed-value-market-value": "Settles total loss or theft on agreed value without disputes.",
            "all-drivers": "Waives RM400 compulsory excess penalty for all authorized drivers.",
            "betterment-protection": "Waives betterment deductions on new parts for vehicles up to 12 years.",
            "personal-accident": "Complimentary accidental death cover with compassionate cash grant.",
            "legal-costs-defense": "Reimburses court legal representation and defense fees up to RM2,000.",
            "cashback-no-claim": "15% surplus cashback return if no claims are incurred during the year.",
            "towing": "24/7 breakdown and accident towing assistance up to 100 km round trip.",
        },
        "addons": {
            "motor-pa-plus": "Tiered personal accident protection for driver and passengers.",
            "special-perils": "Full cover for flood, storm, landslide, earthquake and fallen trees.",
            "windscreen": "Covers windscreen, window glass and tint repair without affecting NCD.",
            "legal-liability-of-passengers": "Protects against third-party claims caused by passenger negligence.",
            "legal-liability-to-passengers": "Protects driver from lawsuits for injury or death caused to passengers.",
            "ev-wall-charger": "Covers accidental damage, fire or theft of home EV wallbox charger.",
            "ev-battery-depletion-towing": "Emergency flatbed towing to nearest public EV charging station.",
            "ev-home-charger-liability": "Third-party injury and property liability from home EV charger.",
        },
    },
    "etiqa": {
        "defaults": {
            "towing": "24/7 accidental towing service to nearest approved repairer up to RM200.",
            "legal-costs-defense": "Reimburses court legal representation and defense fees up to RM2,000.",
        },
        "addons": {
            "payd-telematics": "Cash rebate up to 30% of base premium for low annual mileage.",
            "windscreen": "Covers windscreen, window glass and tint repair without affecting NCD.",
            "all-drivers": "Waives RM400 compulsory excess penalty for unnamed authorized drivers.",
            "special-perils": "Full cover for flood, storm, landslide, earthquake and fallen trees.",
            "legal-liability-to-passengers": "Protects driver from lawsuits for injury or death to passengers.",
            "legal-liability-of-passengers": "Protects against third-party claims caused by passenger negligence.",
            "strike-riot-civil-commotion": "Covers physical damage caused by strikes, riots or public unrest.",
            "vehicle-accessories": "Covers fitted aftermarket accessories, dashcams, multimedia and rims.",
            "gas-conversion-kit": "Dedicated damage cover for installed NGV gas conversion tanks and kits.",
            "ncd-relief": "Protects the financial value of your No Claim Discount after a claim.",
            "betterment-protection": "Waives betterment deduction on new replacement parts up to 10 years.",
            "key-replacement": "Reimburses key and lock replacement up to RM1,000 following theft or loss.",
            "child-car-seat": "Reimburses replacement or repair of child safety seats in a crash.",
            "repaint-spray-paint": "Reimburses full exterior vehicle spray painting up to RM1,000 after repairs.",
            "repair-allowance": "Daily cash allowance during workshop repairs assessed by claims adjuster.",
            "ev-wall-charger": "Covers accidental damage, fire or theft of home EV wallbox charger.",
            "ev-battery-depletion-towing": "Emergency flatbed towing to nearest public EV charging station.",
            "ev-home-charger-liability": "Third-party injury and property liability from home EV charger.",
        },
    },
    "lonpac": {
        "defaults": {
            "towing": "24/7 accidental towing service to nearest approved repairer up to RM200.",
            "out-of-pocket-allowance": "Lump-sum transportation expense allowance of RM75 per own damage claim.",
        },
        "addons": {
            "vehicle-accessories": "Covers fitted aftermarket accessories, multimedia, dashcams and rims.",
            "betterment-protection": "Waives betterment cost-sharing on new original parts for cars aged 5-10 yrs.",
            "repair-allowance": "Daily cash allowance for workshop repair days assessed by claims adjuster.",
            "car-detailing-cleanup": "Professional interior water damage cleaning up to RM5,000 after flood.",
            "ncd-relief": "Preserves the value of your No Claim Discount after an own-damage claim.",
            "e-hailing-extension": "Comprehensive motor insurance coverage during commercial e-hailing driving.",
            "special-perils": "Full cover for flood, storm, landslide, earthquake and fallen trees.",
            "repaint-spray-paint": "Reimburses complete exterior vehicle spray painting up to RM2,000 after repair.",
            "gas-conversion-kit": "Dedicated damage cover for installed NGV gas conversion tanks and kits.",
            "legal-liability-of-passengers": "Protects against third-party claims caused by passenger negligence.",
            "legal-liability-to-passengers": "Protects driver from lawsuits for injury or death to passengers.",
            "key-replacement": "Reimburses key and lock replacement up to RM2,000 due to theft or loss.",
            "strike-riot-civil-commotion": "Covers physical loss or damage caused by strikes, riots or unrest.",
            "windscreen": "Covers windscreen, window glass and tint repair without affecting NCD.",
            "personal-accident": "Accidental death, permanent disability and towing protection package.",
            "ev-wall-charger": "Covers accidental damage, fire or theft of home EV wallbox charger.",
            "ev-battery-depletion-towing": "Emergency flatbed towing to nearest public EV charging station.",
            "ev-home-charger-liability": "Third-party injury and property liability from home EV charger.",
        },
    },
    "berjaya-sompo": {
        "defaults": {
            "agreed-value-market-value": "Settles total loss or theft on agreed value for vehicles up to 3 years.",
            "all-drivers": "Waives RM400 compulsory excess for all authorized licensed drivers 21+.",
            "towing": "24/7 unlimited distance towing to panel workshops and roadside repairs.",
            "legal-costs-defense": "Reimburses court legal representation and defense fees up to RM2,000.",
            "repair-workmanship-warranty": "12-month warranty on repair workmanship and replacement parts from panel shops.",
            "accidental-death": "Lump-sum cash benefit paid to beneficiaries upon accidental road death.",
            "special-perils": "Built-in full protection against flood, typhoon, storm and natural disasters.",
        },
        "addons": {
            "boom-damage": "Covers accidental damage to crane booms, jibs and hydraulic apparatus.",
            "attached-trailers": "Extends third-party liability and damage cover to attached trailers.",
            "betterment-protection": "Waives betterment cost-sharing on new replacement parts for cars up to 15 yrs.",
            "repair-allowance": "Daily cash payout during workshop repair period assessed by claims adjuster.",
            "driver-passenger-protector": "Comprehensive tiered personal accident protection for driver and passengers.",
            "e-hailing-extension": "Comprehensive coverage during commercial ride-hailing and e-hailing operations.",
            "auto-assistance": "Extended towing distance providing nationwide breakdown and accident recovery.",
            "legal-liability-of-passengers": "Protects against third-party claims caused by passenger negligence.",
            "legal-liability-to-passengers": "Protects driver from lawsuits for injury or death to passengers.",
            "motorcycle-pa-bundle": "Personal accident protection and emergency towing for riders and pillions.",
            "ncd-relief": "Preserves the value of your No Claim Discount after an own-damage claim.",
            "sompo-motor-nhancer": "Multi-benefit bundle combining e-hailing CART, liability, and personal accident.",
            "special-perils": "Full protection against flood, storm, landslide and natural disasters.",
            "strike-riot-civil-commotion": "Protection against damage caused by strikers, riots or civil unrest.",
            "tool-of-trade": "Third-party liability cover while machinery operates as a tool of trade.",
            "windscreen": "Repair and replacement of windscreen, window glass and tint without losing NCD.",
            "ev-wall-charger": "Covers accidental damage, fire or theft of home EV wallbox charger.",
            "ev-battery-depletion-towing": "Emergency flatbed towing to nearest public EV charging station.",
            "ev-home-charger-liability": "Third-party injury and property liability from home EV charger.",
        },
    },
    "tune-protect": {
        "defaults": {
            "payd-telematics": "Cash rebate up to 30% of base premium for low annual mileage driving.",
            "towing": "24/7 accidental towing assistance to nearest workshop up to RM200.",
            "legal-costs-defense": "Reimburses court legal representation and defense fees up to RM2,000.",
        },
        "addons": {
            "all-drivers": "Waives RM400 compulsory excess penalty for unnamed authorized drivers.",
            "windscreen": "Covers windscreen, window glass and tint repair without affecting NCD.",
            "special-perils": "Full cover for flood, storm, landslide, earthquake and fallen trees.",
            "legal-liability-to-passengers": "Protects driver from lawsuits for injury or death to passengers.",
            "legal-liability-of-passengers": "Protects against third-party claims caused by passenger negligence.",
            "vehicle-accessories": "Covers fitted aftermarket accessories, multimedia, dashcams and rims.",
            "gas-conversion-kit": "Dedicated damage cover for installed NGV gas conversion tanks and kits.",
            "attached-trailers": "Extends damage and liability coverage to attached luggage or caravan trailers.",
            "repair-allowance": "Daily cash allowance for workshop repair days assessed by claims adjuster.",
            "ferry-transit": "Covers loss or damage while vehicle is transported by ferry or vessel.",
            "strike-riot-civil-commotion": "Covers damage directly caused by strikes, riots or civil commotion.",
            "cross-border": "Extends comprehensive insurance coverage into Thailand and Kalimantan.",
            "personal-accident": "Personal accident, medical, and hospital income protection bundle.",
            "betterment-protection": "Waives betterment cost-sharing on new replacement parts for cars up to 10 yrs.",
            "motorshield-bundle": "Bundles personal accident, excess waiver, side mirror, keys and towing.",
            "ev-wall-charger": "Covers accidental damage, fire or theft of home EV wallbox charger.",
            "ev-battery-depletion-towing": "Emergency flatbed towing to nearest public EV charging station.",
            "ev-home-charger-liability": "Third-party injury and property liability from home EV charger.",
        },
    },
    "amassurance": {
        "defaults": {
            "betterment-scale": "Tariff cost-sharing scale applied when repairing with new original parts.",
            "towing": "Built-in 24/7 emergency accident towing assistance up to policy limit.",
            "legal-costs-defense": "Reimburses court legal representation and defense fees up to RM2,000.",
            "repair-workmanship-warranty": "Guaranteed warranty covering repair workmanship and replacement parts.",
        },
        "addons": {
            "e-hailing-extension": "Permits comprehensive motor insurance coverage during commercial ride-hailing.",
            "repair-allowance": "Daily cash payout for workshop repair period assessed by claims adjuster.",
            "ncd-relief": "Preserves the value of forfeited No Claim Discount after an own-damage claim.",
            "special-perils": "Full cover for flood, storm, landslide, earthquake and natural disasters.",
            "legal-liability-of-passengers": "Protects against third-party claims caused by passenger negligence.",
            "legal-liability-to-passengers": "Protects driver from lawsuits for injury or death to passengers.",
            "gas-conversion-kit": "Dedicated damage cover for installed NGV gas conversion tanks and kits.",
            "strike-riot-civil-commotion": "Covers physical loss or damage caused by strikes, riots or civil unrest.",
            "betterment-protection": "Waives betterment contribution on new original parts for vehicles 5+ years old.",
            "windscreen": "Repair and replacement of windscreen and glass without affecting NCD.",
            "windscreen-auto-reinstatement": "Repair and replacement of solar tint film inclusive of labour cost.",
            "driver-passenger-protector": "Multi-plan personal accident protection for driver and passengers.",
            "ev-wall-charger": "Covers accidental damage, fire or theft of home EV wallbox charger.",
            "ev-battery-depletion-towing": "Emergency flatbed towing to nearest public EV charging station.",
            "ev-home-charger-liability": "Third-party injury and property liability from home EV charger.",
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

        # 1. Update BenefitConcept labels and descriptions
        updated_concepts = 0
        for concept_key, clean_label in CLEAN_CONCEPT_LABELS.items():
            if concept_key in concepts:
                concept = concepts[concept_key]
                if concept.label != clean_label:
                    concept.label = clean_label
                    updated_concepts += 1
        print(f"Updated {updated_concepts} BenefitConcept labels to clean naming standard.")

        all_concepts_list = list(concepts.values())

        # 2. Update CompanyBenefitConfigs
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
