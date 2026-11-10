"""Deterministic HTML/CSS rendering for Risklocker Motor Quotation Design 2.

Matches RISK LOCKER-QUOTATION DESIGN 2.pdf:
- Upper section: Left specs + Premium summary; Right free perks + Bank details & DuitNow badge/QR.
- Lower section: Unified 4-column matrix (Add-On Upgrades ++). Selected items float to the top
  with green checkmarks, unselected items follow with square checkboxes.
- Footer: Full-width solid red banner with company registration, address, and transparent white WhatsApp QR.
- Multi-Page Resilience: Keeps Page 1 locked at clean 794x1123 A4 geometry (slots 01-24) and appends
  structured Page 2+ continuation/Benefits Schedule sheets via `benefit_schedule_renderer` when >24 cards
  or `include_benefit_schedule` is enabled. Zero footer collision or clipping.
"""

from __future__ import annotations

import re
from html import escape
from typing import Any

from app.rendering.benefit_schedule_renderer import (
    get_design2_asset_uris,
    render_design2_footer_html,
    render_design2_icon_svg,
    render_design2_schedule_pages,
    render_free_coverage_gift_svg,
)
from app.rendering.unified_addon_engine import (
    build_unified_matrix_cards,
    extract_free_coverage_items,
)


def _get_val(fields: dict, key: str, fallback: str = "") -> str:
    aliases = {
        "customer_name": ("customer_name", "insured_name"),
        "quotation_reference": ("quotation_reference", "quotation_ref", "quote_ref", "reference_no", "quote_no"),
        "vehicle_no": ("vehicle_no", "vehicle_plate", "car_plate", "plate_no"),
        "insurance_company": ("insurance_company", "company_name", "insurer_name"),
        "car_model": ("car_model",),
        "cover_period": ("cover_period",),
        "coverage_type": ("coverage_type",),
        "ncd_percent": ("ncd_percent", "ncd_percentage"),
        "valuation_type": ("valuation_type", "valuation_basis", "sum_insured_type"),
        "excess_amount": ("excess_amount", "policy_excess", "excess"),
        "coverage_amount": ("coverage_amount", "sum_insured", "market_value", "agreed_value"),
        "premium": ("premium", "coverage_premium", "basic_premium_vehicle"),
        "roadtax": ("roadtax", "road_tax_amount"),
        "runner_fee": ("runner_fee", "service_fee"),
        "total_amount": ("total_amount", "total_premium_adjusted", "gross_premium"),
    }
    candidates = aliases.get(key, (key,))
    for k in candidates:
        field = fields.get(k, {})
        val = field.get("value") if isinstance(field, dict) else field
        if val is not None and str(val).strip():
            s = str(val).strip()
            if key in {"quotation_reference"}:
                s = s.rstrip(" -:_/")
            return s
    return fallback


def _format_money(val: Any) -> str:
    if val is None or val == "":
        return "RM 0.00"
    s = str(val).strip()
    if s.upper().startswith("RM"):
        cleaned = re.sub(r"[^0-9.]", "", s)
        if cleaned:
            try:
                return f"RM {float(cleaned):,.2f}"
            except Exception:
                return s
        return s
    try:
        clean = re.sub(r"[^0-9.]", "", s)
        if not clean:
            return "RM 0.00"
        return f"RM {float(clean):,.2f}"
    except Exception:
        return f"RM {s}"


def _wrap_duitnow_qr(qr_uri: str) -> str:
    if not qr_uri:
        return (
            '<div style="width: 68px; height: 68px; background: #FFFFFF; border-radius: 4px; '
            'display: flex; align-items: center; justify-content: center; font-size: 7.5px; font-weight: 700; color: #64748B;">DuitNow QR</div>'
        )
    return f"""
    <div style="position: relative; width: 68px; height: 68px; padding: 4px; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
        <svg style="position:absolute;inset:0;width:68px;height:68px;pointer-events:none;" viewBox="0 0 68 68" fill="none">
            <path d="M2 14V4C2 2.9 2.9 2 4 2H14" stroke="#E11D48" stroke-width="2.2" stroke-linecap="round"/>
            <path d="M54 2H64C65.1 2 66 2.9 66 4V14" stroke="#E11D48" stroke-width="2.2" stroke-linecap="round"/>
            <path d="M2 54V64C2 65.1 2.9 66 4 66H14" stroke="#E11D48" stroke-width="2.2" stroke-linecap="round"/>
            <path d="M54 66H64C65.1 66 66 65.1 66 64V54" stroke="#E11D48" stroke-width="2.2" stroke-linecap="round"/>
        </svg>
        <img src="{qr_uri}" style="width: 58px; height: 58px; object-fit: contain; display: block;" alt="DuitNow QR" />
    </div>
    """


