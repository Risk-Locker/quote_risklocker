"""Standalone & Attached Multi-Page Benefits Schedule Renderer for Risklocker.

Supports Phase 4 (Benefits & Endorsements Schedule) and Design 2 multi-page overflow:
- Exports shared Risklocker Design 2 brand assets (horizontal logo, DuitNow badge, pink QR,
  transparent white WhatsApp QR), full 24-icon SVG library, and shared footer banner.
- Renders structured `<div class="d2-page">...</div>` A4 sheets detailing overflow add-ons (25+),
  included coverages, selected endorsements, and optional upgrades with full descriptions.
"""

from __future__ import annotations

import base64
from io import BytesIO
import math
import mimetypes
import re
from html import escape
from pathlib import Path
from typing import Any

from app.rendering.design2_icons import (
    render_design2_icon_svg,
    render_free_coverage_gift_svg,
)
from app.rendering.unified_addon_engine import (
    build_unified_matrix_cards,
    extract_free_coverage_items,
    format_addon_value,
)
from app.services.template_assets import asset_data_uri, find_asset_by_hint

ROOT = Path(__file__).resolve().parents[3]


def _trim_image_padding_data_uri(data_uri: str, padding: int = 2) -> str:
    """Non-destructively crops excessive transparent/white square padding from raster data URIs."""
    if not data_uri or not data_uri.startswith("data:image/"):
        return data_uri
    header, _, b64_payload = data_uri.partition(",")
    if not b64_payload or "svg" in header.lower():
        return data_uri
    try:
        raw = base64.b64decode(b64_payload)
        from PIL import Image
        import numpy as np

        with Image.open(BytesIO(raw)) as im:
            rgba = im.convert("RGBA")
            arr = np.array(rgba)
            non_bg = (arr[:, :, 3] > 20) & (
                (arr[:, :, 0] < 245) | (arr[:, :, 1] < 245) | (arr[:, :, 2] < 245)
            )
            ys, xs = np.where(non_bg)
            if len(xs) == 0:
                return data_uri
            h, w = rgba.height, rgba.width
            x0 = max(0, int(xs.min()) - padding)
            y0 = max(0, int(ys.min()) - padding)
            x1 = min(w, int(xs.max()) + 1 + padding)
            y1 = min(h, int(ys.max()) + 1 + padding)
            # Skip re-encoding if already >=92% packed
            if (x1 - x0) >= 0.92 * w and (y1 - y0) >= 0.92 * h:
                return data_uri
            cropped = rgba.crop((x0, y0, x1, y1))
            out = BytesIO()
            cropped.save(out, format="PNG", optimize=True)
            encoded = base64.b64encode(out.getvalue()).decode("ascii")
            return f"data:image/png;base64,{encoded}"
    except Exception:
        return data_uri


def _local_file_data_uri(rel_path: str) -> str:
    p = ROOT / rel_path
    if not p.exists() or not p.is_file():
        return ""
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    encoded = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def get_company_logo_data_uri(insurer_name: str) -> str:
    """Resolve local insurer logo from `assets/Company logos/`."""
    norm = (insurer_name or "").lower()
    mapping = {
        "etiqa": "assets/Company logos/etiqa insurance logo.png",
        "amassurance": "assets/Company logos/AmAssurance logo.webp",
        "amgen": "assets/Company logos/AmAssurance logo.webp",
        "sompo": "assets/Company logos/berjaya sompo insurance logo.jpeg",
        "liberty": "assets/Company logos/Liberty Insurance logo.png",
        "lonpac": "assets/Company logos/Lonpac Insurance logo.png",
        "qbe": "assets/Company logos/QBE Insurance logo.jpg",
        "takaful": "assets/Company logos/Takaful Malaysia logo.png",
        "tune": "assets/Company logos/tune portect logo.png",
    }
    for key, rel_path in mapping.items():
        if key in norm:
            uri = _local_file_data_uri(rel_path)
            if uri:
                return uri
    return ""


