"""Deterministic HTML/CSS rendering for Risklocker quotation PDFs."""

from __future__ import annotations

from html import escape
from typing import Any

from app.rendering.grid_layout import GridBounds, GridSpec, pack_fixed_grid
from app.rendering.render_context import format_money_amount
from app.services.template_assets import asset_data_uri, find_asset_by_hint
from app.services.template_config import default_template_config, normalize_template_config


FIELD_LABELS = {
    "coverage_type": "Coverage Type",
    "cover_period": "Cover of Period",
    "car_model": "Car Model",
    "engine_cc": "Vehicle CC",
    "ncd_percent": "NCD",
    "coverage_amount": "Coverage",
    "excess_amount": "Policy Excess",
    "premium": "Insurance Premium",
    "roadtax": "Roadtax",
    "service_fee": "Runner Fee",
    "total_amount": "Total Premium",
    "insurance_company": "Insurer Name",
    "valid_until": "Validity Date",
}

SHAPE_RADII = {"rounded": "12px", "capsule": "999px", "square": "0"}
SHADOW_MAP = {
    "none": "none",
    "sm": "0 1px 3px rgba(0,0,0,0.12)",
    "md": "0 4px 12px rgba(0,0,0,0.15)",
    "lg": "0 8px 24px rgba(0,0,0,0.18)",
}
GRID_CARD_STYLES = {
    "standard": "border:1px solid #D8DDE6;border-radius:12px;background:#F6F8FB",
    "outlined": "border:2px solid #D8DDE6;border-radius:10px;background:#FFFFFF",
    "soft": "border:0;border-radius:16px;background:#F3F0F0;box-shadow:0 2px 8px rgba(27,23,23,.10)",
    "minimal": "border:0;border-radius:0;background:transparent",
}
GRID_TEXT_DENSITIES = {
    "comfortable": {"padding": 14, "gap": 12, "icon": 52, "label": 17, "value": 14},
    "normal": {"padding": 12, "gap": 10, "icon": 48, "label": 16, "value": 13},
    "compact": {"padding": 8, "gap": 6, "icon": 40, "label": 14, "value": 11},
}


FIELD_FALLBACK_MAP: dict[str, tuple[str, ...]] = {
    "premium": ("coverage_premium", "basic_premium_vehicle"),
    "coverage_premium": ("premium", "basic_premium_vehicle"),
    "coverage_amount": ("sum_insured", "market_value", "agreed_value"),
    "sum_insured": ("coverage_amount", "market_value", "agreed_value"),
    "roadtax": ("road_tax_amount",),
    "road_tax_amount": ("roadtax",),
    "service_fee": ("runner_fee",),
    "runner_fee": ("service_fee",),
    "ncd_percent": ("ncd_percentage",),
    "ncd_percentage": ("ncd_percent",),
    "total_amount": ("total_premium_adjusted", "gross_premium"),
    "total_premium_adjusted": ("total_amount", "gross_premium"),
    "engine_cc": ("vehicle_cc", "engine_capacity", "cubic_capacity"),
    "excess_amount": ("policy_excess", "compulsory_excess", "excess", "lebihan", "ekses", "ekses_polisi"),
    "valid_until": ("validity_date", "expiry_date", "validity", "quotation_validity", "valid_to", "expire_on"),
    "insurance_company": ("company_name", "insurer_name"),
}


def _value(fields: dict, field_name: str) -> str:
    field = fields.get(field_name, {})
    val = field.get("value") if isinstance(field, dict) else field
    if val is not None and str(val).strip():
        return str(val).strip()
    for alias in FIELD_FALLBACK_MAP.get(field_name, ()):
        alt_field = fields.get(alias, {})
        alt_val = alt_field.get("value") if isinstance(alt_field, dict) else alt_field
        if alt_val is not None and str(alt_val).strip():
            return str(alt_val).strip()
    return ""


