"""Admin CRUD helpers for system configuration."""

from __future__ import annotations

from copy import deepcopy

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.errors import AppError
from app.models.enums import AccountStatus, Role
from app.models.tables import AppSetting, FieldAlias, InsuranceCompany, OurSpecial, OurSpecialVariant, OutputTemplateConfig, TemplateGroup, TemplatePageProfile, TemplateRevision, VehicleBrand, VehicleModel
from app.services.template_config import normalize_template_config, review_schema_for
from app.services.template_revision_service import new_v7_template_config


def require_admin(user) -> None:
    if user.role not in {Role.SUPER_ADMIN.value, Role.ADMIN.value}:
        raise AppError("Only Admin can change this setting.", 403)


def require_business_setup(user) -> None:
    if user.role not in {Role.STAFF.value, Role.ADMIN.value, Role.SUPER_ADMIN.value}:
        raise AppError("You do not have permission to manage business templates.", 403)


def upsert_company(db: Session, user, payload: dict) -> InsuranceCompany:
    require_admin(user)
    company = db.get(InsuranceCompany, payload.get("id")) if payload.get("id") else None
    if not company:
        name = payload.get("name")
        if not name:
            raise AppError("Company name is required.", 400)
        company = InsuranceCompany(name=name, category=payload.get("category", "Motor"))
        db.add(company)
    company.name = payload.get("name", company.name)
    company.category = payload.get("category", company.category)
    company.source_template_category = payload.get("source_template_category", company.source_template_category)
    company.detection_phrases = payload.get("detection_phrases", company.detection_phrases)
    company.logo_path = payload.get("logo_path", company.logo_path)
    company.status = payload.get("status", company.status)
    db.commit()
    db.refresh(company)
    return company


def delete_company(db: Session, user, company_id: str) -> None:
    require_admin(user)
    company = db.get(InsuranceCompany, company_id)
    if not company:
        raise AppError("Company not found.", 404)
    remaining = db.scalar(select(func.count()).select_from(InsuranceCompany))
    if remaining is None or remaining <= 1:
        raise AppError("At least one company must remain.", 400)
    db.delete(company)
    db.commit()


def upsert_template(db: Session, user, payload: dict) -> OutputTemplateConfig:
    require_business_setup(user)
    template = db.get(OutputTemplateConfig, payload.get("id")) if payload.get("id") else None
    if template and normalize_template_config(template.fixed_fields, template.name).get("locked"):
        raise AppError("Copy this default template before editing.")
    if not template:
        template = OutputTemplateConfig(name=payload["name"], insurance_type=payload.get("insurance_type", "Motor"))
        db.add(template)
        if not payload.get("fixed_fields"):
            template.fixed_fields = new_v7_template_config(payload["name"])
    for key in ["name", "insurance_type", "insurance_company_id", "group_id", "html_template", "css_template", "static_notes", "editable_fields", "fixed_fields", "status"]:
        if key in payload:
            setattr(template, key, payload[key])
    db.commit()
    db.refresh(template)
    return template


def make_template_master(db: Session, user, template_id: str) -> OutputTemplateConfig:
    require_business_setup(user)
    template = db.get(OutputTemplateConfig, template_id)
    if not template or template.deleted_at:
        raise AppError("Template not found.", 404)
    for other in db.scalars(select(OutputTemplateConfig).where(OutputTemplateConfig.deleted_at.is_(None))).all():
        if other.id == template_id:
            continue
        config = normalize_template_config(other.fixed_fields, other.name)
        if config.get("is_default"):
            config["is_default"] = False
            config["locked"] = False
            other.fixed_fields = config
            flag_modified(other, "fixed_fields")
    config = normalize_template_config(template.fixed_fields, template.name)
    config["is_default"] = True
    config["locked"] = True
    template.fixed_fields = config
    flag_modified(template, "fixed_fields")
    db.commit()
    db.refresh(template)
    return template


