"""Conservative extraction of evidence-bearing benefit source lines with scoped aliases and variant shaping."""

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
    "extra coverage",
    "extra coverages",
    "additional coverage",
    "additional covers",
    "endorsements",
    "policy endorsements",
    "schedule of benefits",
    "optional benefits",
    "extended benefits",
    "selected endorsement",
    "selected endorsements",
    "schedule of extra benefits",
    "endorsement",
)
AVAILABLE_HEADINGS = (
    "available optional covers",
    "optional covers available",
    "available add-ons",
    "available addons",
    "optional covers",
    "optional cover",
)
PDS_HEADINGS = ("product disclosure sheet", "policy wording", "terms and conditions")
GENERIC_HEADINGS = ("benefits", "optional covers", "add-ons", "addons", "know your coverage")
STOP_HEADINGS = (
    "contribution summary",
    "premium summary",
    "total payable",
    "contact us",
    "declaration",
    "takaful contribution",
    "contribution",
    "basic contribution",
    "gross contribution",
    "total contribution",
    "premium calculation",
    "calculation of premium",
    "calculation of contribution",
    "premium details",
    "breakdown of premium",
    "payment details",
    "schedule of payment",
    "payment method",
    "agent code",
    "quotation type",
    "important notice",
    "acceptance of any referred case",
)
NON_BENEFIT_PREFIXES = (
    "total optional cover",
    "total premium",
    "gross premium",
    "stamp duty",
    "service tax",
    "sst",
    "class of vehicle",
    "kelas kenderaan",
    "cover type",
    "jenis perlindungan",
    "geographical area",
    "business/profession",
    "hire purchase",
    "period insurance",
    "sum insured",
    "excess",
    "trailer",
    "cubic capacity",
    "year of manufacture",
    "seating capacity",
    "engine no",
    "chassis no",
    "registration no",
    "regn. card",
    "make & type",
    "named driver",
    "this quotation will expire",
    "endorsement attaching",
    "important notice",
    "cbc regulation",
    "road transport act",
    "motor vehicles",
    "private car protector quotation",
    "private car comprehensive quotation",
    "private car quotation",
    "basic contribution",
    "gross contribution",
    "total contribution",
    "takaful contribution",
    "additional coverage",
    "+ additional",
    "- ncd",
    "+ service tax",
    "+ stamp duty",
    "quotation type",
    "agent code",
    "acceptance of any",
    "total",
    "total payable",
    "basic premium",
    "takaful scheme",
    "insurance scheme",
    "scheme",
    "agreed value",
    "market value",
)
NARRATIVE_PREFIXES = ("example:", "example ", "note:", "important:", "disclaimer :", "disclaimer:")
MONEY_RE = re.compile(r"(?:RM\s*)?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?", re.IGNORECASE)
PURE_AMOUNT_RE = re.compile(r"^[:\-•*+~]?\s*(?:RM|MYR)?\s*[\d,]+(?:\.\d{1,2})?\s*%?\s*$", re.IGNORECASE)


def _normalized(value: str) -> str:
    value = re.sub(r"^(?:☑|☒|✓|✔|☐|□|\[[xX ]\]|[•\-\*\+])\s*", "", value)
    value = re.sub(r"\s+", " ", value).strip(" :-;.").lower()
    # Normalize common abbreviations
    value = re.sub(r"\bw/screen\b|\bwscreen\b", "windscreen", value, flags=re.IGNORECASE)
    value = re.sub(r"\blltp\b", "legal liability to passengers", value, flags=re.IGNORECASE)
    value = re.sub(r"\bllop\b", "legal liability of passengers", value, flags=re.IGNORECASE)
    value = re.sub(r"\blltr\b", "legal liability to pillion", value, flags=re.IGNORECASE)
    # Strip trailing numbers/parameters ONLY if preceded by currency/keywords OR followed by units
    value = re.sub(r"\s+(?:(?:rm|myr|premium|limit|sum\s+insured)\s*[\d,.]+|[\d,.]+\s*(?:km|kilometres?|days?|times?|years?|months?)).*$", "", value, flags=re.IGNORECASE)
    # Strip any trailing parens with money like (RM 2,650.00)
    value = re.sub(r"\s*\(\s*(?:rm|myr)?\s*[\d,.]+\s*\)\s*$", "", value, flags=re.IGNORECASE)
    # Strip trailing colon or standalone number at the end
    value = re.sub(r"\s*[:\-]\s*(?:rm|myr)?\s*[\d,.]+\s*$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+[\d,]+(?:\.\d{1,2})?\s*$", "", value)
    return value.strip(" :-;.")[:500]


