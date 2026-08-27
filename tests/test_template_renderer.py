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
    assert "+RM 67.80" in html
    assert "border:1.5px solid #F59E0B" in html