def list_template_groups(db: Session) -> list[dict]:
    groups = db.scalars(select(TemplateGroup).order_by(TemplateGroup.name)).all()
    result = []
    for group in groups:
        company = db.get(InsuranceCompany, group.company_id) if group.company_id else None
        count = db.scalar(
            select(func.count()).select_from(OutputTemplateConfig).where(
                OutputTemplateConfig.group_id == group.id,
                OutputTemplateConfig.deleted_at.is_(None),
            )
        ) or 0
        result.append({
            "id": group.id,
            "name": group.name,
            "company_id": group.company_id,
            "company_name": company.name if company else None,
            "template_count": count,
        })
    return result


def upsert_template_group(db: Session, user, payload: dict) -> TemplateGroup:
    require_business_setup(user)
    group = db.get(TemplateGroup, payload.get("id")) if payload.get("id") else None
    if not group:
        name = payload.get("name")
        if not name or not name.strip():
            raise AppError("Group name is required.", 400)
        group = TemplateGroup(name=name.strip())
        db.add(group)
    if payload.get("name"):
        group.name = payload["name"].strip()
    group.company_id = payload.get("company_id") or None
    db.commit()
    db.refresh(group)
    return group


def delete_template_group(db: Session, user, group_id: str) -> None:
    require_business_setup(user)
    group = db.get(TemplateGroup, group_id)
    if not group:
        raise AppError("Group not found.", 404)
    for template in db.scalars(select(OutputTemplateConfig).where(OutputTemplateConfig.group_id == group_id)).all():
        template.group_id = None
    db.delete(group)
    db.commit()


def import_vehicles_workbook(db: Session, user, sheets: list[tuple[str, list[dict]]]) -> dict:
    """Import brands/models from parsed workbook sheets (brand per sheet)."""
    require_admin(user)
    created = 0
    updated = 0
    errors: list[str] = []
    for brand_name, models in sheets:
        try:
            brand = db.scalar(select(VehicleBrand).where(VehicleBrand.name == brand_name))
            if brand:
                updated += 1
            else:
                brand = VehicleBrand(name=brand_name, aliases=[], status=AccountStatus.ACTIVE.value)
                db.add(brand)
                db.flush()
                created += 1
            for model in models:
                name = model.get("name", "").strip()
                if not name:
                    continue
                aliases = [a for a in model.get("aliases", []) if a]
                existing_model = db.scalar(
                    select(VehicleModel).where(
                        VehicleModel.brand_id == brand.id,
                        VehicleModel.name == name,
                    )
                )
                if existing_model:
                    existing_model.aliases = list(dict.fromkeys([*existing_model.aliases, *aliases]))
                else:
                    db.add(VehicleModel(name=name, brand_id=brand.id, aliases=aliases, status=AccountStatus.ACTIVE.value))
                    created += 1
        except Exception as exc:  # noqa: BLE001 - per-sheet errors are collected
            errors.append(f"{brand_name}: {exc}")
    db.commit()
    return {"created": created, "updated": updated, "errors": errors}


def get_runner_fee_default(db: Session) -> float:
    setting = db.get(AppSetting, "runner_fee_default")
    if setting is None:
        return 20.0
    try:
        return float((setting.value or {}).get("amount", 20.0))
    except (TypeError, ValueError):
        return 20.0


def set_runner_fee_default(db: Session, user, amount: float) -> float:
    require_admin(user)
    if amount < 0 or amount > 100000:
        raise AppError("Runner fee must be between 0 and 100000.", 400)
    setting = db.get(AppSetting, "runner_fee_default")
    if setting is None:
        setting = AppSetting(key="runner_fee_default", value={})
        db.add(setting)
    setting.value = {"amount": round(amount, 2)}
    db.commit()
    return float(setting.value["amount"])


