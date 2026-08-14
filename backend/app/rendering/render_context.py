"""Build immutable, deterministic quotation benefit-card render context."""

from __future__ import annotations

import json
from decimal import Decimal
from hashlib import sha256
from typing import Any, Iterable

from pydantic import ValidationError

from app.domain.benefits import BenefitValue


class RenderContextError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def canonical_context_hash(context: dict) -> str:
    return sha256(canonical_json(context).encode("utf-8")).hexdigest()


def _number(value: Any) -> str:
    try:
        number = Decimal(str(value))
    except Exception:
        raise RenderContextError("Benefit value is incomplete or invalid.") from None
    if number == number.to_integral_value():
        return f"{int(number):,}"
    return format(number, ",f")


def _money(value: Any, currency: str | None) -> str:
    prefix = "RM" if currency == "MYR" else str(currency or "").upper()
    return f"{prefix} {_number(value)}".strip()


def format_benefit_value(raw_value: dict | None) -> str:
    if raw_value is None:
        return ""
    try:
        value = BenefitValue.model_validate(raw_value)
    except ValidationError as exc:
        raise RenderContextError("Benefit value is incomplete or invalid.") from exc
    if value.display_text:
        return value.display_text
    if value.type == "distance":
        base = "Unlimited" if value.unlimited else f"{_number(value.value)} {value.unit}"
        return f"{base} · {value.region}" if value.region else base
    if value.type == "money":
        return _money(value.value, value.currency)
    if value.type == "percentage":
        base = f"{_number(value.value)}% of {value.basis}"
        return f"{base} · cap {_money(value.cap.amount, value.cap.currency)}" if value.cap else base
    if value.type == "per_day":
        base = f"{_money(value.value, value.currency)} per day · up to {value.max_days} days"
        return f"{base} · cap {_number(value.aggregate_cap)}" if value.aggregate_cap is not None else base
    if value.type == "region":
        return str(value.region)
    if value.type == "boolean":
        return "Included" if value.value else "Not included"
    if value.type == "enum":
        return str(value.enum_key)
    if value.type == "package_plan":
        return str(value.plan_key)
    if value.type == "formula":
        return str(value.expression)
    if value.value is not None:
        suffix = f" {value.unit}" if value.unit else ""
        return f"{value.value}{suffix}"
    return ""


def _index(rows: Iterable[Any]) -> dict[str, Any]:
    return {str(item.id): item for item in rows}


def _card(
    *,
    selection: Any | None,
    offering: Any,
    concept: Any,
    typed_value: dict | None,
    label: str | None = None,
    asset_id: str | None = None,
    facet_id: str | None = None,
    branch_key: str | None = None,
) -> dict:
    return {
        "card_key": f"{getattr(selection, 'id', 'offer')}:{offering.id}:{facet_id or 'parent'}",
        "entitlement_key": str(getattr(selection, "id", f"offer:{offering.id}")),
        "selection_id": getattr(selection, "id", None),
        "offering_id": offering.id,
        "offering_key": getattr(offering, "offering_key", f"custom:{getattr(selection, 'id', 'offer')}"),
        "concept_id": concept.id,
        "concept_key": concept.concept_key,
        "facet_id": facet_id,
        "branch_key": branch_key,
        "label": label or getattr(offering, "label_override", None) or concept.label,
        "value": format_benefit_value(typed_value) if typed_value is not None else "",
        "typed_value": typed_value,
        "asset_id": asset_id or concept.default_asset_id,
        "cost_status": getattr(selection, "cost_status", None),
        "sort_order": int(getattr(offering, "sort_order", 0) or 0),
    }


def _expanded_cards(selection: Any, offering: Any, concept: Any, facets_by_id: dict[str, Any]) -> list[dict]:
    typed_value = getattr(selection, "typed_value_override", None) or offering.typed_value
    facet_ids = list(offering.presentation_facet_ids or [])
    if not facet_ids:
        return [_card(selection=selection, offering=offering, concept=concept, typed_value=typed_value)]
    cards: list[dict] = []
    for facet_id in facet_ids:
        facet = facets_by_id.get(str(facet_id))
        if not facet or facet.status != "active" or facet.parent_concept_id != concept.id:
            raise RenderContextError("A published presentation facet is unavailable or belongs to another concept.")
        cards.append(_card(
            selection=selection,
            offering=offering,
            concept=concept,
            typed_value=typed_value,
            label=facet.label,
            asset_id=facet.asset_id or concept.default_asset_id,
            facet_id=facet.id,
        ))
    return cards


