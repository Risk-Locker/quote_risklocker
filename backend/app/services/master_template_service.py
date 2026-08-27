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


def _text(node_id: str, text: str, x: float, y: float, w: float, h: float, z: int, *, size: int | float = 14, weight: str = "600", color: str = INK, align: str = "left") -> dict:
    return {"id": node_id, "type": "text", "text": text, "x": x, "y": y, "w": w, "h": h, "z": z, "style": {"fontSize": size, "fontWeight": weight, "color": color, "textAlign": align}}


def _variable(node_id: str, variable_id: str, x: float, y: float, w: float, h: float, z: int, *, size: int | float = 14, weight: str = "700", color: str = INK, align: str = "left", prefix: str = "", suffix: str = "") -> dict:
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
        "layoutMode": "masonry", "columns": 3,
        "packing": {
            "strategy": "balanced", "alignment": "start", "aspectRatio": 3.2 if dense else 3.0,
            "referenceWidth": 220, "referenceHeight": 64,
            "gapRatio": 0.025 if dense else 0.04, "paddingRatio": 0.01 if dense else 0.015, "staggerRatio": 0.0,
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
    RED_COLOR = "#DC2626"
    BG_LIGHT = "#F8FAFC"

    elements = [
        # 1. Page Background
        _rectangle("page_bg", 0, 0, 794, height, 1, background="#FFFFFF", border=""),

        # 2. Header: Logos, Insurer Name, Quotation Ref, Vehicle No, and Top Divider
        _image("risklocker_logo", "risklocker_logo", 40, 32, 150, 42, 5),
        _variable("header_insurer_name", "insurance_company", 210, 36, 230, 34, 5, size=16, weight="800", color=DARK, align="left"),
        _text("ref_label", "Quotation Ref: ", 460, 36, 150, 16, 5, size=10.5, weight="500", color=MUTED_COLOR, align="right"),
        _variable("ref_val", "quotation_reference", 614, 36, 140, 16, 5, size=10.5, weight="700", color=MUTED_COLOR, align="left"),
        _text("vehicle_no_label", "Vehicle No: ", 460, 56, 150, 16, 5, size=10.5, weight="500", color=MUTED_COLOR, align="right"),
        _variable("vehicle_no_val", "vehicle_no", 614, 56, 140, 16, 5, size=10.5, weight="700", color=MUTED_COLOR, align="left"),
        _line("header_rule", 40, 82, 714, 2, color=BORDER_COLOR, height=1),

        # 3. Main Title
        _text("title_motor", "Motor Insurance ", 40, 94, 200, 34, 5, size=24, weight="800", color=DARK),
        _text("title_quotation", "Quotation", 236, 94, 160, 34, 5, size=24, weight="800", color=RED_COLOR),

        # 4. Left Column: Coverage & Vehicle Information Card (x=40, w=454, y=134, h=272)
        _rectangle("cov_header_bg", 40, 134, 454, 26, 2, background=NAVY, border="", radius=4),
        _text("cov_header_txt", "Coverage & Vehicle Information / 车辆及保单资料", 52, 139, 430, 16, 5, size=10, weight="700", color="#FFFFFF"),
        _rectangle("cov_table_bg", 40, 160, 454, 246, 2, background="#FFFFFF", border=BORDER_COLOR, radius=4),

        # Row 1: Customer Name
        _text("lbl_customer", "Customer / 客户姓名", 52, 164, 160, 14, 5, size=9.0, weight="600", color=LABEL_COLOR),
        _variable("val_customer", "customer_name", 216, 164, 266, 14, 5, size=9.5, weight="700", color=DARK),

        # Row 2: Coverage Type
        _text("lbl_cov_type", "Coverage Type / 保单种类", 52, 179, 160, 14, 5, size=9.0, weight="600", color=LABEL_COLOR),
        _variable("val_cov_type", "coverage_type", 216, 179, 266, 14, 5, size=9.5, weight="700", color=DARK),

        # Row 3: Car Model
        _text("lbl_car_model", "Car Model / 车型", 52, 194, 160, 14, 5, size=9.0, weight="600", color=LABEL_COLOR),
        _variable("val_car_model", "car_model", 216, 194, 266, 14, 5, size=9.5, weight="700", color=DARK),

        # Row 4: Vehicle CC
        _text("lbl_engine_cc", "Vehicle CC / 引擎容量", 52, 209, 160, 14, 5, size=9.0, weight="600", color=LABEL_COLOR),
        _variable("val_engine_cc", "engine_cc", 216, 209, 266, 14, 5, size=9.5, weight="700", color=DARK, suffix=" cc"),

        # Row 5: NCD
        _text("lbl_ncd", "NCD", 52, 224, 160, 14, 5, size=9.0, weight="600", color=LABEL_COLOR),
        _variable("val_ncd", "ncd_percent", 216, 224, 266, 14, 5, size=9.5, weight="700", color=DARK, suffix="%"),

        # Row 6: Coverage Period
        _text("lbl_period", "Cover of Period / 保单期限", 52, 239, 160, 14, 5, size=9.0, weight="600", color=LABEL_COLOR),
        _variable("val_period", "cover_period", 216, 239, 266, 14, 5, size=9.5, weight="700", color=DARK),

        # Row 7: Coverage / Sum Insured
        _text("lbl_sum_insured", "Vehicle Sum Insured / 车辆保额", 52, 254, 160, 14, 5, size=8.5, weight="600", color=LABEL_COLOR),
        _variable("val_sum_insured", "coverage_amount", 216, 254, 266, 14, 5, size=9.5, weight="700", color=DARK, prefix="RM "),

        # Dynamic Premium Block (Extras, Insurance Premium, Roadtax, Runner Fee, Total Premium)
        {
            "id": "premium_info_block",
            "type": "premium-info-block",
            "x": 52,
            "y": 270,
            "w": 430,
            "h": 132,
            "z": 5,
            "rowHeight": 14.5,
            "labels": {
                "premium": "Insurance Premium / 保费",
                "roadtax": "Roadtax / 路税",
                "runner": "Runner Fee / 服务费",
                "total": "Total Premium / 保费总额",
                "extras": "Extras / 附加项目",
            },
        },

        # 5. Right Column: Payment Method & Excess / All Driver Card (x=508, w=246, y=134, h=272)
        _rectangle("pay_card_bg", 508, 134, 246, 272, 2, background="#FFFFFF", border=BORDER_COLOR, radius=6),
        _text("pay_title", "Payment Method", 522, 144, 218, 15, 5, size=10, weight="700", color=LABEL_COLOR),
        _text("pay_bank_logo", "Hong Leong", 522, 161, 218, 18, 5, size=12.5, weight="800", color=DARK),
        _text("pay_details_lbl", "Bank details", 522, 181, 218, 13, 5, size=8.5, weight="600", color=MUTED_COLOR),
        _text("pay_acc_no", "12303105859", 522, 195, 218, 15, 5, size=11, weight="700", color=DARK),
        _text("pay_holder", "RiskLocker Sdn. Bhd.", 522, 211, 218, 13, 5, size=9, weight="600", color=LABEL_COLOR),
        _text("pay_bank_sub", "Hong Leong Bank", 522, 225, 218, 13, 5, size=9, weight="500", color=MUTED_COLOR),

        # All Driver & Excess Box inside right card
        _rectangle("all_driver_bg", 518, 242, 226, 156, 3, background=BG_LIGHT, border=BORDER_COLOR, radius=4),
        _text("all_driver_title", "All Driver Included", 528, 249, 206, 15, 5, size=10, weight="700", color=DARK),
        _text("all_driver_sub", "Authorised Drivers Covered", 528, 264, 206, 13, 5, size=8.5, weight="500", color=MUTED_COLOR),
        _line("divider_driver_excess", 528, 280, 206, 4, color=BORDER_COLOR, height=1),
        _text("excess_label", "Policy Excess / 自负额", 528, 286, 206, 14, 5, size=9, weight="600", color=LABEL_COLOR),
        _variable("excess_val", "excess_amount", 528, 301, 206, 16, 5, size=11, weight="800", color=DARK, prefix="RM "),
        _text("excess_note", "Compulsory Excess as per quotation", 528, 318, 206, 12, 5, size=7.5, weight="500", color=MUTED_COLOR),

        # 6. Section 1: Our Specials / 特别优惠 (Included Benefits Grid)
        _rectangle("specials_header_bg", 40, 414, 714, 26, 2, background=NAVY, border="", radius=4),
        _text("specials_header_txt", "Our Specials / 特别优惠", 52, 419, 690, 16, 5, size=10.5, weight="700", color="#FFFFFF"),
        _grid("current_benefits_grid", "current_benefits", 40, 444, 714, 314, 4, dense=True),

        # 7. Section 2: You May Add On / 可添加项目 (Available Add-ons Grid)
        _rectangle("addons_header_bg", 40, 766, 714, 26, 2, background=NAVY, border="", radius=4),
        _text("addons_header_txt", "You May Add On (With Additional Charges) / 可添加项目 (额外收费)", 52, 771, 690, 16, 5, size=10.5, weight="700", color="#FFFFFF"),
        _grid("available_addons_grid", "available_addons", 40, 796, 714, 262, 4, dense=True),

        # 8. Footer
        _text("footer_terms", "*Terms & Conditions Apply | Quotation Validity: {valid_until}", 40, 1068, 714, 16, 5, size=8.5, weight="500", color=MUTED_COLOR),
    ]

    config.update({
        "version": 7, "template_name": name, "v7_master_key": key, "is_default": False, "locked": True,
        "page_profile": {
            "profile_key": "a4", "name": "A4",
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
        {"key": "agency_bilingual", "name": "Bilingual Agency Motor", "is_default": False, "config": _agency_bilingual_config()},
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
