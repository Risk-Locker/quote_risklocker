"""Template Section Compiler (Backend Mirror).

Provides deterministic compilation between structured section configurations
and canonical canvas.elements for template revisions and automated tests.
"""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any


CANONICAL_VARIABLE_LABELS: dict[str, tuple[str, str]] = {
    "customer_name": ("Customer", "客户姓名"),
    "coverage_type": ("Coverage Type", "保单种类"),
    "car_model": ("Car Model", "车型"),
    "engine_cc": ("Engine Capacity", "发动机排量 :"),
    "ncd_percent": ("NCD", ""),
    "cover_period": ("Cover of Period", "保单期限"),
    "valuation_type": ("Valuation Type", "估价方式"),
    "excess_amount": ("Policy Excess", "自负额"),
    "coverage_amount": ("Vehicle Sum Insured", "车辆保额"),
}

DEFAULT_VEHICLE_FIELDS = [
    {"id": "customer", "variableId": "customer_name", "labelEn": "Customer", "labelZh": "客户姓名", "visible": True, "rowOrder": 0},
    {"id": "coverage_type", "variableId": "coverage_type", "labelEn": "Coverage Type", "labelZh": "保单种类", "visible": True, "rowOrder": 1},
    {"id": "car_model", "variableId": "car_model", "labelEn": "Car Model", "labelZh": "车型", "visible": True, "rowOrder": 2},
    {"id": "engine_cc", "variableId": "engine_cc", "labelEn": "Engine Capacity", "labelZh": "发动机排量 :", "visible": True, "rowOrder": 3},
    {"id": "ncd_percent", "variableId": "ncd_percent", "labelEn": "NCD", "labelZh": "", "suffix": "%", "visible": True, "rowOrder": 4},
    {"id": "cover_period", "variableId": "cover_period", "labelEn": "Cover of Period", "labelZh": "保单期限", "visible": True, "rowOrder": 5},
    {"id": "valuation_type", "variableId": "valuation_type", "labelEn": "Valuation Type", "labelZh": "估价方式", "visible": True, "rowOrder": 6},
    {"id": "coverage_amount", "variableId": "coverage_amount", "labelEn": "Vehicle Sum Insured", "labelZh": "车辆保额", "prefix": "RM ", "visible": True, "rowOrder": 7},
]


def default_header_config(is_v2: bool = False) -> dict[str, Any]:
    return {
        "layout": "right_3_rows",
        "rowsOrder": ["ref", "vehicle", "insurer"],
        "insurerPosition": "row3",
        "refLabel": "Quotation Ref: ",
        "vehicleLabel": "Vehicle No: ",
        "insurerLabel": "Insurer: ",
        "fontSize": 10.0,
        "logoX": 40.0,
        "logoY": 20.0 if is_v2 else 8.0,
        "logoW": 32.0 if is_v2 else 72.0,
        "logoH": 40.0 if is_v2 else 74.0,
    }


def default_right_containers() -> list[dict[str, Any]]:
    return [
        {
            "id": "rc_container_payment",
            "title": "Payment Method Card",
            "layout": "payment_grid",
            "boxX": 508,
            "boxY": 134,
            "boxW": 246,
            "boxH": 68,
            "background": "#FFFFFF",
            "borderWidth": 1,
            "borderColor": "#E2E8F0",
            "borderRadius": 6,
            "padding": 9,
            "gap": 3,
            "blocks": [
                {
                    "id": "rc_b_pay_title",
                    "type": "text",
                    "text": "Payment Methods :",
                    "fontSize": 9.5,
                    "fontWeight": "700",
                    "color": "#334155",
                    "textAlign": "left",
                    "order": 0,
                },
                {
                    "id": "rc_b_pay_details",
                    "type": "text",
                    "text": "Bank Details : 12300318500\nRiskLocker Sdn. Bhd.",
                    "fontSize": 8.5,
                    "fontWeight": "600",
                    "color": "#475569",
                    "textAlign": "left",
                    "order": 1,
                },
                {
                    "id": "rc_b_bank_logo",
                    "type": "image",
                    "assetSlot": "bank_logo",
                    "assetId": "2168eaee-3e56-4903-8c4f-841f01ff2407",
                    "imageWidth": 72,
                    "imageHeight": 28,
                    "imageFit": "contain",
                    "order": 2,
                },
            ],
        },
        {
            "id": "rc_container_qr",
            "title": "DuitNow QR Card",
            "layout": "row",
            "boxX": 508,
            "boxY": 210,
            "boxW": 246,
            "boxH": 78,
            "background": "#FFFFFF",
            "borderWidth": 1,
            "borderColor": "#E2E8F0",
            "borderRadius": 6,
            "padding": 8,
            "gap": 8,
            "blocks": [
                {
                    "id": "rc_b_qr_code",
                    "type": "image",
                    "assetSlot": "qr_code",
                    "assetId": "c2003185-0000-4000-8000-000000000001",
                    "imageWidth": 70,
                    "imageHeight": 70,
                    "imageFit": "contain",
                    "order": 0,
                },
                {
                    "id": "rc_b_qr_text",
                    "type": "text",
                    "text": "DuitNow QR\nScan to Pay / 扫码付款\nInstant Verification",
                    "fontSize": 8.5,
                    "fontWeight": "700",
                    "color": "#0F172A",
                    "textAlign": "left",
                    "order": 1,
                },
            ],
        },
        {
            "id": "rc_container_drivers",
            "title": "All Drivers & Excess Card",
            "layout": "column",
            "boxX": 508,
            "boxY": 296,
            "boxW": 246,
            "boxH": 74,
            "background": "#F8FAFC",
            "borderWidth": 1,
            "borderColor": "#E2E8F0",
            "borderRadius": 6,
            "padding": 9,
            "gap": 4,
            "blocks": [
                {
                    "id": "rc_b_driver_title",
                    "type": "text",
                    "text": "All Drivers Included / 全司机投保",
                    "fontSize": 9.5,
                    "fontWeight": "700",
                    "color": "#0F172A",
                    "textAlign": "left",
                    "order": 0,
                },
                {
                    "id": "rc_b_driver_sub",
                    "type": "text",
                    "text": "Authorised Drivers Covered",
                    "fontSize": 8,
                    "fontWeight": "500",
                    "color": "#64748B",
                    "textAlign": "left",
                    "order": 1,
                },
                {
                    "id": "rc_b_driver_divider",
                    "type": "divider",
                    "dividerColor": "#E2E8F0",
                    "dividerHeight": 1,
                    "order": 2,
                },
                {
                    "id": "rc_b_excess_val",
                    "type": "variable",
                    "variableId": "excess_amount",
                    "prefix": "Policy Excess : RM ",
                    "fontSize": 9.5,
                    "fontWeight": "700",
                    "color": "#0F172A",
                    "textAlign": "left",
                    "order": 3,
                },
            ],
        },
    ]


