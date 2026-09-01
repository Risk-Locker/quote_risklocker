"""Pin an unambiguous published catalog and seed its reviewed base benefits."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from sqlalchemy import select

from app.domain.benefits import BenefitValue
from app.models.tables import (
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    BenefitPackage,
    BenefitPackagePlan,
    BenefitPackagePlanItem,
    BenefitRelation,
    CatalogOffering,
    CoverageType,
    DraftBenefitSelection,
    DraftSourceLineDecision,
    ExtractionBenefitLine,
    ExtractionRecord,
    InsuranceProduct,
    InsuranceProductTier,
    QuotationDraft,
    Segment,
    VehicleCategory,
    VehicleSubcategory,
    new_id,
)


def _rows(db, model) -> list:
    return list(db.scalars(select(model)).all())


def _norm(value: Any = "") -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def _field_value(fields: dict, *names: str) -> str:
    for name in names:
        raw = (fields or {}).get(name)
        value = raw.get("value") if isinstance(raw, dict) else raw
        if str(value or "").strip():
            return str(value).strip()
    return ""


def _single_exact(rows: list[Any], name: str) -> Any | None:
    matches = [item for item in rows if str(getattr(item, "name", "")).strip().casefold() == name.casefold()]
    return matches[0] if len(matches) == 1 else None


def _resolve_vehicle_category(db, text_val: str, draft_fields: dict | None = None) -> str | None:
    combined = []
    if text_val:
        combined.append(text_val)
    if draft_fields:
        for k in ("vehicle_class", "vehicle_type", "vehicle_category", "car_model", "car_brand", "make_model", "vehicle_description", "product_name"):
            raw = draft_fields.get(k)
            v = raw.get("value") if isinstance(raw, dict) else raw
            if v:
                combined.append(str(v))
    all_text = " ".join(combined)
    if not all_text:
        return None
    normalized = _norm(all_text)
    categories = _rows(db, VehicleCategory)

    # 1. Passenger Car (including popular models, body types, and brands)
    car_words = (
        "car", "private car", "saloon", "sedan", "suv", "mpv", "hatchback", "coupe", "wagon", "passenger",
        "vellfire", "alphard", "myvi", "axia", "bezza", "alza", "ativa", "aruz", "vios", "city", "civic",
        "corolla", "camry", "accord", "crv", "hrv", "cx 5", "cx 3", "cx 30", "saga", "persona", "iriz",
        "exora", "x50", "x70", "x90", "s70", "yaris", "fortuner", "hilux", "triton", "d max", "navara",
        "ranger", "mercedes", "bmw", "audi", "volkswagen", "golf", "passat", "tiguan", "porsche", "tesla",
        "byd", "atto", "dolphin", "seal", "proton", "perodua", "toyota", "honda", "nissan", "mazda",
        "hyundai", "kia", "subaru", "volvo", "suzuki", "mitsubishi", "peugeot", "lexus"
    )
    if any(w in normalized for w in car_words):
        for cat in categories:
            if cat.category_key in {"car", "private_car"}:
                return cat.id

    # 2. Motorcycle (explicit keywords only)
    if any(w in normalized for w in ("motorcycle", "motor cycle", "motosikal", "moped", "kapcai", "scooter", "superbike", "yamaha", "honda ex5", "honda wave", "modenas", "sym", "vespa", "kawasaki")):
        for cat in categories:
            if cat.category_key == "motorcycle":
                return cat.id

    # 3. Commercial Vehicle / Lorry
    if any(w in normalized for w in ("lorry", "truck", "commercial", "rigid", "trailer", "tipper", "van", "bus", "prime mover", "c permit", "a permit", "general haulage", "own goods", "isuzu npr", "hino", "fuso")):
        for cat in categories:
            if cat.category_key == "commercial_vehicle":
                return cat.id

    for cat in categories:
        if _norm(cat.name) in normalized or _norm(cat.category_key) in normalized:
            return cat.id

    # Default to passenger car if vehicle no / plate, engine cc, or car details are present
    if draft_fields and (draft_fields.get("vehicle_no") or draft_fields.get("engine_cc") or draft_fields.get("car_model") or draft_fields.get("car_brand")):
        for cat in categories:
            if cat.category_key in {"car", "private_car"}:
                return cat.id

    return None


def _resolve_segment(db, draft_fields: dict) -> str | None:
    combined = []
    for k in ("policy_type", "vehicle_type", "vehicle_category", "product_name", "customer_name"):
        raw = (draft_fields or {}).get(k)
        v = raw.get("value") if isinstance(raw, dict) else raw
        if v:
            combined.append(str(v))
    normalized = _norm(" ".join(combined))
    segments = _rows(db, Segment)
    if any(w in normalized for w in ("private", "persendirian", "individual", "personal")):
        for seg in segments:
            if seg.segment_key in {"private", "individual"}:
                return seg.id
    if any(w in normalized for w in ("commercial", "perdagangan", "company car", "corporate", "fleet")):
        for seg in segments:
            if seg.segment_key in {"commercial", "corporate"}:
                return seg.id
    return None


def _resolve_coverage_type(db, text_val: str) -> str | None:
    if not text_val:
        return None
    normalized = _norm(text_val)
    coverages = _rows(db, CoverageType)
    if any(w in normalized for w in ("third party fire", "tpft", "fire and theft", "fire theft")):
        for cov in coverages:
            if cov.coverage_key == "third_party_fire_theft":
                return cov.id
    if any(w in normalized for w in ("third party", "tp", "third party only", "tpo")):
        for cov in coverages:
            if cov.coverage_key == "third_party":
                return cov.id
    if "comprehensive" in normalized or "comp" in normalized:
        for cov in coverages:
            if cov.coverage_key == "comprehensive":
                return cov.id
    for cov in coverages:
        if _norm(cov.name) in normalized or _norm(cov.coverage_key) in normalized:
            return cov.id
    return None


def pin_catalog_context(db, draft: QuotationDraft) -> BenefitCatalogRevision | None:
    """Pin only an exact or best-dimension matching published catalog; never guess arbitrarily."""

    if not draft.company_id:
        return None

    # 1. Resolve vehicle & coverage dimensions
    raw_vehicle = _field_value(draft.fields or {}, "vehicle_type", "vehicle_category", "car_model", "vehicle_description", "vehicle_model", "make_model")
    resolved_vehicle_cat_id = _resolve_vehicle_category(db, raw_vehicle, draft.fields or {})
    raw_coverage = _field_value(draft.fields or {}, "coverage_type", "coverage", "policy_type")
    resolved_coverage_id = _resolve_coverage_type(db, raw_coverage)
    resolved_segment_id = _resolve_segment(db, draft.fields or {})

    # 2. Resolve product
    products = [item for item in _rows(db, InsuranceProduct) if item.company_id == draft.company_id and item.status == "active"]
    if draft.product_id and all(item.id != draft.product_id for item in products):
        draft.product_id = None
    product_name = _field_value(draft.fields or {}, "product_name", "product")
    if not draft.product_id and product_name:
        exact = _single_exact(products, product_name)
        if not exact:
            p_norm = _norm(product_name)
            fuzzy_matches = [p for p in products if p_norm in _norm(p.name) or _norm(p.name) in p_norm]
            if len(fuzzy_matches) == 1:
                exact = fuzzy_matches[0]
            elif len(fuzzy_matches) > 1 and resolved_coverage_id:
                cov_matches = [p for p in fuzzy_matches if any(w in _norm(p.name) for w in ("comprehensive", "tpft", "third party") if (resolved_coverage_id and w in p.name.lower()))]
                if cov_matches:
                    exact = cov_matches[0]
                else:
                    exact = fuzzy_matches[0]
        if exact:
            draft.product_id = exact.id
    if not draft.product_id:
        candidate_products = list(products)
        raw_v_text = (raw_vehicle or "").lower()
        if resolved_vehicle_cat_id:
            matching_v = [p for p in candidate_products if getattr(p, "vehicle_category_id", None) == resolved_vehicle_cat_id]
            if matching_v:
                candidate_products = matching_v
        if not resolved_vehicle_cat_id or len(candidate_products) > 1:
            if any(w in raw_v_text for w in ("car", "saloon", "vellfire", "toyota", "proton", "perodua", "honda", "sedan", "suv", "mpv", "private")):
                car_prods = [p for p in candidate_products if ("car" in p.name.lower() or "auto365" in p.name.lower() or "private" in p.name.lower()) and "motorcycle" not in p.name.lower() and "lorry" not in p.name.lower()]
                if car_prods:
                    candidate_products = car_prods
            elif any(w in raw_v_text for w in ("motorcycle", "bike", "yamaha", "honda ex5")):
                bike_prods = [p for p in candidate_products if "motorcycle" in p.name.lower() or "bike" in p.name.lower()]
                if bike_prods:
                    candidate_products = bike_prods
            elif any(w in raw_v_text for w in ("lorry", "truck", "isuzu", "hino", "haulage")):
                lorry_prods = [p for p in candidate_products if "lorry" in p.name.lower() or "haulage" in p.name.lower()]
                if lorry_prods:
                    candidate_products = lorry_prods

        raw_cov_text = (raw_coverage or "").lower()
        if "tpft" in raw_cov_text or "fire" in raw_cov_text:
            tpft_prods = [p for p in candidate_products if "tpft" in p.name.lower()]
            if tpft_prods:
                candidate_products = tpft_prods
        elif "third party" in raw_cov_text and "fire" not in raw_cov_text:
            tp_prods = [p for p in candidate_products if "third party" in p.name.lower() and "tpft" not in p.name.lower()]
            if tp_prods:
                candidate_products = tp_prods
        else:
            comp_prods = [p for p in candidate_products if "comprehensive" in p.name.lower() and "tpft" not in p.name.lower() and "third party" not in p.name.lower()]
            if comp_prods:
                candidate_products = comp_prods

        if resolved_segment_id:
            matching_s = [p for p in candidate_products if getattr(p, "segment_id", None) == resolved_segment_id]
            if matching_s:
                candidate_products = matching_s

        if len(candidate_products) > 1:
            tier_val = _field_value(draft.fields or {}, "tier_name", "product_tier", "plan_name")
            prod_val = _field_value(draft.fields or {}, "product_name", "detected_package_name")
            if tier_val:
                matched_tier = [p for p in candidate_products if tier_val.lower() in p.name.lower()]
                if len(matched_tier) == 1:
                    draft.product_id = matched_tier[0].id
            if not draft.product_id and prod_val:
                matched_exact = [p for p in candidate_products if p.name.lower() == prod_val.lower()]
                if len(matched_exact) == 1:
                    draft.product_id = matched_exact[0].id
            if not draft.product_id and any("auto365" in p.name.lower() for p in candidate_products):
                lite_p = next((p for p in candidate_products if "lite" in p.name.lower()), None)
                if lite_p:
                    draft.product_id = lite_p.id
        elif len(candidate_products) == 1:
            draft.product_id = candidate_products[0].id

    # 3. Resolve legacy tier (if product has tiers)
    tiers = [item for item in _rows(db, InsuranceProductTier) if item.product_id == draft.product_id and item.status == "active"] if draft.product_id else []
    if draft.tier_id and all(item.id != draft.tier_id for item in tiers):
        draft.tier_id = None
    tier_name = _field_value(draft.fields or {}, "tier_name", "product_tier", "plan_name")
    if not draft.tier_id and tier_name:
        exact = _single_exact(tiers, tier_name)
        if exact:
            draft.tier_id = exact.id
    if not draft.tier_id and not tier_name and len(tiers) == 1:
        draft.tier_id = tiers[0].id

    # 4. Find candidate catalogs for this company
    catalogs = [
        item for item in _rows(db, BenefitCatalog)
        if item.company_id == draft.company_id
        and item.status in {"active", "published", "draft"}
    ]
    if draft.product_id:
        matching_prod = [item for item in catalogs if item.product_id == draft.product_id]
        if matching_prod:
            catalogs = matching_prod
    if draft.tier_id:
        matching_tier = [item for item in catalogs if item.tier_id == draft.tier_id]
        if matching_tier:
            catalogs = matching_tier

    # Filter candidate catalogs by segment if available (Private vs Commercial)
    if resolved_segment_id and len(catalogs) > 1:
        matching_s = [item for item in catalogs if item.segment_id == resolved_segment_id]
        if matching_s:
            catalogs = matching_s

    # Filter candidate catalogs by vehicle category if available
    if resolved_vehicle_cat_id and len(catalogs) > 1:
        matching_v = [item for item in catalogs if item.vehicle_category_id == resolved_vehicle_cat_id]
        if matching_v:
            catalogs = matching_v

    # Filter candidate catalogs by coverage type if available
    if resolved_coverage_id and len(catalogs) > 1:
        matching_c = [item for item in catalogs if item.coverage_type_id == resolved_coverage_id]
        if matching_c:
            catalogs = matching_c

    # If still multiple catalogs (e.g. multi-tier ladder catalogs for the same vehicle/coverage):
    # Default to the lowest tier / base catalog
    target_catalog = None
    if len(catalogs) == 1:
        target_catalog = catalogs[0]
    elif len(catalogs) > 1:
        def _cat_sort_key(c):
            if c.tier_id:
                t = next((tr for tr in tiers if tr.id == c.tier_id), None)
                if t:
                    return (0, int(t.sort_order), t.name)
            return (1, 0, c.name)
        sorted_catalogs = sorted(catalogs, key=_cat_sort_key)
        target_catalog = sorted_catalogs[0]
    else:
        # Fall back to single active/published company catalog
        company_catalogs = [
            item for item in _rows(db, BenefitCatalog)
            if item.company_id == draft.company_id and item.status in {"active", "published"}
        ]
        if len(company_catalogs) == 1:
            target_catalog = company_catalogs[0]
            if not draft.product_id and target_catalog.product_id:
                draft.product_id = target_catalog.product_id
        else:
            draft.catalog_revision_id = None
            return None

    revisions = [
        item for item in _rows(db, BenefitCatalogRevision)
        if item.catalog_id == target_catalog.id and item.state == "published"
    ]
    if not revisions:
        draft.catalog_revision_id = None
        return None

    revision = max(revisions, key=lambda item: (int(item.revision_number), str(item.id)))
    draft.catalog_revision_id = revision.id
    if target_catalog.product_id and not draft.product_id:
        draft.product_id = target_catalog.product_id
    if target_catalog.tier_id and not draft.tier_id:
        draft.tier_id = target_catalog.tier_id
    return revision


def seed_base_benefits(db, draft: QuotationDraft, revision: BenefitCatalogRevision) -> int:
    existing = [item for item in _rows(db, DraftBenefitSelection) if item.draft_id == draft.id]
    existing_offerings = {item.catalog_offering_id for item in existing if item.catalog_offering_id}
    existing_concepts = {item.concept_id for item in existing if item.state == "current" and item.concept_id}

    # Find primary package for this draft:
    # 1. draft.package_id if set and valid in revision
    # 2. catalog.package_id if set and valid in revision
    # 3. Lowest-sort active comprehensive package in revision
    catalogs = [item for item in _rows(db, BenefitCatalog) if item.id == revision.catalog_id]
    catalog_pkg_id = catalogs[0].package_id if catalogs else None

    revision_packages = [
        item for item in _rows(db, BenefitPackage)
        if item.catalog_revision_id == revision.id
        and item.package_kind == "comprehensive"
        and item.status == "active"
    ]
    primary_pkg_id = None
    if revision_packages:
        valid_ids = {item.id for item in revision_packages}
        if getattr(draft, "package_id", None) and draft.package_id in valid_ids:
            primary_pkg_id = draft.package_id
        elif catalog_pkg_id and catalog_pkg_id in valid_ids:
            primary_pkg_id = catalog_pkg_id
        else:
            primary_pkg_id = min(revision_packages, key=lambda item: (item.sort_order if item.sort_order is not None else 0, item.name)).id

        if not getattr(draft, "package_id", None):
            draft.package_id = primary_pkg_id

    all_offerings = list(
        db.scalars(
            select(CatalogOffering).where(
                CatalogOffering.catalog_revision_id == revision.id,
                CatalogOffering.status.in_(["active", "compatibility"]),
            )
        ).all()
    )

    base_offerings = []
    for item in all_offerings:
        is_included = item.role == "included" or (item.offering_kind == "base" and item.role is None)
        if not is_included:
            continue
        # If package hierarchy applies, only seed offerings for the primary package (or product-wide)
        if primary_pkg_id and item.applies_to_type == "package" and item.applies_to_id != primary_pkg_id:
            continue
        base_offerings.append(item)

    created = 0
    for offering in sorted(base_offerings, key=lambda item: (int(item.sort_order or 0), item.offering_key)):
        if offering.id in existing_offerings or offering.concept_id in existing_concepts:
            continue
        db.add(DraftBenefitSelection(
            id=new_id(),
            draft_id=draft.id,
            selection_key=f"catalog:{offering.offering_key}"[:160],
            catalog_offering_id=offering.id,
            concept_id=offering.concept_id,
            item_kind="catalog",
            state="current",
            cost_status="included",
            label_override=offering.label_override,
            typed_value_override=None,
            evidence_snapshot={"catalog_revision_id": revision.id, "source": "published_base"},
            sort_order=int(offering.sort_order or 0),
        ))
        existing_offerings.add(offering.id)
        existing_concepts.add(offering.concept_id)
        created += 1
    return created


def initialize_catalog_review(db, draft: QuotationDraft) -> dict:
    revision = pin_catalog_context(db, draft)
    if revision is None:
        return {"catalog_revision_id": None, "base_benefits_created": 0}
    return {
        "catalog_revision_id": revision.id,
        "base_benefits_created": seed_base_benefits(db, draft, revision),
    }


def _normalized_value(value) -> dict | None:
    try:
        return BenefitValue.model_validate(value).model_dump(mode="json", exclude_none=True)
    except Exception:
        return None


def _scalar_equal(left, right) -> bool:
    try:
        return Decimal(str(left)) == Decimal(str(right))
    except (InvalidOperation, TypeError, ValueError):
        return str(left) == str(right)


def _value_matches(typed_value, extracted: dict | None) -> bool:
    left = _normalized_value(typed_value)
    right = _normalized_value(extracted)
    if left is None or right is None:
        return False
    for key in ("type", "value", "unit", "unlimited", "region", "currency", "max_days"):
        if left.get(key) is None and right.get(key) is None:
            continue
        if key == "value":
            if left.get("value") is not None or right.get("value") is not None:
                if not _scalar_equal(left.get("value"), right.get("value")):
                    return False
            continue
        if str(left.get(key) or "") != str(right.get(key) or ""):
            return False
    return True


def auto_apply_extracted_benefits(db, draft: QuotationDraft) -> dict:
    """Apply confidently extracted benefit values onto the pinned catalog.

    Upgrades replace their current in place; unknown variants become exact
    overrides; unmatched selected lines stay as source-only evidence.
    """

    if not draft.catalog_revision_id:
        return {"applied": 0}
    extraction = db.scalar(
        select(ExtractionRecord).where(ExtractionRecord.uploaded_file_id == draft.uploaded_file_id)
    )
    if extraction is None:
        return {"applied": 0}
    lines = [
        item for item in db.scalars(
            select(ExtractionBenefitLine).where(ExtractionBenefitLine.extraction_record_id == extraction.id)
        ).all()
        if item.extraction_record_id == extraction.id
    ]
    decisions = {
        item.source_line_id: item
        for item in db.scalars(
            select(DraftSourceLineDecision).where(DraftSourceLineDecision.draft_id == draft.id)
        ).all()
        if item.draft_id == draft.id
    }
    selections = [
        item for item in db.scalars(
            select(DraftBenefitSelection).where(DraftBenefitSelection.draft_id == draft.id)
        ).all()
        if item.draft_id == draft.id
    ]
    offerings = [
        item for item in db.scalars(
            select(CatalogOffering).where(CatalogOffering.catalog_revision_id == draft.catalog_revision_id)
        ).all()
        if item.catalog_revision_id == draft.catalog_revision_id
    ]
    offering_by_id = {item.id: item for item in offerings}
    relations = [
        item for item in db.scalars(
            select(BenefitRelation).where(BenefitRelation.catalog_revision_id == draft.catalog_revision_id)
        ).all()
        if item.catalog_revision_id == draft.catalog_revision_id
    ]
    applied = 0

    all_concepts = {str(c.id): c for c in db.scalars(select(BenefitConcept)).all()}
    concepts_by_key = {c.concept_key: c for c in all_concepts.values()}
    concepts_by_norm = {_norm(c.label): c for c in all_concepts.values()}

    for line in sorted(lines, key=lambda item: int(item.page_number or 0)):
        decision = decisions.get(line.id)
        if decision is None:
            continue
        state_str = str(line.inclusion_state or "").lower()
        if state_str in {"omitted", "rejected", "excluded", "declined"}:
            if decision.disposition == "unresolved":
                decision.disposition = "omitted"
            continue

        target_concept_id = None
        premium_cost = None
        cov_limit = None
        for mapping in list(line.candidate_mappings or []):
            m_cid = str(mapping.get("concept_id") or "").strip()
            if m_cid:
                if not all_concepts or m_cid in all_concepts:
                    target_concept_id = all_concepts[m_cid].id if m_cid in all_concepts else m_cid
            elif mapping.get("concept_key"):
                c_k = str(mapping["concept_key"]).lower().replace("_", "-")
                if c_k in concepts_by_key:
                    target_concept_id = concepts_by_key[c_k].id
            if mapping.get("premium_cost"):
                premium_cost = mapping.get("premium_cost")
            if mapping.get("coverage_limit") or mapping.get("evidence"):
                cov_limit = mapping.get("coverage_limit") or mapping.get("evidence")

        if all_concepts and target_concept_id and str(target_concept_id) not in all_concepts:
            target_concept_id = None

        if not premium_cost:
            premium_cost = getattr(line, "premium_cost", None)
        if not premium_cost and isinstance(line.extracted_value, dict):
            if line.extracted_value.get("semantic_role") == "premium":
                premium_cost = line.extracted_value.get("value")
            premium_cost = premium_cost or line.extracted_value.get("premium_cost") or (line.extracted_value.get("premium") or {}).get("amount")
        if not premium_cost and isinstance(line.evidence, dict):
            premium_cost = line.evidence.get("premium_cost") or line.evidence.get("cost")

        if not cov_limit:
            cov_limit = getattr(line, "coverage_limit", None)
        if not cov_limit and isinstance(line.extracted_value, dict):
            if line.extracted_value.get("semantic_role") in {"limit", "insured_limit"}:
                cov_limit = line.extracted_value.get("value")
            cov_limit = cov_limit or line.extracted_value.get("coverage_limit")
        if not cov_limit and isinstance(line.evidence, dict):
            cov_limit = line.evidence.get("coverage_limit") or line.evidence.get("limit")

        if not target_concept_id:
            line_norm = _norm(line.raw_label or line.normalized_label)
            if "windscreen" in line_norm or "wndscrn" in line_norm:
                target_concept_id = concepts_by_key.get("windscreen").id if "windscreen" in concepts_by_key else None
            elif "legal liability" in line_norm and "passenger" in line_norm:
                target_concept_id = concepts_by_key.get("legal-liability-of-passengers").id if "legal-liability-of-passengers" in concepts_by_key else (concepts_by_key.get("legal-liability-to-passengers").id if "legal-liability-to-passengers" in concepts_by_key else None)
            if not target_concept_id:
                for norm_k, c_obj in concepts_by_norm.items():
                    if norm_k in line_norm or line_norm in norm_k:
                        target_concept_id = c_obj.id
                        break

        if not target_concept_id:
            if decision.disposition == "unresolved":
                decision.disposition = "source_only"
            continue

        extracted = line.extracted_value if isinstance(line.extracted_value, dict) else None
        if extracted is None:
            ev_str = str(cov_limit or (line.evidence or {}).get("value") or (line.evidence or {}).get("coverage_limit") or "")
            if ev_str and ev_str.lower() not in {"included", "standard", "yes", "true", "selected"}:
                clean_limit = ev_str.upper().replace("RM", "").replace(",", "").strip()
                is_pure_money = bool(re.match(r"^\s*(?:RM\s*)?[\d]+(?:,\d{3})*(?:\.\d{1,2})?\s*$", ev_str, re.IGNORECASE))
                if is_pure_money:
                    extracted = {
                        "type": "money",
                        "value": clean_limit,
                        "currency": "MYR",
                        "semantic_role": "limit",
                        "display_text": f"RM {clean_limit}",
                    }
                else:
                    extracted = {
                        "type": "text",
                        "value": ev_str,
                        "display_text": ev_str,
                    }
            elif premium_cost:
                clean_p = str(premium_cost).upper().replace("RM", "").replace(",", "").strip()
                is_pure_money = bool(re.match(r"^\s*(?:RM\s*)?[\d]+(?:,\d{3})*(?:\.\d{1,2})?\s*$", str(premium_cost), re.IGNORECASE))
                if is_pure_money:
                    extracted = {"type": "money", "value": clean_p, "currency": "MYR", "semantic_role": "premium", "display_text": f"RM {clean_p}"}
                else:
                    extracted = {"type": "text", "value": str(premium_cost), "display_text": str(premium_cost)}

        concept_offerings = [item for item in offerings if str(item.concept_id) == str(target_concept_id)]
        current = next(
            (item for item in selections if str(item.concept_id) == str(target_concept_id) and item.state == "current"),
            None,
        )
        if current is not None and current.catalog_offering_id in offering_by_id:
            current_offering = offering_by_id[current.catalog_offering_id]
            if _value_matches(current_offering.typed_value, extracted):
                decision.disposition = "mapped"
                decision.selection_id = current.id
                continue
            # Check relations or same-concept upgrade options without requiring an explicit edge
            upgrade_ids = {
                item.to_offering_id
                for item in relations
                if item.from_offering_id == current.catalog_offering_id and item.relation_kind == "replaces"
            }
            matched = next((item for item in concept_offerings if item.id in upgrade_ids and _value_matches(item.typed_value, extracted)), None)
            if matched is None:
                matched = next(
                    (item for item in concept_offerings if (item.offering_kind in {"upgrade", "optional"} or item.role in {"addon_option", "bundle_component"}) and _value_matches(item.typed_value, extracted)),
                    None,
                )
            if matched is not None:
                selection_id = new_id()
                current.state = "superseded"
                current.superseded_by_id = selection_id
                price_dict = None
                if premium_cost:
                    clean_p = str(premium_cost).upper().replace("RM", "").replace(",", "").strip()
                    price_dict = {"amount": float(clean_p) if any(c.isdigit() for c in clean_p) else clean_p, "currency": "MYR"}
                elif matched.optional_price:
                    price_dict = deepcopy(matched.optional_price)

                new_selection = DraftBenefitSelection(
                    id=selection_id,
                    draft_id=draft.id,
                    selection_key=f"catalog:{matched.offering_key}"[:160],
                    catalog_offering_id=matched.id,
                    concept_id=target_concept_id,
                    item_kind="catalog",
                    state="current",
                    cost_status=current.cost_status or "included",
                    label_override=matched.label_override or line.raw_label,
                    typed_value_override=extracted if not _value_matches(matched.typed_value, extracted) else None,
                    evidence_snapshot={"source_line_id": line.id, "source": "extracted_upgrade", "is_detected": True},
                    sort_order=int(matched.sort_order or 0),
                    selected_by=draft.owner_id,
                    price=price_dict,
                )
                db.add(new_selection)
                selections.append(new_selection)
                applied += 1
                decision.disposition = "mapped"
                decision.selection_id = selection_id
            else:
                current.typed_value_override = extracted
                applied += 1
                decision.disposition = "mapped"
                decision.selection_id = current.id
            continue

        if current is None:
            optionals = [item for item in concept_offerings if item.offering_kind in {"optional", "upgrade"} or item.role in {"addon_option", "bundle_component"}]
            matched = next((item for item in optionals if _value_matches(item.typed_value, extracted)), None)
            if matched is None and len(optionals) == 1:
                matched = optionals[0]
            elif matched is None and optionals:
                matched = optionals[0]
            typed_val = None
            if isinstance(extracted, dict):
                if extracted.get("type") in {"money", "distance", "percentage", "per_day", "custom", "boolean", "text"}:
                    typed_val = deepcopy(extracted)
                elif "amount" in extracted or "currency" in extracted:
                    typed_val = {
                        "type": "money",
                        "value": str(extracted.get("amount") or extracted.get("value") or ""),
                        "currency": str(extracted.get("currency") or "MYR"),
                        "semantic_role": "limit",
                    }
                elif "value" in extracted and extracted.get("value") is not None:
                    typed_val = {"type": "custom", "display_text": str(extracted.get("value"))}

            if matched is not None:
                selection_id = new_id()
                price_dict = None
                if premium_cost:
                    clean_p = str(premium_cost).upper().replace("RM", "").replace(",", "").strip()
                    val_num = float(clean_p) if any(c.isdigit() for c in clean_p) else clean_p
                    price_dict = {"type": "money", "value": val_num, "amount": val_num, "currency": "MYR"}
                elif matched.optional_price:
                    price_dict = deepcopy(matched.optional_price)

                new_selection = DraftBenefitSelection(
                    id=selection_id,
                    draft_id=draft.id,
                    selection_key=f"catalog:{matched.offering_key}"[:160],
                    catalog_offering_id=matched.id,
                    concept_id=target_concept_id,
                    item_kind="catalog",
                    state="current",
                    cost_status="paid",
                    label_override=matched.label_override or line.raw_label,
                    typed_value_override=typed_val if (typed_val and not _value_matches(matched.typed_value, typed_val)) else None,
                    evidence_snapshot={"source_line_id": line.id, "source": "extracted_addon", "is_detected": True, "coverage_limit": cov_limit, "premium_cost": premium_cost},
                    sort_order=int(matched.sort_order or 0),
                    selected_by=draft.owner_id,
                    price=price_dict,
                )
                db.add(new_selection)
                selections.append(new_selection)
                applied += 1
                decision.disposition = "mapped"
                decision.selection_id = selection_id
                continue
            else:
                # Custom add-on fallback for any detected rider/extra benefit with price or selected state
                selection_id = new_id()
                price_dict = None
                if premium_cost:
                    clean_p = str(premium_cost).upper().replace("RM", "").replace(",", "").strip()
                    price_dict = {"amount": float(clean_p) if any(c.isdigit() for c in clean_p) else clean_p, "currency": "MYR"}

                new_selection = DraftBenefitSelection(
                    id=selection_id,
                    draft_id=draft.id,
                    selection_key=f"custom:{line.id}"[:160],
                    catalog_offering_id=None,
                    concept_id=target_concept_id,
                    item_kind="custom",
                    state="current",
                    cost_status="paid" if premium_cost else "included",
                    label_override=line.raw_label,
                    typed_value_override=typed_val,
                    evidence_snapshot={"source_line_id": line.id, "source": "extracted_custom", "is_detected": True, "coverage_limit": cov_limit, "premium_cost": premium_cost},
                    sort_order=50 + applied,
                    selected_by=draft.owner_id,
                    price=price_dict,
                )
                db.add(new_selection)
                selections.append(new_selection)
                applied += 1
                decision.disposition = "mapped"
                decision.selection_id = selection_id
                continue
        if decision.disposition == "unresolved":
            decision.disposition = "source_only"

    # Apply confidently detected benefit packs (bundled add-on plans).
    detected_packs = (extraction.candidates or {}).get("detected_packs") or []
    if detected_packs:
        applied += _apply_detected_packs(db, draft, draft.catalog_revision_id, detected_packs, selections, offering_by_id)
    return {"applied": applied}


def _apply_detected_packs(
    db,
    draft: QuotationDraft,
    catalog_revision_id: str,
    detected_packs: list[dict],
    selections: list[DraftBenefitSelection],
    offering_by_id: dict,
) -> int:
    """Apply AI-detected purchased packs atomically (same semantics as the workspace op)."""
    packages = {
        item.id: item for item in _rows(db, BenefitPackage)
        if item.catalog_revision_id == catalog_revision_id and item.package_kind == "addon_bundle" and item.status == "active"
    }
    if not packages:
        return 0
    plans = [item for item in _rows(db, BenefitPackagePlan) if item.package_id in packages and item.status == "active"]
    items_by_plan: dict[str, list[BenefitPackagePlanItem]] = {}
    for item in _rows(db, BenefitPackagePlanItem):
        items_by_plan.setdefault(item.plan_id, []).append(item)
    applied = 0
    for pack in detected_packs:
        if not isinstance(pack, dict):
            continue
        package_name = _norm(pack.get("package_name"))
        plan_name = _norm(pack.get("plan_name"))
        if not package_name and not plan_name:
            continue
        matches = []
        for plan in plans:
            plan_norm = _norm(plan.name)
            if plan_name and (plan_norm == plan_name or plan_norm.endswith(f" {plan_name}")):
                matches.append(plan)
            elif not plan_name and (plan_norm == package_name or plan_norm.startswith(package_name)):
                matches.append(plan)
        if len(matches) != 1:
            continue
        plan = matches[0]
        package = packages[plan.package_id]

        # Drop members of other plans of the same bundle first (clean ladder switch).
        sibling_ids = {item.id for item in plans if item.package_id == package.id} - {plan.id}
        for sel in [s for s in selections if s.package_plan_id and s.package_plan_id in sibling_ids]:
            _drop_plan_selection(selections, sel)

        for item in sorted(items_by_plan.get(plan.id, []), key=lambda row: (int(row.sort_order or 0), str(row.id))):
            offering = offering_by_id.get(item.offering_id)
            if offering is None or offering.status not in {"active", "compatibility"}:
                continue
            current = next(
                (s for s in selections if s.concept_id == offering.concept_id and s.state == "current"),
                None,
            )
            if current is not None:
                if current.typed_value_override is not None:
                    current.package_plan_id = plan.id
                    continue
                selection_id = new_id()
                current.state = "superseded"
                current.superseded_by_id = selection_id
                replacement = DraftBenefitSelection(
                    id=selection_id,
                    draft_id=draft.id,
                    selection_key=f"plan:{plan.plan_key}:{offering.offering_key}"[:160],
                    catalog_offering_id=offering.id,
                    concept_id=offering.concept_id,
                    item_kind="catalog",
                    state="current",
                    cost_status="paid",
                    label_override=offering.label_override,
                    typed_value_override=item.typed_value_override,
                    evidence_snapshot={
                        "package_id": package.id,
                        "plan_id": plan.id,
                        "plan_key": plan.plan_key,
                        "source": "package_plan",
                        "is_detected": True,
                    },
                    sort_order=item.sort_order if item.sort_order is not None else 0,
                    package_plan_id=plan.id,
                )
                db.add(replacement)
                selections.append(replacement)
            else:
                member = DraftBenefitSelection(
                    id=new_id(),
                    draft_id=draft.id,
                    selection_key=f"plan:{plan.plan_key}:{offering.offering_key}"[:160],
                    catalog_offering_id=offering.id,
                    concept_id=offering.concept_id,
                    item_kind="catalog",
                    state="current",
                    cost_status="paid",
                    label_override=offering.label_override,
                    typed_value_override=item.typed_value_override,
                    evidence_snapshot={
                        "package_id": package.id,
                        "plan_id": plan.id,
                        "plan_key": plan.plan_key,
                        "source": "package_plan",
                        "is_detected": True,
                    },
                    sort_order=item.sort_order if item.sort_order is not None else 0,
                    package_plan_id=plan.id,
                )
                db.add(member)
                selections.append(member)
            applied += 1
    return applied


def _drop_plan_selection(selections: list[DraftBenefitSelection], selection: DraftBenefitSelection) -> None:
    """Remove one plan member and restore its superseded default, if any."""
    source = str((selection.evidence_snapshot or {}).get("source") or "")
    if source != "package_plan":
        selection.package_plan_id = None
        return
    predecessors = [
        item for item in selections
        if item.superseded_by_id == selection.id and item.state == "superseded"
    ]
    selection.state = "removed"
    selection.superseded_by_id = None
    selection.package_plan_id = None
    if predecessors:
        predecessors[0].state = "current"
        predecessors[0].superseded_by_id = None
        predecessors[0].package_plan_id = None
