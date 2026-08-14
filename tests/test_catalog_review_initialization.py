from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.models.tables import (  # noqa: E402
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitRelation,
    CatalogOffering,
    DraftBenefitSelection,
    DraftSourceLineDecision,
    ExtractionBenefitLine,
    ExtractionRecord,
    InsuranceProduct,
    InsuranceProductTier,
    QuotationDraft,
)
from app.services.catalog_review_service import (  # noqa: E402
    auto_apply_extracted_benefits,
    initialize_catalog_review,
)


class FakeDb:
    def __init__(self, rows):
        self.rows = list(rows)
        self.added = []

    def scalars(self, statement):
        model = statement.column_descriptions[0]["entity"]
        return SimpleNamespace(all=lambda: [item for item in [*self.rows, *self.added] if isinstance(item, model)])

    def scalar(self, statement):
        rows = self.scalars(statement).all()
        return rows[0] if rows else None

    def add(self, item):
        self.added.append(item)


def test_exact_product_and_tier_pin_latest_published_revision_and_seed_bases():
    product = InsuranceProduct(id="product-1", company_id="company-1", name="Motor Plus", status="active")
    tier = InsuranceProductTier(id="tier-1", product_id=product.id, name="Premier", status="active")
    catalog = BenefitCatalog(id="catalog-1", company_id="company-1", product_id=product.id, tier_id=tier.id, name="Premier", status="published")
    old = BenefitCatalogRevision(id="revision-1", catalog_id=catalog.id, revision_number=1, state="published", content_hash="a" * 64)
    latest = BenefitCatalogRevision(id="revision-2", catalog_id=catalog.id, revision_number=2, state="published", content_hash="b" * 64)
    towing = CatalogOffering(id="offering-towing", catalog_revision_id=latest.id, offering_key="towing-50", concept_id="concept-towing", offering_kind="base", typed_value={"type": "distance", "value": 50, "unit": "km"}, status="active")
    optional = CatalogOffering(id="offering-flood", catalog_revision_id=latest.id, offering_key="flood", concept_id="concept-flood", offering_kind="optional", status="active")
    draft = QuotationDraft(id="draft-1", uploaded_file_id="file-1", owner_id="owner-1", company_id="company-1", fields={"product_name": {"value": "Motor Plus"}, "tier_name": {"value": "Premier"}}, scalar_decisions={}, warnings=[])
    db = FakeDb([product, tier, catalog, old, latest, towing, optional])

    result = initialize_catalog_review(db, draft)

    selections = [item for item in db.added if isinstance(item, DraftBenefitSelection)]
    assert result == {"catalog_revision_id": latest.id, "base_benefits_created": 1}
    assert draft.product_id == product.id and draft.tier_id == tier.id and draft.catalog_revision_id == latest.id
    assert [(item.catalog_offering_id, item.state, item.cost_status) for item in selections] == [(towing.id, "current", "included")]


def test_ambiguous_or_unverified_context_stays_unpinned_and_invents_nothing():
    first = InsuranceProduct(id="product-1", company_id="company-1", name="Motor", status="active")
    second = InsuranceProduct(id="product-2", company_id="company-1", name="Motor", status="active")
    draft = QuotationDraft(id="draft-1", uploaded_file_id="file-1", owner_id="owner-1", company_id="company-1", fields={"product_name": {"value": "Motor"}}, scalar_decisions={}, warnings=[])
    db = FakeDb([first, second])

    assert initialize_catalog_review(db, draft) == {"catalog_revision_id": None, "base_benefits_created": 0}
    assert draft.product_id is None and draft.catalog_revision_id is None
    assert not db.added


def test_single_product_and_tier_are_pinned_without_extracted_names():
    product = InsuranceProduct(id="product-1", company_id="company-1", name="Motor Plus", status="active")
    tier = InsuranceProductTier(id="tier-1", product_id=product.id, name="Standard", status="active")
    catalog = BenefitCatalog(id="catalog-1", company_id="company-1", product_id=product.id, tier_id=tier.id, name="Standard", status="published")
    revision = BenefitCatalogRevision(id="revision-1", catalog_id=catalog.id, revision_number=1, state="published", content_hash="c" * 64)
    base = CatalogOffering(id="offering-1", catalog_revision_id=revision.id, offering_key="towing-50", concept_id="concept-towing", offering_kind="base", typed_value={"type": "distance", "value": 50, "unit": "km"}, status="active")
    draft = QuotationDraft(id="draft-1", uploaded_file_id="file-1", owner_id="owner-1", company_id="company-1", fields={"customer_name": {"value": "A", "status": "ready"}}, scalar_decisions={}, warnings=[])
    db = FakeDb([product, tier, catalog, revision, base])

    result = initialize_catalog_review(db, draft)

    assert draft.product_id == product.id and draft.tier_id == tier.id and draft.catalog_revision_id == revision.id
    assert result == {"catalog_revision_id": revision.id, "base_benefits_created": 1}


