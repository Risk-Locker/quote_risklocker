"""Deterministic HTML/CSS rendering for Risklocker quotation PDFs."""

from __future__ import annotations

import re
from decimal import Decimal
from html import escape
from typing import Any

from app.rendering.grid_layout import GridBounds, GridSpec, pack_fixed_grid
from app.rendering.render_context import adjusted_total_text, format_money_amount
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
    "total_amount": "Final Price",
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
    "standard": "border:1px solid #E2E8F0;border-radius:6px;background:#FFFFFF;box-shadow:0 1px 2px rgba(0,0,0,0.03)",
    "outlined": "border:1px solid #E2E8F0;border-radius:6px;background:#FFFFFF;box-shadow:0 1px 2px rgba(0,0,0,0.03)",
    "soft": "border:1px solid #E2E8F0;border-radius:6px;background:#F8FAFC",
    "minimal": "border:0;border-radius:0;background:transparent",
}
GRID_TEXT_DENSITIES = {
    "comfortable": {"padding": 7, "gap": 6, "icon": 24, "label": 11, "value": 10, "desc": 8.5},
    "normal":      {"padding": 5, "gap": 5, "icon": 22, "label": 10.5, "value": 9.5, "desc": 8},
    "compact":     {"padding": 4, "gap": 4.5, "icon": 20, "label": 10, "value": 9, "desc": 7.8},
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
    "quotation_reference": ("quotation_ref", "quote_ref", "reference_no", "quote_no"),
    "quotation_ref": ("quotation_reference", "quote_ref", "reference_no", "quote_no"),
    "vehicle_no": ("vehicle_plate", "car_plate", "plate_no", "registration_no"),
}


def _value(fields: dict, field_name: str) -> str:
    field = fields.get(field_name, {})
    val = field.get("value") if isinstance(field, dict) else field
    if val is not None and str(val).strip():
        s = str(val).strip()
        if field_name in {"quotation_reference", "quotation_ref", "reference_no", "quote_no"}:
            s = s.rstrip(" -:_/")
        return s
    for alias in FIELD_FALLBACK_MAP.get(field_name, ()):
        alt_field = fields.get(alias, {})
        alt_val = alt_field.get("value") if isinstance(alt_field, dict) else alt_field
        if alt_val is not None and str(alt_val).strip():
            s = str(alt_val).strip()
            if field_name in {"quotation_reference", "quotation_ref", "reference_no", "quote_no"}:
                s = s.rstrip(" -:_/")
            return s
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
    if prefix and prefix.strip().upper() == "RM" and re.match(r"^\d+(?:\.\d+)?$", value):
        try:
            num = float(value)
            value = f"{num:,.2f}"
        except Exception:
            pass
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


def _asset_id_for_slot(config: dict[str, Any], slot: str | None, fields: dict, db: Any = None) -> str:
    if not slot:
        return ""
    assets = config.get("assets") or {}
    if assets.get(slot):
        return str(assets[slot])
    if slot == "insurer_logo":
        company_name = _value(fields, "insurance_company").lower().strip()
        if company_name and db is not None:
            # DB-driven: match against InsuranceCompany.detection_phrases (and name)
            try:
                from sqlalchemy import select
                from app.models.tables import InsuranceCompany
                companies = list(db.scalars(select(InsuranceCompany).where(InsuranceCompany.status == "active")).all())
                for c in companies:
                    phrases = list(c.detection_phrases or [])
                    if not phrases:
                        phrases = [c.name]
                    if any(p.lower() in company_name or company_name in p.lower() for p in phrases):
                        if c.logo_asset_id:
                            return str(c.logo_asset_id)
                        # No logo_asset_id — try hint search with company name tokens
                        hints = [p.lower() for p in phrases[:3]]
                        result = find_asset_by_hint(db, hints)
                        if result:
                            return result
            except Exception:
                pass  # DB unavailable — fall through to hint search
        if company_name:
            # Fallback: hint search from the company name tokens directly
            tokens = [t for t in company_name.split() if len(t) >= 3]
            if tokens:
                result = find_asset_by_hint(None, tokens[:4])
                if result:
                    return result
    hints = config.get("asset_slots", {}).get(slot) or [slot]
    return find_asset_by_hint(None, [str(item) for item in hints])


