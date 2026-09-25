"""Publish and align the AmAssurance package catalog (one-time repair, idempotent).

Sessions pin only PUBLISHED catalog revisions, and base-benefit seeding uses
the catalog's primary package. After the builder/benefits save bugs, the
AmAssurance catalog was left in draft state with its package_id pointing at a
package from the wrong revision, so sessions seeded zero benefits and showed
no tier chips.

This command, for every AmAssurance catalog whose product is "Private Car
Comprehensive":

  1. publishes the latest draft revision (if any) through the normal
     publish_catalog_revision service, and
  2. aligns catalog.package_id to the Lite package (lowest sort_order
     comprehensive package) of the now-published revision.

Safe to re-run: skips anything already aligned.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.db.session import SessionLocal
from app.models.tables import (
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitPackage,
    CatalogOffering,
    InsuranceCompany,
    InsuranceProduct,
    User,
)
from app.services.business_setup_service import publish_catalog_revision


def _actor(db):
    return db.scalar(select(User).where(User.role == "super_admin").order_by(User.created_at.asc()))


def _lite_package(db, revision_id: str) -> BenefitPackage | None:
    packages = db.scalars(
        select(BenefitPackage).where(
            BenefitPackage.catalog_revision_id == revision_id,
            BenefitPackage.package_kind == "comprehensive",
            BenefitPackage.status == "active",
        )
    ).all()
    if not packages:
        return None
    for key in ("lite", "auto365-comprehensive-lite"):
        match = next((item for item in packages if item.package_key == key), None)
        if match:
            return match
    return min(packages, key=lambda item: (int(item.sort_order or 0), item.name))


def build_plan(db) -> dict:
    company = db.scalar(select(InsuranceCompany).where(InsuranceCompany.slug == "amassurance"))
    if company is None:
        return {"error": "AmAssurance company row not found (slug=amassurance)."}
    products = db.scalars(
        select(InsuranceProduct).where(
            InsuranceProduct.company_id == company.id,
            InsuranceProduct.status == "active",
        )
    ).all()
    catalogs = [
        item
        for item in db.scalars(select(BenefitCatalog).where(BenefitCatalog.company_id == company.id)).all()
        if any(item.product_id == product.id for product in products)
    ]
    if not catalogs:
        return {"error": "No catalogs found for AmAssurance products.", "catalogs": []}
    steps = []
    for catalog in catalogs:
        revisions = list(
            db.scalars(
                select(BenefitCatalogRevision)
                .where(BenefitCatalogRevision.catalog_id == catalog.id)
                .order_by(BenefitCatalogRevision.revision_number.desc())
            ).all()
        )
        draft = next((item for item in revisions if item.state == "draft"), None)
        published = next((item for item in revisions if item.state == "published"), None)
        if draft is None and published is None:
            steps.append({"catalog": catalog.id, "name": catalog.name, "action": "skip", "reason": "no revisions"})
            continue
        target_revision = draft or published
        draft_offerings = (
            db.scalars(
                select(CatalogOffering).where(CatalogOffering.catalog_revision_id == target_revision.id)
            ).first()
            if draft is not None
            else True
        )
        step = {
            "catalog": str(catalog.id),
            "name": catalog.name,
            "status": catalog.status,
            "revision": catalog.revision,
            "draft_revision": draft.revision_number if draft else None,
            "published_revision": published.revision_number if published else None,
            "actions": [],
        }
        if draft is not None:
            if draft_offerings is None:
                step["actions"].append("blocked: draft revision has no offerings to publish")
            else:
                step["actions"].append(f"publish draft revision {draft.revision_number}")
        lite = _lite_package(db, target_revision.id) if (published or draft) else None
        if lite is not None and str(catalog.package_id or "") != str(lite.id):
            step["actions"].append(f"align package_id -> {lite.name} ({lite.id})")
        elif lite is None:
            step["actions"].append("blocked: no comprehensive package found to align")
        if not step["actions"]:
            step["actions"].append("already aligned")
        steps.append(step)
    return {"company": str(company.id), "steps": steps}


def apply_plan(db) -> dict:
    company = db.scalar(select(InsuranceCompany).where(InsuranceCompany.slug == "amassurance"))
    products = db.scalars(
        select(InsuranceProduct).where(InsuranceProduct.company_id == company.id, InsuranceProduct.status == "active")
    ).all()
    catalogs = [
        item
        for item in db.scalars(select(BenefitCatalog).where(BenefitCatalog.company_id == company.id)).all()
        if any(item.product_id == product.id for product in products)
    ]
    report = []
    actor = _actor(db)
    if actor is None:
        raise SystemExit("No super_admin user found to act as publisher.")
    for catalog in catalogs:
        revisions = list(
            db.scalars(
                select(BenefitCatalogRevision)
                .where(BenefitCatalogRevision.catalog_id == catalog.id)
                .order_by(BenefitCatalogRevision.revision_number.desc())
            ).all()
        )
        draft = next((item for item in revisions if item.state == "draft"), None)
        published = next((item for item in revisions if item.state == "published"), None)
        actions = []
        if draft is not None:
            has_offerings = db.scalars(
                select(CatalogOffering).where(CatalogOffering.catalog_revision_id == draft.id)
            ).first() is not None
            if not has_offerings:
                actions.append("skipped publish: draft has no offerings")
            else:
                publish_catalog_revision(db, actor, catalog.id, base_revision=catalog.revision)
                actions.append(f"published draft revision {draft.revision_number}")
                db.refresh(catalog)
                published = draft
        target = published or draft
        lite = _lite_package(db, target.id) if target else None
        if lite is not None and str(catalog.package_id or "") != str(lite.id):
            catalog.package_id = lite.id
            db.commit()
            actions.append(f"package_id aligned -> {lite.name} ({lite.id})")
        elif lite is not None:
            actions.append("package_id already aligned")
        report.append({"catalog": str(catalog.id), "name": catalog.name, "actions": actions})
    return {"company": str(company.id), "report": report}


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish and align the AmAssurance package catalog.")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry-run).")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        plan = build_plan(db)
        if "error" in plan and "steps" not in plan:
            raise SystemExit(f"Repair not possible: {plan['error']}")
        print(f"AmAssurance company id: {plan['company']}")
        for step in plan["steps"]:
            print(f"- {step['name']} ({step['catalog']}) status={step.get('status')} revision={step.get('revision')}")
            for action in step["actions"]:
                print(f"    * {action}")
        if not args.apply:
            print("Dry run: no changes made. Re-run with --apply to publish and align.")
            return
        report = apply_plan(db)
        print("Applied:")
        for entry in report["report"]:
            for action in entry["actions"]:
                print(f"- {entry['name']}: {action}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
