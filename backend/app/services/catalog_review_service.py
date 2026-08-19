"""Pin an unambiguous published catalog and seed its reviewed base benefits."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy import select

from app.domain.benefits import BenefitValue
from app.models.tables import (
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitPackage,
    BenefitRelation,
    CatalogOffering,
    DraftBenefitSelection,
    DraftSourceLineDecision,
    ExtractionBenefitLine,
    ExtractionRecord,
    InsuranceProduct,
    InsuranceProductTier,
    QuotationDraft,
    new_id,
)


def _rows(db, model) -> list:
    return list(db.scalars(select(model)).all())


def _field_value(fields: dict, *names: str) -> str:
    for name in names:
        raw = (fields or {}).get(name)
        value = raw.get("value") if isinstance(raw, dict) else raw
        if str(value or "").strip():
            return str(value).strip()
    return ""


def _single_exact(rows: list, name: str) -> object | None:
    matches = [item for item in rows if str(getattr(item, "name", "")).strip().casefold() == name.casefold()]
    return matches[0] if len(matches) == 1 else None


def pin_catalog_context(db, draft: QuotationDraft) -> BenefitCatalogRevision | None:
    """Pin only an exact, unambiguous catalog context; never guess an arbitrary catalog."""

    if not draft.company_id:
        return None

    # 1. Resolve product
    products = [item for item in _rows(db, InsuranceProduct) if item.company_id == draft.company_id and item.status == "active"]
    if draft.product_id and all(item.id != draft.product_id for item in products):
        draft.product_id = None
    product_name = _field_value(draft.fields or {}, "product_name", "product")
    if not draft.product_id and product_name:
        exact = _single_exact(products, product_name)
        if exact:
            draft.product_id = exact.id
    if not draft.product_id and not product_name and len(products) == 1:
        draft.product_id = products[0].id

    # 2. Resolve legacy tier (if product has tiers)
    tiers = [item for item in _rows(db, InsuranceProductTier) if item.product_id == draft.product_id and item.status == "active"] if draft.product_id else []
    if draft.tier_id and all(item.id != draft.tier_id for item in tiers):
        draft.tier_id = None
    tier_name = _field_value(draft.fields or {}, "tier_name", "product_tier", "plan_name")
    if not draft.tier_id and tier_name:
        exact = _single_exact(tiers, tier_name)
        if exact:
            draft.tier_id = exact.id
    if not draft.tier_id and not tier_name and len(tiers) == 1:
        draft.tier_id = tiers[0].id

    # 3. Find candidate catalogs
    catalogs = [
        item for item in _rows(db, BenefitCatalog)
        if item.company_id == draft.company_id
        and item.status in {"active", "published", "draft"}
    ]
    if draft.product_id:
        catalogs = [item for item in catalogs if item.product_id == draft.product_id]
    if tiers:
        if not draft.tier_id:
            # Ambiguous tier required
            draft.catalog_revision_id = None
            return None
        catalogs = [item for item in catalogs if item.tier_id == draft.tier_id]

    if not catalogs or len(catalogs) != 1:
        # If no single catalog found, check if there is exactly 1 catalog for this company
        company_catalogs = [
            item for item in _rows(db, BenefitCatalog)
            if item.company_id == draft.company_id and item.status in {"active", "published"}
        ]
        if len(company_catalogs) == 1:
            target_catalog = company_catalogs[0]
            if not draft.product_id and target_catalog.product_id:
                draft.product_id = target_catalog.product_id
        else:
            draft.catalog_revision_id = None
            return None
    else:
        target_catalog = catalogs[0]

    revisions = [
        item for item in _rows(db, BenefitCatalogRevision)
        if item.catalog_id == target_catalog.id and item.state == "published"
    ]
    if not revisions:
        draft.catalog_revision_id = None
        return None

    revision = max(revisions, key=lambda item: (int(item.revision_number), str(item.id)))
    draft.catalog_revision_id = revision.id
    if target_catalog.tier_id and not draft.tier_id:
        draft.tier_id = target_catalog.tier_id
    return revision


def seed_base_benefits(db, draft: QuotationDraft, revision: BenefitCatalogRevision) -> int:
    existing = [item for item in _rows(db, DraftBenefitSelection) if item.draft_id == draft.id]
    existing_offerings = {item.catalog_offering_id for item in existing if item.catalog_offering_id}
    existing_concepts = {item.concept_id for item in existing if item.state == "current" and item.concept_id}

    # Find catalog to check primary package
    catalogs = [item for item in _rows(db, BenefitCatalog) if item.id == revision.catalog_id]
    primary_pkg_id = catalogs[0].package_id if catalogs else None

    # Filter offerings belonging to this revision that are included/base
    all_offerings = [
        item for item in _rows(db, CatalogOffering)
        if item.catalog_revision_id == revision.id and item.status in {"active", "compatibility"}
    ]

    base_offerings = []
    for item in all_offerings:
        is_included = item.role == "included" or (item.offering_kind == "base" and item.role is None)
        if not is_included:
            continue
        # If package hierarchy applies, only seed offerings for the primary package (or product-wide)
        if primary_pkg_id and item.applies_to_type == "package" and item.applies_to_id != primary_pkg_id:
            continue
        base_offerings.append(item)

    created = 0
    for offering in sorted(base_offerings, key=lambda item: (int(item.sort_order or 0), item.offering_key)):
        if offering.id in existing_offerings or offering.concept_id in existing_concepts:
            continue
        db.add(DraftBenefitSelection(
            id=new_id(),
            draft_id=draft.id,
            selection_key=f"catalog:{offering.offering_key}"[:160],
            catalog_offering_id=offering.id,
            concept_id=offering.concept_id,
            item_kind="catalog",
            state="current",
            cost_status="included",
            label_override=offering.label_override,
            typed_value_override=None,
            evidence_snapshot={"catalog_revision_id": revision.id, "source": "published_base"},
            sort_order=int(offering.sort_order or 0),
        ))
        existing_offerings.add(offering.id)
        existing_concepts.add(offering.concept_id)
        created += 1
    return created


def initialize_catalog_review(db, draft: QuotationDraft) -> dict:
    revision = pin_catalog_context(db, draft)
    if revision is None:
        return {"catalog_revision_id": None, "base_benefits_created": 0}
    return {
        "catalog_revision_id": revision.id,
        "base_benefits_created": seed_base_benefits(db, draft, revision),
    }


def _normalized_value(value) -> dict | None:
    try:
        return BenefitValue.model_validate(value).model_dump(mode="json", exclude_none=True)
    except Exception:
        return None


def _scalar_equal(left, right) -> bool:
    try:
        return Decimal(str(left)) == Decimal(str(right))
    except (InvalidOperation, TypeError, ValueError):
        return str(left) == str(right)


def _value_matches(typed_value, extracted: dict | None) -> bool:
    left = _normalized_value(typed_value)
    right = _normalized_value(extracted)
    if left is None or right is None:
        return False
    for key in ("type", "value", "unit", "unlimited", "region", "currency", "max_days"):
        if left.get(key) is None and right.get(key) is None:
            continue
        if key == "value":
            if left.get("value") is not None or right.get("value") is not None:
                if not _scalar_equal(left.get("value"), right.get("value")):
                    return False
            continue
        if str(left.get(key) or "") != str(right.get(key) or ""):
            return False
    return True


def auto_apply_extracted_benefits(db, draft: QuotationDraft) -> dict:
    """Apply confidently extracted benefit values onto the pinned catalog.

    Upgrades replace their current in place; unknown variants become exact
    overrides; unmatched selected lines stay as source-only evidence.
    """

    if not draft.catalog_revision_id:
        return {"applied": 0}
    extraction = db.scalar(
        select(ExtractionRecord).where(ExtractionRecord.uploaded_file_id == draft.uploaded_file_id)
    )
    if extraction is None:
        return {"applied": 0}
    lines = [
        item for item in db.scalars(
            select(ExtractionBenefitLine).where(ExtractionBenefitLine.extraction_record_id == extraction.id)
        ).all()
        if item.extraction_record_id == extraction.id
    ]
    decisions = {
        item.source_line_id: item
        for item in db.scalars(
            select(DraftSourceLineDecision).where(DraftSourceLineDecision.draft_id == draft.id)
        ).all()
        if item.draft_id == draft.id
    }
    selections = [
        item for item in db.scalars(
            select(DraftBenefitSelection).where(DraftBenefitSelection.draft_id == draft.id)
        ).all()
        if item.draft_id == draft.id
    ]
    offerings = [
        item for item in db.scalars(
            select(CatalogOffering).where(CatalogOffering.catalog_revision_id == draft.catalog_revision_id)
        ).all()
        if item.catalog_revision_id == draft.catalog_revision_id
    ]
    offering_by_id = {item.id: item for item in offerings}
    relations = [
        item for item in db.scalars(
            select(BenefitRelation).where(BenefitRelation.catalog_revision_id == draft.catalog_revision_id)
        ).all()
        if item.catalog_revision_id == draft.catalog_revision_id
    ]
    applied = 0

    for line in sorted(lines, key=lambda item: int(item.page_number or 0)):
        decision = decisions.get(line.id)
        if decision is None:
            continue
        extracted = line.extracted_value if isinstance(line.extracted_value, dict) else None
        selected = str(line.inclusion_state) == "selected"
        if selected and extracted is not None:
            for mapping in list(line.candidate_mappings or []):
                concept_id = mapping.get("concept_id")
                if not concept_id:
                    continue
                concept_offerings = [item for item in offerings if str(item.concept_id) == str(concept_id)]
                current = next(
                    (item for item in selections if str(item.concept_id) == str(concept_id) and item.state == "current"),
                    None,
                )
                if current is not None and current.catalog_offering_id in offering_by_id:
                    current_offering = offering_by_id[current.catalog_offering_id]
                    if _value_matches(current_offering.typed_value, extracted):
                        decision.disposition = "mapped"
                        decision.selection_id = current.id
                        break
                    # Check relations or same-concept upgrade options without requiring an explicit edge
                    upgrade_ids = {
                        item.to_offering_id
                        for item in relations
                        if item.from_offering_id == current.catalog_offering_id and item.relation_kind == "replaces"
                    }
                    matched = next((item for item in concept_offerings if item.id in upgrade_ids and _value_matches(item.typed_value, extracted)), None)
                    if matched is None:
                        # Allow same-concept upgrade options matching extracted value
                        matched = next(
                            (item for item in concept_offerings if (item.offering_kind in {"upgrade", "optional"} or item.role == "addon_option") and _value_matches(item.typed_value, extracted)),
                            None,
                        )
                    if matched is not None:
                        selection_id = new_id()
                        current.state = "superseded"
                        current.superseded_by_id = selection_id
                        new_selection = DraftBenefitSelection(
                            id=selection_id,
                            draft_id=draft.id,
                            selection_key=f"catalog:{matched.offering_key}"[:160],
                            catalog_offering_id=matched.id,
                            concept_id=concept_id,
                            item_kind="catalog",
                            state="current",
                            cost_status=current.cost_status or "included",
                            label_override=matched.label_override,
                            typed_value_override=None,
                            evidence_snapshot={"source_line_id": line.id, "source": "extracted_upgrade"},
                            sort_order=int(matched.sort_order or 0),
                            selected_by=draft.owner_id,
                        )
                        db.add(new_selection)
                        selections.append(new_selection)
                        applied += 1
                        decision.disposition = "mapped"
                        decision.selection_id = selection_id
                    else:
                        current.typed_value_override = extracted
                        applied += 1
                        decision.disposition = "mapped"
                        decision.selection_id = current.id
                    break
                if current is None:
                    optionals = [item for item in concept_offerings if item.offering_kind in {"optional", "upgrade"} or item.role == "addon_option"]
                    matched = next((item for item in optionals if _value_matches(item.typed_value, extracted)), None)
                    if matched is None and len(optionals) == 1:
                        matched = optionals[0]
                    if matched is not None:
                        selection_id = new_id()
                        new_selection = DraftBenefitSelection(
                            id=selection_id,
                            draft_id=draft.id,
                            selection_key=f"catalog:{matched.offering_key}"[:160],
                            catalog_offering_id=matched.id,
                            concept_id=concept_id,
                            item_kind="catalog",
                            state="current",
                            cost_status="paid",
                            label_override=matched.label_override,
                            typed_value_override=extracted if not _value_matches(matched.typed_value, extracted) else None,
                            evidence_snapshot={"source_line_id": line.id, "source": "extracted_addon"},
                            sort_order=int(matched.sort_order or 0),
                            selected_by=draft.owner_id,
                        )
                        db.add(new_selection)
                        selections.append(new_selection)
                        applied += 1
                        decision.disposition = "mapped"
                        decision.selection_id = selection_id
                        break
        if decision.disposition == "unresolved":
            decision.disposition = "source_only" if selected else "omitted"
    return {"applied": applied}
