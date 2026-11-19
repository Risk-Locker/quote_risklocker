"""Dynamic conditional add-on definitions, extraction, and DraftBenefitSelection sync helpers."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.tables import DraftBenefitSelection

DYNAMIC_ADDON_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "key": "ehailing",
        "label": "E-Hailing",
        "peril_tag": "E-HAILING",
        "concept_keys": ("ehailing", "e-hailing", "private-hire-car-e-hailing"),
        "default_title": "Private Hire Car (E-Hailing)",
        "positive_re": re.compile(
            r"\b(?:e[\s\-]?hailing|ehailing|private\s+hire\s+car(?:\s*\(?\s*e[\s\-]?hailing\)?)?)\b",
            re.IGNORECASE,
        ),
        "negative_re": re.compile(
            r"\b(?:does\s+not\s+cover|not\s+covered|not\s+included|tidak\s+termasuk|tiada|exclud(?:ing|ed)|without)\b",
            re.IGNORECASE,
        ),
    },
    {
        "key": "srcc",
        "label": "Strike & Riot",
        "peril_tag": "SRCC",
        "concept_keys": ("strike-riot-civil-commotion", "srcc"),
        "default_title": "Strike, Riot & Civil Commotion (SRCC)",
        "positive_re": re.compile(
            r"\b(?:strike[\s,/&-]*riot|civil\s+commotion|srcc)\b",
            re.IGNORECASE,
        ),
        "negative_re": re.compile(
            r"\b(?:does\s+not\s+cover|not\s+covered|not\s+included|tidak\s+termasuk|tiada|exclud(?:ing|ed)|without)\b",
            re.IGNORECASE,
        ),
        "endorsement_codes": ("25", "101"),
    },
    {
        "key": "child_seat",
        "label": "Child Safety",
        "peril_tag": "CHILD SEAT",
        "concept_keys": ("child-car-seat", "child-seat", "child-safety-seat"),
        "default_title": "Child Car Seat Cover",
        "positive_re": re.compile(
            r"\b(?:child\s+(?:car\s+)?safety\s+seat|child\s+car\s+seat|child\s+restraint)\b",
            re.IGNORECASE,
        ),
        "negative_re": re.compile(
            r"\b(?:not\s+covered|not\s+included|tidak\s+termasuk|tiada|exclud(?:ing|ed))\b",
            re.IGNORECASE,
        ),
    },
    {
        "key": "respray",
        "label": "Full Respray",
        "peril_tag": "RESPRAY",
        "concept_keys": ("repaint-spray-paint", "full-respray", "spray-paint", "respray"),
        "default_title": "Full Respray / Paintwork",
        "positive_re": re.compile(
            r"\b(?:full\s+respray|respray|spray\s+paint(?:ing)?|repaint(?:ing)?)\b",
            re.IGNORECASE,
        ),
        "negative_re": re.compile(
            r"\b(?:not\s+covered|not\s+included|tidak\s+termasuk|tiada|exclud(?:ing|ed))\b",
            re.IGNORECASE,
        ),
    },
    {
        "key": "ev_battery",
        "label": "EV Battery",
        "peril_tag": "EV BATTERY",
        "concept_keys": ("ev-battery-depletion-towing", "ev-battery", "battery-coverage"),
        "default_title": "EV Battery Protection",
        "positive_re": re.compile(
            r"\b(?:ev\s+battery|battery\s+depletion|traction\s+battery|out\s+of\s+charge)\b",
            re.IGNORECASE,
        ),
        "negative_re": re.compile(
            r"\b(?:not\s+covered|not\s+included|tidak\s+termasuk|tiada|exclud(?:ing|ed))\b",
            re.IGNORECASE,
        ),
    },
    {
        "key": "ev_other",
        "label": "EV Protection",
        "peril_tag": "EV CHARGE",
        "concept_keys": ("ev-home-wall-charger", "ev-wall-charger", "ev-charger-liability", "ev-charging-cable"),
        "default_title": "EV Wall Charger / Protection",
        "positive_re": re.compile(
            r"\b(?:ev\s+(?:home\s+)?wall\s+charger|wall\s+charger|charging\s+cable|charger\s+liability)\b",
            re.IGNORECASE,
        ),
        "negative_re": re.compile(
            r"\b(?:not\s+covered|not\s+included|tidak\s+termasuk|tiada|exclud(?:ing|ed))\b",
            re.IGNORECASE,
        ),
    },
)

DYNAMIC_ADDON_BY_KEY: dict[str, dict[str, Any]] = {d["key"]: d for d in DYNAMIC_ADDON_DEFINITIONS}


def normalize_dynamic_addon_flag(val: Any) -> str:
    """Normalize arbitrary truthy/string flags into strictly 'Yes' or 'No'."""
    if val is None or isinstance(val, bool):
        return "Yes" if bool(val) else "No"
    s = str(val).strip().lower()
    if s in {"yes", "true", "included", "1", "y", "on"}:
        return "Yes"
    if s in {"no", "false", "not included", "not covered", "excluded", "none", "nil", "0", "-", ""}:
        return "No"
    return "Yes"


def sanitize_extra_addons_map(raw: Any) -> dict[str, str]:
    """Keep only known dynamic add-on keys normalized to 'Yes' | 'No'."""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in raw.items():
        clean_k = str(k or "").strip().lower()
        if clean_k in DYNAMIC_ADDON_BY_KEY and v is not None:
            out[clean_k] = normalize_dynamic_addon_flag(v)
    return out


def _line_has_positive_addon(text: str, defn: dict[str, Any]) -> bool:
    if not text:
        return False
    pos_re: re.Pattern[str] = defn["positive_re"]
    neg_re: re.Pattern[str] = defn["negative_re"]
    for line in text.splitlines():
        if not pos_re.search(line):
            continue
        if neg_re.search(line):
            continue
        return True
    return False


def extract_dynamic_addons(
    *,
    selections: list[DraftBenefitSelection],
    concepts_by_id: dict[str, Any],
    disabled_domains: set[str],
    ext_lines: list[Any],
    combined_text: str,
    end_tokens: set[str],
    draft_fields: dict[str, Any],
) -> dict[str, str]:
    """Detect conditional optional add-ons without false positives from statutory exclusions."""
    result: dict[str, str] = {}
    field_map = draft_fields.get("extra_addons")
    manual_overrides_map = (
        field_map.get("value")
        if isinstance(field_map, dict) and isinstance(field_map.get("value"), dict)
        else (field_map if isinstance(field_map, dict) else {})
    )
    is_manual_dict = isinstance(field_map, dict) and field_map.get("status") == "manual_override"

    for defn in DYNAMIC_ADDON_DEFINITIONS:
        key = defn["key"]
        c_keys = set(defn["concept_keys"])

        # 1. Explicit scalar override in draft_fields["extra_addons"]
        if is_manual_dict and key in manual_overrides_map:
            if normalize_dynamic_addon_flag(manual_overrides_map[key]) == "Yes":
                result[key] = "Yes"
            continue

        # 2. Respect disabled_domains (explicitly removed from workspace)
        if key in disabled_domains:
            continue

        # 3. Active DraftBenefitSelections
        matched_sel = False
        for sel in selections:
            if sel.state != "current":
                continue
            c = concepts_by_id.get(sel.concept_id) if getattr(sel, "concept_id", None) else None
            ck = (getattr(c, "concept_key", "") or "").lower()
            skey = (getattr(sel, "selection_key", "") or "").lower()
            lbl = (getattr(sel, "label_override", "") or (getattr(c, "label", "") if c else "") or "").lower()
            if ck in c_keys or any(ck_cand in skey for ck_cand in c_keys) or _line_has_positive_addon(lbl, defn):
                matched_sel = True
                break
        if matched_sel:
            result[key] = "Yes"
            continue

        # 4. Extracted Benefit Lines
        matched_line = False
        for el in ext_lines or []:
            lbl = f"{getattr(el, 'raw_label', '') or ''} {getattr(el, 'normalized_label', '') or ''}"
            if _line_has_positive_addon(lbl, defn):
                matched_line = True
                break
        if matched_line:
            result[key] = "Yes"
            continue

        # 5. Positive mention in non-negated raw lines or endorsements
        if _line_has_positive_addon(combined_text, defn):
            result[key] = "Yes"
            continue
        ecodes = defn.get("endorsement_codes") or ()
        if ecodes and any(ec in end_tokens for ec in ecodes):
            result[key] = "Yes"

    return result
