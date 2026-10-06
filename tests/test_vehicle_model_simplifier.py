"""Hermetic tests for AI vehicle model simplifier and noise cleaner."""

import pytest
from app.services.vehicle_simplifier_service import (
    clean_vehicle_tokens_deterministic,
    simplify_vehicle_name_with_ai,
)


def test_deterministic_cleaning_removes_transmission_chassis_and_body_noise():
    raw_brand = "MERCEDES-BENZ"
    raw_model = "S 400 L HYBRID (CKD) MY14 W222 4D SEDAN 7 SP AUTOMATIC"
    
    brand, model, combined = clean_vehicle_tokens_deterministic(raw_brand, raw_model)
    assert brand == "Mercedes-Benz"
    assert "CKD" not in model
    assert "W222" not in model
    assert "4D" not in model
    assert "SEDAN" not in model
    assert "AUTOMATIC" not in model
    assert "S 400 L Hybrid" in combined


def test_deterministic_cleaning_preserves_hyphenated_trim_codes():
    raw_brand = "HONDA"
    raw_model = "CIVIC 1.5 TC-P (A) 2018 SEDAN 4-DOOR"
    
    brand, model, combined = clean_vehicle_tokens_deterministic(raw_brand, raw_model)
    assert brand == "Honda"
    assert "TC-P" in model or "Tc-P" in model or "Tc-p" in model
    assert "4-DOOR" not in model
    assert "SEDAN" not in model


def test_deterministic_cleaning_handles_bmw_and_mazda_variants():
    brand, model, combined = clean_vehicle_tokens_deterministic("BMW", "320i M-SPORT LCI F30 (A)")
    assert brand == "BMW"
    assert "M-Sport" in combined or "M-sport" in combined
    assert "F30" not in combined

    brand_m, model_m, combined_m = clean_vehicle_tokens_deterministic("MAZDA", "CX-5 2.0 2WD GL (A) 5-DOOR SUV")
    assert brand_m == "Mazda"
    assert "CX-5" in combined_m
    assert "SUV" not in combined_m


def test_simplify_vehicle_name_with_ai_fallback_on_empty_api_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    brand, model, combined = simplify_vehicle_name_with_ai(
        "MERCEDES-BENZ",
        "S 400 L HYBRID (CKD) MY14 W222 4D SEDAN 7 SP AUTOMATIC"
    )
    assert brand == "Mercedes-Benz"
    assert "S 400 L" in combined
