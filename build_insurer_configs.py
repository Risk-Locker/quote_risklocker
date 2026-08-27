import json

BASE_CAR_DEFAULTS = [
    {"concept_key": "own-damage", "display_value": "Comprehensive accidental damage, fire, theft", "price": 0},
    {"concept_key": "third-party-bi", "display_value": "Unlimited third-party injury & death", "price": 0},
    {"concept_key": "third-party-property", "display_value": "Third-party property damage up to RM 3M", "price": 0},
    {"concept_key": "towing", "display_value": "24/7 Roadside towing & breakdown assistance", "price": 0},
    {"concept_key": "betterment-protection", "display_value": "Betterment scale deduction protection", "price": 0},
    {"concept_key": "legal-costs-defense", "display_value": "Traffic court legal defense costs", "price": 0},
]

BASE_CAR_ADDONS = [
    {"concept_key": "windscreen", "display_value": "Windscreen & glass replacement without NCD loss", "price": 0},
    {"concept_key": "special-perils", "display_value": "Full flood, storm & natural disasters", "price": 0},
    {"concept_key": "strike-riot-civil-commotion", "display_value": "Strike, riot and civil commotion (SRCC)", "price": 0},
    {"concept_key": "legal-liability-to-passengers", "display_value": "Legal Liability to Passengers (LLTP)", "price": 0},
    {"concept_key": "legal-liability-of-passengers", "display_value": "Legal Liability of Passengers (LLOP)", "price": 0},
    {"concept_key": "repair-allowance", "display_value": "Compensation for Assessed Repair Time (CART)", "price": 0},
    {"concept_key": "vehicle-accessories", "display_value": "Non-standard accessories & multimedia", "price": 0},
    {"concept_key": "e-hailing-extension", "display_value": "E-Hailing commercial private hire", "price": 0},
    {"concept_key": "all-drivers", "display_value": "All unnamed drivers authorization", "price": 0},
]

BASE_MC_DEFAULTS = [
    {"concept_key": "own-damage", "display_value": "Accidental collision, fire, theft", "price": 0},
    {"concept_key": "third-party-bi", "display_value": "Unlimited third-party bodily injury and death", "price": 0},
    {"concept_key": "third-party-property", "display_value": "Third-party property damage coverage up to RM3,000,000", "price": 0},
    {"concept_key": "betterment-protection", "display_value": "Tariff motorcycle betterment scale", "price": 0},
    {"concept_key": "legal-costs-defense", "display_value": "Court legal defense costs coverage up to RM2,000", "price": 0}
]

BASE_MC_ADDONS = [
    {"concept_key": "special-perils", "display_value": "Full flood, typhoon, landslide", "price": 0},
    {"concept_key": "strike-riot-civil-commotion", "display_value": "Strike, riot and civil commotion", "price": 0},
    {"concept_key": "all-drivers", "display_value": "Extends policy coverage to any authorized licensed rider", "price": 0}
]

# We build a function to clone these lists and add/override items
def build_product(p_key, p_name, segment, vehicle, defaults, addons):
    return {
        "product_key": p_key,
        "product_name": p_name,
        "segment_key": segment,
        "vehicle_key": vehicle,
        "coverage_key": "comprehensive",
        "default_benefits": defaults,
        "addons": addons
    }

configs = []

# 1. AmAssurance
am_lite_defaults = BASE_CAR_DEFAULTS.copy()
am_plus_defaults = am_lite_defaults + [
    {"concept_key": "all-drivers", "display_value": "Waives RM400 unnamed driver excess", "price": 0},
    {"concept_key": "flood-relief-allowance", "display_value": "Immediate flood assistance cash", "price": 0},
    {"concept_key": "key-replacement", "display_value": "Lost/stolen smart key reimbursement", "price": 0},
    {"concept_key": "personal-belongings-theft", "display_value": "In-car snatch theft compensation", "price": 0},
    {"concept_key": "ambulance-fees", "display_value": "Emergency medical ambulance reimbursement", "price": 0},
]
am_premier_defaults = am_plus_defaults + [
    {"concept_key": "out-of-pocket-allowance", "display_value": "Total loss lifestyle cash payout", "price": 0},
]
configs.append({
    "company_slug": "amassurance",
    "company_name": "AmAssurance",
    "products": [
        build_product("amassurance-auto365-lite", "Auto365 Comprehensive Lite", "private", "car", am_lite_defaults, BASE_CAR_ADDONS),
        build_product("amassurance-auto365-plus", "Auto365 Comprehensive Plus", "private", "car", am_plus_defaults, BASE_CAR_ADDONS),
        build_product("amassurance-auto365-premier", "Auto365 Comprehensive Premier", "private", "car", am_premier_defaults, BASE_CAR_ADDONS),
        build_product("amassurance-motorcycle-standard", "Standard Motorcycle Comprehensive", "private", "motorcycle", BASE_MC_DEFAULTS, BASE_MC_ADDONS)
    ]
})

