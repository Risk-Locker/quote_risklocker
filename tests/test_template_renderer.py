"""Regression tests for deterministic quotation HTML rendering."""

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
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:password@db.test.supabase.co:5432/postgres")
os.environ.setdefault("AUTH_HASH_SECRET", "test-auth-hash-secret-that-is-long-enough")
os.environ.setdefault("SUPABASE_URL", "https://project-ref.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")

from app.rendering.template_renderer import render_quotation_html  # noqa: E402


def _element(element: dict) -> dict:
    return {"canvas": {"width": 794, "height": 1123, "elements": [element]}}


def test_special_renders_label_value_and_icon_placeholder():
    html = render_quotation_html(
        {},
        template_config=_element(
            {
                "id": "s1",
                "type": "special",
                "x": 10,
                "y": 20,
                "w": 300,
                "h": 60,
                "z": 2,
                "variant_label": "Windscreen Coverage",
                "variant_value_text": "Up to RM 300",
                "variant_bg_color": "#F6F8FB",
                "variant_shape": "rounded",
                "variant_shadow": "sm",
            }
        ),
    )
    assert "Windscreen Coverage" in html
    assert "Up to RM 300" in html
    assert "WC" in html  # initials tile
    assert "border-radius:12px" in html
    assert "box-shadow:0 1px 3px rgba(0,0,0,0.12)" in html
    assert "position:absolute" in html
    assert "left:10.0px" in html


def test_special_without_value_omits_value_row():
    html = render_quotation_html(
        {},
        template_config=_element(
            {"id": "s2", "type": "special", "x": 0, "y": 0, "w": 100, "h": 40, "z": 1, "variant_label": "Towing"}
        ),
    )
    assert "Towing" in html
    assert "font-weight:900" in html  # initials tile present


def test_special_capsule_shape_and_border():
    html = render_quotation_html(
        {},
        template_config=_element(
            {
                "id": "s3",
                "type": "special",
                "x": 0,
                "y": 0,
                "w": 100,
                "h": 40,
                "z": 1,
                "variant_label": "Battery",
                "variant_shape": "capsule",
                "variant_border_width": "2",
                "variant_border_color": "#EE1F2A",
            }
        ),
    )
    assert "border-radius:999px" in html
    assert "border:2 solid #EE1F2A" in html


def test_variable_element_resolves_draft_value_with_prefix():
    html = render_quotation_html(
        {"customer_name": {"value": "AHMAD"}},
        template_config={
            "variables": [{"id": "customer_name", "label": "Customer Name", "source": "field", "field": "customer_name"}],
            "canvas": {
                "width": 794,
                "height": 1123,
                "elements": [
                    {"id": "v1", "type": "variable", "x": 0, "y": 0, "w": 200, "h": 30, "z": 1, "variableId": "customer_name", "prefix": "Name:"}
                ],
            },
        },
    )
    assert "Name: AHMAD" in html


def test_text_element_is_escaped():
    html = render_quotation_html(
        {},
        template_config=_element(
            {"id": "t1", "type": "text", "x": 0, "y": 0, "w": 100, "h": 20, "z": 1, "text": "<b>Terms & Conditions</b>"}
        ),
    )
    assert "&lt;b&gt;Terms &amp; Conditions&lt;/b&gt;" in html


def test_line_and_group_elements_render_containers():
    html = render_quotation_html(
        {},
        template_config={
            "canvas": {
                "width": 794,
                "height": 1123,
                "elements": [
                    {"id": "l1", "type": "line", "x": 0, "y": 0, "w": 100, "h": 2, "z": 1},
                    {"id": "g1", "type": "group", "x": 0, "y": 0, "w": 100, "h": 60, "z": 1, "style": {"background": "#ffffff", "borderWidth": 1}},
                ],
            }
        },
    )
    assert html.count("<div") >= 2
    assert "border:1px solid" in html


class _Variant:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _ScalarResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _FakeDb:
    def __init__(self, items):
        self._items = items

    def scalars(self, _stmt):
        return _ScalarResult(self._items)


