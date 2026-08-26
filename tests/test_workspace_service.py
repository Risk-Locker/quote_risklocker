"""Canonical session workspace snapshot, blockers, and optimistic mutations."""

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
    AuditEvent,
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitRelation,
    CatalogOffering,
    DraftBenefitSelection,
    DraftSourceLineDecision,
    ExtractionBenefitLine,
    ExtractionRecord,
    GeneratedPdfVersion,
    InsuranceCompany,
    InsuranceProduct,
    InsuranceProductTier,
    QuotationDraft,
    Session,
    TemplateRevision,
    UploadedFile,
)
from app.services.workspace_service import (
    apply_workspace_patch,
    build_workspace_snapshot,
    generation_blockers,
    template_selection_impact,
)


NOW = datetime.now(timezone.utc)


def objects():
    uploaded = UploadedFile(
        id="file-1",
        batch_id="batch-1",
        owner_id="owner-1",
        original_filename="quote.pdf",
        content_type="application/pdf",
        storage_path="source/quote.pdf",
        storage_status="available",
        security_scan={"result": "clean"},
        size_bytes=100,
        status=RecordStatus.CHECK_NEEDED.value,
    )
    draft = QuotationDraft(
        id="draft-1",
        uploaded_file_id=uploaded.id,
        owner_id="owner-1",
        revision=3,
        fields={
            "customer_name": {"value": "Test Customer", "status": "check_needed", "message": "Please check"},
            "vehicle_no": {"value": "ABC123", "status": "ready", "message": ""},
            "insurance_company": {"value": "Nova Mutual", "status": "ready", "message": ""},
            "premium": {"value": None, "status": "check_needed", "message": "Please check"},
            "roadtax": {"value": None, "status": "check_needed", "message": "Please check"},
            "service_fee": {"value": None, "status": "check_needed", "message": "Please check"},
            "total_amount": {"value": None, "status": "check_needed", "message": "Please check"},
            "issue_date": {"value": "2026-01-25", "status": "ready", "message": ""},
            "ncd_percent": {"value": None, "status": "check_needed", "message": "Please check"},
        },
        scalar_decisions={"vehicle_no": {"decision": "confirm"}},
        warnings=[],
        status=RecordStatus.CHECK_NEEDED.value,
        template_revision_id="template-revision-1",
    )
    session = Session(
        id="session-1",
        owner_id="owner-1",
        uploaded_file_id=uploaded.id,
        draft_id=draft.id,
        status="active",
    )
    extraction = ExtractionRecord(
        id="extraction-1",
        uploaded_file_id=uploaded.id,
        method_summary=[], raw_text="PRIVATE", ocr_text="", page_text=[{"page": 1, "text": "PRIVATE"}],
        words=[], blocks=[], tables=[], images=[], regions=[], candidates={}, benefit_lines=[], company_resolution={}, warnings=[],
    )
    line = ExtractionBenefitLine(
        id="line-1", extraction_record_id=extraction.id, line_id="p1-l1", raw_label="Towing", normalized_label="towing",
        page_number=1, source_scope="quotation_selected", line_kind="benefit_candidate", inclusion_state="selected",
        evidence={"page": 1}, candidate_mappings=[], extracted_value={"type": "distance", "value": "200", "unit": "km", "unlimited": False},
    )
    decision = DraftSourceLineDecision(id="decision-1", draft_id=draft.id, source_line_id=line.id, disposition="unresolved")
    selection = DraftBenefitSelection(
        id="selection-1", draft_id=draft.id, selection_key="custom-roadside", item_kind="custom", state="current",
        cost_status="unknown", label_override="Roadside help", typed_value_override={"type": "custom", "display_text": "As quoted"},
        evidence_snapshot={}, sort_order=0,
    )
    template_revision = TemplateRevision(
        id="template-revision-1", template_id="template-1", revision_number=2, state="published",
        page_profile_id="profile-1", config={"canvas": {"width": 794, "height": 1123, "elements": []}}, config_hash="a" * 64,
    )
    return uploaded, draft, session, extraction, line, decision, selection, template_revision


class Scalars:
    def __init__(self, rows): self.rows = rows
    def all(self): return list(self.rows)


