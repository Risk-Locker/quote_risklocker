"""Single-task extraction worker backed by durable Postgres jobs."""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.core.workspace import QC_TEMP_ROOT, REPOSITORY_ROOT, qc_temp_directory, resolve_qc_path
from app.extraction.company_resolution import build_companies_payload, resolve_company
from app.extraction.db_lookups import get_db_packs, get_correction_memory
from app.extraction.sandbox import extract_with_limits
from app.models.enums import AccountStatus, RecordStatus
from app.models.tables import (
    AppSetting,
    Batch,
    BenefitAlias,
    BenefitConcept,
    CompanyAlias,
    DraftSourceLineDecision,
    ExtractionBenefitLine,
    ExtractionRecord,
    FieldAlias,
    InsuranceCompany,
    InsuranceTenure,
    Job,
    QuotationDraft,
    Session,
    UploadedFile,
    VehicleBrand,
    VehicleModel,
    new_id,
)
from app.services.job_service import claim_next_job, complete_job, fail_job, heartbeat_job
from app.services.catalog_review_service import auto_apply_extracted_benefits, initialize_catalog_review
from app.storage.supabase import SupabaseStorage
from app.workers.render_worker import JobProcessingError as RenderJobProcessingError, process_render_job


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class JobProcessingError(RuntimeError):
    code: str
    safe_message: str

    def __str__(self) -> str:
        return self.safe_message


def _query_extraction_context(db) -> dict:
    aliases = {
        item.field_name: list(item.aliases or [])
        for item in db.scalars(select(FieldAlias).where(FieldAlias.status == AccountStatus.ACTIVE.value)).all()
    }
    brands: list[str] = []
    for item in db.scalars(select(VehicleBrand).where(VehicleBrand.status == AccountStatus.ACTIVE.value)).all():
        brands.extend([item.name, *(item.aliases or [])])
    models: list[str] = []
    for item in db.scalars(select(VehicleModel).where(VehicleModel.status == AccountStatus.ACTIVE.value)).all():
        models.extend([item.name, *(item.aliases or [])])

    company_rows = db.scalars(
        select(InsuranceCompany).where(InsuranceCompany.status == AccountStatus.ACTIVE.value)
    ).all()
    company_alias_rows = db.scalars(
        select(CompanyAlias).where(CompanyAlias.status == AccountStatus.ACTIVE.value)
    ).all()
    companies = build_companies_payload(company_rows, company_alias_rows)

    benefit_alias_rows = db.scalars(
        select(BenefitAlias).where(BenefitAlias.status == AccountStatus.ACTIVE.value)
    ).all()
    aliases_by_concept: dict[str, list[dict]] = {}
    for item in benefit_alias_rows:
        aliases_by_concept.setdefault(str(item.benefit_id), []).append({
            "phrase": item.phrase,
            "normalized_phrase": item.normalized_phrase,
            "scope": item.scope,
            "company_id": str(item.company_id) if item.company_id else None,
            "product_id": str(item.product_id) if item.product_id else None,
            "package_id": str(item.package_id) if item.package_id else None,
        })

    benefit_concepts = [
        {
            "concept_id": concept.id,
            "concept_key": concept.concept_key,
            "label": concept.label,
            "description": concept.description,
            "description_variants": concept.description_variants,
            "match_dataset": concept.match_dataset or [],
            "value_pattern_dataset": concept.value_pattern_dataset or [],
            "aliases": aliases_by_concept.get(str(concept.id), []),
        }
        for concept in db.scalars(
            select(BenefitConcept).where(BenefitConcept.status == AccountStatus.ACTIVE.value)
        ).all()
    ]
    return {
        "db_aliases": aliases,
        "db_brands": list(dict.fromkeys(brands)),
        "db_models": list(dict.fromkeys(models)),
        "db_companies": companies,
        "db_benefit_concepts": benefit_concepts,
        "db_packs": get_db_packs(db),
        "db_corrections": get_correction_memory(db, None),
    }


def load_extraction_context(db) -> dict:
    """Load immutable request inputs once before spawning the extractor with in-memory caching."""
    from app.core.cache import get_or_set
    return get_or_set("extraction_context", lambda: _query_extraction_context(db), ttl_seconds=120.0)


