"""Unified Quote Domain Engine (Single Canonical Truth across Comparison & Workspace).

Pure-Decimal domain primitives shared by Comparison Matrix, Quotation Workspace,
and Extraction/Rescan so both views share 1 canonical `company_id`, 1 canonical
Underwriter Motor Premium, and true two-way Insurer Bundle <-> Towing / Betterment
/ Perils parity.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Any, Callable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.domain.benefit_pricing import (
    parse_money_decimal,
    selection_applied_to_premium,
    stamp_applied_to_premium,
)
from app.domain.motor.discount_calculator import to_decimal_clean
from app.models.tables import (
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    CatalogOffering,
    DraftBenefitSelection,
    InsuranceCompany,
    InsuranceTenure,
    QuotationDraft,
    TenureComparisonEntry,
    new_id,
)

_ZERO = Decimal("0.00")
_CENT = Decimal("0.01")
_RATE_QUANT = Decimal("0.0001")
_HUNDRED = Decimal("100")

_NO_TOWING_VALUES = frozenset(
    {"", "0", "0.0", "0 km", "rm 0", "no towing", "without towing", "not included", "none", "tiada", "nil", "-"}
)


def _q2(value: Any) -> Decimal:
    return to_decimal_clean(value, _ZERO).quantize(_CENT, rounding=ROUND_HALF_UP)


def _extract_field_raw(fields: dict[str, Any] | None, key: str) -> Any:
    if not isinstance(fields, dict):
        return None
    raw = fields.get(key)
    return raw.get("value") if isinstance(raw, dict) else raw


def resolve_session_company_id(session: Any, entry: Any = None) -> str | None:
    """Resolve canonical InsuranceCompany ID safely across Session, Draft, UploadedFile, and Entry.

    `sessions` table has no `company_id` column, so `draft.company_id` and
    `uploaded_file.insurance_company_id` are the authoritative DB columns.
    """
    if session is not None:
        draft = getattr(session, "draft", None)
        d_cid = getattr(draft, "company_id", None) if draft is not None else None
        if d_cid:
            return str(d_cid)
        uf = getattr(session, "uploaded_file", None)
        uf_cid = getattr(uf, "insurance_company_id", None) if uf is not None else None
        if uf_cid:
            return str(uf_cid)
        legacy_cid = getattr(session, "company_id", None)
        if legacy_cid:
            return str(legacy_cid)
    if entry is not None:
        e_cid = getattr(entry, "company_id", None)
        if e_cid:
            return str(e_cid)
    return None


def resolve_canonical_motor_premium_decimal(fields: dict[str, Any] | None) -> Decimal:
    """Extract Underwriter Gross Motor Premium Payable (incl. SST + stamp, pre-discount) in Decimal."""
    if not isinstance(fields, dict):
        return _ZERO

    prem_node = fields.get("premium")
    if isinstance(prem_node, dict) and prem_node.get("status") == "manual_override":
        manual_prem = _q2(prem_node)
        if manual_prem > _ZERO:
            return manual_prem

    for key in ("motor_premium", "premium", "premium_due", "total_payable"):
        val = _q2(fields.get(key))
        if val > _ZERO:
            return val
    return _ZERO


def sync_draft_motor_premium_aliases(fields: dict[str, Any], uw_motor_dec: Decimal | None = None) -> bool:
    """Keep `motor_premium`, `total_payable`, and `premium_due` aligned with `premium`."""
    if not isinstance(fields, dict):
        return False
    target_dec = uw_motor_dec if uw_motor_dec is not None else _q2(fields.get("premium"))
    if target_dec <= _ZERO:
        return False
    target_str = f"{target_dec:.2f}"
    changed = False
    prem_node = fields.get("premium")
    prem_status = prem_node.get("status") if isinstance(prem_node, dict) else "ready"
    for alias in ("premium", "motor_premium", "total_payable", "premium_due"):
        cur = fields.get(alias)
        cur_val = cur.get("value") if isinstance(cur, dict) else cur
        if str(cur_val or "") != target_str or not isinstance(cur, dict):
            prev = dict(cur) if isinstance(cur, dict) else {}
            fields[alias] = {**prev, "value": target_str, "status": prem_status or "ready"}
            changed = True
    return changed


def selection_is_betterment(sel: Any, concepts_by_id: dict[str, BenefitConcept]) -> bool:
    """True when a DraftBenefitSelection represents Waiver of Betterment via key, label, or Concept."""
    concept = concepts_by_id.get(getattr(sel, "concept_id", None)) if getattr(sel, "concept_id", None) else None
    blob = " ".join(
        [
            str(getattr(sel, "selection_key", None) or ""),
            str(getattr(sel, "label_override", None) or ""),
            str(getattr(concept, "concept_key", None) or ""),
            str(getattr(concept, "label", None) or ""),
        ]
    ).lower()
    return "betterment" in blob


def _bundle_towing_effect_value(tier: Any, concepts_by_id: dict[str, Any]) -> str | None:
    for eff in sorted(getattr(tier, "effects", []) or [], key=lambda x: int(getattr(x, "sort_order", 0) or 0)):
        eff_type = str(getattr(eff, "effect_type", "") or "")
        if eff_type not in ("upgrade_to_box2", "add_to_box2"):
            continue
        tc = str(getattr(eff, "target_concept_id", "") or "")
        concept = concepts_by_id.get(tc)
        ck = str(getattr(concept, "concept_key", "") or "").lower()
        title = str(getattr(eff, "display_title", "") or "").lower()
        if ck == "towing" or "towing" in title:
            cv = str(getattr(eff, "comparison_value", "") or "").strip()
            if cv:
                return cv
            if "unlimited" in title:
                return "Unlimited"
            m = re.search(r"((?:rm\s*)?[\d,]+\s*(?:km)?)", title, re.IGNORECASE)
            if m:
                return m.group(1).strip()
    return None


def _tier_matches_target_towing(eff_val: str | None, target_clean: str) -> bool:
    if not eff_val:
        return False
    ev = eff_val.lower().strip()
    tg = target_clean.lower().strip()
    if "unlimited" in tg:
        return "unlimited" in ev
    m_tg = re.search(r"\b(\d+)\b", tg)
    m_ev = re.search(r"\b(\d+)\b", ev)
    if not m_tg or not m_ev:
        return False
    if m_tg.group(1) != m_ev.group(1):
        return False
    tg_is_rm = "rm" in tg or "myr" in tg
    ev_is_rm = "rm" in ev or "myr" in ev
    return tg_is_rm == ev_is_rm


def _deactivate_selection_row(
    sel: DraftBenefitSelection,
    user_id: str | None,
    *,
    by_comparison_sync: bool = False,
) -> Decimal:
    applied = selection_applied_to_premium(sel)
    sel.state = "available_addon" if sel.item_kind == "catalog" else "removed"
    sel.superseded_by_id = None
    sel.bundle_tier_id = None
    ev = dict(sel.evidence_snapshot or {}) if isinstance(sel.evidence_snapshot, dict) else {}
    for k in ("bundle_id", "plan_tier", "plan_tier_key", "plan_tier_uncertain", "needs_review_reason"):
        ev.pop(k, None)
    if by_comparison_sync:
        ev["deactivated_by_comparison_sync"] = True
    sel.evidence_snapshot = ev
    if user_id:
        sel.selected_by = user_id
    stamp_applied_to_premium(sel, _ZERO)
    return applied if applied > _ZERO else _ZERO


def _activate_bundle_selection(
    db: Session,
    draft: QuotationDraft,
    selections: list[DraftBenefitSelection],
    concepts_by_id: dict[str, BenefitConcept],
    bundle: Any,
    tier: Any,
    user_id: str | None,
) -> None:
    from app.services.bundle_plan_matcher import match_bundle_for_selection

    matching = [
        s
        for s in selections
        if match_bundle_for_selection(s, None, concepts_by_id.get(s.concept_id) if s.concept_id else None, [bundle])
        is not None
    ]
    target = next((s for s in matching if s.state == "current"), None) or (matching[0] if matching else None)
    tier_label = str(getattr(tier, "label", "") or "").strip()
    tier_disp_title = str(getattr(tier, "display_title", "") or "").strip()
    tier_display = (
        tier_disp_title
        if tier_disp_title
        else (
            f"{bundle.name} ({tier_label})"
            if getattr(bundle, "has_plan_tiers", False) and tier_label and tier_label.lower() != "default"
            else str(bundle.name)
        )
    )
    ev_patch = {
        "source": "comparison_sync",
        "plan_tier_key": getattr(tier, "tier_key", None),
        "plan_tier": tier_label or None,
        "plan_tier_uncertain": False,
    }

    if target is not None:
        if target.concept_id:
            for other in selections:
                if other.id != target.id and other.concept_id == target.concept_id and other.state == "current":
                    other.state = "superseded"
                    other.superseded_by_id = target.id
                    stamp_applied_to_premium(other, _ZERO)
        target.state = "current"
        target.superseded_by_id = None
        target.bundle_tier_id = getattr(tier, "id", None)
        if target.item_kind == "custom":
            target.label_override = tier_display
        elif tier_label:
            target.label_override = None
        prev_ev = dict(target.evidence_snapshot or {})
        prev_ev.pop("deactivated_by_comparison_sync", None)
        target.evidence_snapshot = {**prev_ev, **ev_patch}
        if selection_applied_to_premium(target) == _ZERO:
            target.cost_status = "paid" if getattr(bundle, "force_box2", True) else (target.cost_status if target.cost_status in {"included", "foc"} else "included")
            stamp_applied_to_premium(target, _ZERO)
        elif getattr(bundle, "force_box2", True):
            target.cost_status = "paid"
        if user_id:
            target.selected_by = user_id
        return

    primary_cid = str(getattr(bundle, "primary_concept_id", "") or "") or None
    concept = concepts_by_id.get(primary_cid) if primary_cid else None
    if concept is None and primary_cid:
        concept = db.get(BenefitConcept, primary_cid)
        if concept is not None:
            concepts_by_id[concept.id] = concept

    offering = None
    if primary_cid and draft.catalog_revision_id:
        offering = db.scalar(
            select(CatalogOffering).where(
                CatalogOffering.catalog_revision_id == draft.catalog_revision_id,
                CatalogOffering.concept_id == primary_cid,
            )
        )

    item_kind = "catalog" if offering is not None else "custom"
    target_key = (f"catalog:{offering.offering_key}" if offering is not None else f"comparison:{bundle.bundle_key}")[:160]
    existing_by_key = next((s for s in selections if (s.selection_key or "") == target_key), None)
    if existing_by_key is None and offering is not None:
        existing_by_key = next((s for s in selections if s.catalog_offering_id == offering.id), None)

    if existing_by_key is not None:
        if existing_by_key.concept_id:
            for other in selections:
                if other.id != existing_by_key.id and other.concept_id == existing_by_key.concept_id and other.state == "current":
                    other.state = "superseded"
                    other.superseded_by_id = existing_by_key.id
                    stamp_applied_to_premium(other, _ZERO)
        existing_by_key.state = "current"
        existing_by_key.superseded_by_id = None
        existing_by_key.bundle_tier_id = getattr(tier, "id", None)
        if existing_by_key.item_kind == "custom":
            existing_by_key.label_override = tier_display
        elif tier_label:
            existing_by_key.label_override = None
        prev_ev_k = dict(existing_by_key.evidence_snapshot or {})
        prev_ev_k.pop("deactivated_by_comparison_sync", None)
        existing_by_key.evidence_snapshot = {**prev_ev_k, **ev_patch}
        existing_by_key.cost_status = "paid" if getattr(bundle, "force_box2", True) else "included"
        stamp_applied_to_premium(existing_by_key, _ZERO)
        if user_id:
            existing_by_key.selected_by = user_id
        return

    if primary_cid:
        for other in selections:
            if other.concept_id == primary_cid and other.state == "current":
                other.state = "superseded"
                stamp_applied_to_premium(other, _ZERO)

    new_sel = DraftBenefitSelection(
        id=new_id(),
        draft_id=draft.id,
        selection_key=target_key,
        catalog_offering_id=offering.id if offering is not None else None,
        concept_id=primary_cid,
        item_kind=item_kind,
        state="current",
        cost_status="paid" if getattr(bundle, "force_box2", True) else "included",
        label_override=tier_display if item_kind == "custom" else None,
        typed_value_override=None,
        evidence_snapshot={**ev_patch, "applied_to_premium": "0.00"},
        sort_order=int(offering.sort_order or 0) if offering is not None else 55,
        selected_by=user_id,
        bundle_tier_id=getattr(tier, "id", None),
    )
    db.add(new_sel)
    selections.append(new_sel)


def sync_towing_and_insurer_bundle_to_draft(
    db: Session,
    session: Any,
    draft: QuotationDraft,
    selections: list[DraftBenefitSelection],
    concepts_by_id: dict[str, BenefitConcept],
    target_towing: str,
    user_id: str | None,
    *,
    activate_domain_fn: Callable[..., None],
    deactivate_domain_fn: Callable[..., Decimal],
) -> Decimal:
    """Synchronize Comparison towing selection <-> Workspace Box 2 Insurer Bundles."""
    from app.services.bundle_plan_matcher import bundle_matches_catalog, match_bundle_for_selection
    from app.services.company_benefit_bundle_service import load_active_company_bundles

    tow_clean = str(target_towing or "").strip()
    tow_low = tow_clean.lower()
    comp_id = resolve_session_company_id(session)
    comp_bundles = load_active_company_bundles(db, comp_id) if comp_id else []

    cat_name = ""
    if getattr(draft, "catalog_revision_id", None):
        cat_row = db.execute(
            select(BenefitCatalog.name)
            .join(BenefitCatalogRevision, BenefitCatalogRevision.catalog_id == BenefitCatalog.id)
            .where(BenefitCatalogRevision.id == draft.catalog_revision_id)
        ).scalar_one_or_none()
        if cat_row:
            cat_name = str(cat_row)

    # Identify every bundle that confers a towing effect
    eff_cids: set[str] = set()
    for b in comp_bundles:
        for t in getattr(b, "tiers", []) or []:
            for eff in getattr(t, "effects", []) or []:
                tc = str(getattr(eff, "target_concept_id", "") or "")
                if tc and tc not in concepts_by_id:
                    eff_cids.add(tc)
    if eff_cids:
        for c in db.scalars(select(BenefitConcept).where(BenefitConcept.id.in_(list(eff_cids)))).all():
            concepts_by_id[c.id] = c

    towing_bundle_ids = {
        b.id
        for b in comp_bundles
        if any(_bundle_towing_effect_value(t, concepts_by_id) for t in (getattr(b, "tiers", []) or []))
    }

    removed_applied = _ZERO

    if tow_low in _NO_TOWING_VALUES:
        removed_applied += deactivate_domain_fn(selections, concepts_by_id, "towing", user_id)
        for sel in selections:
            if sel.state != "current":
                continue
            mb = match_bundle_for_selection(
                sel,
                None,
                concepts_by_id.get(sel.concept_id) if sel.concept_id else None,
                comp_bundles,
                catalog_name=cat_name,
            )
            if mb is not None and mb.id in towing_bundle_ids:
                removed_applied += _deactivate_selection_row(sel, user_id, by_comparison_sync=True)
        return removed_applied

    # Find matching (bundle, tier) for the target towing value (e.g. "Unlimited" or "300 km")
    matched_bundle = None
    matched_tier = None
    for b in comp_bundles:
        if not bundle_matches_catalog(b, cat_name) or b.id not in towing_bundle_ids:
            continue
        tiers = sorted(
            list(getattr(b, "tiers", []) or []),
            key=lambda t: (-int(getattr(t, "sort_order", 0) or 0), str(getattr(t, "tier_key", "") or "")),
        )
        for t in tiers:
            if _tier_matches_target_towing(_bundle_towing_effect_value(t, concepts_by_id), tow_clean):
                matched_bundle = b
                matched_tier = t
                break
        if matched_bundle is not None:
            break

    # Deactivate any OTHER active towing bundle when switching bundle/downgrading to base towing
    for sel in selections:
        if sel.state != "current":
            continue
        mb = match_bundle_for_selection(
            sel,
            None,
            concepts_by_id.get(sel.concept_id) if sel.concept_id else None,
            comp_bundles,
            catalog_name=cat_name,
        )
        if mb is not None and mb.id in towing_bundle_ids:
            if matched_bundle is None or mb.id != matched_bundle.id:
                removed_applied += _deactivate_selection_row(sel, user_id, by_comparison_sync=True)

    if matched_bundle is not None and matched_tier is not None:
        _activate_bundle_selection(db, draft, selections, concepts_by_id, matched_bundle, matched_tier, user_id)

    activate_domain_fn(
        db,
        draft,
        selections,
        concepts_by_id,
        "towing",
        ("towing",),
        "Emergency Towing Assistance",
        {"type": "string", "display_text": tow_clean},
        user_id,
    )
    if matched_bundle is not None and matched_tier is not None:
        from app.services.marketing_comparison.workspace_sync import _selection_matches_domain

        for sel in selections:
            if sel.state == "current" and _selection_matches_domain(sel, concepts_by_id, "towing"):
                ev_t = dict(sel.evidence_snapshot or {}) if isinstance(sel.evidence_snapshot, dict) else {}
                if ev_t.pop("manually_edited", None) is not None or ev_t.get("source") == "manual":
                    if ev_t.get("source") == "manual":
                        ev_t["source"] = "comparison_sync"
                    sel.evidence_snapshot = ev_t
                if sel.item_kind == "catalog":
                    sel.label_override = None
                sel.typed_value_override = None
    return removed_applied


def sync_comparison_from_workspace(
    db: Session,
    *,
    session: Any,
    tenure: InsuranceTenure,
    draft: QuotationDraft,
    selections: list[DraftBenefitSelection],
    changed_paths: Sequence[str],
    operation_names: Sequence[str],
    benefit_mutation_ops: set[str] | frozenset[str],
    eff_rt: Decimal,
    eff_rf: Decimal,
) -> None:
    """Push Workspace Box 1/Box 2 edits atomically into all TenureComparisonEntry rows for `tenure`."""
    from app.services.marketing_comparison.benefits_extractor import _resolve_comparison_benefits
    from app.services.marketing_comparison.materialize import record_manual_overrides
    from app.services.marketing_comparison.ncd_evaluator import evaluate_betterment_rules
    from app.services.marketing_comparison_service import rank_comparison_entries

    f = dict(draft.fields or {})
    has_benefit_mutation = any(op in benefit_mutation_ops for op in operation_names)

    # Keep motor_premium / total_payable / premium_due aliases synced with fields["premium"]
    if has_benefit_mutation or any("fields.premium" in p for p in changed_paths):
        if sync_draft_motor_premium_aliases(f):
            draft.fields = f
            flag_modified(draft, "fields")

    # Clear stale scalar manual_override on benefits when user mutates Box 2 bundles/benefits
    towing_explicitly_edited = any("fields.towing" in p for p in changed_paths)
    if has_benefit_mutation:
        stale_keys: list[str] = []
        if not towing_explicitly_edited:
            stale_keys.extend(["towing", "towing_limit"])
        if not any("fields.llp" in p for p in changed_paths):
            stale_keys.extend(["llp", "llop", "llp_llop"])
        if not any("fields.special_perils" in p for p in changed_paths):
            stale_keys.append("special_perils")
        stale_changed = False
        for sk in stale_keys:
            node = f.get(sk)
            if isinstance(node, dict) and node.get("status") == "manual_override":
                f.pop(sk, None)
                stale_changed = True
        if stale_changed:
            draft.fields = f
            flag_modified(draft, "fields")

    all_tenure_entries = list(
        db.scalars(select(TenureComparisonEntry).where(TenureComparisonEntry.tenure_id == tenure.id)).all()
    )
    if not all_tenure_entries:
        return

    cids = {s.concept_id for s in selections if getattr(s, "concept_id", None)}
    concepts_by_id = (
        {c.id: c for c in db.scalars(select(BenefitConcept).where(BenefitConcept.id.in_(list(cids)))).all()}
        if cids
        else {}
    )

    ws_tgt_dec = parse_money_decimal(tenure.windscreen_target) if tenure.windscreen_target else None
    ws_tgt_str = str(ws_tgt_dec) if ws_tgt_dec and ws_tgt_dec > _ZERO else None
    ws_tgt_arg = parse_money_decimal(ws_tgt_str) if ws_tgt_str else None

    for ce in all_tenure_entries:
        if ce.session_id == session.id:
            resolved_cid = resolve_session_company_id(session, ce)
            if resolved_cid and ce.company_id != resolved_cid:
                ce.company_id = resolved_cid

            mp_dec = resolve_canonical_motor_premium_decimal(f)
            if mp_dec > _ZERO:
                ce.motor_premium = mp_dec

            si_raw = _extract_field_raw(f, "sum_insured") or _extract_field_raw(f, "coverage_amount")
            si_dec = _q2(si_raw)
            if si_dec > _ZERO:
                ce.sum_insured = si_dec

            raw_vt = _extract_field_raw(f, "valuation_type")
            if raw_vt:
                is_agreed = str(raw_vt).strip().lower() in ("agreed value", "agreed_value")
                ce.valuation_type = "agreed_value" if is_agreed else "market_value"
                ce.agreed_value = is_agreed

            raw_ex = _extract_field_raw(f, "excess_amount")
            if raw_ex is None or str(raw_ex).strip() == "":
                raw_ex = _extract_field_raw(f, "excess")
            if raw_ex is not None and str(raw_ex).strip() != "":
                ce.excess = _q2(raw_ex)

            raw_tow = _extract_field_raw(f, "towing") or _extract_field_raw(f, "towing_limit")
            if raw_tow and str(raw_tow).strip() and towing_explicitly_edited:
                ce.towing_limit = str(raw_tow).strip()
                ce.towing_km = ce.towing_limit

            raw_ws = _extract_field_raw(f, "windscreen_sum_insured") or _extract_field_raw(f, "windscreen")
            if raw_ws is not None and str(raw_ws).strip() != "":
                ws_dec = _q2(raw_ws)
                ce.windscreen_sum_insured = ws_dec if ws_dec > _ZERO else None

            if has_benefit_mutation:
                b_sync = _resolve_comparison_benefits(
                    db,
                    session,
                    resolved_cid,
                    f,
                    ws_tgt_arg,
                )
                ws_sync = _q2(b_sync.get("windscreen_sum_insured"))
                ce.windscreen_sum_insured = ws_sync if ws_sync > _ZERO else None
                ce.special_perils = b_sync.get("special_perils")
                ce.llp = b_sync.get("llp")
                ce.llop = b_sync.get("llop")
                ce.llp_llop = b_sync.get("llp_llop")
                if b_sync.get("towing_km") and not towing_explicitly_edited:
                    ce.towing_limit = str(b_sync["towing_km"])
                    ce.towing_km = ce.towing_limit
                ce.extra_addons = dict(b_sync.get("extra_addons") or {})
                flag_modified(ce, "extra_addons")

                has_bet_active = any(s.state == "current" and selection_is_betterment(s, concepts_by_id) for s in selections)
                has_bet_inactive = any(s.state != "current" and selection_is_betterment(s, concepts_by_id) for s in selections)
                bet_exceeds_cap = False
                if has_bet_active or has_bet_inactive:
                    tv = getattr(tenure, "tracked_vehicle", None)
                    veh_yom = getattr(tv, "manufacture_year", None) if tv else None
                    reg_date = _extract_field_raw(f, "registration_date") or _extract_field_raw(f, "reg_date")
                    quote_year = tenure.coverage_start_date.year if tenure.coverage_start_date else datetime.now(timezone.utc).year
                    comp_obj = db.get(InsuranceCompany, ce.company_id) if ce.company_id else None
                    from app.domain.betterment_engine import resolve_vehicle_age_years
                    from app.services.marketing_comparison.company_rules import resolve_company_betterment_policy

                    eff_age = resolve_vehicle_age_years(
                        registration_date=reg_date,
                        yom=veh_yom,
                        inception_date=tenure.coverage_start_date,
                        quote_year=quote_year,
                    )
                    bet_pol = resolve_company_betterment_policy(
                        company_name=getattr(comp_obj, "name", None) if comp_obj else ce.company_name,
                        company_obj=comp_obj,
                    )
                    max_waive_y = int(bet_pol.get("max_waiver_years", 10))
                    bet_exceeds_cap = bool(eff_age is not None and max_waive_y > 0 and eff_age > max_waive_y)
                    _, b_rate, b_disp = evaluate_betterment_rules(
                        yom=veh_yom,
                        quote_year=quote_year,
                        company_name=getattr(comp_obj, "name", None) if comp_obj else ce.company_name,
                        has_betterment_peril=has_bet_active,
                        registration_date=reg_date,
                        coverage_start_date=tenure.coverage_start_date,
                        coverage_type=getattr(tenure, "coverage_type", None) or _extract_field_raw(f, "coverage_type"),
                        company_obj=comp_obj,
                    )
                    ce.waiver_betterment = has_bet_active
                    ce.betterment_rate = _ZERO if has_bet_active else (to_decimal_clean(b_rate) if b_rate is not None else None)
                    ce.betterment_display = "Yes (0%)" if has_bet_active else b_disp

                for clr_key in ("windscreen_sum_insured", "special_perils", "llp", "llop", "llp_llop", "towing_limit", "motor_premium"):
                    record_manual_overrides(ce, clear_field=clr_key)
                if has_bet_active and bet_exceeds_cap:
                    record_manual_overrides(ce, edited_fields=("waiver_betterment",))
                else:
                    record_manual_overrides(ce, clear_field="waiver_betterment")
            elif changed_paths:
                if any("fields.premium" in p for p in changed_paths):
                    record_manual_overrides(ce, clear_field="motor_premium")
                if any("fields.sum_insured" in p or "fields.coverage_amount" in p for p in changed_paths):
                    record_manual_overrides(ce, clear_field="sum_insured")
                if any("fields.valuation_type" in p for p in changed_paths):
                    record_manual_overrides(ce, clear_field="valuation_type")
                    record_manual_overrides(ce, clear_field="agreed_value")
                if any("fields.excess" in p for p in changed_paths):
                    record_manual_overrides(ce, clear_field="excess")
                if towing_explicitly_edited:
                    record_manual_overrides(ce, clear_field="towing_limit")

            cur_si_dec = _q2(ce.sum_insured)
            cur_mp_dec = _q2(ce.motor_premium)
            if cur_si_dec > _ZERO and cur_mp_dec > _ZERO:
                ce.rate_percentage = ((cur_mp_dec / cur_si_dec) * _HUNDRED).quantize(_RATE_QUANT, rounding=ROUND_HALF_UP)

            ce.version = (ce.version or 1) + 1

        ce.road_tax = eff_rt
        ce.runner_fee = eff_rf
        ce.include_road_tax = tenure.include_road_tax is not False
        ce.include_runner_fee = tenure.include_runner_fee is not False
        ce.total_payable = (_q2(ce.motor_premium) + eff_rt + eff_rf).quantize(_CENT, rounding=ROUND_HALF_UP)
        if tenure.covernote_session_id and ce.session_id == tenure.covernote_session_id:
            tenure.won_premium = ce.total_payable

    rank_comparison_entries(
        all_tenure_entries,
        explicit_winning_company_id=tenure.winning_company_id,
        explicit_winning_ref=tenure.winning_quotation_ref,
        auto_recommend_rank1=False,
    )
