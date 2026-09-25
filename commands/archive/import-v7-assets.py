"""Dry-run or apply the tracked owner-asset intake manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.asset_catalog_intake import apply_asset_manifest, build_asset_import_plan
from app.storage.supabase import SupabaseStorage


def _safe_plan_summary(plan: dict) -> dict:
    return {
        "schema_version": plan["schema_version"],
        "asset_count": len(plan["assets"]),
        "company_count": len(plan["companies"]),
        "errors": plan["errors"],
        "assets": [
            {
                "asset_key": item["asset_key"],
                "asset_kind": item["asset_kind"],
                "content_hash": item["content_hash"],
                "original_storage_path": item["original_storage_path"],
                "status": item["status"],
            }
            for item in plan["assets"]
        ],
        "companies": plan["companies"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate/register the tracked v7 company logos and benefit artwork.")
    parser.add_argument("--apply", action="store_true", help="Upload/register after a successful dry-run review.")
    parser.add_argument("--report-path", type=Path, default=Path(".qc-tmp/v7-asset-import-report.json"))
    args = parser.parse_args()
    report_path = (ROOT / args.report_path).resolve() if not args.report_path.is_absolute() else args.report_path.resolve()
    qc_root = (ROOT / ".qc-tmp").resolve()
    try:
        report_path.relative_to(qc_root)
    except ValueError:
        parser.error("--report-path must be inside .qc-tmp")

    manifest = json.loads((ROOT / "assets/v7-source-manifest.json").read_text(encoding="utf-8"))
    plan = build_asset_import_plan(ROOT, manifest)
    report: dict = {"mode": "apply" if args.apply else "dry_run", "plan": _safe_plan_summary(plan)}
    if args.apply:
        if plan["errors"]:
            parser.error("Asset validation errors must be resolved before --apply")
        settings = get_settings()
        storage = SupabaseStorage(settings)
        storage.ensure_bucket()
        with SessionLocal() as db:
            report["result"] = apply_asset_manifest(db, plan, storage=storage)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {report_path.relative_to(ROOT)} ({report['mode']}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