def default_right_containers_v2() -> list[dict[str, Any]]:
    return [
        {
            "id": "rc_container_payment",
            "title": "DuitNow QR & Payment Details",
            "layout": "column",
            "boxX": 584,
            "boxY": 94,
            "boxW": 170,
            "boxH": 236,
            "background": "#FFFFFF",
            "borderWidth": 1,
            "borderColor": "#E2E8F0",
            "borderRadius": 6,
            "padding": 3,
            "gap": 0,
            "blocks": [
                {
                    "id": "payment_account_details_img",
                    "type": "image",
                    "assetSlot": "duitnow_payment_details",
                    "assetId": "c3003185-0000-4000-8000-000000000001",
                    "imageWidth": 154,
                    "imageHeight": 230,
                    "imageFit": "contain",
                    "order": 0,
                },
            ],
        },
        {
            "id": "rc_container_drivers",
            "title": "All Drivers Card",
            "layout": "column",
            "boxX": 584,
            "boxY": 336,
            "boxW": 170,
            "boxH": 42,
            "background": "#F8FAFC",
            "borderWidth": 1,
            "borderColor": "#E2E8F0",
            "borderRadius": 6,
            "padding": 4,
            "gap": 2,
            "blocks": [
                {
                    "id": "all_driver_title",
                    "type": "text",
                    "text": "All Drivers Included/全司机投保",
                    "fontSize": 8.5,
                    "fontWeight": "700",
                    "color": "#0F172A",
                    "textAlign": "center",
                    "order": 0,
                },
                {
                    "id": "all_driver_sub",
                    "type": "text",
                    "text": "Authorised Drivers Covered",
                    "fontSize": 7.5,
                    "fontWeight": "500",
                    "color": "#64748B",
                    "textAlign": "center",
                    "order": 1,
                },
            ],
        },
    ]


def extract_sections_from_canvas(elements: list[dict[str, Any]], saved_sections: dict[str, Any] | None = None) -> dict[str, Any]:
    """Extract structured section slots from canvas elements or return saved_sections."""
    is_v2 = any(
        e.get("id") == "payment_account_details_img"
        or e.get("assetSlot") == "duitnow_payment_details"
        or e.get("id") == "val_excess"
        for e in elements
    )
    rc_default = default_right_containers_v2() if is_v2 else default_right_containers()

    if saved_sections and saved_sections.get("version") == 1 and saved_sections.get("section1", {}).get("vehicleFields"):
        res = deepcopy(saved_sections)
        # Sanitize saved vehicleFields: remove insurer_name and heal corrupted raw variable labels
        sanitized_fields = []
        for f in res.get("section1", {}).get("vehicleFields", []):
            var_id = str(f.get("variableId") or "")
            fid = str(f.get("id") or "")
            lbl_en = str(f.get("labelEn") or "")
            if var_id in {"insurance_company", "quotation_reference", "vehicle_no"} or fid in {"header_insurer_name", "top_insurer_name", "insurer_name"}:
                continue
            if var_id in CANONICAL_VARIABLE_LABELS:
                c_en, c_zh = CANONICAL_VARIABLE_LABELS[var_id]
                if not f.get("labelZh") or lbl_en.startswith(("val_", "value_", "field_", "label_", "header_insurer")) or lbl_en == fid:
                    f["labelEn"] = c_en
                    f["labelZh"] = c_zh
            f["rowOrder"] = len(sanitized_fields)
            sanitized_fields.append(f)
        if not res.get("header"):
            res["header"] = default_header_config(is_v2)
        if not res.get("rightContainers") or (is_v2 and any(float(c.get("boxW") or 0) > 200 for c in res.get("rightContainers", []))):
            res["rightContainers"] = rc_default
        return res

    value_elements = [
        e for e in elements
        if e.get("type") == "variable" and (str(e.get("id", "")).startswith(("value_", "val_")) or e.get("variableId"))
    ]
    sorted_values = sorted(value_elements, key=lambda x: float(x.get("y", 0)))

    detected_fields: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for i, val_elem in enumerate(sorted_values):
        eid = str(val_elem.get("id", ""))
        if eid.startswith("value_val_"):
            raw_key = eid[10:]
        elif eid.startswith("value_"):
            raw_key = eid[6:]
        elif eid.startswith("val_"):
            raw_key = eid[4:]
        else:
            raw_key = eid or str(val_elem.get("variableId") or f"field_{i}")

        if raw_key.startswith("val_"):
            raw_key = raw_key[4:]

        if raw_key in seen_ids:
            continue
        if (
            raw_key in {"quote_vehicle", "validity", "header_insurer_name", "top_insurer_name", "ref_val", "vehicle_no_val", "header_insurer", "insurer_name"}
            or val_elem.get("variableId") in {"insurance_company", "quotation_reference", "vehicle_no"}
            or float(val_elem.get("y", 0)) < 90
            or float(val_elem.get("x", 0)) > 400
        ):
            continue

        seen_ids.add(raw_key)
        label_elem = next((e for e in elements if e.get("id") in {f"label_{raw_key}", f"lbl_{raw_key}", f"label_val_{raw_key}", f"lbl_val_{raw_key}"}), None)
        raw_label = str(label_elem.get("text", "") if label_elem else raw_key)

        label_en = raw_label
        label_zh = ""
        if "/" in raw_label:
            parts = raw_label.split("/", 1)
            label_en = parts[0].strip()
            label_zh = parts[1].strip()

        # Sanitize against corrupted labels (e.g. val_customer, val_cov_type, or missing translations)
        var_id = str(val_elem.get("variableId") or "")
        if var_id in CANONICAL_VARIABLE_LABELS:
            c_en, c_zh = CANONICAL_VARIABLE_LABELS[var_id]
            if (
                not label_zh
                or label_en.startswith(("val_", "value_", "field_", "label_", "header_insurer"))
                or label_en == raw_key
                or "/" not in raw_label
            ):
                label_en, label_zh = c_en, c_zh

        style = val_elem.get("style") or {}
        detected_fields.append({
            "id": raw_key,
            "variableId": val_elem.get("variableId", raw_key),
            "labelEn": label_en or raw_key,
            "labelZh": label_zh,
            "prefix": val_elem.get("prefix"),
            "suffix": val_elem.get("suffix"),
            "fontSize": style.get("fontSize"),
            "fontWeight": style.get("fontWeight"),
            "color": style.get("color"),
            "visible": val_elem.get("visible", True) is not False,
            "rowOrder": len(detected_fields),
        })

    final_fields = detected_fields if detected_fields else deepcopy(DEFAULT_VEHICLE_FIELDS)
    terms_elem = next((e for e in elements if e.get("id") == "terms"), None)

    return {
        "version": 1,
        "header": saved_sections.get("header") if saved_sections and saved_sections.get("header") else default_header_config(is_v2),
        "section1": {
            "vehicleFields": final_fields,
            "headerTitleEn": "Coverage & Vehicle Information",
            "headerTitleZh": "保障与车辆信息",
        },
        "rightContainers": rc_default,
        "footer": {
            "bankName": "Hong Leong Bank",
            "accountNo": "12300318500",
            "accountHolder": "Risklocker Sdn. Bhd.",
            "termsNotice": str(terms_elem.get("text", "*Terms and Condition Applied")) if terms_elem else "*Terms and Condition Applied",
        },
    }


