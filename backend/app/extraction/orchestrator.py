"""Extraction orchestrator that saves full hidden detail and simple draft data."""

from __future__ import annotations

from pathlib import Path

from app.extraction.candidate_finder import find_candidates
from app.extraction.benefit_lines import extract_benefit_lines
from app.extraction.draft_mapper import build_draft
from app.extraction.layout import detect_layout
from app.extraction.native_pdf import extract_native
from app.extraction.ocr import run_enhanced_reading
from app.extraction.types import CandidateValue


class ExtractionOrchestrator:
    def extract_file(
        self,
        file_path: Path,
        enhanced_reading: bool = False,
        source_filename: str | None = None,
        db_aliases: dict | None = None,
        db_brands: list[str] | None = None,
        db_models: list[str] | None = None,
        db_companies: list[dict] | None = None,
        db_benefit_concepts: list[dict] | None = None,
    ) -> dict:
        native = extract_native(file_path)
        ocr_text = ""
        method_summary = list(native.method_summary)
        warnings = list(native.warnings)

        if enhanced_reading or len(native.raw_text.strip()) < 80:
            enhanced_text, enhanced_methods, enhanced_warnings = run_enhanced_reading(file_path)
            ocr_text = enhanced_text
            method_summary.extend(enhanced_methods)
            warnings.extend(enhanced_warnings)

        layout_regions, layout_warnings = detect_layout(native.words)
        warnings.extend(layout_warnings)

        combined_text = "\n".join(part for part in [native.raw_text, ocr_text] if part)
        ocr_page_text = [{"page": 1, "text": ocr_text, "source_method": "ocr"}] if ocr_text.strip() else []
        combined_page_text = [*native.page_text, *ocr_page_text]
        candidates = find_candidates(
            combined_text,
            combined_page_text,
            native.words,
            aliases=db_aliases,
            source_filename=source_filename or file_path.name,
            db_brands=db_brands,
            db_models=db_models,
            db_companies=db_companies,
        )
        fields, draft_warnings, draft_status = build_draft(candidates)
        warnings.extend(draft_warnings)

        candidate_payload = {
            field: [candidate.to_dict() for candidate in field_candidates]
            for field, field_candidates in candidates.items()
        }
        reading_quality = "ready" if draft_status == "Ready" else "cannot_read" if draft_status == "Cannot Read" else "check_needed"
        benefit_lines = extract_benefit_lines(combined_page_text, concepts=db_benefit_concepts or [])

        return {
            "full_record": {
                "raw_text": native.raw_text,
                "ocr_text": ocr_text,
                "page_text": native.page_text,
                "ocr_page_text": ocr_page_text,
                "words": native.words,
                "blocks": native.blocks,
                "tables": native.tables,
                "images": native.images,
                "regions": layout_regions,
                "candidates": candidate_payload,
                "benefit_lines": benefit_lines,
                "method_summary": method_summary,
                "warnings": warnings,
                "reading_quality": reading_quality,
            },
            "draft": {
                "fields": fields,
                "warnings": warnings,
                "status": draft_status,
            },
        }


def candidate_values_from_payload(payload: dict) -> dict[str, list[CandidateValue]]:
    return {
        field: [CandidateValue(**candidate) for candidate in candidates]
        for field, candidates in payload.items()
    }
