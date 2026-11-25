"""Map extraction candidates into simple editable Risklocker draft fields."""

from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.extraction.candidate_finder import DRAFT_FIELDS, MONEY_FIELDS
from app.extraction.conflict_detector import select_all
from app.extraction.types import CandidateValue
from app.extraction.validators import validate_date_range, validate_engine_cc, validate_money, validate_ncd, validate_vehicle_number
from app.models.enums import RecordStatus


COMMON_TRUNCATIONS = {
    "AUTOPILO": "AUTOPILOT",
    "AUTOMATI": "AUTOMATIC",
    "COMPREHENSI": "COMPREHENSIVE",
    "TRANSMISSI": "TRANSMISSION",
    "ELECTRI": "ELECTRIC",
    "STANDAR": "STANDARD",
    "PREMIU": "PREMIUM",
    "HYBRI": "HYBRID",
    "PETRO": "PETROL",
    "DIESE": "DIESEL",
    "TURB": "TURBO",
    "NAVIGATI": "NAVIGATION",
}


def normalize_vehicle_model_text(car_model: str | None, car_brand: str | None = None) -> str:
    """
    Normalizes vehicle model text:
    - CAR MODEL = CAR BRAND + CAR MODEL (e.g. 'TESLA' + 'MODEL 3 ...' -> 'TESLA MODEL 3 ...')
    - If model already starts with the brand (e.g. 'BMW M3' or 'HONDA CIVIC'), do NOT duplicate brand.
    - Repairs common table cell truncations ('AUTOPILO' -> 'AUTOPILOT', 'AUTOMATI' -> 'AUTOMATIC').
    - Balances unclosed parentheses.
    - Deduplicates adjacent identical tokens (e.g. 'BMW BMW M3' -> 'BMW M3').
    """
    if not car_model or not car_model.strip():
        return (car_brand or "").strip()

    text = car_model.strip()

    # Clean leading/trailing punctuation like colons, hyphens
    text = re.sub(r"^[\s:\-]+", "", text).strip()

    # Strip PDF schedule placeholder filler without damaging model trims (e.g. 'S 400', 'G 350')
    text = re.sub(
        r"\b(?:OTHER\s+COMMERCIAL\s+MAKE|ALL\s+MODELS\s*\(?COMMERCIAL\)?|COMMERCIAL\s+MAKE|UNKNOWN\s+MODEL|NOT\s+SPECIFIED)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\s+", " ", text).strip()

    # Repair known cell-boundary truncations
    for truncated, full in COMMON_TRUNCATIONS.items():
        pattern = r"\b" + re.escape(truncated) + r"(?=[^a-zA-Z]|$)"
        text = re.sub(pattern, full, text, flags=re.IGNORECASE)

    # Balance unclosed parentheses
    open_p = text.count("(")
    close_p = text.count(")")
    if open_p > close_p:
        text = text + (")" * (open_p - close_p))

    # Deduplicate adjacent duplicate words and collapse repeated standalone trailing brand token
    parts = [p for p in re.split(r"[\s]+", text) if p]
    deduped = []
    for p in parts:
        if not deduped or deduped[-1].upper() != p.upper():
            deduped.append(p)
    if len(deduped) >= 2 and deduped[0].upper() == deduped[-1].upper():
        deduped = deduped[:-1]
    text = " ".join(deduped)

    # Prepend brand if not already present
    brand = (car_brand or "").strip()
    if brand:
        brand_tokens = [b for b in re.split(r"[\s\-]+", brand) if b]
        first_brand_token = brand_tokens[0].upper() if brand_tokens else ""
        first_model_token = deduped[0].upper() if deduped else ""

        text_upper = text.upper()
        brand_upper = brand.upper()

        starts_with_brand = False
        if text_upper.startswith(brand_upper):
            rest = text_upper[len(brand_upper):]
            if not rest or rest[0] in " -/:()":
                starts_with_brand = True
        elif first_brand_token and first_model_token == first_brand_token:
            starts_with_brand = True

        if not starts_with_brand:
            text = f"{brand} {text}"

        # Re-check adjacent deduplication at start in case of e.g. 'BMW BMW M3'
        start_tokens = re.split(r"[\s]+", text)
        if len(start_tokens) >= 2 and start_tokens[0].upper() == start_tokens[1].upper():
            text = " ".join(start_tokens[1:])

    return text.strip()


