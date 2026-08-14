"""Freeze an exact reviewed revision and enqueue one immutable PDF generation."""

from __future__ import annotations

import base64
import hashlib
import mimetypes
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, text

from app.core.errors import AppError
from app.models.tables import (
    AuditEvent,
    BenefitConcept,
    BenefitFacet,
    BenefitRelation,
    BusinessAsset,
    CatalogOffering,
    DraftBenefitSelection,
    DraftSourceLineDecision,
    GeneratedPdfVersion,
    InsuranceCompany,
    Job,
    OutputTemplateConfig,
    QuotationDraft,
    RenderSnapshot,
    Session,
    TemplateAsset,
    TemplatePageProfile,
    TemplateRevision,
    new_id,
)
from app.rendering.render_context import (
    RenderContextError,
    canonical_context_hash,
    resolve_benefit_cards,
)
from app.services.template_assets import resolve_template_asset
from app.services.template_revision_service import validate_template_config
from app.services.workspace_service import BUSINESS_ROLES, generation_blockers
from app.storage.supabase import StorageError, SupabaseStorage
from app.rendering.template_renderer import render_quotation_html


RENDERER_VERSION = "risklocker-v7.1"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _rows(db, model) -> list:
    return list(db.scalars(select(model)).all())


def _for_draft(db, model, draft_id: str) -> list:
    return [item for item in _rows(db, model) if item.draft_id == draft_id]


def _idempotency_key(value: str) -> str:
    key = str(value or "").strip()
    if not key or len(key) > 160:
        raise AppError("A non-empty idempotency key of at most 160 characters is required.", 422)
    return key


def _existing_request(db, user, draft: QuotationDraft, key: str, revision: int) -> dict | None:
    for version in _for_draft(db, GeneratedPdfVersion, draft.id):
        if version.idempotency_key == key:
            if version.draft_revision != revision:
                raise AppError("This idempotency key belongs to another draft revision.", 409)
            return {"created": False, "job": None, "version": version}
    for job in _rows(db, Job):
        if job.job_type != "render_pdf" or job.idempotency_key != key:
            continue
        if job.owner_id != user.id:
            raise AppError("This idempotency key is already in use.", 409)
        payload = job.payload or {}
        if job.session_id != getattr(draft, "_generation_session_id", job.session_id) or int(payload.get("draft_revision") or 0) != revision:
            raise AppError("This idempotency key belongs to another generation request.", 409)
        return {"created": False, "job": job, "version": None}
    return None


def _template_config(draft: QuotationDraft, revision: TemplateRevision, page: TemplatePageProfile) -> dict:
    exact_override = (
        draft.layout_override is not None
        and draft.layout_override_template_id == revision.template_id
        and draft.layout_override_template_revision_id == revision.id
        and draft.layout_override_base_hash == revision.config_hash
    )
    config = deepcopy(draft.layout_override if exact_override else revision.config)
    config.setdefault("version", 7 if revision.state == "published" else 2)
    config.setdefault("page_profile", {
        "profile_key": page.profile_key,
        "name": page.name,
        "width": float(page.width),
        "height": float(page.height),
        "unit": page.unit,
        "safe_margins": deepcopy(page.safe_margins or {}),
        "bleed": deepcopy(page.bleed or {}),
        "background_behavior": page.background_behavior,
    })
    canvas = config.setdefault("canvas", {})
    canvas.setdefault("width", float(page.width))
    canvas.setdefault("height", float(page.height))
    canvas.setdefault("elements", [])
    try:
        return validate_template_config(config, compatibility=revision.state == "compatibility")
    except ValueError as exc:
        raise AppError(f"The selected template revision is invalid: {exc}", 409) from exc


def _catalog_rows(db, draft: QuotationDraft) -> tuple[list, list, list, list]:
    if not draft.catalog_revision_id:
        return [], [], [], []
    offerings = [
        item for item in _rows(db, CatalogOffering)
        if item.catalog_revision_id == draft.catalog_revision_id
    ]
    offering_ids = {item.id for item in offerings}
    concept_ids = {item.concept_id for item in offerings}
    concepts = [item for item in _rows(db, BenefitConcept) if item.id in concept_ids]
    relations = [
        item for item in _rows(db, BenefitRelation)
        if item.catalog_revision_id == draft.catalog_revision_id
        and item.from_offering_id in offering_ids
        and item.to_offering_id in offering_ids
    ]
    facets = [item for item in _rows(db, BenefitFacet) if item.parent_concept_id in concept_ids]
    return offerings, concepts, relations, facets


def _referenced_asset_ids(config: dict, cards: dict) -> set[str]:
    asset_ids = {str(item) for item in (config.get("assets") or {}).values() if item}
    for element in (config.get("canvas") or {}).get("elements") or []:
        if element.get("assetId"):
            asset_ids.add(str(element["assetId"]))
    for collection in cards.values():
        for card in collection:
            if card.get("asset_id"):
                asset_ids.add(str(card["asset_id"]))
    return asset_ids


