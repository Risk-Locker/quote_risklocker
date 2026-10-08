"""Canonical insurer-independent v7 master documents and idempotent publication."""

from __future__ import annotations

from copy import deepcopy

from sqlalchemy import select
from sqlalchemy.orm import defer
from sqlalchemy.orm.attributes import flag_modified

from app.models.tables import OutputTemplateConfig, TemplateRevision, new_id
from app.services.template_revision_service import new_v7_template_config, publish_template_revision, validate_template_config


RED = "#E51C2A"
INK = "#171719"
MUTED = "#66666B"
BORDER = "#D9D9DE"


def _text(node_id: str, text: str, x: float, y: float, w: float, h: float, z: int, *, size: int | float = 14, weight: str = "600", color: str = INK, align: str = "left", locked: bool = False, group_id: str | None = None, visible: bool = True) -> dict:
    res = {"id": node_id, "type": "text", "text": text, "x": x, "y": y, "w": w, "h": h, "z": z, "style": {"fontSize": size, "fontWeight": weight, "color": color, "textAlign": align}}
    if locked: res["locked"] = True
    if group_id: res["groupId"] = group_id
    if not visible: res["visible"] = False
    return res


def _variable(node_id: str, variable_id: str, x: float, y: float, w: float, h: float, z: int, *, size: int | float = 14, weight: str = "700", color: str = INK, align: str = "left", prefix: str = "", suffix: str = "", transform: str = "none", locked: bool = False, group_id: str | None = None, visible: bool = True) -> dict:
    res = {"id": node_id, "type": "variable", "variableId": variable_id, "prefix": prefix, "suffix": suffix, "x": x, "y": y, "w": w, "h": h, "z": z, "style": {"fontSize": size, "fontWeight": weight, "color": color, "textAlign": align, "textTransform": transform}}
    if locked: res["locked"] = True
    if group_id: res["groupId"] = group_id
    if not visible: res["visible"] = False
    return res


def _image(node_id: str, slot: str, x: float, y: float, w: float, h: float, z: int, *, locked: bool = False, group_id: str | None = None) -> dict:
    res = {"id": node_id, "type": "image", "assetSlot": slot, "x": x, "y": y, "w": w, "h": h, "z": z, "style": {"borderWidth": 0}}
    if locked: res["locked"] = True
    if group_id: res["groupId"] = group_id
    return res


def _rectangle(node_id: str, x: float, y: float, w: float, h: float, z: int, *, background: str = "#FFFFFF", border: str = BORDER, radius: int = 0, locked: bool = False, group_id: str | None = None) -> dict:
    res = {"id": node_id, "type": "rectangle", "x": x, "y": y, "w": w, "h": h, "z": z, "style": {"background": background, "borderWidth": 1 if border else 0, "borderColor": border or "transparent", "borderRadius": radius}}
    if locked: res["locked"] = True
    if group_id: res["groupId"] = group_id
    return res


def _line(node_id: str, x: float, y: float, w: float, z: int, *, color: str = RED, height: float = 2, locked: bool = False, group_id: str | None = None) -> dict:
    res = {"id": node_id, "type": "line", "x": x, "y": y, "w": w, "h": height, "z": z, "style": {"color": color, "borderWidth": height}}
    if locked: res["locked"] = True
    if group_id: res["groupId"] = group_id
    return res


def _grid(node_id: str, kind: str, x: float, y: float, w: float, h: float, z: int, *, dense: bool = False, locked: bool = False, auto_four_col: bool = False) -> dict:
    res = {
        "id": node_id, "type": "benefit-grid", "gridKind": kind, "x": x, "y": y, "w": w, "h": h, "z": z,
        "layoutMode": "masonry", "columns": 3,
        "packing": {
            "strategy": "balanced", "alignment": "start", "aspectRatio": 3.2 if dense else 3.0,
            "referenceWidth": 220, "referenceHeight": 64,
            "gapRatio": 0.025 if dense else 0.04, "paddingRatio": 0.01 if dense else 0.015, "staggerRatio": 0.0,
        },
        "cardStyle": "outlined" if dense else "standard", "textDensity": "compact" if dense else "normal", "emptyState": "hide",
    }
    if auto_four_col or kind == "available_addons":
        res["autoFourCol"] = True
        res["adaptiveColumns"] = True
    if locked: res["locked"] = True
    return res


def _layer_group(node_id: str, name: str) -> dict:
    return {"id": node_id, "type": "layer-group", "name": name, "locked": False}


