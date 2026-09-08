"""Client entity classification (Individual vs Company) and vehicle type resolution."""

from __future__ import annotations

import re
from typing import Tuple

# Standard corporate suffixes and legal structure indicators in Malaysia
_CORP_PATTERNS = re.compile(
    r"\b("
    r"SDN\s*\.?\s*BHD\.?|SDNBHD|BHD\.?|BERHAD|"
    r"ENTERPRISE|ENT\.?|TRADING|PLT\.?|LTD\.?|LIMITED|LLC|INC\.?|CORP\.?|CORPORATION|"
    r"HOLDINGS|GROUP|VENTURES|LOGISTICS|SERVICES|ENGINEERING|HARDWARE|MOTORS|PROPERTIES|"
    r"MANAGEMENT|RESOURCES|AUTO|TRANSPORT|AGENCY|CO\.|COMPANY|"
    r"SYARIKAT|PERUSAHAAN|KOPERASI|PERTUBUHAN|PERSATUAN|YAYASAN|MAJLIS|LEMBAGA|JABATAN|"
    r"PUSAT|KLINIK|FARMASI|RESTORAN|KEDAI|AUTOMOTIVE|TYRE|TRAVEL|TOURS"
    r")\b",
    re.IGNORECASE,
)

# Business Registration Number (BRN / ROC / ROB / SSM) patterns in Malaysia
_BRN_PATTERNS = re.compile(
    r"("
    r"\b\d{5,10}\s*[-/]?\s*[A-Za-z]\b|"  # Old SSM e.g. 123456-X, 001234567-T
    r"\b(19|20)\d{2}\s*(?:01|02|03|04|05|06)\s*\d{6}\b|"  # New 12-digit SSM (e.g. 201901012345)
    r"\bLLP\d{5,9}(?:-[A-Z]{3})?\b|"      # Limited Liability Partnership
    r"\bROC\b|\bROB\b|\bSSM\b|"           # Direct registration keywords
    r"\b(CO|COMPANY|REG|BUSINESS)\s*(?:REGISTRATION|REGIST|NO|NUM)?\.?\s*:\s*[A-Z0-9-]+"
    r")",
    re.IGNORECASE,
)

# Hyphenated Malaysian Individual NRIC: YYMMDD-PB-####
_HYPHEN_NRIC_RE = re.compile(r"^\d{6}-\d{2}-\d{4}$")


def is_malaysian_nric(doc_no: str | None) -> bool:
    """
    Validate if a string strictly conforms to a Malaysian Individual NRIC.
    Validates date part (MM: 01-12, DD: 01-31).
    """
    if not doc_no:
        return False
    cleaned = doc_no.strip()
    if _HYPHEN_NRIC_RE.fullmatch(cleaned):
        digits = cleaned.replace("-", "")
    elif len(cleaned) == 12 and cleaned.isdigit():
        digits = cleaned
    else:
        return False

    month = int(digits[2:4])
    day = int(digits[4:6])
    # Month must be 1..12 and Day must be 1..31
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return False

    # Check if this 12-digit number actually matches a new SSM corporate registration (starts with 2019-2026 with SSM entity codes 01-06)
    year_prefix = int(digits[0:4])
    if 2019 <= year_prefix <= 2030 and digits[4:6] in {"01", "02", "03", "04", "05", "06"}:
        # In this range, digits[2:4] would have been 19..30 which is already > 12 and returned False above!
        return False

    return True


def is_corporate_name(name: str | None) -> bool:
    """Check if a customer name denotes a corporate entity, business, or organisation."""
    if not name or not name.strip():
        return False
    cleaned = " ".join(name.strip().upper().split())
    if _CORP_PATTERNS.search(cleaned):
        return True
    return False


def is_business_registration(doc_no: str | None) -> bool:
    """Check if an identity or registration string is a Business Registration Number (BRN)."""
    if not doc_no or not doc_no.strip():
        return False
    cleaned = doc_no.strip()
    # If explicitly matching a valid individual NRIC, it's not a company BRN
    if is_malaysian_nric(cleaned):
        return False
    if _BRN_PATTERNS.search(cleaned):
        return True
    # If it's a 12-digit number starting with 2019..2030, it is a new SSM company registration
    digits_only = re.sub(r"\D", "", cleaned)
    if len(digits_only) == 12 and (digits_only.startswith("201") or digits_only.startswith("202")):
        return True
    return False


