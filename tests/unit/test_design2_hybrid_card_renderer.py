"""Unit tests for Design 2 Hybrid Card Renderer (2D Transparent Image + SVG fallback)."""

import pytest
from app.rendering.template_renderer_design2 import render_design2_html
from app.rendering.unified_addon_engine import build_unified_matrix_cards


def test_build_unified_matrix_cards_propagates_asset_id():
    active = [
        {
            "id": "windscreen",
            "title": "Windscreen Coverage",
            "value": "RM 1,000.00",
            "is_selected": True,
            "cost_status": "paid",
            "asset_id": "test-windscreen-asset-uuid",
        }
    ]
    cards = build_unified_matrix_cards(active_benefits=active, available_addons=[], fill_to_slots=4)
    windscreen_card = next((c for c in cards if c["id"] == "windscreen"), None)
    assert windscreen_card is not None
    assert windscreen_card["asset_id"] == "test-windscreen-asset-uuid"
    assert windscreen_card["is_selected"] is True


def test_render_design2_html_renders_crisp_vector_svg_icons():
    draft_fields = {
        "customer_name": "Test Customer",
        "vehicle_no": "WYY 1234",
    }
    render_context = {
        "current_benefits": [
            {
                "id": "windscreen",
                "title": "Windscreen Coverage",
                "value": "RM 1,000.00",
                "is_selected": True,
                "cost_status": "paid",
                "asset_id": "asset-uuid-1",
            },
            {
                "id": "towing",
                "title": "Unlimited Towing Distance",
                "is_selected": True,
                "cost_status": "included",
                "asset_id": None,
            },
        ]
    }
    resolved_assets = {
        "asset-uuid-1": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
    }

    html = render_design2_html(
        draft_fields=draft_fields,
        render_context={**render_context, "fill_to_slots": 24},
        resolved_assets=resolved_assets,
    )

    # Benefit cards in Design 2 strictly render crisp 2D vector line-art SVG icons matching quotation_A9243A
    assert '<svg width="38" height="38"' in html
    assert html.count('<svg width="38" height="38"') == 24