# 2. Berjaya Sompo
configs.append({
    "company_slug": "berjayasompo",
    "company_name": "Berjaya Sompo",
    "products": [
        build_product("berjayasompo-private-car", "Private Car Comprehensive", "private", "car", BASE_CAR_DEFAULTS, BASE_CAR_ADDONS),
        build_product("berjayasompo-motorcycle", "Motorcycle Comprehensive", "private", "motorcycle", BASE_MC_DEFAULTS, BASE_MC_ADDONS)
    ]
})

# 3. Etiqa
etiqa_defaults = BASE_CAR_DEFAULTS + [
    {"concept_key": "all-drivers", "display_value": "All unnamed drivers authorization", "price": 0},
    {"concept_key": "towing", "display_value": "24/7 Roadside towing (200km)", "price": 0},
]
configs.append({
    "company_slug": "etiqa",
    "company_name": "Etiqa",
    "products": [
        build_product("etiqa-private-car", "Etiqa Private Car Comprehensive", "private", "car", etiqa_defaults, BASE_CAR_ADDONS),
        build_product("etiqa-motorcycle", "Etiqa Motorcycle Comprehensive", "private", "motorcycle", BASE_MC_DEFAULTS, BASE_MC_ADDONS)
    ]
})

# 4. Lonpac
configs.append({
    "company_slug": "lonpac",
    "company_name": "Lonpac",
    "products": [
        build_product("lonpac-private-car", "Lonpac Private Car Comprehensive", "private", "car", BASE_CAR_DEFAULTS, BASE_CAR_ADDONS),
        build_product("lonpac-motorcycle", "Lonpac Motorcycle Comprehensive", "private", "motorcycle", BASE_MC_DEFAULTS, BASE_MC_ADDONS)
    ]
})

# 5. QBE
configs.append({
    "company_slug": "qbe",
    "company_name": "QBE",
    "products": [
        build_product("qbe-private-car", "QBE Private Car Comprehensive", "private", "car", BASE_CAR_DEFAULTS, BASE_CAR_ADDONS),
        build_product("qbe-motorcycle", "QBE Motorcycle Comprehensive", "private", "motorcycle", BASE_MC_DEFAULTS, BASE_MC_ADDONS)
    ]
})

# 6. STMB
stmb_defaults = BASE_CAR_DEFAULTS + [
    {"concept_key": "all-drivers", "display_value": "All unnamed drivers authorization", "price": 0},
]
configs.append({
    "company_slug": "stmb",
    "company_name": "STMB",
    "products": [
        build_product("stmb-private-car", "STMB Private Car Comprehensive", "private", "car", stmb_defaults, BASE_CAR_ADDONS),
        build_product("stmb-motorcycle", "STMB Motorcycle Comprehensive", "private", "motorcycle", BASE_MC_DEFAULTS, BASE_MC_ADDONS)
    ]
})

# 7. Tune Protect
tune_defaults = BASE_CAR_DEFAULTS + [
    {"concept_key": "flood-relief-allowance", "display_value": "Compassionate Flood Relief", "price": 0},
]
configs.append({
    "company_slug": "tune-protect",
    "company_name": "Tune Protect",
    "products": [
        build_product("tune-protect-motor-easy", "Tune Protect Motor Easy", "private", "car", tune_defaults, BASE_CAR_ADDONS),
        build_product("tune-protect-motorcycle", "Tune Protect Motorcycle", "private", "motorcycle", BASE_MC_DEFAULTS, BASE_MC_ADDONS)
    ]
})

out_code = "INSURER_CONFIGS = " + repr(configs)

with open("commands/generated_insurer_configs.py", "w", encoding="utf-8") as f:
    f.write(out_code)

print("Generated commands/generated_insurer_configs.py")
