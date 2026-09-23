"""Benefit Card Preset service for persistent template styling and default selection."""

from __future__ import annotations

import time
from typing import Any
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.errors import AppError
from app.models.tables import BenefitCardPreset, utcnow

FACTORY_PRESETS: dict[str, dict[str, Any]] = {
    "masonry-flow": {
        "name": "Masonry Flow (Dynamic)",
        "short_name": "Masonry Flow",
        "description": "3-column fluid masonry, natural card heights, zero wasted space",
        "is_default": True,
        "is_custom": False,
        "config": {
            "shape": "rounded",
            "layout": "masonry",
            "borderWidth": 1,
            "borderStyle": "solid",
            "elevation": "lift",
            "uniformHeight": 0,
            "iconSize": 44,
            "imageFit": "contain",
            "iconPadShape": "box",
            "titleSize": 10.5,
            "titleWeight": "bold",
            "titleColor": "#0f172a",
            "textWrap": "wrap",
            "valueBadgeStyle": "red",
            "coverageSize": 11,
            "coverageColor": "#10b981",
            "descSize": 9,
            "descColor": "#64748b",
            "costSize": 9,
            "costColor": "#b91c1c",
            "costBgColor": "#fee2e2",
            "showDescription": True,
            "showCoverage": True,
            "showCost": True,
            "bgColor": "#ffffff",
            "borderColor": "#e2e8f0",
            "textColor": "#0f172a",
            "accentColor": "#dc2626",
            "columns": 3,
            "layoutMode": "masonry",
            "textDensity": "compact",
            "cardStyle": "standard",
            "rowHeight": 66,
        },
    },
    "compact-minimal": {
        "name": "Compact Minimalist (1-Page Fit)",
        "short_name": "Compact Minimal",
        "description": "Ultra-compact single-line rows, fits 35+ items cleanly on 1 page",
        "is_default": False,
        "is_custom": False,
        "config": {
            "shape": "square",
            "layout": "compact",
            "borderWidth": 1,
            "borderStyle": "solid",
            "elevation": "flat",
            "uniformHeight": 38,
            "iconSize": 18,
            "imageFit": "contain",
            "iconPadShape": "none",
            "titleSize": 9.5,
            "titleWeight": "semibold",
            "titleColor": "#0f172a",
            "textWrap": "truncate",
            "valueBadgeStyle": "subtle",
            "coverageSize": 9.5,
            "coverageColor": "#10b981",
            "descSize": 8.5,
            "descColor": "#64748b",
            "costSize": 8.5,
            "costColor": "#475569",
            "costBgColor": "#f1f5f9",
            "showDescription": False,
            "showCoverage": True,
            "showCost": True,
            "bgColor": "#ffffff",
            "borderColor": "#f1f5f9",
            "textColor": "#0f172a",
            "accentColor": "#dc2626",
            "columns": 3,
            "layoutMode": "masonry",
            "textDensity": "compact",
            "cardStyle": "minimal",
            "rowHeight": 40,
        },
    },
    "signature-2col": {
        "name": "Signature 2-Column (Classic)",
        "short_name": "Signature 2-Col",
        "description": "Classic 2-column balanced grid with prominent card titles",
        "is_default": False,
        "is_custom": False,
        "config": {
            "shape": "rounded",
            "layout": "merged-2col",
            "borderWidth": 1,
            "borderStyle": "solid",
            "elevation": "shadow",
            "uniformHeight": 0,
            "iconSize": 24,
            "imageFit": "contain",
            "iconPadShape": "box",
            "titleSize": 11,
            "titleWeight": "bold",
            "titleColor": "#0f172a",
            "textWrap": "wrap",
            "valueBadgeStyle": "red",
            "coverageSize": 12,
            "coverageColor": "#10b981",
            "descSize": 9.5,
            "descColor": "#64748b",
            "costSize": 9.5,
            "costColor": "#b91c1c",
            "costBgColor": "#fee2e2",
            "showDescription": True,
            "showCoverage": True,
            "showCost": True,
            "bgColor": "#ffffff",
            "borderColor": "#e2e8f0",
            "textColor": "#0f172a",
            "accentColor": "#dc2626",
            "columns": 2,
            "layoutMode": "normal",
            "textDensity": "normal",
            "cardStyle": "standard",
            "rowHeight": 68,
        },
    },
    "elevated-3d": {
        "name": "Elevated 3D Card (Shadow Lift)",
        "short_name": "Elevated 3D",
        "description": "Soft cards with modern 3D elevation, subtle drop shadows",
        "is_default": False,
        "is_custom": False,
        "config": {
            "shape": "soft",
            "layout": "masonry",
            "borderWidth": 1,
            "borderStyle": "solid",
            "elevation": "lift",
            "uniformHeight": 0,
            "iconSize": 22,
            "imageFit": "contain",
            "iconPadShape": "box",
            "titleSize": 10.5,
            "titleWeight": "bold",
            "titleColor": "#0f172a",
            "textWrap": "wrap",
            "valueBadgeStyle": "red",
            "coverageSize": 11,
            "coverageColor": "#10b981",
            "descSize": 9,
            "descColor": "#64748b",
            "costSize": 9,
            "costColor": "#b91c1c",
            "costBgColor": "#fee2e2",
            "showDescription": True,
            "showCoverage": True,
            "showCost": True,
            "bgColor": "#ffffff",
            "borderColor": "#e2e8f0",
            "textColor": "#0f172a",
            "accentColor": "#dc2626",
            "columns": 3,
            "layoutMode": "masonry",
            "textDensity": "compact",
            "cardStyle": "soft",
            "rowHeight": 68,
        },
    },
    "grid-tile": {
        "name": "Grid Tile (Modern Outlined)",
        "short_name": "Grid Tile",
        "description": "Clean outlined cards with circular icon pads and pill values",
        "is_default": False,
        "is_custom": False,
        "config": {
            "shape": "rounded",
            "layout": "masonry",
            "borderWidth": 1,
            "borderStyle": "solid",
            "elevation": "flat",
            "uniformHeight": 0,
            "iconSize": 22,
            "imageFit": "contain",
            "iconPadShape": "circle",
            "titleSize": 10,
            "titleWeight": "bold",
            "titleColor": "#0f172a",
            "textWrap": "wrap",
            "valueBadgeStyle": "pill",
            "coverageSize": 10.5,
            "coverageColor": "#0f172a",
            "descSize": 9,
            "descColor": "#64748b",
            "costSize": 9,
            "costColor": "#0f172a",
            "costBgColor": "#e2e8f0",
            "showDescription": True,
            "showCoverage": True,
            "showCost": True,
            "bgColor": "#f8fafc",
            "borderColor": "#cbd5e1",
            "textColor": "#0f172a",
            "accentColor": "#dc2626",
            "columns": 3,
            "layoutMode": "masonry",
            "textDensity": "compact",
            "cardStyle": "outlined",
            "rowHeight": 68,
        },
    },
    "dark-signature": {
        "name": "Dark Luxury Executive",
        "short_name": "Dark Luxury",
        "description": "Executive dark slate cards with high-contrast amber highlights",
        "is_default": False,
        "is_custom": False,
        "config": {
            "shape": "rounded",
            "layout": "masonry",
            "borderWidth": 1,
            "borderStyle": "solid",
            "elevation": "shadow",
            "uniformHeight": 0,
            "iconSize": 20,
            "imageFit": "contain",
            "iconPadShape": "box",
            "titleSize": 10.5,
            "titleWeight": "bold",
            "titleColor": "#ffffff",
            "textWrap": "wrap",
            "valueBadgeStyle": "red",
            "coverageSize": 11,
            "coverageColor": "#34d399",
            "descSize": 9,
            "descColor": "#94a3b8",
            "costSize": 9,
            "costColor": "#fca5a5",
            "costBgColor": "#450a0a",
            "showDescription": True,
            "showCoverage": True,
            "showCost": True,
            "bgColor": "#0f172a",
            "borderColor": "#334155",
            "textColor": "#ffffff",
            "accentColor": "#f59e0b",
            "columns": 3,
            "layoutMode": "masonry",
            "textDensity": "compact",
            "cardStyle": "standard",
            "rowHeight": 66,
        },
    },
    "dynamic-masonry": {
        "name": "Dynamic Expandable Masonry",
        "short_name": "Dynamic Masonry",
        "description": "Auto-expanding masonry grid that dynamically fits benefit boxes of varying heights",
        "is_default": False,
        "is_custom": False,
        "config": {
            "shape": "rounded",
            "layout": "masonry",
            "borderWidth": 1,
            "borderStyle": "dashed",
            "elevation": "flat",
            "uniformHeight": 0,
            "iconSize": 22,
            "imageFit": "contain",
            "iconPadShape": "circle",
            "titleSize": 11,
            "titleWeight": "semibold",
            "titleColor": "#0f172a",
            "textWrap": "wrap",
            "valueBadgeStyle": "subtle",
            "coverageSize": 11.5,
            "coverageColor": "#10b981",
            "descSize": 9.5,
            "descColor": "#64748b",
            "costSize": 9.5,
            "costColor": "#475569",
            "costBgColor": "#f1f5f9",
            "showDescription": True,
            "showCoverage": True,
            "showCost": True,
            "bgColor": "#ffffff",
            "borderColor": "#e2e8f0",
            "textColor": "#0f172a",
            "accentColor": "#dc2626",
            "columns": 2,
            "layoutMode": "masonry",
            "textDensity": "comfortable",
            "cardStyle": "soft",
            "rowHeight": 75,
        },
    },
}