# Non-Saloon vehicle models in Malaysia (MPVs, SUVs, 4x4, Pickups, Crossovers, Vans)
_NON_SALOON_PATTERNS = re.compile(
    r"\b("
    # MPVs / People Movers / Vans
    r"ALZA|EXORA|INNOVA|VELLFIRE|ALPHARD|SERENA|AVANZA|VELOZ|SIENTA|CARNIVAL|STARIA|"
    r"VOXY|NOAH|ESQUIRE|ESTIMA|WISH|STREAM|FREED|BIANTE|ERTIGA|LIVINA|GRAND\s+LIVINA|"
    r"LODGY|SPACIO|TOURAN|SHARAN|ODYSSEY|CITAN|TRAVET|HIACE|URVAN|VAN|MPV|"
    # SUVs / Crossovers
    r"ATIVA|ARUZ|X50|X70|X90|CR-?V|HR-?V|BR-?V|WR-?V|ZR-?V|FORTUNER|HARRIER|"
    r"COROLLA\s+CROSS|CROSS|CX-?3|CX-?5|CX-?8|CX-?30|CX-?60|CX-?90|TUCSON|SANTA\s+FE|"
    r"CRETA|KONA|SPORTAGE|SORENTO|SELTOS|FORESTER|XV|OUTBACK|CROSSTREK|RAV4|KICKS|"
    r"X-?TRAIL|TIGUAN|TOUAREG|Q3|Q5|Q7|GLA|GLB|GLC|GLE|GLS|X1|X3|X4|X5|X6|X7|"
    r"MACAN|CAYENNE|URUS|DEFENDER|DISCOVERY|RANGE\s+ROVER|EVOQUE|VELAR|CHEROKEE|"
    r"WRANGLER|COMPASS|RENEGADE|SUV|"
    # 4x4 / Pickups
    r"D-?MAX|HILUX|RANGER|TRITON|NAVARA|BT-?50|GLADIATOR|AMAROK|COLORADO|4X4|4WD|PICKUP"
    r")\b",
    re.IGNORECASE,
)


def is_non_saloon_model(car_model_text: str | None) -> bool:
    """Check if a vehicle model is a Non-Saloon (MPV, SUV, 4x4, Pickup, Van)."""
    if not car_model_text or not car_model_text.strip():
        return False
    return bool(_NON_SALOON_PATTERNS.search(car_model_text.strip()))


def classify_client_entity(
    customer_name: str | None,
    ic_or_brn: str | None = None,
    ai_client_type: str | None = None,
    current_vehicle_type: str | None = None,
    car_model: str | None = None,
) -> Tuple[str, str]:
    """
    Classify customer into 'Company' or 'Private' and resolve the appropriate vehicle type.

    Returns:
        (entity_type, resolved_vehicle_type)
        e.g. ("Company", "NonSaloonCar"), ("Private", "NonSaloonCar"),
             ("Company", "CompanyCar"), ("Private", "Car"), ("Company", "CompanyMotorcycle"), etc.
    """
    name_str = (customer_name or "").strip()
    doc_str = (ic_or_brn or "").strip()
    ai_type = (ai_client_type or "").strip().capitalize()
    curr_vtype = (current_vehicle_type or "Car").strip()

    # Determine base vehicle category (Motorcycle, Lorry, NonSaloonCar, or Car)
    curr_vtype_lower = curr_vtype.lower()
    if is_non_saloon_model(car_model) or "nonsaloon" in curr_vtype_lower or "non-saloon" in curr_vtype_lower or "suv" in curr_vtype_lower or "mpv" in curr_vtype_lower:
        base_category = "NonSaloonCar"
    elif "motor" in curr_vtype_lower or "bike" in curr_vtype_lower:
        base_category = "Motorcycle"
    elif "lorry" in curr_vtype_lower or "truck" in curr_vtype_lower or "commercial" in curr_vtype_lower:
        base_category = "Lorry"
    elif "other" in curr_vtype_lower:
        base_category = "Others"
    else:
        base_category = "Car"

    is_company = False

    # 1. Deterministic check on customer name (highest authority)
    if is_corporate_name(name_str):
        is_company = True

    # 2. Check on IC or BRN string
    elif is_business_registration(doc_str):
        is_company = True

    # 3. AI classification cross-confirmation
    elif ai_type == "Company":
        # Accept AI classification unless customer_name is explicitly formatted as personal individual name with personal NRIC
        if not is_malaysian_nric(doc_str):
            is_company = True

    # 4. Check if current_vehicle_type explicitly indicated Company
    elif "company" in curr_vtype_lower or "corp" in curr_vtype_lower:
        is_company = True

    if is_company:
        entity_type = "Company"
        if base_category == "NonSaloonCar":
            resolved_vtype = "NonSaloonCar"
        elif base_category == "Car":
            resolved_vtype = "CompanyCar"
        elif base_category == "Motorcycle":
            resolved_vtype = "CompanyMotorcycle"
        elif base_category == "Lorry":
            resolved_vtype = "Lorry"
        else:
            resolved_vtype = "CompanyCar"
    else:
        entity_type = "Private"
        if base_category == "NonSaloonCar":
            resolved_vtype = "NonSaloonCar"
        elif base_category == "Car":
            resolved_vtype = "Car"
        elif base_category == "Motorcycle":
            resolved_vtype = "Motorcycle"
        elif base_category == "Lorry":
            resolved_vtype = "Lorry"
        else:
            resolved_vtype = "Car"

    return entity_type, resolved_vtype
