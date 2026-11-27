"""Database-driven underwriter betterment and towing policy rules resolver.

Reads `InsuranceCompany.policy_rules` JSONB seeded by Migration 082 first,
with canonical dictionary lookup by insurer slug/name only when a synthetic
unit-test row or session-less helper call lacks DB rules.
"""

from __future__ import annotations

from typing import Any

DEFAULT_BETTERMENT_RULE: dict[str, Any] = {
    "auto_waive_without_peril": False,
    "allow_addon_purchase": True,
    "free_exemption_years": 5,
    "max_waiver_years": 10,
    "default_display": "Up to 10 Years",
    "free_display": "Up to 5 Years",
}

DEFAULT_COMPANY_POLICY_RULES: dict[str, dict[str, Any]] = {
    "mmip": {
        "allowed_coverage_types": ["third_party"],
        "betterment": {
            "auto_waive_without_peril": False,
            "allow_addon_purchase": False,
            "free_exemption_years": 0,
            "max_waiver_years": 0,
            "default_display": "No",
            "free_display": "No",
        },
        "towing": {"metric": "none", "base_limit": "No towing"},
    },
    "qbe": {
        "betterment": {
            "auto_waive_without_peril": True,
            "allow_addon_purchase": False,
            "free_exemption_years": 10,
            "max_waiver_years": 10,
            "default_display": "Up to 10 Years",
            "free_display": "Up to 10 Years",
        },
        "towing": {
            "metric": "RM",
            "base_limit": "RM 500",
            "tariff_limit": "RM 200",
            "allowed_rm_values": [200, 300, 400, 500],
            "unlimited_label": "Unlimited - Plan 1",
            "unlimited_triggers": [
                "dpa",
                "dpp",
                "driver plus",
                "driver plus plan",
                "driver passenger protector",
                "driver & passenger protector",
                "driver and passenger protector",
                "endorsement n4",
                "end n4",
                "end. n4",
                "n4",
                "unlimited auto assistance",
                "mestari assist upgrade",
                "private car protector dpa",
            ],
            "raw_ext_unlimited_triggers": ["dpa", "dpp", "n4", "driver plus", "unlimited auto assistance"],
            "respect_universal_unlimited": False,
        },
    },
    "etiqa": {
        "betterment": {"auto_waive_without_peril": False, "allow_addon_purchase": True, "free_exemption_years": 5, "max_waiver_years": 10, "default_display": "Up to 10 Years", "free_display": "Up to 5 Years"},
        "towing": {
            "metric": "km",
            "base_limit": "200 km",
            "unlimited_label": "Unlimited",
            "unlimited_triggers": [
                "driver passenger protection",
                "driver & passenger protection",
                "driver and passenger protection",
                "driver passenger protector",
                "driver & passenger pa",
                "dpp",
                "driver plan 1",
                "driver plan 2",
                "driver plan 3",
                "oto 360",
                "oto360",
                "oto-360",
                "oto premier",
            ],
            "raw_ext_unlimited_triggers": ["driver passenger", "dpp", "driver plan", "oto 360", "oto360"],
            "respect_universal_unlimited": False,
        },
    },
    "takaful-malaysia": {
        "betterment": {"auto_waive_without_peril": False, "allow_addon_purchase": True, "free_exemption_years": 5, "max_waiver_years": 10, "default_display": "Up to 10 Years", "free_display": "Up to 5 Years"},
        "towing": {
            "metric": "km",
            "base_limit": "50 km",
            "upgrade_triggers": [
                "motor pa plus",
                "motor pa+",
                "pa plus",
                "tele bantuan plus",
                "pa+",
                "motor pa plan",
                "motor pa",
            ],
            "raw_ext_upgrade_triggers": ["pa plus", "pa+", "motor pa"],
            "plan_limits": {"plan 1": "100 km", "plan 2": "200 km", "plan 3": "300 km", "plan 4": "Unlimited"},
        },
    },
    "lonpac": {
        "betterment": {"auto_waive_without_peril": False, "allow_addon_purchase": True, "free_exemption_years": 5, "max_waiver_years": 10, "default_display": "Up to 10 Years", "free_display": "Up to 5 Years"},
        "towing": {
            "metric": "RM",
            "base_limit": "RM 400",
            "tariff_limit": "RM 200",
            "sdpa_plan1_limit": "RM 600",
            "allowed_rm_values": [200, 300, 400, 600],
            "sdpa_triggers": [
                "sdpa",
                "sdpa plus",
                "sdpa+",
                "secure driver",
                "secure driver & passenger",
                "secure driver and passenger",
                "e-assist smart driver",
                "smart driver",
            ],
            "raw_ext_sdpa_triggers": ["sdpa", "smart driver"],
            "unlimited_triggers": ["e-assist smart driver", "sdpa", "plan 2", "ev plan"],
        },
    },
    "berjaya-sompo": {
        "betterment": {"auto_waive_without_peril": False, "allow_addon_purchase": True, "free_exemption_years": 5, "max_waiver_years": 10, "default_display": "Up to 10 Years", "free_display": "Up to 5 Years"},
        "towing": {
            "metric": "Unlimited",
            "base_limit": "Unlimited",
            "tariff_limit": "RM 200",
            "tariff_exclude_brand_keywords": ["sompo motor", "n-hancer"],
        },
    },
    "tune-protect": {
        "betterment": {"auto_waive_without_peril": False, "allow_addon_purchase": True, "free_exemption_years": 5, "max_waiver_years": 10, "default_display": "Up to 10 Years", "free_display": "Up to 5 Years"},
        "towing": {
            "metric": "RM",
            "base_limit": "RM 300",
            "allowed_rm_values": [200, 300, 400],
            "unlimited_triggers": [
                "autobuddy",
                "auto buddy",
                "motor pa autobuddy",
                "motor shield",
                "motorshield",
                "motor easy bundle",
            ],
            "raw_ext_unlimited_triggers": ["autobuddy", "motor shield", "motorshield", "motor easy bundle"],
        },
    },
    "amassurance": {
        "betterment": {"auto_waive_without_peril": False, "allow_addon_purchase": True, "free_exemption_years": 5, "max_waiver_years": 10, "default_display": "Up to 10 Years", "free_display": "Up to 5 Years"},
        "towing": {
            "metric": "km",
            "base_limit": "100 km",
            "lite_limit": "50 km",
            "premier_limit": "365 km",
            "tpft_premier_limit": "200 km",
            "sdpa_triggers": ["private car 365", "pc 365", "pc365", "365 plan"],
            "sdpa_plan1_limit": "600 km",
            "unlimited_triggers": ["amdrive plus"],
        },
    },
    "kurnia": {
        "betterment": {"auto_waive_without_peril": False, "allow_addon_purchase": True, "free_exemption_years": 5, "max_waiver_years": 10, "default_display": "Up to 10 Years", "free_display": "Up to 5 Years"},
        "towing": {
            "metric": "km",
            "base_limit": "100 km",
            "lite_limit": "50 km",
            "premier_limit": "365 km",
            "tpft_premier_limit": "200 km",
            "sdpa_triggers": ["private car 365", "pc 365", "pc365", "365 plan"],
            "sdpa_plan1_limit": "600 km",
            "unlimited_triggers": ["amdrive plus", "auto assist plus", "auto assist premier"],
        },
    },
    "allianz": {
        "betterment": {"auto_waive_without_peril": False, "allow_addon_purchase": True, "free_exemption_years": 5, "max_waiver_years": 10, "default_display": "Up to 10 Years", "free_display": "Up to 5 Years"},
        "towing": {
            "metric": "km",
            "base_limit": "150 km",
            "unlimited_triggers": ["road rangers"],
        },
    },
    "liberty": {
        "betterment": {"auto_waive_without_peril": False, "allow_addon_purchase": True, "free_exemption_years": 5, "max_waiver_years": 10, "default_display": "Up to 10 Years", "free_display": "Up to 5 Years"},
        "towing": {
            "metric": "km",
            "base_limit": "100 km",
            "lite_limit": "50 km",
            "premier_limit": "365 km",
            "tpft_premier_limit": "200 km",
            "sdpa_triggers": ["private car 365", "pc 365", "pc365", "365 plan"],
            "sdpa_plan1_limit": "600 km",
            "unlimited_triggers": ["amdrive plus"],
        },
    },
    "zurich": {
        "betterment": {"auto_waive_without_peril": False, "allow_addon_purchase": True, "free_exemption_years": 5, "max_waiver_years": 10, "default_display": "Up to 10 Years", "free_display": "Up to 5 Years"},
        "towing": {"metric": "km", "base_limit": "150 km"},
    },
}

