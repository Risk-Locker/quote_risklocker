"""Hermetic tests for Template Section Compiler and validation parity."""

from __future__ import annotations

import os
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
os.environ.setdefault("APP_ENV", "test")

from app.services.template_section_compiler import (
    extract_sections_from_canvas,
    compile_sections_to_canvas,
    DEFAULT_VEHICLE_FIELDS,
)
from app.services.template_revision_service import validate_template_config


def sample_canvas():
    elements = [
        {"id": "bg", "type": "rectangle", "x": 0, "y": 0, "w": 794, "h": 1123, "z": 0},
        {"id": "label_car_model", "type": "text", "x": 16, "y": 164, "w": 190, "h": 24, "z": 2, "text": "Car Model / 车辆型号"},
        {"id": "colon_car_model", "type": "text", "x": 207, "y": 164, "w": 12, "h": 24, "z": 2, "text": ":"},
        {"id": "value_car_model", "type": "variable", "variableId": "car_model", "x": 231, "y": 164, "w": 215, "h": 24, "z": 2},
        {"id": "label_engine_cc", "type": "text", "x": 16, "y": 192, "w": 190, "h": 24, "z": 2, "text": "Engine CC / 发动机排量"},
        {"id": "colon_engine_cc", "type": "text", "x": 207, "y": 192, "w": 12, "h": 24, "z": 2, "text": ":"},
        {"id": "value_engine_cc", "type": "variable", "variableId": "engine_cc", "x": 231, "y": 192, "w": 215, "h": 24, "z": 2},
        {
            "id": "current_benefits", "type": "benefit-grid", "gridKind": "current_benefits",
            "x": 20, "y": 450, "w": 754, "h": 300, "packing": {"strategy": "balanced", "alignment": "center"},
            "cardStyle": "standard", "textDensity": "normal",
        },
        {"id": "terms", "type": "text", "x": 20, "y": 1050, "w": 300, "h": 24, "z": 2, "text": "*Terms Applied"},
    ]
    return elements


def test_extract_sections_from_canvas():
    elements = sample_canvas()
    sections = extract_sections_from_canvas(elements)
    assert sections["version"] == 1
    fields = sections["section1"]["vehicleFields"]
    assert len(fields) >= 2
    assert fields[0]["id"] == "car_model"
    assert fields[0]["labelEn"] == "Car Model"
    assert fields[0]["labelZh"] == "车辆型号"
    assert fields[1]["id"] == "engine_cc"


def test_compile_sections_produces_valid_template_revision_config():
    elements = sample_canvas()
    sections = extract_sections_from_canvas(elements)

    # Add Seating Capacity field
    new_field = {
        "id": "seating_capacity",
        "variableId": "seating_capacity",
        "labelEn": "Seating Capacity",
        "labelZh": "座位数",
        "visible": True,
        "rowOrder": 0,
    }
    sections["section1"]["vehicleFields"].insert(0, new_field)
    for idx, f in enumerate(sections["section1"]["vehicleFields"]):
        f["rowOrder"] = idx

    compiled_elements = compile_sections_to_canvas(sections, elements)

    # Check compiled elements contain the new field
    assert any(e["id"] == "label_seating_capacity" for e in compiled_elements)
    assert any(e["id"] == "colon_seating_capacity" for e in compiled_elements)
    assert any(e["id"] == "value_seating_capacity" for e in compiled_elements)

    # Validate against strict template publication gate
    full_config = {
        "version": 7,
        "page_profile": {"profile_key": "a4", "width": 794, "height": 1123, "unit": "px"},
        "canvas": {"width": 794, "height": 1123, "elements": compiled_elements},
    }
    validated = validate_template_config(full_config)
    assert validated["canvas"]["width"] == 794
    assert len(validated["canvas"]["elements"]) > len(elements)


def test_hide_field_omits_from_compiled_canvas():
    elements = sample_canvas()
    sections = extract_sections_from_canvas(elements)

    # Mark engine_cc as hidden
    for f in sections["section1"]["vehicleFields"]:
        if f["id"] == "engine_cc":
            f["visible"] = False

    compiled = compile_sections_to_canvas(sections, elements)
    assert not any(e["id"] == "value_engine_cc" for e in compiled)
    assert not any(e["id"] == "label_engine_cc" for e in compiled)
    assert any(e["id"] == "value_car_model" for e in compiled)


