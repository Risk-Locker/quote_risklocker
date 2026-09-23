"""AI Catalog Operations Service — natural language parsing, diff preview, and atomic multi-catalog execution."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.extraction.gemini_extractor import get_key_pool
from app.models.tables import (
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    BenefitPackage,
    BenefitPackagePlan,
    BenefitPackagePlanItem,
    BenefitProfile,
    CatalogOffering,
    CompanyBenefitCondition,
    CompanyBenefitConfig,
    CoverageType,
    InsuranceCompany,
    InsuranceProduct,
    Segment,
    User,
    VehicleCategory,
    new_id,
    utcnow,
)
from app.services.business_setup_service import (
    activate_benefit_profile,
    clone_benefit_profile,
    create_new_draft_revision,
    get_active_benefit_profile,
    publish_catalog_revision,
)

logger = logging.getLogger(__name__)


def _normalize_token(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def parse_catalog_intent(
    db: Session,
    query: str,
    company_id: str,
    profile_id: str | None = None,
) -> list[dict[str, Any]]:
    """Parse natural language instruction into a list of structured operations.

    Combines a fast deterministic regex parser with an optional Gemini LLM enhancement.
    """
    cleaned_query = query.strip()
    if not cleaned_query:
        return []

    operations: list[dict[str, Any]] = []

    # Pre-fetch lookup lists
    concepts = list(db.scalars(select(BenefitConcept)).all())
    concept_by_key = {c.concept_key: c for c in concepts}
    concept_by_norm = {_normalize_token(c.label): c for c in concepts}

    # Helper to find concept
    def find_concept(needle: str) -> BenefitConcept | None:
        needle_clean = needle.strip().lower()
        if needle_clean in concept_by_key:
            return concept_by_key[needle_clean]
        norm = _normalize_token(needle_clean)
        if norm in concept_by_norm:
            return concept_by_norm[norm]
        for c in concepts:
            if needle_clean in c.concept_key or needle_clean in c.label.lower():
                return c
        return None

    # 1. Deterministic Rule Parser
    q_lower = cleaned_query.lower()
    q_norm = re.sub(r"\btier\s*1\b", "basic", q_lower)
    q_norm = re.sub(r"\btier\s*2\b", "plus", q_norm)
    q_norm = re.sub(r"\btier\s*3\b", "premier", q_norm)

    # Scoping context extracted from natural language
    global_powertrain = "ice" if ("ice" in q_lower and "ev" not in q_lower) else ("ev" if ("ev" in q_lower and "ice" not in q_lower) else "all")
    global_vehicle = "commercial" if ("lorry" in q_lower or "commercial" in q_lower) else ("motorcycle" if ("motor" in q_lower or "bike" in q_lower) else ("car" if ("car" in q_lower or "saloon" in q_lower) else "all"))
    global_segment = "private" if "private" in q_lower else ("commercial" if ("commercial" in q_lower and "lorry" not in q_lower) else "all")

    # Pattern: Towing tiers (Lite, Plus, Premier, or general)
    # Examples: "AmAssurance PLUS and Premier towing to 200km and 365km"
    #           "Lite towing 50km, Plus 100km, Premier 365km"
    towing_concept = find_concept("towing")
    if towing_concept and "towing" in q_norm:
        # Check for multi-tier pairing like "PLUS and Premier towing to 200km and 365km"
        found_tiers = [t for t in ["lite", "basic", "plus", "premier"] if re.search(rf"\b{t}\b", q_norm)]
        dist_matches = re.findall(r"(\d+\s*km|\d+\s*miles|unlimited)", q_norm)
        if len(found_tiers) > 1 and len(found_tiers) == len(dist_matches):
            for t_name, dist in zip(found_tiers, dist_matches):
                dist_clean = dist.strip()
                dist_clean = re.sub(r"(\d+)\s*(km|miles)", r"\1 \2", dist_clean, flags=re.IGNORECASE)
                if dist_clean.isdigit():
                    dist_clean = f"{dist_clean} km"
                operations.append({
                    "action": "update_plan_item",
                    "concept_key": towing_concept.concept_key,
                    "tier_filter": t_name.lower(),
                    "vehicle_category": global_vehicle if global_vehicle != "all" else "car",
                    "powertrain": global_powertrain,
                    "segment": global_segment,
                    "value": dist_clean,
                })
        else:
            tier_matches = re.findall(r"\b(lite|plus|premier|basic)\b[^\d]*?(\d+\s*(?:km|miles)?|unlimited)", q_norm)
            if tier_matches:
                for tier_name, dist in tier_matches:
                    dist_clean = dist.strip()
                    dist_clean = re.sub(r"(\d+)\s*(km|miles)", r"\1 \2", dist_clean, flags=re.IGNORECASE)
                    if dist_clean.isdigit():
                        dist_clean = f"{dist_clean} km"
                    operations.append({
                        "action": "update_plan_item",
                        "concept_key": towing_concept.concept_key,
                        "tier_filter": tier_name.lower(),
                        "vehicle_category": global_vehicle if global_vehicle != "all" else "car",
                        "powertrain": global_powertrain,
                        "segment": global_segment,
                        "value": dist_clean,
                    })
            else:
                dist_match = re.search(r"towing\s*(?:limit\s*)?(?:to|:|=|\s)\s*(\d+\s*(?:km|miles)?|unlimited)", q_lower)
                if dist_match:
                    dist_clean = dist_match.group(1).strip()
                    dist_clean = re.sub(r"(\d+)\s*(km|miles)", r"\1 \2", dist_clean, flags=re.IGNORECASE)
                    if dist_clean.isdigit():
                        dist_clean = f"{dist_clean} km"
                    operations.append({
                        "action": "update_plan_item",
                        "concept_key": towing_concept.concept_key,
                        "tier_filter": "all",
                        "vehicle_category": global_vehicle if global_vehicle != "all" else "car",
                        "powertrain": global_powertrain,
                        "segment": global_segment,
                        "value": dist_clean,
                    })


    # Pattern: Windscreen add/update with vehicle/powertrain conditions
    # Example: "add windscreen RM 500 as addon for all ICE cars (saloon + non-saloon)"
    #          "windscreen 15% for ICE only"
    windscreen_concept = find_concept("windscreen")
    if windscreen_concept and "windscreen" in q_lower:
        val_match = re.search(r"windscreen\D*?(?:rm\s*(\d+)|(\d+\s*%)|(\d+))", q_lower)
        val = None
        if val_match:
            g1, g2, g3 = val_match.groups()
            if g1:
                val = f"RM {g1}"
            elif g2:
                val = g2.strip()
            elif g3:
                val = f"RM {g3}"

        powertrain = "ice" if "ice" in q_lower and "ev" not in q_lower else ("ev" if "ev" in q_lower and "ice" not in q_lower else "all")
        veh_cat = "car" if ("car" in q_lower or "saloon" in q_lower) else ("all" if "all" in q_lower else "car")

        is_add = bool(re.search(r"\badd\b.*?\bwindscreen\b|\bwindscreen\b.*?\badd\b", q_lower)) or "add" in q_lower
        operations.append({
            "action": "add_offering" if is_add else ("update_offering" if "update" in q_lower or "change" in q_lower else "add_offering"),
            "concept_key": windscreen_concept.concept_key,
            "vehicle_category": veh_cat,
            "powertrain": powertrain,
            "role": "addon_option",
            "value": val or "15%",
            "optional_price": val or "15%",
        })

    # Pattern: Description override
    # Example: "change description of own-damage to 'Verified Comprehensive Own Damage Protection'"
    #          "change main benefit description just for qbe this one to this"
    #          "Update QBE main benefit description to 'Comprehensive roadside assistance...'"
    desc_match = re.search(r"(?:change|update|set|modify)\s+(?:the\s+)?(?:[a-z0-9-_]+\s+)?(?:main\s+benefit\s+)?description\s+(?:of\s+([a-z0-9-_]+)\s+)?to\s+['\"]?([^'\"]+)['\"]?", cleaned_query, re.IGNORECASE)
    if desc_match:
        c_name = desc_match.group(1) or "own-damage"
        new_desc = desc_match.group(2).strip()
        matched_c = find_concept(c_name)
        if matched_c:
            operations.append({
                "action": "update_description",
                "concept_key": matched_c.concept_key,
                "description": new_desc,
            })

    # Pattern: Remove offering from scenario
    # Example: "remove legal-costs-defense from Lorry TPFT catalogs"
    #          "remove car-detailing-cleanup from addons for qbe"
    remove_matches = re.finditer(r"(?:remove|exclude|delete)\s+([a-z0-9-_]+)(?:\s+from\s+([a-z0-9-_]+(?:\s+[a-z0-9-_]+)?))?", q_lower)
    for rm in remove_matches:
        c_name = rm.group(1).strip()
        scope = rm.group(2) or ""
        matched_c = find_concept(c_name)
        if matched_c:
            veh_cat = "commercial" if "lorry" in scope or "commercial" in scope else ("car" if "car" in scope else "all")
            cov_type = "tpft" if "tpft" in scope else ("comprehensive" if "comp" in scope else "all")
            powertrain = "ev" if "ev" in scope else ("ice" if "ice" in scope else "all")
            operations.append({
                "action": "remove_offering",
                "concept_key": matched_c.concept_key,
                "vehicle_category": veh_cat,
                "coverage_type": cov_type,
                "powertrain": powertrain,
            })

    # 2. LLM Gemini Enhancement (if available and query is complex)
    if not operations or len(cleaned_query) > 60:
        pool = get_key_pool()
        all_keys = pool.get_all_keys()
        if all_keys:
            try:
                system_instruction = (
                    "You are the RiskLocker Insurance Catalog Intent Parser. "
                    "Extract benefit changes into a JSON list of operations. "
                    "Allowed actions: 'update_plan_item', 'update_offering', 'add_offering', 'remove_offering', 'update_description'. "
                    "Keys must match canonical keys like 'towing', 'windscreen', 'own-damage', 'legal-costs-defense'. "
                    "Return ONLY valid JSON array."
                )
                prompt = (
                    f"USER INSTRUCTION: {cleaned_query}\n\n"
                    "OUTPUT FORMAT EXAMPLE:\n"
                    '[{"action": "update_plan_item", "concept_key": "towing", "tier_filter": "plus", "value": "200 km"}, '
                    '{"action": "update_description", "concept_key": "own-damage", "description": "New description"}]'
                )
                settings = get_settings()
                api_key = pool.get_next_key()
                model_name = getattr(settings, "gemini_model", None) or "gemini-3.5-flash"
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                payload = {
                    "system_instruction": {"parts": [{"text": system_instruction}]},
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.0, "maxOutputTokens": 400},
                }
                with httpx.Client(timeout=6.0) as client:
                    res = client.post(url, json=payload)
                    if res.status_code == 200:
                        raw_reply = res.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        clean_json = re.sub(r"```json|```", "", raw_reply).strip()
                        ai_ops = json.loads(clean_json)
                        if isinstance(ai_ops, list):
                            # Merge operations without duplicates
                            seen_keys = {(op.get("action"), op.get("concept_key"), op.get("tier_filter")) for op in operations}
                            for op in ai_ops:
                                if isinstance(op, dict):
                                    sig = (op.get("action"), op.get("concept_key"), op.get("tier_filter"))
                                    if sig not in seen_keys:
                                        operations.append(op)
                                        seen_keys.add(sig)
            except Exception as exc:
                logger.warning("Gemini intent parsing fallback to deterministic: %s", exc)

    return operations


def preview_catalog_operations(
    db: Session,
    company_id: str,
    operations: list[dict[str, Any]],
    profile_id: str | None = None,
) -> dict[str, Any]:
    """Scan company catalogs and calculate the exact before-and-after mutation diff."""
    company = db.get(InsuranceCompany, company_id)
    if company is None:
        raise AppError("Company not found.", 404)

    if profile_id:
        target_profile = db.get(BenefitProfile, profile_id)
    else:
        target_profile = get_active_benefit_profile(db)

    if target_profile is None:
        raise AppError("No benefit profile found.", 404)

    # Reference maps
    segments = {s.id: s for s in db.scalars(select(Segment)).all()}
    vehicles = {v.id: v for v in db.scalars(select(VehicleCategory)).all()}
    coverages = {c.id: c for c in db.scalars(select(CoverageType)).all()}
    concepts = {c.concept_key: c for c in db.scalars(select(BenefitConcept)).all()}

    # All catalogs for this company
    catalogs = list(
        db.scalars(
            select(BenefitCatalog)
            .where(BenefitCatalog.company_id == company_id)
            .order_by(BenefitCatalog.name)
        ).all()
    )

    mutations: list[dict[str, Any]] = []
    mutation_counter = 1

    for op in operations:
        action = op.get("action")
        concept_key = op.get("concept_key")
        concept = concepts.get(concept_key) if isinstance(concept_key, str) else None
        if not concept:
            continue

        # 1. Update Description (Affects CompanyBenefitConfig under profile)
        if action == "update_description":
            new_desc = op.get("description", "").strip()
            cfg = db.scalar(
                select(CompanyBenefitConfig).where(
                    CompanyBenefitConfig.company_id == company_id,
                    CompanyBenefitConfig.profile_id == target_profile.id,
                    CompanyBenefitConfig.concept_id == concept.id,
                )
            )
            old_desc = cfg.baseline_description if cfg else None
            mutations.append({
                "mutation_id": f"mut-{mutation_counter}",
                "category": "config",
                "action_type": "DESC",
                "company_name": company.name,
                "scenario_name": f"{company.name} — Master Pool Baseline",
                "package_name": "Company-wide Baseline",
                "benefit_key": concept.concept_key,
                "benefit_label": concept.label,
                "target_catalog_id": None,
                "target_package_id": None,
                "target_plan_id": None,
                "target_offering_id": None,
                "target_concept_id": concept.id,
                "old_value": old_desc or "Default Catalog Description",
                "new_value": new_desc,
                "is_selected": True,
            })
            mutation_counter += 1
            continue

        # 2. Scope matching across catalogs
        veh_filter = op.get("vehicle_category", "all").lower()
        cov_filter = op.get("coverage_type", "all").lower()
        power_filter = op.get("powertrain", "all").lower()
        seg_filter = op.get("segment", "all").lower()
        tier_filter = op.get("tier_filter", "all").lower()
        target_value = op.get("value")

        for cat in catalogs:
            if cat.status in ("archived", "retired"):
                continue

            veh = vehicles.get(cat.vehicle_category_id) if cat.vehicle_category_id else None
            cov = coverages.get(cat.coverage_type_id) if cat.coverage_type_id else None
            seg = segments.get(cat.segment_id) if cat.segment_id else None
            veh_name = veh.category_key.lower() if veh else ("car" if "car" in cat.name.lower() else "")
            cov_name = cov.coverage_key.lower() if cov else ("comprehensive" if "comprehensive" in cat.name.lower() or "comp" in cat.name.lower() else "")
            seg_name = seg.segment_key.lower() if seg else ""

            # Check segment filter
            if seg_filter != "all" and seg_name and seg_filter not in seg_name:
                continue

            # Check vehicle category filter
            if veh_filter != "all" and veh_name and veh_filter not in veh_name:
                continue

            # Check coverage type filter
            if cov_filter != "all" and cov_name and cov_filter not in cov_name:
                continue

            # Check powertrain filter from catalog name or context
            cat_lower = cat.name.lower()
            is_ev = "ev" in cat_lower or "electric" in cat_lower
            if power_filter == "ice" and is_ev:
                continue
            if power_filter == "ev" and not is_ev:
                continue

            latest_rev = db.scalar(
                select(BenefitCatalogRevision)
                .where(BenefitCatalogRevision.catalog_id == cat.id)
                .order_by(BenefitCatalogRevision.revision_number.desc())
            )
            if not latest_rev:
                continue

            # Check plan items or package offerings if action is update_plan_item
            if action == "update_plan_item":
                # A. Check offerings directly assigned to packages/tiers
                all_rev_offerings = list(
                    db.scalars(
                        select(CatalogOffering).where(
                            CatalogOffering.catalog_revision_id == latest_rev.id,
                            CatalogOffering.concept_id == concept.id,
                        )
                    ).all()
                )
                for off in all_rev_offerings:
                    pkg = db.get(BenefitPackage, off.applies_to_id) if off.applies_to_id else None
                    pkg_name = (pkg.name if pkg else "").lower()
                    off_key = (off.offering_key or "").lower()

                    matches_tier = (
                        tier_filter == "all"
                        or tier_filter in pkg_name
                        or tier_filter in off_key
                        or (tier_filter in ("lite", "basic") and any(k in pkg_name or k in off_key for k in ("basic", "lite")))
                        or (tier_filter == "plus" and "plus" in (pkg_name + " " + off_key))
                        or (tier_filter == "premier" and "premier" in (pkg_name + " " + off_key))
                    )
                    if matches_tier:
                        mutations.append({
                            "mutation_id": f"mut-{mutation_counter}",
                            "category": "offering",
                            "action_type": "UPDATE",
                            "company_name": company.name,
                            "scenario_name": cat.name,
                            "package_name": pkg.name if pkg else "Package Offering",
                            "benefit_key": concept.concept_key,
                            "benefit_label": concept.label,
                            "target_catalog_id": cat.id,
                            "target_package_id": pkg.id if pkg else None,
                            "target_plan_id": None,
                            "target_offering_id": off.id,
                            "target_concept_id": concept.id,
                            "old_value": off.display_value or "Standard",
                            "new_value": target_value or "Updated",
                            "is_selected": True,
                        })
                        mutation_counter += 1

                # B. Also check sub-plans if BenefitPackagePlan exist
                plans = list(
                    db.scalars(
                        select(BenefitPackagePlan)
                        .join(BenefitPackage, BenefitPackage.id == BenefitPackagePlan.package_id)
                        .where(BenefitPackage.catalog_revision_id == latest_rev.id)
                    ).all()
                )
                for plan in plans:
                    plan_lower = plan.name.lower()
                    if tier_filter != "all" and tier_filter not in plan_lower:
                        continue

                    # Find plan item for this concept
                    plan_item = db.scalar(
                        select(BenefitPackagePlanItem)
                        .join(CatalogOffering, CatalogOffering.id == BenefitPackagePlanItem.offering_id)
                        .where(
                            BenefitPackagePlanItem.plan_id == plan.id,
                            CatalogOffering.concept_id == concept.id,
                        )
                    )
                    old_val = "N/A"
                    if plan_item and plan_item.typed_value_override:
                        old_val = str(plan_item.typed_value_override.get("formatted") or plan_item.typed_value_override.get("value") or old_val)
                    elif plan_item:
                        off = db.get(CatalogOffering, plan_item.offering_id)
                        old_val = off.display_value or "Default Limit" if off else "Default Limit"

                    mutations.append({
                        "mutation_id": f"mut-{mutation_counter}",
                        "category": "plan_item",
                        "action_type": "UPDATE",
                        "company_name": company.name,
                        "scenario_name": cat.name,
                        "package_name": plan.name,
                        "benefit_key": concept.concept_key,
                        "benefit_label": concept.label,
                        "target_catalog_id": cat.id,
                        "target_package_id": plan.package_id,
                        "target_plan_id": plan.id,
                        "target_offering_id": plan_item.offering_id if plan_item else None,
                        "target_concept_id": concept.id,
                        "old_value": old_val,
                        "new_value": target_value or "Updated",
                        "is_selected": True,
                    })
                    mutation_counter += 1

            # Check offering updates or additions
            elif action in ("update_offering", "add_offering"):
                offering = db.scalar(
                    select(CatalogOffering).where(
                        CatalogOffering.catalog_revision_id == latest_rev.id,
                        CatalogOffering.concept_id == concept.id,
                    )
                )
                if offering:
                    mutations.append({
                        "mutation_id": f"mut-{mutation_counter}",
                        "category": "offering",
                        "action_type": "UPDATE",
                        "company_name": company.name,
                        "scenario_name": cat.name,
                        "package_name": "Scenario Rider",
                        "benefit_key": concept.concept_key,
                        "benefit_label": concept.label,
                        "target_catalog_id": cat.id,
                        "target_package_id": None,
                        "target_plan_id": None,
                        "target_offering_id": offering.id,
                        "target_concept_id": concept.id,
                        "old_value": offering.display_value or "Standard",
                        "new_value": target_value or "15%",
                        "is_selected": True,
                    })
                    mutation_counter += 1
                else:
                    mutations.append({
                        "mutation_id": f"mut-{mutation_counter}",
                        "category": "offering",
                        "action_type": "ADD",
                        "company_name": company.name,
                        "scenario_name": cat.name,
                        "package_name": "Scenario Rider",
                        "benefit_key": concept.concept_key,
                        "benefit_label": concept.label,
                        "target_catalog_id": cat.id,
                        "target_package_id": None,
                        "target_plan_id": None,
                        "target_offering_id": None,
                        "target_concept_id": concept.id,
                        "old_value": "None (Not present)",
                        "new_value": target_value or "15%",
                        "is_selected": True,
                    })
                    mutation_counter += 1

            # Check offering removals
            elif action == "remove_offering":
                offering = db.scalar(
                    select(CatalogOffering).where(
                        CatalogOffering.catalog_revision_id == latest_rev.id,
                        CatalogOffering.concept_id == concept.id,
                    )
                )
                if offering:
                    mutations.append({
                        "mutation_id": f"mut-{mutation_counter}",
                        "category": "offering",
                        "action_type": "REMOVE",
                        "company_name": company.name,
                        "scenario_name": cat.name,
                        "package_name": "Scenario Rider",
                        "benefit_key": concept.concept_key,
                        "benefit_label": concept.label,
                        "target_catalog_id": cat.id,
                        "target_package_id": None,
                        "target_plan_id": None,
                        "target_offering_id": offering.id,
                        "target_concept_id": concept.id,
                        "old_value": offering.display_value or "Active",
                        "new_value": "[Removed from catalog]",
                        "is_selected": True,
                    })
                    mutation_counter += 1

    return {
        "summary": f"Identified {len(mutations)} catalog and profile updates for {company.name}.",
        "mutations": mutations,
        "operations_preview": [
            {
                "catalog_id": m["target_catalog_id"],
                "catalog_name": m["scenario_name"],
                "action": "update_plan_item" if m["category"] == "plan_item" else ("update_description" if m["category"] == "config" else ("add_offering" if m["action_type"] == "ADD" else ("remove_offering" if m["action_type"] == "REMOVE" else "update_plan_item"))),
                "concept_key": m["benefit_key"],
                "concept_label": m["benefit_label"],
                "current_value": m["old_value"],
                "new_value": m["new_value"],
                "details": f"{m['package_name']} · {m['action_type']}",
            }
            for m in mutations
        ],
        "matched_catalogs": [
            {"id": cat.id, "name": cat.name, "vehicle_category": getattr(cat, "vehicle_category_id", None)}
            for cat in catalogs
        ],
        "target_company_id": company.id,
        "target_company_name": company.name,
        "company_id": company.id,
        "active_profile_id": target_profile.id if target_profile else None,
        "active_profile_name": target_profile.name if target_profile else None,
        "active_profile_version": f"v{target_profile.version_number}" if (target_profile and target_profile.version_number) else "v2",
        "suggested_next_version": f"v{target_profile.version_number + 1}" if (target_profile and target_profile.version_number) else "v3",
        "is_active_profile": target_profile.is_active if target_profile else True,
        "parsed_intent": {"intent": "catalog_mutation", "operations": operations},
    }


def apply_catalog_operations(
    db: Session,
    user: User,
    company_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Execute confirmed catalog mutations atomically, managing profile cloning and revision auto-forking."""
    company = db.get(InsuranceCompany, company_id)
    if company is None:
        raise AppError("Company not found.", 404)

    raw_mutations = payload.get("mutations") or []
    if not raw_mutations and payload.get("operations"):
        preview_res = preview_catalog_operations(
            db,
            company_id,
            payload.get("operations") or [],
            profile_id=payload.get("profile_id"),
        )
        raw_mutations = preview_res.get("mutations") or []

    if not raw_mutations:
        raise AppError("No mutations provided to apply.", 422)

    selected_mutations = [m for m in raw_mutations if m.get("is_selected", True)]
    if not selected_mutations:
        selected_mutations = raw_mutations

    target_profile_action = payload.get("target_profile_action")
    if not target_profile_action:
        target_profile_action = "clone_new" if payload.get("create_new_profile_version") is True else "in_place"
    new_profile_name = payload.get("new_version_name") or payload.get("new_profile_name")

    active_profile = get_active_benefit_profile(db)
    target_profile = active_profile

    # 1. Profile Versioning: Only clone if explicitly requested as clone_new or active profile is archived
    if target_profile_action == "clone_new" or (active_profile and active_profile.status == "archived"):
        custom_name = new_profile_name.strip() if isinstance(new_profile_name, str) and new_profile_name.strip() else None
        clone_res = clone_benefit_profile(
            db,
            user,
            active_profile.id,
            {"name": custom_name or f"{active_profile.name} (v{active_profile.version_number + 1})"},
        )
        target_profile = db.get(BenefitProfile, clone_res["id"])
        if target_profile is None:
            raise AppError("Failed to provision new profile version.", 500)
    elif payload.get("profile_id"):
        explicit_profile = db.get(BenefitProfile, payload["profile_id"])
        if explicit_profile:
            target_profile = explicit_profile

    affected_catalogs: set[str] = set()
    applied_count = 0

    # 2. Apply mutations
    for m in selected_mutations:
        cat_id = m.get("target_catalog_id")
        action_type = m.get("action_type")
        category = m.get("category")
        concept_id = m.get("target_concept_id")
        new_val = m.get("new_value")

        # Config baseline description mutation
        if category == "config" or action_type == "DESC":
            cfg = db.scalar(
                select(CompanyBenefitConfig).where(
                    CompanyBenefitConfig.company_id == company_id,
                    CompanyBenefitConfig.profile_id == target_profile.id,
                    CompanyBenefitConfig.concept_id == concept_id,
                )
            )
            if cfg:
                cfg.baseline_description = new_val
                cfg.updated_at = utcnow()
            else:
                db.add(
                    CompanyBenefitConfig(
                        id=new_id(),
                        company_id=company_id,
                        profile_id=target_profile.id,
                        concept_id=concept_id,
                        is_enabled=True,
                        baseline_description=new_val,
                        created_at=utcnow(),
                        updated_at=utcnow(),
                    )
                )
            applied_count += 1
            continue

        if not cat_id:
            continue

        catalog = db.get(BenefitCatalog, cat_id)
        if not catalog:
            continue

        # Get latest revision
        latest_rev = db.scalar(
            select(BenefitCatalogRevision)
            .where(BenefitCatalogRevision.catalog_id == catalog.id)
            .order_by(BenefitCatalogRevision.revision_number.desc())
        )
        if not latest_rev:
            continue

        # Check if there is already a draft revision to edit
        working_rev = db.scalar(
            select(BenefitCatalogRevision)
            .where(BenefitCatalogRevision.catalog_id == catalog.id, BenefitCatalogRevision.state == "draft")
            .order_by(BenefitCatalogRevision.revision_number.desc())
        )
        if not working_rev:
            if latest_rev.state == "published":
                create_new_draft_revision(db, user, catalog.id, base_revision=catalog.revision)
                working_rev = db.scalar(
                    select(BenefitCatalogRevision)
                    .where(BenefitCatalogRevision.catalog_id == catalog.id, BenefitCatalogRevision.state == "draft")
                )
            else:
                working_rev = latest_rev
        if not working_rev:
            continue

        # Apply Plan Item update
        if category == "plan_item":
            plan_id = m.get("target_plan_id")
            off_id = m.get("target_offering_id")
            if plan_id:
                # Find matching plan in working_rev
                target_plan = db.get(BenefitPackagePlan, plan_id)
                if target_plan:
                    # Find plan item in working_rev
                    item = db.scalar(
                        select(BenefitPackagePlanItem)
                        .join(CatalogOffering, CatalogOffering.id == BenefitPackagePlanItem.offering_id)
                        .where(
                            BenefitPackagePlanItem.plan_id == target_plan.id,
                            CatalogOffering.concept_id == concept_id,
                        )
                    )
                    if item:
                        item.typed_value_override = {"type": "text", "value": new_val, "formatted": new_val}
                        applied_count += 1
                        affected_catalogs.add(catalog.id)

        # Apply Offering update/add/remove
        elif category == "offering":
            if action_type in ("UPDATE", "DESC"):
                off = None
                target_off_id = m.get("target_offering_id")
                if target_off_id:
                    orig_off = db.get(CatalogOffering, target_off_id)
                    if orig_off and orig_off.catalog_revision_id == working_rev.id:
                        off = orig_off
                    elif orig_off:
                        off = db.scalar(
                            select(CatalogOffering).where(
                                CatalogOffering.catalog_revision_id == working_rev.id,
                                CatalogOffering.offering_key == orig_off.offering_key,
                            )
                        )
                if not off:
                    off = db.scalar(
                        select(CatalogOffering).where(
                            CatalogOffering.catalog_revision_id == working_rev.id,
                            CatalogOffering.concept_id == concept_id,
                        )
                    )
                if off:
                    off.display_value = new_val
                    applied_count += 1
                    affected_catalogs.add(catalog.id)
            elif action_type == "REMOVE":
                off = db.scalar(
                    select(CatalogOffering).where(
                        CatalogOffering.catalog_revision_id == working_rev.id,
                        CatalogOffering.concept_id == concept_id,
                    )
                )
                if off:
                    db.delete(off)
                    applied_count += 1
                    affected_catalogs.add(catalog.id)
            elif action_type == "ADD":
                existing = db.scalar(
                    select(CatalogOffering).where(
                        CatalogOffering.catalog_revision_id == working_rev.id,
                        CatalogOffering.concept_id == concept_id,
                    )
                )
                if not existing:
                    concept_obj = db.get(BenefitConcept, concept_id)
                    key_slug = concept_obj.concept_key if concept_obj else "offering"
                    db.add(
                        CatalogOffering(
                            id=new_id(),
                            catalog_revision_id=working_rev.id,
                            offering_key=f"{key_slug}-{int(datetime.now(timezone.utc).timestamp())}",
                            concept_id=concept_id,
                            offering_kind="optional",
                            role="addon_option",
                            display_value=new_val,
                            sort_order=50,
                            status="active",
                            created_at=utcnow(),
                            updated_at=utcnow(),
                        )
                    )
                    applied_count += 1
                    affected_catalogs.add(catalog.id)

    # Flush all child mutations while revision is still in draft state
    db.flush()

    # 3. Publish draft revisions if forked so catalogs become live
    for cid in affected_catalogs:
        cat = db.get(BenefitCatalog, cid)
        if cat and cat.status == "draft":
            try:
                publish_catalog_revision(db, user, cat.id, base_revision=cat.revision)
                db.flush()
            except Exception as p_err:
                logger.warning("Could not auto-publish catalog %s: %s", cid, p_err)

    # 4. Activate new profile if created
    if target_profile.id != active_profile.id:
        activate_benefit_profile(db, user, target_profile.id)

    db.commit()

    return {
        "applied_count": applied_count,
        "catalogs_updated": list(affected_catalogs),
        "affected_catalog_ids": list(affected_catalogs),
        "new_profile": {
            "id": target_profile.id,
            "version": f"v{target_profile.version_number}",
            "name": target_profile.name,
            "is_active": target_profile.is_active,
        } if target_profile else None,
        "active_profile": {
            "id": target_profile.id,
            "name": target_profile.name,
            "version_number": target_profile.version_number,
        },
        "message": f"Successfully applied {applied_count} catalog operations under Profile {target_profile.name}.",
    }
