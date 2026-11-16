"""Unit tests for the Motor Quotation Extraction Referee & Fact-Checking Gate."""

import pytest
from app.extraction.referee import audit_and_reconcile_draft
from app.services.vehicle_simplifier_service import clean_vehicle_tokens_deterministic


def test_referee_detects_company_and_lorry_contradiction():
    # Scenario: An underwriter quotation for a commercial lorry owned by SDN BHD,
    # but the AI extracted 'Car' or 'Private Car Comprehensive'
    fields = {
        "customer_name": {"value": "CHIN YING TRADING SDN BHD", "status": "ready"},
        "car_brand": {"value": "DAIHATSU", "status": "ready"},
        "car_model": {"value": "Daihatsu Delta V116ha", "status": "ready"},
        "vehicle_type": {"value": "Car", "status": "ready"},  # Erroneous 'Car'
        "product_name": {"value": "Private Car Comprehensive", "status": "ready"},  # Contradiction!
        "engine_cc": {"value": "3000 KG", "status": "ready"},
        "client_type": {"value": "Private", "status": "ready"},  # Erroneous 'Private'
    }
    raw_text = (
        "QUOTATION Liberty General Insurance Berhad 197801007153 (44191-P) "
        "Insured Name Issued Date Vehicle Class Capacity Vehicle No Trailer No Named Driver "
        "CHIN YING TRADING SDN BHD 'C' PERMIT GOODS VEHICLE 3000 KG DAIHATSU DELTA V116HA"
    )

    reconciled, notices = audit_and_reconcile_draft(fields, raw_text=raw_text)

    # 1. Company entity enforcement
    assert reconciled["client_type"]["value"] == "Company"

    # 2. Lorry / Commercial vehicle enforcement
    assert reconciled["vehicle_type"]["value"] == "Lorry"

    # 3. Product name contradiction purge
    assert "Private Car" not in reconciled["product_name"]["value"]
    assert "Commercial Vehicle" in reconciled["product_name"]["value"] or "Goods Vehicle" in reconciled["product_name"]["value"]

    # 4. Audit notices generated
    assert any("Referee Fact-Check" in n for n in notices)


def test_referee_preserves_legitimate_private_car():
    # Legitimate private individual driving a Honda Civic
    fields = {
        "customer_name": {"value": "TAN AH KOW", "status": "ready"},
        "ic_or_brn": {"value": "900101-01-5555", "status": "ready"},
        "car_brand": {"value": "HONDA", "status": "ready"},
        "car_model": {"value": "Civic 1.5 TC-P", "status": "ready"},
        "vehicle_type": {"value": "Car", "status": "ready"},
        "product_name": {"value": "Private Car Comprehensive", "status": "ready"},
        "engine_cc": {"value": "1498 CC", "status": "ready"},
    }
    raw_text = "Quotation for TAN AH KOW Honda Civic 1.5 TC-P Private Car Comprehensive"

    reconciled, notices = audit_and_reconcile_draft(fields, raw_text=raw_text)

    assert reconciled["client_type"]["value"] == "Private"
    assert reconciled["vehicle_type"]["value"] == "Car"
    assert reconciled["product_name"]["value"] == "Private Car Comprehensive"
    assert len(notices) == 0


def test_vehicle_name_simplifier_preserves_alphanumeric_codes():
    # Daihatsu Delta V116HA should NOT be lowercased to V116ha
    brand, model, combined = clean_vehicle_tokens_deterministic("DAIHATSU", "DAIHATSU DELTA V116HA")
    assert "V116-HA" in combined or "V116HA" in combined
    assert "V116ha" not in combined

    # Proton Saga BLM should retain BLM uppercase
    brand2, model2, combined2 = clean_vehicle_tokens_deterministic("PROTON", "PROTON SAGA BLM 1.3")
    assert "BLM" in combined2
    assert "Blm" not in combined2
