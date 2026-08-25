"""Build immutable, deterministic quotation benefit-card render context."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any, Iterable

from pydantic import ValidationError

from app.domain.benefits import BenefitValue, MoneyAmount


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


def format_money_amount(raw_price: dict | None) -> str:
    """Render a stored MoneyAmount-like price dict; tolerant of legacy shapes."""
    if not raw_price:
        return ""
    try:
        price = MoneyAmount.model_validate(raw_price)
        return _money(price.amount, price.currency)
    except Exception:
        amount = (raw_price or {}).get("amount") if (raw_price or {}).get("amount") is not None else (raw_price or {}).get("value")
        currency = (raw_price or {}).get("currency") or "MYR"
        if amount is None:
            return ""
        try:
            return _money(amount, currency)
        except RenderContextError:
            return ""


def build_extras(selections: Iterable[Any], concepts: Iterable[Any], offerings: Iterable[Any] | None = None) -> list[dict]:
    """Staff-added priced extras shown above the coverage premium."""
    concept_labels = {str(item.id): item.label for item in concepts}
    offerings_by_id = {str(item.id): item for item in (offerings or [])}
    extras: list[dict] = []
    for sel in selections:
        if sel.state != "current":
            continue
        offering = offerings_by_id.get(str(getattr(sel, "catalog_offering_id", None)))
        price = getattr(sel, "price", None) or getattr(offering, "optional_price", None)
        cost_status = getattr(sel, "cost_status", None)
        if cost_status == "included" and not getattr(sel, "price", None):
            continue
        if not price:
            continue
        label = str(getattr(sel, "label_override", None) or "").strip() or concept_labels.get(str(getattr(sel, "concept_id", None)), "Extra benefit")
        extras.append({
            "selection_id": sel.id,
            "label": label,
            "price": price,
            "sort_order": int(getattr(sel, "sort_order", 0) or 0),
        })
    extras.sort(key=lambda item: (item["sort_order"], item["label"].casefold(), item["selection_id"]))
    return extras


def adjusted_total_text(fields: dict, extras: list[dict]) -> str:
    """Total premium including staff-added extras; deterministic from extracted values."""
    raw = (fields or {}).get("total_amount")
    value = raw.get("value") if isinstance(raw, dict) else raw
    try:
        total = Decimal(str(value or "").replace(",", ""))
    except (InvalidOperation, TypeError, ValueError):
        return ""
    for extra in extras:
        raw_price = extra.get("price") or {}
        amount = raw_price.get("amount") if raw_price.get("amount") is not None else raw_price.get("value")
        try:
            total += Decimal(str(amount))
        except (InvalidOperation, TypeError, ValueError):
            continue
    if total == total.to_integral_value():
        return f"{int(total):,}"
    return format(total, ",f")


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
    try:
        card_val = format_benefit_value(typed_value) if typed_value is not None else ""
    except RenderContextError:
        if isinstance(typed_value, dict):
            card_val = str(typed_value.get("display_text") or typed_value.get("value") or "")
        else:
            card_val = str(typed_value or "")

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
        "value": card_val,
        "typed_value": typed_value,
        "price": getattr(selection, "price", None) or getattr(offering, "optional_price", None),
        "optional_price": getattr(offering, "optional_price", None),
        "asset_id": asset_id or concept.default_asset_id,
        "cost_status": getattr(selection, "cost_status", None),
        "sort_order": int(getattr(offering, "sort_order", 0) or 0),
        "is_detected": bool(
            (getattr(selection, "evidence_snapshot", None) or {}).get("is_detected")
            or (getattr(selection, "evidence_snapshot", None) or {}).get("source") in {"extracted_addon", "gemini_multimodal", "extracted_upgrade"}
        ),
        "group_id": getattr(selection, "package_plan_id", None),
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
    plans: list[Any] | None = None,
) -> dict[str, list[dict]]:
    """Resolve current and available cards solely from pinned rows and decisions."""

    offerings_by_id = _index(offerings)
    concepts_by_id = _index(concepts)
    facets_by_id = _index(facets)
    removed_offering_ids = {
        str(item.catalog_offering_id)
        for item in selections
        if item.catalog_offering_id and item.state == "removed"
    }
    removed_concepts = {
        str(item.concept_id)
        for item in selections
        if item.concept_id and item.state == "removed"
    }
    selected_offering_ids = {
        str(item.catalog_offering_id)
        for item in selections
        if item.catalog_offering_id and item.state in {"current", "superseded", "removed"}
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
                "optional_price": item.price,
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
            if not target or target.status not in {"active", "compatibility"} or target.id in selected_offering_ids or target.id in offered_ids or target.id in removed_offering_ids or str(target.concept_id) in removed_concepts:
                continue
            concept = concepts_by_id.get(str(target.concept_id))
            if not concept:
                raise RenderContextError("An upgrade relation references a missing concept.")
            available_cards.append(_card(
                selection=None, offering=target, concept=concept, typed_value=target.typed_value,
                branch_key=edge.branch_key,
            ))
            offered_ids.add(target.id)

        # Also support same-concept upgrade options without requiring an explicit edge
        if item.concept_id:
            same_concept_upgrades = [
                off for off in offerings
                if str(off.concept_id) == str(item.concept_id)
                and off.id != item.catalog_offering_id
                and off.id not in selected_offering_ids
                and off.id not in offered_ids
                and off.id not in removed_offering_ids
                and str(off.concept_id) not in removed_concepts
                and off.status in {"active", "compatibility"}
                and (off.offering_kind in {"upgrade", "optional"} or getattr(off, "role", None) in {"addon_option", "bundle_component"})
            ]
            for off in sorted(same_concept_upgrades, key=lambda row: (int(row.sort_order or 0), str(row.offering_key))):
                concept = concepts_by_id.get(str(off.concept_id))
                if concept:
                    available_cards.append(_card(
                        selection=None, offering=off, concept=concept, typed_value=off.typed_value,
                        branch_key=getattr(off, "branch_key", None),
                    ))
                    offered_ids.add(off.id)

    active_concepts = {str(item.concept_id) for item in current if item.concept_id}
    optionals_by_concept: dict[str, list[Any]] = {}
    for item in offerings:
        is_optional = (
            item.offering_kind == "optional"
            or getattr(item, "role", None) in {"addon_option", "bundle_component"}
        )
        if is_optional and item.status in {"active", "compatibility"}:
            optionals_by_concept.setdefault(str(item.concept_id), []).append(item)
    for concept_id, items in optionals_by_concept.items():
        if concept_id in active_concepts or concept_id in removed_concepts or any(str(item.id) in offered_ids for item in items):
            continue
        first = min(items, key=lambda item: (int(item.sort_order or 0), str(item.offering_key)))
        concept = concepts_by_id.get(concept_id)
        if concept and str(first.id) not in selected_offering_ids and str(first.id) not in offered_ids and str(first.id) not in removed_offering_ids:
            available_cards.append(_card(selection=None, offering=first, concept=concept, typed_value=first.typed_value))
            offered_ids.add(first.id)

    available_selected = [item for item in selections if item.state == "available_addon"]
    for item in sorted(available_selected, key=lambda row: (int(row.sort_order or 0), str(row.selection_key))):
        if item.concept_id and (str(item.concept_id) in active_concepts or str(item.concept_id) in removed_concepts):
            continue
        if item.item_kind == "custom":
            concept = concepts_by_id.get(str(item.concept_id))
            concept = concept or type("CustomConcept", (), {
                "id": item.concept_id or f"custom:{item.id}", "concept_key": item.selection_key,
                "label": item.label_override or "Custom benefit", "default_asset_id": None,
            })()
            pseudo = type("CustomOffering", (), {
                "id": f"custom:{item.id}", "label_override": item.label_override,
                "typed_value": item.typed_value_override, "sort_order": item.sort_order,
                "optional_price": item.price,
                "presentation_facet_ids": [],
            })()
            available_cards.append(_card(selection=item, offering=pseudo, concept=concept, typed_value=item.typed_value_override))
            continue
        offering = offerings_by_id.get(str(item.catalog_offering_id))
        if not offering or offering.id in offered_ids:
            continue
        concept = concepts_by_id.get(str(offering.concept_id))
        if concept:
            available_cards.append(_card(selection=item, offering=offering, concept=concept, typed_value=item.typed_value_override or offering.typed_value))
            offered_ids.add(offering.id)

    order = lambda card: (card["sort_order"], card["label"].casefold(), card["card_key"])
    current_sorted = sorted(current_cards, key=order)
    addons_sorted = sorted(available_cards, key=order)
    plan_rows = {str(item.id): item for item in (plans or [])}
    groups: list[dict] = []
    for card in current_sorted:
        group_id = card.get("group_id")
        if not group_id:
            continue
        group = next((item for item in groups if item["plan_id"] == group_id), None)
        if group is None:
            plan = plan_rows.get(group_id)
            group = {
                "plan_id": group_id,
                "plan_key": getattr(plan, "plan_key", "") or "",
                "plan_label": getattr(plan, "name", "") or "Package plan",
                "cards": [],
            }
            groups.append(group)
        group["cards"].append(card)
    groups.sort(key=lambda item: (int(getattr(plan_rows.get(item["plan_id"]), "sort_order", 0) or 0), item["plan_key"]))
    return {
        "current_benefits": current_sorted,
        "available_addons": addons_sorted,
        "groups": groups,
    }
