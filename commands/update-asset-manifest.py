"""Regenerate the tracked v7 owner-asset source manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.asset_intake import build_source_manifest


def main() -> None:
    destination = ROOT / "assets" / "v7-source-manifest.json"
    manifest = build_source_manifest(ROOT / "assets")
    destination.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {destination.relative_to(ROOT)} with {len(manifest['assets'])} validated assets.")


if __name__ == "__main__":
    main()
