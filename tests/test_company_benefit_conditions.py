"""Hermetic tests for CompanyBenefitConfig, CompanyBenefitCondition, engine_type, and 7-tier description precedence.

Tests:
1. BenefitCatalog.engine_type, CompanyBenefitConfig, and CompanyBenefitCondition model & schema validations.
2. Dynamic conditional resolution in resolve_benefit_cards (trigger active -> target description upgraded).
3. Dynamic conditional inactive -> falls back to CompanyBenefitConfig.baseline_description.
4. Complete 7-tier resolution hierarchy verification.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault("APP_ENV", "test")

from app.api.schemas import (
    BenefitCatalogSaveRequest,
    CatalogContextRequest,
    CompanyBenefitConditionSaveRequest,
    CompanyBenefitConfigItem,
    CompanyBenefitConfigsUpdateRequest,
)
from app.models.tables import BenefitCatalog, CompanyBenefitCondition, CompanyBenefitConfig
from app.rendering.render_context import resolve_benefit_cards


def row(**kwargs):
    return SimpleNamespace(**kwargs)


def test_models_and_schemas_validation():
    # 1. BenefitCatalog engine_type
    cat_ice = BenefitCatalog(
        id="cat-1",
        name="ICE Catalog",
        engine_type="ice",
        revision=1,
    )
    assert cat_ice.engine_type == "ice"

    cat_ev = BenefitCatalog(
        id="cat-2",
        name="EV Catalog",
        engine_type="ev",
        revision=1,
    )
    assert cat_ev.engine_type == "ev"

    # 2. Schema validation for engine_type
    req_ice = BenefitCatalogSaveRequest(company_id="comp-1", name="Test Catalog", engine_type="ice")
    assert req_ice.engine_type == "ice"

    req_ev = BenefitCatalogSaveRequest(company_id="comp-1", name="Test EV", engine_type="ev")
    assert req_ev.engine_type == "ev"

    ctx_req = CatalogContextRequest(base_revision=1, engine_type="ev")
    assert ctx_req.engine_type == "ev"

    # 3. CompanyBenefitConfig model & schemas
    cfg = CompanyBenefitConfig(
        id="cfg-1",
        company_id="comp-1",
        concept_id="conc-1",
        is_enabled=True,
        baseline_description="Company-wide 100km towing assistance.",
    )
    assert cfg.is_enabled is True
    assert cfg.baseline_description == "Company-wide 100km towing assistance."

    update_req = CompanyBenefitConfigsUpdateRequest(
        items=[
            CompanyBenefitConfigItem(
                concept_id="conc-1",
                is_enabled=True,
                baseline_description="Standard baseline",
            )
        ]
    )
    assert len(update_req.items) == 1
    assert update_req.items[0].baseline_description == "Standard baseline"

    # 4. CompanyBenefitCondition model & schema
    cond = CompanyBenefitCondition(
        id="cond-1",
        company_id="comp-1",
        name="DPP Unlimited Towing",
        trigger_concept_id="conc-dpp",
        target_concept_id="conc-towing",
        replacement_description="Unlimited towing distance within Malaysia",
        is_active=True,
    )
    assert cond.target_concept_id == "conc-towing"
    assert cond.replacement_description == "Unlimited towing distance within Malaysia"

    cond_req = CompanyBenefitConditionSaveRequest(
        name="DPP Towing Rule",
        trigger_concept_id="conc-dpp",
        target_concept_id="conc-towing",
        replacement_description="Unlimited towing distance within Malaysia",
    )
    assert cond_req.trigger_concept_id == "conc-dpp"
    assert cond_req.is_active is True


def test_dynamic_condition_triggers_upgrade():
    # Setup concepts
    conc_dpp = row(
        id="conc-dpp",
        concept_key="addon_driver_passenger_protect",
        label="Driver & Passenger Protection",
        default_asset_id=None,
        display_template="{label}",
        required_variables=[],
        optional_variables=[],
        description="Accidental medical & death coverage.",
        status="active",
    )
    conc_towing = row(
        id="conc-towing",
        concept_key="default_towing_assistance",
        label="Towing & Roadside Assistance",
        default_asset_id=None,
        display_template="{label}",
        required_variables=[],
        optional_variables=[],
        description="Standard 100km complimentary towing.",
        status="active",
    )

    # Setup offerings
    off_dpp = row(
        id="off-dpp",
        offering_key="qbe-dpp",
        concept_id=conc_dpp.id,
        offering_kind="base",
        label_override=None,
        typed_value=None,
        sort_order=1,
        presentation_facet_ids=[],
        description_override=None,
        status="active",
    )
    off_towing = row(
        id="off-towing",
        offering_key="qbe-towing",
        concept_id=conc_towing.id,
        offering_kind="base",
        label_override=None,
        typed_value=None,
        sort_order=2,
        presentation_facet_ids=[],
        description_override="Baseline 100km towing.",
        status="active",
    )

    # Setup selections (both DPP and Towing are active)
    sel_dpp = row(
        id="sel-dpp",
        selection_key="dpp-sel",
        catalog_offering_id=off_dpp.id,
        concept_id=conc_dpp.id,
        item_kind="catalog",
        state="current",
        cost_status="optional_selected",
        label_override=None,
        typed_value_override=None,
        sort_order=1,
        superseded_by_id=None,
    )
    sel_towing = row(
        id="sel-towing",
        selection_key="towing-sel",
        catalog_offering_id=off_towing.id,
        concept_id=conc_towing.id,
        item_kind="catalog",
        state="current",
        cost_status="included",
        label_override=None,
        typed_value_override=None,
        sort_order=2,
        superseded_by_id=None,
    )

    # Condition: When conc-dpp is active, upgrade conc-towing to Unlimited
    condition = row(
        id="cond-1",
        company_id="comp-qbe",
        name="QBE Unlimited Towing Upgrade",
        trigger_concept_id="conc-dpp",
        trigger_plan_filter=None,
        target_concept_id="conc-towing",
        replacement_description="Unlimited towing distance within Malaysia",
        is_active=True,
    )

    result = resolve_benefit_cards(
        selections=[sel_dpp, sel_towing],
        offerings=[off_dpp, off_towing],
        concepts=[conc_dpp, conc_towing],
        relations=[],
        facets=[],
        company_conditions=[condition],
    )

    cards = result["current_benefits"]
    towing_card = next(c for c in cards if c["concept_key"] == "default_towing_assistance")
    assert towing_card["conditional_description"] == "Unlimited towing distance within Malaysia"
    assert towing_card["description_override"] == "Baseline 100km towing."


def test_dynamic_condition_not_triggered_when_inactive():
    conc_dpp = row(
        id="conc-dpp",
        concept_key="addon_driver_passenger_protect",
        label="Driver & Passenger Protection",
        default_asset_id=None,
        display_template="{label}",
        required_variables=[],
        optional_variables=[],
        description="Accidental medical & death coverage.",
        status="active",
    )
    conc_towing = row(
        id="conc-towing",
        concept_key="default_towing_assistance",
        label="Towing & Roadside Assistance",
        default_asset_id=None,
        display_template="{label}",
        required_variables=[],
        optional_variables=[],
        description="Global default 100km towing.",
        status="active",
    )

    off_towing = row(
        id="off-towing",
        offering_key="qbe-towing",
        concept_id=conc_towing.id,
        offering_kind="base",
        label_override=None,
        typed_value=None,
        sort_order=1,
        presentation_facet_ids=[],
        description_override=None,  # No offering override
        status="active",
    )

    sel_towing = row(
        id="sel-towing",
        selection_key="towing-sel",
        catalog_offering_id=off_towing.id,
        concept_id=conc_towing.id,
        item_kind="catalog",
        state="current",
        cost_status="included",
        label_override=None,
        typed_value_override=None,
        sort_order=1,
        superseded_by_id=None,
    )

    condition = row(
        id="cond-1",
        company_id="comp-qbe",
        name="QBE Unlimited Towing Upgrade",
        trigger_concept_id="conc-dpp",
        trigger_plan_filter=None,
        target_concept_id="conc-towing",
        replacement_description="Unlimited towing distance within Malaysia",
        is_active=True,
    )

    company_config = row(
        id="cfg-1",
        company_id="comp-qbe",
        concept_id="conc-towing",
        is_enabled=True,
        baseline_description="QBE baseline 150km breakdown towing assistance.",
    )

    # Note: sel_dpp is NOT present in selections -> condition does not trigger
    result = resolve_benefit_cards(
        selections=[sel_towing],
        offerings=[off_towing],
        concepts=[conc_towing, conc_dpp],
        relations=[],
        facets=[],
        company_conditions=[condition],
        company_configs=[company_config],
    )

    cards = result["current_benefits"]
    towing_card = next(c for c in cards if c["concept_key"] == "default_towing_assistance")
    # Condition did not fire; falls back to company config baseline description!
    assert towing_card["description"] == "QBE baseline 150km breakdown towing assistance."
    assert towing_card["is_custom_description"] is True
    assert towing_card["description_override"] is None


def test_complete_7_tier_precedence():
    conc_target = row(
        id="conc-target",
        concept_key="target_benefit",
        label="Target Benefit",
        default_asset_id=None,
        display_template="{label}",
        required_variables=[],
        optional_variables=[],
        description="Tier 6: Master Concept Default",
        status="active",
    )
    conc_trigger = row(
        id="conc-trigger",
        concept_key="trigger_benefit",
        label="Trigger Benefit",
        default_asset_id=None,
        display_template="{label}",
        required_variables=[],
        optional_variables=[],
        description="Trigger concept",
        status="active",
    )

    off_target = row(
        id="off-target",
        offering_key="target-offering",
        concept_id=conc_target.id,
        offering_kind="base",
        label_override=None,
        typed_value=None,
        sort_order=1,
        presentation_facet_ids=[],
        description_override="Tier 3: Catalog Offering Override",
        status="active",
    )
    off_trigger = row(
        id="off-trigger",
        offering_key="trigger-offering",
        concept_id=conc_trigger.id,
        offering_kind="base",
        label_override=None,
        typed_value=None,
        sort_order=2,
        presentation_facet_ids=[],
        description_override=None,
        status="active",
    )

    sel_trigger = row(
        id="sel-trigger",
        selection_key="sel-trig",
        catalog_offering_id=off_trigger.id,
        concept_id=conc_trigger.id,
        item_kind="catalog",
        state="current",
        cost_status="included",
        label_override=None,
        typed_value_override=None,
        sort_order=2,
        superseded_by_id=None,
    )

    condition = row(
        id="cond-1",
        company_id="comp-1",
        name="Upgrade Rule",
        trigger_concept_id="conc-trigger",
        trigger_plan_filter=None,
        target_concept_id="conc-target",
        replacement_description="Tier 2: Dynamic Conditional Upgrade",
        is_active=True,
    )
    company_config = row(
        id="cfg-1",
        company_id="comp-1",
        concept_id="conc-target",
        is_enabled=True,
        baseline_description="Tier 4: Company Master Baseline Description",
    )

    # 1. Tier 1: Selection override beats all (even when dynamic condition is active)
    sel_target_t1 = row(
        id="sel-target",
        selection_key="sel-target",
        catalog_offering_id=off_target.id,
        concept_id=conc_target.id,
        item_kind="catalog",
        state="current",
        cost_status="included",
        label_override=None,
        typed_value_override={"description": "Tier 1: Manual Quotation Selection Override"},
        sort_order=1,
        superseded_by_id=None,
    )
    res_t1 = resolve_benefit_cards(
        selections=[sel_target_t1, sel_trigger],
        offerings=[off_target, off_trigger],
        concepts=[conc_target, conc_trigger],
        relations=[],
        facets=[],
        company_conditions=[condition],
        company_configs=[company_config],
    )
    assert res_t1["current_benefits"][0]["description"] == "Tier 1: Manual Quotation Selection Override"

    # 2. Tier 2: Dynamic conditional upgrade beats offering override and baseline
    sel_target_plain = row(
        id="sel-target",
        selection_key="sel-target",
        catalog_offering_id=off_target.id,
        concept_id=conc_target.id,
        item_kind="catalog",
        state="current",
        cost_status="included",
        label_override=None,
        typed_value_override=None,
        sort_order=1,
        superseded_by_id=None,
    )
    res_t2 = resolve_benefit_cards(
        selections=[sel_target_plain, sel_trigger],
        offerings=[off_target, off_trigger],
        concepts=[conc_target, conc_trigger],
        relations=[],
        facets=[],
        company_conditions=[condition],
        company_configs=[company_config],
    )
    assert res_t2["current_benefits"][0]["description"] == "Tier 2: Dynamic Conditional Upgrade"

    # 3. Tier 3: Offering override beats company baseline description (when condition inactive)
    res_t3 = resolve_benefit_cards(
        selections=[sel_target_plain],  # No trigger selection
        offerings=[off_target, off_trigger],
        concepts=[conc_target, conc_trigger],
        relations=[],
        facets=[],
        company_conditions=[condition],
        company_configs=[company_config],
    )
    assert res_t3["current_benefits"][0]["description"] == "Tier 3: Catalog Offering Override"

    # 4. Tier 4: Company baseline description (when offering override is None)
    off_target.description_override = None
    res_t4 = resolve_benefit_cards(
        selections=[sel_target_plain],
        offerings=[off_target, off_trigger],
        concepts=[conc_target, conc_trigger],
        relations=[],
        facets=[],
        company_conditions=[condition],
        company_configs=[company_config],
    )
    assert res_t4["current_benefits"][0]["description"] == "Tier 4: Company Master Baseline Description"

    # 5. Tier 6: Master Concept default (when company config baseline is None)
    company_config.baseline_description = None
    res_t6 = resolve_benefit_cards(
        selections=[sel_target_plain],
        offerings=[off_target, off_trigger],
        concepts=[conc_target, conc_trigger],
        relations=[],
        facets=[],
        company_conditions=[condition],
        company_configs=[company_config],
    )
    assert res_t6["current_benefits"][0]["description"] == "Tier 6: Master Concept Default"

    # 6. Tier 7: Fallback empty string (when master concept description is None)
    conc_target.description = None
    res_t7 = resolve_benefit_cards(
        selections=[sel_target_plain],
        offerings=[off_target, off_trigger],
        concepts=[conc_target, conc_trigger],
        relations=[],
        facets=[],
        company_conditions=[condition],
        company_configs=[company_config],
    )
    assert res_t7["current_benefits"][0]["description"] == ""
