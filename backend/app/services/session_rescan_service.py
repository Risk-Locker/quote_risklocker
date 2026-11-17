"""Atomic service for rescanning quotation sessions (in-place renewal & new session creation)."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from app.core.config import Settings
from app.core.errors import AppError
from app.core.workspace import qc_temp_directory
from app.extraction.company_resolution import build_companies_payload, resolve_company
from app.extraction.db_lookups import get_correction_memory, get_db_packs
from app.extraction.entity_classifier import classify_client_entity
from app.extraction.native_pdf import extract_native
from app.extraction.sandbox import extract_with_limits
from app.models.enums import AccountStatus, RecordStatus
from app.models.tables import (
    AppSetting,
    Batch,
    BenefitConcept,
    CompanyAlias,
    DraftBenefitSelection,
    DraftSourceLineDecision,
    ExtractionBenefitLine,
    ExtractionRecord,
    InsuranceCompany,
    QuotationDraft,
    Session as QuotationSession,
    UploadedFile,
    User,
    new_id,
)
from app.auth.rbac import can_view_owner_record
from app.services.catalog_review_service import (
    auto_apply_extracted_benefits,
    initialize_catalog_review,
)
from app.services.pdf_content import load_pdf_bytes
from app.services.quotation_reference_service import generate_quotation_reference
from app.workers.extraction_worker import _record_values, load_extraction_context

logger = logging.getLogger(__name__)


def _clear_draft_dependents(db: DbSession, draft_id: str, extraction_record_id: str | None) -> None:
    """Wipe child selections, decisions, and benefit lines for an in-place renewal."""
    db.execute(delete(DraftBenefitSelection).where(DraftBenefitSelection.draft_id == draft_id))
    db.execute(delete(DraftSourceLineDecision).where(DraftSourceLineDecision.draft_id == draft_id))
    if extraction_record_id:
        db.execute(delete(ExtractionBenefitLine).where(ExtractionBenefitLine.extraction_record_id == extraction_record_id))
    db.flush()


def _extract_scalar_values_map(fields: dict[str, Any] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in (fields or {}).items():
        if isinstance(v, dict):
            out[k] = str(v.get("value") or "").strip()
        elif v is not None:
            out[k] = str(v).strip()
    return out


def _apply_service_fee_if_included(
    db: DbSession,
    fields: dict[str, Any],
    *,
    inc_rf: bool,
    explicit_service_fee: str | None = None,
) -> None:
    if not inc_rf:
        fields["service_fee"] = {"value": "0.00", "status": "ready", "message": ""}
        return
    if explicit_service_fee and str(explicit_service_fee).strip():
        return
    if str((fields.get("service_fee") or {}).get("value") or "").strip():
        return
    fee_setting = db.get(AppSetting, "default_runner_fee")
    if fee_setting is not None:
        try:
            fields["service_fee"] = {
                "value": f"{float((fee_setting.value or {}).get('amount', 0)):.2f}",
                "status": "ready",
                "message": "",
            }
            return
        except (TypeError, ValueError):
            pass
    fields.setdefault("service_fee", {"value": "", "status": "ready", "message": ""})


def apply_gemini_result(
    db: DbSession,
    settings: Settings,
    draft: QuotationDraft,
    session: QuotationSession,
    uploaded: UploadedFile,
    extraction: ExtractionRecord,
    gemini_res: dict,
    quotation_ref: str,
    db_companies: list[dict],
    db_benefit_concepts: list[dict],
    *,
    raw_text: str = "",
) -> None:
    """Apply Gemini AI extraction results to draft, extraction record, tracked vehicle, and catalog."""
    from app.extraction.draft_mapper import reconcile_vehicle_capacity_and_fees
    from app.models.tables import TrackedVehicle

    _SKIP_KEYS = {
        "detected_benefits",
        "detected_package_name",
        "detected_packs",
        "roadtax",
        "road_tax",
        "quotation_reference",
        "quotation_ref",
        "clean_vehicle_name",
        "capacity_unit",
        "powertrain",
    }
    fields = dict(draft.fields or {})
    for key, val in gemini_res.items():
        if key in _SKIP_KEYS or val is None:
            continue
        clean_val = str(val).strip()
        if clean_val:
            fields[key] = {"value": clean_val, "status": "ready", "message": ""}

    # Sum detected optional extras cost to derive net base insurance premium
    gemini_benefits = gemini_res.get("detected_benefits") or []
    extras_cost = Decimal("0")
    for b_item in gemini_benefits:
        if not isinstance(b_item, dict):
            continue
        cost = str(b_item.get("premium_cost") or "").strip()
        if cost:
            clean = re.sub(r"[^\d.]", "", cost)
            if clean:
                try:
                    num = Decimal(clean)
                    if num > 0:
                        extras_cost += num
                except Exception:
                    pass

    if extras_cost == 0 and gemini_res.get("total_optional_cover_amount"):
        clean_tot_opt = re.sub(r"[^\d.]", "", str(gemini_res["total_optional_cover_amount"]))
        if clean_tot_opt:
            try:
                extras_cost = Decimal(clean_tot_opt)
            except Exception:
                pass

    tot_num: Decimal | None = None
    t_val = gemini_res.get("total_amount")
    if t_val:
        clean_tot = re.sub(r"[^\d.]", "", str(t_val))
        if clean_tot:
            try:
                tot_num = Decimal(clean_tot)
                fields["total_payable"] = {"value": f"{tot_num:.2f}", "status": "ready", "message": ""}
                fields["total_amount"] = {"value": f"{tot_num:.2f}", "status": "ready", "message": ""}
                if extras_cost > 0:
                    base_p = tot_num - extras_cost
                    fields["premium"] = {
                        "value": f"{base_p:.2f}" if base_p > 0 else f"{tot_num:.2f}",
                        "status": "ready",
                        "message": "",
                    }
                else:
                    fields["premium"] = {"value": f"{tot_num:.2f}", "status": "ready", "message": ""}
            except Exception:
                tot_num = None

    evidence_text = raw_text or str(extraction.raw_text or "") or ""
    _entity_type, resolved_vtype, inc_rt, inc_rf = reconcile_vehicle_capacity_and_fees(
        fields,
        gemini_hints=gemini_res,
        raw_text=evidence_text,
        db=db,
    )
    _apply_service_fee_if_included(
        db,
        fields,
        inc_rf=inc_rf,
        explicit_service_fee=gemini_res.get("service_fee"),
    )

    # Recompute quotation total_amount when fees are disabled vs enabled
    prem_str = str((fields.get("premium") or {}).get("value") or "").strip()
    if tot_num is not None:
        rt_dec = Decimal(str((fields.get("roadtax") or {}).get("value") or "0") or "0") if inc_rt else Decimal("0")
        rf_dec = Decimal(str((fields.get("service_fee") or {}).get("value") or "0") or "0") if inc_rf else Decimal("0")
        if inc_rt or inc_rf:
            fields["total_amount"] = {"value": f"{(tot_num + rt_dec + rf_dec):.2f}", "status": "ready", "message": ""}
        else:
            fields["total_amount"] = {"value": f"{tot_num:.2f}", "status": "ready", "message": ""}
    elif prem_str:
        try:
            prem_dec = Decimal(prem_str.replace(",", ""))
            rt_dec = Decimal(str((fields.get("roadtax") or {}).get("value") or "0") or "0") if inc_rt else Decimal("0")
            rf_dec = Decimal(str((fields.get("service_fee") or {}).get("value") or "0") or "0") if inc_rf else Decimal("0")
            fields["total_amount"] = {"value": f"{(prem_dec + rt_dec + rf_dec):.2f}", "status": "ready", "message": ""}
        except Exception:
            pass

    start_d = str(gemini_res.get("cover_start_date") or "").strip()
    end_d = str(gemini_res.get("cover_end_date") or "").strip()
    if start_d and end_d:
        fields["cover_period"] = {"value": f"{start_d} to {end_d}", "status": "ready", "message": ""}

    fields["quotation_reference"] = {"value": quotation_ref, "status": "ready", "message": ""}

    from app.extraction.vehicle_grounding_service import (
        finalize_catalog_and_3eye_gate,
        run_level2_grounding_gate,
    )

    fields, level2_grounding, referee_notices = run_level2_grounding_gate(
        db=db,
        fields=fields,
        raw_text=evidence_text,
    )
    if referee_notices:
        existing_w = list(draft.warnings or [])
        for note in referee_notices:
            if note not in existing_w:
                existing_w.append(note)
        draft.warnings = existing_w

    curr_opts = dict(draft.display_options or {})
    curr_opts["include_road_tax"] = str((fields.get("include_road_tax") or {}).get("value") or "true").lower() != "false"
    curr_opts["include_runner_fee"] = str((fields.get("include_runner_fee") or {}).get("value") or "true").lower() != "false"
    draft.display_options = curr_opts
    draft.fields = fields
    draft.status = RecordStatus.READY.value

    comp_name = str(gemini_res.get("insurance_company") or "").strip()
    resolved = resolve_company(comp_name, db_companies)
    if resolved["status"] == "matched":
        company = next((c for c in db_companies if c["company_id"] == resolved["company_id"]), None)
        if company:
            draft.company_id = company["company_id"]
            draft.fields["insurance_company"] = {"value": company["name"], "status": "ready", "message": ""}
            session.detected_company = company["name"]

    if getattr(session, "tracked_vehicle_id", None):
        tv = db.get(TrackedVehicle, session.tracked_vehicle_id)
        if tv:
            if (fields.get("car_brand") or {}).get("value"):
                tv.car_brand = str(fields["car_brand"]["value"])
            if (fields.get("car_model") or {}).get("value"):
                tv.car_model = str(fields["car_model"]["value"])
            if (fields.get("engine_cc") or {}).get("value"):
                tv.engine_cc = str(fields["engine_cc"]["value"])

    candidates = dict(extraction.candidates or {})
    if gemini_res.get("detected_packs"):
        candidates["detected_packs"] = gemini_res["detected_packs"]
    extraction.candidates = candidates

    for b_item in gemini_benefits:
        if isinstance(b_item, dict):
            b_label = str(b_item.get("label") or "").strip()
            b_val = str(b_item.get("value") or "").strip()
            b_key = str(b_item.get("concept_key") or "").strip()
            cov_limit = str(b_item.get("coverage_limit") or "").strip()
            cost = str(b_item.get("premium_cost") or "").strip()
            is_optional = bool(b_item.get("is_optional_cover", False))
        elif isinstance(b_item, str):
            b_label = b_item.strip()
            b_val = ""
            b_key = ""
            cov_limit = ""
            cost = ""
            is_optional = False
        else:
            continue

        b_norm = b_label.lower().replace(" ", "-").replace("_", "-")
        matched_concept = None
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
        limit_val = cov_limit or (b_val if b_val.lower() not in {"included", "standard", "yes", "true", "optional"} else "")
        typed_val = None
        if limit_val and (re.search(r"\d", limit_val) or re.search(r"\bunlimited\b", limit_val, re.I)):
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
                typed_val = {"type": "text", "value": limit_val, "display_text": limit_val}

        line = ExtractionBenefitLine(
            id=new_id(),
            extraction_record_id=extraction.id,
            line_id=f"rescan_gemini_{new_id()[:8]}",
            raw_label=b_label,
            normalized_label=b_label.lower()[:500],
            page_number=1,
            section="Optional Covers" if is_optional else "Selected Benefits",
            source_scope="selected",
            line_kind="benefit_candidate",
            inclusion_state="selected",
            evidence={"value": b_val, "coverage_limit": cov_limit if (re.search(r"\d", cov_limit) or re.search(r"\bunlimited\b", cov_limit, re.I)) else "", "premium_cost": cost},
            candidate_mappings=[{
                "concept_id": concept_id,
                "concept_key": c_key,
                "name": b_label,
                "matched_alias": b_label,
                "score": 100,
                "match_type": "gemini_multimodal",
                "evidence": b_val,
                "shaped_description": f"{b_label} ({limit_val})" if limit_val and (re.search(r"\d", limit_val) or re.search(r"\bunlimited\b", limit_val, re.I)) else b_label,
                "coverage_limit": limit_val if (re.search(r"\d", limit_val) or re.search(r"\bunlimited\b", limit_val, re.I)) else None,
                "premium_cost": cost,
                "is_detected": True,
            }] if concept_id or c_key else [],
            extracted_value=typed_val,
        )
        db.add(line)
        db.flush()
        db.add(DraftSourceLineDecision(
            id=new_id(),
            draft_id=draft.id,
            source_line_id=line.id,
            disposition="unresolved",
        ))
    db.flush()

    finalize_catalog_and_3eye_gate(
        db=db,
        draft=draft,
        grounding=level2_grounding,
        raw_text=evidence_text,
        record=extraction,
        pin_catalog_fn=initialize_catalog_review,
    )
    auto_apply_extracted_benefits(db, draft)


_apply_gemini_result = apply_gemini_result


def rescan_session(
    db: DbSession,
    session_id: str,
    user: User,
    settings: Settings,
    *,
    mode: Literal["in_place", "new_session"] = "in_place",
    engine: Literal["auto", "native", "ai", "deep"] = "auto",
) -> dict[str, Any]:
    """Execute rescan for a quotation session in-place or into a new session."""

    session = db.get(QuotationSession, session_id)
    if not session or not can_view_owner_record(db, user, session.owner_id):
        raise AppError("Session not found.", 404)

    uploaded = db.get(UploadedFile, session.uploaded_file_id)
    if not uploaded or uploaded.deleted_at is not None:
        raise AppError("Uploaded file not found or deleted.", 404)

    draft = db.get(QuotationDraft, session.draft_id)
    if not draft:
        raise AppError("Quotation draft not found.", 404)

    # Load source PDF bytes (throws 410 if expired)
    try:
        source_bytes = load_pdf_bytes(uploaded, settings)
    except AppError:
        raise
    except Exception as exc:
        raise AppError(f"Could not load source PDF: {exc}", 503) from exc

    now = datetime.now(timezone.utc)
    old_scalar_snapshot = _extract_scalar_values_map(draft.fields)
    target_session = session
    target_draft = draft
    target_uploaded = uploaded

    if mode == "new_session":
        new_qref = generate_quotation_reference(db, when=now)
        new_batch = Batch(
            id=new_id(),
            owner_id=user.id,
            name=f"Rescan: {uploaded.original_filename}",
            status=RecordStatus.PREPARING.value,
            enhanced_reading_requested=uploaded.enhanced_reading,
        )
        target_uploaded = UploadedFile(
            id=new_id(),
            batch_id=new_batch.id,
            owner_id=user.id,
            original_filename=uploaded.original_filename,
            content_type="application/pdf",
            storage_path=uploaded.storage_path,
            storage_provider=uploaded.storage_provider,
            storage_bucket=uploaded.storage_bucket,
            storage_status=uploaded.storage_status,
            storage_sha256=uploaded.storage_sha256,
            storage_etag=uploaded.storage_etag,
            storage_stored_at=now,
            storage_expires_at=None,
            size_bytes=uploaded.size_bytes,
            status=RecordStatus.PREPARING.value,
            enhanced_reading=uploaded.enhanced_reading,
        )
        target_draft = QuotationDraft(
            id=new_id(),
            revision=1,
            uploaded_file_id=target_uploaded.id,
            owner_id=user.id,
            status=RecordStatus.PREPARING.value,
            fields={
                "quotation_reference": {
                    "value": new_qref,
                    "status": "ready",
                    "warnings": [],
                    "message": "",
                }
            },
            scalar_decisions={},
            warnings=[],
        )
        target_session = QuotationSession(
            id=new_id(),
            owner_id=user.id,
            uploaded_file_id=target_uploaded.id,
            draft_id=target_draft.id,
            quotation_ref=new_qref,
            status=AccountStatus.ACTIVE.value,
        )
        db.add(new_batch)
        db.add(target_uploaded)
        db.add(target_draft)
        db.add(target_session)
        db.flush()
        quotation_ref = new_qref
    else:
        # In-place renewal: preserve internal ref; defer mutating draft until extraction succeeds!
        existing_ref = (draft.fields or {}).get("quotation_reference") or session.quotation_ref
        ref_val = existing_ref.get("value") if isinstance(existing_ref, dict) else existing_ref
        quotation_ref = str(ref_val) if ref_val else generate_quotation_reference(db, when=now)

    # Prepare extraction context (cached)
    context = load_extraction_context(db)
    db_companies = context.get("db_companies") or []
    db_benefit_concepts = context.get("db_benefit_concepts") or []

    prompt_override = None
    setting = db.get(AppSetting, "ai_system_prompt")
    if setting and isinstance(setting.value, dict) and str(setting.value.get("text") or "").strip():
        prompt_override = str(setting.value["text"]).strip()

    engine_used = "native"
    run_ai = engine in ("ai", "deep")
    full: dict[str, Any] = {}
    draft_data: dict[str, Any] = {}
    draft_fields: dict[str, Any] = {}
    gemini_res: dict | None = None
    doc_text: str | None = None

    # Pass 1: Native PDF extraction (run for 'auto', 'native', AND 'deep' so Gemini gets exact raw text)
    if engine in ("auto", "native", "deep"):
        with qc_temp_directory("rescan-") as directory:
            source_path = (directory / "source.pdf").resolve()
            source_path.write_bytes(source_bytes)
            if engine == "deep":
                try:
                    native = extract_native(source_path)
                    doc_text = native.raw_text
                except Exception:
                    doc_text = None
            else:
                native_result = extract_with_limits(
                    source_path,
                    enhanced_reading=target_uploaded.enhanced_reading,
                    source_filename=target_uploaded.original_filename,
                    prompt_override=prompt_override,
                    **context,
                )
                full = native_result.get("full_record") or {}
                draft_data = native_result.get("draft") or {}
                draft_fields = draft_data.get("fields") or {}
                doc_text = str(full.get("raw_text") or "") or None

                meaningful_count = len([
                    k for k, v in draft_fields.items()
                    if k != "quotation_reference" and isinstance(v, dict) and str(v.get("value") or "").strip()
                ])
                is_empty_or_failed = (
                    meaningful_count < 2
                    or draft_data.get("status") == RecordStatus.CANNOT_READ.value
                    or full.get("reading_quality") == "cannot_read"
                )
                if engine == "auto" and is_empty_or_failed:
                    from app.extraction.gemini_extractor import get_key_pool
                    if get_key_pool().get_all_keys():
                        logger.info("Rescan: Native extraction produced empty/cannot_read (%d fields); attempting Gemini AI fallback", meaningful_count)
                        run_ai = True

    # Pass 2: Gemini Vision extraction BEFORE wiping or mutating existing draft
    if run_ai:
        from app.extraction.gemini_extractor import extract_with_gemini_sync, get_key_pool

        if doc_text is None:
            try:
                with qc_temp_directory("rescan-doc-") as td:
                    temp_pdf = td / "doc.pdf"
                    temp_pdf.write_bytes(source_bytes)
                    native = extract_native(temp_pdf)
                    doc_text = native.raw_text
            except Exception:
                doc_text = None

        try:
            gemini_res = extract_with_gemini_sync(
                source_bytes,
                document_text=doc_text,
                source_filename=target_uploaded.original_filename,
                db_companies=db_companies,
                db_benefit_concepts=db_benefit_concepts,
                db_packs=context.get("db_packs") or [],
                correction_memory=context.get("db_corrections") or [],
                prompt_override=prompt_override,
                batch_item_index=abs(hash(target_session.id)) % 100,
            )
        except AppError:
            raise
        except Exception as ai_exc:
            raise AppError(f"Gemini AI extraction failed: {ai_exc}", 502) from ai_exc

        if not gemini_res:
            keys_pool = get_key_pool()
            if not keys_pool.get_all_keys():
                raise AppError("No GEMINI_API_KEY configured. Please check your environment.", 400)
            err = keys_pool.get_last_error_message() or "AI extraction failed or returned an empty result."
            raise AppError(f"Gemini AI extraction failed: {err}", 502)

    # Atomic mutation phase: ONLY executed after extraction passes succeeded
    if mode == "in_place":
        extraction_rec = db.scalar(select(ExtractionRecord).where(ExtractionRecord.uploaded_file_id == uploaded.id))
        _clear_draft_dependents(db, draft.id, extraction_rec.id if extraction_rec else None)
        draft.product_id = None
        draft.package_id = None
        draft.scalar_decisions = {}
        draft.warnings = []

    if run_ai and gemini_res:
        rec = db.scalar(select(ExtractionRecord).where(ExtractionRecord.uploaded_file_id == target_uploaded.id))
        if rec is None:
            rec = ExtractionRecord(
                id=new_id(),
                uploaded_file_id=target_uploaded.id,
                method_summary=["gemini_deep_rescan" if engine == "deep" else "gemini_ai_rescan"],
                raw_text=doc_text or "",
                ocr_text="",
                page_text=[],
                words=[],
                blocks=[],
                tables=[],
                images=[],
                regions=[],
                candidates={},
                benefit_lines=[],
                company_resolution={},
                warnings=[],
                reading_quality="ready",
            )
            db.add(rec)
            db.flush()

        apply_gemini_result(
            db=db,
            settings=settings,
            draft=target_draft,
            session=target_session,
            uploaded=target_uploaded,
            extraction=rec,
            gemini_res=gemini_res,
            quotation_ref=quotation_ref,
            db_companies=db_companies,
            db_benefit_concepts=db_benefit_concepts,
            raw_text=doc_text or "",
        )
        engine_used = "deep" if engine == "deep" else "ai"
    else:
        values = _record_values(full)
        if not values["company_resolution"]:
            selected_comp = str((draft_fields.get("insurance_company") or {}).get("value") or "").strip()
            values["company_resolution"] = resolve_company(selected_comp, db_companies)

        record = db.scalar(select(ExtractionRecord).where(ExtractionRecord.uploaded_file_id == target_uploaded.id))
        if record is None:
            record = ExtractionRecord(id=new_id(), uploaded_file_id=target_uploaded.id, **values)
            db.add(record)
            db.flush()
        else:
            for field, value in values.items():
                setattr(record, field, value)
            db.flush()

        for field in draft_fields.values():
            if isinstance(field, dict) and field.get("value") not in (None, ""):
                field["status"] = "ready"

        from app.extraction.draft_mapper import reconcile_vehicle_capacity_and_fees
        from app.extraction.vehicle_grounding_service import (
            finalize_catalog_and_3eye_gate,
            run_level2_grounding_gate,
        )

        _ent, _vtype, inc_rt, inc_rf = reconcile_vehicle_capacity_and_fees(
            draft_fields,
            raw_text=doc_text or "",
            db=db,
        )
        _apply_service_fee_if_included(db, draft_fields, inc_rf=inc_rf)

        draft_fields["quotation_reference"] = {"value": quotation_ref, "status": "ready", "message": ""}
        draft_fields, level2_grounding, ref_notices = run_level2_grounding_gate(
            db=db,
            fields=draft_fields,
            raw_text=doc_text or "",
        )

        opts = dict(target_draft.display_options or {})
        opts["include_road_tax"] = inc_rt and str((draft_fields.get("include_road_tax") or {}).get("value") or "true").lower() != "false"
        opts["include_runner_fee"] = inc_rf and str((draft_fields.get("include_runner_fee") or {}).get("value") or "true").lower() != "false"
        target_draft.display_options = opts
        target_draft.fields = draft_fields
        target_draft.warnings = list(draft_data.get("warnings") or []) + ref_notices
        target_draft.status = draft_data.get("status") or RecordStatus.CHECK_NEEDED.value
        target_draft.scalar_decisions = {
            name: {
                "decision": "confirm",
                "decided_by": target_draft.owner_id,
                "decided_at": now.isoformat(),
            }
            for name, field in draft_fields.items()
            if isinstance(field, dict) and field.get("value") not in (None, "")
        }

        target_uploaded.status = target_draft.status
        target_uploaded.simple_issue = (
            "Cannot Read" if target_draft.status == RecordStatus.CANNOT_READ.value
            else "Please check this value." if target_draft.status == RecordStatus.CHECK_NEEDED.value
            else None
        )
        target_session.detected_company = str((target_draft.fields.get("insurance_company") or {}).get("value") or "") or None

        company_id = (values["company_resolution"] or {}).get("company_id")
        if company_id:
            target_draft.company_id = company_id
            target_uploaded.insurance_company_id = company_id
        finalize_catalog_and_3eye_gate(
            db=db,
            draft=target_draft,
            grounding=level2_grounding,
            raw_text=doc_text or "",
            record=record,
            company_resolution=values.get("company_resolution"),
            pin_catalog_fn=initialize_catalog_review,
        )

        for source in values["benefit_lines"]:
            line_id = str(source.get("line_id") or "")
            if not line_id:
                continue
            line = ExtractionBenefitLine(
                id=new_id(),
                extraction_record_id=record.id,
                line_id=line_id,
                raw_label=str(source.get("raw_label") or ""),
                normalized_label=str(source.get("normalized_label") or source.get("raw_label") or "")[:500],
                page_number=source.get("page_number"),
                section=source.get("section"),
                source_scope=str(source.get("source_scope") or "unknown"),
                line_kind=str(source.get("line_kind") or "unknown"),
                inclusion_state=str(source.get("inclusion_state") or "unknown"),
                evidence=source.get("evidence") or {},
                candidate_mappings=source.get("candidate_mappings") or [],
                extracted_value=source.get("extracted_value"),
            )
            db.add(line)
            db.flush()
            db.add(DraftSourceLineDecision(
                id=new_id(),
                draft_id=target_draft.id,
                source_line_id=line.id,
                disposition="unresolved",
            ))
        db.flush()

        auto_apply_extracted_benefits(db, target_draft)
        engine_used = "native"

    target_session.last_edited_by_id = user.id
    target_session.last_edited_at = now

    new_scalar_snapshot = _extract_scalar_values_map(target_draft.fields)
    diff: dict[str, dict[str, str]] = {}
    for k in sorted(set(old_scalar_snapshot.keys()) | set(new_scalar_snapshot.keys())):
        old_v = old_scalar_snapshot.get(k, "")
        new_v = new_scalar_snapshot.get(k, "")
        if old_v != new_v:
            diff[k] = {"old": old_v, "new": new_v}

    if getattr(target_session, "tenure_id", None):
        try:
            from app.services.marketing_comparison_service import rescan_comparison_tenure
            rescan_comparison_tenure(db, target_session.tenure_id, deep=False)
        except Exception as sync_err:
            logger.warning("Could not auto-sync comparison tenure %s: %s", target_session.tenure_id, sync_err)

    db.commit()

    draft_fields = target_draft.fields or {}
    plate_val = str((draft_fields.get("vehicle_no") or draft_fields.get("vehicle_number") or {}).get("value") or "").strip()
    prem_val = str((draft_fields.get("total_amount") or {}).get("value") or "").strip()
    cust_val = str((draft_fields.get("customer_name") or draft_fields.get("insured_name") or {}).get("value") or "").strip()

    fields_count = len([
        k for k, v in draft_fields.items()
        if isinstance(v, dict) and str(v.get("value") or "").strip()
    ])

    return {
        "success": True,
        "session_id": target_session.id,
        "quotation_ref": target_session.quotation_ref,
        "mode": mode,
        "engine_used": engine_used,
        "detected_company": target_session.detected_company,
        "vehicle_plate": plate_val or None,
        "customer_name": cust_val or None,
        "total_premium": prem_val or None,
        "fields_count": fields_count,
        "diff": diff,
        "changed_fields": sorted(diff.keys()),
        "message": f"Quotation {target_session.quotation_ref} re-detected ({engine_used.upper()}) successfully.",
    }

