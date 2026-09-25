"""Repair EV sessions to newest EV catalog revisions and fix cost_status for complimentary benefits.

Target Sessions:
1. '50caaa16-39f1-41f9-9ec2-90d1128611b6' (Etiqa Tesla Model Y)
2. '0987e192-20a9-4784-a1d0-76107940e45e' (Berjaya Sompo Tesla Model 3)
"""

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
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
    Session as SessionModel,
)


def repair_sessions():
    db = SessionLocal()
    try:
        # 1. Repair Etiqa Tesla Model Y
        print("=== Repairing Session 50caaa16-39f1-41f9-9ec2-90d1128611b6 (Etiqa Tesla Model Y) ===")
        etiqa_sess = db.get(SessionModel, "50caaa16-39f1-41f9-9ec2-90d1128611b6")
        if etiqa_sess:
            etiqa_draft = db.scalar(select(QuotationDraft).where(QuotationDraft.uploaded_file_id == etiqa_sess.uploaded_file_id))
            if etiqa_draft:
                ev_cat = db.get(BenefitCatalog, "fc5a6ac6-0edf-4a5d-804a-b85ef0f00cdd")
                if ev_cat:
                    latest_rev = db.scalar(
                        select(BenefitCatalogRevision)
                        .where(BenefitCatalogRevision.catalog_id == ev_cat.id)
                        .order_by(BenefitCatalogRevision.revision_number.desc())
                    )
                    if latest_rev:
                        print(f"Pinning Etiqa draft {etiqa_draft.id} to catalog {ev_cat.name} rev {latest_rev.revision_number} (id={latest_rev.id})")
                        etiqa_draft.product_id = ev_cat.product_id
                        etiqa_draft.catalog_revision_id = latest_rev.id

                        # Map selections to catalog offerings in the new revision
                        offerings = db.scalars(
                            select(CatalogOffering).where(CatalogOffering.catalog_revision_id == latest_rev.id)
                        ).all()
                        off_by_concept = {o.concept_id: o for o in offerings}
                        print(f"New revision has {len(offerings)} offerings.")

                        selections = db.scalars(
                            select(DraftBenefitSelection).where(DraftBenefitSelection.draft_id == etiqa_draft.id)
                        ).all()
                        for s in selections:
                            if s.concept_id and s.concept_id in off_by_concept:
                                matched_off = off_by_concept[s.concept_id]
                                s.catalog_offering_id = matched_off.id
                                s.item_kind = "catalog"
                                s.label_override = matched_off.label_override
                                print(f"  Mapped [{s.cost_status.upper()}] {s.label_override} -> offering {matched_off.offering_key}")

        # 2. Repair Berjaya Sompo Tesla Model 3
        print("\n=== Repairing Session 0987e192-20a9-4784-a1d0-76107940e45e (Sompo Tesla Model 3) ===")
        sompo_sess = db.get(SessionModel, "0987e192-20a9-4784-a1d0-76107940e45e")
        if sompo_sess:
            sompo_draft = db.scalar(select(QuotationDraft).where(QuotationDraft.uploaded_file_id == sompo_sess.uploaded_file_id))
            if sompo_draft:
                sompo = db.scalar(select(InsuranceCompany).where(InsuranceCompany.slug == "berjaya-sompo"))
                sompo_ev_cat = db.scalar(
                    select(BenefitCatalog).where(
                        BenefitCatalog.company_id == sompo.id,
                        BenefitCatalog.engine_type == "ev",
                        BenefitCatalog.coverage_type_id == "d1111111-0000-4000-8000-000000000001", # Comprehensive
                        BenefitCatalog.vehicle_category_id == "b1111111-0000-4000-8000-000000000001", # Car
                    )
                )
                if sompo_ev_cat:
                    sompo_latest_rev = db.scalar(
                        select(BenefitCatalogRevision)
                        .where(BenefitCatalogRevision.catalog_id == sompo_ev_cat.id)
                        .order_by(BenefitCatalogRevision.revision_number.desc())
                    )
                    if sompo_latest_rev:
                        print(f"Pinning Sompo draft {sompo_draft.id} to catalog {sompo_ev_cat.name} rev {sompo_latest_rev.revision_number} (id={sompo_latest_rev.id})")
                        sompo_draft.product_id = sompo_ev_cat.product_id
                        sompo_draft.catalog_revision_id = sompo_latest_rev.id

                        offerings = db.scalars(
                            select(CatalogOffering).where(CatalogOffering.catalog_revision_id == sompo_latest_rev.id)
                        ).all()
                        off_by_concept = {o.concept_id: o for o in offerings}
                        print(f"New revision has {len(offerings)} offerings.")

                        selections = db.scalars(
                            select(DraftBenefitSelection).where(DraftBenefitSelection.draft_id == sompo_draft.id)
                        ).all()

                        all_concepts = {c.id: c for c in db.scalars(select(BenefitConcept)).all()}

                        for s in selections:
                            concept = all_concepts.get(s.concept_id)
                            ckey = concept.concept_key if concept else ""

                            # Fix complimentary benefits misclassified as paid
                            if ckey in {"all-drivers", "special-perils", "roadside-assistance", "emergency-towing", "repair-workmanship-warranty"}:
                                s.cost_status = "included"
                                s.price = None
                                print(f"  Fixed complimentary cover -> INCLUDED: {s.label_override or ckey}")

                            if s.concept_id and s.concept_id in off_by_concept:
                                matched_off = off_by_concept[s.concept_id]
                                s.catalog_offering_id = matched_off.id
                                s.item_kind = "catalog"
                                s.label_override = matched_off.label_override
                                print(f"  Mapped [{s.cost_status.upper()}] {s.label_override} -> offering {matched_off.offering_key}")

        db.commit()
        print("\n=== Test sessions successfully repaired and committed! ===")

    finally:
        db.close()


if __name__ == "__main__":
    repair_sessions()
