"""Additive v7 data-domain and typed-value contracts."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.domain.benefits import BenefitValue, CostStatus, ReviewedBenefitState, SourceLineDisposition
from app.models.tables import Base
from app.db.migrations import discover_migrations
from app.services.compatibility_service import adapt_legacy_special, adapt_legacy_template


V7_TABLES = {
    "legal_entities",
    "company_aliases",
    "insurance_products",
    "insurance_product_tiers",
    "source_documents",
    "benefit_concepts",
    "benefit_facets",
    "benefit_catalogs",
    "benefit_catalog_revisions",
    "catalog_offerings",
    "benefit_relations",
    "benefit_packages",
    "benefit_package_plans",
    "benefit_package_plan_items",
    "catalog_imports",
    "business_assets",
    "extraction_benefit_lines",
    "draft_source_line_decisions",
    "draft_benefit_selections",
    "template_page_profiles",
    "template_revisions",
    "jobs",
    "render_snapshots",
    "record_saved_views",
}

LEGACY_TABLES = {
    "insurance_companies",
    "output_template_configs",
    "our_specials",
    "our_special_variants",
    "quotation_drafts",
    "generated_pdf_versions",
}


def test_v7_schema_is_additive_and_preserves_legacy_tables():
    names = set(Base.metadata.tables)

    assert V7_TABLES <= names
    assert LEGACY_TABLES <= names


def test_v7_schema_migrations_are_additive_and_cover_every_new_table():
    migrations = discover_migrations(ROOT / "migrations")
    v7_sql = "\n".join(
        item.path.read_text(encoding="utf-8").lower()
        for item in migrations
        if item.version in {23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37}
    )

    assert [item.version for item in migrations][-15:] == [23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37]
    for table in V7_TABLES:
        assert f"{table}" in v7_sql
    assert "drop table" not in v7_sql
    assert "drop column" not in v7_sql
    assert "prevent_published_catalog_mutation" in v7_sql
    assert "prevent_published_template_mutation" in v7_sql
    assert "'a4'" in v7_sql


def test_v7_revision_and_snapshot_columns_are_part_of_the_orm_contract():
    draft = Base.metadata.tables["quotation_drafts"].columns
    extraction = Base.metadata.tables["extraction_records"].columns
    generated = Base.metadata.tables["generated_pdf_versions"].columns
    template = Base.metadata.tables["output_template_configs"].columns
    asset = Base.metadata.tables["template_assets"].columns

    assert {
        "revision",
        "company_id",
        "product_id",
        "tier_id",
        "package_id",
        "catalog_revision_id",
        "template_revision_id",
        "layout_override_template_id",
        "layout_override_template_revision_id",
        "layout_override_base_hash",
        "scalar_decisions",
    } <= set(draft.keys())
    assert {"benefit_lines", "company_resolution"} <= set(extraction.keys())
    assert {
        "draft_revision",
        "catalog_revision_id",
        "template_revision_id",
        "render_context_snapshot",
        "render_context_hash",
        "renderer_version",
        "idempotency_key",
    } <= set(generated.keys())
    assert "revision" in template.keys()
    assert {"revision", "content_hash", "original_filename"} <= set(asset.keys())


def test_typed_values_preserve_arbitrary_distance_and_unlimited_semantics():
    exact = BenefitValue.model_validate({"type": "distance", "value": "1700", "unit": "km", "region": "Malaysia"})
    unlimited = BenefitValue.model_validate({"type": "distance", "unlimited": True, "unit": "km", "region": "Malaysia"})

    assert exact.value == Decimal("1700")
    assert exact.model_dump(mode="json")["value"] == "1700"
    assert unlimited.unlimited is True
    assert unlimited.value is None


def test_typed_values_cover_money_percentage_per_day_formula_and_custom():
    money = BenefitValue.model_validate(
        {"type": "money", "value": "1500.50", "currency": "MYR", "semantic_role": "insured_limit"}
    )
    percentage = BenefitValue.model_validate(
        {"type": "percentage", "value": "5", "basis": "sum_insured", "cap": {"amount": "5000", "currency": "MYR"}}
    )
    per_day = BenefitValue.model_validate(
        {"type": "per_day", "value": "150", "currency": "MYR", "max_days": 7, "aggregate_cap": "1050"}
    )
    formula = BenefitValue.model_validate(
        {"type": "formula", "expression": "min(sum_insured * 0.05, 5000)", "variables": {"sum_insured": "100000"}}
    )
    custom = BenefitValue.model_validate({"type": "custom", "display_text": "Reviewed workshop transport arrangement"})

    assert money.value == Decimal("1500.50")
    assert percentage.cap.amount == Decimal("5000")
    assert per_day.max_days == 7
    assert formula.variables["sum_insured"] == "100000"
    assert custom.display_text.startswith("Reviewed")


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "distance", "value": "20"},
        {"type": "distance", "unlimited": True, "value": "20", "unit": "km"},
        {"type": "money", "value": "500"},
        {"type": "per_day", "value": "150", "currency": "MYR", "max_days": 0},
        {"type": "formula", "expression": "", "variables": {}},
        {"type": "custom", "display_text": ""},
    ],
)
def test_invalid_or_incomplete_typed_values_are_rejected(payload: dict):
    with pytest.raises(ValidationError):
        BenefitValue.model_validate(payload)


def test_review_state_enums_do_not_encode_contradictory_render_flags():
    assert set(ReviewedBenefitState) == {
        ReviewedBenefitState.CURRENT,
        ReviewedBenefitState.AVAILABLE_ADDON,
        ReviewedBenefitState.REMOVED,
        ReviewedBenefitState.SUPERSEDED,
        ReviewedBenefitState.UNRESOLVED,
    }
    assert set(CostStatus) == {CostStatus.INCLUDED, CostStatus.PAID, CostStatus.FOC, CostStatus.UNKNOWN}
    assert set(SourceLineDisposition) == {
        SourceLineDisposition.UNRESOLVED,
        SourceLineDisposition.MAPPED,
        SourceLineDisposition.CUSTOM,
        SourceLineDisposition.SOURCE_ONLY,
        SourceLineDisposition.OMITTED,
    }


def test_legacy_special_adapter_preserves_content_without_guessing_company_or_verification():
    adapted = adapt_legacy_special(
        {"id": "legacy-parent", "label": "Towing", "category": "FOC"},
        [{"id": "legacy-variant", "label": "Unlimited Towing", "value_text": "Unlimited", "icon_asset_id": "asset-1"}],
    )

    assert adapted["compatibility_state"] == "legacy_read_only"
    assert adapted["company_id"] is None
    assert adapted["catalog_revision_id"] is None
    assert adapted["verified"] is False
    assert adapted["variants"][0]["value_text"] == "Unlimited"
    assert adapted["variants"][0]["icon_asset_id"] == "asset-1"


def test_legacy_template_adapter_creates_read_only_revision_without_company_coupling():
    adapted = adapt_legacy_template(
        {"id": "template-1", "name": "Legacy QBE", "insurance_company_id": "company-1", "fixed_fields": {"canvas": {"width": 794, "height": 1123}}}
    )

    assert adapted["template_id"] == "template-1"
    assert adapted["company_id"] is None
    assert adapted["legacy_company_id"] == "company-1"
    assert adapted["state"] == "compatibility"
    assert adapted["config"]["canvas"]["width"] == 794
