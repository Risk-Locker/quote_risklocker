"""Canvas-driven Risklocker motor template configuration.

The builder stores its editable layout in ``OutputTemplateConfig.fixed_fields``.
This keeps v1 flexible without forcing a new template table while still making
PDF rendering deterministic.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.services.template_assets import find_asset_by_hint


CANVAS_WIDTH = 794
CANVAS_HEIGHT = 1123

SUMMARY_FIELDS = [
    {"field": "coverage_type", "label": "Coverage Type"},
    {"field": "cover_period", "label": "Cover of Period"},
    {"field": "car_model", "label": "Car Model"},
    {"field": "ncd_percent", "label": "NCD", "suffix": "%"},
    {"field": "coverage_amount", "label": "Coverage", "prefix": "RM"},
    {"field": "premium", "label": "Insurance Premium", "prefix": "RM"},
    {"field": "roadtax", "label": "Roadtax", "prefix": "RM"},
    {"field": "service_fee", "label": "Runner Fee", "prefix": "RM"},
    {"field": "total_amount", "label": "Total Premium", "prefix": "RM"},
]

REVIEW_GROUPS = [
    {
        "id": "quotation_values",
        "title": "Quotation Values",
        "collapsed": False,
        "fields": [item["field"] for item in SUMMARY_FIELDS],
    },
    {
        "id": "source_details",
        "title": "More Source Details",
        "collapsed": True,
        "fields": [
            "insurance_company",
            "source_template_category",
            "product_name",
            "customer_name",
            "vehicle_no",
            "issue_date",
            "valid_until",
            "vehicle_year",
            "engine_cc",
            "engine_no",
            "chassis_no",
            "market_value",
            "agreed_value",
            "excess_amount",
            "basic_premium_vehicle",
            "ncd_amount",
            "service_tax",
            "stamp_duty",
            "gross_premium",
            "optional_cover_amount",
            "optional_covers",
            "notes",
        ],
    },
]

VARIABLES = [
    {"id": "customer_name", "label": "Customer Name", "type": "text", "source": "field", "field": "customer_name"},
    {"id": "vehicle_no", "label": "Vehicle No", "type": "text", "source": "field", "field": "vehicle_no"},
    {"id": "insurance_company", "label": "Insurance Company", "type": "text", "source": "field", "field": "insurance_company"},
    {"id": "insurer_logo", "label": "Insurer Logo", "type": "image", "source": "manual"},
    {"id": "coverage_type", "label": "Coverage Type", "type": "text", "source": "field", "field": "coverage_type"},
    {"id": "cover_period", "label": "Cover Period", "type": "date", "source": "field", "field": "cover_period"},
    {"id": "car_model", "label": "Car Model", "type": "text", "source": "field", "field": "car_model"},
    {"id": "ncd_percent", "label": "NCD", "type": "percent", "source": "field", "field": "ncd_percent"},
    {"id": "coverage_amount", "label": "Coverage Amount", "type": "money", "source": "field", "field": "coverage_amount"},
    {"id": "premium", "label": "Insurance Premium", "type": "money", "source": "field", "field": "premium"},
    {"id": "roadtax", "label": "Roadtax", "type": "money", "source": "field", "field": "roadtax"},
    {"id": "service_fee", "label": "Runner Fee", "type": "money", "source": "field", "field": "service_fee"},
    {"id": "total_amount", "label": "Total Premium", "type": "money", "source": "field", "field": "total_amount"},
    {"id": "valid_until", "label": "Validity Date", "type": "date", "source": "field", "field": "valid_until"},
    {"id": "selected_benefits", "label": "Selected Benefits", "type": "benefit_card", "source": "field", "field": "benefits_selected"},
    {"id": "selected_add_ons", "label": "Selected Add-ons", "type": "benefit_card", "source": "field", "field": "add_ons_selected"},
]

ASSET_HINTS = {
    "risklocker_logo": ["risklocker logo"],
    "bank_logo": ["hongleong", "bank"],
    "all_driver_icon": ["all driver"],
    "background": ["template_bg"],
    "amassurance_logo": ["amgen", "amassurance"],
    "etiqa_logo": ["etiqa"],
    "liberty_logo": ["liberty"],
    "qbe_logo": ["qbe"],
    "lonpac_logo": ["lonpac"],
}

CARD_CATALOG: dict[str, dict[str, Any]] = {
    "windscreen": {"icon": "windscreen", "title": "Windscreen Coverage (Up to RM )", "subtitle": "Mirror glass coverage"},
    "child_seat": {"icon": "child-seat", "title": "Child Seat Replacement Coverage", "subtitle": "Child seat replacement"},
    "workmanship_6m": {"icon": "workshop", "title": "6 Months Workmanship Warranty", "subtitle": "Repair workmanship warranty"},
    "workmanship_1y": {"icon": "workshop", "title": "1 Year Workmanship Warranty", "subtitle": "Repair workmanship warranty"},
    "workmanship_3y": {"icon": "workshop", "title": "3 Years Workmanship Warranty", "subtitle": "Repair workmanship warranty"},
    "unlimited_towing": {"icon": "tow", "title": "Unlimited Towing", "subtitle": "Towing service"},
    "enhanced_auto_assist": {"icon": "tow", "title": "Enhanced Auto Assist (Up to RM 500)", "subtitle": "Roadside assist"},
    "flood_relief": {"icon": "flood", "title": "Flood Relief Allowance - RM 3,000", "subtitle": "Flood allowance"},
    "cleaning_cost": {"icon": "cleaning", "title": "Cleaning Cost (Flood/Theft) - RM5,000", "subtitle": "Cleaning cost after flood or theft"},
    "express_claim_5000": {"icon": "claim", "title": "Express Claim (Below RM 5,000)", "subtitle": "Fast claim service"},
    "express_claim_10000": {"icon": "claim", "title": "Express Claim (Below RM 10,000)", "subtitle": "Fast claim service"},
    "excess": {"icon": "excess", "title": "Excess (RM)", "subtitle": ""},
    "ambulance": {"icon": "ambulance", "title": "Ambulance Fee (Up to RM 1,000)", "subtitle": "Ambulance allowance"},
    "one_touch": {"icon": "mobile", "title": "One Touch Mobile App", "subtitle": "Mobile support app"},
    "e_hailing": {"icon": "car", "title": "E-Hailing", "subtitle": "E-hailing cover"},
    "grab": {"icon": "car", "title": "E-Hailing", "subtitle": "Grab", "asset_hint": "grab"},
    "compassionate": {"icon": "allowance", "title": "Compassionate Allowance - RM 8,000", "subtitle": "Vehicle total loss or theft allowance"},
    "waiver_betterment": {"icon": "document", "title": "Waiver of Betterment", "subtitle": "Betterment waiver"},
    "waiver_betterment_10y": {"icon": "document", "title": "Waive of Betterment (Up to 10 Years)", "subtitle": "Betterment waiver"},
    "passenger_liability": {"icon": "passenger", "title": "Passenger Liability (LLP & LLOP)", "subtitle": "Passenger legal liability"},
    "special_perils": {"icon": "flood", "title": "Inclusion of Special Perils", "subtitle": "Special perils cover"},
    "bundle_a": {
        "icon": "bundle",
        "title": "Liberty Private Car Bundle A",
        "subtitle": "Personal accident plan A",
        "lines": ["Death and Disability - RM 20,000 / Passenger", "Double Indemnity - RM 20,000", "Hospital Income - RM 30 (up to 60 Days)"],
    },
    "bundle_b": {
        "icon": "bundle",
        "title": "Liberty Private Car Bundle B",
        "subtitle": "Personal accident plan B",
        "lines": ["Death and Disability - RM 20,000 / Passenger", "Flood Inconvenience Allowance - RM 1,000", "1 Year Workmanship Warranty"],
    },
    "bundle_c": {
        "icon": "bundle",
        "title": "Liberty Private Car Bundle C",
        "subtitle": "Personal accident plan C",
        "lines": ["Death and Disability - RM 30,000 / Passenger", "Flood Inconvenience Allowance - RM 1,000", "18 Months Workmanship Warranty"],
    },
    "dpp_plan1": {
        "icon": "bundle",
        "title": "Driver Passenger Protection Plan 1",
        "subtitle": "Driver and passenger protection",
        "lines": ["Death and Disability - RM 10,000 / Passenger", "Double Indemnity - RM 10,000", "Cover Immediate Family Under One Roof"],
    },
    "dpp_plan2": {
        "icon": "bundle",
        "title": "Driver Passenger Protection Plan 2",
        "subtitle": "Driver and passenger protection",
        "lines": ["Death and Disability - RM 50,000 / Passenger", "Medical Expenses - RM 2,000 / Passenger", "Funeral Expenses - RM 1,000 / Passenger"],
    },
    "out_of_pocket": {
        "icon": "cash",
        "title": "Out of Pocket Allowance",
        "subtitle": "Extra expense allowance",
        "lines": ["Hotel Accommodation - RM 250", "Transportation Allowance - RM 150", "Whole Car Spray Painting - RM 1,500"],
    },
    "whole_car_spray": {"icon": "spray", "title": "Whole Car Spray Painting", "subtitle": "Whole car spray painting"},
}

DEFAULT_PACKAGES = [
    {"name": "Base", "included_cards": ["unlimited_towing", "excess"], "add_on_cards": ["windscreen", "passenger_liability", "special_perils"]},
    {"name": "Windscreen", "included_cards": ["windscreen", "unlimited_towing", "excess"], "add_on_cards": ["passenger_liability", "special_perils"]},
    {"name": "LLP & LLOP", "included_cards": ["passenger_liability", "unlimited_towing", "excess"], "add_on_cards": ["windscreen", "special_perils"]},
    {"name": "Full Benefits", "included_cards": ["windscreen", "passenger_liability", "special_perils", "unlimited_towing", "excess"], "add_on_cards": []},
]


def card_title(card_id: str) -> str:
    return str(CARD_CATALOG.get(card_id, {}).get("title") or card_id.replace("_", " ").title())


def card_from_label(label: str) -> str:
    normalized = " ".join(label.lower().replace("&", "and").split())
    for card_id, card in CARD_CATALOG.items():
        title = str(card.get("title", "")).lower().replace("&", "and")
        if normalized in title or title in normalized:
            return card_id
    rules = [
        ("windscreen", "windscreen"),
        ("llp", "passenger_liability"),
        ("llop", "passenger_liability"),
        ("passenger liability", "passenger_liability"),
        ("special peril", "special_perils"),
        ("betterment", "waiver_betterment"),
        ("towing", "unlimited_towing"),
        ("driver passenger", "dpp_plan1"),
        ("e-hailing", "e_hailing"),
        ("grab", "grab"),
        ("cleaning", "cleaning_cost"),
        ("spray", "whole_car_spray"),
    ]
    for token, card_id in rules:
        if token in normalized:
            return card_id
    return normalized.replace(" ", "_")


def _normalize_package(package: dict[str, Any]) -> dict[str, Any]:
    included_cards = package.get("included_cards") or [card_from_label(item) for item in package.get("included", [])]
    add_on_cards = package.get("add_on_cards") or [card_from_label(item) for item in package.get("add_ons", [])]
    return {
        "name": package.get("name") or "Base",
        "included_cards": included_cards,
        "add_on_cards": add_on_cards,
        "included": [card_title(card_id) for card_id in included_cards],
        "add_ons": [card_title(card_id) for card_id in add_on_cards],
    }


def _element(element_id: str, element_type: str, x: int, y: int, w: int, h: int, **extra: Any) -> dict[str, Any]:
    base = {
        "id": element_id,
        "type": element_type,
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "z": extra.pop("z", 1),
        "style": {
            "fontSize": extra.pop("fontSize", 14),
            "fontWeight": extra.pop("fontWeight", "400"),
            "color": extra.pop("color", "#111111"),
            "textAlign": extra.pop("textAlign", "left"),
            "borderWidth": extra.pop("borderWidth", 0),
            "borderColor": extra.pop("borderColor", "#111111"),
            "background": extra.pop("background", "transparent"),
        },
    }
    base.update(extra)
    return base


def default_canvas_elements() -> list[dict[str, Any]]:
    rows = []
    y = 140
    for item in SUMMARY_FIELDS:
        row_id = item["field"]
        rows.extend(
            [
                _element(f"label_{row_id}", "text", 24, y, 190, 24, text=item["label"], fontSize=14, fontWeight="700"),
                _element(f"colon_{row_id}", "text", 215, y, 12, 24, text=":", fontSize=14),
                _element(f"value_{row_id}", "variable", 235, y, 215, 24, variableId=row_id, fontSize=14),
            ]
        )
        y += 28
        if row_id == "premium":
            y += 28
    return [
        _element("background", "image", 0, 0, CANVAS_WIDTH, CANVAS_HEIGHT, assetSlot="background", opacity=0.28, z=0),
        _element("risklocker_logo", "image", 52, 12, 120, 88, assetSlot="risklocker_logo", z=3),
        _element("insurer_logo", "image", 270, 20, 220, 72, assetSlot="insurer_logo", z=3),
        _element("title", "text", 520, 16, 250, 30, text="Motor Insurance Quotation", fontSize=20, fontWeight="800", color="#ed1c24", textAlign="right", z=3),
        _element("quote_vehicle", "variable", 560, 51, 210, 25, variableId="vehicle_no", fontSize=17, fontWeight="800", textAlign="right", z=3),
        _element("top_rule", "line", 0, 114, CANVAS_WIDTH, 2, borderWidth=2, z=2),
        *rows,
        _element("payment_box", "group", 532, 160, 224, 122, borderWidth=2, background="#ffffff", z=2),
        _element("bank_logo", "image", 548, 178, 70, 60, assetSlot="bank_logo", z=3),
        _element("payment_text", "text", 622, 166, 120, 104, text="Payment Method\nBank details\n12300318500\nRisklocker Sdn. Bhd.\nHong Leong Bank", fontSize=13, textAlign="right", z=3),
        _element("driver_box", "group", 532, 306, 224, 48, borderWidth=2, background="#ffffff", z=2),
        _element("driver_icon", "image", 548, 314, 34, 34, assetSlot="all_driver_icon", z=3),
        _element("driver_text", "text", 610, 319, 120, 24, text="All Driver", fontSize=14, textAlign="center", z=3),
        _element("summary_rule", "line", 0, 380, CANVAS_WIDTH, 2, borderWidth=2, z=2),
        _element("specials_title", "text", 250, 394, 300, 42, text="Our Specials", fontSize=34, fontWeight="800", textAlign="center", z=2),
        _element("specials_section", "benefit-section", 18, 448, 758, 230, section="specials", columns=2, z=2),
        _element("addons_title", "text", 38, 700, 718, 42, text="You May Add On (With Additional Charges)", fontSize=32, fontWeight="800", textAlign="center", z=2),
        _element("addons_section", "benefit-section", 18, 760, 758, 230, section="add_ons", columns=2, z=2),
        _element("terms", "text", 24, 1040, 300, 24, text="*Terms and Condition Applied", fontSize=13, z=2),
        _element("validity", "variable", 24, 1065, 260, 24, variableId="valid_until", fontSize=13, prefix="Validity: ", z=2),
    ]


def _default_assets() -> dict[str, str]:
    return {
        "risklocker_logo": find_asset_by_hint(None, ["risklocker logo"]),
        "bank_logo": find_asset_by_hint(None, ["hongleong", "bank"]),
        "all_driver_icon": find_asset_by_hint(None, ["all driver"]),
        "background": find_asset_by_hint(None, ["template_bg"]),
    }


def default_template_config(template_category: str = "Motor", packages: list[dict[str, Any]] | None = None, *, locked: bool = True) -> dict[str, Any]:
    normalized_packages = [_normalize_package(item) for item in (packages or DEFAULT_PACKAGES)]
    return {
        "version": 2,
        "is_default": locked,
        "locked": locked,
        "template_category": template_category,
        "variables": deepcopy(VARIABLES),
        "summary_fields": deepcopy(SUMMARY_FIELDS),
        "review_groups": deepcopy(REVIEW_GROUPS),
        "asset_slots": deepcopy(ASSET_HINTS),
        "assets": {key: value for key, value in _default_assets().items() if value},
        "payment": {
            "method": "Payment Method",
            "bank": "Hong Leong Bank",
            "account": "12300318500",
            "account_name": "Risklocker Sdn. Bhd.",
        },
        "driver_box": {"label": "All Driver"},
        "cards": deepcopy(CARD_CATALOG),
        "packages": normalized_packages,
        "canvas": {"width": CANVAS_WIDTH, "height": CANVAS_HEIGHT, "elements": default_canvas_elements()},
        "validity_note": "*Terms and Condition Applied",
    }


def normalize_template_config(fixed_fields: dict[str, Any] | None, template_category: str = "Motor") -> dict[str, Any]:
    base = default_template_config(template_category, fixed_fields.get("packages") if isinstance(fixed_fields, dict) else None)
    if isinstance(fixed_fields, dict):
        base.update(deepcopy(fixed_fields))
    base["version"] = max(int(base.get("version") or 1), 2)
    base["variables"] = base.get("variables") or deepcopy(VARIABLES)
    base["summary_fields"] = base.get("summary_fields") or deepcopy(SUMMARY_FIELDS)
    base["review_groups"] = base.get("review_groups") or deepcopy(REVIEW_GROUPS)
    base["cards"] = {**deepcopy(CARD_CATALOG), **(base.get("cards") or {})}
    base["packages"] = [_normalize_package(item) for item in (base.get("packages") or DEFAULT_PACKAGES)]
    base["asset_slots"] = {**deepcopy(ASSET_HINTS), **(base.get("asset_slots") or {})}
    base["assets"] = base.get("assets") or {}
    base.setdefault("payment", default_template_config()["payment"])
    base.setdefault("driver_box", {"label": "All Driver"})
    base.setdefault("validity_note", "*Terms and Condition Applied")
    canvas = base.get("canvas") or {}
    canvas.setdefault("width", CANVAS_WIDTH)
    canvas.setdefault("height", CANVAS_HEIGHT)
    canvas.setdefault("elements", default_canvas_elements())
    base["canvas"] = canvas
    return base


def selected_package_config(config: dict[str, Any], package_name: str | None) -> dict[str, Any] | None:
    packages = config.get("packages") or []
    for package in packages:
        if package.get("name") == package_name:
            return package
    return packages[0] if packages else None


def cards_for_ids(config: dict[str, Any], card_ids: list[str]) -> list[dict[str, Any]]:
    cards = config.get("cards") or {}
    return [cards.get(card_id, {"id": card_id, "title": card_title(card_id), "icon": "item"}) | {"id": card_id} for card_id in card_ids]


def review_schema_for(config: dict[str, Any], package_name: str | None) -> dict[str, Any]:
    package = selected_package_config(config, package_name)
    included_cards = package.get("included_cards", []) if package else []
    add_on_cards = package.get("add_on_cards", []) if package else []
    return {
        "groups": deepcopy(config.get("review_groups") or REVIEW_GROUPS),
        "summary_fields": deepcopy(config.get("summary_fields") or SUMMARY_FIELDS),
        "variables": deepcopy(config.get("variables") or VARIABLES),
        "selected_package": package,
        "specials": cards_for_ids(config, included_cards),
        "add_ons": cards_for_ids(config, add_on_cards),
    }