def _snapshot_assets(db, config: dict, cards: dict, draft: QuotationDraft) -> tuple[dict, dict, dict]:
    config = deepcopy(config)
    if draft.company_id:
        company = db.get(InsuranceCompany, draft.company_id)
        if company and company.logo_asset_id:
            config.setdefault("assets", {})["insurer_logo"] = company.logo_asset_id

    manifest: dict[str, dict] = {}
    embedded: dict[str, str] = {}
    hashes: dict[str, str] = {}
    for asset_id in sorted(_referenced_asset_ids(config, cards)):
        business = db.get(BusinessAsset, asset_id)
        if business:
            derivative = (business.derivative_manifest or {}).get("pdf") or {}
            content_hash = str(derivative.get("content_hash") or business.content_hash)
            manifest[asset_id] = {
                "storage_path": str(derivative.get("storage_path") or business.storage_path),
                "content_type": str(derivative.get("content_type") or business.content_type),
                "content_hash": content_hash,
            }
            hashes[asset_id] = content_hash
            continue
        legacy = db.get(TemplateAsset, asset_id)
        if legacy and legacy.storage_path and legacy.storage_sha256:
            manifest[asset_id] = {
                "storage_path": legacy.storage_path,
                "content_type": legacy.content_type,
                "content_hash": legacy.storage_sha256,
            }
            hashes[asset_id] = legacy.storage_sha256
            continue
        try:
            resolved = resolve_template_asset(None, asset_id)
        except FileNotFoundError as exc:
            raise AppError("A template or benefit asset required for rendering is unavailable.", 409) from exc
        if not isinstance(resolved, Path):
            raise AppError("A template asset could not be frozen for rendering.", 409)
        data = resolved.read_bytes()
        content_hash = hashlib.sha256(data).hexdigest()
        content_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        embedded[asset_id] = f"data:{content_type};base64,{base64.b64encode(data).decode('ascii')}"
        hashes[asset_id] = content_hash
    return config, {"manifest": manifest, "embedded": embedded}, hashes


def build_render_snapshot_context(db, draft: QuotationDraft, revision: TemplateRevision) -> tuple[dict, dict]:
    page = db.get(TemplatePageProfile, revision.page_profile_id)
    template = db.get(OutputTemplateConfig, revision.template_id)
    if not page or not template:
        raise AppError("The selected template revision is incomplete.", 409)
    uploaded = db.get(__import__("app.models.tables", fromlist=["UploadedFile"]).UploadedFile, draft.uploaded_file_id)
    if not uploaded:
        raise AppError("The quotation source record is unavailable.", 409)
    selections = _for_draft(db, DraftBenefitSelection, draft.id)
    offerings, concepts, relations, facets = _catalog_rows(db, draft)
    try:
        cards = resolve_benefit_cards(
            selections=selections,
            offerings=offerings,
            concepts=concepts,
            relations=relations,
            facets=facets,
        )
    except RenderContextError as exc:
        raise AppError(str(exc), 409) from exc
    config = _template_config(draft, revision, page)
    config, assets, asset_hashes = _snapshot_assets(db, config, cards, draft)
    context = {
        "schema_version": 1,
        "renderer_version": RENDERER_VERSION,
        "draft_id": draft.id,
        "draft_revision": draft.revision,
        "catalog_revision_id": draft.catalog_revision_id,
        "template_revision_id": revision.id,
        "template_revision_number": revision.revision_number,
        "template_name": template.name,
        "source_filename": uploaded.original_filename,
        "fields": deepcopy(draft.fields or {}),
        "template_config": config,
        "page_profile": deepcopy(config["page_profile"]),
        "current_benefits": cards["current_benefits"],
        "available_addons": cards["available_addons"],
        "assets": assets,
    }
    return context, asset_hashes