def _cand_first_value(candidates: dict[str, list[CandidateValue]], key: str) -> str:
    items = candidates.get(key) or []
    return str(items[0].value).strip() if items and getattr(items[0], "value", None) is not None else ""


def reconcile_vehicle_capacity_and_fees(
    fields: dict[str, Any],
    *,
    candidates: dict[str, list[CandidateValue]] | None = None,
    gemini_hints: dict[str, Any] | None = None,
    raw_text: str = "",
    db: Any | None = None,
) -> tuple[str, str, bool, bool]:
    """Normalize vehicle model, classify entity/vehicle type, preserve KG/TON/kW/W/CC units, and apply commercial fee defaults.

    Returns (entity_type, resolved_vehicle_type, include_road_tax, include_runner_fee).
    """
    from app.extraction.entity_classifier import (
        classify_client_entity,
        default_fee_inclusions,
        is_commercial_heavy_vehicle,
    )
    from app.services.road_tax_service import calculate_road_tax
    from app.services.vehicle_catalog_service import infer_vehicle_cc_and_type

    cands = candidates or {}
    hints = gemini_hints or {}

    def _hint(key: str) -> str:
        val = hints.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
        return _cand_first_value(cands, key)

    car_brand_val = (fields.get("car_brand") or {}).get("value")
    clean_name_cand = _hint("clean_vehicle_name")
    car_model_val = clean_name_cand or (fields.get("car_model") or {}).get("value")
    if car_model_val:
        car_model_val = normalize_vehicle_model_text(car_model_val, car_brand_val)
        fields["car_model"] = {"value": car_model_val, "status": "ready", "warnings": [], "message": ""}

    inferred_cc, inferred_type = infer_vehicle_cc_and_type(car_model_val)
    cc_val = (fields.get("engine_cc") or {}).get("value")
    cust_name = (fields.get("customer_name") or {}).get("value") or (fields.get("insured_name") or {}).get("value")
    doc_no = (fields.get("ic_or_brn") or {}).get("value")
    ai_type = (fields.get("client_type") or {}).get("value")
    vclass_cand = _hint("vehicle_class") or str((fields.get("vehicle_class") or {}).get("value") or "").strip()
    powertrain_cand = _hint("powertrain")
    cap_unit_cand = _hint("capacity_unit").lower()
    cand_vtype = _hint("vehicle_type")
    curr_vtype = cand_vtype or (fields.get("vehicle_type") or {}).get("value") or inferred_type or "Car"

    entity_type, resolved_vtype = classify_client_entity(
        customer_name=cust_name,
        ic_or_brn=doc_no,
        ai_client_type=ai_type,
        current_vehicle_type=curr_vtype,
        car_model=car_model_val,
        car_brand=car_brand_val,
        capacity_str=cc_val,
        vehicle_class=vclass_cand,
        powertrain=powertrain_cand,
        raw_text=raw_text,
    )

    fields["client_type"] = {"value": entity_type, "status": "ready", "warnings": [], "message": ""}
    fields["vehicle_type"] = {"value": resolved_vtype, "status": "ready", "warnings": [], "message": ""}

    effective_cc: float | int | str | None = None
    raw_cc_str = str(cc_val or "").strip().lower()
    has_kg_token = bool(re.search(r"\b(?:kg|kilograms?|kgm)\b", raw_cc_str)) or cap_unit_cand == "kg"
    has_ton_token = bool(re.search(r"\b(?:ton(?:s|nes?)?|mt)\b", raw_cc_str)) or cap_unit_cand == "ton"
    has_kw_token = bool(re.search(r"\b(?:kw|kilowatt)\b", raw_cc_str)) or cap_unit_cand == "kw"
    has_watt_token = (bool(re.search(r"(?<![a-z])w(?:att(?:s)?)?(?![a-z])", raw_cc_str)) or cap_unit_cand == "w") and not has_kw_token
    is_comm_heavy = is_commercial_heavy_vehicle(
        vehicle_type=resolved_vtype,
        car_model=f"{car_brand_val or ''} {car_model_val or ''}".strip(),
        vehicle_class=vclass_cand,
        capacity_str=str(cc_val or ""),
        raw_text=raw_text,
    )
    is_ev_vehicle = (
        not is_comm_heavy
        and (
            resolved_vtype in {"EVSaloonCar", "EVNonSaloonCar", "EVMotorcycle"}
            or powertrain_cand.upper() == "EV"
            or has_kw_token
            or has_watt_token
        )
    ) or (resolved_vtype == "EVCommercial")

    if cc_val:
        cleaned_cc_str = re.sub(r"[^\d.]", "", str(cc_val)).strip()
        if cleaned_cc_str:
            try:
                num_val = float(cleaned_cc_str)
                if num_val > 0 and (has_kg_token or has_ton_token):
                    if has_ton_token and num_val <= 150.0:
                        disp_ton = f"{int(num_val)}" if num_val == int(num_val) else f"{num_val:.1f}"
                        effective_cc = f"{disp_ton} TON"
                        fields["engine_cc"] = {"value": f"{disp_ton} TON", "status": "ready", "warnings": [], "message": ""}
                    elif num_val <= 100_000.0:
                        weight_kg = round(num_val)
                        effective_cc = f"{weight_kg} KG"
                        fields["engine_cc"] = {"value": f"{weight_kg} KG", "status": "ready", "warnings": [], "message": ""}
                    else:
                        fields["engine_cc"] = {"value": "", "status": "check_needed", "warnings": [], "message": "Please check this value."}
                    if not is_ev_vehicle:
                        resolved_vtype = "Lorry"
                        fields["vehicle_type"]["value"] = "Lorry"
                elif num_val > 0 and (has_kw_token or has_watt_token or is_ev_vehicle):
                    is_ev_vehicle = True
                    kw = (num_val / 1000.0) if (has_watt_token or (not has_kw_token and num_val >= 1000.0)) else num_val
                    if 0 < kw <= 2_500.0:
                        effective_cc = f"{int(kw) if kw == int(kw) else round(kw, 1)} kW"
                        disp_kw = f"{int(kw)}" if kw == int(kw) else f"{kw:.1f}"
                        fields["engine_cc"] = {"value": f"{disp_kw} kW", "status": "ready", "warnings": [], "message": ""}
                    if not str(fields["vehicle_type"].get("value", "")).lower().startswith("ev"):
                        curr_vt = str(fields["vehicle_type"].get("value", "")).lower()
                        if "motor" in curr_vt or "bike" in curr_vt:
                            resolved_vtype = "EVMotorcycle"
                        elif is_comm_heavy:
                            resolved_vtype = "EVCommercial"
                        else:
                            resolved_vtype = "EVSaloonCar"
                        fields["vehicle_type"]["value"] = resolved_vtype
                elif is_comm_heavy:
                    if num_val > 16_000.0:
                        effective_cc = None
                        fields["engine_cc"] = {"value": "", "status": "check_needed", "warnings": [], "message": "Please verify engine capacity or BDM weight."}
                    elif 0.5 <= num_val < 100.0:
                        disp_ton = f"{int(num_val)}" if num_val == int(num_val) else f"{num_val:.1f}"
                        effective_cc = f"{disp_ton} TON"
                        fields["engine_cc"] = {"value": f"{disp_ton} TON", "status": "ready", "warnings": [], "message": ""}
                    elif num_val >= 100.0:
                        effective_cc = round(num_val)
                        fields["engine_cc"] = {"value": f"{effective_cc} CC", "status": "ready", "warnings": [], "message": ""}
                else:
                    if 0.5 <= num_val <= 8.0:
                        inferred_from_litres = {1.0: 998, 1.2: 1197, 1.3: 1329, 1.5: 1496, 1.6: 1598, 1.8: 1798, 2.0: 1998, 2.5: 2494, 3.0: 2998}
                        effective_cc = inferred_from_litres.get(round(num_val, 1), round(num_val * 1000))
                    elif 8.0 < num_val <= 8_000.0:
                        effective_cc = round(num_val)
                    else:
                        effective_cc = None
                        fields["engine_cc"] = {"value": "", "status": "check_needed", "warnings": [], "message": "Please check this value."}
                    if effective_cc:
                        fields["engine_cc"] = {"value": f"{effective_cc} CC", "status": "ready", "warnings": [], "message": ""}
            except (ValueError, TypeError):
                pass

    if not effective_cc and (fields.get("engine_cc") or {}).get("status") != "check_needed":
        effective_cc = inferred_cc
        if effective_cc and not (fields.get("engine_cc") or {}).get("value"):
            fields["engine_cc"] = {"value": f"{effective_cc} CC", "status": "ready", "warnings": [], "message": ""}

    inc_rt, inc_rf = default_fee_inclusions(
        vehicle_type=resolved_vtype,
        car_model=car_model_val,
        vehicle_class=vclass_cand,
        capacity_str=str((fields.get("engine_cc") or {}).get("value") or cc_val or ""),
        raw_text=raw_text,
    )
    fields["include_road_tax"] = {"value": "true" if inc_rt else "false", "status": "ready", "warnings": [], "message": ""}
    fields["include_runner_fee"] = {"value": "true" if inc_rf else "false", "status": "ready", "warnings": [], "message": ""}

    if not inc_rf:
        fields["service_fee"] = {"value": "0.00", "status": "ready", "warnings": [], "message": ""}
    elif db is not None:
        from app.services.admin_service import get_runner_fee_default

        default_rf = get_runner_fee_default(db)
        fields["service_fee"] = {"value": f"{default_rf:.2f}", "status": "ready", "warnings": [], "message": ""}
    else:
        fields["service_fee"] = {"value": "", "status": "ready", "warnings": [], "message": ""}

    auto_rt = 0.0
    if inc_rt and effective_cc:
        auto_rt = calculate_road_tax(
            cc=effective_cc,
            vehicle_type=resolved_vtype,
            owner_type=entity_type,
            jurisdiction="West Malaysia",
            db=db,
        )

    roadtax_val_str = "0.00" if not inc_rt else (f"{auto_rt:.2f}" if auto_rt > 0 else ("0.00" if (fields.get("engine_cc") or {}).get("status") == "check_needed" else ""))
    fields["roadtax"] = {"value": roadtax_val_str, "status": "ready", "warnings": [], "message": ""}
    return entity_type, resolved_vtype, inc_rt, inc_rf


