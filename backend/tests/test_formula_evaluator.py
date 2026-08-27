import pytest
from app.services.formula_evaluator import (
    extract_evaluation_context,
    evaluate_formula,
    evaluate_cart_tariff
)

def test_safe_math_evaluation():
    context = {"vehicle_sum_insured": 50000.0, "total_seats": 5.0}
    
    assert evaluate_formula("0.0025 * vehicle_sum_insured", context) == 125.0
    assert evaluate_formula("5.00 * (total_seats - 1)", context) == 20.0
    assert evaluate_formula("min(0.05 * vehicle_sum_insured, 5000.00)", context) == 2500.0
    assert evaluate_formula("max(10.0, 5.0)", context) == 10.0
    assert evaluate_formula("round(10.556, 2)", context) == 10.56

def test_symbolic_tokens():
    assert evaluate_formula("statutory_unlimited", {}) == "Statutory Unlimited"
    assert evaluate_formula("100%_waiver", {}) == "100% Waiver"
    assert evaluate_formula("unlimited", {}) == "Unlimited"

def test_extract_evaluation_context():
    draft = {
        "vehicle_sum_insured": "RM 60,000",
        "total_seats": "7",
        "base_tp_premium": "165.50",
        "windscreen_sum_insured": "RM 1,200",
    }
    
    context = extract_evaluation_context(draft)
    assert context["vehicle_sum_insured"] == 60000.0
    assert context["total_seats"] == 7.0
    assert context["base_tp_premium"] == 165.5
    assert context["windscreen_sum_insured"] == 1200.0
    assert context["period_months"] == 12.0 # default

def test_extract_evaluation_context_fallbacks():
    draft = {
        "market_value": "45000", # fallback for sum_insured
        "seating_capacity": "2", # fallback for total_seats
        "basic_premium": "RM 200", # fallback for base_tp
    }
    
    context = extract_evaluation_context(draft)
    assert context["vehicle_sum_insured"] == 45000.0
    assert context["total_seats"] == 2.0
    assert context["base_tp_premium"] == 200.0
    assert context["windscreen_sum_insured"] == 1000.0 # default

def test_evaluate_cart_tariff():
    context = {"rate": 200.0, "days": 7.0}
    assert evaluate_formula("evaluate_cart_tariff(rate, days)", context) == 1400.0
