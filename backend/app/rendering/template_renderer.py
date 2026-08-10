"""Deterministic HTML/CSS rendering for Risklocker quotation PDFs."""

from __future__ import annotations

from html import escape
from typing import Any

from app.services.template_assets import asset_data_uri, find_asset_by_hint
from app.services.template_config import default_template_config, normalize_template_config


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

SHAPE_RADII = {"rounded": "12px", "capsule": "999px", "square": "0"}
SHADOW_MAP = {
    "none": "none",
    "sm": "0 1px 3px rgba(0,0,0,0.12)",
    "md": "0 4px 12px rgba(0,0,0,0.15)",
    "lg": "0 8px 24px rgba(0,0,0,0.18)",
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
        f"font-family:{escape(str(style.get('fontFamily') or 'inherit'))}",
        f"font-style:{escape(str(style.get('fontStyle') or 'normal'))}",
        f"text-transform:{escape(str(style.get('textTransform') or 'none'))}",
        f"color:{escape(str(style.get('color') or '#111'))}",
        f"text-align:{escape(str(style.get('textAlign') or 'left'))}",
        f"background:{escape(str(style.get('background') or 'transparent'))}",
        "overflow:hidden",
        "white-space:pre-wrap",
    ]
    if element.get("shapeKind") == "circle":
        css.append("border-radius:50%")
    elif element.get("shapeKind") == "triangle":
        css.append("clip-path:polygon(50% 0, 100% 100%, 0 100%)")
    elif element.get("shapeKind") == "diamond":
        css.append("clip-path:polygon(50% 0, 100% 50%, 50% 100%, 0 50%)")
    if border_width:
        css.append(
            f"border:{border_width}px {escape(str(style.get('borderStyle') or 'solid'))} {escape(str(style.get('borderColor') or '#111'))}"
        )
    if style.get("borderRadius"):
        css.append(f"border-radius:{float(style['borderRadius'])}px")
    if style.get("letterSpacing"):
        css.append(f"letter-spacing:{float(style['letterSpacing'])}px")
    if style.get("lineHeight"):
        css.append(f"line-height:{escape(str(style['lineHeight']))}")
    if style.get("padding"):
        css.append(f"padding:{float(style['padding'])}px")
    if style.get("boxShadow"):
        css.append(f"box-shadow:{escape(str(style['boxShadow']))}")
    if style.get("rotation"):
        css.append(f"transform:rotate({float(style['rotation'])}deg)")
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
            return find_asset_by_hint(None, ["etiqa"])
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


def _benefit_section(element: dict[str, Any], db: Any = None) -> str:
    columns = max(1, int(element.get("columns") or 2))
    grid = f'{_style(element)};display:grid;grid-template-columns:repeat({columns},1fr);gap:10px 18px;overflow:visible'
    cards = "".join(_variant_card(variant, db) for variant in _section_variants(db, element.get("section")))
    return f'<div style="{grid}">{cards}</div>'


def _section_variants(db: Any, section: str | None) -> list[Any]:
    """Active Our Specials variants for a benefit section (FOC for 'specials', Add-on otherwise)."""
    if db is None:
        return []
    category = "FOC" if section == "specials" else ("Add-on" if section == "add_ons" else None)
    if not category:
        return []
    from sqlalchemy import select

    from app.models.tables import OurSpecial, OurSpecialVariant

    return list(
        db.scalars(
            select(OurSpecialVariant)
            .join(OurSpecial, OurSpecialVariant.special_id == OurSpecial.id)
            .where(
                OurSpecial.status == "active",
                OurSpecial.category == category,
                OurSpecialVariant.status == "active",
            )
            .order_by(OurSpecialVariant.created_at)
        ).all()
    )


def _variant_card(variant: Any, db: Any = None) -> str:
    """A benefit card for an Our Specials variant, sized for a grid cell."""
    label = str(getattr(variant, "label", "") or "")
    value = str(getattr(variant, "value_text", None) or getattr(variant, "secondary_label", None) or "")
    icon_id = str(getattr(variant, "icon_asset_id", None) or "")
    bg = str(getattr(variant, "bg_color", None) or "#F6F8FB")
    fg = str(getattr(variant, "text_color", None) or "#1B1717")
    border_width = str(getattr(variant, "border_width", None) or "")
    border_color = str(getattr(variant, "border_color", None) or "#D8DDE6")
    radius = SHAPE_RADII.get(str(getattr(variant, "shape", None) or "rounded"), "12px")
    shadow = SHADOW_MAP.get(str(getattr(variant, "shadow", None) or "none"), "none")
    border = "" if border_width in {"", "0", "none"} else f"border:{escape(border_width)} solid {escape(border_color)};"

    icon = ""
    if icon_id:
        src = asset_data_uri(db, icon_id)
        if src:
            icon = f'<img alt="" src="{src}" style="max-width:38px;max-height:34px;object-fit:contain;display:block;margin:auto" />'
    if not icon:
        initials = "".join(part[0] for part in label.split() if part)[:2].upper() or "IC"
        icon = f'<span style="display:block;text-align:center;font-weight:900;font-size:9px;line-height:1;color:{escape(fg)}">{escape(initials)}</span>'

    card_style = (
        "display:flex;align-items:center;gap:8px;padding:6px 8px;min-width:0;overflow:hidden;"
        f"background:{escape(bg)};color:{escape(fg)};border-radius:{radius};box-shadow:{shadow};{border}"
    )
    icon_box = (
        "flex:0 0 42px;width:42px;height:42px;display:flex;align-items:center;"
        f"justify-content:center;border-radius:{radius};background:rgba(255,255,255,.35);overflow:hidden"
    )
    copy = f'<div style="min-width:0;overflow:hidden"><div style="font-size:12px;font-weight:700;white-space:pre-wrap;overflow:hidden">{escape(label)}</div>'
    if value:
        copy += f'<div style="font-size:10px;opacity:.85;margin-top:2px;white-space:pre-wrap;overflow:hidden">{escape(value)}</div>'
    copy += "</div>"
    return f'<div style="{card_style}"><div style="{icon_box}">{icon}</div>{copy}</div>'


