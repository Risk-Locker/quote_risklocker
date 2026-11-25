"""Shared, alias-aware insurance company resolution for extracted values.

Every code path that maps a detected company string to a company row
(upload heuristic, worker resolution, Gemini re-extract route) uses the same
normalization and matching so variants like "AmGen", "AmGeneral",
"AM General Insurance Berhad", or "auto365" all resolve to AmAssurance,
while unrelated tokens ("AmBank", "Fortune") never match.
"""

from __future__ import annotations

import re


def normalize_detection(value: str) -> str:
    """Lowercase alphanumerics only; runs of other characters become one space."""
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _strip_liberty_shared_boilerplate(raw: str) -> str:
    """Remove promotional app banners and shared multi-brand PDPA blocks in long documents.

    AmAssurance and Liberty quotations print 'Kurnia One Touch Mobile App today!' in their
    footer, and Liberty General Insurance Berhad schedules include a shared PDPA page listing
    libertyinsurance.com.my, amassurance.com.my, and kurnia.com side by side.
    Single-brand Page 1 footers (e.g. Website: www.libertyinsurance.com.my) are preserved.
    """
    if len(raw) <= 80:
        return raw
    # Rejoin line-wrapped domains (e.g. "libertyinsurance.\ncom.my") before stripping shared boilerplate
    cleaned = re.sub(r"([a-z0-9-])\s*\.\s*([a-z]{2,})", r"\1.\2", raw, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bkurnia\s+one\s+touch(?:\s+mobile\s+app)?\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bdownload\s+kurnia\b", " ", cleaned, flags=re.IGNORECASE)
    # Agency / branch codes like "Issued By : AMGEN J1 RISK LOCKER..." are RiskLocker portal codes, not the underwriter.
    cleaned = re.sub(r"\bAMGEN\s+J\d+\b", " ", cleaned, flags=re.IGNORECASE)
    # Shared across ALL 3 brands (AmAssurance, Liberty, Kurnia): Head Office address & Kurnia logo sub-line
    cleaned = re.sub(r"\bliberty\s+insurance\s+tower\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bby\s+liberty\s+insurance\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"https?://(?:www\.)?(?:kurnia\.com|amassurance\.com\.my|libertyinsurance\.com(?:\.my)?)/(?:content/)?(?:privacy-policy|resources/pdpa)\S*",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    lower = cleaned.lower()
    has_shared_pdpa_emails = (
        ("customer@amassurance.com.my" in lower and "customer@kurnia.com" in lower)
        or ("customer@libertyinsurance.com.my" in lower and ("customer@kurnia.com" in lower or "customer@amassurance.com.my" in lower))
    )
    filtered_lines: list[str] = []
    for line in cleaned.splitlines():
        l_low = line.lower()
        brand_mentions = sum(
            1 for tok in ("kurnia", "amassurance", "liberty")
            if re.search(rf"\b{tok}\b", l_low)
        )
        if brand_mentions >= 2:
            continue
        if has_shared_pdpa_emails and any(
            em in l_low for em in ("customer@kurnia.com", "customer@amassurance.com.my", "customer@libertyinsurance.com.my")
        ):
            continue
        filtered_lines.append(line)
    result = "\n".join(filtered_lines).strip()
    return result or raw


def _score_liberty_group_brands(padded: str) -> dict[str, int]:
    """Score Liberty vs Kurnia vs AmAssurance symmetrically without shared-product bias."""
    # Remove shared legal underwriter phrase & shared head-office address before checking standalone 'liberty insurance'
    liberty_masked = re.sub(r"\bliberty general insurance(?:\s+berhad)?\b", " ", padded)
    liberty_masked = re.sub(r"\bliberty insurance tower\b|\bby liberty insurance\b", " ", liberty_masked)
    liberty_score = (
        (12 if any(d in padded for d in (" www libertyinsurance com my ", " libertyinsurance com my ", " www libertyinsurance com ", " libertyinsurance com ")) else 0)
        + (8 if " liberty insurance berhad " in padded else 0)
        + (6 if " liberty insurance " in liberty_masked else 0)
    )
    am_score = (
        (12 if (" www amassurance com my " in padded or " amassurance com my " in padded or " www amassurance com " in padded or " amassurance com " in padded) else 0)
        + (6 if " amassurance " in padded else 0)
        + (4 if " amgeneral " in padded else 0)
    )
    kurnia_score = (
        (12 if (" www kurnia com " in padded or " kurnia com " in padded or " kurnia com my " in padded) else 0)
        + (6 if any(cue in padded for cue in (" kurnia insurans ", " kurnia insurance ", " kurnia auto assist ")) else 0)
        + (4 if " kurnia " in padded else 0)
    )
    return {"liberty": liberty_score, "amassurance": am_score, "kurnia": kurnia_score}


def _append_liberty_group_winner(
    padded: str,
    company_rows: list[dict],
    out: list[dict],
) -> set[str]:
    """Append Priority 2 Liberty-group matches and return suppressed brand keys."""
    scores = _score_liberty_group_brands(padded)
    max_score = max(scores.values())
    if max_score <= 0:
        return set()
    winners = {brand for brand, score in scores.items() if score == max_score}
    suppressed = set(scores.keys()) - winners
    for company in company_rows:
        c_name = normalize_detection(str(company.get("name") or ""))
        if "liberty" in winners and "liberty" in c_name:
            out.append({"company": company, "alias": "www.libertyinsurance.com.my", "length": 500, "compact": False})
        elif "kurnia" in winners and "kurnia" in c_name:
            out.append({"company": company, "alias": "www.kurnia.com", "length": 500, "compact": False})
        elif "amassurance" in winners and ("amassurance" in c_name or "amgen" in c_name):
            out.append({"company": company, "alias": "AmAssurance", "length": 500, "compact": False})
    return suppressed


def _append_mmip_matches(padded: str, company_rows: list[dict], out: list[dict]) -> None:
    has_mmip_cue = any(
        cue in padded
        for cue in (
            " mmip ",
            " malaysian motor insurance pool ",
            " malaysia motor insurance pool ",
            " motor insurance pool ",
        )
    )
    if not has_mmip_cue:
        return
    for company in company_rows:
        c_name = str(company.get("name") or "").strip()
        c_aliases = [c_name, *(company.get("aliases") or [])]
        if any("mmip" in normalize_detection(str(a)) or "motor insurance pool" in normalize_detection(str(a)) for a in c_aliases):
            out.append({"company": company, "alias": "MMIP", "length": 10000, "compact": False})


def _collect_company_alias_hits(company: dict, padded: str, compact_text: str, out: list[dict]) -> None:
    name = str(company.get("name") or "").strip()
    if not name:
        return
    aliases = [name, *(company.get("aliases") or [])]
    padded_without_liberty_parent: str | None = None
    for raw_alias in aliases:
        normalized = normalize_detection(str(raw_alias))
        if len(normalized) < 2:
            continue
        if normalized == "liberty" and " liberty general insurance " in padded:
            if padded_without_liberty_parent is None:
                padded_without_liberty_parent = re.sub(r"\bliberty general insurance(?:\s+berhad)?\b|\bliberty insurance tower\b|\bby liberty insurance\b", " ", padded)
            if " liberty insurance " not in padded_without_liberty_parent and " libertyinsurance com " not in padded:
                continue
        if f" {normalized} " in padded:
            out.append({"company": company, "alias": raw_alias, "length": len(normalized), "compact": False})
        compact = normalized.replace(" ", "")
        if len(compact) >= 5 and (len(compact) >= 8 or len(compact_text) < 200) and compact in compact_text:
            out.append({"company": company, "alias": raw_alias, "length": len(compact), "compact": True})


def company_alias_matches(selected: str, company_rows: list[dict]) -> list[dict]:
    """Return company/alias matches for a detected string, best-first.

    Two strategies, in descending strength:
      * whole-token spaced: ``"amgeneral insurance"`` inside the padded text,
      * compact substring: ``"amgeneralinsurance"`` inside the de-spaced text,
        allowed only for aliases with >= 5 alphanumerics so short, common
        tokens ("tune" in "fortune", "qbe") never create false positives.

    Each item: {"company", "alias", "length", "compact"}; sorted by
    (length, spaced-over-compact) descending.
    """
    raw = (selected or "").strip()
    if not raw:
        return []
    scan_raw = _strip_liberty_shared_boilerplate(raw)
    spaced = normalize_detection(scan_raw)
    padded = f" {spaced} "
    compact_text = spaced.replace(" ", "")
    out: list[dict] = []

    # Priority 1: MMIP (Malaysian Motor Insurance Pool) overrides servicing insurer names on pool cases
    _append_mmip_matches(padded, company_rows, out)

    # Priority 2: Disambiguate Liberty / Kurnia / AmAssurance under Liberty General Insurance Berhad symmetrically
    has_liberty_parent = " liberty general insurance " in padded or " liberty " in padded
    suppressed_brands: set[str] = _append_liberty_group_winner(padded, company_rows, out) if has_liberty_parent else set()

    for company in company_rows:
        c_norm = normalize_detection(str(company.get("name") or ""))
        if c_norm and any(sb in c_norm or (sb == "amassurance" and "amgen" in c_norm) for sb in suppressed_brands):
            continue
        _collect_company_alias_hits(company, padded, compact_text, out)

    # Sort by length (descending), then spaced (not compact) over compact
    out.sort(key=lambda item: (item["length"], not item["compact"]), reverse=True)
    return out


def build_companies_payload(company_rows, alias_rows=None) -> list[dict]:
    """Build the db_companies payload used by extraction and resolution.

    Each company carries its canonical name, source template category, and a
    deduplicated alias list combined from `detection_phrases` and the active
    `CompanyAlias` rows. Callers are responsible for filtering to active rows.
    """
    aliases_by_company: dict[str, list[str]] = {}
    if alias_rows is not None:
        for item in alias_rows:
            aliases_by_company.setdefault(str(item.company_id), []).append(str(item.alias))
    return [
        {
            "company_id": company.id,
            "name": company.name,
            "source_template_category": company.source_template_category,
            "aliases": list(
                dict.fromkeys([
                    *(company.detection_phrases or []),
                    *aliases_by_company.get(str(company.id), []),
                ])
            ),
        }
        for company in company_rows
    ]


def resolve_company(selected: str, companies: list[dict]) -> dict:
    """Resolve a detected company string to a company by name or alias.

    Longest (most specific) match wins and is de-duplicated by company id.
    Returns:
      {"status": "matched"|"ambiguous"|"unresolved",
       "company_id": str|None, "display_name": str|None}

    ``companies`` entries: {"company_id", "name", "aliases": list[str], ...}.
    """
    raw = (selected or "").strip()
    if not raw:
        return {"status": "unresolved", "company_id": None, "display_name": None}
    matches = company_alias_matches(raw, companies)
    if not matches:
        return {"status": "unresolved", "company_id": None, "display_name": raw}
    best_length = matches[0]["length"]
    best = [item for item in matches if item["length"] == best_length]
    unique_ids = {item["company"]["company_id"] for item in best}
    if len(unique_ids) != 1:
        return {"status": "ambiguous", "company_id": None, "display_name": raw}
    winner = best[0]["company"]
    return {
        "status": "matched",
        "company_id": winner.get("company_id"),
        "display_name": winner.get("name"),
    }
