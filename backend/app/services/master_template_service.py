"""Canonical insurer-independent v7 master documents and idempotent publication."""

from __future__ import annotations

from copy import deepcopy

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.models.tables import OutputTemplateConfig, TemplateRevision, new_id
from app.services.template_revision_service import new_v7_template_config, publish_template_revision, validate_template_config


RED = "#E51C2A"
INK = "#171719"
MUTED = "#66666B"
BORDER = "#D9D9DE"


def _text(node_id: str, text: str, x: float, y: float, w: float, h: float, z: int, *, size: int = 14, weight: str = "600", color: str = INK, align: str = "left") -> dict:
    return {"id": node_id, "type": "text", "text": text, "x": x, "y": y, "w": w, "h": h, "z": z, "style": {"fontSize": size, "fontWeight": weight, "color": color, "textAlign": align}}


def _variable(node_id: str, variable_id: str, x: float, y: float, w: float, h: float, z: int, *, size: int = 14, weight: str = "700", color: str = INK, align: str = "left", prefix: str = "", suffix: str = "") -> dict:
    return {"id": node_id, "type": "variable", "variableId": variable_id, "prefix": prefix, "suffix": suffix, "x": x, "y": y, "w": w, "h": h, "z": z, "style": {"fontSize": size, "fontWeight": weight, "color": color, "textAlign": align}}


def _image(node_id: str, slot: str, x: float, y: float, w: float, h: float, z: int) -> dict:
    return {"id": node_id, "type": "image", "assetSlot": slot, "x": x, "y": y, "w": w, "h": h, "z": z, "style": {"borderWidth": 0}}


def _rectangle(node_id: str, x: float, y: float, w: float, h: float, z: int, *, background: str = "#FFFFFF", border: str = BORDER, radius: int = 0) -> dict:
    return {"id": node_id, "type": "rectangle", "x": x, "y": y, "w": w, "h": h, "z": z, "style": {"background": background, "borderWidth": 1 if border else 0, "borderColor": border or "transparent", "borderRadius": radius}}


def _line(node_id: str, x: float, y: float, w: float, z: int, *, color: str = RED, height: float = 2) -> dict:
    return {"id": node_id, "type": "line", "x": x, "y": y, "w": w, "h": height, "z": z, "style": {"color": color, "borderWidth": height}}


def _grid(node_id: str, kind: str, x: float, y: float, w: float, h: float, z: int, *, dense: bool = False) -> dict:
    return {
        "id": node_id, "type": "benefit-grid", "gridKind": kind, "x": x, "y": y, "w": w, "h": h, "z": z,
        "packing": {
            "strategy": "balanced", "alignment": "center", "aspectRatio": 1.45,
            "referenceWidth": 180, "referenceHeight": 124,
            "gapRatio": 0.035 if dense else 0.055, "paddingRatio": 0.012 if dense else 0.02, "staggerRatio": 0.5,
        },
        "cardStyle": "outlined" if dense else "standard", "textDensity": "compact" if dense else "normal", "emptyState": "hide",
    }


def _identity_header(*, compact: bool = False) -> list[dict]:
    top = 24 if compact else 30
    return [
        _image("risklocker_logo", "risklocker_logo", 32, top, 126, 44, 5),
        _image("insurer_logo", "insurer_logo", 624, top - 4, 138, 58, 5),
        _line("header_rule", 32, 92 if compact else 104, 730, 3, height=3),
        _text("document_title", "Motor Insurance Quotation", 32, 108 if compact else 122, 430, 38, 5, size=24 if compact else 27, weight="800"),
        _text("premium_label", "TOTAL PREMIUM", 522, 111 if compact else 125, 240, 18, 5, size=10, weight="800", color=MUTED, align="right"),
        _variable("premium_value", "total_amount", 500, 130 if compact else 146, 262, 42, 5, size=25 if compact else 29, weight="800", color=RED, align="right", prefix="RM "),
    ]


def _quote_summary(y: float, *, compact: bool = False) -> list[dict]:
    height = 86 if compact else 108
    return [
        _rectangle("summary_panel", 32, y, 730, height, 2, background="#F7F7F8", border="", radius=8),
        _text("customer_label", "CUSTOMER", 48, y + 14, 100, 16, 5, size=9, weight="800", color=MUTED),
        _variable("customer_value", "customer_name", 48, y + 34, 210, 24, 5, size=15, weight="700"),
        _text("vehicle_label", "VEHICLE", 284, y + 14, 100, 16, 5, size=9, weight="800", color=MUTED),
        _variable("vehicle_value", "car_model", 284, y + 34, 205, 24, 5, size=15, weight="700"),
        _text("registration_label", "REGISTRATION", 516, y + 14, 110, 16, 5, size=9, weight="800", color=MUTED),
        _variable("registration_value", "vehicle_no", 516, y + 34, 210, 24, 5, size=15, weight="700"),
        _variable("coverage_value", "coverage_type", 48, y + (64 if compact else 74), 210, 20, 5, size=11, weight="600", color=MUTED),
        _variable("period_value", "cover_period", 284, y + (64 if compact else 74), 205, 20, 5, size=11, weight="600", color=MUTED),
        _variable("sum_insured_value", "coverage_amount", 516, y + (64 if compact else 74), 210, 20, 5, size=11, weight="600", color=MUTED, prefix="Sum insured RM "),
    ]