def _variable_value(fields: dict, config: dict[str, Any], variable_id: str | None) -> str:
    if not variable_id:
        return ""
    for variable in config.get("variables", []):
        if variable.get("id") == variable_id:
            if variable.get("source") == "fixed":
                return str(variable.get("fixed_value") or "")
            val = _value(fields, variable.get("field") or variable_id)
            if not val and (variable_id in {"excess_amount", "excess"} or variable.get("field") in {"excess_amount", "excess"}):
                return "0.00"
            return val
    val = _value(fields, variable_id)
    if not val and variable_id in {"excess_amount", "excess"}:
        return "0.00"
    return val


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
    element_type = str(element.get("type") or "")
    if element_type == "ellipse" or element.get("shapeKind") == "circle":
        css.append("border-radius:50%")
    elif element_type == "triangle" or element.get("shapeKind") == "triangle":
        css.append("clip-path:polygon(50% 0, 100% 100%, 0 100%)")
    elif element_type == "diamond" or element.get("shapeKind") == "diamond":
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


def _image_html(
    element: dict[str, Any],
    config: dict[str, Any],
    fields: dict,
    resolved_assets: dict[str, str] | None = None,
) -> str:
    asset_id = str(element.get("assetId") or _asset_id_for_slot(config, element.get("assetSlot"), fields))
    if resolved_assets is not None:
        src = resolved_assets.get(asset_id, "")
    else:
        src = asset_data_uri(None, asset_id)
    if not src:
        # Preserve the authored geometry when an optional or legacy image is
        # unavailable. A broken-image glyph must never leak into a customer PDF.
        return f'<div data-missing-asset="{escape(str(element.get("assetSlot") or asset_id or "image"))}" style="{_style(element)}"></div>'
    return f'<img alt="" src="{src}" style="{_style(element)};object-fit:contain" />'


def _benefit_section(element: dict[str, Any], db: Any = None) -> str:
    """RL-DISABLED legacy global specials — compatibility rendering only."""
    columns = max(1, int(element.get("columns") or 2))
    grid = f'{_style(element)};display:grid;grid-template-columns:repeat({columns},1fr);gap:10px 18px;overflow:visible'
    cards = "".join(_variant_card(variant, db) for variant in _section_variants(db, element.get("section")))
    return f'<div style="{grid}">{cards}</div>'