def _image_html(
    element: dict[str, Any],
    config: dict[str, Any],
    fields: dict,
    resolved_assets: dict[str, str] | None = None,
    db: Any = None,
) -> str:
    asset_id = str(element.get("assetId") or _asset_id_for_slot(config, element.get("assetSlot"), fields, db))
    if resolved_assets is not None:
        src = resolved_assets.get(asset_id, "")
    else:
        src = asset_data_uri(db, asset_id)
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
    if kind not in {"current_benefits", "available_addons", "extras", "purchased_extras"}:
        return ""
    if kind == "available_addons":
        cards = list(render_context.get("available_addons") or [])
    elif kind in {"extras", "purchased_extras"}:
        current = list(render_context.get("current_benefits") or [])
        cards = [c for c in current if c.get("badge") or c.get("price") or c.get("cost_status") == "paid"]
    else:
        cards = list(render_context.get("current_benefits") or [])
    groups = list(render_context.get("groups") or []) if kind in {"current_benefits", "extras", "purchased_extras"} else []
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
    density_name = str(element.get("textDensity") or "compact")
    layout_mode = str(element.get("layoutMode") or "masonry")
    density = GRID_TEXT_DENSITIES.get(density_name, GRID_TEXT_DENSITIES["compact"])
    card_style_css = GRID_CARD_STYLES.get(card_style_name, GRID_CARD_STYLES["standard"])

    output: list[str] = []
    group_rects: dict[str, list[tuple[float, float, float, float]]] = {}

    def _build_card_html(card: dict, px: float, py: float, pw: float, ph: float, scale: float, extra_style: str = "") -> str:
        group_id_c = str(card.get("group_id") or "")
        if group_id_c and group_id_c in group_by_id:
            group_rects.setdefault(group_id_c, []).append((px, py, pw, ph))

        label_str = escape(str(card.get("label") or ""))
        value_str = escape(str(card.get("value") or ""))
        desc_str = escape(str(card.get("description") or ""))
        cost_status = str(card.get("cost_status") or "")
        asset_id_c = str(card.get("asset_id") or "")
        asset_uri_c = resolved_assets.get(asset_id_c, "")

        is_purchased_extra = bool(card.get("is_extra") or (card.get("cost_status") == "paid" and kind == "current_benefits"))
        is_dark = element.get("benefitPreset") == "dark-signature"
        is_minimal = element.get("benefitPreset") == "compact-minimal" or element.get("cardStyle") == "minimal"
        is_elevated = element.get("benefitPreset") == "elevated-3d" or element.get("cardStyle") == "soft"
        is_grid_tile = element.get("benefitPreset") == "grid-tile" or element.get("cardStyle") == "outlined"

        if is_purchased_extra:
            card_border_css = "border:1.5px solid #F59E0B;background:#FFFDF7;box-shadow:0 1px 3px rgba(245,158,11,0.15)"
        elif is_dark:
            card_border_css = "border:1px solid #334155;background:#0F172A;box-shadow:0 1px 3px rgba(0,0,0,0.3)"
        elif is_elevated:
            card_border_css = "border:1px solid #E2E8F0;background:#FFFFFF;box-shadow:0 4px 12px rgba(0,0,0,0.08)"
        elif is_grid_tile:
            card_border_css = "border:1px solid #CBD5E1;background:#F8FAFC;box-shadow:none"
        elif is_minimal:
            card_border_css = "border:1px solid #F1F5F9;background:#FFFFFF;box-shadow:none"
        else:
            card_border_css = card_style_css

        pad = 3 if is_minimal else density["padding"]
        icon_sz = (density["icon"] - 2) if is_minimal else density["icon"]
        lbl_fs = (density["label"] - 0.5) if is_minimal else density["label"]
        val_fs = density["value"]
        desc_fs = density["desc"]
        title_color = "#FFFFFF" if is_dark else "#0F172A"
        desc_color = "#94A3B8" if is_dark else "#64748B"
        val_color = "#F59E0B" if is_dark else "#DC2626"

        # --- Image cell (bottom-left) ---
        icon_radius = "999px" if is_grid_tile else "4px"
        if asset_uri_c:
            image_html = (
                f'<img alt="" src="{escape(asset_uri_c)}" '
                f'style="width:{icon_sz}px;height:{icon_sz}px;object-fit:contain;display:block;flex-shrink:0;border-radius:{icon_radius}" />'
            )
        else:
            initials = label_str[:2].upper() if label_str else "?"
            image_html = (
                f'<span style="display:grid;place-items:center;width:{icon_sz}px;height:{icon_sz}px;'
                f'border-radius:{icon_radius};background:#FEE2E2;color:#DC2626;font-size:{desc_fs}px;'
                f'font-weight:800;flex-shrink:0">{initials}</span>'
            )

        # --- Coverage value row ---
        cov_limit = card.get("detected_limit") or card.get("coverage_limit")
        if cov_limit:
            value_str = str(cov_limit) if str(cov_limit).startswith("RM") else f"RM {cov_limit}"
        elif value_str and (card.get("price") or card.get("optional_price")):
            try:
                v_num = float(re.sub(r"[^0-9.]", "", value_str))
                price_obj = card.get("price") or card.get("optional_price")
                p_raw = (price_obj.get("amount") if price_obj.get("amount") is not None else price_obj.get("value")) if isinstance(price_obj, dict) else price_obj
                p_num = float(re.sub(r"[^0-9.]", "", str(p_raw)))
                if abs(v_num - p_num) < 0.01:
                    value_str = ""
            except Exception:
                pass

        show_value = bool(value_str and value_str not in {"Included standard cover", "Included", "FOC", "As quoted"})
        coverage_html = (
            f'<span style="display:block;font-size:{val_fs}px;font-weight:700;line-height:1.15;'
            f'color:{val_color};overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{value_str}</span>'
            if show_value else ""
        )

        # --- Short description row ---
        desc_html = (
            f'<span style="display:block;font-size:{desc_fs}px;line-height:1.2;color:{desc_color};'
            f'overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical">'
            f'{desc_str}</span>'
            if (desc_str and not is_minimal) else ""
        )

        # --- Cost / price badge ---
        price_badge = ""
        price = card.get("price") or card.get("optional_price")
        is_addon_card = card.get("is_addon") or kind == "available_addons" or is_purchased_extra or bool(card.get("price"))
        if is_addon_card and not card.get("is_pure_default"):
            p_val = None
            if price:
                p_val = (price.get("amount") if price.get("amount") is not None else price.get("value")) if isinstance(price, dict) else price
            elif card.get("detected_cost"):
                p_val = card.get("detected_cost")

            if p_val is not None and str(p_val).strip() and str(p_val).strip() not in {"0", "0.00", "0.0"}:
                try:
                    p_num = float(re.sub(r"[^0-9.]", "", str(p_val)))
                    p_str = f"Cost : MYR {p_num:,.2f}"
                except Exception:
                    clean_pval = str(p_val).replace("RM ", "").replace("RM", "")
                    p_str = f"Cost : MYR {clean_pval}"
                price_badge = (
                    f'<span style="display:block;margin-top:1px;font-size:{desc_fs}px;font-weight:600;'
                    f'color:{"#FBBF24" if is_dark else "#0F172A"};line-height:1.15;white-space:nowrap">{p_str}</span>'
                )
            elif kind == "available_addons":
                price_badge = (
                    f'<span style="display:block;margin-top:1px;font-size:{desc_fs}px;font-weight:600;'
                    f'color:{"#FBBF24" if is_dark else "#0F172A"};line-height:1.15;white-space:nowrap">Cost : As quoted</span>'
                )

        # Title font: shrink for long labels
        title_fs = lbl_fs - 1.0 if len(label_str) > 30 else (lbl_fs - 0.5 if len(label_str) > 18 else float(lbl_fs))
        title_margin = 1 if is_minimal else 3

        inner_html = (
            # Title row (full width)
            f'<div style="display:block;font-size:{title_fs}px;font-weight:700;line-height:1.15;'
            f'color:{title_color};overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'
            f'margin-bottom:{title_margin}px">{label_str}</div>'
            # Bottom row: image left, detail right
            f'<div style="display:flex;gap:5px;align-items:flex-start">'
            f'{image_html}'
            f'<div style="flex:1;min-width:0;display:flex;flex-direction:column;justify-content:flex-start;gap:1px;overflow:hidden">'
            f'{coverage_html}'
            f'{desc_html}'
            f'{price_badge}'
            f'</div>'
            f'</div>'
        )

        pos_style = f"position:absolute;left:{px:.8f}px;top:{py:.8f}px;width:{pw:.8f}px;height:{ph:.8f}px;" if extra_style == "" else extra_style
        return (
            f'<article data-benefit-card="1" data-card-scale="{scale:.12f}" '
            f'data-card-style="{escape(card_style_name)}" data-text-density="{escape(density_name)}" '
            f'style="{pos_style}box-sizing:border-box">'
            f'<div style="width:100%;display:flex;flex-direction:column;'
            f'padding:{pad}px;box-sizing:border-box;border-radius:6px;{card_border_css};overflow:hidden">'
            f'{inner_html}'
            f'</div></article>'
        )

    if layout_mode != "normal":
        # Pure 3-Column Masonry System (Default)
        col_count = max(1, int(element.get("columns") or 3))
        gap = density["gap"]
        cols: list[list[dict[str, Any]]] = [[] for _ in range(col_count)]
        for idx, card in enumerate(ordered):
            cols[idx % col_count].append(card)

        cols_html = []
        for col_cards in cols:
            cards_html = "".join(
                _build_card_html(
                    card, 0, 0, 0, 0, 1.0,
                    extra_style="position:relative;width:100%;box-sizing:border-box;",
                )
                for card in col_cards
            )
            cols_html.append(
                f'<div style="flex:1;min-width:0;display:flex;flex-direction:column;gap:{gap}px;">'
                f'{cards_html}</div>'
            )

        warning = escape(layout.warning or "")
        return (
            f'<section data-grid-kind="{escape(kind)}" data-density-warning="{warning}" '
            f'style="position:absolute;left:{bounds.x:.8f}px;top:{bounds.y:.8f}px;'
            f'width:{bounds.width:.8f}px;display:flex;flex-direction:row;gap:{gap}px;align-items:flex-start;">'
            f'{"".join(cols_html)}</section>'
        )


    # Normal fixed-grid mode
    for packed, card in zip(layout.cards, ordered, strict=True):
        output.append(_build_card_html(card, packed.x, packed.y, packed.width, packed.height, packed.scale))


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
    rows: list[tuple[str, str, str, str]] = []  # (kind, label, middle_val, right_val)
    if extras:
        extras_hdr = str(labels.get("extras") or "Extras / 附加项目")
        rows.append(("extras_header", extras_hdr, "", ""))
        for extra in extras:
            raw_price = extra.get("price") or {}
            amt = raw_price.get("amount") if isinstance(raw_price, dict) else raw_price
            if amt is not None:
                try:
                    num = Decimal(str(amt))
                    formatted_price = f"RM {num:,.2f}"
                except Exception:
                    formatted_price = format_money_amount(raw_price)
            else:
                formatted_price = format_money_amount(raw_price)
            cov_limit = str(extra.get("coverage_limit") or "")
            if cov_limit:
                clean_cov = re.sub(r"[()]", "", cov_limit).replace("RM", "").strip()
                try:
                    num_cov = float(clean_cov.replace(",", ""))
                    cov_limit = f"(RM {int(num_cov):,})" if num_cov == int(num_cov) else f"(RM {num_cov:,.2f})"
                except Exception:
                    cov_limit = f"({cov_limit.strip()})" if not cov_limit.startswith("(") else cov_limit
            rows.append(("extra", str(extra.get("label") or ""), cov_limit, formatted_price))
    rows.append(("premium", str(labels.get("premium") or "Insurance Premium / 保费"), "", _format_value(_value(fields, "premium"), "RM ")))
    rows.append(("divider", "", "", ""))
    rt_display = _value(fields, "roadtax")
    if not rt_display and (fields or {}).get("engine_cc"):
        from app.services.road_tax_service import calculate_road_tax
        cc_raw = (fields or {}).get("engine_cc")
        cc_val = cc_raw.get("value") if isinstance(cc_raw, dict) else cc_raw
        if cc_val:
            try:
                clean_cc = float(re.sub(r"[^\d.]", "", str(cc_val)))
                if clean_cc > 0:
                    vtype_raw = (fields or {}).get("vehicle_type")
                    vtype_val = vtype_raw.get("value") if isinstance(vtype_raw, dict) else vtype_raw
                    calc_rt = calculate_road_tax(clean_cc, str(vtype_val or "Car"))
                    if calc_rt > 0:
                        rt_display = f"{calc_rt:.2f}"
            except Exception:
                pass
    rows.append(("roadtax", str(labels.get("roadtax") or "Roadtax / 路税"), "", _format_value(rt_display, "RM ")))
    rows.append(("runner", str(labels.get("runner") or "Runner Fee / 服务费"), "", _format_value(_value(fields, "service_fee"), "RM ")))
    total = (render_context or {}).get("total_premium_adjusted") or _value(fields, "total_premium_adjusted")
    if not total:
        total = adjusted_total_text(fields, extras) if extras else _value(fields, "total_amount")
    if not total:
        total = _value(fields, "total_amount")
    rows.append(("total", str(labels.get("total") or "TOTAL PAYABLE"), "", _format_value(total, "RM ")))
    html: list[str] = []
    for index, (kind, label, middle_val, right_val) in enumerate(rows):
        row_y = y + index * row_height
        if kind == "divider":
            html.append(
                f'<div style="position:absolute;left:{x}px;top:{row_y}px;width:{width}px;height:1px;background:#E2E8F0"></div>'
            )
            continue
        if kind == "total":
            label_style = "font-size:11px;font-weight:800;color:#0F172A"
            value_style = "font-size:13px;font-weight:800;color:#DC2626"
        elif kind == "extras_header":
            label_style = "font-size:9px;font-weight:700;color:#DC2626;text-transform:uppercase;letter-spacing:0.5px"
            value_style = "font-size:9px;font-weight:700;color:#DC2626"
        elif kind == "extra":
            label_style = "font-size:9px;font-weight:600;color:#B91C1C;white-space:nowrap"
            limit_html = f'<span style="font-size:9px;font-weight:600;color:#B91C1C;margin-left:4px;white-space:nowrap">{escape(middle_val)}</span>' if middle_val else ""
            value_style = "font-size:9.5px;font-weight:700;color:#0F172A;white-space:nowrap;text-align:right"
            html.append(
                f'<div style="position:absolute;left:{x}px;top:{row_y}px;width:{width}px;height:{row_height}px;'
                f'display:flex;align-items:center;justify-content:space-between;box-sizing:border-box;padding-left:10px">'
                f'<div style="display:flex;align-items:center;min-width:0;overflow:hidden">'
                f'<span style="{label_style}">{escape(label)}</span>'
                f'{limit_html}</div>'
                f'<span style="{value_style}">{escape(right_val)}</span></div>'
            )
            continue
        else:
            label_style = "font-size:9.5px;font-weight:600;color:#334155"
            value_style = "font-size:10px;font-weight:700;color:#0F172A"
        html.append(
            f'<div style="position:absolute;left:{x}px;top:{row_y}px;width:{width}px;height:{row_height}px;'
            f'display:flex;align-items:center;justify-content:space-between">'
            f'<span style="{label_style}">{escape(label)}</span>'
            f'<span style="{value_style}">{escape(right_val)}</span></div>'
        )
    return "".join(html)


