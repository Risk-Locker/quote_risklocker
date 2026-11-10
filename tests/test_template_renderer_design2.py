"""Hermetic tests for Risklocker Motor Quotation Design 2 renderer and UUID guards."""

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
os.environ.setdefault("APP_ENV", "test")

from app.rendering.template_renderer_design2 import render_design2_html


def _base_fields():
    return {
        "customer_name": {"value": "CHENG TECK KIOING"},
        "quotation_reference": {"value": "RL260000314"},
        "vehicle_no": {"value": "ANY 368"},
        "insurance_company": {"value": "ETIQA GENERAL INSURANCE BERHAD"},
        "car_model": {"value": "Tesla Model 3 Performance"},
        "cover_period": {"value": "04-06-2026 TO 03-06-2027"},
        "coverage_type": {"value": "Comprehensive"},
        "ncd_percent": {"value": "25.00%"},
        "valuation_type": {"value": "Market Value"},
        "excess_amount": {"value": "0.00"},
        "coverage_amount": {"value": "198000.00"},
        "premium": {"value": "5328.10"},
        "roadtax": {"value": "40.00"},
        "runner_fee": {"value": "0.00"},
        "total_amount": {"value": "5447.30"},
    }


def test_render_design2_html_structure_and_assets():
    render_context = {
        "current_benefits": [
            {"id": "windscreen", "label": "Windscreen Coverage", "value": "RM 8,000", "is_extra": True},
            {"id": "towing", "label": "Unlimited Towing Distance", "value": "Unlimited", "is_extra": True},
            {"id": "special_perils", "label": "Special Perils", "value": "RM 0", "is_extra": True},
            {"id": "legal_defense", "label": "Legal Defense Costs", "is_extra": False, "cost_status": "foc"},
            {"id": "emergency_towing", "label": "Emergency Towing Assistance", "is_extra": False, "cost_status": "foc"},
        ],
        "available_addons": [
            {"id": "cart", "label": "Compensation for Assessed Repair Time"},
            {"id": "key_care", "label": "Key Care Replacement"},
        ],
    }

    html = render_design2_html(_base_fields(), render_context=render_context)

    assert "<title>Motor Insurance Quotation - RL260000314</title>" in html
    assert 'data-d2-root="1"' in html
    assert "@page { size: 794px 1123px; margin: 0; }" in html
    assert "CHENG TECK KIOING" in html
    assert "ANY 368" in html
    assert "ETIQA GENERAL INSURANCE BERHAD" in html
    assert "Tesla Model 3 Performance" in html
    assert "TOTAL PAYABLE 应付总额" in html
    assert "RM 5,447.30" in html
    assert "Free Added Coverage" in html
    assert "Company Bank Details" in html
    assert "RISKLOCKER SDN.BHD." in html
    assert "12300318500" in html
    assert "Add-On" in html
    assert "Upgrades" in html
    assert "ADDITIONAL PROTECTION FOR GREATER PEACE OF MIND" in html
    assert "RM 8,000.00" in html
    assert ">RM 0<" not in html  # Suppressed ugly RM 0
    assert "data:image/" in html  # Official logo & QRs embedded
    assert "admin@risklocker.com" in html
    assert "Contact Us On Whatsapp" in html
    # Visual parity invariants: value-only underline, #F8F9FC panel, 108px footer, structural dividers
    assert "border-bottom: 1px solid #334155;" in html
    assert "background: #F8F9FC;" in html
    assert "height: 108px;" in html
    assert "height: 46px; background: rgba(255, 255, 255, 0.72);" in html


def test_lonpac_unselected_available_addons_have_zero_selected_marks():
    html = render_design2_html(
        {**_base_fields(), "insurance_company": {"value": "LONPAC INSURANCE BERHAD"}},
        render_context={
            "current_benefits": [
                {"id": "towing-basic", "concept_key": "towing", "label": "Emergency Towing Assistance", "cost_status": "included", "is_extra": False},
            ],
            "available_addons": [
                {"id": "windscreen", "label": "Windscreen Coverage", "value": "1000.0", "price": {"amount": 150.0}},
                {"id": "special_perils", "label": "Special Perils", "price": {"amount": 250.0}},
            ],
        },
    )
    # Only the Free Added Coverage card uses a green checkmark; the 24-card grid must have 0 checkmarks
    lower_part = html.split("ADDITIONAL PROTECTION FOR GREATER PEACE OF MIND")[1]
    assert 'fill="#22C55E"' not in lower_part
    assert 'fill="#5ABA00"' not in lower_part
    assert "RM 1,000.00" in lower_part


