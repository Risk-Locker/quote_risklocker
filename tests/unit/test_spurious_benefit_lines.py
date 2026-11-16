"""Unit tests for spurious benefit line detection and arithmetic subtotal filtering."""

import pytest
from app.extraction.benefit_lines import is_spurious_benefit_line


def test_spurious_benefit_line_rejects_arithmetic_formulas_and_numbers():
    # Mathematical additions, subtotals, and expression lines from quotation PDFs
    assert is_spurious_benefit_line("750.00 + 1,049.35 +") is True
    assert is_spurious_benefit_line("+ 750.00 + 1,049.35") is True
    assert is_spurious_benefit_line("RM 750.00") is True
    assert is_spurious_benefit_line("750.00") is True
    assert is_spurious_benefit_line("- 2,605.61 -") is True
    assert is_spurious_benefit_line("1,049.35") is True
    assert is_spurious_benefit_line("100%") is True
    assert is_spurious_benefit_line("+ 41.85 + 7.50") is True


def test_spurious_benefit_line_preserves_genuine_insurance_benefits():
    # Genuine benefits with words/descriptions
    assert is_spurious_benefit_line("ENHANCED WINDSCREEN COVER") is False
    assert is_spurious_benefit_line("WAIVER OF BETTERMENT") is False
    assert is_spurious_benefit_line("LEGAL LIABILITY TO PASSENGERS") is False
    assert is_spurious_benefit_line("LEGAL LIABILITY OF PASSENGERS") is False
    assert is_spurious_benefit_line("ALL DRIVERS") is False
    assert is_spurious_benefit_line("CONVULSION OF NATURE") is False
    assert is_spurious_benefit_line("REPAIR WARRANTY 12 MONTHS") is False
    assert is_spurious_benefit_line("UNLIMITED TOWING") is False
    assert is_spurious_benefit_line("24-HOUR AUTO ASSIST") is False
    assert is_spurious_benefit_line("Cart 14 Days") is False
    assert is_spurious_benefit_line("Windscreen Coverage (RM 5,000.00)") is False
    assert is_spurious_benefit_line("Endorsement 57 - Inclusion of Special Perils") is False