def ensure_default_presets(db: Session) -> None:
    """Ensure system presets exist in the database with factory definitions."""
    existing_ids = set(db.scalars(select(BenefitCardPreset.id)).all())
    for pid, data in FACTORY_PRESETS.items():
        if pid not in existing_ids:
            preset = BenefitCardPreset(
                id=pid,
                name=data["name"],
                short_name=data["short_name"],
                description=data["description"],
                is_default=data["is_default"],
                is_custom=data["is_custom"],
                config=dict(data["config"]),
            )
            db.add(preset)
    db.flush()


def list_benefit_card_presets(db: Session) -> list[BenefitCardPreset]:
    """Return all benefit card presets, sorted with default first, then system, then custom."""
    ensure_default_presets(db)
    presets = list(db.scalars(select(BenefitCardPreset)).all())
    # Sort: is_default first (descending), then is_custom ascending, then name ascending
    presets.sort(key=lambda p: (not p.is_default, p.is_custom, p.name))
    return presets


def get_benefit_card_preset(db: Session, preset_id: str) -> BenefitCardPreset:
    """Retrieve a single preset by ID."""
    preset = db.get(BenefitCardPreset, preset_id)
    if not preset:
        raise AppError(f"Benefit card preset '{preset_id}' not found.", status_code=404)
    return preset