class FakeDb:
    def __init__(self, values):
        self.values = {(type(item), item.id): item for item in values}
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.refreshed = []

    def get(self, model, object_id): return self.values.get((model, object_id))

    def scalars(self, statement):
        entity = statement.column_descriptions[0].get("entity") if statement.column_descriptions else None
        rows = [item for (model, _id), item in self.values.items() if model is entity]
        return Scalars(rows)

    def scalar(self, statement):
        rows = self.scalars(statement).all()
        return rows[0] if rows else None

    def add(self, item):
        self.added.append(item)
        if getattr(item, "id", None): self.values[(type(item), item.id)] = item

    def delete(self, item): self.values.pop((type(item), item.id), None)
    def flush(self): return None
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1
    def refresh(self, item): self.refreshed.append(item)


def user(role="staff"):
    return SimpleNamespace(id="staff-1", role=role)


def test_workspace_snapshot_is_small_staff_safe_and_has_server_capabilities():
    db = FakeDb(objects())
    snapshot = build_workspace_snapshot(db, user(), "session-1")

    assert snapshot["revision"] == 3
    assert snapshot["draft_id"] == "draft-1"
    assert snapshot["template"] == {"id": "template-1", "revision_id": "template-revision-1", "revision_number": 2, "config_hash": "a" * 64}
    assert snapshot["capabilities"]["can_edit_fields"] is True
    assert snapshot["capabilities"]["can_manage_users"] is False
    assert snapshot["generation_blockers"]
    assert snapshot["benefit_cards"]["current_benefits"][0]["label"] == "Roadside help"
    assert "raw_text" not in snapshot
    assert "page_text" not in snapshot
    assert "method_summary" not in snapshot
    assert "score" not in str(snapshot)


def test_generation_blockers_cover_unconfirmed_scalar_unresolved_line_unknown_cost_and_missing_template():
    _uploaded, draft, _session, _extraction, _line, decision, selection, _template = objects()
    draft.template_revision_id = None
    blockers = generation_blockers(draft, [decision], [selection], template_revision=None)
    codes = {item["code"] for item in blockers}
    assert codes == {"scalar_check_needed", "unresolved_source_line", "unknown_benefit_cost", "missing_template", "missing_catalog"}


def test_patch_only_changes_explicit_scalar_decision_and_never_confirms_untouched_field():
    db = FakeDb(objects())
    result = apply_workspace_patch(
        db,
        user(),
        "draft-1",
        base_revision=3,
        operations=[{"op": "scalar_decision", "field": "customer_name", "decision": "edit", "value": "Correct Name"}],
    )
    draft = db.get(QuotationDraft, "draft-1")

    assert result["revision"] == 4
    assert draft.fields["customer_name"]["value"] == "Correct Name"
    assert draft.fields["customer_name"]["status"] == "ready"
    assert draft.scalar_decisions["customer_name"]["decision"] == "edit"
    assert draft.scalar_decisions["vehicle_no"]["decision"] == "confirm"
    assert db.commits == 1
    assert any(isinstance(item, AuditEvent) and item.action == "workspace.patch" for item in db.added)


def test_keep_check_needed_remains_blocking_and_clear_is_explicit():
    db = FakeDb(objects())
    apply_workspace_patch(
        db, user(), "draft-1", base_revision=3,
        operations=[{"op": "scalar_decision", "field": "customer_name", "decision": "keep_check_needed"}],
    )
    draft = db.get(QuotationDraft, "draft-1")
    assert draft.fields["customer_name"]["status"] == "check_needed"
    assert draft.fields["customer_name"]["value"] == "Test Customer"

    apply_workspace_patch(
        db, user(), "draft-1", base_revision=4,
        operations=[{"op": "scalar_decision", "field": "customer_name", "decision": "clear"}],
    )
    assert draft.fields["customer_name"]["value"] is None
    assert draft.fields["customer_name"]["status"] == "ready"


def test_stale_revision_returns_409_and_changes_nothing():
    db = FakeDb(objects())
    draft = db.get(QuotationDraft, "draft-1")
    original = dict(draft.fields["customer_name"])

    with pytest.raises(AppError) as error:
        apply_workspace_patch(
            db, user(), "draft-1", base_revision=2,
            operations=[{"op": "scalar_decision", "field": "customer_name", "decision": "clear"}],
        )

    assert error.value.status_code == 409
    assert draft.fields["customer_name"] == original
    assert db.commits == 0


