import pytest
from app.extraction.entity_classifier import classify_vehicle_ev_status, classify_client_entity
from app.services.road_tax_service import calculate_road_tax, normalize_power_to_watts


def test_classify_vehicle_ev_status_canonical():
    # Saloon EVs
    is_ev, cat = classify_vehicle_ev_status("TESLA", "MODEL 3", "150 kW")
    assert is_ev is True
    assert cat == "EVSaloonCar"

    is_ev, cat = classify_vehicle_ev_status("BYD", "SEAL", "")
    assert is_ev is True
    assert cat == "EVSaloonCar"

    is_ev, cat = classify_vehicle_ev_status("PORSCHE", "TAYCAN 4S", "")
    assert is_ev is True
    assert cat == "EVSaloonCar"

    # Non-Saloon EVs (SUV / MPV / Crossover)
    is_ev, cat = classify_vehicle_ev_status("GWM", "ORA GOOD CAT", "")
    assert is_ev is True
    assert cat == "EVNonSaloonCar"

    is_ev, cat = classify_vehicle_ev_status("TESLA", "MODEL Y", "")
    assert is_ev is True
    assert cat == "EVNonSaloonCar"

    is_ev, cat = classify_vehicle_ev_status("BYD", "ATTO 3", "")
    assert is_ev is True
    assert cat == "EVNonSaloonCar"

    is_ev, cat = classify_vehicle_ev_status("HYUNDAI", "IONIQ 5", "")
    assert is_ev is True
    assert cat == "EVNonSaloonCar"

    is_ev, cat = classify_vehicle_ev_status("MAXUS", "MIFA 9", "")
    assert is_ev is True
    assert cat == "EVNonSaloonCar"

    # Electric Motorcycles
    is_ev, cat = classify_vehicle_ev_status("BLUESHARK", "R1", "")
    assert is_ev is True
    assert cat == "EVMotorcycle"

    # ICE vehicles should return False
    is_ev, cat = classify_vehicle_ev_status("PERODUA", "MYVI 1.5", "1496 cc")
    assert is_ev is False
    assert cat is None

    is_ev, cat = classify_vehicle_ev_status("PERODUA", "ALZA 1500 EZI", "1495.0 CC")
    assert is_ev is False
    assert cat is None


def test_classify_client_entity_with_ev():
    # Individual (Private) EV Saloon
    entity_type, vtype = classify_client_entity(
        customer_name="TAN AH KOW",
        ic_or_brn="880101-14-5555",
        ai_client_type="Individual",
        current_vehicle_type="Car",
        car_model="TESLA MODEL 3 LONG RANGE",
        car_brand="TESLA",
    )
    assert entity_type == "Private"
    assert vtype == "EVSaloonCar"

    # Company EV Non-Saloon
    entity_type, vtype = classify_client_entity(
        customer_name="PL INKJET SDN. BHD.",
        ic_or_brn="202001012345",
        ai_client_type="Company",
        current_vehicle_type="Car",
        car_model="BYD ATTO 3 EXTENDED",
        car_brand="BYD",
    )
    assert entity_type == "Company"
    assert vtype == "EVNonSaloonCar"


def test_ev_power_normalization():
    # If input is kW (< 1000)
    assert normalize_power_to_watts(150.0) == 150000.0
    assert normalize_power_to_watts("150 kW") == 150000.0

    # If input is Watts (>= 1000)
    assert normalize_power_to_watts(150000) == 150000.0
    assert normalize_power_to_watts("150000 W") == 150000.0


def test_ev_road_tax_calculation_official_rates():
    # 1. EV Motorcycle
    assert calculate_road_tax(7.5, "EVMotorcycle") == 2.00
    assert calculate_road_tax(10.0, "EVMotorcycle") == 9.00
    assert calculate_road_tax(12.5, "EVMotorcycle") == 12.00
    assert calculate_road_tax(25.0, "EVMotorcycle") == 30.00
    assert calculate_road_tax(40.0, "EVMotorcycle") == 40.00
    assert calculate_road_tax(50.0, "EVMotorcycle") == 42.00

    # 2. EV Saloon Car (Official 2026 JPJ Schedule)
    assert calculate_road_tax(50.0, "EVSaloonCar") == 20.00
    assert calculate_road_tax(60.0, "EVSaloonCar") == 30.00
    assert calculate_road_tax(70.0, "EVSaloonCar") == 40.00
    assert calculate_road_tax(80.0, "EVSaloonCar") == 50.00
    assert calculate_road_tax(100.0, "EVSaloonCar") == 70.00
    assert calculate_road_tax(150.0, "EVSaloonCar") == 160.00
    assert calculate_road_tax(200.0, "EVSaloonCar") == 260.00
    assert calculate_road_tax(230.0, "EVSaloonCar") == 335.00

    # 3. EV Non-Saloon Car (Shares same schedule as Saloon under 2026 JPJ rates)
    assert calculate_road_tax(50.0, "EVNonSaloonCar") == 20.00
    assert calculate_road_tax(150.0, "EVNonSaloonCar") == 160.00  # BYD Atto 3
    assert calculate_road_tax(220.0, "EVNonSaloonCar") == 305.00  # Tesla Model Y RWD
    assert calculate_road_tax(378.0, "EVNonSaloonCar") == 915.00  # Tesla Model Y Long Range

    # 4. EV rates are 100% identical for Individual and Company
    rt_ind = calculate_road_tax(220.0, "EVNonSaloonCar", owner_type="Individual")
    rt_com = calculate_road_tax(220.0, "EVNonSaloonCar", owner_type="Company")
    assert rt_ind == rt_com == 305.00

    # 5. Watts vs kW inputs give the exact same result
    assert calculate_road_tax(150.0, "EVSaloonCar") == calculate_road_tax(150000, "EVSaloonCar")
    assert calculate_road_tax(220.0, "EVNonSaloonCar") == calculate_road_tax(220000, "EVNonSaloonCar")

    # 6. Regional discounts (Sabah/Sarawak: 50%, Labuan: 50% above 100kW)
    assert calculate_road_tax(220.0, "EVNonSaloonCar", jurisdiction="Sabah") == 152.50
    assert calculate_road_tax(220.0, "EVNonSaloonCar", jurisdiction="Labuan") == 152.50


def test_template_renderer_engine_capacity_formatting():
    from app.rendering.template_renderer import render_quotation_html

    # Case 1: ICE vehicle
    ice_fields = {
        "car_brand": {"value": "PERODUA"},
        "car_model": {"value": "ALZA 1500 EZI"},
        "engine_cc": {"value": "1495.0 CC"},
        "vehicle_type": {"value": "CompanyCar"},
    }
    html_ice = render_quotation_html(ice_fields)
    assert "Engine Capacity/发动机排量 : " in html_ice
    assert "1495 cc" in html_ice

    # Case 2: EV vehicle with kW input
    ev_fields = {
        "car_brand": {"value": "BYD"},
        "car_model": {"value": "ATTO 3"},
        "engine_cc": {"value": "150 kW"},
        "vehicle_type": {"value": "EVNonSaloonCar"},
    }
    html_ev = render_quotation_html(ev_fields)
    assert "Engine Capacity/发动机排量 : " in html_ev
    assert "150 kW" in html_ev

    # Case 3: EV vehicle with Watts input (>= 1000)
    ev_watts_fields = {
        "car_brand": {"value": "TESLA"},
        "car_model": {"value": "MODEL 3"},
        "engine_cc": {"value": "150000"},
        "vehicle_type": {"value": "EVSaloonCar"},
    }
    html_ev_watts = render_quotation_html(ev_watts_fields)
    assert "150 kW" in html_ev_watts

