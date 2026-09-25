"""Canonical v7 quotation workspace snapshots and optimistic mutations (Facade)."""

from __future__ import annotations

import sys
from typing import Any

import re
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select, delete
from sqlalchemy.orm import defer, load_only
from sqlalchemy.orm.attributes import flag_modified

from app.core.errors import AppError
from app.domain.benefits import (
    BenefitValue,
    CostStatus,
    MoneyAmount,
    ReviewedBenefitState,
    SourceLineDisposition,
)
from app.models.enums import RecordStatus, Role
from app.models.tables import (
    AuditEvent,
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    BenefitFacet,
    BenefitPackage,
    BenefitPackagePlan,
    BenefitPackagePlanItem,
    BenefitRelation,
    CatalogOffering,
    CompanyBenefitCondition,
    CompanyBenefitConfig,
    CorrectionMemory,
    DraftBenefitSelection,
    DraftSourceLineDecision,
    ExtractionBenefitLine,
    ExtractionRecord,
    GeneratedPdfVersion,
    InsuranceCompany,
    InsuranceProduct,
    InsuranceProductTier,
    OutputTemplateConfig,
    QuotationDraft,
    Session,
    TemplateRevision,
    UploadedFile,
    new_id,
)
from app.rendering.render_context import (
    RenderContextError,
    adjusted_total_text,
    build_extras,
    format_benefit_value,
    resolve_benefit_cards,
)
from app.services.catalog_review_service import _resolve_vehicle_category, auto_apply_extracted_benefits, initialize_catalog_review, pin_catalog_context, seed_base_benefits
from app.extraction.validators import normalize_date, normalize_money, normalize_valuation_type
from app.extraction.benefit_lines import is_spurious_benefit_line




from app.services.workspace_common import (
    _field_summary,
    _require_business_user,
    _resolve_vehicle_category,
    _rows_for_draft,
    _session_and_draft,
    _template_for_draft,
    _utcnow,
    generation_blockers,
)
from app.services.workspace_snapshot_service import (
    _catalog_overview,
    _decision_summary,
    _selection_summary,
    _workspace_benefit_cards,
    _workspace_extracted_benefits_section,
    _workspace_package_tiers,
    _workspace_packs,
    build_workspace_snapshot,
    template_selection_impact,
    workspace_capabilities,
)
from app.services.workspace_patch_service import (
    apply_workspace_patch,
)

from app.services import (
    workspace_common,
    workspace_snapshot_service,
    workspace_patch_service,
)

_all_submodules = [
    workspace_common,
    workspace_snapshot_service,
    workspace_patch_service,
]

# Expose any remaining symbols dynamically
for _mod in _all_submodules:
    for _name in getattr(_mod, "__all__", dir(_mod)):
        if not _name.startswith("__") and _name not in globals():
            globals()[_name] = getattr(_mod, _name)


class _WorkspaceModule(sys.modules[__name__].__class__):  # type: ignore[misc]
    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        if name != "__class__" and "_all_submodules" in globals():
            for _mod in _all_submodules:
                setattr(_mod, name, value)


sys.modules[__name__].__class__ = _WorkspaceModule  # type: ignore[assignment]
