"""Build immutable, deterministic quotation benefit-card render context."""

from __future__ import annotations

import json
import re
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
    prefix = "RM" if currency == "MYR" else (currency.upper() if currency else "")
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


def _clean_extra_label(raw_label: str) -> str:
    """Normalize common legal liability acronyms without altering curated titles."""
    label = (raw_label or "").strip()
    lower = label.lower()
    if "legal liability to passenger" in lower or lower == "lltp":
        return "Legal Liability to Passengers (LLTP)"
    if "legal liability of passenger" in lower or lower == "llop":
        return "Legal Liability of Passengers (LLOP)"
    return label


def build_extras(selections: Iterable[Any], concepts: Iterable[Any], offerings: Iterable[Any] | None = None) -> list[dict]:
    """Staff-added priced extras shown above the coverage premium."""
    concepts_list = list(concepts)
    concepts_by_id = {str(item.id): item for item in concepts_list}
    concept_labels = {str(item.id): item.label for item in concepts_list}
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
        concept = concepts_by_id.get(str(getattr(sel, "concept_id", None)))
        disp_ovr = (getattr(concept, "display_overrides", {}) or {}) if concept else {}
        show_cov = True
        if disp_ovr.get("enabled") and disp_ovr.get("showCoverage") is False:
            show_cov = False
        elif disp_ovr.get("showCoverage") is False:
            show_cov = False

        concept_id_str = str(getattr(sel, "concept_id", None))
        concept_title = concept_labels.get(concept_id_str)
        offering_override = getattr(offering, "label_override", None)
        sel_override = getattr(sel, "label_override", None)
        evidence = getattr(sel, "evidence_snapshot", {}) or {}
        if not isinstance(evidence, dict):
            evidence = {}
        is_manual_edit = bool(evidence.get("manually_edited") or getattr(sel, "item_kind", None) == "custom")

        # Display Title Resolution Hierarchy:
        # 1. Manual staff edit from Review Workspace (if staff explicitly edited this card)
        # 2. Offering marketing override (if configured on the specific insurer offering)
        # 3. Global Benefit Title from database concept (the curated max ~3 words title)
        # 4. Explicit selection override or fallback default
        if is_manual_edit and sel_override and str(sel_override).strip():
            raw_label = str(sel_override).strip()
        elif offering_override and str(offering_override).strip():
            raw_label = str(offering_override).strip()
        elif concept_title and str(concept_title).strip():
            raw_label = str(concept_title).strip()
        elif sel_override and str(sel_override).strip():
            raw_label = str(sel_override).strip()
        else:
            raw_label = "Extra benefit"

        label = _clean_extra_label(raw_label)
        label = re.sub(r"(\bplan\s*\d+)\s*\(RM\s*[\d,.]+\)", r"\1", label, flags=re.I).strip()
        if not show_cov:
            label = re.sub(r"\s*\(RM\s*[\d,.]+\)", "", label, flags=re.I).strip()

        price_num = None
        if isinstance(price, dict):
            p_val = price.get("amount") or price.get("value")
            try:
                price_num = float(re.sub(r"[^0-9.]", "", str(p_val)))
            except Exception:
                price_num = None
        elif isinstance(price, (int, float)):
            price_num = float(price)

        limit_val = getattr(sel, "coverage_limit", None)
        if not limit_val:
            ev = getattr(sel, "evidence_snapshot", None)
            if isinstance(ev, dict) and ev.get("coverage_limit"):
                limit_val = ev.get("coverage_limit")
        if not limit_val:
            typed = getattr(sel, "typed_value_override", None) or getattr(offering, "typed_value", None)
            if isinstance(typed, dict):
                if typed.get("coverage_limit"):
                    limit_val = typed.get("coverage_limit")
                elif typed.get("semantic_role") in {"insured_limit", "limit"} and typed.get("value"):
                    limit_val = typed.get("value")

        limit_str = ""
        if limit_val and show_cov:
            s = str(limit_val).strip()
            is_plan_name = bool(re.search(r"\b(plan|tier|level|package|option)\s*\d+\b", s, re.I))
            if not is_plan_name and not any(w in s.lower() for w in ("included", "foc", "n/a", "none", "standard", "covered")):
                clean_num_str = re.sub(r"[^0-9.]", "", s)
                if clean_num_str:
                    try:
                        num = float(clean_num_str)
                        # Only show coverage limit if it is positive, >= 100 (or explicitly RM), and distinct from the add-on price
                        if (num >= 100 or (s.upper().startswith("RM") and num > 0)) and (price_num is None or abs(num - price_num) > 0.01):
                            limit_formatted = f"RM {int(num):,}" if num == int(num) else f"RM {num:,.2f}"
                            limit_str = f"({limit_formatted})"
                    except Exception:
                        pass

        extras.append({
            "selection_id": sel.id,
            "concept_id": getattr(sel, "concept_id", None),
            "concept_key": getattr(concept, "concept_key", None),
            "display_overrides": disp_ovr,
            "show_coverage": show_cov,
            "label": label,
            "coverage_limit": limit_str,
            "price": price,
            "sort_order": int(getattr(sel, "sort_order", 0) or 0),
        })
    extras.sort(key=lambda item: (item["sort_order"], item["label"].casefold(), item["selection_id"]))
    return extras


