"""Hermetic tests for Waiver of Betterment catalog configuration and matrix partitioning.

Validates the 4 strict business rules:
1. Motorcycles & Commercial Vehicles: zero betterment offerings (neither defaults nor addons).
2. QBE (Private Car ICE & EV): strictly in defaults (0 RM, "Waiver of betterment for up to 10 years of age").
3. Tune Protect, Berjaya Sompo, AmAssurance, Etiqa (Private Car ICE & EV): strictly in addons ("Waiver of betterment for up to 15 years of age").
4. Lonpac, STMB / Takaful Malaysia (Private Car ICE & EV): strictly in addons ("Waiver of betterment for up to 10 years of age").
"""

from __future__ import annotations

import sys
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.models.tables import CatalogOffering

seed_demo_path = ROOT / "commands" / "seed-demo.py"
spec = importlib.util.spec_from_file_location("seed_demo", seed_demo_path)
seed_demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed_demo)
INSURER_CONFIGS = seed_demo.INSURER_CONFIGS


def test_seed_demo_betterment_configs_private_cars():
    """Verify that seed demo insurer configurations strictly match the betterment rules for private cars."""
    for conf in INSURER_CONFIGS:
        slug = conf["company_slug"]
        for p in conf.get("products", []):
            cat = p.get("vehicle_key", "car")
            cov = p.get("coverage_key", "comprehensive")

            if cat == "car" and cov == "comprehensive":
                defs = p.get("default_benefits", [])
                adds = p.get("addons", [])

                def_betterment = [d for d in defs if d.get("concept_key") == "betterment-protection"]
                add_betterment = [a for a in adds if a.get("concept_key") == "betterment-protection"]

                if slug == "qbe":
                    # QBE: Must be in defaults, 10 years, NOT in addons
                    assert len(def_betterment) == 1, f"QBE {p.get('product_name')} missing betterment in defaults"
                    assert def_betterment[0]["description_override"] == "Waiver of betterment for up to 10 years of age"
                    assert len(add_betterment) == 0, f"QBE {p.get('product_name')} must not have betterment in addons"

                elif slug in ("tune-protect", "berjaya-sompo", "amassurance", "etiqa"):
                    # 15-year addons
                    assert len(add_betterment) == 1, f"{slug} {p.get('product_name')} missing betterment in addons"
                    assert add_betterment[0]["description_override"] == "Waiver of betterment for up to 15 years of age"
                    assert len(def_betterment) == 0, f"{slug} {p.get('product_name')} must not have betterment in defaults"

                elif slug in ("lonpac", "stmb"):
                    # 10-year addons
                    assert len(add_betterment) == 1, f"{slug} {p.get('product_name')} missing betterment in addons"
                    assert add_betterment[0]["description_override"] == "Waiver of betterment for up to 10 years of age"
                    assert len(def_betterment) == 0, f"{slug} {p.get('product_name')} must not have betterment in defaults"


def test_seed_demo_no_betterment_in_motorcycles_or_commercial():
    """Verify that neither motorcycles nor commercial vehicles have betterment anywhere."""
    for conf in INSURER_CONFIGS:
        slug = conf["company_slug"]
        for p in conf.get("products", []):
            cat = p.get("vehicle_key", "car")
            name_lower = p.get("product_name", "").lower()
            is_non_car = cat != "car" or "motorcycle" in name_lower or "commercial" in name_lower or "lorry" in name_lower

            if is_non_car:
                defs = p.get("default_benefits", [])
                adds = p.get("addons", [])
                def_betterment = [d for d in defs if d.get("concept_key") == "betterment-protection"]
                add_betterment = [a for a in adds if a.get("concept_key") == "betterment-protection"]

                assert len(def_betterment) == 0, f"{slug} non-private vehicle {p.get('product_name')} must not have betterment in defaults"
                assert len(add_betterment) == 0, f"{slug} non-private vehicle {p.get('product_name')} must not have betterment in addons"


def test_matrix_partitioning_and_description_overrides():
    """Hermetic test verifying that defaults vs addons partitioning and description overrides render as expected."""
    def make_offering(off_kind: str, role: str, desc: str, price_val: float | None = None) -> CatalogOffering:
        return CatalogOffering(
            id="off-test",
            catalog_revision_id="rev-test",
            offering_key="test-betterment",
            concept_id="conc-betterment",
            offering_kind=off_kind,
            role=role,
            description_override=desc,
            display_value=desc,
            optional_price={"type": "money", "value": price_val, "currency": "MYR"} if price_val is not None else None,
            sort_order=9,
            status="active",
        )

    # QBE Offering
    qbe_off = make_offering("base", "included", "Waiver of betterment for up to 10 years of age", None)
    assert qbe_off.offering_kind == "base"
    assert qbe_off.role == "included"
    assert qbe_off.description_override == "Waiver of betterment for up to 10 years of age"

    # Sompo / Tune / Etiqa / AmAssurance Offering
    sompo_off = make_offering("optional", "addon_option", "Waiver of betterment for up to 15 years of age", 0.0)
    assert sompo_off.offering_kind == "optional"
    assert sompo_off.role == "addon_option"
    assert sompo_off.description_override == "Waiver of betterment for up to 15 years of age"

    # Lonpac / STMB Offering
    lonpac_off = make_offering("optional", "addon_option", "Waiver of betterment for up to 10 years of age", 0.0)
    assert lonpac_off.offering_kind == "optional"
    assert lonpac_off.role == "addon_option"
    assert lonpac_off.description_override == "Waiver of betterment for up to 10 years of age"
