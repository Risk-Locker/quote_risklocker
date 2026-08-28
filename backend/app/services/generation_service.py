"""Freeze an exact reviewed revision and enqueue one immutable PDF generation."""

from __future__ import annotations

import base64
import hashlib
import mimetypes
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm.attributes import flag_modified

from app.core.errors import AppError
from app.models.tables import (
    AuditEvent,
    BenefitConcept,
    BenefitFacet,
    BenefitPackage,
    BenefitPackagePlan,
    BenefitRelation,
    BusinessAsset,
    CatalogOffering,
    BenefitCatalogRevision,
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
    adjusted_total_text,
    build_extras,
    canonical_context_hash,
    format_money_amount,
    resolve_benefit_cards,
)
from app.services.template_assets import resolve_template_asset
from app.services.template_revision_service import validate_template_config
from app.services.workspace_service import BUSINESS_ROLES, generation_blockers
from app.storage.supabase import StorageError, SupabaseStorage
from app.rendering.template_renderer import _balance_benefit_grid_elements, render_quotation_html


RENDERER_VERSION = "risklocker-v7.1"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _rows(db, model) -> list:
    return list(db.scalars(select(model)).all())


def _for_draft(db, model, draft_id: str) -> list:
    return list(db.scalars(select(model).where(model.draft_id == draft_id)).all())


def _field_text(fields: dict, name: str) -> str:
    raw = (fields or {}).get(name)
    value = raw.get("value") if isinstance(raw, dict) else raw
    return str(value or "").strip()


def _idempotency_key(value: str) -> str:
    key = (value or "").strip()
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
    raw_config = draft.layout_override if exact_override else revision.config
    config: dict = deepcopy(raw_config) if raw_config is not None else {}
    config.setdefault("version", 7 if revision.state == "published" else 2)
    page_w = float(str(page.width)) if page.width is not None else 595.28
    page_h = float(str(page.height)) if page.height is not None else 841.89
    config.setdefault("page_profile", {
        "profile_key": page.profile_key,
        "name": page.name,
        "width": page_w,
        "height": page_h,
        "unit": page.unit,
        "safe_margins": deepcopy(page.safe_margins or {}),
        "bleed": deepcopy(page.bleed or {}),
        "background_behavior": page.background_behavior,
    })
    canvas = config.setdefault("canvas", {})
    if isinstance(canvas, dict):
        canvas.setdefault("width", page_w)
        canvas.setdefault("height", page_h)
        canvas.setdefault("elements", [])
        preset_id = None
        if draft.fields and isinstance(draft.fields, dict):
            raw_p = draft.fields.get("benefit_preset")
            preset_id = raw_p.get("value") if isinstance(raw_p, dict) else raw_p
        if preset_id:
            for el in canvas.get("elements") or []:
                if el.get("type") == "benefit-grid":
                    el["benefitPreset"] = str(preset_id)
                    if preset_id == "compact-minimal":
                        el["layoutMode"] = "masonry"
                        el["columns"] = 3
                        el["cardStyle"] = "minimal"
                        el["textDensity"] = "compact"
                    elif preset_id == "signature-2col":
                        el["layoutMode"] = "normal"
                        el["columns"] = 2
                        el["cardStyle"] = "standard"
                        el["textDensity"] = "normal"
                    elif preset_id == "elevated-3d":
                        el["layoutMode"] = "masonry"
                        el["columns"] = 3
                        el["cardStyle"] = "soft"
                    elif preset_id == "grid-tile":
                        el["layoutMode"] = "masonry"
                        el["columns"] = 3
                        el["cardStyle"] = "outlined"
                    elif preset_id == "dark-signature":
                        el["layoutMode"] = "masonry"
                        el["columns"] = 3
                        el["cardStyle"] = "standard"
    try:
        return validate_template_config(config, compatibility=revision.state == "compatibility")
    except ValueError as exc:
        raise AppError(f"The selected template revision is invalid: {exc}", 409) from exc


