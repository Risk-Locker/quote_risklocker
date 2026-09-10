"""Template Section Compiler (Backend Mirror).

Provides deterministic compilation between structured section configurations
and canonical canvas.elements for template revisions and automated tests.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


DEFAULT_VEHICLE_FIELDS = [
    {"id": "coverage_type", "variableId": "coverage_type", "labelEn": "Coverage Type", "labelZh": "保险类型", "visible": True, "rowOrder": 0},
    {"id": "cover_period", "variableId": "cover_period", "labelEn": "Cover of Period", "labelZh": "保险期限", "visible": True, "rowOrder": 1},
    {"id": "car_model", "variableId": "car_model", "labelEn": "Car Model", "labelZh": "车辆型号", "visible": True, "rowOrder": 2},
    {"id": "ncd_percent", "variableId": "ncd_percent", "labelEn": "NCD", "labelZh": "无索偿折扣", "suffix": "%", "visible": True, "rowOrder": 3},
    {"id": "coverage_amount", "variableId": "coverage_amount", "labelEn": "Coverage", "labelZh": "保额", "prefix": "RM ", "visible": True, "rowOrder": 4},
    {"id": "premium", "variableId": "premium", "labelEn": "Insurance Premium", "labelZh": "基本保费", "prefix": "RM ", "visible": True, "rowOrder": 5},
    {"id": "roadtax", "variableId": "roadtax", "labelEn": "Roadtax", "labelZh": "路税", "prefix": "RM ", "visible": True, "rowOrder": 6},
    {"id": "service_fee", "variableId": "service_fee", "labelEn": "Runner Fee", "labelZh": "服务费", "prefix": "RM ", "visible": True, "rowOrder": 7},
    {"id": "total_amount", "variableId": "total_amount", "labelEn": "Total Premium", "labelZh": "总保费", "prefix": "RM ", "visible": True, "rowOrder": 8},
]


def extract_sections_from_canvas(elements: list[dict[str, Any]], saved_sections: dict[str, Any] | None = None) -> dict[str, Any]:
    """Extract structured section slots from canvas elements or return saved_sections."""
    if saved_sections and saved_sections.get("version") == 1 and saved_sections.get("section1", {}).get("vehicleFields"):
        return deepcopy(saved_sections)

    value_elements = [
        e for e in elements
        if e.get("type") == "variable" and (str(e.get("id", "")).startswith("value_") or e.get("variableId"))
    ]
    sorted_values = sorted(value_elements, key=lambda x: float(x.get("y", 0)))

    detected_fields: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for i, val_elem in enumerate(sorted_values):
        raw_key = str(val_elem.get("id", "")).replace("value_", "") or str(val_elem.get("variableId") or f"field_{i}")
        if raw_key in seen_ids:
            continue
        if raw_key in {"quote_vehicle", "validity"} or float(val_elem.get("x", 0)) > 400:
            continue

        seen_ids.add(raw_key)
        label_elem = next((e for e in elements if e.get("id") == f"label_{raw_key}"), None)
        raw_label = str(label_elem.get("text", "") if label_elem else raw_key)

        label_en = raw_label
        label_zh = ""
        if "/" in raw_label:
            parts = raw_label.split("/", 1)
            label_en = parts[0].strip()
            label_zh = parts[1].strip()

        detected_fields.append({
            "id": raw_key,
            "variableId": val_elem.get("variableId", raw_key),
            "labelEn": label_en or raw_key,
            "labelZh": label_zh,
            "prefix": val_elem.get("prefix"),
            "suffix": val_elem.get("suffix"),
            "visible": val_elem.get("visible", True) is not False,
            "rowOrder": len(detected_fields),
        })

    final_fields = detected_fields if detected_fields else deepcopy(DEFAULT_VEHICLE_FIELDS)
    terms_elem = next((e for e in elements if e.get("id") == "terms"), None)

    return {
        "version": 1,
        "section1": {
            "vehicleFields": final_fields,
            "headerTitleEn": "Coverage & Vehicle Information",
            "headerTitleZh": "保障与车辆信息",
        },
        "footer": {
            "bankName": "Hong Leong Bank",
            "accountNo": "12300318500",
            "accountHolder": "Risklocker Sdn. Bhd.",
            "termsNotice": str(terms_elem.get("text", "*Terms and Condition Applied")) if terms_elem else "*Terms and Condition Applied",
        },
    }


def compile_sections_to_canvas(sections: dict[str, Any], base_elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compile structured sections into valid, canonical CanvasElement list."""
    fields = sorted(
        list(sections.get("section1", {}).get("vehicleFields") or []),
        key=lambda x: int(x.get("rowOrder", 0)),
    )
    visible_fields = [f for f in fields if f.get("visible", True) is not False]

    first_label = next((e for e in base_elements if str(e.get("id", "")).startswith("label_")), None)
    first_colon = next((e for e in base_elements if str(e.get("id", "")).startswith("colon_")), None)
    first_value = next((e for e in base_elements if str(e.get("id", "")).startswith("value_")), None)

    label_x = float(first_label.get("x", 16)) if first_label else 16.0
    colon_x = float(first_colon.get("x", 207)) if first_colon else 207.0
    value_x = float(first_value.get("x", 231)) if first_value else 231.0
    start_y = float(first_label.get("y", 164)) if first_label else 164.0
    row_h = float(sections.get("section1", {}).get("rowHeight", 28.0))

    label_w = float(first_label.get("w", 190)) if first_label else 190.0
    value_w = float(first_value.get("w", 215)) if first_value else 215.0
    elem_h = float(first_label.get("h", 24)) if first_label else 24.0

    remaining = [
        deepcopy(e) for e in base_elements
        if not str(e.get("id", "")).startswith(("label_", "colon_", "value_"))
    ]

    compiled_rows: list[dict[str, Any]] = []
    for idx, field in enumerate(visible_fields):
        curr_y = start_y + (idx * row_h)
        zh = field.get("labelZh")
        combined_label = f"{field.get('labelEn')} / {zh}" if zh else str(field.get("labelEn"))
        fid = str(field.get("id"))

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
            "style": {"fontSize": 12, "fontWeight": "700", "color": "#111111", "textAlign": "left"},
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
            "style": {"fontSize": 12, "fontWeight": "400", "color": "#111111", "textAlign": "left"},
        })
        # Value
        var_id = field.get("variableId")
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
            "style": {"fontSize": 12, "fontWeight": "700", "color": "#111111", "textAlign": "left"},
        })

    terms_notice = sections.get("footer", {}).get("termsNotice")
    for elem in remaining:
        if elem.get("id") == "terms" and terms_notice:
            elem["text"] = terms_notice

    return remaining + compiled_rows
