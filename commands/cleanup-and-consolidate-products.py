"""
Cleanup orphaned Product-* test junk and consolidate duplicate generic packages
across insurers to their canonical brand policies.
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.session import SessionLocal
from sqlalchemy import text


def main():
    db = SessionLocal()
    try:
        print("=== Step 1: Lookup Canonical Product & Catalog IDs ===")
        qbe_pc = db.execute(text("SELECT id, name FROM insurance_products WHERE name = 'Private Car Protector'")).first()
        lonpac_pc = db.execute(text("SELECT id, name FROM insurance_products WHERE name = 'Private Car Secure'")).first()
        
        if not qbe_pc:
            raise RuntimeError("QBE canonical product 'Private Car Protector' not found")
        if not lonpac_pc:
            raise RuntimeError("Lonpac canonical product 'Private Car Secure' not found")
            
        print(f"QBE Canonical Car Product: {qbe_pc.name} ({qbe_pc.id})")
        print(f"Lonpac Canonical Car Product: {lonpac_pc.name} ({lonpac_pc.id})")

        # Find canonical catalog revision for QBE Private Car Protector
        qbe_cat_rev = db.execute(text("""
            SELECT r.id FROM benefit_catalog_revisions r
            JOIN benefit_catalogs c ON c.id = r.catalog_id
            WHERE c.product_id = :pid
            ORDER BY r.revision_number DESC LIMIT 1
        """), {"pid": qbe_pc.id}).scalar()

        # Find canonical catalog revision for Lonpac Private Car Secure
        lonpac_cat_rev = db.execute(text("""
            SELECT r.id FROM benefit_catalog_revisions r
            JOIN benefit_catalogs c ON c.id = r.catalog_id
            WHERE c.product_id = :pid
            ORDER BY r.revision_number DESC LIMIT 1
        """), {"pid": lonpac_pc.id}).scalar()

        print("=== Step 2: Remap Affected Drafts to Canonical Products ===")
        # Remap QBE test junk drafts
        junk_drafts = db.execute(text("""
            SELECT d.id, p.name FROM quotation_drafts d
            JOIN insurance_products p ON p.id = d.product_id
            WHERE p.name ILIKE 'Product-%'
        """)).fetchall()
        print(f"Remapping {len(junk_drafts)} drafts from Product-* junk to QBE Private Car Protector...")
        for row in junk_drafts:
            db.execute(text("""
                UPDATE quotation_drafts
                SET product_id = :canon_prod,
                    catalog_revision_id = COALESCE(:canon_rev, catalog_revision_id)
                WHERE id = :did
            """), {"canon_prod": qbe_pc.id, "canon_rev": qbe_cat_rev, "did": row.id})

        # Remap QBE Private Car Comprehensive drafts
        qbe_gen_drafts = db.execute(text("""
            SELECT d.id FROM quotation_drafts d
            JOIN insurance_products p ON p.id = d.product_id
            WHERE p.name = 'QBE Private Car Comprehensive'
        """)).fetchall()
        print(f"Remapping {len(qbe_gen_drafts)} drafts from QBE Private Car Comprehensive to Private Car Protector...")
        for row in qbe_gen_drafts:
            db.execute(text("""
                UPDATE quotation_drafts
                SET product_id = :canon_prod,
                    catalog_revision_id = COALESCE(:canon_rev, catalog_revision_id)
                WHERE id = :did
            """), {"canon_prod": qbe_pc.id, "canon_rev": qbe_cat_rev, "did": row.id})

        # Remap Lonpac Private Car Comprehensive drafts
        lonpac_gen_drafts = db.execute(text("""
            SELECT d.id FROM quotation_drafts d
            JOIN insurance_products p ON p.id = d.product_id
            WHERE p.name = 'Lonpac Private Car Comprehensive'
        """)).fetchall()
        print(f"Remapping {len(lonpac_gen_drafts)} drafts from Lonpac Private Car Comprehensive to Private Car Secure...")
        for row in lonpac_gen_drafts:
            db.execute(text("""
                UPDATE quotation_drafts
                SET product_id = :canon_prod,
                    catalog_revision_id = COALESCE(:canon_rev, catalog_revision_id)
                WHERE id = :did
            """), {"canon_prod": lonpac_pc.id, "canon_rev": lonpac_cat_rev, "did": row.id})

        db.commit()

        print("\n=== Step 3: Purge 47 Orphaned Product-* Records from QBE ===")
        del_res = db.execute(text("""
            DELETE FROM insurance_products
            WHERE name ILIKE 'Product-%'
        """))
        print(f"Deleted {del_res.rowcount} orphaned Product-* rows from insurance_products.")
        db.commit()

        print("\n=== Step 4: Archive Duplicate Generic Products Across Insurers ===")
        generic_product_names = [
            # QBE
            "QBE Private Car Comprehensive",
            "QBE Private Car Comprehensive (TPFT)",
            "QBE Private Car Comprehensive (Third Party)",
            "QBE Motorcycle Comprehensive",
            "QBE Motorcycle Comprehensive (TPFT)",
            "QBE Motorcycle Comprehensive (Third Party)",
            # Etiqa
            "Etiqa Private Car Comprehensive",
            "Etiqa Private Car Comprehensive (TPFT)",
            "Etiqa Private Car Comprehensive (Third Party)",
            "Etiqa Motorcycle Comprehensive",
            "Etiqa Motorcycle Comprehensive (TPFT)",
            "Etiqa Motorcycle Comprehensive (Third Party)",
            # Lonpac
            "Lonpac Private Car Comprehensive",
            "Lonpac Private Car Comprehensive (TPFT)",
            "Lonpac Private Car Comprehensive (Third Party)",
            "Lonpac Motorcycle Comprehensive",
            "Lonpac Motorcycle Comprehensive (TPFT)",
            "Lonpac Motorcycle Comprehensive (Third Party)",
            # AmAssurance legacy unspecific
            "Private Car Comprehensive",
        ]

        arch_res = db.execute(text("""
            UPDATE insurance_products
            SET status = 'archived'
            WHERE name = ANY(:names)
        """), {"names": generic_product_names})
        print(f"Archived {arch_res.rowcount} duplicate generic products in insurance_products.")

        print("\n=== Step 5: Archive Duplicate Generic Catalogs Across Insurers ===")
        arch_cat_res = db.execute(text("""
            UPDATE benefit_catalogs
            SET status = 'archived'
            WHERE name = ANY(:names)
        """), {"names": generic_product_names})
        print(f"Archived {arch_cat_res.rowcount} duplicate generic benefit_catalogs.")

        db.commit()
        print("\n[SUCCESS] All cleanups and consolidations successfully committed!")

    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] Transaction rolled back: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
