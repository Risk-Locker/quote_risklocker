"""Read-only adapters for legacy business and template records."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _value(record: Any, name: str, default=None):
    return record.get(name, default) if isinstance(record, dict) else getattr(record, name, default)


def adapt_legacy_special(parent: Any, variants: list[Any]) -> dict:
    """Preserve legacy content without inventing catalog/company provenance."""

    return {
        "legacy_id": _value(parent, "id"),
        "label": _value(parent, "label", "Legacy benefit"),
        "legacy_category": _value(parent, "category"),
        "company_id": None,
        "catalog_revision_id": None,
        "verified": False,
        "compatibility_state": "legacy_read_only",
        "variants": [
            {
                "legacy_id": _value(item, "id"),
                "label": _value(item, "label"),
                "secondary_label": _value(item, "secondary_label"),
                "value_text": _value(item, "value_text"),
                "icon_asset_id": _value(item, "icon_asset_id"),
                "style": {
                    key: _value(item, key)
                    for key in ("shape", "bg_color", "text_color", "border_width", "border_color", "shadow")
                    if _value(item, key) is not None
                },
            }
            for item in variants
        ],
    }


def adapt_legacy_template(template: Any) -> dict:
    """Expose a legacy template as a read-only insurer-independent revision."""

    return {
        "template_id": _value(template, "id"),
        "name": _value(template, "name", "Legacy template"),
        "company_id": None,
        "legacy_company_id": _value(template, "insurance_company_id"),
        "state": "compatibility",
        "revision": 0,
        "config": deepcopy(_value(template, "fixed_fields", {}) or {}),
    }