def resolve_benefit_cards(
    *,
    selections: list[Any],
    offerings: list[Any],
    concepts: list[Any],
    relations: list[Any],
    facets: list[Any],
) -> dict[str, list[dict]]:
    """Resolve current and available cards solely from pinned rows and decisions."""

    offerings_by_id = _index(offerings)
    concepts_by_id = _index(concepts)
    facets_by_id = _index(facets)
    selected_offering_ids = {
        str(item.catalog_offering_id)
        for item in selections
        if item.catalog_offering_id and item.state in {"current", "superseded"}
    }
    current = [item for item in selections if item.state == "current"]
    current_by_concept: dict[str, list[Any]] = {}
    for item in current:
        concept_id = str(item.concept_id or "")
        current_by_concept.setdefault(concept_id, []).append(item)
    duplicates = [key for key, items in current_by_concept.items() if key and len(items) > 1]
    if duplicates:
        raise RenderContextError("A benefit concept has more than one current selection.")

    current_cards: list[dict] = []
    for item in sorted(current, key=lambda row: (int(row.sort_order or 0), str(row.selection_key))):
        if item.item_kind == "custom":
            concept = concepts_by_id.get(str(item.concept_id))
            concept = concept or type("CustomConcept", (), {
                "id": item.concept_id or f"custom:{item.id}", "concept_key": item.selection_key,
                "label": item.label_override or "Custom benefit", "default_asset_id": None,
            })()
            pseudo = type("CustomOffering", (), {
                "id": f"custom:{item.id}", "label_override": item.label_override,
                "typed_value": item.typed_value_override, "sort_order": item.sort_order,
                "presentation_facet_ids": [],
            })()
            current_cards.append(_card(selection=item, offering=pseudo, concept=concept, typed_value=item.typed_value_override))
            continue
        offering = offerings_by_id.get(str(item.catalog_offering_id))
        if not offering or offering.status not in {"active", "compatibility"}:
            raise RenderContextError("A selected catalog offering is unavailable from the pinned revision.")
        concept = concepts_by_id.get(str(offering.concept_id))
        if not concept:
            raise RenderContextError("A selected benefit concept is unavailable.")
        current_cards.extend(_expanded_cards(item, offering, concept, facets_by_id))

    outgoing: dict[str, list[Any]] = {}
    for item in relations:
        if item.relation_kind == "replaces":
            outgoing.setdefault(str(item.from_offering_id), []).append(item)
    offered_ids: set[str] = set()
    available_cards: list[dict] = []
    for item in current:
        if not item.catalog_offering_id:
            continue
        edges = sorted(outgoing.get(str(item.catalog_offering_id), []), key=lambda edge: (int(edge.sort_order or 0), str(edge.branch_key or ""), str(edge.to_offering_id)))
        for edge in edges:
            target = offerings_by_id.get(str(edge.to_offering_id))
            if not target or target.status not in {"active", "compatibility"} or target.id in selected_offering_ids or target.id in offered_ids:
                continue
            concept = concepts_by_id.get(str(target.concept_id))
            if not concept:
                raise RenderContextError("An upgrade relation references a missing concept.")
            available_cards.append(_card(
                selection=None, offering=target, concept=concept, typed_value=target.typed_value,
                branch_key=edge.branch_key,
            ))
            offered_ids.add(target.id)

    # A concept with no current/base choice may expose only its first explicit
    # optional offering. Numeric value magnitude is never consulted.
    active_concepts = {str(item.concept_id) for item in current}
    optionals_by_concept: dict[str, list[Any]] = {}
    for item in offerings:
        if item.offering_kind == "optional" and item.status in {"active", "compatibility"}:
            optionals_by_concept.setdefault(str(item.concept_id), []).append(item)
    for concept_id, items in optionals_by_concept.items():
        if concept_id in active_concepts or any(str(item.id) in offered_ids for item in items):
            continue
        first = min(items, key=lambda item: (int(item.sort_order or 0), str(item.offering_key)))
        concept = concepts_by_id.get(concept_id)
        if concept:
            available_cards.append(_card(selection=None, offering=first, concept=concept, typed_value=first.typed_value))
            offered_ids.add(first.id)

    available_selected = [item for item in selections if item.state == "available_addon"]
    for item in sorted(available_selected, key=lambda row: (int(row.sort_order or 0), str(row.selection_key))):
        offering = offerings_by_id.get(str(item.catalog_offering_id))
        if not offering or offering.id in offered_ids:
            continue
        concept = concepts_by_id.get(str(offering.concept_id))
        if concept:
            available_cards.append(_card(selection=item, offering=offering, concept=concept, typed_value=item.typed_value_override or offering.typed_value))
            offered_ids.add(offering.id)

    order = lambda card: (card["sort_order"], card["label"].casefold(), card["card_key"])
    return {
        "current_benefits": sorted(current_cards, key=order),
        "available_addons": sorted(available_cards, key=order),
    }
