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
