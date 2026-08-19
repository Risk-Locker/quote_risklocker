"""Normalization and validation for draft fields."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d")


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
    match = re.search(r"\d+", value)
    if not match:
        return False, "Please check this value."
    return (int(match.group(0)) > 0, None)
