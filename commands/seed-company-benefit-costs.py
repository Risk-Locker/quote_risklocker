"""Seed brochure and policy prices across 7 insurers for active Benefit Profile v2 and cascade to catalogs.

Source Documents: docs/benefits/expanded/*.md and docs/benefits/concise/current_all_benefits_12092026.md
Rules:
- Defaults (FOC): baseline_cost = None
- Windscreen: baseline_cost = '15% of Sum Covered' (evaluated dynamically)
- Fixed Add-ons: exact policy prices from brochure
- Formulas/Percentages: exact rate string (e.g. '0.30% of Sum Insured', '15% of Accessory Value')
- Also update active CatalogOffering.optional_price & display_value where appropriate
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Add backend directory to sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.session import SessionLocal
from app.models.tables import (
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    BenefitProfile,
    CatalogOffering,
    CompanyBenefitConfig,
    InsuranceCompany,
    utcnow,
)
from sqlalchemy import select


COMPANY_BENEFIT_COSTS: dict[str, dict[str, str | None]] = {
    "qbe": {
        # Defaults
        "towing": None,
        "total-loss-theft-allowance": None,
        "personal-accident": None,
        "betterment-protection": None,
        "all-drivers": None,
        "key-replacement": None,
        "special-perils": None,
        "legal-costs-defense": None,
        "out-of-pocket-allowance": None,
        # Add-ons
        "windscreen": "15% of Sum Covered",
        "first-loss-flood": "RM 30.00",
        "strike-riot-civil-commotion": "0.30% of Sum Insured",
        "legal-liability-to-passengers": "RM 20.00",
        "legal-liability-of-passengers": "RM 7.50",
        "vehicle-accessories": "15% of Accessory Value",
        "car-detailing-cleanup": "RM 35.00",
        "repair-allowance": "RM 58.30",
        "tuition-purpose": "RM 25.00",
        "ncd-relief": "RM 80.00",
    },
    "takaful-malaysia": {
        # Defaults
        "agreed-value-market-value": None,
        "all-drivers": None,
        "betterment-protection": None,
        "personal-accident": None,
        "legal-costs-defense": None,
        "cashback-no-claim": None,
        "towing": None,
        "special-perils": None,
        # Add-ons
        "windscreen": "15% of Sum Covered",
        "legal-liability-to-passengers": "RM 30.00",
        "legal-liability-of-passengers": "RM 7.50",
        "motor-pa-plus": "RM 48.00",
    },
    "etiqa": {
        # Defaults
        "towing": None,
        "legal-costs-defense": None,
        "all-drivers": None,
        "betterment-protection": None,
        "key-replacement": None,
        "payd-telematics": None,
        "special-perils": None,
        # Add-ons
        "windscreen": "15% of Sum Covered",
        "strike-riot-civil-commotion": "0.30% of Sum Insured",
        "legal-liability-to-passengers": "RM 7.50",
        "legal-liability-of-passengers": "RM 7.50",
        "repair-allowance": "RM 55.00",
        "repaint-spray-paint": "RM 280.00",
        "child-car-seat": "RM 30.00",
        "ncd-relief": "RM 100.00",
        "gas-conversion-kit": "RM 90.00",
        "vehicle-accessories": "15% of Accessory Value",
    },
    "lonpac": {
        # Defaults
        "towing": None,
        "key-replacement": None,
        "betterment-protection": None,
        "personal-accident": None,
        "special-perils": None,
        "out-of-pocket-allowance": None,
        # Add-ons
        "windscreen": "15% of Sum Covered",
        "strike-riot-civil-commotion": "0.30% of Sum Insured",
        "legal-liability-to-passengers": "RM 20.00",
        "legal-liability-of-passengers": "RM 7.50",
        "repair-allowance": "RM 58.30",
        "vehicle-accessories": "15% of Accessory Value",
        "gas-conversion-kit": "RM 90.00",
        "ncd-relief": "RM 100.00",
        "car-detailing-cleanup": "RM 35.00",
        "repaint-spray-paint": "RM 90.00",
        "e-hailing-extension": "RM 45.00",
    },
    "berjaya-sompo": {
        # Defaults
        "special-perils": None,
        "all-drivers": None,
        "towing": None,
        "repair-workmanship-warranty": None,
        "legal-costs-defense": None,
        "agreed-value-market-value": None,
        "accidental-death": None,
        "betterment-protection": None,
        # Add-ons
        "windscreen": "15% of Sum Covered",
        "legal-liability-to-passengers": "RM 7.50",
        "legal-liability-of-passengers": "RM 7.50",
        "ncd-relief": "RM 50.00",
        "repair-allowance": "RM 58.00",
        "driver-passenger-protector": "RM 60.00",
        "e-hailing-extension": "RM 350.00",
        "sompo-motor-nhancer": "RM 150.00",
        "motorcycle-pa-bundle": "RM 150.00",
        "strike-riot-civil-commotion": "0.30% of Sum Insured",
        "attached-trailers": "RM 75.00",
        "auto-assistance": "RM 60.00",
        "tool-of-trade": "RM 120.00",
        "boom-damage": "RM 100.00",
    },
    "tune-protect": {
        # Defaults
        "payd-telematics": None,
        "betterment-protection": None,
        "towing": None,
        "all-drivers": None,
        "legal-costs-defense": None,
        "special-perils": None,
        "personal-accident": None,
        # Add-ons
        "windscreen": "15% of Sum Covered",
        "strike-riot-civil-commotion": "0.30% of Sum Insured",
        "legal-liability-to-passengers": "RM 20.00",
        "legal-liability-of-passengers": "RM 7.50",
        "repair-allowance": "RM 52.50",
        "vehicle-accessories": "15% of Accessory Value",
        "cross-border": "RM 50.00",
        "ferry-transit": "RM 35.00",
        "motorshield-bundle": "RM 135.00",
        "attached-trailers": "RM 50.00",
        "gas-conversion-kit": "RM 90.00",
    },
    "amassurance": {
        # Defaults
        "repair-workmanship-warranty": None,
        "towing": None,
        "legal-costs-defense": None,
        "betterment-scale": None,
        "special-perils": None,
        "windscreen-auto-reinstatement": None,
        "betterment-protection": None,
        # Add-ons
        "windscreen": "15% of Sum Covered",
        "strike-riot-civil-commotion": "0.30% of Sum Insured",
        "legal-liability-to-passengers": "RM 20.00",
        "legal-liability-of-passengers": "RM 7.50",
        "gas-conversion-kit": "RM 300.00",
        "repair-allowance": "RM 70.00",
        "ncd-relief": "RM 80.00",
        "driver-passenger-protector": "RM 98.00",
        "e-hailing-extension": "RM 350.00",
    },
}


def parse_cost_to_optional_price(cost_str: str | None) -> tuple[dict | None, str | None]:
    if not cost_str or not str(cost_str).strip():
        return None, None
    s = str(cost_str).strip()
    if "%" in s:
        return {"type": "formula", "display_text": s, "formula": s}, s
    try:
        clean = re.sub(r"[^0-9.]", "", s)
        if clean and float(clean) > 0:
            val = float(clean)
            return {"type": "money", "value": val, "currency": "MYR"}, f"RM {val:,.2f}"
    except Exception:
        pass
    return {"type": "string", "display_text": s, "value": s}, s


def main() -> None:
    db = SessionLocal()
    try:
        # Find active profile
        active_profile = db.scalar(
            select(BenefitProfile).where(BenefitProfile.is_active == True)
        )
        if not active_profile:
            print("[ERROR] No active benefit profile found.")
            sys.exit(1)

        print(f"[seed-costs] Active Profile: {active_profile.name} (v{active_profile.version_number}) [{active_profile.id}]")

        # Map concepts by key
        all_concepts = db.scalars(select(BenefitConcept)).all()
        concepts_by_key = {c.concept_key: c for c in all_concepts}

        # Seed company configs
        total_seeded = 0
        for company_slug, benefit_costs in COMPANY_BENEFIT_COSTS.items():
            company = db.scalar(
                select(InsuranceCompany).where(InsuranceCompany.slug == company_slug)
            )
            if not company:
                print(f"  [WARN] Company slug '{company_slug}' not found, skipping.")
                continue

            print(f"  -> Seeding pricing for {company.name} ({company_slug})...")
            company_seeded = 0
            for concept_key, price_val in benefit_costs.items():
                concept = concepts_by_key.get(concept_key)
                if not concept:
                    print(f"     [WARN] Concept key '{concept_key}' not found, skipping.")
                    continue

                cfg = db.scalar(
                    select(CompanyBenefitConfig).where(
                        CompanyBenefitConfig.company_id == company.id,
                        CompanyBenefitConfig.profile_id == active_profile.id,
                        CompanyBenefitConfig.concept_id == concept.id,
                    )
                )
                if cfg:
                    cfg.baseline_cost = price_val
                    cfg.updated_at = utcnow()
                    company_seeded += 1
                else:
                    cfg = CompanyBenefitConfig(
                        company_id=company.id,
                        profile_id=active_profile.id,
                        concept_id=concept.id,
                        is_enabled=True,
                        baseline_description=None,
                        baseline_cost=price_val,
                        created_at=utcnow(),
                        updated_at=utcnow(),
                    )
                    db.add(cfg)
                    company_seeded += 1

            total_seeded += company_seeded
            print(f"     Configured {company_seeded} benefit costs for {company_slug}.")

            # Cascade prices to draft catalog offerings of this company (published revisions are immutable)
            catalog_ids = db.scalars(
                select(BenefitCatalog.id).where(BenefitCatalog.company_id == company.id)
            ).all()

            if catalog_ids:
                draft_revisions = db.scalars(
                    select(BenefitCatalogRevision).where(
                        BenefitCatalogRevision.catalog_id.in_(catalog_ids),
                        BenefitCatalogRevision.state == "draft",
                    )
                ).all()
                draft_rev_ids = [r.id for r in draft_revisions]

                if draft_rev_ids:
                    offerings = db.scalars(
                        select(CatalogOffering).where(
                            CatalogOffering.catalog_revision_id.in_(draft_rev_ids)
                        )
                    ).all()

                    off_updated = 0
                    for off in offerings:
                        concept_obj = next((c for c in all_concepts if c.id == off.concept_id), None)
                        if not concept_obj or concept_obj.concept_key not in benefit_costs:
                            continue
                        target_cost = benefit_costs[concept_obj.concept_key]
                        opt_price, disp_val = parse_cost_to_optional_price(target_cost)
                        if target_cost is not None:
                            off.optional_price = opt_price
                            if not off.display_value or off.display_value.startswith("RM"):
                                off.display_value = disp_val
                            off_updated += 1
                    if off_updated > 0:
                        print(f"     Updated {off_updated} draft catalog offerings.")

        db.commit()
        print(f"\n[SUCCESS] Seeded {total_seeded} baseline costs across all 7 companies for active profile {active_profile.id}!")

    finally:
        db.close()


if __name__ == "__main__":
    main()