def save_benefit_card_preset(
    db: Session,
    preset_id: str,
    payload: dict[str, Any],
) -> BenefitCardPreset:
    """Update styling and metadata for a benefit card preset."""
    preset = get_benefit_card_preset(db, preset_id)

    if "name" in payload and payload["name"]:
        preset.name = str(payload["name"]).strip()
    if "short_name" in payload and payload["short_name"]:
        preset.short_name = str(payload["short_name"]).strip()
    if "description" in payload and payload["description"] is not None:
        preset.description = str(payload["description"]).strip()

    # Merge config: start with existing preset config, apply nested payload['config'] if present,
    # and then allow top-level payload styling fields to take highest precedence.
    current_config = dict(preset.config or {})
    if isinstance(payload.get("config"), dict):
        current_config.update(payload["config"])

    # Extract all styling fields into config
    style_keys = [
        "shape",
        "layout",
        "borderWidth",
        "borderStyle",
        "elevation",
        "uniformHeight",
        "iconSize",
        "imageFit",
        "iconPadShape",
        "titleSize",
        "titleWeight",
        "titleColor",
        "textWrap",
        "valueBadgeStyle",
        "coverageSize",
        "coverageColor",
        "descSize",
        "descWeight",
        "descColor",
        "costSize",
        "costColor",
        "costBgColor",
        "showDescription",
        "showCoverage",
        "showCost",
        "bgColor",
        "borderColor",
        "textColor",
        "accentColor",
        "columns",
        "layoutMode",
        "textDensity",
        "cardStyle",
        "rowHeight",
        "sectionVisibility",
    ]

    for key in style_keys:
        if key in payload:
            current_config[key] = payload[key]

    preset.config = current_config
    flag_modified(preset, "config")
    preset.updated_at = utcnow()
    db.commit()
    db.refresh(preset)
    return preset


