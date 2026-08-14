"""Application API routes."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Header, Query, Request, Response as FastAPIResponse, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import AuthContext, current_auth, current_auth_optional, current_user, ensure_trusted_origin, settings_dep
from app.api.schemas import (
    BulkClientRecordDeleteRequest,
    BulkUploadedFileDeleteRequest,
    BenefitCatalogSaveRequest,
    BenefitConceptSaveRequest,
    BusinessCompanySaveRequest,
    BusinessProductSaveRequest,
    BusinessTierSaveRequest,
    CatalogOfferingSaveRequest,
    CatalogPublishRequest,
    ClientRecordUpdateRequest,
    CompanySaveRequest,
    CompanyAliasSaveRequest,
    DictionaryLearnRequest,
    DraftGenerateRequest,
    DraftUpdateRequest,
    ExtractionSettingsRequest,
    FieldAliasSaveRequest,
    GenerateSelectedRequest,
    LoginRequest,
    OurSpecialSaveRequest,
    OurSpecialVariantSaveRequest,
    RoadTaxRuleSaveRequest,
    RecordBulkActionRequest,
    RecordSavedViewRequest,
    TemplateSaveRequest,
    TemplateGroupSaveRequest,
    TemplatePublishRequest,
    TemplateSelectionImpactRequest,
    TemplateUpdateRequest,
    TrashDeleteForeverRequest,
    UserCreateRequest,
    UserPasswordChangeRequest,
    UserUpdateRequest,
    VariantMoveRequest,
    VehicleBrandSaveRequest,
    VehicleModelSaveRequest,
    WorkspacePatchRequest,
    VersionGenerationRequest,
)
from app.auth.rbac import can_view_owner_record, require_role
from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import csrf_token_for_session
from app.db.session import get_db
from app.models.enums import Role, StorageStatus
from app.models.tables import (
    FieldAlias,
    BusinessAsset,
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
    get_runner_fee_default,
    import_vehicles_workbook,
    learn_dictionary_value,
    list_template_groups,
    make_template_master,
    save_strategy_settings,
    serialize_special,
    serialize_template,
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
from app.services.storage_retention import purge_expired_pdfs
from app.services.template_assets import (
    _uploaded_assets as uploaded_assets_paged,
    count_uploaded_assets,
    delete_template_asset,
    folder_summary,
    list_template_assets,
    resolve_template_asset,
    upload_template_asset,
)
from app.services.upload_service import serialize_batch
from app.services.upload_intake_service import create_queued_upload
from app.services.job_service import cancel_job, serialize_job
from app.services.session_service import get_session, list_sessions, serialize_session
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
from app.services.road_tax_service import (
    delete_rule as delete_road_tax_rule,
    export_csv_bytes as export_road_tax_csv,
    import_rules as import_road_tax_rules,
    list_rules,
    serialize_rule,
    upsert_rule as upsert_road_tax_rule,
)
from app.services.import_export import parse_tabular, parse_vehicles_workbook
from app.storage.supabase import StorageError, SupabaseStorage
from app.services.business_setup_service import (
    create_benefit_catalog,
    get_catalog_workspace,
    get_business_company_workspace,
    list_benefit_concepts,
    list_business_assets,
    list_business_companies,
    list_company_aliases,
    list_source_documents,
    save_benefit_concept,
    save_business_company,
    save_business_product,
    save_business_tier,
    save_company_alias,
    save_catalog_offering,
    publish_catalog_revision,
    upload_business_asset,
    retire_company_alias,
)
from app.services.worker_health import worker_readiness


logger = logging.getLogger(__name__)

router = APIRouter()


def _set_session_cookie(response: FastAPIResponse, settings: Settings, token: str, max_age: int) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key=getattr(settings, "csrf_cookie_name", "risklocker_csrf"),
        value=csrf_token_for_session(token, settings.auth_hash_secret),
        max_age=max_age,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def _pdf_response(data: bytes, filename: str, range_header: str | None, download: bool) -> Response:
    selected_range = parse_byte_range(range_header, len(data))
    disposition = "attachment" if download else "inline"
    safe_filename = filename.replace('"', "_").replace("\r", "_").replace("\n", "_")
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'{disposition}; filename="{safe_filename}"',
        "Cache-Control": "private, no-store",
    }
    if selected_range:
        start, end = selected_range
        headers["Content-Range"] = f"bytes {start}-{end}/{len(data)}"
        return Response(data[start : end + 1], status_code=206, media_type="application/pdf", headers=headers)
    return Response(data, media_type="application/pdf", headers=headers)


@router.get("/health")
def health(settings: Settings = Depends(settings_dep)) -> dict:
    return {"status": "Ready", "app": settings.app_name}


@router.get("/health/ready")
def readiness(db: Session = Depends(get_db)) -> JSONResponse:
    worker = worker_readiness(db)
    ready = bool(worker["ready"])
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "Ready" if ready else "Unavailable", "checks": {"worker": worker}},
    )


@router.post("/auth/login")
def auth_login(
    payload: LoginRequest,
    request: Request,
    response: FastAPIResponse,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
) -> dict:
    ensure_trusted_origin(request, settings)
    user, session, raw_token = login_with_password(
        db,
        settings,
        payload.email,
        payload.password,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    max_age = int((session.absolute_expires_at - session.last_activity_at).total_seconds())
    _set_session_cookie(response, settings, raw_token, max_age)
    return {"user": serialize_user(user)}


@router.post("/auth/logout")
def auth_logout(
    response: FastAPIResponse,
    auth: AuthContext | None = Depends(current_auth_optional),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
) -> dict:
    if auth is not None:
        revoke_session(db, auth.session, auth.user.id)
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        getattr(settings, "csrf_cookie_name", "risklocker_csrf"),
        path="/",
        secure=settings.session_cookie_secure,
        httponly=False,
        samesite="lax",
    )
    return {"signed_out": True}


@router.get("/auth/me")
def me(user: User = Depends(current_user)) -> dict:
    return {**serialize_user(user), "capabilities": workspace_capabilities(user)}


@router.get("/system/checks")
def system_checks(db: Session = Depends(get_db), settings: Settings = Depends(settings_dep), user: User = Depends(current_user)) -> dict:
    if user.role not in {Role.SUPER_ADMIN.value, Role.ADMIN.value, Role.DEV.value}:
        raise AppError("You do not have permission to view system checks.", 403)
    return {"checks": get_system_checks(settings, db)}


@router.post("/users")
def user_create(payload: UserCreateRequest, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    created = create_user(db, user, payload.email, payload.role, password=payload.password)
    return serialize_user(created)


@router.get("/users")
def users_list(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    if user.role not in {Role.SUPER_ADMIN.value, Role.ADMIN.value}:
        raise AppError("You do not have permission to view users.", 403)
    query = select(User).order_by(User.created_at.desc())
    if user.role == Role.ADMIN.value:
        query = query.where(User.role != Role.SUPER_ADMIN.value)
    return {"users": [serialize_user(item) for item in db.scalars(query).all()]}


@router.patch("/users/{user_id}")
def users_update(user_id: str, payload: UserUpdateRequest, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    target = db.get(User, user_id)
    if not target:
        raise AppError("User not found.", 404)
    updated = update_user(
        db,
        user,
        target,
        email=payload.email,
        role=payload.role,
        status=payload.status,
        password=payload.password,
    )
    return serialize_user(updated)


@router.post("/users/{user_id}/sessions/revoke")
def user_sessions_revoke(user_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    if user.role not in {Role.SUPER_ADMIN.value, Role.ADMIN.value}:
        raise AppError("You do not have permission to revoke sessions.", 403)
    target = db.get(User, user_id)
    if not target:
        raise AppError("User not found.", 404)
    if user.role == Role.ADMIN.value and target.role == Role.SUPER_ADMIN.value:
        raise AppError("You do not have permission to revoke the super administrator's sessions.", 403)
    return {"revoked_sessions": revoke_user_sessions(db, target.id, user.id)}


@router.post("/auth/change-password")
def auth_change_password(payload: UserPasswordChangeRequest, auth: AuthContext = Depends(current_auth), db: Session = Depends(get_db)) -> dict:
    updated = change_password(db, auth.user, payload.current_password, payload.new_password)
    return {"user": serialize_user(updated)}


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
def sessions_list(search: str | None = None, limit: int = 25, offset: int = 0, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    sessions, total = list_sessions(db, user.id, search=search, limit=min(max(limit, 1), 100), offset=max(offset, 0))
    return {"sessions": [serialize_session(s) for s in sessions], "total": total}


@router.get("/sessions/{session_id}")
def session_detail(session_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    session = get_session(db, session_id)
    return {"session": serialize_session(session)}


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
    return {"template": get_workspace_template_config(db, user, session_id)}


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
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    result = request_version_generation(
        db,
        user,
        session_id,
        draft_revision=payload.draft_revision,
        idempotency_key=idempotency_key,
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


@router.delete("/business/company-aliases/{alias_id}", status_code=status.HTTP_204_NO_CONTENT)
def business_company_alias_retire(
    alias_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Response:
    retire_company_alias(db, user, alias_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/business/companies")
def business_company_save(
    payload: BusinessCompanySaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"company": save_business_company(db, user, payload.model_dump(exclude_none=True))}


@router.get("/business/companies/{company_id}/workspace")
def business_company_workspace(
    company_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"workspace": get_business_company_workspace(db, user, company_id)}


@router.post("/business/products")
def business_product_save(
    payload: BusinessProductSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"product": save_business_product(db, user, payload.model_dump(exclude_none=True))}


@router.post("/business/tiers")
def business_tier_save(
    payload: BusinessTierSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"tier": save_business_tier(db, user, payload.model_dump(exclude_none=True))}


@router.get("/business/benefit-concepts")
def business_benefit_concepts(
    search: str = Query(default="", max_length=200),
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
        )
    }


@router.post("/business/benefit-concepts")
def business_benefit_concept_save(
    payload: BenefitConceptSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"benefit_concept": save_benefit_concept(db, user, payload.model_dump(exclude_none=True))}


@router.get("/business/assets")
def business_assets(
    search: str = Query(default="", max_length=200),
    kind: str | None = Query(default=None, max_length=40),
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
            page=page,
            page_size=page_size,
        )
    }


@router.get("/business/assets/{asset_id}/content")
def business_asset_content(
    asset_id: str,
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
    try:
        data = SupabaseStorage(settings).download_bytes(storage_path)
    except StorageError as exc:
        raise AppError("Asset content is unavailable.", 503) from exc
    return Response(
        data,
        media_type=content_type,
        headers={
            "Cache-Control": "private, max-age=86400, immutable",
            "ETag": f'"{str((item or {}).get("content_hash") or asset.content_hash)}"',
        },
    )


@router.post("/business/assets")
async def business_asset_upload(
    file: UploadFile = File(...),
    label: str = Form(...),
    kind: str = Form(...),
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
        )
    except StorageError as exc:
        raise AppError("Asset storage is unavailable. Retry without changing the file.", 503) from exc
    return {"asset": asset}


@router.post("/business/catalogs")
def business_catalog_create(
    payload: BenefitCatalogSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"catalog": create_benefit_catalog(db, user, payload.model_dump(exclude_none=True))}


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


@router.post("/business/catalogs/{catalog_id}/publish")
def business_catalog_publish(
    catalog_id: str,
    payload: CatalogPublishRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"catalog": publish_catalog_revision(db, user, catalog_id, base_revision=payload.base_revision)}


@router.get("/business/catalogs/{catalog_id}/workspace")
def business_catalog_workspace(
    catalog_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"workspace": get_catalog_workspace(db, user, catalog_id)}


@router.get("/business/sources")
def business_sources(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return {"sources": list_source_documents(db, user, page=page, page_size=page_size)}


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
    return {
        "template": serialize_template(template, db),
        "template_revision": serialize_template_revision(db, revision),
    }


@router.get("/admin/templates")
def admin_templates(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF)
    return {
        "templates": [
            serialize_template(item, db)
            for item in db.scalars(
                select(OutputTemplateConfig).where(OutputTemplateConfig.deleted_at.is_(None)).order_by(OutputTemplateConfig.name)
            ).all()
        ]
    }


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
    try:
        record = upload_template_asset(db, settings, user, file.filename, file.content_type, data, label=label, folder=folder)
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


@router.get("/settings/limits")
def settings_limits(
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> dict:
    return {
        "max_upload_files": 1,
        "max_upload_bytes": settings.max_upload_bytes,
        "max_source_pdf_bytes": settings.max_source_pdf_bytes,
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
