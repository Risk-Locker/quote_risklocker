"""Identity Normalization Service for Malaysian Customer & Corporate Entities.
Provides immutable government ID normalization (NRIC, Passport, SSM BRN) and canonical name standardization.
"""

from __future__ import annotations

import re
from typing import Any

# SSM / Corporate Legal Suffix Standardization Patterns
_CORP_SUFFIX_REPLACEMENTS = [
    (re.compile(r"\bSENDIRIAN\s+BERHAD\b", re.IGNORECASE), "SDN BHD"),
    (re.compile(r"\bSDN\s*\.?\s*BHD\.?\b", re.IGNORECASE), "SDN BHD"),
    (re.compile(r"\bSDNBHD\b", re.IGNORECASE), "SDN BHD"),
    (re.compile(r"\bBERHAD\b", re.IGNORECASE), "BHD"),
    (re.compile(r"\bBHD\.?\b", re.IGNORECASE), "BHD"),
    (re.compile(r"\bENT\.?\b", re.IGNORECASE), "ENTERPRISE"),
    (re.compile(r"\bENTERPRISE\b", re.IGNORECASE), "ENTERPRISE"),
    (re.compile(r"\bPLT\.?\b", re.IGNORECASE), "PLT"),
    (re.compile(r"\bLIMITED\b", re.IGNORECASE), "LTD"),
    (re.compile(r"\bLTD\.?\b", re.IGNORECASE), "LTD"),
    (re.compile(r"\bCORPORATION\b", re.IGNORECASE), "CORP"),
    (re.compile(r"\bCORP\.?\b", re.IGNORECASE), "CORP"),
    (re.compile(r"\bCOMPANY\b", re.IGNORECASE), "CO"),
    (re.compile(r"\bCO\.?\b", re.IGNORECASE), "CO"),
]

# Old SSM format: 5 to 9 digits followed by 1 letter (e.g. 123456-X, 001234567-T)
_OLD_SSM_RE = re.compile(r"^\d{5,9}[A-Z]$")

# PB (Place of Birth) state codes for Malaysian NRIC
_NRIC_STATE_CODES: dict[str, str] = {
    "01": "Johor", "21": "Johor", "22": "Johor", "23": "Johor", "24": "Johor",
    "02": "Kedah", "25": "Kedah", "26": "Kedah", "27": "Kedah",
    "03": "Kelantan", "28": "Kelantan", "29": "Kelantan",
    "04": "Melaka", "30": "Melaka",
    "05": "Negeri Sembilan", "31": "Negeri Sembilan", "59": "Negeri Sembilan",
    "06": "Pahang", "32": "Pahang", "33": "Pahang",
    "07": "Pulau Pinang", "34": "Pulau Pinang", "35": "Pulau Pinang",
    "08": "Perak", "36": "Perak", "37": "Perak", "38": "Perak", "39": "Perak",
    "09": "Perlis", "40": "Perlis",
    "10": "Selangor", "41": "Selangor", "42": "Selangor", "43": "Selangor", "44": "Selangor",
    "11": "Terengganu", "45": "Terengganu", "46": "Terengganu",
    "12": "Sabah", "47": "Sabah", "48": "Sabah", "49": "Sabah",
    "13": "Sarawak", "50": "Sarawak", "51": "Sarawak", "52": "Sarawak", "53": "Sarawak",
    "14": "Wilayah Persekutuan Kuala Lumpur", "54": "Wilayah Persekutuan Kuala Lumpur", "55": "Wilayah Persekutuan Kuala Lumpur", "56": "Wilayah Persekutuan Kuala Lumpur", "57": "Wilayah Persekutuan Kuala Lumpur",
    "15": "Wilayah Persekutuan Labuan", "58": "Wilayah Persekutuan Labuan",
    "16": "Wilayah Persekutuan Putrajaya",
}


def parse_nric_details(nric: str | None) -> dict[str, Any]:
    """Parse 12-digit Malaysian NRIC YYMMDD-PB-###G into demographic details.

    Returns dict with:
        - valid: bool
        - formatted: str (e.g. 700322-08-5316)
        - birth_date: str (YYYY-MM-DD)
        - age: int
        - gender: 'male' | 'female'
        - state: str (Malaysian state of birth)
    """
    if not nric:
        return {"valid": False}
    digits, id_type = normalize_government_id(nric)
    if id_type != "nric" or len(digits) != 12 or not digits.isdigit():
        return {"valid": False}

    yy = int(digits[0:2])
    mm = int(digits[2:4])
    dd = int(digits[4:6])
    pb = digits[6:8]
    g = int(digits[11])

    # Reference year: 2026
    from datetime import date
    current_year = date.today().year
    century_cutoff = current_year % 100
    birth_year = (2000 + yy) if yy <= century_cutoff else (1900 + yy)

    try:
        bdate = date(birth_year, mm, dd)
    except ValueError:
        return {"valid": False}

    today = date.today()
    age = today.year - bdate.year - ((today.month, today.day) < (bdate.month, bdate.day))
    gender = "male" if g % 2 != 0 else "female"
    state = _NRIC_STATE_CODES.get(pb, "Malaysia")
    formatted = f"{digits[0:6]}-{digits[6:8]}-{digits[8:12]}"

    return {
        "valid": True,
        "nric": digits,
        "formatted": formatted,
        "birth_date": bdate.isoformat(),
        "age": age,
        "gender": gender,
        "state": state,
    }