def test_benefit_section_populates_specials_from_db():
    db = _FakeDb(
        [
            _Variant(
                label="Unlimited Towing", value_text="24/7", secondary_label=None,
                icon_asset_id="", bg_color="#F6F8FB", text_color="#111111",
                border_width="", border_color="#D8DDE6", shape="rounded", shadow="none",
            )
        ]
    )
    html = render_quotation_html(
        {},
        template_config=_element(
            {"id": "bs", "type": "benefit-section", "section": "specials", "columns": 2, "x": 0, "y": 0, "w": 100, "h": 100, "z": 1}
        ),
        db=db,
    )
    assert "Unlimited Towing" in html
    assert "24/7" in html
    assert "grid-template-columns:repeat(2,1fr)" in html


def test_benefit_section_empty_when_no_db():
    html = render_quotation_html(
        {},
        template_config=_element(
            {"id": "bs", "type": "benefit-section", "section": "add_ons", "columns": 2, "x": 0, "y": 0, "w": 100, "h": 100, "z": 1}
        ),
    )
    assert "grid-template-columns:repeat(2,1fr)" in html
    assert "Unlimited Towing" not in html


def test_insurer_logo_hint_does_not_crash_for_etiqa():
    html = render_quotation_html(
        {"insurance_company": {"value": "Etiqa"}},
        template_config=_element(
            {"id": "i1", "type": "image", "x": 0, "y": 0, "w": 100, "h": 40, "z": 1, "assetSlot": "insurer_logo"}
        ),
    )
    assert "position:absolute" in html


def test_quotation_reference_strips_trailing_hyphen():
    html = render_quotation_html(
        {"quotation_reference": {"value": "FL22026M-01587863-"}},
        template_config=_element(
            {"id": "v1", "type": "variable", "x": 0, "y": 0, "w": 200, "h": 20, "z": 1, "variableId": "quotation_reference"}
        ),
    )
    assert "FL22026M-01587863" in html
    assert "FL22026M-01587863-" not in html


def test_premium_info_block_renders_roadtax_chinese_and_clean_extras():
    render_context = {
        "extras": [
            {"selection_id": "s1", "label": "Windscreen", "coverage_limit": "(RM 2,650)", "price": {"amount": "150.00", "currency": "MYR"}},
            {"selection_id": "s2", "label": "Legal Liability to Passengers (LLTP)", "coverage_limit": "", "price": {"amount": "67.80", "currency": "MYR"}},
        ],
        "total_premium_adjusted": "2,845.50",
    }
    fields = {
        "premium": {"value": "2400.00"},
        "roadtax": {"value": "90.00"},
        "service_fee": {"value": "20.00"},
    }
    html = render_quotation_html(
        fields,
        template_config=_element(
            {"id": "pib", "type": "premium-info-block", "x": 0, "y": 0, "w": 400, "h": 200, "z": 1}
        ),
        render_context=render_context,
    )
    assert "Roadtax / 路税" in html
    assert "Windscreen" in html
    assert "(RM 2,650)" in html
    assert "Legal Liability to Passengers (LLTP)" in html
    assert "IncludedRM" not in html
    assert "RM 150.00" in html
    assert "RM 67.80" in html


def test_dynamic_benefit_grid_renders_purchased_extra_with_label_and_badge():
    render_context = {
        "current_benefits": [
            {
                "id": "c1",
                "label": "Legal Liability to Passengers",
                "value": "Passenger coverage",
                "is_extra": True,
                "price": {"amount": "67.80", "currency": "MYR"},
            }
        ],
        "available_addons": [],
    }
    html = render_quotation_html(
        {},
        template_config=_element(
            {"id": "dbg", "type": "benefit-grid", "gridKind": "current_benefits", "x": 0, "y": 0, "w": 500, "h": 200, "z": 1}
        ),
        render_context=render_context,
    )
    assert "Legal Liability to Passengers" in html
    assert "Cost : MYR 67.80" in html
    assert "border:1px solid #E2E8F0" in html
    assert "background:#FEE2E2" in html


