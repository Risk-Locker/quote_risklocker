"""Typed request bodies for all application endpoints."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginRequest(StrictRequest):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class UserCreateRequest(StrictRequest):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=255)
    role: str = "staff"


class UserUpdateRequest(StrictRequest):
    email: str | None = Field(default=None, min_length=3, max_length=255)
    role: str | None = None
    status: str | None = None
    password: str | None = Field(default=None, min_length=8, max_length=255)


class UserPasswordChangeRequest(StrictRequest):
    current_password: str = Field(min_length=1, max_length=255)
    new_password: str = Field(min_length=8, max_length=255)


# --- Drafts ---

class DraftUpdateRequest(BaseModel):
    fields: dict[str, str | None] = Field(default_factory=dict)
    template_id: str | None = None
    layout_override: dict | None = None


class DraftGenerateRequest(BaseModel):
    acknowledge_check_needed: bool = False


class GenerateSelectedRequest(BaseModel):
    draft_ids: list[str] = Field(default_factory=list)
    acknowledge_check_needed: bool = False


# --- Bulk delete ---

class BulkUploadedFileDeleteRequest(BaseModel):
    uploaded_file_ids: list[str] = Field(default_factory=list)


class BulkClientRecordDeleteRequest(BaseModel):
    record_ids: list[str] = Field(default_factory=list)


class VariantMoveRequest(BaseModel):
    special_id: str = Field(min_length=1)


class TrashDeleteForeverRequest(BaseModel):
    entity_type: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)


# --- Client Records ---

class ClientRecordUpdateRequest(BaseModel):
    insurer_no: str | None = None
    notes: str | None = None


# --- Admin: Companies ---

class CompanySaveRequest(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=255)
    category: str = "Motor"
    source_template_category: str = "Other / Unknown"
    detection_phrases: list[str] = Field(default_factory=list)
    logo_path: str | None = None
    status: str | None = None


# --- Admin: Our Specials ---

class OurSpecialSaveRequest(BaseModel):
    id: str | None = None
    label: str = Field(min_length=1, max_length=255)
    category: str = "FOC"
    status: str | None = None


class OurSpecialVariantSaveRequest(BaseModel):
    id: str | None = None
    special_id: str
    label: str = Field(min_length=1, max_length=255)
    secondary_label: str | None = None
    value_text: str | None = None
    icon_asset_id: str | None = None
    shape: str | None = None
    bg_color: str | None = None
    text_color: str | None = None
    border_width: str | None = None
    border_color: str | None = None
    shadow: str | None = None
    status: str | None = None


# --- Admin: Templates ---

class TemplateSaveRequest(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=255)
    insurance_type: str = "Motor"
    insurance_company_id: str | None = None
    group_id: str | None = None
    html_template: str | None = None
    css_template: str | None = None
    static_notes: str | None = None
    editable_fields: list[str] | None = None
    fixed_fields: dict | None = None
    status: str | None = None


class TemplateUpdateRequest(BaseModel):
    name: str | None = None
    insurance_type: str | None = None
    insurance_company_id: str | None = None
    group_id: str | None = None
    static_notes: str | None = None
    editable_fields: list[str] | None = None
    fixed_fields: dict | None = None
    status: str | None = None


class TemplateGroupSaveRequest(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=255)
    company_id: str | None = None


# --- Admin: Field Aliases ---

class FieldAliasSaveRequest(BaseModel):
    id: str | None = None
    field_name: str = Field(min_length=1, max_length=120)
    aliases: list[str] = Field(default_factory=list)
    status: str | None = None


# --- Admin: Vehicle Brands/Models ---

class VehicleBrandSaveRequest(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=255)
    aliases: list[str] = Field(default_factory=list)
    status: str | None = None


class VehicleModelSaveRequest(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=255)
    brand_id: str | None = None
    aliases: list[str] = Field(default_factory=list)
    status: str | None = None


# --- Admin: Extraction Settings ---

class ExtractionSettingsRequest(BaseModel):
    native_pymupdf: bool = True
    native_pdfplumber: bool = True
    enhanced_paddleocr: bool = True
    enhanced_tesseract: bool = True
    layout_ppstructure: bool = True
    visual_opencv: bool = True


# --- Admin: Road Tax Rules ---

class RoadTaxRuleSaveRequest(BaseModel):
    id: str | None = None
    vehicle_type: str = "Car"
    owner_type: str = "Individual"
    jurisdiction: str = "West Malaysia"
    min_cc: int = 0
    max_cc: int | None = None
    base_rate: float = 0
    formula: str | None = None
    source: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    status: str = "active"
