"""Deterministic HTML/CSS rendering for Risklocker quotation PDFs."""

from __future__ import annotations

import json
from html import escape
from typing import Any

from app.services.template_assets import asset_data_uri, find_asset_by_hint
from app.services.template_config import card_from_label, default_template_config, normalize_template_config, selected_package_config


FIELD_LABELS = {
    "coverage_type": "Coverage Type",
    "cover_period": "Cover of Period",
    "car_model": "Car Model",
    "ncd_percent": "NCD",
    "coverage_amount": "Coverage",
    "premium": "Insurance Premium",
    "roadtax": "Roadtax",
    "service_fee": "Runner Fee",
    "total_amount": "Total Premium",
}


def _value(fields: dict, field_name: str) -> str:
    field = fields.get(field_name, {})
    if isinstance(field, dict):
        return str(field.get("value") or "")
    return str(field or "")


def _variable_value(fields: dict, config: dict[str, Any], variable_id: str | None) -> str:
    if not variable_id:
        return ""
    for variable in config.get("variables", []):
        if variable.get("id") == variable_id:
            if variable.get("source") == "fixed":
                return str(variable.get("fixed_value") or "")
            return _value(fields, variable.get("field") or variable_id)
    return _value(fields, variable_id)


def _format_value(value: str, prefix: str = "", suffix: str = "") -> str:
    value = value.strip()
    if not value:
        return ""
    if prefix and not value.upper().startswith(prefix.upper()):
        value = f"{prefix}{value}" if prefix.endswith(" ") else f"{prefix} {value}"
    if suffix and not value.endswith(suffix):
        value = f"{value}{suffix}"
    return value


def _style(element: dict[str, Any]) -> str:
    style = element.get("style") or {}
    border_width = int(style.get("borderWidth") or 0)
    css = [
        "position:absolute",
        f"left:{float(element.get('x', 0))}px",
        f"top:{float(element.get('y', 0))}px",
        f"width:{float(element.get('w', 0))}px",
        f"height:{float(element.get('h', 0))}px",
        f"z-index:{int(element.get('z', 1))}",
        f"font-size:{float(style.get('fontSize') or 14)}px",
        f"font-weight:{escape(str(style.get('fontWeight') or '400'))}",
        f"color:{escape(str(style.get('color') or '#111'))}",
        f"text-align:{escape(str(style.get('textAlign') or 'left'))}",
        f"background:{escape(str(style.get('background') or 'transparent'))}",
        "overflow:hidden",
        "white-space:pre-wrap",
    ]
    if border_width:
        css.append(f"border:{border_width}px solid {escape(str(style.get('borderColor') or '#111'))}")
    if element.get("opacity") is not None:
        css.append(f"opacity:{float(element.get('opacity'))}")
    return ";".join(css)


def _asset_id_for_slot(config: dict[str, Any], slot: str | None, fields: dict) -> str:
    if not slot:
        return ""
    assets = config.get("assets") or {}
    if assets.get(slot):
        return str(assets[slot])
    if slot == "insurer_logo":
        company = _value(fields, "insurance_company").lower()
        if "etiqa" in company:
            return find_asset_by_hint(["etiqa"])
        if "lonpac" in company:
            return find_asset_by_hint(None, ["lonpac"])
        if "qbe" in company:
            return find_asset_by_hint(None, ["qbe"])
        if "liberty" in company:
            return find_asset_by_hint(None, ["liberty"])
        if "amgen" in company or "amassurance" in company or "kurnia" in company:
            return find_asset_by_hint(None, ["amgen", "amassurance"])
    hints = config.get("asset_slots", {}).get(slot) or [slot]
    return find_asset_by_hint(None, [str(item) for item in hints])


def _image_html(element: dict[str, Any], config: dict[str, Any], fields: dict) -> str:
    asset_id = str(element.get("assetId") or _asset_id_for_slot(config, element.get("assetSlot"), fields))
    src = asset_data_uri(None, asset_id)
    if not src:
        return ""
    return f'<img alt="" src="{src}" style="{_style(element)};object-fit:contain" />'


def _selected_card_ids(fields: dict, field_name: str, fallback: list[str]) -> list[str]:
    value = _value(fields, field_name).strip()
    if not value:
        return fallback
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except json.JSONDecodeError:
        pass
    return [card_from_label(item) for item in value.split(";") if item.strip()]


