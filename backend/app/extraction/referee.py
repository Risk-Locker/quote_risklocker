"""Referee Fact-Checking & Cross-Field Consistency Gate for Motor Quotations.

Cross-checks extracted entities to eliminate hallucinations and contradictions
between customer entity type (Corporate vs Individual), vehicle classification
(Commercial Goods / Lorry vs Private Passenger Car), and product coverage schemes.
"""

from __future__ import annotations

import re
from typing import Any

from app.extraction.entity_classifier import is_business_registration, is_corporate_name, is_malaysian_nric

LORRY_INDICATORS = re.compile(
    r"\b("
    r"LORRY|TRUCK|GOODS\s*VEHICLE|PERMIT|'C'\s*PERMIT|'A'\s*PERMIT|RIGID|TRAILER|TIPPER|PRIME\s*MOVER|"
    r"DAIHATSU\s*DELTA|HINO|ISUZU\s*NPR|ISUZU\s*NQR|ISUZU\s*ELF|FUSO|CANTER|"
    r"UD\s*TRUCKS|SCANIA|SINOTRUK|TOYOTA\s*DYNA|COMMERCIAL\s*VEHICLE"
    r")\b",
    re.IGNORECASE,
)


def _get_val(obj: Any) -> str:
    """Safely extract string value from either a plain string or a draft field dict."""
    if isinstance(obj, dict):
        return str(obj.get("value") or "").strip()
    return str(obj or "").strip()


def _set_field(fields: dict[str, Any], key: str, value: str, reason: str, notices: list[str]) -> None:
    """Update field value and append audit reason to field warnings and notices."""
    if key in fields and isinstance(fields[key], dict):
        fields[key]["value"] = value
        fields[key]["status"] = "ready"
        warns = fields[key].setdefault("warnings", [])
        if reason not in warns:
            warns.append(reason)
    else:
        fields[key] = {
            "value": value,
            "status": "ready",
            "warnings": [reason],
            "detected_value": value,
        }
    notices.append(reason)


def audit_and_reconcile_draft(
    fields: dict[str, Any],
    raw_text: str = "",
) -> tuple[dict[str, Any], list[str]]:
    """Audit draft fields against raw document evidence and cross-field domain logic.

    Invariants enforced:
    1. Corporate customer name (e.g. 'SDN BHD', 'TRADING', 'ENTERPRISE') or BRN registration
       forces client_type = 'Company'.
    2. Valid Malaysian individual NRIC with private individual name forces client_type = 'Private'.
    3. Goods vehicle, lorry models ('Daihatsu Delta', 'Hino', 'Isuzu Elf'), C-Permits, or
       weight capacities ('3000 KG') force vehicle_type = 'Lorry'.
    4. Commercial Lorries cannot have product_name or coverage_type set to 'Private Car Comprehensive'.
       Referee sanitizes this to 'Commercial Vehicle - Comprehensive' with an explicit audit notice.
    """
    notices: list[str] = []
    reconciled = dict(fields)

    cust_name = _get_val(reconciled.get("customer_name"))
    id_no = _get_val(reconciled.get("ic_or_brn"))
    brand = _get_val(reconciled.get("car_brand"))
    model = _get_val(reconciled.get("car_model"))
    capacity = _get_val(reconciled.get("engine_cc"))
    curr_vtype = _get_val(reconciled.get("vehicle_type"))
    curr_client_type = _get_val(reconciled.get("client_type"))
    curr_product = _get_val(reconciled.get("product_name"))

    combined_evidence = f"{cust_name} {id_no} {brand} {model} {capacity} {curr_vtype} {raw_text}".upper()

    # 1. Company vs Individual Check
    is_corp = is_corporate_name(cust_name) or is_business_registration(id_no)
    is_individual = is_malaysian_nric(id_no) and not is_corporate_name(cust_name)

    if is_corp and curr_client_type.lower() != "company":
        _set_field(
            reconciled,
            "client_type",
            "Company",
            "Referee Fact-Check: Customer name/BRN contains corporate indicator; reclassified to Company",
            notices,
        )
    elif is_individual:
        if curr_client_type.lower() == "company":
            _set_field(
                reconciled,
                "client_type",
                "Private",
                "Referee Fact-Check: NRIC and customer name confirm private individual; reclassified to Private",
                notices,
            )
        elif not curr_client_type:
            if "client_type" in reconciled and isinstance(reconciled["client_type"], dict):
                reconciled["client_type"]["value"] = "Private"
                reconciled["client_type"]["status"] = "ready"
            else:
                reconciled["client_type"] = {"value": "Private", "status": "ready"}

    # 2. Commercial Vehicle / Lorry Check
    has_lorry_keyword = bool(LORRY_INDICATORS.search(combined_evidence))
    has_weight_capacity = "KG" in capacity.upper() or "BDM" in combined_evidence or "BTM" in combined_evidence
    is_commercial_lorry = has_lorry_keyword or has_weight_capacity or curr_vtype.lower() in ("lorry", "commercialvehicle")

    if is_commercial_lorry:
        if curr_vtype != "Lorry":
            _set_field(
                reconciled,
                "vehicle_type",
                "Lorry",
                "Referee Fact-Check: Vehicle model / specification indicates commercial goods vehicle / lorry",
                notices,
            )

        # 3. Contradiction Resolution: A commercial lorry cannot be 'Private Car'
        product_upper = curr_product.upper()
        if "PRIVATE CAR" in product_upper or product_upper in ("COMPREHENSIVE", ""):
            new_product = "Commercial Vehicle - Comprehensive"
            _set_field(
                reconciled,
                "product_name",
                new_product,
                "Referee Fact-Check: Commercial lorry policy reclassified from Private Car to Commercial Vehicle",
                notices,
            )

        curr_cov = _get_val(reconciled.get("coverage_type"))
        if "PRIVATE CAR" in curr_cov.upper():
            _set_field(
                reconciled,
                "coverage_type",
                "Commercial Vehicle Comprehensive",
                "Referee Fact-Check: Coverage type corrected for commercial vehicle",
                notices,
            )

    return reconciled, notices
