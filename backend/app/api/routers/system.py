"""System API router."""

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


@router.get("/health")
def health(settings: Settings = Depends(settings_dep)) -> dict:
    db_host = "Unknown"
    db_url = getattr(settings, "database_url", None)
    if db_url:
        parts = db_url.split('@') if isinstance(db_url, str) else str(db_url).split('@')
        if len(parts) > 1:
            db_host = parts[-1].split('/')[0]
            
    return {
        "status": "Ready", 
        "app": getattr(settings, "app_name", "Risklocker Quotation Converter"),
        "env": getattr(settings, "app_env", "local"),
        "supabase_url": getattr(settings, "supabase_url", ""),
        "database_host": db_host,
        "storage_bucket": getattr(settings, "supabase_storage_bucket", ""),
    }



@router.get("/health/ready")
def readiness(db: Session = Depends(get_db)) -> JSONResponse:
    worker = worker_readiness(db)
    ready = bool(worker["ready"])
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "Ready" if ready else "Unavailable", "checks": {"worker": worker}},
    )



@router.get("/system/checks")
def system_checks(db: Session = Depends(get_db), settings: Settings = Depends(settings_dep), user: User = Depends(current_user)) -> dict:
    if user.role not in {Role.SUPER_ADMIN.value, Role.ADMIN.value, Role.DEV.value}:
        raise AppError("You do not have permission to view system checks.", 403)
    return {"checks": get_system_checks(settings, db)}



