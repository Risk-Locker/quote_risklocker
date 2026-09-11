"""Hermetic tests for CatalogOffering.description_override and hierarchical resolution.

Ensures that company/vehicle specific short benefit descriptions:
1. Persist cleanly on CatalogOffering and pass Pydantic schema validation.
2. Are preserved across revision cloning and business setup mutations.
3. Resolve hierarchically (Selection -> Offering Override -> Matrix Fallback -> Global Master Concept -> Empty).
4. Correctly populate card.is_custom_description and card.description_override.
5. Export accurately into company matrix service and multi-sheet Excel reports.
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import openpyxl
import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault("APP_ENV", "test")

from app.api.schemas import CatalogOfferingSaveRequest
from app.models.tables import CatalogOffering
from app.rendering.render_context import resolve_benefit_cards
from app.services.business_setup_service import _offering
from app.services.matrix_service import generate_company_matrix_xlsx


def test_catalog_offering_model_and_schema():
    # 1. Model field validation
    offering = CatalogOffering(
        id="off-1",
        catalog_revision_id="rev-1",
        offering_key="test-windscreen",
        concept_id="conc-1",
        offering_kind="base",
        description_override="Custom RM 1,000 windscreen coverage with zero excess.",
    )
    assert offering.description_override == "Custom RM 1,000 windscreen coverage with zero excess."

    # 2. Pydantic request schema validation
    req = CatalogOfferingSaveRequest(
        offering_key="test-windscreen",
        concept_id="conc-1",
        offering_kind="base",
        base_revision=1,
        description_override="  Cleaned text with leading/trailing spaces   ",
    )
    assert req.description_override == "  Cleaned text with leading/trailing spaces   "

    req_none = CatalogOfferingSaveRequest(
        offering_key="test-windscreen",
        concept_id="conc-1",
        offering_kind="base",
        base_revision=1,
        description_override=None,
    )
    assert req_none.description_override is None


def test_business_setup_offering_serialization():
    offering = CatalogOffering(
        id="off-1",
        catalog_revision_id="rev-1",
        offering_key="test-towing",
        concept_id="conc-1",
        offering_kind="base",
        description_override="24/7 Unlimited nationwide towing to authorized workshop.",
    )
    serialized = _offering(offering)
    assert serialized["description_override"] == "24/7 Unlimited nationwide towing to authorized workshop."

    offering_empty = CatalogOffering(
        id="off-2",
        catalog_revision_id="rev-1",
        offering_key="test-towing-empty",
        concept_id="conc-1",
        offering_kind="base",
        description_override=None,
    )
    serialized_empty = _offering(offering_empty)
    assert serialized_empty["description_override"] is None


def test_hierarchical_description_resolution_5_tiers():
    def row(**kwargs):
        return SimpleNamespace(**kwargs)

    conc = row(
        id="concept-flood",
        concept_key="flood-coverage",
        label="Flood / Special Perils",
        default_asset_id=None,
        display_template="{label}",
        required_variables=[],
        optional_variables=[],
        description="Global default protection against floods, storms, and natural disasters.",
        status="active",
    )

    # ── Tier 1: Selection override in draft wins over offering override & concept default ──
    off1 = row(
        id="off-1",
        offering_key="flood-offering",
        concept_id=conc.id,
        offering_kind="base",
        label_override=None,
        typed_value=None,
        sort_order=1,
        presentation_facet_ids=[],
        description_override="Company offering description override.",
        status="active",
    )
    sel1 = row(
        id="sel-1",
        selection_key="flood-sel",
        catalog_offering_id=off1.id,
        concept_id=conc.id,
        item_kind="catalog",
        state="current",
        cost_status="included",
        label_override=None,
        typed_value_override={"description": "Draft selection tier-1 explicit custom description."},
        sort_order=1,
        superseded_by_id=None,
    )

    res1 = resolve_benefit_cards(
        selections=[sel1],
        offerings=[off1],
        concepts=[conc],
        relations=[],
        facets=[],
    )
    cards1 = res1["current_benefits"]
    assert len(cards1) == 1
    assert cards1[0]["description"] == "Draft selection tier-1 explicit custom description."
    assert cards1[0]["is_custom_description"] is True
    assert cards1[0]["description_override"] == "Company offering description override."

    # ── Tier 2: Offering description_override wins when no draft selection override exists ──
    sel2 = row(
        id="sel-2",
        selection_key="flood-sel",
        catalog_offering_id=off1.id,
        concept_id=conc.id,
        item_kind="catalog",
        state="current",
        cost_status="included",
        label_override=None,
        typed_value_override=None,
        sort_order=1,
        superseded_by_id=None,
    )
    res2 = resolve_benefit_cards(
        selections=[sel2],
        offerings=[off1],
        concepts=[conc],
        relations=[],
        facets=[],
    )
    cards2 = res2["current_benefits"]
    assert len(cards2) == 1
    assert cards2[0]["description"] == "Company offering description override."
    assert cards2[0]["is_custom_description"] is True
    assert cards2[0]["description_override"] == "Company offering description override."

    # ── Tier 3: Insurer catalog matrix fallback when offering has no override ──
    conc_windscreen = row(
        id="concept-ws",
        concept_key="windscreen",
        label="Windscreen Cover",
        default_asset_id=None,
        display_template="{label}",
        required_variables=[],
        optional_variables=[],
        description="Global master windscreen protection.",
        status="active",
    )
    off_ws = row(
        id="off-ws",
        offering_key="qbe-ws",
        concept_id=conc_windscreen.id,
        offering_kind="base",
        label_override=None,
        typed_value=None,
        sort_order=2,
        presentation_facet_ids=[],
        description_override=None,  # No override on offering
        status="active",
    )
    sel_ws = row(
        id="sel-ws",
        selection_key="ws-sel",
        catalog_offering_id=off_ws.id,
        concept_id=conc_windscreen.id,
        item_kind="catalog",
        state="current",
        cost_status="included",
        label_override=None,
        typed_value_override=None,
        sort_order=2,
        superseded_by_id=None,
    )
    mock_catalog = [
        {
            "concept_key": "windscreen",
            "description": "Insurer catalog matrix: Replaces front & rear windscreen with zero NCD penalty.",
        }
    ]
    res_ws = resolve_benefit_cards(
        selections=[sel_ws],
        offerings=[off_ws],
        concepts=[conc_windscreen],
        relations=[],
        facets=[],
        insurer_catalog=mock_catalog,
    )
    cards_ws = res_ws["current_benefits"]
    assert len(cards_ws) == 1
    assert cards_ws[0]["description"] == "Insurer catalog matrix: Replaces front & rear windscreen with zero NCD penalty."

    # ── Tier 4: Global Master Concept description used when no offering override or matrix fallback ──
    conc_generic = row(
        id="concept-gen",
        concept_key="unmatched-custom-concept",
        label="Custom Benefit",
        default_asset_id=None,
        display_template="{label}",
        required_variables=[],
        optional_variables=[],
        description="Master global standard benefit wording.",
        status="active",
    )
    off_generic = row(
        id="off-gen",
        offering_key="gen-off",
        concept_id=conc_generic.id,
        offering_kind="base",
        label_override=None,
        typed_value=None,
        sort_order=3,
        presentation_facet_ids=[],
        description_override=None,
        status="active",
    )
    sel_generic = row(
        id="sel-gen",
        selection_key="gen-sel",
        catalog_offering_id=off_generic.id,
        concept_id=conc_generic.id,
        item_kind="catalog",
        state="current",
        cost_status="included",
        label_override=None,
        typed_value_override=None,
        sort_order=3,
        superseded_by_id=None,
    )
    res_gen = resolve_benefit_cards(
        selections=[sel_generic],
        offerings=[off_generic],
        concepts=[conc_generic],
        relations=[],
        facets=[],
    )
    cards_generic = res_gen["current_benefits"]
    assert len(cards_generic) == 1
    assert cards_generic[0]["description"] == "Master global standard benefit wording."
    assert cards_generic[0]["is_custom_description"] is False

    # ── Tier 5: Fallback to empty string if concept has no description ──
    conc_nodesc = row(
        id="concept-nodesc",
        concept_key="no-desc-concept",
        label="No Desc Benefit",
        default_asset_id=None,
        display_template="{label}",
        required_variables=[],
        optional_variables=[],
        description=None,
        status="active",
    )
    off_nodesc = row(
        id="off-nodesc",
        offering_key="nodesc-off",
        concept_id=conc_nodesc.id,
        offering_kind="base",
        label_override=None,
        typed_value=None,
        sort_order=4,
        presentation_facet_ids=[],
        description_override=None,
        status="active",
    )
    sel_nodesc = row(
        id="sel-nodesc",
        selection_key="nodesc-sel",
        catalog_offering_id=off_nodesc.id,
        concept_id=conc_nodesc.id,
        item_kind="catalog",
        state="current",
        cost_status="included",
        label_override=None,
        typed_value_override=None,
        sort_order=4,
        superseded_by_id=None,
    )
    res_nodesc = resolve_benefit_cards(
        selections=[sel_nodesc],
        offerings=[off_nodesc],
        concepts=[conc_nodesc],
        relations=[],
        facets=[],
    )
    cards_nodesc = res_nodesc["current_benefits"]
    assert len(cards_nodesc) == 1
    assert cards_nodesc[0]["description"] == ""
    assert cards_nodesc[0]["is_custom_description"] is False


def test_matrix_excel_export_includes_description_columns():
    test_matrix = {
        "company": {
            "id": "comp-1",
            "name": "QBE Insurance (Malaysia) Berhad",
            "slug": "qbe",
            "category": "Motor",
        },
        "summary": {
            "total_products": 1,
            "total_scenarios": 1,
            "total_defaults": 1,
            "total_addons": 1,
            "total_bundles": 0,
        },
        "scenarios": [
            {
                "catalog_id": "cat-1",
                "product_id": "prod-1",
                "product_name": "Private Car Comprehensive",
                "product_key": "qbe-car",
                "scenario_name": "Private Car Comprehensive",
                "segment_name": "Private",
                "segment_key": "private",
                "vehicle_category_name": "Car",
                "vehicle_category_key": "car",
                "coverage_type_name": "Comprehensive",
                "coverage_type_key": "comprehensive",
                "system_type": "Add-on System",
                "revision_number": 1,
                "state": "published",
                "defaults": [
                    {
                        "offering_id": "off-d1",
                        "offering_key": "qbe-towing",
                        "concept_key": "towing",
                        "label": "24/7 Breakdown Towing",
                        "description": "Unlimited towing to preferred workshop nationwide.",
                        "is_custom_description": True,
                        "description_override": "Unlimited towing to preferred workshop nationwide.",
                        "display_value": "Unlimited",
                        "price": 0.0,
                        "price_text": "0 RM",
                    }
                ],
                "addons": [
                    {
                        "offering_id": "off-a1",
                        "offering_key": "qbe-windscreen",
                        "concept_key": "windscreen",
                        "label": "Windscreen & Window Glass",
                        "description": "Replaces shattered front/rear windshield with zero NCD loss.",
                        "is_custom_description": True,
                        "description_override": "Replaces shattered front/rear windshield with zero NCD loss.",
                        "display_value": "RM 1,000",
                        "price": 150.0,
                        "price_text": "RM 150.00",
                    }
                ],
                "bundles": [],
            }
        ],
    }

    raw_xlsx = generate_company_matrix_xlsx(test_matrix)
    assert len(raw_xlsx.getvalue()) > 0

    wb = openpyxl.load_workbook(raw_xlsx)
    assert "Scenarios Overview" in wb.sheetnames
    assert "Detailed Offerings" in wb.sheetnames

    ws_offerings = wb["Detailed Offerings"]
    headers = [cell.value for cell in ws_offerings[1]]
    assert "Short Description" in headers
    assert "Description Source" in headers

    desc_col_idx = headers.index("Short Description") + 1
    source_col_idx = headers.index("Description Source") + 1

    # Row 2 is default towing
    row2_desc = ws_offerings.cell(row=2, column=desc_col_idx).value
    row2_source = ws_offerings.cell(row=2, column=source_col_idx).value
    assert row2_desc == "Unlimited towing to preferred workshop nationwide."
    assert row2_source == "Custom (Company)"

    # Row 3 is addon windscreen
    row3_desc = ws_offerings.cell(row=3, column=desc_col_idx).value
    row3_source = ws_offerings.cell(row=3, column=source_col_idx).value
    assert row3_desc == "Replaces shattered front/rear windshield with zero NCD loss."
    assert row3_source == "Custom (Company)"
