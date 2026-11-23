"""Level-2 Vehicle Online Search Grounding & PostgreSQL Knowledge Cache.

Resolves ambiguous Malaysian vehicle classifications (Private Car vs Commercial Lorry,
Saloon vs NonSaloonCar, ICE Petrol/Diesel vs EV BEV, insurer product tier) using:
1. Persistent VehicleModel.grounding_meta DB cache (zero external cost on repeat models).
2. Gemini Live Google Search (`tools=[{"google_search": {}}]`) on cache miss.
3. Deterministic tariff-safe fallback when offline or unkeyed.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.extraction.entity_classifier import is_private_passenger_class
from app.models.tables import AccountStatus, VehicleBrand, VehicleModel

logger = logging.getLogger(__name__)

VEHICLE_GROUNDING_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "vehicle_category": {
            "type": "STRING",
            "enum": ["Car", "NonSaloonCar", "SUV", "MPV", "Lorry", "Van", "Bus", "Motorcycle"],
        },
        "powertrain": {
            "type": "STRING",
            "enum": ["ICE", "EV", "Hybrid"],
        },
        "malaysian_tariff_class": {
            "type": "STRING",
            "enum": ["Private Car", "Commercial Vehicle", "Motorcycle"],
        },
        "product_tier_confirmed": {"type": "STRING"},
        "confidence": {"type": "NUMBER"},
        "citations": {"type": "ARRAY", "items": {"type": "STRING"}},
        "reasoning": {"type": "STRING"},
    },
    "required": ["vehicle_category", "powertrain", "malaysian_tariff_class", "confidence", "reasoning"],
}

_PASSENGER_BODY_MAP = {
    "car": "Car",
    "saloon": "Car",
    "sedan": "Car",
    "hatchback": "Car",
    "nonsalooncar": "NonSaloonCar",
    "non-saloon": "NonSaloonCar",
    "suv": "NonSaloonCar",
    "mpv": "NonSaloonCar",
    "crossover": "NonSaloonCar",
    "pickup": "NonSaloonCar",
}
_COMMERCIAL_BODY_MAP = {
    "lorry": "Lorry",
    "truck": "Lorry",
    "prime mover": "Lorry",
    "tipper": "Lorry",
    "van": "Van",
    "bus": "Bus",
    "motorcycle": "Motorcycle",
}
_NON_EV_PASSENGER_CATEGORIES = {"Car", "NonSaloonCar", "SUV", "MPV"}


def _normalize_token(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).upper()


def _spec_cache_key(engine_cc: str | None, vehicle_class: str | None) -> str:
    cc_norm = re.sub(r"[^A-Z0-9]+", "", _normalize_token(engine_cc))
    cls_norm = "PRIVATE" if is_private_passenger_class(vehicle_class) else re.sub(r"[^A-Z0-9]+", "", _normalize_token(vehicle_class))[:16]
    return f"{cc_norm or 'GENERIC'}::{cls_norm or 'ANY'}"


def _normalize_vehicle_category(raw_category: str | None, vehicle_class: str | None) -> str:
    cleaned = re.sub(r"[^a-z]+", "", (raw_category or "").lower())
    if cleaned in _PASSENGER_BODY_MAP:
        mapped = _PASSENGER_BODY_MAP[cleaned]
    elif cleaned in _COMMERCIAL_BODY_MAP:
        mapped = _COMMERCIAL_BODY_MAP[cleaned]
    else:
        mapped = "Car"

    # Authoritative legal tariff class overrides body misclassification when explicit Private Car class is declared.
    if is_private_passenger_class(vehicle_class) and mapped in {"Lorry", "Van", "Bus"}:
        return "NonSaloonCar"
    return mapped


def _lookup_cached_model(db: Session | None, car_brand: str | None, car_model: str | None) -> VehicleModel | None:
    if db is None or not car_model:
        return None
    norm_model = _normalize_token(car_model)
    norm_brand = _normalize_token(car_brand)

    try:
        query = db.query(VehicleModel).filter(VehicleModel.status == AccountStatus.ACTIVE.value)
        if norm_brand:
            brand_row = (
                db.query(VehicleBrand)
                .filter(func.upper(VehicleBrand.name) == norm_brand)
                .first()
            )
            if brand_row:
                query = query.filter(VehicleModel.brand_id == brand_row.id)

        candidates = query.all()
        for row in candidates:
            row_name = _normalize_token(row.name)
            row_aliases = {_normalize_token(a) for a in (row.aliases or []) if a}
            if norm_model == row_name or norm_model in row_aliases or f"{norm_brand} {norm_model}".strip() in row_aliases:
                return row
        return None
    except Exception as exc:
        logger.debug("VehicleModel cache lookup skipped safely: %s", exc)
        return None


def _persist_grounding_cache(
    db: Session | None,
    *,
    model_row: VehicleModel | None,
    car_brand: str | None,
    car_model: str | None,
    spec_key: str,
    normalized_payload: dict[str, Any],
) -> None:
    if db is None:
        return
    try:
        with db.begin_nested():
            target = model_row
            if target is None and car_model:
                brand_id = None
                if car_brand:
                    brand = (
                        db.query(VehicleBrand)
                        .filter(func.upper(VehicleBrand.name) == _normalize_token(car_brand))
                        .first()
                    )
                    if brand is None:
                        brand = VehicleBrand(name=_normalize_token(car_brand), aliases=[car_brand.strip()])
                        db.add(brand)
                        db.flush()
                    brand_id = brand.id
                target = VehicleModel(
                    brand_id=brand_id,
                    name=car_model.strip(),
                    aliases=[alias for alias in {_normalize_token(car_model), f"{_normalize_token(car_brand)} {_normalize_token(car_model)}".strip()} if alias],
                )
                db.add(target)
                db.flush()

            if target is None or not hasattr(target, "grounding_meta"):
                return

            meta = dict(getattr(target, "grounding_meta", None) or {})
            entries = dict(meta.get("entries") or {})
            entries[spec_key] = normalized_payload
            meta.update(normalized_payload)
            meta["entries"] = entries
            target.grounding_meta = meta
            db.flush()
    except Exception as exc:
        logger.debug("VehicleModel grounding cache persist skipped safely: %s", exc)


def _build_query_prompt(
    *,
    car_brand: str | None,
    car_model: str | None,
    engine_cc: str | None,
    vehicle_class: str | None,
    product_name: str | None,
) -> str:
    return (
        "Verify Malaysian JPJ / PIAM motor insurance classification for this vehicle.\n"
        f"- Make / Brand: {car_brand or 'Unknown'}\n"
        f"- Model: {car_model or 'Unknown'}\n"
        f"- Engine / Weight Spec: {engine_cc or 'Unknown'}\n"
        f"- Quotation Vehicle Class: {vehicle_class or 'Unknown'}\n"
        f"- Insurer Product Name: {product_name or 'Unknown'}\n\n"
        "Search authoritative Malaysia specs and classify accurately:\n"
        "1) vehicle_category: Car (saloon/sedan/hatch), NonSaloonCar (SUV/MPV/crossover/pickup), Lorry, Van, Bus, or Motorcycle.\n"
        "2) powertrain: ICE (petrol/diesel), EV (pure electric battery), or Hybrid.\n"
        "3) malaysian_tariff_class: Private Car, Commercial Vehicle, or Motorcycle.\n"
        "4) product_tier_confirmed: confirmed insurer plan tier if mentioned (e.g. auto365 Comprehensive Plus).\n"
        "5) Include official Malaysia manufacturer/insurer citations and high-precision reasoning."
    )


def _deterministic_fallback(
    *,
    engine_cc: str | None,
    vehicle_class: str | None,
    product_name: str | None,
    extracted_vehicle_type: str | None,
) -> dict[str, Any]:
    spec_upper = _normalize_token(engine_cc)
    is_ev_hint = bool(re.search(r"\bKW\b", spec_upper) or re.search(r"\(\s*EV\s*\)", _normalize_token(product_name)))
    is_heavy = bool(re.search(r"\bKG\b|\bTON", spec_upper)) and not is_private_passenger_class(vehicle_class)
    if is_heavy:
        vt = "Lorry"
        tariff = "Commercial Vehicle"
    elif is_ev_hint:
        vt = extracted_vehicle_type if extracted_vehicle_type in {"Car", "NonSaloonCar"} else "Car"
        tariff = "Private Car"
    else:
        vt = _normalize_vehicle_category(extracted_vehicle_type, vehicle_class)
        tariff = "Commercial Vehicle" if vt in {"Lorry", "Van", "Bus"} else ("Motorcycle" if vt == "Motorcycle" else "Private Car")

    return {
        "vehicle_type": vt,
        "powertrain": "EV" if is_ev_hint else "ICE",
        "tariff_class": tariff,
        "product_tier_confirmed": product_name or "",
        "confidence": 0.72,
        "citations": [],
        "reasoning": "Deterministic JPJ tariff fallback (offline / unkeyed).",
        "source": "deterministic_fallback",
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }


def _try_clear_deterministic_grounding(
    *,
    car_brand: str | None,
    car_model: str | None,
    engine_cc: str | None,
    vehicle_class: str | None,
    product_name: str | None,
    extracted_vehicle_type: str | None,
) -> dict[str, Any] | None:
    """Fast-path deterministic classification when PDF specs are already unambiguous."""
    spec_upper = _normalize_token(engine_cc)
    vtype_norm = (extracted_vehicle_type or "").strip()
    is_ev_hint = bool(re.search(r"\bKW\b|\bW\b", spec_upper) or re.search(r"\(\s*EV\s*\)", _normalize_token(product_name)))
    is_weight = bool(re.search(r"\bKG\b|\bTON", spec_upper))
    is_cc = bool(re.search(r"\b(\d{3,4}(?:\.\d+)?)\s*CC\b", spec_upper))

    # Case A: Unambiguous Passenger Car (Private Car class + explicit CC/kW + non-commercial type)
    if (
        is_private_passenger_class(vehicle_class, engine_cc, f"{car_brand or ''} {car_model or ''}".strip())
        and (is_cc or is_ev_hint)
        and vtype_norm not in {"Lorry", "Truck", "Commercial", "EVCommercial"}
    ):
        vt = vtype_norm if vtype_norm in {"Car", "NonSaloonCar", "EVSaloonCar", "EVNonSaloonCar"} else "Car"
        return {
            "vehicle_type": vt,
            "powertrain": "EV" if is_ev_hint else "ICE",
            "tariff_class": "Private Car",
            "product_tier_confirmed": product_name or "",
            "confidence": 0.92,
            "citations": [],
            "reasoning": "Clear JPJ Private Car classification from unambiguous vehicle_class & capacity.",
            "source": "deterministic_clear",
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }

    # Case B: Unambiguous Heavy Commercial Vehicle (KG/TON capacity + Lorry/EVCommercial type)
    if is_weight and not is_private_passenger_class(vehicle_class) and vtype_norm in {"Lorry", "EVCommercial"}:
        return {
            "vehicle_type": vtype_norm,
            "powertrain": "EV" if (vtype_norm == "EVCommercial" or is_ev_hint) else "ICE",
            "tariff_class": "Commercial Vehicle",
            "product_tier_confirmed": product_name or "",
            "confidence": 0.92,
            "citations": [],
            "reasoning": "Clear JPJ Commercial Vehicle classification from weight capacity (KG/TON).",
            "source": "deterministic_clear",
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }

    return None


def resolve_vehicle_level2_grounding(
    *,
    db: Session | None = None,
    car_brand: str | None = None,
    car_model: str | None = None,
    engine_cc: str | None = None,
    vehicle_class: str | None = None,
    product_name: str | None = None,
    extracted_vehicle_type: str | None = None,
    search_fn: Callable[..., dict[str, Any] | None] | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Resolve Level-2 vehicle classification via DB cache first, then Gemini Google Search."""
    spec_key = _spec_cache_key(engine_cc, vehicle_class)
    model_row = _lookup_cached_model(db, car_brand, car_model)

    if model_row is not None and not force_refresh:
        meta = dict(getattr(model_row, "grounding_meta", None) or {})
        entries = meta.get("entries") or {}
        cached = entries.get(spec_key) if isinstance(entries, dict) else None
        if not isinstance(cached, dict) and meta.get("vehicle_type"):
            cached = meta
        if isinstance(cached, dict) and cached.get("vehicle_type"):
            return {
                **cached,
                "source": "vehicle_model_cache",
            }

    if search_fn is None and not force_refresh:
        clear_result = _try_clear_deterministic_grounding(
            car_brand=car_brand,
            car_model=car_model,
            engine_cc=engine_cc,
            vehicle_class=vehicle_class,
            product_name=product_name,
            extracted_vehicle_type=extracted_vehicle_type,
        )
        if clear_result is not None:
            return clear_result

    caller = search_fn
    if caller is None:
        from app.extraction.gemini_extractor import call_gemini_grounded_search

        caller = call_gemini_grounded_search

    raw_response: dict[str, Any] | None = None
    if car_model or car_brand:
        try:
            prompt = _build_query_prompt(
                car_brand=car_brand,
                car_model=car_model,
                engine_cc=engine_cc,
                vehicle_class=vehicle_class,
                product_name=product_name,
            )
            raw_response = caller(query_prompt=prompt, response_schema=VEHICLE_GROUNDING_SCHEMA)
        except Exception as exc:
            logger.warning("Level-2 search caller failed cleanly; using fallback: %s", exc)
            raw_response = None

    if isinstance(raw_response, dict) and raw_response.get("vehicle_category"):
        vt = _normalize_vehicle_category(raw_response.get("vehicle_category"), vehicle_class)
        tariff = "Private Car" if vt in _NON_EV_PASSENGER_CATEGORIES else str(raw_response.get("malaysian_tariff_class") or "Commercial Vehicle")
        payload = {
            "vehicle_type": vt,
            "powertrain": str(raw_response.get("powertrain") or "ICE").upper(),
            "tariff_class": tariff,
            "product_tier_confirmed": str(raw_response.get("product_tier_confirmed") or product_name or ""),
            "confidence": float(raw_response.get("confidence") or 0.9),
            "citations": list(raw_response.get("citations") or []),
            "reasoning": str(raw_response.get("reasoning") or ""),
            "source": "online_google_search",
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }
        _persist_grounding_cache(
            db,
            model_row=model_row,
            car_brand=car_brand,
            car_model=car_model,
            spec_key=spec_key,
            normalized_payload=payload,
        )
        return payload

    return _deterministic_fallback(
        engine_cc=engine_cc,
        vehicle_class=vehicle_class,
        product_name=product_name,
        extracted_vehicle_type=extracted_vehicle_type,
    )