SAMPLE_SIMULATED_EXTRAS = [
    {"id": "sim_extra_1", "labelEn": "Driver PA", "labelZh": "司机个人意外险", "price": "RM 300.00"},
    {"id": "sim_extra_2", "labelEn": "Windscreen Repair (RM 4,000)", "labelZh": "挡风玻璃保障", "price": "RM 600.00"},
    {"id": "sim_extra_3", "labelEn": "Special Perils (Flood) (RM 55,000)", "labelZh": "天灾特别风险", "price": "RM 110.00"},
    {"id": "sim_extra_4", "labelEn": "Legal Liability to Passengers", "labelZh": "乘客法律责任险", "price": "RM 25.00"},
    {"id": "sim_extra_5", "labelEn": "Key Care & Replacement (RM 1,500)", "labelZh": "车钥匙重置保障", "price": "RM 35.00"},
    {"id": "sim_extra_6", "labelEn": "All Authorized Drivers Protection", "labelZh": "全司机驾驶保障", "price": "RM 50.00"},
    {"id": "sim_extra_7", "labelEn": "Waiver of Betterment (10 Years)", "labelZh": "豁免折旧费用", "price": "RM 120.00"},
    {"id": "sim_extra_8", "labelEn": "24/7 Unlimited Towing & Roadside", "labelZh": "无限距离拖车救援", "price": "RM 80.00"},
]


def get_lump_sum_extras_price(count: int = 0) -> str:
    num_items = min(count, len(SAMPLE_SIMULATED_EXTRAS)) if count > 0 else 1
    total = 0.0
    for i in range(num_items):
        raw_price = re.sub(r"[^0-9.]", "", SAMPLE_SIMULATED_EXTRAS[i]["price"])
        total += float(raw_price) if raw_price else 0.0
    return f"RM {total:.2f}"


