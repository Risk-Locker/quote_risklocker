"""SQLAlchemy tables for the full app foundation."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
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
        now = utcnow()
        self.deleted_at = now
        self.purge_after = now + timedelta(days=retention_days)

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


class InsuranceCategory(Base, TimestampMixin):
    __tablename__ = "insurance_categories"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=AccountStatus.ACTIVE.value)


class InsuranceCompany(Base, TimestampMixin):
    __tablename__ = "insurance_companies"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default=InsuranceType.MOTOR.value, index=True)
    source_template_category: Mapped[str] = mapped_column(String(120), nullable=False, default="Other / Unknown")
    logo_path: Mapped[str | None] = mapped_column(String(600), nullable=True)
    detection_phrases: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=AccountStatus.ACTIVE.value, index=True)


class OutputTemplateConfig(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "output_template_configs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
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
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    reading_quality: Mapped[str] = mapped_column(String(50), nullable=False, default="check_needed")

    uploaded_file: Mapped[UploadedFile] = relationship(back_populates="extraction_record")


class QuotationDraft(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "quotation_drafts"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    uploaded_file_id: Mapped[str] = mapped_column(ForeignKey("uploaded_files.id"), nullable=False, unique=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    insurance_type: Mapped[str] = mapped_column(String(100), nullable=False, default=InsuranceType.MOTOR.value)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=RecordStatus.CHECK_NEEDED.value, index=True)
    fields: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    layout_override: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    uploaded_file: Mapped[UploadedFile] = relationship(back_populates="draft")
    versions: Mapped[list["GeneratedPdfVersion"]] = relationship(back_populates="draft")


class GeneratedPdfVersion(Base, TimestampMixin):
    __tablename__ = "generated_pdf_versions"
    __table_args__ = (UniqueConstraint("draft_id", "version_number", name="uq_generated_pdf_draft_version"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_id)
    draft_id: Mapped[str] = mapped_column(ForeignKey("quotation_drafts.id"), nullable=False, index=True)
    uploaded_file_id: Mapped[str] = mapped_column(ForeignKey("uploaded_files.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
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
    purge_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


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
    uploaded_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
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