def serialize_template(template: OutputTemplateConfig, db: Session | None = None) -> dict:
    config = normalize_template_config(template.fixed_fields, template.name)
    company_name = None
    if db is not None and template.insurance_company_id:
        company = db.get(InsuranceCompany, template.insurance_company_id)
        company_name = company.name if company else None
    group_name = None
    if db is not None and template.group_id:
        group = db.get(TemplateGroup, template.group_id)
        group_name = group.name if group else None
    revision_summaries: list[dict] = []
    latest_published = None
    if db is not None:
        revisions = list(
            db.scalars(
                select(TemplateRevision)
                .where(TemplateRevision.template_id == template.id)
                .order_by(TemplateRevision.revision_number.desc())
            ).all()
        )
        for revision in revisions:
            profile = db.get(TemplatePageProfile, revision.page_profile_id)
            summary = {
                "id": revision.id,
                "revision_number": revision.revision_number,
                "state": revision.state,
                "config_hash": revision.config_hash,
                "published_at": revision.published_at.isoformat() if revision.published_at else None,
                "page_profile": {
                    "id": profile.id,
                    "profile_key": profile.profile_key,
                    "name": profile.name,
                    "width": float(str(profile.width)),
                    "height": float(str(profile.height)),
                    "unit": profile.unit,
                } if profile else None,
            }
            revision_summaries.append(summary)
            if latest_published is None and revision.state == "published":
                latest_published = summary
    return {
        "id": template.id,
        "revision": template.revision,
        "name": template.name,
        "insurance_type": template.insurance_type,
        "insurance_company_id": template.insurance_company_id,
        "insurance_company_name": company_name,
        "group_id": template.group_id,
        "group_name": group_name,
        "status": template.status,
        "static_notes": template.static_notes,
        "editable_fields": template.editable_fields,
        "fixed_fields": config,
        "locked": bool(config.get("locked")),
        "is_default": bool(config.get("is_default")),
        "packages": config.get("packages", []),
        "review_schema": review_schema_for(config, None),
        "template_revisions": revision_summaries,
        "latest_published_revision": latest_published,
    }


def copy_template(db: Session, user, template_id: str) -> OutputTemplateConfig:
    require_business_setup(user)
    source = db.get(OutputTemplateConfig, template_id)
    if not source or source.deleted_at:
        raise AppError("Template not found.", 404)
    config = normalize_template_config(source.fixed_fields, source.name)
    config["is_default"] = False
    config["locked"] = False
    copy = OutputTemplateConfig(
        name=f"Copy of {source.name}",
        insurance_type=source.insurance_type,
        insurance_company_id=source.insurance_company_id,
        group_id=source.group_id,
        html_template=source.html_template,
        css_template=source.css_template,
        static_notes=source.static_notes,
        editable_fields=list(source.editable_fields or []),
        fixed_fields=deepcopy(config),
        status=AccountStatus.ACTIVE.value,
    )
    db.add(copy)
    db.commit()
    db.refresh(copy)
    return copy


def update_template(db: Session, user, template_id: str, payload: dict) -> OutputTemplateConfig:
    require_business_setup(user)
    template = db.get(OutputTemplateConfig, template_id)
    if not template or template.deleted_at:
        raise AppError("Template not found.", 404)
    current_config = normalize_template_config(template.fixed_fields, template.name)
    if current_config.get("locked"):
        raise AppError("Copy this default template before editing.")
    base_revision = payload.pop("base_revision", None)
    if base_revision is not None and int(base_revision) != template.revision:
        raise AppError("This template changed elsewhere. Reload before saving.", 409)
    for key in ["name", "insurance_type", "insurance_company_id", "group_id", "static_notes", "editable_fields", "status"]:
        if key in payload:
            setattr(template, key, payload[key])
    if "fixed_fields" in payload:
        config = normalize_template_config(payload["fixed_fields"], template.name)
        config["is_default"] = False
        config["locked"] = False
        template.fixed_fields = config
        flag_modified(template, "fixed_fields")
    template.revision += 1
    db.commit()
    db.refresh(template)
    return template


SPECIAL_CATEGORIES = {"FOC", "Add-on"}


