"""Conservative extraction of evidence-bearing benefit source lines."""

from __future__ import annotations

import hashlib
import re
from decimal import Decimal, InvalidOperation


CHECKED_PREFIXES = ("☑", "☒", "✓", "✔", "[x]", "[X]")
UNCHECKED_PREFIXES = ("☐", "□", "[ ]")
SELECTED_HEADINGS = (
    "selected optional covers",
    "selected benefits",
    "optional cover list",
    "optional covers selected",
    "benefits included",
)
AVAILABLE_HEADINGS = (
    "available optional covers",
    "optional covers available",
    "available add-ons",
    "available addons",
)
PDS_HEADINGS = ("product disclosure sheet", "policy wording", "terms and conditions")
GENERIC_HEADINGS = ("benefits", "optional covers", "add-ons", "addons")
STOP_HEADINGS = (
    "contribution summary",
    "premium summary",
    "total payable",
    "contact us",
    "declaration",
)
NON_BENEFIT_PREFIXES = (
    "total optional cover",
    "total premium",
    "gross premium",
    "stamp duty",
    "service tax",
    "sst",
)
NARRATIVE_PREFIXES = ("example:", "example ", "note:", "important:")
MONEY_RE = re.compile(r"(?:RM\s*)?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?", re.IGNORECASE)


def _normalized(value: str) -> str:
    value = re.sub(r"^(?:☑|☒|✓|✔|☐|□|\[[xX ]\])\s*", "", value)
    value = re.sub(r"\s+", " ", value).strip(" :-;.").lower()
    value = re.sub(r"\s+(?:rm\s*)?\d[\d,.]*(?:\s*(?:km|kilometres?|days?|times?))?.*$", "", value, flags=re.IGNORECASE)
    return value[:500]


def _stable_line_id(page: int, ordinal: int, raw: str) -> str:
    digest = hashlib.sha256(f"{page}\x1f{ordinal}\x1f{raw.strip()}".encode("utf-8")).hexdigest()[:20]
    return f"p{page}-l{ordinal}-{digest}"


def _money(raw: str) -> str:
    try:
        return f"{Decimal(raw.replace(',', '')):.2f}"
    except InvalidOperation:
        return raw.replace(",", "")


def _typed_value(raw: str, normalized: str) -> dict | None:
    distance = re.search(r"\b(\d[\d,]*(?:\.\d+)?)\s*(km|kilometres?)\b", raw, re.IGNORECASE)
    if distance:
        return {"type": "distance", "value": distance.group(1).replace(",", ""), "unit": "km", "unlimited": False}
    if re.search(r"\bunlimited\b", raw, re.IGNORECASE) and "tow" in normalized:
        return {"type": "distance", "value": None, "unit": "km", "unlimited": True}

    amounts = list(MONEY_RE.finditer(raw))
    if not amounts:
        return None
    premium_match = re.search(r"premium\s*RM?\s*(\d[\d,]*(?:\.\d+)?)", raw, re.IGNORECASE)
    first = amounts[0]
    amount = _money(f"{first.group(1)}.{first.group(2) or '00'}")
    role = "insured_limit" if any(token in normalized for token in ("windscreen", "cover", "allowance", "benefit")) else "amount"
    value: dict = {"type": "money", "value": amount, "currency": "MYR", "semantic_role": role}
    if premium_match:
        value["premium"] = {"amount": _money(premium_match.group(1)), "currency": "MYR"}
    return value


def _candidate_mappings(normalized: str, concepts: list[dict]) -> list[dict]:
    scored: list[tuple[int, dict]] = []
    padded = f" {normalized} "
    for concept in concepts:
        aliases = [concept.get("label"), *(concept.get("aliases") or [])]
        best = 0
        evidence = ""
        for raw_alias in aliases:
            alias = _normalized(str(raw_alias or ""))
            if alias and f" {alias} " in padded:
                score = len(alias)
                if score > best:
                    best = score
                    evidence = alias
        if best:
            scored.append((best, {
                "concept_id": concept.get("concept_id") or concept.get("id"),
                "label": concept.get("label"),
                "matched_alias": evidence,
                "match_type": "database_alias",
            }))
    scored.sort(key=lambda item: (-item[0], str(item[1].get("concept_id"))))
    return [item for _score, item in scored]


def _heading_scope(line: str) -> tuple[str, str] | None:
    normalized = re.sub(r"\s+", " ", line).strip(" :").lower()
    if normalized in SELECTED_HEADINGS:
        return "quotation_selected", "selected"
    if normalized in AVAILABLE_HEADINGS:
        return "quotation_available", "not_selected"
    if normalized in PDS_HEADINGS:
        return "pds", "unknown"
    if normalized in GENERIC_HEADINGS:
        return "unknown", "unknown"
    if normalized in STOP_HEADINGS:
        return "outside", "unknown"
    return None


def _looks_like_benefit(raw: str, concepts: list[dict], in_section: bool) -> bool:
    normalized = _normalized(raw)
    if not normalized or normalized.startswith(NON_BENEFIT_PREFIXES):
        return False
    if any(candidate for candidate in _candidate_mappings(normalized, concepts)):
        return True
    if raw.startswith((*CHECKED_PREFIXES, *UNCHECKED_PREFIXES)):
        return True
    return in_section and len(normalized) >= 4 and not normalized.startswith(NARRATIVE_PREFIXES)


def extract_benefit_lines(page_text: list[dict], *, concepts: list[dict] | None = None) -> list[dict]:
    """Return source lines without treating heuristic matches as reviewed truth."""

    concept_rows = concepts or []
    extracted: list[dict] = []
    scope = "outside"
    section_state = "unknown"
    section_label: str | None = None
    ordinal = 0
    for page in sorted(page_text, key=lambda item: int(item.get("page", 0))):
        page_number = int(page.get("page") or 1)
        for raw_line in str(page.get("text") or "").splitlines():
            raw = re.sub(r"\s+", " ", raw_line).strip()
            if not raw:
                continue
            heading = _heading_scope(raw)
            if heading:
                scope, section_state = heading
                section_label = raw[:255]
                continue
            lower = raw.lower()
            narrative = scope == "pds" or lower.startswith(NARRATIVE_PREFIXES) or " may cover " in f" {lower} " or " could " in f" {lower} " or "not included" in lower
            in_section = scope not in {"outside", "pds"}
            if not _looks_like_benefit(raw, concept_rows, in_section) and not narrative:
                continue
            normalized = _normalized(raw)
            if not normalized or normalized.startswith(NON_BENEFIT_PREFIXES):
                continue
            ordinal += 1
            if raw.startswith(CHECKED_PREFIXES):
                inclusion = "selected"
            elif raw.startswith(UNCHECKED_PREFIXES):
                inclusion = "not_selected"
            elif narrative:
                inclusion = "not_selected" if "not included" in lower else "unknown"
            else:
                inclusion = section_state
            source_scope = "pds" if scope == "pds" else "narrative" if narrative else scope if scope != "outside" else "unknown"
            extracted.append({
                "line_id": _stable_line_id(page_number, ordinal, raw),
                "raw_label": raw,
                "normalized_label": normalized,
                "page_number": page_number,
                "section": section_label,
                "source_scope": source_scope,
                "line_kind": "benefit_candidate" if not narrative else "narrative",
                "inclusion_state": inclusion,
                "evidence": {"page": page_number, "line": ordinal, "text": raw},
                "candidate_mappings": _candidate_mappings(normalized, concept_rows),
                "extracted_value": _typed_value(raw, normalized),
            })
    return extracted