def test_right_container_div_block_engine_compiles_cleanly():
    elements = sample_canvas()
    sections = extract_sections_from_canvas(elements)

    # Configure custom Right Container with Image, Text, Variable, and Divider blocks
    sections["rightContainers"] = [
        {
            "id": "custom_right_box",
            "title": "Payment & Extras Box",
            "layout": "column",
            "boxX": 508,
            "boxY": 134,
            "boxW": 246,
            "boxH": 272,
            "background": "#F8FAFC",
            "borderWidth": 2,
            "borderColor": "#CBD5E1",
            "borderRadius": 8,
            "padding": 12,
            "gap": 8,
            "blocks": [
                {
                    "id": "block_img_qr",
                    "type": "image",
                    "assetSlot": "custom_qr",
                    "imageWidth": 80,
                    "imageHeight": 80,
                    "order": 0,
                },
                {
                    "id": "block_txt_instruction",
                    "type": "text",
                    "text": "Scan QR to Pay via DuitNow\nRiskLocker Sdn. Bhd.",
                    "fontSize": 9.0,
                    "fontWeight": "600",
                    "color": "#1E293B",
                    "order": 1,
                },
                {
                    "id": "block_divider_line",
                    "type": "divider",
                    "dividerColor": "#94A3B8",
                    "dividerHeight": 1,
                    "order": 2,
                },
                {
                    "id": "block_var_excess",
                    "type": "variable",
                    "variableId": "excess_amount",
                    "prefix": "Agreed Excess: RM ",
                    "fontSize": 10.0,
                    "fontWeight": "800",
                    "color": "#0F172A",
                    "order": 3,
                },
            ],
        }
    ]

    compiled = compile_sections_to_canvas(sections, elements)

    # Assert container box is present
    container_box = next((e for e in compiled if e["id"] == "custom_right_box"), None)
    assert container_box is not None
    assert container_box["type"] == "rectangle"
    assert container_box["style"]["background"] == "#F8FAFC"
    assert container_box["style"]["borderWidth"] == 2

    # Assert child blocks are compiled
    img_block = next((e for e in compiled if e["id"] == "block_img_qr"), None)
    assert img_block is not None
    assert img_block["type"] == "image"
    assert img_block["assetSlot"] == "custom_qr"
    assert img_block["w"] == 80
    assert img_block["h"] == 80

    txt_block = next((e for e in compiled if e["id"] == "block_txt_instruction"), None)
    assert txt_block is not None
    assert txt_block["type"] == "text"
    assert "Scan QR" in txt_block["text"]

    var_block = next((e for e in compiled if e["id"] == "block_var_excess"), None)
    assert var_block is not None
    assert var_block["type"] == "variable"
    assert var_block["variableId"] == "excess_amount"
    assert var_block["prefix"] == "Agreed Excess: RM "

    div_block = next((e for e in compiled if e["id"] == "block_divider_line"), None)
    assert div_block is not None
    assert div_block["type"] == "line"

    # Strict template config validation
    full_config = {
        "version": 7,
        "page_profile": {"profile_key": "a4", "width": 794, "height": 1123, "unit": "px"},
        "canvas": {"width": 794, "height": 1123, "elements": compiled},
    }
    validated = validate_template_config(full_config)
    assert len(validated["canvas"]["elements"]) > 0


def test_custom_row_styling_and_insertion():
    elements = sample_canvas()
    sections = extract_sections_from_canvas(elements)

    # Insert a custom row at index 1 with custom styling
    ncd_row = {
        "id": "ncd_custom",
        "variableId": "ncd_percent",
        "labelEn": "No Claim Discount",
        "labelZh": "无索偿折扣",
        "fontSize": 13,
        "fontWeight": "800",
        "color": "#DC2626",
        "suffix": "%",
        "visible": True,
        "rowOrder": 1,
    }
    sections["section1"]["vehicleFields"].insert(1, ncd_row)
    for idx, f in enumerate(sections["section1"]["vehicleFields"]):
        f["rowOrder"] = idx

    compiled = compile_sections_to_canvas(sections, elements)
    ncd_label = next(e for e in compiled if e["id"] == "label_ncd_custom")
    assert ncd_label["style"]["fontSize"] == 13
    assert ncd_label["style"]["fontWeight"] == "800"
    assert ncd_label["style"]["color"] == "#DC2626"


