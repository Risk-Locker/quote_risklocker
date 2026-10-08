"""Deterministic HTML/CSS rendering for Risklocker quotation PDFs."""

from __future__ import annotations

import json
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
    "engine_cc": "Engine Capacity",
    "ncd_percent": "NCD",
    "valuation_type": "Valuation Type",
    "coverage_amount": "Coverage",
    "excess_amount": "Policy Excess",
    "compulsory_excess": "Compulsory Excess",
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
    "valuation_type": ("valuation_basis", "sum_insured_type", "basis_of_sum_insured"),
    "roadtax": ("road_tax_amount",),
    "road_tax_amount": ("roadtax",),
    "service_fee": ("runner_fee",),
    "runner_fee": ("service_fee",),
    "ncd_percent": ("ncd_percentage",),
    "ncd_percentage": ("ncd_percent",),
    "total_amount": ("total_premium_adjusted", "gross_premium"),
    "total_premium_adjusted": ("total_amount", "gross_premium"),
    "engine_cc": ("vehicle_cc", "engine_capacity", "cubic_capacity"),
    "excess_amount": ("policy_excess", "excess", "lebihan", "ekses", "ekses_polisi"),
    "compulsory_excess": ("compulsory_excess_amount", "ekses_wajib", "ekses_mandatori"),
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
            if not val and (variable_id in {"excess_amount", "excess", "compulsory_excess"} or variable.get("field") in {"excess_amount", "excess", "compulsory_excess"}):
                return "0.00"
            if not val and (variable_id in {"authorized_driver", "authorised_driver"} or variable.get("field") in {"authorized_driver", "authorised_driver"}):
                try:
                    fstr = json.dumps(fields, default=str).lower()
                    if "named driver" in fstr or "named_driver" in fstr:
                        return "Named Driver"
                except Exception:
                    pass
                return "All Driver"
            return val
    val = _value(fields, variable_id)
    if not val and variable_id in {"excess_amount", "excess", "compulsory_excess"}:
        return "0.00"
    if not val and variable_id in {"authorized_driver", "authorised_driver"}:
        try:
            fstr = json.dumps(fields, default=str).lower()
            if "named driver" in fstr or "named_driver" in fstr:
                return "Named Driver"
        except Exception:
            pass
        return "All Driver"
    return val


def _format_value(value: Any, prefix: str = "", suffix: str = "") -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        value = f"{float(value):,.2f}"
    else:
        value = str(value).strip()
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
    op_val = element.get("opacity")
    if op_val is not None:
        css.append(f"opacity:{float(op_val)}")
    return ";".join(css)


SYSTEM_DEFAULT_SLOTS = {
    "risklocker_logo": "e9685e1f-ac95-410c-a2e9-eccb7ca35d5f",
    "bank_logo": "2168eaee-3e56-4903-8c4f-841f01ff2407",
    "all_driver_icon": "91116a7dc3540d62",
    "background": "49e754a6faa949c2",
    "qr_code": "c4003185-0000-4000-8000-000000000001",
    "duitnow_payment_details": "c4003185-0000-4000-8000-000000000001",
    "bank_qr_layout": "c4003185-0000-4000-8000-000000000001",
    "bank_qr_layout_dark": "c4003185-0000-4000-8000-000000000001",
}


def _asset_id_for_slot(config: dict[str, Any], slot: str | None, fields: dict, db: Any = None) -> str:
    if not slot:
        return ""
    assets = config.get("assets") or {}
    if assets.get(slot):
        return str(assets[slot])
    if slot in SYSTEM_DEFAULT_SLOTS:
        return SYSTEM_DEFAULT_SLOTS[slot]
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
    return find_asset_by_hint(db, [str(item) for item in hints])


