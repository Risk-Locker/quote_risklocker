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

# Canonical 17 Saloon Electric Vehicle (EV) models in Malaysia
_SALOON_EV_PATTERNS = re.compile(
    r"\b("
    r"CLA\s*EQ|EQE\b(?!(\s*SUV|\s*4MATIC\s*SUV))|AMG\s*EQS|AMG\s*EQE|EQS\b(?!(\s*SUV|\s*4MATIC\s*SUV))|"
    r"I4\b|I5\b|I4\s*M50|I7\b|"
    r"SEAL\s*6|SEAL\b(?!ION)|"
    r"ES90\b|"
    r"DONGFENG\s*007|\b007\b|"
    r"AION\s*ES|"
    r"IONIQ\s*6\s*N|IONIQ\s*6\b|"
    r"MODEL\s*3\b|MODEL\s*S\b|"
    r"TAYCAN\b(?!(\s*CROSS|\s*SPORT\s*TURISMO))|"
    r"ID\.3\b|ID\.7\b|POLESTAR\s*2\b|ZEEKR\s*001\b|ZEEKR\s*007\b|"
    r"EMEYA\b"
    r")\b",
    re.IGNORECASE,
)

# Canonical 70 Non-Saloon Electric Vehicle (EV) models in Malaysia (SUVs, MPVs, Crossovers, Pickups, Vans)
_NON_SALOON_EV_PATTERNS = re.compile(
    r"\b("
    r"EQA\b|EQE\s*SUV|EQV\b|G-?CLASS\s*EV|MAYBACH\s*EQS\s*SUV|EQS\s*SUV|"
    r"IX1\s*L|IX1\b|IX2\b|IX3\b|IX\b|"
    r"ATTO\s*2|M6\b|ATTO\s*3|SEALION\s*7|"
    r"EX30\b|EC40\b|EX90\b|"
    r"DONGFENG\s*BOX|DONGFENG\s*VIGO|\bBOX\b|\bVIGO\b|"
    r"MG\s*4|MG\s*S5|\bS5\b|CYBERSTER\b|"
    r"MINI\s*ELECTRIC|ACEMAN\b|COUNTRYMAN\s*EV|"
    r"MACAN\s*ELECTRIC|CAYENNE\s*ELECTRIC|CAYENNE\s*COUPE\s*ELECTRIC|TAYCAN\s*CROSS\s*TURISMO|"
    r"URBAN\s*CRUISER\s*EV|BZ4X\b|HILUX\s*EV|"
    r"ZEEKR\s*X|ZEEKR\s*7X|ZEEKR\s*009|\b7X\b|\b009\b|"
    r"SMART\s*#1|SMART\s*#3|SMART\s*#5|\b#1\b|\b#3\b|\b#5\b|"
    r"AION\s*Y\s*PLUS|Y\s*PLUS\b|"
    r"Q8\s*E-?TRON|E-?TRON\b|"
    r"DENZA\s*D9|DENZA\s*Z9|D9\s*EV|Z9\s*GT\s*EV|"
    r"IONIQ\s*5\s*N|IONIQ\s*5\b|KONA\s*ELECTRIC|"
    r"LEAPMOTOR\s*B10|LEAPMOTOR\s*C10|\bB10\b|\bC10\b|"
    r"ELETRE\b|"
    r"ETERRON\s*9|MIFA\s*9|MIFA\s*7|"
    r"EMAS\s*5|E-?MAS\s*5|EMAS\s*7|E-?MAS\s*7|"
    r"MODEL\s*Y\b|MODEL\s*X\b|"
    r"XPENG\s*G6|XPENG\s*X9|\bG6\b|\bX9\b|"
    r"ICAUR\s*03|ICAUR\s*V23|ICAR\s*03|ICAR\s*V23|\bV23\b|"
    r"OMODA\s*E5\b|"
    r"ORA\s*GOOD\s*CAT|GOOD\s*CAT\b|ORA\s*07|"
    r"E:?N1\b|"
    r"JAC\s*T9\s*EV|T9\s*EV|"
    r"EV9\b|EV6\b|"
    r"RZ450E|\bRZ\b|"
    r"NETA\s*X|NETA\s*V|"
    r"LEAF\b|"
    r"JACOO\s*J5\s*EV|J5\s*EV|J7\s*EV|"
    r"QV-?E\b|"
    r"ZOE\b|"
    r"SERES\s*3|SERES\s*5|"
    r"EVITARA\b|E-?VITARA\b|"
    r"BINGO\s*EV|BINGO\b|AIR\s*EV"
    r")\b",
    re.IGNORECASE,
)

# Canonical 13 Electric Motorcycle models in Malaysia
_ELECTRIC_MOTO_PATTERNS = re.compile(
    r"\b("
    r"BLUESHARK|R1\s*LITE|\bR1\b|SOLO\s*1C|SOLO\s*2|"
    r"EZI\s*TS1|EZI\s*RAY-?01|TS1\b|RAY-?01\b|"
    r"YADEA|E8S\s*PRO|GT\s*20|RS20\b|VELAX\b|"
    r"ZEEHO|AE4\b|AE8S\+?|"
    r"QJ\s*MOTOR\s*E-?LTR|E-?LTR\b"
    r")\b",
    re.IGNORECASE,
)

