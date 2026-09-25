"""Copilot API router."""

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


@router.post("/copilot/chat", response_model=CopilotChatResponse)
def copilot_chat_route(
    payload: CopilotChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    from app.services.copilot_chat_service import chat_with_copilot

    history_dicts = [h.model_dump() for h in payload.history]
    result = chat_with_copilot(
        db=db,
        user=user,
        message=payload.message,
        company_id=payload.company_id,
        history=history_dicts,
        scope=payload.scope,
    )
    return result



@router.post("/copilot/sessions/cleanup-duplicates")
def copilot_sessions_cleanup_route(
    payload: SessionCleanupRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> dict:
    from app.services.copilot_chat_service import execute_session_cleanup

    return execute_session_cleanup(db, settings, user, payload.session_ids)



@router.post("/copilot/profiles/cleanup-dummy")
def copilot_profiles_cleanup_route(
    payload: ProfileCleanupRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    from app.services.copilot_chat_service import execute_profile_cleanup

    return execute_profile_cleanup(db, user, payload.profile_ids)



@router.get("/settings/ai-context")
def settings_ai_context(
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> dict:
    from app.extraction.gemini_extractor import get_key_pool, build_rag_system_prompt
    from app.models.tables import InsuranceCompany, BenefitConcept, FieldAlias, ClientRecord, QuotationDraft

    pool = get_key_pool()
    quota = pool.get_quota_stats()

    companies = [
        {
            "id": c.id,
            "name": c.name,
            "code": getattr(c, "code", "") or "",
            "aliases": list(c.detection_phrases or []),
            "aliases_count": len(c.detection_phrases or []),
            "has_packages": "amassurance" in c.name.lower(),
        }
        for c in db.scalars(select(InsuranceCompany).order_by(InsuranceCompany.name)).all()
    ]

    concepts = [
        {
            "id": b.id,
            "key": b.concept_key,
            "name": b.label,
            "category": getattr(b, "category", "") or "Add-on",
            "aliases_count": len(b.aliases or []) if hasattr(b, "aliases") and b.aliases else 0,
        }
        for b in db.scalars(select(BenefitConcept).order_by(BenefitConcept.label)).all()
    ]

    field_aliases_db = db.scalars(select(FieldAlias).order_by(FieldAlias.field_name)).all()
    field_aliases = [
        {
            "field_name": fa.field_name,
            "aliases": list(fa.aliases or []),
            "count": len(fa.aliases or []),
        }
        for fa in field_aliases_db
    ]

    saved_records_count = db.scalar(select(func.count(ClientRecord.id))) or 0
    total_sessions_count = db.scalar(select(func.count(QuotationDraft.id))) or 0

    rag_companies = [{"name": c["name"], "aliases": c["aliases"]} for c in companies]
    rag_concepts = [{"key": c["key"], "name": c["name"]} for c in concepts]
    live_prompt = build_rag_system_prompt(db_companies=rag_companies, db_benefit_concepts=rag_concepts)

    return {
        "gemini": {
            "active": quota["keys_count"] > 0,
            "model": getattr(settings, "gemini_model", "gemini-3.5-flash") or "gemini-3.5-flash",
            "key_count": quota["keys_count"],
            "rpm_limit": quota["rpm_limit"],
            "rpm_used": quota["rpm_used"],
            "rpd_limit": quota["rpd_limit"],
            "rpd_used": quota["rpd_used"],
            "rpd_remaining": quota["rpd_remaining"],
            "percent_rpd_remaining": quota["percent_rpd_remaining"],
        },
        "summary_stats": {
            "active_companies_count": len(companies),
            "benefit_concepts_count": len(concepts),
            "field_aliases_count": len(field_aliases),
            "saved_records_count": saved_records_count,
            "total_sessions_count": total_sessions_count,
        },
        "companies": companies,
        "benefit_concepts": concepts,
        "field_aliases": field_aliases,
        "live_system_prompt": live_prompt,
    }



@router.post("/settings/ai-grounding-chat")
def settings_ai_grounding_chat(
    payload: GroundingChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    """Answer targeted grounding queries with ultra-low token context."""
    from app.services.grounding_assistant import answer_grounding_query
    return answer_grounding_query(db, query=payload.query, session_id=payload.session_id)



@router.get("/settings/ai-memory")
def settings_ai_memory_get(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    """Return all AI correction memory items learned from user reviews."""
    from app.models.tables import CorrectionMemory, InsuranceCompany
    from sqlalchemy import func, desc

    memories = (
        db.query(CorrectionMemory, InsuranceCompany.name.label("company_name"))
        .outerjoin(InsuranceCompany, CorrectionMemory.insurance_company_id == InsuranceCompany.id)
        .order_by(desc(CorrectionMemory.created_at))
        .limit(300)
        .all()
    )

    items = []
    for m, cname in memories:
        items.append({
            "id": str(m.id),
            "field_name": m.field_name,
            "original_value": m.original_value or "—",
            "corrected_value": m.corrected_value or "—",
            "insurance_company": cname or "Global / All Insurers",
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })

    field_counts = (
        db.query(CorrectionMemory.field_name, func.count(CorrectionMemory.id))
        .group_by(CorrectionMemory.field_name)
        .order_by(desc(func.count(CorrectionMemory.id)))
        .all()
    )
    summary_by_field = [{"field": row[0], "count": row[1]} for row in field_counts]
    total_count = db.query(func.count(CorrectionMemory.id)).scalar() or 0

    return {
        "total_memories": total_count,
        "summary_by_field": summary_by_field,
        "items": items,
    }



@router.get("/settings/ai-prompt")
def settings_ai_prompt_get(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    """Return the global AI system-prompt override and the effective prompt."""
    from app.extraction.gemini_extractor import build_rag_system_prompt
    from app.models.tables import AppSetting, InsuranceCompany, BenefitConcept

    setting = db.get(AppSetting, "ai_system_prompt")
    override = str((setting.value or {}).get("text") or "") if setting and isinstance(setting.value, dict) else ""
    companies = [{"name": c.name} for c in db.scalars(select(InsuranceCompany).order_by(InsuranceCompany.name)).all()]
    concepts = [{"key": c.concept_key, "name": c.label} for c in db.scalars(select(BenefitConcept).order_by(BenefitConcept.label)).all()]
    effective = build_rag_system_prompt(
        db_companies=companies,
        db_benefit_concepts=concepts,
        prompt_override=override or None,
    )
    return {
        "override": override,
        "effective_prompt": effective,
        "is_override_active": bool(override.strip()),
    }



@router.put("/settings/ai-prompt")
def settings_ai_prompt_put(
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    """Set (or clear) the global AI system-prompt override. Admin/super_admin only."""
    if user.role not in {Role.SUPER_ADMIN.value, Role.ADMIN.value}:
        raise AppError("Only administrators can change the AI system prompt.", 403)
    from app.models.tables import AppSetting

    text = str(payload.get("text") or "").strip()
    if len(text) > 12_000:
        raise AppError("The AI system prompt is too long (max 12,000 characters).", 422)
    setting = db.get(AppSetting, "ai_system_prompt")
    if not setting:
        setting = AppSetting(key="ai_system_prompt", value={"text": text})
        db.add(setting)
    else:
        setting.value = {"text": text}
    db.add(AuditEvent(
        actor_id=user.id,
        action="settings.ai_prompt.update",
        entity_type="app_settings",
        entity_id="ai_system_prompt",
        details={"characters": len(text), "active": bool(text)},
    ))
    db.commit()
    return {"override": text, "is_override_active": bool(text)}