def _image_html(
    element: dict[str, Any],
    config: dict[str, Any],
    fields: dict,
    resolved_assets: dict[str, str] | None = None,
    db: Any = None,
) -> str:
    slot = element.get("assetSlot")
    eid = element.get("id") or ""
    if not slot:
        if eid in {"risklocker_logo", "pay_holder", "text_ltaa394"}:
            slot = "risklocker_logo"
        elif eid in {"bank_logo", "pay_bank_logo", "pay_bank_sub", "text_ul2w5ka"}:
            slot = "bank_logo"
        elif eid in {"driver_icon", "all_driver_icon"}:
            slot = "all_driver_icon"
        elif eid in {"rc_b_qr_code", "qr_code", "qr", "bank_qr_layout", "bank_qr_layout_dark", "rc_b_duitnow_img", "duitnow_img", "duitnow_card", "payment_account_details_img"}:
            slot = "bank_qr_layout_dark"

    asset_id = str(element.get("assetId") or _asset_id_for_slot(config, slot, fields, db))
    if (not asset_id or asset_id == "None") and slot in SYSTEM_DEFAULT_SLOTS:
        asset_id = SYSTEM_DEFAULT_SLOTS[slot]
    
    if not asset_id or asset_id == "None":
        if slot in SYSTEM_DEFAULT_SLOTS:
            asset_id = SYSTEM_DEFAULT_SLOTS[slot]
        elif eid in SYSTEM_DEFAULT_SLOTS:
            asset_id = SYSTEM_DEFAULT_SLOTS[eid]
        elif eid in {"pay_holder", "text_ltaa394"}:
            asset_id = SYSTEM_DEFAULT_SLOTS["risklocker_logo"]
        elif eid in {"pay_bank_logo", "pay_bank_sub", "text_ul2w5ka"}:
            asset_id = SYSTEM_DEFAULT_SLOTS["bank_logo"]
        elif eid in {"rc_b_qr_code", "qr_code", "qr"}:
            asset_id = SYSTEM_DEFAULT_SLOTS["qr_code"]
        elif eid in {"rc_b_duitnow_img", "duitnow_img", "duitnow_card", "payment_account_details_img"}:
            asset_id = SYSTEM_DEFAULT_SLOTS["duitnow_payment_details"]

    if resolved_assets is not None:
        src = resolved_assets.get(asset_id, "")
    else:
        src = asset_data_uri(db, asset_id)
    if not src:
        # Preserve the authored geometry when an optional or legacy image is
        # unavailable. A broken-image glyph must never leak into a customer PDF.
        return f'<div data-missing-asset="{escape(str(element.get("assetSlot") or asset_id or "image"))}" style="{_style(element)}"></div>'
    obj_pos = "left center" if (eid == "risklocker_logo" or slot == "risklocker_logo") else "center"
    return f'<img alt="" src="{src}" style="{_style(element)};object-fit:contain;object-position:{obj_pos}" />'


def _benefit_section(element: dict[str, Any], db: Any = None) -> str:
    """RL-DISABLED legacy global specials — compatibility rendering only."""
    columns = max(1, int(element.get("columns") or 2))
    grid = f'{_style(element)};display:grid;grid-template-columns:repeat({columns},1fr);gap:10px 18px;overflow:visible'
    cards = "".join(_variant_card(variant, db) for variant in _section_variants(db, element.get("section")))
    return f'<div style="{grid}">{cards}</div>'


def _is_paid_extra(card: dict[str, Any]) -> bool:
    if card.get("is_extra") or card.get("badge") or card.get("cost_status") == "paid":
        return True
    price = card.get("price") or card.get("optional_price")
    if price is not None:
        if isinstance(price, dict):
            amt = price.get("amount") if price.get("amount") is not None else price.get("value")
            try:
                clean = re.sub(r"[^0-9.]", "", str(amt or 0))
                return bool(clean and float(clean) > 0)
            except Exception:
                return False
        try:
            clean = re.sub(r"[^0-9.]", "", str(price))
            return bool(clean and float(clean) > 0)
        except Exception:
            return False
    tv = card.get("typed_value")
    if isinstance(tv, dict) and tv.get("semantic_role") == "premium":
        try:
            clean = re.sub(r"[^0-9.]", "", str(tv.get("value") or 0))
            return bool(clean and float(clean) > 0)
        except Exception:
            pass
    if card.get("detected_cost"):
        try:
            clean = re.sub(r"[^0-9.]", "", str(card.get("detected_cost") or 0))
            return bool(clean and float(clean) > 0)
        except Exception:
            pass
    return False


def _is_core_motor_cover(card: dict[str, Any]) -> bool:
    label = str(card.get("label") or "")
    return bool(re.search(r"own damage|third\s?-?\s?party bodily|third\s?-?\s?party property", label, re.I))


