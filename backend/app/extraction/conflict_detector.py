"""Candidate selection without silent guessing."""

from __future__ import annotations

from collections import Counter

from app.extraction.types import CandidateValue, FieldSelection


REQUIRED_FIELDS = {"customer_name", "vehicle_no", "insurance_company", "car_brand", "car_model", "vehicle_year", "cover_start_date", "cover_end_date", "premium", "total_amount"}


def _norm(value: str) -> str:
    return " ".join(value.upper().replace("RM", "").replace(",", "").split())


def select_field(field: str, candidates: list[CandidateValue]) -> FieldSelection:
    if not candidates:
        return FieldSelection(None, "check_needed" if field in REQUIRED_FIELDS else "ready", [], ["Missing value."])

    # Special handling for company detection:
    # If an exact match was found in the upload filename or text via database_company_*,
    # prefer the verified database match over an ungrounded or conflicting Gemini guess.
    if field in ("insurance_company", "source_template_category"):
        db_cand = next((c for c in candidates if getattr(c, "source_method", "") in ("database_company_filename", "database_company_text") and c.value and str(c.value).strip()), None)
        gemini_cand = next((c for c in candidates if getattr(c, "source_method", "") == "gemini_vision" and c.value and str(c.value).strip()), None)
        if db_cand and gemini_cand:
            if _norm(db_cand.value) == _norm(gemini_cand.value):
                return FieldSelection(gemini_cand.value, "ready", candidates, [])
            return FieldSelection(db_cand.value, "ready", candidates, [])
        if db_cand:
            return FieldSelection(db_cand.value, "ready", candidates, [])
        if gemini_cand:
            return FieldSelection(gemini_cand.value, "ready", candidates, [])

    # Prioritize Gemini Multimodal AI extraction directly over heuristic candidates
    gemini_cand = next((c for c in candidates if getattr(c, "source_method", "") == "gemini_vision" and c.value and str(c.value).strip()), None)
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
