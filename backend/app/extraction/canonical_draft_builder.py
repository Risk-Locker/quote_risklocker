"""Shared Canonical Motor Pricing & Accounting Status Builder.

Eliminates split-brain divergence between Upload (`draft_mapper.py`) and Re-Detect
(`session_rescan_service.py`). Anchors `fields["premium"]`, `fields["motor_premium"]`,
and `fields["total_payable"]` strictly to the Underwriter Final Total Payable
without ever subtracting `extras_cost`, and computes `total_amount` cleanly in pure Decimal.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.domain.motor.discount_calculator import calculate_motor_discount, to_decimal_clean
from app.extraction.accounting_proof_gate import AccountingProofVerdict, verify_quotation_accounting


def apply_verified_motor_pricing(
    fields: dict[str, Any],
    gemini_res: dict[str, Any],
    *,
    is_covernote: bool = False,
    accounting_verdict: AccountingProofVerdict | None = None,
    preserved_pct: Decimal | None = None,
    preserved_flat: Decimal | None = None,
    inc_rt: bool = False,
    inc_rf: bool = False,
) -> AccountingProofVerdict:
    """Stamp canonical underwriter motor premium, discounts, and total_amount into draft fields."""
    verdict = accounting_verdict
    if verdict is None:
        raw_verdict = gemini_res.get("_accounting_verdict")
        if isinstance(raw_verdict, dict) and raw_verdict.get("authoritative_motor_premium"):
            verdict = AccountingProofVerdict(
                passed=bool(raw_verdict.get("passed", True)),
                authoritative_motor_premium=to_decimal_clean(raw_verdict.get("authoritative_motor_premium"), Decimal("0.00")),
                sum_optional_riders=to_decimal_clean(raw_verdict.get("sum_optional_riders"), Decimal("0.00")),
                expected_gross=to_decimal_clean(raw_verdict.get("expected_gross")) if raw_verdict.get("expected_gross") else None,
                expected_payable=to_decimal_clean(raw_verdict.get("expected_payable")) if raw_verdict.get("expected_payable") else None,
                discrepancies=list(raw_verdict.get("discrepancies") or []),
                quarantine_reason=raw_verdict.get("quarantine_reason"),
            )
        else:
            verdict = verify_quotation_accounting(gemini_res, is_covernote=is_covernote)

    uw_motor_dec = verdict.authoritative_motor_premium
    if uw_motor_dec is None or uw_motor_dec <= Decimal("0.00"):
        cand_total = to_decimal_clean(gemini_res.get("total_amount"), Decimal("0.00"))
        cand_prem = to_decimal_clean(gemini_res.get("premium"), Decimal("0.00"))
        uw_motor_dec = cand_total if cand_total > Decimal("0.00") else cand_prem

    # Only quarantine to check_needed when genuine multi-line accounting equations disagree
    # or comprehensive coverage amount fails sanity (missing optional breakdown vs stated total or Gross+SST+Stamp mismatch).
    has_quarantine = bool(verdict.quarantine_reason)
    prem_status = "check_needed" if has_quarantine else "ready"
    prem_msg = verdict.quarantine_reason or ""

    pct_dec = preserved_pct if preserved_pct is not None else to_decimal_clean(fields.get("motor_discount_pct"), Decimal("0.00"))
    flat_dec = preserved_flat if preserved_flat is not None else to_decimal_clean(fields.get("quotation_discount"), Decimal("0.00"))
    rt_dec = to_decimal_clean((fields.get("roadtax") or {}).get("value") if isinstance(fields.get("roadtax"), dict) else fields.get("roadtax"), Decimal("0.00")) if inc_rt else Decimal("0.00")
    rf_dec = to_decimal_clean((fields.get("service_fee") or {}).get("value") if isinstance(fields.get("service_fee"), dict) else fields.get("service_fee"), Decimal("0.00")) if inc_rf else Decimal("0.00")

    if uw_motor_dec > Decimal("0.00"):
        uw_str = f"{uw_motor_dec:.2f}"
        for key in ("premium", "motor_premium", "total_payable", "premium_due"):
            fields[key] = {
                "value": uw_str,
                "detected_value": uw_str,
                "status": prem_status,
                "warnings": [prem_msg] if prem_msg else [],
                "message": "Please verify pricing breakdown." if has_quarantine else "",
            }

        disc_bd = calculate_motor_discount(uw_motor_dec, pct_dec, flat_dec)
        fields["motor_discount_pct"] = {"value": f"{disc_bd.motor_discount_pct:.2f}", "status": "ready", "message": ""}
        fields["motor_discount_amount"] = {"value": f"{disc_bd.pct_discount_amount:.2f}", "status": "ready", "message": ""}
        fields["quotation_discount"] = {"value": f"{disc_bd.flat_discount_amount:.2f}", "status": "ready", "message": ""}
        fields["effective_discount"] = {"value": f"{disc_bd.effective_discount:.2f}", "status": "ready", "message": ""}
        fields["net_motor_premium"] = {"value": f"{disc_bd.net_motor_premium:.2f}", "status": "ready", "message": ""}
        tot_payable_str = f"{disc_bd.net_total_payable(rt_dec, rf_dec):.2f}"
        fields["total_amount"] = {
            "value": tot_payable_str,
            "detected_value": uw_str,
            "status": prem_status,
            "warnings": [prem_msg] if prem_msg else [],
            "message": "Please verify pricing breakdown." if has_quarantine else "",
        }
    return verdict


def run_orchestrator_vision_step(
    *,
    file_path: Any,
    source_filename: str,
    operative_text: str,
    operative_page_text: list[dict[str, Any]],
    pds_page_nums: list[int],
    candidates: dict[str, Any],
    db_aliases: Any,
    db_brands: Any,
    db_models: Any,
    db_companies: Any,
    db_benefit_concepts: Any,
    db_packs: Any,
    db_corrections: Any,
    prompt_override: str | None,
    fail_closed: bool,
    warnings: list[str],
    gemini_telemetry: list[dict[str, Any]],
    augment_liberty_fn: Any,
) -> tuple[dict[str, Any] | None, AccountingProofVerdict | None]:
    """Execute Upload-path Multi-Zoom Vision extraction + 400-DPI Decimal Proof Gate."""
    from app.core.errors import AIExtractionUnavailableException
    from app.extraction import gemini_extractor
    from app.extraction.brand_logo_scanner import (
        extract_liberty_group_spatial_brand,
        extract_page1_primary_brand_signals,
        is_liberty_group_document,
        render_page1_logo_crop,
    )
    from app.extraction.candidate_finder import detect_is_covernote
    from app.extraction.multi_zoom_pipeline import (
        _has_multi_slot_consensus_fleet,
        _merge_reconciled_result,
        run_multi_zoom_vision_pipeline,
    )
    from app.extraction.page_filter import slice_pdf_bytes_excluding_pages
    from app.extraction.visual_zone_crops import (
        render_header_footer_crops,
        render_schedule_and_pricing_crops,
    )

    pdf_bytes = file_path.read_bytes()
    operative_pdf_bytes = slice_pdf_bytes_excluding_pages(pdf_bytes, pds_page_nums)
    pool = gemini_extractor.get_key_pool()
    pool_keys = pool.get_all_keys()
    is_cn_doc = detect_is_covernote(
        text=operative_text,
        filename=source_filename or file_path.name,
        page_count=len(operative_page_text),
    )
    if not pool_keys:
        if fail_closed:
            raise AIExtractionUnavailableException(
                reason="No GEMINI_API_KEY configured in pool.",
                status_code=503,
                detail="AI Extraction Unavailable: No GEMINI_API_KEY configured. Please verify API billing or switch keys.",
            )
        warnings.append("AI Notice: No GEMINI_API_KEY configured. Extracted via native PDF/OCR fallback.")
        return None, None

    if len(pdf_bytes) <= 500:
        return None, None

    page1_text = str((operative_page_text[0] if operative_page_text else {}).get("text") or "")
    logo_crop_png: bytes | None = None
    logo_color_meta: dict[str, Any] = {}
    if is_liberty_group_document(operative_text, page1_text, source_filename or file_path.name):
        logo_crop_png, logo_color_meta = render_page1_logo_crop(pdf_bytes)
    item_idx = abs(hash(source_filename or file_path.name)) % 100

    gemini_res: dict[str, Any] | None = None
    accounting_verdict: AccountingProofVerdict | None = None

    if _has_multi_slot_consensus_fleet(pool):
        precomputed_p1 = {
            "raw_text": operative_text,
            "operative_pdf_bytes": operative_pdf_bytes,
            "page1_text": page1_text,
            "native_fields": {},
            "candidates": candidates,
            "logo_crop_png": logo_crop_png,
            "logo_color_meta": logo_color_meta,
            "p1_signals": extract_page1_primary_brand_signals(page1_text),
            "spatial_brand": extract_liberty_group_spatial_brand(pdf_bytes, page1_text, db_companies=db_companies),
        }
        mv_res = run_multi_zoom_vision_pipeline(
            pdf_bytes=pdf_bytes,
            source_filename=source_filename or file_path.name,
            db_context={
                "db_aliases": db_aliases,
                "db_brands": db_brands,
                "db_models": db_models,
                "db_companies": db_companies,
                "db_benefit_concepts": db_benefit_concepts,
                "db_packs": db_packs,
                "db_corrections": db_corrections,
            },
            prompt_override=prompt_override,
            batch_item_index=item_idx,
            pass1_precomputed=precomputed_p1,
            enable_dual_model_consensus=True,
            is_covernote=is_cn_doc,
        )
        gemini_res = mv_res.gemini_res
        accounting_verdict = mv_res.accounting_verdict
        gemini_telemetry.extend(mv_res.telemetry_log)
    else:
        vision_imgs = [
            *render_header_footer_crops(operative_pdf_bytes, dpi=300),
            *render_schedule_and_pricing_crops(operative_pdf_bytes, dpi=350, include_pricing_zoom=False),
        ]
        gemini_res = gemini_extractor.extract_with_gemini_sync(
            operative_pdf_bytes,
            document_text=operative_text,
            source_filename=source_filename or file_path.name,
            db_companies=db_companies,
            db_benefit_concepts=db_benefit_concepts,
            db_aliases=db_aliases,
            db_packs=db_packs,
            correction_memory=db_corrections,
            prompt_override=prompt_override,
            logo_crop_png=logo_crop_png,
            vision_images=vision_imgs or None,
            inject_document_text=False,
            batch_item_index=item_idx,
            telemetry_log=gemini_telemetry,
        )
        if gemini_res:
            accounting_verdict = verify_quotation_accounting(gemini_res, is_covernote=is_cn_doc)
            if accounting_verdict.discrepancies:
                try:
                    zoom_imgs = render_schedule_and_pricing_crops(
                        operative_pdf_bytes,
                        dpi=350,
                        zoom_pricing_dpi=400,
                        include_pricing_zoom=True,
                    )
                    guidance = (
                        "400-DPI ACCOUNTING VERIFICATION: Fix these exact equation discrepancies: "
                        + "; ".join(accounting_verdict.discrepancies[:4])
                    )
                    ref_res = gemini_extractor.extract_with_gemini_sync(
                        operative_pdf_bytes,
                        document_text=operative_text,
                        source_filename=source_filename or file_path.name,
                        db_companies=db_companies,
                        db_benefit_concepts=db_benefit_concepts,
                        db_aliases=db_aliases,
                        db_packs=db_packs,
                        correction_memory=db_corrections,
                        prompt_override=prompt_override,
                        logo_crop_png=logo_crop_png,
                        vision_images=zoom_imgs or vision_imgs or None,
                        inject_document_text=False,
                        extra_prompt_guidance=guidance,
                        batch_item_index=item_idx + 1,
                        telemetry_log=gemini_telemetry,
                    )
                    if ref_res:
                        gemini_res = _merge_reconciled_result(gemini_res, ref_res)
                        accounting_verdict = verify_quotation_accounting(gemini_res, is_covernote=is_cn_doc)
                except StopIteration:
                    pass
            if accounting_verdict and accounting_verdict.authoritative_motor_premium:
                auth_str = f"{accounting_verdict.authoritative_motor_premium:.2f}"
                gemini_res["premium"] = auth_str
                gemini_res["total_amount"] = auth_str
                gemini_res["_accounting_verdict"] = {
                    "passed": accounting_verdict.passed,
                    "quarantine_reason": accounting_verdict.quarantine_reason,
                    "discrepancies": list(accounting_verdict.discrepancies),
                    "authoritative_motor_premium": auth_str,
                }

    augment_liberty_fn(
        pdf_bytes=pdf_bytes,
        page1_text=page1_text,
        combined_text=operative_text,
        source_filename=source_filename or file_path.name,
        db_companies=db_companies,
        candidates=candidates,
        gemini_res=gemini_res,
        logo_crop_png=logo_crop_png,
        logo_color_meta=logo_color_meta,
    )
    if not gemini_res:
        if fail_closed:
            last_err = pool.get_last_error_message() or "API Token Quota Exhausted or Rate-Limited"
            status_code = 429 if any(k in last_err.lower() for k in ["429", "quota", "rate"]) else 503
            raise AIExtractionUnavailableException(
                reason=last_err,
                status_code=status_code,
                detail=f"AI Extraction Unavailable: API Token Quota Exhausted. Please verify API billing or switch keys. ({last_err})",
            )
        warnings.append("AI Notice: Gemini AI token quota expired or rate-limited. Extracted via native PDF/OCR fallback.")
    return gemini_res, accounting_verdict

