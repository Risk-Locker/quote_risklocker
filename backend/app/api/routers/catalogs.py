"""Catalogs API router."""

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


@router.get("/business/template-page-profiles")
def business_template_page_profiles(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    return {"page_profiles": list_page_profiles(db, user)}



@router.get("/business/companies")
def business_companies(
    search: str = Query(default="", max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {
        "companies": list_business_companies(
            db,
            user,
            search=search,
            page=page,
            page_size=page_size,
        )
    }



@router.get("/business/company-aliases")
def business_company_aliases(
    search: str = Query(default="", max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"aliases": list_company_aliases(db, user, search=search, page=page, page_size=page_size)}



@router.post("/business/company-aliases")
def business_company_alias_save(
    payload: CompanyAliasSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"company_alias": save_company_alias(db, user, payload.model_dump(exclude_none=True))}



@router.put("/business/company-aliases/{alias_id}")
def business_company_alias_update(
    alias_id: str,
    payload: CompanyAliasSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    body = payload.model_dump(exclude_none=True)
    body["id"] = alias_id
    return {"company_alias": save_company_alias(db, user, body)}



@router.delete("/business/company-aliases/{alias_id}", status_code=status.HTTP_204_NO_CONTENT)
def business_company_alias_retire(
    alias_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Response:
    retire_company_alias(db, user, alias_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)



@router.get("/business/companies")
def business_companies(
    search: str = Query(default="", max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"companies": list_business_companies(db, user, search=search, page=page, page_size=page_size)}



@router.post("/business/companies")
def business_company_save(
    payload: BusinessCompanySaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"company": save_business_company(db, user, payload.model_dump(exclude_none=True))}



@router.delete("/business/companies/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def business_company_delete(
    company_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Response:
    delete_business_company(db, user, company_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)



@router.get("/business/companies/{company_id}/workspace")
def business_company_workspace(
    company_id: str,
    include_archived: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    if include_archived:
        return {"workspace": get_business_company_workspace(db, user, company_id, include_archived=True)}
    return {"workspace": get_business_company_workspace(db, user, company_id)}



@router.get("/business/benefit-profiles")
def business_benefit_profiles_list(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"profiles": list_benefit_profiles(db, user)}



@router.post("/business/benefit-profiles")
def business_benefit_profile_create(
    payload: BenefitProfileCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"profile": create_benefit_profile(db, user, payload.model_dump())}



@router.post("/business/benefit-profiles/{profile_id}/clone")
def business_benefit_profile_clone(
    profile_id: str,
    payload: BenefitProfileCloneRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"profile": clone_benefit_profile(db, user, profile_id, payload.model_dump())}



@router.put("/business/benefit-profiles/{profile_id}")
def business_benefit_profile_update(
    profile_id: str,
    payload: BenefitProfileUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"profile": update_benefit_profile(db, user, profile_id, payload.model_dump(exclude_unset=True))}



@router.post("/business/benefit-profiles/{profile_id}/activate")
def business_benefit_profile_activate(
    profile_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"profile": activate_benefit_profile(db, user, profile_id)}



@router.delete("/business/benefit-profiles/{profile_id}")
def business_benefit_profile_delete(
    profile_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    delete_benefit_profile(db, user, profile_id)
    return {"ok": True}



@router.get("/business/companies/{company_id}/profiles")
def business_company_profiles_list(
    company_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"profiles": list_benefit_profiles(db, user)}



@router.post("/business/companies/{company_id}/profiles")
def business_company_profile_create(
    company_id: str,
    payload: BenefitProfileCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"profile": create_benefit_profile(db, user, payload.model_dump())}



@router.post("/business/companies/{company_id}/profiles/{profile_id}/clone")
def business_company_profile_clone(
    company_id: str,
    profile_id: str,
    payload: BenefitProfileCloneRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"profile": clone_benefit_profile(db, user, profile_id, payload.model_dump())}



@router.put("/business/companies/{company_id}/profiles/{profile_id}")
def business_company_profile_update(
    company_id: str,
    profile_id: str,
    payload: BenefitProfileUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"profile": update_benefit_profile(db, user, profile_id, payload.model_dump(exclude_unset=True))}



@router.post("/business/companies/{company_id}/profiles/{profile_id}/activate")
def business_company_profile_activate(
    company_id: str,
    profile_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"profile": activate_benefit_profile(db, user, profile_id)}



@router.delete("/business/companies/{company_id}/profiles/{profile_id}")
def business_company_profile_delete(
    company_id: str,
    profile_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    delete_benefit_profile(db, user, profile_id)
    return {"ok": True}



@router.get("/business/companies/{company_id}/benefit-configs")
def business_company_benefit_configs(
    company_id: str,
    profile_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"configs": get_company_benefit_configs(db, user, company_id, profile_id=profile_id)}



@router.put("/business/companies/{company_id}/benefit-configs")
def business_company_benefit_configs_update(
    company_id: str,
    payload: CompanyBenefitConfigsUpdateRequest,
    profile_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    updated = update_company_benefit_configs(db, user, company_id, [item.model_dump() for item in payload.items], profile_id=profile_id)
    return {"configs": updated}



@router.get("/business/companies/{company_id}/conditions")
def business_company_conditions_list(
    company_id: str,
    profile_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"conditions": list_company_conditions(db, user, company_id, profile_id=profile_id)}



@router.post("/business/companies/{company_id}/conditions")
def business_company_condition_save(
    company_id: str,
    payload: CompanyBenefitConditionSaveRequest,
    profile_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"condition": save_company_condition(db, user, company_id, payload.model_dump(), profile_id=profile_id)}



@router.delete("/business/companies/{company_id}/conditions/{condition_id}")
def business_company_condition_delete(
    company_id: str,
    condition_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    delete_company_condition(db, user, company_id, condition_id)
    return {"ok": True}



@router.get("/business/companies/{company_id}/matrix")
def business_company_matrix(
    company_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"matrix": get_company_matrix_data(db, company_id)}



@router.get("/business/companies/{company_id}/export-matrix")
def business_company_matrix_export(
    company_id: str,
    format: str = "docx",
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Response:
    matrix = get_company_matrix_data(db, company_id)
    slug = matrix["company"].get("slug") or "company"
    fmt = (format or "docx").lower().strip()
    today_str = date.today().isoformat()
    if fmt == "xlsx":
        xlsx_buf = generate_company_matrix_xlsx(matrix)
        filename = f"{slug}_benefits_matrix_{today_str}.xlsx"
        return Response(
            xlsx_buf.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    docx_buf = generate_company_matrix_docx(matrix)
    filename = f"{slug}_benefits_matrix_{today_str}.docx"
    return Response(
        docx_buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )



@router.post("/business/companies/{company_id}/diff-matrix")
def business_company_matrix_diff(
    company_id: str,
    payload: CompanyMatrixDiffRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    existing = get_company_matrix_data(db, company_id)
    diff = diff_company_matrix(existing, payload.model_dump())
    return {"diff": diff}



@router.post("/business/companies/{company_id}/catalog-operations/preview")
def business_catalog_operations_preview(
    company_id: str,
    payload: CatalogOperationsPreviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    operations = parse_catalog_intent(db, payload.query, company_id, payload.profile_id)
    preview = preview_catalog_operations(db, company_id, operations, payload.profile_id)
    return {
        "preview": preview,
        "operations": operations,
        "parsed_intent": {"operations": operations},
        **preview,
    }



@router.post("/business/companies/{company_id}/catalog-operations/apply")
def business_catalog_operations_apply(
    company_id: str,
    payload: CatalogOperationsApplyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    result = apply_catalog_operations(db, user, company_id, payload.model_dump())
    return result



@router.post("/business/products")
def business_product_save(
    payload: BusinessProductSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"product": save_business_product(db, user, payload.model_dump(exclude_none=True))}



@router.put("/business/products/{product_id}")
def business_product_update(
    product_id: str,
    payload: BusinessProductSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    body = payload.model_dump(exclude_none=True)
    body["id"] = product_id
    return {"product": save_business_product(db, user, body)}



@router.delete("/business/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def business_product_delete(
    product_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Response:
    delete_business_product(db, user, product_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)



@router.post("/business/tiers")
def business_tier_save(
    payload: BusinessTierSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"tier": save_business_tier(db, user, payload.model_dump(exclude_none=True))}



@router.put("/business/tiers/{tier_id}")
def business_tier_update(
    tier_id: str,
    payload: BusinessTierSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    body = payload.model_dump(exclude_none=True)
    body["id"] = tier_id
    return {"tier": save_business_tier(db, user, body)}



@router.delete("/business/tiers/{tier_id}", status_code=status.HTTP_204_NO_CONTENT)
def business_tier_delete(
    tier_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Response:
    delete_business_tier(db, user, tier_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)



@router.get("/business/benefit-concepts")
def business_benefit_concepts(
    search: str = Query(default="", max_length=200),
    visual_profile_id: str | None = Query(default=None, max_length=60),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {
        "benefit_concepts": list_benefit_concepts(
            db,
            user,
            search=search,
            page=page,
            page_size=page_size,
            visual_profile_id=visual_profile_id,
        )
    }



@router.post("/business/benefit-concepts")
def business_benefit_concept_save(
    payload: BenefitConceptSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"benefit_concept": save_benefit_concept(db, user, payload.model_dump(exclude_none=True))}



@router.delete("/business/benefit-concepts/{concept_id}", status_code=status.HTTP_204_NO_CONTENT)
def business_benefit_concept_retire(
    concept_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Response:
    retire_benefit_concept(db, user, concept_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)



@router.post("/business/benefit-concepts/{concept_id}/restore")
def business_benefit_concept_restore(
    concept_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"benefit_concept": restore_benefit_concept(db, user, concept_id)}



@router.get("/business/segments")
def business_segments(
    search: str = Query(default="", max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"segments": list_segments(db, user, search=search, page=page, page_size=page_size)}



@router.post("/business/segments")
def business_segment_save(
    payload: SegmentSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"segment": save_segment(db, user, payload.model_dump(exclude_none=True))}



@router.delete("/business/segments/{segment_id}", status_code=status.HTTP_204_NO_CONTENT)
def business_segment_retire(
    segment_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Response:
    retire_segment(db, user, segment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)



@router.get("/business/vehicle-categories")
def business_vehicle_categories(
    search: str = Query(default="", max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"vehicle_categories": list_vehicle_categories(db, user, search=search, page=page, page_size=page_size)}



@router.post("/business/vehicle-categories")
def business_vehicle_category_save(
    payload: VehicleCategorySaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"vehicle_category": save_vehicle_category(db, user, payload.model_dump(exclude_none=True))}



@router.delete("/business/vehicle-categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def business_vehicle_category_retire(
    category_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Response:
    retire_vehicle_category(db, user, category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)



@router.get("/business/vehicle-subcategories")
def business_vehicle_subcategories(
    category_id: str | None = Query(default=None, max_length=80),
    search: str = Query(default="", max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"vehicle_subcategories": list_vehicle_subcategories(db, user, category_id=category_id, search=search, page=page, page_size=page_size)}



@router.post("/business/vehicle-subcategories")
def business_vehicle_subcategory_save(
    payload: VehicleSubcategorySaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"vehicle_subcategory": save_vehicle_subcategory(db, user, payload.model_dump(exclude_none=True))}



@router.delete("/business/vehicle-subcategories/{subcategory_id}", status_code=status.HTTP_204_NO_CONTENT)
def business_vehicle_subcategory_retire(
    subcategory_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Response:
    retire_vehicle_subcategory(db, user, subcategory_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)



@router.get("/business/coverage-types")
def business_coverage_types(
    search: str = Query(default="", max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"coverage_types": list_coverage_types(db, user, search=search, page=page, page_size=page_size)}



@router.post("/business/coverage-types")
def business_coverage_type_save(
    payload: CoverageTypeSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"coverage_type": save_coverage_type(db, user, payload.model_dump(exclude_none=True))}



@router.delete("/business/coverage-types/{coverage_id}", status_code=status.HTTP_204_NO_CONTENT)
def business_coverage_type_retire(
    coverage_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Response:
    retire_coverage_type(db, user, coverage_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)



@router.get("/business/benefit-aliases")
def business_benefit_aliases(
    benefit_id: str | None = Query(default=None, max_length=80),
    scope: str | None = Query(default=None, max_length=40),
    product_id: str | None = Query(default=None, max_length=80),
    package_id: str | None = Query(default=None, max_length=80),
    search: str = Query(default="", max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"benefit_aliases": list_benefit_aliases(db, user, benefit_id=benefit_id, scope=scope, product_id=product_id, package_id=package_id, search=search, page=page, page_size=page_size)}



@router.post("/business/benefit-aliases")
def business_benefit_alias_save(
    payload: BenefitAliasSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"benefit_alias": save_benefit_alias(db, user, payload.model_dump(exclude_none=True))}



@router.put("/business/benefit-aliases/{alias_id}")
def business_benefit_alias_update(
    alias_id: str,
    payload: BenefitAliasSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    body = payload.model_dump(exclude_none=True)
    body["id"] = alias_id
    return {"benefit_alias": save_benefit_alias(db, user, body)}



@router.delete("/business/benefit-aliases/{alias_id}", status_code=status.HTTP_204_NO_CONTENT)
def business_benefit_alias_retire(
    alias_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Response:
    retire_benefit_alias(db, user, alias_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)



@router.get("/business/global-benefit-profiles")
def business_list_global_benefit_profiles(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"profiles": list_global_benefit_profiles(db, user)}



@router.post("/business/global-benefit-profiles")
def business_create_global_benefit_profile(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return create_global_benefit_profile(db, user, payload)



@router.get("/business/global-benefit-profiles/{profile_id}")
def business_get_global_benefit_profile(
    profile_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return get_global_benefit_profile_detail(db, user, profile_id)



@router.post("/business/global-benefit-profiles/{profile_id}/clone")
def business_clone_global_benefit_profile(
    profile_id: str,
    payload: dict = Body(default={}),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return clone_global_benefit_profile(db, user, profile_id, payload)



@router.post("/business/global-benefit-profiles/{profile_id}/activate")
def business_activate_global_benefit_profile(
    profile_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return activate_global_benefit_profile(db, user, profile_id)



@router.delete("/business/global-benefit-profiles/{profile_id}")
def business_delete_global_benefit_profile(
    profile_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Response:
    delete_global_benefit_profile(db, user, profile_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)



@router.post("/business/global-benefit-profiles/{profile_id}/auto-assign")
def business_auto_assign_global_benefit_profile(
    profile_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return auto_assign_category_assets(db, user, profile_id)



@router.put("/business/global-benefit-profiles/{profile_id}/assets")
def business_save_global_benefit_profile_assets(
    profile_id: str,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    items = payload.get("items") or []
    return save_global_benefit_profile_assets(db, user, profile_id, items)



@router.post("/business/catalogs")
def business_catalog_create(
    payload: BenefitCatalogSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"catalog": create_benefit_catalog(db, user, payload.model_dump(exclude_none=True))}



@router.post("/business/catalogs/{catalog_id}/context")
def business_catalog_context(
    catalog_id: str,
    payload: CatalogContextRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"catalog": update_catalog_context(db, user, catalog_id, payload.model_dump(exclude_none=True))}



@router.post("/business/catalogs/{catalog_id}/offerings")
def business_catalog_offering_save(
    catalog_id: str,
    payload: CatalogOfferingSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {
        "offering": save_catalog_offering(
            db,
            user,
            catalog_id,
            payload.model_dump(mode="json", exclude_none=True),
        )
    }



@router.delete("/business/catalogs/{catalog_id}/offerings/{offering_id}", status_code=status.HTTP_204_NO_CONTENT)
def business_catalog_offering_delete(
    catalog_id: str,
    offering_id: str,
    base_revision: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Response:
    remove_catalog_offering(db, user, catalog_id, offering_id, base_revision=base_revision)
    return Response(status_code=status.HTTP_204_NO_CONTENT)



@router.post("/business/catalogs/{catalog_id}/packages")
def business_catalog_package_save(
    catalog_id: str,
    payload: PackageSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"package": save_package(db, user, catalog_id, payload.model_dump(exclude_none=True))}



@router.put("/business/catalogs/{catalog_id}/packages/{package_id}")
def business_catalog_package_update(
    catalog_id: str,
    package_id: str,
    payload: PackageSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    body = payload.model_dump(exclude_none=True)
    body["id"] = package_id
    return {"package": save_package(db, user, catalog_id, body)}



@router.post("/business/catalogs/{catalog_id}/packages/{package_id}/clone")
def business_catalog_package_clone(
    catalog_id: str,
    package_id: str,
    payload: PackageCloneRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"package": clone_package(db, user, catalog_id, package_id, payload.model_dump(exclude_none=True))}



@router.delete("/business/catalogs/{catalog_id}/packages/{package_id}", status_code=status.HTTP_204_NO_CONTENT)
def business_catalog_package_retire(
    catalog_id: str,
    package_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Response:
    retire_package(db, user, catalog_id, package_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)



@router.post("/business/catalogs/{catalog_id}/packages/{package_id}/plans")
def business_catalog_plan_save(
    catalog_id: str,
    package_id: str,
    payload: PackagePlanSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"plan": save_plan(db, user, catalog_id, package_id, payload.model_dump(exclude_none=True))}



@router.put("/business/catalogs/{catalog_id}/packages/{package_id}/plans/{plan_id}")
def business_catalog_plan_update(
    catalog_id: str,
    package_id: str,
    plan_id: str,
    payload: PackagePlanSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    body = payload.model_dump(exclude_none=True)
    body["id"] = plan_id
    return {"plan": save_plan(db, user, catalog_id, package_id, body)}



@router.delete("/business/catalogs/{catalog_id}/packages/{package_id}/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def business_catalog_plan_retire(
    catalog_id: str,
    package_id: str,
    plan_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Response:
    retire_plan(db, user, catalog_id, package_id, plan_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)



@router.put("/business/catalogs/{catalog_id}/packages/{package_id}/plans/{plan_id}/items")
def business_catalog_plan_items(
    catalog_id: str,
    package_id: str,
    plan_id: str,
    payload: PackagePlanItemsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return save_plan_items(db, user, catalog_id, package_id, plan_id, payload.model_dump(exclude_none=True))



@router.post("/business/catalogs/{catalog_id}/publish")
def business_catalog_publish(
    catalog_id: str,
    payload: CatalogPublishRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"catalog": publish_catalog_revision(db, user, catalog_id, base_revision=payload.base_revision)}



@router.post("/business/catalogs/{catalog_id}/new-draft")
def business_catalog_new_draft(
    catalog_id: str,
    payload: CatalogPublishRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"catalog": create_new_draft_revision(db, user, catalog_id, base_revision=payload.base_revision)}



@router.get("/business/catalogs/{catalog_id}/workspace")
def business_catalog_workspace(
    catalog_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"workspace": get_catalog_workspace(db, user, catalog_id)}



@router.delete("/business/catalogs/{catalog_id}", status_code=status.HTTP_204_NO_CONTENT)
def business_catalog_retire(
    catalog_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Response:
    retire_benefit_catalog(db, user, catalog_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)



@router.get("/business/sources")
def business_sources(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"sources": list_source_documents(db, user, page=page, page_size=page_size)}



@router.get("/business/dictionaries/contains")
def business_dictionary_contains(
    field: str = Query(min_length=1, max_length=40),
    value: str = Query(min_length=1, max_length=160),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF)
    return {"known": dictionary_contains(db, field, value)}



@router.post("/business/dictionaries/learn")
def business_dictionary_learn(payload: DictionaryLearnRequest, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    result = learn_dictionary_value(db, user, payload.field, payload.value)
    return {"result": result}

