"""SQLAlchemy tables for the full app foundation."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.models.enums import AccountStatus, InsuranceType, RecordStatus, Role, StorageStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purge_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def mark_deleted(self, retention_days: int) -> None:
        # RL-DISABLED timed trash expiry — disabled 2026-08-14; v7 trash is
        # retained until a user performs an explicit reference-aware purge.
        self.deleted_at = utcnow()
        self.purge_after = None

    def restore(self) -> None:
        self.deleted_at = None
        self.purge_after = None


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    role: Mapped[str] = mapped_column(String(50), nullable=False, default=Role.STAFF.value, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=AccountStatus.ACTIVE.value, index=True)

    batches: Mapped[list["Batch"]] = relationship(back_populates="owner")
    auth_sessions: Mapped[list["AuthSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", foreign_keys="AuthSession.user_id"
    )


class AuthSession(Base, TimestampMixin):
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    revoked_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)

    user: Mapped[User] = relationship(back_populates="auth_sessions", foreign_keys=[user_id])


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"

    scope: Mapped[str] = mapped_column(String(80), primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class InsuranceCategory(Base, TimestampMixin):
    __tablename__ = "insurance_categories"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=AccountStatus.ACTIVE.value)


class InsuranceCompany(Base, TimestampMixin):
    __tablename__ = "insurance_companies"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    legal_entity_id: Mapped[str | None] = mapped_column(ForeignKey("legal_entities.id", ondelete="SET NULL"), nullable=True, index=True)
    slug: Mapped[str | None] = mapped_column(String(160), nullable=True, unique=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default=InsuranceType.MOTOR.value, index=True)
    source_template_category: Mapped[str] = mapped_column(String(120), nullable=False, default="Other / Unknown")
    logo_path: Mapped[str | None] = mapped_column(String(600), nullable=True)
    logo_asset_id: Mapped[str | None] = mapped_column(ForeignKey("business_assets.id", ondelete="SET NULL"), nullable=True, index=True)
    detection_phrases: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=AccountStatus.ACTIVE.value, index=True)


class OutputTemplateConfig(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "output_template_configs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    insurance_type: Mapped[str] = mapped_column(String(100), nullable=False, default=InsuranceType.MOTOR.value, index=True)
    insurance_company_id: Mapped[str | None] = mapped_column(ForeignKey("insurance_companies.id"), nullable=True)
    group_id: Mapped[str | None] = mapped_column(ForeignKey("template_groups.id", ondelete="SET NULL"), nullable=True)
    html_template: Mapped[str] = mapped_column(Text, nullable=False, default="")
    css_template: Mapped[str] = mapped_column(Text, nullable=False, default="")
    static_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    editable_fields: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    fixed_fields: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=AccountStatus.ACTIVE.value)


class TemplateGroup(Base, TimestampMixin):
    __tablename__ = "template_groups"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("insurance_companies.id", ondelete="SET NULL"), nullable=True)


class OurSpecial(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "our_specials"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(10), nullable=False, default="FOC")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=AccountStatus.ACTIVE.value)

    variants: Mapped[list["OurSpecialVariant"]] = relationship(back_populates="special", cascade="all, delete-orphan")


class OurSpecialVariant(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "our_special_variants"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    special_id: Mapped[str] = mapped_column(ForeignKey("our_specials.id", ondelete="CASCADE"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    secondary_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    value_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    icon_asset_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    shape: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bg_color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    text_color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    border_width: Mapped[str | None] = mapped_column(String(20), nullable=True)
    border_color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    shadow: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=AccountStatus.ACTIVE.value)

    special: Mapped[OurSpecial] = relationship(back_populates="variants")


class FieldAlias(Base, TimestampMixin):
    __tablename__ = "field_aliases"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    field_name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=AccountStatus.ACTIVE.value)


class VehicleBrand(Base, TimestampMixin):
    __tablename__ = "vehicle_brands"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=AccountStatus.ACTIVE.value)


class VehicleModel(Base, TimestampMixin):
    __tablename__ = "vehicle_models"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    brand_id: Mapped[str | None] = mapped_column(ForeignKey("vehicle_brands.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=AccountStatus.ACTIVE.value)


class Batch(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "batches"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=RecordStatus.UPLOADED.value, index=True)
    enhanced_reading_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    owner: Mapped[User] = relationship(back_populates="batches")
    files: Mapped[list["UploadedFile"]] = relationship(back_populates="batch", cascade="all, delete-orphan")


class Session(Base, TimestampMixin):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    uploaded_file_id: Mapped[str] = mapped_column(ForeignKey("uploaded_files.id"), nullable=False, unique=True)
    draft_id: Mapped[str] = mapped_column(ForeignKey("quotation_drafts.id"), nullable=False, unique=True)
    insurance_type: Mapped[str] = mapped_column(String(100), nullable=False, default=InsuranceType.MOTOR.value)
    detected_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=AccountStatus.ACTIVE.value)

    owner: Mapped[User] = relationship()
    uploaded_file: Mapped[UploadedFile] = relationship()
    draft: Mapped[QuotationDraft] = relationship()


class ClientRecord(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "client_records"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    insurer_no: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.id"), nullable=True)
    draft_id: Mapped[str | None] = mapped_column(ForeignKey("quotation_drafts.id"), nullable=True)
    uploaded_file_id: Mapped[str | None] = mapped_column(ForeignKey("uploaded_files.id"), nullable=True)
    insurance_company: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    vehicle_no: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    coverage_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cover_period: Mapped[str | None] = mapped_column(String(100), nullable=True)
    car_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ncd_percent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ncd: Mapped[str | None] = mapped_column(String(50), nullable=True)
    coverage_amount: Mapped[str | None] = mapped_column(String(100), nullable=True)
    premium: Mapped[str | None] = mapped_column(String(100), nullable=True)
    roadtax: Mapped[str | None] = mapped_column(String(100), nullable=True)
    service_fee: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total_premium: Mapped[str | None] = mapped_column(String(100), nullable=True)
    issue_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    valid_until: Mapped[str | None] = mapped_column(String(50), nullable=True)
    vehicle_year: Mapped[str | None] = mapped_column(String(20), nullable=True)
    capacity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    engine_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    chassis_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    market_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    agreed_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    excess_amount: Mapped[str | None] = mapped_column(String(100), nullable=True)
    basic_premium: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ncd_amount: Mapped[str | None] = mapped_column(String(100), nullable=True)
    service_tax: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stamp_duty: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gross_premium: Mapped[str | None] = mapped_column(String(100), nullable=True)
    optional_covers: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_values: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)


class RecordSavedView(Base, TimestampMixin):
    __tablename__ = "record_saved_views"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_record_saved_view_owner_name"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    filters: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    is_shared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class RoadTaxRule(Base, TimestampMixin):
    __tablename__ = "road_tax_rules"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    vehicle_type: Mapped[str] = mapped_column(String(50), nullable=False, default="Car")
    owner_type: Mapped[str] = mapped_column(String(50), nullable=False, default="Individual")
    jurisdiction: Mapped[str] = mapped_column(String(100), nullable=False, default="West Malaysia")
    min_cc: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_cc: Mapped[int | None] = mapped_column(Integer, nullable=True)
    base_rate: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    formula: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=AccountStatus.ACTIVE.value)


class DocumentGroup(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "document_groups"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    insurance_type: Mapped[str] = mapped_column(String(100), nullable=False, default=InsuranceType.MOTOR.value)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=RecordStatus.UPLOADED.value)
    draft_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    uploaded_file_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class StorageConnection(Base, TimestampMixin):
    __tablename__ = "storage_connections"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="microsoft")
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    site_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    drive_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    root_item_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)
    connected_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class UploadedFile(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "uploaded_files"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id"), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    document_group_id: Mapped[str | None] = mapped_column(ForeignKey("document_groups.id"), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(800), nullable=False)
    storage_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="supabase")
    storage_bucket: Mapped[str | None] = mapped_column(String(160), nullable=True)
    storage_status: Mapped[str] = mapped_column(String(50), nullable=False, default=StorageStatus.AVAILABLE.value, index=True)
    storage_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_stored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    storage_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    storage_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archive_connection_id: Mapped[str | None] = mapped_column(ForeignKey("storage_connections.id"), nullable=True)
    archive_item_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    archive_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    archive_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    security_scan: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    insurance_type: Mapped[str] = mapped_column(String(100), nullable=False, default=InsuranceType.MOTOR.value)
    insurance_company_id: Mapped[str | None] = mapped_column(ForeignKey("insurance_companies.id"), nullable=True)
    template_id: Mapped[str | None] = mapped_column(ForeignKey("output_template_configs.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=RecordStatus.UPLOADED.value, index=True)
    enhanced_reading: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    simple_issue: Mapped[str | None] = mapped_column(String(255), nullable=True)

    batch: Mapped[Batch] = relationship(back_populates="files")
    extraction_record: Mapped["ExtractionRecord"] = relationship(back_populates="uploaded_file", uselist=False)
    draft: Mapped["QuotationDraft"] = relationship(back_populates="uploaded_file", uselist=False)


class ExtractionRecord(Base, TimestampMixin):
    __tablename__ = "extraction_records"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    uploaded_file_id: Mapped[str] = mapped_column(ForeignKey("uploaded_files.id"), nullable=False, unique=True)
    method_summary: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ocr_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    page_text: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    words: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    blocks: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    tables: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    images: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    regions: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    candidates: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    benefit_lines: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    company_resolution: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    reading_quality: Mapped[str] = mapped_column(String(50), nullable=False, default="check_needed")

    uploaded_file: Mapped[UploadedFile] = relationship(back_populates="extraction_record")


class QuotationDraft(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "quotation_drafts"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    uploaded_file_id: Mapped[str] = mapped_column(ForeignKey("uploaded_files.id"), nullable=False, unique=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    insurance_type: Mapped[str] = mapped_column(String(100), nullable=False, default=InsuranceType.MOTOR.value)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=RecordStatus.CHECK_NEEDED.value, index=True)
    fields: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    scalar_decisions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("insurance_companies.id", ondelete="SET NULL"), nullable=True, index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("insurance_products.id", ondelete="SET NULL"), nullable=True, index=True)
    tier_id: Mapped[str | None] = mapped_column(ForeignKey("insurance_product_tiers.id", ondelete="SET NULL"), nullable=True, index=True)
    catalog_revision_id: Mapped[str | None] = mapped_column(ForeignKey("benefit_catalog_revisions.id", ondelete="SET NULL"), nullable=True, index=True)
    template_revision_id: Mapped[str | None] = mapped_column(ForeignKey("template_revisions.id", ondelete="SET NULL"), nullable=True, index=True)
    layout_override: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    layout_override_template_id: Mapped[str | None] = mapped_column(ForeignKey("output_template_configs.id", ondelete="SET NULL"), nullable=True)
    layout_override_template_revision_id: Mapped[str | None] = mapped_column(ForeignKey("template_revisions.id", ondelete="SET NULL"), nullable=True)
    layout_override_base_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    uploaded_file: Mapped[UploadedFile] = relationship(back_populates="draft")
    versions: Mapped[list["GeneratedPdfVersion"]] = relationship(back_populates="draft")


class GeneratedPdfVersion(Base, TimestampMixin):
    __tablename__ = "generated_pdf_versions"
    __table_args__ = (
        UniqueConstraint("draft_id", "version_number", name="uq_generated_pdf_draft_version"),
        UniqueConstraint("draft_id", "idempotency_key", name="uq_generated_pdf_draft_idempotency"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    draft_id: Mapped[str] = mapped_column(ForeignKey("quotation_drafts.id"), nullable=False, index=True)
    uploaded_file_id: Mapped[str] = mapped_column(ForeignKey("uploaded_files.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    draft_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    catalog_revision_id: Mapped[str | None] = mapped_column(ForeignKey("benefit_catalog_revisions.id", ondelete="SET NULL"), nullable=True)
    template_revision_id: Mapped[str | None] = mapped_column(ForeignKey("template_revisions.id", ondelete="SET NULL"), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(800), nullable=False)
    storage_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="supabase")
    storage_bucket: Mapped[str | None] = mapped_column(String(160), nullable=True)
    storage_status: Mapped[str] = mapped_column(String(50), nullable=False, default=StorageStatus.AVAILABLE.value, index=True)
    storage_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_stored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    storage_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    storage_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archive_connection_id: Mapped[str | None] = mapped_column(ForeignKey("storage_connections.id"), nullable=True)
    archive_item_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    archive_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    archive_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    draft_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    template_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    render_context_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    render_context_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    renderer_version: Mapped[str] = mapped_column(String(80), nullable=False, default="legacy")
    generated_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    draft: Mapped[QuotationDraft] = relationship(back_populates="versions")


class TrashRecord(Base, TimestampMixin):
    __tablename__ = "trash_records"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    original_status: Mapped[str] = mapped_column(String(50), nullable=False)
    deleted_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    purge_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CorrectionMemory(Base, TimestampMixin):
    __tablename__ = "correction_memory"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    draft_id: Mapped[str] = mapped_column(ForeignKey("quotation_drafts.id"), nullable=False, index=True)
    uploaded_file_id: Mapped[str] = mapped_column(ForeignKey("uploaded_files.id"), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    original_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    insurance_company_id: Mapped[str | None] = mapped_column(ForeignKey("insurance_companies.id"), nullable=True)
    corrected_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)


class TemplateAsset(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "template_assets"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    uploaded_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    folder: Mapped[str] = mapped_column(String(120), nullable=False, default="Uncategorized", index=True)
    storage_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="supabase")
    storage_bucket: Mapped[str | None] = mapped_column(String(160), nullable=True)
    storage_path: Mapped[str] = mapped_column(String(800), nullable=False)
    storage_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=AccountStatus.ACTIVE.value, index=True)


class AdminSuggestion(Base, TimestampMixin):
    __tablename__ = "admin_suggestions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    suggestion_type: Mapped[str] = mapped_column(String(80), nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    correction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    examples: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AppSetting(Base, TimestampMixin):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(160), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class AuditEvent(Base, TimestampMixin):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    recipient_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_state: Mapped[str] = mapped_column(String(20), nullable=False, default="sent")
    delivery_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    audit_event_id: Mapped[str | None] = mapped_column(ForeignKey("audit_events.id", ondelete="SET NULL"), nullable=True)


# --- v7 additive business, review, template, job, and snapshot domain ---


class LegalEntity(Base, TimestampMixin):
    __tablename__ = "legal_entities"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    registration_no: Mapped[str | None] = mapped_column(String(120), nullable=True)
    jurisdiction: Mapped[str] = mapped_column(String(80), nullable=False, default="MY")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active", index=True)


class CompanyAlias(Base, TimestampMixin):
    __tablename__ = "company_aliases"
    __table_args__ = (UniqueConstraint("normalized_alias", name="uq_company_alias_normalized"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("insurance_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    alias: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(255), nullable=False)
    alias_kind: Mapped[str] = mapped_column(String(40), nullable=False, default="detection")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")


class InsuranceProduct(Base, TimestampMixin):
    __tablename__ = "insurance_products"
    __table_args__ = (UniqueConstraint("company_id", "product_key", name="uq_product_company_key"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("insurance_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    product_key: Mapped[str] = mapped_column(String(160), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[str | None] = mapped_column(String(120), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active", index=True)


class InsuranceProductTier(Base, TimestampMixin):
    __tablename__ = "insurance_product_tiers"
    __table_args__ = (UniqueConstraint("product_id", "tier_key", name="uq_product_tier_key"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("insurance_products.id", ondelete="CASCADE"), nullable=False, index=True)
    tier_key: Mapped[str] = mapped_column(String(160), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")


class SourceDocument(Base, TimestampMixin):
    __tablename__ = "source_documents"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    issuer: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    reference_url: Mapped[str | None] = mapped_column(String(1_500), nullable=True)
    reference_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    verification_status: Mapped[str] = mapped_column(String(40), nullable=False, default="unverified", index=True)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class BenefitConcept(Base, TimestampMixin):
    __tablename__ = "benefit_concepts"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    concept_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    value_schema: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    display_template: Mapped[str] = mapped_column(String(500), nullable=False, default="{label}")
    required_variables: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    optional_variables: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    validation_rules: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    default_asset_id: Mapped[str | None] = mapped_column(ForeignKey("business_assets.id", ondelete="SET NULL"), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    demo_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    match_dataset: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    value_pattern_dataset: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    description_variants: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active", index=True)


class BenefitAlias(Base, TimestampMixin):
    __tablename__ = "benefit_aliases"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    benefit_id: Mapped[str] = mapped_column(ForeignKey("benefit_concepts.id", ondelete="CASCADE"), nullable=False, index=True)
    phrase: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_phrase: Mapped[str] = mapped_column(String(255), nullable=False)
    scope: Mapped[str] = mapped_column(String(40), nullable=False, default="global")
    company_id: Mapped[str | None] = mapped_column(ForeignKey("insurance_companies.id", ondelete="CASCADE"), nullable=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("insurance_products.id", ondelete="CASCADE"), nullable=True)
    package_id: Mapped[str | None] = mapped_column(ForeignKey("benefit_packages.id", ondelete="CASCADE"), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")


class Segment(Base, TimestampMixin):
    __tablename__ = "segments"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    segment_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active", index=True)


class VehicleCategory(Base, TimestampMixin):
    __tablename__ = "vehicle_categories"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    category_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active", index=True)


class VehicleSubcategory(Base, TimestampMixin):
    __tablename__ = "vehicle_subcategories"
    __table_args__ = (UniqueConstraint("category_id", "subcategory_key", name="uq_vehicle_subcategory_key"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    category_id: Mapped[str] = mapped_column(ForeignKey("vehicle_categories.id", ondelete="CASCADE"), nullable=False, index=True)
    subcategory_key: Mapped[str] = mapped_column(String(160), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active", index=True)


class CoverageType(Base, TimestampMixin):
    __tablename__ = "coverage_types"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    coverage_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active", index=True)


class BenefitFacet(Base, TimestampMixin):
    __tablename__ = "benefit_facets"
    __table_args__ = (UniqueConstraint("parent_concept_id", "facet_key", name="uq_benefit_facet_key"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    parent_concept_id: Mapped[str] = mapped_column(ForeignKey("benefit_concepts.id", ondelete="CASCADE"), nullable=False, index=True)
    facet_key: Mapped[str] = mapped_column(String(160), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_id: Mapped[str | None] = mapped_column(ForeignKey("business_assets.id", ondelete="SET NULL"), nullable=True)
    display_template: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")


class BenefitCatalog(Base, TimestampMixin):
    __tablename__ = "benefit_catalogs"
    __table_args__ = (UniqueConstraint("company_id", "product_id", "tier_id", name="uq_catalog_context"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("insurance_companies.id", ondelete="CASCADE"), nullable=True, index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("insurance_products.id", ondelete="CASCADE"), nullable=True, index=True)
    tier_id: Mapped[str | None] = mapped_column(ForeignKey("insurance_product_tiers.id", ondelete="CASCADE"), nullable=True, index=True)
    package_id: Mapped[str | None] = mapped_column(ForeignKey("benefit_packages.id", ondelete="SET NULL"), nullable=True, index=True)
    segment_id: Mapped[str | None] = mapped_column(ForeignKey("segments.id", ondelete="SET NULL"), nullable=True)
    vehicle_category_id: Mapped[str | None] = mapped_column(ForeignKey("vehicle_categories.id", ondelete="SET NULL"), nullable=True)
    vehicle_subcategory_id: Mapped[str | None] = mapped_column(ForeignKey("vehicle_subcategories.id", ondelete="SET NULL"), nullable=True)
    coverage_type_id: Mapped[str | None] = mapped_column(ForeignKey("coverage_types.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft", index=True)


class BenefitCatalogRevision(Base, TimestampMixin):
    __tablename__ = "benefit_catalog_revisions"
    __table_args__ = (UniqueConstraint("catalog_id", "revision_number", name="uq_catalog_revision"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    catalog_id: Mapped[str] = mapped_column(ForeignKey("benefit_catalogs.id", ondelete="CASCADE"), nullable=False, index=True)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False, default="draft", index=True)
    source_document_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    published_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CatalogOffering(Base, TimestampMixin):
    __tablename__ = "catalog_offerings"
    __table_args__ = (UniqueConstraint("catalog_revision_id", "offering_key", name="uq_catalog_offering_key"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    catalog_revision_id: Mapped[str] = mapped_column(ForeignKey("benefit_catalog_revisions.id", ondelete="CASCADE"), nullable=False, index=True)
    offering_key: Mapped[str] = mapped_column(String(160), nullable=False)
    concept_id: Mapped[str] = mapped_column(ForeignKey("benefit_concepts.id", ondelete="RESTRICT"), nullable=False, index=True)
    offering_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    applies_to_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    applies_to_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    label_override: Mapped[str | None] = mapped_column(String(255), nullable=True)
    typed_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    display_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    optional_price: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id", ondelete="SET NULL"), nullable=True)
    source_citation: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    source_aliases: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    presentation_facet_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active", index=True)


class BenefitRelation(Base, TimestampMixin):
    __tablename__ = "benefit_relations"
    __table_args__ = (UniqueConstraint("catalog_revision_id", "from_offering_id", "relation_kind", "to_offering_id", name="uq_benefit_relation"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    catalog_revision_id: Mapped[str] = mapped_column(ForeignKey("benefit_catalog_revisions.id", ondelete="CASCADE"), nullable=False, index=True)
    from_offering_id: Mapped[str] = mapped_column(ForeignKey("catalog_offerings.id", ondelete="CASCADE"), nullable=False, index=True)
    to_offering_id: Mapped[str] = mapped_column(ForeignKey("catalog_offerings.id", ondelete="CASCADE"), nullable=False, index=True)
    relation_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    branch_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class BenefitPackage(Base, TimestampMixin):
    __tablename__ = "benefit_packages"
    __table_args__ = (UniqueConstraint("catalog_revision_id", "package_key", name="uq_benefit_package_key"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    catalog_revision_id: Mapped[str] = mapped_column(ForeignKey("benefit_catalog_revisions.id", ondelete="CASCADE"), nullable=False, index=True)
    package_key: Mapped[str] = mapped_column(String(160), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    package_kind: Mapped[str] = mapped_column(String(40), nullable=False, default="comprehensive")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")


class BenefitPackagePlan(Base, TimestampMixin):
    __tablename__ = "benefit_package_plans"
    __table_args__ = (UniqueConstraint("package_id", "plan_key", name="uq_benefit_package_plan_key"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    package_id: Mapped[str] = mapped_column(ForeignKey("benefit_packages.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_key: Mapped[str] = mapped_column(String(160), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")


class BenefitPackagePlanItem(Base, TimestampMixin):
    __tablename__ = "benefit_package_plan_items"
    __table_args__ = (UniqueConstraint("plan_id", "offering_id", name="uq_benefit_package_plan_item"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    plan_id: Mapped[str] = mapped_column(ForeignKey("benefit_package_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    offering_id: Mapped[str] = mapped_column(ForeignKey("catalog_offerings.id", ondelete="RESTRICT"), nullable=False, index=True)
    typed_value_override: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class CatalogImport(Base, TimestampMixin):
    __tablename__ = "catalog_imports"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    state: Mapped[str] = mapped_column(String(40), nullable=False, default="dry_run", index=True)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    report: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BusinessAsset(Base, TimestampMixin):
    __tablename__ = "business_assets"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    asset_key: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    asset_kind: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_path: Mapped[str] = mapped_column(String(800), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_transparency: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    derivative_manifest: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="unassigned", index=True)


class ExtractionBenefitLine(Base, TimestampMixin):
    __tablename__ = "extraction_benefit_lines"
    __table_args__ = (UniqueConstraint("extraction_record_id", "line_id", name="uq_extraction_benefit_line"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    extraction_record_id: Mapped[str] = mapped_column(ForeignKey("extraction_records.id", ondelete="CASCADE"), nullable=False, index=True)
    line_id: Mapped[str] = mapped_column(String(160), nullable=False)
    raw_label: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_label: Mapped[str] = mapped_column(String(500), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_scope: Mapped[str] = mapped_column(String(60), nullable=False, default="unknown")
    line_kind: Mapped[str] = mapped_column(String(60), nullable=False, default="unknown")
    inclusion_state: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    evidence: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    candidate_mappings: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    extracted_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class DraftSourceLineDecision(Base, TimestampMixin):
    __tablename__ = "draft_source_line_decisions"
    __table_args__ = (UniqueConstraint("draft_id", "source_line_id", name="uq_draft_source_line_decision"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    draft_id: Mapped[str] = mapped_column(ForeignKey("quotation_drafts.id", ondelete="CASCADE"), nullable=False, index=True)
    source_line_id: Mapped[str] = mapped_column(ForeignKey("extraction_benefit_lines.id", ondelete="CASCADE"), nullable=False, index=True)
    disposition: Mapped[str] = mapped_column(String(40), nullable=False, default="unresolved", index=True)
    selection_id: Mapped[str | None] = mapped_column(ForeignKey("draft_benefit_selections.id", ondelete="SET NULL"), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DraftBenefitSelection(Base, TimestampMixin):
    __tablename__ = "draft_benefit_selections"
    __table_args__ = (UniqueConstraint("draft_id", "selection_key", name="uq_draft_benefit_selection_key"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    draft_id: Mapped[str] = mapped_column(ForeignKey("quotation_drafts.id", ondelete="CASCADE"), nullable=False, index=True)
    selection_key: Mapped[str] = mapped_column(String(160), nullable=False)
    catalog_offering_id: Mapped[str | None] = mapped_column(ForeignKey("catalog_offerings.id", ondelete="SET NULL"), nullable=True, index=True)
    concept_id: Mapped[str | None] = mapped_column(ForeignKey("benefit_concepts.id", ondelete="SET NULL"), nullable=True, index=True)
    source_line_id: Mapped[str | None] = mapped_column(ForeignKey("extraction_benefit_lines.id", ondelete="SET NULL"), nullable=True)
    item_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False, default="unresolved", index=True)
    cost_status: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    label_override: Mapped[str | None] = mapped_column(String(255), nullable=True)
    typed_value_override: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    selected_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    superseded_by_id: Mapped[str | None] = mapped_column(ForeignKey("draft_benefit_selections.id", ondelete="SET NULL"), nullable=True)
    package_plan_id: Mapped[str | None] = mapped_column(ForeignKey("benefit_package_plans.id", ondelete="SET NULL"), nullable=True, index=True)
    price: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class TemplatePageProfile(Base, TimestampMixin):
    __tablename__ = "template_page_profiles"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    profile_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    width: Mapped[Numeric] = mapped_column(Numeric(12, 4), nullable=False)
    height: Mapped[Numeric] = mapped_column(Numeric(12, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="px")
    safe_margins: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    bleed: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    background_behavior: Mapped[str] = mapped_column(String(40), nullable=False, default="clip")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")


class TemplateRevision(Base, TimestampMixin):
    __tablename__ = "template_revisions"
    __table_args__ = (UniqueConstraint("template_id", "revision_number", name="uq_template_revision"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    template_id: Mapped[str] = mapped_column(ForeignKey("output_template_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False, default="draft", index=True)
    page_profile_id: Mapped[str] = mapped_column(ForeignKey("template_page_profiles.id", ondelete="RESTRICT"), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    published_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("job_type", "idempotency_key", name="uq_job_type_idempotency"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True, index=True)
    uploaded_file_id: Mapped[str | None] = mapped_column(ForeignKey("uploaded_files.id", ondelete="CASCADE"), nullable=True, index=True)
    job_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False, default="queued", index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    safe_error: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    phase: Mapped[str] = mapped_column(String(80), nullable=False, default="queued")
    phase_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    phase_timestamps: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    lease_owner: Mapped[str | None] = mapped_column(String(160), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    worker_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    state: Mapped[str] = mapped_column(String(40), nullable=False, default="idle")
    process_id: Mapped[int] = mapped_column(Integer, nullable=False)
    release_id: Mapped[str | None] = mapped_column(String(160), nullable=True)


class RenderSnapshot(Base, TimestampMixin):
    __tablename__ = "render_snapshots"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    draft_id: Mapped[str] = mapped_column(ForeignKey("quotation_drafts.id", ondelete="RESTRICT"), nullable=False, index=True)
    draft_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    catalog_revision_id: Mapped[str | None] = mapped_column(ForeignKey("benefit_catalog_revisions.id", ondelete="RESTRICT"), nullable=True)
    template_revision_id: Mapped[str] = mapped_column(ForeignKey("template_revisions.id", ondelete="RESTRICT"), nullable=False)
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    context: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    asset_hashes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    renderer_version: Mapped[str] = mapped_column(String(80), nullable=False)