def _card_html(card: dict[str, Any], config: dict[str, Any]) -> str:
    title = escape(str(card.get("title", "")))
    subtitle = escape(str(card.get("subtitle", "")))
    lines = "".join(f"<div>{escape(str(line))}</div>" for line in card.get("lines", []))
    asset_id = str(card.get("asset_id") or "")
    if not asset_id:
        asset_id = find_asset_by_hint(None, [str(card.get("asset_hint") or ""), str(card.get("title") or ""), str(card.get("icon") or "")])
    img = asset_data_uri(None, asset_id)
    icon_html = f'<img alt="" src="{img}" />' if img else f"<span>{escape(str(card.get('icon', 'IC'))[:2].upper())}</span>"
    return (
        '<div class="benefit-card">'
        f'<div class="benefit-icon">{icon_html}</div>'
        '<div class="benefit-copy">'
        f"<strong>{title}</strong>"
        f"{f'<div>{subtitle}</div>' if subtitle else ''}{lines}"
        "</div></div>"
    )


def _benefit_section(element: dict[str, Any], fields: dict, config: dict[str, Any], selected_package: str | None) -> str:
    package = selected_package_config(config, selected_package)
    section = element.get("section") or "specials"
    fallback = package.get("included_cards" if section == "specials" else "add_on_cards", []) if package else []
    field_name = "benefits_selected" if section == "specials" else "add_ons_selected"
    card_ids = _selected_card_ids(fields, field_name, fallback)
    cards = config.get("cards") or {}
    card_html = "".join(_card_html(cards.get(card_id, {"id": card_id, "title": card_id}), config) for card_id in card_ids)
    columns = max(1, int(element.get("columns") or 2))
    return f'<div style="{_style(element)};display:grid;grid-template-columns:repeat({columns},1fr);gap:10px 18px;overflow:visible">{card_html}</div>'


def _element_html(element: dict[str, Any], fields: dict, config: dict[str, Any], selected_package: str | None) -> str:
    element_type = element.get("type")
    if element_type == "image":
        return _image_html(element, config, fields)
    if element_type == "line":
        return f'<div style="{_style(element)}"></div>'
    if element_type in {"shape", "group"}:
        return f'<div style="{_style(element)}"></div>'
    if element_type == "variable":
        value = _format_value(_variable_value(fields, config, element.get("variableId")), str(element.get("prefix") or ""), str(element.get("suffix") or ""))
        return f'<div style="{_style(element)}">{escape(value)}</div>'
    if element_type == "benefit-section":
        return _benefit_section(element, fields, config, selected_package)
    if element_type == "benefit-card":
        card = (config.get("cards") or {}).get(element.get("cardId"), {"title": element.get("cardId") or ""})
        return f'<div style="{_style(element)}">{_card_html(card, config)}</div>'
    text = str(element.get("text") or "")
    return f'<div style="{_style(element)}">{escape(text)}</div>'


def render_quotation_html(
    draft_fields: dict,
    template_name: str = "Risklocker Motor Quotation",
    static_notes: str = "",
    template_config: dict[str, Any] | None = None,
    selected_package: str | None = None,
    insurer_name: str | None = None,
) -> str:
    config = normalize_template_config(template_config or default_template_config())
    if insurer_name:
        draft_fields = {**draft_fields, "insurance_company": {"value": insurer_name}}
    canvas = config.get("canvas") or {}
    width = int(canvas.get("width") or 794)
    height = int(canvas.get("height") or 1123)
    elements = sorted(canvas.get("elements") or [], key=lambda item: int(item.get("z", 1)))
    body = "".join(_element_html(element, draft_fields, config, selected_package) for element in elements)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>{escape(template_name)}</title>
<style>
@page {{ size: A4; margin: 0; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: "Be Vietnam Pro", Arial, sans-serif; color: #111; background: #fff; }}
.page {{ position: relative; width: {width}px; height: {height}px; margin: 0 auto; overflow: hidden; background: #fff; }}
.benefit-card {{ display: grid; grid-template-columns: 54px 1fr; min-height: 42px; border: 1px solid #111; background: rgba(255,255,255,.78); break-inside: avoid; }}
.benefit-icon {{ display: flex; align-items: center; justify-content: center; border-right: 1px solid #111; font-size: 12px; font-weight: 900; overflow: hidden; }}
.benefit-icon img {{ max-width: 42px; max-height: 34px; object-fit: contain; }}
.benefit-copy {{ padding: 5px 6px; font-size: 12px; line-height: 1.32; overflow: hidden; }}
.benefit-copy strong {{ display: block; font-size: 12px; }}
</style>
</head>
<body>
<main class="page" aria-label="{escape(template_name)}">
{body}
</main>
</body>
</html>"""
