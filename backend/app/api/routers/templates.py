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
    TemplateLivePreviewRequest,
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
    TemplateRevision,
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



def evict_asset_cache_paths(paths: list[str]) -> None:
    with _asset_cache_lock:
        for path in paths:
            _asset_memory_cache.pop(path, None)
            safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", path) + ".bin"
            disk_path = _ASSET_CACHE_DIR / safe_name
            if disk_path.exists():
                try:
                    disk_path.unlink()
                except Exception:
                    pass



@router.get("/business/assets/{asset_id}/content")
def business_asset_content(
    asset_id: str,
    request: Request,
    profile: str = Query(default="ui", pattern="^(ui|pdf|original)$"),
    v: str | None = Query(default=None),
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

    has_version = bool(v or request.query_params.get("v"))
    cache_control = "private, max-age=86400, immutable" if has_version else "private, no-cache"

    if_none_match = request.headers.get("if-none-match")
    if if_none_match and content_hash in if_none_match:
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers={
                "Cache-Control": cache_control,
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
            "Cache-Control": cache_control,
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



@router.post("/business/templates/{template_id}/unpublish")
def business_unpublish_template(
    template_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF)
    template = db.get(OutputTemplateConfig, template_id)
    if not template or template.deleted_at:
        raise AppError("Template not found.", 404)
    revisions = list(
        db.scalars(
            select(TemplateRevision).where(
                TemplateRevision.template_id == template_id,
                TemplateRevision.state.in_(["published", "compatibility"]),
            )
        ).all()
    )
    for rev in revisions:
        rev.state = "draft"
    db.commit()
    return {"status": "ok", "template": serialize_template(template, db)}




@router.get("/admin/templates")
def admin_templates(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF)
    items = list(
        db.scalars(
            select(OutputTemplateConfig).where(OutputTemplateConfig.deleted_at.is_(None))
        ).all()
    )
    templates = serialize_templates_batch(db, items)
    def _admin_sort_key(item: dict) -> tuple:
        name = item.get("name", "").lower()
        is_def = not item.get("is_default", False)
        priority = 0 if "v4" in name else (1 if "v3" in name else 2)
        return (is_def, priority, name.casefold())

    templates.sort(key=_admin_sort_key)
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


_BENEFIT_ARTWORK_CACHE: dict[str, str] | None = None

_MOCK_CARD_KEYS: dict[str, str] = {
    "Panel Workmanship Warranty": "repair-workmanship-warranty",
    "Emergency Towing Assistance": "towing",
    "Legal Defense Costs": "legal-costs-defense",
    "All Drivers Excess Waiver": "all-drivers",
    "Key Care Protection": "key-replacement",
    "Legal Liability of Passengers": "legal-liability-of-passengers",
    "Legal Liability to Passengers": "legal-liability-to-passengers",
    "Flood & Special Perils": "special-perils",
    "Windscreen Protection": "windscreen",
    "Driver & Passenger PA": "driver-passenger-protector",
    "Compensation Repair (CART)": "repair-allowance",
    "Cart 14 Days": "repair-allowance",
    "Waiver of Betterment": "betterment-protection",
    "Strike, Riot & Civil Commotion": "strike-riot-civil-commotion",
    "Road Tax Courier Service": "document-replacement",
    "Vehicle Accessories Protection": "vehicle-accessories",
    "Car Spray Repainting": "repaint-spray-paint",
    "Personal Accident Extended": "driver-passenger-protector",
    "Child Seat Replacement": "child-car-seat",
    "Tire Replacement Cover": "side-mirror-protection",
    "Rim Damage Protection": "side-mirror-protection",
    "Medical Expenses Allowance": "medical-expenses",
    "Ambulance Fee Reimbursement": "ambulance-fees",
}


def _get_benefit_artwork_data_uris() -> dict[str, str]:
    global _BENEFIT_ARTWORK_CACHE
    if _BENEFIT_ARTWORK_CACHE is not None:
        return _BENEFIT_ARTWORK_CACHE

    import base64
    from pathlib import Path

    art: dict[str, str] = {}
    base_dir = Path(__file__).resolve().parents[4] / "assets" / "benefits"

    # 1. First load 2D assets (compact, crisp, fast)
    p_2d = base_dir / "global_benefits_2d_assets_v2_new"
    if p_2d.exists():
        for f in p_2d.glob("*.*"):
            if f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                mime = "image/png" if f.suffix.lower() == ".png" else "image/jpeg"
                try:
                    data = f.read_bytes()
                    b64 = f"data:{mime};base64," + base64.b64encode(data).decode("ascii")
                    stem = f.stem.lower()
                    clean = stem.split("_", 1)[-1] if "_" in stem else stem
                    clean_spaced = clean.replace("-", " ").strip()
                    clean_dashed = clean.replace(" ", "-").strip()
                    art[clean_spaced] = b64
                    art[clean_dashed] = b64
                    art[f"preview-{clean_dashed}"] = b64
                except Exception:
                    pass

    # 2. Add high-res PNG benefit files as fallback/complement
    if base_dir.exists():
        for f in base_dir.glob("*.png"):
            try:
                data = f.read_bytes()
                b64 = "data:image/png;base64," + base64.b64encode(data).decode("ascii")
                stem = f.stem.lower().strip()
                art[stem] = b64
                art[stem.replace(" ", "-")] = b64
                art[f"preview-{stem.replace(' ', '-')}"] = b64
            except Exception:
                pass

    # 3. Add canonical aliases & keywords
    synonyms = {
        "towing": ["towing", "emergency roadside assistance"],
        "windscreen": ["windscreen", "windscreen coverage"],
        "special-perils": ["special perils", "flood coverage  flood damage protection", "first loss flood"],
        "flood": ["special perils", "flood coverage  flood damage protection"],
        "workmanship": ["repair workmanship warranty", "repair-workmanship-warranty"],
        "betterment": ["betterment-protection", "waiver of betterment", "betterment protection"],
        "key-replacement": ["key-replacement", "key replacement  key care", "key care"],
        "key-care": ["key-replacement", "key replacement  key care"],
        "all-drivers": ["all-drivers", "all drivers coverage"],
        "driver-passenger-protector": ["driver-passenger-protector", "driver and passenger protection plan", "personal accident"],
        "pa": ["driver-passenger-protector", "personal accident"],
        "cart": ["repair allowance", "repair-allowance", "courtesy car or replacement car"],
        "strike-riot": ["strike-riot-civil-commotion", "strike, riot and civil commotion"],
        "ambulance": ["ambulance-fees", "ambulance fees"],
        "medical": ["medical-expenses", "medical expenses"],
        "child-seat": ["child-car-seat", "child car seat coverage"],
        "legal-passengers": ["legal-liability-of-passengers", "legal liability of passengers"],
        "legal-liability-to-passengers": ["legal-liability-to-passengers", "legal liability to passengers"],
        "legal-costs-defense": ["legal-costs-defense", "legal defense"],
        "accessories": ["vehicle-accessories", "vehicle accessories"],
        "spray": ["repaint-spray-paint", "whole car spray painting or new coat of paint"],
    }
    for alias, targets in synonyms.items():
        for target in targets:
            if target in art:
                art[alias] = art[target]
                art[alias.replace("-", " ")] = art[target]
                art[f"preview-{alias}"] = art[target]
                break

    _BENEFIT_ARTWORK_CACHE = art
    return _BENEFIT_ARTWORK_CACHE


def _build_preview_profile_data(
    load_profile: str,
    insurer_name: str = "BERJAYA SOMPO INSURANCE BERHAD",
    include_purchased_perils: bool = True,
) -> tuple[dict, dict]:
    """Constructs realistic preview data for template builder stress test profiles."""
    if load_profile == "minimum":
        foc_cards = [
            {"id": "b1", "label": "Panel Workmanship Warranty", "coverage_limit": "12 Months", "short_description": "Repair guarantee at panel workshops."},
            {"id": "b2", "label": "Emergency Towing Assistance", "coverage_limit": "Unlimited", "short_description": "24/7 unlimited breakdown towing."},
        ]
        if include_purchased_perils:
            extras_cards = [
                {"id": "e1", "label": "Flood & Special Perils", "coverage_limit": "RM 85,000", "price": {"amount": 250.0}, "is_extra": True, "cost_status": "paid", "short_description": "Full natural disaster flood, storm, and landslide cover."},
                {"id": "e2", "label": "Windscreen Protection", "coverage_limit": "RM 2,000", "price": {"amount": 150.0}, "is_extra": True, "cost_status": "paid", "short_description": "Front & rear glass replacement without NCD loss."},
            ]
            addon_cards = [
                {"id": "a1", "label": "Driver & Passenger PA", "price": {"amount": 150.0}, "short_description": "Accidental medical reimbursement and disability cover."},
                {"id": "a2", "label": "Cart 14 Days", "price": {"amount": 150.0}, "short_description": "Compensation for assessed repair time."},
            ]
        else:
            extras_cards = []
            addon_cards = [
                {"id": "a1", "label": "Flood & Special Perils", "price": {"amount": 250.0}, "short_description": "Flood, storm, landslide and typhoon."},
                {"id": "a2", "label": "Windscreen Protection", "price": {"amount": 150.0}, "short_description": "Front & rear glass replacement."},
            ]
    elif load_profile == "high":
        foc_cards = [
            {"id": "b1", "label": "Panel Workmanship Warranty", "coverage_limit": "12 Months", "short_description": "Repair guarantee at panel workshops."},
            {"id": "b2", "label": "Emergency Towing Assistance", "coverage_limit": "Unlimited", "short_description": "24/7 unlimited breakdown towing."},
            {"id": "b3", "label": "Legal Defense Costs", "coverage_limit": "RM 2,000", "short_description": "Legal fees protection up to RM 2,000."},
            {"id": "b4", "label": "All Drivers Excess Waiver", "coverage_limit": "Included", "short_description": "Waives RM400 compulsory excess."},
            {"id": "b5", "label": "Key Care Protection", "coverage_limit": "RM 1,500", "short_description": "Key replacement reimbursement."},
            {"id": "b6", "label": "Legal Liability of Passengers", "coverage_limit": "Included", "short_description": "Third party negligence cover."},
        ]
        if include_purchased_perils:
            extras_cards = [
                {"id": "e1", "label": "Flood & Special Perils", "coverage_limit": "RM 199,000", "price": {"amount": 350.0}, "is_extra": True, "cost_status": "paid", "short_description": "Full natural disaster flood, storm, and landslide cover."},
                {"id": "e2", "label": "Windscreen Protection", "coverage_limit": "RM 4,000", "price": {"amount": 150.0}, "is_extra": True, "cost_status": "paid", "short_description": "Front & rear glass replacement without NCD loss."},
                {"id": "e3", "label": "Driver & Passenger PA", "coverage_limit": "RM 20,000", "price": {"amount": 150.0}, "is_extra": True, "cost_status": "paid", "short_description": "Medical reimbursement and disability cover."},
                {"id": "e4", "label": "Compensation Repair (CART)", "coverage_limit": "14 Days", "price": {"amount": 200.0}, "is_extra": True, "cost_status": "paid", "short_description": "Daily allowance during repair."},
                {"id": "e5", "label": "Waiver of Betterment", "coverage_limit": "Included", "price": {"amount": 120.0}, "is_extra": True, "cost_status": "paid", "short_description": "No deduction for new parts."},
                {"id": "e6", "label": "Strike, Riot & Civil Commotion", "coverage_limit": "Included", "price": {"amount": 90.0}, "is_extra": True, "cost_status": "paid", "short_description": "Damage from civil commotion."},
            ]
            addon_cards = [
                {"id": "a1", "label": "Road Tax Courier Service", "price": {"amount": 25.0}, "short_description": "Express door-to-door delivery."},
                {"id": "a2", "label": "Vehicle Accessories Protection", "price": {"amount": 120.0}, "short_description": "In-car dashcam and audio system."},
                {"id": "a3", "label": "Car Spray Repainting", "price": {"amount": 250.0}, "short_description": "Full body repainting benefit."},
                {"id": "a4", "label": "Personal Accident Extended", "price": {"amount": 180.0}, "short_description": "Extended family passenger cover."},
                {"id": "a5", "label": "Child Seat Replacement", "price": {"amount": 100.0}, "short_description": "Child safety restraint replacement."},
                {"id": "a6", "label": "Tire Replacement Cover", "price": {"amount": 90.0}, "short_description": "Puncture and blowout road hazard."},
                {"id": "a7", "label": "Rim Damage Protection", "price": {"amount": 110.0}, "short_description": "Alloy wheel rim impact protection."},
                {"id": "a8", "label": "Medical Expenses Allowance", "price": {"amount": 130.0}, "short_description": "Accident hospitalization daily cash."},
                {"id": "a9", "label": "Ambulance Fee Reimbursement", "price": {"amount": 70.0}, "short_description": "Emergency ambulance charges cover."},
            ]
        else:
            extras_cards = []
            addon_cards = [
                {"id": "a1", "label": "Flood & Special Perils", "price": {"amount": 350.0}, "short_description": "Flood, storm, landslide and typhoon."},
                {"id": "a2", "label": "Windscreen Protection", "price": {"amount": 150.0}, "short_description": "Front & rear glass replacement."},
                {"id": "a3", "label": "Driver & Passenger PA", "price": {"amount": 150.0}, "short_description": "Personal accident cover."},
                {"id": "a4", "label": "Compensation Repair (CART)", "price": {"amount": 200.0}, "short_description": "Daily allowance during repair."},
                {"id": "a5", "label": "Waiver of Betterment", "price": {"amount": 120.0}, "short_description": "No deduction for new parts."},
                {"id": "a6", "label": "Strike, Riot & Civil Commotion", "price": {"amount": 90.0}, "short_description": "Damage from civil commotion."},
            ]
    else:  # "medium"
        foc_cards = [
            {"id": "b1", "label": "Panel Workmanship Warranty", "coverage_limit": "12 Months", "short_description": "Repair guarantee at panel workshops."},
            {"id": "b2", "label": "Emergency Towing Assistance", "coverage_limit": "Unlimited", "short_description": "24/7 unlimited breakdown towing."},
            {"id": "b3", "label": "Key Care Protection", "coverage_limit": "RM 1,500", "short_description": "Reimbursement for lost or damaged vehicle keys."},
            {"id": "b4", "label": "All Drivers Excess Waiver", "coverage_limit": "Included", "short_description": "Waives RM400 compulsory excess."},
        ]
        if include_purchased_perils:
            extras_cards = [
                {"id": "e1", "label": "Flood & Special Perils", "coverage_limit": "RM 199,000", "price": {"amount": 350.0}, "is_extra": True, "cost_status": "paid", "short_description": "Full natural disaster flood, storm, and landslide cover."},
                {"id": "e2", "label": "Windscreen Protection", "coverage_limit": "RM 4,000", "price": {"amount": 150.0}, "is_extra": True, "cost_status": "paid", "short_description": "Front & rear glass replacement without NCD loss."},
                {"id": "e3", "label": "Driver & Passenger PA", "coverage_limit": "RM 20,000", "price": {"amount": 150.0}, "is_extra": True, "cost_status": "paid", "short_description": "Accidental medical reimbursement and disability cover."},
            ]
            addon_cards = [
                {"id": "a1", "label": "Cart 14 Days", "price": {"amount": 150.0}, "short_description": "Compensation for assessed repair time."},
                {"id": "a2", "label": "Legal Liability to Passengers", "price": {"amount": 45.0}, "short_description": "Negligence claims cover for passengers."},
                {"id": "a3", "label": "Waiver of Betterment", "price": {"amount": 120.0}, "short_description": "No deduction for new parts."},
                {"id": "a4", "label": "Strike, Riot & Civil Commotion", "price": {"amount": 90.0}, "short_description": "Damage from civil commotion."},
            ]
        else:
            extras_cards = []
            addon_cards = [
                {"id": "a1", "label": "Flood & Special Perils", "price": {"amount": 350.0}, "short_description": "Flood, storm, landslide and typhoon."},
                {"id": "a2", "label": "Windscreen Protection", "price": {"amount": 150.0}, "short_description": "Front & rear glass replacement."},
                {"id": "a3", "label": "Driver & Passenger PA", "price": {"amount": 150.0}, "short_description": "Accidental medical reimbursement and disability cover."},
                {"id": "a4", "label": "Cart 14 Days", "price": {"amount": 150.0}, "short_description": "Compensation for assessed repair time."},
                {"id": "a5", "label": "Waiver of Betterment", "price": {"amount": 120.0}, "short_description": "No deduction for new parts."},
            ]

    def _enrich_card(card: dict) -> dict:
        lbl = str(card.get("label") or "")
        key = _MOCK_CARD_KEYS.get(lbl, lbl.lower().replace(" ", "-"))
        c = dict(card)
        c.setdefault("concept_key", key)
        c.setdefault("asset_id", f"preview-{key}")
        if "short_description" in c and "description" not in c:
            c["description"] = c["short_description"]
        return c

    foc_cards = [_enrich_card(c) for c in foc_cards]
    extras_cards = [_enrich_card(c) for c in extras_cards]
    addon_cards = [_enrich_card(c) for c in addon_cards]

    extras_data = [
        {
            "id": c["id"],
            "label": c["label"],
            "concept_key": c.get("concept_key"),
            "asset_id": c.get("asset_id"),
            "coverage_limit": c.get("coverage_limit", ""),
            "price": c.get("price", {}),
            "show_coverage": True,
        }
        for c in extras_cards
    ]

    render_context = {
        "current_benefits": foc_cards + extras_cards,
        "available_addons": addon_cards,
        "extras": extras_data,
        "extras_mode": "itemized",
    }
    draft_fields = {
        "quotation_reference": {"value": "RL260000313"},
        "customer_name": {"value": "CHENG TECK KIONG"},
        "vehicle_no": {"value": "ANY 368"},
        "car_model": {"value": "Tesla Model 3 Performance"},
        "insurance_company": {"value": insurer_name},
        "coverage_type": {"value": "Comprehensive"},
        "cover_period": {"value": "04-06-2026 to 03-06-2027"},
        "engine_cc": {"value": "9.4 kW"},
        "ncd_percent": {"value": "25.00%"},
        "valuation_type": {"value": "Market Value"},
        "authorized_driver": {"value": "All Driver"},
        "excess_amount": {"value": "RM 0.00"},
        "coverage_amount": {"value": "RM 199,000.00"},
        "premium": {"value": "3,758.21"},
        "roadtax": {"value": "20.00"},
        "service_fee": {"value": "10.00"},
        "total_amount": {"value": "4,423.21" if extras_cards else "3,788.21"},
        "valid_until": {"value": "14 Days"},
    }
    return draft_fields, render_context


@router.post("/admin/templates/preview-render")
def admin_template_preview_render(
    payload: TemplateLivePreviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    from app.rendering.template_renderer import render_quotation_html
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    draft_fields, render_context = _build_preview_profile_data(
        payload.load_profile,
        include_purchased_perils=payload.include_purchased_perils,
    )
    insurer = "BERJAYA SOMPO INSURANCE BERHAD"

    if payload.session_id:
        try:
            from app.services.workspace_snapshot_service import build_workspace_snapshot
            snap = build_workspace_snapshot(db, user, payload.session_id)
            if snap:
                for k, v in (snap.get("fields") or {}).items():
                    if isinstance(v, dict) and "value" in v:
                        draft_fields[k] = v
                if draft_fields.get("insurance_company", {}).get("value"):
                    insurer = str(draft_fields["insurance_company"]["value"])

                bc = snap.get("benefit_cards") or {}
                snap_extras = list(snap.get("extras") or [])
                curr_benefits = list(bc.get("current_benefits") or [])
                avail_addons = list(bc.get("available_addons") or [])

                if not payload.include_purchased_perils:
                    from app.rendering.template_renderer import _is_paid_extra
                    snap_extras = []
                    curr_benefits = [c for c in curr_benefits if not _is_paid_extra(c)]

                render_context["current_benefits"] = curr_benefits
                render_context["available_addons"] = avail_addons
                render_context["extras"] = snap_extras
                render_context["display_options"] = snap.get("display_options") or {}
                render_context["total_premium_adjusted"] = snap.get("total_premium_adjusted")
        except Exception:
            pass

    import copy
    tmpl_config = copy.deepcopy(payload.template_config or {})
    tmpl_name = str(tmpl_config.get("name") or "")

    if payload.template_id:
        tmpl = db.query(OutputTemplateConfig).filter_by(id=payload.template_id).first()
        if tmpl and tmpl.fixed_fields:
            if not tmpl_config:
                tmpl_config = copy.deepcopy(tmpl.fixed_fields)
            if not tmpl_name:
                tmpl_name = tmpl.name

    if not tmpl_config:
        default_t = db.query(OutputTemplateConfig).filter(OutputTemplateConfig.name.ilike("%v4%")).first()
        if default_t and default_t.fixed_fields:
            tmpl_config = copy.deepcopy(default_t.fixed_fields)
            tmpl_name = default_t.name

    if payload.benefit_preset_config and isinstance(payload.benefit_preset_config, dict):
        canvas = tmpl_config.setdefault("canvas", {})
        elems = canvas.setdefault("elements", [])
        for el in elems:
            if el.get("type") == "benefit-grid":
                for k in [
                    "layoutMode", "columns", "cardStyle", "textDensity",
                    "iconSize", "shape", "elevation", "borderWidth", "borderStyle",
                    "imageFit", "iconPadShape", "titleSize", "titleWeight", "titleColor",
                    "textWrap", "valueBadgeStyle", "coverageSize", "coverageColor",
                    "descSize", "descWeight", "descColor", "descMaxLines",
                    "costSize", "costColor", "costBgColor",
                    "bgColor", "borderColor", "textColor", "accentColor",
                    "rowHeight", "uniformHeight", "sectionVisibility",
                    "showDescription", "showCoverage", "showCost", "benefitPreset"
                ]:
                    if k in payload.benefit_preset_config:
                        el[k] = payload.benefit_preset_config[k]
        render_context["benefit_preset_config"] = payload.benefit_preset_config

    if tmpl_config and "extras_mode" in tmpl_config:
        render_context["extras_mode"] = str(tmpl_config["extras_mode"]).lower()

    if not tmpl_name:
        tmpl_name = "Bilingual Agency Motor v4"

    resolved_assets = dict(_get_benefit_artwork_data_uris())

    if payload.session_id:
        try:
            from app.services.global_benefit_profile_service import get_active_visual_profile_asset_map
            from app.rendering.template_renderer import asset_data_uri
            vp_map = get_active_visual_profile_asset_map(db)
            for c_id, a_id in (vp_map or {}).items():
                if a_id and a_id not in resolved_assets:
                    uri = asset_data_uri(db, a_id)
                    if uri:
                        resolved_assets[a_id] = uri
                        resolved_assets[c_id] = uri
        except Exception:
            pass

    html = render_quotation_html(
        draft_fields=draft_fields,
        template_name=tmpl_name,
        template_config=tmpl_config,
        insurer_name=insurer,
        db=db,
        render_context=render_context,
        resolved_assets=resolved_assets,
    )
    return {"html": html}


