"""Idempotently seed and publish Bilingual Agency Motor v4 canonical master templates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import select


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.session import SessionLocal
from app.models.tables import User
from app.services.master_template_service import ensure_master_templates


TARGET_KEYS = [
    "agency_bilingual_v4",
    "agency_bilingual_v4_no_extras",
    "agency_bilingual_v4_lump_sum",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish Bilingual Agency Motor v4 canonical masters.")
    parser.add_argument("--apply", action="store_true", help="Create and publish missing masters. Default is dry-run.")
    parser.add_argument("--force", action="store_true", help="Force update published masters.")
    parser.add_argument("--report-path", type=Path, default=Path(".qc-tmp/v4-master-template-report.json"))
    args = parser.parse_args()
    destination = (ROOT / args.report_path).resolve() if not args.report_path.is_absolute() else args.report_path.resolve()
    try:
        destination.relative_to((ROOT / ".qc-tmp").resolve())
    except ValueError:
        parser.error("--report-path must be inside .qc-tmp")

    with SessionLocal() as db:
        actor = db.scalar(select(User).where(User.role == "super_admin", User.status == "active").order_by(User.created_at))
        if actor is None:
            actor = db.scalar(select(User).where(User.status == "active").order_by(User.created_at))
        if actor is None:
            parser.error("An active user must exist before masters can be published.")
        report = ensure_master_templates(
            db,
            actor,
            apply=args.apply,
            force=args.force or args.apply,
            target_keys=TARGET_KEYS,
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {destination.relative_to(ROOT)} ({'apply' if args.apply else 'dry-run'}). Report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