def get_design2_asset_uris(
    insurer: str,
    template_config: dict[str, Any] | None = None,
    resolved_assets: dict[str, str] | None = None,
    db: Any = None,
) -> dict[str, str]:
    """Resolves official Design 2 assets: horizontal RL logo, insurer logo, DuitNow badge + QR, WhatsApp QR."""
    template_config = template_config or {}
    resolved_assets = resolved_assets or {}
    cfg_assets = template_config.get("assets") or {}

    # 1. Risklocker Horizontal Black Logo (matches DESIGN 2.pdf top-left)
    rl_logo_uri = _local_file_data_uri(
        "assets/RL Logo/risklocker logo horizontal square with black text good for white bg.png"
    )
    if not rl_logo_uri:
        rl_id = cfg_assets.get("risklocker_logo") or "e9685e1f-ac95-410c-a2e9-eccb7ca35d5f"
        rl_logo_uri = resolved_assets.get("risklocker_logo") or resolved_assets.get(rl_id) or ""
        if not rl_logo_uri:
            rl_aid = find_asset_by_hint(db, ["horizontal", "risklocker"]) or rl_id
            rl_logo_uri = resolved_assets.get(rl_aid) or (asset_data_uri(db, rl_aid) if rl_aid else "")

    # 2. DuitNow Badge + Clean Pink DuitNow QR
    duitnow_badge_uri = _local_file_data_uri("assets/duitnow/Duit Now Logo Vector.svg .png")
    duitnow_qr_uri = _local_file_data_uri("assets/QR/qr.jpeg")
    if not duitnow_qr_uri:
        qr_id = cfg_assets.get("bank_qr") or cfg_assets.get("duitnow_qr") or "c4003185-0000-4000-8000-000000000001"
        duitnow_qr_uri = resolved_assets.get("bank_qr") or resolved_assets.get("duitnow_qr") or resolved_assets.get(qr_id) or ""

    # 3. Transparent White Footer WhatsApp QR
    whatsapp_qr_uri = _local_file_data_uri("assets/QR/whatsapp_qr.png")
    if not whatsapp_qr_uri:
        whatsapp_qr_uri = duitnow_qr_uri

    # 4. Insurer Logo
    ins_id = cfg_assets.get("insurer_logo") or ""
    insurer_logo_uri = resolved_assets.get("insurer_logo") or (resolved_assets.get(ins_id) if ins_id else "") or ""
    if not insurer_logo_uri and insurer:
        insurer_logo_uri = get_company_logo_data_uri(insurer)
    if not insurer_logo_uri and insurer:
        norm_ins = insurer.lower()
        hint = (
            "etiqa" if "etiqa" in norm_ins else
            "amgen" if ("amassurance" in norm_ins or "amgen" in norm_ins) else
            "sompo" if "sompo" in norm_ins else
            "lonpac" if "lonpac" in norm_ins else
            "liberty" if "liberty" in norm_ins else
            "qbe" if "qbe" in norm_ins else
            "takaful" if "takaful" in norm_ins else
            "tune" if "tune" in norm_ins else "insurer"
        )
        ins_aid = find_asset_by_hint(db, [hint, "logo"])
        insurer_logo_uri = resolved_assets.get(ins_aid) or (asset_data_uri(db, ins_aid) if ins_aid else "")

    if insurer_logo_uri:
        insurer_logo_uri = _trim_image_padding_data_uri(insurer_logo_uri)

    return {
        "rl_logo_uri": rl_logo_uri,
        "insurer_logo_uri": insurer_logo_uri,
        "duitnow_badge_uri": duitnow_badge_uri,
        "duitnow_qr_uri": duitnow_qr_uri,
        "whatsapp_qr_uri": whatsapp_qr_uri,
    }


