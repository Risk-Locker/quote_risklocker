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
    BenefitPackage,
    BenefitRelation,
    CatalogOffering,
    CoverageType,
    DraftBenefitSelection,
    DraftSourceLineDecision,
    ExtractionBenefitLine,
    ExtractionRecord,
    InsuranceProduct,
    InsuranceProductTier,
    QuotationDraft,
    VehicleCategory,
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


def test_package_based_catalog_pinning_and_primary_package_seeding():
    product = InsuranceProduct(id="prod-qbe", company_id="comp-qbe", product_key="qbe-pc", name="QBE Private Car", status="active")
    catalog = BenefitCatalog(id="cat-qbe", company_id="comp-qbe", product_id=product.id, name="QBE Private Car", status="published", package_id="pkg-lite")
    revision = BenefitCatalogRevision(id="rev-qbe", catalog_id=catalog.id, revision_number=1, state="published", content_hash="d" * 64)
    lite_towing = CatalogOffering(id="off-lite-tow", catalog_revision_id=revision.id, offering_key="lite-tow", concept_id="c-tow", offering_kind="base", role="included", applies_to_type="package", applies_to_id="pkg-lite", status="active")
    plus_towing = CatalogOffering(id="off-plus-tow", catalog_revision_id=revision.id, offering_key="plus-tow", concept_id="c-tow", offering_kind="base", role="included", applies_to_type="package", applies_to_id="pkg-plus", status="active")
    lite_windscreen = CatalogOffering(id="off-lite-ws", catalog_revision_id=revision.id, offering_key="lite-ws", concept_id="c-ws", offering_kind="optional", role="addon_option", applies_to_type="package", applies_to_id="pkg-lite", status="active")

    draft = QuotationDraft(id="draft-qbe", uploaded_file_id="f-qbe", owner_id="u-1", company_id="comp-qbe", fields={"product_name": {"value": "QBE Private Car"}}, scalar_decisions={}, warnings=[])
    db = FakeDb([product, catalog, revision, lite_towing, plus_towing, lite_windscreen])

    res = initialize_catalog_review(db, draft)
    assert res["catalog_revision_id"] == revision.id
    assert res["base_benefits_created"] == 1
    selections = [item for item in db.added if isinstance(item, DraftBenefitSelection)]
    assert len(selections) == 1
    assert selections[0].catalog_offering_id == lite_towing.id


def test_stale_primary_package_falls_back_to_revision_lite_package():
    product = InsuranceProduct(id="prod-am", company_id="comp-am", name="Private Car Comprehensive", status="active")
    catalog = BenefitCatalog(id="cat-am", company_id="comp-am", product_id=product.id, name="Private Car Comprehensive", status="published", package_id="pkg-stale-other-revision")
    revision = BenefitCatalogRevision(id="rev-am", catalog_id=catalog.id, revision_number=2, state="published", content_hash="f" * 64)
    lite = BenefitPackage(id="pkg-lite", catalog_revision_id=revision.id, package_key="lite", name="auto365 Comprehensive Lite", package_kind="comprehensive", sort_order=1, status="active")
    top = BenefitPackage(id="pkg-top", catalog_revision_id=revision.id, package_key="top", name="Private Car Comprehensive", package_kind="comprehensive", sort_order=4, status="active")
    lite_towing = CatalogOffering(id="off-lite-tow", catalog_revision_id=revision.id, offering_key="lite-tow", concept_id="c-tow", offering_kind="base", role="included", applies_to_type="package", applies_to_id=lite.id, status="active")
    top_towing = CatalogOffering(id="off-top-tow", catalog_revision_id=revision.id, offering_key="top-tow", concept_id="c-tow", offering_kind="base", role="included", applies_to_type="package", applies_to_id=top.id, status="active")

    draft = QuotationDraft(id="draft-am", uploaded_file_id="f-am", owner_id="u-1", company_id="comp-am", fields={"product_name": {"value": "Private Car Comprehensive"}}, scalar_decisions={}, warnings=[])
    db = FakeDb([product, catalog, revision, lite, top, lite_towing, top_towing])

    res = initialize_catalog_review(db, draft)

    assert res["catalog_revision_id"] == revision.id
    selections = [item for item in db.added if isinstance(item, DraftBenefitSelection)]
    assert [item.catalog_offering_id for item in selections] == [lite_towing.id]