def apply_level2_grounding_to_fields(
    fields: dict[str, Any],
    grounding: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    """Apply high-confidence Level-2 grounded classification onto draft fields without clobbering manual overrides."""
    if not isinstance(fields, dict) or not isinstance(grounding, dict):
        return fields, []
    updated = dict(fields)
    notices: list[str] = []

    vt = grounding.get("vehicle_type")
    powertrain = grounding.get("powertrain")
    tariff = grounding.get("tariff_class")
    conf = float(grounding.get("confidence") or 0.0)

    def _cur(key: str) -> str:
        node = updated.get(key)
        if isinstance(node, dict):
            return str(node.get("value") or "").strip()
        return str(node or "").strip()

    if vt and conf >= 0.7:
        cur_vt = _cur("vehicle_type")
        is_manual = isinstance(updated.get("vehicle_type"), dict) and str(updated["vehicle_type"].get("source") or "") == "manual"
        if not is_manual and cur_vt != vt:
            updated["vehicle_type"] = {
                **(updated.get("vehicle_type") if isinstance(updated.get("vehicle_type"), dict) else {}),
                "value": vt,
                "status": "ready",
                "confidence": round(max(conf, 0.9), 2),
                "source": f"level2_{grounding.get('source', 'grounding')}",
            }
            notices.append(
                f"Level-2 Vehicle Grounding ({grounding.get('source')}): reclassified vehicle_type from '{cur_vt or 'Empty'}' to '{vt}'."
            )

    if powertrain:
        updated["powertrain"] = {
            **(updated.get("powertrain") if isinstance(updated.get("powertrain"), dict) else {}),
            "value": powertrain,
            "status": "ready",
            "confidence": round(max(conf, 0.85), 2),
            "source": f"level2_{grounding.get('source', 'grounding')}",
        }
    if tariff and not _cur("tariff_class"):
        updated["tariff_class"] = {
            "value": tariff,
            "status": "ready",
            "confidence": round(max(conf, 0.85), 2),
            "source": f"level2_{grounding.get('source', 'grounding')}",
        }
    return updated, notices


def _extract_field_str(fields: dict[str, Any], key: str) -> str:
    node = fields.get(key)
    if isinstance(node, dict):
        return str(node.get("value") or "").strip()
    return str(node or "").strip()


def run_level2_grounding_gate(
    *,
    db: Session | None,
    fields: dict[str, Any],
    raw_text: str = "",
    search_fn: Callable[..., dict[str, Any] | None] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """Run Eye-1 Referee + Eye-2 Online Vehicle Grounding + re-reconcile coherently.

    Shared single path used by both `extraction_worker.py` and `session_rescan_service.py`.
    """
    from app.extraction.referee import audit_and_reconcile_draft

    initial_vt = _extract_field_str(fields, "vehicle_type")
    updated, notices = audit_and_reconcile_draft(fields, raw_text=raw_text)
    prior_vt = _extract_field_str(updated, "vehicle_type")

    grounding = resolve_vehicle_level2_grounding(
        db=db,
        car_brand=_extract_field_str(updated, "car_brand"),
        car_model=_extract_field_str(updated, "car_model"),
        engine_cc=_extract_field_str(updated, "engine_cc"),
        vehicle_class=_extract_field_str(updated, "vehicle_class"),
        product_name=_extract_field_str(updated, "product_name"),
        extracted_vehicle_type=prior_vt,
        search_fn=search_fn,
    )
    updated, l2_notices = apply_level2_grounding_to_fields(updated, grounding)
    notices.extend(l2_notices)

    new_vt = _extract_field_str(updated, "vehicle_type")
    # If Eye-1 or Eye-2 reclassified a passenger vehicle wrongly marked as Lorry, restore road tax / fee flags cleanly.
    if initial_vt == "Lorry" and new_vt in {"Car", "NonSaloonCar"}:
        updated["include_road_tax"] = {"value": "true", "status": "ready", "message": ""}
        updated["include_runner_fee"] = {"value": "true", "status": "ready", "message": ""}

    if new_vt != prior_vt:
        updated, extra_notices = audit_and_reconcile_draft(updated, raw_text=raw_text)
        for note in extra_notices:
            if note not in notices:
                notices.append(note)

    return updated, grounding, notices


def finalize_catalog_and_3eye_gate(
    *,
    db: Session,
    draft: Any,
    grounding: dict[str, Any] | None,
    raw_text: str = "",
    record: Any | None = None,
    company_resolution: dict[str, Any] | None = None,
    pin_catalog_fn: Callable[[Session, Any], dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Pin active insurer catalog and run the 3-Eye extraction consensus gate."""
    from app.extraction.visual_referee import audit_extraction_3_eye_consensus
    from app.services.catalog_review_service import initialize_catalog_review

    catalog_ctx: dict[str, Any] = {}
    if getattr(draft, "company_id", None):
        pinner = pin_catalog_fn or initialize_catalog_review
        catalog_ctx = pinner(db, draft) or {}

    three_eye = audit_extraction_3_eye_consensus(
        fields=getattr(draft, "fields", None) or {},
        grounding=grounding,
        catalog_context=catalog_ctx,
        raw_text=raw_text,
    )

    if three_eye.get("status") != "PASS":
        existing_warnings = list(getattr(draft, "warnings", None) or [])
        for note in three_eye.get("findings") or []:
            tag = f"3-Eye Audit: {note}"
            if tag not in existing_warnings:
                existing_warnings.append(tag)
        draft.warnings = existing_warnings

    merged_resolution = dict(company_resolution if isinstance(company_resolution, dict) else (getattr(record, "company_resolution", None) or {}))
    merged_resolution["level2_grounding"] = grounding or {}
    merged_resolution["three_eye_consensus"] = three_eye
    if isinstance(company_resolution, dict):
        company_resolution.update(merged_resolution)
    if record is not None:
        record.company_resolution = merged_resolution

    return catalog_ctx, three_eye


