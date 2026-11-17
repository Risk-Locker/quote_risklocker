"""Normalization and validation for draft fields."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%Y/%m/%d",
    "%d %b %Y",
    "%d-%b-%Y",
    "%d %B %Y",
    "%d-%B-%Y",
)


def normalize_money(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"(?i)\bRM\b", "", value).replace(",", "").strip()
    cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
    try:
        amount = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None
    if amount < 0:
        return None
    return f"{amount:.2f}"


def normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def validate_vehicle_number(value: str | None) -> tuple[bool, str | None]:
    if not value:
        return False, "Vehicle number is required."
    cleaned = re.sub(r"\s+", "", value.upper())
    if re.fullmatch(r"[A-Z]{1,3}[0-9]{1,4}[A-Z]?", cleaned):
        return True, None
    return False, "Please check this value."


def validate_money(value: str | None) -> tuple[bool, str | None]:
    normalized = normalize_money(value)
    if normalized is None:
        return False, "Please check this value."
    return Decimal(normalized) >= 0, None


def validate_date(value: str | None) -> tuple[bool, str | None]:
    if normalize_date(value) is None:
        return False, "Please check this value."
    return True, None


def validate_date_range(start: str | None, end: str | None) -> tuple[bool, str | None]:
    start_norm = normalize_date(start)
    end_norm = normalize_date(end)
    if not start_norm or not end_norm:
        return False, "Please check this value."
    if date.fromisoformat(end_norm) <= date.fromisoformat(start_norm):
        return False, "Please check this value."
    return True, None


def validate_ncd(value: str | None) -> tuple[bool, str | None]:
    if value in (None, ""):
        return True, None
    match = re.search(r"\d+(?:\.\d+)?", value)
    if not match:
        return False, "Please check this value."
    number = Decimal(match.group(0))
    if not (Decimal("0") <= number <= Decimal("55")):
        return False, "Please check this value."
    return True, None


def validate_engine_cc(value: str | None) -> tuple[bool, str | None]:
    if value in (None, ""):
        return True, None
    s = str(value).strip()
    lower = s.lower()
    match = re.search(r"\d+(?:\.\d+)?", s)
    if not match:
        return False, "Please check this value."
    try:
        num = float(match.group(0))
    except ValueError:
        return False, "Please check this value."
    if num <= 0:
        return False, "Please check this value."
    # Commercial weights (KG / TON): plausible up to 100,000 KG / 100 TON
    if re.search(r"\b(?:kg|kilograms?|ton(?:s|nes?)?|mt)\b", lower):
        cap_max = 100.0 if re.search(r"\b(?:ton(?:s|nes?)?|mt)\b", lower) else 100_000.0
        return (num <= cap_max, None if num <= cap_max else "Please check commercial weight value.")
    # Electric Vehicles (kW / W)
    if re.search(r"(?<![a-z])(?:k?w|kilowatt|watt(?:s)?)(?![a-z])", lower):
        if "kw" in lower or "kilowatt" in lower:
            return (num <= 2_500.0, None if num <= 2_500.0 else "Please check EV power (kW).")
        return (num <= 2_500_000.0, None if num <= 2_500_000.0 else "Please check EV power (W).")
    # Standard combustion engine CC: plausible range <= 16,000 CC (lorries <= 16L, cars <= 8L)
    if num > 16_000.0:
        return False, "Implausible engine capacity (likely serial/ID number)."
    return True, None


def normalize_valuation_type(value: str | None) -> str:
    """Normalize valuation type considering English and Malay terms."""
    if not value:
        return "Market Value"
    s = value.strip().lower()
    if "agreed" in s or "dipersetujui" in s:
        return "Agreed Value"
    if "market" in s or "pasaran" in s:
        return "Market Value"
    return "Market Value"

