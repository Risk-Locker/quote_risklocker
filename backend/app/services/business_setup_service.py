"""Company-first business setup services for the revisioned v7 catalog (Facade)."""

from __future__ import annotations

import sys
from typing import Any

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from collections import defaultdict

from sqlalchemy import delete, func, or_, select, text, update

from app.core.cache import _memory_cache, invalidate_cache
from app.core.errors import AppError
from app.domain.benefits import BenefitValue
from app.models.enums import Role
from app.models.tables import (
    AuditEvent,
    BenefitAlias,
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    BenefitPackage,
    BenefitPackagePlan,
    BenefitPackagePlanItem,
    BenefitRelation,
    BusinessAsset,
    CatalogOffering,
    CompanyAlias,
    CompanyBenefitCondition,
    CompanyBenefitConfig,
    BenefitProfile,
    CompanyBenefitProfile,
    GlobalBenefitProfile,
    GlobalBenefitProfileAsset,
    InsuranceCompany,
    InsuranceProduct,
    InsuranceProductTier,
    QuotationDraft,
    DraftBenefitSelection,
    SourceDocument,
    new_id,
    utcnow,
)
from app.rendering.render_context import canonical_context_hash
from app.services.asset_intake import create_derivative, validate_image_bytes
from app.storage.supabase import SupabaseStorage




from app.services.business_setup_common import (
    _asset_summary,
    _audit,
    _normalize_string_list,
    _require_business,
    _require_revision,
    _slug,
)
from app.services.company_setup_service import (
    delete_business_company,
    delete_business_product,
    delete_business_tier,
    get_business_company_workspace,
    list_business_companies,
    list_company_aliases,
    retire_company_alias,
    save_business_company,
    save_business_product,
    save_business_tier,
    save_company_alias,
)
from app.services.benefit_concept_service import (
    list_benefit_concepts,
    restore_benefit_concept,
    retire_benefit_concept,
    save_benefit_concept,
)
from app.services.business_asset_service import (
    _find_collision_in_category,
    _generate_unique_label_and_filename,
    batch_upload_business_assets,
    bulk_delete_business_assets,
    bulk_move_business_assets,
    delete_business_asset,
    delete_business_asset_folder,
    list_business_asset_categories,
    list_business_assets,
    rename_business_asset_folder,
    replace_business_asset_file,
    update_business_asset,
    upload_business_asset,
)
from app.services.catalog_lifecycle_service import (
    _offering,
    _revision_content_payload,
    _validate_assignment_context,
    create_benefit_catalog,
    create_new_draft_revision,
    delete_benefit_catalog,
    get_catalog_workspace,
    list_source_documents,
    publish_catalog_revision,
    remove_catalog_offering,
    retire_benefit_catalog,
    save_catalog_offering,
    update_catalog_context,
)
from app.services.benefit_profile_service import (
    activate_benefit_profile,
    activate_company_profile,
    clone_benefit_profile,
    clone_company_profile,
    create_benefit_profile,
    create_company_profile,
    delete_benefit_profile,
    delete_company_profile,
    get_active_benefit_profile,
    get_active_company_profile,
    get_company_benefit_configs,
    list_benefit_profiles,
    list_company_profiles,
    update_benefit_profile,
    update_company_benefit_configs,
    update_company_profile,
)
from app.services.company_benefit_condition_service import (
    delete_company_condition,
    list_company_conditions,
    save_company_condition,
)

from app.services import (
    business_setup_common,
    company_setup_service,
    benefit_concept_service,
    business_asset_service,
    catalog_lifecycle_service,
    benefit_profile_service,
    company_benefit_condition_service,
)

_all_submodules = [
    business_setup_common,
    company_setup_service,
    benefit_concept_service,
    business_asset_service,
    catalog_lifecycle_service,
    benefit_profile_service,
    company_benefit_condition_service,
]

# Expose any remaining symbols dynamically
for _mod in _all_submodules:
    for _name in getattr(_mod, "__all__", dir(_mod)):
        if not _name.startswith("__") and _name not in globals():
            globals()[_name] = getattr(_mod, _name)


class _BusinessSetupModule(sys.modules[__name__].__class__):  # type: ignore[misc]
    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        if name != "__class__" and "_all_submodules" in globals():
            for _mod in _all_submodules:
                setattr(_mod, name, value)


sys.modules[__name__].__class__ = _BusinessSetupModule  # type: ignore[assignment]
