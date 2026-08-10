"""Application API routes."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Header, Query, Request, Response as FastAPIResponse, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import AuthContext, current_auth, current_auth_optional, current_user, ensure_trusted_origin, settings_dep
from app.api.schemas import (
    BulkClientRecordDeleteRequest,
    BulkUploadedFileDeleteRequest,
    ClientRecordUpdateRequest,
    CompanySaveRequest,
    DraftGenerateRequest,
    DraftUpdateRequest,
    ExtractionSettingsRequest,
    FieldAliasSaveRequest,
    GenerateSelectedRequest,
    LoginRequest,
    OurSpecialSaveRequest,
    OurSpecialVariantSaveRequest,
    RoadTaxRuleSaveRequest,
    TemplateSaveRequest,
    TemplateUpdateRequest,
    TrashDeleteForeverRequest,
    UserCreateRequest,
    UserPasswordChangeRequest,
    UserUpdateRequest,
    VariantMoveRequest,
    VehicleBrandSaveRequest,
    VehicleModelSaveRequest,
)
from app.auth.rbac import can_view_owner_record, require_role
from app.core.config import Settings
from app.core.errors import AppError
from app.db.session import get_db
from app.models.enums import Role, StorageStatus
from app.models.tables import (
    FieldAlias,
    GeneratedPdfVersion,
    InsuranceCompany,
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
    delete_vehicle_brand,
    delete_vehicle_model,
    save_strategy_settings,
    serialize_special,
    serialize_template,
    update_template,
    upsert_company,
    upsert_field_alias,
    upsert_special,
    upsert_template,
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
from app.services.pdf_service import generate_pdf
from app.services.pdf_content import load_pdf_bytes, parse_byte_range
from app.services.review_service import (
    get_accessible_draft,
    list_history,
    move_to_trash,
    purge_expired_trash,
    restore_from_trash,
    serialize_draft,
    update_draft_fields,
)
from app.services.system_checks import get_system_checks
from app.services.storage_retention import purge_expired_pdfs
from app.services.template_assets import delete_template_asset, list_template_assets, resolve_template_asset, upload_template_asset
from app.services.upload_service import create_batch_from_uploads, serialize_batch, serialize_file
from app.services.session_service import get_session, list_sessions, serialize_session
from app.services.client_record_service import export_csv_bytes, get_record, list_records, serialize_record, update_record
from app.services.road_tax_service import delete_rule as delete_road_tax_rule, list_rules, serialize_rule, upsert_rule as upsert_road_tax_rule
from app.storage.supabase import StorageError, SupabaseStorage


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
    return {"signed_out": True}


@router.get("/auth/me")
def me(user: User = Depends(current_user)) -> dict:
    return serialize_user(user)


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
    batch = await create_batch_from_uploads(db, settings, user.id, files, enhanced_reading)
    from app.models.tables import Session as SessionModel
    from app.services.session_service import serialize_session
    sessions = [
        serialize_session(s)
        for s in db.scalars(
            select(SessionModel).where(
                SessionModel.uploaded_file_id.in_([f.id for f in batch.files if not f.deleted_at])
            )
        ).all()
    ]
    return {"batch": serialize_batch(batch), "sessions": sessions}


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
    )
    return {"draft": serialize_draft(draft, db)}


@router.post("/drafts/{draft_id}/generate")
def draft_generate(draft_id: str, payload: DraftGenerateRequest | None = None, db: Session = Depends(get_db), settings: Settings = Depends(settings_dep), user: User = Depends(current_user)) -> dict:
    draft = get_accessible_draft(db, user, draft_id)
    version = generate_pdf(db, settings, user, draft, acknowledge_check_needed=bool((payload or DraftGenerateRequest()).acknowledge_check_needed))
    return {
        "version": {
            "id": version.id,
            "filename": version.filename,
            "version_number": version.version_number,
            "download_url": f"/generated-versions/{version.id}/content?download=true",
        }
    }


@router.post("/drafts/{draft_id}/preview-png")
def draft_preview_png(draft_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> Response:
    from app.rendering.template_renderer import render_quotation_html
    from app.models.tables import OutputTemplateConfig
    from app.services.template_config import normalize_template_config
    from app.core.errors import AppError
    import tempfile
    from pathlib import Path

    draft = get_accessible_draft(db, user, draft_id)
    if not draft.uploaded_file or not draft.uploaded_file.template_id:
        raise AppError("No template assigned.", 400)
    template = db.get(OutputTemplateConfig, draft.uploaded_file.template_id)
    if not template:
        raise AppError("Template not found.", 404)
    config = normalize_template_config(template.fixed_fields, template.name)
    html = render_quotation_html(
        draft.fields, template_name=template.name,
        template_config=config,
        insurer_name=(draft.fields.get("insurance_company") or {}).get("value"),
        db=db,
    )
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 794, "height": 1123})
            page.set_content(html, wait_until="networkidle")
            png = page.screenshot(type="png", full_page=False)
            browser.close()
        return Response(png, media_type="image/png")
    except Exception as exc:
        raise AppError(f"Preview generation failed: {exc.__class__.__name__}", 500) from exc


@router.post("/drafts/generate-selected")
def generate_selected(payload: GenerateSelectedRequest, db: Session = Depends(get_db), settings: Settings = Depends(settings_dep), user: User = Depends(current_user)) -> dict:
    versions = []
    for draft_id in payload.draft_ids:
        draft = get_accessible_draft(db, user, draft_id)
        version = generate_pdf(db, settings, user, draft, acknowledge_check_needed=payload.acknowledge_check_needed)
        versions.append({"id": version.id, "filename": version.filename, "download_url": f"/generated-versions/{version.id}/content?download=true"})
    return {"versions": versions}


@router.get("/sessions")
def sessions_list(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    sessions = list_sessions(db, user.id)
    return {"sessions": [serialize_session(s) for s in sessions]}


@router.get("/sessions/{session_id}")
def session_detail(session_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    session = get_session(db, session_id)
    return {"session": serialize_session(session)}


@router.get("/client-records")
def client_records_list(
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    records = list_records(db, search=search, date_from=date_from, date_to=date_to, sort_by=sort_by, sort_dir=sort_dir)
    return {"records": [serialize_record(r) for r in records]}


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


@router.get("/history")
def history(status: str | None = None, search: str | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    from app.models.tables import Session as SessionModel
    files = list_history(db, user, status, search)
    file_ids = [f.id for f in files]
    session_map = {}
    if file_ids:
        for s in db.scalars(select(SessionModel).where(SessionModel.uploaded_file_id.in_(file_ids))).all():
            session_map[s.uploaded_file_id] = s.id
    return {
        "records": [
            {**serialize_file(file), "session_id": session_map.get(file.id)}
            for file in files
        ]
    }


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
def trash_purge(db: Session = Depends(get_db), settings: Settings = Depends(settings_dep), user: User = Depends(current_user)) -> dict:
    from app.services.trash_service import purge_all_expired
    purged = purge_expired_trash(db, user, SupabaseStorage(settings))
    return {"purged": purged + purge_all_expired(db)}


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


@router.get("/admin/templates")
def admin_templates(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
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
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    from app.services.trash_service import delete_template
    delete_template(db, settings, user, template_id)
    return {"deleted": True}


@router.get("/admin/template-assets")
def admin_template_assets(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    return {"assets": list_template_assets(db)}


@router.post("/admin/template-assets")
async def admin_template_asset_upload(
    file: UploadFile = File(...),
    label: str | None = Form(None),
    folder: str | None = Form(None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
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
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    from app.services.trash_service import delete_template_asset
    delete_template_asset(db, settings, user, asset_id)
    return {"deleted": True}


@router.get("/admin/templates/{template_id}")
def admin_template_detail(template_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)
    template = db.get(OutputTemplateConfig, template_id)
    if not template:
        raise AppError("Template not found.", 404)
    return {"template": serialize_template(template, db)}


@router.post("/admin/templates/{template_id}/copy")
def admin_template_copy(template_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    template = copy_template(db, user, template_id)
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
    if not user or user.role not in {Role.SUPER_ADMIN.value, Role.ADMIN.value, Role.DEV.value}:
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


@router.get("/settings/limits")
def settings_limits(
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> dict:
    return {
        "max_upload_files": settings.max_upload_files,
        "max_upload_bytes": settings.max_upload_bytes,
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
            "retention_days": settings.pdf_retention_days,
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
    return purge_expired_pdfs(db, SupabaseStorage(settings))


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
