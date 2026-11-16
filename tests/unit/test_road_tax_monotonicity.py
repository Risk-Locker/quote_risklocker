"""Unit tests asserting JPJ Road Tax monotonicity and schedule parity across 2500cc-3000cc boundaries."""

from __future__ import annotations

import pytest
from app.services.road_tax_engine import calculate_road_tax


def test_west_malaysia_private_car_monotonicity_and_continuity():
    # 2500 cc: RM 380 + (500 * 1.0) = RM 880.00
    tax_2500 = calculate_road_tax(2500, "Car", "Individual", "West Malaysia")
    assert tax_2500 == 880.0, f"Expected 880.0 at 2500cc, got {tax_2500}"

    # 2501 cc: RM 880 + (1 * 2.50) = RM 882.50
    tax_2501 = calculate_road_tax(2501, "Car", "Individual", "West Malaysia")
    assert tax_2501 == 882.50, f"Expected 882.50 at 2501cc (monotonically increasing), got {tax_2501}"

    # Strict monotonicity check: increasing CC must strictly increase road tax
    assert tax_2501 > tax_2500, f"Discontinuity defect: tax(2501)={tax_2501} is not > tax(2500)={tax_2500}"

    # 3000 cc: RM 880 + (500 * 2.50) = RM 2130.00
    tax_3000 = calculate_road_tax(3000, "Car", "Individual", "West Malaysia")
    assert tax_3000 == 2130.0, f"Expected 2130.0 at 3000cc, got {tax_3000}"

    # 3001 cc: RM 2130 + (1 * 4.50) = RM 2134.50
    tax_3001 = calculate_road_tax(3001, "Car", "Individual", "West Malaysia")
    assert tax_3001 == 2134.50, f"Expected 2134.50 at 3001cc, got {tax_3001}"
    assert tax_3001 > tax_3000


def test_labuan_private_car_monotonicity_and_continuity():
    # 2500 cc: RM 190 + (500 * 0.50) = RM 440.00
    tax_2500 = calculate_road_tax(2500, "Car", "Individual", "Labuan")
    assert tax_2500 == 440.0, f"Expected 440.0 at 2500cc in Labuan, got {tax_2500}"

    # 2501 cc: RM 440 + (1 * 1.25) = RM 441.25
    tax_2501 = calculate_road_tax(2501, "Car", "Individual", "Labuan")
    assert tax_2501 == 441.25, f"Expected 441.25 at 2501cc in Labuan, got {tax_2501}"

    # Strict monotonicity check
    assert tax_2501 > tax_2500, f"Discontinuity defect in Labuan: tax(2501)={tax_2501} is not > tax(2500)={tax_2500}"

    # 3000 cc: RM 440 + (500 * 1.25) = RM 1065.00
    tax_3000 = calculate_road_tax(3000, "Car", "Individual", "Labuan")
    assert tax_3000 == 1065.0, f"Expected 1065.0 at 3000cc in Labuan, got {tax_3000}"
