"""Conservative reference checks for legacy local and uploaded assets."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.legacy_asset_inventory import build_reference_inventory


def test_inventory_separates_referenced_local_assets_and_uploaded_records(tmp_path: Path):
    local = tmp_path / "template_assets"
    local.mkdir()
    referenced = local / "Used Logo.png"
    unreferenced = local / "Unused.png"
    referenced.write_bytes(b"used")
    unreferenced.write_bytes(b"unused")

    from app.services.template_assets import _local_asset_id

    used_id = _local_asset_id(referenced)
    uploaded = [
        SimpleNamespace(id="asset-used", label="Used", filename="used.png", status="active", storage_path="used"),
        SimpleNamespace(id="sticker-test", label="Sticker test", filename="sticker.png", status="active", storage_path="sticker"),
    ]
    surfaces = [
        {"entity": "template", "id": "template-1", "payload": {"assetId": used_id}},
        {"entity": "version", "id": "version-1", "payload": {"assets": ["asset-used"]}},
    ]

    report = build_reference_inventory([referenced, unreferenced], uploaded, surfaces)

    assert [item["filename"] for item in report["local_referenced"]] == ["Used Logo.png"]
    assert [item["filename"] for item in report["local_unreferenced"]] == ["Unused.png"]
    uploaded_by_id = {item["id"]: item for item in report["uploaded_records"]}
    assert uploaded_by_id["asset-used"]["references"] == [{"entity": "version", "id": "version-1"}]
    assert uploaded_by_id["sticker-test"]["references"] == []
