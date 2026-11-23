"""Candidate selection without silent guessing."""

from __future__ import annotations

from collections import Counter

from app.extraction.types import CandidateValue, FieldSelection


REQUIRED_FIELDS = {"customer_name", "vehicle_no", "insurance_company", "car_brand", "car_model", "vehicle_year", "cover_start_date", "cover_end_date", "premium", "total_amount"}


def _norm(value: str) -> str:
    return " ".join(value.upper().replace("RM", "").replace(",", "").split())


_LIBERTY_GROUP_TOKENS = ("AMASSURANCE", "AMGEN", "AMGENERAL", "KURNIA", "LIBERTY")


def _is_liberty_group_brand(value: str | None) -> bool:
    upper = (value or "").upper()
    return any(tok in upper for tok in _LIBERTY_GROUP_TOKENS)


def _resolve_text_vs_gemini(
    field: str,
    txt_cands: list[CandidateValue],
    gemini_cand: CandidateValue,
    candidates: list[CandidateValue],
) -> FieldSelection:
    unique_txt = {_norm(c.value) for c in txt_cands}
    if len(unique_txt) == 1 and _norm(txt_cands[0].value) == _norm(gemini_cand.value):
        return FieldSelection(gemini_cand.value, "ready", candidates, [])
    if (
        field == "insurance_company"
        and _is_liberty_group_brand(gemini_cand.value)
        and all(_is_liberty_group_brand(c.value) for c in txt_cands)
    ):
        return FieldSelection(gemini_cand.value, "ready", candidates, [])
    return FieldSelection(txt_cands[0].value, "ready", candidates, [])


def _select_company_field(field: str, candidates: list[CandidateValue]) -> FieldSelection | None:
    """Resolve insurance_company / source_template_category prioritizing MMIP & visual logo checks."""
    valid = [c for c in candidates if c.value and c.value.strip()]
    by_method: dict[str, list[CandidateValue]] = {}
    for c in valid:
        by_method.setdefault(getattr(c, "source_method", ""), []).append(c)

    mmip_cand = by_method["mmip_priority"][0] if by_method.get("mmip_priority") else None
    if mmip_cand:
        return FieldSelection(mmip_cand.value, "ready", candidates, [])

    logo_cand = by_method["logo_vision_verified"][0] if by_method.get("logo_vision_verified") else None
    if logo_cand and field == "insurance_company" and float(getattr(logo_cand, "score", 0.0) or 0.0) >= 0.90:
        return FieldSelection(logo_cand.value, "ready", candidates, [])

    fn_cands = by_method.get("database_company_filename") or []
    txt_cands = by_method.get("database_company_text") or []
    p1_cands = by_method.get("page1_brand_signal") or []
    gemini_cand = by_method["gemini_vision"][0] if by_method.get("gemini_vision") else None

    if fn_cands and len({_norm(c.value) for c in fn_cands}) == 1:
        return FieldSelection(fn_cands[0].value, "ready", candidates, [])
    if txt_cands and gemini_cand:
        return _resolve_text_vs_gemini(field, txt_cands, gemini_cand, candidates)
    if p1_cands and gemini_cand and _norm(p1_cands[0].value) == _norm(gemini_cand.value):
        return FieldSelection(gemini_cand.value, "ready", candidates, [])
    if fn_cands:
        return FieldSelection(fn_cands[0].value, "ready", candidates, [])
    if p1_cands:
        return FieldSelection(p1_cands[0].value, "ready", candidates, [])
    if txt_cands:
        status = "check_needed" if len({_norm(c.value) for c in txt_cands}) > 1 else "ready"
        reasons = ["Conflicting values found."] if status == "check_needed" else []
        return FieldSelection(txt_cands[0].value, status, candidates, reasons)
    if gemini_cand:
        return FieldSelection(gemini_cand.value, "ready", candidates, [])
    return None


def select_field(field: str, candidates: list[CandidateValue]) -> FieldSelection:
    if not candidates:
        return FieldSelection(None, "check_needed" if field in REQUIRED_FIELDS else "ready", [], ["Missing value."])

    # Special handling for company detection:
    # 1) MMIP pool priority always wins.
    # 2) Verified Page 1 logo vision scan beats noisy text/shared boilerplate for Liberty-group brands.
    # 3) Verified upload filename match beats noisy text matches.
    # 4) When text heuristics conflict with Gemini Vision among Liberty-group brands, trust Gemini Vision.
    if field in ("insurance_company", "source_template_category"):
        selected_company = _select_company_field(field, candidates)
        if selected_company is not None:
            return selected_company

    # Prioritize Gemini Multimodal AI extraction directly over heuristic candidates
    gemini_cand = next((c for c in candidates if getattr(c, "source_method", "") == "gemini_vision" and c.value and c.value.strip()), None)
    if gemini_cand:
        return FieldSelection(gemini_cand.value, "ready", candidates, [])

    ranked = sorted(candidates, key=lambda candidate: candidate.score, reverse=True)
    best_by_score = ranked[0]
    high_confidence = [candidate for candidate in ranked if candidate.score >= 0.93]
    high_confidence_norms = {_norm(candidate.value) for candidate in high_confidence}
    if high_confidence:
        if len(high_confidence_norms) > 1:
            return FieldSelection(best_by_score.value, "check_needed", candidates, ["Conflicting values found."])
        return FieldSelection(best_by_score.value, "ready", candidates, [])

    normalized = [_norm(candidate.value) for candidate in candidates]
    counts = Counter(normalized)
    top_norm, top_count = counts.most_common(1)[0]
    top_candidates = [candidate for candidate in candidates if _norm(candidate.value) == top_norm]
    best = sorted(top_candidates, key=lambda candidate: candidate.score, reverse=True)[0]

    if len(counts) > 1 and top_count == 1:
        return FieldSelection(best_by_score.value, "check_needed", candidates, ["Conflicting values found."])

    if best.score < 0.75 and field in REQUIRED_FIELDS:
        return FieldSelection(best.value, "check_needed", candidates, ["Please check this value."])

    return FieldSelection(best.value, "ready", candidates, [])


def select_all(candidates: dict[str, list[CandidateValue]], fields: list[str]) -> dict[str, FieldSelection]:
    return {field: select_field(field, candidates.get(field, [])) for field in fields}
