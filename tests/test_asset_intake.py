"""Owner-supplied v7 asset validation, identity, and derivative contracts."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.asset_intake import (
    AssetValidationError,
    build_source_manifest,
    create_derivative,
    validate_image_file,
    validate_image_bytes,
)


def test_owner_source_set_is_valid_dynamic_data_and_manifest_is_stable():
    manifest = build_source_manifest(ROOT / "assets")

    assert manifest["schema_version"] == 1
    assert manifest["summary"] == {
        "benefit_art_count": 35,
        "company_logo_count": 8,
        "error_count": 0,
        "duplicate_content_count": 0,
    }
    entries = manifest["assets"]
    assert len(entries) == 43
    assert all(entry["validation_status"] == "valid" for entry in entries)
    assert all(entry["width_px"] > 0 and entry["height_px"] > 0 for entry in entries)
    assert len({entry["content_hash"] for entry in entries}) == 43
    assert all(entry["source_path"].startswith(("assets/benefits/", "assets/Company logos/")) for entry in entries)

    tune = next(entry for entry in entries if entry["source_filename"] == "tune portect logo.png")
    assert tune["asset_key"] == "company-logo:tune-protect"
    assert tune["brand_key"] == "tune-protect"
    assert tune["display_name"] == "Tune Protect"

    artwork = next(entry for entry in entries if entry["source_filename"] == "Special Perils.png")
    assert artwork["asset_key"] == "benefit-art:special-perils"
    assert artwork["suggested_concept_key"] == "special-perils"
    assert artwork["catalog_assignment"] == "unassigned"

    settlement = next(
        entry
        for entry in entries
        if entry["source_filename"] == "Agreed Value  or Market Value Settlement.png"
    )
    assert settlement["display_name"] == "Agreed Value / Market Value Settlement"


def test_tracked_manifest_matches_current_owner_source_set():
    expected = build_source_manifest(ROOT / "assets")
    tracked = json.loads((ROOT / "assets" / "v7-source-manifest.json").read_text(encoding="utf-8"))

    assert tracked == expected


def test_signature_mismatch_and_pixel_limit_are_rejected(tmp_path: Path):
    fake_png = tmp_path / "fake.png"
    fake_png.write_bytes(b"not an image")
    with pytest.raises(AssetValidationError, match="decode"):
        validate_image_file(fake_png, max_bytes=10_000, max_pixels=100_000)

    actual_png_wrong_extension = tmp_path / "image.jpg"
    Image.new("RGBA", (20, 20), (255, 0, 0, 127)).save(actual_png_wrong_extension, format="PNG")
    with pytest.raises(AssetValidationError, match="extension"):
        validate_image_file(actual_png_wrong_extension, max_bytes=10_000, max_pixels=100_000)

    oversized = tmp_path / "large.png"
    Image.new("RGB", (20, 20), "white").save(oversized)
    with pytest.raises(AssetValidationError, match="pixel"):
        validate_image_file(oversized, max_bytes=10_000, max_pixels=399)


def test_derivative_preserves_aspect_ratio_without_cropping():
    source = io.BytesIO()
    Image.new("RGBA", (400, 200), (20, 30, 40, 128)).save(source, format="PNG")

    derivative = create_derivative(source.getvalue(), max_width=100, max_height=100)

    with Image.open(io.BytesIO(derivative.data)) as image:
        assert image.size == (100, 50)
        assert image.format == "PNG"
        assert "A" in image.getbands()
    assert derivative.width_px == 100
    assert derivative.height_px == 50
    assert derivative.content_type == "image/png"


def test_opaque_derivative_uses_webp_and_never_enlarges():
    source = io.BytesIO()
    Image.new("RGB", (50, 20), "white").save(source, format="JPEG")

    derivative = create_derivative(source.getvalue(), max_width=100, max_height=100)

    with Image.open(io.BytesIO(derivative.data)) as image:
        assert image.size == (50, 20)
        assert image.format == "WEBP"
    assert derivative.content_type == "image/webp"


def test_uploaded_image_bytes_receive_the_same_signature_validation():
    source = io.BytesIO()
    Image.new("RGB", (32, 20), "white").save(source, format="PNG")

    result = validate_image_bytes(source.getvalue(), "benefit.png", max_bytes=10_000, max_pixels=1_000)

    assert result["format"] == "PNG"
    assert result["width_px"] == 32
    with pytest.raises(AssetValidationError, match="extension"):
        validate_image_bytes(source.getvalue(), "benefit.jpg", max_bytes=10_000, max_pixels=1_000)
