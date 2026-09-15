"""
Sanitization Script (Immutable Revision Pattern):
1. Enforce Lorry Towing Invariant: Create new published revision for all commercial lorry & commercial vehicle catalogs excluding any towing offerings.
2. Enforce Motorcycle Windscreen Invariant: Verify & exclude any windscreen offerings from new motorcycle catalog revisions.
3. Promote EV Comprehensive Defaults: In new revisions of EV Comprehensive catalogs, promote complimentary benefits (Towing for Cars, Legal Defense Costs, Panel Warranty) to role="included", offering_kind="base".
4. Populate empty Lonpac Motorcycle TPO catalogs with legal liability add-on.
5. Re-pin any active QuotationDrafts referencing old revisions to the new published revisions, and purge any lorry draft towing selections.
"""

import sys
from pathlib import Path
from hashlib import sha256

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select, delete, update
from app.db.session import SessionLocal
from app.models.tables import (
    InsuranceCompany,
    InsuranceProduct,
    BenefitCatalog,
    BenefitCatalogRevision,
    CatalogOffering,
    BenefitConcept,
    QuotationDraft,
    DraftBenefitSelection,
    new_id,
    utcnow,
)

TOWING_CONCEPT_KEYS = {
    "towing",
    "emergency-towing",
    "unlimited-towing",
    "ev-battery-depletion-towing",
    "roadside-assistance",
    "auto-assistance",
}

WINDSCREEN_CONCEPT_KEYS = {
    "windscreen",
    "windscreen-damage",
    "windscreen-auto-reinstatement",
}

def is_lorry_catalog(cat_name: str, prod_name: str) -> bool:
    text = (cat_name + " " + prod_name).lower()
    if "company car" in text:
        return False
    return any(k in text for k in [
        "lorry", "haulage", "c permit", "a permit", "commercial vehicle",
        "commercial lorry", "prime mover", "rigid", "tipper", "trailer"
    ])

def is_motorcycle_catalog(cat_name: str, prod_name: str) -> bool:
    text = (cat_name + " " + prod_name).lower()
    return any(k in text for k in ["motorcycle", "bike", "motosikal"])