def request_version_generation(
    db,
    user,
    session_id: str,
    *,
    draft_revision: int,
    idempotency_key: str,
) -> dict:
    if user.role not in BUSINESS_ROLES:
        raise AppError("You do not have permission to generate quotation PDFs.", 403)
    key = _idempotency_key(idempotency_key)
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"), {"lock_key": f"render_pdf:{key}"})
    session = db.get(Session, session_id)
    if not session:
        raise AppError("Session not found.", 404)
    draft = db.get(QuotationDraft, session.draft_id)
    if not draft or draft.deleted_at:
        raise AppError("Quotation not found.", 404)
    draft._generation_session_id = session.id
    existing = _existing_request(db, user, draft, key, draft_revision)
    if existing:
        return existing
    if draft.revision != draft_revision:
        raise AppError("The quotation changed. Save and review the latest revision before generating.", 409)
    revision = db.get(TemplateRevision, draft.template_revision_id) if draft.template_revision_id else None
    decisions = _for_draft(db, DraftSourceLineDecision, draft.id)
    selections = _for_draft(db, DraftBenefitSelection, draft.id)
    blockers = generation_blockers(draft, decisions, selections, template_revision=revision)
    if blockers:
        raise AppError("Resolve every generation blocker before creating the PDF.", 409)
    if not revision:
        raise AppError("Choose a published template before generating.", 409)

    context, asset_hashes = build_render_snapshot_context(db, draft, revision)
    context_hash = canonical_context_hash(context)
    snapshot = next(
        (item for item in _rows(db, RenderSnapshot) if item.context_hash == context_hash),
        None,
    )
    if snapshot is None:
        snapshot = RenderSnapshot(
            id=new_id(),
            draft_id=draft.id,
            draft_revision=draft.revision,
            catalog_revision_id=draft.catalog_revision_id,
            template_revision_id=revision.id,
            context_hash=context_hash,
            context=context,
            asset_hashes=asset_hashes,
            renderer_version=RENDERER_VERSION,
        )
        db.add(snapshot)
        db.flush()
    job = Job(
        id=new_id(),
        owner_id=user.id,
        session_id=session.id,
        uploaded_file_id=draft.uploaded_file_id,
        job_type="render_pdf",
        idempotency_key=key,
        state="queued",
        priority=100,
        payload={
            "render_snapshot_id": snapshot.id,
            "draft_id": draft.id,
            "draft_revision": draft.revision,
            "idempotency_key": key,
        },
        result={},
        safe_error={},
        progress=0,
        attempt=0,
        max_attempts=3,
        available_at=_utcnow(),
    )
    db.add(job)
    db.add(AuditEvent(
        id=new_id(),
        actor_id=user.id,
        action="quotation.generation_requested",
        entity_type="quotation_draft",
        entity_id=draft.id,
        details={
            "draft_revision": draft.revision,
            "template_revision_id": revision.id,
            "catalog_revision_id": draft.catalog_revision_id,
            "context_hash": context_hash,
            "job_id": job.id,
        },
    ))
    db.commit()
    return {"created": True, "job": job, "version": None}


def request_preview_render(db, user, session_id: str, *, draft_revision: int) -> RenderSnapshot:
    """Freeze or reuse the exact saved context used by final PDF generation."""

    if user.role not in BUSINESS_ROLES:
        raise AppError("You do not have permission to preview quotations.", 403)
    session = db.get(Session, session_id)
    if not session:
        raise AppError("Session not found.", 404)
    draft = db.get(QuotationDraft, session.draft_id)
    if not draft or draft.deleted_at:
        raise AppError("Quotation not found.", 404)
    if draft.revision != draft_revision:
        raise AppError("The quotation changed. Save the latest revision before previewing.", 409)
    revision = db.get(TemplateRevision, draft.template_revision_id) if draft.template_revision_id else None
    decisions = _for_draft(db, DraftSourceLineDecision, draft.id)
    selections = _for_draft(db, DraftBenefitSelection, draft.id)
    if generation_blockers(draft, decisions, selections, template_revision=revision):
        raise AppError("Resolve every generation blocker before rendering the final preview.", 409)
    if not revision:
        raise AppError("Choose a published template before previewing.", 409)
    context, asset_hashes = build_render_snapshot_context(db, draft, revision)
    context_hash = canonical_context_hash(context)
    snapshot = next((item for item in _rows(db, RenderSnapshot) if item.context_hash == context_hash), None)
    if snapshot is None:
        snapshot = RenderSnapshot(
            id=new_id(), draft_id=draft.id, draft_revision=draft.revision,
            catalog_revision_id=draft.catalog_revision_id, template_revision_id=revision.id,
            context_hash=context_hash, context=context, asset_hashes=asset_hashes,
            renderer_version=RENDERER_VERSION,
        )
        db.add(snapshot)
        db.commit()
    return snapshot


def _resolve_preview_assets(snapshot: RenderSnapshot, storage: SupabaseStorage) -> dict[str, str]:
    assets = snapshot.context.get("assets") or {}
    resolved = dict(assets.get("embedded") or {})
    for asset_id, item in sorted((assets.get("manifest") or {}).items()):
        try:
            data = storage.download_bytes(str(item.get("storage_path") or ""))
        except StorageError as exc:
            raise AppError("A frozen preview asset is temporarily unavailable.", 503) from exc
        expected = str(item.get("content_hash") or "")
        if hashlib.sha256(data).hexdigest() != expected:
            raise AppError("A frozen preview asset failed its integrity check.", 503)
        resolved[asset_id] = f"data:{item.get('content_type') or 'application/octet-stream'};base64,{base64.b64encode(data).decode('ascii')}"
    return resolved


def render_snapshot_preview_html(db, user, snapshot_id: str, settings) -> str:
    if user.role not in BUSINESS_ROLES:
        raise AppError("You do not have permission to preview quotations.", 403)
    snapshot = db.get(RenderSnapshot, snapshot_id)
    if not snapshot or canonical_context_hash(snapshot.context) != snapshot.context_hash:
        raise AppError("Preview not found.", 404)
    context = snapshot.context
    resolved = _resolve_preview_assets(snapshot, SupabaseStorage(settings))
    return render_quotation_html(
        context.get("fields") or {},
        template_name=str(context.get("template_name") or "Risklocker Quotation"),
        template_config=context.get("template_config") or {},
        render_context={
            "current_benefits": context.get("current_benefits") or [],
            "available_addons": context.get("available_addons") or [],
        },
        resolved_assets=resolved,
    )