def _stable_line_id(page: int, ordinal: int, raw: str) -> str:
    digest = hashlib.sha256(f"{page}\x1f{ordinal}\x1f{raw.strip()}".encode("utf-8")).hexdigest()[:20]
    return f"p{page}-l{ordinal}-{digest}"


def _money(raw: str) -> str:
    try:
        return f"{Decimal(raw.replace(',', '')):.2f}"
    except InvalidOperation:
        return raw.replace(",", "")


def _format_display_money(amount_str: str) -> str:
    try:
        dec = Decimal(amount_str)
        if dec == dec.to_integral():
            return f"RM{int(dec):,}"
        return f"RM{dec:,.2f}"
    except (InvalidOperation, ValueError):
        return f"RM{amount_str}"


def _typed_value(raw: str, normalized: str) -> dict | None:
    # 1. Distance
    distance = re.search(r"\b(\d[\d,]*(?:\.\d+)?)\s*(km|kilometres?)\b", raw, re.IGNORECASE)
    if distance:
        return {"type": "distance", "value": distance.group(1).replace(",", ""), "unit": "km", "unlimited": False}
    if re.search(r"\bunlimited\b", raw, re.IGNORECASE) and "tow" in normalized:
        return {"type": "distance", "value": None, "unit": "km", "unlimited": True}

    # 2. Duration / Warranty
    duration = re.search(r"\b(\d+)\s*(years?|yrs?|months?|mths?)\b", raw, re.IGNORECASE)
    if duration and any(k in normalized for k in ("warranty", "workmanship", "repair")):
        val = duration.group(1)
        unit = "years" if "y" in duration.group(2).lower() else "months"
        return {"type": "duration", "value": val, "unit": unit}

    # 3. Per-Day allowance (e.g. Daily Hospital Income)
    per_day = re.search(r"(?:RM\s*)?(\d[\d,]*(?:\.\d+)?)\s*(?:\/|\s*per\s*)\s*(?:day|daily)", raw, re.IGNORECASE)
    if per_day:
        amount = _money(per_day.group(1))
        return {"type": "per_day", "value": amount, "currency": "MYR", "unit": "day"}

    # 4. Money / Insured Limit & Cost
    amounts = list(MONEY_RE.finditer(raw))
    if not amounts:
        return None
    if len(amounts) >= 2:
        a1 = _money(f"{amounts[0].group(1)}.{amounts[0].group(2) or '00'}")
        a2 = _money(f"{amounts[1].group(1)}.{amounts[1].group(2) or '00'}")
        try:
            d1, d2 = Decimal(a1), Decimal(a2)
            limit_val, cost_val = (a1, a2) if d1 >= d2 else (a2, a1)
        except Exception:
            limit_val, cost_val = a1, a2
        return {
            "type": "money",
            "value": limit_val,
            "currency": "MYR",
            "semantic_role": "insured_limit",
            "premium": {"amount": cost_val, "currency": "MYR"},
        }

    premium_match = re.search(r"premium\s*RM?\s*(\d[\d,]*(?:\.\d+)?)", raw, re.IGNORECASE)
    first = amounts[0]
    amount = _money(f"{first.group(1)}.{first.group(2) or '00'}")
    is_table_cost = bool(re.search(r"[:\-]\s*(?:RM|MYR)?\s*[\d,]+", raw, re.IGNORECASE))
    is_liability_driver = any(token in normalized for token in ("passenger", "driver", "all drivers", "lltp", "llop", "pillion"))

    if premium_match:
        value = {"type": "money", "value": "0.00", "currency": "MYR", "semantic_role": "amount", "premium": {"amount": _money(premium_match.group(1)), "currency": "MYR"}}
    elif is_table_cost or (is_liability_driver and not any(token in normalized for token in ("windscreen", "peril", "flood", "theft", "loss", "key", "seat", "cart"))):
        value = {"type": "money", "value": "0.00", "currency": "MYR", "semantic_role": "amount", "premium": {"amount": amount, "currency": "MYR"}}
    else:
        role = "insured_limit" if any(token in normalized for token in ("windscreen", "cover", "allowance", "benefit", "peril", "flood", "theft", "loss", "key", "seat")) else "amount"
        value = {"type": "money", "value": amount, "currency": "MYR", "semantic_role": role}
    return value


