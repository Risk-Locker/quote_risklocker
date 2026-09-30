"""Hermetic unit tests for identity_normalization_service."""

import pytest
from app.services.identity_normalization_service import (
    is_corporate_entity,
    normalize_canonical_name,
    normalize_government_id,
)


def test_normalize_government_id_nric():
    # Hyphenated NRIC
    norm, id_type = normalize_government_id("901231-10-5432")
    assert norm == "901231105432"
    assert id_type == "nric"

    # Spaced / unhyphenated NRIC
    norm2, id_type2 = normalize_government_id(" 950515 14 6789 ")
    assert norm2 == "950515146789"
    assert id_type2 == "nric"


def test_normalize_government_id_new_ssm():
    # 12-digit SSM company registration starting 2019+ with entity code 01..06
    norm, id_type = normalize_government_id("201901012345")
    assert norm == "201901012345"
    assert id_type == "brn_new"


def test_normalize_government_id_old_ssm():
    # Old SSM format: 5-9 digits followed by a letter
    norm, id_type = normalize_government_id("123456-X")
    assert norm == "123456X"
    assert id_type == "brn_old"

    norm2, id_type2 = normalize_government_id("001234567-T")
    assert norm2 == "001234567T"
    assert id_type2 == "brn_old"


def test_normalize_government_id_passport():
    # Passport starts with a letter followed by alphanumeric
    norm, id_type = normalize_government_id("A12345678")
    assert norm == "A12345678"
    assert id_type == "passport"

    norm2, id_type2 = normalize_government_id("E 87654321")
    assert norm2 == "E87654321"
    assert id_type2 == "passport"


def test_normalize_government_id_llp():
    # LLP format
    norm, id_type = normalize_government_id("LLP0012345-LGN")
    assert norm == "LLP0012345LGN"
    assert id_type == "llp"


def test_normalize_canonical_company_name():
    # The exact issue raised by the user:
    # "PL INKJET sdn bhd" vs "PL Inkjet SDN BHD." vs "PL INKJET SDN. BHD."
    name1 = normalize_canonical_name("PL INKJET sdn bhd")
    name2 = normalize_canonical_name("PL Inkjet SDN BHD.")
    name3 = normalize_canonical_name("PL INKJET SDN. BHD.")
    name4 = normalize_canonical_name("pl inkjet sendirian berhad")

    assert name1 == "PL INKJET SDN BHD"
    assert name2 == "PL INKJET SDN BHD"
    assert name3 == "PL INKJET SDN BHD"
    assert name4 == "PL INKJET SDN BHD"

    # All 4 variants evaluate to the exact same canonical string!
    assert name1 == name2 == name3 == name4


def test_normalize_individual_name():
    name1 = normalize_canonical_name("Tan Ah Kow (Mr)")
    assert name1 == "TAN AH KOW MR"

    name2 = normalize_canonical_name("  muhammad bin abdullah  ")
    assert name2 == "MUHAMMAD BIN ABDULLAH"


def test_is_corporate_entity():
    assert is_corporate_entity("PL INKJET SDN BHD", "brn_old") is True
    assert is_corporate_entity("MAJU JAYA ENTERPRISE", "brn_new") is True
    assert is_corporate_entity("TAN AH KOW", "nric") is False
    assert is_corporate_entity("JOHN DOE", "passport") is False
    assert is_corporate_entity("ABC LOGISTICS SERVICES", "unknown") is True
