"""
Maintenance script to:
1. Safely purge test-generated benefit concepts (test-active-*, test-retired-*, test-cascade-*)
2. Batch update the 58 canonical benefit descriptions in benefit_concepts
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.db.session import SessionLocal
from app.models.tables import (
    BenefitConcept,
    CatalogOffering,
    DraftBenefitSelection,
    BenefitCatalogRevision,
    BenefitCatalog,
)
from sqlalchemy import select, delete

CANONICAL_DESCRIPTIONS = [
  {
    "title": "Own Damage",
    "alias": "own-damage",
    "description": "Covers accidental collision, overturn, fire, theft, malicious act, and inland transit."
  },
  {
    "title": "Third Party Bodily Injury",
    "alias": "third-party-bi",
    "description": "Unlimited legal liability protection for death or bodily injury sustained by third parties."
  },
  {
    "title": "Third Party Property Damage",
    "alias": "third-party-property",
    "description": "Covers legal liability for third-party vehicle and property damage up to RM 3,000,000."
  },
  {
    "title": "Fire & Theft Cover",
    "alias": "fire-theft",
    "description": "Covers accidental fire, self-ignition, lightning, vehicle theft, and break-in damages."
  },
  {
    "title": "Emergency Towing Assistance",
    "alias": "towing",
    "description": "24/7 accident towing service to the nearest approved repairer up to designated limits."
  },
  {
    "title": "Personal Accident",
    "alias": "personal-accident",
    "description": "Personal Accident coverage (includes Accidental Death / Total Permanent Disability)."
  },
  {
    "title": "Workmanship Warranty",
    "alias": "repair-workmanship-warranty",
    "description": "3-year warranty on body repair, spray painting, and parts from panel repair workshops."
  },
  {
    "title": "Legal Defense Costs",
    "alias": "legal-costs-defense",
    "description": "Reimbursement of approved legal representation costs in court defense up to RM 2,000."
  },
  {
    "title": "Betterment Waiver / Scale",
    "alias": "betterment-protection",
    "description": "Waiver or standard scale (0%-40%) for new parts on vehicles aged 5 to 15 years old."
  },
  {
    "title": "All Drivers Excess Waiver",
    "alias": "all-drivers",
    "description": "Covers authorized licensed drivers and waives RM 400 unnamed driver compulsory excess."
  },
  {
    "title": "Agreed Value Settlement",
    "alias": "agreed-value-market-value",
    "description": "Settlement based on agreed sum insured or ISM value with zero depreciation disputes."
  },
  {
    "title": "No-Claim Cashback / Rebate",
    "alias": "cashback-no-claim",
    "description": "Cashback reward or surplus payout via Hibah of 15% to 30% for claim-free policy terms."
  },
  {
    "title": "Pay-As-You-Drive Telematics",
    "alias": "payd-telematics",
    "description": "Smart telematics drive reward offering 15%-20% premium cash refund for low mileage."
  },
  {
    "title": "Windscreen & Window Glass",
    "alias": "windscreen",
    "description": "Repair or replacement of broken windscreen, windows, and tint film without NCD loss."
  },
  {
    "title": "Inclusion of Special Perils",
    "alias": "special-perils",
    "description": "Full natural disaster coverage including floods, storms, typhoons, and landslides."
  },
  {
    "title": "First Loss Flood",
    "alias": "first-loss-flood",
    "description": "Standalone first loss flood and storm disaster protection up to RM 10,000 limit."
  },
  {
    "title": "Strike, Riot & Civil Commotion",
    "alias": "strike-riot-civil-commotion",
    "description": "Covers physical vehicle loss or damage caused by strikers, riots, and civil unrest."
  },
  {
    "title": "Legal Liability to Passengers (LLTP)",
    "alias": "legal-liability-to-passengers",
    "description": "Indemnity for accidental bodily injury or death claims made by vehicle passengers."
  },
  {
    "title": "Legal Liability of Passengers (LLOP)",
    "alias": "legal-liability-of-passengers",
    "description": "Covers legal liability for third-party property damage caused by vehicle passengers."
  },
  {
    "title": "Legal Liability to Pillion",
    "alias": "legal-liability-to-pillion",
    "description": "Rider legal liability protection for accidental bodily injury or death to pillions."
  },
  {
    "title": "Compensation for Assessed Repair Time (CART)",
    "alias": "repair-allowance",
    "description": "Daily repair allowance (RM 50-RM 100/day for 7-14 days) during workshop accident fixes."
  },
  {
    "title": "Replacement Car",
    "alias": "replacement-car",
    "description": "Provision of a temporary courtesy or rental replacement car during accident repairs."
  },
  {
    "title": "Key Care & Replacement",
    "alias": "key-replacement",
    "description": "Reimbursement for replacement or reprogramming of lost or stolen keys up to RM 1,000."
  },
  {
    "title": "Personal Belongings Theft",
    "alias": "personal-belongings-theft",
    "description": "Reimbursement for personal belongings or laptops lost in smash-and-grab thefts."
  },
  {
    "title": "Total Loss / Theft Allowance",
    "alias": "total-loss-theft-allowance",
    "description": "Lump-sum compassionate allowance of 5% to 10% sum insured upon total loss or theft."
  },
  {
    "title": "Flood Relief Cash Allowance",
    "alias": "flood-relief-allowance",
    "description": "Immediate lump-sum compassionate cash allowance (RM 1,500-RM 3,000) for flood damage."
  },
  {
    "title": "Replacement Cost",
    "alias": "replacement-cost",
    "description": "Replacement cost compensation ensuring market value uplift or total replacement value."
  },
  {
    "title": "Ambulance Transport Fees",
    "alias": "ambulance-fees",
    "description": "Emergency ambulance transport fees reimbursement to hospital after a road accident."
  },
  {
    "title": "Medical Expenses Reimbursement",
    "alias": "medical-expenses",
    "description": "Reimbursement of medical, clinical, and hospital fees incurred from motor injuries."
  },
  {
    "title": "Bereavement & Funeral Cash",
    "alias": "bereavement-allowance",
    "description": "Lump-sum compassionate bereavement benefit (RM 1,000-RM 3,000) upon accidental death."
  },
  {
    "title": "Flood Detailing & Cleaning",
    "alias": "car-detailing-cleanup",
    "description": "Professional interior cleaning and sanitisation reimbursement for flood damages."
  },
  {
    "title": "Out-of-Pocket Allowance",
    "alias": "out-of-pocket-allowance",
    "description": "Incidental allowance covering minor unexpected travel, transit, or towing expenses."
  },
  {
    "title": "Driver Passenger Protector",
    "alias": "driver-passenger-protector",
    "description": "Comprehensive personal accident protection for driver and passengers in tiered plans."
  },
  {
    "title": "Full Car Spray Painting",
    "alias": "repaint-spray-paint",
    "description": "Full exterior vehicle body spray painting coverage (up to RM 2,000) after repairs."
  },
  {
    "title": "Child Car Safety Seat Cover",
    "alias": "child-car-seat",
    "description": "Reimbursement to replace child safety car seats (up to RM 500) after accidents."
  },
  {
    "title": "Private Car 365 Plan",
    "alias": "private-car-365",
    "description": "All-in-one 365 days emergency and personal accident motor protection packages included."
  },
  {
    "title": "Motor PA Plus",
    "alias": "motor-pa-plus",
    "description": "Tiered accidental death, disability, and hospital cash coverage for vehicle occupants."
  },
  {
    "title": "Side Mirror Replacement",
    "alias": "side-mirror-protection",
    "description": "Repair or replacement of broken exterior mirrors and wing assemblies up to RM 1,000."
  },
  {
    "title": "EV Charger & Wallbox Cover",
    "alias": "ev-wall-charger",
    "description": "EV coverage for wallbox damage, public charger liability, and flat battery towing."
  },
  {
    "title": "OTO 360",
    "alias": "oto-360",
    "description": "Comprehensive motor takaful coverage package with enhanced death and disability care."
  },
  {
    "title": "Vehicle Accessories",
    "alias": "vehicle-accessories",
    "description": "Separate coverage for non-factory fitted dashcams, rims, multimedia, and body kits."
  },
  {
    "title": "E-Hailing / Private Hire",
    "alias": "e-hailing-extension",
    "description": "Policy endorsement authorizing commercial e-hailing work with passenger liability."
  },
  {
    "title": "Current Year NCD Relief",
    "alias": "ncd-relief",
    "description": "Reimburses or protects accumulated No Claim Discount entitlement after own-damage claim."
  },
  {
    "title": "Increased TPPD Limit",
    "alias": "increased-tppd",
    "description": "Upgrades third-party property damage indemnity limit from RM 3M up to RM 4M - RM 6M."
  },
  {
    "title": "Ferry Transit (Sabah-Labuan)",
    "alias": "ferry-transit",
    "description": "Marine transit loss or damage coverage across Sabah, Sarawak, Labuan, or Penang waters."
  },
  {
    "title": "Cross-Border (Thailand/Kalimantan)",
    "alias": "cross-border",
    "description": "Geographical policy extension into Thailand, Kalimantan, or Brunei with TPPD cover."
  },
  {
    "title": "Vehicle Overturning Damage",
    "alias": "overturning",
    "description": "Covers accidental damage caused by vehicle overturning or transport load shifts."
  },
  {
    "title": "Authorized Attendants Liability",
    "alias": "authorized-attendants",
    "description": "Legal liability protection for authorized crew members, loaders, or cabin attendants."
  },
  {
    "title": "Crane Boom Damage",
    "alias": "boom-damage",
    "description": "Unforeseen physical damage protection to crane boom while used as a tool of trade."
  },
  {
    "title": "Tool of Trade Working Risks",
    "alias": "tool-of-trade",
    "description": "Third-party bodily injury and property liability while operating as a mobile plant."
  },
  {
    "title": "Attached Trailers & Couplings",
    "alias": "attached-trailers",
    "description": "Indemnity extension covering unspecified attached trailers and commercial couplings."
  },
  {
    "title": "NGV Gas Conversion Kit",
    "alias": "gas-conversion-kit",
    "description": "Separate protection for installed natural gas fuel conversion tanks, valves, and kits."
  },
  {
    "title": "Cargo & Goods in Transit",
    "alias": "cargo-protection",
    "description": "Protection for enterprise trade merchandise and goods carried under commercial haulage."
  },
  {
    "title": "Accidental Death Benefit",
    "alias": "accidental-death",
    "description": "Lump-sum accidental death cash benefit per insured passenger carried in the vehicle."
  },
  {
    "title": "Permanent Disablement Benefit",
    "alias": "permanent-disablement",
    "description": "Tiered lump-sum compensation for permanent total or partial disablement per person."
  },
  {
    "title": "Double Indemnity",
    "alias": "double-indemnity",
    "description": "Double benefit payout for quadriplegia or accidents occurring on national holidays."
  },
  {
    "title": "Auto Assistance / Towing Rider",
    "alias": "auto-assistance",
    "description": "Standalone 24-hour unlimited towing and nationwide roadside emergency repair rider."
  },
  {
    "title": "Daily Hospital Income",
    "alias": "daily-hospital-income",
    "description": "Daily hospitalization income cash allowance up to a maximum duration of 60 full days."
  }
]


def run_cleanup(dry_run: bool = True):
    db = SessionLocal()
    try:
        print(f"=== Running Benefit Cleanup & Description Update (dry_run={dry_run}) ===")

        # 1. Identify test concepts to delete
        test_concepts = db.scalars(
            select(BenefitConcept).where(
                (BenefitConcept.concept_key.like("test-active-%"))
                | (BenefitConcept.concept_key.like("test-retired-%"))
                | (BenefitConcept.concept_key.like("test-cascade-%"))
            )
        ).all()

        test_concept_ids = [c.id for c in test_concepts]
        print(f"\n[Step 1] Found {len(test_concepts)} test concepts to purge:")
        for c in test_concepts:
            print(f"  - ID={c.id} | KEY={c.concept_key} | LABEL={c.label}")

        if test_concept_ids:
            # Check draft selections referencing them
            selections = db.scalars(
                select(DraftBenefitSelection).where(DraftBenefitSelection.concept_id.in_(test_concept_ids))
            ).all()
            if selections:
                print(f"  Deleting {len(selections)} test draft selections...")
                if not dry_run:
                    db.execute(delete(DraftBenefitSelection).where(DraftBenefitSelection.concept_id.in_(test_concept_ids)))

            # Check offerings referencing them
            offerings = db.scalars(
                select(CatalogOffering).where(CatalogOffering.concept_id.in_(test_concept_ids))
            ).all()
            if offerings:
                print(f"  Deleting {len(offerings)} test catalog offerings...")
                if not dry_run:
                    db.execute(delete(CatalogOffering).where(CatalogOffering.concept_id.in_(test_concept_ids)))

            # Delete the test concepts
            print(f"  Deleting {len(test_concepts)} test benefit concepts...")
            if not dry_run:
                db.execute(delete(BenefitConcept).where(BenefitConcept.id.in_(test_concept_ids)))

        # 2. Update canonical descriptions
        print(f"\n[Step 2] Updating {len(CANONICAL_DESCRIPTIONS)} canonical benefit short descriptions:")
        all_concepts = db.scalars(select(BenefitConcept)).all()
        by_key = {c.concept_key: c for c in all_concepts}
        by_label = {c.label.strip().lower(): c for c in all_concepts}

        updated_count = 0
        for item in CANONICAL_DESCRIPTIONS:
            target = by_key.get(item["alias"])
            if not target:
                target = by_label.get(item["title"].strip().lower())

            if not target:
                print(f"  [ERROR] Unmatched concept: {item['title']} ({item['alias']})")
                continue

            old_desc = target.description
            new_desc = item["description"]
            if old_desc != new_desc:
                print(f"  [UPDATE] '{target.label}' ({target.concept_key})")
                print(f"     OLD: {old_desc}")
                print(f"     NEW: {new_desc}")
                target.description = new_desc
                updated_count += 1
            else:
                print(f"  [NO CHANGE] '{target.label}' ({target.concept_key}) already up to date")

        print(f"\nTotal descriptions updated: {updated_count} of {len(CANONICAL_DESCRIPTIONS)}")

        if not dry_run:
            db.commit()
            print("\n[SUCCESS] All changes successfully committed to database!")
        else:
            db.rollback()
            print("\n[DRY RUN] Rolled back all changes. Run with --apply to commit.")

    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] Transaction failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean test concepts and update benefit descriptions")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry run)")
    args = parser.parse_args()
    run_cleanup(dry_run=not args.apply)