def test_source_disposition_and_custom_selection_are_atomic_and_validated():
    db = FakeDb(objects())
    result = apply_workspace_patch(
        db, user(), "draft-1", base_revision=3,
        operations=[
            {
                "op": "create_custom_benefit",
                "selection_key": "custom-towing",
                "label": "Towing",
                "typed_value": {"type": "distance", "value": "1700", "unit": "km", "unlimited": False},
                "cost_status": "foc",
                "state": "current",
                "source_line_id": "line-1",
            },
            {"op": "source_disposition", "source_line_id": "line-1", "disposition": "custom", "selection_key": "custom-towing"},
        ],
    )

    created = next(item for item in db.added if isinstance(item, DraftBenefitSelection))
    decision = db.get(DraftSourceLineDecision, "decision-1")
    assert created.typed_value_override["value"] == "1700"
    assert decision.disposition == "custom"
    assert decision.selection_id == created.id
    assert result["revision"] == 4


def test_explicit_upgrade_replaces_current_value_preserves_exact_override_and_can_undo():
    values = list(objects())
    draft = next(item for item in values if isinstance(item, QuotationDraft))
    draft.catalog_revision_id = "catalog-revision-1"
    base = CatalogOffering(
        id="offering-50", catalog_revision_id=draft.catalog_revision_id, offering_key="towing-50",
        concept_id="concept-towing", offering_kind="base", typed_value={"type": "distance", "value": 50, "unit": "km"}, status="active",
    )
    upgrade = CatalogOffering(
        id="offering-unlimited", catalog_revision_id=draft.catalog_revision_id, offering_key="towing-unlimited",
        concept_id="concept-towing", offering_kind="upgrade", typed_value={"type": "distance", "unit": "km", "unlimited": True}, status="active",
    )
    relation = BenefitRelation(
        id="relation-1", catalog_revision_id=draft.catalog_revision_id, from_offering_id=base.id,
        to_offering_id=upgrade.id, relation_kind="replaces", sort_order=1,
    )
    current = DraftBenefitSelection(
        id="selection-base", draft_id=draft.id, selection_key="catalog:towing-50", catalog_offering_id=base.id,
        concept_id=base.concept_id, item_kind="catalog", state="current", cost_status="included", evidence_snapshot={}, sort_order=0,
    )
    values.extend([base, upgrade, relation, current])
    db = FakeDb(values)

    apply_workspace_patch(db, user(), draft.id, base_revision=3, operations=[{
        "op": "select_catalog_offering", "offering_id": upgrade.id, "cost_status": "foc",
        "typed_value": {"type": "distance", "value": 999, "unit": "km"},
    }])

    selected = next(item for item in db.added if isinstance(item, DraftBenefitSelection))
    assert current.state == "superseded" and current.superseded_by_id == selected.id
    assert selected.state == "current" and selected.cost_status == "foc"
    assert selected.typed_value_override["value"] == "999"
    assert len([item for item in db.values.values() if isinstance(item, DraftBenefitSelection) and item.state == "current" and item.concept_id == base.concept_id]) == 1

    apply_workspace_patch(db, user(), draft.id, base_revision=4, operations=[{"op": "revert_benefit", "selection_id": selected.id}])
    assert selected.state == "removed"
    assert current.state == "current" and current.superseded_by_id is None


def test_unrelated_upgrade_is_rejected_and_remove_or_cost_change_is_quotation_only():
    values = list(objects())
    draft = next(item for item in values if isinstance(item, QuotationDraft))
    draft.catalog_revision_id = "catalog-revision-1"
    base = CatalogOffering(id="base", catalog_revision_id=draft.catalog_revision_id, offering_key="base", concept_id="concept", offering_kind="base", status="active")
    unrelated = CatalogOffering(id="upgrade", catalog_revision_id=draft.catalog_revision_id, offering_key="upgrade", concept_id="concept", offering_kind="upgrade", status="active")
    current = DraftBenefitSelection(id="current", draft_id=draft.id, selection_key="catalog:base", catalog_offering_id=base.id, concept_id="concept", item_kind="catalog", state="current", cost_status="included", evidence_snapshot={})
    values.extend([base, unrelated, current])
    db = FakeDb(values)

    with pytest.raises(AppError, match="explicit upgrade"):
        apply_workspace_patch(db, user(), draft.id, base_revision=3, operations=[{"op": "select_catalog_offering", "offering_id": unrelated.id, "cost_status": "paid"}])

    apply_workspace_patch(db, user(), draft.id, base_revision=3, operations=[{"op": "benefit_update", "selection_id": current.id, "state": "removed", "cost_status": "foc"}])
    assert current.state == "removed" and current.cost_status == "foc"


