"""Multi-pass self-verifying Deep Re-detection engine for quotation & cover-note PDFs."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import logging
import re
import threading
from typing import Any, Callable

from app.core.errors import AppError
from app.core.workspace import qc_temp_directory
from app.extraction.brand_logo_scanner import (
    extract_liberty_group_spatial_brand,
    extract_page1_primary_brand_signals,
    is_liberty_group_document,
    render_page1_logo_crop,
    verify_brand_logo_with_vision,
)
from app.extraction.candidate_finder import find_candidates
from app.extraction.draft_mapper import build_draft
from app.extraction import gemini_extractor
from app.extraction.native_pdf import extract_native
from app.extraction.ocr import run_enhanced_reading
from app.extraction.page_filter import slice_pdf_bytes_excluding_pages, split_operative_pages

logger = logging.getLogger(__name__)

_CRITICAL_AUDIT_FIELDS: tuple[str, ...] = (
    "insurance_company",
    "customer_name",
    "vehicle_no",
    "car_model",
    "vehicle_year",
    "engine_cc",
    "vehicle_type",
    "cover_start_date",
    "cover_end_date",
    "valuation_type",
    "coverage_amount",
    "ncd_percent",
    "excess_amount",
    "premium",
    "total_amount",
    "detected_package_name",
)


class RedetectCancelledError(Exception):
    """Raised when a user cancels an active deep re-detect job cleanly."""


@dataclass
class DeepRedetectResult:
    gemini_res: dict[str, Any]
    native_raw_text: str
    native_fields: dict[str, Any]
    brand_verdict: dict[str, Any] | None = None
    audit_conflicts: list[str] = field(default_factory=list)
    math_issues: list[str] = field(default_factory=list)
    passes_used: int = 2
    logo_color_meta: dict[str, Any] = field(default_factory=dict)


def _check_cancel(cancel_event: threading.Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise RedetectCancelledError("Re-detection cancelled by user.")


def _emit(
    on_progress: Callable[[str, str, str, int, dict[str, Any] | None], None] | None,
    step_key: str,
    step_label: str,
    why_waiting: str,
    pct: int,
    detail: dict[str, Any] | None = None,
) -> None:
    if on_progress is not None:
        on_progress(step_key, step_label, why_waiting, pct, detail)


def _to_dec(raw: Any) -> Decimal | None:
    s = re.sub(r"[^\d.-]", "", str(raw or "").strip())
    if not s or s in {"-", "."}:
        return None
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def _norm_cmp(raw: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(raw or "").lower())


def _run_pass1_native_and_logo_crop(
    pdf_bytes: bytes,
    source_filename: str,
    db_context: dict[str, Any],
) -> dict[str, Any]:
    with qc_temp_directory("deep-redetect-") as tmpdir:
        pdf_path = (tmpdir / "source.pdf").resolve()
        pdf_path.write_bytes(pdf_bytes)
        native = extract_native(pdf_path)
        ocr_text = ""
        if len((native.raw_text or "").strip()) < 80:
            ocr_text, _, _ = run_enhanced_reading(pdf_path)

    combined_text = "\n".join(part for part in (native.raw_text, ocr_text) if part).strip()
    ocr_pages = [{"page": 1, "text": ocr_text, "source_method": "ocr"}] if ocr_text.strip() else []
    page_text = [*(native.page_text or []), *ocr_pages]
    operative_pages, pds_pages = split_operative_pages(page_text)
    operative_words = [w for w in (native.words or []) if int(w.get("page", 1)) not in pds_pages]
    operative_text = (
        "\n".join(str(p.get("text") or "") for p in operative_pages if str(p.get("text") or "").strip()).strip()
        or combined_text
    )
    operative_pdf_bytes = slice_pdf_bytes_excluding_pages(pdf_bytes, pds_pages)
    page1_text = str((operative_pages[0] if operative_pages else (page_text[0] if page_text else {})).get("text") or "")

    candidates = find_candidates(
        operative_text,
        operative_pages,
        operative_words,
        aliases=db_context.get("db_aliases"),
        source_filename=source_filename,
        db_brands=db_context.get("db_brands"),
        db_models=db_context.get("db_models"),
        db_companies=db_context.get("db_companies"),
    )
    native_fields, _, _ = build_draft(candidates, raw_text=operative_text)
    logo_crop_png, logo_color_meta = render_page1_logo_crop(pdf_bytes)
    p1_signals = extract_page1_primary_brand_signals(page1_text)
    spatial_brand = extract_liberty_group_spatial_brand(
        pdf_bytes,
        page1_text,
        db_companies=db_context.get("db_companies") or [],
    )
    return {
        "raw_text": operative_text,
        "operative_pdf_bytes": operative_pdf_bytes,
        "page1_text": page1_text,
        "native_fields": native_fields,
        "candidates": candidates,
        "logo_crop_png": logo_crop_png,
        "logo_color_meta": logo_color_meta,
        "p1_signals": p1_signals,
        "spatial_brand": spatial_brand,
    }


def _should_verify_brand_visually(
    pass1: dict[str, Any],
    current_fields: dict[str, str],
    source_filename: str,
) -> bool:
    if is_liberty_group_document(pass1["raw_text"], pass1["page1_text"], source_filename):
        return True
    cur_comp = (current_fields.get("insurance_company") or "").strip().lower()
    nat_comp = str((pass1["native_fields"].get("insurance_company") or {}).get("value") or "").strip().lower()
    if not cur_comp or not nat_comp:
        return True
    return cur_comp != nat_comp


def _check_mmip_override(pass1: dict[str, Any], source_filename: str) -> bool:
    combined = f"{source_filename} {pass1.get('raw_text', '')}".lower()
    return any(
        cue in combined
        for cue in ("mmip", "malaysian motor insurance pool", "malaysia motor insurance pool")
    )


def _audit_optional_cover_and_required_math(gemini_res: dict[str, Any]) -> list[str]:
    math_issues: list[str] = []
    benefits = gemini_res.get("detected_benefits") or []
    opt_sum = sum(
        (c_dec for item in benefits if isinstance(item, dict) and (c_dec := _to_dec(item.get("premium_cost"))) and c_dec > Decimal("0.00")),
        Decimal("0.00"),
    )
    stated_opt = _to_dec(gemini_res.get("total_optional_cover_amount"))
    if stated_opt and stated_opt > Decimal("0.00") and abs(opt_sum - stated_opt) > Decimal("1.00"):
        math_issues.append(
            f"optional_covers_sum ({opt_sum:.2f}) != stated total_optional_cover_amount ({stated_opt:.2f})"
        )

    cov_type = str(gemini_res.get("coverage_type") or "").lower()
    si_dec = _to_dec(gemini_res.get("coverage_amount"))
    if "comprehensive" in cov_type and (si_dec is None or si_dec < Decimal("1000.00")):
        math_issues.append(f"sum_insured suspiciously low/missing for Comprehensive: {si_dec}")

    if not str(gemini_res.get("vehicle_no") or "").strip():
        math_issues.append("vehicle_no missing")
    return math_issues


def _audit_conflicts_and_math(
    current_fields: dict[str, str],
    native_fields: dict[str, Any],
    gemini_res: dict[str, Any],
    brand_verdict: dict[str, Any] | None,
) -> tuple[list[str], list[str]]:
    conflicts: list[str] = []
    diff_keys = {"vehicle_no", "coverage_amount", "ncd_percent", "total_amount", "premium", "engine_cc"}

    for key in _CRITICAL_AUDIT_FIELDS:
        g_val = str(gemini_res.get(key) or "").strip()
        cur_val = (current_fields.get(key) or "").strip()
        nat_val = str((native_fields.get(key) or {}).get("value") or "").strip()
        if not g_val and (cur_val or nat_val):
            conflicts.append(f"{key}: AI returned blank while previous='{cur_val}' native='{nat_val}'")
        elif nat_val and g_val and key in diff_keys and _norm_cmp(nat_val) != _norm_cmp(g_val):
            conflicts.append(f"{key}: native='{nat_val}' vs fresh_ai='{g_val}' (previous='{cur_val}')")

    if brand_verdict and brand_verdict.get("canonical_company"):
        b_name = str(brand_verdict["canonical_company"])
        g_name = str(gemini_res.get("insurance_company") or "")
        if _norm_cmp(b_name) != _norm_cmp(g_name):
            conflicts.append(f"insurance_company: logo_vision='{b_name}' vs fresh_ai='{g_name}'")

    math_issues = _audit_optional_cover_and_required_math(gemini_res)
    return conflicts, math_issues


def _build_reconciliation_guidance(
    current_fields: dict[str, str],
    native_fields: dict[str, Any],
    gemini_res: dict[str, Any],
    conflicts: list[str],
    math_issues: list[str],
    brand_verdict: dict[str, Any] | None,
) -> str:
    safe_summary = {
        "previous_values": {k: current_fields.get(k, "") for k in _CRITICAL_AUDIT_FIELDS if current_fields.get(k)},
        "native_pdf_values": {
            k: str((native_fields.get(k) or {}).get("value") or "")
            for k in _CRITICAL_AUDIT_FIELDS
            if (native_fields.get(k) or {}).get("value")
        },
        "pass3_ai_values": {k: gemini_res.get(k) for k in _CRITICAL_AUDIT_FIELDS if gemini_res.get(k) is not None},
        "brand_logo_verdict": brand_verdict,
        "conflicts": conflicts,
        "math_issues": math_issues,
    }
    payload_str = __import__("json").dumps(safe_summary, default=str)[:4500]
    payload_str = payload_str.replace("</untrusted_document_content>", "[ESCAPED_TAG]")
    return (
        "DEEP VERIFICATION & SELF-AUDIT PASS:\n"
        "Compare the PDF visual document directly against the discrepancies below and resolve every single one with 100% precision. "
        "Make sure ALL priced optional covers in the schedule table are included so optional_covers_sum matches Total Optional Cover Amount.\n"
        f"<untrusted_document_content>\n{payload_str}\n</untrusted_document_content>"
    )


def _merge_reconciled_result(base_res: dict[str, Any], verified_res: dict[str, Any] | None) -> dict[str, Any]:
    if not verified_res or not isinstance(verified_res, dict):
        return base_res
    merged = dict(base_res)
    for k, val in verified_res.items():
        if k == "detected_benefits":
            base_b = base_res.get("detected_benefits") or []
            ver_b = val if isinstance(val, list) else []
            if len(ver_b) >= len(base_b) and ver_b:
                merged["detected_benefits"] = ver_b
            continue
        if val is not None and str(val).strip() != "":
            merged[k] = val
    return merged


def run_deep_redetect_pipeline(
    *,
    pdf_bytes: bytes,
    source_filename: str,
    current_fields: dict[str, str] | None = None,
    db_context: dict[str, Any] | None = None,
    prompt_override: str | None = None,
    on_progress: Callable[[str, str, str, int, dict[str, Any] | None], None] | None = None,
    cancel_event: threading.Event | None = None,
    batch_item_index: int = 0,
) -> DeepRedetectResult:
    """Execute 4-pass self-verifying deep re-detection with cooperative cancellation."""
    ctx = db_context or {}
    cur_map = current_fields or {}
    _check_cancel(cancel_event)

    # Pass 1: Native extraction + Page 1 top-left logo crop
    _emit(
        on_progress,
        "native_and_logo_crop",
        "Pass 1/4 · Reading PDF text & cropping logo",
        "Extracting raw schedule tables and cropping Page 1 top-left insurer logo for visual brand inspection.",
        15,
        None,
    )
    pass1 = _run_pass1_native_and_logo_crop(pdf_bytes, source_filename, ctx)
    _check_cancel(cancel_event)

    pool = gemini_extractor.get_key_pool()
    if not pool.get_all_keys():
        raise AppError("No GEMINI_API_KEY configured. Please check your environment.", 400)

    # Pass 2: Brand & Logo Visual Identification
    brand_verdict: dict[str, Any] | None = None
    passes_used = 1
    is_mmip = _check_mmip_override(pass1, source_filename)
    if is_mmip:
        brand_verdict = {
            "insurance_company": "MMIP",
            "canonical_company": "MMIP",
            "confidence": 1.0,
            "reasoning": "MMIP pool indicator present in document.",
        }
    elif pass1.get("spatial_brand") and float(pass1["spatial_brand"].get("confidence") or 0.0) >= 0.99:
        brand_verdict = pass1["spatial_brand"]
        _emit(
            on_progress,
            "brand_logo_vision",
            "Pass 2/4 · Verified insurer footer website",
            str(brand_verdict.get("reasoning") or "Matched authoritative Page 1 footer website domain."),
            35,
            {"brand_verdict": brand_verdict.get("canonical_company"), "domain": brand_verdict.get("domain")},
        )
    elif _should_verify_brand_visually(pass1, cur_map, source_filename):
        _emit(
            on_progress,
            "brand_logo_vision",
            "Pass 2/4 · Scanning insurer logo & colors",
            "Inspecting Page 1 logo shape, brand color (Liberty dark blue vs Kurnia sky-blue vs AmAssurance red), and primary domain.",
            35,
            pass1["logo_color_meta"],
        )
        brand_verdict = verify_brand_logo_with_vision(
            pdf_bytes,
            page1_text=pass1["page1_text"],
            source_filename=source_filename,
            db_companies=ctx.get("db_companies") or [],
            logo_crop_png=pass1["logo_crop_png"],
            color_meta=pass1["logo_color_meta"],
            timeout_seconds=18.0,
        )
        passes_used += 1
    _check_cancel(cancel_event)

    # Pass 3: Fresh Full-Document Multimodal AI Extraction
    _emit(
        on_progress,
        "fresh_multimodal_extraction",
        "Pass 3/4 · Full multimodal AI extraction",
        "Extracting all policy, vehicle, pricing, and optional benefit rows against live database catalogs.",
        60,
        {"brand_verdict": (brand_verdict or {}).get("canonical_company")},
    )
    brand_hint_text = ""
    if brand_verdict and brand_verdict.get("canonical_company") and float(brand_verdict.get("confidence") or 0.0) >= 0.85:
        brand_hint_text = (
            f"VERIFIED VISUAL BRAND HINT: Page 1 logo scan identified insurer as "
            f"'{brand_verdict['canonical_company']}' ({brand_verdict.get('reasoning', '')})."
        )
    gemini_res = gemini_extractor.extract_with_gemini_sync(
        pass1.get("operative_pdf_bytes") or pdf_bytes,
        document_text=pass1["raw_text"] or None,
        source_filename=source_filename,
        db_companies=ctx.get("db_companies") or [],
        db_benefit_concepts=ctx.get("db_benefit_concepts") or [],
        db_aliases=ctx.get("db_aliases"),
        db_packs=ctx.get("db_packs") or [],
        correction_memory=ctx.get("db_corrections") or [],
        prompt_override=prompt_override,
        logo_crop_png=pass1["logo_crop_png"],
        extra_prompt_guidance=brand_hint_text or None,
        batch_item_index=batch_item_index,
        timeout_seconds=25.0,
    )
    passes_used += 1
    if not gemini_res:
        err = pool.get_last_error_message() or "AI extraction failed or returned an empty result."
        raise AppError(f"Gemini AI extraction failed: {err}", 502)
    _check_cancel(cancel_event)

    # Pass 4: Self-Audit, Cross-Verification & Math Check
    _emit(
        on_progress,
        "cross_verify_and_audit",
        "Pass 4/4 · Auditing conflicts & math",
        "Cross-checking previous detection, native PDF tables, and fresh AI output plus optional-cover math.",
        82,
        None,
    )
    conflicts, math_issues = _audit_conflicts_and_math(cur_map, pass1["native_fields"], gemini_res, brand_verdict)
    if conflicts or math_issues:
        _emit(
            on_progress,
            "cross_verify_and_audit",
            "Pass 4/4 · Re-verifying disputed fields",
            f"Found {len(conflicts) + len(math_issues)} discrepancy/audit check(s); running targeted verification pass against PDF.",
            88,
            {"conflicts": conflicts[:4], "math_issues": math_issues[:3]},
        )
        reconcile_guidance = _build_reconciliation_guidance(
            cur_map,
            pass1["native_fields"],
            gemini_res,
            conflicts,
            math_issues,
            brand_verdict,
        )
        verified_res = gemini_extractor.extract_with_gemini_sync(
            pass1.get("operative_pdf_bytes") or pdf_bytes,
            document_text=pass1["raw_text"] or None,
            source_filename=source_filename,
            db_companies=ctx.get("db_companies") or [],
            db_benefit_concepts=ctx.get("db_benefit_concepts") or [],
            db_aliases=ctx.get("db_aliases"),
            db_packs=ctx.get("db_packs") or [],
            correction_memory=ctx.get("db_corrections") or [],
            prompt_override=prompt_override,
            logo_crop_png=pass1["logo_crop_png"],
            extra_prompt_guidance=reconcile_guidance,
            batch_item_index=(batch_item_index + 1) % 100,
            timeout_seconds=25.0,
        )
        gemini_res = _merge_reconciled_result(gemini_res, verified_res)
        passes_used += 1

    # Authoritative brand verdict overrides noisy AI brand drift when confident
    if is_mmip:
        gemini_res["insurance_company"] = "MMIP"
    elif brand_verdict and brand_verdict.get("canonical_company") and float(brand_verdict.get("confidence") or 0.0) >= 0.85:
        gemini_res["insurance_company"] = brand_verdict["canonical_company"]
    elif pass1["p1_signals"].get("winning_brand") and not gemini_res.get("insurance_company"):
        gemini_res["insurance_company"] = pass1["p1_signals"]["winning_brand"]

    _check_cancel(cancel_event)
    return DeepRedetectResult(
        gemini_res=gemini_res,
        native_raw_text=pass1["raw_text"],
        native_fields=pass1["native_fields"],
        brand_verdict=brand_verdict,
        audit_conflicts=conflicts,
        math_issues=math_issues,
        passes_used=passes_used,
        logo_color_meta=pass1["logo_color_meta"],
    )
