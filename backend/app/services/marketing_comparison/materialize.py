"""Write-time materialization and field-level manual override helpers for Marketing Comparison."""

from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

OVERRIDABLE_ENTRY_FIELDS: frozenset[str] = frozenset(
    {
        "company_name",
        "sum_insured",
        "valuation_type",
        "agreed_value",
        "motor_premium",
        "basic_figure_amount",
        "towing_limit",
        "towing_km",
        "waiver_betterment",
        "betterment_rate",
        "excess",
        "windscreen_sum_insured",
        "special_perils",
        "llp_llop",
        "extra_addons",
        "notes",
        "discount",
        "is_recommended",
        "is_hidden",
        "manual_rank",
    }
)

LEGACY_DEFAULT_LOCKED_FIELDS: tuple[str, ...] = (
    "company_name",
    "sum_insured",
    "valuation_type",
    "agreed_value",
    "motor_premium",
    "towing_limit",
    "waiver_betterment",
    "excess",
    "windscreen_sum_insured",
    "special_perils",
    "llp_llop",
    "notes",
)


def _canonical_override_key(field_name: str) -> str:
    if field_name == "towing_km":
        return "towing_limit"
    if field_name == "basic_premium":
        return "basic_figure_amount"
    return field_name


def get_entry_overrides(entry: Any) -> list[str]:
    """Return normalized list of manually overridden field names for an entry."""
    raw = getattr(entry, "manual_overrides", None)
    if isinstance(raw, list):
        return [str(x) for x in raw if x]
    return []


def is_field_overridden(entry: Any, field_name: str) -> bool:
    """Return True if field_name is locked by field-level manual_overrides or legacy is_manual."""
    canon = _canonical_override_key(field_name)
    overrides = get_entry_overrides(entry)
    if overrides:
        if canon in overrides or field_name in overrides:
            return True
        if canon == "towing_limit" and "towing_km" in overrides:
            return True
        if canon in ("valuation_type", "agreed_value") and (
            "valuation_type" in overrides or "agreed_value" in overrides
        ):
            return True
        return False
    # Legacy row compatibility: is_manual=True with empty manual_overrides locks all fields
    if bool(getattr(entry, "is_manual", False)):
        return True
    return False


def record_manual_overrides(
    entry: Any,
    edited_fields: Iterable[str] = (),
    clear_field: str | None = None,
) -> list[str]:
    """Record newly edited fields into entry.manual_overrides and optionally clear one field."""
    current = get_entry_overrides(entry)
    # If legacy row had is_manual=True and empty manual_overrides, and user is selectively clearing one field,
    # expand the remaining legacy fields first so other manual edits remain protected.
    if not current and bool(getattr(entry, "is_manual", False)) and clear_field:
        current = list(LEGACY_DEFAULT_LOCKED_FIELDS)

    seen = list(dict.fromkeys(_canonical_override_key(f) for f in current if f))
    for f in edited_fields:
        canon = _canonical_override_key(f)
        if canon in OVERRIDABLE_ENTRY_FIELDS and canon not in seen:
            seen.append(canon)

    if clear_field:
        clear_canon = _canonical_override_key(clear_field)
        seen = [f for f in seen if f not in {clear_canon, clear_field}]

    entry.manual_overrides = seen
    try:
        flag_modified(entry, "manual_overrides")
    except Exception:
        pass
    entry.is_manual = bool(seen) or (getattr(entry, "session_id", None) is None and bool(getattr(entry, "is_manual", False)))
    return seen


def materialize_comparison_entries(db: Session, tenure_id: str) -> dict[str, Any]:
    """Idempotently materialize and commit comparison entries for a tenure at write time."""
    from app.services.marketing_comparison_service import get_marketing_comparison

    result = get_marketing_comparison(db, tenure_id)
    db.commit()
    result["needs_materialize"] = False
    return result
