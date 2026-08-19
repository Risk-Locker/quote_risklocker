"""Vehicle catalog matching and CC inference service for Malaysia motor insurance."""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import VehicleBrand, VehicleModel


logger = logging.getLogger(__name__)

CATALOG_PATH = Path(__file__).resolve().parents[3] / "fix" / "malaysia_vehicle_brand_model_cc_1995_2026.json"

# Common CC multipliers / engine badge regexes
# Examples: "2.5", "1.5L", "1.3 VVT", "150 CC", "125CC", "2.0G", "2.4V", "3.5 V6", "1.8 E"
_CC_LITRE_RE = re.compile(r"\b([1-9]\.[0-9])\s*(?:l|litre|liter|vvt|vti|turbo|tgdi|tsi|gdi|v|g|e|s|x)?\b", re.IGNORECASE)
_CC_DIRECT_RE = re.compile(r"\b([0-9]{3,4})\s*(?:cc|c\.c\.)\b", re.IGNORECASE)


@lru_cache(maxsize=1)
def load_vehicle_catalog() -> list[dict[str, Any]]:
    """Load and cache the curated Malaysian vehicle make-model-cc master."""
    if not CATALOG_PATH.exists():
        logger.warning("Vehicle catalog JSON not found at %s", CATALOG_PATH)
        return []
    try:
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        return data.get("vehicles", [])
    except Exception as exc:
        logger.warning("Failed to load vehicle catalog: %s", exc)
        return []


def infer_vehicle_cc_and_type(car_model_text: str | None) -> tuple[int | None, str]:
    """
    Infer engine displacement (CC) and vehicle type (Car, Motorcycle, Lorry)
    from vehicle model description, registration text or catalog match.
    """
    if not car_model_text or not car_model_text.strip():
        return None, "Car"

    text = car_model_text.strip()
    norm_text = text.upper()

    # Detect Vehicle Type
    vehicle_type = "Car"
    motorcycle_keywords = ["YAMAHA", "HONDA MOTOR", "MODENAS", "SYM", "KAWASAKI", "SUZUKI MOTOR", "KTM", "DUCATI", "BENELLI", "VESPA", "Y15", "Y16", "NVX", "RS150", "VARIO", "LC135", "EX5"]
    lorry_keywords = ["LORRY", "TRUCK", "ISUZU NPR", "ISUZU ELF", "HINO", "FUSO", "CANTER", "DAIHATSU DELTA", "VOLVO TRUCK", "SCANIA", "PRIME MOVER"]

    if any(k in norm_text for k in motorcycle_keywords):
        vehicle_type = "Motorcycle"
    elif any(k in norm_text for k in lorry_keywords):
        vehicle_type = "Lorry"

    # 1. Check direct CC in text (e.g. "1798 CC", "2494CC", "150CC")
    direct_match = _CC_DIRECT_RE.search(text)
    if direct_match:
        try:
            return int(direct_match.group(1)), vehicle_type
        except ValueError:
            pass

    # 2. Check litre displacement in text (e.g. "2.5", "1.5", "1.8", "2.0")
    litre_match = _CC_LITRE_RE.search(text)
    if litre_match:
        try:
            litres = float(litre_match.group(1))
            # Standard displacement mappings for common Malaysian engine sizes
            mapped_cc = {
                1.0: 998,
                1.2: 1197,
                1.3: 1329,
                1.4: 1395,
                1.5: 1496,
                1.6: 1598,
                1.8: 1798,
                2.0: 1998,
                2.2: 2198,
                2.4: 2362,
                2.5: 2494,
                2.8: 2755,
                3.0: 2997,
                3.5: 3456,
            }.get(litres, int(litres * 1000))
            return mapped_cc, vehicle_type
        except ValueError:
            pass

    # 3. Match against Malaysian Vehicle Catalog
    vehicles = load_vehicle_catalog()
    best_match_cc: int | None = None
    max_score = 0

    tokens = set(re.findall(r"\w+", norm_text))
    for item in vehicles:
        model_name = str(item.get("model", "")).upper()
        brand_name = str(item.get("brand", "")).upper()
        cc_val = item.get("cc")
        if not cc_val:
            continue

        model_tokens = set(re.findall(r"\w+", model_name))
        brand_tokens = set(re.findall(r"\w+", brand_name))

        # Check overlap
        matched_model = model_tokens.issubset(tokens) if model_tokens else False
        matched_brand = brand_tokens.issubset(tokens) if brand_tokens else False

        score = (2 if matched_brand else 0) + (3 if matched_model else 0)
        if score > max_score and score >= 3:
            max_score = score
            best_match_cc = int(cc_val)
            vtype_raw = str(item.get("vehicle_type", "")).lower()
            if vtype_raw == "bike":
                vehicle_type = "Motorcycle"
            elif vtype_raw == "lorry":
                vehicle_type = "Lorry"
            elif vtype_raw == "car":
                vehicle_type = "Car"

    if best_match_cc:
        return best_match_cc, vehicle_type

    return None, vehicle_type


def seed_vehicle_catalog_to_db(db: Session, max_records: int = 2000) -> dict[str, int]:
    """Seed brands and models from the Malaysian master catalog into the database."""
    vehicles = load_vehicle_catalog()
    if not vehicles:
        return {"brands_seeded": 0, "models_seeded": 0}

    # Group models by brand
    brands_map: dict[str, list[dict[str, Any]]] = {}
    for item in vehicles:
        brand = (item.get("brand") or "").strip().upper()
        if not brand:
            continue
        brands_map.setdefault(brand, []).append(item)

    brands_seeded = 0
    models_seeded = 0

    for brand_name, model_list in brands_map.items():
        brand_obj = db.scalar(select(VehicleBrand).where(VehicleBrand.name == brand_name))
        if not brand_obj:
            brand_obj = VehicleBrand(name=brand_name, aliases=[brand_name, brand_name.capitalize()])
            db.add(brand_obj)
            db.flush()
            brands_seeded += 1

        # Seed distinct models for this brand
        seen_models: set[str] = set()
        for item in model_list:
            model_name = (item.get("model") or "").strip().upper()
            if not model_name or model_name in seen_models:
                continue
            seen_models.add(model_name)

            existing_model = db.scalar(
                select(VehicleModel).where(
                    VehicleModel.brand_id == brand_obj.id,
                    VehicleModel.name == model_name,
                )
            )
            if not existing_model:
                aliases = [model_name]
                cc = item.get("cc")
                if cc:
                    aliases.append(f"{model_name} {cc}CC")
                db.add(VehicleModel(brand_id=brand_obj.id, name=model_name, aliases=aliases))
                models_seeded += 1

    if brands_seeded > 0 or models_seeded > 0:
        db.commit()

    return {"brands_seeded": brands_seeded, "models_seeded": models_seeded}