def _shape_description(concept: dict, typed_val: dict | None) -> str:
    """Format description template with extracted value (e.g. 'up to 50 km')."""
    if not typed_val:
        return str(concept.get("description") or "")

    # Derive display value string
    v_type = typed_val.get("type")
    if v_type == "distance":
        disp = "Unlimited" if typed_val.get("unlimited") else f"{typed_val.get('value')} km"
    elif v_type == "duration":
        disp = f"{typed_val.get('value')} {typed_val.get('unit')}"
    elif v_type == "per_day":
        disp = f"{_format_display_money(str(typed_val.get('value') or '0'))}/day"
    elif v_type == "money":
        disp = _format_display_money(typed_val.get("value") or "0")
    else:
        disp = str(typed_val.get("value") or "")

    # 1. Search variants for template
    variants = concept.get("description_variants") or []
    for var in variants:
        tmpl = var.get("template")
        if tmpl and "{value}" in tmpl:
            return tmpl.replace("{value}", disp)

    # 2. Heuristic fallback based on value type
    desc = str(concept.get("description") or "")
    if v_type == "distance":
        return f"up to {disp}"
    if v_type == "duration":
        return f"up to {disp}"
    if v_type == "per_day":
        return f"up to {disp}"
    if v_type == "money":
        return f"up to {disp}"
    return desc


def _candidate_mappings(
    normalized: str,
    concepts: list[dict],
    *,
    company_id: str | None = None,
    product_id: str | None = None,
    package_id: str | None = None,
    typed_val: dict | None = None,
) -> list[dict]:
    scored: list[tuple[int, dict]] = []
    padded = f" {normalized} "

    for concept in concepts:
        best_score = 0
        best_evidence = ""
        best_type = "database_alias"

        # 1. Check aliases (including scoped aliases)
        raw_aliases = concept.get("aliases") or []
        for alias_entry in raw_aliases:
            if isinstance(alias_entry, dict):
                raw_phrase = alias_entry.get("phrase") or alias_entry.get("normalized_phrase") or ""
                scope = alias_entry.get("scope") or "global"
                a_company = alias_entry.get("company_id")
                a_product = alias_entry.get("product_id")
                a_package = alias_entry.get("package_id")
            else:
                raw_phrase = str(alias_entry or "")
                scope = "global"
                a_company = a_product = a_package = None

            alias_norm = _normalized(raw_phrase)
            if not alias_norm:
                continue

            if f" {alias_norm} " in padded or padded.strip() == alias_norm:
                # Scoped priority weight
                base_weight = 100
                if scope == "package" and package_id and a_package == package_id:
                    base_weight = 400
                elif scope == "product" and product_id and a_product == product_id:
                    base_weight = 300
                elif scope == "company" and company_id and a_company == company_id:
                    base_weight = 200
                elif scope == "global":
                    base_weight = 100

                score = base_weight + len(alias_norm) * 2
                if score > best_score:
                    best_score = score
                    best_evidence = alias_norm
                    best_type = "scoped_alias" if scope != "global" else "database_alias"

        # 2. Check concept label
        label_norm = _normalized(str(concept.get("label") or ""))
        if label_norm and (f" {label_norm} " in padded or padded.strip() == label_norm):
            score = 100 + len(label_norm) * 2
            if score > best_score:
                best_score = score
                best_evidence = label_norm
                best_type = "database_alias"

        # 3. Check match_dataset (word/phrase tokens)
        match_words = concept.get("match_dataset") or []
        for mw in match_words:
            mw_norm = _normalized(str(mw or ""))
            if mw_norm and f" {mw_norm} " in padded:
                score = 50 + len(mw_norm)
                if score > best_score:
                    best_score = score
                    best_evidence = mw_norm
                    best_type = "match_dataset"

        if best_score > 0:
            c_id = concept.get("concept_id") or concept.get("id")
            shaped_desc = _shape_description(concept, typed_val)
            scored.append((best_score, {
                "concept_id": str(c_id),
                "concept_key": concept.get("concept_key"),
                "label": concept.get("label"),
                "matched_alias": best_evidence,
                "match_type": best_type,
                "shaped_description": shaped_desc,
            }))

    scored.sort(key=lambda item: (-item[0], str(item[1].get("concept_id"))))
    return [item for _score, item in scored]


