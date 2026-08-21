"""Seed the 3 additional insurance companies (Lonpac, Berjaya Sompo, Tune Protect).

Creates the company rows, links their existing company-logo assets, and seeds
their detection aliases. Idempotent: companies that already exist are skipped.

Usage:
    python commands/seed-companies.py           # Dry-run (reports proposed changes)
    python commands/seed-companies.py --apply   # Commits changes to the database
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
COMMANDS = ROOT / "commands"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(COMMANDS) not in sys.path:
    sys.path.insert(0, str(COMMANDS))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.tables import (
    BusinessAsset,
    CompanyAlias,
    InsuranceCompany,
    new_id,
)


def _load_canonical_alias_map() -> dict:
    """Load COMPANY_ALIASES_MAP from seed-demo.py (single source of truth).

    seed-demo.py cannot be imported by name (hyphenated filename), so load it
    by path via importlib.
    """
    seed_demo_path = COMMANDS / "seed-demo.py"
    spec = importlib.util.spec_from_file_location("seed_demo", seed_demo_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.COMPANY_ALIASES_MAP


COMPANY_ALIASES_MAP = _load_canonical_alias_map()

# Company seed data: slug, canonical name, logo asset key, detection phrases.
COMPANY_SEED_DATA = [
    {
        "slug": "lonpac",
        "name": "Lonpac Insurance",
        "logo_asset_key": "company-logo:lonpac",
        "detection_phrases": ["Lonpac", "Lonpac Insurance", "Lonpac Insurance Berhad"],
    },
    {
        "slug": "berjaya-sompo",
        "name": "Berjaya Sompo",
        "logo_asset_key": "company-logo:berjaya-sompo",
        "detection_phrases": ["Berjaya Sompo", "Berjaya Sompo Insurance", "Sompo"],
    },
    {
        "slug": "tune-protect",
        "name": "Tune Protect",
        "logo_asset_key": "company-logo:tune-protect",
        "detection_phrases": ["Tune Protect", "Tune Insurance", "Motor Easy"],
    },
]


def _normalize_alias(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def seed_companies(db, dry_run: bool) -> list[str]:
    logs = []
    assets_by_key = {
        a.asset_key: a
        for a in db.scalars(select(BusinessAsset).where(BusinessAsset.asset_kind == "company_logo")).all()
    }

    for data in COMPANY_SEED_DATA:
        slug = data["slug"]
        company = db.scalar(select(InsuranceCompany).where(InsuranceCompany.slug == slug))
        if company is not None:
            logs.append(f"Company '{data['name']}' (slug={slug}) already exists, skipping.")
            continue

        asset = assets_by_key.get(data["logo_asset_key"])
        company = InsuranceCompany(
            id=new_id(),
            slug=slug,
            name=data["name"],
            category="Motor",
            source_template_category="Other / Unknown",
            logo_asset_id=asset.id if asset else None,
            detection_phrases=data["detection_phrases"],
            status="active",
            revision=1,
        )
        if not dry_run:
            db.add(company)
            db.flush()
        logs.append(
            f"Created company '{data['name']}' (slug={slug}) with logo "
            f"{'linked' if asset else 'MISSING (no asset found)'}."
        )

        # Seed detection aliases from the canonical alias map.
        for raw_alias in COMPANY_ALIASES_MAP.get(slug, []):
            norm = _normalize_alias(raw_alias)
            existing = db.scalar(select(CompanyAlias).where(CompanyAlias.normalized_alias == norm))
            if existing is not None:
                continue
            alias = CompanyAlias(
                id=new_id(),
                company_id=company.id,
                alias=raw_alias,
                normalized_alias=norm,
                alias_kind="detection",
                status="active",
            )
            if not dry_run:
                db.add(alias)
            logs.append(f"  alias '{raw_alias}' -> {data['name']}")

    if not dry_run:
        db.flush()
    return logs


def main():
    parser = argparse.ArgumentParser(description="Seed the 3 additional insurance companies.")
    parser.add_argument("--apply", action="store_true", help="Apply changes to the database (default is dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="Perform a trial run with no changes committed (default)")
    args = parser.parse_args()

    dry_run = not args.apply
    mode_str = "DRY-RUN" if dry_run else "APPLY"
    print(f"=== Starting seed-companies.py [{mode_str}] ===")

    with SessionLocal() as db:
        try:
            logs = seed_companies(db, dry_run=dry_run)
            for log in logs:
                print(f"[COMPANY] {log}")
            if dry_run:
                print("\n[DRY-RUN COMPLETE] No database changes committed. Run with --apply to commit.")
            else:
                db.commit()
                print("\n[APPLY COMPLETE] Database changes successfully committed.")
        except Exception as e:
            db.rollback()
            print(f"\n[ERROR in seed-companies]: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()