def upsert_special(db: Session, user, payload: dict) -> OurSpecial:
    require_admin(user)
    special = db.get(OurSpecial, payload.get("id")) if payload.get("id") else None
    category = payload.get("category") or (special.category if special else "FOC")
    if category not in SPECIAL_CATEGORIES:
        raise AppError("Category must be FOC or Add-on.", 400)
    if not special:
        special = OurSpecial(label=payload["label"], category=category)
        db.add(special)
    for key in ["label", "category", "status"]:
        if key in payload:
            setattr(special, key, payload[key])
    db.commit()
    db.refresh(special)
    return special


def delete_special(db: Session, user, special_id: str) -> None:
    require_admin(user)
    special = db.get(OurSpecial, special_id)
    if not special:
        raise AppError("Special not found.", 404)
    db.delete(special)
    db.commit()


def upsert_variant(db: Session, user, payload: dict) -> OurSpecialVariant:
    require_admin(user)
    variant = db.get(OurSpecialVariant, payload.get("id")) if payload.get("id") else None
    if not variant:
        special = db.get(OurSpecial, payload["special_id"])
        if not special:
            raise AppError("Parent special not found.", 404)
        variant = OurSpecialVariant(special_id=payload["special_id"], label=payload["label"])
        db.add(variant)
    for key in ["label", "secondary_label", "value_text", "icon_asset_id", "shape", "bg_color", "text_color", "border_width", "border_color", "shadow", "status"]:
        if key in payload:
            setattr(variant, key, payload[key])
    db.commit()
    db.refresh(variant)
    return variant


def delete_variant(db: Session, user, variant_id: str) -> None:
    require_admin(user)
    variant = db.get(OurSpecialVariant, variant_id)
    if not variant:
        raise AppError("Variant not found.", 404)
    db.delete(variant)
    db.commit()


def move_variant(db: Session, user, variant_id: str, special_id: str) -> OurSpecialVariant:
    require_admin(user)
    variant = db.get(OurSpecialVariant, variant_id)
    if not variant or variant.deleted_at:
        raise AppError("Variant not found.", 404)
    target = db.get(OurSpecial, special_id)
    if not target or target.deleted_at:
        raise AppError("Target special not found.", 404)
    variant.special_id = target.id
    db.commit()
    db.refresh(variant)
    return variant


def serialize_special(special: OurSpecial) -> dict:
    return {
        "id": special.id,
        "label": special.label,
        "category": special.category,
        "status": special.status,
        "variants": [
            {
                "id": v.id,
                "special_id": v.special_id,
                "label": v.label,
                "secondary_label": v.secondary_label,
                "value_text": v.value_text,
                "icon_asset_id": v.icon_asset_id,
                "shape": v.shape,
                "bg_color": v.bg_color,
                "text_color": v.text_color,
                "border_width": v.border_width,
                "border_color": v.border_color,
                "shadow": v.shadow,
                "status": v.status,
            }
            for v in (special.variants or [])
            if not v.deleted_at
        ],
    }


def upsert_field_alias(db: Session, user, payload: dict) -> FieldAlias:
    require_admin(user)
    alias = db.scalar(select(FieldAlias).where(FieldAlias.field_name == payload["field_name"]))
    if not alias:
        alias = FieldAlias(field_name=payload["field_name"])
        db.add(alias)
    alias.aliases = payload.get("aliases", alias.aliases)
    alias.status = payload.get("status", alias.status)
    db.commit()
    db.refresh(alias)
    return alias


def delete_field_alias(db: Session, user, field_name: str) -> None:
    require_admin(user)
    alias = db.scalar(select(FieldAlias).where(FieldAlias.field_name == field_name))
    if not alias:
        raise AppError("Field alias not found.", 404)
    db.delete(alias)
    db.commit()


