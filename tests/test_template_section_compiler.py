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
