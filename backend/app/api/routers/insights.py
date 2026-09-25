"""Insights API router."""

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



logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/client-records")
def client_records_list(
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    company: str | None = None,
    state: str = "active",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    result = list_records_page(
        db, search=search, date_from=date_from, date_to=date_to, sort_by=sort_by,
        sort_dir=sort_dir, company=company, state=state, page=page, page_size=page_size,
    )
    return {
        "records": [serialize_record(item) for item in result["items"]],
        "page": result["page"], "page_size": result["page_size"], "total": result["total"],
        "companies": result["companies"],
    }



@router.get("/client-records/saved-views")
def client_record_saved_views(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    return {"views": [serialize_saved_view(item) for item in list_saved_views(db, user)]}



@router.post("/client-records/saved-views")
def client_record_saved_view_save(payload: RecordSavedViewRequest, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    return {"view": serialize_saved_view(save_record_view(db, user, payload.model_dump()))}



@router.delete("/client-records/saved-views/{view_id}")
def client_record_saved_view_delete(view_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    delete_record_view(db, user, view_id)
    return {"deleted": True}



@router.get("/client-records/export")
def client_records_export(
    search: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    from fastapi.responses import Response as FastAPIResponse
    csv_data = export_csv_bytes(db, search=search)
    return FastAPIResponse(csv_data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=client_records.csv"})



@router.get("/client-records/{record_id}")
def client_record_detail(record_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    return {"record": serialize_record(get_record(db, record_id))}



@router.patch("/client-records/{record_id}")
def client_record_update(record_id: str, payload: ClientRecordUpdateRequest, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    record = update_record(db, record_id, payload.model_dump(exclude_none=True))
    return {"record": serialize_record(record)}



@router.delete("/client-records/{record_id}")
def client_record_delete(record_id: str, db: Session = Depends(get_db), settings: Settings = Depends(settings_dep), user: User = Depends(current_user)) -> dict:
    from app.services.trash_service import delete_client_record
    delete_client_record(db, settings, user, record_id)
    return {"deleted": True}



@router.post("/client-records/bulk-delete")
def client_records_bulk_delete(payload: BulkClientRecordDeleteRequest, db: Session = Depends(get_db), settings: Settings = Depends(settings_dep), user: User = Depends(current_user)) -> dict:
    from app.services.trash_service import delete_client_record
    deleted: list[str] = []
    failed: list[dict] = []
    for record_id in payload.record_ids:
        try:
            delete_client_record(db, settings, user, record_id)
            deleted.append(record_id)
        except AppError as exc:
            failed.append({"id": record_id, "message": str(exc)})
    return {"deleted": deleted, "failed": failed}



@router.post("/client-records/bulk-action")
def client_records_bulk_action(payload: RecordBulkActionRequest, db: Session = Depends(get_db), settings: Settings = Depends(settings_dep), user: User = Depends(current_user)) -> dict:
    record_ids = records_matching_ids(db, payload.filters) if payload.all_matching else list(dict.fromkeys(payload.record_ids))
    if not record_ids:
        raise AppError("Choose at least one matching record.", 422)
    if payload.action in {"archive", "unarchive"}:
        changed = set_records_archived(db, user, record_ids, archived=payload.action == "archive")
        return {"changed": changed, "failed": []}
    from app.services.trash_service import delete_client_record
    changed: list[str] = []
    failed: list[dict] = []
    for record_id in record_ids:
        try:
            delete_client_record(db, settings, user, record_id)
            changed.append(record_id)
        except AppError as exc:
            failed.append({"id": record_id, "message": str(exc)})
    return {"changed": changed, "failed": failed}



@router.delete("/records/{uploaded_file_id}")
def delete_record(uploaded_file_id: str, db: Session = Depends(get_db), settings: Settings = Depends(settings_dep), user: User = Depends(current_user)) -> dict:
    move_to_trash(db, settings, user, uploaded_file_id)
    return {"status": "Deleted"}



@router.post("/records/bulk-delete")
def delete_records_bulk(payload: BulkUploadedFileDeleteRequest, db: Session = Depends(get_db), settings: Settings = Depends(settings_dep), user: User = Depends(current_user)) -> dict:
    deleted: list[str] = []
    failed: list[dict] = []
    for uploaded_file_id in payload.uploaded_file_ids:
        try:
            move_to_trash(db, settings, user, uploaded_file_id)
            deleted.append(uploaded_file_id)
        except AppError as exc:
            failed.append({"id": uploaded_file_id, "message": str(exc)})
    return {"deleted": deleted, "failed": failed}



@router.get("/insights/calendar")
def insights_calendar(
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    search: str | None = Query(None),
    status: str | None = Query(None),
    sent_only: bool = Query(False),
    vehicle_no: str | None = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return get_calendar_activities(
        db=db,
        date_from=date_from,
        date_to=date_to,
        search=search,
        status=status,
        sent_only=sent_only,
        vehicle_no=vehicle_no,
        limit=limit,
    )



@router.post("/insights/sessions/{session_id}/activity")
def create_session_activity(
    session_id: str,
    payload: QuotationActivityCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    session = get_session(db, session_id)
    if getattr(session, "is_test", False):
        return {
            "id": "test",
            "session_id": session.id,
            "action_type": payload.action_type,
            "sent_to_client": payload.sent_to_client,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    activity = log_quotation_activity(
        db=db,
        session_id=session.id,
        action_type=payload.action_type,
        user_id=user.id,
        sent_to_client=payload.sent_to_client,
        summary=payload.summary or "",
        addons_snapshot=payload.addons_snapshot,
        version_number=payload.version_number,
        status=payload.status or session.quotation_status or "pending",
        won_premium=payload.won_premium,
        miss_reason=payload.miss_reason,
        notes=payload.notes,
    )
    db.commit()
    if not activity:
        return {
            "id": "test",
            "session_id": session.id,
            "action_type": payload.action_type,
            "sent_to_client": payload.sent_to_client,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    return {
        "id": activity.id,
        "session_id": activity.session_id,
        "action_type": activity.action_type,
        "sent_to_client": activity.sent_to_client,
        "timestamp": activity.timestamp.isoformat() if activity.timestamp else None,
    }



@router.post("/insights/sessions/{session_id}/status")
def update_session_status(
    session_id: str,
    payload: QuotationStatusUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    get_session(db, session_id)
    result = update_quotation_status(
        db=db,
        session_id=session_id,
        status=payload.status,
        miss_reason=payload.miss_reason,
        won_premium=payload.won_premium,
        notes=payload.notes,
        user_id=user.id,
        coverage_start_date=payload.coverage_start_date,
        coverage_end_date=payload.coverage_end_date,
    )
    db.commit()
    return result



@router.get("/insights/analytics")
def insights_analytics(
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return get_insights_analytics(db=db, date_from=date_from, date_to=date_to)



@router.get("/insights/vehicles/{vehicle_no}/history")
def vehicle_history(
    vehicle_no: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return get_vehicle_history(db=db, vehicle_no=vehicle_no)



@router.get("/insights/renewals")
def upcoming_renewals(
    days_ahead: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    from app.services.vehicle_tracking_service import get_upcoming_renewals
    renewals = get_upcoming_renewals(db=db, days_ahead=days_ahead)
    return {"renewals": renewals, "total": len(renewals)}



@router.post("/insights/backfill")
def run_insights_backfill(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    res = backfill_existing_sessions(db)
    db.commit()
    return res



@router.get("/insights/backfill/preview")
def preview_insights_backfill(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return preview_backfill_sessions(db=db)



@router.post("/insights/backfill/confirm")
def confirm_insights_backfill(
    payload: BackfillConfirmRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    res = backfill_existing_sessions(
        db=db,
        session_ids=payload.session_ids if payload.session_ids else None,
        manual_overrides=payload.manual_overrides,
    )
    db.commit()
    return res



@router.get("/insights/clients")
def insights_clients(
    search: str | None = Query(None),
    status: str | None = Query(None),
    client_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return get_client_dossiers(
        db=db,
        search=search,
        status=status,
        client_type=client_type,
        page=page,
        page_size=page_size,
    )