def test_dynamic_row_expansion_pushes_down_and_expands_boxes():
    elements = sample_canvas()
    elements.append({"id": "cov_table_bg", "type": "rectangle", "x": 40, "y": 160, "w": 454, "h": 246, "z": 2})
    elements.append({"id": "specials_title", "type": "text", "x": 20, "y": 404, "w": 300, "h": 20, "z": 2, "text": "Benefits"})
    
    sections = extract_sections_from_canvas(elements)
    # Add 11 fields (2 over the baseline 9)
    extra_fields = [
        {"id": f"field_{i}", "variableId": "vehicle_no", "labelEn": f"Field {i}", "visible": True, "rowOrder": i}
        for i in range(11)
    ]
    sections["section1"]["vehicleFields"] = extra_fields
    sections["rightContainers"] = [
        {"id": "rc_container_main", "title": "Info Box", "boxX": 508, "boxY": 134, "boxW": 246, "boxH": 272, "blocks": []}
    ]

    compiled = compile_sections_to_canvas(sections, elements)
    delta_y = (11 - 9) * 28  # 56.0

    cov_bg = next(e for e in compiled if e["id"] == "cov_table_bg")
    assert cov_bg["h"] == 246 + delta_y

    right_box = next(e for e in compiled if e["id"] == "rc_container_main")
    assert right_box["h"] == 272 + delta_y

    specials_title = next(e for e in compiled if e["id"] == "specials_title")
    assert specials_title["y"] == 404.0 + delta_y

    terms = next(e for e in compiled if e["id"] == "terms")
    assert terms["y"] == 1090.0 + delta_y


def test_simulated_extras_injection_and_expansion():
    elements = sample_canvas()
    elements.append({"id": "cov_table_bg", "type": "rectangle", "x": 40, "y": 160, "w": 454, "h": 246, "z": 2})
    elements.append({"id": "specials_title", "type": "text", "x": 20, "y": 404, "w": 300, "h": 20, "z": 2, "text": "Benefits"})

    sections = extract_sections_from_canvas(elements)
    # Default 9 fields
    base_fields = [
        {"id": f"field_{i}", "variableId": "premium" if i == 5 else "vehicle_no", "labelEn": f"Field {i}", "visible": True, "rowOrder": i}
        for i in range(9)
    ]
    sections["section1"]["vehicleFields"] = base_fields
    sections["rightContainers"] = [
        {"id": "rc_container_main", "title": "Info Box", "boxX": 508, "boxY": 134, "boxW": 246, "boxH": 272, "blocks": []}
    ]

    # Compile with 4 simulated extras
    compiled = compile_sections_to_canvas(sections, elements, simulated_extras_count=4)
    # 9 base fields + 1 header + 4 extras = 14 rows -> delta_y = (14 - 9) * 28 = 140.0
    expected_delta_y = 140.0

    assert any(e["id"] == "label_sim_extras_header" for e in compiled)
    assert any(e["id"] == "label_sim_extra_0" for e in compiled)
    assert any(e["id"] == "label_sim_extra_3" for e in compiled)
    assert not any(e["id"] == "label_sim_extra_4" for e in compiled)

    cov_bg = next(e for e in compiled if e["id"] == "cov_table_bg")
    assert cov_bg["h"] == 246.0 + expected_delta_y

    right_box = next(e for e in compiled if e["id"] == "rc_container_main")
    assert right_box["h"] == 272.0 + expected_delta_y

    specials_title = next(e for e in compiled if e["id"] == "specials_title")
    assert specials_title["y"] == 404.0 + expected_delta_y


def test_lump_sum_extras_mode_compilation():
    elements = sample_canvas()
    sections = extract_sections_from_canvas(elements)
    sections["section1"]["extrasDisplayMode"] = "lump_sum"
    
    compiled = compile_sections_to_canvas(sections, elements, simulated_extras_count=1)
    
    assert any(e["id"] == "label_extras_lump" and e["text"] == "Extras / 附加项目" for e in compiled)
    assert any(e["id"] == "value_extras_lump" and e["variableId"] == "total_optional_cover_amount" for e in compiled)
    assert not any(e["id"] == "label_sim_extras_header" for e in compiled)


