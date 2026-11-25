"""Tests for Product Disclosure Sheet (PDS) isolation and spurious benefit extraction prevention."""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.extraction.benefit_lines import (
    extract_benefit_lines,
    is_pds_text,
    is_spurious_benefit_line,
)
from app.extraction.candidate_finder import _add_optional_covers


def test_is_spurious_benefit_line_catches_all_noise():
    """Verify that contact info, taxes, basic premium, NCD, commission, vehicle metadata, and PDS questions are rejected."""
    spurious_cases = [
        # 1. Contact info
        "03-2262 8666",
        "+603-27237899",
        "012-3456789",
        "Email us at: customerservice@lonpac.com 1 2",
        "claims@lonpac.com",
        "visit: www.pidm.gov.my",
        "www.lonpac.com",
        # 2. Form & revision codes
        "26/PRN/PDS/VC CP/Jan v-1.0.0",
        "PDS/VC/2026",
        "Form v-2.0",
        # 3. Accounting computation breakdown rows
        "Basic premium RM 2296.60",
        "(-) 0% NCD entitlement",
        "(+) 8% Service tax RM 193.33",
        "(+) Stamp duty RM 10.00",
        "10% or RM 241.66",
        "Total premium payable RM 2,619.93",
        "Gross premium RM 9,027.37",
        "Policy Excess : RM5900.00",
        "Compulsory Excess : RM 400.00",
        "Rebate for direct channel : 10%",
        # 4. Vehicle metadata & sum insured / cover type lines
        "Manufacturing year 2020",
        "Year of manufacture: 2025",
        "RM50,000 / Comprehensive",
        "RM 80,000 / Third Party Fire & Theft",
        "Class of Vehicle : Commercial Vehicle",
        "Vehicle Make & Model / Capacity",
        "Engine No : CM6D1837550125A00109",
        "Chassis No : LZ5N2CD3XSB000554",
        # 5. Narrative illustration / disclaimers / questionnaires
        "As an illustration, for RM2,619.93 annually, you will receive the following coverage:",
        "For this motor insurance policy, you must pay a premium of:",
        "Disclaimer: The premium stated in this document is an indicative and non-binding.",
        "NOTE: 1) If estimated figures are provided in this quotation, accurate computations will be provided",
        "Can I cancel my policy?",
        "What is Commercial Vehicle (A or C Permit) - Comprehensive?",
        "Customer’s Acknowledgment*",
        "Ensure you are filling this section yourself and are aware of what you are placing your signature for.",
        "I acknowledge that Lonpac Insurance Bhd has provided me with a copy of the PDS.",
        "Name: Date: 3",
        "fire, theft or accident",
        "Your liability or your authorised driver’s liability to third",
        "parties for: bodily injury and death; and property loss or damage",
        "Your own death or bodily injury due to a motor accident.",
        "Your liability against claims from passengers in your",
    ]

    for item in spurious_cases:
        assert is_spurious_benefit_line(item) is True, f"Expected '{item}' to be rejected as spurious, but was kept!"


def test_is_spurious_benefit_line_preserves_genuine_riders():
    """Verify that legitimate rider names and add-on descriptions are never rejected."""
    genuine_cases = [
        "Windscreen coverage of RM800.00",
        "Windscreen Damage (RM 1,000.00)",
        "Special Perils / Flood",
        "Inclusion of Special Perils",
        "Passenger Risks – Employees",
        "Passenger Risks (Commercial Veh.)",
        "Transportation Of Damage Vehicle (RM2,500)",
        "Legal Liability To Passengers",
        "Legal Liability Of Passengers",
        "Legal Liability to Pillion",
        "All Drivers",
        "Key Replacement",
        "CART 14 Days",
        "Waiver of Betterment",
        "24-hr Emergency Towing",
    ]

    for item in genuine_cases:
        assert is_spurious_benefit_line(item) is False, f"Expected genuine rider '{item}' to be preserved, but was rejected!"