def adjusted_total_text(fields: dict, extras: list[dict], round_total: bool = False) -> str:
    """Total premium including staff-added extras; deterministic from extracted values."""
    extras_total = Decimal("0")
    for extra in extras:
        raw_price = extra.get("price") or {}
        amount = raw_price.get("amount") if raw_price.get("amount") is not None else raw_price.get("value")
        if amount is not None:
            try:
                extras_total += Decimal(re.sub(r"[^\d.]", "", str(amount)))
            except (InvalidOperation, TypeError, ValueError):
                pass

    p_raw = (fields or {}).get("premium")
    p_val = p_raw.get("value") if isinstance(p_raw, dict) else p_raw
    base_prem = None
    if p_val:
        try:
            clean_p = re.sub(r"[^\d.]", "", str(p_val))
            if clean_p:
                base_prem = Decimal(clean_p)
        except (InvalidOperation, TypeError, ValueError):
            base_prem = None

    rt_raw = (fields or {}).get("roadtax")
    rt_val = rt_raw.get("value") if isinstance(rt_raw, dict) else rt_raw
    rt_num = Decimal("0")
    if rt_val:
        try:
            clean_rt = re.sub(r"[^\d.]", "", str(rt_val))
            if clean_rt:
                rt_num = Decimal(clean_rt)
        except Exception:
            pass
    if rt_num == Decimal("0") and (fields or {}).get("engine_cc"):
        from app.services.road_tax_service import calculate_road_tax
        cc_raw = (fields or {}).get("engine_cc")
        cc_val = cc_raw.get("value") if isinstance(cc_raw, dict) else cc_raw
        if cc_val:
            try:
                clean_cc = float(re.sub(r"[^\d.]", "", str(cc_val)))
                if clean_cc > 0:
                    vtype_raw = (fields or {}).get("vehicle_type")
                    vtype_val = vtype_raw.get("value") if isinstance(vtype_raw, dict) else vtype_raw
                    ctype_raw = (fields or {}).get("client_type")
                    ctype_val = ctype_raw.get("value") if isinstance(ctype_raw, dict) else ctype_raw
                    cname_raw = (fields or {}).get("insured_name") or (fields or {}).get("customer_name")
                    cname_val = cname_raw.get("value") if isinstance(cname_raw, dict) else cname_raw
                    cmodel_raw = (fields or {}).get("car_model")
                    cmodel_val = cmodel_raw.get("value") if isinstance(cmodel_raw, dict) else cmodel_raw
                    cbrand_raw = (fields or {}).get("car_brand")
                    cbrand_val = cbrand_raw.get("value") if isinstance(cbrand_raw, dict) else cbrand_raw
                    from app.extraction.entity_classifier import classify_vehicle_ev_status, is_corporate_name
                    is_corp = (
                        str(ctype_val or "").lower() in {"company", "corporate", "business"}
                        or "company" in str(vtype_val or "").lower()
                        or is_corporate_name(str(cname_val or ""))
                    )
                    is_ev, ev_cat = classify_vehicle_ev_status(str(cbrand_val or ""), str(cmodel_val or ""), str(cc_val or ""))
                    vtype_to_use = ev_cat if (is_ev and ev_cat) else str(vtype_val or "Car")
                    rt_calc = calculate_road_tax(
                        clean_cc,
                        vtype_to_use,
                        owner_type="Company" if is_corp else "Individual",
                    )
                    if rt_calc > 0:
                        rt_num = Decimal(f"{rt_calc:.2f}")
            except Exception:
                pass

    sf_raw = (fields or {}).get("service_fee") or (fields or {}).get("runner_fee")
    sf_val = sf_raw.get("value") if isinstance(sf_raw, dict) else sf_raw
    sf_num = Decimal("0")
    if sf_val:
        try:
            clean_sf = re.sub(r"[^\d.]", "", str(sf_val))
            if clean_sf:
                sf_num = Decimal(clean_sf)
        except Exception:
            pass

    if base_prem is not None and base_prem > 0:
        total = base_prem + extras_total + rt_num + sf_num
    else:
        tot_raw = (fields or {}).get("total_amount")
        tot_val = tot_raw.get("value") if isinstance(tot_raw, dict) else tot_raw
        try:
            clean_tot = re.sub(r"[^\d.]", "", str(tot_val or ""))
            total = Decimal(clean_tot) if clean_tot else Decimal("0")
        except (InvalidOperation, TypeError, ValueError):
            return ""
        if total == 0:
            return ""

    if round_total:
        total = Decimal(int(total.quantize(Decimal("1"), rounding="ROUND_HALF_UP")))
        return f"{total:,.2f}"

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
        return ""
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