def test_layout_override_requires_exact_template_binding():
    db = FakeDb(objects())
    apply_workspace_patch(
        db, user(), "draft-1", base_revision=3,
        operations=[{
            "op": "layout_override",
            "template_id": "template-1",
            "template_revision_id": "template-revision-1",
            "base_hash": "a" * 64,
            "layout": {"canvas": {"width": 794, "height": 1123, "elements": []}},
        }],
    )
    draft = db.get(QuotationDraft, "draft-1")
    assert draft.layout_override_template_id == "template-1"
    assert draft.layout_override_template_revision_id == "template-revision-1"

    with pytest.raises(AppError, match="template"):
        apply_workspace_patch(
            db, user(), "draft-1", base_revision=4,
            operations=[{
                "op": "layout_override", "template_id": "foreign", "template_revision_id": "template-revision-1",
                "base_hash": "a" * 64, "layout": {},
            }],
        )


def test_template_selection_requires_impact_confirmation_and_resets_foreign_layout():
    values = list(objects())
    draft = next(item for item in values if isinstance(item, QuotationDraft))
    draft.layout_override = {"canvas": {"elements": []}}
    draft.layout_override_template_id = "template-1"
    draft.layout_override_template_revision_id = "template-revision-1"
    draft.layout_override_base_hash = "a" * 64
    target = TemplateRevision(
        id="template-revision-2",
        template_id="template-2",
        revision_number=1,
        state="published",
        page_profile_id="profile-1",
        config={"template_name": "Long Master", "canvas": {"width": 794, "height": 1400, "elements": []}},
        config_hash="b" * 64,
    )
    values.append(target)
    db = FakeDb(values)

    impact = template_selection_impact(
        db,
        user(),
        "session-1",
        template_revision_id=target.id,
        base_revision=3,
    )
    assert impact["target"]["template_revision_id"] == target.id
    assert impact["will_reset_layout_override"] is True
    assert impact["requires_confirmation"] is True

    with pytest.raises(AppError, match="Confirm") as error:
        apply_workspace_patch(
            db,
            user(),
            "draft-1",
            base_revision=3,
            operations=[{
                "op": "template_selection",
                "template_revision_id": target.id,
                "confirmed": False,
            }],
        )
    assert error.value.status_code == 422
    assert draft.template_revision_id == "template-revision-1"

    result = apply_workspace_patch(
        db,
        user(),
        "draft-1",
        base_revision=3,
        operations=[{
            "op": "template_selection",
            "template_revision_id": target.id,
            "confirmed": True,
        }],
    )
    assert result["revision"] == 4
    assert draft.template_revision_id == target.id
    assert draft.layout_override is None
    assert draft.layout_override_template_id is None
    assert draft.layout_override_template_revision_id is None
    assert draft.layout_override_base_hash is None


def test_template_selection_rejects_unpublished_revision():
    values = list(objects())
    target = TemplateRevision(
        id="draft-template-revision",
        template_id="template-2",
        revision_number=1,
        state="draft",
        page_profile_id="profile-1",
        config={"canvas": {"width": 794, "height": 1123, "elements": []}},
        config_hash="b" * 64,
    )
    values.append(target)

    with pytest.raises(AppError, match="published") as error:
        template_selection_impact(
            FakeDb(values),
            user(),
            "session-1",
            template_revision_id=target.id,
            base_revision=3,
        )
    assert error.value.status_code == 422


def test_snapshot_marks_old_versions_stale_by_exact_draft_revision():
    values = list(objects())
    values.append(GeneratedPdfVersion(
        id="version-1", draft_id="draft-1", uploaded_file_id="file-1", version_number=1, draft_revision=2,
        filename="quote.pdf", storage_path="generated/quote.pdf", draft_snapshot={}, template_snapshot={},
        render_context_snapshot={}, renderer_version="v7", generated_by="staff-1", generated_at=NOW,
    ))
    snapshot = build_workspace_snapshot(FakeDb(values), user(), "session-1")
    assert snapshot["versions"] == [{"id": "version-1", "version_number": 1, "draft_revision": 2, "stale": True, "generated_at": NOW.isoformat()}]