def _company_resolution(fields: dict, companies: list[dict]) -> dict:
    selected = str((fields.get("insurance_company") or {}).get("value") or "").strip()
    return resolve_company(selected, companies)


def _record_values(full: dict) -> dict:
    return {
        "method_summary": full.get("method_summary") or [],
        "raw_text": full.get("raw_text") or "",
        "ocr_text": full.get("ocr_text") or "",
        "page_text": full.get("page_text") or [],
        "words": full.get("words") or [],
        "blocks": full.get("blocks") or [],
        "tables": full.get("tables") or [],
        "images": full.get("images") or [],
        "regions": full.get("regions") or [],
        "candidates": full.get("candidates") or {},
        "benefit_lines": full.get("benefit_lines") or [],
        "company_resolution": full.get("company_resolution") or {},
        "warnings": full.get("warnings") or [],
        "reading_quality": full.get("reading_quality") or "check_needed",
    }


def process_extraction_job(
    db,
    settings,
    job: Job,
    *,
    worker_id: str,
    storage: SupabaseStorage | None = None,
    extractor=extract_with_limits,
    context_loader=load_extraction_context,
) -> None:
    """Process one already-leased extraction job and atomically complete it."""

    uploaded = db.get(UploadedFile, job.uploaded_file_id) if job.uploaded_file_id else None
    session = db.get(Session, job.session_id) if job.session_id else None
    if not uploaded or not session:
        raise JobProcessingError("source_missing", "The uploaded document is no longer available.")
    draft = db.get(QuotationDraft, session.draft_id)
    batch = db.get(Batch, uploaded.batch_id)
    if not draft or not batch:
        raise JobProcessingError("workspace_missing", "The quotation workspace is incomplete.")
    if draft.revision != 1 or draft.scalar_decisions:
        raise JobProcessingError("draft_changed", "This quotation changed before extraction completed. Start a fresh upload.")

    heartbeat_job(db, job, worker_id=worker_id, progress=5, phase="validating_source", lease_seconds=300)
    logger.info("Job %s: validating source document (file=%s, name=%s)", job.id, uploaded.id, uploaded.original_filename)
    # Track the local ephemeral path for post-extraction Supabase promotion.
    _ephemeral_path: Path | None = None
    if uploaded.storage_provider == "local_ephemeral":
        resolved_file = resolve_qc_path(uploaded.storage_path)
        _ephemeral_path = resolved_file
        source_bytes = None
        import time
        for _ in range(6):
            if _ephemeral_path.exists():
                try:
                    source_bytes = _ephemeral_path.read_bytes()
                    break
                except (PermissionError, FileNotFoundError, OSError):
                    pass
            if source_bytes is None:
                for candidate in [
                    QC_TEMP_ROOT / "stateless_uploads" / f"{uploaded.id}.pdf",
                    REPOSITORY_ROOT / "backend" / ".qc-tmp" / "stateless_uploads" / f"{uploaded.id}.pdf",
                    Path(".qc-tmp/stateless_uploads") / f"{uploaded.id}.pdf",
                ]:
                    if candidate.exists():
                        try:
                            source_bytes = candidate.read_bytes()
                            _ephemeral_path = candidate
                            break
                        except Exception:
                            pass
            if source_bytes is not None:
                break
            time.sleep(0.3)
                
        if source_bytes is None:
            import os
            logger.error("EPHEMERAL MISSING. storage_path=%r, resolved_file=%r, cwd=%r", uploaded.storage_path, str(resolved_file), os.getcwd())
            raise JobProcessingError("source_missing", "The ephemeral uploaded document is no longer available.")
    else:
        source_bytes = (storage or SupabaseStorage(settings)).download_bytes(uploaded.storage_path)

    expected_hash = uploaded.storage_sha256 or ""
    if not expected_hash or not hashlib.sha256(source_bytes).hexdigest() == expected_hash:
        raise JobProcessingError("source_integrity_failed", "The uploaded document failed its integrity check.")
    maximum = getattr(settings, "max_source_pdf_bytes", None)
    if maximum and len(source_bytes) > maximum:
        raise JobProcessingError("source_limit_exceeded", "The uploaded document exceeds the configured source limit.")

    logger.info("Job %s: source document ready (%d bytes)", job.id, len(source_bytes))

    if job.cancelled_at is not None or job.state == "cancelled":
        logger.info("Job %s was cancelled before extraction started; aborting.", job.id)
        return

    context = context_loader(db)
    heartbeat_job(db, job, worker_id=worker_id, progress=15, phase="extracting", lease_seconds=300)
    logger.info("Job %s: executing extraction pipeline (enhanced_reading=%s)", job.id, bool((job.payload or {}).get("enhanced_reading")))
    with qc_temp_directory("extract-") as directory:
        source_path = (directory / "source.pdf").resolve()
        source_path.write_bytes(source_bytes)
        result = extractor(
            source_path,
            enhanced_reading=bool((job.payload or {}).get("enhanced_reading")),
            source_filename=uploaded.original_filename,
            **context,
        )

    # If job was cancelled while extractor was running, discard results immediately
    db.refresh(job)
    if job.cancelled_at is not None or job.state == "cancelled":
        logger.info("Job %s was cancelled during extraction; discarding results.", job.id)
        return

    full = result.get("full_record") or {}
    draft_data = result.get("draft") or {}
    values = _record_values(full)
    heartbeat_job(db, job, worker_id=worker_id, progress=85, phase="saving_review", lease_seconds=300)
    logger.info("Job %s: extraction completed (%d fields), saving review records", job.id, len(draft_data.get("fields") or {}))
    if not values["company_resolution"]:
        values["company_resolution"] = _company_resolution(draft_data.get("fields") or {}, context.get("db_companies") or [])

    record = db.scalar(select(ExtractionRecord).where(ExtractionRecord.uploaded_file_id == uploaded.id))
    if record is None:
        record = ExtractionRecord(id=new_id(), uploaded_file_id=uploaded.id, **values)
        db.add(record)
        db.flush()
    else:
        for field, value in values.items():
            setattr(record, field, value)
        db.flush()

    fields = draft_data.get("fields") or {}
    for field in fields.values():
        if isinstance(field, dict) and field.get("value") not in (None, ""):
            field["status"] = "ready"
    fee_setting = db.get(AppSetting, "default_runner_fee")
    if fee_setting is not None and str(fields.get("service_fee", {}).get("value") or "").strip() == "":
        try:
            fields["service_fee"] = {"value": f"{float((fee_setting.value or {}).get('amount', 0)):.2f}", "status": "ready", "message": ""}
        except (TypeError, ValueError):
            pass

    # Strictly preserve internal system quotation reference (never overwrite from PDF)
    existing_qref = (draft.fields or {}).get("quotation_reference") or session.quotation_ref
    qref_val = existing_qref.get("value") if isinstance(existing_qref, dict) else existing_qref
    if not qref_val or not str(qref_val).startswith("RL"):
        from app.services.quotation_reference_service import generate_quotation_reference
        qref_val = session.quotation_ref if session.quotation_ref and str(session.quotation_ref).startswith("RL") else generate_quotation_reference(db)
        session.quotation_ref = qref_val
    fields["quotation_reference"] = {"value": qref_val, "status": "ready", "message": ""}
    draft.fields = fields
    draft.warnings = draft_data.get("warnings") or []
    draft.status = draft_data.get("status") or RecordStatus.CHECK_NEEDED.value
    draft.scalar_decisions = {
        name: {
            "decision": "confirm",
            "decided_by": draft.owner_id,
            "decided_at": datetime.now(timezone.utc).isoformat(),
        }
        for name, field in fields.items()
        if isinstance(field, dict) and field.get("value") not in (None, "")
    }
    uploaded.status = draft.status
    uploaded.simple_issue = (
        "Cannot Read" if draft.status == RecordStatus.CANNOT_READ.value
        else "Please check this value." if draft.status == RecordStatus.CHECK_NEEDED.value
        else None
    )
    batch.status = draft.status
    session.detected_company = str((draft.fields.get("insurance_company") or {}).get("value") or "") or None
    company_id = (values["company_resolution"] or {}).get("company_id")
    if not session.detected_company and company_id:
        comp_obj = db.get(InsuranceCompany, company_id)
        if comp_obj:
            session.detected_company = comp_obj.name
    elif not session.detected_company and uploaded.original_filename:
        # Match filename against company names/aliases using standardized resolver
        fn_clean = uploaded.original_filename.replace("_", " ").replace("-", " ")
        db_comps = context.get("db_companies") or []
        res = resolve_company(fn_clean, db_comps)
        if res.get("status") == "matched" and res.get("company_id"):
            session.detected_company = res.get("display_name")
            if not company_id:
                company_id = res.get("company_id")
        else:
            fn_lower = fn_clean.lower()
            for comp_dict in db_comps:
                c_name = str(comp_dict.get("name") or "").lower()
                c_aliases = [str(a).lower() for a in comp_dict.get("aliases") or []]
                if any(n and len(n) >= 3 and n in fn_lower for n in [c_name, *c_aliases]):
                    session.detected_company = comp_dict.get("name")
                    if not company_id:
                        company_id = comp_dict.get("company_id")
                    break

    if company_id:
        draft.company_id = company_id
        uploaded.insurance_company_id = company_id
        initialize_catalog_review(db, draft)

    existing_line_ids = {
        item.line_id
        for item in db.scalars(
            select(ExtractionBenefitLine).where(ExtractionBenefitLine.extraction_record_id == record.id)
        ).all()
        if item.extraction_record_id == record.id
    }
    new_lines = []
    for source in values["benefit_lines"]:
        line_id = str(source.get("line_id") or "")
        if not line_id or line_id in existing_line_ids:
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
        new_lines.append(line)
        existing_line_ids.add(line_id)

    if new_lines:
        db.flush()
        for line in new_lines:
            db.add(DraftSourceLineDecision(
                id=new_id(),
                draft_id=draft.id,
                source_line_id=line.id,
                disposition="unresolved",
            ))
        db.flush()

    auto_apply_extracted_benefits(db, draft)

    # -------------------------------------------------------------------------
    # Auto-Resolve Vehicle, Customer Account & Insurance Tenure for All Quotes
    # -------------------------------------------------------------------------
    from app.services.insurance_tenure_service import (
        compute_quotation_content_hash,
        evaluate_tenure_ingestion,
        resolve_or_create_tenure,
    )
    from app.services.customer_account_service import resolve_or_create_customer
    from app.services.vehicle_tracking_service import get_or_create_vehicle_tracking

    def _fval(k: str) -> str:
        item = (draft.fields or {}).get(k)
        if isinstance(item, dict):
            val = item.get("value")
            return str(val).strip() if val is not None else ""
        return str(item).strip() if item is not None else ""

    raw_plate = _fval("vehicle_no")
    raw_chassis = _fval("chassis_no")
    raw_engine = _fval("engine_no")
    raw_cc = _fval("engine_cc")
    raw_brand = _fval("car_brand")
    raw_model = _fval("car_model")
    raw_yom = _fval("vehicle_year") or _fval("manufacture_year") or _fval("year_of_manufacture") or _fval("yom")
    veh_yom_val: int | None = None
    if raw_yom:
        m_yom = re.search(r"\b(19\d{2}|20\d{2})\b", raw_yom)
        if m_yom:
            try:
                veh_yom_val = int(m_yom.group(1))
            except Exception:
                pass
    customer = _fval("customer_name") or _fval("insured_name")
    raw_id = _fval("ic_or_brn") or _fval("customer_ic_no")

    # Universal Tenure Dates Fallback: cover_start -> issue_date -> valid_until -> today
    cover_start = _fval("cover_start_date") or _fval("issue_date") or _fval("valid_until")
    cover_end = _fval("cover_end_date") or _fval("valid_until")

    # Plate Fallback to Filename or Chassis
    clean_plate = raw_plate.upper().strip() if raw_plate else ""
    if clean_plate in ("", "N/A", "NA", "NONE", "UNREGISTERED", "NEW", "TBA", "-", "UNKNOWN") and uploaded.original_filename:
        clean_fn = uploaded.original_filename.upper().replace("_", " ").replace("-", " ")
        for fn_candidate in re.findall(r"\b[A-Z]{1,3}\s*\d{1,4}\s*[A-Z]?\b", clean_fn):
            compact_cand = re.sub(r"\s+", "", fn_candidate)
            if not re.fullmatch(r"20\d{2}|19\d{2}|PDF|REF|STMB|AMGEN|QBE|PDS|QUOTATION", compact_cand):
                clean_plate = compact_cand
                if isinstance(draft.fields, dict):
                    draft.fields["vehicle_no"] = {"value": compact_cand, "status": "ready", "source": "filename"}
                break

    clean_chassis = raw_chassis.upper().strip() if raw_chassis else ""
    if clean_plate in ("", "N/A", "NA", "NONE", "UNREGISTERED", "NEW", "TBA", "-", "UNKNOWN") and clean_chassis:
        effective_veh_no = f"CHASSIS: {clean_chassis}"
    else:
        effective_veh_no = clean_plate or (f"CHASSIS: {clean_chassis}" if clean_chassis else "UNPLATED")

    # Customer account resolution
    cust_account = None
    if customer or raw_id:
        cust_account, discrepancies = resolve_or_create_customer(
            db=db,
            raw_name=customer or "Valued Client",
            raw_id=raw_id or None,
        )
        if cust_account:
            session.customer_id = cust_account.id
            if discrepancies:
                curr_opts = draft.display_options or {}
                curr_opts["customer_discrepancies"] = discrepancies
                draft.display_options = curr_opts

    # Vehicle Tracking & Full Spec Persistence
    veh, owner_alert = get_or_create_vehicle_tracking(
        db=db,
        vehicle_no=effective_veh_no,
        customer_name=customer or "Valued Client",
        validity_date=cover_end or cover_start or None,
        session_id=session.id,
        brand=raw_brand or None,
        model=raw_model or None,
        chassis_no=raw_chassis or None,
        engine_no=raw_engine or None,
        customer_id=cust_account.id if cust_account else None,
    )
    if veh:
        session.tracked_vehicle_id = veh.id
        if veh_yom_val and not veh.manufacture_year:
            veh.manufacture_year = veh_yom_val
        if raw_cc and not veh.engine_cc:
            veh.engine_cc = raw_cc
        if raw_chassis and not veh.chassis_no:
            veh.chassis_no = raw_chassis
        if raw_engine and not veh.engine_no:
            veh.engine_no = raw_engine
        if raw_brand and not veh.car_brand:
            veh.car_brand = raw_brand
        if raw_model and not veh.car_model:
            veh.car_model = raw_model
        if owner_alert:
            curr_opts = draft.display_options or {}
            curr_opts["owner_change_alert"] = owner_alert
            draft.display_options = curr_opts

    # Insurance Tenure (100% Guaranteed Anchor with Any Date or Today)
    tenure: InsuranceTenure | None = None
    if session.tenure_id:
        tenure = db.get(InsuranceTenure, session.tenure_id)
        if tenure:
            if veh and not tenure.tracked_vehicle_id:
                tenure.tracked_vehicle_id = veh.id
            if cust_account and not tenure.customer_id:
                tenure.customer_id = cust_account.id

    if not tenure:
        tenure = resolve_or_create_tenure(
            db=db,
            vehicle_no=effective_veh_no,
            customer_name=customer or "Valued Client",
            start_date=cover_start or None,
            end_date=cover_end or None,
            tracked_vehicle_id=veh.id if veh else None,
            customer_id=cust_account.id if cust_account else None,
            chassis_no=raw_chassis or None,
            engine_no=raw_engine or None,
        )
    session.tenure_id = tenure.id
    session.coverage_start_date = tenure.coverage_start_date
    session.coverage_end_date = tenure.coverage_end_date

    # Propagate detected NCD into tenure if not initialized
    if tenure and tenure.ncd_percentage is None and isinstance(draft.fields, dict):
        from app.services.marketing_comparison_service import _extract_ncd_from_draft
        ext_ncd = _extract_ncd_from_draft(draft.fields)
        if ext_ncd is not None:
            tenure.ncd_percentage = ext_ncd

    # Compute content hash & evaluate tenure ingestion
    content_hash = compute_quotation_content_hash(
        fields=draft.fields,
        benefits=draft_data.get("benefits"),
    )
    session.content_hash = content_hash

    action, existing_sess, version = evaluate_tenure_ingestion(
        db=db,
        tenure_id=tenure.id,
        company_name=session.detected_company,
        company_id=draft.company_id,
        content_hash=content_hash,
        current_session_id=session.id,
    )
    curr_opts = draft.display_options or {}
    if action == "SKIP_IDENTICAL" and existing_sess and existing_sess.id != session.id:
        session.status = "trash"
        session.is_tenure_active = False
        session.tenure_version = existing_sess.tenure_version
        curr_opts["duplicate_skipped"] = True
        curr_opts["original_session_id"] = existing_sess.id
        curr_opts["skip_message"] = (
            f"Identical quote for {session.detected_company or 'this insurer'} already active in this tenure (v{existing_sess.tenure_version})."
        )
    else:
        session.tenure_version = version
        session.is_tenure_active = True
        if version > 1:
            curr_opts["tenure_version_notice"] = f"Created revised version v{version} under {session.detected_company or 'insurer'}."
    draft.display_options = curr_opts

    complete_job(
        db,
        job,
        worker_id,
        {"session_id": session.id, "draft_id": draft.id, "tenure_id": tenure.id},
    )

    logger.info("Job %s: review saved and job marked complete (session=%s, draft=%s, tenure=%s)", job.id, session.id, draft.id, tenure.id)

    # Deferred Supabase promotion: runs AFTER the job is marked complete so the
    # user sees results immediately. Uses a fresh httpx.Client (not the shared
    # singleton) to avoid thread-safety issues from asyncio.to_thread context.
    # RL-NOTE: _ephemeral_path is set only when storage_provider=="local_ephemeral".
    if _ephemeral_path is not None:
        try:
            import httpx as _httpx
            with _httpx.Client(timeout=_httpx.Timeout(60.0, connect=10.0)) as _http:
                _sc = SupabaseStorage(settings, client=_http)
                now = datetime.now(timezone.utc)
                _object_key = f"source/{now:%Y}/{now:%m}/{uploaded.id}/{uploaded.original_filename}"
                _uploader = getattr(_sc, "upload_source_pdf", getattr(_sc, "upload_pdf", None))
                if _uploader is not None:
                    _stored = _uploader(_object_key, source_bytes)
                    uploaded.storage_path = _stored.object_key
                    uploaded.storage_provider = "supabase"
                    uploaded.storage_bucket = getattr(_stored, "bucket", None)
                    uploaded.storage_etag = getattr(_stored, "etag", None)
                    db.commit()
                    _ephemeral_path.unlink(missing_ok=True)
                    logger.info("Source PDF promoted to Supabase after extraction: %s", _stored.object_key)
        except Exception as _upload_exc:
            logger.warning("Post-extraction Supabase promotion failed (ephemeral file retained): %s", _upload_exc)