def _catalog_rows(db, draft: QuotationDraft) -> tuple[list, list, list, list, list]:
    if not draft.catalog_revision_id:
        return [], [], [], [], []
    offerings = list(
        db.scalars(
            select(CatalogOffering).where(CatalogOffering.catalog_revision_id == draft.catalog_revision_id)
        ).all()
    )
    offering_ids = {item.id for item in offerings}
    concept_ids = {item.concept_id for item in offerings}
    concepts = (
        list(db.scalars(select(BenefitConcept).where(BenefitConcept.id.in_(concept_ids))).all())
        if concept_ids
        else []
    )
    relations = (
        list(
            db.scalars(
                select(BenefitRelation).where(
                    BenefitRelation.catalog_revision_id == draft.catalog_revision_id,
                    BenefitRelation.from_offering_id.in_(offering_ids),
                    BenefitRelation.to_offering_id.in_(offering_ids),
                )
            ).all()
        )
        if offering_ids
        else []
    )
    facets = (
        list(db.scalars(select(BenefitFacet).where(BenefitFacet.parent_concept_id.in_(concept_ids))).all())
        if concept_ids
        else []
    )
    package_ids = {
        item.id
        for item in db.scalars(
            select(BenefitPackage).where(BenefitPackage.catalog_revision_id == draft.catalog_revision_id)
        ).all()
    }
    plans = (
        list(db.scalars(select(BenefitPackagePlan).where(BenefitPackagePlan.package_id.in_(package_ids))).all())
        if package_ids
        else []
    )
    return offerings, concepts, relations, facets, plans


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
    offerings, concepts, relations, facets, plans = _catalog_rows(db, draft)
    from app.services.formula_evaluator import extract_evaluation_context
    from app.services.benefit_catalog_matrix import get_catalog_for_product
    from app.services.workspace_service import _workspace_extracted_benefits_section
    
    # Needs to be called with db, draft, decisions (empty list is fine for generation), selections
    extras_section = _workspace_extracted_benefits_section(db, draft, [], selections)
    eval_context = extract_evaluation_context(draft.fields or {}, extras_section.get("extras", []))
    insurer_key = str(getattr(draft.company, "company_key", "") or "etiqa") if hasattr(draft, "company") and draft.company else "etiqa"
    product_type = str(getattr(draft.product, "name", "private_car") or "private_car") if hasattr(draft, "product") and draft.product else "private_car"
    insurer_catalog = get_catalog_for_product(insurer_key, product_type)

    try:
        cards = resolve_benefit_cards(
            selections=selections,
            offerings=offerings,
            concepts=concepts,
            relations=relations,
            facets=facets,
            plans=plans,
            eval_context=eval_context,
            insurer_catalog=insurer_catalog,
        )
    except RenderContextError as exc:
        raise AppError(str(exc), 409) from exc
    config = _template_config(draft, revision, page)
    config, assets, asset_hashes = _snapshot_assets(db, config, cards, draft)
    extras = build_extras(selections, concepts, offerings)
    fields = deepcopy(draft.fields or {})
    adjusted_total = adjusted_total_text(fields, extras)
    fields["total_premium_adjusted"] = {
        "value": adjusted_total if adjusted_total else _field_text(fields, "total_amount"),
        "status": "ready",
        "message": "",
    }
    canvas = config.get("canvas") or {}
    raw_elements = canvas.get("elements") or []
    render_ctx = {
        "current_benefits": cards["current_benefits"],
        "available_addons": cards["available_addons"],
        "extras": extras,
    }
    balanced = _balance_benefit_grid_elements(raw_elements, render_ctx)
    max_element_y = max((float(e.get("y") or 0) + float(e.get("h") or 0) for e in balanced), default=0.0)
    base_height = float(config.get("page_profile", {}).get("height") or 1123.0)
    if max_element_y + 30.0 > base_height:
        config["page_profile"]["height"] = float(int(max_element_y + 30.0))

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
        "fields": fields,
        "template_config": config,
        "page_profile": deepcopy(config["page_profile"]),
        "current_benefits": cards["current_benefits"],
        "available_addons": cards["available_addons"],
        "groups": cards.get("groups", []),
        "extras": extras,
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
    if draft.revision != draft_revision:
        raise AppError("The quotation changed. Save the latest revision before generating.", 409)
    existing = _existing_request(db, user, draft, key, draft_revision)
    if existing:
        return existing
    revision = db.get(TemplateRevision, draft.template_revision_id) if draft.template_revision_id else None
    if not revision:
        revision = db.scalars(
            select(TemplateRevision)
            .where(TemplateRevision.state.in_(["published", "compatibility"]))
            .order_by(TemplateRevision.revision_number.desc())
        ).first()
        if revision:
            draft.template_revision_id = revision.id
    if not draft.catalog_revision_id:
        active_cat = db.scalars(
            select(BenefitCatalogRevision)
            .where(BenefitCatalogRevision.state.in_(["published", "compatibility"]))
            .order_by(BenefitCatalogRevision.revision_number.desc())
        ).first()
        if active_cat:
            draft.catalog_revision_id = active_cat.id

    decisions = _for_draft(db, DraftSourceLineDecision, draft.id)
    selections = _for_draft(db, DraftBenefitSelection, draft.id)
    blockers = generation_blockers(draft, decisions, selections, template_revision=revision)
    fatal_blockers = [b for b in blockers if b.get("code") not in {"scalar_check_needed", "missing_catalog"}]
    if fatal_blockers:
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
    if not revision:
        revision = db.scalars(
            select(TemplateRevision)
            .where(TemplateRevision.state.in_(["published", "compatibility"]))
            .order_by(TemplateRevision.revision_number.desc())
        ).first()
        if revision:
            draft.template_revision_id = revision.id
    decisions = _for_draft(db, DraftSourceLineDecision, draft.id)
    selections = _for_draft(db, DraftBenefitSelection, draft.id)
    fatal_blockers = [
        b for b in generation_blockers(draft, decisions, selections, template_revision=revision)
        if b.get("code") not in {"scalar_check_needed", "missing_catalog"}
    ]
    if fatal_blockers:
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
            "groups": context.get("groups") or [],
            "extras": context.get("extras") or [],
            "total_premium_adjusted": (context.get("fields") or {}).get("total_premium_adjusted", {}).get("value") or context.get("total_premium_adjusted"),
        },
        resolved_assets=resolved,
    )