def _special_html(element: dict[str, Any], config: dict[str, Any]) -> str:
    """Render an Our Specials / Add-on variant as a styled benefit card."""
    style = element.get("style") or {}
    label = str(element.get("variant_label") or "")
    value = str(element.get("variant_value_text") or "")
    icon_id = str(element.get("variant_icon_asset_id") or "")
    bg = str(element.get("variant_bg_color") or style.get("background") or "#F6F8FB")
    fg = str(element.get("variant_text_color") or style.get("color") or "#1B1717")
    border_width = str(element.get("variant_border_width") or "")
    border_color = str(element.get("variant_border_color") or "#D8DDE6")
    radius = SHAPE_RADII.get(str(element.get("variant_shape") or "rounded"), "12px")
    shadow = SHADOW_MAP.get(str(element.get("variant_shadow") or "none"), "none")
    border = "" if border_width in {"", "0", "none"} else f"border:{escape(border_width)} solid {escape(border_color)};"

    if icon_id:
        src = asset_data_uri(None, icon_id)
        icon = f'<img alt="" src="{src}" style="max-width:38px;max-height:34px;object-fit:contain;display:block;margin:auto" />' if src else ""
    else:
        initials = "".join(part[0] for part in label.split() if part)[:2].upper() or "IC"
        icon = f'<span style="display:block;text-align:center;font-weight:900;font-size:9px;line-height:1;color:{escape(fg)}">{escape(initials)}</span>'
    if not icon:
        icon = f'<span style="display:block;text-align:center;font-weight:900;font-size:9px;line-height:1;color:{escape(fg)}">IC</span>'

    font_size = float(style.get("fontSize") or 12)
    card_style = (
        f"{_style(element)};"
        "display:flex;align-items:center;gap:8px;padding:6px 8px;"
        f"background:{escape(bg)};color:{escape(fg)};"
        f"border-radius:{radius};box-shadow:{shadow};{border}"
    )
    icon_box = (
        "flex:0 0 42px;width:42px;height:42px;display:flex;align-items:center;"
        f"justify-content:center;border-radius:{radius};background:rgba(255,255,255,.35);overflow:hidden"
    )
    copy = (
        '<div style="min-width:0;overflow:hidden">'
        f'<div style="font-size:{font_size}px;font-weight:700;white-space:pre-wrap;overflow:hidden">{escape(label)}</div>'
    )
    if value:
        copy += f'<div style="font-size:10px;opacity:.85;margin-top:2px;white-space:pre-wrap;overflow:hidden">{escape(value)}</div>'
    copy += "</div>"
    return f'<div style="{card_style}"><div style="{icon_box}">{icon}</div>{copy}</div>'


def _element_html(element: dict[str, Any], fields: dict, config: dict[str, Any], db: Any = None) -> str:
    element_type = element.get("type")
    if element_type == "image":
        return _image_html(element, config, fields)
    if element_type == "line":
        style = element.get("style") or {}
        thickness = max(2.0, float(element.get("h") or 2))
        line_style = f"{_style(element)};height:{thickness}px"
        if style.get("borderStyle") in {"dashed", "dotted"}:
            dash = 2.0 if style.get("borderStyle") == "dotted" else 6.0
            color = escape(str(style.get("color") or "#111"))
            line_style += f";background:repeating-linear-gradient(90deg,{color} 0 {dash}px,transparent {dash}px {dash * 2}px)"
        return f'<div style="{line_style}"></div>'
    if element_type in {"shape", "group"}:
        return f'<div style="{_style(element)}"></div>'
    if element_type == "variable":
        value = _format_value(_variable_value(fields, config, element.get("variableId")), str(element.get("prefix") or ""), str(element.get("suffix") or ""))
        return f'<div style="{_style(element)}">{escape(value)}</div>'
    if element_type == "benefit-section":
        return _benefit_section(element, db)
    if element_type == "special":
        return _special_html(element, config)
    text = str(element.get("text") or "")
    return f'<div style="{_style(element)}">{escape(text)}</div>'


def render_quotation_html(
    draft_fields: dict,
    template_name: str = "Risklocker Motor Quotation",
    static_notes: str = "",
    template_config: dict[str, Any] | None = None,
    insurer_name: str | None = None,
    db: Any = None,
) -> str:
    config = normalize_template_config(template_config or default_template_config())
    if insurer_name:
        draft_fields = {**draft_fields, "insurance_company": {"value": insurer_name}}
    canvas = config.get("canvas") or {}
    width = int(canvas.get("width") or 794)
    height = int(canvas.get("height") or 1123)
    elements = sorted(canvas.get("elements") or [], key=lambda item: int(item.get("z", 1)))
    body = "".join(_element_html(element, draft_fields, config, db) for element in elements)
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