def test_renamed_section_titles_and_header_realignment():
    elements = sample_canvas()
    elements.extend([
        {"id": "specials_title", "type": "text", "x": 20, "y": 404, "w": 300, "h": 20, "z": 2, "text": "Featured Standard Benefits :"},
        {"id": "extras_title", "type": "text", "x": 20, "y": 633, "w": 300, "h": 20, "z": 2, "text": "Purchased Addons and Extras"},
        {"id": "addons_title", "type": "text", "x": 20, "y": 862, "w": 300, "h": 20, "z": 2, "text": "You May Add On"},
        {"id": "title", "type": "text", "x": 480, "y": 16, "w": 296, "h": 24, "z": 2, "text": "Motor Insurance Quotation"},
        {"id": "validity", "type": "text", "x": 480, "y": 40, "w": 296, "h": 20, "z": 2, "text": "Validity Until"},
        {"id": "quote_vehicle", "type": "text", "x": 480, "y": 96, "w": 296, "h": 28, "z": 2, "text": "Vehicle"},
        {"id": "insurer_logo", "type": "image", "x": 300, "y": 20, "w": 100, "h": 40, "z": 2},
    ])
    sections = extract_sections_from_canvas(elements)
    compiled = compile_sections_to_canvas(sections, elements)

    assert any(e["id"] == "specials_title" and e["text"] == "QBE Free Added Coverage" for e in compiled)
    assert any(e["id"] == "extras_title" and e["text"] == "Included Optional Add-On" for e in compiled)
    assert any(e["id"] == "addons_title" and e["text"] == "Recommended Add-On Upgrades :" for e in compiled)

    top_insurer = next(e for e in compiled if e["id"] == "top_insurer_name")
    assert top_insurer["y"] == 56.0
    assert top_insurer["variableId"] == "insurance_company"
    assert "AmGeneral" in top_insurer["text"] or "QBE" in top_insurer["text"]

    center_logo = next((e for e in compiled if e["id"] == "insurer_logo"), None)
    assert center_logo is not None and center_logo.get("visible") is False


def test_right_container_qr_and_no_compulsory_excess():
    elements = sample_canvas()
    sections = extract_sections_from_canvas(elements)
    
    # Check default right containers (3 modular cards: Payment, QR, Drivers)
    from app.services.template_section_compiler import default_right_containers
    rcs = default_right_containers()
    assert len(rcs) == 3
    container_ids = [c["id"] for c in rcs]
    assert container_ids == ["rc_container_payment", "rc_container_qr", "rc_container_drivers"]

    all_blocks = [b for c in rcs for b in c["blocks"]]
    block_ids = [b["id"] for b in all_blocks]
    
    assert "rc_b_compulsory_excess" not in block_ids
    assert "rc_b_qr_code" in block_ids
    
    # Verify QR card sits above All Drivers Card
    qr_container_idx = next(i for i, c in enumerate(rcs) if c["id"] == "rc_container_qr")
    driver_container_idx = next(i for i, c in enumerate(rcs) if c["id"] == "rc_container_drivers")
    assert qr_container_idx < driver_container_idx
    assert rcs[qr_container_idx]["boxY"] < rcs[driver_container_idx]["boxY"]

    # Verify bank account is strictly 12300318500
    pay_details = next(b for b in rcs[0]["blocks"] if b["id"] == "rc_b_pay_details")
    assert "12300318500" in pay_details["text"]
    assert "12303105859" not in pay_details["text"]


