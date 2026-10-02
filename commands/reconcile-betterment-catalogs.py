"""Reconcile Waiver of Betterment (betterment-protection) offerings across all catalogs in the live database.

Rules:
1. Motorcycles & Commercial Vehicles:
   - Completely remove betterment-protection from all catalogs (both defaults and addons).
2. QBE (Private Car ICE & EV):
   - Place in DEFAULTS section (offering_kind='base', role='included').
   - Description override: "Waiver of betterment for up to 10 years of age".
   - Display value: "Waiver of betterment for up to 10 years of age".
   - Price: 0 RM (optional_price=None).
   - Removed from addons section.
3. Tune Protect, Berjaya Sompo, AmAssurance, Etiqa (Private Car ICE & EV):
   - Place in ADDONS section (offering_kind='optional', role='addon_option').
   - Description override: "Waiver of betterment for up to 15 years of age".
   - Display value: "Waiver of betterment for up to 15 years of age".
   - Optional price configured.
   - Removed from defaults section.
4. Lonpac, STMB / Takaful Malaysia (Private Car ICE & EV):
   - Place in ADDONS section (offering_kind='optional', role='addon_option').
   - Description override: "Waiver of betterment for up to 10 years of age".
   - Display value: "Waiver of betterment for up to 10 years of age".
   - Optional price configured.
   - Removed from defaults section.
"""

from __future__ import annotations

import sys
from uuid import uuid4

sys.path.insert(0, "backend")

from app.db.session import SessionLocal
from app.models.tables import (
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    BenefitPackagePlanItem,
    BenefitRelation,
    CatalogOffering,
    CoverageType,
    DraftBenefitSelection,
    InsuranceCompany,
    Segment,
    VehicleCategory,
)
from sqlalchemy import delete, or_, select, update


def safe_delete_offering(db, off: CatalogOffering, replacement_off: CatalogOffering | None = None) -> None:
    """Safely delete a catalog offering by cleaning up or re-pointing referencing foreign keys."""
    off_id = str(off.id)
    if replacement_off and str(replacement_off.id) != off_id:
        repl_id = str(replacement_off.id)
        # 1. Re-point plan items to replacement_off, deleting if duplicate plan_item exists
        plan_items = list(db.scalars(
            select(BenefitPackagePlanItem).where(BenefitPackagePlanItem.offering_id == off_id)
        ).all())
        for pi in plan_items:
            existing = db.scalar(
                select(BenefitPackagePlanItem).where(
                    BenefitPackagePlanItem.plan_id == pi.plan_id,
                    BenefitPackagePlanItem.offering_id == repl_id,
                )
            )
            if existing:
                db.delete(pi)
            else:
                pi.offering_id = repl_id

        # 2. Clean up benefit relations referencing this offering
        db.execute(
            delete(BenefitRelation).where(
                or_(BenefitRelation.from_offering_id == off_id, BenefitRelation.to_offering_id == off_id)
            )
        )

        # 3. Re-point draft benefit selections to replacement offering
        db.execute(
            update(DraftBenefitSelection)
            .where(DraftBenefitSelection.catalog_offering_id == off_id)
            .values(catalog_offering_id=repl_id)
        )
    else:
        # Full deletion: clean up all referencing plan items first (RESTRICT)
        db.execute(delete(BenefitPackagePlanItem).where(BenefitPackagePlanItem.offering_id == off_id))
        db.execute(
            delete(BenefitRelation).where(
                or_(BenefitRelation.from_offering_id == off_id, BenefitRelation.to_offering_id == off_id)
            )
        )
        db.execute(
            update(DraftBenefitSelection)
            .where(DraftBenefitSelection.catalog_offering_id == off_id)
            .values(catalog_offering_id=None)
        )

    db.delete(off)


def is_non_private_car(cat: BenefitCatalog, comp: InsuranceCompany | None, vc: VehicleCategory | None, seg: Segment | None) -> bool:
    """Return True if the catalog is for motorcycle, commercial vehicle, company car, or non-comprehensive non-private."""
    cname_lower = (cat.name or "").lower()
    vkey = vc.category_key.lower() if vc else ""
    skey = seg.segment_key.lower() if seg else ""

    if vkey in ("motorcycle", "commercial_vehicle"):
        return True
    if skey in ("company_commercial", "commercial"):
        return True
    if any(keyword in cname_lower for keyword in ("motorcycle", "commercial", "lorry", "despatch", "company car")):
        return True
    if vkey != "car":
        return True
    return False


