"""Plan or apply the non-destructive v7 compatibility backfill."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import SessionLocal
from app.models.tables import GeneratedPdfVersion, InsuranceCompany, OurSpecial, OutputTemplateConfig, QuotationDraft
from app.services.v7_backfill import apply_backfill_plan, build_backfill_plan, report_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or apply the v7 compatibility backfill plan.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Build the report without database changes (default).")
    mode.add_argument("--apply", action="store_true", help="Apply only the idempotent compatibility inserts in the report.")
    parser.add_argument("--report-path", type=Path, default=Path(".qc-tmp/backfill-report.json"))
    args = parser.parse_args()
    destination = report_path(ROOT, args.report_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    with SessionLocal() as db:
        plan = build_backfill_plan(
            companies=list(db.scalars(select(InsuranceCompany).order_by(InsuranceCompany.id)).all()),
            specials=list(
                db.scalars(select(OurSpecial).options(selectinload(OurSpecial.variants)).order_by(OurSpecial.id)).all()
            ),
            templates=list(db.scalars(select(OutputTemplateConfig).order_by(OutputTemplateConfig.id)).all()),
            legacy_draft_ids=list(db.scalars(select(QuotationDraft.id).order_by(QuotationDraft.id)).all()),
            legacy_version_ids=list(db.scalars(select(GeneratedPdfVersion.id).order_by(GeneratedPdfVersion.id)).all()),
        )
        result = None
        if args.apply:
            result = apply_backfill_plan(db, plan)

    report = {**plan, "requested_mode": "apply" if args.apply else "dry_run", "apply_result": result}
    destination.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(f"Wrote v7 backfill report: {destination}")
    print(json.dumps(report["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