def render_design2_footer_html(whatsapp_qr_uri: str) -> str:
    """Shared full-width Risklocker red footer bar (108px, 3-column with vertical white dividers)."""
    qr_img = (
        f'<img src="{whatsapp_qr_uri}" style="width: 64px; height: 64px; object-fit: contain; display: block; flex-shrink: 0;" alt="WhatsApp QR" />'
        if whatsapp_qr_uri
        else '<div style="width: 64px; height: 64px; border: 1.5px solid #FFF; color: #FFF; font-size: 8px; display: flex; align-items: center; justify-content: center; font-weight: 800; flex-shrink: 0;">QR</div>'
    )
    return f"""
    <div class="d2-footer">
        <div style="min-width: 0;">
            <div style="font-size: 14.5px; font-weight: 800; letter-spacing: 0.1px; line-height: 1.1;">RISKLOCKER SDN. BHD.</div>
            <div style="font-size: 6.8px; font-weight: 500; opacity: 0.92; margin-top: 2px; margin-bottom: 6px;">202301041962(1535879-U)</div>
            <div style="font-size: 11.2px; font-weight: 500; display: flex; align-items: center; gap: 6px; line-height: 1.3;">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" style="flex-shrink: 0;"><path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/></svg>
                <span>admin@risklocker.com</span>
            </div>
            <div style="font-size: 11.2px; font-weight: 500; display: flex; align-items: center; gap: 6px; margin-top: 2px; line-height: 1.3;">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" style="flex-shrink: 0;"><path d="M4 21h16v-2h-1V9h-5V4H5v15H4v2zm3-15h5v13H7V6zm7 5h3v8h-3v-8zM9 8h1.5v2H9V8zm0 3.5h1.5v2H9v-2zm0 3.5h1.5v2H9v-2z"/></svg>
                <span>011 1011 6880 ( Office )</span>
            </div>
        </div>
        <div style="width: 1px; height: 46px; background: rgba(255, 255, 255, 0.72); flex-shrink: 0;"></div>
        <div style="font-size: 11px; font-weight: 600; line-height: 1.35; display: flex; align-items: flex-start; gap: 7px;">
            <svg width="14" height="18" viewBox="0 0 24 24" fill="currentColor" style="flex-shrink: 0; margin-top: 1px;"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>
            <div>
                No. 77-02, Jalan Setia Tropika 1/8,<br/>
                Taman Setia Tropika,<br/>
                81200 Johor Bahru, Johor.
            </div>
        </div>
        <div style="width: 1px; height: 46px; background: rgba(255, 255, 255, 0.72); flex-shrink: 0;"></div>
        <div style="display: flex; align-items: center; gap: 10px;">
            {qr_img}
            <div>
                <div style="font-size: 10.5px; font-weight: 800; line-height: 1.2;">Scan For<br/>More Information</div>
                <div style="font-size: 9px; font-weight: 600; font-style: italic; opacity: 0.96; margin-top: 3px;">Contact Us On Whatsapp</div>
            </div>
        </div>
    </div>
    """


def _extract_field(fields: dict[str, Any], keys: tuple[str, ...], fallback: str = "") -> str:
    for k in keys:
        f = fields.get(k)
        val = f.get("value") if isinstance(f, dict) else f
        if val is not None and str(val).strip():
            return str(val).strip()
    return fallback


def _format_price_badge(item: dict[str, Any]) -> tuple[str, str]:
    """Returns (badge_text, css_style_suffix)."""
    if item.get("cost_status") == "included" or item.get("is_pure_default"):
        return ("INCLUDED FOC", "background:#ECFDF5;color:#15803D;border:1px solid #A7F3D0;")
    price = item.get("price") or item.get("optional_price")
    val = price.get("amount") if isinstance(price, dict) else price
    if val is None and isinstance(price, dict):
        val = price.get("value")
    try:
        num = float(re.sub(r"[^0-9.]", "", str(val or "0")) or "0")
    except Exception:
        num = 0.0
    if item.get("is_selected"):
        if num > 0:
            return (f"ADDED · RM {num:,.2f}", "background:#FEF2F2;color:#B91C1C;border:1px solid #FECACA;")
        return ("SELECTED", "background:#ECFDF5;color:#15803D;border:1px solid #A7F3D0;")
    if num > 0:
        return (f"OPTIONAL · +RM {num:,.2f}", "background:#F8FAFC;color:#475569;border:1px solid #E2E8F0;")
    return ("OPTIONAL ADD-ON", "background:#F8FAFC;color:#475569;border:1px solid #E2E8F0;")