def _catalog_values():
    company = InsuranceCompany(id="company-1", name="Nova Mutual", status="active")
    product = InsuranceProduct(id="product-1", company_id="company-1", name="Motor Plus", status="active")
    tier = InsuranceProductTier(id="tier-1", product_id="product-1", name="Premier", status="active")
    catalog = BenefitCatalog(id="catalog-1", company_id="company-1", product_id="product-1", tier_id="tier-1", name="Premier", status="published")
    revision = BenefitCatalogRevision(id="revision-1", catalog_id=catalog.id, revision_number=1, state="published", content_hash="c" * 64)
    base = CatalogOffering(id="offering-1", catalog_revision_id=revision.id, offering_key="towing-50", concept_id="concept-towing", offering_kind="base", typed_value={"type": "distance", "value": 50, "unit": "km"}, status="active")
    return [company, product, tier, catalog, revision, base]


def test_pin_catalog_operation_pins_chain_seeds_bases_and_updates_company_field():
    values = list(objects())
    draft = next(item for item in values if isinstance(item, QuotationDraft))
    values.extend(_catalog_values())
    db = FakeDb(values)

    result = apply_workspace_patch(db, user(), draft.id, base_revision=3, operations=[{
        "op": "pin_catalog", "company_id": "company-1", "product_id": "product-1", "tier_id": "tier-1",
    }])

    assert result["revision"] == 4
    assert draft.company_id == "company-1"
    assert draft.product_id == "product-1" and draft.tier_id == "tier-1" and draft.catalog_revision_id == "revision-1"
    seeded = [item for item in db.added if isinstance(item, DraftBenefitSelection)]
    assert len(seeded) == 1 and seeded[0].state == "current" and seeded[0].cost_status == "included"
    assert draft.fields["insurance_company"]["value"] == "Nova Mutual"
    assert draft.fields["insurance_company"]["status"] == "ready"
    assert "missing_catalog" not in {item["code"] for item in result["generation_blockers"]}


def test_pin_catalog_rejects_tier_from_another_product():
    values = list(objects())
    draft = next(item for item in values if isinstance(item, QuotationDraft))
    company = InsuranceCompany(id="company-1", name="Nova Mutual", status="active")
    product = InsuranceProduct(id="product-1", company_id="company-1", name="Motor Plus", status="active")
    other_product = InsuranceProduct(id="product-2", company_id="company-1", name="Home Plus", status="active")
    foreign_tier = InsuranceProductTier(id="tier-1", product_id="product-2", name="Premier", status="active")
    values.extend([company, product, other_product, foreign_tier])
    db = FakeDb(values)

    with pytest.raises(AppError) as error:
        apply_workspace_patch(db, user(), draft.id, base_revision=3, operations=[{
            "op": "pin_catalog", "company_id": "company-1", "product_id": "product-1", "tier_id": "tier-1",
        }])

    assert error.value.status_code == 422
    assert db.commits == 0
    assert draft.catalog_revision_id is None


def test_editing_insurance_company_repins_catalog_and_seeds_bases():
    values = list(objects())
    draft = next(item for item in values if isinstance(item, QuotationDraft))
    values.extend(_catalog_values())
    db = FakeDb(values)

    apply_workspace_patch(db, user(), draft.id, base_revision=3, operations=[{
        "op": "scalar_decision", "field": "insurance_company", "decision": "edit", "value": "Nova Mutual",
    }])

    assert draft.company_id == "company-1"
    assert draft.product_id == "product-1" and draft.tier_id == "tier-1" and draft.catalog_revision_id == "revision-1"
    assert any(isinstance(item, DraftBenefitSelection) and item.catalog_offering_id == "offering-1" for item in db.added)


def test_editing_insurance_company_to_an_unknown_name_clears_the_pin():
    values = list(objects())
    draft = next(item for item in values if isinstance(item, QuotationDraft))
    draft.company_id = "company-1"
    draft.catalog_revision_id = "revision-1"
    values.extend(_catalog_values())
    db = FakeDb(values)

    apply_workspace_patch(db, user(), draft.id, base_revision=3, operations=[{
        "op": "scalar_decision", "field": "insurance_company", "decision": "edit", "value": "Unknown Insurer",
    }])

    assert draft.company_id is None and draft.product_id is None and draft.tier_id is None
    assert draft.catalog_revision_id is None