def test_header_section_custom_order_and_top_left_insurer():
    elements = sample_canvas()
    elements.extend([
        {"id": "risklocker_logo", "type": "image", "x": 40, "y": 24, "w": 150, "h": 48},
        {"id": "ref_label", "type": "text", "x": 420, "y": 20, "w": 115, "h": 16, "text": "Quotation ref :"},
        {"id": "ref_val", "type": "variable", "variableId": "quotation_reference", "x": 540, "y": 20, "w": 214, "h": 16},
        {"id": "vehicle_no_label", "type": "text", "x": 420, "y": 38, "w": 115, "h": 16, "text": "Vehicle no. :"},
        {"id": "vehicle_no_val", "type": "variable", "variableId": "vehicle_no", "x": 540, "y": 38, "w": 214, "h": 16},
        {"id": "header_insurer_label", "type": "text", "x": 420, "y": 56, "w": 115, "h": 16, "text": "Insurer :"},
        {"id": "header_insurer_name", "type": "variable", "variableId": "insurance_company", "x": 540, "y": 56, "w": 214, "h": 16},
    ])
    sections = extract_sections_from_canvas(elements)
    assert "header" in sections
    assert sections["header"]["rowsOrder"] == ["ref", "vehicle", "insurer"]

    # 1. Verify default 3-row order compilation
    compiled_default = compile_sections_to_canvas(sections, elements)
    c_ref = next(e for e in compiled_default if e["id"] == "ref_label")
    c_veh = next(e for e in compiled_default if e["id"] == "vehicle_no_label")
    c_ins = next(e for e in compiled_default if e["id"] == "header_insurer_label")
    assert c_ref["y"] == 20.0
    assert c_veh["y"] == 38.0
    assert c_ins["y"] == 56.0

    # 2. Reorder: Insurer first, then vehicle, then ref
    sections["header"]["rowsOrder"] = ["insurer", "vehicle", "ref"]
    sections["header"]["insurerLabel"] = "Underwritten by :"
    sections["header"]["fontSize"] = 11.5
    compiled_reordered = compile_sections_to_canvas(sections, elements)
    r_ins = next(e for e in compiled_reordered if e["id"] == "header_insurer_label")
    r_veh = next(e for e in compiled_reordered if e["id"] == "vehicle_no_label")
    r_ref = next(e for e in compiled_reordered if e["id"] == "ref_label")
    assert r_ins["y"] == 20.0
    assert r_ins["text"] == "Underwritten by :"
    assert r_ins["style"]["fontSize"] == 11.5
    assert r_veh["y"] == 38.0
    assert r_ref["y"] == 56.0

    # 3. Position Insurer at top_left
    sections["header"]["insurerPosition"] = "top_left"
    compiled_top_left = compile_sections_to_canvas(sections, elements)
    tl_ins_lbl = next(e for e in compiled_top_left if e["id"] == "header_insurer_label")
    tl_ins_val = next(e for e in compiled_top_left if e["id"] == "header_insurer_name")
    assert tl_ins_lbl["x"] == 40.0
    assert tl_ins_lbl["y"] == 88.0  # logoY(12) + logoH(70) + 6
    assert tl_ins_val["x"] == 105.0
    assert tl_ins_val["y"] == 88.0


def test_agency_bilingual_v2_section_extraction_and_compilation():
    from app.services.master_template_service import _agency_bilingual_v2_config

    v2_config = _agency_bilingual_v2_config()
    v2_elements = v2_config["canvas"]["elements"]

    # 1. Extract sections
    sections = extract_sections_from_canvas(v2_elements)

    # 2. Verify right containers are v2 defaults (2 containers: DuitNow image + Drivers)
    right_containers = sections.get("rightContainers") or []
    assert len(right_containers) == 2
    assert right_containers[0]["id"] == "rc_container_payment"
    assert right_containers[0]["blocks"][0]["id"] == "payment_account_details_img"
    assert right_containers[0]["blocks"][0]["assetSlot"] == "duitnow_payment_details"

    assert right_containers[1]["id"] == "rc_container_drivers"
    assert any("全司机投保" in str(b.get("text", "")) for b in right_containers[1]["blocks"])

    # 3. Verify left table vehicleFields contains excess_amount directly after valuation_type
    fields = sections["section1"]["vehicleFields"]
    var_ids = [f["variableId"] for f in fields]
    assert "customer_name" in var_ids
    assert "valuation_type" in var_ids
    assert "excess_amount" in var_ids
    assert "coverage_amount" in var_ids

    val_type_idx = var_ids.index("valuation_type")
    excess_idx = var_ids.index("excess_amount")
    cov_amt_idx = var_ids.index("coverage_amount")
    assert excess_idx == val_type_idx + 1
    assert cov_amt_idx == excess_idx + 1

    excess_field = fields[excess_idx]
    assert excess_field["labelEn"] == "Policy Excess"
    assert excess_field["labelZh"] == "自负额"

    # 4. Compile sections to canvas and validate
    compiled = compile_sections_to_canvas(sections, v2_elements)
    assert len(compiled) > 0

    full_config = {
        "version": 7,
        "page_profile": {"profile_key": "a4", "width": 794, "height": 1123, "unit": "px"},
        "canvas": {"width": 794, "height": 1123, "elements": compiled},
    }
    validated = validate_template_config(full_config)
    assert len(validated["canvas"]["elements"]) > 0
