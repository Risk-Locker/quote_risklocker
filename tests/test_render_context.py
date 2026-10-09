"""Canonical benefit-card and immutable render-context behavior."""

from __future__ import annotations

import os
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault("APP_ENV", "test")

from app.rendering.render_context import (  # noqa: E402
    RenderContextError,
    canonical_context_hash,
    format_benefit_value,
    resolve_benefit_cards,
)
from app.domain.benefits import BenefitValue  # noqa: E402


def row(**values):
    return SimpleNamespace(**values)


def concept(key: str, label: str, *, asset_id: str | None = None, template: str = "{label}"):
    return row(
        id=f"concept-{key}", concept_key=key, label=label, default_asset_id=asset_id,
        display_template=template, required_variables=[], optional_variables=[], status="active",
    )


def offering(key: str, parent, *, kind="base", value=None, order=0, facets=None):
    return row(
        id=f"offering-{key}", offering_key=key, concept_id=parent.id,
        offering_kind=kind, label_override=None, typed_value=value,
        sort_order=order, presentation_facet_ids=facets or [], status="active",
    )


def selection(key: str, item, *, state="current", cost="included", override=None, superseded_by=None):
    return row(
        id=f"selection-{key}", selection_key=key, catalog_offering_id=item.id if item else None,
        concept_id=item.concept_id if item else None, item_kind="catalog" if item else "custom",
        state=state, cost_status=cost, label_override=None,
        typed_value_override=override, sort_order=0, superseded_by_id=superseded_by,
    )


def relation(source, target, *, kind="replaces", branch=None, order=0):
    return row(
        from_offering_id=source.id, to_offering_id=target.id,
        relation_kind=kind, branch_key=branch, sort_order=order,
    )


def test_selected_upgrade_replaces_current_concept_and_offers_only_explicit_next_edge():
    towing = concept("towing", "Towing")
    base = offering("towing-50", towing, value={"type": "distance", "value": 50, "unit": "km"})
    upgraded = offering("towing-100", towing, value={"type": "distance", "value": 100, "unit": "km"}, order=1)
    next_upgrade = offering("towing-200", towing, value={"type": "distance", "value": 200, "unit": "km"}, order=2)
    cards = resolve_benefit_cards(
        selections=[
            selection("base", base, state="superseded", superseded_by="selection-upgrade"),
            selection("upgrade", upgraded, state="current", cost="paid"),
        ],
        offerings=[base, upgraded, next_upgrade],
        concepts=[towing],
        relations=[relation(base, upgraded), relation(upgraded, next_upgrade)],
        facets=[],
    )
    assert [card["offering_id"] for card in cards["current_benefits"]] == [upgraded.id]
    assert [card["offering_id"] for card in cards["available_addons"]] == [next_upgrade.id]
    assert cards["current_benefits"][0]["cost_status"] == "paid"
    assert "default" not in cards["current_benefits"][0]
    assert "purchased" not in cards["current_benefits"][0]


def test_branching_upgrade_edges_are_presented_as_separate_choices():
    parent = concept("windscreen", "Windscreen")
    base = offering("windscreen-base", parent, value={"type": "money", "value": 500, "currency": "MYR", "semantic_role": "limit"})
    glass = offering("windscreen-glass", parent, kind="optional", order=1)
    premium = offering("windscreen-premium", parent, kind="optional", order=2)
    cards = resolve_benefit_cards(
        selections=[selection("base", base)], offerings=[base, glass, premium], concepts=[parent],
        relations=[relation(base, glass, branch="glass"), relation(base, premium, branch="premium")], facets=[],
    )
    assert [card["offering_id"] for card in cards["available_addons"]] == [glass.id, premium.id]
    assert [card["branch_key"] for card in cards["available_addons"]] == ["glass", "premium"]