def _dynamic_benefit_grid(
    element: dict[str, Any],
    render_context: dict[str, Any],
    resolved_assets: dict[str, str],
) -> str:
    kind = str(element.get("gridKind") or "current_benefits")
    if kind not in {"current_benefits", "available_addons"}:
        return ""
    cards = list(render_context.get(kind) or [])
    groups = list(render_context.get("groups") or []) if kind == "current_benefits" else []
    group_by_id = {str(item.get("plan_id")): item for item in groups if item.get("plan_id")}
    ordered = cards
    if groups:
        free = [card for card in cards if not str(card.get("group_id") or "")]
        members: dict[str, list[dict]] = {}
        for card in cards:
            group_id = str(card.get("group_id") or "")
            if group_id and group_id in group_by_id:
                members.setdefault(group_id, []).append(card)
        ordered = free + [card for group in groups for card in members.get(str(group.get("plan_id")), [])]
    packing = element.get("packing") or {}
    bounds = GridBounds(
        x=float(element.get("x") or 0),
        y=float(element.get("y") or 0),
        width=float(element.get("w") or 0),
        height=float(element.get("h") or 0),
    )
    spec = GridSpec(
        strategy=str(packing.get("strategy") or "balanced"),
        alignment=str(packing.get("alignment") or "center"),
        aspect_ratio=float(packing.get("aspectRatio") or 4.5),
        reference_width=float(packing.get("referenceWidth") or 226),
        reference_height=float(packing.get("referenceHeight") or 50),
        gap_ratio=float(packing["gapRatio"]) if packing.get("gapRatio") is not None else 0.04,
        padding_ratio=float(packing["paddingRatio"]) if packing.get("paddingRatio") is not None else 0.02,
        stagger_ratio=float(packing.get("staggerRatio") if packing.get("staggerRatio") is not None else 0.0),
        empty_state=str(element.get("emptyState") or "hide"),
    )
    layout = pack_fixed_grid(len(ordered), bounds, spec)
    if not ordered:
        empty_message = escape(str(element.get("emptyMessage") or "")) if layout.empty_state == "message" else ""
        return (
            f'<div data-grid-kind="{escape(kind)}" data-grid-empty="{escape(layout.empty_state or "hide")}" '
            f'style="position:absolute;left:{bounds.x}px;top:{bounds.y}px;width:{bounds.width}px;height:{bounds.height}px;'
            f'overflow:hidden;display:flex;align-items:center;justify-content:center;text-align:center">{empty_message}</div>'
        )
    card_style_name = str(element.get("cardStyle") or "standard")
    card_style = GRID_CARD_STYLES.get(card_style_name, GRID_CARD_STYLES["standard"])
    density_name = str(element.get("textDensity") or "normal")
    density = GRID_TEXT_DENSITIES.get(density_name, GRID_TEXT_DENSITIES["normal"])
    output: list[str] = []
    group_rects: dict[str, list[tuple[float, float, float, float]]] = {}
    for packed, card in zip(layout.cards, ordered, strict=True):
        group_id = str(card.get("group_id") or "")
        if group_id and group_id in group_by_id:
            group_rects.setdefault(group_id, []).append((packed.x, packed.y, packed.width, packed.height))
        label = escape(str(card.get("label") or ""))
        value = escape(str(card.get("value") or ""))
        cost = str(card.get("cost_status") or "")
        asset_id = str(card.get("asset_id") or "")
        asset_uri = resolved_assets.get(asset_id, "")
        icon_size = max(24, min(36, density["icon"]))
        icon = (
            f'<img alt="" src="{escape(asset_uri)}" style="width:{icon_size}px;height:{icon_size}px;object-fit:contain" />'
            if asset_uri else f'<span style="display:grid;place-items:center;width:{icon_size}px;height:{icon_size}px;border-radius:6px;background:#FEE2E2;color:#DC2626;font-size:10px;font-weight:800">{label[:2].upper()}</span>'
        )
        price_badge = ""
        price = card.get("price")
        if price:
            p_val = price.get("amount") if isinstance(price, dict) else price
            try:
                p_num = float(str(p_val).replace(",", ""))
                p_str = f"RM {p_num:,.2f}"
            except Exception:
                p_str = f"RM {p_val}" if not str(p_val).startswith("RM") else str(p_val)
            price_badge = f'<span style="font-size:9px;font-weight:800;color:#DC2626;background:#FEF2F2;padding:2px 5px;border-radius:4px;white-space:nowrap;border:1px solid #FECACA">+{p_str}</span>'
        elif cost == "foc":
            price_badge = '<span style="font-size:8.5px;font-weight:700;color:#16A34A;background:#F0FDF4;padding:2px 4px;border-radius:4px;white-space:nowrap">FOC</span>'

        value_html = f'<span style="display:block;margin-top:1px;font-size:{max(8.5, density["value"] - 1)}px;line-height:1.15;color:#64748B;word-break:break-word">{value}</span>' if value else ""
        font_size = density["label"] if len(label) <= 24 else max(9.5, density["label"] - 2)
        scale = packed.scale
        output.append(
            f'<article data-benefit-card="1" data-card-scale="{scale:.12f}" '
            f'data-card-style="{escape(card_style_name)}" data-text-density="{escape(density_name)}" '
            f'style="position:absolute;left:{packed.x:.8f}px;top:{packed.y:.8f}px;'
            f'width:{packed.width:.8f}px;height:{packed.height:.8f}px;overflow:hidden;'
            'display:flex;align-items:stretch;box-sizing:border-box">'
            f'<div style="width:100%;height:100%;display:grid;align-items:center;'
            f'grid-template-columns:{icon_size + 8}px minmax(0,1fr) auto;gap:{density["gap"]}px;padding:{density["padding"]}px;'
            f'box-sizing:border-box;{card_style};overflow:hidden;border-radius:6px;border:1px solid #E2E8F0;background:#FFFFFF">'
            f'<div style="display:flex;align-items:center;justify-content:center">{icon}</div>'
            f'<div style="min-width:0;display:flex;flex-direction:column;justify-content:center">'
            f'<strong style="display:block;font-size:{font_size}px;line-height:1.18;word-break:break-word;color:#0F172A">{label}</strong>'
            f'{value_html}</div>'
            f'<div style="display:flex;align-items:center;justify-content:flex-end;margin-left:4px">{price_badge}</div>'
            f'</div></article>'
        )
    warning = escape(layout.warning or "")
    borders: list[str] = []
    for group_id, rects in group_rects.items():
        if not rects:
            continue
        group = group_by_id.get(group_id)
        min_x = min(item[0] for item in rects)
        min_y = min(item[1] for item in rects)
        max_x = max(item[0] + item[2] for item in rects)
        max_y = max(item[1] + item[3] for item in rects)
        pad = 7.0
        box_x = max(bounds.x, min_x - pad)
        box_y = max(bounds.y, min_y - pad)
        box_x2 = min(bounds.x + bounds.width, max_x + pad)
        box_y2 = min(bounds.y + bounds.height, max_y + pad)
        plan_label = escape(str((group or {}).get("plan_label") or "Package plan"))
        borders.append(
            f'<div data-benefit-group="1" style="position:absolute;left:{box_x:.8f}px;top:{box_y:.8f}px;'
            f'width:{box_x2 - box_x:.8f}px;height:{box_y2 - box_y:.8f}px;'
            f'border:2px solid #E51C2A;border-radius:10px;background:rgba(229,28,42,0.025);pointer-events:none">'
            f'<span style="position:absolute;left:8px;top:-11px;background:#E51C2A;color:#fff;'
            f'font-size:10px;font-weight:800;line-height:1;padding:4px 8px;border-radius:4px;'
            f'white-space:nowrap">{plan_label}</span></div>'
        )
    return (
        f'<section data-grid-kind="{escape(kind)}" data-density-warning="{warning}" '
        f'style="position:absolute;left:0;top:0;width:100%;height:100%;overflow:hidden">'
        f'{"".join(borders)}{"".join(output)}</section>'
    )