def _render_schedule_header(
    rl_logo_uri: str,
    insurer_logo_uri: str,
    insurer: str,
    quote_ref: str,
    veh_plate: str,
    cust_name: str,
    page_num: int,
    total_pages: int,
) -> str:
    return f"""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; border-bottom: 1.5px solid #E2E8F0; padding-bottom: 8px;">
        <div style="display: flex; align-items: center; gap: 10px;">
            {f'<img src="{rl_logo_uri}" style="height: 30px; max-width: 150px; object-fit: contain;" alt="RISK LOCKER" />' if rl_logo_uri else '<div style="font-size: 18px; font-weight: 900; color: #0F172A;">RISK LOCKEЯ</div>'}
        </div>
        <div style="text-align: right; flex-grow: 1; padding: 0 12px;">
            <div style="font-size: 13px; font-weight: 900; letter-spacing: -0.2px;">
                <span style="color: #0F172A;">Benefits &amp; Endorsements Schedule</span>
                <span style="color: #E52320;"> | {escape(quote_ref)}</span>
            </div>
            <div style="font-size: 8px; font-weight: 600; color: #475569; margin-top: 2px;">
                Client: <strong style="color:#0F172A;">{escape(cust_name)}</strong> · Vehicle: <strong style="color:#0F172A;">{escape(veh_plate)}</strong> · Insurer: <strong style="color:#0F172A;">{escape(insurer.upper())}</strong> · Sheet {page_num}/{total_pages}
            </div>
        </div>
        <div>
            {f'<img src="{insurer_logo_uri}" style="height: 30px; max-width: 90px; object-fit: contain;" alt="{escape(insurer)}" />' if insurer_logo_uri else ''}
        </div>
    </div>
    """