def run_one_job(
    db,
    settings,
    *,
    worker_id: str,
    storage: SupabaseStorage | None = None,
) -> Job | None:
    """Claim and synchronously run at most one heavy task."""

    job = claim_next_job(db, worker_id=worker_id, lease_seconds=300)
    if job is None:
        return None
    logger.info(
        "Worker [%s] claimed job %s (type=%s, attempt=%s/%s)",
        worker_id,
        job.id,
        job.job_type,
        job.attempt,
        job.max_attempts,
    )
    try:
        if job.job_type == "extract_pdf":
            process_extraction_job(db, settings, job, worker_id=worker_id, storage=storage)
        elif job.job_type == "render_pdf":
            process_render_job(db, settings, job, worker_id=worker_id, storage=storage)
        else:
            raise JobProcessingError("unsupported_job", "This background task is not supported.")
        logger.info("Job %s (%s) finished successfully", job.id, job.job_type)
    except JobProcessingError as exc:
        logger.error(
            "Job %s (%s) failed with JobProcessingError: [%s] %s",
            job.id,
            job.job_type,
            exc.code,
            exc.safe_message,
        )
        db.rollback()
        fresh_job = db.get(Job, job.id) or job
        fail_job(db, fresh_job, worker_id=worker_id, code=exc.code, message=exc.safe_message)
    except RenderJobProcessingError as exc:
        logger.error(
            "Job %s (%s) failed with RenderJobProcessingError: [%s] %s",
            job.id,
            job.job_type,
            exc.code,
            exc.safe_message,
        )
        db.rollback()
        fresh_job = db.get(Job, job.id) or job
        fail_job(db, fresh_job, worker_id=worker_id, code=exc.code, message=exc.safe_message)
    except Exception:
        logger.exception("Job %s (%s) failed with unhandled exception", job.id, job.job_type)
        db.rollback()
        fresh_job = db.get(Job, job.id) or job
        fail_job(
            db,
            fresh_job,
            worker_id=worker_id,
            code="processing_failed",
            message="The background task failed safely and will be retried.",
        )
    return job