def run_sanitization():
    db = SessionLocal()
    try:
        print("=== Step 1: Mapping Concepts ===")
        all_concepts = {c.id: c for c in db.scalars(select(BenefitConcept)).all()}
        concept_by_key = {c.concept_key: c for c in all_concepts.values()}
        
        towing_concept_ids = {c.id for c in all_concepts.values() if c.concept_key in TOWING_CONCEPT_KEYS or any(k in c.label.lower() for k in ["towing", "roadside assistance helpline"])}
        windscreen_concept_ids = {c.id for c in all_concepts.values() if c.concept_key in WINDSCREEN_CONCEPT_KEYS or "windscreen" in c.label.lower()}
        
        print(f"Identified {len(towing_concept_ids)} Towing concept IDs")
        print(f"Identified {len(windscreen_concept_ids)} Windscreen concept IDs")

        catalogs = db.scalars(
            select(BenefitCatalog).where(
                BenefitCatalog.status.in_(["published", "active", "draft"])
            )
        ).all()
        print(f"Total non-archived catalogs to inspect: {len(catalogs)}")

        towing_deleted_count = 0
        windscreen_deleted_count = 0
        ev_promoted_count = 0
        new_revisions_created = 0
        rev_id_map = {} # old_rev_id -> new_rev_id

        for cat in catalogs:
            prod = db.get(InsuranceProduct, cat.product_id) if cat.product_id else None
            pname = prod.name if prod else ""
            cname = cat.name
            
            # Find latest revision
            revisions = db.scalars(
                select(BenefitCatalogRevision)
                .where(BenefitCatalogRevision.catalog_id == cat.id)
                .order_by(BenefitCatalogRevision.revision_number.desc())
            ).all()
            if not revisions:
                continue
            latest_rev = revisions[0]

            offerings = list(
                db.scalars(
                    select(CatalogOffering).where(CatalogOffering.catalog_revision_id == latest_rev.id)
                ).all()
            )

            is_lorry = is_lorry_catalog(cname, pname)
            is_bike = is_motorcycle_catalog(cname, pname)
            is_ev_comp = ("(ev)" in (cname + " " + pname).lower() or " ev" in (cname + " " + pname).lower()) and "comprehensive" in (cname + " " + pname).lower()
            is_car = not is_bike and not is_lorry

            needs_update = False

            # Check if any lorry towing needs removal
            if is_lorry and any(o.concept_id in towing_concept_ids for o in offerings):
                needs_update = True
            # Check if any bike windscreen needs removal
            if is_bike and any(o.concept_id in windscreen_concept_ids for o in offerings):
                needs_update = True
            # Check if any EV comp benefits need promotion
            if is_ev_comp:
                for o in offerings:
                    c_obj = all_concepts.get(o.concept_id)
                    ckey = c_obj.concept_key if c_obj else ""
                    if is_car and ckey == "towing" and o.role != "included":
                        needs_update = True
                    elif ckey in ["legal-costs-defense", "repair-workmanship-warranty"] and o.role != "included":
                        needs_update = True

            if not needs_update:
                continue

            # Create new revision (state='draft' during offering insertion)
            next_rev_num = latest_rev.revision_number + 1
            new_rev_id = new_id()
            new_rev = BenefitCatalogRevision(
                id=new_rev_id,
                catalog_id=cat.id,
                revision_number=next_rev_num,
                state="draft",
                source_document_ids=latest_rev.source_document_ids or [],
                content_hash=sha256(f"{cat.id}:{next_rev_num}:{utcnow()}".encode()).hexdigest(),
            )
            db.add(new_rev)
            db.flush()

            sort_idx = 1
            for off in offerings:
                c_obj = all_concepts.get(off.concept_id)
                ckey = c_obj.concept_key if c_obj else ""

                # Filter 1: Lorries CANNOT have Towing
                if is_lorry and off.concept_id in towing_concept_ids:
                    print(f"  [LORRY TOWING REMOVAL] Excluding '{c_obj.label if c_obj else off.offering_key}' from new rev of '{cname}'")
                    towing_deleted_count += 1
                    continue

                # Filter 2: Motorcycles CANNOT have Windscreen
                if is_bike and off.concept_id in windscreen_concept_ids:
                    print(f"  [BIKE WINDSCREEN REMOVAL] Excluding '{c_obj.label if c_obj else off.offering_key}' from new rev of '{cname}'")
                    windscreen_deleted_count += 1
                    continue

                # Filter 3: EV Comprehensive Defaults Promotion
                role = off.role
                kind = off.offering_kind
                price = off.optional_price
                if is_ev_comp:
                    should_promote = False
                    if is_car and ckey == "towing":
                        should_promote = True
                    elif ckey in ["legal-costs-defense", "repair-workmanship-warranty"]:
                        should_promote = True

                    if should_promote and role != "included":
                        role = "included"
                        kind = "base"
                        price = None
                        ev_promoted_count += 1
                        print(f"  [EV DEFAULT PROMOTED] '{c_obj.label if c_obj else off.offering_key}' -> role=included in new rev of '{cname}'")

                # Insert offering into new revision
                new_offering = CatalogOffering(
                    id=new_id(),
                    catalog_revision_id=new_rev.id,
                    offering_key=off.offering_key,
                    concept_id=off.concept_id,
                    offering_kind=kind,
                    applies_to_type=off.applies_to_type,
                    applies_to_id=off.applies_to_id,
                    role=role,
                    label_override=off.label_override,
                    description_override=off.description_override,
                    typed_value=off.typed_value,
                    display_value=off.display_value,
                    optional_price=price,
                    source_document_id=off.source_document_id,
                    source_citation=off.source_citation or {},
                    source_aliases=off.source_aliases or [],
                    presentation_facet_ids=off.presentation_facet_ids or [],
                    sort_order=sort_idx,
                    status="active",
                )
                db.add(new_offering)
                sort_idx += 1

            db.flush()

            # Now publish the new revision
            new_rev.state = "published"
            new_rev.published_at = utcnow()
            cat.revision = next_rev_num
            cat.status = "published"
            rev_id_map[latest_rev.id] = new_rev.id
            new_revisions_created += 1

        db.flush()
        print(f"\nCompleted catalog offerings sanitization:")
        print(f"  - New revisions created & published: {new_revisions_created}")
        print(f"  - Towing offerings excluded from Lorries: {towing_deleted_count}")
        print(f"  - Windscreen offerings excluded from Motorcycles: {windscreen_deleted_count}")
        print(f"  - EV offerings promoted to default included: {ev_promoted_count}")

        # --- RULE 4: Populate Empty Lonpac Motorcycle TPO Catalogs ---
        print("\n=== Step 2: Populating Empty Lonpac Motorcycle TPO Catalogs ===")
        lonpac = db.scalar(select(InsuranceCompany).where(InsuranceCompany.slug == "lonpac"))
        if lonpac:
            lonpac_bike_tpo_cats = db.scalars(
                select(BenefitCatalog).where(
                    BenefitCatalog.company_id == lonpac.id,
                    BenefitCatalog.name.like("%Motorcycle%"),
                    BenefitCatalog.name.like("%Third Party%"),
                    BenefitCatalog.status != "archived",
                )
            ).all()

            llp_concept = concept_by_key.get("legal-liability-to-passengers")
            for cat in lonpac_bike_tpo_cats:
                revisions = db.scalars(
                    select(BenefitCatalogRevision)
                    .where(BenefitCatalogRevision.catalog_id == cat.id)
                    .order_by(BenefitCatalogRevision.revision_number.desc())
                ).all()
                latest_rev = revisions[0] if revisions else None

                offs = []
                if latest_rev:
                    offs = db.scalars(
                        select(CatalogOffering).where(CatalogOffering.catalog_revision_id == latest_rev.id)
                    ).all()

                if len(offs) == 0 and llp_concept:
                    next_rev_num = (latest_rev.revision_number + 1) if latest_rev else 1
                    new_rev = BenefitCatalogRevision(
                        id=new_id(),
                        catalog_id=cat.id,
                        revision_number=next_rev_num,
                        state="draft",
                        content_hash=sha256(f"{cat.id}:{next_rev_num}".encode()).hexdigest(),
                    )
                    db.add(new_rev)
                    db.flush()

                    new_off = CatalogOffering(
                        id=new_id(),
                        catalog_revision_id=new_rev.id,
                        offering_key=f"lonpac-bike-tpo-llp-{new_id()[:6]}",
                        concept_id=llp_concept.id,
                        offering_kind="optional",
                        role="addon_option",
                        label_override=llp_concept.label,
                        description_override="Protects against legal liability to pillion passengers.",
                        optional_price={"raw": "RM 20", "currency": "MYR"},
                        presentation_facet_ids=[],
                        sort_order=1,
                        status="active",
                    )
                    db.add(new_off)
                    db.flush()

                    new_rev.state = "published"
                    new_rev.published_at = utcnow()
                    cat.revision = next_rev_num
                    cat.status = "published"
                    if latest_rev:
                        rev_id_map[latest_rev.id] = new_rev.id
                    print(f"  Populated empty Lonpac catalog '{cat.name}' with Legal Liability to Passengers in rev #{next_rev_num}")

        # --- RULE 5: Re-pin Active QuotationDrafts to New Revisions & Clean Lorry Towing Selections ---
        print("\n=== Step 3: Re-pinning Drafts and Cleaning Lorry Towing Selections ===")
        drafts = db.scalars(select(QuotationDraft)).all()
        draft_repinned_count = 0
        draft_selections_purged = 0

        for draft in drafts:
            # Re-pin draft to new revision if old revision was updated
            if draft.catalog_revision_id in rev_id_map:
                draft.catalog_revision_id = rev_id_map[draft.catalog_revision_id]
                draft_repinned_count += 1

            def get_fval(fdict, fname):
                val = (fdict or {}).get(fname)
                if isinstance(val, dict):
                    val = val.get("value")
                return str(val or "").strip().lower()

            vtype = get_fval(draft.fields, "vehicle_type")
            cmodel = get_fval(draft.fields, "car_model")
            pname = ""
            if draft.product_id:
                p = db.get(InsuranceProduct, draft.product_id)
                if p:
                    pname = p.name.lower()
            
            is_lorry_draft = any(k in (vtype + " " + cmodel + " " + pname) for k in [
                "lorry", "haulage", "c permit", "a permit", "commercial", "fuso", "hino", "canter", "isuzu npr"
            ])
            if is_lorry_draft:
                selections = list(db.scalars(
                    select(DraftBenefitSelection).where(DraftBenefitSelection.draft_id == draft.id)
                ).all())
                for sel in selections:
                    is_towing = False
                    if sel.concept_id and sel.concept_id in towing_concept_ids:
                        is_towing = True
                    elif sel.catalog_offering_id:
                        off = db.get(CatalogOffering, sel.catalog_offering_id)
                        if off and off.concept_id in towing_concept_ids:
                            is_towing = True
                    if is_towing:
                        print(f"  Purging towing selection from Lorry Draft {draft.id}")
                        db.delete(sel)
                        draft_selections_purged += 1

        print(f"Total drafts re-pinned to new published revisions: {draft_repinned_count}")
        print(f"Total draft towing selections purged for lorries: {draft_selections_purged}")

        db.commit()
        print("\nAll database sanitizations successfully committed and published!")

    finally:
        db.close()

if __name__ == "__main__":
    run_sanitization()