def render_design2_html(
    draft_fields: dict[str, Any],
    template_config: dict[str, Any] | None = None,
    render_context: dict[str, Any] | None = None,
    resolved_assets: dict[str, str] | None = None,
    db: Any = None,
) -> str:
    """Renders the complete HTML document for Risklocker Motor Quotation Design 2."""
    template_config = template_config or {}
    render_context = render_context or {}
    resolved_assets = resolved_assets or {}

    cust_name = _get_val(draft_fields, "customer_name", "CHENG TECK KIOING")
    quote_ref = _get_val(draft_fields, "quotation_reference", "RL260000314")
    veh_plate = _get_val(draft_fields, "vehicle_no", "ANY 368")
    insurer = _get_val(draft_fields, "insurance_company", "ETIQA GENERAL INSURANCE BERHAD")
    car_model = _get_val(draft_fields, "car_model", "Tesla Model 3 Performance")
    period = _get_val(draft_fields, "cover_period", "04-06-2026 TO 03-06-2027")
    cov_type = _get_val(draft_fields, "coverage_type", "Comprehensive")
    ncd_raw = _get_val(draft_fields, "ncd_percent", "25.00%")
    ncd = ncd_raw if "%" in ncd_raw else f"{ncd_raw}%"
    val_type = _get_val(draft_fields, "valuation_type", "Market Value")
    excess = _get_val(draft_fields, "excess_amount", "RM 0.00")
    sum_insured = _get_val(draft_fields, "coverage_amount", "RM 198,000.00")

    premium = _get_val(draft_fields, "premium", "RM 5,328.10")
    roadtax = _get_val(draft_fields, "roadtax", "RM 40.00")
    runner = _get_val(draft_fields, "runner_fee", "RM 0.00")
    total_payable = _get_val(draft_fields, "total_amount", "RM 5,447.30")

    try:
        rt_num = float(re.sub(r"[^0-9.]", "", roadtax or "0") or "0")
        rf_num = float(re.sub(r"[^0-9.]", "", runner or "0") or "0")
        rt_combined = f"RM {rt_num + rf_num:,.2f}"
    except Exception:
        rt_combined = _format_money(roadtax)

    assets = get_design2_asset_uris(insurer, template_config, resolved_assets, db)
    rl_logo_uri = assets["rl_logo_uri"]
    insurer_logo_uri = assets["insurer_logo_uri"]
    duitnow_badge_uri = assets["duitnow_badge_uri"]
    duitnow_qr_uri = assets["duitnow_qr_uri"]
    whatsapp_qr_uri = assets["whatsapp_qr_uri"]

    current_benefits = list(render_context.get("current_benefits") or [])
    available_addons = list(render_context.get("available_addons") or [])

    # Extract deduplicated insurer FOC perks (excludes canonical upgrade addons & paid extras)
    free_items = extract_free_coverage_items(current_benefits, limit=6)
    if not free_items and not current_benefits:
        free_items = [
            {"title": "Legal Defense Costs", "description": "Reimburses court legal representation and defense fees up to RM2,000."},
            {"title": "Emergency Towing Assistance", "description": "24/7 accidental towing service to nearest approved repairer up to RM 200."},
            {"title": "Drive-Less Save-More", "description": "Cash rebate up to 30% of base premium for low annual mileage."},
            {"title": "Child Car Safety Seat", "description": "Reimburses replacement or repair of child safety seats in a crash."},
        ]

    free_items_html = ""
    for fi in free_items[:6]:
        ftitle = escape(fi.get("title") or "Free Coverage")
        fdesc = escape(fi.get("description") or "")
        free_items_html += f"""
        <div style="display: flex; align-items: flex-start; gap: 6px;">
            <div style="flex-shrink: 0; margin-top: 1px;">
                <svg width="15" height="15" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="#5ABA00"/><path d="m8.2 12.2 2.5 2.5 5-5.2" stroke="#FFF" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </div>
            <div style="min-width: 0;">
                <div style="font-size: 8.5px; font-weight: 700; color: #0F172A; line-height: 1.15;">{ftitle}</div>
                {f'<div style="font-size: 7.2px; color: #52525B; line-height: 1.24; margin-top: 2px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;">{fdesc}</div>' if fdesc else ''}
            </div>
        </div>
        """

    if not free_items_html:
        free_items_html = '<div style="grid-column: 1 / -1; font-size: 8px; color: #52525B;">Standard comprehensive policy benefits included under underwriter terms.</div>'

    # Unified Add-On Matrix (Selected float to top 01..k, unselected follow ..24+)
    raw_sel = render_context.get("selected_ids")
    selected_ids = set(raw_sel) if raw_sel else None
    addon_cards = build_unified_matrix_cards(
        active_benefits=current_benefits,
        available_addons=available_addons,
        selected_ids=selected_ids,
        fill_to_slots=24,
    )

    page1_cards = addon_cards[:24]
    has_overflow = len(addon_cards) > 24
    disp_opts = render_context.get("display_options") or {}
    include_schedule = bool(
        render_context.get("include_benefit_schedule")
        or template_config.get("include_benefit_schedule")
        or (disp_opts.get("include_benefit_schedule") if isinstance(disp_opts, dict) else False)
        or has_overflow
    )

    addon_grid_html = ""
    for card in page1_cards:
        is_sel = card["is_selected"]
        serial = card["serial_number"]
        title = escape(card["title"])
        desc = escape(card.get("description") or "")
        val = escape(card.get("value") or "")
        icon_svg = render_design2_icon_svg(card.get("icon_hint", "generic"), size=38)

        indicator_html = (
            '<svg width="14" height="14" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="#5ABA00"/><path d="m8.2 12.2 2.5 2.5 5-5.2" stroke="#FFF" stroke-width="2.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>'
            if is_sel
            else '<div style="width: 10.5px; height: 10.5px; border: 1.8px solid #677184; border-radius: 1.5px; background: #FFFFFF;"></div>'
        )

        addon_grid_html += f"""
        <div class="d2-card">
            <div style="flex: 0 0 38px; display: flex; align-items: center; justify-content: center; padding-left: 3px;">
                {icon_svg}
            </div>
            <div style="flex: 1; min-width: 0; padding: 4.5px 5.5px 4.5px 2px; display: flex; flex-direction: column; justify-content: space-between;">
                <div style="min-height: 0;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 3px;">
                        <div style="font-size: 7.05px; font-weight: 700; color: #0F172A; line-height: 1.13; padding-top: 2px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;">{title}</div>
                        <div style="font-size: 6.1px; font-weight: 600; color: #94A3B8; flex-shrink: 0; line-height: 1;">{escape(serial)}</div>
                    </div>
                    {f'<div style="font-size: 6.9px; font-weight: 800; color: #16A34A; margin-top: 1px; line-height: 1.1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{val}</div>' if val else ''}
                    {f'<div style="font-size: 6.05px; color: #475569; line-height: 1.16; margin-top: 1px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;">{desc}</div>' if desc else ''}
                </div>
                <div style="display: flex; justify-content: flex-end; align-items: center;">
                    {indicator_html}
                </div>
            </div>
        </div>
        """

    footer_html = render_design2_footer_html(whatsapp_qr_uri)
    gift_svg = render_free_coverage_gift_svg(width=28, height=24)

    schedule_pages_html = ""
    if include_schedule:
        sched_pages = render_design2_schedule_pages(
            draft_fields=draft_fields,
            template_config=template_config,
            render_context=render_context,
            resolved_assets=resolved_assets,
            db=db,
            addon_cards=addon_cards,
            overflow_start_index=24,
            start_page_num=2,
        )
        schedule_pages_html = "\n".join(sched_pages)

    insurer_badge_html = (
        f'<img src="{insurer_logo_uri}" style="max-height: 38px; max-width: 132px; width: auto; height: auto; object-fit: contain; display: block;" alt="{escape(insurer)}" />'
        if insurer_logo_uri
        else f'<div style="font-size: 12px; font-weight: 900; color: #0F172A; text-transform: uppercase;">{escape(insurer.split(" ")[0])}</div>'
    )

    duitnow_badge_html = (
        f'<img src="{duitnow_badge_uri}" style="height: 45px; width: auto; object-fit: contain; display: block;" alt="DuitNow" />'
        if duitnow_badge_uri
        else '<div style="font-size: 10px; font-weight: 900; color: #E11D48;">DuitNow</div>'
    )

    overflow_banner = (
        f'<div style="font-size: 6.8px; font-weight: 700; color: #E52320; margin-top: 4px; text-align: right;">+ {len(addon_cards) - 24} additional add-ons &amp; full terms continued on Sheet 2 &rarr;</div>'
        if has_overflow
        else ""
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Motor Insurance Quotation - {escape(quote_ref)}</title>
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
    padding: 30px 44px 12px 44px;
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
.spec-row {{
    display: flex;
    align-items: flex-end;
    font-size: 9px;
    padding: 6px 0 3.5px 0;
    min-height: 26.5px;
}}
.spec-label {{
    width: 168px;
    white-space: nowrap;
    font-weight: 500;
    color: #1E293B;
    flex-shrink: 0;
    padding-bottom: 2px;
}}
.spec-colon {{
    width: 14px;
    text-align: center;
    color: #475569;
    flex-shrink: 0;
    padding-bottom: 2px;
}}
.spec-value {{
    font-weight: 700;
    color: #0F172A;
    word-break: break-word;
    flex-grow: 1;
    border-bottom: 1px solid #334155;
    padding-bottom: 2px;
    line-height: 1.2;
}}
.d2-card {{
    border-radius: 6px;
    background: #F8F9FC;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.045);
    display: flex;
    align-items: stretch;
    height: 66px;
    overflow: hidden;
}}
</style>
</head>
<body data-d2-root="1">

<div class="d2-page">
    <div class="d2-main">
        <!-- Header -->
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center;">
                {f'<img src="{rl_logo_uri}" style="height: 46px; max-width: 215px; object-fit: contain; display: block;" alt="RISK LOCKER" />' if rl_logo_uri else '<div style="font-size: 24px; font-weight: 900; color: #0F172A; letter-spacing: -0.5px;">RISK LOCKEЯ</div>'}
            </div>
            <div style="display: flex; align-items: center; gap: 14px;">
                <div style="text-align: right;">
                    <div style="font-size: 17.3px; font-weight: 800; letter-spacing: -0.3px; line-height: 1.15;">
                        <span style="color: #535353; font-weight: 700;">Motor Insurance</span>
                        <span style="color: #94A3B8; font-weight: 300; margin: 0 2px;">|</span>
                        <span style="color: #E52320; font-weight: 800;">Quotation</span>
                    </div>
                    <div style="display: grid; grid-template-columns: auto auto; justify-content: end; column-gap: 6px; row-gap: 1px; margin-top: 3px; font-size: 8.6px; line-height: 1.3;">
                        <span style="font-weight: 600; color: #334155;">Quotation Ref :</span>
                        <span style="font-weight: 700; color: #010000;">{escape(quote_ref)}</span>
                        <span style="font-weight: 600; color: #334155;">Vehicle No :</span>
                        <span style="font-weight: 700; color: #010000;">{escape(veh_plate)}</span>
                        <span style="font-weight: 600; color: #334155;">Insurer :</span>
                        <span style="font-weight: 700; color: #010000; text-transform: uppercase;">{escape(insurer)}</span>
                    </div>
                </div>
                <div style="display: flex; align-items: center; justify-content: flex-end;">{insurer_badge_html}</div>
            </div>
        </div>

        <!-- Structural Hairline 1: Header Bottom Divider -->
        <div style="height: 1px; background: #64748B; margin: 13px 0 16px 0; flex-shrink: 0;"></div>

        <!-- Upper Section: 2 Columns separated by Vertical Center Hairline -->
        <div style="display: flex; align-items: stretch;">
            <!-- Left Column: Specs + Premium Summary -->
            <div style="flex: 1.02; padding-right: 18px; display: flex; flex-direction: column; justify-content: space-between;">
                <div>
                    <div style="font-size: 14px; font-weight: 800; color: #E52320; margin-bottom: 6px; line-height: 1.2;">
                        Vehicle Information <span style="font-size: 13px; font-weight: 700; color: #544F4E;">车辆资料</span>
                    </div>
                    <div class="spec-row"><div class="spec-label">Customer / 客户姓名</div><div class="spec-colon">:</div><div class="spec-value">{escape(cust_name)}</div></div>
                    <div class="spec-row"><div class="spec-label">Period Of Insurance / 保障期限</div><div class="spec-colon">:</div><div class="spec-value">{escape(period)}</div></div>
                    <div class="spec-row"><div class="spec-label">Coverage Type / 保障种类</div><div class="spec-colon">:</div><div class="spec-value">{escape(cov_type)}</div></div>
                    <div class="spec-row"><div class="spec-label">Car Model / 车型</div><div class="spec-colon">:</div><div class="spec-value">{escape(car_model)}</div></div>
                    <div class="spec-row"><div class="spec-label">NCD / 无索偿折扣</div><div class="spec-colon">:</div><div class="spec-value">{escape(ncd)}</div></div>
                    <div class="spec-row"><div class="spec-label">Valuation Type / 估价方式</div><div class="spec-colon">:</div><div class="spec-value">{escape(val_type)}</div></div>
                    <div class="spec-row"><div class="spec-label">Policy Excess / 自负额</div><div class="spec-colon">:</div><div class="spec-value">{escape(_format_money(excess))}</div></div>
                    <div class="spec-row"><div class="spec-label">Vehicle Sum Insured / 车辆保额</div><div class="spec-colon">:</div><div class="spec-value">{escape(_format_money(sum_insured))}</div></div>
                </div>

                <div style="margin-top: 18px;">
                    <div style="font-size: 14px; font-weight: 800; color: #E52320; margin-bottom: 5px; line-height: 1.2;">
                        Premium Summary <span style="font-size: 13px; font-weight: 700; color: #544F4E;">保费</span>
                    </div>
                    <div class="spec-row"><div class="spec-label">Insurance Premium / 保费</div><div class="spec-colon">:</div><div class="spec-value">{escape(_format_money(premium))}</div></div>
                    <div class="spec-row"><div class="spec-label">Roadtax and Runner Fee / 路税及服务费</div><div class="spec-colon">:</div><div class="spec-value">{escape(rt_combined)}</div></div>
                    <div style="display: flex; align-items: baseline; gap: 8px; margin-top: 22px;">
                        <div style="font-size: 13px; font-weight: 800; color: #E52320; white-space: nowrap;">TOTAL PAYABLE 应付总额 :</div>
                        <div style="font-size: 21px; font-weight: 900; color: #E52320; letter-spacing: -0.4px; line-height: 1; white-space: nowrap;">{escape(_format_money(total_payable))}</div>
                    </div>
                </div>
            </div>

            <!-- Structural Hairline 2: Vertical Center Divider -->
            <div style="width: 1px; background: #64748B; flex-shrink: 0;"></div>

            <!-- Right Column: Unified Soft Grey Container (#F8F9FC) -->
            <div style="flex: 0.98; padding-left: 18px; display: flex; flex-direction: column;">
                <div style="flex: 1; background: #F8F9FC; border-radius: 10px; overflow: hidden; display: flex; flex-direction: column; justify-content: space-between;">
                    <div>
                        <div style="background: #E52320; color: #FFFFFF; height: 40px; padding: 0 15px; font-size: 10.5px; font-weight: 800; display: flex; align-items: center; gap: 9px;">
                            {gift_svg}
                            <span>{escape(insurer.split(' ')[0])} Free Added Coverage</span>
                        </div>
                        <div style="padding: 16px 15px 12px 15px; display: grid; grid-template-columns: 1fr 1fr; gap: 14px 11px; align-content: start;">
                            {free_items_html}
                        </div>
                    </div>

                    <div style="padding: 10px 14px 14px 14px; display: flex; justify-content: space-between; align-items: flex-end; gap: 6px;">
                        <div style="min-width: 0; flex: 1;">
                            <div style="font-size: 10.8px; font-weight: 800; color: #E52320; margin-bottom: 4px; line-height: 1.2; white-space: nowrap;">
                                Company Bank Details <span style="font-size: 9.8px; font-weight: 700; color: #544F4E;">公司银行戶口</span>
                            </div>
                            <div style="font-size: 11.4px; font-weight: 800; color: #0F172A; line-height: 1.28;">RISKLOCKER SDN.BHD.</div>
                            <div style="font-size: 11.2px; font-weight: 400; color: #1E293B; line-height: 1.28;">Hong Leong Bank</div>
                            <div style="font-size: 11.4px; font-weight: 400; color: #1E293B; letter-spacing: 0.2px; line-height: 1.28;">12300318500</div>
                        </div>
                        <div style="display: flex; align-items: center; gap: 6px; flex-shrink: 0;">
                            {duitnow_badge_html}
                            {_wrap_duitnow_qr(duitnow_qr_uri)}
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Structural Hairline 3: Mid-Page Horizontal Divider -->
        <div style="height: 1px; background: #64748B; margin: 18px 0 12px 0; flex-shrink: 0;"></div>

        <!-- Lower Section: Add-On Upgrades ++ -->
        <div style="flex: 1 1 auto; min-height: 0; display: flex; flex-direction: column;">
            <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 11px;">
                <div style="font-size: 24.5px; font-weight: 900; letter-spacing: -0.4px; line-height: 1;">
                    <span style="color: #E52320;">Add-On</span> <span style="color: #1D1D1B;">Upgrades</span> <span style="color: #E52320;">++</span>
                </div>
                <div style="font-size: 11.2px; font-weight: 700; font-style: italic; color: #353331; letter-spacing: 0.2px; text-transform: uppercase;">
                    ADDITIONAL PROTECTION FOR GREATER PEACE OF MIND
                </div>
            </div>

            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 7px 7px;">
                {addon_grid_html}
            </div>
            {overflow_banner}
        </div>
    </div>

    {footer_html}
</div>

{schedule_pages_html}

</body>
</html>"""
