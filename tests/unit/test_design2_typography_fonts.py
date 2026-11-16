import pytest
from app.rendering.template_renderer_design2 import render_design2_html
from app.rendering.benefit_schedule_renderer import render_benefit_schedule_html


def test_design2_html_renders_designer_font_hierarchy():
    draft = {
        "quotation_reference": "QT-FONT-TEST-001",
        "vehicle_number": "WXY1234",
        "underwriter": "Allianz",
        "customer_name": "TEST DRIVER",
        "period_of_insurance": "01/01/2026 - 31/12/2026",
        "coverage_type": "Comprehensive",
        "model_name": "Proton Saga",
        "ncd": "55%",
        "sum_insured": "35000",
        "total_premium": "1200.00",
    }
    html = render_design2_html(draft)

    # Must contain Helvetica and Chinese font family stack (Source Han Sans / Noto Sans SC)
    assert "Helvetica" in html
    assert "Source Han Sans" in html or "Noto Sans SC" in html
    assert "Calibri" in html
    # Must not contain retired Be Vietnam Pro font
    assert "Be Vietnam Pro" not in html


def test_benefit_schedule_html_renders_designer_font_hierarchy():
    draft = {
        "quotation_reference": "QT-FONT-TEST-002",
        "vehicle_number": "WXY1234",
        "underwriter": "Allianz",
        "customer_name": "TEST DRIVER",
    }
    html = render_benefit_schedule_html(draft)

    assert "Helvetica" in html
    assert "Source Han Sans" in html or "Noto Sans SC" in html
    assert "Be Vietnam Pro" not in html
