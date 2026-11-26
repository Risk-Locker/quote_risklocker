"""Atomic service for rescanning quotation sessions (in-place renewal & new session creation)."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from app.core.config import Settings
from app.core.errors import AppError
from app.core.workspace import qc_temp_directory
from app.extraction.company_resolution import resolve_company
from app.extraction.native_pdf import extract_native
from app.extraction.sandbox import extract_with_limits
from app.models.enums import AccountStatus, RecordStatus
from app.models.tables import (
    AppSetting,
    Batch,
    DraftBenefitSelection,
    DraftSourceLineDecision,
    ExtractionBenefitLine,
    ExtractionRecord,
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
        rec_obj = db.get(ExtractionRecord, extraction_record_id)
        if rec_obj is not None:
            rec_obj.benefit_lines = []
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
    if explicit_service_fee and explicit_service_fee.strip():
        return
    from app.services.admin_service import get_runner_fee_default

    fields["service_fee"] = {
        "value": f"{get_runner_fee_default(db):.2f}",
        "status": "ready",
        "message": "",
    }


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
    brand_verdict: dict[str, Any] | None = None,
) -> None:
    """Apply Gemini AI extraction results to draft, extraction record, tracked vehicle, and catalog."""
    from sqlalchemy import func
    from sqlalchemy.orm.attributes import flag_modified
    from app.domain.motor.discount_calculator import calculate_motor_discount, to_decimal_clean
    from app.extraction.candidate_finder import is_blocked_vehicle_field_value
    from app.extraction.draft_mapper import normalize_vehicle_model_text, reconcile_vehicle_capacity_and_fees
    from app.models.tables import InsuranceTenure, TrackedVehicle
    from app.services.insurance_tenure_service import (
        is_valid_chassis,
        normalize_chassis,
        record_vehicle_plate_history,
    )
    from app.services.vehicle_tracking_service import is_valid_malaysian_plate, normalize_plate

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
        "motor_discount_pct",
        "motor_discount_amount",
        "quotation_discount",
        "effective_discount",
        "net_motor_premium",
        "_accounting_verdict",
    }
    fields = dict(draft.fields or {})
    preserved_pct = to_decimal_clean(fields.get("motor_discount_pct"), Decimal("0.00"))
    preserved_flat = to_decimal_clean(fields.get("quotation_discount"), Decimal("0.00"))

    # Clear stale blocked/hallucinated vehicle fields whenever Gemini returns blank OR existing value is a label placeholder
    _vehicle_auth_keys = {"vehicle_no", "car_brand", "car_model", "chassis_no", "engine_no"}
    for auth_key in _vehicle_auth_keys:
        existing_entry = fields.get(auth_key)
        existing_val = str(existing_entry.get("value") if isinstance(existing_entry, dict) else (existing_entry or "")).strip()
        gem_has_key = auth_key in gemini_res
        gem_val = gemini_res.get(auth_key)
        gem_blank = gem_val is None or str(gem_val).strip() == ""
        should_clear = (
            (gem_has_key and gem_blank)
            or is_blocked_vehicle_field_value(existing_val)
            or (auth_key == "vehicle_no" and bool(existing_val) and not is_valid_malaysian_plate(existing_val))
        )
        if should_clear and auth_key in fields:
            if isinstance(existing_entry, dict):
                fields[auth_key] = {**existing_entry, "value": "", "status": "ready", "message": ""}
            else:
                fields[auth_key] = ""

    for key, val in gemini_res.items():
        if key in _SKIP_KEYS or val is None:
            continue
        clean_val = str(val).strip()
        if not clean_val:
            continue
        if key in _vehicle_auth_keys and is_blocked_vehicle_field_value(clean_val):
            continue
        if key == "vehicle_no" and not is_valid_malaysian_plate(clean_val):
            continue
        fields[key] = {"value": clean_val, "status": "ready", "message": ""}

    # Normalize car_model so stale field-label prefixes or blocked brands never linger
    raw_brand_v = str((fields.get("car_brand") or {}).get("value") if isinstance(fields.get("car_brand"), dict) else (fields.get("car_brand") or "")).strip()
    raw_model_v = str((fields.get("car_model") or {}).get("value") if isinstance(fields.get("car_model"), dict) else (fields.get("car_model") or "")).strip()
    if raw_model_v:
        clean_model_v = normalize_vehicle_model_text(raw_model_v, raw_brand_v or None)
        if clean_model_v:
            fields["car_model"] = {"value": clean_model_v, "status": "ready", "message": ""}

    # Unregistered vehicle fallback: if vehicle_no has no valid Malaysian plate, fall back to bare normalized chassis_no
    cur_vno = str((fields.get("vehicle_no") or {}).get("value") if isinstance(fields.get("vehicle_no"), dict) else (fields.get("vehicle_no") or "")).strip()
    cur_chassis = str((fields.get("chassis_no") or {}).get("value") if isinstance(fields.get("chassis_no"), dict) else (fields.get("chassis_no") or "")).strip()
    clean_chassis = normalize_chassis(cur_chassis) if (cur_chassis and not is_blocked_vehicle_field_value(cur_chassis)) else ""
    if is_valid_malaysian_plate(cur_vno):
        norm_vno = normalize_plate(cur_vno)
        fields["vehicle_no"] = {"value": norm_vno, "status": "ready", "message": ""}
    elif is_valid_chassis(clean_chassis):
        fields["vehicle_no"] = {"value": clean_chassis, "status": "ready", "message": ""}

    gemini_benefits = gemini_res.get("detected_benefits") or []

    evidence_text = raw_text or (extraction.raw_text or "")
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
    )

    from app.extraction.canonical_draft_builder import apply_verified_motor_pricing

    is_cn_doc = getattr(session, "document_type", "") == "covernote"
    accounting_verdict = apply_verified_motor_pricing(
        fields,
        gemini_res,
        is_covernote=is_cn_doc,
        preserved_pct=preserved_pct,
        preserved_flat=preserved_flat,
        inc_rt=inc_rt,
        inc_rf=inc_rf,
    )

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
    if accounting_verdict.quarantine_reason:
        referee_notices = [
            *referee_notices,
            f"Accounting Proof Gate: {accounting_verdict.quarantine_reason}",
        ]
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
    flag_modified(draft, "display_options")
    draft.fields = fields
    flag_modified(draft, "fields")
    draft.status = (
        RecordStatus.CHECK_NEEDED.value
        if accounting_verdict.quarantine_reason
        else RecordStatus.READY.value
    )

    comp_name = str(gemini_res.get("insurance_company") or "").strip()
    if (
        brand_verdict
        and brand_verdict.get("canonical_company")
        and float(brand_verdict.get("confidence") or 0.0) >= 0.85
        and "mmip" not in comp_name.lower()
    ):
        comp_name = str(brand_verdict["canonical_company"]).strip()
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
            f_brand = str((fields.get("car_brand") or {}).get("value") or "").strip()
            f_model = str((fields.get("car_model") or {}).get("value") or "").strip()
            f_cc = str((fields.get("engine_cc") or {}).get("value") or "").strip()
            f_chassis = str((fields.get("chassis_no") or {}).get("value") or "").strip()
            f_engine = str((fields.get("engine_no") or {}).get("value") or "").strip()
            f_vno = str((fields.get("vehicle_no") or {}).get("value") or "").strip()

            if f_brand and not is_blocked_vehicle_field_value(f_brand):
                tv.car_brand = f_brand
            elif tv.car_brand and is_blocked_vehicle_field_value(tv.car_brand):
                tv.car_brand = None
            if f_model and not is_blocked_vehicle_field_value(f_model):
                tv.car_model = f_model
            elif tv.car_model and is_blocked_vehicle_field_value(tv.car_model):
                tv.car_model = None
            if f_cc:
                tv.engine_cc = f_cc
            if f_chassis and not is_blocked_vehicle_field_value(f_chassis) and not tv.chassis_no:
                tv.chassis_no = normalize_chassis(f_chassis) or f_chassis
            if f_engine and not is_blocked_vehicle_field_value(f_engine):
                tv.engine_no = f_engine
            elif tv.engine_no and is_blocked_vehicle_field_value(tv.engine_no):
                tv.engine_no = None

            tv_vno_bad = (
                not tv.vehicle_no
                or is_blocked_vehicle_field_value(tv.vehicle_no)
                or str(tv.vehicle_no).upper().startswith("CHASSIS")
                or str(tv.vehicle_no).upper().startswith("ENGINE")
                or str(tv.vehicle_no).upper().startswith("UNPLATED")
            )
            target_vno = normalize_plate(f_vno) if is_valid_malaysian_plate(f_vno) else (clean_chassis if is_valid_chassis(clean_chassis) else "")
            if target_vno and tv_vno_bad:
                collision = db.scalar(
                    select(TrackedVehicle).where(
                        func.upper(func.replace(TrackedVehicle.vehicle_no, " ", "")) == target_vno,
                        TrackedVehicle.id != tv.id,
                    )
                )
                if not collision:
                    tv.vehicle_no = target_vno
                    if is_valid_malaysian_plate(target_vno):
                        record_vehicle_plate_history(
                            db,
                            tracked_vehicle=tv,
                            new_plate=target_vno,
                            source_tenure_id=getattr(session, "tenure_id", None),
                        )
            if getattr(session, "tenure_id", None):
                tenure_obj = db.get(InsuranceTenure, session.tenure_id)
                if tenure_obj and target_vno and tenure_obj.stage != "Close - Win" and not tenure_obj.covernote_session_id:
                    t_bad = (
                        not tenure_obj.vehicle_no
                        or is_blocked_vehicle_field_value(tenure_obj.vehicle_no)
                        or str(tenure_obj.vehicle_no).upper().startswith("CHASSIS")
                        or str(tenure_obj.vehicle_no).upper().startswith("ENGINE")
                        or str(tenure_obj.vehicle_no).upper().startswith("UNPLATED")
                    )
                    if t_bad:
                        tenure_obj.vehicle_no = target_vno

    candidates = dict(extraction.candidates or {})
    if gemini_res.get("detected_packs"):
        candidates["detected_packs"] = gemini_res["detected_packs"]
    extraction.candidates = candidates

    from app.domain.benefits import is_auto_coverage_allowed_for_benefit
    from app.extraction.benefit_lines import is_spurious_benefit_line
    from app.services.bundle_plan_matcher import extract_plan_tier_token, is_base_auto365_policy_label
    from sqlalchemy.orm.attributes import flag_modified

    benefit_lines_json: list[dict[str, Any]] = []
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

        if not b_label or is_base_auto365_policy_label(b_label) or is_spurious_benefit_line(b_label) or is_spurious_benefit_line(b_raw):
            continue

        inferred_plan = b_plan or extract_plan_tier_token(f"{b_label} {b_val} {b_raw}") or ""
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

        # Strict Zero-Fake-Coverage Gate: never fall back to b_val (price) or allow auto coverage outside Windscreen/Towing/Betterment
        limit_val = ""
        if cov_limit and is_auto_coverage_allowed_for_benefit(c_key, b_label, cov_limit, cost):
            limit_val = cov_limit
        elif b_val and is_auto_coverage_allowed_for_benefit(c_key, b_label, b_val, cost):
            limit_val = b_val

        typed_val = None
        if limit_val:
            clean_limit = limit_val.upper().replace("RM", "").replace(",", "").strip()
            is_pure_money = bool(re.match(r"^\s*(?:RM\s*)?[\d]+(?:,\d{3})*(?:\.\d{1,2})?\s*$", limit_val, re.IGNORECASE))
            if is_pure_money:
                typed_val = {
                    "type": "money",
                    "value": clean_limit,
                    "currency": "MYR",
                    "semantic_role": "limit",
                    "display_text": limit_val if limit_val.upper().startswith("RM") else f"RM {limit_val}",
                }
            else:
                typed_val = {
                    "type": "text",
                    "value": limit_val,
                    "semantic_role": "limit",
                    "display_text": limit_val,
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

        rescan_line_id = f"rescan_gemini_{new_id()[:8]}"
        mappings_payload = [{
            "concept_id": concept_id,
            "concept_key": c_key,
            "name": b_label,
            "matched_alias": b_label,
            "score": 100,
            "match_type": "gemini_multimodal",
            "evidence": limit_val or b_val,
            "shaped_description": f"{b_label} ({limit_val})" if limit_val else b_label,
            "coverage_limit": limit_val,
            "premium_cost": cost,
            "plan_tier": inferred_plan,
            "is_detected": True,
        }] if concept_id or c_key else []

        benefit_lines_json.append({
            "line_id": rescan_line_id,
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
            "coverage_limit": limit_val,
            "premium_cost": cost,
            "plan_tier": inferred_plan,
            "is_optional_cover": is_optional,
            "extracted_value": typed_val,
            "candidate_mappings": mappings_payload,
        })

        line = ExtractionBenefitLine(
            id=new_id(),
            extraction_record_id=extraction.id,
            line_id=rescan_line_id,
            raw_label=b_label,
            normalized_label=b_label.lower()[:500],
            page_number=1,
            section="Optional Covers" if is_optional else "Selected Benefits",
            source_scope="selected",
            line_kind="benefit_candidate",
            inclusion_state="selected",
            evidence={"value": b_val, "coverage_limit": limit_val, "premium_cost": cost},
            candidate_mappings=mappings_payload,
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
    extraction.benefit_lines = benefit_lines_json
    flag_modified(extraction, "benefit_lines")
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
    brand_verdict: dict[str, Any] | None = None

    if engine == "deep":
        from app.extraction.deep_redetect_engine import run_deep_redetect_pipeline

        deep_out = run_deep_redetect_pipeline(
            pdf_bytes=source_bytes,
            source_filename=target_uploaded.original_filename or "quotation.pdf",
            current_fields=old_scalar_snapshot,
            db_context=context,
            prompt_override=prompt_override,
            batch_item_index=abs(hash(target_session.id)) % 100,
        )
        gemini_res = deep_out.gemini_res
        doc_text = deep_out.native_raw_text
        brand_verdict = deep_out.brand_verdict
    else:
        # Pass 1: Native PDF extraction (run for 'auto' and 'native')
        if engine in ("auto", "native"):
            with qc_temp_directory("rescan-") as directory:
                source_path = (directory / "source.pdf").resolve()
                source_path.write_bytes(source_bytes)
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

        # Pass 2: Unified Multi-Zoom Gemini Vision extraction BEFORE wiping or mutating existing draft
        if run_ai:
            from app.extraction.gemini_extractor import get_key_pool
            from app.extraction.multi_zoom_pipeline import run_multi_zoom_vision_pipeline

            try:
                mv_out = run_multi_zoom_vision_pipeline(
                    pdf_bytes=source_bytes,
                    source_filename=target_uploaded.original_filename or "quotation.pdf",
                    current_fields=old_scalar_snapshot,
                    db_context=context,
                    prompt_override=prompt_override,
                    batch_item_index=abs(hash(target_session.id)) % 100,
                    is_covernote=(getattr(target_session, "document_type", "") == "covernote"),
                )
                gemini_res = mv_out.gemini_res
                doc_text = mv_out.native_raw_text or doc_text
                brand_verdict = mv_out.brand_verdict or brand_verdict
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
            brand_verdict=brand_verdict,
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

    tenure_id = getattr(target_session, "tenure_id", None)
    if tenure_id:
        try:
            from app.services.marketing_comparison.materialize import materialize_comparison_entries
            from app.services.marketing_comparison_service import rescan_comparison_tenure

            rescan_comparison_tenure(db, tenure_id, deep=False)
            materialize_comparison_entries(db, str(tenure_id))
        except Exception as sync_err:
            logger.warning("Could not auto-sync comparison tenure %s: %s", tenure_id, sync_err)

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