def compile_sections_to_canvas(
    sections: dict[str, Any],
    base_elements: list[dict[str, Any]],
    simulated_extras_count: int = 0,
) -> list[dict[str, Any]]:
    """Compile structured sections into valid, canonical CanvasElement list."""
    fields = sorted(
        list(sections.get("section1", {}).get("vehicleFields") or []),
        key=lambda x: int(x.get("rowOrder", 0)),
    )
    visible_fields = [f for f in fields if f.get("visible", True) is not False]

    extras_mode = sections.get("section1", {}).get("extrasDisplayMode", "itemized")
    simulated_count = max(0, min(simulated_extras_count, len(SAMPLE_SIMULATED_EXTRAS)))
    has_itemized_extras = (extras_mode == "itemized" and simulated_count > 0)
    extra_rows_count = 0 if extras_mode == "none" else (1 if extras_mode == "lump_sum" else ((1 + simulated_count) if has_itemized_extras else 0))
    total_rows = len(visible_fields) + extra_rows_count

    has_cov_table = any(e.get("id") == "cov_table_bg" for e in base_elements)
    first_label = next((e for e in base_elements if (str(e.get("id", "")).startswith("label_") or str(e.get("id", "")).startswith("lbl_")) and "sim_extra" not in str(e.get("id", ""))), None)
    first_colon = next((e for e in base_elements if (str(e.get("id", "")).startswith("colon_") or str(e.get("id", "")).startswith("col_")) and "sim_extra" not in str(e.get("id", ""))), None)
    first_value = next((e for e in base_elements if (str(e.get("id", "")).startswith("value_") or str(e.get("id", "")).startswith("val_")) and "sim_extra" not in str(e.get("id", ""))), None)

    has_dense_layout = first_label is not None and (float(first_label.get("h", 24)) <= 16 or float(first_label.get("x", 16)) >= 40)

    label_x = float(first_label.get("x", 52 if has_dense_layout else 16)) if first_label else (52.0 if has_dense_layout else 16.0)
    colon_x = float(first_colon.get("x", 207)) if first_colon else 207.0
    value_x = float(first_value.get("x", 216 if has_dense_layout else 231)) if first_value else (216.0 if has_dense_layout else 231.0)
    start_y = float(first_label.get("y", 164)) if first_label else 164.0
    label_w = float(first_label.get("w", 160 if has_dense_layout else 190)) if first_label else (160.0 if has_dense_layout else 190.0)
    value_w = float(first_value.get("w", 266 if has_dense_layout else 215)) if first_value else (266.0 if has_dense_layout else 215.0)
    elem_h = float(first_label.get("h", 14 if has_dense_layout else 24)) if first_label else (14.0 if has_dense_layout else 24.0)

    if sections.get("section1", {}).get("rowHeight"):
        row_h = float(sections["section1"]["rowHeight"])
    elif has_dense_layout:
        row_h = 14.0
    else:
        row_h = 28.0

    right_container_ids = {
        "pay_card_bg", "pay_title", "bank_logo", "pay_bank_logo", "pay_details_lbl", "pay_acc_no", "pay_holder",
        "qr_card_bg", "qr_code_img", "qr_title", "qr_sub", "qr_hint", "qr_badge",
        "all_driver_bg", "all_driver_title", "all_driver_sub", "divider_driver_excess",
        "excess_label", "excess_val", "compulsory_excess_label", "compulsory_excess_val",
        "excess_note", "payment_box", "payment_text", "pay_bank_sub", "driver_box",
        "driver_icon", "driver_text", "rc_container_main",
        "rc_container_payment", "rc_container_qr", "rc_container_drivers",
        "grp_payment_card", "grp_qr_card", "grp_excess_card",
        "payment_account_details_img",
    }

    right_containers = sections.get("rightContainers") or []
    has_right_containers = len(right_containers) > 0

    ghost_ids = {
        "group_4pysxhb", "group_4pysxhb--rectangle", "text_3yr0mvi",
        "text_ltaa394", "text_ul2w5ka", "group_90j9e0t",
        "group_4b1q6op", "group_ovsuz2u", "group_ovsuz2u--rectangle",
    }

    remaining = []
    for e in base_elements:
        eid = str(e.get("id", ""))
        etype = str(e.get("type", ""))
        ex = float(e.get("x", 0) or 0)
        ey = float(e.get("y", 0) or 0)
        if eid.startswith(("label_", "colon_", "value_", "lbl_", "val_", "col_")) or "sim_extra" in eid or eid == "label_sim_extras_header":
            continue
        if eid == "premium_info_block" or etype == "premium-info-block":
            continue
        if eid in ghost_ids or etype == "special":
            continue
        if eid in right_container_ids or eid.startswith("rc_") or eid.startswith("rc_b_"):
            continue
        if ex >= 480 and 90 <= ey <= 430 and eid not in {"quote_vehicle", "validity"}:
            continue
        remaining.append(deepcopy(e))

    premium_idx = -1
    for idx, f in enumerate(visible_fields):
        if f.get("variableId") == "premium" or f.get("id") in {"premium", "insurance_premium"}:
            premium_idx = idx
            break
    insert_extras_after_idx = premium_idx if premium_idx != -1 else len(visible_fields) - 1

    compiled_rows: list[dict[str, Any]] = []
    current_render_row = 0
    for idx, field in enumerate(visible_fields):
        curr_y = start_y + (current_render_row * row_h)
        zh = field.get("labelZh")
        combined_label = f"{field.get('labelEn')} / {zh}" if zh else str(field.get("labelEn"))
        fid = str(field.get("id"))
        font_size = field.get("fontSize") or (9.0 if has_cov_table else 12)
        font_weight = str(field.get("fontWeight") or ("600" if has_cov_table else "700"))
        color = str(field.get("color") or ("#64748B" if has_cov_table else "#111111"))

        # Label
        compiled_rows.append({
            "id": f"label_{fid}",
            "type": "text",
            "x": label_x,
            "y": curr_y,
            "w": label_w,
            "h": elem_h,
            "z": 2,
            "text": combined_label,
            "style": {"fontSize": font_size, "fontWeight": font_weight, "color": color, "textAlign": "left"},
        })
        # Colon
        compiled_rows.append({
            "id": f"colon_{fid}",
            "type": "text",
            "x": colon_x,
            "y": curr_y,
            "w": 12.0,
            "h": elem_h,
            "z": 2,
            "text": ":",
            "style": {"fontSize": font_size, "fontWeight": "400", "color": color, "textAlign": "left"},
        })
        # Value
        var_id = field.get("variableId")
        val_font_size = field.get("fontSize") or (9.5 if has_cov_table else 12)
        val_font_weight = str(field.get("fontWeight") or "700")
        val_color = str(field.get("color") or ("#0F172A" if has_cov_table else "#111111"))
        compiled_rows.append({
            "id": f"value_{fid}",
            "type": "variable" if var_id else "text",
            "variableId": var_id,
            "text": field.get("fixedValue"),
            "prefix": field.get("prefix"),
            "suffix": field.get("suffix"),
            "x": value_x,
            "y": curr_y,
            "w": value_w,
            "h": elem_h,
            "z": 2,
            "style": {"fontSize": val_font_size, "fontWeight": val_font_weight, "color": val_color, "textAlign": "left"},
        })
        current_render_row += 1

        if idx == insert_extras_after_idx:
            if extras_mode == "lump_sum":
                lump_y = start_y + (current_render_row * row_h)
                compiled_rows.append({
                    "id": "label_extras_lump",
                    "type": "text",
                    "x": label_x,
                    "y": lump_y,
                    "w": label_w,
                    "h": elem_h,
                    "z": 2,
                    "text": "Extras / 附加项目",
                    "style": {"fontSize": 12, "fontWeight": "700", "color": "#111111", "textAlign": "left"},
                })
                compiled_rows.append({
                    "id": "colon_extras_lump",
                    "type": "text",
                    "x": colon_x,
                    "y": lump_y,
                    "w": 12.0,
                    "h": elem_h,
                    "z": 2,
                    "text": ":",
                    "style": {"fontSize": 12, "fontWeight": "400", "color": "#111111", "textAlign": "left"},
                })
                compiled_rows.append({
                    "id": "value_extras_lump",
                    "type": "variable",
                    "variableId": "total_optional_cover_amount",
                    "text": get_lump_sum_extras_price(simulated_count),
                    "prefix": "RM ",
                    "x": value_x,
                    "y": lump_y,
                    "w": value_w,
                    "h": elem_h,
                    "z": 2,
                    "style": {"fontSize": 12, "fontWeight": "700", "color": "#111111", "textAlign": "left"},
                })
                current_render_row += 1
            elif has_itemized_extras:
                hdr_y = start_y + (current_render_row * row_h)
                compiled_rows.append({
                    "id": "label_sim_extras_header",
                    "type": "text",
                    "x": label_x,
                    "y": hdr_y,
                    "w": label_w + colon_x + value_w,
                    "h": elem_h,
                    "z": 2,
                    "text": "Extras / 附加项目 :",
                    "style": {"fontSize": 10, "fontWeight": "800", "color": "#0F172A", "textAlign": "left", "letterSpacing": "0.5px"},
                })
                current_render_row += 1

                for e_idx in range(simulated_count):
                    extra = SAMPLE_SIMULATED_EXTRAS[e_idx]
                    e_y = start_y + (current_render_row * row_h)
                    e_zh = extra.get("labelZh")
                    e_lbl = f"{extra['labelEn']} / {e_zh}" if e_zh else extra["labelEn"]

                    compiled_rows.append({
                        "id": f"label_sim_extra_{e_idx}",
                        "type": "text",
                        "x": label_x,
                        "y": e_y,
                        "w": label_w,
                        "h": elem_h,
                        "z": 2,
                        "text": e_lbl,
                        "style": {"fontSize": 10.5, "fontWeight": "600", "color": "#334155", "textAlign": "left"},
                    })
                    compiled_rows.append({
                        "id": f"colon_sim_extra_{e_idx}",
                        "type": "text",
                        "x": colon_x,
                        "y": e_y,
                        "w": 12.0,
                        "h": elem_h,
                        "z": 2,
                        "text": ":",
                        "style": {"fontSize": 10.5, "fontWeight": "400", "color": "#334155", "textAlign": "left"},
                    })
                    compiled_rows.append({
                        "id": f"value_sim_extra_{e_idx}",
                        "type": "text",
                        "text": extra["price"],
                        "x": value_x,
                        "y": e_y,
                        "w": value_w,
                        "h": elem_h,
                        "z": 2,
                        "style": {"fontSize": 11, "fontWeight": "700", "color": "#0F172A", "textAlign": "left"},
                    })
                    current_render_row += 1

    has_val_authorized_driver = any(e.get("id") == "val_authorized_driver" for e in base_elements)
    is_v2_layout = any(e.get("id") in {"payment_account_details_img", "val_excess"} for e in base_elements) or any(float(c.get("boxY", 0)) <= 100 for c in right_containers)
    baseline_count = 10 if has_val_authorized_driver else (9 if is_v2_layout else 8)
    delta_y = max(0.0, float(len(visible_fields) - baseline_count) * row_h) if has_dense_layout else max(0.0, float(total_rows - 9) * row_h)

    # In production mode (when simulated extras are not requested), append canonical premium_info_block
    if not has_itemized_extras and has_dense_layout:
        premium_y = start_y + (len(visible_fields) * row_h)
        compiled_rows.append({
            "id": "premium_info_block",
            "type": "premium-info-block",
            "x": 52.0,
            "y": premium_y,
            "w": 506.0 if is_v2_layout else 430.0,
            "h": 130.0,
            "z": 4,
            "rowHeight": row_h,
            "extras_mode": extras_mode,
            "labels": {
                "extras": "EXTRAS / 附加项目",
                "premium": "Insurance Premium / 保费",
                "roadtax": "Roadtax and Runner Fee / 路税及服务费",
                "runner": "Runner Fee / 服务费",
                "total": "TOTAL PAYABLE",
            },
            "locked": True,
        })

    # Compile Right Containers
    compiled_right_blocks: list[dict[str, Any]] = []
    if has_right_containers:
        is_multi_box = len(right_containers) > 1
        for c_idx, container in enumerate(right_containers):
            is_last_or_bottom = not is_multi_box or c_idx == len(right_containers) - 1 or str(container.get("id")) == "rc_container_drivers" or float(container.get("boxY", 0)) >= 300
            box_x = float(container.get("boxX", 508))
            box_y = float(container.get("boxY", 134))
            box_w = float(container.get("boxW", 246))
            base_h = float(container.get("boxH", 80 if is_multi_box else 272))
            box_h = base_h + delta_y if is_last_or_bottom else base_h
            padding = float(container.get("padding", 10))
            gap = float(container.get("gap", 6))

            compiled_right_blocks.append({
                "id": str(container.get("id", "rc_container_main")),
                "type": "rectangle",
                "x": box_x,
                "y": box_y,
                "w": box_w,
                "h": box_h,
                "z": 2,
                "style": {
                    "background": container.get("background", "#FFFFFF"),
                    "borderWidth": container.get("borderWidth", 1),
                    "borderColor": container.get("borderColor", "#E2E8F0"),
                    "borderRadius": container.get("borderRadius", 6),
                },
            })

            blocks = sorted(
                list(container.get("blocks") or []),
                key=lambda x: int(x.get("order", 0)),
            )
            visible_blocks = [b for b in blocks if b.get("visible", True) is not False]

            if container.get("layout") == "payment_grid" or (str(container.get("id")) == "rc_container_payment" and (not container.get("layout") or container.get("layout") == "payment_grid")):
                curr_y = box_y + padding
                b_w = box_w - (padding * 2)
                b_x = box_x + padding
                pay_title = next((b for b in visible_blocks if "title" in str(b.get("id"))), visible_blocks[0] if visible_blocks else None)
                pay_details = next((b for b in visible_blocks if "details" in str(b.get("id"))), None)
                bank_logo = next((b for b in visible_blocks if b.get("type") == "image" or "bank" in str(b.get("id"))), None)

                if pay_title:
                    fs = float(pay_title.get("fontSize", 9.5))
                    compiled_right_blocks.append({
                        "id": str(pay_title.get("id")),
                        "type": "text",
                        "x": b_x,
                        "y": curr_y,
                        "w": b_w,
                        "h": 14.0,
                        "z": 3,
                        "text": str(pay_title.get("text", "Payment Methods :")),
                        "style": {
                            "fontSize": fs,
                            "fontWeight": str(pay_title.get("fontWeight", "700")),
                            "color": str(pay_title.get("color", "#334155")),
                            "textAlign": str(pay_title.get("textAlign", "left")),
                        },
                    })
                    curr_y += 14.0 + gap

                sub_y = curr_y
                left_w = 150.0
                right_w = 72.0
                sub_h = 28.0

                if pay_details:
                    text = str(pay_details.get("text", "Bank Details : 12300318500\nRiskLocker Sdn. Bhd."))
                    fs = float(pay_details.get("fontSize", 8.5))
                    compiled_right_blocks.append({
                        "id": str(pay_details.get("id")),
                        "type": "text",
                        "x": b_x,
                        "y": sub_y,
                        "w": left_w,
                        "h": sub_h,
                        "z": 3,
                        "text": text,
                        "style": {
                            "fontSize": fs,
                            "fontWeight": str(pay_details.get("fontWeight", "600")),
                            "color": str(pay_details.get("color", "#475569")),
                            "textAlign": str(pay_details.get("textAlign", "left")),
                        },
                    })

                if bank_logo:
                    logo_x = box_x + box_w - padding - right_w
                    compiled_right_blocks.append({
                        "id": str(bank_logo.get("id")),
                        "type": "image",
                        "x": logo_x,
                        "y": sub_y,
                        "w": right_w,
                        "h": sub_h,
                        "z": 3,
                        "assetSlot": bank_logo.get("assetSlot", "bank_logo"),
                        "assetId": bank_logo.get("assetId", "2168eaee-3e56-4903-8c4f-841f01ff2407"),
                    })
            elif container.get("layout") == "row":
                curr_x = box_x + padding
                b_y = box_y + padding
                avail_h = box_h - (padding * 2)
                for b in visible_blocks:
                    b_type = b.get("type")
                    if b_type == "image":
                        b_w = float(b.get("imageWidth", 64))
                        b_h = min(avail_h, float(b.get("imageHeight", avail_h)))
                        compiled_right_blocks.append({
                            "id": str(b.get("id")),
                            "type": "image",
                            "x": curr_x,
                            "y": b_y + (avail_h - b_h) / 2,
                            "w": b_w,
                            "h": b_h,
                            "z": 3,
                            "assetSlot": b.get("assetSlot"),
                            "assetId": b.get("assetId"),
                        })
                        curr_x += b_w + gap
                    elif b_type == "text":
                        b_w = max(60.0, box_x + box_w - padding - curr_x)
                        compiled_right_blocks.append({
                            "id": str(b.get("id")),
                            "type": "text",
                            "x": curr_x,
                            "y": b_y,
                            "w": b_w,
                            "h": avail_h,
                            "z": 3,
                            "text": str(b.get("text", "")),
                            "style": {
                                "fontSize": b.get("fontSize", 9),
                                "fontWeight": str(b.get("fontWeight", "500")),
                                "color": str(b.get("color", "#0F172A")),
                                "textAlign": str(b.get("textAlign", "left")),
                            },
                        })
                        curr_x += b_w + gap
            else:
                # Column stack
                curr_y = box_y + padding
                b_w = box_w - (padding * 2)
                b_x = box_x + padding
                for b in visible_blocks:
                    b_type = b.get("type")
                    if b_type == "image":
                        h = float(b.get("imageHeight", 22))
                        w = min(b_w, float(b.get("imageWidth", 96)))
                        img_x = b_x + max(0.0, (b_w - w) / 2.0)
                        compiled_right_blocks.append({
                            "id": str(b.get("id")),
                            "type": "image",
                            "x": img_x,
                            "y": curr_y,
                            "w": w,
                            "h": h,
                            "z": 3,
                            "assetSlot": b.get("assetSlot"),
                            "assetId": b.get("assetId"),
                        })
                        curr_y += h + gap
                    elif b_type == "text":
                        text = str(b.get("text", ""))
                        lines = text.split("\n")
                        fs = float(b.get("fontSize", 9.0))
                        h = max(14.0, float(len(lines)) * fs * 1.35)
                        compiled_right_blocks.append({
                            "id": str(b.get("id")),
                            "type": "text",
                            "x": b_x,
                            "y": curr_y,
                            "w": b_w,
                            "h": h,
                            "z": 3,
                            "text": text,
                            "style": {
                                "fontSize": fs,
                                "fontWeight": str(b.get("fontWeight", "500")),
                                "color": str(b.get("color", "#0F172A")),
                                "textAlign": str(b.get("textAlign", "left")),
                            },
                        })
                        curr_y += h + gap
                    elif b_type == "variable":
                        fs = float(b.get("fontSize", 9.5))
                        h = max(14.0, fs * 1.4)
                        compiled_right_blocks.append({
                            "id": str(b.get("id")),
                            "type": "variable",
                            "variableId": b.get("variableId"),
                            "prefix": b.get("prefix"),
                            "suffix": b.get("suffix"),
                            "x": b_x,
                            "y": curr_y,
                            "w": b_w,
                            "h": h,
                            "z": 3,
                            "style": {
                                "fontSize": fs,
                                "fontWeight": str(b.get("fontWeight", "700")),
                                "color": str(b.get("color", "#0F172A")),
                                "textAlign": str(b.get("textAlign", "left")),
                            },
                        })
                        curr_y += h + gap
                    elif b_type == "divider":
                        h = float(b.get("dividerHeight", 1))
                        compiled_right_blocks.append({
                            "id": str(b.get("id")),
                            "type": "line",
                            "x": b_x,
                            "y": curr_y,
                            "w": b_w,
                            "h": 2,
                            "z": 3,
                            "style": {
                                "borderWidth": h,
                                "borderColor": str(b.get("dividerColor", "#E2E8F0")),
                            },
                        })
                        curr_y += h + gap

    baseline_y_map = {
        "specials_title": 380.0 if has_dense_layout else 404.0,
        "current_benefits_grid": 404.0 if has_dense_layout else 428.0,
        "extras_title": 609.0 if has_dense_layout else 633.0,
        "purchased_extras_grid": 633.0 if has_dense_layout else 657.0,
        "addons_title": 838.0 if has_dense_layout else 862.0,
        "available_addons_grid": 862.0 if has_dense_layout else 886.0,
        "terms": 1090.0,
    }

    has_legacy_specials = any(e.get("id") == "specials_title" for e in remaining)
    terms_notice = sections.get("footer", {}).get("termsNotice")
    for elem in remaining:
        eid = str(elem.get("id", ""))
        if eid in ("cov_table_bg", "group_specs_box"):
            elem["baseline_h"] = float(elem.get("baseline_h") or elem.get("h", 258.0 if is_v2_layout else 246.0))
            elem["h"] = elem["baseline_h"] + delta_y

        if has_legacy_specials and eid in baseline_y_map:
            elem["y"] = baseline_y_map[eid] + delta_y
        elif float(elem.get("y", 0) or 0) >= (380.0 if has_dense_layout else 400.0):
            elem["baseline_y"] = float(elem.get("baseline_y") or elem.get("y", 0))
            elem["y"] = elem["baseline_y"] + delta_y

        # Update section titles as requested
        if eid == "specials_title":
            elem["text"] = "QBE Free Added Coverage"
        elif eid == "extras_title":
            elem["text"] = "Included Optional Add-On"
        elif eid == "addons_title":
            elem["text"] = "Recommended Add-On Upgrades :"

        # Top Header Realignment
        if not is_v2_layout:
            if eid == "title":
                elem["x"] = 480.0
                elem["y"] = 16.0
                elem["w"] = 296.0
                elem["h"] = 24.0
                elem_style = elem.get("style") or {}
                elem_style.update({"textAlign": "right", "fontSize": 16, "fontWeight": "800", "color": "#ed1c24"})
                elem["style"] = elem_style
            elif eid == "validity":
                elem["x"] = 480.0
                elem["y"] = 40.0
                elem["w"] = 296.0
                elem["h"] = 20.0
                elem_style = elem.get("style") or {}
                elem_style.update({"textAlign": "right", "fontSize": 11, "fontWeight": "600", "color": "#475569"})
                elem["style"] = elem_style
            elif eid == "quote_vehicle":
                elem["x"] = 480.0
                elem["y"] = 96.0
                elem["w"] = 296.0
                elem["h"] = 28.0
                elem_style = elem.get("style") or {}
                elem_style.update({"textAlign": "right", "fontSize": 16, "fontWeight": "800"})
                elem["style"] = elem_style
        else:
            if eid == "title_motor":
                elem["x"] = 78.0
                elem["y"] = 26.0
                elem["w"] = 150.0
                elem["h"] = 32.0
                elem["text"] = "Motor Insurance "
                elem_style = elem.get("style") or {}
                elem_style.update({"fontSize": 18, "fontWeight": "800", "color": "#0F172A", "whiteSpace": "pre"})
                elem["style"] = elem_style
            elif eid == "title_quotation":
                elem["x"] = 232.0
                elem["y"] = 26.0
                elem["w"] = 100.0
                elem["h"] = 32.0
                elem["text"] = "Quotation"
                elem_style = elem.get("style") or {}
                elem_style.update({"fontSize": 18, "fontWeight": "800", "color": "#ED1C24"})
                elem["style"] = elem_style
            elif eid == "header_rule":
                elem["x"] = 40.0
                elem["y"] = 78.0
                elem["w"] = 714.0
                elem["h"] = 1.0

        if eid == "insurer_logo" and 180 < float(elem.get("x", 0) or 0) < 450:
            elem["visible"] = False

        header = sections.get("header") or default_header_config(is_v2_layout)
        rows_order = header.get("rowsOrder") or ["ref", "vehicle", "insurer"]
        header_font_size = float(header.get("fontSize") or 10.5)
        is_top_left_insurer = header.get("insurerPosition") == "top_left"

        right_row_slots = [r for r in rows_order if r != "insurer"] if is_top_left_insurer else rows_order
        base_slot_y = 18.0 if is_v2_layout else 20.0
        step_slot_y = 16.0 if is_v2_layout else 18.0
        row_slot_y_map = {slot: base_slot_y + idx * step_slot_y for idx, slot in enumerate(right_row_slots)}

        if eid == "risklocker_logo":
            elem["x"] = 40.0
            elem["y"] = 20.0 if is_v2_layout else float(header.get("logoY") or 8.0)
            elem["w"] = 32.0 if is_v2_layout else float(header.get("logoW") or 72.0)
            elem["h"] = 40.0 if is_v2_layout else float(header.get("logoH") or 74.0)
        elif eid == "ref_label":
            slot_y = row_slot_y_map.get("ref", 20.0)
            elem["visible"] = False
            elem["x"] = 354.0
            elem["y"] = slot_y
            elem["w"] = 400.0
            elem["h"] = 16.0
            if header.get("refLabel"):
                elem["text"] = header["refLabel"]
            elem_style = elem.get("style") or {}
            elem_style.update({"textAlign": "right", "fontSize": header_font_size, "fontWeight": "500", "color": "#64748B"})
            elem["style"] = elem_style
        elif eid == "ref_val":
            slot_y = row_slot_y_map.get("ref", 20.0)
            elem["x"] = 354.0
            elem["y"] = slot_y
            elem["w"] = 400.0
            elem["h"] = 16.0
            elem["prefix"] = header.get("refLabel") or "Quotation Ref: "
            elem_style = elem.get("style") or {}
            elem_style.update({"textAlign": "right", "fontSize": header_font_size, "fontWeight": "700", "color": "#ED1C24"})
            elem["style"] = elem_style
        elif eid == "vehicle_no_label":
            slot_y = row_slot_y_map.get("vehicle", 38.0)
            elem["visible"] = False
            elem["x"] = 354.0
            elem["y"] = slot_y
            elem["w"] = 400.0
            elem["h"] = 16.0
            if header.get("vehicleLabel"):
                elem["text"] = header["vehicleLabel"]
            elem_style = elem.get("style") or {}
            elem_style.update({"textAlign": "right", "fontSize": header_font_size, "fontWeight": "500", "color": "#64748B"})
            elem["style"] = elem_style
        elif eid == "vehicle_no_val":
            slot_y = row_slot_y_map.get("vehicle", 38.0)
            elem["x"] = 354.0
            elem["y"] = slot_y
            elem["w"] = 400.0
            elem["h"] = 16.0
            elem["prefix"] = header.get("vehicleLabel") or "Vehicle No: "
            elem_style = elem.get("style") or {}
            elem_style.update({"textAlign": "right", "fontSize": header_font_size, "fontWeight": "700", "color": "#ED1C24"})
            elem["style"] = elem_style
        elif eid == "header_insurer_label":
            if is_top_left_insurer:
                elem["visible"] = True
                elem["x"] = 40.0
                elem["y"] = float(header.get("logoY") or 12.0) + float(header.get("logoH") or 70.0) + 6.0
                elem["w"] = 60.0
                elem["h"] = 16.0
                if header.get("insurerLabel"):
                    elem["text"] = header["insurerLabel"]
                elem_style = elem.get("style") or {}
                elem_style.update({"textAlign": "left", "fontSize": header_font_size, "fontWeight": "600", "color": "#64748B"})
                elem["style"] = elem_style
            else:
                slot_y = row_slot_y_map.get("insurer", 56.0)
                elem["visible"] = False
                elem["x"] = 354.0
                elem["y"] = slot_y
                elem["w"] = 400.0
                elem["h"] = 16.0
                if header.get("insurerLabel"):
                    elem["text"] = header["insurerLabel"]
                elem_style = elem.get("style") or {}
                elem_style.update({"textAlign": "right", "fontSize": header_font_size, "fontWeight": "500", "color": "#64748B"})
                elem["style"] = elem_style
        elif eid == "header_insurer_name":
            if is_top_left_insurer:
                elem["x"] = 105.0
                elem["y"] = float(header.get("logoY") or 12.0) + float(header.get("logoH") or 70.0) + 6.0
                elem["w"] = 280.0
                elem["h"] = 16.0
                elem["prefix"] = ""
                elem_style = elem.get("style") or {}
                elem_style.update({"textAlign": "left", "fontSize": header_font_size, "fontWeight": "800", "color": "#ED1C24", "textTransform": "uppercase"})
                elem["style"] = elem_style
            else:
                slot_y = row_slot_y_map.get("insurer", 56.0)
                elem["x"] = 354.0
                elem["y"] = slot_y
                elem["w"] = 400.0
                elem["h"] = 16.0
                elem["prefix"] = header.get("insurerLabel") or "Insurer: "
                elem_style = elem.get("style") or {}
                elem_style.update({"textAlign": "right", "fontSize": header_font_size, "fontWeight": "800", "color": "#ED1C24", "textTransform": "uppercase"})
                elem["style"] = elem_style

        if eid == "terms" and terms_notice:
            elem["text"] = terms_notice

    has_top_insurer = any(
        e.get("id") in ("top_insurer_name", "header_insurer_name") or (
            e.get("variableId") == "insurance_company" and float(e.get("y", 0) or 0) < 130 and e.get("visible", True) is not False
        )
        for e in remaining
    )
    top_insurer_elem: list[dict[str, Any]] = []
    if not has_top_insurer:
        header = sections.get("header") or default_header_config()
        rows_order = header.get("rowsOrder") or ["ref", "vehicle", "insurer"]
        header_font_size = float(header.get("fontSize") or 10.5)
        is_top_left_insurer = header.get("insurerPosition") == "top_left"
        right_row_slots = [r for r in rows_order if r != "insurer"] if is_top_left_insurer else rows_order
        row_slot_y_map = {slot: 20.0 + idx * 18.0 for idx, slot in enumerate(right_row_slots)}

        slot_y = (float(header.get("logoY") or 18.0) + float(header.get("logoH") or 58.0) + 6.0) if is_top_left_insurer else row_slot_y_map.get("insurer", 56.0)
        pos_x = 105.0 if is_top_left_insurer else 555.0
        pos_w = 280.0 if is_top_left_insurer else 200.0

        top_insurer_elem.append({
            "id": "top_insurer_name",
            "type": "variable",
            "variableId": "insurance_company",
            "text": "AmGeneral Insurance Berhad",
            "x": pos_x,
            "y": slot_y,
            "w": pos_w,
            "h": 16.0,
            "z": 3,
            "style": {
                "fontSize": header_font_size,
                "fontWeight": "800",
                "color": "#ED1C24",
                "textAlign": "left",
                "textTransform": "uppercase",
            },
        })

    return remaining + top_insurer_elem + compiled_rows + compiled_right_blocks
