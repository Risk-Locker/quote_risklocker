"""Unit tests for Milestone 5: Master Template Consolidation and Extras Display Mode."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.master_template_service import master_template_specs
from app.services.template_revision_service import list_published_templates
from app.models.tables import OutputTemplateConfig, TemplateRevision, TemplatePageProfile, User, Role


class FakeDb:
    def __init__(self, values):
        self.values = {(type(item), item.id): item for item in values}

    def get(self, model, object_id):
        return self.values.get((model, object_id))

    def scalars(self, statement):
        entity = statement.column_descriptions[0].get("entity") if statement.column_descriptions else None
        return FakeScalars(item for (model, _item_id), item in self.values.items() if model is entity)


class FakeScalars:
    def __init__(self, items):
        self.items = list(items)

    def all(self):
        return list(self.items)


def test_master_template_specs_marks_extras_variants_as_deprecated():
    """Verify master_template_specs distinguishes active vs deprecated variant rows."""
    all_specs = master_template_specs(active_only=False)
    active_specs = master_template_specs(active_only=True)

    # 1. Total specs contains legacy and active
    assert len(all_specs) >= len(active_specs)

    # 2. Active specs must NOT contain separate (No Extras) or (Lump Sum Extras) variants
    for spec in active_specs:
        assert "(No Extras)" not in spec["name"], f"Deprecated variant found in active specs: {spec['name']}"
        assert "(Lump Sum Extras)" not in spec["name"], f"Deprecated variant found in active specs: {spec['name']}"

    # 3. Canonical default Bilingual Agency Motor v4 must be present and active
    v4_active = next((s for s in active_specs if s["key"] == "agency_bilingual_v4"), None)
    assert v4_active is not None
    assert v4_active["is_default"] is True


def test_list_published_templates_excludes_deprecated_variants():
    """Verify list_published_templates excludes (No Extras) and (Lump Sum Extras) variants from published list."""
    user = User(id="u1", email="admin@risklocker.com", role=Role.ADMIN, password_hash="fakehash")
    profile = TemplatePageProfile(id="p1", profile_key="a4", name="A4", width=794.0, height=1123.0, unit="px", safe_margins={}, background_behavior="clip")

    canonical_tmpl = OutputTemplateConfig(
        id="t-v4",
        name="Bilingual Agency Motor v4",
        status="active",
        insurance_type="Motor",
        fixed_fields={"is_default": True, "v7_master_key": "agency_bilingual_v4"},
    )
    no_extras_tmpl = OutputTemplateConfig(
        id="t-v4-no-extras",
        name="Bilingual Agency Motor v4 (No Extras)",
        status="active",
        insurance_type="Motor",
        fixed_fields={"is_default": False, "v7_master_key": "agency_bilingual_v4_no_extras"},
    )
    lump_sum_tmpl = OutputTemplateConfig(
        id="t-v4-lump-sum",
        name="Bilingual Agency Motor v4 (Lump Sum Extras)",
        status="active",
        insurance_type="Motor",
        fixed_fields={"is_default": False, "v7_master_key": "agency_bilingual_v4_lump_sum"},
    )

    revisions = [
        TemplateRevision(id="r-v4", template_id="t-v4", revision_number=1, state="published", page_profile_id=profile.id, config={"template_name": "Bilingual Agency Motor v4"}, config_hash="h1"),
        TemplateRevision(id="r-no-extras", template_id="t-v4-no-extras", revision_number=1, state="published", page_profile_id=profile.id, config={"template_name": "Bilingual Agency Motor v4 (No Extras)"}, config_hash="h2"),
        TemplateRevision(id="r-lump-sum", template_id="t-v4-lump-sum", revision_number=1, state="published", page_profile_id=profile.id, config={"template_name": "Bilingual Agency Motor v4 (Lump Sum Extras)"}, config_hash="h3"),
    ]

    db = FakeDb([profile, canonical_tmpl, no_extras_tmpl, lump_sum_tmpl, *revisions])

    published = list_published_templates(db, user)

    # Must contain ONLY the canonical template, not the deprecated variant presets
    published_names = [p["name"] for p in published]
    assert "Bilingual Agency Motor v4" in published_names
    assert "Bilingual Agency Motor v4 (No Extras)" not in published_names
    assert "Bilingual Agency Motor v4 (Lump Sum Extras)" not in published_names
    assert len(published) == 1


def test_renderer_honors_display_options_extras_mode():
    """Verify template renderer honors extras_mode set via display_options."""
    from app.rendering.template_renderer import render_quotation_html
    from app.services.master_template_service import _agency_bilingual_v4_config

    config = _agency_bilingual_v4_config()
    fields = {"premium": {"value": "2000.00"}, "roadtax": {"value": "100.00"}, "total_amount": {"value": "2100.00"}}
    extras = [{"label": "Windscreen Coverage", "price": {"amount": "150.00"}}, {"label": "Legal Liability Passenger", "price": {"amount": "25.00"}}]

    # 1. Itemized mode: shows individual extra names
    html_itemized = render_quotation_html(
        draft_fields=fields,
        template_name="Bilingual Agency Motor v4",
        template_config=config,
        render_context={"extras": extras, "display_options": {"extras_mode": "itemized"}},
    )
    assert "Windscreen Coverage" in html_itemized
    assert "Legal Liability Passenger" in html_itemized

    # 2. Lump sum mode: collapses individual items
    html_lump = render_quotation_html(
        draft_fields=fields,
        template_name="Bilingual Agency Motor v4",
        template_config=config,
        render_context={"extras": extras, "display_options": {"extras_mode": "lump_sum"}},
    )
    assert "Windscreen Coverage" not in html_lump

    # 3. None mode: completely hides extra coverage
    html_none = render_quotation_html(
        draft_fields=fields,
        template_name="Bilingual Agency Motor v4",
        template_config=config,
        render_context={"extras": extras, "display_options": {"extras_mode": "none"}},
    )
    assert "Windscreen Coverage" not in html_none
    assert "Total Extra Coverage" not in html_none

