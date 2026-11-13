"""100% hermetic unit tests for the Malaysian Motor Insurance Towing Resolver.

Validates exact entitlements for:
  - QBE (RM500 standard vs Unlimited with Passenger Protector N4)
  - STMB / Takaful Malaysia (50km base; Motor PA Plus P1=100km, P2=200km, P3=300km, P4=Unlimited)
  - Etiqa (200km base vs Unlimited with OTO 360)
  - Lonpac (RM400 base; E-Assist Smart Driver P1=RM1,000, P2/EV=Unlimited)
  - Berjaya Sompo (Rakan Auto/Standard=RM300 vs SOMPO Motor/MotorSafe=Unlimited)
  - Tune Protect (200km base vs Unlimited with Motor Easy / AutoBuddy / Motor Shield)
  - AmAssurance / Amgen (auto365 Lite=RM200 or 150km with breakdown, Plus=100km, Premier=365km)
  - Kurnia (RM200 base vs Unlimited with Auto Assist Plus/Premier)
"""

from __future__ import annotations

import pytest

from app.domain.motor.towing_matrix import resolve_towing_entitlement, TowingEntitlement


@pytest.mark.parametrize(
    ("company", "product", "rider", "text", "expected"),
    [
        # QBE
        ("QBE", None, None, "", "RM500"),
        ("QBE Insurance", "Comprehensive", "Driver Protector", "N4 Unlimited Auto Assistance", "Unlimited"),
        ("QBE", None, "Passenger Protector", "Unlimited Auto Assistance", "Unlimited"),

        # STMB / Takaful Malaysia
        ("STMB", None, None, "", "50km"),
        ("Takaful Malaysia", "Motor Takaful", None, "", "50km"),
        ("STMB", None, "Motor PA Plus - Plan 1", "", "100km"),
        ("STMB", None, "Motor PA Plus - Plan 2", "", "200km"),
        ("STMB", None, "Motor PA Plus - Plan 3", "", "300km"),
        ("STMB", None, "Motor PA Plus - Plan 4", "", "Unlimited"),
        ("STMB", None, "Motor PA Plus", "Plan 1 endorsement", "100km"),
        ("STMB", None, "Motor PA Plus", "Plan 4 endorsement", "Unlimited"),

        # Etiqa
        ("Etiqa", None, None, "", "200km"),
        ("Etiqa General Insurance", "Motor", "OTO 360", "", "Unlimited"),
        ("Etiqa", None, None, "Includes OTO 360 personal accident", "Unlimited"),

        # Lonpac
        ("Lonpac", None, None, "", "RM400"),
        ("Lonpac Insurance Bhd", "Comprehensive", "E-Assist Smart Driver - Plan 1", "", "RM1,000"),
        ("Lonpac", None, "E-Assist Smart Driver - Plan 2", "", "Unlimited"),
        ("Lonpac", None, "E-Assist EV Plan", "", "Unlimited"),

        # Berjaya Sompo
        ("Berjaya Sompo", "Rakan Auto", None, "", "RM300"),
        ("Berjaya Sompo", "Standard", None, "", "RM300"),
        ("Berjaya Sompo", "SOMPO Motor", None, "", "Unlimited"),
        ("Berjaya Sompo", "MotorSafe", None, "", "Unlimited"),

        # Tune Protect
        ("Tune Protect", None, None, "", "200km"),
        ("Tune Protect", "Motor Easy", None, "", "Unlimited"),
        ("Tune Protect", None, "AutoBuddy", "", "Unlimited"),
        ("Tune Protect", None, "Motor Shield", "", "Unlimited"),

        # AmAssurance (Amgen)
        ("AmAssurance", "auto365 Lite", None, "", "RM200"),
        ("AmAssurance", "auto365 Lite", "Breakdown Towing Assistance", "", "150km"),
        ("AmAssurance", "auto365 Plus", None, "", "100km"),
        ("AmAssurance", "auto365 Premier", None, "", "365km"),
        ("Amgen", "Auto365 Comprehensive Premier", None, "", "365km"),

        # Kurnia
        ("Kurnia", None, None, "", "RM200"),
        ("Kurnia Insurans", None, "Kurnia Auto Assist Plus", "", "Unlimited"),
        ("Kurnia Insurans", None, "Auto Assist Premier", "", "Unlimited"),
    ],
)
def test_resolve_towing_entitlement_canonical_matrix(company, product, rider, text, expected):
    entitlement = resolve_towing_entitlement(
        company_name=company,
        product_name=product,
        package_or_rider=rider,
        raw_document_text=text,
    )
    assert entitlement.formatted.replace(" ", "") == expected.replace(" ", "")
    assert entitlement.limit_type in {"RM", "km", "Unlimited"}


def test_towing_entitlement_edge_cases():
    # Empty inputs default safely
    res_empty = resolve_towing_entitlement(company_name="")
    assert res_empty.formatted == "Unlimited"  # safe default

    # Case-insensitivity
    res_case = resolve_towing_entitlement(company_name="stmb", package_or_rider="motor pa plus -- plan 2")
    assert res_case.formatted.replace(" ", "") == "200km"
    assert res_case.km_value == 200

    # Explicit KM extraction from document text if unlisted company
    res_custom = resolve_towing_entitlement(company_name="Allianz", raw_document_text="Free roadside towing up to 150 km")
    assert res_custom.formatted.replace(" ", "") == "150km"
    assert res_custom.km_value == 150

