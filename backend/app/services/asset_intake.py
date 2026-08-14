"""Technical validation and deterministic manifest generation for v7 images."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from PIL import Image, UnidentifiedImageError


class AssetValidationError(ValueError):
    pass


FORMAT_EXTENSIONS = {
    "PNG": {".png"},
    "JPEG": {".jpg", ".jpeg"},
    "WEBP": {".webp"},
}

COMPANY_FILES = {
    "AmAssurance logo.webp": ("amassurance", "AmAssurance"),
    "berjaya sompo insurance logo.jpeg": ("berjaya-sompo", "Berjaya Sompo"),
    "etiqa insurance logo.png": ("etiqa", "Etiqa"),
    "Liberty Insurance logo.png": ("liberty", "Liberty Insurance"),
    "Lonpac Insurance logo.png": ("lonpac", "Lonpac Insurance"),
    "QBE Insurance logo.jpg": ("qbe", "QBE Insurance"),
    "Takaful Malaysia logo.png": ("takaful-malaysia", "Takaful Malaysia"),
    "tune portect logo.png": ("tune-protect", "Tune Protect"),
}


def slugify(value: str) -> str:
    value = value.replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def benefit_identity(filename: str) -> tuple[str, str]:
    label = Path(filename).stem
    label = re.sub(r"\s+or\s+", " / ", label, flags=re.IGNORECASE)
    label = re.sub(r"\s{2,}", " / ", label).strip()
    label = re.sub(r"(?:\s*/\s*){2,}", " / ", label)
    key = slugify(Path(filename).stem)
    return key, label


def validate_image_file(path: Path, *, max_bytes: int, max_pixels: int) -> dict:
    data = path.read_bytes()
    return validate_image_bytes(data, path.name, max_bytes=max_bytes, max_pixels=max_pixels)


def validate_image_bytes(data: bytes, filename: str, *, max_bytes: int, max_pixels: int) -> dict:
    size = len(data)
    if size <= 0 or size > max_bytes:
        raise AssetValidationError(f"Image byte size is outside the allowed limit: {filename}")
    try:
        with Image.open(io.BytesIO(data)) as opened:
            image_format = opened.format
            opened.verify()
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            mode = image.mode
            has_transparency = "A" in image.getbands() or "transparency" in image.info
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise AssetValidationError(f"Image could not decode safely: {filename}") from exc
    if image_format not in FORMAT_EXTENSIONS:
        raise AssetValidationError(f"Unsupported image format: {image_format}")
    suffix = Path(filename).suffix.lower()
    if suffix not in FORMAT_EXTENSIONS[image_format]:
        raise AssetValidationError(f"Image extension does not match its real {image_format} signature: {filename}")
    if width <= 0 or height <= 0 or width * height > max_pixels:
        raise AssetValidationError(f"Image pixel count exceeds the allowed limit: {filename}")
    return {
        "format": image_format,
        "content_type": Image.MIME[image_format],
        "width_px": width,
        "height_px": height,
        "mode": mode,
        "has_transparency": has_transparency,
        "size_bytes": size,
        "content_hash": sha256(data).hexdigest(),
    }


def build_source_manifest(asset_root: Path) -> dict:
    project_root = asset_root.resolve().parent
    entries: list[dict] = []
    errors: list[dict] = []
    for folder, kind in ((asset_root / "benefits", "benefit_art"), (asset_root / "Company logos", "company_logo")):
        for path in sorted(folder.iterdir(), key=lambda item: item.name.casefold()):
            if not path.is_file():
                continue
            relative = path.resolve().relative_to(project_root).as_posix()
            try:
                technical = validate_image_file(path, max_bytes=10 * 1024 * 1024, max_pixels=32_000_000)
            except AssetValidationError as exc:
                errors.append({"source_path": relative, "error": str(exc)})
                continue
            if kind == "company_logo":
                brand_key, display_name = COMPANY_FILES.get(
                    path.name,
                    (slugify(re.sub(r"\blogo\b|\binsurance\b", "", path.stem, flags=re.IGNORECASE)), path.stem),
                )
                identity = {
                    "asset_key": f"company-logo:{brand_key}",
                    "brand_key": brand_key,
                    "display_name": display_name,
                    "catalog_assignment": "company_logo",
                }
            else:
                concept_key, display_name = benefit_identity(path.name)
                identity = {
                    "asset_key": f"benefit-art:{concept_key}",
                    "suggested_concept_key": concept_key,
                    "display_name": display_name,
                    "catalog_assignment": "unassigned",
                }
            entries.append(
                {
                    "source_path": relative,
                    "source_filename": path.name,
                    "asset_kind": kind,
                    **identity,
                    **technical,
                    "validation_status": "valid",
                    "derivative_policy": "aspect_preserving_non_cropped",
                }
            )
    hashes: dict[str, int] = {}
    for entry in entries:
        hashes[entry["content_hash"]] = hashes.get(entry["content_hash"], 0) + 1
    duplicate_count = sum(count - 1 for count in hashes.values() if count > 1)
    return {
        "schema_version": 1,
        "source_policy": "filename_mapping_with_technical_validation",
        "assets": entries,
        "errors": errors,
        "summary": {
            "benefit_art_count": sum(item["asset_kind"] == "benefit_art" for item in entries),
            "company_logo_count": sum(item["asset_kind"] == "company_logo" for item in entries),
            "error_count": len(errors),
            "duplicate_content_count": duplicate_count,
        },
    }


@dataclass(frozen=True)
class Derivative:
    data: bytes
    content_type: str
    width_px: int
    height_px: int
    content_hash: str


def create_derivative(data: bytes, *, max_width: int, max_height: int, quality: int = 88) -> Derivative:
    if max_width <= 0 or max_height <= 0:
        raise AssetValidationError("Derivative bounds must be positive.")
    try:
        with Image.open(io.BytesIO(data)) as source:
            source.load()
            image = source.copy()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise AssetValidationError("Source image could not decode safely.") from exc
    image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
    transparent = "A" in image.getbands() or "transparency" in image.info
    output = io.BytesIO()
    if transparent:
        if image.mode != "RGBA":
            image = image.convert("RGBA")
        image.save(output, format="PNG", compress_level=6)
        content_type = "image/png"
    else:
        if image.mode != "RGB":
            image = image.convert("RGB")
        image.save(output, format="WEBP", quality=quality, method=4)
        content_type = "image/webp"
    result = output.getvalue()
    return Derivative(
        data=result,
        content_type=content_type,
        width_px=image.width,
        height_px=image.height,
        content_hash=sha256(result).hexdigest(),
    )
