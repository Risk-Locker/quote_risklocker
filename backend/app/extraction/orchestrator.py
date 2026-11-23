"""Extraction orchestrator that saves full hidden detail and simple draft data."""

from __future__ import annotations

from pathlib import Path
import re

from app.core.errors import AIExtractionUnavailableException
from app.extraction.brand_logo_scanner import (
    extract_page1_primary_brand_signals,
    is_liberty_group_document,
    render_page1_logo_crop,
    verify_brand_logo_with_vision,
)
from app.extraction.candidate_finder import find_candidates
from app.extraction.benefit_lines import extract_benefit_lines, is_spurious_benefit_line
from app.extraction.draft_mapper import build_draft
from app.extraction.layout import detect_layout
from app.extraction.native_pdf import extract_native
from app.extraction.ocr import run_enhanced_reading
from app.extraction.types import CandidateValue


def _augment_liberty_company_candidates(
    *,
    pdf_bytes: bytes,
    page1_text: str,
    combined_text: str,
    source_filename: str,
    db_companies: list[dict] | None,
    candidates: dict[str, list[CandidateValue]],
    gemini_res: dict | None,
    logo_crop_png: bytes | None,
    logo_color_meta: dict,
) -> None:
    """Run visual logo + Page 1 verification whenever Liberty-group brands compete."""
    if not is_liberty_group_document(combined_text, page1_text, source_filename):
        return
    p1_sig = extract_page1_primary_brand_signals(page1_text)
    if p1_sig.get("winning_brand"):
        candidates.setdefault("insurance_company", []).append(
            CandidateValue(
                field="insurance_company",
                value=str(p1_sig["winning_brand"]),
                source_method="page1_brand_signal",
                score=0.97,
                page=1,
                evidence=f"Page 1 primary brand signal: {', '.join(p1_sig.get('evidence') or [])}",
            )
        )

    existing_vals = {
        c.value.strip().lower()
        for c in candidates.get("insurance_company", [])
        if getattr(c, "value", None)
    }
    gemini_comp = str((gemini_res or {}).get("insurance_company") or "").strip()
    needs_logo_verify = (
        not gemini_comp
        or "general insurance" in gemini_comp.lower()
        or len(existing_vals) > 1
        or (p1_sig.get("winning_brand") and gemini_comp.lower() != str(p1_sig["winning_brand"]).lower())
    )
    if not needs_logo_verify or not pdf_bytes:
        return

    verdict = verify_brand_logo_with_vision(
        pdf_bytes,
        page1_text=page1_text,
        source_filename=source_filename,
        db_companies=db_companies,
        logo_crop_png=logo_crop_png,
        color_meta=logo_color_meta,
    )
    canonical = str((verdict or {}).get("canonical_company") or (verdict or {}).get("insurance_company") or "").strip()
    conf = float((verdict or {}).get("confidence") or 0.0)
    if verdict is not None and canonical and conf >= 0.85:
        candidates.setdefault("insurance_company", []).insert(
            0,
            CandidateValue(
                field="insurance_company",
                value=canonical,
                source_method="logo_vision_verified",
                score=min(0.995, max(0.92, conf)),
                page=1,
                evidence=f"Logo vision ({verdict.get('logo_color_observed', '')}): {verdict.get('reasoning', '')}",
            ),
        )
        if gemini_res is not None:
            gemini_res["insurance_company"] = canonical


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
        db_packs: list[dict] | None = None,
        db_corrections: list[dict] | None = None,
        fail_closed: bool = False,
        **kwargs,
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
        gemini_telemetry: list[dict] = []
        try:
            from app.extraction.gemini_extractor import extract_with_gemini_sync, get_key_pool

            pdf_bytes = file_path.read_bytes()
            pool_keys = get_key_pool().get_all_keys()
            if not pool_keys:
                if fail_closed:
                    raise AIExtractionUnavailableException(
                        reason="No GEMINI_API_KEY configured in pool.",
                        status_code=503,
                        detail="AI Extraction Unavailable: No GEMINI_API_KEY configured. Please verify API billing or switch keys.",
                    )
                warnings.append("AI Notice: No GEMINI_API_KEY configured. Extracted via native PDF/OCR fallback.")
            elif len(pdf_bytes) > 500:
                page1_text = str((combined_page_text[0] if combined_page_text else {}).get("text") or "")
                logo_crop_png: bytes | None = None
                logo_color_meta: dict = {}
                if is_liberty_group_document(combined_text, page1_text, source_filename or file_path.name):
                    logo_crop_png, logo_color_meta = render_page1_logo_crop(pdf_bytes)
                item_idx = abs(hash(source_filename or file_path.name)) % 100
                gemini_res = extract_with_gemini_sync(
                    pdf_bytes,
                    document_text=combined_text,
                    source_filename=source_filename or file_path.name,
                    db_companies=db_companies,
                    db_benefit_concepts=db_benefit_concepts,
                    db_aliases=db_aliases,
                    db_packs=db_packs,
                    correction_memory=db_corrections,
                    prompt_override=prompt_override,
                    logo_crop_png=logo_crop_png,
                    batch_item_index=item_idx,
                    telemetry_log=gemini_telemetry,
                )
                _augment_liberty_company_candidates(
                    pdf_bytes=pdf_bytes,
                    page1_text=page1_text,
                    combined_text=combined_text,
                    source_filename=source_filename or file_path.name,
                    db_companies=db_companies,
                    candidates=candidates,
                    gemini_res=gemini_res,
                    logo_crop_png=logo_crop_png,
                    logo_color_meta=logo_color_meta,
                )
                if not gemini_res:
                    if fail_closed:
                        pool = get_key_pool()
                        last_err = pool.get_last_error_message() or "API Token Quota Exhausted or Rate-Limited"
                        status_code = 429 if any(k in last_err.lower() for k in ["429", "quota", "rate"]) else 503
                        raise AIExtractionUnavailableException(
                            reason=last_err,
                            status_code=status_code,
                            detail=f"AI Extraction Unavailable: API Token Quota Exhausted. Please verify API billing or switch keys. ({last_err})",
                        )
                    warnings.append("AI Notice: Gemini AI token quota expired or rate-limited. Extracted via native PDF/OCR fallback.")
            else:
                gemini_res = None
            if gemini_res:
                winning_call = next((t for t in reversed(gemini_telemetry) if t.get("is_success")), None)
                used_model = winning_call.get("model") if winning_call else "gemini"
                method_summary.append(f"Gemini AI Extraction ({used_model})")
                for key, val in gemini_res.items():
                    if key in {"detected_benefits", "detected_package_name"} or val is None or str(val).strip() == "":
                        continue
                    clean_val = str(val).strip()
                    keys_to_populate = [key]
                    if key in {"coverage_amount", "sum_insured"}:
                        keys_to_populate = ["coverage_amount", "sum_insured", "market_value", "agreed_value"]
                    for target_key in keys_to_populate:
                        existing = candidates.get(target_key, [])
                        norm_clean = re.sub(r"[\s,.-]", "", clean_val).lower()
                        has_agreement = any(
                            re.sub(r"[\s,.-]", "", c.value).lower() == norm_clean
                            for c in existing
                        )
                        calibrated_score = 0.98 if has_agreement else (0.88 if existing else 0.92)
                        gemini_candidate = CandidateValue(
                            field=target_key,
                            value=clean_val,
                            source_method="gemini_vision",
                            score=calibrated_score,
                            page=1,
                            evidence=f"Gemini multimodal extraction: {clean_val}",
                        )
                        if target_key in candidates:
                            candidates[target_key].insert(0, gemini_candidate)
                        else:
                            candidates[target_key] = [gemini_candidate]

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
                from app.services.bundle_plan_matcher import extract_plan_tier_token, is_base_auto365_policy_label

                gemini_benefits = gemini_res.get("detected_benefits") or []
                for b_item in gemini_benefits:
                    if isinstance(b_item, dict):
                        b_label = str(b_item.get("label") or "").strip()
                        b_val = str(b_item.get("value") or "").strip()
                        b_key = str(b_item.get("concept_key") or "").strip()
                        b_plan = str(b_item.get("plan_tier") or "").strip()
                        cov_limit = str(b_item.get("coverage_limit") or "").strip()
                        cost = str(b_item.get("premium_cost") or "").strip()
                        is_optional = bool(b_item.get("is_optional_cover", False))
                        b_raw = str(b_item.get("raw_text") or f"{b_label}: {b_val}").strip()
                    elif isinstance(b_item, str):
                        b_label = b_item.strip()
                        b_val = ""
                        b_key = ""
                        b_plan = ""
                        cov_limit = ""
                        cost = ""
                        is_optional = False
                        b_raw = b_label
                    else:
                        continue
                    inferred_plan = b_plan or extract_plan_tier_token(f"{b_label} {b_val} {b_raw}") or ""

                    if b_label:
                        if is_base_auto365_policy_label(b_label) or is_spurious_benefit_line(b_label) or is_spurious_benefit_line(b_raw):
                            continue
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

                        clean_cov = re.sub(r"[^0-9.]", "", cov_limit)
                        clean_cost = re.sub(r"[^0-9.]", "", cost)
                        clean_val = re.sub(r"[^0-9.]", "", b_val)

                        # Genuine coverage limit must be non-zero and distinct from premium price
                        final_cov_limit = ""
                        if clean_cov:
                            try:
                                c_num = float(clean_cov)
                                p_num = float(clean_cost) if clean_cost else None
                                if c_num > 0 and (p_num is None or abs(c_num - p_num) > 0.01):
                                    final_cov_limit = cov_limit
                            except Exception:
                                final_cov_limit = cov_limit
                        elif clean_val and clean_cost:
                            try:
                                v_num = float(clean_val)
                                p_num = float(clean_cost)
                                if v_num > 0 and abs(v_num - p_num) > 0.01 and b_val.lower() not in {"included", "standard", "yes", "true"}:
                                    final_cov_limit = b_val
                            except Exception:
                                pass

                        typed_val = None
                        if final_cov_limit:
                            clean_limit = final_cov_limit.upper().replace("RM", "").replace(",", "").strip()
                            is_pure_money = bool(re.match(r"^\s*(?:RM\s*)?[\d]+(?:,\d{3})*(?:\.\d{1,2})?\s*$", final_cov_limit, re.IGNORECASE))
                            if is_pure_money:
                                typed_val = {
                                    "type": "money",
                                    "value": clean_limit,
                                    "currency": "MYR",
                                    "semantic_role": "limit",
                                    "display_text": final_cov_limit if final_cov_limit.startswith("RM") else f"RM {final_cov_limit}",
                                }
                            else:
                                typed_val = {
                                    "type": "text",
                                    "value": final_cov_limit,
                                    "semantic_role": "limit",
                                    "display_text": final_cov_limit,
                                }
                        elif cost:
                            clean_cost_val = cost.upper().replace("RM", "").replace(",", "").strip()
                            is_pure_money = bool(re.match(r"^\s*(?:RM\s*)?[\d]+(?:,\d{3})*(?:\.\d{1,2})?\s*$", cost, re.IGNORECASE))
                            if is_pure_money:
                                typed_val = {
                                    "type": "money",
                                    "value": clean_cost_val,
                                    "currency": "MYR",
                                    "semantic_role": "premium",
                                    "display_text": f"RM {clean_cost_val}",
                                }
                            else:
                                typed_val = {
                                    "type": "text",
                                    "value": cost,
                                    "semantic_role": "premium",
                                    "display_text": cost,
                                }

                        elif inferred_plan:
                            typed_val = {
                                "type": "custom",
                                "value": inferred_plan,
                                "plan_key": inferred_plan.lower().replace(" ", "_"),
                                "display_text": inferred_plan,
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
                            "coverage_limit": final_cov_limit,
                            "premium_cost": cost,
                            "plan_tier": inferred_plan,
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
                                    "evidence": final_cov_limit or b_val,
                                    "shaped_description": f"{b_label} ({final_cov_limit})" if final_cov_limit else b_label,
                                    "coverage_limit": final_cov_limit,
                                    "premium_cost": cost,
                                    "plan_tier": inferred_plan,
                                    "is_detected": True,
                                }
                            ] if concept_id or c_key else [],
                        })

                        # Directly bind windscreen and special perils candidates for draft fields
                        if (c_key == "windscreen" or "windscreen" in b_norm or "cermin" in b_norm) and final_cov_limit:
                            clean_limit_val = re.sub(r"[^0-9.]", "", final_cov_limit)
                            if clean_limit_val:
                                try:
                                    w_num = float(clean_limit_val)
                                    if 500.0 <= w_num <= 50000.0:
                                        candidates["windscreen_sum_insured"] = [
                                            CandidateValue(
                                                field="windscreen_sum_insured",
                                                value=f"{w_num:.2f}",
                                                source_method="gemini_vision",
                                                score=0.99,
                                                page=1,
                                                evidence=f"Gemini windscreen: {b_label} limit {w_num}",
                                            )
                                        ]
                                except Exception:
                                    pass
                            if cost:
                                clean_cost_val = re.sub(r"[^0-9.]", "", cost)
                                if clean_cost_val:
                                    try:
                                        wp_num = float(clean_cost_val)
                                        if wp_num > 0:
                                            candidates["windscreen_premium"] = [
                                                CandidateValue(
                                                    field="windscreen_premium",
                                                    value=f"{wp_num:.2f}",
                                                    source_method="gemini_vision",
                                                    score=0.99,
                                                    page=1,
                                                    evidence=f"Gemini windscreen premium: {wp_num}",
                                                )
                                            ]
                                    except Exception:
                                        pass
                        elif (c_key == "special-perils" or "special-peril" in b_norm or "peril-khas" in b_norm or "banjir" in b_norm) and cost:
                            clean_cost_val = re.sub(r"[^0-9.]", "", cost)
                            if clean_cost_val:
                                try:
                                    sp_num = float(clean_cost_val)
                                    if sp_num > 0:
                                        candidates["special_perils_premium"] = [
                                            CandidateValue(
                                                field="special_perils_premium",
                                                value=f"{sp_num:.2f}",
                                                source_method="gemini_vision",
                                                score=0.99,
                                                page=1,
                                                evidence=f"Gemini special perils premium: {sp_num}",
                                            )
                                        ]
                                except Exception:
                                    pass
        except AIExtractionUnavailableException:
            raise
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Gemini multimodal extraction note: %s", exc)
            if fail_closed and any(term in str(exc).lower() for term in ["429", "quota", "rate limit", "resourceexhausted", "unauthenticated", "401", "403"]):
                raise AIExtractionUnavailableException(
                    reason=str(exc),
                    status_code=429,
                    detail=f"AI Extraction Unavailable: {exc}",
                ) from exc
            warnings.append(f"Gemini multimodal extraction note: {exc}")

        fields, draft_warnings, draft_status = build_draft(
            candidates,
            benefit_lines=benefit_lines,
            raw_text=combined_text,
        )
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
        fallback_lines = extract_benefit_lines(combined_page_text, concepts=db_benefit_concepts or [])
        if not benefit_lines:
            benefit_lines = fallback_lines
        elif fallback_lines:
            from app.services.bundle_plan_matcher import is_base_auto365_policy_label

            # Merge only mapped deterministic lines that Gemini genuinely missed (never unmapped scraps or duplicate concepts)
            existing_labels = {
                (b.get("normalized_label") or b.get("raw_label") or "").lower().strip()
                for b in benefit_lines
            }
            existing_concept_keys = {
                str(m.get("concept_key") or "").strip()
                for b in benefit_lines
                for m in (b.get("candidate_mappings") or [])
                if isinstance(m, dict) and m.get("concept_key")
            }
            for fl in fallback_lines:
                fl_lbl = (fl.get("normalized_label") or fl.get("raw_label") or "").lower().strip()
                if not fl_lbl or is_base_auto365_policy_label(fl_lbl) or is_spurious_benefit_line(fl_lbl):
                    continue
                fl_maps = [m for m in (fl.get("candidate_mappings") or []) if isinstance(m, dict) and m.get("concept_key")]
                if not fl_maps:
                    continue
                fl_keys = {str(m.get("concept_key") or "").strip() for m in fl_maps}
                if fl_keys & existing_concept_keys:
                    continue
                if not any(fl_lbl in ex or ex in fl_lbl for ex in existing_labels):
                    fl["line_id"] = f"det_{len(benefit_lines) + 1}"
                    benefit_lines.append(fl)
                    existing_labels.add(fl_lbl)
                    existing_concept_keys.update(fl_keys)

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
                "gemini_telemetry": gemini_telemetry,
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
