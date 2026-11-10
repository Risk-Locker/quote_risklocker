"""Hermetic tests for standalone and combined Benefits & Endorsements Schedule rendering."""

import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
os.environ.setdefault("APP_ENV", "test")

from app.api.routers.templates import admin_template_preview_render
from app.api.schemas import TemplateLivePreviewRequest
from app.models.enums import Role
from app.rendering.benefit_schedule_renderer import (
    render_benefit_schedule_html,
    render_design2_schedule_pages,
)
from app.rendering.template_renderer_design2 import render_design2_html


def _sample_fields():
    return {
        "customer_name": {"value": "TAN MEI LING"},
        "quotation_reference": {"value": "RL260000777"},
        "vehicle_no": {"value": "WXY 7788"},
        "insurance_company": {"value": "TAKAFUL MALAYSIA"},
    }


def _sample_context():
    return {
        "current_benefits": [
            {"id": "b1", "label": "Legal Defense Costs", "cost_status": "included", "is_extra": False, "description": "Court legal fee reimbursement up to RM 2,000."},
            {"id": "e1", "label": "Windscreen Coverage", "value": "RM 8,000", "is_extra": True, "price": {"amount": 220.0}, "description": "Front & rear laminated windscreen replacement without NCD impact."},
            {"id": "e2", "label": "Special Perils", "value": "RM 0", "is_extra": True, "price": {"amount": 350.0}, "description": "Flood, storm, tempest, landslide and natural disaster cover."},
        ],
        "available_addons": [
            {"id": "a1", "label": "Compensation for Assessed Repair Time", "value": "14 Days", "price": {"amount": 200.0}, "description": "RM 100 per day allowance while vehicle is in panel workshop."},
            {"id": "a2", "label": "Waiver of Betterment", "price": {"amount": 120.0}, "description": "Covers new replacement part cost without age-based deduction."},
        ],
    }


def test_render_standalone_benefit_schedule_html():
    html = render_benefit_schedule_html(_sample_fields(), render_context=_sample_context())

    assert "<title>Benefits & Endorsements Schedule - RL260000777</title>" in html
    assert 'class="d2-page"' in html
    assert "TAN MEI LING" in html
    assert "WXY 7788" in html
    assert "Active Coverages &amp; Selected Endorsements" in html
    assert "Optional Add-On Upgrades Reference" in html
    assert "RM 8,000.00" in html
    assert "Sheet 1/" in html
    assert "RISKLOCKER SDN. BHD." in html


def test_render_design2_combined_via_display_options():
    html = render_design2_html(
        _sample_fields(),
        render_context={**_sample_context(), "display_options": {"include_benefit_schedule": True}},
    )
    assert html.count('class="d2-page"') == 2
    assert "Sheet 2/" in html


def test_render_design2_schedule_pages_overflow_and_pagination():
    large_addons = [
        {"id": f"opt-{i}", "label": f"Extended Underwriter Protection #{i}", "description": "Full extended endorsement terms apply."}
        for i in range(1, 22)
    ]
    ctx = {
        "current_benefits": _sample_context()["current_benefits"],
        "available_addons": large_addons,
    }
    pages = render_design2_schedule_pages(_sample_fields(), render_context=ctx, overflow_start_index=24, start_page_num=2)
    # 21 custom items -> slots 25..45 overflow + remaining optional pagination creates 2 schedule sheets
    assert len(pages) == 2
    assert "Continued Slots 25" in pages[0]
    assert "Sheet 2/3" in pages[0]
    assert "Sheet 3/3" in pages[1]


def test_admin_preview_render_modes_hermetic():
    class FakeQuery:
        def filter(self, *args, **kwargs):
            return self

        def filter_by(self, **kwargs):
            return self

        def first(self):
            return None

        def all(self):
            return []

    class StrictDummyDb:
        bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        def query(self, *args, **kwargs):
            return FakeQuery()

        def scalars(self, *args, **kwargs):
            return FakeQuery()

        def scalar(self, *args, **kwargs):
            return 0

        def execute(self, *args, **kwargs):
            return FakeQuery()

        def rollback(self):
            pass

    db = StrictDummyDb()
    user = SimpleNamespace(id="u1", role=Role.SUPER_ADMIN.value)

    # Standalone schedule preview
    sched_res = admin_template_preview_render(
        TemplateLivePreviewRequest(
            template_id="non-uuid-key",
            session_id="invalid-uuid",
            load_profile="medium",
            render_mode="schedule",
        ),
        db=db,
        user=user,
    )
    assert "Benefits &amp; Endorsements Schedule" in sched_res["html"]
    assert sched_res["html"].count('class="d2-page"') == 1

    # Combined quotation + schedule preview (legacy v4 template fallback injects Sheet 2)
    comb_res = admin_template_preview_render(
        TemplateLivePreviewRequest(
            load_profile="medium",
            render_mode="combined",
        ),
        db=db,
        user=user,
    )
    assert "Benefits &amp; Endorsements Schedule" in comb_res["html"]
    assert 'class="d2-page"' in comb_res["html"]

    # Design 2 combined preview
    d2_res = admin_template_preview_render(
        TemplateLivePreviewRequest(
            template_config={"layout_engine": "design2", "template_key": "motor_modern_design_2"},
            load_profile="high",
            render_mode="combined",
        ),
        db=db,
        user=user,
    )
    assert d2_res["html"].count('class="d2-page"') >= 2