def _identity_header(*, compact: bool = False) -> list[dict]:
    top = 24 if compact else 30
    return [
        _image("risklocker_logo", "risklocker_logo", 32, top, 126, 44, 5),
        _image("insurer_logo", "insurer_logo", 624, top - 4, 138, 58, 5),
        _line("header_rule", 32, 92 if compact else 104, 730, 3, height=3),
        _text("document_title", "Motor Insurance Quotation", 32, 108 if compact else 122, 430, 38, 5, size=24 if compact else 27, weight="800"),
        _text("premium_label", "TOTAL PREMIUM", 522, 111 if compact else 125, 240, 18, 5, size=10, weight="800", color=MUTED, align="right"),
        _variable("premium_value", "total_premium_adjusted", 500, 130 if compact else 146, 262, 42, 5, size=25 if compact else 29, weight="800", color=RED, align="right", prefix="RM "),
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


def _agency_bilingual_config() -> dict:
    name = "Bilingual Agency Motor"
    key = "agency_bilingual"
    height = 1123
    config = new_v7_template_config(name)

    NAVY = "#1E293B"
    DARK = "#0F172A"
    LABEL_COLOR = "#334155"
    MUTED_COLOR = "#64748B"
    BORDER_COLOR = "#E2E8F0"
    RED_COLOR = "#ED1C24"
    BG_LIGHT = "#F8FAFC"

    elements = [
        # 1. Page Background
        _rectangle("page_bg", 0, 0, 794, height, 1, background="#FFFFFF", border=""),

        # 2. Header: Logos, Insurer Name, Quotation Ref, Vehicle No, and Top Divider
        _image("risklocker_logo", "risklocker_logo", 40, 8, 72, 74, 5),
        _text("ref_label", "Quotation Ref: ", 354, 20, 400, 16, 5, size=10, weight="500", color=MUTED_COLOR, align="right", visible=False),
        _variable("ref_val", "quotation_reference", 354, 20, 400, 16, 5, size=10, weight="700", color=RED_COLOR, align="right", prefix="Quotation Ref: "),
        _text("vehicle_no_label", "Vehicle No: ", 354, 38, 400, 16, 5, size=10, weight="500", color=MUTED_COLOR, align="right", visible=False),
        _variable("vehicle_no_val", "vehicle_no", 354, 38, 400, 16, 5, size=10, weight="700", color=RED_COLOR, align="right", prefix="Vehicle No: "),
        _text("header_insurer_label", "Insurer: ", 354, 56, 400, 16, 5, size=10, weight="500", color=MUTED_COLOR, align="right", visible=False),
        _variable("header_insurer_name", "insurance_company", 354, 56, 400, 18, 5, size=10.5, weight="800", color=RED_COLOR, align="right", transform="uppercase", prefix="Insurer: "),
        _line("header_rule", 40, 82, 714, 2, color=BORDER_COLOR, height=1),

        # 3. Main Title
        _text("title_motor", "Motor Insurance ", 40, 94, 200, 34, 5, size=24, weight="800", color=DARK, locked=True),
        _text("title_quotation", "Quotation", 236, 94, 160, 34, 5, size=24, weight="800", color=RED_COLOR, locked=True),

        # 4. Left Column: Coverage & Vehicle Information Card (x=40, w=454, y=134, h=272)
        _rectangle("cov_header_bg", 40, 134, 454, 26, 2, background=NAVY, border="", radius=4, locked=True),
        _text("cov_header_txt", "Coverage & Vehicle Information / 车辆及保单资料", 52, 139, 430, 16, 5, size=10, weight="700", color="#FFFFFF", locked=True),
        _rectangle("cov_table_bg", 40, 160, 454, 246, 2, background="#FFFFFF", border=BORDER_COLOR, radius=4, locked=True),

        # Row 1: Customer Name
        _text("lbl_customer", "Customer / 客户姓名", 52, 164, 160, 14, 5, size=9.0, weight="600", color=LABEL_COLOR, locked=True),
        _variable("val_customer", "customer_name", 216, 164, 266, 14, 5, size=9.5, weight="700", color=DARK, locked=True),

        # Row 2: Coverage Type
        _text("lbl_cov_type", "Coverage Type / 保单种类", 52, 178, 160, 14, 5, size=9.0, weight="600", color=LABEL_COLOR, locked=True),
        _variable("val_cov_type", "coverage_type", 216, 178, 266, 14, 5, size=9.5, weight="700", color=DARK, locked=True),

        # Row 3: Car Model
        _text("lbl_car_model", "Car Model / 车型", 52, 192, 160, 14, 5, size=9.0, weight="600", color=LABEL_COLOR, locked=True),
        _variable("val_car_model", "car_model", 216, 192, 266, 14, 5, size=9.5, weight="700", color=DARK, locked=True),

        # Row 4: Vehicle Capacity
        _text("lbl_engine_cc", "Engine Capacity/发动机排量 : ", 52, 206, 160, 14, 5, size=9.0, weight="600", color=LABEL_COLOR, locked=True),
        _variable("val_engine_cc", "engine_cc", 216, 206, 266, 14, 5, size=9.5, weight="700", color=DARK, suffix="", locked=True),

        # Row 5: NCD
        _text("lbl_ncd", "NCD", 52, 220, 160, 14, 5, size=9.0, weight="600", color=LABEL_COLOR, locked=True),
        _variable("val_ncd", "ncd_percent", 216, 220, 266, 14, 5, size=9.5, weight="700", color=DARK, suffix="%", locked=True),

        # Row 6: Coverage Period
        _text("lbl_period", "Cover of Period / 保单期限", 52, 234, 160, 14, 5, size=9.0, weight="600", color=LABEL_COLOR, locked=True),
        _variable("val_period", "cover_period", 216, 234, 266, 14, 5, size=9.5, weight="700", color=DARK, locked=True),

        # Row 7: Valuation Type
        _text("lbl_valuation_type", "Valuation Type / 估价方式", 52, 248, 160, 14, 5, size=8.5, weight="600", color=LABEL_COLOR, locked=True),
        _variable("val_valuation_type", "valuation_type", 216, 248, 266, 14, 5, size=9.5, weight="700", color=DARK, locked=True),

        # Row 8: Coverage / Sum Insured
        _text("lbl_sum_insured", "Vehicle Sum Insured / 车辆保额", 52, 262, 160, 14, 5, size=8.5, weight="600", color=LABEL_COLOR, locked=True),
        _variable("val_sum_insured", "coverage_amount", 216, 262, 266, 14, 5, size=9.5, weight="700", color=DARK, prefix="RM ", locked=True),

        # Dynamic Premium Block (Extras, Insurance Premium, Roadtax, Runner Fee, Total Premium)
        {
            "id": "premium_info_block",
            "type": "premium-info-block",
            "x": 52,
            "y": 276,
            "w": 430,
            "h": 126,
            "z": 5,
            "locked": True,
            "rowHeight": 14,
            "labels": {
                "premium": "Insurance Premium / 保费",
                "roadtax": "Roadtax / 路税",
                "runner": "Runner Fee / 服务费",
                "total": "TOTAL PAYABLE",
                "extras": "Extras / 附加项目",
            },
        },

        # 5. Right Column: 3 Modular Cards (Payment, QR Code, All Driver & Policy Excess)
        _layer_group("grp_payment_card", "Payment Method Card"),
        _layer_group("grp_qr_card", "DuitNow QR Card"),
        _layer_group("grp_excess_card", "All Drivers & Excess Card"),

        # Card 1: Payment Method (x=508, y=134, w=246, h=92)
        _rectangle("pay_card_bg", 508, 134, 246, 92, 2, background="#FFFFFF", border=BORDER_COLOR, radius=6, group_id="grp_payment_card"),
        _text("pay_title", "Payment Method", 522, 142, 218, 14, 5, size=9.5, weight="700", color=LABEL_COLOR, group_id="grp_payment_card"),
        _image("bank_logo", "bank_logo", 522, 158, 96, 22, 5, group_id="grp_payment_card"),
        _text("pay_acc_no", "12300318500", 522, 184, 218, 14, 5, size=10.5, weight="700", color=DARK, group_id="grp_payment_card"),
        _text("pay_holder", "RiskLocker Sdn. Bhd.", 522, 200, 218, 14, 5, size=8.5, weight="600", color=MUTED_COLOR, group_id="grp_payment_card"),

        # Card 2: Dedicated DuitNow QR (x=508, y=232, w=246, h=88)
        _rectangle("qr_card_bg", 508, 232, 246, 88, 2, background="#FFFFFF", border=BORDER_COLOR, radius=6, group_id="grp_qr_card"),
        _image("qr_code_img", "qr_code", 520, 240, 72, 72, 5, group_id="grp_qr_card"),
        _text("qr_title", "DuitNow QR", 602, 248, 140, 16, 5, size=10.5, weight="800", color=DARK, group_id="grp_qr_card"),
        _text("qr_sub", "Scan to Pay / 扫码付款", 602, 266, 140, 14, 5, size=8.5, weight="600", color=LABEL_COLOR, group_id="grp_qr_card"),
        _text("qr_hint", "Instant Verification", 602, 282, 140, 13, 5, size=8, weight="500", color=MUTED_COLOR, group_id="grp_qr_card"),

        # Card 3: All Driver & Policy Excess (x=508, y=328, w=246, h=78)
        _rectangle("all_driver_bg", 508, 328, 246, 78, 2, background=BG_LIGHT, border=BORDER_COLOR, radius=6, group_id="grp_excess_card"),
        _text("all_driver_title", "All Driver Included", 522, 334, 218, 14, 5, size=9.5, weight="700", color=DARK, group_id="grp_excess_card"),
        _text("all_driver_sub", "Authorised Drivers Covered", 522, 348, 218, 12, 5, size=8, weight="500", color=MUTED_COLOR, group_id="grp_excess_card"),
        _line("divider_driver_excess", 522, 362, 218, 4, color=BORDER_COLOR, height=1, group_id="grp_excess_card"),
        _text("excess_label", "Policy Excess / 自负额", 522, 368, 120, 14, 5, size=8.5, weight="600", color=LABEL_COLOR, group_id="grp_excess_card"),
        _variable("excess_val", "excess_amount", 642, 368, 98, 14, 5, size=10, weight="800", color=DARK, prefix="RM ", align="right", group_id="grp_excess_card"),

        # 6. Section 1: Our Specials / 特别优惠 (Included Benefits Grid)
        _rectangle("specials_header_bg", 40, 414, 714, 26, 2, background=NAVY, border="", radius=4, locked=True),
        _text("specials_header_txt", "Our Specials / 特别优惠", 52, 419, 690, 16, 5, size=10.5, weight="700", color="#FFFFFF", locked=True),
        _grid("current_benefits_grid", "current_benefits", 40, 444, 714, 314, 4, dense=True, locked=True),

        # 7. Section 2: You May Add On / 可添加项目 (Available Add-ons Grid)
        _rectangle("addons_header_bg", 40, 766, 714, 26, 2, background=NAVY, border="", radius=4, locked=True),
        _text("addons_header_txt", "You May Add On (With Additional Charges) / 可添加项目 (额外收费)", 52, 771, 690, 16, 5, size=10.5, weight="700", color="#FFFFFF", locked=True),
        _grid("available_addons_grid", "available_addons", 40, 796, 714, 262, 4, dense=True, locked=True),

        # 8. Footer
        _text("footer_terms", "*Terms & Conditions Apply | Quotation Validity: {valid_until}", 40, 1068, 714, 16, 5, size=8.5, weight="500", color=MUTED_COLOR),
    ]

    config.update({
        "version": 7, "template_name": name, "v7_master_key": key, "is_default": True, "locked": False,
        "assets": {
            "risklocker_logo": "e9685e1f-ac95-410c-a2e9-eccb7ca35d5f",
            "bank_logo": "2168eaee-3e56-4903-8c4f-841f01ff2407",
            "qr_code": "9ca8e404c89dd905",
        },
        "page_profile": {
            "profile_key": "a4", "name": "A4",
            "width": 794, "height": height, "unit": "px", "safe_margins": {"top": 24, "right": 24, "bottom": 24, "left": 24},
            "bleed": {}, "background_behavior": "clip",
        },
    })
    config["canvas"] = {**config["canvas"], "width": 794, "height": height, "elements": elements}
    return validate_template_config(config)


def _agency_bilingual_v2_config() -> dict:
    name = "Bilingual Agency Motor v2"
    key = "agency_bilingual_v2"
    height = 1123
    config = new_v7_template_config(name)

    NAVY = "#1E293B"
    DARK = "#0F172A"
    LABEL_COLOR = "#334155"
    MUTED_COLOR = "#64748B"
    BORDER_COLOR = "#E2E8F0"
    RED_COLOR = "#ED1C24"
    BG_LIGHT = "#F8FAFC"

    elements = [
        # 1. Page Background
        _rectangle("page_bg", 0, 0, 794, height, 1, background="#FFFFFF", border=""),

        # 2. Header (Single Row): Sleek Logo + Motor Insurance Quotation (Left) | Ref, Vehicle No, Insurer (Right)
        _image("risklocker_logo", "risklocker_logo", 40, 20, 32, 40, 5),
        _text("title_motor", "Motor Insurance ", 78, 26, 150, 32, 5, size=18, weight="800", color=DARK, locked=True),
        _text("title_quotation", "Quotation", 232, 26, 100, 32, 5, size=18, weight="800", color=RED_COLOR, locked=True),

        _text("ref_label", "Quotation Ref: ", 354, 18, 400, 16, 5, size=10, weight="500", color=MUTED_COLOR, align="right", visible=False),
        _variable("ref_val", "quotation_reference", 354, 18, 400, 16, 5, size=10, weight="700", color=RED_COLOR, align="right", prefix="Quotation Ref: "),
        _text("vehicle_no_label", "Vehicle No: ", 354, 34, 400, 16, 5, size=10, weight="500", color=MUTED_COLOR, align="right", visible=False),
        _variable("vehicle_no_val", "vehicle_no", 354, 34, 400, 16, 5, size=10, weight="700", color=RED_COLOR, align="right", prefix="Vehicle No: "),
        _text("header_insurer_label", "Insurer: ", 354, 50, 400, 18, 5, size=10, weight="500", color=MUTED_COLOR, align="right", visible=False),
        _variable("header_insurer_name", "insurance_company", 354, 50, 400, 18, 5, size=10.5, weight="800", color=RED_COLOR, align="right", transform="uppercase", prefix="Insurer: "),
        _line("header_rule", 40, 78, 714, 2, color=BORDER_COLOR, height=1),

        # 3. Left Column: Coverage & Vehicle Information Card (x=40, w=530, y=94, h=284)
        _rectangle("cov_header_bg", 40, 94, 530, 26, 2, background=NAVY, border="", radius=4, locked=True),
        _text("cov_header_txt", "Coverage & Vehicle Information / 车辆及保单资料", 52, 99, 506, 16, 5, size=10, weight="700", color="#FFFFFF", locked=True),
        _rectangle("cov_table_bg", 40, 120, 530, 258, 2, background="#FFFFFF", border=BORDER_COLOR, radius=4, locked=True),

        # Row 1: Customer Name
        _text("lbl_customer", "Customer / 客户姓名", 52, 124, 180, 14, 5, size=9.0, weight="600", color=LABEL_COLOR, locked=True),
        _variable("val_customer", "customer_name", 236, 124, 320, 14, 5, size=9.5, weight="700", color=DARK, locked=True),

        # Row 2: Coverage Type
        _text("lbl_cov_type", "Coverage Type / 保单种类", 52, 138, 180, 14, 5, size=9.0, weight="600", color=LABEL_COLOR, locked=True),
        _variable("val_cov_type", "coverage_type", 236, 138, 320, 14, 5, size=9.5, weight="700", color=DARK, locked=True),

        # Row 3: Car Model
        _text("lbl_car_model", "Car Model / 车型", 52, 152, 180, 14, 5, size=9.0, weight="600", color=LABEL_COLOR, locked=True),
        _variable("val_car_model", "car_model", 236, 152, 320, 14, 5, size=9.5, weight="700", color=DARK, locked=True),

        # Row 4: Vehicle Capacity
        _text("lbl_engine_cc", "Engine Capacity/发动机排量 : ", 52, 166, 180, 14, 5, size=9.0, weight="600", color=LABEL_COLOR, locked=True),
        _variable("val_engine_cc", "engine_cc", 236, 166, 320, 14, 5, size=9.5, weight="700", color=DARK, suffix="", locked=True),

        # Row 5: NCD
        _text("lbl_ncd", "NCD", 52, 180, 180, 14, 5, size=9.0, weight="600", color=LABEL_COLOR, locked=True),
        _variable("val_ncd", "ncd_percent", 236, 180, 320, 14, 5, size=9.5, weight="700", color=DARK, suffix="%", locked=True),

        # Row 6: Coverage Period
        _text("lbl_period", "Cover of Period / 保单期限", 52, 194, 180, 14, 5, size=9.0, weight="600", color=LABEL_COLOR, locked=True),
        _variable("val_period", "cover_period", 236, 194, 320, 14, 5, size=9.5, weight="700", color=DARK, locked=True),

        # Row 7: Valuation Type
        _text("lbl_valuation_type", "Valuation Type / 估价方式", 52, 208, 180, 14, 5, size=8.5, weight="600", color=LABEL_COLOR, locked=True),
        _variable("val_valuation_type", "valuation_type", 236, 208, 320, 14, 5, size=9.5, weight="700", color=DARK, locked=True),

        # Row 8: Policy Excess (Directly below Valuation Type)
        _text("lbl_excess", "Policy Excess / 自负额", 52, 222, 180, 14, 5, size=8.5, weight="600", color=LABEL_COLOR, locked=True),
        _variable("val_excess", "excess_amount", 236, 222, 320, 14, 5, size=9.5, weight="700", color=DARK, prefix="RM ", locked=True),

        # Row 9: Vehicle Sum Insured
        _text("lbl_sum_insured", "Vehicle Sum Insured / 车辆保额", 52, 236, 180, 14, 5, size=8.5, weight="600", color=LABEL_COLOR, locked=True),
        _variable("val_sum_insured", "coverage_amount", 236, 236, 320, 14, 5, size=9.5, weight="700", color=DARK, prefix="RM ", locked=True),

        # Dynamic Premium Block (Extras, Insurance Premium, Roadtax, Runner Fee, Total Premium)
        {
            "id": "premium_info_block",
            "type": "premium-info-block",
            "x": 52,
            "y": 250,
            "w": 506,
            "h": 126,
            "z": 5,
            "locked": True,
            "rowHeight": 14,
            "labels": {
                "premium": "Insurance Premium / 保费",
                "roadtax": "Roadtax and Runner Fee / 路税及服务费",
                "runner": "Runner Fee / 服务费",
                "total": "TOTAL PAYABLE",
                "extras": "Extras / 附加项目",
            },
        },

        # 4. Right Column: 2 Rows (Snug Width w=170, x=584 to 754 flush right, No Gas)
        _layer_group("grp_payment_card", "DuitNow QR & Payment Details Card"),
        _layer_group("grp_excess_card", "All Drivers Card"),

        # Row 1: Dedicated DuitNow QR & Payment Details Card (x=584, y=94, w=170, h=236)
        _rectangle("pay_card_bg", 584, 94, 170, 236, 2, background="#FFFFFF", border=BORDER_COLOR, radius=6, group_id="grp_payment_card"),
        _image("payment_account_details_img", "duitnow_payment_details", 592, 97, 154, 230, 5, group_id="grp_payment_card"),

        # Row 2: All Drivers Badge (x=584, y=336, w=170, h=42, centered text)
        _rectangle("all_driver_bg", 584, 336, 170, 42, 2, background=BG_LIGHT, border=BORDER_COLOR, radius=6, group_id="grp_excess_card"),
        _text("all_driver_title", "All Drivers Included/全司机投保", 588, 341, 162, 15, 5, size=8.5, weight="700", color=DARK, align="center", group_id="grp_excess_card"),
        _text("all_driver_sub", "Authorised Drivers Covered", 588, 357, 162, 14, 5, size=7.5, weight="500", color=MUTED_COLOR, align="center", group_id="grp_excess_card"),

        # 5. Section 2: Our Specials / 特别优惠 (Included Benefits Grid)
        _rectangle("specials_header_bg", 40, 390, 714, 26, 2, background=NAVY, border="", radius=4, locked=True),
        _text("specials_header_txt", "Our Specials / 特别优惠", 52, 395, 690, 16, 5, size=10.5, weight="700", color="#FFFFFF", locked=True),
        _grid("current_benefits_grid", "current_benefits", 40, 420, 714, 330, 4, dense=True, locked=True),

        # 6. Section 3: You May Add On / 可添加项目 (Available Add-ons Grid)
        _rectangle("addons_header_bg", 40, 760, 714, 26, 2, background=NAVY, border="", radius=4, locked=True),
        _text("addons_header_txt", "You May Add On (With Additional Charges) / 可添加项目 (额外收费)", 52, 765, 690, 16, 5, size=10.5, weight="700", color="#FFFFFF", locked=True),
        _grid("available_addons_grid", "available_addons", 40, 790, 714, 268, 4, dense=True, locked=True),

        # 7. Footer
        _text("footer_terms", "*Terms & Conditions Apply | Quotation Validity: {valid_until}", 40, 1072, 714, 16, 5, size=8.5, weight="500", color=MUTED_COLOR),
    ]

    config.update({
        "version": 7, "template_name": name, "v7_master_key": key, "is_default": False, "locked": False,
        "assets": {
            "risklocker_logo": "e9685e1f-ac95-410c-a2e9-eccb7ca35d5f",
            "duitnow_payment_details": "c3003185-0000-4000-8000-000000000001",
        },
        "page_profile": {
            "profile_key": "a4", "name": "A4",
            "width": 794, "height": height, "unit": "px", "safe_margins": {"top": 24, "right": 24, "bottom": 24, "left": 24},
            "bleed": {}, "background_behavior": "clip",
        },
    })
    config["canvas"] = {**config["canvas"], "width": 794, "height": height, "elements": elements}
    return validate_template_config(config)


def _agency_bilingual_v3_config() -> dict:
    name = "Bilingual Agency Motor v3"
    key = "agency_bilingual_v3"
    height = 1123
    config = new_v7_template_config(name)

    NAVY = "#1E293B"
    DARK = "#0F172A"
    LABEL_COLOR = "#334155"
    MUTED_COLOR = "#64748B"
    BORDER_COLOR = "#E2E8F0"
    RED_COLOR = "#ED1C24"

    elements = [
        # 1. Page Background
        _rectangle("page_bg", 0, 0, 794, height, 1, background="#FFFFFF", border=""),

        # 2. Header (Single Row): Balanced Logo + Motor Insurance Quotation (Left) | Ref, Vehicle No, Insurer (Right)
        _image("risklocker_logo", "risklocker_logo", 40, 22, 26, 26, 5),
        _text("title_motor", "Motor Insurance ", 72, 23, 140, 26, 5, size=16, weight="800", color=DARK, locked=True),
        _text("title_quotation", "Quotation", 212, 23, 90, 26, 5, size=16, weight="800", color=RED_COLOR, locked=True),

        _text("ref_label", "Quotation Ref: ", 354, 16, 400, 15, 5, size=9.5, weight="500", color=MUTED_COLOR, align="right", visible=False),
        _variable("ref_val", "quotation_reference", 354, 16, 400, 15, 5, size=9.5, weight="700", color=RED_COLOR, align="right", prefix="Quotation Ref: "),
        _text("vehicle_no_label", "Vehicle No: ", 354, 31, 400, 15, 5, size=9.5, weight="500", color=MUTED_COLOR, align="right", visible=False),
        _variable("vehicle_no_val", "vehicle_no", 354, 31, 400, 15, 5, size=9.5, weight="700", color=RED_COLOR, align="right", prefix="Vehicle No: "),
        _text("header_insurer_label", "Insurer: ", 354, 46, 400, 16, 5, size=9.5, weight="500", color=MUTED_COLOR, align="right", visible=False),
        _variable("header_insurer_name", "insurance_company", 354, 46, 400, 16, 5, size=10, weight="800", color=RED_COLOR, align="right", transform="uppercase", prefix="Insurer: "),
        _line("header_rule", 40, 70, 714, 2, color=BORDER_COLOR, height=1),

        # 3. Left Column: Coverage & Vehicle Information Card (x=40, w=530, y=94)
        # Unified border container: table background covers from y=120 through Total Payable with NO internal boxes
        _rectangle("cov_header_bg", 40, 94, 530, 26, 2, background=NAVY, border="", radius=4, locked=True),
        _text("cov_header_txt", "Coverage & Vehicle Information / 车辆及保单资料", 52, 99, 506, 16, 5, size=10, weight="700", color="#FFFFFF", locked=True),
        _rectangle("cov_table_bg", 40, 120, 530, 272, 2, background="#FFFFFF", border=BORDER_COLOR, radius=4, locked=True),

        # Row 1: Customer Name
        _text("lbl_customer", "Customer / 客户姓名", 52, 124, 180, 14, 5, size=9.0, weight="600", color=LABEL_COLOR, locked=True),
        _variable("val_customer", "customer_name", 236, 124, 320, 14, 5, size=9.5, weight="700", color=DARK, locked=True),

        # Row 2: Coverage Type
        _text("lbl_cov_type", "Coverage Type / 保单种类", 52, 138, 180, 14, 5, size=9.0, weight="600", color=LABEL_COLOR, locked=True),
        _variable("val_cov_type", "coverage_type", 236, 138, 320, 14, 5, size=9.5, weight="700", color=DARK, locked=True),

        # Row 3: Car Model
        _text("lbl_car_model", "Car Model / 车型", 52, 152, 180, 14, 5, size=9.0, weight="600", color=LABEL_COLOR, locked=True),
        _variable("val_car_model", "car_model", 236, 152, 320, 14, 5, size=9.5, weight="700", color=DARK, locked=True),

        # Row 4: Vehicle Capacity
        _text("lbl_engine_cc", "Engine Capacity/发动机排量 : ", 52, 166, 180, 14, 5, size=9.0, weight="600", color=LABEL_COLOR, locked=True),
        _variable("val_engine_cc", "engine_cc", 236, 166, 320, 14, 5, size=9.5, weight="700", color=DARK, suffix="", locked=True),

        # Row 5: NCD
        _text("lbl_ncd", "NCD", 52, 180, 180, 14, 5, size=9.0, weight="600", color=LABEL_COLOR, locked=True),
        _variable("val_ncd", "ncd_percent", 236, 180, 320, 14, 5, size=9.5, weight="700", color=DARK, suffix="%", locked=True),

        # Row 6: Coverage Period
        _text("lbl_period", "Cover of Period / 保单期限", 52, 194, 180, 14, 5, size=9.0, weight="600", color=LABEL_COLOR, locked=True),
        _variable("val_period", "cover_period", 236, 194, 320, 14, 5, size=9.5, weight="700", color=DARK, locked=True),

        # Row 7: Valuation Type
        _text("lbl_valuation_type", "Valuation Type / 估价方式", 52, 208, 180, 14, 5, size=8.5, weight="600", color=LABEL_COLOR, locked=True),
        _variable("val_valuation_type", "valuation_type", 236, 208, 320, 14, 5, size=9.5, weight="700", color=DARK, locked=True),

        # Row 8: Authorized Driver (Directly above Policy Excess)
        _text("lbl_authorized_driver", "Authorised Driver / 授权驾驶人", 52, 222, 180, 14, 5, size=8.5, weight="600", color=LABEL_COLOR, locked=True),
        _variable("val_authorized_driver", "authorized_driver", 236, 222, 320, 14, 5, size=9.5, weight="700", color=DARK, locked=True),

        # Row 9: Policy Excess (Directly below Authorized Driver)
        _text("lbl_excess", "Policy Excess / 自负额", 52, 236, 180, 14, 5, size=8.5, weight="600", color=LABEL_COLOR, locked=True),
        _variable("val_excess", "excess_amount", 236, 236, 320, 14, 5, size=9.5, weight="700", color=DARK, prefix="RM ", locked=True),

        # Row 10: Vehicle Sum Insured
        _text("lbl_sum_insured", "Vehicle Sum Insured / 车辆保额", 52, 250, 180, 14, 5, size=8.5, weight="600", color=LABEL_COLOR, locked=True),
        _variable("val_sum_insured", "coverage_amount", 236, 250, 320, 14, 5, size=9.5, weight="700", color=DARK, prefix="RM ", locked=True),

        # Dynamic Premium Block (Extras, Insurance Premium, Roadtax & Runner Fee, Total Premium)
        {
            "id": "premium_info_block",
            "type": "premium-info-block",
            "x": 52,
            "y": 264,
            "w": 506,
            "h": 126,
            "z": 5,
            "locked": True,
            "rowHeight": 14,
            "labels": {
                "premium": "Insurance Premium / 保费",
                "roadtax": "Roadtax and Runner Fee / 路税及服务费",
                "runner": "Runner Fee / 服务费",
                "total": "TOTAL PAYABLE",
                "extras": "Extras / 附加项目",
            },
        },

        # 4. Right Column: Dedicated Full Height Bank QR Layout Image (Flush right w=170, no extra border/card)
        _image("payment_account_details_img", "bank_qr_layout_dark", 584, 94, 170, 284, 5),

        # 5. Section 2: Our Specials / 特别优惠 (Included Benefits Grid)
        _rectangle("specials_header_bg", 40, 396, 714, 26, 2, background=NAVY, border="", radius=4, locked=True),
        _text("specials_header_txt", "Our Specials / 特别优惠", 52, 401, 690, 16, 5, size=10.5, weight="700", color="#FFFFFF", locked=True),
        _grid("current_benefits_grid", "current_benefits", 40, 426, 714, 324, 4, dense=True, locked=True),

        # 6. Section 3: You May Add On / 可添加项目 (Available Add-ons Grid)
        _rectangle("addons_header_bg", 40, 760, 714, 26, 2, background=NAVY, border="", radius=4, locked=True),
        _text("addons_header_txt", "You May Add On (With Additional Charges) / 可添加项目 (额外收费)", 52, 765, 690, 16, 5, size=10.5, weight="700", color="#FFFFFF", locked=True),
        _grid("available_addons_grid", "available_addons", 40, 790, 714, 268, 4, dense=True, locked=True),

        # 7. Footer
        _text("footer_terms", "*Terms & Conditions Apply | Quotation Validity: {valid_until}", 40, 1072, 714, 16, 5, size=8.5, weight="500", color=MUTED_COLOR),
    ]

    config.update({
        "version": 7, "template_name": name, "v7_master_key": key, "is_default": False, "locked": False,
        "assets": {
            "risklocker_logo": "e9685e1f-ac95-410c-a2e9-eccb7ca35d5f",
            "bank_qr_layout_dark": "c4003185-0000-4000-8000-000000000001",
            "duitnow_payment_details": "c4003185-0000-4000-8000-000000000001",
        },
        "page_profile": {
            "profile_key": "a4", "name": "A4",
            "width": 794, "height": height, "unit": "px", "safe_margins": {"top": 24, "right": 24, "bottom": 24, "left": 24},
            "bleed": {}, "background_behavior": "clip",
        },
    })
    config["canvas"] = {**config["canvas"], "width": 794, "height": height, "elements": elements}
    return validate_template_config(config)


def _agency_bilingual_v3_no_extras_config() -> dict:
    name = "Bilingual Agency Motor v3 (No Extras)"
    key = "agency_bilingual_v3_no_extras"
    config = deepcopy(_agency_bilingual_v3_config())
    config["template_name"] = name
    config["v7_master_key"] = key
    config["is_default"] = False
    config["extras_mode"] = "none"
    for elem in config["canvas"]["elements"]:
        if elem.get("id") == "premium_info_block" or elem.get("type") == "premium-info-block":
            elem["extras_mode"] = "none"
        elif elem.get("id") == "current_benefits_grid" or (elem.get("type") == "benefit-grid" and elem.get("gridKind") == "current_benefits"):
            elem["excludeExtras"] = True
    return validate_template_config(config)


def _agency_bilingual_v3_lump_sum_config() -> dict:
    name = "Bilingual Agency Motor v3 (Lump Sum Extras)"
    key = "agency_bilingual_v3_lump_sum"
    config = deepcopy(_agency_bilingual_v3_config())
    config["template_name"] = name
    config["v7_master_key"] = key
    config["is_default"] = False
    config["extras_mode"] = "lump_sum"
    for elem in config["canvas"]["elements"]:
        if elem.get("id") == "premium_info_block" or elem.get("type") == "premium-info-block":
            elem["extras_mode"] = "lump_sum"
        elif elem.get("id") == "current_benefits_grid" or (elem.get("type") == "benefit-grid" and elem.get("gridKind") == "current_benefits"):
            elem["excludeExtras"] = True
    return validate_template_config(config)


def _agency_bilingual_v4_config() -> dict:
    name = "Bilingual Agency Motor v4"
    key = "agency_bilingual_v4"
    config = deepcopy(_agency_bilingual_v3_config())
    config["template_name"] = name
    config["v7_master_key"] = key
    config["is_default"] = True
    config["v4_mode"] = True
    for elem in config["canvas"]["elements"]:
        if elem.get("id") == "premium_info_block" or elem.get("type") == "premium-info-block":
            elem["v4_mode"] = True
    return validate_template_config(config)


def _agency_bilingual_v4_no_extras_config() -> dict:
    name = "Bilingual Agency Motor v4 (No Extras)"
    key = "agency_bilingual_v4_no_extras"
    config = deepcopy(_agency_bilingual_v3_no_extras_config())
    config["template_name"] = name
    config["v7_master_key"] = key
    config["is_default"] = False
    config["v4_mode"] = True
    for elem in config["canvas"]["elements"]:
        if elem.get("id") == "premium_info_block" or elem.get("type") == "premium-info-block":
            elem["v4_mode"] = True
    return validate_template_config(config)


def _agency_bilingual_v4_lump_sum_config() -> dict:
    name = "Bilingual Agency Motor v4 (Lump Sum Extras)"
    key = "agency_bilingual_v4_lump_sum"
    config = deepcopy(_agency_bilingual_v3_lump_sum_config())
    config["template_name"] = name
    config["v7_master_key"] = key
    config["is_default"] = False
    config["v4_mode"] = True
    for elem in config["canvas"]["elements"]:
        if elem.get("id") == "premium_info_block" or elem.get("type") == "premium-info-block":
            elem["v4_mode"] = True
    return validate_template_config(config)


def _agency_english_config() -> dict:
    name = "English Agency Motor"
    key = "agency_english"
    config = deepcopy(_agency_bilingual_config())
    config["template_name"] = name
    config["v7_master_key"] = key
    config["is_default"] = False

    elements = config["canvas"]["elements"]
    for e in elements:
        eid = e.get("id")
        if eid == "header_insurer_label":
            e["text"] = "Insurer: "
        elif eid == "cov_header_txt":
            e["text"] = "Coverage & Vehicle Information"
        elif eid == "lbl_customer":
            e["text"] = "Customer Name"
        elif eid == "lbl_cov_type":
            e["text"] = "Coverage Type"
        elif eid == "lbl_car_model":
            e["text"] = "Car Model"
        elif eid == "lbl_engine_cc":
            e["text"] = "Engine Capacity"
        elif eid == "lbl_ncd":
            e["text"] = "NCD"
        elif eid == "lbl_period":
            e["text"] = "Cover Period"
        elif eid == "lbl_valuation_type":
            e["text"] = "Valuation Type"
        elif eid == "lbl_sum_insured":
            e["text"] = "Vehicle Sum Insured"
        elif eid == "premium_info_block":
            e["labels"] = {
                "premium": "Insurance Premium",
                "roadtax": "Roadtax",
                "runner": "Runner Fee",
                "total": "TOTAL PAYABLE",
                "extras": "Purchased Extras",
            }
        elif eid == "qr_sub":
            e["text"] = "Scan to Pay"
        elif eid == "all_driver_title":
            e["text"] = "All Drivers Included"
        elif eid == "excess_label":
            e["text"] = "Policy Excess"
        elif eid == "specials_header_txt":
            e["text"] = "Your Benefits"
        elif eid == "addons_header_txt":
            e["text"] = "Available Add-ons (Optional)"
        elif eid == "footer_terms":
            e["text"] = "*Terms & Conditions Apply | Quotation Validity: {valid_until}"

    return validate_template_config(config)


def _agency_mandarin_config() -> dict:
    name = "Mandarin Agency Motor"
    key = "agency_mandarin"
    config = deepcopy(_agency_bilingual_config())
    config["template_name"] = name
    config["v7_master_key"] = key
    config["is_default"] = False

    elements = config["canvas"]["elements"]
    for e in elements:
        eid = e.get("id")
        if eid == "title_motor":
            e["text"] = "汽车保险 "
        elif eid == "title_quotation":
            e["text"] = "报价单"
        elif eid == "ref_label":
            e["text"] = "报价单号: "
        elif eid == "vehicle_no_label":
            e["text"] = "车牌号码: "
        elif eid == "header_insurer_label":
            e["text"] = "保险公司: "
        elif eid == "cov_header_txt":
            e["text"] = "车辆及保单资料"
        elif eid == "lbl_customer":
            e["text"] = "客户姓名"
        elif eid == "lbl_cov_type":
            e["text"] = "保单种类"
        elif eid == "lbl_car_model":
            e["text"] = "车型"
        elif eid == "lbl_engine_cc":
            e["text"] = "发动机排量"
        elif eid == "lbl_ncd":
            e["text"] = "无索偿折扣"
        elif eid == "lbl_period":
            e["text"] = "保单期限"
        elif eid == "lbl_valuation_type":
            e["text"] = "估价方式"
        elif eid == "lbl_sum_insured":
            e["text"] = "车辆保额"
        elif eid == "premium_info_block":
            e["labels"] = {
                "premium": "基本保费",
                "roadtax": "路税",
                "runner": "跑腿服务费",
                "total": "应付总额",
                "extras": "已购买附加项目",
            }
        elif eid == "pay_title":
            e["text"] = "付款方式"
        elif eid == "qr_title":
            e["text"] = "DuitNow 二维码"
        elif eid == "qr_sub":
            e["text"] = "扫码付款"
        elif eid == "qr_hint":
            e["text"] = "即时到账"
        elif eid == "all_driver_title":
            e["text"] = "受权驾驶员全面保障"
        elif eid == "all_driver_sub":
            e["text"] = "已包含所有合法驾驶人"
        elif eid == "excess_label":
            e["text"] = "自负额"
        elif eid == "specials_header_txt":
            e["text"] = "特别优惠与专享保障"
        elif eid == "addons_header_txt":
            e["text"] = "可添加项目 (额外收费)"
        elif eid == "footer_terms":
            e["text"] = "*适用条款及细则 | 报价有效期: {valid_until}"

    return validate_template_config(config)


def master_template_specs() -> list[dict]:
    # Canonical motor templates: Bilingual, Bilingual v2, Bilingual v3, Bilingual v4, English, and Mandarin presets
    return [
        {"key": "agency_bilingual", "name": "Bilingual Agency Motor", "is_default": False, "config": _agency_bilingual_config()},
        {"key": "agency_bilingual_v2", "name": "Bilingual Agency Motor v2", "is_default": False, "config": _agency_bilingual_v2_config()},
        {"key": "agency_bilingual_v3", "name": "Bilingual Agency Motor v3", "is_default": False, "config": _agency_bilingual_v3_config()},
        {"key": "agency_bilingual_v3_no_extras", "name": "Bilingual Agency Motor v3 (No Extras)", "is_default": False, "config": _agency_bilingual_v3_no_extras_config()},
        {"key": "agency_bilingual_v3_lump_sum", "name": "Bilingual Agency Motor v3 (Lump Sum Extras)", "is_default": False, "config": _agency_bilingual_v3_lump_sum_config()},
        {"key": "agency_bilingual_v4", "name": "Bilingual Agency Motor v4", "is_default": True, "config": _agency_bilingual_v4_config()},
        {"key": "agency_bilingual_v4_no_extras", "name": "Bilingual Agency Motor v4 (No Extras)", "is_default": False, "config": _agency_bilingual_v4_no_extras_config()},
        {"key": "agency_bilingual_v4_lump_sum", "name": "Bilingual Agency Motor v4 (Lump Sum Extras)", "is_default": False, "config": _agency_bilingual_v4_lump_sum_config()},
        {"key": "agency_english", "name": "English Agency Motor", "is_default": False, "config": _agency_english_config()},
        {"key": "agency_mandarin", "name": "Mandarin Agency Motor", "is_default": False, "config": _agency_mandarin_config()},
    ]


def ensure_master_templates(db, user, *, apply: bool = False, force: bool = False, target_keys: list[str] | None = None) -> dict:
    """Create and publish missing canonical masters without overwriting a published revision unless force is True."""
    templates = list(db.scalars(select(OutputTemplateConfig).where(OutputTemplateConfig.deleted_at.is_(None)).options(defer(OutputTemplateConfig.fixed_fields))).all())
    revisions = list(db.scalars(select(TemplateRevision).options(defer(TemplateRevision.config))).all())
    report = {"created": [], "published": [], "retained": [], "default_cleared": [], "apply": apply}
    by_key = {str((item.fixed_fields or {}).get("v7_master_key") or ""): item for item in templates}
    specs = [s for s in master_template_specs() if target_keys is None or s["key"] in target_keys]
    for spec in specs:
        current = by_key.get(spec["key"])
        published = [item for item in revisions if current and item.template_id == current.id and item.state == "published"]
        if current and published and not force:
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
        bilingual = by_key.get("agency_bilingual_v4") or by_key.get("agency_bilingual_v3") or by_key.get("agency_bilingual")
        for item in templates + list(by_key.values()):
            config = deepcopy(item.fixed_fields or {})
            wanted = bool(bilingual and item.id == bilingual.id)
            if bool(config.get("is_default")) == wanted:
                continue
            config["is_default"] = wanted
            item.fixed_fields = config
            flag_modified(item, "fixed_fields")
            report["default_cleared"].append(item.id)
        db.commit()
    return report
