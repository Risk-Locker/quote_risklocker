"""Two-way Comparison <-> Quotation Workspace synchronization helpers.

Shared cleanly by both `patch_comparison_entry` (inline comparison card edits),
`save_comparison_entry` (modal edits), and Cover Note updates so scalar fields,
DraftBenefitSelections, and idempotent `applied_to_premium` deltas stay 1:1.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.domain.benefit_pricing import (
    parse_money_decimal,
    selection_applied_to_premium,
    stamp_applied_to_premium,
)
from app.models.tables import (
    BenefitConcept,
    CatalogOffering,
    DraftBenefitSelection,
    InsuranceTenure,
    QuotationDraft,
    Session as SessionModel,
    new_id,
)
from app.services.marketing_comparison.special_perils import is_special_perils_value_included


_CONCEPT_MATCHERS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "windscreen": (
        ("windscreen", "windscreen-protection", "windscreen-coverage"),
        ("windscreen", "w/screen", "cermin"),
    ),
    "special-perils": (
        ("special-perils", "special_perils", "flood"),
        ("special peril", "flood", "banjir", "peril khas", "convulsions"),
    ),
    "llp_llop": (
        ("legal-liability-to-passengers", "legal-liability-of-passengers", "llp", "llop"),
        ("legal liability to passenger", "legal liability of passenger", "llp", "llop", "lltp"),
    ),
    "towing": (
        ("towing", "emergency-towing", "towing-assistance"),
        ("emergency towing", "unlimited towing", "roadside assistance", "towing"),
    ),
    "betterment": (
        ("betterment", "waiver-of-betterment", "waiver-betterment", "betterment-protection"),
        ("betterment",),
    ),
    "ehailing": (
        ("ehailing", "e-hailing", "private-hire-car-e-hailing"),
        ("e-hailing", "ehailing", "e hailing", "private hire car"),
    ),
    "srcc": (
        ("strike-riot-civil-commotion", "srcc"),
        ("strike, riot", "strike riot", "civil commotion", "srcc"),
    ),
    "child_seat": (
        ("child-car-seat", "child-seat", "child-safety-seat"),
        ("child car seat", "child safety seat"),
    ),
    "respray": (
        ("repaint-spray-paint", "full-respray", "spray-paint", "respray"),
        ("full respray", "respray", "spray paint", "repaint"),
    ),
    "ev_battery": (
        ("ev-battery-depletion-towing", "ev-battery", "battery-coverage"),
        ("ev battery", "battery depletion", "out of charge"),
    ),
    "ev_other": (
        ("ev-home-wall-charger", "ev-wall-charger", "ev-charger-liability"),
        ("wall charger", "ev wall charger", "charger liability"),
    ),
}


def _selection_matches_domain(
    sel: DraftBenefitSelection,
    concepts_by_id: dict[str, BenefitConcept],
    domain_key: str,
) -> bool:
    c_keys, keywords = _CONCEPT_MATCHERS[domain_key]
    concept = concepts_by_id.get(sel.concept_id) if sel.concept_id else None
    if concept and (concept.concept_key or "").strip().lower() in c_keys:
        return True
    s_key = (sel.selection_key or "").strip().lower()
    if any(ck in s_key for ck in c_keys):
        return True
    lbl = (sel.label_override or (concept.label if concept else "") or "").strip().lower()
    return any(kw in lbl for kw in keywords)


def _find_concept_and_offering(
    db: Session,
    draft: QuotationDraft,
    candidate_keys: tuple[str, ...],
) -> tuple[BenefitConcept | None, CatalogOffering | None]:
    concepts = list(
        db.scalars(
            select(BenefitConcept).where(BenefitConcept.concept_key.in_(list(candidate_keys)))
        ).all()
    )
    concept = next(
        (c for ck in candidate_keys for c in concepts if (c.concept_key or "").lower() == ck),
        concepts[0] if concepts else None,
    )
    offering = None
    if concept and draft.catalog_revision_id:
        offering = db.scalar(
            select(CatalogOffering).where(
                CatalogOffering.catalog_revision_id == draft.catalog_revision_id,
                CatalogOffering.concept_id == concept.id,
            )
        )
    return concept, offering


def _deactivate_domain_selections(
    selections: list[DraftBenefitSelection],
    concepts_by_id: dict[str, BenefitConcept],
    domain_key: str,
    user_id: str | None,
) -> Decimal:
    """Deactivate active selections for a domain and return any applied RM amount removed."""
    removed_applied = Decimal("0.00")
    for sel in selections:
        if sel.state != "current":
            continue
        if not _selection_matches_domain(sel, concepts_by_id, domain_key):
            continue
        applied = selection_applied_to_premium(sel)
        if applied > Decimal("0.00"):
            removed_applied += applied
        sel.state = "available_addon" if sel.item_kind == "catalog" else "removed"
        sel.superseded_by_id = None
        if user_id:
            sel.selected_by = user_id
        stamp_applied_to_premium(sel, Decimal("0.00"))
    return removed_applied


def _activate_domain_selection(
    db: Session,
    draft: QuotationDraft,
    selections: list[DraftBenefitSelection],
    concepts_by_id: dict[str, BenefitConcept],
    domain_key: str,
    candidate_keys: tuple[str, ...],
    default_label: str,
    typed_value: dict[str, Any] | None,
    user_id: str | None,
) -> None:
    """Ensure exactly one current DraftBenefitSelection exists for this domain."""
    matching = [s for s in selections if _selection_matches_domain(s, concepts_by_id, domain_key)]
    target = next((s for s in matching if s.state == "current"), None) or (matching[0] if matching else None)

    if target is not None:
        # Resolve any other active row on same concept to keep unique index safe
        if target.concept_id:
            for other in selections:
                if other.id != target.id and other.concept_id == target.concept_id and other.state == "current":
                    other.state = "superseded"
                    other.superseded_by_id = target.id
                    stamp_applied_to_premium(other, Decimal("0.00"))
        target.state = "current"
        target.superseded_by_id = None
        if target.item_kind == "custom" and not target.label_override:
            target.label_override = default_label
        if domain_key == "towing" and typed_value is not None:
            new_disp = str(typed_value.get("display_text") or "").lower()
            cur_lbl_low = str(target.label_override or "").lower()
            if "unlimited" in cur_lbl_low and "unlimited" not in new_disp:
                target.label_override = default_label
        if typed_value is not None:
            curr_tv = dict(target.typed_value_override or {})
            desc = curr_tv.get("description")
            next_tv = dict(typed_value)
            if desc and "description" not in next_tv:
                next_tv["description"] = desc
            target.typed_value_override = next_tv
        if selection_applied_to_premium(target) == Decimal("0.00"):
            target.cost_status = target.cost_status if target.cost_status in {"included", "foc"} else "included"
            stamp_applied_to_premium(target, Decimal("0.00"))
        if user_id:
            target.selected_by = user_id
        return

    concept, offering = _find_concept_and_offering(db, draft, candidate_keys)
    resolved_item_kind = "catalog" if offering else "custom"
    target_key = (f"catalog:{offering.offering_key}" if offering else f"comparison:{domain_key}")[:160]
    resolved_label = (
        (offering.label_override if offering and offering.label_override else None)
        or (default_label if resolved_item_kind == "custom" else None)
    )

    # Reuse any existing DraftBenefitSelection matching target_key or offering to satisfy uq_draft_benefit_selection_key
    existing_by_key = next((s for s in selections if (s.selection_key or "") == target_key), None)
    if existing_by_key is None and offering is not None:
        existing_by_key = next((s for s in selections if s.catalog_offering_id == offering.id), None)
    if existing_by_key is not None:
        if existing_by_key.concept_id:
            for other in selections:
                if other.id != existing_by_key.id and other.concept_id == existing_by_key.concept_id and other.state == "current":
                    other.state = "superseded"
                    other.superseded_by_id = existing_by_key.id
                    stamp_applied_to_premium(other, Decimal("0.00"))
        existing_by_key.state = "current"
        existing_by_key.superseded_by_id = None
        existing_by_key.cost_status = "included"
        if existing_by_key.item_kind == "custom" and not existing_by_key.label_override:
            existing_by_key.label_override = resolved_label or default_label
        if domain_key == "towing" and typed_value is not None:
            new_disp = str(typed_value.get("display_text") or "").lower()
            cur_lbl_low = str(existing_by_key.label_override or "").lower()
            if "unlimited" in cur_lbl_low and "unlimited" not in new_disp:
                existing_by_key.label_override = resolved_label or default_label
        if typed_value is not None:
            curr_tv = dict(existing_by_key.typed_value_override or {})
            next_tv = dict(typed_value)
            if curr_tv.get("description") and "description" not in next_tv:
                next_tv["description"] = curr_tv["description"]
            existing_by_key.typed_value_override = next_tv
        stamp_applied_to_premium(existing_by_key, Decimal("0.00"))
        if user_id:
            existing_by_key.selected_by = user_id
        return

    # Supersede any current row on target.concept_id if present
    if concept:
        for other in selections:
            if other.concept_id == concept.id and other.state == "current":
                other.state = "superseded"
                stamp_applied_to_premium(other, Decimal("0.00"))

    new_sel = DraftBenefitSelection(
        id=new_id(),
        draft_id=draft.id,
        selection_key=target_key,
        catalog_offering_id=offering.id if offering else None,
        concept_id=concept.id if concept else None,
        item_kind=resolved_item_kind,
        state="current",
        cost_status="included",
        label_override=resolved_label,
        typed_value_override=typed_value,
        evidence_snapshot={"source": "comparison_sync", "applied_to_premium": "0.00"},
        sort_order=int(offering.sort_order or 0) if offering else 60,
        selected_by=user_id,
    )
    db.add(new_sel)
    selections.append(new_sel)


def sync_session_draft_from_comparison(
    db: Session,
    tenure: InsuranceTenure | None,
    session_id: str | None,
    *,
    edited_fields: Sequence[str],
    field_values: dict[str, Any],
    explicit_motor_premium: bool = False,
    user_id: str | None = None,
) -> Decimal:
    """Sync scalar fields and DraftBenefitSelections from Comparison back into QuotationDraft.

    Returns any subtracted RM amount (negative Decimal) when removing a priced
    benefit on Comparison when `explicit_motor_premium` is False so callers can
    deduct that same RM cost from `entry.motor_premium` and `draft.fields.premium`.
    """
    if not session_id or not edited_fields:
        return Decimal("0.00")
    s_obj = db.get(SessionModel, session_id)
    if not s_obj or not s_obj.draft:
        return Decimal("0.00")

    draft = s_obj.draft
    d_fields = dict(draft.fields or {})
    d_decisions = dict(draft.scalar_decisions or {})
    now_iso = datetime.now(timezone.utc).isoformat()
    edited_set = set(edited_fields)

    def _set_manual_field(key: str, value: str) -> None:
        prev = d_fields.get(key) if isinstance(d_fields.get(key), dict) else {}
        d_fields[key] = {**prev, "value": value, "status": "manual_override"}

    def _set_decision(key: str, value: str) -> None:
        d_decisions[key] = {
            "decision": "edit",
            "value": value,
            "decided_by": user_id,
            "decided_at": now_iso,
        }

    # 1. Selection & Benefit Synchronization + applied_to_premium removal deltas
    removed_applied_total = Decimal("0.00")
    benefit_sync_keys = {
        "windscreen_sum_insured",
        "special_perils",
        "llp_llop",
        "towing_limit",
        "towing_km",
        "waiver_betterment",
        "extra_addons",
        "included_perils",
    }
    if edited_set.intersection(benefit_sync_keys):
        selections = list(
            db.scalars(select(DraftBenefitSelection).where(DraftBenefitSelection.draft_id == draft.id)).all()
        )
        concept_ids = {s.concept_id for s in selections if s.concept_id}
        concepts_by_id = (
            {c.id: c for c in db.scalars(select(BenefitConcept).where(BenefitConcept.id.in_(list(concept_ids)))).all()}
            if concept_ids
            else {}
        )

        if "windscreen_sum_insured" in edited_set:
            ws_dec = parse_money_decimal(field_values.get("windscreen_sum_insured")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if ws_dec > Decimal("0.00"):
                ws_str = f"{ws_dec:,.2f}"
                _activate_domain_selection(
                    db,
                    draft,
                    selections,
                    concepts_by_id,
                    "windscreen",
                    ("windscreen", "windscreen-protection"),
                    "Windscreen Coverage",
                    {"type": "money", "value": f"{ws_dec:.2f}", "currency": "MYR", "display_text": f"RM {ws_str}", "semantic_role": "limit"},
                    user_id,
                )
            else:
                removed_applied_total += _deactivate_domain_selections(selections, concepts_by_id, "windscreen", user_id)

        if "special_perils" in edited_set:
            sp_raw = field_values.get("special_perils")
            if is_special_perils_value_included(sp_raw):
                _activate_domain_selection(
                    db,
                    draft,
                    selections,
                    concepts_by_id,
                    "special-perils",
                    ("special-perils", "special_perils"),
                    "Special Perils",
                    {"type": "boolean", "value": True, "display_text": "Included"},
                    user_id,
                )
            else:
                removed_applied_total += _deactivate_domain_selections(selections, concepts_by_id, "special-perils", user_id)

        if "llp_llop" in edited_set:
            llp_raw = field_values.get("llp_llop")
            if is_special_perils_value_included(llp_raw):
                _activate_domain_selection(
                    db,
                    draft,
                    selections,
                    concepts_by_id,
                    "llp_llop",
                    ("legal-liability-to-passengers", "legal-liability-of-passengers"),
                    "Legal Liability to Passengers",
                    {"type": "boolean", "value": True, "display_text": str(llp_raw or "Included")},
                    user_id,
                )
            else:
                removed_applied_total += _deactivate_domain_selections(selections, concepts_by_id, "llp_llop", user_id)

        if "towing_limit" in edited_set or "towing_km" in edited_set:
            tow_raw = str(field_values.get("towing_limit") or field_values.get("towing_km") or "").strip()
            if tow_raw and tow_raw.lower() not in {"no towing", "not included", "none", "-"}:
                _activate_domain_selection(
                    db,
                    draft,
                    selections,
                    concepts_by_id,
                    "towing",
                    ("towing",),
                    "Emergency Towing Assistance",
                    {"type": "string", "display_text": tow_raw},
                    user_id,
                )
            else:
                removed_applied_total += _deactivate_domain_selections(selections, concepts_by_id, "towing", user_id)

        if "waiver_betterment" in edited_set:
            if bool(field_values.get("waiver_betterment")):
                _activate_domain_selection(
                    db,
                    draft,
                    selections,
                    concepts_by_id,
                    "betterment",
                    ("betterment", "waiver-of-betterment", "betterment-protection"),
                    "Waiver of Betterment",
                    None,
                    user_id,
                )
            else:
                removed_applied_total += _deactivate_domain_selections(selections, concepts_by_id, "betterment", user_id)

        if "extra_addons" in edited_set and isinstance(field_values.get("extra_addons"), dict):
            from app.services.marketing_comparison.dynamic_addons import (
                DYNAMIC_ADDON_BY_KEY,
                normalize_dynamic_addon_flag,
            )

            for addon_k, addon_v in field_values["extra_addons"].items():
                defn = DYNAMIC_ADDON_BY_KEY.get(str(addon_k or "").strip().lower())
                if not defn:
                    continue
                if normalize_dynamic_addon_flag(addon_v) == "Yes":
                    _activate_domain_selection(
                        db,
                        draft,
                        selections,
                        concepts_by_id,
                        defn["key"],
                        defn["concept_keys"],
                        defn["default_title"],
                        {"type": "boolean", "value": True, "display_text": "Included"},
                        user_id,
                    )
                else:
                    removed_applied_total += _deactivate_domain_selections(selections, concepts_by_id, defn["key"], user_id)

        if explicit_motor_premium:
            for sel in selections:
                if sel.state == "current" and any(_selection_matches_domain(sel, concepts_by_id, dk) for dk in _CONCEPT_MATCHERS):
                    stamp_applied_to_premium(sel)

    # 2. Scalar Field Sync
    if "company_name" in edited_set and field_values.get("company_name"):
        comp_val = str(field_values["company_name"]).strip()
        _set_manual_field("insurance_company", comp_val)
        _set_manual_field("insurer_name", comp_val)
        s_obj.detected_company = comp_val

    if "sum_insured" in edited_set and field_values.get("sum_insured") is not None:
        si_dec = parse_money_decimal(field_values.get("sum_insured")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        si_str = f"{si_dec:.2f}"
        _set_manual_field("sum_insured", si_str)
        _set_manual_field("coverage_amount", si_str)
        _set_decision("sum_insured", si_str)

    if "agreed_value" in edited_set or "valuation_type" in edited_set:
        vt_raw = field_values.get("valuation_type")
        if vt_raw is not None and str(vt_raw).strip() != "":
            is_agreed = str(vt_raw).strip().lower() in {"agreed value", "agreed_value"}
        else:
            is_agreed = bool(field_values.get("agreed_value"))
        vt_str = "Agreed Value" if is_agreed else "Market Value"
        _set_manual_field("valuation_type", vt_str)
        _set_decision("valuation_type", vt_str)

    if "towing_limit" in edited_set or "towing_km" in edited_set:
        tow_val = str(field_values.get("towing_limit") or field_values.get("towing_km") or "")
        _set_manual_field("towing", tow_val)
        _set_manual_field("towing_limit", tow_val)

    if "special_perils" in edited_set:
        sp_out = str(field_values.get("special_perils") or "Not Included")
        _set_manual_field("special_perils", sp_out)

    if "llp_llop" in edited_set:
        llp_out = str(field_values.get("llp_llop") or "Not Included")
        _set_manual_field("llp_llop", llp_out)

    if "waiver_betterment" in edited_set:
        _set_manual_field("waiver_of_betterment", "Included" if field_values.get("waiver_betterment") else "Not Included")

    if "betterment_rate" in edited_set:
        if field_values.get("betterment_rate") is not None:
            _set_manual_field("betterment_rate", str(field_values["betterment_rate"]))
        else:
            d_fields.pop("betterment_rate", None)

    if "extra_addons" in edited_set and isinstance(field_values.get("extra_addons"), dict):
        from app.services.marketing_comparison.dynamic_addons import sanitize_extra_addons_map

        prev_ea = d_fields.get("extra_addons")
        base_map = (
            dict(prev_ea.get("value"))
            if isinstance(prev_ea, dict) and isinstance(prev_ea.get("value"), dict)
            else (dict(prev_ea) if isinstance(prev_ea, dict) else {})
        )
        merged_ea = {**sanitize_extra_addons_map(base_map), **sanitize_extra_addons_map(field_values["extra_addons"])}
        d_fields["extra_addons"] = {"value": merged_ea, "status": "manual_override"}

    if "included_perils" in edited_set:
        raw_perils = field_values.get("included_perils")
        if isinstance(raw_perils, list):
            clean_list = list(dict.fromkeys(str(p).strip().upper() for p in raw_perils if str(p).strip()))
            d_fields["included_perils"] = {"value": clean_list, "status": "manual_override"}
        elif raw_perils is None:
            d_fields.pop("included_perils", None)

    if "vehicle_model" in edited_set and field_values.get("vehicle_model"):
        vm_val = str(field_values["vehicle_model"]).strip()
        _set_manual_field("car_model", vm_val)
        _set_manual_field("vehicle_model", vm_val)

    if "manufacture_year" in edited_set and field_values.get("manufacture_year"):
        yom_str = str(int(field_values["manufacture_year"]))
        _set_manual_field("vehicle_year", yom_str)
        _set_manual_field("manufacture_year", yom_str)

    if "excess" in edited_set and field_values.get("excess") is not None:
        ex_dec = parse_money_decimal(field_values.get("excess")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        ex_str = f"{ex_dec:.2f}"
        _set_manual_field("excess", ex_str)
        _set_manual_field("excess_amount", ex_str)
        _set_decision("excess_amount", ex_str)

    if "windscreen_sum_insured" in edited_set:
        ws_dec = parse_money_decimal(field_values.get("windscreen_sum_insured")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        ws_str = f"{ws_dec:.2f}" if ws_dec > Decimal("0.00") else ""
        _set_manual_field("windscreen_sum_insured", ws_str)
        _set_manual_field("windscreen", ws_str)

    # 3. Premium & Total Amount Sync
    prem_delta_out = Decimal("0.00")
    eff_rt = (
        parse_money_decimal(tenure.road_tax).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if (tenure and tenure.include_road_tax is not False)
        else Decimal("0.00")
    )
    eff_rf = (
        parse_money_decimal(tenure.runner_fee).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if (tenure and tenure.include_runner_fee is not False)
        else Decimal("0.00")
    )
    if explicit_motor_premium and field_values.get("motor_premium") is not None:
        from app.domain.motor.discount_calculator import calculate_motor_discount

        mp_dec = parse_money_decimal(field_values.get("motor_premium")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        pct_val = getattr(tenure, "motor_discount_pct", Decimal("0.00")) if tenure else Decimal("0.00")
        flat_val = getattr(tenure, "quotation_discount", Decimal("0.00")) if tenure else Decimal("0.00")
        disc_bd = calculate_motor_discount(mp_dec, pct_val, flat_val)
        _set_manual_field("motor_premium", f"{mp_dec:.2f}")
        _set_manual_field("premium", f"{mp_dec:.2f}")
        _set_manual_field("premium_due", f"{mp_dec:.2f}")
        _set_decision("premium", f"{mp_dec:.2f}")
        d_fields["motor_discount_pct"] = {"value": f"{disc_bd.motor_discount_pct:.2f}", "status": "ready"}
        d_fields["motor_discount_amount"] = {"value": f"{disc_bd.pct_discount_amount:.2f}", "status": "ready"}
        d_fields["quotation_discount"] = {"value": f"{disc_bd.flat_discount_amount:.2f}", "status": "ready"}
        tot_dec = disc_bd.net_total_payable(eff_rt, eff_rf)
        d_fields["include_road_tax"] = {"value": bool(tenure.include_road_tax is not False) if tenure else True, "status": "ready"}
        d_fields["include_runner_fee"] = {"value": bool(tenure.include_runner_fee is not False) if tenure else True, "status": "ready"}
        d_fields["roadtax"] = {"value": f"{eff_rt:.2f}", "status": "ready"}
        d_fields["service_fee"] = {"value": f"{eff_rf:.2f}", "status": "ready"}
        d_fields["total_amount"] = {"value": f"{tot_dec:.2f}", "status": "ready"}
        d_decisions["total_amount"] = {"decision": "confirm", "decided_by": user_id, "decided_at": now_iso}
    elif removed_applied_total > Decimal("0.00"):
        from app.domain.motor.discount_calculator import calculate_motor_discount

        cur_prem = parse_money_decimal(d_fields.get("premium"))
        new_prem = max(Decimal("0.00"), (cur_prem - removed_applied_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        prem_delta_out = -removed_applied_total
        pct_val = getattr(tenure, "motor_discount_pct", Decimal("0.00")) if tenure else Decimal("0.00")
        flat_val = getattr(tenure, "quotation_discount", Decimal("0.00")) if tenure else Decimal("0.00")
        disc_bd = calculate_motor_discount(new_prem, pct_val, flat_val)
        _set_manual_field("motor_premium", f"{new_prem:.2f}")
        _set_manual_field("premium", f"{new_prem:.2f}")
        _set_manual_field("premium_due", f"{new_prem:.2f}")
        _set_decision("premium", f"{new_prem:.2f}")
        d_fields["motor_discount_pct"] = {"value": f"{disc_bd.motor_discount_pct:.2f}", "status": "ready"}
        d_fields["motor_discount_amount"] = {"value": f"{disc_bd.pct_discount_amount:.2f}", "status": "ready"}
        d_fields["quotation_discount"] = {"value": f"{disc_bd.flat_discount_amount:.2f}", "status": "ready"}
        tot_dec = disc_bd.net_total_payable(eff_rt, eff_rf)
        d_fields["include_road_tax"] = {"value": bool(tenure.include_road_tax is not False) if tenure else True, "status": "ready"}
        d_fields["include_runner_fee"] = {"value": bool(tenure.include_runner_fee is not False) if tenure else True, "status": "ready"}
        d_fields["roadtax"] = {"value": f"{eff_rt:.2f}", "status": "ready"}
        d_fields["service_fee"] = {"value": f"{eff_rf:.2f}", "status": "ready"}
        d_fields["total_amount"] = {"value": f"{tot_dec:.2f}", "status": "ready"}
        d_decisions["total_amount"] = {"decision": "confirm", "decided_by": user_id, "decided_at": now_iso}

    draft.fields = d_fields
    draft.scalar_decisions = d_decisions
    draft.revision = (draft.revision or 1) + 1
    draft.reviewed_at = datetime.now(timezone.utc)
    if user_id:
        draft.reviewed_by = user_id
    flag_modified(draft, "fields")
    flag_modified(draft, "scalar_decisions")
    return prem_delta_out
