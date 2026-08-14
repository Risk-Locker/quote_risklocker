"""Write a read-only reference inventory before legacy asset cleanup."""

from __future__ import annotations

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
from app.services.template_assets import asset_root


def main() -> int:
    destination = ROOT / ".qc-tmp" / "legacy-asset-reference-report.json"
    local_paths = [path for path in asset_root().iterdir() if path.is_file()] if asset_root().exists() else []
    with SessionLocal() as db:
        report = build_reference_inventory(
            local_paths,
            db.scalars(select(TemplateAsset)).all(),
            collect_database_surfaces(db),
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"Wrote {destination.relative_to(ROOT)}: "
        f"{len(report['local_referenced'])} referenced, "
        f"{len(report['local_unreferenced'])} unreferenced local files."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