def _premium_info_block(element: dict[str, Any], fields: dict, render_context: dict[str, Any]) -> str:
    """Dynamic coverage-card rows: extras, premium, roadtax, runner fee, total.

    Positioned deterministically in the canvas, bound to calculated draft values.
    """
    x = float(element.get("x") or 0)
    y = float(element.get("y") or 0)
    width = float(element.get("w") or 0)
    row_height = float(element.get("rowHeight") or 14)
    labels = element.get("labels") or {}
    extras = list((render_context or {}).get("extras") or [])
    rows: list[tuple[str, str, str]] = []
    for extra in extras:
        rows.append(("extra", str(extra.get("label") or ""), format_money_amount(extra.get("price"))))
    rows.append(("premium", str(labels.get("premium") or "Coverage Premium"), _format_value(_value(fields, "premium"), "RM ")))
    rows.append(("divider", "", ""))
    rows.append(("roadtax", str(labels.get("roadtax") or "Roadtax"), _format_value(_value(fields, "roadtax"), "RM ")))
    rows.append(("runner", str(labels.get("runner") or "Runner Fee"), _format_value(_value(fields, "service_fee"), "RM ")))
    total = _value(fields, "total_premium_adjusted") or _value(fields, "total_amount")
    rows.append(("total", str(labels.get("total") or "Total Premium"), _format_value(total, "RM ")))
    html: list[str] = []
    for index, (kind, label, value) in enumerate(rows):
        row_y = y + index * row_height
        if kind == "divider":
            html.append(
                f'<div style="position:absolute;left:{x}px;top:{row_y}px;width:{width}px;height:1px;background:#E2E8F0"></div>'
            )
            continue
        if kind == "total":
            label_style = "font-size:11px;font-weight:800;color:#0F172A"
            value_style = "font-size:13px;font-weight:800;color:#DC2626"
        elif kind == "extra":
            label_style = "font-size:9.5px;font-weight:600;color:#B91C1C"
            value_style = "font-size:10px;font-weight:700;color:#0F172A"
        else:
            label_style = "font-size:9.5px;font-weight:600;color:#334155"
            value_style = "font-size:10px;font-weight:700;color:#0F172A"
        html.append(
            f'<div style="position:absolute;left:{x}px;top:{row_y}px;width:{width}px;height:{row_height}px;'
            f'display:flex;align-items:center;justify-content:space-between">'
            f'<span style="{label_style}">{escape(label)}</span>'
            f'<span style="{value_style}">{escape(value)}</span></div>'
        )
    return "".join(html)