_NAME_TO_RULE_KEY: tuple[tuple[tuple[str, ...], str], ...] = (
    (("mmip", "motor insurance pool"), "mmip"),
    (("qbe",), "qbe"),
    (("etiqa", "maybank"), "etiqa"),
    (("takaful malaysia", "syarikat takaful", "stmb"), "takaful-malaysia"),
    (("lonpac",), "lonpac"),
    (("sompo", "berjaya"), "berjaya-sompo"),
    (("tune",), "tune-protect"),
    (("amassurance", "amgen", "amgeneral"), "amassurance"),
    (("kurnia",), "kurnia"),
    (("allianz",), "allianz"),
    (("liberty",), "liberty"),
    (("zurich",), "zurich"),
)


def _match_rule_key(company_name: str | None) -> str | None:
    comp = (company_name or "").strip().lower()
    if not comp:
        return None
    for tokens, rule_key in _NAME_TO_RULE_KEY:
        if any(tok in comp for tok in tokens):
            return rule_key
    return None


def resolve_company_policy_rules(
    company_name: str | None = None,
    company_obj: Any = None,
) -> dict[str, Any]:
    """Return merged policy_rules dict (DB InsuranceCompany.policy_rules takes precedence)."""
    db_rules = getattr(company_obj, "policy_rules", None) if company_obj is not None else None
    key = _match_rule_key(getattr(company_obj, "slug", None) or getattr(company_obj, "name", None) or company_name)
    base_rules = dict(DEFAULT_COMPANY_POLICY_RULES.get(key or "", {}))
    if isinstance(db_rules, dict) and db_rules:
        merged = dict(base_rules)
        for section, payload in db_rules.items():
            if isinstance(payload, dict) and isinstance(merged.get(section), dict):
                merged[section] = {**merged[section], **payload}
            else:
                merged[section] = payload
        return merged
    return base_rules


