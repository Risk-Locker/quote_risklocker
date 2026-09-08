"""Regression tests for road-tax service edge cases."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_PROVIDER": "supabase_postgres",
        "DATABASE_URL": "postgresql://postgres:password@db.test.supabase.co:5432/postgres",
        "AUTH_HASH_SECRET": "test-auth-hash-secret-that-is-long-enough",
        "STORAGE_DRIVER": "supabase",
        "SUPABASE_URL": "https://project-ref.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
    }
)

from app.services.road_tax_service import _eval_formula


def test_eval_formula_returns_none_for_empty_formula():
    assert _eval_formula("", 1800) is None


def test_eval_formula_returns_none_for_invalid_characters():
    assert _eval_formula("__import__('os').system('x')", 1800) is None


def test_eval_formula_evaluates_safe_expression():
    assert _eval_formula("280 + 0.5 * (cc - 1800)", 2000) == 380.0


def test_eval_formula_returns_none_for_syntax_error():
    assert _eval_formula("280 + * (cc - 1800)", 2000) is None


def test_eval_formula_returns_none_for_undefined_name():
    assert _eval_formula("cc + unknown", 2000) is None


def test_eval_formula_returns_none_for_type_error():
    assert _eval_formula("cc + 'text'", 2000) is None


def test_calculate_road_tax_private_car():
    from app.services.road_tax_service import calculate_road_tax

    assert calculate_road_tax(998, vehicle_type="Car", owner_type="Individual") == 20.00
    assert calculate_road_tax(1197, vehicle_type="Car", owner_type="Individual") == 55.00
    assert calculate_road_tax(1329, vehicle_type="Car", owner_type="Individual") == 70.00
    assert calculate_road_tax(1496, vehicle_type="Car", owner_type="Individual") == 90.00
    # 1601-1800: 200 + 0.40 * (1798 - 1600) = 200 + 79.2 = 279.20
    assert calculate_road_tax(1798, vehicle_type="Car", owner_type="Individual") == 279.20
    # 1801-2000: 280 + 0.50 * (1998 - 1800) = 280 + 99 = 379.00
    assert calculate_road_tax(1998, vehicle_type="Car", owner_type="Individual") == 379.00
    # 2001-2500: 380 + 1.00 * (2494 - 2000) = 380 + 494 = 874.00
    assert calculate_road_tax(2494, vehicle_type="Car", owner_type="Individual") == 874.00
    # 2501-3000: 840 + 2.50 * (2997 - 2500) = 840 + 1242.50 = 2082.50
    assert calculate_road_tax(2997, vehicle_type="Car", owner_type="Individual") == 2082.50
    # >3000: 2130 + 4.50 * (3456 - 3000) = 2130 + 2052 = 4182.00
    assert calculate_road_tax(3456, vehicle_type="Car", owner_type="Individual") == 4182.00


def test_calculate_road_tax_private_motorcycle():
    from app.services.road_tax_service import calculate_road_tax

    assert calculate_road_tax(135, vehicle_type="Motorcycle", owner_type="Individual") == 2.00
    assert calculate_road_tax(180, vehicle_type="Motorcycle", owner_type="Individual") == 30.00
    assert calculate_road_tax(249, vehicle_type="Motorcycle", owner_type="Individual") == 50.00
    assert calculate_road_tax(300, vehicle_type="Motorcycle", owner_type="Individual") == 100.00
    assert calculate_road_tax(650, vehicle_type="Motorcycle", owner_type="Individual") == 250.00
    assert calculate_road_tax(1000, vehicle_type="Motorcycle", owner_type="Individual") == 350.00


def test_calculate_road_tax_company_car():
    from app.services.road_tax_service import calculate_road_tax

    assert calculate_road_tax(998, vehicle_type="Car", owner_type="Company") == 20.00
    assert calculate_road_tax(1197, vehicle_type="Car", owner_type="Company") == 110.00
    assert calculate_road_tax(1329, vehicle_type="Car", owner_type="Company") == 140.00
    assert calculate_road_tax(1496, vehicle_type="Car", owner_type="Company") == 180.00
    # Also verify vehicle_type="CompanyCar" works seamlessly without passing owner_type="Company"
    assert calculate_road_tax(1495, vehicle_type="CompanyCar") == 180.00
    assert calculate_road_tax(1495, vehicle_type="CompanyCar", owner_type="Individual") == 180.00
    # 1601-1800: 400 + 0.80 * (1798 - 1600) = 400 + 158.4 = 558.40
    assert calculate_road_tax(1798, vehicle_type="Car", owner_type="Company") == 558.40
    # 1801-2000: 560 + 1.00 * (1998 - 1800) = 560 + 198 = 758.00
    assert calculate_road_tax(1998, vehicle_type="Car", owner_type="Company") == 758.00
    # 2001-2500: 760 + 3.00 * (2494 - 2000) = 760 + 1482 = 2242.00
    assert calculate_road_tax(2494, vehicle_type="Car", owner_type="Company") == 2242.00
    # 2501-3000: 2260 + 7.50 * (2997 - 2500) = 2260 + 3727.50 = 5987.50
    assert calculate_road_tax(2997, vehicle_type="Car", owner_type="Company") == 5987.50
    # >3000: 6010 + 13.50 * (3456 - 3000) = 6010 + 6156 = 12166.00
    assert calculate_road_tax(3456, vehicle_type="Car", owner_type="Company") == 12166.00


def test_calculate_road_tax_corporate_motorcycle():
    from app.services.road_tax_service import calculate_road_tax

    assert calculate_road_tax(135, vehicle_type="Motorcycle", owner_type="Corporate") == 2.00
    assert calculate_road_tax(180, vehicle_type="Motorcycle", owner_type="Corporate") == 30.00
    assert calculate_road_tax(249, vehicle_type="Motorcycle", owner_type="Corporate") == 50.00
    assert calculate_road_tax(300, vehicle_type="Motorcycle", owner_type="Corporate") == 180.00
    assert calculate_road_tax(650, vehicle_type="Motorcycle", owner_type="Corporate") == 250.00
    assert calculate_road_tax(1000, vehicle_type="Motorcycle", owner_type="Corporate") == 350.00


def test_calculate_road_tax_sabah_sarawak():
    from app.services.road_tax_service import calculate_road_tax

    # Private Car: 1998cc: 224 + (1998 - 1800) * 0.25 = 224 + 49.50 = 273.50
    assert calculate_road_tax(1998, vehicle_type="Car", owner_type="Individual", jurisdiction="Sabah") == 273.50
    assert calculate_road_tax(1998, vehicle_type="Car", owner_type="Individual", jurisdiction="Sarawak") == 273.50
    # Private Car: 1496cc: flat 72.00
    assert calculate_road_tax(1496, vehicle_type="Car", owner_type="Individual", jurisdiction="Sabah") == 72.00


def test_calculate_road_tax_labuan():
    from app.services.road_tax_service import calculate_road_tax

    # Private Car: 1998cc: 140 + (1998 - 1800) * 0.25 = 140 + 49.50 = 189.50
    assert calculate_road_tax(1998, vehicle_type="Car", owner_type="Individual", jurisdiction="Labuan") == 189.50
    # Private Car: 1496cc: flat 45.00
    assert calculate_road_tax(1496, vehicle_type="Car", owner_type="Individual", jurisdiction="Labuan") == 45.00


def test_calculate_road_tax_commercial_lorry():
    from app.services.road_tax_service import calculate_road_tax

    assert calculate_road_tax(1500, vehicle_type="Lorry", owner_type="Company") == 120.00
    assert calculate_road_tax(2200, vehicle_type="Lorry", owner_type="Company") == 240.00
    assert calculate_road_tax(4500, vehicle_type="Lorry", owner_type="Company") == 480.00
    assert calculate_road_tax(6000, vehicle_type="Lorry", owner_type="Company") == 720.00


def test_calculate_breakdown():
    from app.services.road_tax_service import calculate_breakdown

    bd = calculate_breakdown(1998, vehicle_type="Car", owner_type="Individual", jurisdiction="West Malaysia")
    assert bd["engine_cc"] == 1998
    assert bd["base_rate"] == 280.00
    assert bd["progressive_rate"] == 0.50
    assert bd["excess_cc"] == 198
    assert bd["progressive_amount"] == 99.00
    assert bd["total_road_tax"] == 379.00


def test_calculate_road_tax_non_saloon_car():
    from app.services.road_tax_service import calculate_road_tax

    # West Malaysia Non-Saloon rates (same for Individual and Company)
    # Perodua Alza 1495cc -> Flat 120.00
    assert calculate_road_tax(1495, vehicle_type="NonSaloonCar", owner_type="Individual") == 120.00
    assert calculate_road_tax(1495, vehicle_type="NonSaloonCar", owner_type="Company") == 120.00
    assert calculate_road_tax(998, vehicle_type="NonSaloonCar") == 20.00
    assert calculate_road_tax(1197, vehicle_type="NonSaloonCar") == 85.00
    assert calculate_road_tax(1329, vehicle_type="NonSaloonCar") == 100.00
    assert calculate_road_tax(1598, vehicle_type="NonSaloonCar") == 120.00
    # 1601-1800: 300 + 0.30 * (1798 - 1600) = 300 + 59.40 = 359.40
    assert calculate_road_tax(1798, vehicle_type="NonSaloonCar") == 359.40
    # 1801-2000: 360 + 0.40 * (1998 - 1800) = 360 + 79.20 = 439.20
    assert calculate_road_tax(1998, vehicle_type="NonSaloonCar") == 439.20
    # 2001-2500: 440 + 0.80 * (2494 - 2000) = 440 + 395.20 = 835.20
    assert calculate_road_tax(2494, vehicle_type="NonSaloonCar") == 835.20
    # 2501-3000: 840 + 1.60 * (2997 - 2500) = 840 + 795.20 = 1635.20
    assert calculate_road_tax(2997, vehicle_type="NonSaloonCar") == 1635.20
    # >3000: 1640 + 1.60 * (3456 - 3000) = 1640 + 729.60 = 2369.60
    assert calculate_road_tax(3456, vehicle_type="NonSaloonCar") == 2369.60

    # East Malaysia Non-Saloon rates
    assert calculate_road_tax(1495, vehicle_type="NonSaloonCar", jurisdiction="Sabah") == 96.00
    assert calculate_road_tax(1495, vehicle_type="NonSaloonCar", jurisdiction="Sarawak") == 96.00

    # Labuan Non-Saloon rates
    assert calculate_road_tax(1495, vehicle_type="NonSaloonCar", jurisdiction="Labuan") == 60.00


def test_calculate_breakdown_non_saloon():
    from app.services.road_tax_service import calculate_breakdown

    bd = calculate_breakdown(1495, vehicle_type="NonSaloonCar", owner_type="Company", jurisdiction="West Malaysia")
    assert bd["engine_cc"] == 1495
    assert bd["vehicle_type"] == "NonSaloonCar"
    assert bd["base_rate"] == 120.00
    assert bd["progressive_rate"] == 0.0
    assert bd["excess_cc"] == 0
    assert bd["progressive_amount"] == 0.0
    assert bd["total_road_tax"] == 120.00
    assert bd["matched_tier"] == "1401 – 1600 cc"


