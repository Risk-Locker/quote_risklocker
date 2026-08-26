"""Extraction orchestrator that saves full hidden detail and simple draft data."""

from __future__ import annotations

from pathlib import Path
import re

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
        prompt_override: str | None = None,
    ) -> dict:
        native = extract_native(file_path)
        ocr_text = ""
        method_summary = list(native.method_summary)
        warnings = list(native.warnings)

        # Only run expensive OCR if native text is genuinely missing or sparse (< 80 chars)
        if len(native.raw_text.strip()) < 80:
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
        benefit_lines: list[dict] = []
        # Check Gemini Multimodal Extraction (Free Tier / Multi-Key Pool)
        gemini_res = None
        try:
            from app.extraction.gemini_extractor import extract_with_gemini_sync, get_key_pool
            pdf_bytes = file_path.read_bytes()
            if get_key_pool().get_all_keys() and len(pdf_bytes) > 500:
                gemini_res = extract_with_gemini_sync(
                    pdf_bytes,
                    document_text=combined_text,
                    db_companies=db_companies,
                    db_benefit_concepts=db_benefit_concepts,
                    db_aliases=db_aliases,
                    prompt_override=prompt_override,
                )
            else:
                gemini_res = None
            if gemini_res:
                method_summary.append("Gemini 3.6 Flash AI Extraction")
                for key, val in gemini_res.items():
                    if key in {"detected_benefits", "detected_package_name"} or val is None or str(val).strip() == "":
                        continue
                    clean_val = str(val).strip()
                    gemini_candidate = CandidateValue(
                        field=key,
                        value=clean_val,
                        source_method="gemini_vision",
                        score=0.99,
                        page=1,
                        evidence=f"Gemini multimodal extraction: {clean_val}",
                    )
                    if key in candidates:
                        candidates[key].insert(0, gemini_candidate)
                    else:
                        candidates[key] = [gemini_candidate]

                # If package detected, record as candidate
                pkg_name = str(gemini_res.get("detected_package_name") or "").strip()
                if pkg_name:
                    pkg_candidate = CandidateValue(
                        field="product_tier",
                        value=pkg_name,
                        source_method="gemini_vision",
                        score=0.99,
                        page=1,
                        evidence=f"Gemini detected package: {pkg_name}",
                    )
                    candidates["product_tier"] = [pkg_candidate]
                    candidates["tier_name"] = [pkg_candidate]

                # Map Gemini detected benefits
                gemini_benefits = gemini_res.get("detected_benefits") or []
                for b_item in gemini_benefits:
                    b_label = str(b_item.get("label") or "").strip()
                    b_val = str(b_item.get("value") or "").strip()
                    b_key = str(b_item.get("concept_key") or "").strip()
                    b_raw = str(b_item.get("raw_text") or f"{b_label}: {b_val}").strip()
                    if b_label:
                        # Find matching concept robustly across id/concept_id, key/concept_key, name/label
                        matched_concept = None
                        b_norm = b_label.lower().replace(" ", "-").replace("_", "-")
                        for c in (db_benefit_concepts or []):
                            c_k = (c.get("concept_key") or c.get("key") or "").lower().replace("_", "-")
                            c_lbl = (c.get("label") or c.get("name") or "").lower()
                            if b_key and c_k and (c_k == b_key.lower().replace("_", "-")):
                                matched_concept = c
                                break
                            if c_lbl and (c_lbl == b_label.lower() or c_lbl in b_label.lower() or b_label.lower() in c_lbl):
                                matched_concept = c
                                break
                            if b_norm and c_k and (c_k in b_norm or b_norm in c_k):
                                matched_concept = c
                                break

                        concept_id = (matched_concept.get("concept_id") or matched_concept.get("id")) if matched_concept else None
                        c_key = (matched_concept.get("concept_key") or matched_concept.get("key")) if matched_concept else (b_key or b_norm)
                        cov_limit = str(b_item.get("coverage_limit") or "").strip()
                        cost = str(b_item.get("premium_cost") or "").strip()
                        is_optional = bool(b_item.get("is_optional_cover", False))
                        
                        limit_val = cov_limit or (b_val if b_val.lower() not in {"included", "standard", "yes", "true"} else "")
                        typed_val = None
                        if limit_val:
                            clean_limit = limit_val.upper().replace("RM", "").replace(",", "").strip()
                            is_pure_money = bool(re.match(r"^\s*(?:RM\s*)?[\d]+(?:,\d{3})*(?:\.\d{1,2})?\s*$", limit_val, re.IGNORECASE))
                            if is_pure_money:
                                typed_val = {
                                    "type": "money",
                                    "value": clean_limit,
                                    "currency": "MYR",
                                    "display_text": limit_val if limit_val.startswith("RM") else f"RM {limit_val}",
                                }
                            else:
                                typed_val = {
                                    "type": "text",
                                    "value": limit_val,
                                    "display_text": limit_val,
                                }
                        elif cost:
                            clean_cost = cost.upper().replace("RM", "").replace(",", "").strip()
                            is_pure_money = bool(re.match(r"^\s*(?:RM\s*)?[\d]+(?:,\d{3})*(?:\.\d{1,2})?\s*$", cost, re.IGNORECASE))
                            if is_pure_money:
                                typed_val = {
                                    "type": "money",
                                    "value": clean_cost,
                                    "currency": "MYR",
                                    "display_text": f"RM {clean_cost}",
                                }
                            else:
                                typed_val = {
                                    "type": "text",
                                    "value": cost,
                                    "display_text": cost,
                                }

                        benefit_lines.append({
                            "line_id": f"gemini_{len(benefit_lines) + 1}",
                            "raw_label": b_label,
                            "raw_text": b_raw or b_label,
                            "normalized_label": b_label.lower(),
                            "normalized_text": b_label.lower(),
                            "page_number": 1,
                            "page": 1,
                            "section": "Optional Covers" if is_optional else "Selected Benefits",
                            "source_scope": "selected",
                            "line_kind": "benefit_candidate",
                            "heading_category": "selected",
                            "inclusion_state": "selected",
                            "confidence": 1.0,
                            "source_disposition": "auto_apply",
                            "is_detected": True,
                            "coverage_limit": cov_limit or b_val,
                            "premium_cost": cost,
                            "is_optional_cover": is_optional,
                            "extracted_value": typed_val,
                            "candidate_mappings": [
                                {
                                    "concept_id": concept_id,
                                    "concept_key": c_key,
                                    "name": b_label,
                                    "matched_alias": b_label,
                                    "score": 100,
                                    "match_type": "gemini_multimodal",
                                    "evidence": b_val,
                                    "shaped_description": f"{b_label} ({b_val})" if b_val and b_val.lower() != "included" else b_label,
                                    "coverage_limit": cov_limit or b_val,
                                    "premium_cost": cost,
                                    "is_detected": True,
                                }
                            ] if concept_id or c_key else [],
                        })
        except Exception as exc:
            warnings.append(f"Gemini multimodal extraction note: {exc}")

        fields, draft_warnings, draft_status = build_draft(candidates)
        warnings.extend(draft_warnings)

        candidate_payload = {
            field: [candidate.to_dict() for candidate in field_candidates]
            for field, field_candidates in candidates.items()
        }
        if gemini_res:
            detected_packs = gemini_res.get("detected_packs") or []
            if detected_packs:
                candidate_payload["detected_packs"] = detected_packs
        reading_quality = "ready" if draft_status == "Ready" else "cannot_read" if draft_status == "Cannot Read" else "check_needed"
        if not benefit_lines:
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
    result: dict[str, list[CandidateValue]] = {}
    for field, candidates in payload.items():
        if not isinstance(candidates, list):
            continue
        parsed: list[CandidateValue] = []
        for candidate in candidates:
            if not isinstance(candidate, dict) or "field" not in candidate:
                continue
            try:
                parsed.append(CandidateValue(**candidate))
            except (TypeError, ValueError):
                continue
        result[field] = parsed
    return result
