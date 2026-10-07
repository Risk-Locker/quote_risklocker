"""Clean insurer-independent v7 master template contract."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.rendering.grid_layout import GridBounds, GridSpec, pack_fixed_grid  # noqa: E402
from app.services.master_template_service import master_template_specs  # noqa: E402
from app.services.template_revision_service import validate_template_config  # noqa: E402


def test_clean_insurer_independent_masters_are_defined():
    specs = master_template_specs()
    assert [item["key"] for item in specs] == [
        "agency_bilingual",
        "agency_bilingual_v2",
        "agency_bilingual_v3",
        "agency_bilingual_v3_no_extras",
        "agency_bilingual_v3_lump_sum",
        "agency_bilingual_v4",
        "agency_bilingual_v4_no_extras",
        "agency_bilingual_v4_lump_sum",
        "agency_english",
        "agency_mandarin",
    ]
    assert [item["name"] for item in specs] == [
        "Bilingual Agency Motor",
        "Bilingual Agency Motor v2",
        "Bilingual Agency Motor v3",
        "Bilingual Agency Motor v3 (No Extras)",
        "Bilingual Agency Motor v3 (Lump Sum Extras)",
        "Bilingual Agency Motor v4",
        "Bilingual Agency Motor v4 (No Extras)",
        "Bilingual Agency Motor v4 (Lump Sum Extras)",
        "English Agency Motor",
        "Mandarin Agency Motor",
    ]
    assert [item["is_default"] for item in specs] == [False, False, False, False, False, True, False, False, False, False]
    assert [item["config"]["page_profile"]["height"] for item in specs] == [1123] * len(specs)


def test_master_nodes_are_clean_bounded_and_publishable():
    forbidden = {"group", "shape", "special", "benefit-card", "benefit-section"}
    for spec in master_template_specs():
        config = validate_template_config(spec["config"])
        canvas = config["canvas"]
        elements = canvas["elements"]
        assert not forbidden.intersection(item["type"] for item in elements)
        assert not any(key in config for key in {"insurance_company_id", "company_id", "insurer_id"})
        grids = [item for item in elements if item["type"] == "benefit-grid"]
        assert [item["gridKind"] for item in grids] == ["current_benefits", "available_addons"]
        for item in elements:
            if item["type"] == "layer-group":
                continue
            assert 0 <= item["x"] <= canvas["width"] - item["w"]
            assert 0 <= item["y"] <= canvas["height"] - item["h"]


def test_customer_card_scenarios_fit_every_master_grid():
    for master in master_template_specs():
        for element in master["config"]["canvas"]["elements"]:
            if element["type"] != "benefit-grid":
                continue
            packing = element["packing"]
            spec = GridSpec(
                strategy=packing["strategy"], alignment=packing["alignment"],
                aspect_ratio=packing["aspectRatio"], reference_width=packing["referenceWidth"],
                reference_height=packing["referenceHeight"], gap_ratio=packing["gapRatio"],
                padding_ratio=packing["paddingRatio"], stagger_ratio=packing["staggerRatio"],
            )
            bounds = GridBounds(element["x"], element["y"], element["w"], element["h"])
            for count in (0, 1, 6, 12, 15, 20):
                layout = pack_fixed_grid(count, bounds, spec)
                assert len(layout.cards) == count
                assert not layout.clipped and not layout.paginated and layout.page_extension == 0
                assert all(bounds.x <= card.x and card.x + card.width <= bounds.x + bounds.width + 1e-6 for card in layout.cards)
                assert all(bounds.y <= card.y and card.y + card.height <= bounds.y + bounds.height + 1e-6 for card in layout.cards)


def test_agency_bilingual_v3_structure_and_authorized_driver():
    from app.services.master_template_service import master_template_specs
    from app.rendering.template_renderer import render_quotation_html

    spec = next(item for item in master_template_specs() if item["key"] == "agency_bilingual_v3")
    assert spec is not None
    assert spec["name"] == "Bilingual Agency Motor v3"

    elements = spec["config"]["canvas"]["elements"]
    element_ids = {e["id"] for e in elements}

    # Authorised Driver row must exist
    assert "lbl_authorized_driver" in element_ids
    assert "val_authorized_driver" in element_ids

    # Right column should NOT have all_driver_bg or redundant cards
    assert "all_driver_bg" not in element_ids
    assert "rc_container_drivers" not in element_ids

    # Payment image should point to bank_qr_layout_dark slot
    pay_img = next(e for e in elements if e["id"] == "payment_account_details_img")
    assert pay_img.get("assetSlot") == "bank_qr_layout_dark"

    # Coverage table background should have top border and encompass total payable
    cov_table = next(e for e in elements if e["id"] == "cov_table_bg")
    assert cov_table["y"] == 120

    # Test rendering with default / all driver vs named driver
    fields = {
        "insured_name": {"value": "CHENG TECK KIONG"},
        "premium": {"value": "4419.01"},
        "roadtax": {"value": "40.00"},
        "service_fee": {"value": "0.00"},
        "total_amount": {"value": "4673.21"},
    }
    html_default = render_quotation_html(fields, template_config=spec["config"])
    assert "Authorised Driver / 授权驾驶人" in html_default
    assert "All Driver" in html_default
    assert "Roadtax and Runner Fee / 路税及服务费" in html_default

    # Named driver quotation
    fields_named = {
        **fields,
        "raw_text": {"value": "Named Driver only: John Doe"},
    }
    html_named = render_quotation_html(fields_named, template_config=spec["config"])
    assert "Named Driver" in html_named


def test_agency_bilingual_v3_no_extras_structure_and_rendering():
    from app.services.master_template_service import master_template_specs
    from app.rendering.template_renderer import render_quotation_html

    spec = next(item for item in master_template_specs() if item["key"] == "agency_bilingual_v3_no_extras")
    assert spec is not None
    assert spec["name"] == "Bilingual Agency Motor v3 (No Extras)"
    assert spec["config"]["extras_mode"] == "none"

    pib = next(e for e in spec["config"]["canvas"]["elements"] if e["id"] == "premium_info_block")
    assert pib.get("extras_mode") == "none"

    fields = {
        "insured_name": {"value": "CHENG TECK KIONG"},
        "premium": {"value": "4000.00"},
        "roadtax": {"value": "40.00"},
        "service_fee": {"value": "0.00"},
        "total_amount": {"value": "4790.00"},
    }
    render_context = {
        "extras": [
            {"label": "Windscreen Protection", "price": {"amount": 500.00}, "coverage_limit": "5,000"},
            {"label": "Special Perils", "price": {"amount": 250.00}},
        ],
        "current_benefits": [
            {"label": "Windscreen Protection", "is_extra": True, "price": 500.00},
            {"label": "Special Perils", "is_extra": True, "price": 250.00},
            {"label": "24 Hours Towing", "is_extra": False},
        ],
        "available_addons": [
            {"label": "Legal Liability to Passengers"},
        ],
    }
    html = render_quotation_html(fields, template_config=spec["config"], render_context=render_context)

    # Folded Insurance Premium = base 4000.00 + extras 750.00 = 4,750.00
    assert "4,750.00" in html
    assert "40.00" in html
    assert "4,790.00" in html

    # Extras text and section completely omitted
    assert "Windscreen" not in html
    assert "Special Perils" not in html
    assert "Extras / 附加项目" not in html

    # Benefits and add-ons remain
    assert "24 Hours Towing" in html
    assert "Legal Liability" in html

    # Verify coverage card is not inflated and page fits strictly within A4 height (1123px)
    from app.rendering.template_renderer import _balance_benefit_grid_elements
    balanced = _balance_benefit_grid_elements(spec["config"]["canvas"]["elements"], render_context)
    cov_table = next(e for e in balanced if e["id"] == "cov_table_bg")
    assert cov_table["h"] == 260.0
    max_bottom = max(float(e.get("y", 0)) + float(e.get("h", 0)) for e in balanced)
    assert max_bottom <= 1123.0


def test_agency_bilingual_v3_lump_sum_structure_and_rendering():
    from app.services.master_template_service import master_template_specs
    from app.rendering.template_renderer import render_quotation_html

    spec = next(item for item in master_template_specs() if item["key"] == "agency_bilingual_v3_lump_sum")
    assert spec is not None
    assert spec["name"] == "Bilingual Agency Motor v3 (Lump Sum Extras)"
    assert spec["config"]["extras_mode"] == "lump_sum"

    pib = next(e for e in spec["config"]["canvas"]["elements"] if e["id"] == "premium_info_block")
    assert pib.get("extras_mode") == "lump_sum"

    fields = {
        "insured_name": {"value": "CHENG TECK KIONG"},
        "premium": {"value": "4000.00"},
        "roadtax": {"value": "40.00"},
        "service_fee": {"value": "0.00"},
        "total_amount": {"value": "4790.00"},
    }
    render_context = {
        "extras": [
            {"label": "Windscreen Protection", "price": {"amount": 500.00}, "coverage_limit": "5,000"},
            {"label": "Special Perils", "price": {"amount": 250.00}},
        ],
        "current_benefits": [
            {"label": "Windscreen Protection", "is_extra": True, "price": 500.00},
            {"label": "Special Perils", "is_extra": True, "price": 250.00},
            {"label": "24 Hours Towing", "is_extra": False},
        ],
        "available_addons": [
            {"label": "Legal Liability to Passengers"},
        ],
    }
    html = render_quotation_html(fields, template_config=spec["config"], render_context=render_context)

    # Base premium displayed distinctly
    assert "4,000.00" in html
    # Single lump sum line: Extras / 附加项目 RM 750.00
    assert "Extras / 附加项目" in html
    assert "750.00" in html
    assert "40.00" in html
    assert "4,790.00" in html

    # Individual benefit item lines omitted
    assert "Windscreen" not in html
    assert "Special Perils" not in html

    # Benefits and add-ons remain
    assert "24 Hours Towing" in html
    assert "Legal Liability" in html

    # Verify coverage card is not inflated and page fits strictly within A4 height (1123px)
    from app.rendering.template_renderer import _balance_benefit_grid_elements
    balanced = _balance_benefit_grid_elements(spec["config"]["canvas"]["elements"], render_context)
    cov_table = next(e for e in balanced if e["id"] == "cov_table_bg")
    assert cov_table["h"] == 260.0
    max_bottom = max(float(e.get("y", 0)) + float(e.get("h", 0)) for e in balanced)
    assert max_bottom <= 1123.0