def test_valuation_type_renders_in_agency_bilingual_template():
    from app.services.master_template_service import _agency_bilingual_config

    fields = {
        "customer_name": {"value": "John Doe"},
        "cover_period": {"value": "01/01/2026 - 31/12/2026"},
        "valuation_type": {"value": "Agreed Value"},
        "coverage_amount": {"value": "75,000.00"},
        "car_model": {"value": "Honda Civic"},
        "ncd_percent": {"value": "55"},
        "total_amount": {"value": "1,500.00"},
    }
    config = _agency_bilingual_config()
    html = render_quotation_html(fields, template_name="Bilingual Agency Motor", template_config=config, render_context={"current_benefits": [], "available_addons": []})
    assert "Valuation Type / 估价方式" in html
    assert "Agreed Value" in html
    assert "Vehicle Sum Insured / 车辆保额" in html
    assert "RM 75,000.00" in html


def test_premium_info_block_omits_coverage_limit_when_show_coverage_is_false():
    render_context = {
        "extras": [
            {
                "selection_id": "s1",
                "label": "Windscreen (RM 3,000)",
                "coverage_limit": "(RM 3,000)",
                "show_coverage": False,
                "display_overrides": {"enabled": True, "showCoverage": False},
                "price": {"amount": "400.00", "currency": "MYR"},
            },
        ],
        "total_premium_adjusted": "1,000.00",
    }
    fields = {"premium": {"value": "600.00"}}
    html = render_quotation_html(
        fields,
        template_config=_element(
            {"id": "pib", "type": "premium-info-block", "x": 0, "y": 0, "w": 400, "h": 200, "z": 1}
        ),
        render_context=render_context,
    )
    assert "Windscreen" in html
    assert "(RM 3,000)" not in html
    assert "RM 400.00" in html


def test_balance_benefit_grid_row_height_calibration_for_44px_icons():
    from app.rendering.template_renderer import _balance_benefit_grid_elements

    elements = [
        {"id": "specials_header_bg", "type": "rectangle", "y": 414, "h": 26},
        {"id": "specials_header_txt", "type": "text", "y": 419, "h": 16},
        {"id": "grid1", "type": "benefit-grid", "gridKind": "current_benefits", "y": 444, "columns": 3, "iconSize": 44},
        {"id": "addons_header_bg", "type": "rectangle", "y": 700, "h": 26},
        {"id": "addons_header_txt", "type": "text", "y": 705, "h": 16},
        {"id": "grid2", "type": "benefit-grid", "gridKind": "available_addons", "y": 730, "columns": 3, "iconSize": 44},
    ]
    render_context = {
        "current_benefits": [{"id": f"b{i}"} for i in range(9)] + [{"id": "ext1", "price": 100}],
        "available_addons": [{"id": f"a{i}"} for i in range(6)],
    }
    balanced = _balance_benefit_grid_elements(elements, render_context)
    by_id = {e["id"]: e for e in balanced}
    assert by_id["grid1"]["h"] >= 200.0
    assert by_id["extras_grid"]["h"] >= 90.0
    assert float(by_id["extras_header_bg"]["y"]) > float(by_id["grid1"]["y"]) + float(by_id["grid1"]["h"])
    assert float(by_id["addons_header_bg"]["y"]) > float(by_id["extras_grid"]["y"]) + float(by_id["extras_grid"]["h"])