def test_extract_benefit_lines_isolates_pds_pages():
    """Verify that a multi-page document with Quotation Slip and PDS extracts only genuine quotation riders."""
    mock_concepts = [
        {"concept_id": "c-windscreen", "concept_key": "windscreen", "label": "Windscreen Damage", "aliases": [{"phrase": "windscreen damage", "scope": "global"}]},
        {"concept_id": "c-lltp", "concept_key": "legal-liability-to-passengers", "label": "Legal Liability to Passengers", "aliases": [{"phrase": "legal liability to passengers", "scope": "global"}]},
        {"concept_id": "c-perils", "concept_key": "special-perils", "label": "Special Perils", "aliases": [{"phrase": "special perils", "scope": "global"}]},
    ]

    pages = [
        {
            "page": 1,
            "text": """
MOTOR INSURANCE QUOTATION SLIP
Quotation No: QJV26040103JHR
Name: M. A. TRANSPORTATION SDN BHD
Class of Vehicle: COMMERCIAL VEHICLE (A PERMITS - VEHICLE ONLY)
Type of Cover: COMPREHENSIVE
Make & Model: OTHER COMMERCIAL ALL MODELS (COMMERCIAL)
Vehicle No: -UNREGISTERED-
Sum Insured: RM 295,000.00
Basic Premium: RM 12,036.50
Total Payable: RM 9,759.56
""",
        },
        {
            "page": 2,
            "text": """
NOTE: 1) If estimated figures are provided in this quotation, accurate computations will be provided when available.
www.lonpac.com
""",
        },
        {
            "page": 3,
            "text": """
26/PRN/PDS/VC CP/Jan v-1.0.0
PRODUCT DISCLOSURE SHEET
Dear Customer,
This Product Disclosure Sheet (PDS) provides you with key information on your Commercial Vehicle Comprehensive Insurance.
Know Your Coverage
As an illustration, for RM2,619.93 annually, you will receive the following coverage:
Class of Vehicle: C Permit
Sum Insured / Cover type: RM50,000 / Comprehensive
Manufacturing year: 2020
Vehicle Make & Model: Hino 500 GH8JL1D / 10 tons
Additional Coverage
(This is purchased with an additional premium)
• Windscreen coverage with sum covered: RM 800
• Special Perils / Flood
03-2262 8666
Email us at: customerservice@lonpac.com 1 2
""",
        },
        {
            "page": 4,
            "text": """
26/PRN/PDS/VC CP/Jan v-1.0.0
Know Your Obligations
For this motor insurance policy, you must pay a premium of:
Basic premium RM 2296.60
(-) 0% NCD entitlement
(+) Windscreen coverage of RM800.00 RM 120.00
(+) 8% Service tax RM 193.33
10% or RM 241.66
Total premium payable RM 2,619.93
Customer’s Acknowledgment*
Name: Date: 3
""",
        },
    ]

    lines = extract_benefit_lines(pages, concepts=mock_concepts)
    # Page 1 has 0 riders. Pages 2-4 are note/PDS. Total extracted lines must be 0!
    candidate_lines = [l for l in lines if l.get("line_kind") == "benefit_candidate"]
    assert len(candidate_lines) == 0, f"Expected 0 candidate lines, got: {candidate_lines}"


def test_candidate_finder_ignores_pds_pages_for_optional_covers():
    """Verify that _add_optional_covers does not extract keywords that appear only on PDS pages."""
    results = {}
    page_text = [
        {
            "page": 1,
            "text": "MOTOR INSURANCE QUOTATION SLIP\nSum Insured: RM 295,000.00\nTotal Payable: RM 9,759.56",
        },
        {
            "page": 2,
            "text": "PRODUCT DISCLOSURE SHEET\nAs an illustration:\nAdditional Coverage:\nWindscreen coverage with sum covered: RM 800\nSpecial Perils / Flood",
        },
    ]
    full_text = "\n".join(p["text"] for p in page_text)

    _add_optional_covers(full_text, page_text, results)

    # Optional covers must NOT be added because 'Windscreen' and 'Special Perils' only appear in the PDS
    assert "optional_covers" not in results or not results["optional_covers"]
    assert "benefits_selected" not in results or not results["benefits_selected"]


