"""Schema creation and default data seeding."""

from __future__ import annotations

import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.enums import AccountStatus, InsuranceType, Role
from app.models.tables import (
    AppSetting,
    Base,
    FieldAlias,
    InsuranceCategory,
    InsuranceCompany,
    OutputTemplateConfig,
    User,
    VehicleBrand,
    VehicleModel,
)
from app.services.template_config import default_template_config
from app.services.auth_service import ensure_super_admin


DEFAULT_COMPANIES = [
    ("QBE", "QBE", ["qbe"]),
]

DEFAULT_FIELD_ALIASES = {
    "customer_name": ["insured name", "name", "customer", "client name", "policyholder", "owner name"],
    "vehicle_no": ["vehicle no", "registration no", "reg no", "car no", "plate no", "vehicle registration"],
    "insurance_company": ["insurer", "insurance company", "company"],
    "cover_start_date": ["cover start", "period from", "from date", "effective date"],
    "cover_end_date": ["cover end", "period to", "to date", "expiry date"],
    "issue_date": ["issue date", "quotation date"],
    "car_brand": ["make", "brand", "car"],
    "car_model": ["model", "vehicle model"],
    "vehicle_year": ["year", "manufacture year", "mfg year"],
    "engine_cc": ["engine cc", "capacity", "cubic capacity", "engine capacity", "cc"],
    "coverage_amount": ["sum insured", "coverage amount", "insured value", "market value", "agreed value"],
    "premium": ["premium", "gross premium", "premium payable", "basic premium"],
    "total_amount": ["total payable", "total amount", "amount payable", "gross amount"],
    "roadtax": ["road tax", "roadtax"],
    "service_fee": ["service fee", "runner fee"],
    "ncd_percent": ["ncd", "no claim discount"],
    "windscreen": ["windscreen"],
    "towing": ["towing"],
}

DEFAULT_VEHICLES = {
    "PROTON": ["PROTON"],
    "PERODUA": ["PERODUA"],
    "HONDA": ["HONDA"],
    "TOYOTA": ["TOYOTA"],
    "NISSAN": ["NISSAN"],
    "BMW": ["BMW"],
    "MERCEDES": ["MERCEDES", "MERCEDES-BENZ"],
}

DEFAULT_MODELS = [
    ("PROTON", "SAGA BLM", ["SAGA BLM", "BLM", "SAGA"]),
    ("PROTON", "WAJA", ["WAJA"]),
    ("PERODUA", "MYVI", ["MYVI"]),
    ("PERODUA", "AXIA", ["AXIA"]),
    ("TOYOTA", "VIOS", ["VIOS"]),
    ("HONDA", "CITY", ["CITY"]),
]


def create_schema(engine) -> None:
    Base.metadata.create_all(bind=engine)


def seed_defaults(db: Session, settings: Settings) -> None:
    for category in [InsuranceType.MOTOR.value, InsuranceType.PROPERTY.value, InsuranceType.CONSTRUCTION.value, InsuranceType.FIRE.value]:
        if not db.scalar(select(InsuranceCategory).where(InsuranceCategory.name == category)):
            db.add(InsuranceCategory(name=category))

    for name, template_category, phrases in DEFAULT_COMPANIES:
        company = db.scalar(select(InsuranceCompany).where(InsuranceCompany.name == name))
        if not company:
            company = InsuranceCompany(
                name=name,
                category=InsuranceType.MOTOR.value,
                source_template_category=template_category,
                detection_phrases=phrases,
            )
            db.add(company)
            db.flush()

    default_template = db.scalar(select(OutputTemplateConfig).where(OutputTemplateConfig.name == "Risklocker Motor Template"))
    if not default_template:
        default_template = OutputTemplateConfig(
            name="Risklocker Motor Template",
            insurance_type=InsuranceType.MOTOR.value,
            editable_fields=list(DEFAULT_FIELD_ALIASES.keys()),
            static_notes="Generated from reviewed Risklocker draft data.",
        )
        db.add(default_template)
    default_template.insurance_company_id = None
    default_template.status = AccountStatus.ACTIVE.value
    default_template.fixed_fields = default_template_config("Motor", locked=True)
    default_template.static_notes = "Generated from reviewed Risklocker draft data."

    for field, aliases in DEFAULT_FIELD_ALIASES.items():
        if not db.scalar(select(FieldAlias).where(FieldAlias.field_name == field)):
            db.add(FieldAlias(field_name=field, aliases=aliases))

    brand_by_name: dict[str, VehicleBrand] = {}
    for brand, aliases in DEFAULT_VEHICLES.items():
        obj = db.scalar(select(VehicleBrand).where(VehicleBrand.name == brand))
        if not obj:
            obj = VehicleBrand(name=brand, aliases=aliases)
            db.add(obj)
            db.flush()
        brand_by_name[brand] = obj

    for brand, model, aliases in DEFAULT_MODELS:
        if not db.scalar(select(VehicleModel).where(VehicleModel.name == model)):
            brand_entry = brand_by_name.get(brand)
            db.add(VehicleModel(brand_id=brand_entry.id if brand_entry is not None else None, name=model, aliases=aliases))

    if not db.get(AppSetting, "extraction_strategies"):
        db.add(
            AppSetting(
                key="extraction_strategies",
                value={
                    "native_pymupdf": True,
                    "native_pdfplumber": True,
                    "enhanced_paddleocr": True,
                    "enhanced_tesseract": True,
                    "layout_ppstructure": True,
                    "visual_opencv": True,
                },
            )
        )

    if not db.get(AppSetting, "default_runner_fee"):
        db.add(AppSetting(key="default_runner_fee", value={"amount": 20.0, "currency": "MYR"}))

    from app.services.road_tax_service import seed_standard_road_tax_rules
    seed_standard_road_tax_rules(db)

    from app.services.vehicle_catalog_service import seed_vehicle_catalog_to_db
    seed_vehicle_catalog_to_db(db)

    # RL-DISABLED startup credential synchronization — disabled 2026-08-13;
    # Primary Admin bootstrap is an explicit one-time operational command.