def _balance_benefit_grid_elements(elements: list[dict[str, Any]], render_context: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Dynamically balance the heights of current benefits, purchased extras, and available add-ons grids."""
    extras = list((render_context or {}).get("extras") or []) if render_context else []
    extra_shift = (len(extras) + (1 if extras else 0)) * 15.0

    current_cards = list((render_context or {}).get("current_benefits") or []) if render_context else []
    addon_cards = list((render_context or {}).get("available_addons") or []) if render_context else []

    # Separate true FOC benefits from purchased extras / priced add-ons
    extras_cards = [c for c in current_cards if c.get("badge") or c.get("price") or c.get("cost_status") == "paid"]
    foc_cards = [c for c in current_cards if not (c.get("badge") or c.get("price") or c.get("cost_status") == "paid")] if extras_cards else current_cards

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

    hdr_h = 26.0
    gap = 10.0
    pad = 4.0

    has_explicit_extras_grid = any(e.get("gridKind") in {"extras", "purchased_extras"} for e in elements)
    has_extras_section = has_explicit_extras_grid and len(extras_cards) > 0

    cols = max(1, int(grid1.get("columns") or 3)) if grid1 else 3
    is_minimal = bool(grid1 and (grid1.get("benefitPreset") == "compact-minimal" or grid1.get("cardStyle") == "minimal"))
    default_row_height = 40.0 if is_minimal else (72.0 if cols == 2 else 68.0)
    addon_row_height = 40.0 if is_minimal else (88.0 if cols == 2 else 84.0)
    card_gap = 5.0

    if has_extras_section:
        n1 = len(foc_cards)
        n_ext = len(extras_cards)
        n2 = len(addon_cards)

        rows1 = max(1, (n1 + cols - 1) // cols) if n1 > 0 else 0
        rows_ext = max(1, (n_ext + cols - 1) // cols) if n_ext > 0 else 0
        rows2 = max(1, (n2 + cols - 1) // cols) if n2 > 0 else 0

        h1 = rows1 * default_row_height + max(0, rows1 - 1) * card_gap if rows1 > 0 else 40.0
        h_ext = rows_ext * addon_row_height + max(0, rows_ext - 1) * card_gap if rows_ext > 0 else 40.0
        h2 = rows2 * addon_row_height + max(0, rows2 - 1) * card_gap if rows2 > 0 else 40.0

        y_g1 = y_top + hdr_h + pad
        y_h_ext = y_g1 + h1 + gap
        y_g_ext = y_h_ext + hdr_h + pad
        y_h2 = y_g_ext + h_ext + gap
        y_g2 = y_h2 + hdr_h + pad

        grid_bottom = y_g2 + h2
        footer_shift = grid_bottom + 24.0 - 1050.0 if grid_bottom > 1020.0 else 0.0

        adjusted_elements = []
        for elem in elements:
            e = dict(elem)
            eid = e.get("id")
            if (eid in {"cov_table_bg", "premium_info_block"} or e.get("type") == "premium-info-block") and extra_shift > 0:
                e["h"] = float(e.get("h") or (246 if eid == "cov_table_bg" else 132)) + extra_shift
            elif eid == "specials_header_bg" and hdr1_bg:
                e["y"] = y_top
                e["h"] = hdr_h
            elif eid == "specials_header_txt" and hdr1_txt:
                e["y"] = y_top + 5
            elif e.get("type") == "benefit-grid" and e.get("gridKind") == "current_benefits":
                e["y"] = y_g1
                e["h"] = h1
                adjusted_elements.append(e)
                # Insert Extras section right after current_benefits_grid
                adjusted_elements.append({
                    "id": "extras_header_bg",
                    "type": "rectangle",
                    "x": 40,
                    "y": y_h_ext,
                    "w": 714,
                    "h": hdr_h,
                    "z": 2,
                    "style": {"background": "#1E293B", "borderWidth": 0, "borderColor": "transparent", "borderRadius": 4},
                })
                adjusted_elements.append({
                    "id": "extras_header_txt",
                    "type": "text",
                    "text": "Purchased Extras & Add-ons / 特别附加项目",
                    "x": 52,
                    "y": y_h_ext + 5,
                    "w": 690,
                    "h": 16,
                    "z": 5,
                    "style": {"fontSize": 10.5, "fontWeight": "700", "color": "#FFFFFF", "textAlign": "left"},
                })
                adjusted_elements.append({
                    "id": "extras_grid",
                    "type": "benefit-grid",
                    "gridKind": "extras",
                    "x": 40,
                    "y": y_g_ext,
                    "w": 714,
                    "h": h_ext,
                    "z": 4,
                    "benefitPreset": grid1.get("benefitPreset"),
                    "layoutMode": grid1.get("layoutMode"),
                    "columns": cols,
                    "cardStyle": grid1.get("cardStyle") or "standard",
                    "textDensity": grid1.get("textDensity") or "compact",
                    "emptyState": "hide",
                })
                continue
            elif eid == "addons_header_bg" and hdr2_bg:
                e["y"] = y_h2
                e["h"] = hdr_h
            elif eid == "addons_header_txt" and hdr2_txt:
                e["y"] = y_h2 + 5
            elif e.get("type") == "benefit-grid" and e.get("gridKind") == "available_addons":
                e["y"] = y_g2
                e["h"] = h2
            elif footer_shift > 0.0 and (float(e.get("y") or 0) >= 1050.0 or str(eid or "").startswith("footer") or str(eid or "").startswith("tc_")):
                e["y"] = float(e.get("y") or 1068.0) + footer_shift
            adjusted_elements.append(e)
        return adjusted_elements

    # Standard 2-section layout when no extras exist
    n1 = len(current_cards)
    n2 = len(addon_cards)

    rows1 = max(1, (n1 + cols - 1) // cols) if n1 > 0 else 0
    rows2 = max(1, (n2 + cols - 1) // cols) if n2 > 0 else 0

    h1 = rows1 * default_row_height + max(0, rows1 - 1) * card_gap if rows1 > 0 else 40.0
    h2 = rows2 * addon_row_height + max(0, rows2 - 1) * card_gap if rows2 > 0 else 40.0

    y_g1 = y_top + hdr_h + pad
    y_h2 = y_g1 + h1 + gap
    y_g2 = y_h2 + hdr_h + pad

    grid_bottom = y_g2 + h2
    footer_shift = grid_bottom + 24.0 - 1050.0 if grid_bottom > 1020.0 else 0.0

    adjusted_elements = []
    for elem in elements:
        e = dict(elem)
        eid = e.get("id")
        if (eid in {"cov_table_bg", "premium_info_block"} or e.get("type") == "premium-info-block") and extra_shift > 0:
            e["h"] = float(e.get("h") or (246 if eid == "cov_table_bg" else 132)) + extra_shift
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
        elif footer_shift > 0.0 and (float(e.get("y") or 0) >= 1050.0 or str(eid or "").startswith("footer") or str(eid or "").startswith("tc_")):
            e["y"] = float(e.get("y") or 1068.0) + footer_shift
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
        return _image_html(element, config, fields, resolved_assets, db)
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
    
    max_element_y = 0
    for elem in balanced:
        elem_bottom = float(elem.get("y") or 0) + float(elem.get("h") or 0)
        if elem_bottom > max_element_y:
            max_element_y = elem_bottom
            
    # Auto-expand height only if elements strictly exceed A4 base height
    if max_element_y + 30 > height:
        height = int(max_element_y + 30)

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
