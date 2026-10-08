"""Benefit Grid rendering and balancing logic."""

from __future__ import annotations

import re
import math
from html import escape
from typing import Any

from app.rendering.grid_layout import GridBounds, GridSpec, pack_fixed_grid

# Lazy imports to avoid circular dependencies
def _get_helpers():
    from app.rendering.template_renderer import _style, _image_html, _value, _is_paid_extra, _is_core_motor_cover, _variant_card, _benefit_section, GRID_TEXT_DENSITIES, GRID_CARD_STYLES
    return _style, _image_html, _value, _is_paid_extra, _is_core_motor_cover, _variant_card, _benefit_section, GRID_TEXT_DENSITIES, GRID_CARD_STYLES

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
        current = [c for c in list(render_context.get("current_benefits") or []) if not _get_helpers()[4](c)]
        cards = [c for c in current if _get_helpers()[3](c)]
    else:
        current = [c for c in list(render_context.get("current_benefits") or []) if not _get_helpers()[4](c)]
        v4_mode = (
            bool(render_context.get("v4_mode"))
            or bool(element.get("v4_mode"))
            or any(e.get("v4_mode") for e in (render_context.get("template_config", {}).get("canvas", {}).get("elements") or []))
        )
        extras_mode = str(render_context.get("extras_mode") or "itemized").lower()
        if element.get("excludeExtras") or (not v4_mode and extras_mode in {"none", "lump_sum"}):
            cards = [c for c in current if not _get_helpers()[3](c)]
        else:
            cards = current
    groups = list(render_context.get("groups") or []) if kind in {"current_benefits", "extras", "purchased_extras"} else []
    group_by_id = {str(item.get("plan_id")): item for item in groups if item.get("plan_id")}
    disp_opts = (
        render_context.get("display_options")
        or (render_context.get("draft") or {}).get("display_options")
        or (render_context.get("template_config") or {}).get("display_options")
        or {}
    )
    visible_cards = []
    for card in cards:
        disp_ovr = card.get("display_overrides") or {}
        def get_vis(key, default_val=True):
            if disp_ovr:
                if disp_ovr.get("enabled"):
                    if key in disp_ovr:
                        return bool(disp_ovr[key])
                    # If hard display override is enabled on the concept, any visibility flag not explicitly false defaults to True
                    if key in {"showGroup", "showAsset", "showTitle", "showCoverage", "showCost", "showDescription", "isVisible"}:
                        return True
                if disp_ovr.get(key) is False:
                    return False
            sec_vis_map = element.get("sectionVisibility")
            if sec_vis_map and isinstance(sec_vis_map, dict):
                is_extra = bool(card.get("is_extra") or (card.get("cost_status") == "paid" and kind in {"current_benefits", "extras", "purchased_extras"}) or card.get("price"))
                sec_key = "optionalAddons" if kind == "available_addons" else ("addedAddons" if is_extra else "default")
                sec_vis = sec_vis_map.get(sec_key)
                if sec_vis and isinstance(sec_vis, dict):
                    if key in {"showGroup", "showTitle"} and "showTitle" in sec_vis:
                        return bool(sec_vis["showTitle"])
                    if key in sec_vis:
                        return bool(sec_vis[key])
            if disp_opts.get("enabled") is not False:
                cat = "addon" if card.get("is_addon") else "default"
                cat_opts = disp_opts.get(cat) or {}
                if key in cat_opts:
                    return cat_opts[key]
                if key in disp_opts:
                    return disp_opts[key]
            return default_val
        if not get_vis("isVisible", True):
            continue
        card["_showCoverage"] = get_vis("showCoverage", True)
        card["_showDescription"] = get_vis("showDescription", True)
        card["_showCost"] = get_vis("showCost", True)
        card["_showAsset"] = get_vis("showAsset", True)
        card["_showGroup"] = get_vis("showGroup", True) and get_vis("showTitle", True)
        visible_cards.append(card)
    cards = visible_cards
    ordered = cards
    if groups:
        free = [card for card in cards if not str(card.get("group_id") or "") or not card.get("_showGroup", True)]
        members: dict[str, list[dict]] = {}
        for card in cards:
            group_id = str(card.get("group_id") or "") if card.get("_showGroup", True) else ""
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
    if bounds.width <= 0 or bounds.height <= 0:
        return ""
    custom_icon_size = float(element.get("iconSize") or 0)
    ref_h = max(float(packing.get("referenceHeight") or 50), (custom_icon_size + 18) if custom_icon_size > 0 else 50)
    spec = GridSpec(
        strategy=str(packing.get("strategy") or "balanced"),
        alignment=str(packing.get("alignment") or "center"),
        aspect_ratio=float(packing.get("aspectRatio") or 4.5),
        reference_width=float(packing.get("referenceWidth") or 226),
        reference_height=ref_h,
        gap_ratio=float(packing["gapRatio"]) if packing.get("gapRatio") is not None else 0.04,
        padding_ratio=float(packing["paddingRatio"]) if packing.get("paddingRatio") is not None else 0.02,
        stagger_ratio=float(packing.get("staggerRatio") or 0.0),
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
    density = _get_helpers()[7].get(density_name, _get_helpers()[7]["compact"])
    card_style_css = _get_helpers()[8].get(card_style_name, _get_helpers()[8]["standard"])

    output: list[str] = []
    group_rects: dict[str, list[tuple[float, float, float, float]]] = {}

    def _build_card_html(card: dict, px: float, py: float, pw: float, ph: float, scale: float, extra_style: str = "") -> str:
        group_id_c = str(card.get("group_id") or "")
        if group_id_c and group_id_c in group_by_id:
            group_rects.setdefault(group_id_c, []).append((px, py, pw, ph))

        label_str = escape(str(card.get("label") or ""))
        value_str = escape(str(card.get("value") or ""))
        desc_str = escape(str(card.get("description") or card.get("short_description") or ""))
        asset_id_c = str(card.get("asset_id") or "")
        concept_key_c = str(card.get("concept_key") or card.get("concept_id") or "")
        label_lower = str(card.get("label") or "").lower().strip()
        asset_uri_c = (
            resolved_assets.get(asset_id_c)
            or resolved_assets.get(concept_key_c)
            or str(card.get("asset_url") or "")
            or resolved_assets.get(label_lower)
            or ""
        )
        if not asset_uri_c and label_lower:
            for k, uri in resolved_assets.items():
                if k and len(k) >= 4 and (k in label_lower or label_lower in k):
                    asset_uri_c = uri
                    break

        is_purchased_extra = bool(card.get("is_extra") or (card.get("cost_status") == "paid" and kind == "current_benefits"))
        is_dark = element.get("benefitPreset") == "dark-signature"
        is_minimal = element.get("benefitPreset") == "compact-minimal" or element.get("cardStyle") == "minimal"
        is_elevated = element.get("benefitPreset") == "elevated-3d" or element.get("cardStyle") == "soft"
        is_grid_tile = element.get("benefitPreset") == "grid-tile" or element.get("cardStyle") == "outlined"

        shape = str(element.get("shape") or "")
        radius_map = {
            "racetrack": "999px",
            "oval": "24px / 14px",
            "soft": "12px",
            "square": "0px",
            "rounded": "8px",
        }
        card_radius = radius_map.get(shape, "6px")

        elevation = str(element.get("elevation") or "")
        elevation_shadow = (
            "box-shadow:0 4px 12px rgba(0,0,0,0.08);" if elevation == "shadow"
            else ("box-shadow:0 8px 20px rgba(0,0,0,0.12);" if elevation == "lift" else "")
        )

        bg_col = element.get("bgColor")
        border_col = element.get("borderColor")
        border_w = element.get("borderWidth")
        border_s = element.get("borderStyle") or "solid"

        if border_col or bg_col or border_w is not None:
            bw = f"{border_w}px" if border_w is not None else "1px"
            bc = border_col or "#E2E8F0"
            bg = bg_col or "#FFFFFF"
            card_border_css = f"border:{bw} {border_s} {bc};background:{bg};{elevation_shadow}"
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

        custom_icon_size = float(element.get("iconSize") or 0)
        target_row_h = float(element.get("targetRowHeight") or 0)
        if custom_icon_size > 0:
            icon_sz = min(60.0, max(14.0, custom_icon_size))
            pad = 2 if is_minimal else (3 if icon_sz <= 24 else 4)
            lbl_fs = (density["label"] - 0.5) if is_minimal else density["label"]
            val_fs = density["value"]
            desc_fs = density["desc"]
        elif target_row_h > 0:
            if target_row_h < 46.0:
                pad = 2
                icon_sz = min(16.0, max(12.0, target_row_h * 0.35))
                lbl_fs = 8.5
                val_fs = 8.5
                desc_fs = 7.0
            elif target_row_h < 64.0:
                pad = 3
                icon_sz = min(20.0, max(15.0, target_row_h * 0.35))
                lbl_fs = 9.0
                val_fs = 9.0
                desc_fs = 7.5
            else:
                pad = 4
                icon_sz = min(24.0, max(18.0, target_row_h * 0.35))
                lbl_fs = min(10.0, (density["label"] - 0.5) if is_minimal else density["label"])
                val_fs = min(10.0, density["value"])
                desc_fs = min(8.0, density["desc"])
        else:
            pad = 3 if is_minimal else density["padding"]
            icon_sz = (density["icon"] - 2) if is_minimal else density["icon"]
            lbl_fs = (density["label"] - 0.5) if is_minimal else density["label"]
            val_fs = density["value"]
            desc_fs = density["desc"]

        uniform_h = float(element.get("uniformHeight") or 0)
        h_style = f"min-height:{uniform_h}px;" if uniform_h > 0 else ""

        title_sz = element.get("titleSize")
        if title_sz is not None:
            try:
                lbl_fs = float(title_sz)
            except (ValueError, TypeError):
                pass
        elif target_row_h > 0:
            if target_row_h < 46.0:
                lbl_fs = min(lbl_fs, 8.5)
            elif target_row_h < 64.0:
                lbl_fs = min(lbl_fs, 9.5)

        cov_sz = element.get("coverageSize")
        if cov_sz is not None:
            try:
                val_fs = float(cov_sz)
            except (ValueError, TypeError):
                pass

        desc_sz = element.get("descSize")
        if desc_sz is not None:
            try:
                desc_fs = float(desc_sz)
            except (ValueError, TypeError):
                pass

        title_color = escape(str(element.get("titleColor") or element.get("textColor") or ("#FFFFFF" if is_dark else "#0F172A")))
        desc_color = escape(str(element.get("descColor") or ("#94A3B8" if is_dark else "#64748B")))
        val_color = escape(str(element.get("coverageColor") or ("#F8FAFC" if is_dark else "#0F172A")))

        # --- Image cell (bottom-left) ---
        pad_shape = str(element.get("iconPadShape") or "")
        icon_radius = "999px" if (pad_shape == "circle" or is_grid_tile) else ("6px" if pad_shape == "box" else ("0px" if pad_shape == "none" else "4px"))
        img_fit = escape(str(element.get("imageFit") or "contain"))

        if not card.get("_showAsset", True):
            image_html = ""
        elif asset_uri_c:
            image_html = (
                f'<img alt="" src="{escape(asset_uri_c)}" '
                f'style="width:{icon_sz}px;height:{icon_sz}px;object-fit:{img_fit};display:block;flex-shrink:0;border-radius:{icon_radius}" />'
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
        if cov_limit and (re.search(r"\d", str(cov_limit)) or str(cov_limit).strip().lower() == "unlimited"):
            value_str = str(cov_limit) if str(cov_limit).startswith("RM") or not any(c.isdigit() for c in str(cov_limit)) else f"RM {cov_limit}"
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

        # Strict validation: value_str must have digits or be 'unlimited'
        is_valid_cov = bool(value_str and (re.search(r"\d", value_str) or value_str.strip().lower() == "unlimited"))
        if is_valid_cov and value_str.lower() in {"included standard cover", "included", "foc", "as quoted", "selected", "optional"}:
            is_valid_cov = False
            value_str = ""

        show_value = is_valid_cov and card.get("_showCoverage", True)
        coverage_html = (
            f'<span style="display:block;font-size:{val_fs}px;font-weight:700;line-height:1.15;'
            f'color:{val_color};overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{value_str}</span>'
            if show_value else ""
        )

        # --- Short description row ---
        desc_weight = "700" if element.get("descWeight") == "bold" else ("600" if element.get("descWeight") == "semibold" else ("500" if element.get("descWeight") == "medium" else "400"))
        desc_max_lines = int(element.get("descMaxLines") or element.get("descLines") or 4)
        if target_row_h > 0:
            if target_row_h < 46.0:
                desc_max_lines = 0
            elif target_row_h < 64.0:
                desc_max_lines = min(1, desc_max_lines)
            else:
                desc_max_lines = min(2, desc_max_lines)

        clamp_css = f"-webkit-line-clamp:{desc_max_lines};display:-webkit-box;-webkit-box-orient:vertical;" if desc_max_lines > 0 else "display:block;"
        desc_max_h = max(55.0, desc_fs * (desc_max_lines + 1.0)) if desc_max_lines > 0 else 999.0
        desc_html = (
            f'<span style="font-size:{desc_fs}px;font-weight:{desc_weight};line-height:1.2;color:{desc_color};'
            f'max-height:{desc_max_h}px;overflow:hidden;{clamp_css}">'
            f'{desc_str}</span>'
            if (desc_str and not is_minimal and desc_max_lines > 0 and card.get("_showDescription", True)) else ""
        )

        # --- Cost / price badge ---
        price_badge = ""
        price = card.get("price") or card.get("optional_price")
        is_addon_card = card.get("is_addon") or kind == "available_addons" or is_purchased_extra or bool(card.get("price"))
        if is_addon_card and not card.get("is_pure_default") and card.get("_showCost", True):
            p_val = None
            if price:
                p_val = (price.get("amount") if price.get("amount") is not None else price.get("value")) if isinstance(price, dict) else price
            elif card.get("detected_cost"):
                p_val = card.get("detected_cost")

            cost_fs = max(7.0, desc_fs - 0.5) if (target_row_h > 0 and target_row_h < 50.0) else max(7.5, desc_fs - 0.5)
            badge_pad = "1px 3px" if (target_row_h > 0 and target_row_h < 50.0) else "1px 5px"
            cost_sz = element.get("costSize")
            if cost_sz is not None:
                try:
                    cost_fs = float(cost_sz)
                except (ValueError, TypeError):
                    pass
            badge_bg = escape(str(element.get("costBgColor") or ("#450A0A" if is_dark else "#FEE2E2")))
            badge_fg = escape(str(element.get("costColor") or ("#FCA5A5" if is_dark else "#B91C1C")))
            badge_border = escape("#7F1D1D" if is_dark else ("#FECACA" if not element.get("costBgColor") else badge_bg))

            if p_val is not None and str(p_val).strip() and str(p_val).strip() not in {"0", "0.00", "0.0"}:
                s_val = str(p_val).strip()
                if "%" in s_val or "sum covered" in s_val.lower() or "sum insured" in s_val.lower() or "tariff" in s_val.lower():
                    p_str = ""
                else:
                    try:
                        clean_num = re.sub(r"[^0-9.]", "", s_val)
                        if clean_num and float(clean_num) > 0:
                            p_num = float(clean_num)
                            p_str = f"Cost : MYR {p_num:,.2f}"
                        else:
                            p_str = ""
                    except Exception:
                        clean_pval = s_val.replace("RM ", "").replace("RM", "").strip()
                        if clean_pval and clean_pval.lower() not in {"0", "0.00", "null", "none", "quoted"}:
                            p_str = f"Cost : MYR {clean_pval}"
                        else:
                            p_str = ""
                if p_str:
                    price_badge = (
                        f'<div style="margin-top:2px"><span style="display:inline-block;padding:{badge_pad};border-radius:4px;'
                        f'font-size:{cost_fs}px;font-weight:700;line-height:1.2;white-space:nowrap;'
                        f'background:{badge_bg};color:{badge_fg};border:1px solid {badge_border}">{p_str}</span></div>'
                    )

        # Title font: shrink for long labels
        title_fs = lbl_fs - 1.0 if len(label_str) > 30 else (lbl_fs - 0.5 if len(label_str) > 18 else float(lbl_fs))
        title_margin = 1 if (is_minimal or (target_row_h > 0 and target_row_h < 50.0)) else 3
        text_wrap = str(element.get("textWrap") or "wrap")
        if target_row_h > 0 and target_row_h < 46.0:
            title_wrap_css = "overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:block;"
        elif target_row_h > 0 and target_row_h < 64.0:
            title_wrap_css = "overflow:hidden;display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;word-break:break-word;white-space:normal;"
        elif text_wrap == "truncate":
            title_wrap_css = "overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:block;"
        elif text_wrap == "multi":
            title_wrap_css = "overflow:hidden;display:block;word-break:break-word;white-space:normal;"
        else:
            title_wrap_css = "overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;word-break:break-word;white-space:normal;"

        title_html = (
            f'<div style="font-size:{title_fs}px;font-weight:700;line-height:1.15;'
            f'color:{title_color};{title_wrap_css}'
            f'margin-bottom:{title_margin}px">{label_str}</div>'
            if card.get("_showGroup", True) else ""
        )

        inner_html = (
            # Title row (full width)
            f'{title_html}'
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

        custom_icon_size = float(element.get("iconSize") or 0)
        custom_title_size = float(element.get("titleSize") or 0)
        min_card_needed = max(
            28.0,
            (custom_icon_size + 18.0) if custom_icon_size > 0 else 28.0,
            (custom_title_size + 28.0) if custom_title_size > 0 else 28.0,
        )
        effective_row_h = uniform_h if uniform_h > 0 else (
            max(target_row_h, min_card_needed) if (custom_icon_size > 24 or custom_title_size > 10) else target_row_h
        )
        card_h_css = f"height:{effective_row_h}px;max-height:{effective_row_h}px;overflow:hidden;" if effective_row_h > 0 else ""
        pos_style = f"position:absolute;left:{px:.8f}px;top:{py:.8f}px;width:{pw:.8f}px;height:{ph:.8f}px;" if extra_style == "" else extra_style
        return (
            f'<article data-benefit-card="1" data-card-scale="{scale:.12f}" '
            f'data-card-style="{escape(card_style_name)}" data-text-density="{escape(density_name)}" '
            f'style="{pos_style}{card_h_css}box-sizing:border-box">'
            f'<div style="width:100%;height:100%;{h_style}display:flex;flex-direction:column;'
            f'padding:{pad}px;box-sizing:border-box;border-radius:{card_radius};{card_border_css};overflow:hidden">'
            f'{inner_html}'
            f'</div></article>'
        )

    if layout_mode != "normal":
        # Equal-Height Row System (Non-masonry, Tabular Alignment)
        col_count = max(1, int(element.get("columns") or 3))
        gap = density["gap"]
        row_chunks: list[list[dict[str, Any]]] = [
            ordered[i : i + col_count] for i in range(0, len(ordered), col_count)
        ]

        target_row_h = float(element.get("targetRowHeight") or 0)
        row_h_style = f"height:{target_row_h}px;max-height:{target_row_h}px;overflow:hidden;" if target_row_h > 0 else ""

        rows_html = []
        for row_cards in row_chunks:
            cards_html = []
            for card in row_cards:
                cards_html.append(
                    _build_card_html(
                        card,
                        0,
                        0,
                        0,
                        0,
                        1.0,
                        extra_style=f"flex:1;min-width:0;height:100%;{row_h_style}display:flex;flex-direction:column;box-sizing:border-box;",
                    )
                )
            # Pad partial row with empty flex items to ensure equal column widths
            for _ in range(col_count - len(row_cards)):
                cards_html.append(f'<div style="flex:1;min-width:0;{row_h_style}box-sizing:border-box;"></div>')

            rows_html.append(
                f'<div style="display:flex;flex-direction:row;gap:{gap}px;align-items:stretch;width:100%;{row_h_style}box-sizing:border-box;">'
                f'{"".join(cards_html)}</div>'
            )

        warning = escape(layout.warning or "")
        return (
            f'<section data-grid-kind="{escape(kind)}" data-density-warning="{warning}" '
            f'style="position:absolute;left:{bounds.x:.8f}px;top:{bounds.y:.8f}px;'
            f'width:{bounds.width:.8f}px;display:flex;flex-direction:column;gap:{gap}px;">'
            f'{"".join(rows_html)}</section>'
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


def _balance_benefit_grid_elements(elements: list[dict[str, Any]], render_context: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Dynamically balance the heights of coverage card, right containers, and benefit grids."""
    extras = list((render_context or {}).get("extras") or []) if render_context else []
    pib_elem = next((e for e in elements if e.get("id") == "premium_info_block" or e.get("type") == "premium-info-block"), None)
    extras_mode = str((pib_elem or {}).get("extras_mode") or (render_context or {}).get("extras_mode") or "itemized").lower()
    pib_y = float(pib_elem.get("y") or 276.0) if pib_elem else 276.0
    if extras_mode == "none":
        total_pib_rows = 5
    elif extras_mode == "lump_sum":
        total_pib_rows = 6 if extras else 5
    else:
        if extras:
            extra_rows = min(len(extras), 3) + (1 if len(extras) > 3 else 0)
            total_pib_rows = 6 + extra_rows
        else:
            total_pib_rows = 5
    content_bottom = pib_y + (total_pib_rows * 14.0)
    card_bottom = max(380.0, content_bottom + 12.0)
    cov_elem = next((e for e in elements if e.get("id") == "cov_table_bg"), None)
    cov_table_y = float(cov_elem.get("y") or 120.0) if cov_elem else 120.0
    cov_table_h = card_bottom - cov_table_y
    y_top = card_bottom + 10.0
    drivers_h = 74.0
    drivers_y = card_bottom - drivers_h
    qr_y = 210.0
    qr_h = (drivers_y - 8.0) - qr_y
    qr_center_y = qr_y + qr_h / 2.0
    qr_size = min(90.0, max(70.0, qr_h - 16.0))

    current_cards = [c for c in list((render_context or {}).get("current_benefits") or []) if not _get_helpers()[4](c)] if render_context else []
    addon_cards = list((render_context or {}).get("available_addons") or []) if render_context else []

    # Separate true FOC benefits from purchased extras / priced add-ons
    extras_cards = [c for c in current_cards if _get_helpers()[3](c)]
    foc_cards = [c for c in current_cards if not _get_helpers()[3](c)] if extras_cards else current_cards

    grid1 = next((e for e in elements if e.get("type") == "benefit-grid" and e.get("gridKind") == "current_benefits"), None)
    grid2 = next((e for e in elements if e.get("type") == "benefit-grid" and e.get("gridKind") == "available_addons"), None)
    if not grid1 or not grid2:
        return elements

    hdr1_bg = next((e for e in elements if e.get("id") == "specials_header_bg"), None)
    hdr1_txt = next((e for e in elements if e.get("id") == "specials_header_txt"), None)
    hdr2_bg = next((e for e in elements if e.get("id") == "addons_header_bg"), None)
    hdr2_txt = next((e for e in elements if e.get("id") == "addons_header_txt"), None)

    v4_mode = any(e.get("v4_mode") for e in elements) or bool((render_context or {}).get("v4_mode"))
    hdr_h = 24.0 if v4_mode else 26.0
    gap = 8.0
    pad = 3.0

    if v4_mode:
        has_extras_section = len(extras_cards) > 0
    else:
        has_extras_section = len(extras_cards) > 0 and (extras_mode not in {"none", "lump_sum"})

    cols = max(1, int(grid1.get("columns") or 3)) if grid1 else 3
    is_minimal = bool(grid1 and (grid1.get("benefitPreset") == "compact-minimal" or grid1.get("cardStyle") == "minimal"))
    custom_icon_size = float(grid1.get("iconSize") or 0) if grid1 else 0.0
    dynamic_icon_extra = max(0.0, custom_icon_size - 24.0) if custom_icon_size > 24.0 else 0.0

    desc_sz = float(grid1.get("descSize") or 8.0) if grid1 else 8.0
    has_desc = grid1.get("showDescription") is not False if grid1 else True
    has_cov = grid1.get("showCoverage") is not False if grid1 else True

    desc_max_lines = int(grid1.get("descMaxLines") or grid1.get("descLines") or 4) if grid1 else 4
    text_wrap = str(grid1.get("textWrap") or "wrap") if grid1 else "wrap"
    extra_title_h = 10.0 if text_wrap == "multi" else 0.0
    extra_desc_h = max(0.0, (desc_max_lines - 4) * 12.0) if has_desc else 0.0

    footer_elem = next((e for e in elements if e.get("id") == "footer_terms" or str(e.get("id") or "").startswith("footer") or str(e.get("id") or "").startswith("tc_")), None)
    footer_y = float(footer_elem.get("y") or 1068.0) if footer_elem else 1068.0
    safe_bottom = max(y_top + 160.0, footer_y - 14.0)
    available_h = safe_bottom - y_top

    items1 = foc_cards if has_extras_section else current_cards
    items_ext = extras_cards if has_extras_section else []
    items2 = addon_cards

    n1 = len(items1)
    n_ext = len(items_ext)
    n2 = len(items2)
    total_cards = n1 + n_ext + n2

    base_cols = max(1, int(grid1.get("columns") or 3))
    effective_cols = base_cols
    extras_cols = min(2, effective_cols) if n_ext <= 2 else effective_cols

    rows1 = (n1 + effective_cols - 1) // effective_cols if n1 > 0 else 0
    rows_ext = (n_ext + extras_cols - 1) // extras_cols if (has_extras_section and n_ext > 0) else 0
    rows2 = (n2 + effective_cols - 1) // effective_cols if n2 > 0 else 0

    active_sections = (1 if rows1 > 0 else 0) + (1 if rows_ext > 0 else 0) + (1 if rows2 > 0 else 0)
    effective_sections = max(1, active_sections)
    total_rows = max(1, rows1 + rows_ext + rows2)

    card_gap = 4.5 if v4_mode else 5.0
    total_headers_h = (effective_sections * (hdr_h + pad)) + (max(0, effective_sections - 1) * gap)
    cards_avail_h = max(60.0, available_h - total_headers_h)
    total_row_gaps = (max(0, rows1 - 1) + max(0, rows_ext - 1) + max(0, rows2 - 1)) * card_gap
    pure_cards_h = max(40.0, cards_avail_h - total_row_gaps)

    raw_row_h = pure_cards_h / float(total_rows)

    if v4_mode:
        custom_icon_sz = float(grid1.get("iconSize") or 0) if grid1 else 0.0
        custom_title_sz = float(grid1.get("titleSize") or 0) if grid1 else 0.0
        uniform_h = float(grid1.get("uniformHeight") or grid1.get("rowHeight") or 0) if grid1 else 0.0
        min_card_needed = max(
            28.0,
            (custom_icon_sz + 18.0) if custom_icon_sz > 0 else 28.0,
            (custom_title_sz + desc_sz + 20.0) if custom_title_sz > 0 else 28.0,
        )
        if uniform_h > 0:
            target_row_h = uniform_h
        elif custom_icon_sz > 24 or custom_title_sz > 10:
            target_row_h = max(min_card_needed, raw_row_h)
        else:
            target_row_h = min(38.0, max(28.0, raw_row_h)) if is_minimal else min(52.0, max(28.0, raw_row_h))
        h1 = (rows1 * target_row_h + max(0, rows1 - 1) * card_gap) if rows1 > 0 else float(grid1.get("h") or 40.0)
        h_ext = (rows_ext * target_row_h + max(0, rows_ext - 1) * card_gap) if (has_extras_section and rows_ext > 0) else 40.0
        h2 = (rows2 * target_row_h + max(0, rows2 - 1) * card_gap) if rows2 > 0 else float(grid2.get("h") or 40.0)
    else:
        target_row_h = 0.0
        default_row_height = (
            36.0 if is_minimal
            else (
                max(74.0 if cols == 2 else 74.0, 44.0 + dynamic_icon_extra + (16.0 if has_desc else 0.0) + (8.0 if has_cov else 0.0)) + extra_title_h + extra_desc_h
                if has_desc
                else max(42.0, 34.0 + dynamic_icon_extra + (8.0 if has_cov else 0.0)) + extra_title_h
            )
        )
        addon_row_height = (
            36.0 if is_minimal
            else (
                max(84.0 if cols == 2 else 84.0, 38.0 + dynamic_icon_extra + (8.0 if has_cov else 0.0) + (12.0 if has_desc else 0.0) + 12.0) + extra_title_h + extra_desc_h
                if has_desc
                else max(50.0, 38.0 + dynamic_icon_extra + 12.0) + extra_title_h
            )
        )
        h1 = (rows1 * default_row_height + max(0, rows1 - 1) * card_gap) if rows1 > 0 else 0.0
        h_ext = (rows_ext * addon_row_height + max(0, rows_ext - 1) * card_gap) if (has_extras_section and rows_ext > 0) else 0.0
        h2 = (rows2 * addon_row_height + max(0, rows2 - 1) * card_gap) if rows2 > 0 else 0.0

    # Magnetic sequential positioning — each section starts strictly after previous section ends
    cur_y = y_top

    y_hdr1 = 0.0
    y_g1 = 0.0
    bottom1 = 0.0
    if n1 > 0:
        y_hdr1 = cur_y
        y_g1 = y_hdr1 + hdr_h + pad
        bottom1 = y_g1 + h1
        cur_y = bottom1 + gap

    y_hdr_ext = 0.0
    y_g_ext = 0.0
    bottom_ext = 0.0
    if has_extras_section and n_ext > 0:
        y_hdr_ext = cur_y
        y_g_ext = y_hdr_ext + hdr_h + pad
        bottom_ext = y_g_ext + h_ext
        cur_y = bottom_ext + gap

    y_hdr2 = 0.0
    y_g2 = 0.0
    bottom2 = cur_y
    if n2 > 0:
        y_hdr2 = cur_y
        y_g2 = y_hdr2 + hdr_h + pad
        bottom2 = y_g2 + h2

    footer_shift = ((bottom2 + 24.0 - 1050.0) if bottom2 > 1020.0 else 0.0) if not v4_mode else 0.0

    def _adjust_common(e: dict[str, Any]) -> dict[str, Any]:
        eid = e.get("id")
        if eid == "cov_table_bg":
            e["h"] = cov_table_h
        elif eid == "payment_account_details_img" and not any(x.get("id") == "all_driver_bg" for x in elements):
            e["h"] = card_bottom - float(e.get("y") or 94.0)
        elif eid == "premium_info_block" or e.get("type") == "premium-info-block":
            e["h"] = total_pib_rows * 14.0
        elif eid == "rc_container_payment":
            e["y"] = 134.0
            e["h"] = 68.0
        elif eid == "rc_b_pay_title":
            e["y"] = 143.0
            e["h"] = 14.0
        elif eid == "rc_b_pay_details":
            e["x"] = 517.0
            e["y"] = 160.0
            e["w"] = 150.0
            e["h"] = 28.0
        elif eid == "rc_b_bank_logo":
            e["x"] = 672.0
            e["y"] = 160.0
            e["w"] = 72.0
            e["h"] = 28.0
        elif eid == "rc_container_qr":
            e["y"] = qr_y
            e["h"] = qr_h
        elif eid == "rc_b_qr_code":
            e["x"] = 516.0
            e["y"] = qr_center_y - (qr_size / 2.0)
            e["w"] = qr_size
            e["h"] = qr_size
        elif eid == "rc_b_qr_text":
            text_x = 516.0 + qr_size + 8.0
            e["x"] = text_x
            e["y"] = qr_center_y - 27.0
            e["w"] = 746.0 - text_x
            e["h"] = 54.0
        elif eid == "rc_container_drivers":
            e["y"] = drivers_y
            e["h"] = drivers_h
        elif eid == "rc_b_driver_title":
            e["y"] = drivers_y + 8.0
        elif eid == "rc_b_driver_sub":
            e["y"] = drivers_y + 24.0
        elif eid == "rc_b_driver_divider":
            e["y"] = drivers_y + 42.0
        elif eid == "rc_b_excess_val":
            e["y"] = drivers_y + 48.0
        return e

    adjusted_elements = []
    for elem in elements:
        e = dict(elem)
        eid = e.get("id")
        e = _adjust_common(e)
        if eid == "specials_header_bg" and hdr1_bg:
            if n1 == 0:
                e["h"] = 0
                e["style"] = {**(e.get("style") or {}), "opacity": 0, "borderWidth": 0}
            else:
                e["y"] = y_hdr1
                e["h"] = hdr_h
        elif eid == "specials_header_txt" and hdr1_txt:
            if n1 == 0:
                e["text"] = ""
            else:
                e["y"] = y_hdr1 + 5
        elif e.get("type") == "benefit-grid" and e.get("gridKind") == "current_benefits":
            e["y"] = y_g1
            e["h"] = h1
            e["columns"] = effective_cols
            e["targetRowHeight"] = target_row_h
            if has_extras_section:
                e["excludeExtras"] = True
            adjusted_elements.append(e)

            if has_extras_section and n_ext > 0:
                adjusted_elements.append({
                    "id": "extras_header_bg",
                    "type": "rectangle",
                    "x": float(grid1.get("x") or 40),
                    "y": y_hdr_ext,
                    "w": float(grid1.get("w") or 714),
                    "h": hdr_h,
                    "z": 2,
                    "style": {"background": "#1E293B", "borderWidth": 0, "borderColor": "transparent", "borderRadius": 4},
                })
                adjusted_elements.append({
                    "id": "extras_header_txt",
                    "type": "text",
                    "text": "Purchased Extras & Add-ons / 已附加特别项目",
                    "x": float(grid1.get("x") or 40) + 12,
                    "y": y_hdr_ext + 5,
                    "w": float(grid1.get("w") or 714) - 24,
                    "h": 16,
                    "z": 5,
                    "style": {"fontSize": 10.5, "fontWeight": "700", "color": "#FFFFFF", "textAlign": "left"},
                })
                extras_elem = dict(grid1)
                extras_elem.update({
                    "id": "extras_grid",
                    "type": "benefit-grid",
                    "gridKind": "extras",
                    "x": float(grid1.get("x") or 40),
                    "y": y_g_ext,
                    "w": float(grid1.get("w") or 714),
                    "h": h_ext,
                    "z": 4,
                    "columns": extras_cols,
                    "targetRowHeight": target_row_h,
                    "emptyState": "hide",
                })
                adjusted_elements.append(extras_elem)
            continue
        elif eid == "addons_header_bg" and hdr2_bg:
            if n2 == 0:
                e["h"] = 0
                e["style"] = {**(e.get("style") or {}), "opacity": 0, "borderWidth": 0}
            else:
                e["y"] = y_hdr2
                e["h"] = hdr_h
        elif eid == "addons_header_txt" and hdr2_txt:
            if n2 == 0:
                e["text"] = ""
            else:
                e["y"] = y_hdr2 + 5
        elif e.get("type") == "benefit-grid" and e.get("gridKind") == "available_addons":
            e["y"] = y_g2
            e["h"] = h2
            e["columns"] = effective_cols
            e["targetRowHeight"] = target_row_h
        elif footer_shift > 0.0 and (float(e.get("y") or 0) >= 1050.0 or str(eid or "").startswith("footer") or str(eid or "").startswith("tc_")):
            e["y"] = float(e.get("y") or 1068.0) + footer_shift
        adjusted_elements.append(e)

    return adjusted_elements


