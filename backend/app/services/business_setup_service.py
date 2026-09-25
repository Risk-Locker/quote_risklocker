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

# Expose all symbols from submodules onto this facade module
for _mod in _all_submodules:
    for _name in getattr(_mod, "__all__", dir(_mod)):
        if not _name.startswith("__"):
            globals()[_name] = getattr(_mod, _name)


class _BusinessSetupModule(sys.modules[__name__].__class__):  # type: ignore[misc]
    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        if name != "__class__" and "_all_submodules" in globals():
            for _mod in _all_submodules:
                setattr(_mod, name, value)


sys.modules[__name__].__class__ = _BusinessSetupModule