def resolve_company_betterment_policy(
    company_name: str | None = None,
    company_obj: Any = None,
) -> dict[str, Any]:
    """Return full DB-first betterment policy configuration for an underwriter."""
    rules = resolve_company_policy_rules(company_name=company_name, company_obj=company_obj)
    bet = rules.get("betterment") if isinstance(rules.get("betterment"), dict) else {}
    auto_waive = bool(bet.get("auto_waive_without_peril", DEFAULT_BETTERMENT_RULE["auto_waive_without_peril"]))
    allow_addon_purchase = bool(
        bet.get("allow_addon_purchase", not auto_waive)
    )
    max_years = int(bet.get("max_waiver_years", DEFAULT_BETTERMENT_RULE["max_waiver_years"]))
    if max_years <= 0:
        allow_addon_purchase = False
    free_years_default = max_years if auto_waive else (5 if max_years > 0 else 0)
    free_exemption_years = int(bet.get("free_exemption_years", free_years_default))
    default_disp = str(
        bet.get("default_display")
        or ("No" if max_years <= 0 else f"Up to {max_years} Years")
    )
    if default_disp.strip().lower() == "n/a (third party)":
        default_disp = "No"
    free_disp = str(
        bet.get("free_display")
        or (default_disp if auto_waive else ("No" if free_exemption_years <= 0 else f"Up to {free_exemption_years} Years"))
    )
    return {
        "auto_waive_without_peril": auto_waive,
        "allow_addon_purchase": allow_addon_purchase,
        "free_exemption_years": max(0, free_exemption_years),
        "max_waiver_years": max(0, max_years),
        "default_display": default_disp,
        "free_display": free_disp,
    }


def resolve_company_betterment_rule(
    company_name: str | None = None,
    company_obj: Any = None,
) -> tuple[bool, int, str]:
    """Return `(auto_waive_without_peril, max_waiver_years, default_display)`."""
    pol = resolve_company_betterment_policy(company_name=company_name, company_obj=company_obj)
    return (
        bool(pol["auto_waive_without_peril"]),
        int(pol["max_waiver_years"]),
        str(pol["default_display"]),
    )


def resolve_company_towing_rule(
    company_name: str | None = None,
    company_obj: Any = None,
) -> dict[str, Any]:
    """Return DB-first `policy_rules['towing']` config merged over fallback defaults."""
    rules = resolve_company_policy_rules(company_name=company_name, company_obj=company_obj)
    towing = rules.get("towing") if isinstance(rules.get("towing"), dict) else {}
    return dict(towing)
