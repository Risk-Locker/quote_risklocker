"""Typed benefit values and canonical quotation decision states."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
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


class SourceLineDisposition(StrEnum):
    UNRESOLVED = "unresolved"
    MAPPED = "mapped"
    CUSTOM = "custom"
    SOURCE_ONLY = "source_only"
    OMITTED = "omitted"


class MoneyAmount(BaseModel):
    amount: Decimal = Field(ge=0)
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
    aggregate_cap: Decimal | None = Field(default=None, ge=0)
    per_event: Decimal | int | None = None
    occurrences: int | None = Field(default=None, ge=0)
    expression: str | None = Field(default=None, max_length=1_000)
    variables: dict[str, str] = Field(default_factory=dict)
    enum_key: str | None = Field(default=None, max_length=120)
    plan_key: str | None = Field(default=None, max_length=120)
    display_text: str | None = Field(default=None, max_length=500)

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
            if self.value is None or not self.currency or not self.semantic_role:
                raise ValueError("Money requires value, currency, and semantic role.")
        elif self.type == "percentage":
            if self.value is None or not self.basis:
                raise ValueError("Percentage requires value and basis.")
        elif self.type == "per_day":
            if self.value is None or not self.currency or self.max_days is None:
                raise ValueError("Per-day allowance requires value, currency, and maximum days.")
        elif self.type == "formula":
            if not (self.expression or "").strip():
                raise ValueError("Formula requires an expression.")
        elif self.type == "custom":
            if not (self.display_text or "").strip():
                raise ValueError("Custom reviewed values require display text.")
        elif self.type == "region" and not self.region:
            raise ValueError("Region values require a region.")
        elif self.type == "enum" and not self.enum_key:
            raise ValueError("Enum values require an enum key.")
        elif self.type == "package_plan" and not self.plan_key:
            raise ValueError("Package-plan values require a plan key.")
        elif self.type in {"occurrence", "duration", "count", "boolean"} and self.value is None:
            raise ValueError(f"{self.type} requires a value.")
        return self