def build_draft(
    candidates: dict[str, list[CandidateValue]],
    benefit_lines: list[dict] | None = None,
    raw_text: str = "",
) -> tuple[dict, list[str], str]:
    selections = select_all(candidates, DRAFT_FIELDS)
    fields = {field: selection.to_draft_field() for field, selection in selections.items()}
    fields["insurance_type"]["value"] = fields["insurance_type"]["value"] or "Motor"
    fields["insurance_type"]["status"] = "ready"

    warnings: list[str] = []
    required_money_fields = {"coverage_amount", "premium", "total_amount"}
    validators = {
        "vehicle_no": validate_vehicle_number,
        "ncd_percent": validate_ncd,
        "engine_cc": validate_engine_cc,
    }
    validators.update({field_name: validate_money for field_name in MONEY_FIELDS})
    for field_name, validator in validators.items():
        if field_name not in fields:
            continue
        if field_name in MONEY_FIELDS and field_name not in required_money_fields and not fields[field_name].get("value"):
            continue
        ok, message = validator(fields[field_name].get("value"))
        if not ok:
            fields[field_name]["status"] = "check_needed"
            fields[field_name]["message"] = "Please check this value."
            if message:
                fields[field_name].setdefault("warnings", []).append(message)

    date_ok, date_message = validate_date_range(fields.get("cover_start_date", {}).get("value"), fields.get("cover_end_date", {}).get("value"))
    if not date_ok:
        for name in ("cover_start_date", "cover_end_date"):
            fields[name]["status"] = "check_needed"
            fields[name]["message"] = "Please check this value."
            fields[name].setdefault("warnings", []).append(date_message or "Please check this value.")

    # Date range formatting (Always DD-MM-YYYY)
    start_raw = fields.get("cover_start_date", {}).get("value") or fields.get("issue_date", {}).get("value") or ""
    end_raw = fields.get("cover_end_date", {}).get("value") or ""

    def _to_dmy(date_str: str) -> str:
        if not date_str:
            return ""
        import datetime
        try:
            if "-" in date_str:
                parts = [int(p) for p in date_str.strip().split("-")]
                if len(parts) == 3:
                    if parts[0] > 1000:  # YYYY-MM-DD
                        return f"{parts[2]:02d}-{parts[1]:02d}-{parts[0]:04d}"
                    elif parts[2] > 1000:  # DD-MM-YYYY
                        return f"{parts[0]:02d}-{parts[1]:02d}-{parts[2]:04d}"
            elif "/" in date_str:
                parts = [int(p) for p in date_str.strip().split("/")]
                if len(parts) == 3:
                    if parts[2] > 1000:
                        return f"{parts[0]:02d}-{parts[1]:02d}-{parts[2]:04d}"
                    elif parts[0] > 1000:
                        return f"{parts[2]:02d}-{parts[1]:02d}-{parts[0]:04d}"
        except Exception:
            pass
        return date_str

    if start_raw and not end_raw:
        import datetime
        try:
            dt = None
            if "-" in start_raw:
                parts = [int(p) for p in start_raw.strip().split("-")]
                if len(parts) == 3:
                    dt = datetime.date(parts[0], parts[1], parts[2]) if parts[0] > 1000 else datetime.date(parts[2], parts[1], parts[0])
            elif "/" in start_raw:
                parts = [int(p) for p in start_raw.strip().split("/")]
                if len(parts) == 3:
                    dt = datetime.date(parts[2], parts[1], parts[0]) if parts[2] > 1000 else datetime.date(parts[0], parts[1], parts[2])
            if dt:
                try:
                    end_dt = dt.replace(year=dt.year + 1)
                except ValueError:
                    end_dt = dt + datetime.timedelta(days=365)
                end_raw = f"{end_dt.day:02d}-{end_dt.month:02d}-{end_dt.year:04d}"
                if "cover_end_date" in fields:
                    fields["cover_end_date"]["value"] = end_raw
                date_ok = True
        except Exception:
            pass

    start_dmy = _to_dmy(start_raw)
    end_dmy = _to_dmy(end_raw)

    if start_dmy and end_dmy:
        fields["cover_period"]["value"] = f"{start_dmy} to {end_dmy}"
    elif start_dmy:
        fields["cover_period"]["value"] = start_dmy
    elif end_dmy:
        fields["cover_period"]["value"] = end_dmy
    else:
        fields["cover_period"]["value"] = ""

    fields["cover_period"]["status"] = "ready" if (start_dmy and end_dmy and date_ok) else ("check_needed" if not date_ok else "ready")

    # Sync Sum Insured / Coverage Amount / Market Value / Agreed Value aliases
    coverage_candidates: list[str] = []
    for alias in ("coverage_amount", "sum_insured", "market_value", "agreed_value"):
        val = fields.get(alias, {}).get("value")
        if val and str(val).strip():
            coverage_candidates.append(str(val).strip())

    def _parse_money_flt(v: Any) -> float:
        if v is None:
            return 0.0
        clean = re.sub(r"[^\d.]", "", str(v))
        try:
            return float(clean) if clean else 0.0
        except ValueError:
            return 0.0

    best_coverage_val: str | None = None
    if coverage_candidates:
        # Prioritize realistic vehicle sum insured (>= 1,000 RM) over stray small amounts (< 1,000 RM)
        realistic = [v for v in coverage_candidates if _parse_money_flt(v) >= 1000.0]
        if realistic:
            best_coverage_val = realistic[0]
        else:
            best_coverage_val = coverage_candidates[0]

    if best_coverage_val:
        for alias in ("coverage_amount", "sum_insured", "market_value", "agreed_value"):
            if alias in fields:
                existing = fields[alias].get("value")
                # Overwrite if empty or if existing is unrealistically small (< 1000) while best is realistic (>= 1000)
                if not existing or (_parse_money_flt(existing) < 1000.0 and _parse_money_flt(best_coverage_val) >= 1000.0):
                    fields[alias]["value"] = best_coverage_val
                    fields[alias]["detected_value"] = best_coverage_val
                    fields[alias]["status"] = "ready"
                    fields[alias]["warnings"] = []
                    fields[alias]["message"] = ""
                if "detected_value" not in fields[alias] or not fields[alias]["detected_value"]:
                    fields[alias]["detected_value"] = fields[alias].get("value")

    # Ensure excess_amount defaults to 0.00 if missing or empty
    if "excess_amount" not in fields or not str(fields.get("excess_amount", {}).get("value") or "").strip():
        fields["excess_amount"] = {
            "value": "0.00",
            "status": "ready",
            "warnings": [],
            "message": "",
        }

    # Ensure compulsory_excess defaults to 0.00 if missing or empty
    if "compulsory_excess" not in fields or not str(fields.get("compulsory_excess", {}).get("value") or "").strip():
        fields["compulsory_excess"] = {
            "value": "0.00",
            "status": "ready",
            "warnings": [],
            "message": "",
        }

    # Ensure valid_until falls back to cover_start_date or start_dmy if missing or empty
    if "valid_until" not in fields or not str(fields.get("valid_until", {}).get("value") or "").strip():
        fallback_validity = start_dmy or start_raw or ""
        if fallback_validity:
            fields["valid_until"] = {
                "value": str(fallback_validity),
                "status": "ready",
                "warnings": [],
                "message": "",
            }
            if "quotation_validity" in fields:
                fields["quotation_validity"]["value"] = str(fallback_validity)
                fields["quotation_validity"]["status"] = "ready"

    # Determine Valuation Type / Basis: "Agreed Value" or "Market Value"
    raw_val_type = str(fields.get("valuation_type", {}).get("value") or "").strip().lower()

    all_text_snippets: list[str] = []
    for cand_list in (candidates or {}).values():
        for c in cand_list:
            if getattr(c, "evidence", None):
                all_text_snippets.append(c.evidence.lower())
            if getattr(c, "value", None):
                all_text_snippets.append(c.value.lower())
    if benefit_lines:
        for bl in benefit_lines:
            if isinstance(bl, dict):
                all_text_snippets.append(str(bl.get("line_text") or bl.get("label") or "").lower())

    joined_evidence = " ".join(all_text_snippets)

    # Negative qualifiers take strict precedence:
    # "agreed value : no / tidak / false" means Market Value!
    has_agreed_no = bool(re.search(r"(?i)\bagreed\s*value\s*[:=\-]?\s*(?:no|tidak|false|0)\b", joined_evidence))
    has_market_no = bool(re.search(r"(?i)\bmarket\s*value\s*[:=\-]?\s*(?:no|tidak|false|0)\b", joined_evidence))
    has_agreed_yes = bool(re.search(r"(?i)\bagreed\s*value\s*[:=\-]?\s*(?:yes|ya|true|1|\bx\b|\[x\])", joined_evidence))
    has_market_yes = bool(re.search(r"(?i)\bmarket\s*value\s*[:=\-]?\s*(?:yes|ya|true|1|\bx\b|\[x\])", joined_evidence))

    is_agreed = False
    is_market = False

    if has_agreed_no:
        is_agreed = False
        is_market = True
    elif has_market_no:
        is_agreed = True
        is_market = False
    elif has_agreed_yes:
        is_agreed = True
    elif has_market_yes:
        is_market = True
    elif "agreed" in raw_val_type and not has_agreed_no:
        is_agreed = True
    elif "market" in raw_val_type and not has_market_no:
        is_market = True
    elif ("endorsement 89" in joined_evidence or "nilai yang dipersetujui" in joined_evidence or "agreed value" in joined_evidence) and not has_agreed_no:
        is_agreed = True
    elif "market value" in joined_evidence or "nilai pasaran" in joined_evidence:
        is_market = True

    final_val_type = "Agreed Value" if is_agreed else "Market Value"
    if "valuation_type" not in fields:
        fields["valuation_type"] = {"value": final_val_type, "status": "ready", "warnings": [], "message": ""}
    else:
        fields["valuation_type"]["value"] = final_val_type
        fields["valuation_type"]["status"] = "ready"
        fields["valuation_type"]["warnings"] = []
        fields["valuation_type"]["message"] = ""

    reconcile_vehicle_capacity_and_fees(fields, candidates=candidates, raw_text=raw_text)

    # Ensure premium is the net base insurance premium (excluding extras)
    try:
        p_val = fields.get("premium", {}).get("value")
        t_val = fields.get("total_amount", {}).get("value")
        gp_val = fields.get("gross_premium", {}).get("value")
        st_val = fields.get("service_tax", {}).get("value")
        bp_val = fields.get("basic_premium_vehicle", {}).get("value") or fields.get("basic_premium", {}).get("value")

        # Sanity check: if optional_cover_amount is identical to basic_premium, it's a layout hallucination
        opt_val = fields.get("optional_cover_amount", {}).get("value")
        if opt_val and bp_val:
            opt_clean = re.sub(r"[^\d.]", "", str(opt_val))
            bp_clean = re.sub(r"[^\d.]", "", str(bp_val))
            if opt_clean and opt_clean == bp_clean:
                fields["optional_cover_amount"]["value"] = ""
                opt_val = ""

        # Sum detected optional cover / extra costs
        extras_cost = Decimal("0")
        if benefit_lines:
            for b in benefit_lines:
                if not isinstance(b, dict):
                    continue
                cost_str = b.get("premium_cost") or ""
                if cost_str:
                    clean = re.sub(r"[^\d.]", "", str(cost_str))
                    if clean:
                        try:
                            num = Decimal(clean)
                            if num > 0:
                                extras_cost += num
                        except Exception:
                            pass

        # Underwriting Sanity Check & BNM Derivation for basic_premium_vehicle
        cov_amt = _parse_money_flt(fields.get("coverage_amount", {}).get("value") or 0)
        ncd_pct = _parse_money_flt(fields.get("ncd_percent", {}).get("value") or 0)
        bp_num = _parse_money_flt(bp_val)

        # Sanity check: If bp_val is <= 50.0 or equals ncd_pct while vehicle sum insured is >= 10,000,
        # it is a corrupt candidate (e.g. 25 RM NCD leak).
        if cov_amt >= 10000.0 and (bp_num < 50.0 or (ncd_pct > 0 and abs(bp_num - ncd_pct) < 0.01)):
            valid_cand = None
            raw_bp_f = fields.get("basic_premium", {}).get("value") if isinstance(fields.get("basic_premium"), dict) else fields.get("basic_premium")
            if raw_bp_f:
                raw_bp_flt = _parse_money_flt(str(raw_bp_f))
                if raw_bp_flt >= 50.0 and (ncd_pct == 0 or abs(raw_bp_flt - ncd_pct) >= 1.0):
                    valid_cand = raw_bp_flt

            if not valid_cand:
                for c in candidates.get("basic_premium_vehicle", []):
                    c_num = _parse_money_flt(c.value)
                    if c_num >= 50.0 and (ncd_pct == 0 or abs(c_num - ncd_pct) >= 1.0):
                        valid_cand = c_num
                        break

            if valid_cand:
                bp_num = valid_cand
            else:
                gp_num = _parse_money_flt(gp_val)
                if gp_num > 50.0 and 0.0 < ncd_pct < 100.0:
                    derived_bp = (gp_num - float(extras_cost)) / (1.0 - ncd_pct / 100.0)
                    if derived_bp >= 50.0:
                        bp_num = derived_bp

            if bp_num >= 50.0:
                bp_str = f"{bp_num:.2f}"
                if "basic_premium_vehicle" in fields:
                    fields["basic_premium_vehicle"]["value"] = bp_str
                    fields["basic_premium_vehicle"]["detected_value"] = bp_str
                    fields["basic_premium_vehicle"]["status"] = "ready"
                if "basic_premium" in fields:
                    fields["basic_premium"]["value"] = bp_str
                    fields["basic_premium"]["detected_value"] = bp_str
                    fields["basic_premium"]["status"] = "ready"
                bp_val = bp_str

        if bp_num > 0.0 and cov_amt > 0.0:
            rate_dec = (Decimal(str(bp_num)) / Decimal(str(cov_amt))).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
            fields["rate"] = {
                "value": f"{rate_dec:.6f}",
                "status": "ready",
                "warnings": [],
                "message": "",
            }

        # If gross_premium and service_tax (plus optional stamp_duty) are extracted, calculate total net insurance premium
        sd_val = fields.get("stamp_duty", {}).get("value")
        calc_prem: Decimal | None = None
        if gp_val and st_val and "premium" in fields:
            try:
                gp_num = Decimal(str(gp_val).replace(",", ""))
                st_num = Decimal(str(st_val).replace(",", ""))
                sd_num = Decimal(str(sd_val).replace(",", "")) if sd_val else Decimal("0.00")
                calc_prem = gp_num + st_num + sd_num
                if not p_val or (bp_val and str(p_val) == str(bp_val)):
                    fields["premium"]["value"] = f"{calc_prem:.2f}"
                    fields["premium"]["status"] = "ready"
                    p_val = f"{calc_prem:.2f}"
            except Exception:
                pass

        # If total_amount in PDF was the insurer total contribution / total payable
        # (STMB TOTAL CONTRIBUTION, AmAssurance/Lonpac Total Payable, Etiqa Total Contribution Payable,
        # Tune Total Payable Perlu Dibayar, Sompo Total Amount Payable)
        if t_val and "premium" in fields:
            try:
                tot_num = Decimal(str(t_val).replace(",", ""))
                r_raw = fields.get("roadtax", {}).get("value") or "0"
                s_raw = fields.get("service_fee", {}).get("value") or "0"
                r_dec = Decimal(str(r_raw).replace(",", "")) if str(r_raw).strip() else Decimal("0.00")
                s_dec = Decimal(str(s_raw).replace(",", "")) if str(s_raw).strip() else Decimal("0.00")
                p_dec = Decimal(str(p_val).replace(",", "")) if p_val else Decimal("0.00")
                bp_dec = Decimal(str(bp_val).replace(",", "")) if bp_val else None
                gp_dec = Decimal(str(gp_val).replace(",", "")) if gp_val else None

                # Do not fold Risklocker roadtax/runner fee back into fields["premium"]
                includes_rf_rt = (r_dec + s_dec) > Decimal("0.00") and abs(tot_num - (p_dec + r_dec + s_dec)) <= Decimal("0.10")
                if not includes_rf_rt:
                    should_promote_total = (
                        not p_val
                        or p_dec <= Decimal("0.00")
                        or (bp_dec is not None and p_dec == bp_dec and tot_num != bp_dec)
                        or (gp_dec is not None and p_dec == gp_dec and tot_num > gp_dec)
                        or (calc_prem is not None and abs(tot_num - calc_prem) <= Decimal("0.10"))
                        or (tot_num == p_dec)
                    )
                    if should_promote_total:
                        fields["premium"]["value"] = f"{tot_num:.2f}"
                        fields["premium"]["status"] = "ready"
                        p_val = f"{tot_num:.2f}"

                # Always keep motor_premium, total_payable, and premium aligned to Underwriter Total Payable (never subtract extras)
                aligned_uw = fields["premium"].get("value") or f"{tot_num:.2f}"
                fields["motor_premium"] = {
                    "value": aligned_uw,
                    "detected_value": aligned_uw,
                    "status": fields["premium"].get("status") or "ready",
                    "warnings": list(fields["premium"].get("warnings") or []),
                    "message": fields["premium"].get("message") or "",
                }
                fields["total_payable"] = {
                    "value": aligned_uw,
                    "detected_value": aligned_uw,
                    "status": fields["premium"].get("status") or "ready",
                    "warnings": list(fields["premium"].get("warnings") or []),
                    "message": fields["premium"].get("message") or "",
                }

                # Always preserve extracted total_amount as the Final Price / Total Payable from PDF
                if "total_amount" in fields:
                    fields["total_amount"]["value"] = f"{tot_num:.2f}"
                    fields["total_amount"]["status"] = "ready"
            except Exception:
                pass

        # Calculate Risklocker total amount if total_amount is not explicitly in the document
        if "total_amount" in fields and (not fields["total_amount"].get("value") or fields["total_amount"].get("value") in {"0", "0.00"}) and p_val:
            r_val = fields.get("roadtax", {}).get("value") or "0"
            s_val = fields.get("service_fee", {}).get("value") or "0"
            try:
                r_num = Decimal(str(r_val).replace(",", "")) if str(r_val).strip() else Decimal("0")
                s_num = Decimal(str(s_val).replace(",", "")) if str(s_val).strip() else Decimal("0")
                uw_p_dec = Decimal(str(p_val).replace(",", ""))
                tot = uw_p_dec + r_num + s_num
                fields["total_amount"]["value"] = f"{tot:.2f}"
                fields["total_amount"]["status"] = "ready"
                fields["motor_premium"] = {"value": f"{uw_p_dec:.2f}", "detected_value": f"{uw_p_dec:.2f}", "status": "ready", "warnings": [], "message": ""}
                fields["total_payable"] = {"value": f"{uw_p_dec:.2f}", "detected_value": f"{uw_p_dec:.2f}", "status": "ready", "warnings": [], "message": ""}
            except Exception:
                pass
    except Exception:
        pass

    for f_name, f_data in fields.items():
        if isinstance(f_data, dict) and ("detected_value" not in f_data or f_data.get("detected_value") is None):
            f_data["detected_value"] = f_data.get("value")

    if "special_perils" not in fields:
        try:
            from app.services.marketing_comparison.special_perils import resolve_special_perils
            sp_status = resolve_special_perils(text=raw_text or "", benefit_lines=benefit_lines or (), fields=fields)
            fields["special_perils"] = {
                "value": sp_status,
                "detected_value": sp_status,
                "status": "ready",
                "warnings": [],
                "message": "",
            }
        except Exception:
            pass

    # Referee Fact-Checking Pass
    from app.extraction.referee import audit_and_reconcile_draft
    fields, ref_notices = audit_and_reconcile_draft(fields, raw_text=raw_text)
    warnings.extend(ref_notices)

    check_count = sum(1 for field in fields.values() if field.get("status") == "check_needed")
    if check_count:
        warnings.append("Please check highlighted values before generating.")
        status = RecordStatus.CHECK_NEEDED.value
    else:
        status = RecordStatus.READY.value

    has_any_required = any(fields[name].get("value") for name in ("customer_name", "vehicle_no", "insurance_company"))
    if not has_any_required:
        status = RecordStatus.CANNOT_READ.value
        warnings.append("Cannot Read")

    return fields, warnings, status
