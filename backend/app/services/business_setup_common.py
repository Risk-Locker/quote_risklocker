"""Shared constants and helper functions for business setup services."""

from __future__ import annotations

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




BUSINESS_ROLES = frozenset({Role.STAFF.value, Role.ADMIN.value, Role.SUPER_ADMIN.value})
OFFERING_KINDS = frozenset({"base", "upgrade", "optional", "package_component"})
STATUSES = frozenset({"active", "inactive", "retired"})
ALIAS_KINDS = frozenset({"detection", "legal_name", "brand", "product", "compatibility"})
VARIANT_TYPES = frozenset({"money", "distance", "duration"})


__all__ = ['_require_business', '_slug', '_require_revision', '_audit', '_asset_summary', '_normalize_string_list', 'BUSINESS_ROLES', 'OFFERING_KINDS', 'STATUSES', 'ALIAS_KINDS', 'VARIANT_TYPES']


def _require_business(user) -> None:
    if user.role not in BUSINESS_ROLES:
        raise AppError("You do not have permission to manage Business Setup.", 403)



def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")



def _require_revision(record, supplied: int | None, label: str) -> None:
    if supplied is None or record.revision != supplied:
        raise AppError(f"This {label} changed elsewhere. Reload before saving.", 409)



def _audit(db, user, action: str, entity_type: str, entity_id: str, details: dict) -> None:
    actor_id = getattr(user, "id", str(user)) if user is not None else None
    db.add(AuditEvent(actor_id=actor_id, action=action, entity_type=entity_type, entity_id=entity_id, details=details))



def _asset_summary(asset: BusinessAsset | None) -> dict | None:
    if asset is None:
        return None
    return {
        "id": asset.id,
        "asset_key": asset.asset_key,
        "asset_kind": asset.asset_kind,
        "category": getattr(asset, "category", "General") or "General",
        "label": asset.label,
        "original_filename": getattr(asset, "original_filename", ""),
        "size_bytes": getattr(asset, "size_bytes", 0),
        "width_px": asset.width_px,
        "height_px": asset.height_px,
        "status": asset.status,
        "url": f"/business/assets/{asset.id}/content?profile=ui",
    }



def _normalize_string_list(values, label: str) -> list[str]:
    output: list[str] = []
    for value in values or []:
        text = str(value).strip()
        if not text:
            continue
        if len(text) > 500:
            raise AppError(f"{label} entries must be at most 500 characters.", 422)
        output.append(text)
    return list(dict.fromkeys(output))

