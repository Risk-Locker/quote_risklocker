"""Automated tests for Liberty / Kurnia / AmAssurance / MMIP disambiguation & catalog domain parity."""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import fitz
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.domain.motor.towing_matrix import resolve_towing_entitlement
from app.domain.motor.winner_ranking_rules import apply_towing_advantage_rule
from app.extraction.brand_logo_scanner import (
    analyze_logo_chromaticity,
    extract_page1_primary_brand_signals,
    is_liberty_group_document,
    render_page1_logo_crop,
)
from app.extraction.candidate_finder import find_candidates
from app.extraction.company_resolution import company_alias_matches, resolve_company
from app.extraction.draft_mapper import build_draft
from app.services.marketing_comparison.company_rules import resolve_company_policy_rules
from app.services.marketing_comparison.towing_evaluator import resolve_insurer_towing_limit

LIBERTY_ID = "c0000000-0000-4000-8000-000000000091"
KURNIA_ID = "c0000000-0000-4000-8000-000000000002"
AMASSURANCE_ID = "c0000000-0000-4000-8000-000000000001"
MMIP_ID = "c0000000-0000-4000-8000-000000000099"

SEPARATE_COMPANIES = [
    {
        "company_id": AMASSURANCE_ID,
        "name": "AmAssurance",
        "source_template_category": "Amgen / AmAssurance / Kurnia-style",
        "aliases": ["AmAssurance", "AmGen", "AmGeneral", "AmGeneral Insurance", "www.amassurance.com.my", "amassurance.com.my"],
    },
    {
        "company_id": KURNIA_ID,
        "name": "Kurnia",
        "source_template_category": "Amgen / AmAssurance / Kurnia-style",
        "aliases": ["Kurnia", "Kurnia Insurans", "Kurnia Insurance", "www.kurnia.com", "kurnia.com", "Kurnia Auto Assist"],
    },
    {
        "company_id": LIBERTY_ID,
        "name": "Liberty",
        "source_template_category": "Amgen / AmAssurance / Kurnia-style",
        "aliases": ["Liberty", "Liberty Insurance", "Liberty Insurance Berhad", "www.libertyinsurance.com.my", "libertyinsurance.com.my"],
    },
    {
        "company_id": MMIP_ID,
        "name": "MMIP",
        "source_template_category": "Third Party",
        "aliases": ["MMIP", "Malaysian Motor Insurance Pool", "Motor Insurance Pool"],
    },
]


def test_liberty_schedule_with_shared_parent_and_auto365_resolves_strictly_to_liberty():
    liberty_doc = (
        "Liberty Insurance\n"
        "Liberty General Insurance Berhad 197801007153 (44191-P)\n"
        "Product: auto365 Comprehensive Premier\n"
        "Quotation Ref No. QE310595-001\n"
        "Head Office: Liberty Insurance Tower, CT9 Pavilion Damansara\n"
        "Website: www.libertyinsurance.com.my\n"
        "Download Kurnia One Touch or read PDPA Notice for AmGeneral customers.\n"
    )
    resolved = resolve_company(liberty_doc, SEPARATE_COMPANIES)
    assert resolved["status"] == "matched"
    assert resolved["company_id"] == LIBERTY_ID
    assert resolved["display_name"] == "Liberty"


def test_kurnia_schedule_with_amgen_agency_code_resolves_to_kurnia():
    kurnia_doc = (
        "KURNIA INSURANS\n"
        "Liberty General Insurance Berhad\n"
        "Agency Code: AMGEN J1204\n"
        "Product: auto365 Comprehensive Premier\n"
        "Website: www.kurnia.com\n"
    )
    resolved = resolve_company(kurnia_doc, SEPARATE_COMPANIES)
    assert resolved["status"] == "matched"
    assert resolved["company_id"] == KURNIA_ID
    assert resolved["display_name"] == "Kurnia"


def test_amassurance_schedule_with_kurnia_one_touch_footer_resolves_to_amassurance():
    am_doc = (
        "AmAssurance\n"
        "Liberty General Insurance Berhad\n"
        "Product: auto365 Comprehensive Premier\n"
        "Website: www.amassurance.com.my\n"
        "Manage claims anytime via Kurnia One Touch Mobile App.\n"
    )
    resolved = resolve_company(am_doc, SEPARATE_COMPANIES)
    assert resolved["status"] == "matched"
    assert resolved["company_id"] == AMASSURANCE_ID
    assert resolved["display_name"] == "AmAssurance"