# Generic EV indicator tokens
_GENERIC_EV_INDICATORS = re.compile(
    r"\b(EV|BEV|ZEV|ELECTRIC\s*VEHICLE|FULL\s*ELECTRIC|BATTERY\s*ELECTRIC|MOTOR\s*OUTPUT)\b",
    re.IGNORECASE,
)


def is_non_saloon_model(car_model_text: str | None) -> bool:
    """Check if a vehicle model is a Non-Saloon (MPV, SUV, 4x4, Pickup, Van)."""
    if not car_model_text or not car_model_text.strip():
        return False
    return bool(_NON_SALOON_PATTERNS.search(car_model_text.strip()))


def classify_vehicle_ev_status(
    car_brand: str | None,
    car_model: str | None,
    capacity_str: str | None = None,
) -> Tuple[bool, str | None]:
    """
    Classify whether a vehicle is an Electric Vehicle (EV) and determine its EV category.

    Returns:
        (is_ev, ev_category)
        ev_category: "EVSaloonCar" | "EVNonSaloonCar" | "EVMotorcycle" | None
    """
    text_comb = f"{car_brand or ''} {car_model or ''}".strip().upper()
    cap_text = (capacity_str or "").strip().upper()

    if not text_comb and not cap_text:
        return False, None

    # 1. Check Electric Motorcycle models first
    if _ELECTRIC_MOTO_PATTERNS.search(text_comb):
        return True, "EVMotorcycle"

    # 2. Check canonical Saloon EV models (17 verified models)
    if _SALOON_EV_PATTERNS.search(text_comb):
        return True, "EVSaloonCar"

    # 3. Check canonical Non-Saloon EV models (70 verified models)
    if _NON_SALOON_EV_PATTERNS.search(text_comb):
        return True, "EVNonSaloonCar"

    # 4. Check explicit EV indicators in model text or capacity text (e.g. "KW", "WATT")
    has_ev_token = bool(_GENERIC_EV_INDICATORS.search(text_comb))
    has_kw_token = "KW" in cap_text or "WATT" in cap_text

    if has_ev_token or has_kw_token:
        # Determine body style: Non-Saloon vs Saloon vs Motorcycle
        if "MOTOR" in text_comb or "BIKE" in text_comb or "SCOOTER" in text_comb:
            return True, "EVMotorcycle"
        if is_non_saloon_model(text_comb):
            return True, "EVNonSaloonCar"
        return True, "EVSaloonCar"

    return False, None


def classify_client_entity(
    customer_name: str | None,
    ic_or_brn: str | None = None,
    ai_client_type: str | None = None,
    current_vehicle_type: str | None = None,
    car_model: str | None = None,
    car_brand: str | None = None,
    capacity_str: str | None = None,
) -> Tuple[str, str]:
    """
    Classify customer into 'Company' or 'Private' and resolve the appropriate vehicle type.

    Returns:
        (entity_type, resolved_vehicle_type)
        e.g. ("Company", "NonSaloonCar"), ("Private", "NonSaloonCar"),
             ("Company", "CompanyCar"), ("Private", "Car"),
             ("Company", "EVSaloonCar"), ("Private", "EVSaloonCar"),
             ("Company", "EVNonSaloonCar"), ("Private", "EVNonSaloonCar"),
             ("Company", "EVMotorcycle"), ("Private", "EVMotorcycle"), etc.
    """
    name_str = (customer_name or "").strip()
    doc_str = (ic_or_brn or "").strip()
    ai_type = (ai_client_type or "").strip().capitalize()
    curr_vtype = (current_vehicle_type or "Car").strip()

    # Check EV status first
    is_ev, ev_category = classify_vehicle_ev_status(car_brand, car_model, capacity_str)
    curr_vtype_lower = curr_vtype.lower()

    if is_ev and ev_category:
        base_category = ev_category
    elif "evsaloon" in curr_vtype_lower:
        base_category = "EVSaloonCar"
    elif "evnonsaloon" in curr_vtype_lower or ("ev" in curr_vtype_lower and ("suv" in curr_vtype_lower or "non" in curr_vtype_lower)):
        base_category = "EVNonSaloonCar"
    elif "evmotor" in curr_vtype_lower:
        base_category = "EVMotorcycle"
    elif is_non_saloon_model(car_model) or "nonsaloon" in curr_vtype_lower or "non-saloon" in curr_vtype_lower or "suv" in curr_vtype_lower or "mpv" in curr_vtype_lower:
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
        if not is_malaysian_nric(doc_str):
            is_company = True

    # 4. Check if current_vehicle_type explicitly indicated Company
    elif "company" in curr_vtype_lower or "corp" in curr_vtype_lower:
        is_company = True

    if is_company:
        entity_type = "Company"
        if base_category in {"EVSaloonCar", "EVNonSaloonCar", "EVMotorcycle"}:
            resolved_vtype = base_category
        elif base_category == "NonSaloonCar":
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
        if base_category in {"EVSaloonCar", "EVNonSaloonCar", "EVMotorcycle"}:
            resolved_vtype = base_category
        elif base_category == "NonSaloonCar":
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
