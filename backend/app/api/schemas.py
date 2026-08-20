"""Typed request bodies for all application endpoints."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.benefits import BenefitValue


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


class WorkspacePatchRequest(StrictRequest):
    base_revision: int = Field(ge=1)
    operations: list[dict] = Field(min_length=1, max_length=200)


class TemplateSelectionImpactRequest(StrictRequest):
    base_revision: int = Field(ge=1)
    template_revision_id: str = Field(min_length=1, max_length=80)


class VersionGenerationRequest(StrictRequest):
    draft_revision: int = Field(ge=1)


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


class RecordBulkActionRequest(StrictRequest):
    action: str = Field(pattern=r"^(archive|unarchive|trash)$")
    record_ids: list[str] = Field(default_factory=list, max_length=5_000)
    all_matching: bool = False
    filters: dict = Field(default_factory=dict)


class RecordSavedViewRequest(StrictRequest):
    id: str | None = None
    base_revision: int | None = Field(default=None, ge=1)
    name: str = Field(min_length=1, max_length=120)
    filters: dict = Field(default_factory=dict)
    is_shared: bool = True


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
    base_revision: int | None = Field(default=None, ge=1)
    name: str | None = None
    insurance_type: str | None = None
    insurance_company_id: str | None = None
    group_id: str | None = None
    static_notes: str | None = None
    editable_fields: list[str] | None = None
    fixed_fields: dict | None = None
    status: str | None = None


# --- Business Setup v7 ---

class BusinessCompanySaveRequest(StrictRequest):
    id: str | None = None
    base_revision: int | None = Field(default=None, ge=1)
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=160)
    legal_entity_id: str | None = None
    logo_asset_id: str | None = None
    status: str = "active"


class BusinessProductSaveRequest(StrictRequest):
    id: str | None = None
    base_revision: int | None = Field(default=None, ge=1)
    company_id: str
    product_key: str | None = Field(default=None, max_length=160)
    name: str = Field(min_length=1, max_length=255)
    channel: str | None = Field(default=None, max_length=120)
    status: str = "active"


class BusinessTierSaveRequest(StrictRequest):
    id: str | None = None
    base_revision: int | None = Field(default=None, ge=1)
    product_id: str
    tier_key: str | None = Field(default=None, max_length=160)
    name: str = Field(min_length=1, max_length=255)
    sort_order: int = Field(default=0, ge=0)
    status: str = "active"


class CompanyAliasSaveRequest(StrictRequest):
    id: str | None = None
    company_id: str
    alias: str = Field(min_length=1, max_length=255)
    alias_kind: str = Field(default="detection", max_length=40)
    status: str = "active"


class BenefitConceptSaveRequest(StrictRequest):
    id: str | None = None
    base_revision: int | None = Field(default=None, ge=1)
    concept_key: str = Field(min_length=1, max_length=160)
    label: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, pattern=r"^(default|addon)$")
    variants: list[str] = Field(default_factory=list, max_length=50)
    value_schema: dict = Field(default_factory=dict)
    display_template: str = Field(default="{label}", min_length=1, max_length=500)
    required_variables: list[str] = Field(default_factory=list, max_length=40)
    optional_variables: list[str] = Field(default_factory=list, max_length=40)
    validation_rules: dict = Field(default_factory=dict)
    description: str | None = Field(default=None, max_length=2_000)
    demo_value: dict | None = None
    match_dataset: list[str] = Field(default_factory=list, max_length=500)
    value_pattern_dataset: list[str] = Field(default_factory=list, max_length=500)
    description_variants: list[dict] = Field(default_factory=list, max_length=2)
    sort_order: int = Field(default=0, ge=0)
    default_asset_id: str | None = None
    status: str = "active"


class SegmentSaveRequest(StrictRequest):
    id: str | None = None
    segment_key: str | None = Field(default=None, max_length=160)
    name: str = Field(min_length=1, max_length=255)
    sort_order: int = Field(default=0, ge=0)
    status: str = "active"


class VehicleCategorySaveRequest(StrictRequest):
    id: str | None = None
    category_key: str | None = Field(default=None, max_length=160)
    name: str = Field(min_length=1, max_length=255)
    sort_order: int = Field(default=0, ge=0)
    status: str = "active"


class VehicleSubcategorySaveRequest(StrictRequest):
    id: str | None = None
    category_id: str
    subcategory_key: str | None = Field(default=None, max_length=160)
    name: str = Field(min_length=1, max_length=255)
    sort_order: int = Field(default=0, ge=0)
    status: str = "active"


class CoverageTypeSaveRequest(StrictRequest):
    id: str | None = None
    coverage_key: str | None = Field(default=None, max_length=160)
    name: str = Field(min_length=1, max_length=255)
    sort_order: int = Field(default=0, ge=0)
    status: str = "active"


class BenefitAliasSaveRequest(StrictRequest):
    id: str | None = None
    benefit_id: str
    phrase: str = Field(min_length=1, max_length=255)
    scope: str = Field(default="global", max_length=40)
    company_id: str | None = None
    product_id: str | None = None
    package_id: str | None = None
    status: str = "active"


class BenefitCatalogSaveRequest(StrictRequest):
    company_id: str
    product_id: str | None = None
    tier_id: str | None = None
    segment_id: str | None = None
    vehicle_category_id: str | None = None
    vehicle_subcategory_id: str | None = None
    coverage_type_id: str | None = None
    name: str = Field(min_length=1, max_length=255)


class CatalogContextRequest(StrictRequest):
    base_revision: int = Field(ge=1)
    segment_id: str | None = None
    vehicle_category_id: str | None = None
    vehicle_subcategory_id: str | None = None
    coverage_type_id: str | None = None


class CatalogOfferingSaveRequest(StrictRequest):
    id: str | None = None
    base_revision: int = Field(ge=1)
    offering_key: str | None = Field(default=None, max_length=160)
    concept_id: str | None = None
    offering_kind: str | None = None
    applies_to_type: str | None = Field(default=None, pattern=r"^(product|package|bundle)$")
    applies_to_id: str | None = None
    role: str | None = Field(default=None, pattern=r"^(included|addon_option|bundle_component)$")
    label_override: str | None = Field(default=None, max_length=255)
    typed_value: BenefitValue | None = None
    display_value: str | None = Field(default=None, max_length=500)
    optional_price: dict | None = None
    source_document_id: str | None = None
    source_citation: dict = Field(default_factory=dict)
    source_aliases: list[str] = Field(default_factory=list, max_length=100)
    presentation_facet_ids: list[str] = Field(default_factory=list, max_length=100)
    sort_order: int = Field(default=0, ge=0)
    status: str = "active"


class PackageSaveRequest(StrictRequest):
    id: str | None = None
    base_revision: int = Field(ge=1)
    package_key: str | None = Field(default=None, max_length=160)
    name: str = Field(min_length=1, max_length=255)
    package_kind: str = Field(default="comprehensive", pattern=r"^(comprehensive|addon_bundle)$")
    sort_order: int = Field(default=0, ge=0)
    status: str = "active"


class PackageCloneRequest(StrictRequest):
    base_revision: int = Field(ge=1)
    package_key: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=255)
    package_kind: str | None = Field(default=None, pattern=r"^(comprehensive|addon_bundle)$")
    sort_order: int = Field(default=0, ge=0)


class PackagePlanSaveRequest(StrictRequest):
    id: str | None = None
    base_revision: int = Field(ge=1)
    plan_key: str | None = Field(default=None, max_length=160)
    name: str = Field(min_length=1, max_length=255)
    sort_order: int = Field(default=0, ge=0)
    status: str = "active"


class PackagePlanItemEntry(StrictRequest):
    offering_id: str
    typed_value_override: BenefitValue | None = None
    sort_order: int = Field(default=0, ge=0)


class PackagePlanItemsRequest(StrictRequest):
    base_revision: int = Field(ge=1)
    items: list[PackagePlanItemEntry] = Field(default_factory=list, max_length=100)


class TemplatePublishRequest(StrictRequest):
    base_revision: int = Field(ge=1)


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


# --- Business: dictionary learning ---

class DictionaryLearnRequest(BaseModel):
    field: str = Field(min_length=1, max_length=40)
    value: str = Field(min_length=1, max_length=160)


# --- Business: catalog publication ---

class CatalogPublishRequest(BaseModel):
    base_revision: int = Field(ge=1)


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
