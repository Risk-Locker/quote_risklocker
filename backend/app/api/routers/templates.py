"""Templates API router."""

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

_ASSET_CACHE_DIR = Path(__file__).resolve().parents[4] / ".qc-tmp" / "asset-cache"
_asset_memory_cache: dict[str, bytes] = {}
_asset_cache_lock = Lock()


@router.get("/admin/template-groups")
def admin_template_groups(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF)
    return {"groups": list_template_groups(db)}



@router.post("/admin/template-groups")
def admin_template_group_save(payload: TemplateGroupSaveRequest, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    group = upsert_template_group(db, user, payload.model_dump(exclude_none=True))
    return {"group": {"id": group.id, "name": group.name, "company_id": group.company_id}}



@router.delete("/admin/template-groups/{group_id}")
def admin_template_group_delete(group_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    delete_template_group(db, user, group_id)
    return {"deleted": True}



@router.get("/business/assets")
def business_assets(
    search: str = Query(default="", max_length=200),
    kind: str | None = Query(default=None, max_length=40),
    category: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {
        "assets": list_business_assets(
            db,
            user,
            search=search,
            kind=kind,
            category=category,
            page=page,
            page_size=page_size,
        )
    }



@router.get("/business/assets/categories")
def business_asset_categories(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"categories": list_business_asset_categories(db, user)}



def _get_cached_asset_bytes(storage_path: str, settings: Settings) -> bytes:
    if storage_path in _asset_memory_cache:
        return _asset_memory_cache[storage_path]

    with _asset_cache_lock:
        if storage_path in _asset_memory_cache:
            return _asset_memory_cache[storage_path]

        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", storage_path) + ".bin"
        disk_path = _ASSET_CACHE_DIR / safe_name
        if disk_path.exists():
            try:
                data = disk_path.read_bytes()
                _asset_memory_cache[storage_path] = data
                return data
            except Exception:
                pass

        data = SupabaseStorage(settings).download_bytes(storage_path)

        try:
            _ASSET_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            disk_path.write_bytes(data)
        except Exception:
            pass

        _asset_memory_cache[storage_path] = data
        return data



@router.get("/business/assets/{asset_id}/content")
def business_asset_content(
    asset_id: str,
    request: Request,
    profile: str = Query(default="ui", pattern="^(ui|pdf|original)$"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> Response:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF)
    asset = db.get(BusinessAsset, asset_id)
    if asset is None or asset.status not in {"active", "unassigned"}:
        raise AppError("Asset not found.", 404)
    item = (asset.derivative_manifest or {}).get(profile) if profile != "original" else None
    storage_path = str((item or {}).get("storage_path") or asset.storage_path)
    content_type = str((item or {}).get("content_type") or asset.content_type)
    content_hash = str((item or {}).get("content_hash") or asset.content_hash)
    etag = f'"{content_hash}"'

    if_none_match = request.headers.get("if-none-match")
    if if_none_match and content_hash in if_none_match:
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers={
                "Cache-Control": "private, max-age=86400, immutable",
                "ETag": etag,
            },
        )

    try:
        data = _get_cached_asset_bytes(storage_path, settings)
    except StorageNotFound as exc:
        raise AppError("Asset not found in storage.", 404) from exc
    except StorageError as exc:
        raise AppError("Asset content is unavailable.", 503) from exc
    return Response(
        data,
        media_type=content_type,
        headers={
            "Cache-Control": "private, max-age=86400, immutable",
            "ETag": etag,
        },
    )



@router.post("/business/assets")
async def business_asset_upload(
    file: UploadFile = File(...),
    label: str = Form(...),
    kind: str = Form(...),
    category: str = Form(default="General"),
    on_duplicate: str = Form(default="rename"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> dict:
    data = await file.read()
    try:
        asset = upload_business_asset(
            db,
            settings,
            user,
            filename=file.filename or "asset",
            label=label,
            kind=kind,
            data=data,
            category=category,
            on_duplicate=on_duplicate,
        )
    except StorageError as exc:
        raise AppError("Asset storage is unavailable. Retry without changing the file.", 503) from exc
    return {"asset": asset}



@router.post("/business/assets/batch")
async def business_asset_batch_upload(
    files: list[UploadFile] = File(...),
    kind: str = Form(default="benefit_art"),
    category: str = Form(default="General"),
    on_duplicate: str = Form(default="rename"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> dict:
    file_payloads = []
    for f in files:
        data = await f.read()
        file_payloads.append((f.filename or "asset.png", Path(f.filename or "asset").stem, data))
    return batch_upload_business_assets(
        db,
        settings,
        user,
        files=file_payloads,
        kind=kind,
        category=category,
        on_duplicate=on_duplicate,
    )



@router.post("/business/assets/bulk-delete")
def business_asset_bulk_delete(
    payload: BusinessAssetBulkDeleteRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> dict:
    return bulk_delete_business_assets(db, settings, user, payload.asset_ids)



@router.post("/business/assets/bulk-move")
def business_asset_bulk_move(
    payload: BusinessAssetBulkMoveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return bulk_move_business_assets(db, user, payload.asset_ids, payload.target_category)



@router.patch("/business/assets/folders")
def business_asset_folder_rename(
    payload: BusinessAssetFolderRenameRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return rename_business_asset_folder(db, user, payload.old_name, payload.new_name)



@router.delete("/business/assets/folders")
def business_asset_folder_delete(
    payload: BusinessAssetFolderDeleteRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> dict:
    return delete_business_asset_folder(db, settings, user, payload.category, action=payload.action)



@router.patch("/business/assets/{asset_id}")
def business_asset_update(
    asset_id: str,
    payload: BusinessAssetUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {
        "asset": update_business_asset(
            db,
            user,
            asset_id,
            label=payload.label,
            category=payload.category,
            kind=payload.kind,
        )
    }



@router.post("/business/assets/{asset_id}/replace-file")
async def business_asset_replace_file(
    asset_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> dict:
    data = await file.read()
    try:
        updated = replace_business_asset_file(
            db,
            settings,
            user,
            asset_id,
            filename=file.filename or "replacement.png",
            data=data,
        )
    except StorageError as exc:
        raise AppError("Asset storage is unavailable. Retry without changing the file.", 503) from exc
    return {"asset": updated}



@router.delete("/business/assets/{asset_id}")
def business_asset_delete(
    asset_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> dict:
    return delete_business_asset(db, settings, user, asset_id)



def _preset_to_dict(p: BenefitCardPreset) -> dict[str, Any]:
    cfg = dict(p.config or {})
    return {
        "id": p.id,
        "name": p.name,
        "shortName": p.short_name,
        "short_name": p.short_name,
        "description": p.description,
        "is_default": p.is_default,
        "is_custom": p.is_custom,
        **cfg,
        "config": cfg,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }



@router.get("/business/benefit-card-presets")
def business_benefit_card_presets_list(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    presets = list_benefit_card_presets(db)
    return {"presets": [_preset_to_dict(p) for p in presets]}



@router.get("/business/benefit-card-presets/{preset_id}")
def business_benefit_card_preset_get(
    preset_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    preset = get_benefit_card_preset(db, preset_id)
    return {"preset": _preset_to_dict(preset)}



@router.put("/business/benefit-card-presets/{preset_id}")
def business_benefit_card_preset_update(
    preset_id: str,
    payload: BenefitCardPresetSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    preset = save_benefit_card_preset(db, preset_id, payload.model_dump(exclude_unset=True))
    return {"preset": _preset_to_dict(preset)}



@router.post("/business/benefit-card-presets")
def business_benefit_card_preset_create(
    payload: BenefitCardPresetCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    preset = create_custom_benefit_card_preset(db, payload.model_dump(exclude_unset=True))
    return {"preset": _preset_to_dict(preset)}



@router.post("/business/benefit-card-presets/{preset_id}/set-default")
def business_benefit_card_preset_set_default(
    preset_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    preset = set_default_benefit_card_preset(db, preset_id)
    return {"preset": _preset_to_dict(preset)}



@router.post("/business/benefit-card-presets/{preset_id}/reset")
def business_benefit_card_preset_reset(
    preset_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    preset = reset_benefit_card_preset(db, preset_id)
    return {"preset": _preset_to_dict(preset)}



@router.delete("/business/benefit-card-presets/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
def business_benefit_card_preset_delete(
    preset_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Response:
    delete_custom_benefit_card_preset(db, preset_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)



@router.get("/business/templates/published")
def business_published_templates(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    return {"templates": list_published_templates(db, user)}



@router.post("/business/templates/{template_id}/publish")
def business_publish_template(
    template_id: str,
    payload: TemplatePublishRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    revision = publish_template_revision(
        db,
        user,
        template_id,
        base_revision=payload.base_revision,
    )
    template = db.get(OutputTemplateConfig, template_id)
    if not template:
        raise AppError("Template not found.", 404)
    return {
        "template": serialize_template(template, db),
        "template_revision": serialize_template_revision(db, revision),
    }



@router.get("/admin/templates")
def admin_templates(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF)
    items = list(
        db.scalars(
            select(OutputTemplateConfig).where(OutputTemplateConfig.deleted_at.is_(None))
        ).all()
    )
    templates = serialize_templates_batch(db, items)
    templates.sort(key=lambda item: (not item.get("is_default", False), item.get("name", "").casefold()))
    return {"templates": templates}



@router.delete("/admin/templates/{template_id}")
def admin_template_delete(template_id: str, db: Session = Depends(get_db), settings: Settings = Depends(settings_dep), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF)
    from app.services.trash_service import delete_template
    delete_template(db, settings, user, template_id)
    return {"deleted": True}



@router.get("/admin/template-assets")
def admin_template_assets(folder: str | None = None, search: str | None = None, limit: int = 50, offset: int = 0, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF)
    local = [a for a in list_template_assets() if a["source"] == "local"]
    uploaded = uploaded_assets_paged(db, folder=folder, search=search, limit=min(max(limit, 1), 200), offset=max(offset, 0))
    total = count_uploaded_assets(db, folder=folder, search=search)
    return {"assets": local + uploaded, "total": total, "folders": folder_summary(db)}



@router.post("/admin/template-assets")
async def admin_template_asset_upload(
    file: UploadFile = File(...),
    label: str | None = Form(None),
    folder: str | None = Form(None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF)
    data = await file.read()
    filename = file.filename or "asset.png"
    content_type = file.content_type or "application/octet-stream"
    try:
        record = upload_template_asset(db, settings, user, filename, content_type, data, label=label, folder=folder)
    except StorageError as exc:
        raise AppError(str(exc), 400) from exc
    return {
        "asset": {
            "id": record.id,
            "label": record.label,
            "filename": record.filename,
            "url": f"/template-assets/{record.id}",
            "size_bytes": record.size_bytes,
            "source": "uploaded",
            "folder": record.folder,
        }
    }



@router.delete("/admin/template-assets/{asset_id}")
def admin_template_asset_delete(asset_id: str, db: Session = Depends(get_db), settings: Settings = Depends(settings_dep), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF)
    from app.services.trash_service import delete_template_asset
    delete_template_asset(db, settings, user, asset_id)
    return {"deleted": True}



@router.get("/admin/templates/{template_id}")
def admin_template_detail(template_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF)
    template = db.get(OutputTemplateConfig, template_id)
    if not template:
        raise AppError("Template not found.", 404)
    return {"template": serialize_template(template, db)}



@router.post("/admin/templates/{template_id}/copy")
def admin_template_copy(template_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    template = copy_template(db, user, template_id)
    return {"template": serialize_template(template, db)}



@router.post("/admin/templates/{template_id}/make-master")
def admin_template_make_master(template_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    template = make_template_master(db, user, template_id)
    return {"template": serialize_template(template, db)}



@router.post("/admin/templates/{template_id}/set-default")
def admin_template_set_default(template_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    template = make_template_master(db, user, template_id)
    return {"template": serialize_template(template, db)}



@router.patch("/admin/templates/{template_id}")
def admin_template_update(template_id: str, payload: TemplateUpdateRequest, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    template = update_template(db, user, template_id, payload.model_dump(exclude_none=True))
    return {"template": serialize_template(template)}



@router.post("/admin/templates")
def admin_template_save(payload: TemplateSaveRequest, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    template = upsert_template(db, user, payload.model_dump(exclude_none=True))
    return {"template": serialize_template(template, db)}



@router.get("/template-assets/{asset_id}")
def template_asset_file(
    asset_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Response:
    if not user or user.role not in {Role.SUPER_ADMIN.value, Role.ADMIN.value, Role.STAFF.value}:
        raise AppError("File not found.", 404)
    try:
        resolved = resolve_template_asset(db, asset_id)
    except FileNotFoundError:
        raise AppError("File not found.", 404) from None
    if isinstance(resolved, Path):
        return FileResponse(resolved)
    mime = "image/svg+xml" if asset_id.lower().endswith(".svg") else "image/png"
    return Response(resolved, media_type=mime)



@router.get("/admin/our-specials")
def admin_our_specials(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    return {
        "our_specials": [
            serialize_special(item)
            for item in db.scalars(
                select(OurSpecial)
                .where(OurSpecial.deleted_at.is_(None))
                .options(selectinload(OurSpecial.variants))
            ).all()
        ]
    }



@router.post("/admin/our-specials")
def admin_our_special_save(payload: OurSpecialSaveRequest, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    special = upsert_special(db, user, payload.model_dump(exclude_none=True))
    return {"our_special": serialize_special(special)}



@router.delete("/admin/our-specials/{special_id}")
def admin_our_special_delete(special_id: str, db: Session = Depends(get_db), settings: Settings = Depends(settings_dep), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    delete_special(db, settings, user, special_id)
    return {"deleted": True}



@router.get("/previews/{preview_id}/html")
def preview_html(
    preview_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> Response:
    html = render_snapshot_preview_html(db, user, preview_id, settings)
    return Response(
        content=html,
        media_type="text/html",
        headers={
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": "default-src 'none'; img-src data:; style-src 'unsafe-inline'",
            "X-Content-Type-Options": "nosniff",
        },
    )