from app.rendering.benefit_grid_renderer import _dynamic_benefit_grid, _balance_benefit_grid_elements

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
    extras_mode = str(element.get("extras_mode") or (render_context or {}).get("extras_mode") or "itemized").lower()
    rows: list[tuple[str, str, str, str]] = []  # (kind, label, middle_val, right_val)

    v4_mode = bool(element.get("v4_mode"))

    # Calculate roadtax & runner fee early
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
                    ctype_raw = (fields or {}).get("client_type")
                    ctype_val = ctype_raw.get("value") if isinstance(ctype_raw, dict) else ctype_raw
                    cname_raw = (fields or {}).get("insured_name") or (fields or {}).get("customer_name")
                    cname_val = cname_raw.get("value") if isinstance(cname_raw, dict) else cname_raw
                    cmodel_raw = (fields or {}).get("car_model")
                    cmodel_val = cmodel_raw.get("value") if isinstance(cmodel_raw, dict) else cmodel_raw
                    cbrand_raw = (fields or {}).get("car_brand")
                    cbrand_val = cbrand_raw.get("value") if isinstance(cbrand_raw, dict) else cbrand_raw
                    from app.extraction.entity_classifier import classify_vehicle_ev_status, is_corporate_name
                    is_corp = (
                        str(ctype_val or "").lower() in {"company", "corporate", "business"}
                        or "company" in str(vtype_val or "").lower()
                        or is_corporate_name(str(cname_val or ""))
                    )
                    is_ev, ev_cat = classify_vehicle_ev_status(str(cbrand_val or ""), str(cmodel_val or ""), str(cc_val or ""))
                    vtype_to_use = ev_cat if (is_ev and ev_cat) else str(vtype_val or "Car")
                    calc_rt = calculate_road_tax(
                        clean_cc,
                        vtype_to_use,
                        owner_type="Company" if is_corp else "Individual",
                    )
                    if calc_rt > 0:
                        rt_display = f"{calc_rt:.2f}"
            except Exception:
                pass
    try:
        clean_rt_num = float((rt_display or "0").replace(",", "").strip())
    except (ValueError, TypeError):
        clean_rt_num = 0.0
    try:
        clean_sf_num = float((_value(fields, "service_fee") or "0").replace(",", "").strip())
    except (ValueError, TypeError):
        clean_sf_num = 0.0
    combined_rt_val = clean_rt_num + clean_sf_num
    combined_rt_display = f"{combined_rt_val:.2f}" if combined_rt_val > 0 else (rt_display or "")
    rt_label = str(labels.get("roadtax") or "Roadtax and Runner Fee / 路税及服务费")

    # Get total early
    total = (render_context or {}).get("total_premium_adjusted") or _value(fields, "total_premium_adjusted")
    if not total:
        disp_opts = (render_context or {}).get("display_options") or ((render_context or {}).get("draft") or {}).get("display_options") or {}
        round_tot = bool(disp_opts.get("round_total", False))
        total = adjusted_total_text(fields, extras, round_total=round_tot) if extras else _value(fields, "total_amount")
    if not total:
        total = _value(fields, "total_amount")

    def _get_v4_premium():
        try:
            total_num = float(re.sub(r"[^\d.]", "", str(total or "0")))
            return f"{total_num - combined_rt_val:,.2f}"
        except Exception:
            return _value(fields, "premium")

    if extras_mode == "none":
        # Template 1: Remove extras completely; fold extras prices into Insurance Premium so left side adds up properly
        if v4_mode:
            p_display = _get_v4_premium()
        else:
            extras_sum = Decimal("0")
            for extra in extras:
                raw_price = extra.get("price") or {}
                amt = raw_price.get("amount") if isinstance(raw_price, dict) else raw_price
                if amt is not None:
                    try:
                        extras_sum += Decimal(re.sub(r"[^\d.]", "", str(amt)))
                    except Exception:
                        pass
            p_display = _value(fields, "insurance_premium_total")
            if not p_display:
                p_raw = _value(fields, "premium")
                if p_raw and extras_sum > 0:
                    try:
                        clean_p = Decimal(re.sub(r"[^\d.]", "", p_raw))
                        p_display = f"{(clean_p + extras_sum):,.2f}"
                    except Exception:
                        p_display = p_raw
                else:
                    p_display = p_raw
        rows.append(("premium", str(labels.get("premium") or "Insurance Premium / 保费"), "", _format_value(p_display, "RM ")))

    elif extras_mode == "lump_sum":
        # Template 2: Single lump sum row: Extras RM XXX (no itemized benefit lines below)
        if extras:
            extras_sum = Decimal("0")
            for extra in extras:
                raw_price = extra.get("price") or {}
                amt = raw_price.get("amount") if isinstance(raw_price, dict) else raw_price
                if amt is not None:
                    try:
                        extras_sum += Decimal(re.sub(r"[^\d.]", "", str(amt)))
                    except Exception:
                        pass
            extras_hdr = str(labels.get("extras") or "Extras / 附加项目")
            formatted_lump = f"RM {extras_sum:,.2f}"
            rows.append(("extra_lump", extras_hdr, "", formatted_lump))
        p_val = _get_v4_premium() if v4_mode else _value(fields, "premium")
        rows.append(("premium", str(labels.get("premium") or "Insurance Premium / 保费"), "", _format_value(p_val, "RM ")))

    else:
        # Standard itemized extras mode
        if extras:
            extras_hdr = str(labels.get("extras") or "Extras / 附加项目")
            rows.append(("extras_header", extras_hdr, "", ""))
            
            display_extras = extras[:3]
            overflow_extras = extras[3:]
            
            for extra in display_extras:
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
                show_cov = extra.get("show_coverage", True)
                disp_ovr = extra.get("display_overrides") or {}
                if disp_ovr.get("enabled") and disp_ovr.get("showCoverage") is False:
                    show_cov = False
                elif disp_ovr.get("showCoverage") is False:
                    show_cov = False

                is_plan = bool(re.search(r"\b(plan|tier|level|package|option)\s*\d+\b", str(extra.get("label") or "") + " " + str(extra.get("coverage_limit") or ""), re.I))
                cov_limit = str(extra.get("coverage_limit") or "") if show_cov else ""
                if cov_limit and is_plan:
                    clean_cov = re.sub(r"[()]", "", cov_limit).replace("RM", "").strip()
                    try:
                        num_cov = float(clean_cov.replace(",", ""))
                        if num_cov < 100:
                            cov_limit = ""
                    except Exception:
                        pass
                if cov_limit:
                    clean_cov = re.sub(r"[()]", "", cov_limit).replace("RM", "").strip()
                    try:
                        num_cov = float(clean_cov.replace(",", ""))
                        if num_cov >= 100 or "RM" in str(extra.get("coverage_limit") or ""):
                            cov_limit = f"(RM {int(num_cov):,})" if num_cov == int(num_cov) else f"(RM {num_cov:,.2f})"
                        else:
                            cov_limit = ""
                    except Exception:
                        cov_limit = f"({cov_limit.strip()})" if not cov_limit.startswith("(") else cov_limit
                label = str(extra.get("label") or "")
                if not show_cov:
                    label = re.sub(r"\s*\(RM\s*[\d,.]+\)", "", label, flags=re.I).strip()
                else:
                    label = re.sub(r"(\bplan\s*\d+)\s*\(RM\s*[\d,.]+\)", r"\1", label, flags=re.I).strip()
                rows.append(("extra", label, cov_limit, formatted_price))
                
            if overflow_extras:
                overflow_sum = Decimal("0")
                for extra in overflow_extras:
                    raw_price = extra.get("price") or {}
                    amt = raw_price.get("amount") if isinstance(raw_price, dict) else raw_price
                    if amt is not None:
                        try:
                            overflow_sum += Decimal(re.sub(r"[^\d.]", "", str(amt)))
                        except Exception:
                            pass
                formatted_overflow = f"RM {overflow_sum:,.2f}" if overflow_sum > 0 else ""
                rows.append(("extra", f"+ {len(overflow_extras)} more...", "", formatted_overflow))
                
        p_val = _get_v4_premium() if v4_mode else _value(fields, "premium")
        rows.append(("premium", str(labels.get("premium") or "Insurance Premium / 保费"), "", _format_value(p_val, "RM ")))

    if not v4_mode:
        rows.append(("divider", "", "", ""))

    rows.append(("roadtax", rt_label, "", _format_value(combined_rt_display, "RM ")))

    if v4_mode:
        rows.append(("divider", "", "", ""))

    rows.append(("total", str(labels.get("total") or "TOTAL PAYABLE"), "", _format_value(total, "RM ")))
    html: list[str] = []
    z = int(element.get("z") or 4)
    for index, (kind, label, middle_val, right_val) in enumerate(rows):
        row_y = y + index * row_height
        if kind == "divider":
            html.append(
                f'<div style="position:absolute;left:{x - 12}px;top:{row_y + 6}px;width:{width + 24}px;height:1px;z-index:{z};background:#E2E8F0"></div>'
            )
            continue
        if kind == "total":
            label_style = "font-size:11px;font-weight:800;color:#0F172A"
            value_style = "font-size:13px;font-weight:800;color:#DC2626"
        elif kind == "extra_lump":
            label_style = "font-size:9.5px;font-weight:700;color:#DC2626"
            value_style = f"font-size:10px;font-weight:700;color:{'#94A3B8' if v4_mode else '#0F172A'}"
        elif kind == "extras_header":
            label_style = "font-size:9px;font-weight:700;color:#DC2626;text-transform:uppercase;letter-spacing:0.5px"
            value_style = "font-size:9px;font-weight:700;color:#DC2626"
        elif kind == "extra":
            label_style = "font-size:9px;font-weight:600;color:#B91C1C;white-space:nowrap"
            limit_html = f'<span style="font-size:9px;font-weight:600;color:#B91C1C;margin-left:4px;white-space:nowrap">{escape(middle_val)}</span>' if middle_val else ""
            value_style = f"font-size:9.5px;font-weight:700;color:{'#94A3B8' if v4_mode else '#0F172A'};white-space:nowrap;text-align:right"
            html.append(
                f'<div style="position:absolute;left:{x}px;top:{row_y}px;width:{width}px;height:{row_height}px;z-index:{z};'
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
            f'<div style="position:absolute;left:{x}px;top:{row_y}px;width:{width}px;height:{row_height}px;z-index:{z};'
            f'display:flex;align-items:center;justify-content:space-between">'
            f'<span style="{label_style}">{escape(label)}</span>'
            f'<span style="{value_style}">{escape(right_val)}</span></div>'
        )
    return "".join(html)


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
    eid = element.get("id") or ""
    if element.get("visible") is False or element_type == "layer-group":
        return ""
    if element_type == "text" and eid in {"text_ltaa394", "text_ul2w5ka"}:
        element_type = "image"
        if eid == "text_ltaa394":
            element = dict(element, type="image", assetSlot="risklocker_logo", assetId=SYSTEM_DEFAULT_SLOTS["risklocker_logo"])
        else:
            element = dict(element, type="image", assetSlot="bank_logo", assetId=SYSTEM_DEFAULT_SLOTS["bank_logo"])
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
        var_id = element.get("variableId")
        if var_id == "engine_cc":
            raw_val = _variable_value(fields, config, "engine_cc")
            if raw_val:
                from app.extraction.entity_classifier import classify_vehicle_ev_status
                cbrand = _value(fields, "car_brand")
                cmodel = _value(fields, "car_model")
                vtype = _value(fields, "vehicle_type")
                is_ev, _ = classify_vehicle_ev_status(cbrand, cmodel, raw_val)
                if not is_ev and "ev" in vtype.lower():
                    is_ev = True
                
                clean_num = re.sub(r"(?i)\s*(?:cc|kw|kilowatt|watt|w)\b", "", raw_val).strip()
                try:
                    num = float(clean_num)
                    if is_ev:
                        if num >= 1000.0:
                            num = num / 1000.0
                        disp_val = f"{int(num)}" if num == int(num) else f"{num:.1f}"
                        value = f"{disp_val} kW"
                    else:
                        disp_val = f"{int(num)}" if num == int(num) else f"{num:.1f}"
                        value = f"{disp_val} cc"
                except Exception:
                    value = f"{clean_num} kW" if is_ev else f"{clean_num} cc"
                return f'<div style="{_style(element)}">{escape(value)}</div>'
        if eid in {"ref_val", "vehicle_no_val", "header_insurer_name"} and element.get("style", {}).get("textAlign") == "right":
            prefix = str(element.get("prefix") or "")
            raw_val = _variable_value(fields, config, var_id)
            if not raw_val and eid == "ref_val":
                raw_val = "RL260000341"
            elif not raw_val and eid == "vehicle_no_val":
                raw_val = "JXS2820"
            elif not raw_val and eid == "header_insurer_name":
                raw_val = "QBE INSURANCE (MALAYSIA) BERHAD"
            val_style = "font-size:10px;font-weight:700;color:#ED1C24"
            if eid == "header_insurer_name":
                val_style = "font-size:10px;font-weight:800;color:#ED1C24;text-transform:uppercase"
            lbl_style = "font-size:10px;font-weight:500;color:#64748B"
            return (
                f'<div style="{_style(element)};text-align:right;white-space:nowrap;display:flex;align-items:center;justify-content:flex-end">'
                f'<span style="{lbl_style};margin-right:4px;flex-shrink:0">{escape(prefix)}</span>'
                f'<span style="{val_style}">{escape(raw_val)}</span>'
                f'</div>'
            )
        value = _format_value(_variable_value(fields, config, var_id), str(element.get("prefix") or ""), str(element.get("suffix") or ""))
        base_style = _style(element)
        if var_id in {"car_model", "customer_name", "insured_name"} and float(element.get("h", 0) or 0) <= 18.0:
            val_len = len(str(value or ""))
            fs_override = ""
            if val_len > 42:
                fs_override = ";font-size:8px"
            elif val_len > 32:
                fs_override = ";font-size:8.5px"
            return f'<div style="{base_style}{fs_override};white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="{escape(value)}">{escape(value)}</div>'
        return f'<div style="{base_style}">{escape(value)}</div>'
    if element_type == "special":
        return _special_html(element, config)
    if element_type == "benefit-section":
        return _benefit_section(element, db)
    if element_type == "benefit-grid":
        return _dynamic_benefit_grid(element, render_context or {}, resolved_assets or {})
    if element_type == "premium-info-block":
        return _premium_info_block(element, fields, render_context or {})
    text = str(element.get("text") or "")
    if eid in {"lbl_engine_cc", "label_engine_cc"} or "Vehicle CC" in text or ("Engine Capacity" in text and "发动机排量" not in text):
        text = "Engine Capacity / 发动机排量"
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
    
    render_context = dict(render_context or {})
    if "extras_mode" not in render_context:
        render_context["extras_mode"] = str(config.get("extras_mode") or "itemized").lower()

    if insurer_name:
        draft_fields = {**draft_fields, "insurance_company": {"value": insurer_name}}
    canvas = config.get("canvas") or {}
    width = int(canvas.get("width") or 794)
    height = int(canvas.get("height") or 1123)
    raw_elements = canvas.get("elements") or []
    is_v4 = bool(
        config.get("v4_mode")
        or str(config.get("v7_master_key") or "").startswith("agency_bilingual_v4")
        or any(e.get("v4_mode") for e in raw_elements)
        or "v4" in str(config.get("template_name") or config.get("name") or "").lower()
        or "v4" in (template_name or "").lower()
    )
    if is_v4:
        render_context["v4_mode"] = True
        for elem in raw_elements:
            if elem.get("id") == "premium_info_block" or elem.get("type") == "premium-info-block":
                elem["v4_mode"] = True
    balanced = _balance_benefit_grid_elements(raw_elements, render_context)
    
    max_element_y = 0
    for elem in balanced:
        if elem.get("type") == "rectangle" and float(elem.get("w") or 0) >= width and float(elem.get("h") or 0) >= height:
            continue
        elem_bottom = float(elem.get("y") or 0) + float(elem.get("h") or 0)
        if elem_bottom > max_element_y:
            max_element_y = elem_bottom
            
    scale_css = ""
    inner_h = height

    elements = sorted(balanced, key=lambda item: int(item.get("z", 1)))
    body_content = "".join(
        _element_html(element, draft_fields, config, db, render_context, resolved_assets)
        for element in elements
    )
    body = f'<div style="position:relative; width:{width}px; height:{inner_h}px; {scale_css}">{body_content}</div>'
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>{escape(template_name)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,400;1,600&display=swap" rel="stylesheet">
<style>
@page {{ size: {width}px {height}px; margin: 0; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: "Be Vietnam Pro", Arial, sans-serif; color: #111; background: #fff; -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; text-rendering: optimizeLegibility; }}
img {{ image-rendering: -webkit-optimize-contrast; }}
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