def _is_valid_price(price: Any) -> bool:
    if not price:
        return False
    if isinstance(price, (int, float)):
        return price > 0
    if isinstance(price, str):
        s = price.strip().lower()
        if not s:
            return False
        clean = re.sub(r"^(rm|myr)\s*", "", s).strip()
        if clean in {"", "0", "00", "0.0", "0.00", "null", "none", "quoted", "as quoted", "foc", "included"}:
            return False
        if "%" in s:
            return True
        try:
            num = float(re.sub(r"[^0-9.]", "", clean))
            return num > 0
        except Exception:
            return False
    if isinstance(price, dict):
        disp = str(price.get("display_text") or "").strip().lower()
        if disp:
            clean_disp = re.sub(r"^(rm|myr)\s*", "", disp).strip()
            if clean_disp in {"", "0", "00", "0.0", "0.00", "null", "none", "quoted", "as quoted", "foc", "included"}:
                return False
            if "%" in disp:
                return False
        val = price.get("value") if price.get("value") is not None else price.get("amount")
        if val is not None:
            val_str = str(val).strip()
            if "%" in val_str or any(w in val_str.lower() for w in ("sum insured", "sum covered", "accessory")):
                return False
            try:
                num = float(re.sub(r"[^0-9.]", "", val_str))
                return num > 0
            except Exception:
                pass
        return False
    return False


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
    eval_context: dict | None = None,
    insurer_catalog: list[dict] | None = None,
    active_conditional_descriptions: dict[str, str] | None = None,
    company_baseline_descriptions: dict[str, str] | None = None,
    company_baseline_costs: dict[str, str] | None = None,
    visual_profile_assets: dict[str, str] | None = None,
) -> dict:
    price = getattr(selection, "price", None) or getattr(offering, "optional_price", None)
    cost_status = getattr(selection, "cost_status", None) or getattr(offering, "cost_status", "foc")
    if not cost_status:
        cost_status = "foc"

    has_selection_price = selection is not None and hasattr(selection, "price") and selection.price is not None
    is_selection_explicit_foc = selection is not None and getattr(selection, "cost_status", None) in {"foc", "included"} and getattr(selection, "price", None) is None
    has_selection_typed = selection is not None and bool(getattr(selection, "typed_value_override", None))

    # Dynamic company baseline cost calculation (only if user hasn't explicitly set price or FOC)
    if not has_selection_price and not is_selection_explicit_foc:
        if company_baseline_costs and concept and getattr(concept, "id", None):
            raw_b_cost = company_baseline_costs.get(str(concept.id))
            if raw_b_cost and raw_b_cost.strip():
                s_cost = raw_b_cost.strip()
                if "%" in s_cost:
                    # Formula rate, e.g. "15% of Sum Covered" or "0.30% of Sum Insured"
                    try:
                        windscreen_val = (eval_context or {}).get("windscreen_sum_covered") or (eval_context or {}).get("windscreen") or (eval_context or {}).get("windscreen_sum_insured")
                        if windscreen_val and ("15%" in s_cost or "windscreen" in s_cost.lower()):
                            clean_w = re.sub(r"[^0-9.]", "", str(windscreen_val))
                            if clean_w and float(clean_w) > 0:
                                calc_val = round(float(clean_w) * 0.15, 2)
                                price = {"type": "money", "amount": calc_val, "value": calc_val, "currency": "MYR"}
                            else:
                                price = None
                        else:
                            pct_match = re.search(r"([0-9.]+)\s*%", s_cost)
                            vsi_val = (eval_context or {}).get("vehicle_sum_insured") or (eval_context or {}).get("sum_insured")
                            if pct_match and vsi_val and float(vsi_val) > 0:
                                rate = float(pct_match.group(1))
                                calc_val = round(float(vsi_val) * (rate / 100.0), 2)
                                if calc_val > 0:
                                    price = {"type": "money", "amount": calc_val, "value": calc_val, "currency": "MYR"}
                                else:
                                    price = None
                            else:
                                # Cannot reliably calculate cost: suppress price badge to avoid wrong numbers (e.g. MYR 0.30)
                                price = None
                    except Exception:
                        price = None
                else:
                    try:
                        num_val = float(re.sub(r"[^0-9.]", "", s_cost))
                        if num_val > 0:
                            price = {"type": "money", "amount": num_val, "value": num_val, "currency": "MYR"}
                        else:
                            price = None
                    except Exception:
                        price = None

    if not _is_valid_price(price):
        price = None

    catalog_def = None
    if insurer_catalog and concept and hasattr(concept, "concept_key"):
        for item in insurer_catalog:
            if item.get("concept_key") == concept.concept_key:
                catalog_def = item
                break

    if catalog_def and eval_context:
        from app.services.formula_evaluator import evaluate_formula
        if catalog_def.get("coverage_formula") and not has_selection_typed:
            try:
                calc_val = evaluate_formula(catalog_def["coverage_formula"], eval_context)
                if calc_val is not None:
                    typed_value = {"type": "string", "display_text": str(calc_val)}
            except Exception:
                pass
                
        if catalog_def.get("cost_formula") and not has_selection_price and not is_selection_explicit_foc:
            try:
                cost_res = evaluate_formula(catalog_def["cost_formula"], eval_context)
                if cost_res is not None:
                    cost_res = round(float(cost_res), 2)
                    price = {"amount": cost_res, "currency": "MYR"}
                    if cost_res == 0.0:
                        cost_status = "foc"
                    else:
                        cost_status = "paid"
            except Exception:
                pass

    # Disambiguate coverage amount (typed_value / card_val) from price / cost
    opt_p = getattr(offering, "optional_price", None) or price
    if opt_p and typed_value:
        p_val = (opt_p.get("amount") if opt_p.get("amount") is not None else opt_p.get("value")) if isinstance(opt_p, dict) else opt_p
        t_val = (typed_value.get("amount") if typed_value.get("amount") is not None else typed_value.get("value")) if isinstance(typed_value, dict) else typed_value
        if p_val is not None and t_val is not None:
            try:
                if abs(float(str(p_val).replace(",", "")) - float(str(t_val).replace(",", ""))) < 0.01:
                    ev_lim = (getattr(selection, "evidence_snapshot", None) or {}).get("coverage_limit")
                    disp = getattr(offering, "display_value", None)
                    if ev_lim:
                        typed_value = {"type": "string", "display_text": str(ev_lim)}
                    elif disp and str(disp).strip() and str(disp).strip() != str(p_val).strip():
                        typed_value = {"type": "string", "display_text": str(disp)}
                    else:
                        typed_value = None
            except Exception:
                pass

    try:
        card_val = format_benefit_value(typed_value) if typed_value is not None else ""
    except RenderContextError:
        if isinstance(typed_value, dict):
            card_val = str(typed_value.get("display_text") or typed_value.get("value") or "")
        else:
            card_val = ""

    # Strict check: card_val must contain digits or be 'unlimited'
    if card_val:
        has_digits = any(c.isdigit() for c in card_val)
        is_unlimited = card_val.strip().lower() == "unlimited"
        if not has_digits and not is_unlimited:
            card_val = ""
        elif card_val.strip().lower() in {"included standard cover", "included", "foc", "as quoted", "selected", "yes", "true", "standard", "optional"}:
            card_val = ""

    # If card_val is empty, but evidence_snapshot has an extracted coverage limit (e.g. RM 4,000):
    ev_lim = (getattr(selection, "evidence_snapshot", None) or {}).get("coverage_limit")
    if ev_lim and (not card_val or card_val.lower() in {"included standard cover", "included", "foc", "as quoted", "selected", "optional"}):
        ev_str = str(ev_lim).strip()
        if ev_str.lower() in {"included standard cover", "included", "foc", "as quoted", "selected", "yes", "true", "standard", "optional"}:
            card_val = ""
        else:
            has_digits = any(c.isdigit() for c in ev_str)
            is_unlimited = ev_str.lower() == "unlimited"
            if has_digits and not ev_str.startswith("RM"):
                card_val = f"RM {ev_str}"
            elif has_digits or is_unlimited:
                card_val = ev_str
            else:
                card_val = ""

    is_detected = getattr(selection, "source_kind", None) == "extracted" or getattr(selection, "evidence_snapshot", None) is not None
    is_purchased_extra = (cost_status == "paid" and price is not None) or is_detected
    is_pure_default = catalog_def.get("category") == "default" and not is_detected and not is_purchased_extra if catalog_def else False
    is_addon = bool(
        getattr(selection, "state", None) == "available_addon"
        or getattr(offering, "role", None) in {"addon_option", "bundle_component"}
        or getattr(offering, "offering_kind", None) in {"optional", "upgrade"}
        or (catalog_def and catalog_def.get("category") == "addon")
    )

    # Resolve description through 7-tier precedence:
    # 1. Selection override (typed_value_override["description"] or manual edit)
    # 2. Dynamic conditional upgrade (company_benefit_conditions when trigger benefit/plan is active)
    # 3. Scenario catalog offering override (CatalogOffering.description_override)
    # 4. Company master baseline description (CompanyBenefitConfig.baseline_description)
    # 5. Insurer matrix catalog fallback (benefit_catalog_matrix.py)
    # 6. Master concept default (BenefitConcept.description)
    # 7. Fallback ("")
    concept_id_key = str(getattr(concept, "id", None) or "")
    sel_typed = getattr(selection, "typed_value_override", None)
    sel_desc = sel_typed.get("description") if isinstance(sel_typed, dict) and sel_typed.get("description") else getattr(selection, "description_override", None)
    cond_desc = (active_conditional_descriptions or {}).get(concept_id_key)
    offering_desc = getattr(offering, "description_override", None)
    comp_base_desc = (company_baseline_descriptions or {}).get(concept_id_key)
    cat_desc = catalog_def.get("description") if catalog_def and catalog_def.get("description") else None
    concept_desc = getattr(concept, "description", None)

    if sel_desc and str(sel_desc).strip():
        final_desc = str(sel_desc).strip()
    elif cond_desc and cond_desc.strip():
        final_desc = cond_desc.strip()
    elif comp_base_desc and comp_base_desc.strip():
        final_desc = comp_base_desc.strip()
    elif offering_desc and str(offering_desc).strip():
        final_desc = str(offering_desc).strip()
    elif cat_desc and str(cat_desc).strip():
        final_desc = cat_desc.strip()
    elif concept_desc and str(concept_desc).strip():
        final_desc = str(concept_desc).strip()
    else:
        final_desc = ""

    is_custom_desc = bool(
        (sel_desc and str(sel_desc).strip())
        or (cond_desc and cond_desc.strip())
        or (offering_desc and str(offering_desc).strip())
        or (comp_base_desc and comp_base_desc.strip())
    )

    effective_asset_id = (visual_profile_assets.get(str(concept.id)) if visual_profile_assets and concept else None) or asset_id or getattr(concept, "default_asset_id", None)

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
        "label": getattr(selection, "label_override", None) or label or getattr(offering, "label_override", None) or concept.label,
        "description": final_desc,
        "is_custom_description": is_custom_desc,
        "description_override": offering_desc,
        "conditional_description": cond_desc if cond_desc else None,
        "value": card_val,
        "typed_value": typed_value,
        "price": price,
        "optional_price": getattr(offering, "optional_price", None),
        "initial_price": getattr(offering, "optional_price", None),
        "detected_cost": (getattr(selection, "evidence_snapshot", None) or {}).get("premium_cost"),
        "detected_limit": (getattr(selection, "evidence_snapshot", None) or {}).get("coverage_limit"),
        "asset_id": effective_asset_id,
        "cost_status": cost_status,
        "sort_order": int(getattr(offering, "sort_order", 0) or 0),
        "is_detected": is_detected,
        "is_pure_default": is_pure_default,
        "is_addon": is_addon,
        "is_extra": bool(cost_status == "paid" or getattr(selection, "item_kind", None) == "extra" or (isinstance(price, dict) and float(price.get("amount") or price.get("value") or 0) > 0)),
        "group_id": getattr(selection, "package_plan_id", None),
        "display_overrides": getattr(concept, "display_overrides", {}) or {},
    }



