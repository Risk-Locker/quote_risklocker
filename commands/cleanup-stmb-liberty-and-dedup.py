import sys
import os
from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.db.session import SessionLocal
from app.models.tables import (
    BenefitCatalog,
    BenefitCatalogRevision,
    InsuranceProduct,
    QuotationDraft,
    InsuranceCompany,
)

def run():
    db = SessionLocal()
    try:
        print("=== 1. Purging 42 QBE Test Catalogs ===")
        qbe = db.query(InsuranceCompany).filter(InsuranceCompany.name.ilike("%qbe%")).first()
        if qbe:
            test_cats = db.query(BenefitCatalog).filter(
                BenefitCatalog.company_id == qbe.id,
                BenefitCatalog.name.ilike("test catalog%")
            ).all()
            print(f"Found {len(test_cats)} test catalogs for QBE remaining.")
            test_cat_ids = [c.id for c in test_cats]
            if test_cat_ids:
                db.execute(text("DELETE FROM catalog_offerings WHERE catalog_revision_id IN (SELECT id FROM benefit_catalog_revisions WHERE catalog_id = ANY(:ids))"), {"ids": test_cat_ids})
                db.execute(text("DELETE FROM benefit_catalog_revisions WHERE catalog_id = ANY(:ids)"), {"ids": test_cat_ids})
                db.execute(text("DELETE FROM benefit_catalogs WHERE id = ANY(:ids)"), {"ids": test_cat_ids})
                db.commit()
                print("Deleted test catalogs.")

        print("\n=== 2. STMB -> Takaful Migration & Repinning ===")
        legacy_stmb_prod_id = "84de9ee8-f83a-451d-bfbc-b61a476e1591"
        canonical_takaful_prod_id = "dd3b2ba6-1c78-49f3-b867-0a7d7194e1f1"

        takaful_cat = db.query(BenefitCatalog).filter(BenefitCatalog.product_id == canonical_takaful_prod_id).first()
        takaful_rev_id = None
        if takaful_cat:
            takaful_rev = db.query(BenefitCatalogRevision).filter(
                BenefitCatalogRevision.catalog_id == takaful_cat.id,
                BenefitCatalogRevision.state == "published"
            ).order_by(BenefitCatalogRevision.revision_number.desc()).first()
            if takaful_rev:
                takaful_rev_id = takaful_rev.id

        drafts_stmb = db.query(QuotationDraft).filter(QuotationDraft.product_id == legacy_stmb_prod_id).all()
        print(f"Repinning {len(drafts_stmb)} drafts from STMB to Takaful...")
        for d in drafts_stmb:
            d.product_id = canonical_takaful_prod_id
            if takaful_rev_id:
                d.catalog_revision_id = takaful_rev_id
            if d.fields and isinstance(d.fields, dict):
                f_copy = dict(d.fields)
                f_copy["product_name"] = {"value": "Takaful myMotor (Private Car)"}
                d.fields = f_copy
        db.commit()

        # Archive legacy STMB products and catalogs
        stmb_prods = db.query(InsuranceProduct).filter(
            InsuranceProduct.name.ilike("stmb%")
        ).all()
        for p in stmb_prods:
            p.status = "archived"
            for cat in db.query(BenefitCatalog).filter(BenefitCatalog.product_id == p.id).all():
                cat.status = "archived"
        print(f"Archived {len(stmb_prods)} legacy STMB products & catalogs.")
        db.commit()

        # Rename stmb- package keys to takaful- with trigger bypass
        db.execute(text("""
            ALTER TABLE benefit_packages DISABLE TRIGGER benefit_package_immutable;
            UPDATE benefit_packages SET package_key = replace(package_key, 'stmb-', 'takaful-') WHERE package_key ILIKE 'stmb-%';
            ALTER TABLE benefit_packages ENABLE TRIGGER benefit_package_immutable;
        """))
        db.commit()
        print("Renamed STMB package keys to takaful-.")

        print("\n=== 3. AmAssurance Deduplication & Draft Repinning ===")
        repins = [
            ("3633cd0c-010f-4041-b851-936e9fb7627a", "068a9ef1-6842-441d-85d0-3300efc9f773", "Auto365 Comprehensive Premier"),
            ("fa15f294-9bc2-4077-bde4-47060e2684e3", "c6e9c63a-175e-4f66-83de-8b2dcace058b", "Auto365 Comprehensive Plus"),
            ("8230d7e4-d724-4734-8044-270f23fa527b", "46575fed-3906-491c-a142-8c822359a212", "Auto365 Comprehensive Lite"),
        ]

        for dup_id, canon_id, name in repins:
            canon_cat = db.query(BenefitCatalog).filter(BenefitCatalog.product_id == canon_id).first()
            canon_rev_id = None
            if canon_cat:
                rev = db.query(BenefitCatalogRevision).filter(
                    BenefitCatalogRevision.catalog_id == canon_cat.id,
                    BenefitCatalogRevision.state == "published"
                ).order_by(BenefitCatalogRevision.revision_number.desc()).first()
                if rev:
                    canon_rev_id = rev.id

            dup_drafts = db.query(QuotationDraft).filter(QuotationDraft.product_id == dup_id).all()
            print(f"Repinning {len(dup_drafts)} drafts from duplicate {name} ({dup_id}) to {canon_id}...")
            for d in dup_drafts:
                d.product_id = canon_id
                if canon_rev_id:
                    d.catalog_revision_id = canon_rev_id
                if d.fields and isinstance(d.fields, dict):
                    f_copy = dict(d.fields)
                    f_copy["product_name"] = {"value": name}
                    d.fields = f_copy
            db.commit()

        # Archive duplicate products and their catalogs
        dups_to_archive = [
            "3633cd0c-010f-4041-b851-936e9fb7627a",
            "fa15f294-9bc2-4077-bde4-47060e2684e3",
            "8230d7e4-d724-4734-8044-270f23fa527b",
            "329a005d-32ef-4963-a95e-0f36071538dd",
            "e2615fa9-d6c7-4fa0-845b-0230f9b52da3",
        ]
        for p_id in dups_to_archive:
            prod = db.get(InsuranceProduct, p_id)
            if prod:
                prod.status = "archived"
                for cat in db.query(BenefitCatalog).filter(BenefitCatalog.product_id == p_id).all():
                    cat.status = "archived"
        print(f"Archived {len(dups_to_archive)} duplicate AmAssurance products & catalogs.")
        db.commit()

        print("\nAll database cleanups and migrations completed successfully!")
    finally:
        db.close()

if __name__ == "__main__":
    run()
