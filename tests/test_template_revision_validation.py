"""Published template revisions enforce the fixed page and grid contract."""

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

from app.services.template_revision_service import (  # noqa: E402
    convert_legacy_template_nodes,
    new_v7_template_config,
    template_config_hash,
    validate_template_config,
)


def config(elements=None, *, width=794, height=1123):
    return {
        "version": 7,
        "page_profile": {"profile_key": "a4", "width": width, "height": height, "unit": "px"},
        "canvas": {"width": width, "height": height, "elements": elements or []},
    }


def grid(grid_id, kind, **patch):
    return {
        "id": grid_id, "type": "benefit-grid", "gridKind": kind,
        "x": 20, "y": 300, "w": 754, "h": 300,
        "packing": {"strategy": "balanced", "alignment": "center"},
        "cardStyle": "standard", "textDensity": "normal", **patch,
    }


def test_valid_config_has_stable_hash_and_no_slot_capacity():
    value = config([grid("current", "current_benefits"), grid("addons", "available_addons", y=650)])
    normalized = validate_template_config(value)
    assert normalized["canvas"]["height"] == 1123
    assert template_config_hash(value) == template_config_hash({"canvas": value["canvas"], "page_profile": value["page_profile"], "version": 7})
    assert "maxCards" not in str(normalized)


@pytest.mark.parametrize("kind", ["current_benefits", "available_addons"])
def test_duplicate_grid_kind_is_rejected(kind):
    with pytest.raises(ValueError, match="at most one"):
        validate_template_config(config([grid("one", kind), grid("two", kind, y=650)]))


def test_grid_must_be_inside_fixed_page_and_geometry_must_match_profile():
    with pytest.raises(ValueError, match="inside"):
        validate_template_config(config([grid("bad", "current_benefits", x=780, w=100)]))
    invalid = config()
    invalid["canvas"]["height"] = 1200
    with pytest.raises(ValueError, match="match"):
        validate_template_config(invalid)


def test_editor_scenario_data_and_new_legacy_manual_benefit_elements_are_rejected():
    with pytest.raises(ValueError, match="scenario"):
        validate_template_config({**config(), "scenarioMode": "dense"})
    with pytest.raises(ValueError, match="legacy manual"):
        validate_template_config(config([{"id": "old", "type": "special", "x": 0, "y": 0, "w": 10, "h": 10}]))


def test_compatibility_mode_can_read_legacy_manual_benefits_but_not_publish_them():
    legacy = config([{"id": "old", "type": "special", "x": 0, "y": 0, "w": 10, "h": 10}])
    assert validate_template_config(legacy, compatibility=True)["canvas"]["elements"][0]["type"] == "special"


@pytest.mark.parametrize("field", ["cardStyle", "textDensity"])
def test_grid_style_enums_are_validated(field):
    with pytest.raises(ValueError, match=field):
        validate_template_config(config([grid("bad", "current_benefits", **{field: "anything"})]))


def test_every_new_element_must_stay_inside_the_fixed_page():
    with pytest.raises(ValueError, match="inside"):
        validate_template_config(config([{
            "id": "outside",
            "type": "text",
            "x": 760,
            "y": 10,
            "w": 80,
            "h": 20,
            "text": "Outside",
        }]))


@pytest.mark.parametrize(
    ("patch", "message"),
    [
        ({"packing": {"strategy": "balanced", "alignment": "center", "gapRatio": 1.2}}, "gapRatio"),
        ({"packing": {"strategy": "balanced", "alignment": "center", "paddingRatio": 0.6}}, "paddingRatio"),
        ({"packing": {"strategy": "staggered", "alignment": "center", "staggerRatio": -0.1}}, "staggerRatio"),
        ({"packing": {"strategy": "balanced", "alignment": "center", "aspectRatio": 0}}, "aspectRatio"),
        ({"emptyState": "anything"}, "emptyState"),
    ],
)
def test_grid_numeric_and_empty_state_contract_is_validated(patch, message):
    with pytest.raises(ValueError, match=message):
        validate_template_config(config([grid("bad", "current_benefits", **patch)]))


def test_empty_message_requires_customer_facing_copy():
    with pytest.raises(ValueError, match="emptyMessage"):
        validate_template_config(config([grid("bad", "current_benefits", emptyState="message")]))


def test_new_revisions_reject_unknown_element_types_and_non_pixel_coordinate_units():
    with pytest.raises(ValueError, match="element type"):
        validate_template_config(config([{"id": "mystery", "type": "plugin-widget", "x": 0, "y": 0, "w": 10, "h": 10}]))
    millimetres = config()
    millimetres["page_profile"]["unit"] = "mm"
    with pytest.raises(ValueError, match="pixel"):
        validate_template_config(millimetres)


def test_semantic_layer_groups_are_non_rendering_and_shapes_are_explicit():
    value = config([
        {"id": "folder", "type": "layer-group", "name": "Header", "order": 2, "visible": True, "locked": False},
        {"id": "box", "type": "rectangle", "groupId": "folder", "x": 10, "y": 10, "w": 200, "h": 80},
        {"id": "oval", "type": "ellipse", "x": 30, "y": 120, "w": 100, "h": 60},
        {"id": "tri", "type": "triangle", "x": 30, "y": 220, "w": 100, "h": 80},
        {"id": "gem", "type": "diamond", "x": 30, "y": 320, "w": 100, "h": 80},
    ])
    normalized = validate_template_config(value)
    assert normalized["canvas"]["elements"][0]["type"] == "layer-group"
    with pytest.raises(ValueError, match="element type"):
        validate_template_config(config([{"id": "wrong", "type": "group", "x": 0, "y": 0, "w": 10, "h": 10}]))


def test_legacy_group_conversion_preserves_hierarchy_and_visible_background():
    legacy = config([
        {"id": "legacy-group", "type": "group", "groupName": "Header", "x": 5, "y": 5, "w": 300, "h": 100, "z": 1, "style": {"background": "#fff", "borderWidth": 1}},
        {"id": "child", "type": "text", "groupId": "legacy-group", "x": 20, "y": 20, "w": 100, "h": 20},
        {"id": "orphan", "type": "group", "x": 50, "y": 200, "w": 100, "h": 50, "style": {"background": "#eee"}},
    ])
    converted = convert_legacy_template_nodes(legacy)
    by_id = {item["id"]: item for item in converted["canvas"]["elements"]}
    assert by_id["legacy-group"]["type"] == "layer-group"
    assert by_id["legacy-group--rectangle"]["type"] == "rectangle"
    assert by_id["legacy-group--rectangle"]["groupId"] == "legacy-group"
    assert by_id["child"]["groupId"] == "legacy-group"
    assert by_id["orphan"]["type"] == "rectangle"
    validate_template_config(converted)


def test_new_v7_config_contains_no_ambiguous_group_or_shape_nodes():
    config = new_v7_template_config()
    types = {item["type"] for item in config["canvas"]["elements"]}
    assert "group" not in types
    assert "shape" not in types
    assert config["canvas"]["elements"] == []