def test_page_filter_lonpac_6page_pds_vs_covernote_and_tune_schedule():
    """Verify per-page PDS classification trims Lonpac/Tune PDS pages while preserving Cover Notes & active schedules."""
    from app.extraction.page_filter import split_operative_pages

    lonpac_quote_pages = [
        {"page": 1, "text": "MOTOR INSURANCE QUOTATION SLIP\nName : LIM HAU YANG\nPREMIUM COMPUTATION\nTotal Payable\n10,326.19"},
        {"page": 2, "text": "Disclaimer:\nThe premium stated in this document is an indicative and non-binding.\nQUOTATION DATE : 20/11/2026"},
        {"page": 3, "text": "Quotation No : QJV26063148JHR\n26/PRN/PDS/VP02/Sep v-1.1.0\nPRODUCT DISCLOSURE SHEET\nKnow Your Coverage\nAs an illustration, for RM1,659.00 annual premium\nSpecial Perils / Flood"},
        {"page": 4, "text": "26/PRN/PDS/VP02/Sep v-1.1.0\nIMPORTANT INFORMATION YOU SHOULD KNOW\nCan I cancel my policy?"},
        {"page": 5, "text": "26/PRN/PDS/VP02/Sep v-1.1.0\nPRODUCT DISCLOSURE SHEET\nWhat is E-Assist Smart Driver (Personal Accident Insurance)?\nKnow Your Coverage\nSection C: Electric Vehicle (EV) Benefits\nReimbursement of Towing Charges to the nearest Charging Station due to Electric Vehicle Battery depletion"},
        {"page": 6, "text": "26/PRN/PDS/VP02/Sep v-1.1.0\nIMPORTANT INFORMATION YOU SHOULD KNOW\nCan I cancel my policy?"},
    ]
    op_pages, pds_nums = split_operative_pages(lonpac_quote_pages)
    assert [p["page"] for p in op_pages] == [1, 2]
    assert pds_nums == {3, 4, 5, 6}

    lonpac_covernote_pages = [
        {
            "page": 1,
            "text": (
                "COMMERCIAL VEHICLE POLICY\nPolicy Number : J/26/VC00/302097/JHR-22\n"
                "PRODUCT DISCLOSURE SHEET\n"
                "For general information on our products, you can refer to the Product Disclosure Sheet at https://www.lonpac.com/downloads#product-disclosure-sheets"
            ),
        },
        {"page": 2, "text": "THE SCHEDULE\nJADUAL\nClass of Policy: COMMERCIAL VEHICLE (C PERMITS - VEHICLE ONLY)"},
        {"page": 3, "text": "THE SCHEDULE\nEndorsements Attached: 57, 89"},
    ]
    cn_op, cn_pds = split_operative_pages(lonpac_covernote_pages)
    assert [p["page"] for p in cn_op] == [1, 2, 3]
    assert cn_pds == set()

    tune_pages = [
        {"page": 1, "text": "TUNE PROTECT MALAYSIA\nMotor Quotation\nTotal Payable Perlu Dibayar: RM 1,200.00"},
        {"page": 3, "text": "Only The Extensions, Endorsement And / Or Warranties Indicated Below Apply To This Quote.\nSubject to terms and conditions."},
        {"page": 5, "text": "PRODUCT DISCLOSURE SHEET\nKnow Your Coverage\nWhat is this product?\nImportant Information You Should Know"},
    ]
    tune_op, tune_pds = split_operative_pages(tune_pages)
    assert [p["page"] for p in tune_op] == [1, 3]
    assert tune_pds == {5}