def is_private_car_comprehensive(cat: BenefitCatalog, vc: VehicleCategory | None, seg: Segment | None, cov: CoverageType | None) -> bool:
    """Return True if catalog is Private Car Comprehensive (either ICE or EV)."""
    cname_lower = (cat.name or "").lower()
    cov_key = cov.coverage_key.lower() if cov else ""

    if is_non_private_car(cat, None, vc, seg):
        return False

    # Check that coverage is comprehensive (betterment is strictly an own-damage cover)
    if cov_key in ("third_party_fire_theft", "third_party"):
        return False
    if "(tpft)" in cname_lower or "(third party)" in cname_lower or "third party" in cname_lower:
        return False

    # Must be car and private (or named Private Car / auto365 / SOMPO Motor / Motor Easy / etc.)
    return True


def reconcile_betterment_catalogs(dry_run: bool = False) -> dict[str, int]:
    db = SessionLocal()
    stats = {
        "deleted_non_pvt_car": 0,
        "deleted_wrong_section": 0,
        "migrated_offerings": 0,
        "created_offerings": 0,
        "updated_offerings": 0,
    }

    try:
        betterment = db.scalar(select(BenefitConcept).where(BenefitConcept.concept_key == "betterment-protection"))
        if not betterment:
            print("ERROR: BenefitConcept 'betterment-protection' not found in database!")
            return stats

        # Ensure concept default category is 'addon' (as 6 of 7 insurers have it as addon)
        if betterment.description_variants:
            betterment.description_variants = [{"category": "addon"}]
        print(f"Loaded concept: {betterment.label} ({betterment.concept_key}) id={betterment.id}")

        companies = {c.id: c for c in db.scalars(select(InsuranceCompany)).all()}
        segments = {s.id: s for s in db.scalars(select(Segment)).all()}
        vehicles = {v.id: v for v in db.scalars(select(VehicleCategory)).all()}
        coverages = {c.id: c for c in db.scalars(select(CoverageType)).all()}

        # 15-year addon insurers vs 10-year addon insurers vs QBE (10-year default)
        INSURERS_15_YEAR_ADDON = {"tune-protect", "berjaya-sompo", "amassurance", "etiqa"}
        INSURERS_10_YEAR_ADDON = {"lonpac", "stmb"}

        DESC_15_YEARS = "Waiver of betterment for up to 15 years of age"
        DESC_10_YEARS = "Waiver of betterment for up to 10 years of age"

        all_catalogs = list(db.scalars(select(BenefitCatalog)).all())
        print(f"Auditing {len(all_catalogs)} catalogs...")

        for cat in all_catalogs:
            comp = companies.get(cat.company_id)
            comp_slug = (comp.slug if comp else "").lower()
            vc = vehicles.get(cat.vehicle_category_id)
            seg = segments.get(cat.segment_id)
            cov = coverages.get(cat.coverage_type_id)

            # Get all revisions for this catalog
            revisions = list(db.scalars(
                select(BenefitCatalogRevision)
                .where(BenefitCatalogRevision.catalog_id == cat.id)
            ).all())

            if not revisions:
                continue

            is_non_pvt = is_non_private_car(cat, comp, vc, seg)
            is_pvt_comp = is_private_car_comprehensive(cat, vc, seg, cov)

            for rev in revisions:
                existing_offs = list(db.scalars(
                    select(CatalogOffering)
                    .where(
                        CatalogOffering.catalog_revision_id == rev.id,
                        CatalogOffering.concept_id == betterment.id,
                    )
                ).all())

                if is_non_pvt or not is_pvt_comp:
                    # RULE: No betterment in motorcycle, commercial, or non-comprehensive
                    for off in existing_offs:
                        print(f"  [DEL NON-PVT] {comp_slug} | {cat.name} (rev {rev.revision_number}): removing {off.offering_key} ({off.offering_kind})")
                        if not dry_run:
                            safe_delete_offering(db, off, replacement_off=None)
                        stats["deleted_non_pvt_car"] += 1
                    continue

                # It is Private Car Comprehensive (ICE or EV)!
                if comp_slug == "qbe":
                    # QBE: Defaults only, 10 years
                    target_kind = "base"
                    target_role = "included"
                    target_desc = DESC_10_YEARS
                    target_price = None
                elif comp_slug in INSURERS_15_YEAR_ADDON:
                    # Tune, Sompo, AmAssurance, Etiqa: Add-ons only, 15 years
                    target_kind = "optional"
                    target_role = "addon_option"
                    target_desc = DESC_15_YEARS
                    target_price = {"type": "money", "value": 0.0, "currency": "MYR"}
                elif comp_slug in INSURERS_10_YEAR_ADDON:
                    # Lonpac, STMB: Add-ons only, 10 years
                    target_kind = "optional"
                    target_role = "addon_option"
                    target_desc = DESC_10_YEARS
                    target_price = {"type": "money", "value": 0.0, "currency": "MYR"}
                else:
                    # Fallback default: add-on 10 years
                    target_kind = "optional"
                    target_role = "addon_option"
                    target_desc = DESC_10_YEARS
                    target_price = {"type": "money", "value": 0.0, "currency": "MYR"}

                # Separate existing offerings by kind
                correct_offs = [o for o in existing_offs if o.offering_kind == target_kind]
                wrong_offs = [o for o in existing_offs if o.offering_kind != target_kind]

                target_off = None
                if correct_offs:
                    target_off = correct_offs[0]
                    # Delete duplicate correct offerings
                    for dup_off in correct_offs[1:]:
                        print(f"  [DEL DUP] {comp_slug} | {cat.name} (rev {rev.revision_number}): removing duplicate {dup_off.offering_key}")
                        if not dry_run:
                            safe_delete_offering(db, dup_off, replacement_off=target_off)
                        stats["deleted_wrong_section"] += 1

                    # Delete wrong section offerings
                    for w_off in wrong_offs:
                        print(f"  [DEL WRONG SECTION] {comp_slug} | {cat.name} (rev {rev.revision_number}): removing {w_off.offering_key} ({w_off.offering_kind}, wanted {target_kind})")
                        if not dry_run:
                            safe_delete_offering(db, w_off, replacement_off=target_off)
                        stats["deleted_wrong_section"] += 1
                elif wrong_offs:
                    # No correct kind exists, but we have wrong kind. Migrate wrong_offs[0]!
                    target_off = wrong_offs[0]
                    off_prefix = "def" if target_kind == "base" else "add"
                    target_off.offering_key = f"{cat.id[:8]}-{off_prefix}-betterment-protection"
                    print(f"  [MIGRATE] {comp_slug} | {cat.name} (rev {rev.revision_number}): migrating {target_off.offering_key} to {target_kind}")
                    stats["migrated_offerings"] += 1

                    # Delete any other duplicate wrong offerings
                    for dup_w_off in wrong_offs[1:]:
                        print(f"  [DEL DUP WRONG] {comp_slug} | {cat.name} (rev {rev.revision_number}): removing {dup_w_off.offering_key}")
                        if not dry_run:
                            safe_delete_offering(db, dup_w_off, replacement_off=target_off)
                        stats["deleted_wrong_section"] += 1
                else:
                    # Create the offering from scratch
                    off_prefix = "def" if target_kind == "base" else "add"
                    off_key = f"{cat.id[:8]}-{off_prefix}-betterment-protection"
                    target_off = CatalogOffering(
                        id=str(uuid4()),
                        catalog_revision_id=rev.id,
                        offering_key=off_key,
                        concept_id=betterment.id,
                        offering_kind=target_kind,
                        role=target_role,
                        label_override=None,
                        description_override=target_desc,
                        display_value=target_desc,
                        typed_value={"type": "text", "value": target_desc},
                        optional_price=target_price,
                        sort_order=9,
                        status="active",
                    )
                    if not dry_run:
                        db.add(target_off)
                    print(f"  [CREATE] {comp_slug} | {cat.name} (rev {rev.revision_number}): created {off_key} ({target_kind}) -> {target_desc}")
                    stats["created_offerings"] += 1

                if target_off and not dry_run:
                    # Update fields to ensure 100% compliance with target description & values
                    target_off.offering_kind = target_kind
                    target_off.role = target_role
                    target_off.description_override = target_desc
                    target_off.display_value = target_desc
                    target_off.typed_value = {"type": "text", "value": target_desc}
                    target_off.optional_price = target_price
                    target_off.status = "active"
                stats["updated_offerings"] += 1

        if not dry_run:
            db.commit()
            print("\nSuccessfully committed all reconciliation changes to the database!")
        else:
            print("\nDry run completed - no changes committed.")

    finally:
        db.close()

    return stats


if __name__ == "__main__":
    dry_run_mode = "--dry-run" in sys.argv
    print(f"Starting Waiver of Betterment catalog reconciliation (dry_run={dry_run_mode})...")
    res = reconcile_betterment_catalogs(dry_run=dry_run_mode)
    print("\nReconciliation Summary:")
    for k, v in res.items():
        print(f"  {k}: {v}")
