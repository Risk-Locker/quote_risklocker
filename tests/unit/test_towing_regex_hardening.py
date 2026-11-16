"""Unit tests asserting hardening of STMB PA Plus towing regex and fallback towing in towing_evaluator."""

from __future__ import annotations

import pytest
from app.services.marketing_comparison.towing_evaluator import resolve_insurer_towing_limit


def test_stmb_pa_plus_digits_do_not_falsely_trigger_unlimited():
    # Defect F-05 reproducer: text contains digits '4', '3', '2', '1' in year, price, or plate
    # but does NOT specify Plan 4 / Pelan 4.
    text_with_digits = (
        "Syarikat Takaful Malaysia Am Berhad Quotation 2024\n"
        "Vehicle Plate: WXY 1234\n"
        "Motor PA Plus Add-on Selected: Yes\n"
        "Gross Premium: RM 450.00\n"
        "NCD: 25%\n"
    )
    # Must NOT evaluate to "Unlimited" just because '4' is present in the text!
    result = resolve_insurer_towing_limit(company_name="Takaful Malaysia", combined_text=text_with_digits)
    assert result != "Unlimited", f"Expected non-unlimited towing, got '{result}' due to naive '4' in text matching!"
    assert result == "100 km"


def test_stmb_pa_plus_explicit_plans_resolve_correctly():
    comp = "Takaful Malaysia"

    # Plan 4 -> Unlimited
    res_p4 = resolve_insurer_towing_limit(company_name=comp, combined_text="Takaful Malaysia Motor PA Plus Pelan 4")
    assert res_p4 == "Unlimited"

    # Plan 3 -> 300 km
    res_p3 = resolve_insurer_towing_limit(company_name=comp, combined_text="Takaful Malaysia Motor PA Plus Pelan 3")
    assert res_p3 == "300 km"

    # Plan 2 -> 200 km
    res_p2 = resolve_insurer_towing_limit(company_name=comp, combined_text="Takaful Malaysia Motor PA Plus Plan 2")
    assert res_p2 == "200 km"

    # Plan 1 -> 100 km
    res_p1 = resolve_insurer_towing_limit(company_name=comp, combined_text="Takaful Malaysia Motor PA Plus Plan 1")
    assert res_p1 == "100 km"

    # Standard complimentary towing without PA Plus -> 50 km
    res_std = resolve_insurer_towing_limit(company_name=comp, combined_text="Takaful Malaysia Standard Comprehensive")
    assert res_std == "50 km"


def test_unknown_insurer_does_not_default_to_unlimited():
    # Defect F-05: Unlisted unknown insurers must NOT default to "Unlimited"
    comp = "Generic Unknown Takaful"
    text = "Comprehensive Motor Policy Quotation with standard benefits"
    res = resolve_insurer_towing_limit(company_name=comp, combined_text=text)
    assert res != "Unlimited", f"Unknown insurer falsely received Unlimited towing: {res}"
    assert res in ("50 km", "RM 200")