def upsert_vehicle_brand(db: Session, user, payload: dict) -> VehicleBrand:
    require_admin(user)
    brand = db.get(VehicleBrand, payload.get("id")) if payload.get("id") else None
    if not brand:
        brand = VehicleBrand(name=payload["name"])
        db.add(brand)
    brand.name = payload.get("name", brand.name)
    brand.aliases = payload.get("aliases", brand.aliases)
    brand.status = payload.get("status", brand.status)
    db.commit()
    db.refresh(brand)
    return brand


def upsert_vehicle_model(db: Session, user, payload: dict) -> VehicleModel:
    require_admin(user)
    model = db.get(VehicleModel, payload.get("id")) if payload.get("id") else None
    if not model:
        model = VehicleModel(name=payload["name"])
        db.add(model)
    for key in ["brand_id", "name", "aliases", "status"]:
        if key in payload:
            setattr(model, key, payload[key])
    db.commit()
    db.refresh(model)
    return model


LEARNABLE_FIELDS = frozenset({"car_model", "car_brand"})


def dictionary_contains(db: Session, field: str, value: str) -> bool:
    if field not in LEARNABLE_FIELDS:
        return False
    folded = (value or "").strip().casefold()
    if not folded:
        return False
    if field == "car_model":
        rows = db.scalars(select(VehicleModel)).all()
    else:
        rows = db.scalars(select(VehicleBrand)).all()
    return any(
        folded in {row.name.casefold(), *[alias.casefold() for alias in (row.aliases or [])]}
        for row in rows
    )


def learn_dictionary_value(db: Session, user, field: str, value: str) -> dict:
    if user.role not in {Role.STAFF.value, Role.ADMIN.value, Role.SUPER_ADMIN.value}:
        raise AppError("You do not have permission to extend the extraction dictionary.", 403)
    if field not in LEARNABLE_FIELDS:
        raise AppError("Only vehicle make and model values can be learned.", 422)
    cleaned = (value or "").strip()
    if not cleaned or len(cleaned) > 160:
        raise AppError("Dictionary value is invalid.", 422)
    if dictionary_contains(db, field, cleaned):
        return {"added": False, "field": field, "value": cleaned}
    if field == "car_model":
        model = VehicleModel(name=cleaned, aliases=[cleaned])
        db.add(model)
        db.commit()
        db.refresh(model)
        return {"added": True, "id": model.id, "field": field, "value": cleaned}
    brand = VehicleBrand(name=cleaned, aliases=[cleaned])
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return {"added": True, "id": brand.id, "field": field, "value": cleaned}


def delete_vehicle_brand(db: Session, user, brand_id: str) -> None:
    require_admin(user)
    brand = db.get(VehicleBrand, brand_id)
    if not brand:
        raise AppError("Vehicle brand not found.", 404)
    db.delete(brand)
    db.commit()


def delete_vehicle_model(db: Session, user, model_id: str) -> None:
    require_admin(user)
    model = db.get(VehicleModel, model_id)
    if not model:
        raise AppError("Vehicle model not found.", 404)
    db.delete(model)
    db.commit()


def save_strategy_settings(db: Session, user, payload: dict) -> AppSetting:
    require_admin(user)
    if not any(payload.values()):
        raise AppError("At least one reading method must stay enabled.")
    setting = db.get(AppSetting, "extraction_strategies")
    if not setting:
        setting = AppSetting(key="extraction_strategies", value=payload)
        db.add(setting)
    else:
        setting.value = payload
    db.commit()
    db.refresh(setting)
    return setting


def get_runner_fee_default(db: Session) -> float:
    setting = db.get(AppSetting, "default_runner_fee")
    if not setting or not isinstance(setting.value, dict):
        return 20.0
    return float(setting.value.get("amount", 20.0))


def set_runner_fee_default(db: Session, user, amount: float) -> float:
    require_admin(user)
    setting = db.get(AppSetting, "default_runner_fee")
    if not setting:
        setting = AppSetting(key="default_runner_fee", value={"amount": amount, "currency": "MYR"})
        db.add(setting)
    else:
        setting.value = {"amount": amount, "currency": "MYR"}
    db.commit()
    db.refresh(setting)
    return amount