def test_balance_benefit_grid_three_section_expansion_and_no_overlap():
    from app.rendering.template_renderer import _balance_benefit_grid_elements, render_quotation_html

    elements = [
        {"id": "specials_header_bg", "type": "rectangle", "y": 414, "h": 26},
        {"id": "specials_header_txt", "type": "text", "y": 419, "h": 16},
        {"id": "grid1", "type": "benefit-grid", "gridKind": "current_benefits", "x": 40, "y": 444, "w": 714, "columns": 3},
        {"id": "addons_header_bg", "type": "rectangle", "y": 766, "h": 26},
        {"id": "addons_header_txt", "type": "text", "y": 771, "h": 16},
        {"id": "grid2", "type": "benefit-grid", "gridKind": "available_addons", "x": 40, "y": 796, "w": 714, "columns": 3},
        {"id": "footer_terms", "type": "text", "y": 1068, "h": 16},
    ]
    render_context = {
        "current_benefits": [
            {"id": "od", "label": "Own Damage", "price": {"amount": 0.0, "currency": "MYR"}},
            {"id": "b1", "label": "Roadside Assistance"},
            {"id": "b2", "label": "Emergency Towing"},
            {"id": "b3", "label": "No-Claim Cashback"},
            {"id": "b4", "label": "Excess Waiver"},
            {"id": "b5", "label": "Betterment Waiver"},
            {"id": "b6", "label": "Legal Defense"},
            {"id": "e1", "label": "Windscreen", "price": 540},
            {"id": "e2", "label": "LLP", "price": 37.8},
            {"id": "e3", "label": "LLOP", "price": 7.5},
            {"id": "e4", "label": "Agreed Value", "price": 50},
            {"id": "e5", "label": "Motor PA Plus", "price": 85},
        ],
        "available_addons": [{"id": f"a{i}", "label": f"Addon {i}"} for i in range(8)],
        "extras": [{"label": "Windscreen"}, {"label": "LLP"}, {"label": "LLOP"}, {"label": "Agreed Value"}, {"label": "Motor PA"}],
    }
    balanced = _balance_benefit_grid_elements(elements, render_context)
    by_id = {e["id"]: e for e in balanced}

    # Verify header ordering and non-overlapping gaps
    g1_bottom = float(by_id["grid1"]["y"]) + float(by_id["grid1"]["h"])
    h_ext_y = float(by_id["extras_header_bg"]["y"])
    assert h_ext_y >= g1_bottom + 8.0

    g_ext_bottom = float(by_id["extras_grid"]["y"]) + float(by_id["extras_grid"]["h"])
    h2_y = float(by_id["addons_header_bg"]["y"])
    assert h2_y >= g_ext_bottom + 8.0

    g2_bottom = float(by_id["grid2"]["y"]) + float(by_id["grid2"]["h"])
    footer_y = float(by_id["footer_terms"]["y"])
    assert footer_y >= g2_bottom

    # Verify auto-expanded HTML
    html = render_quotation_html(
        {"quotation_reference": {"value": "RL260000156"}},
        template_config={"canvas": {"width": 794, "height": 1123, "elements": elements}},
        render_context=render_context,
    )
    import re
    height_match = re.search(r"@page\s*\{\s*size:\s*\d+px\s*(\d+)px", html)
    assert height_match and int(height_match.group(1)) > 1123


def test_build_extras_uses_global_benefit_title_and_preserves_manual_override():
    from app.rendering.render_context import build_extras
    from unittest.mock import MagicMock

    c1 = MagicMock(id="c1", label="Windscreen", concept_key="windscreen", display_overrides={})
    c2 = MagicMock(id="c2", label="Special Perils", concept_key="special-perils", display_overrides={})

    s1 = MagicMock(
        id="s1",
        state="current",
        concept_id="c1",
        catalog_offering_id="off1",
        label_override=None,
        price={"amount": 120.0, "currency": "MYR"},
        cost_status="paid",
        coverage_limit="800",
        evidence_snapshot={"extracted_label": "Repair of Windscreen, Window and Sunroof"},
        sort_order=1,
    )
    s2 = MagicMock(
        id="s2",
        state="current",
        concept_id="c2",
        catalog_offering_id="off2",
        label_override="Special Perils (Full Storm)",
        price={"amount": 40.0, "currency": "MYR"},
        cost_status="paid",
        coverage_limit="",
        evidence_snapshot={"manually_edited": True},
        sort_order=2,
    )

    off1 = MagicMock(id="off1", label_override=None, optional_price=None)
    off2 = MagicMock(id="off2", label_override=None, optional_price=None)

    extras = build_extras([s1, s2], concepts=[c1, c2], offerings=[off1, off2])
    assert len(extras) == 2
    assert extras[0]["label"] == "Windscreen"
    assert extras[0]["coverage_limit"] == "(RM 800)"
    assert extras[1]["label"] == "Special Perils (Full Storm)"