def _heading_scope(line: str) -> tuple[str, str] | None:
    normalized = re.sub(r"\s+", " ", line).strip(" :-;.").lower()
    if re.match(r"^total(?:\s*[:\-].*|\s+payable.*|\s+contribution.*|\s+premium.*|\s+amount.*)?$", normalized):
        return "outside", "unknown"
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
    if PURE_AMOUNT_RE.match(raw.strip()):
        return False
    normalized = _normalized(raw)
    if not normalized or normalized.startswith(NON_BENEFIT_PREFIXES):
        return False
    if PURE_AMOUNT_RE.match(normalized):
        return False
    if any(candidate for candidate in _candidate_mappings(normalized, concepts)):
        return True
    if raw.startswith((*CHECKED_PREFIXES, *UNCHECKED_PREFIXES)):
        return True
    if in_section and len(normalized) >= 4 and not normalized.startswith(NARRATIVE_PREFIXES):
        if any(normalized.startswith(nbp) for nbp in NON_BENEFIT_PREFIXES):
            return False
        return True
    return False


def _stitch_lines(raw_lines: list[str]) -> list[str]:
    stitched: list[str] = []
    for line in raw_lines:
        s = re.sub(r"\s+", " ", line).strip()
        if not s or s in {"•", "*", "·"}:
            continue
        if s in {":", "-", "+"}:
            if stitched:
                stitched[-1] += " " + s
            continue

        is_amount = bool(re.match(r"^(?:[:\-]\s*)?(?:RM|MYR)?\s*[\d,]+(?:\.\d{1,2})?(?:\s*%)?$", s, re.IGNORECASE))
        is_continuation = False
        if stitched:
            prev = stitched[-1].strip()
            prev_lower = prev.lower()
            prev_has_amount = bool(re.search(r"(?:RM|MYR)\s*[\d,]+(?:\.\d{2})?", prev, re.IGNORECASE))
            if is_amount:
                if not prev_has_amount and not _heading_scope(prev):
                    is_continuation = True
            elif s.startswith(":"):
                is_continuation = True
            elif prev_lower.endswith((" in", " of", " for", " with", " and", " or", ":")):
                if not _heading_scope(prev):
                    is_continuation = True

        if is_continuation and stitched:
            stitched[-1] += " " + s
        else:
            stitched.append(s)
    return stitched


def extract_benefit_lines(
    page_text: list[dict],
    *,
    concepts: list[dict] | None = None,
    company_id: str | None = None,
    product_id: str | None = None,
    package_id: str | None = None,
) -> list[dict]:
    """Return source lines without treating heuristic matches as reviewed truth."""

    concept_rows = concepts or []
    extracted: list[dict] = []
    scope = "outside"
    section_state = "unknown"
    section_label: str | None = None
    ordinal = 0
    for page in sorted(page_text, key=lambda item: int(item.get("page", 0))):
        page_number = int(page.get("page") or 1)
        stitched_lines = _stitch_lines(str(page.get("text") or "").splitlines())
        for raw in stitched_lines:
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
            typed_val = _typed_value(raw, normalized)
            if raw.startswith(CHECKED_PREFIXES):
                inclusion = "selected"
            elif raw.startswith(UNCHECKED_PREFIXES):
                inclusion = "not_selected"
            elif narrative:
                inclusion = "not_selected" if "not included" in lower else "unknown"
            elif typed_val and typed_val.get("type") == "money" and (typed_val.get("value") or typed_val.get("premium")):
                inclusion = "selected"
            else:
                inclusion = section_state
            source_scope = "pds" if scope == "pds" else "narrative" if narrative else scope if scope != "outside" else "unknown"
            candidate_maps = _candidate_mappings(
                normalized,
                concept_rows,
                company_id=company_id,
                product_id=product_id,
                package_id=package_id,
                typed_val=typed_val,
            )

            cov_limit = (
                typed_val.get("value")
                if isinstance(typed_val, dict) and typed_val.get("semantic_role") == "insured_limit"
                else None
            )
            prem_cost = (
                typed_val.get("premium", {}).get("amount")
                if isinstance(typed_val, dict) and typed_val.get("premium")
                else (typed_val.get("value") if isinstance(typed_val, dict) and typed_val.get("semantic_role") == "amount" else None)
            )
            is_opt = scope == "optional" or section_label == "Optional Covers" or bool(prem_cost)

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
                "candidate_mappings": candidate_maps,
                "extracted_value": typed_val,
                "coverage_limit": cov_limit,
                "premium_cost": prem_cost,
                "is_optional_cover": is_opt,
            })
    return extracted