def _balance_benefit_grid_elements(elements: list[dict[str, Any]], render_context: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Dynamically balance the heights of current benefits and available add-ons grids."""
    extras = list((render_context or {}).get("extras") or []) if render_context else []
    extra_shift = len(extras) * 14.0

    current_cards = list((render_context or {}).get("current_benefits") or []) if render_context else []
    addon_cards = list((render_context or {}).get("available_addons") or []) if render_context else []
    n1 = len(current_cards)
    n2 = len(addon_cards)

    grid1 = next((e for e in elements if e.get("type") == "benefit-grid" and e.get("gridKind") == "current_benefits"), None)
    grid2 = next((e for e in elements if e.get("type") == "benefit-grid" and e.get("gridKind") == "available_addons"), None)
    if not grid1 or not grid2:
        return elements

    hdr1_bg = next((e for e in elements if e.get("id") == "specials_header_bg"), None)
    hdr1_txt = next((e for e in elements if e.get("id") == "specials_header_txt"), None)
    hdr2_bg = next((e for e in elements if e.get("id") == "addons_header_bg"), None)
    hdr2_txt = next((e for e in elements if e.get("id") == "addons_header_txt"), None)

    base_y_top = float(hdr1_bg.get("y") or 414) if hdr1_bg else float(grid1.get("y") or 444)
    y_top = base_y_top + extra_shift
    y_bottom = float(grid2.get("y") or 796) + float(grid2.get("h") or 262)

    rows1 = max(1, (n1 + 1) // 2) if n1 > 0 else 0
    rows2 = max(1, (n2 + 1) // 2) if n2 > 0 else 0

    total_space = y_bottom - y_top
    hdr_h = 26.0
    gap = 10.0
    pad = 4.0

    avail_grids_h = total_space - (2 * hdr_h) - gap - (2 * pad)
    if avail_grids_h <= 100:
        avail_grids_h = 360.0

    if rows1 > 0 and rows2 > 0:
        ratio1 = rows1 / (rows1 + rows2)
        h1 = max(100.0, min(avail_grids_h - 80.0, avail_grids_h * ratio1))
        h2 = avail_grids_h - h1
    elif rows1 > 0 and rows2 == 0:
        h1 = avail_grids_h + hdr_h + gap + pad - 60.0
        h2 = 60.0
    elif rows1 == 0 and rows2 > 0:
        h1 = 60.0
        h2 = avail_grids_h + hdr_h + gap + pad - 60.0
    else:
        h1 = avail_grids_h / 2.0
        h2 = avail_grids_h / 2.0

    adjusted_elements = []
    y_g1 = y_top + hdr_h + pad
    y_h2 = y_g1 + h1 + gap
    y_g2 = y_h2 + hdr_h + pad

    for elem in elements:
        e = dict(elem)
        eid = e.get("id")
        if eid == "cov_table_bg" and extra_shift > 0:
            e["h"] = float(e.get("h") or 246) + extra_shift
        elif eid == "specials_header_bg" and hdr1_bg:
            e["y"] = y_top
            e["h"] = hdr_h
        elif eid == "specials_header_txt" and hdr1_txt:
            e["y"] = y_top + 5
        elif e.get("type") == "benefit-grid" and e.get("gridKind") == "current_benefits":
            e["y"] = y_g1
            e["h"] = h1
        elif eid == "addons_header_bg" and hdr2_bg:
            e["y"] = y_h2
            e["h"] = hdr_h
        elif eid == "addons_header_txt" and hdr2_txt:
            e["y"] = y_h2 + 5
        elif e.get("type") == "benefit-grid" and e.get("gridKind") == "available_addons":
            e["y"] = y_g2
            e["h"] = h2
        adjusted_elements.append(e)

    return adjusted_elements


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
    card_style = (
        "display:flex;align-items:center;gap:8px;padding:8px;box-sizing:border-box;overflow:hidden;"
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


def _element_html(
    element: dict[str, Any],
    fields: dict,
    config: dict[str, Any],
    db: Any = None,
    render_context: dict[str, Any] | None = None,
    resolved_assets: dict[str, str] | None = None,
) -> str:
    element_type = element.get("type")
    if element.get("visible") is False or element_type == "layer-group":
        return ""
    if element_type == "image":
        return _image_html(element, config, fields, resolved_assets)
    if element_type == "line":
        style = element.get("style") or {}
        thickness = max(2.0, float(element.get("h") or 2))
        line_style = f"{_style(element)};height:{thickness}px"
        if style.get("borderStyle") in {"dashed", "dotted"}:
            dash = 2.0 if style.get("borderStyle") == "dotted" else 6.0
            color = escape(str(style.get("color") or "#111"))
            line_style += f";background:repeating-linear-gradient(90deg,{color} 0 {dash}px,transparent {dash}px {dash * 2}px)"
        return f'<div style="{line_style}"></div>'
    if element_type in {"shape", "group", "rectangle", "ellipse", "triangle", "diamond"}:
        return f'<div style="{_style(element)}"></div>'
    if element_type == "variable":
        value = _format_value(_variable_value(fields, config, element.get("variableId")), str(element.get("prefix") or ""), str(element.get("suffix") or ""))
        return f'<div style="{_style(element)}">{escape(value)}</div>'
    if element_type == "special":
        return _special_html(element, config)
    if element_type == "benefit-section":
        return _benefit_section(element, db)
    if element_type == "benefit-grid":
        return _dynamic_benefit_grid(element, render_context or {}, resolved_assets or {})
    if element_type == "premium-info-block":
        return _premium_info_block(element, fields, render_context or {})
    text = str(element.get("text") or "")
    if "{" in text:
        def _replace_var(m):
            v_name = m.group(1)
            val = _value(fields, v_name)
            if not val and v_name == "valid_until":
                return "30 Days"
            return val if val else m.group(0)
        text = re.sub(r"\{([a-zA-Z0-9_-]+)\}", _replace_var, text)
    return f'<div style="{_style(element)}">{escape(text)}</div>'


def render_quotation_html(
    draft_fields: dict,
    template_name: str = "Risklocker Motor Quotation",
    static_notes: str = "",
    template_config: dict[str, Any] | None = None,
    insurer_name: str | None = None,
    db: Any = None,
    render_context: dict[str, Any] | None = None,
    resolved_assets: dict[str, str] | None = None,
) -> str:
    config = normalize_template_config(template_config or default_template_config())
    if insurer_name:
        draft_fields = {**draft_fields, "insurance_company": {"value": insurer_name}}
    canvas = config.get("canvas") or {}
    width = int(canvas.get("width") or 794)
    height = int(canvas.get("height") or 1123)
    raw_elements = canvas.get("elements") or []
    balanced = _balance_benefit_grid_elements(raw_elements, render_context)
    elements = sorted(balanced, key=lambda item: int(item.get("z", 1)))
    body = "".join(
        _element_html(element, draft_fields, config, db, render_context, resolved_assets)
        for element in elements
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>{escape(template_name)}</title>
<style>
@page {{ size: {width}px {height}px; margin: 0; }}
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