def _master_config(key: str, name: str, *, height: int, dense: bool, extended: bool, is_default: bool) -> dict:
    config = new_v7_template_config(name)
    summary_y = 168 if dense else 194
    current_title_y = 270 if dense else 332
    current_y = 300 if dense else 366
    current_h = 470 if dense else 414
    addon_title_y = 790 if dense else 806
    addon_y = 820 if dense else 840
    addon_h = 238 if dense else 205
    if extended:
        summary_y, current_title_y, current_y, current_h = 204, 352, 388, 610
        addon_title_y, addon_y, addon_h = 1026, 1062, 320
    elements = [
        _rectangle("page_background", 0, 0, 794, height, 1, background="#FFFFFF", border=""),
        *_identity_header(compact=dense),
        *_quote_summary(summary_y, compact=dense),
        _text("current_heading", "Your Benefits", 32, current_title_y, 730, 28, 5, size=19, weight="800"),
        _grid("current_benefits_grid", "current_benefits", 32, current_y, 730, current_h, 4, dense=dense),
        _text("addons_heading", "Available Add-ons", 32, addon_title_y, 730, 28, 5, size=18, weight="800"),
        _grid("available_addons_grid", "available_addons", 32, addon_y, 730, addon_h, 4, dense=dense),
        _line("footer_rule", 32, height - 54, 730, 3, color=BORDER, height=1),
        _text("footer_note", "This summary is based on the reviewed quotation. Refer to the insurer wording for full terms.", 32, height - 42, 730, 18, 5, size=9, weight="500", color=MUTED, align="center"),
    ]
    config.update({
        "version": 7, "template_name": name, "v7_master_key": key, "is_default": is_default, "locked": True,
        "page_profile": {
            "profile_key": "extended_portrait" if extended else "a4", "name": "Extended Portrait" if extended else "A4",
            "width": 794, "height": height, "unit": "px", "safe_margins": {"top": 24, "right": 24, "bottom": 24, "left": 24},
            "bleed": {}, "background_behavior": "clip",
        },
    })
    config["canvas"] = {**config["canvas"], "width": 794, "height": height, "elements": elements}
    return validate_template_config(config)


def master_template_specs() -> list[dict]:
    return [
        {"key": "standard_a4", "name": "Standard A4", "is_default": True, "config": _master_config("standard_a4", "Standard A4", height=1123, dense=False, extended=False, is_default=True)},
        {"key": "dense_a4", "name": "Dense A4", "is_default": False, "config": _master_config("dense_a4", "Dense A4", height=1123, dense=True, extended=False, is_default=False)},
        {"key": "extended_portrait", "name": "Extended Portrait", "is_default": False, "config": _master_config("extended_portrait", "Extended Portrait", height=1480, dense=False, extended=True, is_default=False)},
    ]


def ensure_master_templates(db, user, *, apply: bool = False) -> dict:
    """Create and publish missing canonical masters without overwriting a published revision."""
    templates = list(db.scalars(select(OutputTemplateConfig).where(OutputTemplateConfig.deleted_at.is_(None))).all())
    revisions = list(db.scalars(select(TemplateRevision)).all())
    report = {"created": [], "published": [], "retained": [], "default_cleared": [], "apply": apply}
    by_key = {str((item.fixed_fields or {}).get("v7_master_key") or ""): item for item in templates}
    for spec in master_template_specs():
        current = by_key.get(spec["key"])
        published = [item for item in revisions if current and item.template_id == current.id and item.state == "published"]
        if current and published:
            report["retained"].append({"key": spec["key"], "template_id": current.id, "revision": max(item.revision_number for item in published)})
            continue
        if current is None:
            report["created"].append(spec["key"])
            if not apply:
                continue
            current = OutputTemplateConfig(id=new_id(), name=spec["name"], insurance_type="Motor", status="active", fixed_fields=deepcopy(spec["config"]))
            db.add(current)
            db.commit()
            db.refresh(current)
            by_key[spec["key"]] = current
        elif apply:
            current.name = spec["name"]
            current.fixed_fields = deepcopy(spec["config"])
            flag_modified(current, "fixed_fields")
            current.revision += 1
            db.commit()
            db.refresh(current)
        report["published"].append(spec["key"])
        if apply:
            publish_template_revision(db, user, current.id, base_revision=current.revision)

    if apply:
        standard = by_key.get("standard_a4")
        for item in templates + list(by_key.values()):
            config = deepcopy(item.fixed_fields or {})
            wanted = bool(standard and item.id == standard.id)
            if bool(config.get("is_default")) == wanted:
                continue
            config["is_default"] = wanted
            item.fixed_fields = config
            flag_modified(item, "fixed_fields")
            report["default_cleared"].append(item.id)
        db.commit()
    return report
