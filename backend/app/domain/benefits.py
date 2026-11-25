"""Typed benefit values and canonical quotation decision states."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ReviewedBenefitState(StrEnum):
    CURRENT = "current"
    AVAILABLE_ADDON = "available_addon"
    REMOVED = "removed"
    SUPERSEDED = "superseded"
    UNRESOLVED = "unresolved"


class CostStatus(StrEnum):
    INCLUDED = "included"
    PAID = "paid"
    FOC = "foc"
    UNKNOWN = "unknown"


def normalize_cost_status(val: object, default: CostStatus = CostStatus.UNKNOWN) -> CostStatus:
    """Safely normalizes cost status strings including client aliases (optional, free, etc.)."""
    if val is None:
        return default
    clean = str(val).strip().lower()
    if not clean:
        return default
    if clean in ("optional", "extra", "add_on", "addon", "paid", "chargeable"):
        return CostStatus.PAID
    if clean in ("free", "foc", "waived", "complimentary"):
        return CostStatus.FOC
    if clean in ("included", "built_in", "standard"):
        return CostStatus.INCLUDED
    if clean == "unknown":
        return CostStatus.UNKNOWN
    try:
        return CostStatus(clean)
    except ValueError:
        return default


class SourceLineDisposition(StrEnum):
    UNRESOLVED = "unresolved"
    MAPPED = "mapped"
    CUSTOM = "custom"
    SOURCE_ONLY = "source_only"
    OMITTED = "omitted"


class MoneyAmount(BaseModel):
    amount: Decimal = Field(ge=Decimal("0"))
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")


class BenefitValue(BaseModel):
    """Validated tagged value; fields not relevant to the selected tag remain null."""

    type: Literal[
        "money",
        "distance",
        "percentage",
        "per_day",
        "occurrence",
        "duration",
        "count",
        "region",
        "boolean",
        "enum",
        "formula",
        "package_plan",
        "custom",
        "text",
        "string",
    ]
    value: Decimal | int | str | bool | None = None
    unit: str | None = Field(default=None, max_length=40)
    region: str | None = Field(default=None, max_length=160)
    unlimited: bool = False
    currency: str | None = Field(default=None, min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    semantic_role: str | None = Field(default=None, max_length=80)
    basis: str | None = Field(default=None, max_length=80)
    cap: MoneyAmount | None = None
    premium: MoneyAmount | None = None
    max_days: int | None = Field(default=None, ge=1, le=366)
    aggregate_cap: Decimal | None = Field(default=None, ge=Decimal("0"))
    per_event: Decimal | int | None = None
    occurrences: int | None = Field(default=None, ge=0)
    expression: str | None = Field(default=None, max_length=1_000)
    variables: dict[str, str] = Field(default_factory=dict)
    enum_key: str | None = Field(default=None, max_length=120)
    plan_key: str | None = Field(default=None, max_length=120)
    display_text: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=1_000)
    icon_hint: str | None = Field(default=None, max_length=80)
    label: str | None = Field(default=None, max_length=255)
    hideCoverage: bool | None = False
    hideCost: bool | None = False
    hide_limit: bool | None = None
    hide_price: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_numeric_value(cls, data):
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if normalized.get("type") in {"money", "distance", "percentage", "per_day"}:
            value = normalized.get("value")
            if value is not None and not isinstance(value, bool):
                if isinstance(value, str):
                    value = value.replace(",", "").strip()
                try:
                    normalized["value"] = Decimal(str(value))
                except Exception:
                    raise ValueError("Numeric benefit values must be valid numbers.")
        return normalized

    @model_validator(mode="after")
    def validate_tagged_value(self) -> "BenefitValue":
        if self.type == "distance":
            if not self.unit:
                raise ValueError("Distance requires a unit.")
            if self.unlimited and self.value is not None:
                raise ValueError("Unlimited distance cannot also have a finite value.")
            if not self.unlimited and self.value is None:
                raise ValueError("Finite distance requires a value.")
        elif self.type == "money":
            if self.value is None or not self.currency:
                raise ValueError("Money requires value and currency.")
            if not self.semantic_role:
                self.semantic_role = "limit"
        elif self.type == "percentage":
            if self.value is None or not self.basis:
                raise ValueError("Percentage requires value and basis.")
        elif self.type == "per_day":
            if self.value is None or not self.currency or self.max_days is None:
                raise ValueError("Per-day allowance requires value, currency, and maximum days.")
        elif self.type == "formula":
            if not (self.expression or "").strip():
                raise ValueError("Formula requires an expression.")
        elif self.type in {"text", "string"}:
            # Allow empty display_text when user explicitly clears/hides coverage or stores description overrides
            pass
        elif self.type == "region" and not self.region:
            raise ValueError("Region values require a region.")
        elif self.type == "enum" and not self.enum_key:
            raise ValueError("Enum values require an enum key.")
        elif self.type == "package_plan" and not self.plan_key:
            raise ValueError("Package-plan values require a plan key.")
        elif self.type in {"occurrence", "duration", "count", "boolean"} and self.value is None:
            raise ValueError(f"{self.type} requires a value.")
        elif self.type == "custom" and not (self.display_text and self.display_text.strip()):
            raise ValueError("Custom value requires display_text.")
        return self


def format_coverage_value(val: object, coverage_format: str | None = None) -> str:
    """Format benefit coverage according to configured unit/format (RM, KM, or text)."""
    if val is None:
        return ""
    text_val = str(val).strip()
    if not text_val:
        return ""

    fmt = (coverage_format or "").strip().upper()
    import re
    if fmt == "RM":
        clean_str = re.sub(r"^(?:RM|MYR)\s*", "", text_val, flags=re.IGNORECASE).strip()
        clean_num_str = clean_str.replace(",", "")
        try:
            num = float(clean_num_str)
            if num.is_integer():
                return f"RM {int(num):,}"
            return f"RM {num:,.2f}"
        except ValueError:
            m = re.search(r"(\d+(?:,\d+)*(?:\.\d+)?)", text_val)
            if m:
                try:
                    num = float(m.group(1).replace(",", ""))
                    return f"RM {int(num):,}" if num.is_integer() else f"RM {num:,.2f}"
                except ValueError:
                    pass
            return text_val

    elif fmt == "KM":
        if "unlimited" in text_val.lower():
            return "Unlimited KM"
        m = re.search(r"(\d+(?:,\d+)*(?:\.\d+)?)", text_val)
        if m:
            try:
                num = float(m.group(1).replace(",", ""))
                return f"{int(num):,} KM" if num.is_integer() else f"{num:,.0f} KM"
            except ValueError:
                pass
        return f"{text_val} KM" if not text_val.lower().endswith("km") else text_val

    return text_val


_NON_INFORMATIVE_LIMIT_TOKENS = {
    "",
    "included",
    "included standard cover",
    "standard",
    "yes",
    "true",
    "selected",
    "optional",
    "foc",
    "as quoted",
    "none",
    "null",
    "nil",
    "-",
    "—",
}


def _parse_positive_money(raw: object) -> float | None:
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, dict):
        raw = raw.get("amount") if raw.get("amount") is not None else raw.get("value")
    s = re.sub(r"[^0-9.]", "", str(raw or ""))
    if not s:
        return None
    try:
        val = float(s)
        return val if val > 0 else None
    except ValueError:
        return None


def benefit_auto_coverage_domain(concept_key: str | None, label: str | None) -> str:
    """Classify a benefit into one of the 3 automatic coverage domains or 'none'."""
    combined = f"{concept_key or ''} {label or ''}".lower().replace("_", " ").replace("-", " ")
    if any(
        tok in combined
        for tok in (
            "windscreen",
            "wndscrn",
            "w screen",
            "cermin",
            "endorsement 89",
            "endt 89",
            "endorsement 97",
            "endt 97",
        )
    ):
        return "windscreen"
    if any(tok in combined for tok in ("towing", "roadside assistance", "auto assist", "e assist smart driver")):
        if "ev battery" not in combined and "out of charge" not in combined and "international" not in combined:
            return "towing"
    if any(
        tok in combined
        for tok in (
            "betterment",
            "endorsement 113",
            "endt 113",
            "endorsement 030",
            "endorsement 30",
            "make vehicle aged",
        )
    ):
        return "betterment"
    return "none"


def is_auto_coverage_allowed_for_benefit(
    concept_key: str | None,
    label: str | None,
    raw_limit: object,
    raw_cost: object = None,
) -> bool:
    """Strict Zero-Fake-Coverage Gate for automatic extraction/rescan.

    Only Windscreen (PDF sum insured), Towing (km / Unlimited), and Betterment
    (vehicle age / waiver text) may populate an automatic coverage value. All
    other benefits (LLOP, LLP, Special Perils, Private Car 365, SRCC, etc.)
    keep coverage empty unless manually edited by a user.
    """
    if raw_limit is None:
        return False
    if isinstance(raw_limit, dict):
        role = str(raw_limit.get("semantic_role") or "").strip().lower()
        if role == "premium":
            return False
        if raw_limit.get("type") == "distance":
            if raw_limit.get("unlimited") is True:
                limit_str = "Unlimited"
            elif raw_limit.get("value") is not None and raw_limit.get("unit"):
                limit_str = f"{raw_limit.get('value')} {raw_limit.get('unit')}".strip()
            else:
                limit_str = str(raw_limit.get("display_text") or raw_limit.get("value") or "").strip()
        else:
            limit_str = str(raw_limit.get("display_text") or raw_limit.get("value") or "").strip()
            if not limit_str and raw_limit.get("unlimited") is True:
                limit_str = "Unlimited"
    else:
        limit_str = str(raw_limit).strip()

    low = limit_str.lower().rstrip(" .")
    if low in _NON_INFORMATIVE_LIMIT_TOKENS:
        return False

    limit_num = _parse_positive_money(raw_limit)
    cost_num = _parse_positive_money(raw_cost)
    if limit_num is not None and cost_num is not None and abs(limit_num - cost_num) <= 0.01:
        return False

    domain = benefit_auto_coverage_domain(concept_key, label)
    if domain == "windscreen":
        if "%" in limit_str:
            return False
        return limit_num is not None and limit_num >= 200.0
    if domain == "towing":
        if "unlimited" in low or re.search(r"\b\d[\d,]*(?:\.\d+)?\s*(?:km|kilometres?)\b", low):
            return True
        return False
    if domain == "betterment":
        if re.match(r"^(?:rm|myr)\b", low) or (limit_num is not None and "year" not in low and "yr" not in low):
            return False
        return "year" in low or "yr" in low or "waiv" in low

    return False


