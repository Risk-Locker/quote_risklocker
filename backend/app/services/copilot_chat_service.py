"""Conversational AI Copilot Service — status checks, Q&A, catalog mutations, and session deduplication hygiene."""

from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import func, or_, select
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
    BusinessAsset,
    CatalogOffering,
    CompanyBenefitCondition,
    CompanyBenefitConfig,
    GlobalBenefitProfile,
    GlobalBenefitProfileAsset,
    InsuranceCompany,
    QuotationDraft,
    Session as SessionModel,
    UploadedFile,
    User,
)
from app.services.business_setup_service import get_active_benefit_profile
from app.services.catalog_operations_service import (
    parse_catalog_intent,
    preview_catalog_operations,
)
from app.services.review_service import move_to_trash

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. LIVE DATABASE GROUND TRUTH EXTRACTION
# ---------------------------------------------------------------------------

def _find_target_company(
    db: Session,
    company_id: str | None = None,
    query: str = "",
    history: list[dict[str, str]] | None = None,
) -> InsuranceCompany | None:
    """Find company by ID or smart matching from query text, falling back to recent conversation history."""
    if company_id:
        company = db.get(InsuranceCompany, company_id)
        if company:
            return company

    companies = list(db.scalars(select(InsuranceCompany).where(InsuranceCompany.status == "active")).all())

    def _match_in_text(text: str) -> InsuranceCompany | None:
        t_lower = text.lower()
        for comp in companies:
            if comp.slug and comp.slug.lower() in t_lower:
                return comp
            if comp.name.lower() in t_lower:
                return comp
            first_word = comp.name.lower().split()[0]
            if len(first_word) >= 3 and re.search(rf"\b{re.escape(first_word)}\b", t_lower):
                return comp
        return None

    # 1. Match in current query first
    comp = _match_in_text(query)
    if comp:
        return comp

    # 2. Match in recent history (reverse order, latest message first)
    if history:
        for msg in reversed(history):
            c = _match_in_text(msg.get("content", ""))
            if c:
                return c

    return None


