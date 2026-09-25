"""Cleanup and consolidate duplicate AmAssurance catalogs into canonical Auto365 package catalogs.

Remaps existing drafts from orphaned duplicate standalone catalogs to canonical package revisions,
then archives the duplicate catalogs and products.
"""

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.session import SessionLocal
from app.models.tables import BenefitCatalog, BenefitCatalogRevision, BenefitPackage, InsuranceProduct, QuotationDraft, utcnow
from sqlalchemy import select


def main():
    db = SessionLocal()
    try:
        # Mapping duplicate catalog -> (canonical_catalog_id, canonical_rev_id, canonical_pkg_id)
        # Canonical catalogs:
        # 1. auto365 Comprehensive Lite: d3241bc8-160e-4aba-83bb-c88aec3a6758, rev: ce614660-608c-4a9d-89e4-0efbaae4f82c, pkg: 8876707e-c05e-4924-8f50-1e987695a545
        # 2. auto365 Comprehensive Plus: 7ec7079a-ab2d-4984-97cc-bcd500c2679f, rev: de823b82-c7f5-475f-84ed-f39a7cec517d, pkg: 2bfa3935-fbc3-4062-b09f-b2fc40a4e38d
        # 3. auto365 Comprehensive Premier: 84199f87-a803-4670-904c-3363829cdbad, rev: 652187ec-829b-4e9f-8c24-5bd5c539f133, pkg: 6b4bfa9d-e394-4ffe-85a2-8cb325f425ec

        remap = {
            "88e3969b-616f-4d31-bef4-f7b6928fe7a5": {
                "name": "Auto365 Comprehensive Lite (duplicate)",
                "canon_cat_id": "d3241bc8-160e-4aba-83bb-c88aec3a6758",
                "canon_rev_id": "ce614660-608c-4a9d-89e4-0efbaae4f82c",
                "canon_pkg_id": "8876707e-c05e-4924-8f50-1e987695a545",
                "dup_prod_id": "46575fed-3906-491c-a142-8c822359a212",
            },
            "751b5494-8dbb-452e-8772-32a90d367c5e": {
                "name": "Auto365 Comprehensive Plus (duplicate)",
                "canon_cat_id": "7ec7079a-ab2d-4984-97cc-bcd500c2679f",
                "canon_rev_id": "de823b82-c7f5-475f-84ed-f39a7cec517d",
                "canon_pkg_id": "2bfa3935-fbc3-4062-b09f-b2fc40a4e38d",
                "dup_prod_id": "c6e9c63a-175e-4f66-83de-8b2dcace058b",
            },
            "d8c38149-256a-42a0-a755-f155023a5643": {
                "name": "Auto365 Comprehensive Premier (duplicate)",
                "canon_cat_id": "84199f87-a803-4670-904c-3363829cdbad",
                "canon_rev_id": "652187ec-829b-4e9f-8c24-5bd5c539f133",
                "canon_pkg_id": "6b4bfa9d-e394-4ffe-85a2-8cb325f425ec",
                "dup_prod_id": "068a9ef1-6842-441d-85d0-3300efc9f773",
            },
        }

        total_remapped = 0
        canonical_car_product_id = "6549519c-eda5-4c93-bf1e-bb2da87ce268"

        for dup_cat_id, info in remap.items():
            dup_cat = db.get(BenefitCatalog, dup_cat_id)
            if not dup_cat:
                continue

            rev_ids = [
                r.id for r in db.scalars(
                    select(BenefitCatalogRevision).where(BenefitCatalogRevision.catalog_id == dup_cat_id)
                ).all()
            ]

            drafts = list(
                db.scalars(
                    select(QuotationDraft).where(QuotationDraft.catalog_revision_id.in_(rev_ids))
                ).all()
            ) if rev_ids else []

            for d in drafts:
                d.catalog_revision_id = info["canon_rev_id"]
                d.package_id = info["canon_pkg_id"]
                d.product_id = canonical_car_product_id
                d.updated_at = utcnow()
                total_remapped += 1

            # Archive duplicate catalog
            dup_cat.status = "archived"
            dup_cat.updated_at = utcnow()

            # Archive duplicate product
            dup_prod = db.get(InsuranceProduct, info["dup_prod_id"])
            if dup_prod:
                dup_prod.status = "archived"
                dup_prod.updated_at = utcnow()

            print(f"Archived {info['name']} ({dup_cat_id}): remapped {len(drafts)} drafts to canonical package revision")

        db.commit()
        print(f"Done! Successfully consolidated AmAssurance catalogs and remapped {total_remapped} drafts.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