def test_ambiguous_tier_never_pins_even_when_product_is_unique():
    product = InsuranceProduct(id="product-1", company_id="company-1", name="Motor Plus", status="active")
    first = InsuranceProductTier(id="tier-1", product_id=product.id, name="Standard", status="active")
    second = InsuranceProductTier(id="tier-2", product_id=product.id, name="Premier", status="active")
    draft = QuotationDraft(id="draft-1", uploaded_file_id="file-1", owner_id="owner-1", company_id="company-1", fields={"product_name": {"value": "Motor Plus"}}, scalar_decisions={}, warnings=[])
    db = FakeDb([product, first, second])

    assert initialize_catalog_review(db, draft) == {"catalog_revision_id": None, "base_benefits_created": 0}
    assert draft.product_id == product.id and draft.tier_id is None and draft.catalog_revision_id is None


def test_stale_product_and_tier_ids_are_cleared_before_pinning():
    product = InsuranceProduct(id="product-1", company_id="company-1", name="Motor Plus", status="active")
    draft = QuotationDraft(
        id="draft-1", uploaded_file_id="file-1", owner_id="owner-1", company_id="company-1",
        product_id="product-stale", tier_id="tier-stale", catalog_revision_id="revision-stale",
        fields={"customer_name": {"value": "A", "status": "ready"}}, scalar_decisions={}, warnings=[],
    )
    db = FakeDb([product])

    assert initialize_catalog_review(db, draft) == {"catalog_revision_id": None, "base_benefits_created": 0}
    assert draft.product_id == product.id
    assert draft.tier_id is None and draft.catalog_revision_id is None


def _pinned_catalog_objects():
    product = InsuranceProduct(id="product-1", company_id="company-1", name="Motor Plus", status="active")
    tier = InsuranceProductTier(id="tier-1", product_id=product.id, name="Standard", status="active")
    catalog = BenefitCatalog(id="catalog-1", company_id="company-1", product_id=product.id, tier_id=tier.id, name="Standard", status="published")
    revision = BenefitCatalogRevision(id="revision-1", catalog_id=catalog.id, revision_number=1, state="published", content_hash="c" * 64)
    return product, tier, catalog, revision


def test_extracted_upgrade_value_replaces_current_and_maps_the_source_line():
    product, _tier, _catalog, revision = _pinned_catalog_objects()
    base = CatalogOffering(id="offering-base", catalog_revision_id=revision.id, offering_key="towing-50", concept_id="concept-towing", offering_kind="base", typed_value={"type": "distance", "value": 50, "unit": "km"}, status="active")
    upgrade = CatalogOffering(id="offering-up", catalog_revision_id=revision.id, offering_key="towing-200", concept_id="concept-towing", offering_kind="upgrade", typed_value={"type": "distance", "value": 200, "unit": "km"}, status="active", sort_order=1)
    relation = BenefitRelation(id="relation-1", catalog_revision_id=revision.id, from_offering_id=base.id, to_offering_id=upgrade.id, relation_kind="replaces", sort_order=1)
    extraction = ExtractionRecord(id="extraction-1", uploaded_file_id="file-1", benefit_lines=[], company_resolution={}, candidates={}, warnings=[])
    line = ExtractionBenefitLine(id="line-1", extraction_record_id=extraction.id, line_id="p1-l1", raw_label="Towing", normalized_label="towing", page_number=1, source_scope="quotation_selected", line_kind="benefit_candidate", inclusion_state="selected", evidence={}, candidate_mappings=[{"concept_id": "concept-towing", "label": "Towing"}], extracted_value={"type": "distance", "value": 200, "unit": "km"})
    current = DraftBenefitSelection(id="selection-base", draft_id="draft-1", selection_key="catalog:towing-50", catalog_offering_id=base.id, concept_id=base.concept_id, item_kind="catalog", state="current", cost_status="included", evidence_snapshot={}, sort_order=0)
    decision = DraftSourceLineDecision(id="decision-1", draft_id="draft-1", source_line_id=line.id, disposition="unresolved")
    draft = QuotationDraft(id="draft-1", uploaded_file_id="file-1", owner_id="owner-1", company_id="company-1", product_id=product.id, tier_id=_tier.id, catalog_revision_id=revision.id, fields={}, scalar_decisions={}, warnings=[])
    db = FakeDb([product, _tier, _catalog, revision, base, upgrade, relation, extraction, line, current, decision, draft])

    result = auto_apply_extracted_benefits(db, draft)

    assert result["applied"] == 1
    assert current.state == "superseded"
    selected = next(item for item in db.added if isinstance(item, DraftBenefitSelection))
    assert selected.catalog_offering_id == upgrade.id and selected.state == "current" and selected.cost_status == "included"
    assert decision.disposition == "mapped" and decision.selection_id == selected.id