def render_design2_schedule_pages(
    draft_fields: dict[str, Any],
    template_config: dict[str, Any] | None = None,
    render_context: dict[str, Any] | None = None,
    resolved_assets: dict[str, str] | None = None,
    db: Any = None,
    *,
    addon_cards: list[dict[str, Any]] | None = None,
    overflow_start_index: int = 24,
    start_page_num: int = 2,
) -> list[str]:
    """Builds A4 `<div class="d2-page">` sheets for Page 2+ Benefits Schedule & overflow cards."""
    template_config = template_config or {}
    render_context = render_context or {}
    quote_ref = _extract_field(draft_fields, ("quotation_reference", "quotation_ref", "quote_ref"), "RL260000314").rstrip(" -:_/")
    veh_plate = _extract_field(draft_fields, ("vehicle_no", "vehicle_plate", "car_plate"), "ANY 368")
    cust_name = _extract_field(draft_fields, ("customer_name", "insured_name"), "VALUED CLIENT")
    insurer = _extract_field(draft_fields, ("insurance_company", "company_name", "insurer_name"), "ETIQA GENERAL INSURANCE BERHAD")

    assets = get_design2_asset_uris(insurer, template_config, resolved_assets, db)
    current_benefits = list(render_context.get("current_benefits") or [])
    available_addons = list(render_context.get("available_addons") or [])

    if addon_cards is None:
        addon_cards = build_unified_matrix_cards(
            active_benefits=current_benefits,
            available_addons=available_addons,
            fill_to_slots=24,
        )

    overflow_cards = addon_cards[overflow_start_index:] if len(addon_cards) > overflow_start_index else []
    free_items = extract_free_coverage_items(current_benefits, limit=12)
    selected_cards = [c for c in addon_cards if c.get("is_selected")]
    optional_cards = [c for c in addon_cards if not c.get("is_selected")]

    # Build structured schedule rows (Active/Selected first, then Optional Upgrades)
    active_rows: list[dict[str, Any]] = []
    for fi in free_items:
        active_rows.append(
            {
                "title": fi["title"],
                "description": fi.get("description") or "Standard underwriter complimentary coverage.",
                "value": "",
                "icon_hint": "generic",
                "badge_text": "INCLUDED FOC",
                "badge_css": "background:#ECFDF5;color:#15803D;border:1px solid #A7F3D0;",
            }
        )
    for sc in selected_cards:
        badge_txt, badge_css = _format_price_badge(sc)
        active_rows.append(
            {
                "title": sc["title"],
                "description": sc.get("description") or "",
                "value": sc.get("value") or "",
                "icon_hint": sc.get("icon_hint") or "generic",
                "badge_text": badge_txt,
                "badge_css": badge_css,
            }
        )

    # Render overflow grid HTML if cards > 24 exist (matches Page 1 horizontal #F8F9FC card geometry)
    overflow_html = ""
    if overflow_cards:
        ov_cards_html = ""
        for card in overflow_cards:
            is_sel = card["is_selected"]
            icon_svg = render_design2_icon_svg(card.get("icon_hint", "generic"), size=36)
            indicator = (
                '<svg width="14" height="14" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="#5ABA00"/><path d="m8.2 12.2 2.5 2.5 5-5.2" stroke="#FFF" stroke-width="2.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>'
                if is_sel
                else '<div style="width:10.5px;height:10.5px;border:1.8px solid #677184;border-radius:1.5px;background:#FFF;"></div>'
            )
            val = escape(card.get("value") or "")
            ov_cards_html += f"""
            <div style="background:#F8F9FC;border-radius:6px;box-shadow:0 1px 2px rgba(15,23,42,0.05);height:62px;display:flex;align-items:stretch;overflow:hidden;">
                <div style="flex:0 0 40px;display:flex;align-items:center;justify-content:center;padding-left:4px;">{icon_svg}</div>
                <div style="flex:1;min-width:0;padding:4px 7px 4px 2px;display:flex;flex-direction:column;justify-content:space-between;position:relative;">
                    <div>
                        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:3px;">
                            <div style="font-size:7.4px;font-weight:700;color:#0F172A;line-height:1.12;padding-top:2px;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;">{escape(card['title'])}</div>
                            <div style="font-size:6.2px;font-weight:600;color:#94A3B8;flex-shrink:0;line-height:1;">{escape(card['serial_number'])}</div>
                        </div>
                        {f'<div style="font-size:7px;font-weight:800;color:#16A34A;margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{val}</div>' if val else ''}
                        <div style="font-size:6.2px;color:#475569;line-height:1.15;margin-top:1px;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;">{escape(card.get('description') or '')}</div>
                    </div>
                    <div style="display:flex;justify-content:flex-end;align-items:center;">{indicator}</div>
                </div>
            </div>
            """
        overflow_html = f"""
        <div style="margin-bottom: 10px;">
            <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #64748B;padding-bottom:3px;margin-bottom:7px;">
                <div style="font-size:11px;font-weight:900;color:#E52320;">Add-On Upgrades <span style="color:#1E293B;">++</span> <span style="font-size:9.5px;color:#64748B;font-weight:700;">(Continued Slots {escape(overflow_cards[0]['serial_number'])}–{escape(overflow_cards[-1]['serial_number'])})</span></div>
                <div style="font-size:7.2px;font-weight:700;font-style:italic;color:#353331;">EXTENDED COVERAGE OPTIONS</div>
            </div>
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:7px 8px;">
                {ov_cards_html}
            </div>
        </div>
        """

    def _row_html(row: dict[str, Any], idx: int) -> str:
        icon_svg = render_design2_icon_svg(row.get("icon_hint", "generic"), size=20)
        val = format_addon_value(row.get("value"))
        return f"""
        <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:10px;padding:6px 8px;border:1px solid #E2E8F0;border-radius:6px;background:#FFFFFF;">
            <div style="display:flex;align-items:flex-start;gap:8px;min-width:0;flex:1;">
                <div style="width:26px;height:26px;border-radius:5px;background:#F8F9FC;border:1px solid #E2E8F0;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:1px;">
                    {icon_svg}
                </div>
                <div style="min-width:0;flex:1;">
                    <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
                        <span style="font-size:7.5px;font-weight:800;color:#94A3B8;">#{idx:02d}</span>
                        <span style="font-size:9px;font-weight:800;color:#0F172A;">{escape(row['title'])}</span>
                        {f'<span style="font-size:8px;font-weight:800;color:#16A34A;background:#ECFDF5;padding:1px 5px;border-radius:4px;">{escape(val)}</span>' if val else ''}
                    </div>
                    <div style="font-size:7.4px;color:#475569;line-height:1.3;margin-top:2px;">{escape(row.get('description') or 'Subject to master policy terms and endorsements.')}</div>
                </div>
            </div>
            <div style="flex-shrink:0;">
                <span style="font-size:7px;font-weight:800;padding:2px 6px;border-radius:4px;white-space:nowrap;{row['badge_css']}">{escape(row['badge_text'])}</span>
            </div>
        </div>
        """

    # Fit cleanly on Sheet 2 without footer collision (accounting for 108px taller footer -> 875px budget)
    overflow_grid_rows = math.ceil(len(overflow_cards) / 4) if overflow_cards else 0
    overflow_h = overflow_grid_rows * 69 + (34 if overflow_cards else 0)
    shown_active = active_rows[:12]
    remaining_active = active_rows[12:]
    active_grid_rows = math.ceil(len(shown_active) / 2) if shown_active else 0
    active_h = active_grid_rows * 46 + (32 if shown_active else 0)
    remaining_budget = max(0, 875 - overflow_h - active_h - 28)
    opt_limit = max(0, (remaining_budget // 38) * 2)

    active_section = ""
    if shown_active:
        rows_markup = "".join(_row_html(r, i) for i, r in enumerate(shown_active, start=1))
        active_section = f"""
        <div style="margin-bottom: 12px;">
            <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1.5px solid #0F172A;padding-bottom:3px;margin-bottom:6px;">
                <div style="font-size:11px;font-weight:900;color:#0F172A;">Active Coverages &amp; Selected Endorsements <span style="color:#E52320;">({len(active_rows)})</span></div>
                <div style="font-size:7px;font-weight:700;color:#64748B;">FULL POLICY TERMS &amp; LIMITS</div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:5px 8px;">
                {rows_markup}
            </div>
        </div>
        """

    opt_chunk = optional_cards[:opt_limit]
    opt_section = ""
    if opt_chunk:
        opt_rows = ""
        for oc in opt_chunk:
            badge_txt, badge_css = _format_price_badge(oc)
            val = format_addon_value(oc.get("value"))
            opt_rows += f"""
            <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:6px;padding:4px 7px;border:1px solid #F1F5F9;border-radius:5px;background:#F8FAFC;">
                <div style="display:flex;align-items:flex-start;gap:6px;min-width:0;flex:1;">
                    <div style="flex-shrink:0;margin-top:1px;">{render_design2_icon_svg(oc.get('icon_hint', 'generic'), size=13)}</div>
                    <div style="min-width:0;">
                        <div style="font-size:7.8px;font-weight:700;color:#0F172A;">{escape(oc['serial_number'])} · {escape(oc['title'])} {f'<span style="color:#16A34A;">({escape(val)})</span>' if val else ''}</div>
                        <div style="font-size:6.6px;color:#64748B;line-height:1.25;">{escape(oc.get('description') or '')}</div>
                    </div>
                </div>
                <span style="font-size:6.4px;font-weight:700;padding:1.5px 4.5px;border-radius:3px;white-space:nowrap;{badge_css}">{escape(badge_txt)}</span>
            </div>
            """
        opt_section = f"""
        <div style="margin-bottom: 6px;">
            <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #CBD5E1;padding-bottom:2px;margin-bottom:5px;">
                <div style="font-size:10px;font-weight:800;color:#334155;">Optional Add-On Upgrades Reference <span style="font-weight:600;color:#64748B;">({len(optional_cards)} Available)</span></div>
                <div style="font-size:6.8px;font-weight:700;color:#94A3B8;">ASK YOUR ADVISOR TO INCLUDE ANY RIDER</div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 8px;">
                {opt_rows}
            </div>
        </div>
        """

    remaining_opt = optional_cards[opt_limit:]
    cont_chunks: list[tuple[list[dict[str, Any]], list[dict[str, Any]]]] = []
    if remaining_active or remaining_opt:
        # First continuation sheet starts with any remaining active rows (usually empty) + optional slice
        rem_act = list(remaining_active)
        rem_opt = list(remaining_opt)
        while rem_act or rem_opt:
            act_take = rem_act[:12]
            rem_act = rem_act[12:]
            act_h_cont = (math.ceil(len(act_take) / 2) * 50 + 34) if act_take else 0
            opt_cap = max(8, ((840 - act_h_cont - 32) // 44) * 2)
            opt_take = rem_opt[:opt_cap]
            rem_opt = rem_opt[opt_cap:]
            cont_chunks.append((act_take, opt_take))

    total_pages = start_page_num + len(cont_chunks)

    footer_html = render_design2_footer_html(assets["whatsapp_qr_uri"])
    pages: list[str] = []

    page1_sched = f"""
    <div class="d2-page">
        <div class="d2-main">
            {_render_schedule_header(assets['rl_logo_uri'], assets['insurer_logo_uri'], insurer, quote_ref, veh_plate, cust_name, start_page_num, total_pages)}
            {overflow_html}
            {active_section}
            {opt_section}
        </div>
        {footer_html}
    </div>
    """
    pages.append(page1_sched)

    for offset, (act_slice, opt_slice) in enumerate(cont_chunks, start=1):
        cont_active_html = ""
        if act_slice:
            cont_act_rows = "".join(_row_html(r, i) for i, r in enumerate(act_slice, start=13 + (offset - 1) * 12))
            cont_active_html = f"""
            <div style="margin-bottom: 10px;">
                <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1.5px solid #0F172A;padding-bottom:3px;margin-bottom:6px;">
                    <div style="font-size:10.5px;font-weight:900;color:#0F172A;">Active Coverages &amp; Selected Endorsements (Continued)</div>
                    <div style="font-size:7px;font-weight:700;color:#64748B;">FULL POLICY TERMS &amp; LIMITS</div>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:5px 8px;">{cont_act_rows}</div>
            </div>
            """

        cont_opt_html = ""
        if opt_slice:
            rem_rows = ""
            for oc in opt_slice:
                badge_txt, badge_css = _format_price_badge(oc)
                val = format_addon_value(oc.get("value"))
                rem_rows += f"""
                <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:6px;padding:4px 7px;border:1px solid #E2E8F0;border-radius:5px;background:#FFF;">
                    <div style="display:flex;align-items:flex-start;gap:7px;min-width:0;flex:1;">
                        <div style="flex-shrink:0;margin-top:1px;">{render_design2_icon_svg(oc.get('icon_hint', 'generic'), size=13)}</div>
                        <div style="min-width:0;">
                            <div style="font-size:7.8px;font-weight:700;color:#0F172A;">{escape(oc['serial_number'])} · {escape(oc['title'])} {f'<span style="color:#16A34A;">({escape(val)})</span>' if val else ''}</div>
                            <div style="font-size:6.6px;color:#64748B;line-height:1.25;">{escape(oc.get('description') or '')}</div>
                        </div>
                    </div>
                    <span style="font-size:6.4px;font-weight:700;padding:1.5px 4.5px;border-radius:3px;white-space:nowrap;{badge_css}">{escape(badge_txt)}</span>
                </div>
                """
            cont_opt_html = f"""
            <div>
                <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1.5px solid #0F172A;padding-bottom:3px;margin-bottom:6px;">
                    <div style="font-size:10.5px;font-weight:800;color:#334155;">Optional Add-On Upgrades Reference (Continued)</div>
                    <div style="font-size:7px;font-weight:700;color:#64748B;">COMPLETE ENDORSEMENT DIRECTORY</div>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 8px;">
                    {rem_rows}
                </div>
            </div>
            """

        pages.append(f"""
        <div class="d2-page">
            <div class="d2-main">
                {_render_schedule_header(assets['rl_logo_uri'], assets['insurer_logo_uri'], insurer, quote_ref, veh_plate, cust_name, start_page_num + offset, total_pages)}
                {cont_active_html}
                {cont_opt_html}
            </div>
            {footer_html}
        </div>
        """)

    return pages


DESIGN2_PAGE_CSS = """
.d2-page {
    width: 794px;
    height: 1123px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    background: #FFFFFF;
    color: #0F172A;
    font-family: 'Be Vietnam Pro', -apple-system, BlinkMacSystemFont, Arial, sans-serif;
    overflow: hidden;
    page-break-after: always;
    break-after: page;
}
.d2-page:last-child {
    page-break-after: auto;
    break-after: auto;
}
.d2-main {
    flex: 1 1 auto;
    min-height: 0;
    padding: 28px 44px 16px 44px;
    display: flex;
    flex-direction: column;
}
.d2-footer {
    flex: 0 0 108px;
    height: 108px;
    background: #E52320;
    color: #FFFFFF;
    padding: 0 44px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
"""


def render_benefit_schedule_html(
    draft_fields: dict[str, Any],
    template_config: dict[str, Any] | None = None,
    render_context: dict[str, Any] | None = None,
    resolved_assets: dict[str, str] | None = None,
    db: Any = None,
) -> str:
    """Renders a standalone full HTML document for the Benefits & Endorsements Schedule."""
    quote_ref = _extract_field(draft_fields, ("quotation_reference", "quotation_ref", "quote_ref"), "RL260000314").rstrip(" -:_/")
    pages = render_design2_schedule_pages(
        draft_fields=draft_fields,
        template_config=template_config,
        render_context=render_context,
        resolved_assets=resolved_assets,
        db=db,
        start_page_num=1,
    )
    pages_html = "\n".join(pages)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Benefits & Endorsements Schedule - {escape(quote_ref)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
@page {{ size: 794px 1123px; margin: 0; }}
* {{ box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
body {{
    margin: 0;
    padding: 0;
    width: 794px;
    font-family: 'Be Vietnam Pro', -apple-system, BlinkMacSystemFont, Arial, sans-serif;
    color: #0F172A;
    background: #FFFFFF;
}}
.d2-page {{
    width: 794px;
    height: 1123px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    background: #FFFFFF;
    overflow: hidden;
    page-break-after: always;
    break-after: page;
}}
.d2-page:last-child {{
    page-break-after: auto;
    break-after: auto;
}}
.d2-main {{
    flex: 1 1 auto;
    min-height: 0;
    padding: 28px 44px 16px 44px;
    display: flex;
    flex-direction: column;
}}
.d2-footer {{
    flex: 0 0 108px;
    height: 108px;
    background: #E52320;
    color: #FFFFFF;
    padding: 0 44px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}}
</style>
</head>
<body>
{pages_html}
</body>
</html>"""
