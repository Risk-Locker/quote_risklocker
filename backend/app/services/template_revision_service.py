"""Validation and immutable publication helpers for v7 master templates."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import defer
from sqlalchemy.orm.attributes import flag_modified

from app.core.errors import AppError
from app.models.enums import Role
from app.models.tables import (
    AuditEvent,
    OutputTemplateConfig,
    TemplatePageProfile,
    TemplateRevision,
    new_id,
)
from app.rendering.render_context import canonical_context_hash
from app.services.template_config import normalize_template_config


GRID_KINDS = frozenset({"current_benefits", "available_addons"})
GRID_STRATEGIES = frozenset({"balanced", "square_biased", "staggered"})
GRID_ALIGNMENTS = frozenset({"start", "center", "end"})
CARD_STYLES = frozenset({"standard", "outlined", "soft", "minimal"})
TEXT_DENSITIES = frozenset({"comfortable", "normal", "compact"})
LEGACY_MANUAL_BENEFITS = frozenset({"special", "benefit-section", "benefit-card"})
RENDERABLE_ELEMENT_TYPES = frozenset({"text", "variable", "image", "line", "rectangle", "ellipse", "triangle", "diamond", "benefit-grid", "premium-info-block"})
NEW_ELEMENT_TYPES = RENDERABLE_ELEMENT_TYPES | {"layer-group"}
EMPTY_STATES = frozenset({"hide", "message"})
BUSINESS_ROLES = frozenset({Role.STAFF.value, Role.ADMIN.value, Role.SUPER_ADMIN.value})
INSURER_IDENTITY_KEYS = frozenset({"company_id", "insurance_company_id", "insurer_id", "brand_id"})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _require_business_user(user) -> None:
    if user.role not in BUSINESS_ROLES:
        raise AppError("You do not have permission to manage business templates.", 403)


def template_config_hash(config: dict) -> str:
    return canonical_context_hash(validate_template_config(config, compatibility=True))


def _number(value, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric.") from exc
    if result <= 0:
        raise ValueError(f"{label} must be positive.")
    return result


def _ratio(value: Any, label: str, *, minimum: float = 0, maximum: float = 1) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric.") from exc
    if result < minimum or result > maximum:
        raise ValueError(f"{label} is outside its supported range.")
    return result


def convert_legacy_template_nodes(config: dict) -> dict:
    """Convert ambiguous legacy groups/shapes into explicit v7 nodes.

    A referenced legacy group becomes non-rendering hierarchy. Its visible
    background/border, when present, is preserved as a separate rectangle.
    """
    converted = deepcopy(config)
    canvas = converted.setdefault("canvas", {})
    elements = list(canvas.get("elements") or [])
    referenced_groups = {str(item.get("groupId")) for item in elements if item.get("groupId")}
    used_ids = {str(item.get("id")) for item in elements if item.get("id")}
    output: list[dict] = []
    for index, source in enumerate(elements):
        item = deepcopy(source)
        item_type = str(item.get("type") or "")
        if item_type == "shape":
            shape = str(item.pop("shapeKind", "") or "rectangle")
            item["type"] = {"circle": "ellipse", "triangle": "triangle", "diamond": "diamond"}.get(shape, "rectangle")
            output.append(item)
            continue
        if item_type != "group":
            output.append(item)
            continue
        item_id = str(item.get("id") or f"legacy-group-{index + 1}")
        if item_id not in referenced_groups:
            item["type"] = "rectangle"
            item.pop("groupName", None)
            output.append(item)
            continue
        style = item.get("style") or {}
        background = str(style.get("background") or "").strip().casefold()
        visible_box = background not in {"", "transparent", "none"} or float(style.get("borderWidth") or 0) > 0
        group = {
            "id": item_id,
            "type": "layer-group",
            "name": str(item.get("groupName") or item.get("name") or f"Group {index + 1}"),
            "parentId": item.get("parentId"),
            "order": int(item.get("order") if item.get("order") is not None else item.get("z") or index),
            "visible": item.get("visible", True),
            "locked": bool(item.get("locked", False)),
        }
        output.append({key: value for key, value in group.items() if value is not None})
        if visible_box:
            rect_id = f"{item_id}--rectangle"
            suffix = 2
            while rect_id in used_ids:
                rect_id = f"{item_id}--rectangle-{suffix}"
                suffix += 1
            used_ids.add(rect_id)
            rectangle = deepcopy(item)
            rectangle.update({"id": rect_id, "type": "rectangle", "groupId": item_id})
            rectangle.pop("groupName", None)
            rectangle.pop("parentId", None)
            output.append(rectangle)
    converted["version"] = 7
    canvas["elements"] = output
    return converted


def validate_template_config(config: dict, *, compatibility: bool = False) -> dict:
    if not isinstance(config, dict):
        raise ValueError("Template config must be an object.")
    forbidden = {"scenarioMode", "scenarioData", "previewScenario"}.intersection(config)
    if forbidden:
        raise ValueError("Editor scenario data cannot be persisted in a template revision.")
    normalized = deepcopy(config)
    page = normalized.get("page_profile")
    canvas = normalized.get("canvas")
    if not isinstance(page, dict) or not isinstance(canvas, dict):
        raise ValueError("A fixed page profile and canvas are required.")
    width = _number(page.get("width"), "Page width")
    height = _number(page.get("height"), "Page height")
    if _number(canvas.get("width"), "Canvas width") != width or _number(canvas.get("height"), "Canvas height") != height:
        raise ValueError("Canvas dimensions must match the fixed page profile.")
    page_unit = str(page.get("unit") or "px")
    if page_unit not in {"px", "mm", "in"}:
        raise ValueError("Page-profile unit is invalid.")
    if not compatibility and page_unit != "px":
        raise ValueError("New template revisions use pixel canvas coordinates and require a pixel page profile.")
    safe_margins = page.get("safe_margins") or {}
    if not isinstance(safe_margins, dict):
        raise ValueError("Page safe margins must be an object.")
    for side in ("top", "right", "bottom", "left"):
        try:
            margin = float(safe_margins.get(side) or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Page {side} safe margin must be numeric.") from exc
        if margin < 0 or margin * 2 >= (height if side in {"top", "bottom"} else width):
            raise ValueError("Page safe margins must remain inside the fixed page.")
    elements = canvas.get("elements")
    if not isinstance(elements, list):
        raise ValueError("Template canvas elements must be an array.")
    ids: set[str] = set()
    group_ids = {str(item.get("id") or "") for item in elements if isinstance(item, dict) and item.get("type") == "layer-group"}
    grid_counts = {kind: 0 for kind in GRID_KINDS}
    for element in elements:
        if not isinstance(element, dict):
            raise ValueError("Every canvas element must be an object.")
        element_id = str(element.get("id") or "")
        if not element_id or element_id in ids:
            raise ValueError("Canvas element IDs must be present and unique.")
        ids.add(element_id)
        element_type = str(element.get("type") or "")
        if element_type in LEGACY_MANUAL_BENEFITS and not compatibility:
            raise ValueError("New template revisions cannot contain legacy manual benefit elements.")
        if not compatibility and element_type not in NEW_ELEMENT_TYPES:
            raise ValueError("Canvas element type is not supported in new template revisions.")
        if element_type == "layer-group":
            if not str(element.get("name") or "").strip():
                raise ValueError("Every semantic layer group requires a name.")
            parent_id = str(element.get("parentId") or "")
            if parent_id and parent_id not in group_ids:
                raise ValueError("A semantic layer group has an invalid parent.")
            continue
        try:
            x = float(element.get("x") or 0)
            y = float(element.get("y") or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError("Canvas element coordinates must be numeric.") from exc
        element_width = _number(element.get("w"), "Element width")
        element_height = _number(element.get("h"), "Element height")
        if x < 0 or y < 0 or x + element_width > width or y + element_height > height:
            raise ValueError("Every canvas element must remain inside the fixed page geometry.")
        group_id = str(element.get("groupId") or "")
        if group_id and group_id not in group_ids and not compatibility:
            raise ValueError("A canvas element has an invalid semantic group.")
        if element_type != "benefit-grid":
            continue
        kind = str(element.get("gridKind") or "")
        if kind not in GRID_KINDS:
            raise ValueError("Benefit-grid kind is invalid.")
        grid_counts[kind] += 1
        if grid_counts[kind] > 1:
            raise ValueError(f"A template may contain at most one {kind} grid.")
        packing = element.get("packing") or {}
        if not isinstance(packing, dict):
            raise ValueError("Benefit-grid packing must be an object.")
        if packing.get("strategy", "balanced") not in GRID_STRATEGIES:
            raise ValueError("Grid strategy is invalid.")
        if packing.get("alignment", "center") not in GRID_ALIGNMENTS:
            raise ValueError("Grid alignment is invalid.")
        _ratio(packing.get("gapRatio", 0.06), "gapRatio")
        _ratio(packing.get("paddingRatio", 0.02), "paddingRatio", maximum=0.49)
        _ratio(packing.get("staggerRatio", 0.5), "staggerRatio")
        _number(packing.get("aspectRatio", 1.45), "aspectRatio")
        _number(packing.get("referenceWidth", 180), "referenceWidth")
        _number(packing.get("referenceHeight", 124), "referenceHeight")
        if element.get("cardStyle", "standard") not in CARD_STYLES:
            raise ValueError("cardStyle is invalid.")
        if element.get("textDensity", "normal") not in TEXT_DENSITIES:
            raise ValueError("textDensity is invalid.")
        empty_state = element.get("emptyState", "hide")
        if empty_state not in EMPTY_STATES:
            raise ValueError("emptyState is invalid.")
        if empty_state == "message" and not str(element.get("emptyMessage") or "").strip():
            raise ValueError("emptyMessage is required when a grid shows an empty message.")
        if "maxCards" in element or "slots" in element:
            raise ValueError("Dynamic grids cannot persist finite card slots or capacity.")
        if any(key in element for key in {"scenarioMode", "scenarioData", "scenarioItems"}):
            raise ValueError("Editor scenario data cannot be persisted in a grid.")
    return normalized


def new_v7_template_config(template_name: str = "Motor") -> dict:
    """Create a clean editable fixed-page document, never a disguised legacy clone."""
    config = normalize_template_config({}, template_name)
    config.update({
        "version": 7,
        "is_default": False,
        "locked": False,
        "page_profile": {
            "profile_key": "a4",
            "name": "A4",
            "width": 794,
            "height": 1123,
            "unit": "px",
            "safe_margins": {"top": 24, "right": 24, "bottom": 24, "left": 24},
            "bleed": {},
            "background_behavior": "clip",
        },
    })
    config["canvas"] = {**config["canvas"], "width": 794, "height": 1123, "elements": []}
    return validate_template_config(convert_legacy_template_nodes(config))


def serialize_page_profile(profile: TemplatePageProfile) -> dict:
    return {
        "id": profile.id,
        "profile_key": profile.profile_key,
        "name": profile.name,
        "width": float(str(profile.width)),
        "height": float(str(profile.height)),
        "unit": profile.unit,
        "safe_margins": deepcopy(profile.safe_margins or {}),
        "background_behavior": profile.background_behavior or "clip",
    }


def serialize_template_revision(db, revision: TemplateRevision) -> dict:
    profile = db.get(TemplatePageProfile, revision.page_profile_id)
    return {
        "id": revision.id,
        "template_id": revision.template_id,
        "revision_number": revision.revision_number,
        "state": revision.state,
        "config_hash": revision.config_hash,
        "page_profile": serialize_page_profile(profile) if profile else None,
        "published_by": revision.published_by,
        "published_at": revision.published_at.isoformat() if revision.published_at else None,
    }


def _all_rows(db, model) -> list:
    return list(db.scalars(select(model)).all())


def list_page_profiles(db, user) -> list[dict]:
    _require_business_user(user)
    profiles = [profile for profile in _all_rows(db, TemplatePageProfile) if profile.status == "active"]
    profiles.sort(key=lambda item: (item.name.casefold(), item.profile_key))
    return [serialize_page_profile(profile) for profile in profiles]


def list_published_templates(db, user) -> list[dict]:
    """Return one insurer-independent option per master: its latest published revision."""
    _require_business_user(user)
    templates = {
        item.id: item
        for item in db.scalars(select(OutputTemplateConfig).options(defer(OutputTemplateConfig.fixed_fields))).all()
        if not item.deleted_at and item.status == "active"
    }
    latest: dict[str, TemplateRevision] = {}
    
    published_revisions = db.scalars(
        select(TemplateRevision)
        .where(TemplateRevision.state == "published")
        .options(defer(TemplateRevision.config))
    ).all()

    for revision in published_revisions:
        if revision.state != "published" or revision.template_id not in templates:
            continue
        current = latest.get(revision.template_id)
        if current is None or revision.revision_number > current.revision_number:
            latest[revision.template_id] = revision

    result: list[dict] = []
    for template_id, revision in latest.items():
        profile = db.get(TemplatePageProfile, revision.page_profile_id)
        if profile is None:
            continue
        template = templates[template_id]
        is_default = bool((template.fixed_fields or {}).get("is_default"))
        result.append({
            "template_id": template.id,
            "template_revision_id": revision.id,
            "name": str((revision.config or {}).get("template_name") or template.name),
            "revision_number": revision.revision_number,
            "config_hash": revision.config_hash,
            "page_profile": serialize_page_profile(profile),
            "is_default": is_default,
        })
    result.sort(key=lambda item: (not item.get("is_default", False), item["name"].casefold(), item["template_id"]))
    return result


def _profile_key(page: dict) -> str:
    supplied = str(page.get("profile_key") or "").strip().lower()
    if supplied and supplied != "custom":
        return supplied
    signature = canonical_context_hash({
        "width": float(page["width"]),
        "height": float(page["height"]),
        "unit": str(page.get("unit") or "px"),
        "safe_margins": page.get("safe_margins") or {},
        "bleed": page.get("bleed") or {},
        "background_behavior": page.get("background_behavior") or "clip",
    })
    return f"custom-{signature[:16]}"


def _resolve_page_profile(db, page: dict) -> TemplatePageProfile:
    profile_key = _profile_key(page)
    width = float(page["width"])
    height = float(page["height"])
    unit = str(page.get("unit") or "px")
    existing = next(
        (profile for profile in _all_rows(db, TemplatePageProfile) if profile.profile_key == profile_key),
        None,
    )
    if existing:
        if float(existing.width) != width or float(existing.height) != height or existing.unit != unit:
            raise AppError("The selected page profile does not match this fixed page geometry.", 422)
        if existing.status != "active":
            raise AppError("The selected page profile is not active.", 422)
        return existing
    profile = TemplatePageProfile(
        id=new_id(),
        profile_key=profile_key,
        name=str(page.get("name") or ("A4" if profile_key == "a4" else f"Custom {width:g} x {height:g}")),
        width=width,
        height=height,
        unit=unit,
        safe_margins=deepcopy(page.get("safe_margins") or {}),
        bleed=deepcopy(page.get("bleed") or {}),
        background_behavior=str(page.get("background_behavior") or "clip"),
        revision=1,
        status="active",
    )
    db.add(profile)
    db.flush()
    return profile


def _canonical_page(profile: TemplatePageProfile) -> dict:
    return {
        "profile_key": profile.profile_key,
        "name": profile.name,
        "width": float(str(profile.width)),
        "height": float(str(profile.height)),
        "unit": profile.unit,
        "safe_margins": deepcopy(profile.safe_margins or {}),
        "bleed": deepcopy(profile.bleed or {}),
        "background_behavior": profile.background_behavior or "clip",
    }


def publish_template_revision(db, user, template_id: str, *, base_revision: int) -> TemplateRevision:
    """Publish one validated immutable snapshot under an optimistic row lock."""
    _require_business_user(user)
    template = db.scalar(
        select(OutputTemplateConfig)
        .where(OutputTemplateConfig.id == template_id, OutputTemplateConfig.deleted_at.is_(None))
        .with_for_update()
    )
    if template is None or template.id != template_id or template.deleted_at:
        raise AppError("Template not found.", 404)
    if template.revision != base_revision:
        raise AppError("This template changed elsewhere. Reload before publishing.", 409)
    try:
        config = normalize_template_config(template.fixed_fields, template.name)
        config["version"] = 7
        config["template_name"] = template.name
        for key in INSURER_IDENTITY_KEYS:
            config.pop(key, None)
        config = validate_template_config(config)
        profile = _resolve_page_profile(db, config["page_profile"])
        config["page_profile"] = _canonical_page(profile)
        config["canvas"]["width"] = float(str(profile.width))
        config["canvas"]["height"] = float(str(profile.height))
        config = validate_template_config(config)
        config_hash = canonical_context_hash(config)
        revisions = list(db.scalars(
            select(TemplateRevision)
            .where(TemplateRevision.template_id == template.id)
            .options(defer(TemplateRevision.config))
        ).all())
        matching = [item for item in revisions if item.state == "published" and item.config_hash == config_hash]
        if matching:
            return max(matching, key=lambda item: item.revision_number)
        revision = TemplateRevision(
            id=new_id(),
            template_id=template.id,
            revision_number=max((item.revision_number for item in revisions), default=0) + 1,
            state="published",
            page_profile_id=profile.id,
            config=deepcopy(config),
            config_hash=config_hash,
            published_by=user.id,
            published_at=_utcnow(),
        )
        db.add(revision)
        template.fixed_fields = deepcopy(config)
        flag_modified(template, "fixed_fields")
        template.revision += 1
        db.add(AuditEvent(
            actor_id=user.id,
            action="template.publish",
            entity_type="template_revision",
            entity_id=revision.id,
            details={
                "template_id": template.id,
                "template_revision": revision.revision_number,
                "config_hash": config_hash,
                "base_revision": base_revision,
                "new_revision": template.revision,
            },
        ))
        db.commit()
        db.refresh(revision)
        return revision
    except AppError:
        db.rollback()
        raise
    except ValueError as exc:
        db.rollback()
        raise AppError(str(exc), 422) from exc
