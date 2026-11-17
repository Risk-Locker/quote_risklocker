"""Single authoritative Special Perils (Flood / Endorsement 57) evidence resolver.

Enforces word-boundary matching, negative-phrase negation ('not covered', 'tidak termasuk'),
and explicit exclusion of Takaful 'contribution' substrings.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Sequence

# Strict word-boundary regex for Special Perils / Flood / Endorsement 57
SPECIAL_PERILS_WORD_RE = re.compile(
    r"\b(?:"
    r"special\s+perils?|"
    r"perils?\s+khas|"
    r"inclusion\s+of\s+special\s+perils?|"
    r"convulsions?\s+of\s+nature|"
    r"natural\s+disasters?|"
    r"acts?\s+of\s+god|"
    r"flood(?:s|ing)?|"
    r"banjir|"
    r"storms?|"
    r"ribut|"
    r"typhoons?|"
    r"landslides?|"
    r"tanah\s+runtuh|"
    r"water\s+damage"
    r")\b",
    re.IGNORECASE,
)

ENDORSEMENT_57_RE = re.compile(
    r"\b(?:endorsements?|endt?\.?|clauses?|perils?)\s*(?:no\.?|attached|attaching|applied)?\s*[:\-]?\s*57(?:[ab]|\b)",
    re.IGNORECASE,
)

NEGATIVE_PERIL_PHRASE_RE = re.compile(
    r"\b(?:"
    r"not\s+covered|"
    r"not\s+included|"
    r"tidak\s+termasuk|"
    r"tiada\s+perlindungan|"
    r"excluded|"
    r"excluding\s+special\s+perils?|"
    r"without\s+special\s+perils?|"
    r"no\s+special\s+perils?"
    r")\b"
    r"|[:\-]\s*(?:nil|none|no|tiada|rm\s*0(?:\.00)?|0\.00)\s*$",
    re.IGNORECASE,
)


def is_special_perils_value_included(val: Any) -> bool:
    """Return True only when a stored/resolved special_perils string represents active inclusion."""
    if val is None:
        return False
    cleaned = str(val).strip().lower()
    if not cleaned:
        return False
    if cleaned in {"not included", "not covered", "none", "nil", "no", "false", "-", "—", "tiada", "tidak termasuk", "0", "0.00", "rm 0", "rm 0.00"}:
        return False
    if NEGATIVE_PERIL_PHRASE_RE.search(cleaned):
        return False
    return True


def has_special_perils_evidence(
    text: str = "",
    endorsements: Iterable[str] = (),
    benefit_lines: Sequence[Any] = (),
    fields: dict[str, Any] | None = None,
) -> bool:
    """Return True if genuine evidence of Special Perils / Endorsement 57 coverage is present."""
    # 1. Explicit manual override in draft fields
    if isinstance(fields, dict):
        sp_field = fields.get("special_perils")
        if isinstance(sp_field, dict) and sp_field.get("status") == "manual_override":
            return is_special_perils_value_included(sp_field.get("value"))
        sp_prem = fields.get("special_perils_premium")
        sp_prem_val = sp_prem.get("value") if isinstance(sp_prem, dict) else sp_prem
        if sp_prem_val is not None:
            try:
                num = float(re.sub(r"[^0-9.]", "", str(sp_prem_val)) or "0")
                if num > 0:
                    return True
            except (ValueError, TypeError):
                pass

    # 2. Explicit endorsement code tokens (57 / 57a / 57b)
    norm_tokens = {re.sub(r"[^0-9a-z]", "", str(t or "")).lower() for t in (endorsements or ())}
    if {"57", "57a", "57b"}.intersection(norm_tokens):
        return True

    # 3. Extracted benefit lines (when not marked deselected or negated)
    for bl in benefit_lines or ():
        if isinstance(bl, dict):
            scope = str(bl.get("source_scope") or "").lower()
            raw_lbl = f"{bl.get('raw_label') or ''} {bl.get('normalized_label') or ''} {bl.get('raw_text') or ''}"
            c_key = str(bl.get("concept_key") or "").lower()
        else:
            scope = str(getattr(bl, "source_scope", "") or "").lower()
            raw_lbl = f"{getattr(bl, 'raw_label', '') or ''} {getattr(bl, 'normalized_label', '') or ''}"
            c_key = ""
            for m in getattr(bl, "candidate_mappings", None) or ():
                if isinstance(m, dict) and m.get("concept_key") == "special-perils":
                    c_key = "special-perils"
                    break
        if scope in {"not_selected", "quotation_available", "pds"}:
            continue
        if NEGATIVE_PERIL_PHRASE_RE.search(raw_lbl):
            continue
        if c_key == "special-perils" or SPECIAL_PERILS_WORD_RE.search(raw_lbl) or ENDORSEMENT_57_RE.search(raw_lbl):
            return True

    # 4. Line-by-line scan of combined text with word boundaries and negation filtering
    if text:
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if NEGATIVE_PERIL_PHRASE_RE.search(line):
                continue
            if ENDORSEMENT_57_RE.search(line):
                return True
            # Check compact endorsement list line e.g. "Endorsements Attached: 02, 57, 89"
            m_list = re.search(
                r"(?:endorsements?|clauses?|perils?)\s*(?:attached|attaching|applied)?\s*[:\-]\s*([0-9a-zA-Z,\s\(\)\.\/]+)",
                line,
                re.IGNORECASE,
            )
            if m_list:
                tokens = {
                    re.sub(r"[^0-9a-zA-Z]", "", tok).lower()
                    for tok in re.split(r"[,;\s]+", m_list.group(1))
                    if tok.strip()
                }
                if {"57", "57a", "57b"}.intersection(tokens):
                    return True
            if SPECIAL_PERILS_WORD_RE.search(line):
                return True

    return False


def resolve_special_perils(
    text: str = "",
    endorsements: Iterable[str] = (),
    benefit_lines: Sequence[Any] = (),
    fields: dict[str, Any] | None = None,
) -> str:
    """Resolve canonical 'Included' or 'Not Included' Special Perils status."""
    return "Included" if has_special_perils_evidence(
        text=text,
        endorsements=endorsements,
        benefit_lines=benefit_lines,
        fields=fields,
    ) else "Not Included"