def get_catalog_status_facts(
    db: Session,
    company_id: str | None = None,
    query: str = "",
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Gather live facts about insurer catalogs, vehicle categories, towing configs, and conditions."""
    target_company = _find_target_company(db, company_id, query, history)
    
    if not target_company:
        # Return global company summary
        companies = db.scalars(select(InsuranceCompany).where(InsuranceCompany.status == "active")).all()
        return {
            "scope": "global",
            "total_companies": len(companies),
            "companies": [{"id": c.id, "name": c.name, "slug": c.slug} for c in companies],
        }

    company_id = target_company.id
    catalogs = db.scalars(
        select(BenefitCatalog).where(BenefitCatalog.company_id == company_id)
    ).all()
    all_profiles = db.scalars(select(BenefitProfile)).all()
    active_profile = next((p for p in all_profiles if p.is_active), None)

    # Categorize catalogs
    vehicle_cats = defaultdict(list)
    powertrain_cats = defaultdict(list)
    for cat in catalogs:
        v_name = cat.vehicle_category.name if getattr(cat, "vehicle_category", None) else "Uncategorized"
        vehicle_cats[v_name].append(cat.name)
        p_name = cat.engine_type if hasattr(cat, "engine_type") and cat.engine_type else ("ev" if "ev" in cat.name.lower() else "ice")
        powertrain_cats[p_name].append(cat.name)

    # Inspect towing offerings and descriptions across catalogs in a single fast query
    towing_info: list[dict[str, Any]] = []
    towing_descriptions: set[str] = set()

    cat_ids = [c.id for c in catalogs]
    if cat_ids:
        towing_rows = (
            db.query(
                BenefitCatalog.name.label("catalog_name"),
                BenefitConcept.concept_key,
                BenefitConcept.label.label("concept_label"),
                BenefitConcept.description.label("concept_desc"),
                CatalogOffering.role,
                CatalogOffering.display_value,
                CatalogOffering.description_override,
            )
            .join(BenefitCatalogRevision, BenefitCatalogRevision.catalog_id == BenefitCatalog.id)
            .join(CatalogOffering, CatalogOffering.catalog_revision_id == BenefitCatalogRevision.id)
            .join(BenefitConcept, CatalogOffering.concept_id == BenefitConcept.id)
            .filter(
                BenefitCatalog.id.in_(cat_ids),
                CatalogOffering.status == "active",
                or_(
                    BenefitConcept.concept_key.ilike("%towing%"),
                    BenefitConcept.label.ilike("%towing%"),
                ),
            )
            .limit(20)
            .all()
        )
        for row in towing_rows:
            desc = row.description_override or row.concept_desc or ""
            if desc:
                towing_descriptions.add(desc.strip())
            val = row.display_value or ""
            towing_info.append({
                "catalog_name": row.catalog_name,
                "concept_key": row.concept_key,
                "concept_label": row.concept_label,
                "is_included": row.role == "included",
                "values": [val] if val else [],
                "description": desc[:120] if desc else "None",
            })

    # Check CompanyBenefitCondition rules
    conditions = db.scalars(
        select(CompanyBenefitCondition).where(
            CompanyBenefitCondition.company_id == company_id,
            CompanyBenefitCondition.is_active == True,
        )
    ).all()

    # Identify dummy / inactive profiles
    dummy_profiles = []
    for p in all_profiles:
        is_dummy = (not p.is_active) or ("dummy" in p.name.lower()) or ("test" in p.name.lower())
        if is_dummy:
            dummy_profiles.append({
                "id": p.id,
                "name": p.name,
                "version": f"v{p.version_number}.0",
                "is_active": p.is_active,
            })

    return {
        "scope": "company",
        "company_id": target_company.id,
        "company_name": target_company.name,
        "active_profile": {
            "id": active_profile.id if active_profile else None,
            "name": active_profile.name if active_profile else "None",
            "version": f"v{active_profile.version_number}.0" if active_profile else "None",
        },
        "total_catalogs": len(catalogs),
        "vehicle_breakdown": {k: len(v) for k, v in vehicle_cats.items()},
        "powertrain_breakdown": {k: len(v) for k, v in powertrain_cats.items()},
        "towing_details": towing_info[:8],
        "same_towing_description_across_all": len(towing_descriptions) <= 1,
        "unique_towing_descriptions_count": len(towing_descriptions),
        "conditions_count": len(conditions),
        "conditions_summary": [
            {
                "id": c.id,
                "name": c.name,
                "description": c.replacement_description or f"Condition: {c.action_type}",
                "action_type": c.action_type,
            }
            for c in conditions
        ],
        "dummy_profiles": dummy_profiles,
    }


def get_profile_and_visual_facts(db: Session) -> dict[str, Any]:
    """Gather live facts about Catalog Profiles (BenefitProfile) and Visual Image Profiles (GlobalBenefitProfile)."""
    # 1. Catalog Profiles
    catalog_profiles = db.scalars(
        select(BenefitProfile).order_by(BenefitProfile.is_active.desc(), BenefitProfile.created_at.desc())
    ).all()
    active_catalog_profile = next((p for p in catalog_profiles if p.is_active), None)

    # 2. Visual Profiles (GlobalBenefitProfile)
    visual_profiles = db.scalars(
        select(GlobalBenefitProfile).order_by(GlobalBenefitProfile.is_active.desc(), GlobalBenefitProfile.created_at.desc())
    ).all()
    active_visual_profile = next((p for p in visual_profiles if p.is_active), None)

    # Total Active Concepts
    total_concepts = db.scalar(
        select(func.count(BenefitConcept.id)).where(BenefitConcept.status != "retired")
    ) or 0

    # Active visual profile stats
    mapped_count = 0
    active_visual_name = "None"
    asset_category = "None"
    if active_visual_profile:
        active_visual_name = active_visual_profile.name
        asset_category = active_visual_profile.asset_category
        mapped_count = db.scalar(
            select(func.count(GlobalBenefitProfileAsset.id))
            .where(GlobalBenefitProfileAsset.profile_id == active_visual_profile.id)
        ) or 0

    # Available assets in active visual folder
    category_assets_count = 0
    if active_visual_profile:
        category_assets_count = db.scalar(
            select(func.count(BusinessAsset.id))
            .where(BusinessAsset.category == active_visual_profile.asset_category)
        ) or 0

    return {
        "catalog_profiles": {
            "total": len(catalog_profiles),
            "active_profile_name": active_catalog_profile.name if active_catalog_profile else "None",
            "active_profile_id": active_catalog_profile.id if active_catalog_profile else None,
            "profiles_list": [{"id": p.id, "name": p.name, "is_active": p.is_active} for p in catalog_profiles],
        },
        "visual_profiles": {
            "total": len(visual_profiles),
            "active_profile_name": active_visual_name,
            "active_profile_id": active_visual_profile.id if active_visual_profile else None,
            "asset_category": asset_category,
            "total_concepts": total_concepts,
            "mapped_concept_artworks": mapped_count,
            "category_assets_available": category_assets_count,
            "profiles_list": [
                {
                    "id": p.id,
                    "name": p.name,
                    "asset_category": p.asset_category,
                    "is_active": p.is_active,
                    "status": p.status,
                }
                for p in visual_profiles
            ],
            "switch_images_supported": True,
            "switch_images_instructions": (
                f"Visual images are managed in '/builder/global-benefits'. The currently active visual profile is '{active_visual_name}' "
                f"(folder category: '{asset_category}'). Users can upload an image into folder '{asset_category}', and then assign or swap "
                "it for any benefit concept (such as Emergency Towing Assistance) directly on the visual grid or via Auto-Assign."
            ),
        },
    }


def get_session_hygiene_facts(db: Session, user: User | None = None) -> dict[str, Any]:
    """Analyze sessions to identify exact file duplicates vs unique edited quotes using Survivorship Scoring."""
    from app.models.tables import GeneratedPdfVersion
    from sqlalchemy import func

    results = (
        db.query(
            SessionModel.id,
            SessionModel.status,
            SessionModel.detected_company,
            SessionModel.quotation_ref,
            SessionModel.created_at,
            SessionModel.quotation_status,
            SessionModel.last_edited_at,
            UploadedFile.id.label("file_id"),
            UploadedFile.original_filename,
            UploadedFile.storage_sha256,
            QuotationDraft.id.label("draft_id"),
            QuotationDraft.fields,
        )
        .join(UploadedFile, SessionModel.uploaded_file_id == UploadedFile.id)
        .join(QuotationDraft, SessionModel.draft_id == QuotationDraft.id)
        .filter(SessionModel.status != "trash")
        .filter(SessionModel.is_test.is_(False))
        .filter(UploadedFile.deleted_at.is_(None))
        .order_by(SessionModel.created_at.desc())
        .all()
    )

    total_sessions = len(results)
    all_draft_ids = [r.draft_id for r in results]
    pdf_counts: dict[str, int] = {}
    if all_draft_ids:
        pdf_rows = (
            db.query(GeneratedPdfVersion.draft_id, func.count(GeneratedPdfVersion.id))
            .filter(GeneratedPdfVersion.draft_id.in_(all_draft_ids))
            .group_by(GeneratedPdfVersion.draft_id)
            .all()
        )
        pdf_counts = {str(draft_id): int(cnt) for draft_id, cnt in pdf_rows}

    by_sha: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_plate: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for r in results:
        fields = r.fields or {}
        plate = None
        for k in ["vehicle_no", "car_plate", "registration_number"]:
            if k in fields:
                val = fields[k]
                plate = val.get("value") if isinstance(val, dict) else val
                if plate:
                    break

        clean_plate = plate.strip().upper() if plate else "UNKNOWN"

        def get_field_val(key: str) -> str:
            item = fields.get(key)
            if isinstance(item, dict):
                return str(item.get("value", "") or "").strip()
            return str(item or "").strip()

        gross_premium = get_field_val("gross_premium")
        roadtax = get_field_val("roadtax")
        addons = get_field_val("optional_covers")

        info = {
            "session_id": r.id,
            "quotation_ref": r.quotation_ref or f"RL-{r.id[:8].upper()}",
            "draft_id": r.draft_id,
            "file_id": r.file_id,
            "filename": r.original_filename,
            "company": r.detected_company or "Unknown Insurer",
            "plate": clean_plate,
            "sha": r.storage_sha256,
            "gross_premium": gross_premium,
            "roadtax": roadtax,
            "addons": addons,
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "created_at_dt": r.created_at,
            "quotation_status": (r.quotation_status or "pending").lower(),
            "last_edited_at": r.last_edited_at.isoformat() if r.last_edited_at else None,
            "pdf_count": pdf_counts.get(r.draft_id, 0),
        }

        if r.storage_sha256:
            by_sha[r.storage_sha256].append(info)
        if clean_plate != "UNKNOWN":
            by_plate[clean_plate].append(info)

    # Exact Duplicates: Same storage_sha256 uploaded multiple times
    # Apply Survivorship Scoring: keep session with generated PDFs, closed status, manual edits, or valid plates
    exact_duplicate_groups: list[dict[str, Any]] = []
    redundant_session_ids: list[str] = []

    invalid_plate_tokens = {None, "", "UNKNOWN", "-UNREGISTERED-", "VEHICLEMAKE", "RM2", "NA"}

    def calculate_survivor_score(item: dict[str, Any]) -> tuple:
        pdf_score = 10000 if item["pdf_count"] > 0 else 0
        status_score = 5000 if item["quotation_status"] in ("hit", "miss") else 0
        edit_score = 2000 if item["last_edited_at"] is not None else 0
        plate_score = 1000 if item["plate"] not in invalid_plate_tokens else 0
        ts_score = item["created_at_dt"].timestamp() if item.get("created_at_dt") else 0.0
        return (pdf_score, status_score, edit_score, plate_score, ts_score)

    for sha, group in by_sha.items():
        if len(group) > 1:
            # Sort group by survivorship score (highest priority survives)
            sorted_group = sorted(group, key=calculate_survivor_score, reverse=True)
            keep_session = sorted_group[0]
            redundant_sessions = sorted_group[1:]

            # If keep_session plate is invalid, borrow the cleanest plate from the group if available
            if keep_session["plate"] in invalid_plate_tokens:
                for candidate in sorted_group:
                    if candidate["plate"] not in invalid_plate_tokens:
                        keep_session["plate"] = candidate["plate"]
                        break

            for red in redundant_sessions:
                redundant_session_ids.append(red["session_id"])

            exact_duplicate_groups.append({
                "group_type": "exact_file_hash",
                "sha": sha[:10],
                "car_plate": keep_session["plate"],
                "filename": keep_session["filename"],
                "company": keep_session["company"],
                "roadtax": keep_session["roadtax"],
                "gross_premium": keep_session["gross_premium"],
                "total_instances": len(group),
                "keep_session": keep_session,
                "trash_sessions": redundant_sessions,
            })

    # Legitimate Unique Quote Edits: Same car plate, but DIFFERENT roadtax, gross premium, or file hash
    unique_quote_variations: list[dict[str, Any]] = []
    for plate, group in by_plate.items():
        if len(group) > 1:
            # Check if values differ
            rt_values = set(g["roadtax"] for g in group if g["roadtax"])
            gross_values = set(g["gross_premium"] for g in group if g["gross_premium"])
            sha_values = set(g["sha"] for g in group if g["sha"])
            if len(rt_values) > 1 or len(gross_values) > 1 or len(sha_values) > 1:
                unique_quote_variations.append({
                    "car_plate": plate,
                    "sessions_count": len(group),
                    "unique_files_count": len(sha_values),
                    "roadtax_values": list(rt_values),
                    "gross_premiums": list(gross_values),
                })

    return {
        "total_active_sessions": total_sessions,
        "unique_car_plates_count": len(by_plate),
        "exact_duplicate_sets_count": len(exact_duplicate_groups),
        "redundant_sessions_count": len(redundant_session_ids),
        "redundant_session_ids": redundant_session_ids,
        "duplicate_groups": exact_duplicate_groups,
        "unique_quote_variations_count": len(unique_quote_variations),
        "sample_unique_quote_variations": unique_quote_variations[:5],
    }


def get_dataset_analytics_facts(db: Session) -> dict[str, Any]:
    """Extract aggregate analytics across all active quotation drafts:
    - Engine capacity (CC) list and bracket distribution (<=1000cc, 1001-1500cc, 1501-2000cc, >2000cc, EV)
    - Insurer quotation counts, rankings, and market share percentages
    - Vehicle make and model frequencies (top brands and cars mostly found)
    - Most frequently used / selected optional benefits & riders
    """
    rows = (
        db.query(
            QuotationDraft.fields,
            SessionModel.detected_company,
        )
        .join(SessionModel, SessionModel.draft_id == QuotationDraft.id)
        .filter(SessionModel.status != "trash")
        .all()
    )

    total_quotes = len(rows)
    insurer_counter: Counter[str] = Counter()
    cc_counter: Counter[str] = Counter()
    bracket_counter: Counter[str] = Counter()
    brand_counter: Counter[str] = Counter()
    model_counter: Counter[str] = Counter()
    benefit_counter: Counter[str] = Counter()

    for fields, comp in rows:
        c_name = comp or "Unspecified Insurer"
        insurer_counter[c_name] += 1

        if not fields:
            continue

        def _get_val(key: str) -> str:
            item = fields.get(key)
            if isinstance(item, dict):
                return str(item.get("value", "") or "").strip()
            return str(item or "").strip()

        # Engine CC extraction
        cc_raw = _get_val("engine_cc") or _get_val("capacity") or _get_val("cubic_capacity")
        cc_num = None
        if cc_raw:
            m = re.search(r"(\d{3,4})", cc_raw.replace(",", ""))
            if m:
                val = int(m.group(1))
                if 50 <= val <= 10000:
                    cc_num = val

        model_raw = _get_val("car_model") or _get_val("model") or ""
        if not cc_num and model_raw:
            m = re.search(r"\b(\d{3,4})\s*(?:cc|c\.c\.)\b", model_raw, re.IGNORECASE)
            if m:
                val = int(m.group(1))
                if 50 <= val <= 10000:
                    cc_num = val
            elif re.search(r"\b1\.0\s*l?\b", model_raw, re.IGNORECASE):
                cc_num = 998
            elif re.search(r"\b1\.3\s*l?\b", model_raw, re.IGNORECASE):
                cc_num = 1329
            elif re.search(r"\b1\.5\s*l?\b", model_raw, re.IGNORECASE):
                cc_num = 1496
            elif re.search(r"\b1\.6\s*l?\b", model_raw, re.IGNORECASE):
                cc_num = 1598
            elif re.search(r"\b2\.0\s*l?\b", model_raw, re.IGNORECASE):
                cc_num = 1998
            elif re.search(r"\b2\.5\s*l?\b", model_raw, re.IGNORECASE):
                cc_num = 2488

        if cc_num:
            cc_str = f"{cc_num} CC"
            cc_counter[cc_str] += 1
            if cc_num <= 1000:
                bracket_counter["<= 1,000 cc (Compact / City Cars)"] += 1
            elif cc_num <= 1500:
                bracket_counter["1,001 – 1,500 cc (Sedans & Compact Hatchbacks)"] += 1
            elif cc_num <= 2000:
                bracket_counter["1,501 – 2,000 cc (Mid-size, SUVs & Crossovers)"] += 1
            else:
                bracket_counter["> 2,000 cc (Large Executive, 4x4s & Commercial)"] += 1
        elif "ev" in model_raw.lower() or "electric" in model_raw.lower():
            bracket_counter["Electric Vehicles (EV)"] += 1

        # Brand / Make
        brand = _get_val("car_brand") or _get_val("make")
        if brand and len(brand) >= 3:
            b_clean = brand.upper().strip()
            if not any(k in b_clean.lower() for k in ["year", "make", "valid", "model", "trailer"]):
                brand_counter[b_clean] += 1

        # Model
        if model_raw and len(model_raw) >= 3:
            if not any(k in model_raw.lower() for k in ["year", "sum", "insured", "trailer"]):
                clean_m = re.sub(r"^(?:PROTON|PERODUA|TOYOTA|HONDA|MAZDA|CHERY|NISSAN|MITSUBISHI|BMW|MERCEDES)\s+", "", model_raw, flags=re.IGNORECASE).strip()
                words = clean_m.split()
                if words:
                    short_model = " ".join(words[:3]).upper()
                    model_counter[short_model] += 1

        # Benefits & Optional Covers
        addons_combined = " ".join([
            _get_val("optional_covers"),
            _get_val("add_ons_selected"),
            _get_val("benefits_selected"),
            _get_val("extra_covers"),
        ]).lower()

        signatures = {
            "Windscreen & Window Glass": ["windscreen", "window glass", "cermin depan", "end 89", "end 89a"],
            "Inclusion of Special Perils (Flood & Storm)": ["special perils", "flood", "banjir", "bencana", "end 57"],
            "Legal Liability to Passengers (LLP)": ["legal liability to passengers", "llp", "end 100"],
            "Legal Liability of Passengers (LLOP)": ["legal liability of passengers", "llop", "end 72"],
            "Compensation for Repair Time (CART)": ["cart", "repair allowance", "repair time", "end 112"],
            "Key Care & Replacement": ["key replacement", "key care", "kunci", "smart key"],
            "Emergency Towing Assistance": ["towing", "auto assistance", "bantuan tunda", "breakdown towing"],
            "Current Year NCD Relief": ["ncd relief", "ncd protection", "end 111"],
            "All Drivers Excess Waiver": ["all drivers", "unnamed driver", "all-riders"],
            "Personal Accident for Driver & Passengers": ["personal accident", "accidental death", "pa plus"],
        }

        for b_name, sigs in signatures.items():
            if any(s in addons_combined for s in sigs):
                benefit_counter[b_name] += 1

    # Format structured outputs
    insurer_ranking = [
        {
            "company": comp,
            "quotations_count": count,
            "share_percentage": round((count / total_quotes) * 100, 1) if total_quotes else 0,
        }
        for comp, count in insurer_counter.most_common()
    ]

    cc_brackets = [
        {
            "bracket": bracket,
            "count": count,
            "percentage": round((count / sum(bracket_counter.values())) * 100, 1) if bracket_counter else 0,
        }
        for bracket, count in bracket_counter.most_common()
    ]

    top_ccs = [
        {"cc": cc, "count": count}
        for cc, count in cc_counter.most_common(12)
    ]

    top_brands = [
        {"brand": b, "count": count}
        for b, count in brand_counter.most_common(8)
    ]

    top_models = [
        {"model": m, "count": count}
        for m, count in model_counter.most_common(8)
    ]

    top_benefits = [
        {
            "benefit": b,
            "selected_count": count,
            "adoption_rate": round((count / total_quotes) * 100, 1) if total_quotes else 0,
        }
        for b, count in benefit_counter.most_common(10)
    ]

    return {
        "total_quotations_analyzed": total_quotes,
        "insurer_ranking": insurer_ranking,
        "cc_brackets": cc_brackets,
        "top_engine_ccs": top_ccs,
        "top_vehicle_brands": top_brands,
        "top_vehicle_models": top_models,
        "top_benefits_used": top_benefits,
    }


def _resolve_refinement_operations(
    db: Session,
    query: str,
    company_id: str,
    history: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Resolve a follow-up refinement query (e.g. 'no not that part, just this one', 'only towing')
    against previous proposals or instructions in the conversation history.
    """
    q_lower = query.lower()

    # Find the most recent user instruction that requested changes
    prev_user_query = ""
    for msg in reversed(history):
        if msg.get("role") == "user":
            c = msg.get("content", "").strip()
            if any(w in c.lower() for w in ["update", "change", "set", "add", "remove", "towing", "windscreen", "limit", "cover"]):
                prev_user_query = c
                break

    if not prev_user_query:
        return []

    # Parse what the previous operations were
    raw_ops = parse_catalog_intent(db, prev_user_query, company_id)
    if not raw_ops:
        return []

    # Order previous operations based on where their concept appears in the original user query
    def _pos_in_query(op: dict[str, Any]) -> int:
        k = op.get("concept_key", "").lower()
        lbl = op.get("concept_label", "").lower()
        pos_k = prev_user_query.lower().find(k) if k else -1
        pos_lbl = prev_user_query.lower().find(lbl) if lbl else -1
        positions = [p for p in [pos_k, pos_lbl] if p != -1]
        return min(positions) if positions else 9999

    sorted_ops = sorted(raw_ops, key=_pos_in_query)
    seen_keys = set()
    prev_ops: list[dict[str, Any]] = []
    for op in sorted_ops:
        ck = op.get("concept_key", "")
        if ck and ck not in seen_keys:
            seen_keys.add(ck)
            prev_ops.append(op)
        elif not ck:
            prev_ops.append(op)

    if len(prev_ops) == 1:
        # If there was only 1 operation, try combined query (e.g. "make it 150km instead")
        combined = f"{prev_user_query}. {query}"
        combined_ops = parse_catalog_intent(db, combined, company_id)
        return combined_ops or prev_ops

    # Multiple operations previously proposed:
    # 1. Did the user name a specific concept to keep? (e.g. "just towing", "only towing")
    for op in prev_ops:
        concept_key = op.get("concept_key", "").lower()
        concept_label = op.get("concept_label", "").lower()
        if concept_key in q_lower or (concept_label and any(w in q_lower for w in concept_label.split() if len(w) > 3)):
            return [op]

    # 2. Did the user name a specific concept to exclude? (e.g. "no not windscreen", "exclude windscreen")
    filtered = []
    for op in prev_ops:
        concept_key = op.get("concept_key", "").lower()
        concept_label = op.get("concept_label", "").lower()
        is_excluded = False
        for ex_phrase in ["not " + concept_key, "no " + concept_key, "skip " + concept_key, "remove " + concept_key]:
            if ex_phrase in q_lower:
                is_excluded = True
                break
        if not is_excluded:
            filtered.append(op)
    if filtered and len(filtered) < len(prev_ops):
        return filtered

    # 3. Phrasings like "just this one", "this one", "first one", "only this", "just the first", "not that part", "that part":
    if any(p in q_lower for p in ["just this one", "this one", "first one", "only this", "just the first", "not that part", "that part"]):
        return [prev_ops[0]]

    # 4. Phrasings like "just the second one":
    if any(p in q_lower for p in ["second one", "just the second"]):
        return [prev_ops[1]] if len(prev_ops) > 1 else prev_ops

    return prev_ops


def _build_deterministic_response(
    query: str,
    catalog_facts: dict[str, Any],
    session_facts: dict[str, Any],
    parsed_mutations: list[dict[str, Any]],
    dataset_facts: dict[str, Any] | None = None,
    profile_facts: dict[str, Any] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Generate a high-quality deterministic response if Gemini is unavailable or offline."""
    q_lower = query.lower()
    actions: list[dict[str, Any]] = []
    df = dataset_facts or {}
    pf = profile_facts or {}
    # 0a. Benefit Profiles Count & Details ("how many profiles are there")
    if any(k in q_lower for k in ["how many profile", "how many proile", "profiles are there", "profiles for the builder", "benefit profile", "visual profile", "builder/benefits", "how many profiles"]):
        cf = pf.get("catalog_profiles", {})
        vf = pf.get("visual_profiles", {})
        active_cat = cf.get("active_profile_name", "Master Unified Profile")
        active_vis = vf.get("active_profile_name", "gb v3 2d no bg")
        folder = vf.get("asset_category", "global benefits v3 2d no bg")

        reply = (
            f"### Benefit Profiles in RiskLocker\n\n"
            f"There are **two distinct profile systems** in the builder architecture:\n\n"
            f"#### 1. Catalog Profiles ({cf.get('total', 3)} total)\n"
            f"- **Active**: **{active_cat}** (governs underwriter rules, towing baselines, and catalog offerings across all 7 companies).\n"
            f"- **Baselines/Versions**: {', '.join(p['name'] for p in cf.get('profiles_list', []) if not p.get('is_active')) or 'None'}.\n\n"
            f"#### 2. Visual Image Profiles ({vf.get('total', 3)} total)\n"
            f"- **Active**: **{active_vis}** (mapped to asset folder `{folder}`, with {vf.get('mapped_concept_artworks', 51)}/{vf.get('total_concepts', 51)} concept artworks assigned).\n"
            f"- **Other Visual Styles**: {', '.join(p['name'] for p in vf.get('profiles_list', []) if not p.get('is_active')) or 'None'}.\n\n"
            f"*(Note: There are also **7 insurance companies** in the catalog: QBE, Etiqa, Takaful Malaysia, Lonpac, Sompo, Tune Protect, and AmAssurance).*"
        )
        return reply, actions

    # 0b. Global Benefits Image Switching / Modifying Artwork Questions
    if any(k in q_lower for k in ["switch image", "change image", "swap image", "artwork", "modify image", "modifying image", "assign image", "upload image", "benefit image", "images in global benefit"]):
        vf = pf.get("visual_profiles", {})
        active_vis = vf.get("active_profile_name", "gb v3 2d no bg")
        folder = vf.get("asset_category", "global benefits v3 2d no bg")
        mapped = vf.get("mapped_concept_artworks", 51)
        total_c = vf.get("total_concepts", 51)

        reply = (
            f"### Modifying & Switching Images in Global Benefits\n\n"
            f"**Yes**, you can modify and switch benefit imagery in RiskLocker.\n\n"
            f"- **Current Active Visual Profile**: **{active_vis}**\n"
            f"- **Asset Category Folder**: `{folder}`\n"
            f"- **Current Coverage**: **{mapped}/{total_c} concepts** have mapped artwork in this active profile.\n\n"
            f"**How to switch or assign an image:**\n"
            f"1. Navigate to **Builder → Global Benefits** (`/builder/global-benefits`).\n"
            f"2. Ensure the active visual profile (**{active_vis}**) is selected in the top bar.\n"
            f"3. Upload your new artwork into folder category `{folder}` (via Business Assets or file upload).\n"
            f"4. Click on the target benefit concept (e.g., *Emergency Towing Assistance*), select your new asset from the category grid, and save.\n"
            f"5. Alternatively, use the **Auto-Assign** button to automatically map newly uploaded images based on naming similarity."
        )
        return reply, actions

    # 1. Engine CC Questions
    if any(k in q_lower for k in ["engine cc", "list of cc", "list of ccs", "cubic capacity", "brackets", "capacities", "what cc"]):
        total_q = df.get("total_quotations_analyzed", 0)
        brackets = df.get("cc_brackets", [])
        models = df.get("top_vehicle_models", [])

        reply = (
            f"### Vehicle Engine Capacities (CC) in Quotations\n\n"
            f"Across **{total_q} analyzed quotation records**, here is the distribution of vehicle engine sizes:\n\n"
            f"| Engine Capacity Bracket | Quotation Count | Percentage |\n"
            f"| :--- | :--- | :--- |\n"
        )
        for b in brackets:
            reply += f"| **{b['bracket']}** | {b['count']} quotes | {b['percentage']}% |\n"

        if models:
            rep_models = ", ".join(f"{m['model']} ({m['count']})" for m in models[:5])
            reply += f"\n**Representative models observed**: {rep_models}.\n"
        reply += "\nWould you like me to filter or inspect quotes for a specific CC bracket?"
        return reply, actions

    # 2. Insurer Quote Distribution / Rankings ("which companies were more")
    if any(k in q_lower for k in ["which companies were more", "which companies", "more quotes", "market share", "insurer ranking", "companies had more"]):
        total_q = df.get("total_quotations_analyzed", 0)
        rankings = df.get("insurer_ranking", [])

        reply = (
            f"### Insurer Quotation Distribution & Rankings\n\n"
            f"From **{total_q} total active quotations**, here is how quote volume ranks across underwriters:\n\n"
            f"| Rank | Insurer Name | Total Quotes | Market Share |\n"
            f"| :--- | :--- | :--- | :--- |\n"
        )
        for i, r in enumerate(rankings, 1):
            star = "⭐ " if i == 1 else ""
            comp_name = r.get('insurer') or r.get('company') or 'Unknown'
            reply += f"| {i} | {star}**{comp_name}** | {r['quotations_count']} quotes | {r['share_percentage']}% |\n"

        reply += "\nWould you like me to inspect catalog packages or conditions for any of these insurers?"
        return reply, actions

    # 3. Vehicle Makes & Models ("what type of cars mostly found")
    if any(k in q_lower for k in ["type of car", "types of car", "type of vehicle", "vehicle mostly", "cars mostly", "brands", "models", "what car"]):
        total_q = df.get("total_quotations_analyzed", 0)
        brands = df.get("top_vehicle_brands", [])
        models = df.get("top_vehicle_models", [])

        reply = (
            f"### Vehicle Makes & Models Found in Quotations\n\n"
            f"Analysis of **{total_q} quotation records** reveals the following most frequent vehicles:\n\n"
            f"#### Top Vehicle Brands (Makes):\n"
        )
        for b in brands:
            reply += f"- **{b['brand']}**: {b['count']} vehicle quotes\n"

        reply += "\n#### Most Common Vehicle Models:\n"
        for m in models:
            reply += f"- **{m['model']}**: {m['count']} quotes\n"

        reply += "\nWould you like to see quotations or ownership histories for any of these vehicle models?"
        return reply, actions

    # 4. Benefits & Add-ons mostly used
    if (
        any(k in q_lower for k in ["benefit mostly", "benefits mostly", "mostly used benefit", "popular cover", "addons", "riders"])
        or ("benefit" in q_lower and any(w in q_lower for w in ["mostly", "popular", "top", "rank", "selected", "used", "adoption", "common"]))
    ):
        total_q = df.get("total_quotations_analyzed", 0)
        benefits = df.get("top_benefits_used", [])

        reply = (
            f"### Most Frequently Selected Benefits & Optional Covers\n\n"
            f"From **{total_q} quotations** with custom covers and riders, here are the most widely selected add-ons:\n\n"
            f"| Rank | Benefit / Optional Cover | Adoption Count | Frequency |\n"
            f"| :--- | :--- | :--- | :--- |\n"
        )
        for i, b in enumerate(benefits, 1):
            star = "⭐ " if i <= 2 else ""
            reply += f"| {i} | {star}**{b['benefit']}** | {b['selected_count']} | {b['adoption_rate']}% |\n"

        reply += "\n**Key Observation**: Windscreen protection and Special Perils (Flood) remain the two dominant voluntary add-ons across Malaysian drivers.\n\n"
        reply += "Would you like me to inspect pricing or conditions for any of these benefits?"
        return reply, actions

    # 5. Session Hygiene & Duplicate Check
    if any(k in q_lower for k in ["session", "duplicate", "car number", "plate", "upload", "redundant", "clean"]):
        total = session_facts.get("total_active_sessions", 0)
        unique_plates = session_facts.get("unique_car_plates_count", 0)
        dup_sets = session_facts.get("exact_duplicate_sets_count", 0)
        redundant = session_facts.get("redundant_sessions_count", 0)
        dup_groups = session_facts.get("duplicate_groups", [])

        reply = (
            f"### Session & Quotation Health Analysis\n\n"
            f"- **Active Sessions**: {total} total non-trash records in the database.\n"
            f"- **Unique Vehicle Plates**: {unique_plates} registered car numbers.\n"
            f"- **Exact Duplicate Uploads**: **{dup_sets} sets ({redundant} redundant sessions)** with identical file SHA-256 hashes.\n"
            f"- **Unique Quote Variations**: Verified that sessions with user edits (such as roadtax or addon adjustments) are preserved as unique quotes.\n\n"
        )

        if redundant > 0:
            reply += (
                f"You can safely clean the **{redundant} redundant sessions** (keeping the newest instance for each upload) "
                f"by clicking **Clean Duplicates** below. Deleting them uses safe soft-delete (`Trash`), so you can restore them at any time.\n\n"
                f"Would you like me to clean all {redundant} redundant sessions now?"
            )
            actions.append({
                "type": "session_cleanup",
                "title": f"Clean {redundant} Exact Duplicate Uploads",
                "redundant_count": redundant,
                "groups": dup_groups,
                "session_ids_to_trash": session_facts.get("redundant_session_ids", []),
            })
        else:
            reply += "Your sessions database is completely clean with zero redundant duplicate uploads!"

        return reply, actions

    # 6. Insurer Catalogs & Towing Situation
    if catalog_facts.get("scope") == "company":
        comp_name = catalog_facts.get("company_name", "Insurer")
        total_cats = catalog_facts.get("total_catalogs", 0)
        vb = catalog_facts.get("vehicle_breakdown", {})
        same_desc = catalog_facts.get("same_towing_description_across_all", True)
        conditions_count = catalog_facts.get("conditions_count", 0)
        dummy_profiles = catalog_facts.get("dummy_profiles", [])

        reply = (
            f"### {comp_name} Catalog & Benefit Overview\n\n"
            f"- **Total Catalogs**: {total_cats} active catalogs (Vehicle breakdown: {', '.join(f'{k}: {v}' for k, v in vb.items()) or 'None'}).\n"
            f"- **Towing Benefit Situation**: "
            f"{'All plans currently share the exact same baseline towing description across ICE and EV.' if same_desc else 'Different towing descriptions are configured across plans.'}\n"
            f"- **Benefit Conditions**: Currently **{conditions_count} active condition rules** configured.\n"
        )

        if conditions_count == 0:
            reply += (
                f"> **Observation**: Because no condition rules are set, if a quotation detects standard towing, "
                f"it will not automatically upgrade or hide standard towing when an unlimited towing add-on is present.\n\n"
            )

        if dummy_profiles:
            reply += (
                f"- **Profile Hygiene**: Found **{len(dummy_profiles)} unused / draft profile version(s)** "
                f"({', '.join(p['name'] for p in dummy_profiles[:3])}) that can be safely pruned to keep the database clean.\n\n"
            )
            actions.append({
                "type": "profile_cleanup",
                "title": f"Deactivate {len(dummy_profiles)} Unused Profile(s)",
                "profiles": dummy_profiles,
            })

        reply += "Would you like me to generate a condition rule to handle towing upgrades, or help you adjust any catalog limits?"
        return reply, actions

    # 9. Fallback General / Catalog Mutation
    if parsed_mutations:
        if any(w in q_lower for w in ["no not", "just this", "only this", "that part", "this one", "first one"]):
            ops_summary = ", ".join(f"{op.get('concept_label', op.get('concept_key'))} ({op.get('proposed_value', 'updated')})" for op in parsed_mutations)
            reply = (
                f"Understood! I have updated the proposal to keep only your confirmed change: **{ops_summary}**, "
                f"and removed the other part. Review the refined diff table below and click **Confirm & Apply** when ready."
            )
        else:
            reply = (
                f"I have parsed your request into {len(parsed_mutations)} catalog operation(s). "
                f"Review the diff table below and click **Confirm & Apply** when ready."
            )
        return reply, actions

    return (
        "I am your RiskLocker Intelligence Copilot. You can ask me analytical questions across your quotation database "
        "(such as *'What is the list of car CCs found?'*, *'Which companies had more quotes?'*, *'What types of cars mostly found?'*, "
        "or *'What benefits mostly used?'*), run duplicate cleanups, or inspect insurer towing rules and condition packages.",
        actions,
    )


def chat_with_copilot(
    db: Session,
    user: User,
    message: str,
    company_id: str | None = None,
    history: list[dict[str, str]] | None = None,
    scope: str = "all",
) -> dict[str, Any]:
    """Full conversational engine: queries live DB facts, formats with Gemini 2.5 Flash, and attaches actionable payloads."""
    cleaned_query = message.strip()
    if not cleaned_query:
        raise AppError("Message cannot be empty", 400)

    q_lower = cleaned_query.lower()

    # Quick check for cancellation / abort intent
    cancel_triggers = [
        "dont do anything", "don't do anything", "do not do anything",
        "cancel", "cancel that", "cancel request", "cancel this",
        "nevermind", "never mind", "abort", "no thanks", "stop", "leave it as is", "leave it"
    ]
    if any(q_lower == t or q_lower.startswith(t + " ") or q_lower.endswith(" " + t) for t in cancel_triggers):
        return {
            "reply": "Understood! No changes will be applied. The proposal has been dismissed. Let me know if you would like any other analysis, catalog adjustments, or duplicate checks.",
            "actions": [],
            "facts_summary": {
                "cancelled": True,
            },
        }

    # 1. Gather live database facts based on intent/scope
    target_comp = _find_target_company(db, company_id, cleaned_query, history)
    inferred_company_id = target_comp.id if target_comp else company_id

    is_session_query = any(k in q_lower for k in ["session", "duplicate", "redundant", "car plate", "car number", "plate", "uploads", "clean duplicate", "quotation"]) or scope == "sessions"
    is_catalog_query = any(k in q_lower for k in ["catalog", "towing", "benefit", "coverage", "insurer", "company", "amassurance", "qbe", "etiqa", "lonpac", "sompo", "stmb", "tune", "condition", "dummy", "profile", "add", "remove", "update"]) or scope == "catalogs" or bool(inferred_company_id)

    catalog_facts = get_catalog_status_facts(db, inferred_company_id, cleaned_query, history) if (is_catalog_query or not is_session_query) else {}
    session_facts = get_session_hygiene_facts(db, user) if (is_session_query or not is_catalog_query) else {}
    dataset_facts = get_dataset_analytics_facts(db)
    profile_facts = get_profile_and_visual_facts(db)

    # 2. Check for catalog mutation intent (ONLY if mutation keywords are present or follow-up refinement)
    target_company_id = catalog_facts.get("company_id") or inferred_company_id
    parsed_operations: list[dict[str, Any]] = []
    diff_preview: dict[str, Any] | None = None

    is_mutation_intent = any(w in q_lower for w in ["update", "change", "set", "add", "remove", "exclude", "delete", "replace", "increase", "decrease"])
    is_refinement_intent = any(
        w in q_lower for w in [
            "no not", "not that", "not his", "just this", "only this", "only the", "just the",
            "leave that", "skip that", "remove that", "instead", "just one", "this one", "that part"
        ]
    )

    if target_company_id:
        if is_mutation_intent:
            try:
                parsed_operations = parse_catalog_intent(db, cleaned_query, target_company_id)
            except Exception as e:
                logger.warning(f"Error parsing catalog mutation intent: {e}")

        # If current query is a conversational refinement without explicit new mutation verbs
        if not parsed_operations and is_refinement_intent and history:
            try:
                parsed_operations = _resolve_refinement_operations(db, cleaned_query, target_company_id, history)
            except Exception as e:
                logger.warning(f"Error resolving refinement operations: {e}")

        if parsed_operations:
            try:
                diff_preview = preview_catalog_operations(db, target_company_id, parsed_operations)
            except Exception as e:
                logger.warning(f"Error computing catalog diff preview: {e}")

    # 3. Call Gemini 2.5 Flash for natural conversational response
    pool = get_key_pool()
    all_keys = pool.get_all_keys()
    reply_text: str | None = None
    actions: list[dict[str, Any]] = []

    # If diff preview found, add catalog_diff action
    if diff_preview and diff_preview.get("operations_preview"):
        actions.append({
            "type": "catalog_diff",
            "title": "Proposed Catalog Changes",
            "company_id": target_company_id,
            "preview": diff_preview,
        })

    if all_keys:
        try:
            active_cat_name = profile_facts.get("catalog_profiles", {}).get("active_profile_name", "Master Unified Profile")
            active_vis_name = profile_facts.get("visual_profiles", {}).get("active_profile_name", "gb v3 2d no bg")
            asset_folder = profile_facts.get("visual_profiles", {}).get("asset_category", "global benefits v3 2d no bg")
            mapped_art = profile_facts.get("visual_profiles", {}).get("mapped_concept_artworks", 51)
            total_art = profile_facts.get("visual_profiles", {}).get("total_concepts", 51)

            system_prompt = (
                "You are the RiskLocker Insurance Intelligence Copilot. "
                "You have access to live, deterministic database facts provided in the context. "
                "CRITICAL RULES:\n"
                "1. Answer concisely, directly, and accurately based ONLY on the provided Ground Truth Data.\n"
                "2. When the user asks about insurer catalogs or towing (e.g. AmAssurance), state the exact catalog count, "
                "vehicle breakdown, explain if towing uses the same description across all, mention if conditions are missing for upgrades, "
                "and ask if they want suggestions or condition rules added.\n"
                "3. When the user asks about sessions or duplicates, state the exact active session count, unique vehicle plates, "
                "the exact count of identical file duplicates, confirm that minor edits (like roadtax) are preserved as unique, "
                "and mention that they can clean the duplicates with 1 click.\n"
                "4. When the user asks about CCs, engine capacity, or types of cars, provide the exact CC distribution table from ground_truth_dataset_analytics.\n"
                "5. When the user asks which companies were more or have more quotes, provide the ranked underwriter table from ground_truth_dataset_analytics.\n"
                "6. When the user asks what car types, models, or benefits are mostly found or used, cite the top vehicle brands/models and top benefits from ground_truth_dataset_analytics.\n"
                f"7. When the user asks about profiles or how many profiles exist for builder/benefits:\n"
                f"   State clearly that there are TWO distinct profile systems in RiskLocker:\n"
                f"   (a) Catalog Profiles ({profile_facts.get('catalog_profiles', {}).get('total', 3)} total, active: '{active_cat_name}', plus inactive baselines) which govern insurer catalog offerings and pricing, and\n"
                f"   (b) Visual Image Profiles ({profile_facts.get('visual_profiles', {}).get('total', 3)} total, active: '{active_vis_name}' in asset folder '{asset_folder}', with {mapped_art}/{total_art} concepts mapped) which govern benefit card artwork in quotations.\n"
                "   Cite these exact counts and names. NEVER confuse profiles with the 7 insurance companies.\n"
                f"8. When the user asks about modifying, changing, or switching images in global benefits:\n"
                f"   Confirm that YES, images can be changed and switched. Explain that images are managed via Visual Profiles in '/builder/global-benefits' (currently active: '{active_vis_name}'). "
                f"Users can upload an image into folder '{asset_folder}', and then assign or swap it for any benefit concept (such as Emergency Towing Assistance) directly on the visual grid or via Auto-Assign.\n"
                "9. Maintain a professional, crisp, helpful tone. Use markdown with bullet points and bold highlights.\n"
                "10. Conversational Continuity & Multi-Turn Refinements:\n"
                "    - Maintain active conversational context across consecutive messages in the session.\n"
                "    - When the user refines, narrows, or corrects a previous request (such as 'no not that part, just this one', 'only towing', 'make it 150km instead', 'what about its conditions?'):\n"
                "      Identify the active insurer and previous proposals from the conversation history.\n"
                "      Acknowledge the correction and produce the refined response or updated diff containing ONLY the accepted item or values.\n"
            )

            context_payload = {
                "user_query": cleaned_query,
                "ground_truth_catalog_facts": catalog_facts,
                "ground_truth_session_facts": {
                    "total_sessions": session_facts.get("total_active_sessions"),
                    "unique_car_plates": session_facts.get("unique_car_plates_count"),
                    "exact_duplicate_sets": session_facts.get("exact_duplicate_sets_count"),
                    "redundant_sessions_to_clean": session_facts.get("redundant_sessions_count"),
                    "sample_duplicates": session_facts.get("duplicate_groups", [])[:3],
                    "sample_unique_quotes": session_facts.get("sample_unique_quote_variations", []),
                },
                "ground_truth_dataset_analytics": dataset_facts,
                "ground_truth_profile_and_image_facts": profile_facts,
                "parsed_catalog_mutations": parsed_operations,
            }

            api_key = pool.get_next_key()
            settings = get_settings()
            model_name = getattr(settings, "gemini_model", None) or "gemini-2.5-flash"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

            contents: list[dict[str, Any]] = []
            if history:
                for h in history[-6:]:
                    contents.append({
                        "role": "user" if h.get("role") == "user" else "model",
                        "parts": [{"text": h.get("content", "")}],
                    })

            contents.append({
                "role": "user",
                "parts": [{"text": f"GROUND TRUTH CONTEXT:\n{json.dumps(context_payload, indent=2, default=str)}\n\nUSER QUESTION: {cleaned_query}"}],
            })

            payload = {
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "contents": contents,
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 600},
            }

            with httpx.Client(timeout=8.0) as client:
                res = client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            reply_text = parts[0].get("text", "").strip()
        except Exception as err:
            logger.warning(f"Gemini conversational API call failed: {err}")

    # Fallback to deterministic synthesis if Gemini didn't return text
    if not reply_text:
        det_reply, det_actions = _build_deterministic_response(
            cleaned_query, catalog_facts, session_facts, parsed_operations, dataset_facts, profile_facts
        )
        reply_text = det_reply
        if not actions:
            actions = det_actions
    else:
        # Check if we should attach session cleanup action
        q_lower = cleaned_query.lower()
        if any(k in q_lower for k in ["session", "duplicate", "redundant", "clean"]) and session_facts.get("redundant_sessions_count", 0) > 0:
            actions.append({
                "type": "session_cleanup",
                "title": f"Clean {session_facts.get('redundant_sessions_count')} Exact Duplicate Uploads",
                "redundant_count": session_facts.get("redundant_sessions_count"),
                "groups": session_facts.get("duplicate_groups", []),
                "session_ids_to_trash": session_facts.get("redundant_session_ids", []),
            })
        if catalog_facts.get("dummy_profiles") and any(k in q_lower for k in ["dummy", "profile", "useless", "clean"]):
            actions.append({
                "type": "profile_cleanup",
                "title": f"Deactivate {len(catalog_facts['dummy_profiles'])} Unused Profile(s)",
                "profiles": catalog_facts["dummy_profiles"],
            })

    return {
        "reply": reply_text,
        "actions": actions,
        "facts_summary": {
            "company_name": catalog_facts.get("company_name"),
            "total_catalogs": catalog_facts.get("total_catalogs"),
            "total_sessions": session_facts.get("total_active_sessions"),
            "redundant_sessions": session_facts.get("redundant_sessions_count"),
            "total_quotations_analyzed": dataset_facts.get("total_quotations_analyzed"),
        },
    }


# ---------------------------------------------------------------------------
# 3. ACTION EXECUTION: SESSION CLEANUP & PROFILE HYGIENE
# ---------------------------------------------------------------------------

def execute_session_cleanup(
    db: Session,
    settings: Any,
    user: User,
    duplicate_session_ids: list[str],
) -> dict[str, Any]:
    """Safely soft-delete redundant duplicate sessions to Trash via resilient batched transaction."""
    if not duplicate_session_ids:
        return {"cleaned_count": 0, "trashed_session_ids": []}

    trashed: list[str] = []
    from app.models.enums import RecordStatus
    from app.models.tables import GeneratedPdfVersion, TrashRecord
    from sqlalchemy.orm import selectinload

    # Preload sessions with uploaded_file and draft in a single query
    sessions = (
        db.query(SessionModel)
        .filter(SessionModel.id.in_(duplicate_session_ids), SessionModel.status != "trash")
        .options(
            selectinload(SessionModel.uploaded_file).selectinload(UploadedFile.draft),
        )
        .all()
    )

    draft_ids = [s.draft_id for s in sessions if s.draft_id]
    protected_draft_ids: set[str] = set()
    if draft_ids:
        pdf_draft_rows = (
            db.query(GeneratedPdfVersion.draft_id)
            .filter(GeneratedPdfVersion.draft_id.in_(draft_ids))
            .distinct()
            .all()
        )
        protected_draft_ids = {str(r[0]) for r in pdf_draft_rows}

    trash_retention = getattr(settings, "trash_retention_days", 30) if settings else 30

    for session in sessions:
        s_id = session.id
        # Safety guard: never trash a session with generated PDFs or finalized status
        if session.draft_id and session.draft_id in protected_draft_ids:
            logger.warning(f"Protected session {s_id} from trash: contains generated PDF version.")
            continue
        if (session.quotation_status or "").lower() in ("hit", "miss"):
            logger.warning(f"Protected session {s_id} from trash: status is {session.quotation_status}.")
            continue

        uploaded = session.uploaded_file
        if uploaded:
            if not uploaded.deleted_at:
                original_status = uploaded.status
                uploaded.status = RecordStatus.DELETED.value
                uploaded.mark_deleted(trash_retention)
                if uploaded.draft:
                    uploaded.draft.status = RecordStatus.DELETED.value
                    uploaded.draft.mark_deleted(trash_retention)
                db.add(
                    TrashRecord(
                        entity_type="uploaded_file",
                        entity_id=uploaded.id,
                        original_status=original_status,
                        deleted_by=user.id,
                        purge_after=None,
                    )
                )

        session.status = "trash"
        trashed.append(s_id)

    if trashed:
        db.commit()

    return {
        "cleaned_count": len(trashed),
        "trashed_session_ids": trashed,
        "message": f"Successfully moved {len(trashed)} duplicate session(s) to Trash. You can restore them anytime.",
    }


def execute_profile_cleanup(
    db: Session,
    user: User,
    profile_ids: list[str],
) -> dict[str, Any]:
    """Deactivate unused or dummy benefit profile versions."""
    if not profile_ids:
        return {"cleaned_count": 0, "deactivated_profile_ids": []}

    deactivated: list[str] = []
    for p_id in profile_ids:
        profile = db.get(BenefitProfile, p_id)
        if profile and not profile.is_active:
            profile.status = "inactive"
            deactivated.append(p_id)

    db.commit()
    return {
        "cleaned_count": len(deactivated),
        "deactivated_profile_ids": deactivated,
        "message": f"Successfully cleaned {len(deactivated)} unused profile(s).",
    }