def test_money_edits_normalize_to_rm_and_recompute_total():
    db = FakeDb(objects())
    apply_workspace_patch(db, user(), "draft-1", base_revision=3, operations=[
        {"op": "scalar_decision", "field": "premium", "decision": "edit", "value": "RM 1,234.50"},
        {"op": "scalar_decision", "field": "roadtax", "decision": "edit", "value": "90"},
        {"op": "scalar_decision", "field": "service_fee", "decision": "edit", "value": "20"},
    ])
    draft = db.get(QuotationDraft, "draft-1")
    assert draft.fields["premium"]["value"] == "1234.50"
    assert draft.fields["roadtax"]["value"] == "90.00"
    assert draft.fields["total_amount"]["value"] == "1344.50"
    assert draft.fields["total_amount"]["status"] == "ready"
    assert draft.scalar_decisions["total_amount"]["decision"] == "edit"


def test_invalid_money_and_date_edits_are_rejected_without_committing():
    db = FakeDb(objects())
    with pytest.raises(AppError, match="RM amount"):
        apply_workspace_patch(db, user(), "draft-1", base_revision=3, operations=[{"op": "scalar_decision", "field": "premium", "decision": "edit", "value": "abc"}])
    with pytest.raises(AppError, match="valid date"):
        apply_workspace_patch(db, user(), "draft-1", base_revision=3, operations=[{"op": "scalar_decision", "field": "issue_date", "decision": "edit", "value": "not-a-date"}])
    assert db.commits == 0


def test_date_edits_store_date_only_and_ncd_stores_percentage_number():
    db = FakeDb(objects())
    apply_workspace_patch(db, user(), "draft-1", base_revision=3, operations=[
        {"op": "scalar_decision", "field": "issue_date", "decision": "edit", "value": "25/01/2026"},
        {"op": "scalar_decision", "field": "ncd_percent", "decision": "edit", "value": "25%"},
    ])
    draft = db.get(QuotationDraft, "draft-1")
    assert draft.fields["issue_date"]["value"] == "2026-01-25"
    assert draft.fields["ncd_percent"]["value"] == "25"


def test_pending_catalog_id_resolves_via_selection_key_instead_of_crashing():
    """P0 regression: pending:catalog:* must resolve by selection_key, not crash on UUID cast."""
    values = list(objects())
    draft = next(item for item in values if isinstance(item, QuotationDraft))
    draft.catalog_revision_id = "catalog-revision-1"
    selection = DraftBenefitSelection(
        id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        draft_id=draft.id,
        selection_key="catalog:4d122011-plus-bundle-flood-relief-allowance-1",
        item_kind="catalog",
        state="current",
        cost_status="included",
        evidence_snapshot={},
        sort_order=0,
    )
    values.append(selection)
    db = FakeDb(values)

    # Simulate what the frontend sends: pending:catalog:<offering_key>
    apply_workspace_patch(db, user(), draft.id, base_revision=3, operations=[
        {"op": "benefit_update", "selection_id": "pending:catalog:4d122011-plus-bundle-flood-relief-allowance-1", "state": "removed"},
    ])
    assert selection.state == "removed"


def test_completely_invalid_selection_id_returns_404():
    """Non-UUID, non-pending junk selection_id must produce a clean 404, not a 500."""
    db = FakeDb(objects())
    with pytest.raises(AppError, match="not found") as exc_info:
        apply_workspace_patch(db, user(), "draft-1", base_revision=3, operations=[
            {"op": "benefit_update", "selection_id": "definitely-not-a-uuid-or-key", "state": "removed"},
        ])
    assert exc_info.value.status_code == 404


def test_revert_benefit_with_pending_key_resolves_by_selection_key():
    """revert_benefit with a non-UUID key must also resolve via selection_key."""
    values = list(objects())
    draft = next(item for item in values if isinstance(item, QuotationDraft))
    selection = DraftBenefitSelection(
        id="11111111-2222-3333-4444-555555555555",
        draft_id=draft.id,
        selection_key="catalog:some-offering-key",
        item_kind="catalog",
        state="current",
        cost_status="paid",
        evidence_snapshot={},
        sort_order=0,
    )
    values.append(selection)
    db = FakeDb(values)

    apply_workspace_patch(db, user(), draft.id, base_revision=3, operations=[
        {"op": "revert_benefit", "selection_id": "pending:catalog:some-offering-key"},
    ])
    assert selection.state == "removed"

