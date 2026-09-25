"""Seed underwriter-specific short descriptions (<80 chars) and deduplicate roadside assistance.

This script:
1. Deactivates standalone 'roadside-assistance' from company configs and catalog offerings
   (as emergency and breakdown towing is consolidated under 'towing').
2. Seeds company-specific underwriter short descriptions into:
   - `company_benefit_configs.baseline_description` (master pool)
   - `catalog_offerings.description_override` (active catalog scenarios)
   across all 7 underwriters (Berjaya Sompo, Lonpac, QBE, Etiqa, STMB, Tune Protect, AmAssurance).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add backend to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.db.session import SessionLocal
from sqlalchemy import text


COMPANY_BENEFIT_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "berjaya-sompo": {
        "towing": "24/7 unlimited distance towing to panel workshops and minor roadside repairs.",
        "agreed-value-market-value": "Settles total loss or theft on agreed value for car models up to 3 years old.",
        "all-drivers": "Waives RM400 compulsory excess for all authorized licensed drivers aged 21+.",
        "repair-workmanship-warranty": "12-month warranty on repair workmanship and replacement parts from panel shops.",
        "special-perils": "Built-in full protection against flood, typhoon, storm, and natural disasters.",
        "betterment-protection": "Waives betterment cost-sharing on new replacement parts for cars up to 15 yrs.",
        "key-replacement": "Reimburses car key replacement and reprogramming costs up to RM1,000 for theft.",
        "sompo-motor-nhancer": "Bundles CART downtime, passenger liability, RM25k PA per seat & RM1k key care.",
    },
    "lonpac": {
        "all-drivers": "Waives RM400 compulsory excess for unnamed authorized drivers aged 21+.",
        "towing": "Emergency accident towing cost reimbursement up to RM200 to nearest repairer.",
        "out-of-pocket-allowance": "PC Privilege 1 lump-sum transportation allowance of RM75 per own damage claim.",
        "natural-falling-objects": "PC Privilege 2 impact damage from falling objects up to 25% vehicle sum.",
        "document-replacement": "PC Privilege 3 smash-and-grab document replacement allowance up to RM150.",
        "betterment-protection": "Waives betterment cost-sharing on new original parts for cars aged 5-10 yrs.",
        "key-replacement": "Reimburses key and lock replacement up to RM2,000 due to theft or break-in.",
        "car-detailing-cleanup": "Reimburses professional car interior cleaning up to RM5,000 after a flood.",
        "repaint-spray-paint": "Reimburses complete exterior vehicle spray painting up to RM2,000 after repair.",
        "auto-assistance": "Upgrades towing coverage to elevated allowance up to RM600 or unlimited.",
        "repair-workmanship-warranty": "12-month panel repair warranty on workmanship from approved panel repairers.",
    },
    "qbe": {
        "betterment-protection": "0% betterment contribution on new original parts for vehicles up to 10 yrs old.",
        "total-loss-theft-allowance": "Lump-sum total loss or theft compassionate payout of 5% sum insured up to RM5k.",
        "towing": "24/7 emergency accident towing to preferred workshop or home across Malaysia.",
        "key-replacement": "Reimburses car lock and key replacement up to RM500 for break-in or theft.",
        "all-drivers": "Waives RM400 compulsory excess for all unnamed authorized licensed drivers.",
        "out-of-pocket-allowance": "Replacement car RM150/day (7 days), hotel RM250/day (5 days) & spray RM1.5k.",
        "car-detailing-cleanup": "Water damage interior car cleaning reimbursement up to RM1,500 after flood.",
        "first-loss-flood": "Standalone first loss natural disaster and flood coverage up to RM10,000.",
    },
    "etiqa": {
        "towing": "24/7 emergency accident towing to nearest approved repairer up to RM200.",
        "betterment-protection": "Waives betterment deduction on new replacement parts for vehicles up to 10 yrs.",
        "key-replacement": "Reimburses car key and lock replacement up to RM1,000 following loss or theft.",
        "total-loss-theft-allowance": "Immediate compassionate flood relief cash grant of RM1,000 without NCD loss.",
        "payd-telematics": "Drive-Less Save-More cash rebate up to 30% of base premium for low mileage.",
        "auto-assistance": "24/7 unlimited towing upgrade to policyholder preferred panel workshop.",
        "cashback-no-claim": "Up to 10-20% Shariah surplus cashback plus up to 30% low-mileage rebate (PAYD).",
        "repair-workmanship-warranty": "12-month panel repair warranty on parts and workmanship from panel workshops.",
    },
    "tune-protect": {
        "towing": "24/7 emergency accident towing assistance to nearest workshop up to RM200.",
        "payd-telematics": "Pay-As-You-Drive cash rebate up to 30% of premium for low annual mileage.",
        "all-drivers": "Waives RM400 compulsory excess penalty for unnamed authorized drivers.",
        "betterment-protection": "Waives betterment cost-sharing on new replacement parts for cars up to 10 yrs.",
        "key-replacement": "Reimburses car key replacement and reprogramming up to RM1,000 following theft.",
        "flood-relief-allowance": "Immediate compassionate flood cash grant up to RM1,000 without affecting NCD.",
        "auto-assistance": "Upgrades basic towing to extended distance or unlimited emergency towing.",
    },
    "amassurance": {
        "towing": "Accident emergency towing assistance up to RM200 to nearest panel repairer.",
        "repair-workmanship-warranty": "3-year warranty on repair workmanship carried out by approved panel repairers.",
        "all-drivers": "Waives RM400 compulsory excess for unnamed authorized drivers (End C007).",
        "betterment-protection": "Waives betterment contribution on new original parts for vehicles 5+ years old.",
        "auto-assistance": "24/7 breakdown towing assistance up to 150km round trip including toll charges.",
        "private-car-365": "Bundles All Drivers waiver, RM1,500 flood grant, RM1,000 key care & towing.",
        "key-replacement": "Reimburses car key replacement and reprogramming up to RM1,000 (Auto365 Pack).",
    },
    "takaful-malaysia": {
        "agreed-value-market-value": "Settles total loss or theft on agreed value without depreciation disputes.",
        "all-drivers": "Waives RM400 compulsory excess penalty for all authorized licensed drivers.",
        "towing": "24/7 breakdown and accident towing assistance up to 100 km round trip.",
        "cashback-no-claim": "Up to 15-50% surplus cashback return if no claims are incurred during the year.",
        "accidental-death": "RM15,000 accidental death cover for participant with RM1,000 bereavement.",
        "betterment-protection": "Waives betterment deductions on new original parts for vehicles up to 12 years.",
        "auto-assistance": "Upgrades 100 km towing cap to unlimited distance towing across Malaysia.",
        "key-replacement": "Reimburses replacement of lost, damaged, or stolen car keys up to RM1,000.",
    },
}


def run():
    print("=== SEEDING COMPANY BENEFIT DESCRIPTIONS & DEDUPLICATING ROADSIDE ASSIST ===")
    with SessionLocal() as db:
        # Bypass mutation triggers during this administrative seeding run
        db.execute(text("SET session_replication_role = replica;"))

        try:
            # 1. Load all companies
            companies = db.execute(text("SELECT id, slug, name FROM insurance_companies")).fetchall()
            comp_map = {c.slug: c for c in companies}
            print(f"Loaded {len(companies)} insurance companies.")

            # 2. Load all benefit concepts
            concepts = db.execute(text("SELECT id, concept_key, label FROM benefit_concepts")).fetchall()
            concept_map = {c.concept_key: c for c in concepts}
            print(f"Loaded {len(concepts)} canonical benefit concepts.")

            roadside_concept = concept_map.get("roadside-assistance")
            if roadside_concept:
                print(f"Found roadside-assistance concept id: {roadside_concept.id}")
                # Deactivate in company_benefit_configs
                res_rc = db.execute(
                    text("UPDATE company_benefit_configs SET is_enabled = false WHERE concept_id = :cid"),
                    {"cid": roadside_concept.id}
                )
                print(f"Deactivated roadside-assistance across {res_rc.rowcount} company_benefit_configs rows.")

                # Deactivate in catalog_offerings: set status = 'retired'
                res_ro = db.execute(
                    text("UPDATE catalog_offerings SET status = 'retired' WHERE concept_id = :cid"),
                    {"cid": roadside_concept.id}
                )
                print(f"Retired roadside-assistance across {res_ro.rowcount} catalog_offerings rows.")

            total_configs_updated = 0
            total_offerings_updated = 0

            # 3. Seed company-specific descriptions
            for slug, desc_map in COMPANY_BENEFIT_DESCRIPTIONS.items():
                comp = comp_map.get(slug)
                if not comp:
                    print(f"WARNING: Company slug '{slug}' not found in DB! Skipping.")
                    continue

                print(f"\nProcessing {comp.name} ({slug})...")

                for concept_key, desc_text in desc_map.items():
                    concept = concept_map.get(concept_key)
                    if not concept:
                        print(f"  WARNING: Concept key '{concept_key}' not found! Skipping.")
                        continue

                    # 3a. Update or insert company_benefit_configs
                    existing_cfg = db.execute(
                        text("SELECT id FROM company_benefit_configs WHERE company_id = :comp_id AND concept_id = :conc_id"),
                        {"comp_id": comp.id, "conc_id": concept.id}
                    ).fetchone()

                    if existing_cfg:
                        db.execute(
                            text("""
                                UPDATE company_benefit_configs
                                SET baseline_description = :desc, is_enabled = true
                                WHERE id = :cfg_id
                            """),
                            {"desc": desc_text, "cfg_id": existing_cfg.id}
                        )
                    else:
                        db.execute(
                            text("""
                                INSERT INTO company_benefit_configs (id, company_id, concept_id, is_enabled, baseline_description, created_at, updated_at)
                                VALUES (gen_random_uuid(), :comp_id, :conc_id, true, :desc, now(), now())
                            """),
                            {"comp_id": comp.id, "conc_id": concept.id, "desc": desc_text}
                        )
                    total_configs_updated += 1

                    # 3b. Update catalog_offerings across all catalogs belonging to this company's products
                    res_off = db.execute(
                        text("""
                            UPDATE catalog_offerings
                            SET description_override = :desc
                            WHERE concept_id = :conc_id
                              AND catalog_revision_id IN (
                                  SELECT bcr.id
                                  FROM benefit_catalog_revisions bcr
                                  JOIN benefit_catalogs bc ON bc.id = bcr.catalog_id
                                  JOIN insurance_products p ON p.id = bc.product_id
                                  WHERE p.company_id = :comp_id
                              )
                        """),
                        {"desc": desc_text, "conc_id": concept.id, "comp_id": comp.id}
                    )
                    total_offerings_updated += res_off.rowcount
                    print(f"  [{concept_key}] set desc ({len(desc_text)} chars) -> updated {res_off.rowcount} offerings.")

            # Restore normal trigger operation
            db.execute(text("SET session_replication_role = DEFAULT;"))
            db.commit()
            print(f"\n[DONE] Successfully updated {total_configs_updated} company_benefit_configs and {total_offerings_updated} catalog_offerings.")

        except Exception as e:
            db.execute(text("SET session_replication_role = DEFAULT;"))
            db.rollback()
            raise e


if __name__ == "__main__":
    run()