@router.get("/notifications")
def notifications_list(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    return {"notifications": [serialize_notification(n) for n in get_notifications(db, user.id)]}



@router.get("/notifications/unread-count")
def notifications_unread_count(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    return {"unread_count": get_unread_count(db, user.id)}



@router.patch("/notifications/{notification_id}/read")
def notification_mark_read(notification_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    notification = mark_read(db, notification_id, user.id)
    return {"notification": serialize_notification(notification)}



@router.patch("/notifications/read")
def notification_mark_all_read(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    return {"updated": mark_all_read(db, user.id)}



@router.get("/trash")
def trash(db: Session = Depends(get_db), settings: Settings = Depends(settings_dep), user: User = Depends(current_user)) -> dict:
    from app.services.trash_service import list_trash_categorized
    return list_trash_categorized(db, user, settings.trash_retention_days)



@router.post("/trash/{uploaded_file_id}/restore")
def trash_restore(uploaded_file_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    restore_from_trash(db, user, uploaded_file_id)
    return {"status": "Ready"}



@router.post("/trash/templates/{template_id}/restore")
def trash_template_restore(template_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    from app.services.trash_service import restore_template
    restore_template(db, user, template_id)
    return {"status": "Ready"}



@router.post("/trash/our-specials/{special_id}/restore")
def trash_special_restore(special_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    from app.services.trash_service import restore_special
    restore_special(db, user, special_id)
    return {"status": "Ready"}



@router.post("/trash/our-special-variants/{variant_id}/restore")
def trash_variant_restore(variant_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    from app.services.trash_service import restore_special_variant
    restore_special_variant(db, user, variant_id)
    return {"status": "Ready"}



@router.post("/trash/client-records/{record_id}/restore")
def trash_record_restore(record_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    from app.services.trash_service import restore_client_record
    restore_client_record(db, user, record_id)
    return {"status": "Ready"}



@router.post("/trash/template-assets/{asset_id}/restore")
def trash_asset_restore(asset_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    from app.services.trash_service import restore_template_asset
    restore_template_asset(db, user, asset_id)
    return {"status": "Ready"}



@router.post("/trash/purge-expired")
def trash_purge(user: User = Depends(current_user)) -> dict:
    # RL-DISABLED timed trash purge — disabled 2026-08-14; compatibility route.
    raise AppError("Timed trash purge is disabled. Delete selected items or explicitly empty Trash.", 410)



@router.post("/trash/empty")
def trash_empty(db: Session = Depends(get_db), settings: Settings = Depends(settings_dep), user: User = Depends(current_user)) -> dict:
    from app.services.trash_service import empty_all_trash
    return {"emptied": empty_all_trash(db, user, SupabaseStorage(settings))}



@router.post("/trash/delete-forever")
def trash_delete_forever(payload: TrashDeleteForeverRequest, db: Session = Depends(get_db), settings: Settings = Depends(settings_dep), user: User = Depends(current_user)) -> dict:
    from app.services import trash_service

    handlers = {
        "session": lambda: trash_service.permanent_delete_session(db, user, payload.entity_id, SupabaseStorage(settings)),
        "template": lambda: trash_service.permanent_delete_template(db, user, payload.entity_id),
        "our_special": lambda: trash_service.permanent_delete_special(db, user, payload.entity_id),
        "our_special_variant": lambda: trash_service.permanent_delete_special_variant(db, user, payload.entity_id),
        "client_record": lambda: trash_service.permanent_delete_client_record(db, user, payload.entity_id),
        "template_asset": lambda: trash_service.permanent_delete_template_asset(db, user, payload.entity_id),
    }
    handler = handlers.get(payload.entity_type)
    if not handler:
        raise AppError("Unknown trash item type.", 400)
    handler()
    return {"deleted": True}



@router.post("/trash/bulk-delete-forever")
def trash_bulk_delete_forever(payload: BulkDeleteRequest, db: Session = Depends(get_db), settings: Settings = Depends(settings_dep), user: User = Depends(current_user)) -> dict:
    from app.services import trash_service
    # Trash records are listed in trash UI as trash.id
    for tid in payload.item_ids:
        try:
            trash_service.permanent_delete_trash_record(db, user, tid, SupabaseStorage(settings))
        except Exception:
            pass
    return {"deleted": True}



@router.get("/admin/companies")
def admin_companies(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    return {
        "companies": [
            {
                "id": item.id,
                "name": item.name,
                "category": item.category,
                "source_template_category": item.source_template_category,
                "detection_phrases": item.detection_phrases,
                "status": item.status,
            }
            for item in db.scalars(select(InsuranceCompany)).all()
        ]
    }



@router.post("/admin/companies")
def admin_company_save(payload: CompanySaveRequest, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    company = upsert_company(db, user, payload.model_dump(exclude_none=True))
    return {"company": {"id": company.id, "name": company.name, "category": company.category, "status": company.status, "detection_phrases": company.detection_phrases}}



@router.delete("/admin/companies/{company_id}")
def admin_company_delete(company_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    from app.services.admin_service import delete_company
    delete_company(db, user, company_id)
    return {"deleted": True}



@router.post("/admin/our-special-variants")
def admin_our_special_variant_save(payload: OurSpecialVariantSaveRequest, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    variant = upsert_variant(db, user, payload.model_dump(exclude_none=True))
    return {"variant": {"id": variant.id, "special_id": variant.special_id, "label": variant.label, "secondary_label": variant.secondary_label, "value_text": variant.value_text, "icon_asset_id": variant.icon_asset_id, "shape": variant.shape, "bg_color": variant.bg_color, "text_color": variant.text_color, "border_width": variant.border_width, "border_color": variant.border_color, "shadow": variant.shadow, "status": variant.status}}



@router.delete("/admin/our-special-variants/{variant_id}")
def admin_our_special_variant_delete(variant_id: str, db: Session = Depends(get_db), settings: Settings = Depends(settings_dep), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    delete_special_variant(db, settings, user, variant_id)
    return {"deleted": True}



@router.post("/admin/our-special-variants/{variant_id}/move")
def admin_our_special_variant_move(variant_id: str, payload: VariantMoveRequest, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    variant = move_variant(db, user, variant_id, payload.special_id)
    return {"variant": {"id": variant.id, "special_id": variant.special_id, "label": variant.label}}



@router.get("/admin/dictionaries")
def admin_dictionaries(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    return {
        "field_aliases": [{"id": item.id, "field_name": item.field_name, "aliases": item.aliases} for item in db.scalars(select(FieldAlias)).all()],
        "vehicle_brands": [{"id": item.id, "name": item.name, "aliases": item.aliases} for item in db.scalars(select(VehicleBrand)).all()],
        "vehicle_models": [{"id": item.id, "brand_id": item.brand_id, "name": item.name, "aliases": item.aliases} for item in db.scalars(select(VehicleModel)).all()],
    }



@router.post("/admin/dictionaries/field-aliases")
def admin_field_alias_save(payload: FieldAliasSaveRequest, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    item = upsert_field_alias(db, user, payload.model_dump(exclude_none=True))
    return {"field_alias": {"id": item.id, "field_name": item.field_name, "aliases": item.aliases}}



@router.delete("/admin/dictionaries/field-aliases/{field_name}")
def admin_field_alias_delete(field_name: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    delete_field_alias(db, user, field_name)
    return {"deleted": True}



@router.get("/admin/dictionaries/field-aliases/export")
def admin_field_alias_export(db: Session = Depends(get_db), user: User = Depends(current_user)) -> Response:
    import csv, io
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    items = db.scalars(select(FieldAlias)).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["accepted_variant", "canonical_field"])
    for item in items:
        for alias in item.aliases:
            writer.writerow([alias, item.field_name])
    data = buf.getvalue().encode("utf-8-sig")
    return Response(data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=field_aliases.csv"})



@router.post("/admin/dictionaries/field-aliases/import")
async def admin_field_alias_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    import csv, io
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    data = await file.read()
    content = data.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    created = 0
    updated = 0
    errors: list[str] = []
    for row in reader:
        variant = (row.get("accepted_variant") or "").strip()
        field_name = (row.get("canonical_field") or "").strip()
        if not variant or not field_name:
            errors.append(f"Missing values in row: {row}")
            continue
        try:
            existing = db.scalar(select(FieldAlias).where(FieldAlias.field_name == field_name))
            if existing:
                if variant not in existing.aliases:
                    existing.aliases = [*existing.aliases, variant]
                    updated += 1
            else:
                db.add(FieldAlias(field_name=field_name, aliases=[variant]))
                created += 1
        except (SQLAlchemyError, ValueError, TypeError) as exc:
            logger.warning("Field-alias import row failed for %s/%s: %s", field_name, variant, exc)
            errors.append(f"{field_name}/{variant}: {exc}")
    db.commit()
    return {"created": created, "updated": updated, "errors": errors}



@router.post("/admin/dictionaries/vehicle-brands")
def admin_vehicle_brand_save(payload: VehicleBrandSaveRequest, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    item = upsert_vehicle_brand(db, user, payload.model_dump(exclude_none=True))
    return {"vehicle_brand": {"id": item.id, "name": item.name, "aliases": item.aliases}}



@router.post("/admin/dictionaries/vehicle-models")
def admin_vehicle_model_save(payload: VehicleModelSaveRequest, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    item = upsert_vehicle_model(db, user, payload.model_dump(exclude_none=True))
    return {"vehicle_model": {"id": item.id, "name": item.name, "aliases": item.aliases}}



@router.delete("/admin/dictionaries/vehicle-brands/{brand_id}")
def admin_vehicle_brand_delete(brand_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    delete_vehicle_brand(db, user, brand_id)
    return {"deleted": True}



@router.delete("/admin/dictionaries/vehicle-models/{model_id}")
def admin_vehicle_model_delete(model_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    delete_vehicle_model(db, user, model_id)
    return {"deleted": True}



@router.get("/admin/dictionaries/vehicles/export")
def admin_vehicles_export(db: Session = Depends(get_db), user: User = Depends(current_user)) -> Response:
    import csv, io
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["type", "name", "brand", "aliases"])
    for b in db.scalars(select(VehicleBrand)).all():
        writer.writerow(["brand", b.name, "", ", ".join(b.aliases)])
    for m in db.scalars(select(VehicleModel)).all():
        brand = db.get(VehicleBrand, m.brand_id) if m.brand_id else None
        brand_name = brand.name if brand else ""
        writer.writerow(["model", m.name, brand_name, ", ".join(m.aliases)])
    return Response(buf.getvalue().encode("utf-8-sig"), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=vehicles.csv"})



@router.post("/admin/extraction-settings")
def admin_extraction_settings_save(payload: ExtractionSettingsRequest, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    setting = save_strategy_settings(db, user, payload.model_dump())
    return {"setting": {"key": setting.key, "value": setting.value}}



@router.get("/admin/road-tax-rules")
def road_tax_rules_list(vehicle_type: str | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    return {"rules": [serialize_rule(r) for r in list_rules(db, vehicle_type=vehicle_type)]}



@router.post("/admin/road-tax-rules")
def road_tax_rule_save(payload: RoadTaxRuleSaveRequest, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    rule = upsert_road_tax_rule(db, payload.model_dump(exclude_none=True))
    return {"rule": serialize_rule(rule)}



@router.delete("/admin/road-tax-rules/{rule_id}")
def road_tax_rule_delete(rule_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    delete_road_tax_rule(db, rule_id)
    return {"deleted": True}



@router.get("/admin/road-tax-rules/export")
def road_tax_rules_export(db: Session = Depends(get_db), user: User = Depends(current_user)) -> Response:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    return Response(
        export_road_tax_csv(list_rules(db)),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="road_tax_rules.csv"'},
    )



@router.post("/admin/road-tax-rules/import")
async def road_tax_rules_import(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    data = await file.read()
    rows = parse_tabular(file.filename or "import.csv", data)
    return import_road_tax_rules(db, rows)



@router.post("/admin/road-tax-rules/seed-standard")
def road_tax_rules_seed_standard(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    result = seed_standard_road_tax_rules(db)
    return {"result": result}



@router.post("/admin/road-tax-rules/calculate")
def road_tax_calculate_preview(
    payload: RoadTaxCalculateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    breakdown = calculate_breakdown(
        cc=payload.cc,
        vehicle_type=payload.vehicle_type,
        owner_type=payload.owner_type,
        jurisdiction=payload.jurisdiction,
        db=db,
    )
    return {"breakdown": breakdown}



@router.post("/admin/dictionaries/vehicles/import")
async def vehicles_import(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    data = await file.read()
    sheets = parse_vehicles_workbook(file.filename or "vehicles.xlsx", data)
    return import_vehicles_workbook(db, user, sheets)



@router.get("/admin/settings/runner-fee")
def runner_fee_get(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    return {"amount": get_runner_fee_default(db)}



@router.post("/admin/settings/runner-fee")
def runner_fee_set(payload: dict, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    amount = set_runner_fee_default(db, user, float(payload.get("amount", 20.0)))
    return {"amount": amount}



@router.get("/admin/settings/upload-limits")
def upload_limits_get(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    return {
        "max_bulk_upload_files": get_bulk_upload_limit(db),
        "min_allowed": 3,
    }



@router.post("/admin/settings/upload-limits")
def upload_limits_set(payload: dict, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    raw_val = payload.get("max_bulk_upload_files")
    if raw_val is None:
        raise AppError("max_bulk_upload_files is required.", 400)
    try:
        limit = int(raw_val)
    except (ValueError, TypeError):
        raise AppError("max_bulk_upload_files must be an integer.", 400)
    saved = set_bulk_upload_limit(db, user, limit)
    return {"max_bulk_upload_files": saved, "min_allowed": 3}



@router.get("/settings/limits")
def settings_limits(
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> dict:
    from app.extraction.gemini_extractor import get_key_pool
    pool = get_key_pool()
    stats = pool.get_quota_stats()
    count = stats["keys_count"]
    bulk_limit = get_bulk_upload_limit(db)
    return {
        "max_upload_files": 1,
        "max_bulk_upload_files": bulk_limit,
        "max_upload_bytes": settings.max_upload_bytes,
        "max_source_pdf_bytes": settings.max_source_pdf_bytes,
        "gemini": {
            "active": bool(count > 0),
            "model": getattr(settings, "gemini_model", "gemini-3.5-flash") or "gemini-3.5-flash",
            "key_count": count,
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
            "message": f"Connected ({count} key{'s' if count > 1 else ''} in pool, {stats['rpd_remaining']:,} / {stats['rpd_limit']:,} RPD remaining today)" if count else "No GEMINI_API_KEY set in .env",
        },
    }



@router.get("/admin/storage")
def admin_storage_status(
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN)
    storage_ready, storage_message = SupabaseStorage(settings).check()
    source_bytes = db.scalar(
        select(func.coalesce(func.sum(UploadedFile.size_bytes), 0)).where(
            UploadedFile.storage_provider == "supabase",
            UploadedFile.storage_status.in_([StorageStatus.AVAILABLE.value, StorageStatus.ARCHIVE_PENDING.value, StorageStatus.ARCHIVE_FAILED.value]),
        )
    )
    connections = list(db.scalars(select(StorageConnection).order_by(StorageConnection.created_at.desc())).all())
    return {
        "supabase": {
            "status": "Ready" if storage_ready else "Needs Setup",
            "message": storage_message,
            "bucket": settings.supabase_storage_bucket,
            "retention_policy": "manual_reference_aware_deletion",
            "tracked_source_bytes": int(source_bytes or 0),
        },
        "microsoft": {
            "status": "Not Connected",
            "message": "SharePoint/OneDrive permanent archive is optional and can be connected later.",
            "connections": [
                {
                    "id": item.id,
                    "name": item.display_name,
                    "status": item.status,
                    "site_id": item.site_id,
                    "drive_id": item.drive_id,
                    "last_checked_at": item.last_checked_at.isoformat() if item.last_checked_at else None,
                }
                for item in connections
            ],
        },
    }



@router.post("/admin/storage/purge-expired")
def admin_storage_purge(
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN)
    # RL-DISABLED automatic PDF expiry — disabled 2026-08-14; compatibility route.
    raise AppError("PDF expiry is disabled. Use reference-aware deletion from Trash.", 410)



@router.post("/admin/storage/microsoft/connect")
def admin_storage_microsoft_connect(user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN)
    raise AppError("Microsoft 365 archive requires Entra application credentials before it can be connected.", 503)

