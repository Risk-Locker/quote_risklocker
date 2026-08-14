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
