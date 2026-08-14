import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.extraction.candidate_finder import find_candidates
from app.extraction.draft_mapper import build_draft
from app.extraction.validators import normalize_date, normalize_money, validate_date_range
from app.rendering.pdf_generator import PdfRendererUnavailable, html_to_pdf
from app.rendering.template_renderer import render_quotation_html
from app.services.template_config import default_template_config, normalize_template_config


def test_messy_text_maps_customer_vehicle_and_year():
    text = "NAME : XKSFSKSGS CAR- PROTON model no. ajbgyubygwpv is saga blm dngdnf 2010 sgsgs"
    candidates = find_candidates(text, [{"page": 1, "text": text}])
    fields, warnings, status = build_draft(candidates)

    assert fields["customer_name"]["value"] == "XKSFSKSGS"
    assert fields["car_brand"]["value"] == "PROTON"
    assert fields["car_model"]["value"] == "SAGA BLM"
    assert fields["vehicle_year"]["value"] == "2010"
    assert status in {"Check Needed", "Cannot Read"}
    assert warnings


def test_messy_compact_text_maps_model_cc_and_coverage_type():
    text = "SAGA1556cc1.6lcomprehensiveJALANSetiatropika"
    candidates = find_candidates(text, [{"page": 1, "text": text}])
    fields, _, _ = build_draft(candidates)

    assert fields["car_model"]["value"] == "SAGA"
    assert fields["engine_cc"]["value"] == "1556"
    assert fields["coverage_type"]["value"] == "Comprehensive"


def test_ncd_brackets_are_normalized_to_number():
    text = "CONTRIBUTION SUMMARY\nNCD (55.00%)\nRM\n891.50"
    candidates = find_candidates(text, [{"page": 1, "text": text}])
    fields, _, _ = build_draft(candidates)

    assert fields["ncd_percent"]["value"] == "55.00"


def test_money_and_date_normalization():
    assert normalize_money("RM 1,234.50") == "1234.50"
    assert normalize_date("09/07/2026") == "2026-07-09"
    assert validate_date_range("2026-07-09", "2027-07-08")[0]


def test_pdf_generation_smoke(tmp_path):
    html = render_quotation_html({"customer_name": {"value": "Test Customer"}})
    try:
        output, _ = html_to_pdf(html, tmp_path / "quotation.pdf")
    except PdfRendererUnavailable as exc:
        import pytest

        pytest.skip(f"Pinned browser renderer is unavailable in this execution sandbox: {exc}")
    data = output.read_bytes()
    assert data.startswith(b"%PDF")
    assert len(data) > 100


def test_default_template_is_canvas_locked_and_visual():
    config = normalize_template_config(default_template_config())

    assert config["locked"] is True
    assert config["canvas"]["width"] == 794
    assert any(element["type"] == "benefit-section" for element in config["canvas"]["elements"])


def test_canvas_renderer_uses_fields():
    config = default_template_config(locked=False)
    fields = {
        "vehicle_no": {"value": "ABC1234"},
        "coverage_type": {"value": "Comprehensive"},
    }

    html = render_quotation_html(fields, template_config=config)

    assert "ABC1234" in html
    assert "Comprehensive" in html
