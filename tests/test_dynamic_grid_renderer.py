"""Dynamic v7 benefit grids use canonical cards and fixed page geometry."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
os.environ.setdefault("APP_ENV", "test")

from app.rendering.template_renderer import render_quotation_html  # noqa: E402


def config(kind="current_benefits", *, width=794, height=1400):
    return {
        "version": 7,
        "page_profile": {"width": width, "height": height, "unit": "px"},
        "canvas": {
            "width": width,
            "height": height,
            "elements": [{
                "id": "benefits-grid",
                "type": "benefit-grid",
                "gridKind": kind,
                "x": 20,
                "y": 200,
                "w": width - 40,
                "h": 300,
                "z": 2,
                "packing": {"strategy": "staggered", "alignment": "center"},
            }],
        },
    }


def cards(count):
    return [{
        "card_key": f"card-{index}",
        "label": f"Benefit <{index}>",
        "value": f"Value {index}",
        "asset_id": None,
        "cost_status": "foc" if index % 2 else "included",
    } for index in range(count)]


def test_renderer_uses_context_cards_and_custom_fixed_page_size_without_db_queries():
    context = {"current_benefits": cards(7), "available_addons": []}
    html = render_quotation_html({}, template_config=config(), render_context=context, resolved_assets={})
    assert "Benefit &lt;0&gt;" in html
    assert "Benefit &lt;6&gt;" in html
    assert 'data-grid-kind="current_benefits"' in html
    assert "width: 794px; height: 1400px" in html
    assert "@page { size: 794px 1400px" in html
    assert "overflow: hidden" in html
    assert "overflow:visible" not in html


def test_all_dense_cards_have_one_uniform_scale_and_remain_present():
    html = render_quotation_html({}, template_config=config(), render_context={"current_benefits": cards(100), "available_addons": []}, resolved_assets={})
    assert html.count('data-benefit-card="1"') == 100
    scales = re.findall(r'data-card-scale="([0-9.]+)"', html)
    assert len(scales) == 100
    assert len(set(scales)) == 1


def test_empty_grid_hides_without_fake_or_legacy_global_cards():
    html = render_quotation_html({}, template_config=config(), render_context={"current_benefits": [], "available_addons": []}, resolved_assets={})
    assert 'data-grid-empty="hide"' in html
    assert 'data-benefit-card="1"' not in html


def test_grid_style_density_stagger_and_empty_message_are_rendered_from_allowlists():
    value = config()
    element = value["canvas"]["elements"][0]
    element.update({
        "cardStyle": "outlined",
        "textDensity": "compact",
        "emptyState": "message",
        "emptyMessage": "No confirmed benefits yet",
    })
    element["packing"]["staggerRatio"] = 0.25

    empty_html = render_quotation_html(
        {},
        template_config=value,
        render_context={"current_benefits": [], "available_addons": []},
        resolved_assets={},
    )
    assert 'data-grid-empty="message"' in empty_html
    assert "No confirmed benefits yet" in empty_html

    filled_html = render_quotation_html(
        {},
        template_config=value,
        render_context={"current_benefits": cards(4), "available_addons": []},
        resolved_assets={},
    )
    assert 'data-card-style="outlined"' in filled_html
    assert 'data-text-density="compact"' in filled_html


def test_available_addons_grid_uses_only_available_context_cards():
    context = {"current_benefits": [{**cards(1)[0], "label": "Current only"}], "available_addons": [{**cards(1)[0], "label": "Next offer"}]}
    html = render_quotation_html({}, template_config=config("available_addons"), render_context=context, resolved_assets={})
    assert "Next offer" in html
    assert "Current only" not in html


def test_resolved_asset_data_is_used_without_live_asset_lookup():
    context = {"current_benefits": [{**cards(1)[0], "asset_id": "asset-a"}], "available_addons": []}
    html = render_quotation_html(
        {}, template_config=config(), render_context=context,
        resolved_assets={"asset-a": "data:image/png;base64,AAAA"},
    )
    assert "data:image/png;base64,AAAA" in html


def test_frozen_render_never_falls_back_to_a_live_asset_lookup(monkeypatch):
    monkeypatch.setattr("app.rendering.template_renderer.asset_data_uri", lambda *_args: (_ for _ in ()).throw(AssertionError("live lookup")))
    value = config()
    value["canvas"]["elements"] = [{"id": "logo", "type": "image", "assetId": "missing", "x": 0, "y": 0, "w": 10, "h": 10}]
    html = render_quotation_html({}, template_config=value, render_context={}, resolved_assets={})
    assert "<img" not in html


def test_layout_balancer_caps_itemized_extras_at_four_rows():
    from app.rendering.benefit_grid_renderer import _balance_benefit_grid_elements

    elements = [
        {"id": "premium_info_block", "type": "premium-info-block", "y": 276.0, "extras_mode": "itemized"},
        {"id": "cov_table_bg", "y": 120.0},
        {"id": "specials_header_bg"}, {"id": "specials_header_txt"},
        {"id": "addons_header_bg"}, {"id": "addons_header_txt"},
        {"type": "benefit-grid", "gridKind": "current_benefits", "y": 400.0, "h": 200.0},
        {"type": "benefit-grid", "gridKind": "available_addons", "y": 620.0, "h": 200.0},
    ]
    # 10 extras
    extras = [{"id": f"e{i}", "label": f"Extra {i}"} for i in range(10)]
    balanced = _balance_benefit_grid_elements(elements, {"extras": extras, "extras_mode": "itemized"})
    cov = next(e for e in balanced if e.get("id") == "cov_table_bg")
    # With cap at 3 itemized + 1 overflow row: total_pib_rows = 10, card_bottom = 428.0, h = 308.0
    assert cov["h"] == 308.0


def test_dense_quotation_auto_fit_zero_scale_and_multiline_title():
    """Verify high-density quotation (7 rows: 3 FOC + 6 Extras + 11 Addons) fits in A4 without scale shrinkage."""
    from app.rendering.benefit_grid_renderer import _balance_benefit_grid_elements

    elements = [
        {"id": "cov_table_bg", "y": 120.0, "h": 296.0},
        {"id": "premium_info_block", "type": "premium-info-block", "y": 276.0, "h": 140.0},
        {"id": "specials_header_bg", "type": "rectangle", "x": 40, "y": 414, "w": 714, "h": 24},
        {"id": "specials_header_txt", "type": "text", "x": 52, "y": 419, "w": 690, "h": 16},
        {"id": "current_benefits_grid", "type": "benefit-grid", "gridKind": "current_benefits", "x": 40, "y": 441, "w": 714, "h": 80, "columns": 3, "showDescription": True},
        {"id": "addons_header_bg", "type": "rectangle", "x": 40, "y": 550, "w": 714, "h": 24},
        {"id": "addons_header_txt", "type": "text", "x": 52, "y": 555, "w": 690, "h": 16},
        {"id": "available_addons_grid", "type": "benefit-grid", "gridKind": "available_addons", "x": 40, "y": 580, "w": 714, "h": 268, "columns": 3, "showDescription": True},
        {"id": "footer_tc_text", "type": "text", "x": 40, "y": 1072, "w": 714, "h": 20, "text": "*Terms & Conditions Apply"},
    ]

    context = {
        "current_benefits": [
            {"label": "Emergency Towing", "description": "24/7 accident towing", "cost_status": "included"},
            {"label": "24/7 Roadside Assist", "description": "On-site minor repairs", "cost_status": "included"},
            {"label": "Accident Flood Relief", "description": "Allowance up to RM 1,500", "cost_status": "included"},
            {"label": "Waiver of Compulsory Excess for Unnamed Drivers", "price": {"amount": 0}, "description": "No compulsory excess", "cost_status": "paid"},
            {"label": "Windscreen Coverage", "price": {"amount": 150}, "description": "Window repair", "cost_status": "paid"},
            {"label": "Special Perils", "price": {"amount": 200}, "description": "Flood & storm", "cost_status": "paid"},
            {"label": "Legal Liability to Passengers", "price": {"amount": 56.70}, "description": "Passenger protection", "cost_status": "paid"},
            {"label": "Legal Liability of Passengers", "price": {"amount": 7.50}, "description": "Negligence protection", "cost_status": "paid"},
            {"label": "Key Care Cover", "price": {"amount": 30}, "description": "Key replacement", "cost_status": "paid"},
        ],
        "extras": [
            {"label": "Waiver of Compulsory Excess for Unnamed Drivers", "price": {"amount": 0}},
            {"label": "Windscreen Coverage", "price": {"amount": 150}},
            {"label": "Special Perils", "price": {"amount": 200}},
            {"label": "Legal Liability to Passengers", "price": {"amount": 56.70}},
            {"label": "Legal Liability of Passengers", "price": {"amount": 7.50}},
            {"label": "Key Care Cover", "price": {"amount": 30}},
        ],
        "available_addons": [
            {"label": f"Addon Benefit {i}", "coverage_limit": f"RM {i*1000}", "description": f"Description text {i}", "price": {"amount": 50 + i * 10}}
            for i in range(1, 12)
        ],
    }

    balanced = _balance_benefit_grid_elements(elements, context)
    by_id = {e.get("id"): e for e in balanced}
    g2 = by_id["available_addons_grid"]
    bottom2 = float(g2["y"]) + float(g2["h"])
    # 7 rows auto-fitted must strictly fit within safe_bottom (1058.0px) on A4 canvas
    assert bottom2 <= 1058.0, f"Expected Section 3 bottom <= 1058.0 with dynamic auto-fit, got {bottom2}"

    html = render_quotation_html(
        {},
        template_config={"canvas": {"width": 794, "height": 1123, "elements": elements}},
        render_context=context,
    )
    # Zero scaling applied (scale factor is 1.0)
    assert "transform: scale(" not in html
    # Long title is rendered without truncation
    assert "Waiver of Compulsory Excess for Unnamed Drivers" in html
    # Title wraps naturally without rigid clamping
    assert "white-space:normal" in html
    # All 11 addons are rendered
    for i in range(1, 12):
        assert f"Addon Benefit {i}" in html