def test_lonpac_stacked_benefits_llp_negligent_acts_and_smart_driver():
    """Verify Lonpac stacked Page 1 amounts pair 1-to-1 and 'LLP FOR NEGLIGENT ACTS' maps strictly to LLOP."""
    mock_concepts = [
        {"concept_id": "c-ws", "concept_key": "windscreen", "label": "Windscreen Coverage", "aliases": [{"phrase": "windscreen", "scope": "global"}]},
        {"concept_id": "c-lltp", "concept_key": "legal-liability-to-passengers", "label": "Legal Liability to Passengers", "aliases": [{"phrase": "legal liability to passengers", "scope": "global"}]},
        {"concept_id": "c-llop", "concept_key": "legal-liability-of-passengers", "label": "Legal Liability of Passengers", "aliases": [{"phrase": "legal liability of passengers", "scope": "global"}]},
        {"concept_id": "c-sdpa", "concept_key": "smart-driver-pa", "label": "Smart Driver PA", "aliases": [{"phrase": "e-assist smart driver", "scope": "global"}]},
    ]
    pages = [
        {
            "page": 1,
            "text": (
                "MOTOR INSURANCE QUOTATION SLIP\n"
                "Additional Benefits:\n"
                " - LLP FOR NEGLIGENT ACTS\n"
                " - WINDSCREEN(15.00%) RM15,000.00\n"
                "7.50\n"
                "2,250.00\n"
                "Additional Policy:\n"
                " - E-ASSIST SMART DRIVER - PLAN 2 (Unlimited Towing)\n"
                "138.00\n"
                "Gross Premium\n"
                "9,552.03\n"
            ),
        }
    ]
    lines = extract_benefit_lines(pages, concepts=mock_concepts)
    assert not any("7.50 2,250.00" in (l.get("raw_label") or "") for l in lines)

    llop_lines = [l for l in lines if "negligent" in (l.get("raw_label") or "").lower()]
    assert len(llop_lines) == 1
    assert llop_lines[0]["premium_cost"] == "7.50"
    assert [m["concept_key"] for m in llop_lines[0]["candidate_mappings"]] == ["legal-liability-of-passengers"]

    ws_lines = [l for l in lines if "windscreen" in (l.get("raw_label") or "").lower()]
    assert len(ws_lines) == 1
    assert ws_lines[0]["coverage_limit"] == "15000.00"
    assert ws_lines[0]["premium_cost"] == "2250.00"

    pa_lines = [l for l in lines if "e-assist" in (l.get("raw_label") or "").lower()]
    assert len(pa_lines) == 1
    assert pa_lines[0]["premium_cost"] == "138.00"
    assert pa_lines[0]["extracted_value"]["unlimited"] is True


def test_lonpac_comparison_ignores_historical_pds_leakage():
    """Verify comparison benefits extraction ignores Page 3-6 PDS text even on stored historical records."""
    from types import SimpleNamespace
    from app.services.marketing_comparison.benefits_extractor import _resolve_comparison_benefits

    p1 = (
        "MOTOR INSURANCE QUOTATION SLIP\n"
        "Name : LIM HAU YANG\n"
        "Make & Model : BMW M4\n"
        "Sum Insured : RM442,000.00\n"
        "Additional Benefits:\n"
        " - LLP FOR NEGLIGENT ACTS\n"
        "7.50\n"
        "Gross Premium\n"
        "9,552.03\n"
    )
    p3 = (
        "26/PRN/PDS/VP02/Sep v-1.1.0\n"
        "PRODUCT DISCLOSURE SHEET\n"
        "Know Your Coverage\n"
        "As an illustration, for RM1,659.00 annual premium\n"
        "• Special Perils / Flood\n"
    )
    p5 = (
        "26/PRN/PDS/VP02/Sep v-1.1.0\n"
        "PRODUCT DISCLOSURE SHEET\n"
        "What is E-Assist Smart Driver?\n"
        "Know Your Coverage\n"
        "Reimbursement of Towing Charges due to Electric Vehicle Battery depletion\n"
    )
    ext_rec = SimpleNamespace(
        raw_text="\n".join([p1, p3, p5]),
        ocr_text="",
        page_text=[{"page": 1, "text": p1}, {"page": 3, "text": p3}, {"page": 5, "text": p5}],
        benefit_lines=[],
        words=[],
        blocks=[],
        candidates={},
    )
    session = SimpleNamespace(
        draft_id=None,
        uploaded_file_id="f-lonpac-1",
        company_id=None,
        detected_company="Lonpac Insurance",
        uploaded_file=SimpleNamespace(extraction_record=ext_rec),
    )

    class _DummyDB:
        def scalars(self, *args, **kwargs):
            return SimpleNamespace(all=lambda: [])

        def get(self, *args, **kwargs):
            return None

    res = _resolve_comparison_benefits(
        _DummyDB(),
        session,
        None,
        {"insurance_company": "Lonpac Insurance"},
        prefetched={
            "all_selections_by_draft": {},
            "selections_by_draft": {},
            "concepts_by_id": {},
            "ext_lines_by_file": {},
            "ext_records_by_file": {"f-lonpac-1": ext_rec},
            "companies_by_id": {},
            "conditions_by_company": {},
            "towing_by_rev": {},
            "bundles_by_company": {},
            "catalog_rev_names": {},
        },
    )
    assert res["special_perils"] is None
    assert "ev_battery" not in (res.get("extra_addons") or {})
    assert "LLOP" in res["canonical_perils"]
    assert "LLP" not in res["canonical_perils"]