def test_unmatched_extracted_value_becomes_exact_override_and_unknown_lines_stay_non_blocking():
    product, _tier, _catalog, revision = _pinned_catalog_objects()
    base = CatalogOffering(id="offering-base", catalog_revision_id=revision.id, offering_key="towing-50", concept_id="concept-towing", offering_kind="base", typed_value={"type": "distance", "value": 50, "unit": "km"}, status="active")
    extraction = ExtractionRecord(id="extraction-1", uploaded_file_id="file-1", benefit_lines=[], company_resolution={}, candidates={}, warnings=[])
    line = ExtractionBenefitLine(id="line-1", extraction_record_id=extraction.id, line_id="p1-l1", raw_label="Towing", normalized_label="towing", page_number=1, source_scope="quotation_selected", line_kind="benefit_candidate", inclusion_state="selected", evidence={}, candidate_mappings=[{"concept_id": "concept-towing", "label": "Towing"}], extracted_value={"type": "distance", "value": 900, "unit": "km"})
    odd = ExtractionBenefitLine(id="line-2", extraction_record_id=extraction.id, line_id="p1-l2", raw_label="Something odd", normalized_label="something odd", page_number=1, source_scope="narrative", line_kind="narrative", inclusion_state="selected", evidence={}, candidate_mappings=[], extracted_value=None)
    current = DraftBenefitSelection(id="selection-base", draft_id="draft-1", selection_key="catalog:towing-50", catalog_offering_id=base.id, concept_id=base.concept_id, item_kind="catalog", state="current", cost_status="included", evidence_snapshot={}, sort_order=0)
    decision = DraftSourceLineDecision(id="decision-1", draft_id="draft-1", source_line_id=line.id, disposition="unresolved")
    odd_decision = DraftSourceLineDecision(id="decision-2", draft_id="draft-1", source_line_id=odd.id, disposition="unresolved")
    draft = QuotationDraft(id="draft-1", uploaded_file_id="file-1", owner_id="owner-1", company_id="company-1", product_id=product.id, tier_id=_tier.id, catalog_revision_id=revision.id, fields={}, scalar_decisions={}, warnings=[])
    db = FakeDb([product, _tier, _catalog, revision, base, extraction, line, odd, current, decision, odd_decision, draft])

    result = auto_apply_extracted_benefits(db, draft)

    assert result["applied"] == 1
    assert current.typed_value_override == {"type": "distance", "value": 900, "unit": "km"}
    assert current.state == "current"
    assert decision.disposition == "mapped"
    assert odd_decision.disposition == "source_only"


def test_extracted_optional_addon_value_auto_selects_the_offer():
    product, _tier, _catalog, revision = _pinned_catalog_objects()
    flood = CatalogOffering(id="offering-flood", catalog_revision_id=revision.id, offering_key="flood", concept_id="concept-flood", offering_kind="optional", typed_value={"type": "money", "value": 5000, "currency": "MYR", "semantic_role": "limit"}, status="active")
    extraction = ExtractionRecord(id="extraction-1", uploaded_file_id="file-1", benefit_lines=[], company_resolution={}, candidates={}, warnings=[])
    line = ExtractionBenefitLine(id="line-1", extraction_record_id=extraction.id, line_id="p1-l1", raw_label="Flood", normalized_label="flood", page_number=1, source_scope="quotation_selected", line_kind="benefit_candidate", inclusion_state="selected", evidence={}, candidate_mappings=[{"concept_id": "concept-flood", "label": "Flood"}], extracted_value={"type": "money", "value": 5000, "currency": "MYR", "semantic_role": "limit"})
    decision = DraftSourceLineDecision(id="decision-1", draft_id="draft-1", source_line_id=line.id, disposition="unresolved")
    draft = QuotationDraft(id="draft-1", uploaded_file_id="file-1", owner_id="owner-1", company_id="company-1", product_id=product.id, tier_id=_tier.id, catalog_revision_id=revision.id, fields={}, scalar_decisions={}, warnings=[])
    db = FakeDb([product, _tier, _catalog, revision, flood, extraction, line, decision, draft])

    result = auto_apply_extracted_benefits(db, draft)

    assert result["applied"] == 1
    selected = next(item for item in db.added if isinstance(item, DraftBenefitSelection))
    assert selected.catalog_offering_id == flood.id and selected.state == "current" and selected.cost_status == "paid"
    assert decision.disposition == "mapped" and decision.selection_id == selected.id