def _expanded_cards(
    selection: Any,
    offering: Any,
    concept: Any,
    facets_by_id: dict[str, Any],
    eval_context: dict | None = None,
    insurer_catalog: list[dict] | None = None,
    active_conditional_descriptions: dict[str, str] | None = None,
    company_baseline_descriptions: dict[str, str] | None = None,
    company_baseline_costs: dict[str, str] | None = None,
    visual_profile_assets: dict[str, str] | None = None,
) -> list[dict]:
    typed_value = getattr(selection, "typed_value_override", None) or offering.typed_value
    facet_ids = list(offering.presentation_facet_ids or [])
    if not facet_ids:
        return [_card(
            selection=selection,
            offering=offering,
            concept=concept,
            typed_value=typed_value,
            eval_context=eval_context,
            insurer_catalog=insurer_catalog,
            active_conditional_descriptions=active_conditional_descriptions,
            company_baseline_descriptions=company_baseline_descriptions,
            company_baseline_costs=company_baseline_costs,
            visual_profile_assets=visual_profile_assets,
        )]
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
            eval_context=eval_context,
            insurer_catalog=insurer_catalog,
            active_conditional_descriptions=active_conditional_descriptions,
            company_baseline_descriptions=company_baseline_descriptions,
            company_baseline_costs=company_baseline_costs,
            visual_profile_assets=visual_profile_assets,
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
    eval_context: dict | None = None,
    insurer_catalog: list[dict] | None = None,
    company_conditions: list[Any] | None = None,
    company_configs: list[Any] | None = None,
    visual_profile_assets: dict[str, str] | None = None,
) -> dict[str, list[dict]]:
    """Resolve current and available cards solely from pinned rows and decisions."""
    _global_card = globals().get("_card")
    _global_expanded_cards = globals().get("_expanded_cards")

    retired_concept_ids = {str(getattr(c, "id", "")) for c in concepts if getattr(c, "status", "active") == "retired"}
    concepts_by_id = {k: v for k, v in _index(concepts).items() if k not in retired_concept_ids}
    current = [item for item in selections if item.state == "current" and str(item.concept_id or "") not in retired_concept_ids]

    # Dynamic conditional upgrades from company rules
    active_concept_ids = {str(item.concept_id) for item in current if item.concept_id}
    active_conditional_descriptions: dict[str, str] = {}
    hidden_concept_ids: set[str] = set()
    for cond in (company_conditions or []):
        if not getattr(cond, "is_active", True):
            continue
        trig_id = str(getattr(cond, "trigger_concept_id", "") or "")
        if trig_id in active_concept_ids:
            plan_filter = getattr(cond, "trigger_plan_filter", None)
            matched = False
            if not plan_filter or not str(plan_filter).strip():
                matched = True
            else:
                filter_term = str(plan_filter).strip().lower()
                trig_sels = [s for s in current if str(s.concept_id) == trig_id]
                for s in trig_sels:
                    cov = str(getattr(s, "coverage_limit", "") or "").lower()
                    lbl = str(getattr(s, "label_override", "") or "").lower()
                    plan = str(getattr(s, "package_plan_id", "") or "").lower()
                    tv = getattr(s, "typed_value_override", {}) or {}
                    plan_k = str(tv.get("plan_key", "") if isinstance(tv, dict) else "").lower()
                    disp = str(tv.get("display_text", "") if isinstance(tv, dict) else "").lower()
                    if (filter_term in cov or filter_term in lbl or filter_term in plan or filter_term in plan_k or filter_term in disp):
                        matched = True
                        break
            if matched:
                action = getattr(cond, "action_type", "replace_description") or "replace_description"
                if action == "hide_target" or getattr(cond, "replacement_description", "") == "__HIDE__":
                    hidden_concept_ids.add(str(cond.target_concept_id))
                else:
                    active_conditional_descriptions[str(cond.target_concept_id)] = cond.replacement_description

    company_baseline_descriptions: dict[str, str] = {
        str(cfg.concept_id): cfg.baseline_description
        for cfg in (company_configs or [])
        if getattr(cfg, "concept_id", None) and getattr(cfg, "baseline_description", None) and str(cfg.baseline_description).strip()
    }

    company_baseline_costs: dict[str, str] = {
        str(cfg.concept_id): cfg.baseline_cost
        for cfg in (company_configs or [])
        if getattr(cfg, "concept_id", None) and getattr(cfg, "baseline_cost", None) and str(cfg.baseline_cost).strip()
    }

    disabled_concept_ids: set[str] = {
        str(cfg.concept_id)
        for cfg in (company_configs or [])
        if getattr(cfg, "concept_id", None) and getattr(cfg, "is_enabled", True) is False
    }

    def _card(**kwargs):
        kwargs["eval_context"] = eval_context
        kwargs["insurer_catalog"] = insurer_catalog
        kwargs["active_conditional_descriptions"] = active_conditional_descriptions
        kwargs["company_baseline_descriptions"] = company_baseline_descriptions
        kwargs["company_baseline_costs"] = company_baseline_costs
        if "visual_profile_assets" not in kwargs:
            kwargs["visual_profile_assets"] = visual_profile_assets
        assert _global_card is not None
        return _global_card(**kwargs)

    def _expanded_cards(selection, offering, concept, facets_by_id, visual_profile_assets=visual_profile_assets):
        assert _global_expanded_cards is not None
        return _global_expanded_cards(
            selection,
            offering,
            concept,
            facets_by_id,
            eval_context=eval_context,
            insurer_catalog=insurer_catalog,
            active_conditional_descriptions=active_conditional_descriptions,
            company_baseline_descriptions=company_baseline_descriptions,
            company_baseline_costs=company_baseline_costs,
            visual_profile_assets=visual_profile_assets,
        )

    offerings_by_id = _index(offerings)
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
            if item.concept_id and str(item.concept_id) in retired_concept_ids:
                continue
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
            current_cards.append(_card(selection=item, offering=pseudo, concept=concept, typed_value=item.typed_value_override, visual_profile_assets=visual_profile_assets))
            continue
        offering = offerings_by_id.get(str(item.catalog_offering_id))
        if not offering or offering.status not in {"active", "compatibility"}:
            concept = concepts_by_id.get(str(item.concept_id))
            if not concept:
                continue
            pseudo = type("FallbackOffering", (), {
                "id": str(item.catalog_offering_id or item.id),
                "label_override": item.label_override,
                "typed_value": item.typed_value_override,
                "sort_order": item.sort_order,
                "optional_price": item.price,
                "presentation_facet_ids": [],
            })()
            current_cards.append(_card(selection=item, offering=pseudo, concept=concept, typed_value=item.typed_value_override, visual_profile_assets=visual_profile_assets))
            continue
        concept = concepts_by_id.get(str(offering.concept_id))
        if not concept:
            continue
        current_cards.extend(_expanded_cards(item, offering, concept, facets_by_id, visual_profile_assets=visual_profile_assets))

    outgoing: dict[str, list[Any]] = {}
    for item in relations:
        if item.relation_kind == "replaces":
            outgoing.setdefault(str(item.from_offering_id), []).append(item)
    offered_ids: set[str] = set()
    available_cards: list[dict] = []

    available_selected = [item for item in selections if item.state == "available_addon"]
    available_selected_by_offering = {str(item.catalog_offering_id): item for item in available_selected if item.catalog_offering_id}
    available_selected_by_concept = {str(item.concept_id): item for item in available_selected if item.concept_id}

    for item in current:
        if not item.catalog_offering_id:
            continue
        edges = sorted(outgoing.get(str(item.catalog_offering_id), []), key=lambda edge: (int(edge.sort_order or 0), str(edge.branch_key or ""), str(edge.to_offering_id)))
        for edge in edges:
            target = offerings_by_id.get(str(edge.to_offering_id))
            if not target or target.status not in {"active", "compatibility"} or target.id in selected_offering_ids or target.id in offered_ids or target.id in removed_offering_ids or str(target.concept_id) in removed_concepts or str(target.concept_id) in disabled_concept_ids:
                continue
            concept = concepts_by_id.get(str(target.concept_id))
            if not concept:
                continue
            matching_sel = available_selected_by_offering.get(str(target.id)) or available_selected_by_concept.get(str(target.concept_id))
            available_cards.append(_card(
                selection=matching_sel,
                offering=target,
                concept=concept,
                typed_value=(matching_sel.typed_value_override if matching_sel else None) or target.typed_value,
                branch_key=edge.branch_key,
                visual_profile_assets=visual_profile_assets,
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
                and str(off.concept_id) not in disabled_concept_ids
                and off.status in {"active", "compatibility"}
                and (off.offering_kind in {"upgrade", "optional"} or getattr(off, "role", None) in {"addon_option", "bundle_component"})
            ]
            for off in sorted(same_concept_upgrades, key=lambda row: (int(row.sort_order or 0), str(row.offering_key))):
                concept = concepts_by_id.get(str(off.concept_id))
                if concept:
                    matching_sel = available_selected_by_offering.get(str(off.id)) or available_selected_by_concept.get(str(off.concept_id))
                    available_cards.append(_card(
                        selection=matching_sel,
                        offering=off,
                        concept=concept,
                        typed_value=(matching_sel.typed_value_override if matching_sel else None) or off.typed_value,
                        branch_key=getattr(off, "branch_key", None),
                        visual_profile_assets=visual_profile_assets,
                    ))
                    offered_ids.add(off.id)

    active_concepts = {str(item.concept_id) for item in current if item.concept_id}
    optionals_by_concept: dict[str, list[Any]] = {}
    for item in offerings:
        is_optional = (
            getattr(item, "offering_kind", None) == "optional"
            or getattr(item, "role", None) in {"addon_option", "bundle_component"}
        )
        if is_optional and item.status in {"active", "compatibility"}:
            optionals_by_concept.setdefault(str(item.concept_id), []).append(item)
    for concept_id, items in optionals_by_concept.items():
        if concept_id in active_concepts or concept_id in removed_concepts or concept_id in disabled_concept_ids or any(str(item.id) in offered_ids for item in items):
            continue
        first = min(items, key=lambda item: (int(item.sort_order or 0), str(item.offering_key)))
        concept = concepts_by_id.get(concept_id)
        if concept and str(first.id) not in selected_offering_ids and str(first.id) not in offered_ids and str(first.id) not in removed_offering_ids:
            matching_sel = available_selected_by_offering.get(str(first.id)) or available_selected_by_concept.get(concept_id)
            available_cards.append(_card(
                selection=matching_sel,
                offering=first,
                concept=concept,
                typed_value=(matching_sel.typed_value_override if matching_sel else None) or first.typed_value,
                visual_profile_assets=visual_profile_assets,
            ))
            offered_ids.add(first.id)

    for item in sorted(available_selected, key=lambda row: (int(row.sort_order or 0), str(row.selection_key))):
        if item.concept_id and (str(item.concept_id) in active_concepts or str(item.concept_id) in removed_concepts or str(item.concept_id) in disabled_concept_ids):
            continue
        if getattr(item, "item_kind", None) == "custom":
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
            available_cards.append(_card(selection=item, offering=pseudo, concept=concept, typed_value=item.typed_value_override, visual_profile_assets=visual_profile_assets))
            continue
        offering = offerings_by_id.get(str(item.catalog_offering_id))
        if not offering or offering.id in offered_ids or str(offering.concept_id) in disabled_concept_ids:
            continue
        concept = concepts_by_id.get(str(offering.concept_id))
        if concept:
            available_cards.append(_card(selection=item, offering=offering, concept=concept, typed_value=item.typed_value_override or offering.typed_value, visual_profile_assets=visual_profile_assets))
            offered_ids.add(offering.id)


    if hidden_concept_ids:
        current_cards = [card for card in current_cards if str(card.get("concept_id") or "") not in hidden_concept_ids]
        available_cards = [card for card in available_cards if str(card.get("concept_id") or "") not in hidden_concept_ids]

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
        cards_list = group["cards"]
        if isinstance(cards_list, list):
            cards_list.append(card)
    groups.sort(key=lambda item: (int(getattr(plan_rows.get(item["plan_id"]), "sort_order", 0) or 0), item["plan_key"]))
    return {
        "current_benefits": current_sorted,
        "available_addons": addons_sorted,
        "groups": groups,
    }