def test_first_optional_is_offered_without_inventing_numeric_upgrade_order():
    flood = concept("flood-assistance", "Flood Assistance")
    second_by_amount = offering("large", flood, kind="optional", value={"type": "money", "value": 5000, "currency": "MYR", "semantic_role": "limit"}, order=20)
    first_by_explicit_order = offering("small", flood, kind="optional", value={"type": "money", "value": 50, "currency": "MYR", "semantic_role": "limit"}, order=5)
    cards = resolve_benefit_cards(
        selections=[], offerings=[second_by_amount, first_by_explicit_order], concepts=[flood], relations=[], facets=[],
    )
    assert [card["offering_id"] for card in cards["available_addons"]] == [first_by_explicit_order.id]


def test_presentation_facets_replace_parent_card_without_creating_extra_entitlements():
    peril = concept("special-perils", "Special Perils", asset_id="parent-art")
    parent = offering("special-perils", peril, facets=["facet-flood", "facet-storm"])
    facets = [
        row(id="facet-flood", parent_concept_id=peril.id, facet_key="flood", label="Flood", asset_id="flood-art", display_template=None, status="active"),
        row(id="facet-storm", parent_concept_id=peril.id, facet_key="storm", label="Storm", asset_id="storm-art", display_template=None, status="active"),
    ]
    cards = resolve_benefit_cards(
        selections=[selection("perils", parent)], offerings=[parent], concepts=[peril], relations=[], facets=facets,
    )
    current = cards["current_benefits"]
    assert [card["label"] for card in current] == ["Flood", "Storm"]
    assert {card["entitlement_key"] for card in current} == {"selection-perils"}
    assert all(card["label"] != "Special Perils" for card in current)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({"type": "distance", "value": 1700, "unit": "km"}, "1,700 km"),
        ({"type": "distance", "value": None, "unit": "km", "unlimited": True, "region": "Malaysia"}, "Unlimited · Malaysia"),
        ({"type": "money", "value": 1500, "currency": "MYR", "semantic_role": "limit"}, "RM 1,500"),
        ({"type": "per_day", "value": 150, "currency": "MYR", "max_days": 7}, "RM 150 per day · up to 7 days"),
        ({"type": "custom", "display_text": "Reviewed roadside arrangement"}, "Reviewed roadside arrangement"),
        ({"type": "distance", "value": "1,200", "unit": "km"}, "1,200 km"),
        ({"type": "money", "value": "1,200", "currency": "MYR", "semantic_role": "limit"}, "RM 1,200"),
        ({"type": "money", "value": "1,200.50", "currency": "MYR", "semantic_role": "limit"}, "RM 1,200.50"),
        ({"type": "distance", "value": "12.345", "unit": "km"}, "12.345 km"),
        ({"type": "distance", "value": "999", "unit": "km"}, "999 km"),
    ],
)
def test_typed_values_preserve_arbitrary_reviewed_values(value, expected):
    assert format_benefit_value(value) == expected


def test_comma_grouped_numeric_values_normalize_exactly_without_rounding():
    value = BenefitValue.model_validate({"type": "distance", "value": "1,200", "unit": "km"})
    assert value.value == Decimal("1200")


def test_invalid_numeric_values_fail_closed_instead_of_crashing():
    with pytest.raises(RenderContextError, match="incomplete or invalid"):
        format_benefit_value({"type": "distance", "value": "abc", "unit": "km"})
    with pytest.raises(ValidationError):
        BenefitValue.model_validate({"type": "distance", "value": "abc", "unit": "km"})


def test_duplicate_current_selections_for_one_concept_fail_closed():
    parent = concept("towing", "Towing")
    first = offering("one", parent)
    second = offering("two", parent)
    with pytest.raises(RenderContextError, match="more than one current"):
        resolve_benefit_cards(
            selections=[selection("one", first), selection("two", second)],
            offerings=[first, second], concepts=[parent], relations=[], facets=[],
        )


def test_context_hash_is_stable_across_dictionary_order_and_changes_on_content():
    left = {"fields": {"a": 1, "b": 2}, "cards": [{"id": "x"}]}
    right = {"cards": [{"id": "x"}], "fields": {"b": 2, "a": 1}}
    assert canonical_context_hash(left) == canonical_context_hash(right)
    right["cards"][0]["id"] = "y"
    assert canonical_context_hash(left) != canonical_context_hash(right)