def test_same_concept_addon_upgrade_supersedes_without_relations_edge():
    product = InsuranceProduct(id="prod-1", company_id="comp-1", name="Product", status="active")
    catalog = BenefitCatalog(id="cat-1", company_id="comp-1", product_id=product.id, name="Product", status="published")
    revision = BenefitCatalogRevision(id="rev-1", catalog_id=catalog.id, revision_number=1, state="published", content_hash="e" * 64)
    base_towing = CatalogOffering(id="off-base", catalog_revision_id=revision.id, offering_key="tow-50", concept_id="c-tow", offering_kind="base", role="included", typed_value={"type": "distance", "value": "50", "unit": "km"}, status="active")
    upgrade_towing = CatalogOffering(id="off-upg", catalog_revision_id=revision.id, offering_key="tow-150", concept_id="c-tow", offering_kind="optional", role="addon_option", typed_value={"type": "distance", "value": "150", "unit": "km"}, status="active")

    extraction = ExtractionRecord(id="ext-1", uploaded_file_id="f-1", benefit_lines=[], company_resolution={}, candidates={}, warnings=[])
    line = ExtractionBenefitLine(id="l-1", extraction_record_id=extraction.id, line_id="p1-l1", raw_label="Towing 150 km", normalized_label="towing 150 km", page_number=1, source_scope="quotation_selected", line_kind="benefit_candidate", inclusion_state="selected", evidence={}, candidate_mappings=[{"concept_id": "c-tow", "label": "Towing"}], extracted_value={"type": "distance", "value": "150", "unit": "km"})
    decision = DraftSourceLineDecision(id="dec-1", draft_id="draft-1", source_line_id=line.id, disposition="unresolved")
    current_sel = DraftBenefitSelection(id="sel-base", draft_id="draft-1", selection_key="catalog:tow-50", catalog_offering_id=base_towing.id, concept_id="c-tow", item_kind="catalog", state="current", cost_status="included", evidence_snapshot={}, sort_order=0)
    draft = QuotationDraft(id="draft-1", uploaded_file_id="f-1", owner_id="u-1", company_id="comp-1", product_id=product.id, catalog_revision_id=revision.id, fields={}, scalar_decisions={}, warnings=[])

    # Note: NO BenefitRelation objects in db!
    db = FakeDb([product, catalog, revision, base_towing, upgrade_towing, extraction, line, decision, current_sel, draft])

    result = auto_apply_extracted_benefits(db, draft)
    assert result["applied"] == 1
    assert current_sel.state == "superseded"
    new_sel = next(item for item in db.added if isinstance(item, DraftBenefitSelection))
    assert new_sel.catalog_offering_id == upgrade_towing.id
    assert new_sel.state == "current"
    assert decision.disposition == "mapped"


def test_multi_catalog_vehicle_dimension_resolution():
    v_car = VehicleCategory(id="v-car", category_key="car", name="Private Car")
    v_lorry = VehicleCategory(id="v-lorry", category_key="commercial_vehicle", name="Commercial Vehicle")

    cat_car = BenefitCatalog(id="cat-car", company_id="comp-qbe", name="Private Car Protector", vehicle_category_id=v_car.id, status="published")
    rev_car = BenefitCatalogRevision(id="rev-car", catalog_id=cat_car.id, revision_number=1, state="published", content_hash="1" * 64)

    cat_lorry = BenefitCatalog(id="cat-lorry", company_id="comp-qbe", name="Commercial Vehicle Protector", vehicle_category_id=v_lorry.id, status="published")
    rev_lorry = BenefitCatalogRevision(id="rev-lorry", catalog_id=cat_lorry.id, revision_number=1, state="published", content_hash="2" * 64)

    # Draft with vehicle_type = "Lorry"
    draft_lorry = QuotationDraft(
        id="draft-l", uploaded_file_id="f-1", owner_id="u-1", company_id="comp-qbe",
        fields={"vehicle_type": {"value": "ISUZU LORRY 3 TON"}}, scalar_decisions={}, warnings=[],
    )
    db = FakeDb([v_car, v_lorry, cat_car, rev_car, cat_lorry, rev_lorry])

    res = initialize_catalog_review(db, draft_lorry)
    assert res["catalog_revision_id"] == rev_lorry.id
    assert draft_lorry.catalog_revision_id == rev_lorry.id

    # Draft with car_model = "HONDA CIVIC"
    draft_car = QuotationDraft(
        id="draft-c", uploaded_file_id="f-2", owner_id="u-1", company_id="comp-qbe",
        fields={"car_model": {"value": "HONDA CIVIC 1.5 SEDAN"}}, scalar_decisions={}, warnings=[],
    )
    res_car = initialize_catalog_review(db, draft_car)
    assert res_car["catalog_revision_id"] == rev_car.id
    assert draft_car.catalog_revision_id == rev_car.id


def test_multi_catalog_coverage_dimension_resolution():
    c_comp = CoverageType(id="c-comp", coverage_key="comprehensive", name="Comprehensive")
    c_tpft = CoverageType(id="c-tpft", coverage_key="third_party_fire_theft", name="Third Party, Fire and Theft")

    cat_comp = BenefitCatalog(id="cat-comp", company_id="comp-etiqa", name="Etiqa Comprehensive", coverage_type_id=c_comp.id, status="published")
    rev_comp = BenefitCatalogRevision(id="rev-comp", catalog_id=cat_comp.id, revision_number=1, state="published", content_hash="3" * 64)

    cat_tpft = BenefitCatalog(id="cat-tpft", company_id="comp-etiqa", name="Etiqa TPFT", coverage_type_id=c_tpft.id, status="published")
    rev_tpft = BenefitCatalogRevision(id="rev-tpft", catalog_id=cat_tpft.id, revision_number=1, state="published", content_hash="4" * 64)

    draft_tpft = QuotationDraft(
        id="draft-tpft", uploaded_file_id="f-3", owner_id="u-1", company_id="comp-etiqa",
        fields={"coverage_type": {"value": "Third Party Fire & Theft"}}, scalar_decisions={}, warnings=[],
    )
    db = FakeDb([c_comp, c_tpft, cat_comp, rev_comp, cat_tpft, rev_tpft])

    res = initialize_catalog_review(db, draft_tpft)
    assert res["catalog_revision_id"] == rev_tpft.id
    assert draft_tpft.catalog_revision_id == rev_tpft.id

