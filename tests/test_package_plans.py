"""Benefit pack plans: CRUD, publish hash, workspace ops, groups, and extras."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.errors import AppError
from app.models.enums import RecordStatus
from app.models.tables import (
    BenefitAlias,
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    BenefitPackage,
    BenefitPackagePlan,
    BenefitPackagePlanItem,
    CatalogOffering,
    DraftBenefitSelection,
    DraftSourceLineDecision,
    ExtractionRecord,
    QuotationDraft,
    Session,
    TemplateRevision,
    UploadedFile,
)
from app.rendering.render_context import (
    adjusted_total_text,
    build_extras,
    format_money_amount,
    resolve_benefit_cards,
)
from app.services.benefit_setup_service import save_plan, save_plan_items, retire_plan
from app.services.business_setup_service import _revision_content_payload
from app.services.catalog_review_service import auto_apply_extracted_benefits, seed_base_benefits
from app.services.workspace_service import _workspace_package_tiers, apply_workspace_patch
from app.extraction.gemini_extractor import build_rag_system_prompt


NOW = datetime.now(timezone.utc)


def _draft():
    return QuotationDraft(
        id="draft-1",
        uploaded_file_id="file-1",
        owner_id="owner-1",
        revision=3,
        fields={
            "customer_name": {"value": "Test Customer", "status": "ready", "message": ""},
            "insurance_company": {"value": "Nova Mutual", "status": "ready", "message": ""},
            "premium": {"value": "4286.55", "status": "ready", "message": ""},
            "roadtax": {"value": "70.00", "status": "ready", "message": ""},
            "service_fee": {"value": "50.00", "status": "ready", "message": ""},
            "total_amount": {"value": "2749.37", "status": "ready", "message": ""},
        },
        scalar_decisions={},
        warnings=[],
        status=RecordStatus.READY.value,
        template_revision_id="template-revision-1",
        catalog_revision_id="catalog-revision-1",
    )


class Scalars:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return list(self.rows)


class FakeDb:
    def __init__(self, values):
        self.values = {(type(item), item.id): item for item in values}
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def get(self, model, object_id):
        return self.values.get((model, object_id))

    def scalars(self, statement):
        entity = statement.column_descriptions[0].get("entity") if statement.column_descriptions else None
        rows = [item for (model, _id), item in self.values.items() if model is entity]
        return Scalars(rows)

    def scalar(self, statement):
        rows = self.scalars(statement).all()
        return rows[0] if rows else None

    def add(self, item):
        self.added.append(item)
        if getattr(item, "id", None):
            self.values[(type(item), item.id)] = item

    def delete(self, item):
        self.values.pop((type(item), item.id), None)

    def flush(self):
        return None

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, item):
        return None


def user(role="staff"):
    return SimpleNamespace(id="staff-1", role=role)


def plan_fixture_values(*, with_base_selection=True, staff_override=False):
    values = []
    uploaded = UploadedFile(
        id="file-1", batch_id="batch-1", owner_id="owner-1", original_filename="quote.pdf",
        content_type="application/pdf", storage_path="source/quote.pdf", storage_status="available",
        security_scan={"result": "clean"}, size_bytes=100, status=RecordStatus.READY.value,
    )
    draft = _draft()
    session = Session(id="session-1", owner_id="owner-1", uploaded_file_id=uploaded.id, draft_id=draft.id, status="active")
    template_revision = TemplateRevision(
        id="template-revision-1", template_id="template-1", revision_number=2, state="published",
        page_profile_id="profile-1", config={"canvas": {"width": 794, "height": 1123, "elements": []}}, config_hash="a" * 64,
    )
    values.extend([uploaded, draft, session, template_revision])

    catalog = BenefitCatalog(
        id="catalog-1", company_id="company-1", product_id=None, tier_id=None, package_id="package-main",
        name="Nova Catalog", revision=1, status="published",
    )
    revision = BenefitCatalogRevision(
        id="catalog-revision-1", catalog_id=catalog.id, revision_number=2, state="published",
        source_document_ids=[], content_hash="b" * 64,
    )
    main_package = BenefitPackage(
        id="package-main", catalog_revision_id=revision.id, package_key="main", name="Main",
        package_kind="comprehensive", sort_order=0, revision=1, status="active",
    )
    bundle = BenefitPackage(
        id="package-bundle", catalog_revision_id=revision.id, package_key="driver-protection",
        name="Driver Protection Pack", package_kind="addon_bundle", sort_order=1, revision=1, status="active",
    )
    plan = BenefitPackagePlan(
        id="plan-a", package_id=bundle.id, plan_key="plan-a", name="Driver Protection Plan A",
        sort_order=0, status="active",
    )
    values.extend([catalog, revision, main_package, bundle, plan])

    towing_base = CatalogOffering(
        id="offering-towing-50", catalog_revision_id=revision.id, offering_key="towing-50",
        concept_id="concept-towing", offering_kind="base",
        typed_value={"type": "distance", "value": 50, "unit": "km"}, status="active",
    )
    towing_up = CatalogOffering(
        id="offering-towing-200", catalog_revision_id=revision.id, offering_key="towing-200",
        concept_id="concept-towing", offering_kind="optional",
        typed_value={"type": "distance", "value": 200, "unit": "km"}, status="active",
    )
    pa = CatalogOffering(
        id="offering-pa", catalog_revision_id=revision.id, offering_key="personal-accident",
        concept_id="concept-pa", offering_kind="optional",
        typed_value={"type": "money", "value": 10000, "currency": "MYR", "semantic_role": "insured_limit"}, status="active",
    )
    values.extend([towing_base, towing_up, pa])

    plan_items = [
        BenefitPackagePlanItem(id="item-1", plan_id=plan.id, offering_id=towing_up.id, typed_value_override=None, sort_order=0),
        BenefitPackagePlanItem(id="item-2", plan_id=plan.id, offering_id=pa.id, typed_value_override=None, sort_order=1),
    ]
    values.extend(plan_items)
    if with_base_selection:
        base_selection = DraftBenefitSelection(
            id="selection-base", draft_id=draft.id, selection_key="catalog:towing-50",
            catalog_offering_id=towing_base.id, concept_id=towing_base.concept_id, item_kind="catalog",
            state="current", cost_status="included",
            typed_value_override={"type": "custom", "display_text": "Staff custom 999 km"} if staff_override else None,
            evidence_snapshot={}, sort_order=0,
        )
        values.append(base_selection)
    return values


def test_plan_crud_requires_an_addon_bundle_and_plans_freezes_into_publish_hash():
    values = plan_fixture_values(with_base_selection=False)
    db = FakeDb(values)

    with pytest.raises(AppError) as error:
        save_plan(db, user(), "catalog-1", "package-main", {"base_revision": 1, "name": "Nope"})
    assert error.value.status_code == 422

    payload = _revision_content_payload(db, db.get(BenefitCatalogRevision, "catalog-revision-1"))
    assert any(item["plan_key"] == "plan-a" for item in payload["plans"])
    assert any(item["offering_id"] == "offering-towing-200" for item in payload["plan_items"])

    # FakeDb cannot filter by package/plan key; remove the fixture plan so the
    # duplicate scan sees an empty table for this package.
    db.values.pop((BenefitPackagePlan, "plan-a"), None)
    plan = save_plan(db, user(), "catalog-1", "package-bundle", {"base_revision": 1, "name": "Driver Protection Plan B"})
    assert plan["package_id"] == "package-bundle"
    assert plan["plan_key"] == "driver-protection-plan-b"
    assert db.commits == 1

    with pytest.raises(AppError) as error:
        save_plan(db, user(), "catalog-1", "package-bundle", {"base_revision": 2, "name": "Driver Protection Plan B"})
    assert error.value.status_code == 409

    retire_plan(db, user(), "catalog-1", "package-bundle", plan["id"])
    assert db.get(BenefitPackagePlan, plan["id"]).status == "retired"


def test_plan_items_replace_atomically_and_validate_overrides():
    values = plan_fixture_values(with_base_selection=False)
    db = FakeDb(values)
    result = save_plan_items(
        db, user(), "catalog-1", "package-bundle", "plan-a",
        {"base_revision": 1, "items": [
            {
                "offering_id": "offering-towing-200",
                "typed_value_override": {"type": "distance", "unlimited": True, "unit": "km", "region": "Malaysia"},
                "sort_order": 0,
            },
        ]},
    )
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["offering_id"] == "offering-towing-200"
    assert item["typed_value_override"]["unlimited"] is True

    with pytest.raises(AppError) as error:
        save_plan_items(
            db, user(), "catalog-1", "package-bundle", "plan-a",
            {"base_revision": 2, "items": [{"offering_id": "offering-towing-200", "typed_value_override": {"type": "distance", "unlimited": True, "value": 3, "unit": "km"}}]},
        )
    assert error.value.status_code == 422

    with pytest.raises(AppError) as error:
        save_plan_items(
            db, user(), "catalog-1", "package-bundle", "plan-a",
            {"base_revision": 2, "items": [{"offering_id": "offering-towing-200"}, {"offering_id": "offering-towing-200"}]},
        )
    assert error.value.status_code == 422


def test_resolve_benefit_cards_emits_groups_for_plan_members():
    draft = _draft()
    plan = SimpleNamespace(id="plan-a", plan_key="plan-a", name="Driver Protection Plan A", sort_order=0)
    base = SimpleNamespace(
        id="offering-towing-50", offering_key="towing-50", concept_id="concept-towing", offering_kind="base",
        typed_value={"type": "distance", "value": 50, "unit": "km"}, sort_order=0, status="active",
        label_override=None, presentation_facet_ids=[], role=None,
    )
    towing = SimpleNamespace(
        id="offering-towing-200", offering_key="towing-200", concept_id="concept-towing", offering_kind="optional",
        typed_value={"type": "distance", "value": 200, "unit": "km"}, sort_order=0, status="active",
        label_override=None, presentation_facet_ids=[], role="addon_option",
    )
    towing_concept = SimpleNamespace(id="concept-towing", concept_key="towing", label="Towing", default_asset_id=None)
    selection = SimpleNamespace(
        id="selection-1", selection_key="plan:plan-a:towing-200", catalog_offering_id=towing.id,
        concept_id="concept-towing", item_kind="catalog",
        state="current", cost_status="paid", label_override=None, typed_value_override=None,
        evidence_snapshot={"package_id": "package-bundle", "plan_id": "plan-a", "source": "package_plan"},
        sort_order=0, package_plan_id="plan-a",
    )
    cards = resolve_benefit_cards(
        selections=[selection], offerings=[base, towing], concepts=[towing_concept],
        relations=[], facets=[], plans=[plan],
    )
    assert cards["groups"][0]["plan_id"] == "plan-a"
    assert cards["groups"][0]["plan_label"] == "Driver Protection Plan A"
    assert cards["groups"][0]["cards"][0]["group_id"] == "plan-a"


def test_select_package_plan_adds_members_supersedes_defaults_and_switches_cleanly():
    values = plan_fixture_values()
    db = FakeDb(values)
    apply_workspace_patch(db, user(), "draft-1", base_revision=3, operations=[
        {"op": "select_package_plan", "package_id": "package-bundle", "plan_id": "plan-a"},
    ])

    selections = [item for item in db.values.values() if isinstance(item, DraftBenefitSelection)]
    current = [item for item in selections if item.state == "current"]
    towing_current = next(item for item in current if item.concept_id == "concept-towing")
    base = db.get(DraftBenefitSelection, "selection-base")
    assert base.state == "superseded" and base.superseded_by_id == towing_current.id
    assert towing_current.package_plan_id == "plan-a"
    assert towing_current.catalog_offering_id == "offering-towing-200"
    assert any(item.concept_id == "concept-pa" and item.package_plan_id == "plan-a" for item in current)

    plan_b = BenefitPackagePlan(id="plan-b", package_id="package-bundle", plan_key="plan-b", name="Driver Protection Plan B", sort_order=1, status="active")
    db.values[(BenefitPackagePlan, "plan-b")] = plan_b
    # Simulate real scoping: plan-a items no longer belong to the applied plan.
    db.values.pop((BenefitPackagePlanItem, "item-1"), None)
    db.values.pop((BenefitPackagePlanItem, "item-2"), None)
    pa_up = CatalogOffering(
        id="offering-pa-up", catalog_revision_id="catalog-revision-1", offering_key="pa-up",
        concept_id="concept-pa", offering_kind="optional",
        typed_value={"type": "money", "value": 20000, "currency": "MYR", "semantic_role": "insured_limit"}, status="active",
    )
    db.values[(CatalogOffering, "offering-pa-up")] = pa_up
    db.values[(BenefitPackagePlanItem, "item-b")] = BenefitPackagePlanItem(
        id="item-b", plan_id=plan_b.id, offering_id=pa_up.id, typed_value_override=None, sort_order=0,
    )

    apply_workspace_patch(db, user(), "draft-1", base_revision=4, operations=[
        {"op": "select_package_plan", "package_id": "package-bundle", "plan_id": "plan-b"},
    ])
    selections = [item for item in db.values.values() if isinstance(item, DraftBenefitSelection)]
    current = [item for item in selections if item.state == "current"]
    pa_current = next(item for item in current if item.concept_id == "concept-pa")
    assert pa_current.package_plan_id == "plan-b"
    assert pa_current.catalog_offering_id == "offering-pa-up"
    towing_current = next(item for item in current if item.concept_id == "concept-towing")
    assert towing_current.catalog_offering_id == "offering-towing-50"
    assert towing_current.package_plan_id is None
    base = db.get(DraftBenefitSelection, "selection-base")
    assert base.state == "current" and base.superseded_by_id is None


def test_select_package_plan_keeps_staff_custom_value_and_remove_restores_defaults():
    values = plan_fixture_values(staff_override=True)
    db = FakeDb(values)
    apply_workspace_patch(db, user(), "draft-1", base_revision=3, operations=[
        {"op": "select_package_plan", "package_id": "package-bundle", "plan_id": "plan-a"},
    ])
    base = db.get(DraftBenefitSelection, "selection-base")
    assert base.state == "current"
    assert base.package_plan_id == "plan-a"
    assert base.typed_value_override["display_text"] == "Staff custom 999 km"

    apply_workspace_patch(db, user(), "draft-1", base_revision=4, operations=[
        {"op": "remove_package_plan", "plan_id": "plan-a"},
    ])
    selections = [item for item in db.values.values() if isinstance(item, DraftBenefitSelection)]
    assert base.state == "current" and base.package_plan_id is None
    assert not any(item.package_plan_id == "plan-a" and item.state == "current" for item in selections)


def test_extras_payload_and_adjusted_total():
    draft = _draft()
    concepts = [SimpleNamespace(id="concept-pa", label="Personal Accident")]
    priced = DraftBenefitSelection(
        id="selection-extra", draft_id=draft.id, selection_key="custom-key-replacement", item_kind="custom",
        concept_id="concept-pa", state="current", cost_status="paid", label_override="Key Replacement",
        typed_value_override=None, evidence_snapshot={}, sort_order=0,
        price={"amount": "43.00", "currency": "MYR"},
    )
    unpriced = DraftBenefitSelection(
        id="selection-plain", draft_id=draft.id, selection_key="custom-plain", item_kind="custom",
        concept_id="concept-pa", state="current", cost_status="paid", label_override=None,
        typed_value_override=None, evidence_snapshot={}, sort_order=1, price=None,
    )
    extras = build_extras([priced, unpriced], concepts)
    assert [item["label"] for item in extras] == ["Key Replacement"]
    assert format_money_amount(extras[0]["price"]) == "RM 43"

    assert adjusted_total_text(draft.fields, extras) == "2,792.37"
    assert adjusted_total_text(draft.fields, []) == "2,749.37"


def test_format_money_amount_tolerates_bad_shapes():
    assert format_money_amount({"amount": "288.05", "currency": "MYR"}) == "RM 288.05"
    assert format_money_amount({"currency": "MYR"}) == ""
    assert format_money_amount(None) == ""


def test_ai_detected_pack_auto_applies_plan_members():
    values = plan_fixture_values()
    draft = next(item for item in values if isinstance(item, QuotationDraft))
    extraction = ExtractionRecord(
        id="extraction-1",
        uploaded_file_id=draft.uploaded_file_id,
        method_summary=["Gemini 3.6 Flash AI Extraction"],
        raw_text="PRIVATE",
        ocr_text="",
        page_text=[],
        words=[], blocks=[], tables=[], images=[], regions=[],
        candidates={"detected_packs": [{"package_name": "Driver Protection Pack", "plan_name": "Plan A", "raw_text": "DPA pack A -> 288.05 RM"}]},
        benefit_lines=[], company_resolution={}, warnings=[],
    )
    values.append(extraction)
    db = FakeDb(values)

    result = auto_apply_extracted_benefits(db, draft)
    assert result["applied"] >= 2

    selections = [item for item in db.values.values() if isinstance(item, DraftBenefitSelection)]
    current = [item for item in selections if item.state == "current"]
    towing = next(item for item in current if item.concept_id == "concept-towing")
    assert towing.package_plan_id == "plan-a"
    assert towing.catalog_offering_id == "offering-towing-200"
    assert towing.evidence_snapshot.get("is_detected") is True
    base = db.get(DraftBenefitSelection, "selection-base")
    assert base.state == "superseded" and base.superseded_by_id == towing.id
    assert any(item.concept_id == "concept-pa" and item.package_plan_id == "plan-a" for item in current)


def test_rag_prompt_override_replaces_instructions_but_keeps_grounding():
    default = build_rag_system_prompt(db_companies=[{"name": "Nova Mutual"}], db_benefit_concepts=[{"key": "towing", "name": "Towing"}])
    assert "CRITICAL GROUNDING RULES" in default
    assert "Nova Mutual" in default

    custom = build_rag_system_prompt(
        db_companies=[{"name": "Nova Mutual"}],
        db_benefit_concepts=[{"key": "towing", "name": "Towing"}],
        prompt_override="You are a custom extractor. Always prefer the customer name.",
    )
    assert "CRITICAL GROUNDING RULES" not in custom
    assert "You are a custom extractor" in custom
    assert "LIVE DATABASE GROUNDING CONTEXT" in custom
    assert "Nova Mutual" in custom
    assert "Towing" in custom


def test_workspace_package_tiers_lists_comprehensive_tiers_in_single_revision():
    values = plan_fixture_values()
    draft = next(item for item in values if isinstance(item, QuotationDraft))
    draft.company_id = "company-1"
    draft.catalog_revision_id = "catalog-revision-1"
    draft.package_id = None

    # Add second and third comprehensive packages into the SAME catalog revision
    pkg_plus = BenefitPackage(
        id="package-plus", catalog_revision_id="catalog-revision-1", package_key="plus", name="Plus",
        package_kind="comprehensive", sort_order=1, revision=1, status="active",
    )
    pkg_premier = BenefitPackage(
        id="package-premier", catalog_revision_id="catalog-revision-1", package_key="premier", name="Premier",
        package_kind="comprehensive", sort_order=2, revision=1, status="active",
    )
    # Add an offering tied specifically to package-plus
    offering_plus = CatalogOffering(
        id="offering-plus-spec", catalog_revision_id="catalog-revision-1", offering_key="plus-spec",
        concept_id="concept-spec", offering_kind="base", role="included",
        applies_to_type="package", applies_to_id="package-plus", status="active",
    )
    values.extend([pkg_plus, pkg_premier, offering_plus])
    db = FakeDb(values)

    tiers = _workspace_package_tiers(db, draft)
    assert len(tiers) == 3
    by_key = {item["package_key"]: item for item in tiers}
    assert [item["package_key"] for item in tiers] == ["main", "plus", "premier"]
    # Main is current by default because catalog.package_id points to package-main
    assert by_key["main"]["is_current"] is True
    assert by_key["plus"]["is_current"] is False
    assert by_key["premier"]["is_current"] is False
    assert by_key["main"]["catalog_revision_id"] == "catalog-revision-1"
    assert by_key["plus"]["defaults_count"] >= by_key["main"]["defaults_count"]

    # When draft.package_id is explicitly set to plus:
    draft.package_id = "package-plus"
    tiers_updated = _workspace_package_tiers(db, draft)
    by_key_updated = {item["package_key"]: item for item in tiers_updated}
    assert by_key_updated["main"]["is_current"] is False
    assert by_key_updated["plus"]["is_current"] is True
    assert by_key_updated["premier"]["is_current"] is False


def test_workspace_package_tiers_legacy_multicatalog_fallback():
    values = plan_fixture_values()
    draft = next(item for item in values if isinstance(item, QuotationDraft))
    draft.company_id = "company-1"
    draft.catalog_revision_id = None
    draft.package_id = None

    catalog2 = BenefitCatalog(
        id="catalog-2", company_id="company-1", product_id=None, tier_id=None, package_id="package-main2",
        name="Nova Catalog 2", revision=1, status="published",
    )
    revision2 = BenefitCatalogRevision(
        id="catalog-revision-2", catalog_id=catalog2.id, revision_number=1, state="published",
        source_document_ids=[], content_hash="c" * 64,
    )
    package2 = BenefitPackage(
        id="package-main2", catalog_revision_id=revision2.id, package_key="main2", name="Main 2",
        package_kind="comprehensive", sort_order=2, revision=1, status="active",
    )
    values.extend([catalog2, revision2, package2])
    db = FakeDb(values)

    tiers = _workspace_package_tiers(db, draft)
    assert len(tiers) == 2
    by_key = {item["package_key"]: item for item in tiers}
    assert by_key["main"]["catalog_id"] == "catalog-1"
    assert by_key["main2"]["catalog_id"] == "catalog-2"


def test_apply_select_package_tier_operation():
    values = plan_fixture_values()
    draft = next(item for item in values if isinstance(item, QuotationDraft))
    draft.company_id = "company-1"
    draft.catalog_revision_id = "catalog-revision-1"
    draft.package_id = "package-main"

    pkg_plus = BenefitPackage(
        id="package-plus", catalog_revision_id="catalog-revision-1", package_key="plus", name="Plus",
        package_kind="comprehensive", sort_order=1, revision=1, status="active",
    )
    offering_plus = CatalogOffering(
        id="offering-plus-spec", catalog_revision_id="catalog-revision-1", offering_key="plus-spec",
        concept_id="concept-spec", offering_kind="base", role="included",
        applies_to_type="package", applies_to_id="package-plus", status="active",
    )
    # Foreign package in different revision
    pkg_foreign = BenefitPackage(
        id="package-foreign", catalog_revision_id="other-revision", package_key="foreign", name="Foreign",
        package_kind="comprehensive", sort_order=1, revision=1, status="active",
    )
    values.extend([pkg_plus, offering_plus, pkg_foreign])
    db = FakeDb(values)

    # 1. Switch to package-plus
    res = apply_workspace_patch(
        db, user(), draft.id,
        base_revision=draft.revision,
        operations=[{"op": "select_package_tier", "package_id": "package-plus"}],
    )
    assert res["revision"] == 4
    assert draft.package_id == "package-plus"
    selections = [s for s in db.values.values() if isinstance(s, DraftBenefitSelection) and s.draft_id == draft.id]
    assert any(s.catalog_offering_id == "offering-plus-spec" for s in selections)

    # 2. Foreign package rejected
    with pytest.raises(AppError, match="does not belong"):
        apply_workspace_patch(
            db, user(), draft.id,
            base_revision=draft.revision,
            operations=[{"op": "select_package_tier", "package_id": "package-foreign"}],
        )

    # 3. Same package tier select is a clean no-op
    res_noop = apply_workspace_patch(
        db, user(), draft.id,
        base_revision=draft.revision,
        operations=[{"op": "select_package_tier", "package_id": "package-plus"}],
    )
    assert res_noop["revision"] == 5


def test_seed_base_benefits_honors_draft_package_id():
    values = plan_fixture_values(with_base_selection=False)
    draft = next(item for item in values if isinstance(item, QuotationDraft))
    draft.company_id = "company-1"
    draft.catalog_revision_id = "catalog-revision-1"
    revision = next(item for item in values if isinstance(item, BenefitCatalogRevision))

    pkg_plus = BenefitPackage(
        id="package-plus", catalog_revision_id=revision.id, package_key="plus", name="Plus",
        package_kind="comprehensive", sort_order=1, revision=1, status="active",
    )
    offering_main_only = CatalogOffering(
        id="offering-main-only", catalog_revision_id=revision.id, offering_key="main-only",
        concept_id="concept-main-only", offering_kind="base", role="included",
        applies_to_type="package", applies_to_id="package-main", status="active",
    )
    offering_plus_only = CatalogOffering(
        id="offering-plus-only", catalog_revision_id=revision.id, offering_key="plus-only",
        concept_id="concept-plus-only", offering_kind="base", role="included",
        applies_to_type="package", applies_to_id="package-plus", status="active",
    )
    values.extend([pkg_plus, offering_main_only, offering_plus_only])
    db = FakeDb(values)

    draft.package_id = "package-plus"
    created = seed_base_benefits(db, draft, revision)
    assert created >= 1
    added_offering_ids = {item.catalog_offering_id for item in db.added if isinstance(item, DraftBenefitSelection)}
    assert "offering-plus-only" in added_offering_ids
    assert "offering-main-only" not in added_offering_ids