def test_build_extras_formats_coverage_limit_as_parenthesized_rm_and_ignores_price_matches():
    from app.rendering.render_context import build_extras

    class FakeSel:
        def __init__(self, id, state, label_override, price, coverage_limit=None):
            self.id = id
            self.state = state
            self.label_override = label_override
            self.price = price
            self.coverage_limit = coverage_limit
            self.cost_status = "paid"
            self.catalog_offering_id = None
            self.concept_id = None
            self.sort_order = 0

    selections = [
        FakeSel("s1", "current", "Windscreen", {"amount": "397.50", "currency": "MYR"}, "2650"),
        FakeSel("s2", "current", "Legal Liability to Passengers (LLTP)", {"amount": "41.85", "currency": "MYR"}, "41.85"),
        FakeSel("s3", "current", "Legal Liability of Passengers (LLOP)", {"amount": "7.50", "currency": "MYR"}, None),
    ]
    extras = build_extras(selections, [])
    assert len(extras) == 3
    by_label = {e["label"]: e for e in extras}
    assert by_label["Windscreen"]["coverage_limit"] == "(RM 2,650)"
    assert by_label["Legal Liability to Passengers (LLTP)"]["coverage_limit"] == ""  # Price match suppressed
    assert by_label["Legal Liability of Passengers (LLOP)"]["coverage_limit"] == ""


def test_build_extras_omits_coverage_when_display_overrides_show_coverage_is_false():
    from app.rendering.render_context import build_extras

    class FakeConcept:
        def __init__(self, id, label, concept_key, display_overrides=None):
            self.id = id
            self.label = label
            self.concept_key = concept_key
            self.display_overrides = display_overrides or {}

    class FakeSel:
        def __init__(self, id, concept_id, label_override, price, coverage_limit=None):
            self.id = id
            self.state = "current"
            self.concept_id = concept_id
            self.label_override = label_override
            self.price = price
            self.coverage_limit = coverage_limit
            self.cost_status = "paid"
            self.catalog_offering_id = None
            self.sort_order = 0

    concepts = [
        FakeConcept("c1", "Windscreen", "windscreen", {"enabled": True, "showCoverage": False}),
        FakeConcept("c2", "Towing", "towing", {"showCoverage": True}),
    ]
    selections = [
        FakeSel("s1", "c1", "Windscreen (RM 3,000)", {"amount": "400.00", "currency": "MYR"}, "3000"),
        FakeSel("s2", "c2", "Towing", {"amount": "50.00", "currency": "MYR"}, "1000"),
    ]
    extras = build_extras(selections, concepts)
    by_key = {e["concept_key"]: e for e in extras}
    assert by_key["windscreen"]["coverage_limit"] == ""
    assert by_key["windscreen"]["show_coverage"] is False
    assert by_key["windscreen"]["label"] == "Windscreen"

def test_adjusted_total_text_round_total():
    from app.rendering.render_context import adjusted_total_text

    fields = {
        "premium": {"value": "2060.12"},
        "roadtax": {"value": "90.00"},
        "service_fee": {"value": "0.00"},
        "total_amount": {"value": "2150.12"},
    }
    # Unrounded:
    assert adjusted_total_text(fields, [], round_total=False) == "2,150.12"
    # Rounded: rounds 2150.12 to 2150.00 with 0 cents
    assert adjusted_total_text(fields, [], round_total=True) == "2,150.00"

    # Test with .50 exactly (no premium, falls back to total_amount):
    fields_half = {
        "total_amount": {"value": "800.50"},
    }
    assert adjusted_total_text(fields_half, [], round_total=True) == "801.00"


