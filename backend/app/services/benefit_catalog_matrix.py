from typing import Dict, List, Any

# Standardized Benefit Catalogs Mapping
# Evaluated against formula_evaluator context to derive dynamic pricing and coverage.
# Format: { insurer_key: { product_type: [ list of benefit definitions ] } }

BENEFIT_CATALOGS: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
    "qbe": {
        "private_car": [
            {
                "concept_key": "own-damage",
                "label": "Own Damage",
                "category": "default",
                "coverage_formula": "vehicle_sum_insured",
                "cost_formula": "0.00",
                "description": "Accidental collision, overturning, fire, explosion & theft protection."
            },
            {
                "concept_key": "towing",
                "label": "Emergency Towing Assistance",
                "category": "default",
                "coverage_formula": "200.00", # 200km or RM200 limit
                "cost_formula": "0.00",
                "description": "24/7 unlimited breakdown roadside towing to nearest authorized workshop."
            },
            {
                "concept_key": "windscreen",
                "label": "Windscreen Protection",
                "category": "addon",
                "coverage_formula": "windscreen_sum_insured",
                "cost_formula": "0.15 * windscreen_sum_insured",
                "description": "Repair & replacement of front, rear and all side door glass with 0% excess."
            },
            {
                "concept_key": "special-perils",
                "label": "Special Perils",
                "category": "addon",
                "coverage_formula": "vehicle_sum_insured",
                "cost_formula": "0.0025 * vehicle_sum_insured",
                "description": "Full protection against floods, typhoons, landslides, fallen trees & tempests."
            },
            {
                "concept_key": "legal-liability-to-passengers",
                "label": "Legal Liability to Passengers",
                "category": "addon",
                "coverage_formula": "statutory_unlimited",
                "cost_formula": "max(0.00, 5.00 * (total_seats - 1))",
                "description": "Legal protection against third-party negligence lawsuits by passengers."
            },
            {
                "concept_key": "legal-liability-of-passengers",
                "label": "Legal Liability of Passengers",
                "category": "addon",
                "coverage_formula": "statutory_limit",
                "cost_formula": "7.50",
                "description": "Protects you against legal liability incurred by your passengers."
            }
        ],
        "commercial_car": [],
        "motorcycle": [
            {
                "concept_key": "own-damage",
                "label": "Own Damage",
                "category": "default",
                "coverage_formula": "vehicle_sum_insured",
                "cost_formula": "0.00",
                "description": "Accidental collision, overturning, fire, explosion & theft protection."
            }
        ],
        "lorry": []
    },
    "etiqa": {
        "private_car": [
            {
                "concept_key": "own-damage",
                "label": "Own Damage",
                "category": "default",
                "coverage_formula": "vehicle_sum_insured",
                "cost_formula": "0.00",
                "description": "Accidental collision, overturning, fire, explosion & theft protection."
            },
            {
                "concept_key": "windscreen",
                "label": "Windscreen Protection",
                "category": "addon",
                "coverage_formula": "windscreen_sum_insured",
                "cost_formula": "0.15 * windscreen_sum_insured",
                "description": "Repair & replacement of front, rear and all side door glass with 0% excess."
            },
            {
                "concept_key": "special-perils",
                "label": "Special Perils",
                "category": "addon",
                "coverage_formula": "vehicle_sum_insured",
                "cost_formula": "0.0020 * vehicle_sum_insured", # Etiqa might have 0.20% instead of 0.25%
                "description": "Full protection against floods, typhoons, landslides, fallen trees & tempests."
            }
        ]
    }
}

def get_catalog_for_product(insurer: str, product_type: str) -> List[Dict[str, Any]]:
    """
    Retrieve the standard benefits mapping for a specific insurer and product.
    If the exact product type doesn't exist, fallback to private_car.
    """
    insurer_catalog = BENEFIT_CATALOGS.get(insurer.lower())
    if not insurer_catalog:
        return []
    
    # Simple normalizer for product type
    pt_normalized = product_type.lower()
    if "motorcycle" in pt_normalized or "bike" in pt_normalized:
        return insurer_catalog.get("motorcycle", insurer_catalog.get("private_car", []))
    elif "commercial" in pt_normalized or "company" in pt_normalized:
        return insurer_catalog.get("commercial_car", insurer_catalog.get("private_car", []))
    elif "lorry" in pt_normalized or "truck" in pt_normalized:
        return insurer_catalog.get("lorry", insurer_catalog.get("commercial_car", []))
        
    return insurer_catalog.get("private_car", [])
