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
    {"field": "car_model", "label": "Car Model"},
    {"field": "engine_cc", "label": "Vehicle CC", "suffix": " cc"},
    {"field": "ncd_percent", "label": "NCD", "suffix": "%"},
    {"field": "cover_period", "label": "Cover of Period"},
    {"field": "coverage_amount", "label": "Coverage", "prefix": "RM"},
    {"field": "excess_amount", "label": "Policy Excess", "prefix": "RM"},
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
    {"id": "engine_cc", "label": "Vehicle CC / Capacity", "type": "text", "source": "field", "field": "engine_cc"},
    {"id": "ncd_percent", "label": "NCD", "type": "percent", "source": "field", "field": "ncd_percent"},
    {"id": "coverage_amount", "label": "Coverage Amount", "type": "money", "source": "field", "field": "coverage_amount"},
    {"id": "excess_amount", "label": "Policy Excess", "type": "money", "source": "field", "field": "excess_amount"},
    {"id": "premium", "label": "Insurance Premium", "type": "money", "source": "field", "field": "premium"},
    {"id": "roadtax", "label": "Roadtax", "type": "money", "source": "field", "field": "roadtax"},
    {"id": "service_fee", "label": "Runner Fee", "type": "money", "source": "field", "field": "service_fee"},
    {"id": "total_amount", "label": "Total Premium", "type": "money", "source": "field", "field": "total_amount"},
    {"id": "valid_until", "label": "Validity Date", "type": "date", "source": "field", "field": "valid_until"},
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
        "canvas": {"width": CANVAS_WIDTH, "height": CANVAS_HEIGHT, "elements": default_canvas_elements()},
        "validity_note": "*Terms and Condition Applied",
    }


def normalize_template_config(fixed_fields: dict[str, Any] | None, template_category: str = "Motor") -> dict[str, Any]:
    base = default_template_config(template_category)
    if isinstance(fixed_fields, dict):
        base.update(deepcopy(fixed_fields))
    base["version"] = max(int(base.get("version") or 1), 2)
    base["variables"] = base.get("variables") or deepcopy(VARIABLES)
    base["summary_fields"] = base.get("summary_fields") or deepcopy(SUMMARY_FIELDS)
    base["review_groups"] = base.get("review_groups") or deepcopy(REVIEW_GROUPS)
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


def review_schema_for(config: dict[str, Any], package_name: str | None) -> dict[str, Any]:
    return {
        "groups": deepcopy(config.get("review_groups") or REVIEW_GROUPS),
        "summary_fields": deepcopy(config.get("summary_fields") or SUMMARY_FIELDS),
        "variables": deepcopy(config.get("variables") or VARIABLES),
    }