def test_plan_tier_token_suppression_in_coverage_limit():
    from app.rendering.render_context import build_extras

    class FakeConcept:
        def __init__(self, id, label, key):
            self.id = id
            self.label = label
            self.concept_key = key
            self.display_overrides = {}

    class FakeSel:
        def __init__(self, id, concept_id, label_override, coverage_limit, evidence_limit=None):
            self.id = id
            self.concept_id = concept_id
            self.label_override = label_override
            self.price = {"amount": "50.00", "currency": "MYR"}
            self.coverage_limit = coverage_limit
            self.cost_status = "paid"
            self.catalog_offering_id = None
            self.sort_order = 0
            self.state = "current"
            self.evidence_snapshot = {"coverage_limit": evidence_limit} if evidence_limit else None

    # Extracted tokens like "2", "Plan 2", "Tier 3" should be suppressed from coverage badges
    concepts = [
        FakeConcept("c1", "Motor PA Plus", "motor_pa"),
        FakeConcept("c2", "Windscreen", "windscreen"),
        FakeConcept("c3", "OTO 360", "oto_360"),
    ]
    selections = [
        FakeSel("s1", "c1", "Motor PA Plus", "2", evidence_limit="2"),
        FakeSel("s2", "c2", "Windscreen", "3000", evidence_limit="3000"),
        FakeSel("s3", "c3", "OTO 360", "Plan 2", evidence_limit="Plan 2"),
    ]
    extras = build_extras(selections, concepts)
    by_key = {e["concept_key"]: e for e in extras}
    assert by_key["motor_pa"]["coverage_limit"] == ""
    assert by_key["oto_360"]["coverage_limit"] == ""
    assert by_key["windscreen"]["coverage_limit"] == "(RM 3,000)"


def test_conditional_replacement_title_in_render_context():
    from app.rendering.render_context import resolve_benefit_cards

    class FakeConcept:
        def __init__(self, id, key, label):
            self.id = id
            self.concept_key = key
            self.label = label
            self.default_asset_id = None
            self.display_overrides = {}
            self.description = "Base desc"
            self.status = "active"

    class FakeOffering:
        def __init__(self, id, key, concept_id):
            self.id = id
            self.offering_key = key
            self.concept_id = concept_id
            self.label_override = None
            self.description_override = None
            self.optional_price = None
            self.sort_order = 0
            self.role = "addon_option"
            self.offering_kind = "optional"
            self.presentation_facet_ids = []
            self.typed_value = None
            self.status = "active"

    class FakeSelection:
        def __init__(self, id, concept_id, offering_id, key):
            self.id = id
            self.concept_id = concept_id
            self.catalog_offering_id = offering_id
            self.selection_key = key
            self.state = "current"
            self.item_kind = "extra"
            self.label_override = None
            self.description_override = None
            self.coverage_limit = None
            self.sort_order = 0
            self.typed_value_override = None
            self.evidence_snapshot = None
            self.cost_status = "paid"
            self.package_plan_id = None

    class FakeCondition:
        def __init__(self, trig_id, target_id, rep_title, rep_desc):
            self.trigger_concept_id = trig_id
            self.target_concept_id = target_id
            self.plan_filter = None
            self.action_type = "replace_description"
            self.replacement_title = rep_title
            self.replacement_description = rep_desc

    c_trig = FakeConcept("c_trig", "pa_plus", "PA Plus")
    c_target = FakeConcept("c_target", "car_allowance", "Daily Car Allowance")
    off_trig = FakeOffering("off_trig", "pa_plus", "c_trig")
    off_target = FakeOffering("off_target", "car_allowance", "c_target")
    sel_trig = FakeSelection("sel_trig", "c_trig", "off_trig", "pa_plus")
    sel_target = FakeSelection("sel_target", "c_target", "off_target", "car_allowance")
    cond = FakeCondition("c_trig", "c_target", "Executive Car Allowance", "Upgraded to RM 150/day")

    res = resolve_benefit_cards(
        selections=[sel_trig, sel_target],
        offerings=[off_trig, off_target],
        concepts=[c_trig, c_target],
        relations=[],
        facets=[],
        company_conditions=[cond],
    )
    cards = {c["concept_key"]: c for c in res["current_benefits"]}
    assert cards["car_allowance"]["label"] == "Executive Car Allowance"
    assert cards["car_allowance"]["description"] == "Upgraded to RM 150/day"


