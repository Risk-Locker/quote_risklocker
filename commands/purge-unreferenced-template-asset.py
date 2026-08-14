"""Purge one legacy uploaded asset only after a locked reference recheck."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import select


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.db.session import SessionLocal
from app.models.tables import TemplateAsset
from app.services.legacy_asset_inventory import build_reference_inventory, collect_database_surfaces
from app.storage.supabase import SupabaseStorage


def main() -> int:
    parser = argparse.ArgumentParser(description="Reference-check and purge one legacy uploaded template asset.")
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    with SessionLocal() as db:
        record = db.scalar(select(TemplateAsset).where(TemplateAsset.id == args.asset_id).with_for_update())
        if record is None:
            parser.error("Asset record does not exist.")
        report = build_reference_inventory([], [record], collect_database_surfaces(db))["uploaded_records"][0]
        if report["references"]:
            parser.error("Asset still has references and cannot be purged.")
        report["mode"] = "apply" if args.apply else "dry_run"
        if args.apply:
            SupabaseStorage().delete_pdf(record.storage_path)
            db.delete(record)
            db.commit()
            report["purged"] = True
        else:
            report["purged"] = False

    destination = ROOT / ".qc-tmp" / f"purge-template-asset-{args.asset_id}.json"
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {destination.relative_to(ROOT)} ({report['mode']}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
