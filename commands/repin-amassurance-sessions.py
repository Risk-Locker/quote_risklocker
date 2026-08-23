"""Re-pin AmAssurance quotation drafts to the newest published catalog revision and tier.

Idempotent repair script. Older sessions (e.g. pinned to revision 1) or sessions
lacking an explicit draft.package_id are re-pinned to the newest published revision
(revision 3) and re-seeded with the appropriate tier defaults (e.g. auto365 Lite).

Safe to run repeatedly; skips drafts that are already on the newest revision with
a valid package_id.
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
    DraftBenefitSelection,
    InsuranceCompany,
    QuotationDraft,
    Session,
)
from app.services.catalog_review_service import (
    auto_apply_extracted_benefits,
    seed_base_benefits,
)


def _get_amassurance_company(db) -> InsuranceCompany | None:
    company = db.scalar(select(InsuranceCompany).where(InsuranceCompany.slug == "amassurance"))
    if not company:
        company = db.scalar(
            select(InsuranceCompany).where(
                InsuranceCompany.name.ilike("%amassurance%"),
                InsuranceCompany.status == "active",
            )
        )
    return company


def _get_newest_published_revision(db, company_id: str) -> tuple[BenefitCatalogRevision | None, list[BenefitPackage]]:
    catalogs = db.scalars(
        select(BenefitCatalog).where(
            BenefitCatalog.company_id == company_id,
            BenefitCatalog.status.in_(["active", "published"]),
        )
    ).all()
    if not catalogs:
        return None, []
    cat_ids = [c.id for c in catalogs]
    revisions = db.scalars(
        select(BenefitCatalogRevision).where(
            BenefitCatalogRevision.catalog_id.in_(cat_ids),
            BenefitCatalogRevision.state == "published",
        )
    ).all()
    if not revisions:
        return None, []
    newest = max(revisions, key=lambda r: (int(r.revision_number), str(r.id)))
    packages = db.scalars(
        select(BenefitPackage).where(
            BenefitPackage.catalog_revision_id == newest.id,
            BenefitPackage.package_kind == "comprehensive",
            BenefitPackage.status == "active",
        )
    ).all()
    packages = sorted(packages, key=lambda p: (int(p.sort_order or 0), p.name.casefold()))
    return newest, packages


def build_plan(db) -> dict:
    company = _get_amassurance_company(db)
    if not company:
        return {"error": "AmAssurance company not found in database."}

    revision, packages = _get_newest_published_revision(db, company.id)
    if not revision:
        return {"error": "No published revision found for AmAssurance."}
    if not packages:
        return {"error": f"No active comprehensive packages found in AmAssurance revision {revision.id}."}

    default_pkg = min(packages, key=lambda p: (int(p.sort_order or 0), p.name.casefold()))
    pkg_by_key = {p.package_key: p for p in packages}
    pkg_ids = {p.id for p in packages}

    drafts = db.scalars(
        select(QuotationDraft).where(
            QuotationDraft.company_id == company.id,
            QuotationDraft.deleted_at.is_(None),
        )
    ).all()

    items = []
    for draft in drafts:
        needs_repinned = draft.catalog_revision_id != revision.id
        needs_package = not draft.package_id or draft.package_id not in pkg_ids

        if not needs_repinned and not needs_package:
            items.append({
                "draft_id": draft.id,
                "action": "skip",
                "current_rev": draft.catalog_revision_id,
                "current_pkg": draft.package_id,
                "target_rev": revision.id,
                "target_pkg": draft.package_id,
            })
            continue

        target_pkg = default_pkg
        if draft.package_id:
            old_pkg = db.get(BenefitPackage, draft.package_id)
            if old_pkg and old_pkg.package_key in pkg_by_key:
                target_pkg = pkg_by_key[old_pkg.package_key]

        items.append({
            "draft_id": draft.id,
            "action": "repin",
            "current_rev": draft.catalog_revision_id,
            "current_pkg": draft.package_id,
            "target_rev": revision.id,
            "target_pkg_id": target_pkg.id,
            "target_pkg_name": target_pkg.name,
        })

    return {
        "company_id": company.id,
        "company_name": company.name,
        "newest_revision_id": revision.id,
        "newest_revision_number": revision.revision_number,
        "available_packages": [p.name for p in packages],
        "items": items,
    }


def apply_plan(db, plan: dict) -> list[dict]:
    results = []
    rev_id = plan["newest_revision_id"]
    revision = db.get(BenefitCatalogRevision, rev_id)

    for item in plan["items"]:
        if item["action"] != "repin":
            continue
        draft = db.get(QuotationDraft, item["draft_id"])
        if not draft:
            continue

        draft.catalog_revision_id = rev_id
        draft.package_id = item["target_pkg_id"]

        # Clear old catalog selections
        selections = db.scalars(
            select(DraftBenefitSelection).where(
                DraftBenefitSelection.draft_id == draft.id,
                DraftBenefitSelection.item_kind == "catalog",
            )
        ).all()
        for s in selections:
            db.delete(s)

        seed_base_benefits(db, draft, revision)
        auto_apply_extracted_benefits(db, draft)
        draft.revision += 1
        db.commit()

        results.append({
            "draft_id": draft.id,
            "status": "repinned",
            "package": item["target_pkg_name"],
            "revision_number": plan["newest_revision_number"],
        })

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-pin AmAssurance quotation drafts.")
    parser.add_argument("--apply", action="store_true", help="Apply the re-pin and re-seeding changes.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        plan = build_plan(db)
        if "error" in plan:
            print(f"Error: {plan['error']}")
            sys.exit(1)

        print(f"Company: {plan['company_name']} ({plan['company_id']})")
        print(f"Target Revision: {plan['newest_revision_id']} (rev {plan['newest_revision_number']})")
        print(f"Available Packages: {', '.join(plan['available_packages'])}")
        print()

        repin_count = sum(1 for i in plan["items"] if i["action"] == "repin")
        skip_count = sum(1 for i in plan["items"] if i["action"] == "skip")
        print(f"Found {len(plan['items'])} drafts: {repin_count} to repin, {skip_count} already current.")

        for i in plan["items"]:
            if i["action"] == "repin":
                print(f"  [REPIN] draft={i['draft_id']} rev: {i['current_rev']} -> {i['target_rev']}, pkg: -> {i['target_pkg_name']}")
            else:
                print(f"  [CURRENT] draft={i['draft_id']}")

        if not args.apply:
            print("\nDry run complete. Use --apply to execute changes.")
            return

        print("\nApplying re-pins...")
        applied = apply_plan(db, plan)
        print(f"Successfully repinned {len(applied)} drafts.")
    finally:
        db.close()


if __name__ == "__main__":
    main()