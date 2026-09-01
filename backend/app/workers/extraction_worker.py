"""Single-task extraction worker backed by durable Postgres jobs."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.core.workspace import qc_temp_directory
from app.extraction.company_resolution import build_companies_payload, resolve_company
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


def load_extraction_context(db) -> dict:
    """Load immutable request inputs once before spawning the extractor."""

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
    }


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
    if uploaded.storage_provider == "local_ephemeral":
        import os
        if not os.path.exists(uploaded.storage_path):
            raise JobProcessingError("source_missing", "The ephemeral uploaded document is no longer available.")
        source_bytes = Path(uploaded.storage_path).read_bytes()
    else:
        storage_client = storage or SupabaseStorage(settings)
        source_bytes = storage_client.download_bytes(uploaded.storage_path)
    expected_hash = uploaded.storage_sha256 or ""
    if not expected_hash or not hashlib.sha256(source_bytes).hexdigest() == expected_hash:
        raise JobProcessingError("source_integrity_failed", "The uploaded document failed its integrity check.")
    maximum = getattr(settings, "max_source_pdf_bytes", None)
    if maximum and len(source_bytes) > maximum:
        raise JobProcessingError("source_limit_exceeded", "The uploaded document exceeds the configured source limit.")

    context = context_loader(db)
    heartbeat_job(db, job, worker_id=worker_id, progress=15, phase="extracting", lease_seconds=300)
    with qc_temp_directory("extract-") as directory:
        source_path = (directory / "source.pdf").resolve()
        source_path.write_bytes(source_bytes)
        result = extractor(
            source_path,
            enhanced_reading=bool((job.payload or {}).get("enhanced_reading")),
            source_filename=uploaded.original_filename,
            **context,
        )

    full = result.get("full_record") or {}
    draft_data = result.get("draft") or {}
    values = _record_values(full)
    heartbeat_job(db, job, worker_id=worker_id, progress=85, phase="saving_review", lease_seconds=300)
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
    complete_job(
        db,
        job,
        worker_id,
        {"session_id": session.id, "draft_id": draft.id},
    )
    
    if uploaded.storage_provider == "local_ephemeral":
        Path(uploaded.storage_path).unlink(missing_ok=True)


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
    try:
        if job.job_type == "extract_pdf":
            process_extraction_job(db, settings, job, worker_id=worker_id, storage=storage)
        elif job.job_type == "render_pdf":
            process_render_job(db, settings, job, worker_id=worker_id, storage=storage)
        else:
            raise JobProcessingError("unsupported_job", "This background task is not supported.")
    except JobProcessingError as exc:
        db.rollback()
        fail_job(db, job, worker_id=worker_id, code=exc.code, message=exc.safe_message)
    except RenderJobProcessingError as exc:
        db.rollback()
        fail_job(db, job, worker_id=worker_id, code=exc.code, message=exc.safe_message)
    except Exception:
        logger.exception("Background job failed", extra={"job_id": job.id, "job_type": job.job_type})
        db.rollback()
        fail_job(
            db,
            job,
            worker_id=worker_id,
            code="processing_failed",
            message="The background task failed safely and will be retried.",
        )
    return job
