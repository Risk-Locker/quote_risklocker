"""Map extraction candidates into simple editable Risklocker draft fields."""

from __future__ import annotations

from app.extraction.candidate_finder import DRAFT_FIELDS, MONEY_FIELDS
from app.extraction.conflict_detector import select_all
from app.extraction.types import CandidateValue
from app.extraction.validators import validate_date_range, validate_engine_cc, validate_money, validate_ncd, validate_vehicle_number
from app.models.enums import RecordStatus


def build_draft(candidates: dict[str, list[CandidateValue]]) -> tuple[dict, list[str], str]:
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
    coverage_val = (
        fields.get("coverage_amount", {}).get("value")
        or fields.get("sum_insured", {}).get("value")
        or fields.get("market_value", {}).get("value")
        or fields.get("agreed_value", {}).get("value")
    )
    if coverage_val:
        for alias in ("coverage_amount", "sum_insured", "market_value", "agreed_value"):
            if alias in fields:
                if not fields[alias].get("value"):
                    fields[alias]["value"] = str(coverage_val)
                    fields[alias]["status"] = "ready"
                    fields[alias]["warnings"] = []
                    fields[alias]["message"] = ""

    # Infer vehicle CC and vehicle type
    import re
    from app.services.vehicle_catalog_service import infer_vehicle_cc_and_type
    from app.services.road_tax_service import calculate_road_tax

    car_model_val = fields.get("car_model", {}).get("value")
    inferred_cc, inferred_type = infer_vehicle_cc_and_type(car_model_val)
    if "vehicle_type" in fields:
        if not fields["vehicle_type"].get("value"):
            fields["vehicle_type"]["value"] = inferred_type
            fields["vehicle_type"]["status"] = "ready"

    # Extract numeric CC safely from raw string (e.g. '998 CC', '1,498 cc', '1.0', '1.5L')
    cc_val = fields.get("engine_cc", {}).get("value")
    effective_cc = None
    if cc_val:
        cleaned_cc_str = re.sub(r"[^\d.]", "", str(cc_val)).strip()
        if cleaned_cc_str:
            try:
                num_cc = float(cleaned_cc_str)
                if 0.5 <= num_cc <= 8.0:
                    # Litres format (e.g. 1.0 -> 998, 1.5 -> 1496)
                    inferred_from_litres = {1.0: 998, 1.2: 1197, 1.3: 1329, 1.5: 1496, 1.6: 1598, 1.8: 1798, 2.0: 1998, 2.5: 2494, 3.0: 2998}
                    effective_cc = inferred_from_litres.get(round(num_cc, 1), int(round(num_cc * 1000)))
                elif num_cc > 8.0:
                    effective_cc = int(round(num_cc))
            except (ValueError, TypeError):
                pass

    if not effective_cc:
        effective_cc = inferred_cc

    if "engine_cc" in fields and not fields["engine_cc"].get("value") and effective_cc:
        fields["engine_cc"]["value"] = str(effective_cc)
        fields["engine_cc"]["status"] = "ready"

    # Default Runner Fee to RM 20.00 if missing
    if "service_fee" in fields and not fields["service_fee"].get("value"):
        fields["service_fee"]["value"] = "20.00"
        fields["service_fee"]["status"] = "ready"
        fields["service_fee"]["warnings"] = []
        fields["service_fee"]["message"] = ""

    # 2-Level Road Tax Calculation:
    # Level 1: If roadtax is already explicitly present in quotation PDF and > 0, preserve it.
    # Level 2: If roadtax is missing, empty, or 0.00, compute from vehicle CC and vehicle type schedule.
    if "roadtax" in fields:
        raw_rt = fields["roadtax"].get("value")
        parsed_rt = None
        if raw_rt:
            try:
                cleaned_rt = re.sub(r"[^\d.]", "", str(raw_rt)).strip()
                if cleaned_rt:
                    parsed_rt = float(cleaned_rt)
            except (ValueError, TypeError):
                pass

        if parsed_rt is not None and parsed_rt > 0:
            fields["roadtax"]["value"] = f"{parsed_rt:.2f}"
            fields["roadtax"]["status"] = "ready"
            fields["roadtax"]["warnings"] = []
            fields["roadtax"]["message"] = ""
        elif effective_cc:
            computed_rt = calculate_road_tax(effective_cc, vehicle_type=inferred_type)
            if computed_rt > 0:
                fields["roadtax"]["value"] = f"{computed_rt:.2f}"
                fields["roadtax"]["status"] = "ready"
                fields["roadtax"]["warnings"] = []
                fields["roadtax"]["message"] = ""

    # Ensure premium is the net payable insurance premium (after NCD, extras, and SST)
    try:
        from decimal import Decimal
        p_val = fields.get("premium", {}).get("value")
        t_val = fields.get("total_amount", {}).get("value")
        gp_val = fields.get("gross_premium", {}).get("value")
        st_val = fields.get("service_tax", {}).get("value")
        bp_val = fields.get("basic_premium_vehicle", {}).get("value") or fields.get("basic_premium", {}).get("value")

        # If gross_premium and service_tax are extracted, calculate total net insurance premium
        if gp_val and st_val and "premium" in fields:
            try:
                calc_prem = Decimal(str(gp_val).replace(",", "")) + Decimal(str(st_val).replace(",", ""))
                if not p_val or (bp_val and str(p_val) == str(bp_val)):
                    fields["premium"]["value"] = f"{calc_prem:.2f}"
                    fields["premium"]["status"] = "ready"
                    p_val = f"{calc_prem:.2f}"
            except Exception:
                pass

        # If total_amount in PDF was the insurer total premium (e.g. 2,522.42) and premium had basic premium
        if t_val and bp_val and str(p_val) == str(bp_val) and str(t_val) != str(bp_val) and "premium" in fields:
            fields["premium"]["value"] = str(t_val)
            fields["premium"]["status"] = "ready"
            p_val = str(t_val)

        # Calculate Risklocker total amount if total_amount is not explicitly in the document
        if "total_amount" in fields and (not fields["total_amount"].get("value") or fields["total_amount"].get("value") in {"0", "0.00"}) and p_val:
            r_val = fields.get("roadtax", {}).get("value") or "0"
            s_val = fields.get("service_fee", {}).get("value") or "0"
            try:
                tot = Decimal(str(p_val).replace(",", "")) + Decimal(str(r_val).replace(",", "")) + Decimal(str(s_val).replace(",", ""))
                fields["total_amount"]["value"] = f"{tot:.2f}"
                fields["total_amount"]["status"] = "ready"
            except Exception:
                pass
    except Exception:
        pass

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
