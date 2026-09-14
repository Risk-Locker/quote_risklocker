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