def test_render_design2_overflow_beyond_24_and_multipage_pdf(tmp_path):
    from app.rendering.pdf_generator import html_to_pdf

    extra_custom = [
        {"id": f"custom-{i}", "label": f"Extended Motor Shield {i}", "description": "Custom underwriter endorsement."}
        for i in range(1, 6)
    ]
    render_context = {
        "current_benefits": [
            {"id": "windscreen", "label": "Windscreen Coverage", "value": "RM 10,000.00", "is_extra": True},
            {"id": "towing", "label": "Unlimited Towing Distance", "value": "Unlimited", "is_extra": True},
        ],
        "available_addons": extra_custom,
    }

    html = render_design2_html(_base_fields(), render_context=render_context)
    assert html.count('class="d2-page"') >= 2
    assert "Continued Slots 25" in html
    assert "Extended Motor Shield 5" in html

    out_pdf = tmp_path / "test_design2_multipage.pdf"
    path, _warnings = html_to_pdf(html, out_pdf, width=794, height=1123)
    assert path.exists()
    assert out_pdf.read_bytes().startswith(b"%PDF-")

    try:
        import fitz
        doc = fitz.open(str(out_pdf))
        assert doc.page_count >= 2
        doc.close()
    except ImportError:
        pass


def test_motor_modern_design2_config_is_valid_v7_and_dispatches():
    from app.services.master_template_service import motor_modern_design_2_config
    from app.services.template_revision_service import validate_template_config
    from app.rendering.template_renderer import render_quotation_html

    cfg = motor_modern_design_2_config()
    validated = validate_template_config(cfg)
    assert validated["version"] == 7
    assert validated["layout_engine"] == "design2"
    assert validated["template_key"] == "motor_modern_design_2"

    html = render_quotation_html(
        draft_fields={"customer_name": {"value": "ALICE TAN"}},
        template_name=validated["template_name"],
        template_config=validated,
        render_context={"current_benefits": [], "available_addons": []},
    )
    assert "ALICE TAN" in html
    assert "Add-On" in html
    assert "Upgrades" in html


def test_non_uuid_template_ids_never_crash_postgres_queries():
    from app.core.errors import AppError
    from app.models.enums import Role
    from app.models.tables import QuotationDraft, Session
    from app.services.session_service import serialize_session
    from app.services.workspace_patch_service import _apply_layout_override, _apply_template_selection
    from app.services.workspace_snapshot_service import template_selection_impact

    class StrictUuidDb:
        bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        def get(self, model, pk):
            model_name = getattr(model, "__name__", str(model))
            if model is Session:
                return SimpleNamespace(id=pk, draft_id="draft-1", owner_id="u1")
            if model is QuotationDraft:
                return SimpleNamespace(
                    id=pk,
                    deleted_at=None,
                    template_revision_id="rev-motor-modern-design-2",
                    layout_override=None,
                    layout_override_template_id=None,
                    layout_override_template_revision_id=None,
                    layout_override_base_hash=None,
                )
            raise AssertionError(f"Unexpected db.get({model_name}, {pk!r}) — UUID validation failed to guard query")

    db = StrictUuidDb()
    user = SimpleNamespace(id="u1", role=Role.STAFF.value)
    draft = db.get(QuotationDraft, "draft-1")

    with pytest.raises(AppError) as exc1:
        template_selection_impact(db, user, "sess-1", template_revision_id="rev-motor-modern-design-2", base_revision=1)
    assert exc1.value.status_code == 422

    with pytest.raises(AppError) as exc2:
        _apply_template_selection(db, draft, {"template_revision_id": "rev-motor-modern-design-2", "confirmed": True})
    assert exc2.value.status_code == 422

    with pytest.raises(AppError) as exc3:
        _apply_layout_override(db, draft, {"template_revision_id": "rev-motor-modern-design-2", "template_id": "t1", "base_hash": "h1", "layout": {}})
    assert exc3.value.status_code == 409

    # serialize_session must also tolerate non-UUID legacy/stale revision IDs without querying TemplateRevision
    fake_session = SimpleNamespace(
        id="00000000-0000-0000-0000-000000000002",
        owner_id="u1",
        is_test=False,
        owner=SimpleNamespace(name="Admin", email="admin@risklocker.com"),
        last_edited_by=None,
        last_edited_at=None,
        quotation_ref="RL260000999",
        quotation_status="pending",
        document_type="quotation",
        policy_number=None,
        miss_reason=None,
        coverage_start_date=None,
        coverage_end_date=None,
        tenure_id=None,
        customer_id=None,
        tracked_vehicle_id=None,
        tracked_vehicle=None,
        detected_company="Etiqa",
        status="review",
        created_at=None,
        updated_at=None,
        uploaded_file_id=None,
        uploaded_file=None,
        draft_id=draft.id,
        draft=SimpleNamespace(
            status="reviewed",
            fields={},
            template_revision_id="rev-motor-modern-design-2",
            layout_override_template_id=None,
            revision=1,
            display_options={},
            company_id=None,
            company=None,
            package_id=None,
            package=None,
            product_id=None,
            product=None,
            tier_id=None,
            tier=None,
            generated_versions=[],
        ),
    )
    payload = serialize_session(fake_session, db=db)
    assert payload["id"] == fake_session.id