def normalize_government_id(raw_id: str | None) -> tuple[str, str]:
    """
    Normalize an identification string (NRIC, Passport, or SSM BRN).
    Strips hyphens, slashes, spaces, and punctuation.
    Returns:
        (normalized_id, id_type)
        where id_type is one of: 'nric', 'passport', 'brn_new', 'brn_old', 'llp', 'unknown'
    """
    if not raw_id:
        return "", "unknown"

    raw_str = raw_id.strip()

    # Reject internal placeholder IDs
    if raw_str.upper().startswith("PENDING-") or "PENDING-" in raw_str.upper():
        return "", "unknown"

    # Pre-clean common parenthetical annotations: (new), (baru), (old), (lama), etc.
    cleaned_note = re.sub(r"(?i)\s*\((?:new|baru|old|lama|c|co)\)\s*", "", raw_str).strip()

    # Direct 12-digit NRIC extraction if present anywhere (e.g. 700322-08-5316 or 700322085316)
    m_nric = re.search(r"\b(\d{6})[-\s]?(\d{2})[-\s]?(\d{4})\b", cleaned_note)
    if m_nric:
        nric_digits = f"{m_nric.group(1)}{m_nric.group(2)}{m_nric.group(3)}"
        mm = int(nric_digits[2:4])
        dd = int(nric_digits[4:6])
        if 1 <= mm <= 12 and 1 <= dd <= 31:
            return nric_digits, "nric"

    cleaned = re.sub(r"[^A-Za-z0-9]", "", cleaned_note.upper())
    if not cleaned:
        return "", "unknown"

    # 1. Limited Liability Partnership: starts with LLP
    if cleaned.startswith("LLP"):
        return cleaned, "llp"

    # 2. Check for 12 digits: Could be New SSM (2019+) or Malaysian NRIC
    if len(cleaned) == 12 and cleaned.isdigit():
        year_prefix = int(cleaned[0:4])
        entity_code = cleaned[4:6]
        # New SSM company format starts with 2019..2035 with entity codes 01..06
        if 2019 <= year_prefix <= 2035 and entity_code in {"01", "02", "03", "04", "05", "06"}:
            return cleaned, "brn_new"

        # Check if valid NRIC (Month 01-12, Day 01-31)
        month = int(cleaned[2:4])
        day = int(cleaned[4:6])
        if 1 <= month <= 12 and 1 <= day <= 31:
            return cleaned, "nric"

        # Default for 12 digits
        return cleaned, "nric"

    # 3. Old SSM Business Registration Number (e.g. 123456-X, 001234567-T)
    if _OLD_SSM_RE.match(cleaned):
        return cleaned, "brn_old"

    # 4. Passport detection:
    # Foreign passports almost always start with 1-2 letters followed by numbers (e.g. A12345678, E8765432, K1234567)
    if cleaned[0].isalpha() and len(cleaned) >= 6:
        # Check if it has letters inside but isn't just an old SSM
        return cleaned, "passport"

    # If it ends with a letter after numbers, it is likely an old SSM (e.g. 123456X)
    if cleaned[-1].isalpha() and cleaned[:-1].isdigit():
        return cleaned, "brn_old"

    # Default fallback
    return cleaned, "unknown"


def normalize_canonical_name(name: str | None) -> str:
    """
    Standardize customer or company name into canonical form.
    - Strips all punctuation (. , / \\ - _ ( ) " ')
    - Converts to UPPERCASE
    - Standardizes corporate legal suffixes (SDN BHD, BHD, ENTERPRISE, etc.)
    - Collapses multiple whitespace to single space
    Example:
        'PL INKJET sdn bhd' -> 'PL INKJET SDN BHD'
        'PL Inkjet SDN BHD.' -> 'PL INKJET SDN BHD'
        'PL INKJET SDN. BHD.' -> 'PL INKJET SDN BHD'
    """
    if not name:
        return ""

    # Remove all punctuation and symbols
    cleaned = re.sub(r"[\.,/\\_\-\(\)\[\]\{\}\"\'`@#\$\%^&\*~:;!?|]", " ", name.strip().upper())

    # Standardize corporate suffixes
    for pattern, replacement in _CORP_SUFFIX_REPLACEMENTS:
        cleaned = pattern.sub(f" {replacement} ", cleaned)

    # Collapse multiple whitespaces
    tokens = cleaned.split()
    return " ".join(tokens)


def is_corporate_entity(name: str | None, id_type: str | None = None) -> bool:
    """
    Determine if the entity is a company/business or an individual.
    """
    if id_type in ("brn_new", "brn_old", "llp"):
        return True
    if id_type in ("nric", "passport"):
        return False

    if not name:
        return False

    norm = normalize_canonical_name(name)
    corporate_keywords = {
        "SDN", "BHD", "ENTERPRISE", "TRADING", "PLT", "LTD", "CORP", "CO",
        "HOLDINGS", "GROUP", "VENTURES", "LOGISTICS", "SERVICES", "ENGINEERING",
        "MOTORS", "MANAGEMENT", "RESOURCES", "TRANSPORT", "AGENCY", "PERUSAHAAN",
        "SYARIKAT", "KOPERASI", "YAYASAN", "AUTOMOTIVE", "TOURS", "TRAVEL"
    }
    words = set(norm.split())
    return bool(words.intersection(corporate_keywords))
