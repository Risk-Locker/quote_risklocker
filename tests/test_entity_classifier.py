"""Unit tests for entity classification (Individual vs Company)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.extraction.entity_classifier import classify_client_entity, is_business_registration, is_corporate_name


@pytest.mark.parametrize(
    "name, expected_company",
    [
        ("PL INKJET SDN. BHD.", True),
        ("PL INKJET SDN BHD", True),
        ("PL INKJET SDNBHD", True),
        ("BERJAYA SOMPO INSURANCE BHD", True),
        ("MEWAH TRADING", True),
        ("KEDAI BUKU ALI ENTERPRISE", True),
        ("KOPERASI PEGAWAI KERAJAAN", True),
        ("ABC LOGISTICS SERVICES", True),
        ("GLOBAL TECH VENTURES PLT", True),
        ("TOP GLOVE CORP", True),
        ("SENG HUP MOTORS", True),
        ("PERUSAHAAN OTOMOBIL KEBANGSAAN", True),
        ("AHMAD BIN ALI", False),
        ("TAN AH KOW", False),
        ("MUTHUSAMY A/L VELLASAMY", False),
        ("SITI NURHALIZA BINTI TARUDIN", False),
        ("JOHN DOE", False),
        ("YEO JING SHY", False),
    ],
)
def test_is_corporate_name(name: str, expected_company: bool):
    assert is_corporate_name(name) == expected_company


@pytest.mark.parametrize(
    "doc_no, expected_brn",
    [
        ("123456-X", True),
        ("001234567-T", True),
        ("201901012345", True),
        ("LLP0012345-LGN", True),
        ("ROC: 987654-A", True),
        ("-".join(("850101", "10", "5555")), False),
        ("991231145678", False),
    ],
)
def test_is_business_registration(doc_no: str, expected_brn: bool):
    assert is_business_registration(doc_no) == expected_brn


def test_classify_client_entity():
    # Corporate name -> CompanyCar
    entity, vtype = classify_client_entity("PL INKJET SDN. BHD.", current_vehicle_type="Car")
    assert entity == "Company"
    assert vtype == "CompanyCar"

    # Corporate name with bike -> CompanyMotorcycle
    entity, vtype = classify_client_entity("PL INKJET SDN. BHD.", current_vehicle_type="Motorcycle")
    assert entity == "Company"
    assert vtype == "CompanyMotorcycle"

    # Personal name -> Car (Private)
    entity, vtype = classify_client_entity("YEO JING SHY", ic_or_brn="-".join(("950512", "01", "5555")), current_vehicle_type="Car")
    assert entity == "Private"
    assert vtype == "Car"

    # Ambiguous name with BRN -> Company
    entity, vtype = classify_client_entity("LIM BROTHERS", ic_or_brn="202001098765", current_vehicle_type="Car")
    assert entity == "Company"
    assert vtype == "CompanyCar"

    # AI hints Company with no personal NRIC -> Company
    entity, vtype = classify_client_entity("DYNAMIC SOLUTIONS", ai_client_type="Company", current_vehicle_type="Car")
    assert entity == "Company"
    assert vtype == "CompanyCar"

    # Non-Saloon Car model for Company owner -> Company, NonSaloonCar
    entity, vtype = classify_client_entity(
        "PL INKJET SDN. BHD.",
        current_vehicle_type="Car",
        car_model="PERODUA ALZA 1500 EZI(AUTO)",
    )
    assert entity == "Company"
    assert vtype == "NonSaloonCar"

    # Non-Saloon Car model for Private owner -> Private, NonSaloonCar
    entity, vtype = classify_client_entity(
        "YEO JING SHY",
        ic_or_brn="-".join(("950512", "01", "5555")),
        current_vehicle_type="Car",
        car_model="HONDA CR-V 2.0 (AUTO)",
    )
    assert entity == "Private"
    assert vtype == "NonSaloonCar"


@pytest.mark.parametrize(
    "model, expected_non_saloon",
    [
        ("PERODUA ALZA 1500 EZI(AUTO)", True),
        ("PROTON EXORA 1.6 BOLD", True),
        ("TOYOTA INNOVA 2.0G", True),
        ("TOYOTA VELLFIRE 2.5", True),
        ("HONDA CR-V 2.0 I-VTEC", True),
        ("HONDA HR-V 1.8", True),
        ("PROTON X50 1.5 TGDI", True),
        ("PROTON X70 1.8 TGDI", True),
        ("PERODUA ATIVA 1.0 TURBO", True),
        ("PERODUA ARUZ 1.5", True),
        ("TOYOTA HILUX 2.4 DOUBLE CAB", True),
        ("FORD RANGER 2.0 BI-TURBO", True),
        ("ISUZU D-MAX 1.9 DIESEL", True),
        ("TOYOTA HIACE 2.5 PANEL VAN", True),
        # Saloon / Hatchback models should be False
        ("PERODUA MYVI 1.5 H", False),
        ("PERODUA BEZZA 1.3 X", False),
        ("PERODUA AXIA 1.0 G", False),
        ("PROTON SAGA 1.3 PREMIUM", False),
        ("PROTON PERSONA 1.6", False),
        ("TOYOTA VIOS 1.5 G", False),
        ("HONDA CITY 1.5 RS", False),
        ("HONDA CIVIC 1.5 TURBO", False),
    ],
)
def test_is_non_saloon_model(model: str, expected_non_saloon: bool):
    from app.extraction.entity_classifier import is_non_saloon_model

    assert is_non_saloon_model(model) == expected_non_saloon


def test_lonpac_cc_watts_tonnage_and_seating_capacity_never_false_ev():
    """Verify Lonpac C.C / Watts, Tonnage, and Seating Capacity never misclassify ICE/Commercial vehicles as EV."""
    from app.extraction.candidate_finder import find_candidates
    from app.extraction.draft_mapper import build_draft

    xpander_text = (
        "MOTOR INSURANCE QUOTATION SLIP\n"
        "Name :\nBETTY HEE WAI CHEN\n"
        f"NRIC :\n(New) {'-'.join(('880202', '10', '9999'))}\n"
        "Class of Vehicle :\nPRIVATE CAR SECURE\n"
        "Make & Model :\nMITSUBISHI XPANDER PLUS MY24\n"
        "Vehicle No. :\nVNE 8178\n"
        "C.C / Watts :\n1499\n"
        "Year of Manufacture :\n2024\n"
        "Seating Capacity :\n7\n"
        "Sum Insured :\nRM90,000.00\n"
        "Total Payable\n1,961.35\n"
        "2026\nWhat is Private Car\n"
    )
    xp_cands = find_candidates(xpander_text, [{"page": 1, "text": xpander_text}], source_filename="20261008_VNE8178_Quotation_Lonpac.pdf")
    xp_fields, _, _ = build_draft(xp_cands, raw_text=xpander_text)
    assert xp_fields["engine_cc"]["value"] == "1499 CC"
    assert xp_fields["vehicle_type"]["value"] in {"Car", "NonSaloonCar"}
    assert "EV" not in xp_fields["vehicle_type"]["value"]

    urvan_text = (
        "MOTOR INSURANCE QUOTATION SLIP\n"
        "Name :\nTRIWOOD COVERINGS SDN. BHD.\n"
        "Bus Reg. No :\n(Old) 202301047521\n"
        "Class of Vehicle :\nCOMMERCIAL VEHICLE (C PERMITS - VEHICLE ONLY)\n"
        "Make & Model :\nNISSAN URVAN\n"
        "Vehicle No. :\nBKP 3396\n"
        "Tonnage :\n1.5\n"
        "Year of Manufacture :\n2010\n"
        "Seating Capacity :\n3\n"
        "Sum Insured :\nRM30,000.00\n"
        "Total Payable\n1,474.03\n"
    )
    urv_cands = find_candidates(urvan_text, [{"page": 1, "text": urvan_text}], source_filename="20261027_BKP3396_Quotation_Lonpac_REF.pdf")
    urv_fields, _, _ = build_draft(urv_cands, raw_text=urvan_text)
    assert urv_fields["engine_cc"]["value"] == "1.5 TON"
    assert urv_fields["vehicle_type"]["value"] == "Lorry"

    ev_text = (
        "MOTOR INSURANCE QUOTATION SLIP\n"
        "Name :\nTAN WEI MING\n"
        f"NRIC :\n(New) {'-'.join(('900101', '01', '1234'))}\n"
        "Class of Vehicle :\nPRIVATE CAR SECURE\n"
        "Make & Model :\nBYD ATTO 3 EXTENDED RANGE\n"
        "Vehicle No. :\nJXY 8888\n"
        "C.C / Watts :\n150000\n"
        "Year of Manufacture :\n2025\n"
        "Seating Capacity :\n5\n"
        "Sum Insured :\nRM120,000.00\n"
        "Total Payable\n3,200.00\n"
    )
    ev_cands = find_candidates(ev_text, [{"page": 1, "text": ev_text}], source_filename="20261125_JXY8888_Quotation_Lonpac.pdf")
    ev_fields, _, _ = build_draft(ev_cands, raw_text=ev_text)
    assert ev_fields["engine_cc"]["value"] == "150 kW"
    assert ev_fields["vehicle_type"]["value"] == "EVNonSaloonCar"

