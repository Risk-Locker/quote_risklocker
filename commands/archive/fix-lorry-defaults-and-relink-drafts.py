"""Add standard defaults to lorry catalogs and re-link all quotation drafts to active revision offerings."""

import hashlib
import json
import sys
import uuid

sys.path.insert(0, "backend")

from app.db.session import SessionLocal
from app.models.tables import (
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    CatalogOffering,
    DraftBenefitSelection,
    InsuranceCompany,
    QuotationDraft,
    new_id,
    utcnow,
)
from sqlalchemy import select


def main():
    db = SessionLocal()

    # 1. Fetch key concepts
    legal_defense_concept = db.scalars(select(BenefitConcept).where(BenefitConcept.concept_key == "legal-costs-defense")).first()
    betterment_concept = db.scalars(select(BenefitConcept).where(BenefitConcept.concept_key == "betterment-protection")).first()

    assert legal_defense_concept is not None
    assert betterment_concept is not None

    print(f"Legal defense concept ID: {legal_defense_concept.id}")
    print(f"Betterment concept ID: {betterment_concept.id}")

    # 2. Catalogs to ensure standard base defaults:
    # (Company Name, Catalog Name, include_legal_defense, include_betterment)
    targets = [
        ("Berjaya Sompo", "Commercial Lorry (General Haulage - A Permit)", True, True),
        ("Berjaya Sompo", "Commercial Lorry (Own Goods - C Permit)", True, True),
        ("Lonpac Insurance", "Commercial Lorry (General Haulage - A Permit)", True, False),  # Already has betterment
        ("Lonpac Insurance", "Commercial Lorry (Own Goods - C Permit)", True, False),  # Already has betterment
        ("Lonpac Insurance", "Lonpac Insurance Commercial Vehicle Comprehensive (EV)", True, False),
        ("Etiqa", "Commercial Lorry (General Haulage - A Permit)", False, True),  # Already has legal defense
        ("Etiqa", "Commercial Lorry (Own Goods - C Permit)", False, True),  # Already has legal defense
    ]

    new_rev_count = 0
    revisions_created = {}

    for comp_name, cat_name, add_legal, add_betterment in targets:
        comp = db.scalars(select(InsuranceCompany).where(InsuranceCompany.name == comp_name)).first()
        if not comp:
            print(f"[WARN] Company not found: {comp_name}")
            continue

        cat = db.scalars(
            select(BenefitCatalog)
            .where(BenefitCatalog.company_id == comp.id, BenefitCatalog.name == cat_name, BenefitCatalog.status != "archived")
        ).first()
        if not cat:
            print(f"[WARN] Catalog not found: {comp_name} - {cat_name}")
            continue

        latest_rev = db.scalars(
            select(BenefitCatalogRevision)
            .where(BenefitCatalogRevision.catalog_id == cat.id, BenefitCatalogRevision.state == "published")
            .order_by(BenefitCatalogRevision.revision_number.desc())
        ).first()

        if not latest_rev:
            print(f"[WARN] No published revision for {cat.name}")
            continue

        existing_offs = db.scalars(
            select(CatalogOffering).where(CatalogOffering.catalog_revision_id == latest_rev.id, CatalogOffering.status == "active")
        ).all()

        existing_concept_ids = {o.concept_id for o in existing_offs}
        needs_update = False
        if add_legal and legal_defense_concept.id not in existing_concept_ids:
            needs_update = True
        if add_betterment and betterment_concept.id not in existing_concept_ids:
            needs_update = True

        if not needs_update:
            print(f"[SKIP] {comp_name} | {cat_name} already has required defaults")
            continue

        # Create new revision
        new_rev_num = latest_rev.revision_number + 1
        new_rev_id = new_id()

        content_blob = {
            "catalog_id": cat.id,
            "revision_number": new_rev_num,
            "company_id": comp.id,
            "catalog_name": cat.name,
            "timestamp": "2026-09-15T03:30:00Z",
        }
        content_hash = hashlib.sha256(json.dumps(content_blob, sort_keys=True).encode("utf-8")).hexdigest()

        new_rev = BenefitCatalogRevision(
            id=new_rev_id,
            catalog_id=cat.id,
            revision_number=new_rev_num,
            state="draft",  # draft first to allow child inserts
            content_hash=content_hash,
        )
        db.add(new_rev)
        db.flush()

        # Copy existing offerings
        sort_order = 10
        for off in existing_offs:
            new_off = CatalogOffering(
                id=new_id(),
                catalog_revision_id=new_rev_id,
                offering_key=off.offering_key,
                concept_id=off.concept_id,
                offering_kind=off.offering_kind,
                role=off.role,
                status="active",
                sort_order=sort_order,
                label_override=off.label_override,
                typed_value=off.typed_value,
                optional_price=off.optional_price,
            )
            db.add(new_off)
            sort_order += 10

        # Add Legal Defense Costs as base included if requested
        if add_legal and legal_defense_concept.id not in existing_concept_ids:
            new_off = CatalogOffering(
                id=new_id(),
                catalog_revision_id=new_rev_id,
                offering_key=f"def-legal-costs-defense-{uuid.uuid4().hex[:8]}",
                concept_id=legal_defense_concept.id,
                offering_kind="base",
                role="included",
                status="active",
                sort_order=sort_order,
                label_override="Legal Defense Costs",
                typed_value={"type": "standard", "value": "Included"},
                optional_price=0.0,
            )
            db.add(new_off)
            sort_order += 10
            print(f"   [+] Added Legal Defense Costs to {comp_name} - {cat_name}")

        # Add Betterment Protection as base included if requested
        if add_betterment and betterment_concept.id not in existing_concept_ids:
            new_off = CatalogOffering(
                id=new_id(),
                catalog_revision_id=new_rev_id,
                offering_key=f"def-betterment-protection-{uuid.uuid4().hex[:8]}",
                concept_id=betterment_concept.id,
                offering_kind="base",
                role="included",
                status="active",
                sort_order=sort_order,
                label_override="Betterment Waiver",
                typed_value={"type": "standard", "value": "Included"},
                optional_price=0.0,
            )
            db.add(new_off)
            sort_order += 10
            print(f"   [+] Added Betterment Waiver to {comp_name} - {cat_name}")

        db.flush()

        # Publish new revision
        new_rev.state = "published"
        new_rev.published_at = utcnow()
        cat.revision = new_rev_num
        revisions_created[latest_rev.id] = new_rev_id
        new_rev_count += 1
        db.flush()

    db.commit()
    print(f"\n[DONE] Created and published {new_rev_count} new revisions with defaults.")

    # 3. Re-pin drafts pointing to previous revisions
    drafts_to_repin = db.scalars(select(QuotationDraft).where(QuotationDraft.catalog_revision_id.in_(list(revisions_created.keys())))).all()
    for d in drafts_to_repin:
        d.catalog_revision_id = revisions_created[d.catalog_revision_id]
    db.commit()
    print(f"[DONE] Repinned {len(drafts_to_repin)} drafts to newest revisions.")

    # 4. Re-link ALL drafts across DB where catalog_offering_id is orphaned or from previous revision
    all_drafts = db.scalars(select(QuotationDraft).where(QuotationDraft.catalog_revision_id.isnot(None))).all()
    relinked_selections = 0
    seeded_missing_defaults = 0

    for d in all_drafts:
        rev_offs = db.scalars(
            select(CatalogOffering).where(CatalogOffering.catalog_revision_id == d.catalog_revision_id, CatalogOffering.status == "active")
        ).all()
        off_by_concept = {o.concept_id: o for o in rev_offs if o.concept_id}
        off_ids = {o.id for o in rev_offs}

        sels = db.scalars(select(DraftBenefitSelection).where(DraftBenefitSelection.draft_id == d.id)).all()
        existing_concept_ids = {s.concept_id for s in sels if s.concept_id and s.state == "current"}

        for s in sels:
            if s.item_kind == "catalog" and s.catalog_offering_id not in off_ids:
                if s.concept_id and s.concept_id in off_by_concept:
                    new_o = off_by_concept[s.concept_id]
                    s.catalog_offering_id = new_o.id
                    relinked_selections += 1

        # Also seed missing base included offerings if draft has 0 base included benefits
        base_offs = [o for o in rev_offs if (o.offering_kind == "base" or getattr(o, "role", "") == "included") and o.concept_id]
        base_concept_ids = {b.concept_id for b in base_offs if b.concept_id}
        has_current_base = any(
            s.concept_id in base_concept_ids
            for s in sels if s.concept_id and s.state == "current"
        )
        if not has_current_base and base_offs:
            # Check vehicle type: skip towing if lorry, skip windscreen if motorcycle
            vtype = str((d.fields or {}).get("vehicle_type", "")).lower()
            is_lorry = any(k in vtype for k in ["lorry", "truck", "commercial", "haulage"])
            is_bike = any(k in vtype for k in ["motor", "bike"])

            for b in base_offs:
                if not b.concept_id:
                    continue
                if is_lorry and b.concept_id in [
                    "47e25689-0ef1-4db5-ae8e-251e8cd94af1",
                    "336302ae-014f-4135-a2d9-8a50cdd1e24f",
                    "1d89edbc-760a-438f-84bb-d6951bf90871",
                ]:
                    continue
                if is_bike and b.concept_id == "5dbde077-f14d-4b4d-9caf-b3ebdf272c89":
                    continue
                if b.concept_id not in existing_concept_ids:
                    db.add(DraftBenefitSelection(
                        id=new_id(),
                        draft_id=d.id,
                        selection_key=f"catalog:{b.offering_key}"[:160],
                        catalog_offering_id=b.id,
                        concept_id=b.concept_id,
                        state="current",
                        cost_status="included",
                        label_override=b.label_override,
                        typed_value_override=b.typed_value,
                        item_kind="catalog",
                        sort_order=b.sort_order,
                    ))
                    existing_concept_ids.add(b.concept_id)
                    seeded_missing_defaults += 1

    db.commit()
    print(f"[DONE] Relinked {relinked_selections} orphaned catalog selections across all drafts.")
    print(f"[DONE] Seeded {seeded_missing_defaults} missing base defaults into drafts with empty defaults.")
    db.close()


if __name__ == "__main__":
    main()