def test_mmip_overrides_servicing_insurer_and_forces_third_party():
    mmip_doc = (
        "MALAYSIAN MOTOR INSURANCE POOL (MMIP)\n"
        "Servicing Insurer: Liberty General Insurance Berhad / Liberty Insurance / AmAssurance\n"
        "Comprehensive Quotation Schedule\n"
        "Sum Insured: RM 25,000.00\n"
        "Gross Premium: RM 350.00\n"
    )
    matches = company_alias_matches(mmip_doc, SEPARATE_COMPANIES)
    assert matches[0]["company"]["name"] == "MMIP"

    cands = find_candidates(
        mmip_doc,
        [{"page": 1, "text": mmip_doc}],
        [],
        source_filename="Liberty_MMIP_QBG1431.pdf",
        db_companies=SEPARATE_COMPANIES,
    )
    fields, _, _ = build_draft(cands, raw_text=mmip_doc)
    assert fields["insurance_company"]["value"] == "MMIP"
    assert fields["coverage_type"]["value"] == "Third Party"


def test_liberty_kurnia_amassurance_domain_towing_and_ranking_parity():
    scenarios = [
        ("auto365 Comprehensive Lite", None, "", "50 km"),
        ("auto365 Comprehensive Plus", None, "", "100 km"),
        ("auto365 Comprehensive Premier", None, "", "365 km"),
        ("auto365 TPFT Premier", None, "", "200 km"),
        ("auto365 Comprehensive", "Private Car 365 Plan 1", "", "600 km"),
        ("auto365 Comprehensive", "Private Car 365 Plan 2", "", "Unlimited"),
        ("auto365 Comprehensive", "Private Car 365 Plan 4", "", "Unlimited"),
    ]
    for product, rider, text, expected in scenarios:
        res_by_brand = [
            resolve_towing_entitlement(brand, product, rider, text).formatted
            for brand in ("AmAssurance", "Kurnia", "Liberty")
        ]
        assert res_by_brand == [expected, expected, expected], (product, rider, res_by_brand)

    # Ensure legacy 150 km Liberty hijack is completely gone in towing_evaluator & policy_rules
    assert resolve_insurer_towing_limit("Liberty", "private car comprehensive") == "100 km"
    assert resolve_insurer_towing_limit("Liberty", "auto365 Comprehensive Premier") == "365 km"
    assert resolve_company_policy_rules("Liberty")["towing"]["premier_limit"] == "365 km"
    assert resolve_company_policy_rules("Kurnia")["towing"]["premier_limit"] == "365 km"

    # STMB vs Amgen/Liberty/Kurnia RM 40 towing-advantage rule treats Liberty/Kurnia identically to AmAssurance
    for insurer_name in ("AmAssurance", "Kurnia", "Liberty"):
        stmb = SimpleNamespace(company_name="STMB", total_payable=Decimal("1000.00"), towing_km="100 km", rank=1, is_recommended=True)
        am_family = SimpleNamespace(company_name=insurer_name, total_payable=Decimal("1035.00"), towing_km="365 km", rank=2, is_recommended=False)
        ranked = apply_towing_advantage_rule([stmb, am_family])
        assert ranked[0].company_name == insurer_name
        assert ranked[0].rank == 1
        assert ranked[0].is_recommended is True


def _make_logo_png_bytes(rgb: tuple[int, int, int]) -> bytes:
    img = Image.new("RGB", (240, 120), color=(255, 255, 255))
    for x in range(20, 140):
        for y in range(20, 90):
            img.putpixel((x, y), rgb)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_brand_logo_scanner_chromaticity_and_pdf_crop():
    assert analyze_logo_chromaticity(_make_logo_png_bytes((229, 35, 32)))["color_hint"] == "red_amassurance"
    assert analyze_logo_chromaticity(_make_logo_png_bytes((35, 165, 235)))["color_hint"] == "sky_blue_kurnia"
    assert analyze_logo_chromaticity(_make_logo_png_bytes((15, 35, 80)))["color_hint"] == "dark_blue_liberty_or_kurnia"

    # Build a synthetic 1-page PDF with dark navy top-left block + Liberty website footer
    doc = fitz.open()
    page = cast(Any, doc).new_page(width=595, height=842)
    page.draw_rect(fitz.Rect(24, 24, 150, 80), color=(0.05, 0.14, 0.35), fill=(0.05, 0.14, 0.35))
    page.insert_text((24, 110), "Liberty Insurance - Liberty General Insurance Berhad\nauto365 Comprehensive Premier")
    page.insert_text((24, 800), "Website: www.libertyinsurance.com.my")
    pdf_bytes = doc.tobytes()
    doc.close()

    crop_png, meta = render_page1_logo_crop(pdf_bytes)
    assert crop_png is not None and len(crop_png) > 100
    assert meta["color_hint"] == "dark_blue_liberty_or_kurnia"

    p1 = extract_page1_primary_brand_signals(
        "Liberty Insurance\nLiberty General Insurance Berhad\nwww.libertyinsurance.com.my\nauto365 Comprehensive Premier"
    )
    assert p1["winning_brand"] == "Liberty"
    assert is_liberty_group_document("auto365 Comprehensive Premier", "www.kurnia.com") is True
    assert is_liberty_group_document("Malaysian Motor Insurance Pool MMIP", "") is False