def create_custom_benefit_card_preset(
    db: Session,
    payload: dict[str, Any],
) -> BenefitCardPreset:
    """Create a new custom benefit card preset."""
    name = str(payload.get("name", "")).strip()
    if not name:
        raise AppError("Preset name is required.", status_code=422)

    preset_id = str(payload.get("id", "")).strip() or f"custom-{int(time.time() * 1000)}"
    if db.get(BenefitCardPreset, preset_id):
        raise AppError(f"Preset with id '{preset_id}' already exists.", status_code=409)

    short_name = str(payload.get("shortName") or payload.get("short_name") or name[:16]).strip()
    description = str(payload.get("description", "")).strip()

    # Extract styling into config: nested config first, then top-level fields
    config: dict[str, Any] = {}
    if isinstance(payload.get("config"), dict):
        config.update(payload["config"])

    style_keys = [
        "shape", "layout", "borderWidth", "borderStyle", "elevation", "uniformHeight",
        "iconSize", "imageFit", "iconPadShape", "titleSize", "titleWeight", "titleColor",
        "textWrap", "valueBadgeStyle", "coverageSize", "coverageColor", "descSize",
        "descWeight", "descColor", "costSize", "costColor", "costBgColor",
        "showDescription", "showCoverage", "showCost", "bgColor", "borderColor",
        "textColor", "accentColor", "columns", "layoutMode", "textDensity",
        "cardStyle", "rowHeight", "sectionVisibility",
    ]
    for key in style_keys:
        if key in payload:
            config[key] = payload[key]

    preset = BenefitCardPreset(
        id=preset_id,
        name=name,
        short_name=short_name,
        description=description,
        is_default=False,
        is_custom=True,
        config=config,
    )
    db.add(preset)
    db.commit()
    db.refresh(preset)
    return preset


def set_default_benefit_card_preset(db: Session, preset_id: str) -> BenefitCardPreset:
    """Atomically set target preset as the global default."""
    target = get_benefit_card_preset(db, preset_id)

    # Invalidate all existing defaults
    db.execute(
        update(BenefitCardPreset)
        .where(BenefitCardPreset.is_default.is_(True))
        .values(is_default=False)
    )

    target.is_default = True
    target.updated_at = utcnow()
    db.commit()
    db.refresh(target)
    return target


def reset_benefit_card_preset(db: Session, preset_id: str) -> BenefitCardPreset:
    """Reset a system preset to factory default configuration."""
    preset = get_benefit_card_preset(db, preset_id)
    if preset.is_custom:
        raise AppError("Custom presets cannot be reset to factory defaults.", status_code=400)

    factory = FACTORY_PRESETS.get(preset_id)
    if not factory:
        raise AppError(f"Factory preset definition not found for '{preset_id}'.", status_code=404)

    preset.name = factory["name"]
    preset.short_name = factory["short_name"]
    preset.description = factory["description"]
    preset.config = dict(factory["config"])
    flag_modified(preset, "config")
    preset.updated_at = utcnow()
    db.commit()
    db.refresh(preset)
    return preset


def delete_custom_benefit_card_preset(db: Session, preset_id: str) -> None:
    """Delete a custom preset."""
    preset = get_benefit_card_preset(db, preset_id)
    if not preset.is_custom:
        raise AppError("System presets cannot be deleted.", status_code=400)
    if preset.is_default:
        raise AppError("Cannot delete the active default preset. Select another default first.", status_code=400)

    db.delete(preset)
    db.commit()
