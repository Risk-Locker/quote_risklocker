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
    spaced = normalize_detection(raw)
    padded = f" {spaced} "
    compact_text = spaced.replace(" ", "")
    out: list[dict] = []
    for company in company_rows:
        name = str(company.get("name") or "").strip()
        if not name:
            continue
        aliases = [name, *(company.get("aliases") or [])]
        for raw_alias in aliases:
            normalized = normalize_detection(str(raw_alias))
            if len(normalized) < 2:
                continue
            if f" {normalized} " in padded:
                out.append({"company": company, "alias": raw_alias, "length": len(normalized), "compact": False})
            compact = normalized.replace(" ", "")
            
            # If the search text is very long (e.g. a full document), short compact matches 
            # (like 'amgen') are likely false positives formed by crossing word boundaries.
            if len(compact) >= 5 and (len(compact) >= 8 or len(compact_text) < 200):
                if compact in compact_text:
                    out.append({"company": company, "alias": raw_alias, "length": len(compact), "compact": True})
    
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
