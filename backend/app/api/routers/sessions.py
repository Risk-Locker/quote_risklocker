"""Sessions API router."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import APIRouter, Body, Depends, File, Form, Header, Query, Request, Response as FastAPIResponse, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import AuthContext, current_auth, current_auth_optional, current_user, ensure_trusted_origin, settings_dep
from app.api.schemas import (
    BenefitAliasSaveRequest,
    BenefitCatalogSaveRequest,
    BenefitConceptSaveRequest,
    BulkClientRecordDeleteRequest,
    BulkUploadedFileDeleteRequest,
    BusinessCompanySaveRequest,
    BusinessProductSaveRequest,
    BusinessTierSaveRequest,
    CatalogContextRequest,
    CatalogOfferingSaveRequest,
    CatalogPublishRequest,
    ClientRecordUpdateRequest,
    CompanySaveRequest,
    CompanyAliasSaveRequest,
    CoverageTypeSaveRequest,
    DictionaryLearnRequest,
    DraftGenerateRequest,
    DraftUpdateRequest,
    ExtractionSettingsRequest,
    FieldAliasSaveRequest,
    GenerateSelectedRequest,
    GroundingChatRequest,
    LoginRequest,
    OurSpecialSaveRequest,
    OurSpecialVariantSaveRequest,
    PackageCloneRequest,
    PackagePlanItemsRequest,
    PackagePlanSaveRequest,
    PackageSaveRequest,
    RoadTaxRuleSaveRequest,
    RoadTaxCalculateRequest,
    BenefitProfileCreateRequest,
    BenefitProfileCloneRequest,
    BenefitProfileUpdateRequest,
    CompanyBenefitProfileCreateRequest,
    CompanyBenefitProfileCloneRequest,
    CompanyBenefitProfileUpdateRequest,
    CompanyBenefitConfigsUpdateRequest,
    CompanyBenefitConditionSaveRequest,
    CompanyMatrixDiffRequest,
    RecordBulkActionRequest,
    RecordSavedViewRequest,
    SegmentSaveRequest,
    TemplateSaveRequest,
    TemplateGroupSaveRequest,
    TemplatePublishRequest,
    TemplateSelectionImpactRequest,
    TemplateUpdateRequest,
    TrashDeleteForeverRequest,
    BulkDeleteRequest,
    BulkDownloadZipRequest,
    BulkQuotationStatusRequest,
    UserCreateRequest,
    UserPasswordChangeRequest,
    UserUpdateRequest,
    VariantMoveRequest,
    VehicleBrandSaveRequest,
    VehicleCategorySaveRequest,
    VehicleModelSaveRequest,
    VehicleSubcategorySaveRequest,
    WorkspacePatchRequest,
    VersionGenerationRequest,
    SessionRescanRequest,
    BenefitCardPresetSaveRequest,
    BenefitCardPresetCreateRequest,
    BusinessAssetUpdateRequest,
    BusinessAssetBulkDeleteRequest,
    BusinessAssetBulkMoveRequest,
    BusinessAssetFolderRenameRequest,
    BusinessAssetFolderDeleteRequest,
    CatalogOperationsPreviewRequest,
    CatalogOperationsApplyRequest,
    CopilotChatRequest,
    CopilotChatResponse,
    SessionCleanupRequest,
    ProfileCleanupRequest,
    QuotationActivityCreateRequest,
    QuotationStatusUpdateRequest,
    BackfillConfirmRequest,
    VehicleOwnershipResolutionRequest,
)
from app.auth.cookies import clear_auth_cookies, set_auth_cookies
from app.auth.rbac import can_view_owner_record, require_role
from app.core.config import Settings
from app.core.errors import AppError
from app.extraction.company_resolution import build_companies_payload, resolve_company
from app.db.session import get_db
from app.models.enums import AccountStatus, Role, StorageStatus
from app.models.tables import (
    AuditEvent,
    CompanyAlias,
    FieldAlias,
    BusinessAsset,
    BenefitCardPreset,
    DraftBenefitSelection,
    DraftSourceLineDecision,
    ExtractionBenefitLine,
    ExtractionRecord,
    GeneratedPdfVersion,
    InsuranceCompany,
    Job,
    OurSpecial,
    OurSpecialVariant,
    OutputTemplateConfig,
    QuotationDraft,
    StorageConnection,
    UploadedFile,
    User,
    VehicleBrand,
    VehicleModel,
)
from app.services.admin_service import (
    copy_template,
    delete_field_alias,
    delete_template_group,
    delete_vehicle_brand,
    delete_vehicle_model,
    dictionary_contains,
    get_bulk_upload_limit,
    get_runner_fee_default,
    import_vehicles_workbook,
    learn_dictionary_value,
    list_template_groups,
    make_template_master,
    save_strategy_settings,
    serialize_special,
    serialize_template,
    serialize_templates_batch,
    set_bulk_upload_limit,
    set_runner_fee_default,
    update_template,
    upsert_company,
    upsert_field_alias,
    upsert_special,
    upsert_template,
    upsert_template_group,
    upsert_variant,
    move_variant,
    upsert_vehicle_brand,
    upsert_vehicle_model,
)
from app.services.trash_service import (
    delete_special,
    delete_special_variant,
)
from app.services.auth_service import (
    change_password,
    create_user,
    login_with_password,
    revoke_session,
    revoke_user_sessions,
    serialize_user,
    update_user,
)
from app.services.notification_service import (
    get_notifications,
    get_unread_count,
    mark_all_read,
    mark_read,
    serialize_notification,
)
from app.services.generation_service import (
    render_snapshot_preview_html,
    request_preview_render,
    request_version_generation,
)
from app.services.pdf_content import load_pdf_bytes, parse_byte_range
from app.services.review_service import (
    get_accessible_draft,
    move_to_trash,
    purge_expired_trash,
    restore_from_trash,
    serialize_draft,
    update_draft_fields,
)
from app.services.system_checks import get_system_checks
from app.services.template_assets import (
    _uploaded_assets as uploaded_assets_paged,
    count_uploaded_assets,
    delete_template_asset,
    folder_summary,
    list_template_assets,
    resolve_template_asset,
    upload_template_asset,
)
from app.services.job_service import cancel_job, serialize_job
from app.services.upload_service import serialize_batch
from app.services.upload_intake_service import create_queued_upload
from app.services.session_service import (
    get_session,
    get_session_filter_options,
    list_sessions,
    serialize_session,
)
from app.services.quotation_activity_service import (
    backfill_existing_sessions,
    get_calendar_activities,
    get_insights_analytics,
    log_quotation_activity,
    preview_backfill_sessions,
    update_quotation_status,
)
from app.services.client_dossier_service import (
    get_client_dossiers,
)
from app.services.vehicle_tracking_service import (
    get_vehicle_history,
)
from app.services.workspace_service import apply_workspace_patch, build_workspace_snapshot, template_selection_impact
from app.services.workspace_service import workspace_capabilities
from app.services.workspace_source_service import get_source_evidence, get_source_pages, get_workspace_template_config
from app.services.template_revision_service import (
    list_page_profiles,
    list_published_templates,
    publish_template_revision,
    serialize_template_revision,
)
from app.services.client_record_service import (
    delete_view as delete_record_view,
    export_csv_bytes,
    get_record,
    list_records_page,
    list_saved_views,
    records_matching_ids,
    save_view as save_record_view,
    serialize_record,
    serialize_saved_view,
    set_records_archived,
    update_record,
)
from app.services.matrix_service import (
    get_company_matrix_data,
    generate_company_matrix_docx,
    generate_company_matrix_xlsx,
    diff_company_matrix,
)
from app.services.catalog_operations_service import (
    parse_catalog_intent,
    preview_catalog_operations,
    apply_catalog_operations,
)
from app.services.road_tax_service import (
    calculate_breakdown,
    delete_rule as delete_road_tax_rule,
    export_csv_bytes as export_road_tax_csv,
    import_rules as import_road_tax_rules,
    list_rules,
    seed_standard_road_tax_rules,
    serialize_rule,
    upsert_rule as upsert_road_tax_rule,
)
from app.services.import_export import parse_tabular, parse_vehicles_workbook
from app.storage.supabase import StorageError, StorageNotFound, SupabaseStorage
from app.services.business_setup_service import (
    create_benefit_catalog,
    create_new_draft_revision,
    activate_benefit_profile,
    clone_benefit_profile,
    create_benefit_profile,
    delete_benefit_profile,
    list_benefit_profiles,
    update_benefit_profile,
    activate_company_profile,
    clone_company_profile,
    create_company_profile,
    delete_company_condition,
    delete_company_profile,
    get_catalog_workspace,
    get_business_company_workspace,
    get_company_benefit_configs,
    list_benefit_concepts,
    list_business_assets,
    list_business_asset_categories,
    batch_upload_business_assets,
    update_business_asset,
    replace_business_asset_file,
    bulk_move_business_assets,
    delete_business_asset,
    bulk_delete_business_assets,
    rename_business_asset_folder,
    delete_business_asset_folder,
    list_business_companies,
    list_company_aliases,
    list_company_conditions,
    list_company_profiles,
    list_source_documents,
    save_benefit_concept,
    save_company_condition,
    update_company_benefit_configs,
    update_company_profile,
    retire_benefit_concept,
    restore_benefit_concept,
    save_business_company,
    delete_business_company,
    save_business_product,
    delete_business_product,
    save_business_tier,
    delete_business_tier,
    save_company_alias,
    save_catalog_offering,
    remove_catalog_offering,
    publish_catalog_revision,
    retire_benefit_catalog,
    update_catalog_context,
    upload_business_asset,
    retire_company_alias,
)
from app.services.worker_health import worker_readiness
from app.services.benefit_setup_service import (
    clone_package,
    list_benefit_aliases,
    list_coverage_types,
    list_segments,
    list_vehicle_categories,
    list_vehicle_subcategories,
    retire_benefit_alias,
    retire_coverage_type,
    retire_package,
    retire_plan,
    retire_segment,
    retire_vehicle_category,
    retire_vehicle_subcategory,
    save_benefit_alias,
    save_coverage_type,
    save_package,
    save_plan,
    save_plan_items,
    save_segment,
    save_vehicle_category,
    save_vehicle_subcategory,
)
from app.services.global_benefit_profile_service import (
    activate_global_benefit_profile,
    auto_assign_category_assets,
    clone_global_benefit_profile,
    create_global_benefit_profile,
    delete_global_benefit_profile,
    get_global_benefit_profile_detail,
    list_global_benefit_profiles,
    save_global_benefit_profile_assets,
)
from app.services.benefit_template_preset_service import (
    create_custom_benefit_card_preset,
    delete_custom_benefit_card_preset,
    get_benefit_card_preset,
    list_benefit_card_presets,
    reset_benefit_card_preset,
    save_benefit_card_preset,
    set_default_benefit_card_preset,
)


from app.api.routers.common import _pdf_response

logger = logging.getLogger(__name__)

router = APIRouter()

def load_pdf_bytes(record: Any, settings: Settings) -> bytes:
    import app.api.routes as routes
    if hasattr(routes, "load_pdf_bytes") and routes.load_pdf_bytes is not load_pdf_bytes:
        return routes.load_pdf_bytes(record, settings)
    from app.services.pdf_content import load_pdf_bytes as _default_load_pdf_bytes
    return _default_load_pdf_bytes(record, settings)


@router.post("/batches/upload")
async def upload_batch(
    files: list[UploadFile] = File(...),
    enhanced_reading: bool = Form(False),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> dict:
    # RL-DISABLED new batch upload — disabled 2026-08-13; legacy batch records remain readable.
    raise AppError("Multi-file upload is no longer available. Upload one PDF from the Upload page.", 410)



@router.post("/uploads", status_code=status.HTTP_202_ACCEPTED)
async def upload_one(
    file: UploadFile = File(...),
    enhanced_reading: bool = Form(False),
    is_test: bool = Form(False),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> dict:
    queued = await create_queued_upload(
        db,
        settings,
        owner_id=user.id,
        upload=file,
        idempotency_key=idempotency_key,
        enhanced_reading=enhanced_reading,
        is_test=is_test,
    )
    return {
        "session_id": queued.session.id,
        "job_id": queued.job.id,
        "uploaded_file_id": queued.uploaded_file.id,
        "created": queued.created,
    }



@router.get("/jobs/{job_id}")
def job_detail(job_id: str, db: Session = Depends(get_db), _user: User = Depends(current_user)) -> dict:
    job = db.get(Job, job_id)
    if not job:
        raise AppError("Job not found.", 404)
    return {"job": serialize_job(job)}



@router.post("/jobs/{job_id}/cancel")
def job_cancel(job_id: str, db: Session = Depends(get_db), _user: User = Depends(current_user)) -> dict:
    job = db.get(Job, job_id)
    if not job:
        raise AppError("Job not found.", 404)
    cancel_job(db, job)
    return {"job": serialize_job(job)}



@router.get("/batches/{batch_id}")
def batch_detail(batch_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    from app.models.tables import Batch

    batch = db.scalar(select(Batch).where(Batch.id == batch_id).options(selectinload(Batch.files).selectinload(UploadedFile.draft)))
    if not batch or batch.deleted_at:
        raise AppError("Batch not found.", 404)
    if not can_view_owner_record(db, user, batch.owner_id):
        raise AppError("You do not have permission to view this batch.", 403)
    return {"batch": serialize_batch(batch)}



@router.get("/drafts/{draft_id}")
def draft_detail(draft_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    draft = get_accessible_draft(db, user, draft_id)
    return {"draft": serialize_draft(draft, db)}



@router.patch("/drafts/{draft_id}")
def draft_update(draft_id: str, payload: DraftUpdateRequest, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    draft = update_draft_fields(
        db,
        user,
        draft_id,
        payload.fields,
        template_id=payload.template_id,
        layout_override=payload.layout_override,
    )
    return {"draft": serialize_draft(draft, db)}



@router.post("/drafts/{draft_id}/generate")
def draft_generate(draft_id: str, payload: DraftGenerateRequest | None = None, db: Session = Depends(get_db), settings: Settings = Depends(settings_dep), user: User = Depends(current_user)) -> dict:
    # RL-DISABLED legacy direct generation — disabled 2026-08-13; use the exact-revision session endpoint.
    raise AppError("Generate PDFs only from the final session Preview step.", 410)



@router.post("/drafts/{draft_id}/preview-png")
def draft_preview_png(draft_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> Response:
    # RL-DISABLED request-local Chromium preview — disabled 2026-08-13; canonical queued preview is a later endpoint.
    raise AppError("This legacy preview endpoint is no longer available.", 410)



@router.post("/drafts/generate-selected")
def generate_selected(payload: GenerateSelectedRequest, db: Session = Depends(get_db), settings: Settings = Depends(settings_dep), user: User = Depends(current_user)) -> dict:
    # RL-DISABLED batch generation — disabled 2026-08-13; generation belongs only to the final session step.
    raise AppError("Batch generation is no longer available. Review and generate each quotation from its final step.", 410)



@router.get("/sessions")
def sessions_list(
    search: str | None = None,
    company: str | None = None,
    staff_id: str | None = None,
    user_id: str | None = None,
    status: str | None = None,
    sort_by: str = "vehicle",
    type_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    effective_user_id = staff_id or user_id
    sessions, total = list_sessions(
        db,
        user.id,
        search=search,
        company=company,
        staff_id=effective_user_id,
        status=status,
        sort_by=sort_by,
        type_filter=type_filter,
        limit=min(max(limit, 1), 100),
        offset=max(offset, 0),
    )
    filter_options = get_session_filter_options(db) if offset == 0 else {"companies": [], "users": [], "staff": []}

    serialized = [serialize_session(s) for s in sessions]

    return {
        "sessions": serialized,
        "total": total,
        "filter_options": filter_options,
    }



@router.post("/sessions/bulk-delete")
def sessions_bulk_delete(payload: BulkDeleteRequest, db: Session = Depends(get_db), settings: Settings = Depends(settings_dep), user: User = Depends(current_user)) -> dict:
    from app.services.trash_service import permanent_delete_session
    for sid in payload.item_ids:
        try:
            permanent_delete_session(db, user, sid, SupabaseStorage(settings))
        except Exception:
            pass # Skip if not found or already deleted
    return {"deleted": True}



@router.post("/sessions/bulk-status")
def sessions_bulk_status(
    payload: BulkQuotationStatusRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    from app.services.quotation_activity_service import bulk_update_quotation_status

    return bulk_update_quotation_status(
        db=db,
        session_ids=payload.session_ids,
        status=payload.status,
        miss_reason=payload.miss_reason,
        won_premium=payload.won_premium,
        notes=payload.notes,
        user_id=user.id,
        coverage_start_date=payload.coverage_start_date,
        coverage_end_date=payload.coverage_end_date,
    )



@router.post("/sessions/bulk-download-zip")
def sessions_bulk_download_zip(
    payload: BulkDownloadZipRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> Response:
    import io
    import re
    import zipfile
    from app.models.tables import GeneratedPdfVersion, Session as SessionModel, UploadedFile

    if not payload.session_ids:
        raise AppError("No sessions provided for bulk download.", 400)

    buf = io.BytesIO()
    file_count = 0
    used_filenames: set[str] = set()

    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for sid in payload.session_ids:
            sess = db.get(SessionModel, sid)
            if not sess or sess.status == "trash":
                continue

            pdf_bytes: bytes | None = None
            gen_version = None
            if sess.draft_id:
                gen_version = db.scalar(
                    select(GeneratedPdfVersion)
                    .where(GeneratedPdfVersion.draft_id == sess.draft_id)
                    .order_by(GeneratedPdfVersion.version_number.desc())
                )

            if gen_version:
                try:
                    pdf_bytes = load_pdf_bytes(gen_version, settings)
                except Exception:
                    pdf_bytes = None

            if not pdf_bytes and sess.uploaded_file_id:
                up_file = db.get(UploadedFile, sess.uploaded_file_id)
                if up_file:
                    try:
                        pdf_bytes = load_pdf_bytes(up_file, settings)
                    except Exception:
                        pdf_bytes = None

            if not pdf_bytes:
                continue

            fields = sess.draft.fields if sess.draft and sess.draft.fields else {}
            plate = (fields.get("vehicle_no", {}).get("value") or "NOVIN").strip().upper().replace(" ", "")
            company = (sess.detected_company or fields.get("insurance_company", {}).get("value") or "Underwriter").strip().replace(" ", "_")
            qref = (sess.quotation_ref or fields.get("quotation_no", {}).get("value") or sess.id[:8]).strip()

            clean_name = re.sub(r"[^A-Za-z0-9_\-]", "_", f"{plate}_{company}_{qref}")[:60]
            filename = f"{clean_name}.pdf"

            idx = 2
            while filename in used_filenames:
                filename = f"{clean_name}_{idx}.pdf"
                idx += 1
            used_filenames.add(filename)

            zf.writestr(filename, pdf_bytes)
            file_count += 1

    if file_count == 0:
        raise AppError("None of the selected sessions have accessible PDF documents.", 404)

    buf.seek(0)
    zip_bytes = buf.getvalue()
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    download_name = f"Risklocker_Quotations_{timestamp_str}.zip"

    headers = {
        "Content-Disposition": f'attachment; filename="{download_name}"',
        "Content-Length": str(len(zip_bytes)),
    }
    return Response(content=zip_bytes, media_type="application/zip", headers=headers)



@router.get("/sessions/{session_id}")
def session_detail(session_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    session = get_session(db, session_id)
    return {"session": serialize_session(session)}



@router.delete("/sessions/{session_id}")
def session_delete(
    session_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> dict:
    session = get_session(db, session_id)
    active_jobs = db.scalars(
        select(Job).where(
            Job.session_id == session_id,
            Job.state.in_(["queued", "processing"]),
        )
    ).all()
    for j in active_jobs:
        try:
            cancel_job(db, j)
        except Exception:
            pass

    if session.uploaded_file_id:
        try:
            move_to_trash(db, settings, user, session.uploaded_file_id)
        except Exception:
            pass

    session.status = "trash"
    db.commit()
    return {"deleted": True, "session_id": session_id}



@router.get("/sessions/{session_id}/pdf")
def session_pdf(
    session_id: str,
    download: bool = Query(default=False),
    range_header: str | None = Header(default=None, alias="Range"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> Response:
    sess = get_session(db, session_id)
    if not can_view_owner_record(db, user, sess.owner_id):
        raise AppError("Session not found.", 404)

    if sess.draft_id:
        gen_version = db.scalar(
            select(GeneratedPdfVersion)
            .where(GeneratedPdfVersion.draft_id == sess.draft_id)
            .order_by(GeneratedPdfVersion.version_number.desc())
        )
        if gen_version:
            return _pdf_response(load_pdf_bytes(gen_version, settings), gen_version.filename, range_header, download)

    if sess.uploaded_file_id:
        uploaded = db.get(UploadedFile, sess.uploaded_file_id)
        if uploaded:
            return _pdf_response(load_pdf_bytes(uploaded, settings), uploaded.original_filename, range_header, download)

    raise AppError("No PDF document available for this session.", 404)



@router.get("/sessions/{session_id}/workspace")
def session_workspace(session_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    return {"workspace": build_workspace_snapshot(db, user, session_id)}



@router.post("/sessions/{session_id}/template-selection-impact")
def session_template_selection_impact(
    session_id: str,
    payload: TemplateSelectionImpactRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {
        "impact": template_selection_impact(
            db,
            user,
            session_id,
            template_revision_id=payload.template_revision_id,
            base_revision=payload.base_revision,
        )
    }



@router.get("/sessions/{session_id}/source-pages")
def session_source_pages(
    session_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return get_source_pages(db, user, session_id, page=page, page_size=page_size)



@router.get("/sessions/{session_id}/evidence/{field_name}")
def session_field_evidence(
    session_id: str,
    field_name: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return get_source_evidence(db, user, session_id, field_name)



@router.get("/sessions/{session_id}/template-config")
def session_template_config(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    try:
        return {"template": get_workspace_template_config(db, user, session_id)}
    except AppError as err:
        if err.status_code == 409:
            return {"template": None}
        raise



@router.post("/sessions/{session_id}/extract-gemini")
def session_extract_gemini(
    session_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> dict:
    from app.extraction.gemini_extractor import extract_with_gemini_sync, get_key_pool
    from app.services.catalog_review_service import initialize_catalog_review
    from app.models.tables import AppSetting, InsuranceCompany, BenefitConcept
    from app.extraction.db_lookups import get_db_packs, get_correction_memory

    session = get_session(db, session_id)
    if not session or not can_view_owner_record(db, user, session.owner_id):
        raise AppError("Session not found.", 404)
    draft = db.get(QuotationDraft, session.draft_id)
    if not draft:
        raise AppError("Quotation draft not found.", 404)
    uploaded = db.get(UploadedFile, session.uploaded_file_id)
    if not uploaded:
        raise AppError("Uploaded file not found.", 404)

    pdf_bytes = load_pdf_bytes(uploaded, settings)

    company_rows = db.scalars(
        select(InsuranceCompany).where(InsuranceCompany.status == AccountStatus.ACTIVE.value)
    ).all()
    alias_rows = db.scalars(
        select(CompanyAlias).where(CompanyAlias.status == AccountStatus.ACTIVE.value)
    ).all()
    db_companies = build_companies_payload(company_rows, alias_rows)
    db_benefit_concepts = [
        {
            "concept_id": concept.id,
            "concept_key": concept.concept_key,
            "label": concept.label,
        }
        for concept in db.scalars(select(BenefitConcept)).all()
    ]

    from app.extraction.native_pdf import extract_native
    from app.core.workspace import qc_temp_directory

    doc_text = None
    try:
        with qc_temp_directory("gemini-re-extract-") as td:
            temp_pdf = td / "doc.pdf"
            temp_pdf.write_bytes(pdf_bytes)
            native = extract_native(temp_pdf)
            doc_text = native.raw_text
    except Exception:
        doc_text = None

    prompt_override = None
    setting = db.get(AppSetting, "ai_system_prompt")
    if setting and isinstance(setting.value, dict) and str(setting.value.get("text") or "").strip():
        prompt_override = str(setting.value["text"]).strip()

    gemini_res = extract_with_gemini_sync(
        pdf_bytes,
        document_text=doc_text,
        source_filename=uploaded.original_filename if uploaded else None,
        db_companies=db_companies,
        db_benefit_concepts=db_benefit_concepts,
        db_packs=get_db_packs(db),
        correction_memory=get_correction_memory(db, None),
        prompt_override=prompt_override,
    )
    if not gemini_res:
        keys_pool = get_key_pool()
        if not keys_pool.get_all_keys():
            raise AppError("No GEMINI_API_KEY set in .env. Add your free Google AI Studio key to enable AI extraction.", 400)
        raise AppError("Gemini AI extraction attempt failed or returned empty result. Check your API key or network.", 502)

    # Apply extracted fields to draft
    fields = dict(draft.fields or {})
    for key, val in gemini_res.items():
        if key in {"detected_benefits", "detected_package_name", "roadtax"} or val is None:
            continue
        clean_val = str(val).strip()
        if clean_val:
            fields[key] = {"value": clean_val, "status": "ready", "message": ""}

    # Classify customer entity (Private Individual vs Company) and vehicle type
    from app.extraction.entity_classifier import classify_client_entity
    cust_name = fields.get("customer_name", {}).get("value")
    doc_no = fields.get("ic_or_brn", {}).get("value")
    ai_type = fields.get("client_type", {}).get("value")
    curr_vtype = fields.get("vehicle_type", {}).get("value") or "Car"
    car_model_val = fields.get("car_model", {}).get("value")

    entity_type, resolved_vtype = classify_client_entity(
        customer_name=cust_name,
        ic_or_brn=doc_no,
        ai_client_type=ai_type,
        current_vehicle_type=curr_vtype,
        car_model=car_model_val,
    )
    fields["client_type"] = {"value": entity_type, "status": "ready", "message": ""}
    fields["vehicle_type"] = {"value": resolved_vtype, "status": "ready", "message": ""}

    # Sum detected optional extras cost to net out from total_amount
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

    # Fallback to total_optional_cover_amount if individual items did not specify premium_cost
    if extras_cost == 0 and gemini_res.get("total_optional_cover_amount"):
        clean_tot_opt = re.sub(r"[^\d.]", "", str(gemini_res["total_optional_cover_amount"]))
        if clean_tot_opt:
            try:
                extras_cost = Decimal(clean_tot_opt)
            except Exception:
                pass

    t_val = gemini_res.get("total_amount")
    if t_val:
        clean_tot = re.sub(r"[^\d.]", "", str(t_val))
        if clean_tot:
            try:
                tot_num = Decimal(clean_tot)
                fields["total_amount"] = {"value": f"{tot_num:.2f}", "status": "ready", "message": ""}
                # Insurance Premium = Final Price (Total Contribution) - Extras
                if extras_cost > 0:
                    base_p = tot_num - extras_cost
                    if base_p > 0:
                        fields["premium"] = {"value": f"{base_p:.2f}", "status": "ready", "message": ""}
                    else:
                        fields["premium"] = {"value": f"{tot_num:.2f}", "status": "ready", "message": ""}
                else:
                    fields["premium"] = {"value": f"{tot_num:.2f}", "status": "ready", "message": ""}
            except Exception:
                pass

    # Road tax: strictly calculate dynamically
    cc_val = fields.get("engine_cc", {}).get("value")
    rt_calc = 0.0
    if cc_val:
        try:
            from app.services.road_tax_service import calculate_road_tax
            clean_cc = int(re.sub(r"[^\d]", "", str(cc_val)))
            rt_calc = calculate_road_tax(
                cc=clean_cc,
                vehicle_type=resolved_vtype,
                owner_type=entity_type,
                jurisdiction="West Malaysia",
                db=db,
            )
        except Exception:
            rt_calc = 0.0
    fields["roadtax"] = {"value": f"{rt_calc:.2f}" if rt_calc > 0 else "", "status": "ready", "message": ""}

    if "service_fee" not in gemini_res or not gemini_res.get("service_fee"):
        fields["service_fee"] = {"value": "", "status": "ready", "message": ""}

    # Period
    start_d = str(gemini_res.get("cover_start_date") or "").strip()
    end_d = str(gemini_res.get("cover_end_date") or "").strip()
    if start_d and end_d:
        fields["cover_period"] = {"value": f"{start_d} to {end_d}", "status": "ready", "message": ""}

    draft.fields = fields

    from app.services.catalog_review_service import auto_apply_extracted_benefits, initialize_catalog_review
    from app.models.tables import ExtractionBenefitLine, DraftSourceLineDecision, new_id

    # Sync company if detected — alias-aware so Gemini variants like
    # "AmGeneral" / "AmGen" / "AM General Insurance Berhad" map to AmAssurance.
    comp_name = str(gemini_res.get("insurance_company") or "").strip()
    resolved = resolve_company(comp_name, db_companies)
    if resolved["status"] == "matched":
        company = next((c for c in db_companies if c["company_id"] == resolved["company_id"]), None)
        if company:
            draft.company_id = company["company_id"]
            draft.fields["insurance_company"] = {"value": company["name"], "status": "ready", "message": ""}
            session.detected_company = company["name"]

    # Process extraction benefit lines & candidate mappings
    extraction = db.scalar(select(ExtractionRecord).where(ExtractionRecord.uploaded_file_id == draft.uploaded_file_id))
    if extraction:
        candidates = dict(extraction.candidates or {})
        if gemini_res.get("detected_packs"):
            candidates["detected_packs"] = gemini_res["detected_packs"]
        extraction.candidates = candidates

        gemini_benefits = gemini_res.get("detected_benefits") or []
        for b_item in gemini_benefits:
            if isinstance(b_item, dict):
                b_label = str(b_item.get("label") or "").strip()
                b_val = str(b_item.get("value") or "").strip()
                b_key = str(b_item.get("concept_key") or "").strip()
                cov_limit = str(b_item.get("coverage_limit") or "").strip()
                cost = str(b_item.get("premium_cost") or "").strip()
                is_optional = bool(b_item.get("is_optional_cover", False))
                b_raw = str(b_item.get("raw_text") or f"{b_label}: {b_val}").strip()
            elif isinstance(b_item, str):
                b_label = b_item.strip()
                b_val = ""
                b_key = ""
                cov_limit = ""
                cost = ""
                is_optional = False
                b_raw = b_label
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
                    typed_val = {
                        "type": "text",
                        "value": limit_val,
                        "display_text": limit_val,
                    }

            line = ExtractionBenefitLine(
                id=new_id(),
                extraction_record_id=extraction.id,
                line_id=f"gemini_re_{new_id()[:8]}",
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

    initialize_catalog_review(db, draft)
    auto_apply_extracted_benefits(db, draft)
    db.commit()

    pool = get_key_pool()
    stats = pool.get_quota_stats()
    return {
        "success": True,
        "message": f"Gemini AI extracted {len(fields)} fields successfully.",
        "quota": {
            "model": getattr(settings, "gemini_model", "gemini-3.5-flash") or "gemini-3.5-flash",
            "keys_count": stats["keys_count"],
            "rpm_limit": stats["rpm_limit"],
            "rpm_used": stats["rpm_used"],
            "rpm_remaining": stats["rpm_remaining"],
            "rpd_limit": stats["rpd_limit"],
            "rpd_used": stats["rpd_used"],
            "rpd_remaining": stats["rpd_remaining"],
            "percent_rpd_remaining": stats["percent_rpd_remaining"],
            "rpm_per_key": 15,
            "rpd_per_key": 1500,
            "total_rpd": stats["rpd_limit"],
            "active": True,
        },
        "gemini_result": gemini_res,
    }



@router.post("/sessions/{session_id}/rescan")
def session_rescan_endpoint(
    session_id: str,
    payload: SessionRescanRequest | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> dict:
    from app.services.session_rescan_service import rescan_session

    mode = payload.mode if payload else "in_place"
    engine = payload.engine if payload else "auto"
    return rescan_session(
        db,
        session_id,
        user,
        settings,
        mode=mode,
        engine=engine,
    )



@router.patch("/drafts/{draft_id}/workspace")
def draft_workspace_patch(
    draft_id: str,
    payload: WorkspacePatchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {
        "workspace": apply_workspace_patch(
            db,
            user,
            draft_id,
            base_revision=payload.base_revision,
            operations=payload.operations,
        )
    }



@router.post("/sessions/{session_id}/versions", status_code=status.HTTP_202_ACCEPTED)
def session_generate_version(
    session_id: str,
    payload: VersionGenerationRequest,
    response: FastAPIResponse,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    from app.models.tables import new_id
    resolved_key = idempotency_key or new_id()
    result = request_version_generation(
        db,
        user,
        session_id,
        draft_revision=payload.draft_revision,
        idempotency_key=resolved_key,
    )
    version = result.get("version")
    if version is not None:
        response.status_code = status.HTTP_200_OK
        return {
            "created": False,
            "version": {
                "id": version.id,
                "version_number": version.version_number,
                "draft_revision": version.draft_revision,
            },
        }
    response.status_code = status.HTTP_202_ACCEPTED
    return {"created": bool(result["created"]), "job": serialize_job(result["job"])}



@router.post("/sessions/{session_id}/preview-render")
def session_preview_render(
    session_id: str,
    payload: VersionGenerationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    snapshot = request_preview_render(
        db,
        user,
        session_id,
        draft_revision=payload.draft_revision,
    )
    return {
        "preview_id": snapshot.id,
        "context_hash": snapshot.context_hash,
        "preview_url": f"/previews/{snapshot.id}/html",
    }



@router.get("/extractions/{uploaded_file_id}")
def extraction_detail(uploaded_file_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    uploaded = db.scalar(select(UploadedFile).where(UploadedFile.id == uploaded_file_id).options(selectinload(UploadedFile.extraction_record)))
    if not uploaded or not uploaded.extraction_record:
        raise AppError("Extraction details not found.", 404)
    record = uploaded.extraction_record
    return {
        "extraction": {
            "uploaded_file_id": uploaded.id,
            "method_summary": record.method_summary,
            "page_text": record.page_text,
            "words": record.words,
            "blocks": record.blocks,
            "tables": record.tables,
            "images": record.images,
            "regions": record.regions,
            "candidates": record.candidates,
            "warnings": record.warnings,
            "reading_quality": record.reading_quality,
        }
    }



@router.get("/uploaded-files/{uploaded_file_id}/content")
def uploaded_file_content(
    uploaded_file_id: str,
    download: bool = Query(default=False),
    range_header: str | None = Header(default=None, alias="Range"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> Response:
    uploaded = db.get(UploadedFile, uploaded_file_id)
    if not uploaded or not can_view_owner_record(db, user, uploaded.owner_id):
        raise AppError("File not found.", 404)
    return _pdf_response(load_pdf_bytes(uploaded, settings), uploaded.original_filename, range_header, download)



@router.get("/generated-versions/{version_id}/content")
def generated_version_content(
    version_id: str,
    download: bool = Query(default=False),
    range_header: str | None = Header(default=None, alias="Range"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> Response:
    version = db.scalar(select(GeneratedPdfVersion).where(GeneratedPdfVersion.id == version_id).options(selectinload(GeneratedPdfVersion.draft)))
    if not version or not version.draft or not can_view_owner_record(db, user, version.draft.owner_id):
        raise AppError("File not found.", 404)
    return _pdf_response(load_pdf_bytes(version, settings), version.filename, range_header, download)



@router.get("/versions/{version_id}/pdf")
def version_pdf(
    version_id: str,
    download: bool = Query(default=True),
    range_header: str | None = Header(default=None, alias="Range"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> Response:
    version = db.scalar(
        select(GeneratedPdfVersion)
        .where(GeneratedPdfVersion.id == version_id)
        .options(selectinload(GeneratedPdfVersion.draft))
    )
    if not version or not version.draft or not can_view_owner_record(db, user, version.draft.owner_id):
        raise AppError("File not found.", 404)
    return _pdf_response(load_pdf_bytes(version, settings), version.filename, range_header, download)



@router.get("/sessions/{session_id}/ownership-conflict")
def get_session_ownership_conflict(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    from app.services.vehicle_tracking_service import check_vehicle_ownership_conflict
    return check_vehicle_ownership_conflict(db=db, session_id=session_id)



@router.post("/sessions/{session_id}/resolve-ownership")
def post_resolve_session_ownership(
    session_id: str,
    payload: VehicleOwnershipResolutionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    from app.services.vehicle_tracking_service import resolve_vehicle_ownership
    return resolve_vehicle_ownership(
        db=db,
        session_id=session_id,
        resolution_type=payload.resolution_type,
        user_id=user.id,
        notes=payload.notes,
    )