def test_benefit_grid_custom_typography_and_colors():
    elements = [
        {
            "id": "bg1",
            "type": "benefit-grid",
            "gridKind": "current_benefits",
            "x": 20,
            "y": 50,
            "w": 750,
            "h": 300,
            "columns": 2,
            "cardStyle": "standard",
            "titleSize": 13,
            "titleColor": "#1e3a8a",
            "coverageSize": 12,
            "coverageColor": "#059669",
            "descSize": 10,
            "descColor": "#475569",
            "costSize": 10,
            "costColor": "#991b1b",
            "costBgColor": "#fef2f2",
        }
    ]
    render_context = {
        "current_benefits": [
            {
                "label": "Roadside Towing",
                "coverage_limit": "300km",
                "description": "Unlimited breakdown towing assistance",
                "price": {"amount": 50.0},
                "is_addon": True,
                "_showAsset": False,
                "_showTitle": True,
                "_showCoverage": True,
                "_showDescription": True,
                "_showCost": True,
            }
        ],
        "available_addons": [],
    }
    html = render_quotation_html(
        {},
        template_config={"canvas": {"width": 794, "height": 1123, "elements": elements}},
        render_context=render_context,
    )
    assert "Roadside Towing" in html
    assert "300km" in html
    assert "color:#059669" in html
    assert "color:#475569" in html
    assert "color:#991b1b" in html
    assert "background:#fef2f2" in html


def test_benefit_card_description_allows_three_lines_without_truncation():
    from app.rendering.template_renderer import _balance_benefit_grid_elements
    elements = [
        {
            "id": "grid1",
            "type": "benefit-grid",
            "gridKind": "current_benefits",
            "x": 40,
            "y": 444,
            "w": 714,
            "h": 100,
            "columns": 3,
            "cardStyle": "standard",
            "descSize": 8.5,
            "showDescription": True,
        },
        {
            "id": "grid2",
            "type": "benefit-grid",
            "gridKind": "available_addons",
            "x": 40,
            "y": 600,
            "w": 714,
            "h": 100,
            "columns": 3,
            "cardStyle": "standard",
            "descSize": 8.5,
            "showDescription": True,
        },
    ]
    render_context = {
        "current_benefits": [
            {
                "label": "Emergency Towing Assistance",
                "description": "24/7 accident towing service to the nearest authorized workshop or panel repairer",
                "_showTitle": True,
                "_showDescription": True,
            }
        ],
        "available_addons": [
            {
                "label": "Windscreen & Window Glass",
                "coverage_limit": "RM 1,000",
                "description": "Repair or replacement of broken windscreen, windows, and tint film without NCD loss.",
                "price": {"amount": 150.0},
                "_showTitle": True,
                "_showCoverage": True,
                "_showDescription": True,
                "_showCost": True,
            }
        ],
        "extras": [],
    }
    
    # Check layout calculations
    balanced = _balance_benefit_grid_elements(elements, render_context)
    by_id = {e["id"]: e for e in balanced}
    # With 1 card in grid1 (3 columns) -> 1 row >= 90px
    assert float(by_id["grid1"]["h"]) >= 90.0
    # With 1 card in grid2 (3 columns) -> 1 row >= 126px
    assert float(by_id["grid2"]["h"]) >= 126.0

    html = render_quotation_html(
        {},
        template_config={"canvas": {"width": 794, "height": 1123, "elements": elements}},
        render_context=render_context,
    )
    # Ensure line-clamp-2 and rigid 24px max-height are completely gone
    assert "-webkit-line-clamp:2" not in html
    assert "max-height:24.0px" not in html
    assert "-webkit-line-clamp:4" in html

