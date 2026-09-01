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
    assert [item["key"] for item in specs] == ["standard_a4", "dense_a4", "agency_bilingual", "extended_portrait"]
    assert [item["name"] for item in specs] == ["Standard A4", "Dense A4", "Bilingual Agency Motor", "Extended Portrait"]
    assert [item["is_default"] for item in specs] == [False, False, True, False]
    assert [item["config"]["page_profile"]["height"] for item in specs] == [1123, 1123, 1123, 1480]


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
