"""Admin CRUD helpers for system configuration."""

from __future__ import annotations

from copy import deepcopy

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.enums import AccountStatus, Role
from app.models.tables import AppSetting, FieldAlias, InsuranceCompany, OurSpecial, OurSpecialVariant, OutputTemplateConfig, VehicleBrand, VehicleModel
from app.services.template_config import normalize_template_config, review_schema_for


def require_admin(user) -> None:
    if user.role not in {Role.SUPER_ADMIN.value, Role.ADMIN.value}:
        raise AppError("Only Admin can change this setting.", 403)


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
    require_admin(user)
    template = db.get(OutputTemplateConfig, payload.get("id")) if payload.get("id") else None
    if template and normalize_template_config(template.fixed_fields, template.name).get("locked"):
        raise AppError("Copy this default template before editing.")
    if not template:
        template = OutputTemplateConfig(name=payload["name"], insurance_type=payload.get("insurance_type", "Motor"))
        db.add(template)
    for key in ["name", "insurance_type", "insurance_company_id", "html_template", "css_template", "static_notes", "editable_fields", "fixed_fields", "status"]:
        if key in payload:
            setattr(template, key, payload[key])
    db.commit()
    db.refresh(template)
    return template


def serialize_template(template: OutputTemplateConfig, db: Session | None = None) -> dict:
    config = normalize_template_config(template.fixed_fields, template.name)
    company_name = None
    if db is not None and template.insurance_company_id:
        company = db.get(InsuranceCompany, template.insurance_company_id)
        company_name = company.name if company else None
    return {
        "id": template.id,
        "name": template.name,
        "insurance_type": template.insurance_type,
        "insurance_company_id": template.insurance_company_id,
        "insurance_company_name": company_name,
        "status": template.status,
        "static_notes": template.static_notes,
        "editable_fields": template.editable_fields,
        "fixed_fields": config,
        "locked": bool(config.get("locked")),
        "is_default": bool(config.get("is_default")),
        "packages": config.get("packages", []),
        "review_schema": review_schema_for(config, None),
    }


def copy_template(db: Session, user, template_id: str) -> OutputTemplateConfig:
    require_admin(user)
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
    require_admin(user)
    template = db.get(OutputTemplateConfig, template_id)
    if not template or template.deleted_at:
        raise AppError("Template not found.", 404)
    current_config = normalize_template_config(template.fixed_fields, template.name)
    if current_config.get("locked"):
        raise AppError("Copy this default template before editing.")
    for key in ["name", "insurance_type", "insurance_company_id", "static_notes", "editable_fields", "status"]:
        if key in payload:
            setattr(template, key, payload[key])
    if "fixed_fields" in payload:
        config = normalize_template_config(payload["fixed_fields"], template.name)
        config["is_default"] = False
        config["locked"] = False
        template.fixed_fields = config
    db.commit()
    db.refresh(template)
    return template


def upsert_special(db: Session, user, payload: dict) -> OurSpecial:
    require_admin(user)
    special = db.get(OurSpecial, payload.get("id")) if payload.get("id") else None
    if not special:
        special = OurSpecial(label=payload["label"], category=payload.get("category", "FOC"))
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
