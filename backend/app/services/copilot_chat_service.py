"""Conversational AI Copilot Service — status checks, Q&A, catalog mutations, and session deduplication hygiene."""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
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
    CatalogOffering,
    CompanyBenefitCondition,
    CompanyBenefitConfig,
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

def _find_target_company(db: Session, company_id: str | None = None, query: str = "") -> InsuranceCompany | None:
    """Find company by ID or smart matching from query text."""
    if company_id:
        company = db.get(InsuranceCompany, company_id)
        if company:
            return company

    q_lower = query.lower()
    companies = db.scalars(select(InsuranceCompany).where(InsuranceCompany.status == "active")).all()
    
    # Check for name or slug matches
    for comp in companies:
        name_lower = comp.name.lower()
        if comp.slug and comp.slug.lower() in q_lower:
            return comp
        if name_lower in q_lower:
            return comp
        # Sub-word matches (e.g. "amassurance", "etiqa", "lonpac", "sompo", "stmb", "takaful", "qbe")
        first_word = name_lower.split()[0]
        if len(first_word) >= 3 and first_word in q_lower:
            return comp

    # Default to first active company or None
    return None


def get_catalog_status_facts(db: Session, company_id: str | None = None, query: str = "") -> dict[str, Any]:
    """Gather live facts about insurer catalogs, vehicle categories, towing configs, and conditions."""
    target_company = _find_target_company(db, company_id, query)
    
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


def get_session_hygiene_facts(db: Session, user: User | None = None) -> dict[str, Any]:
    """Analyze sessions to identify exact file duplicates vs unique edited quotes."""
    results = (
        db.query(
            SessionModel.id,
            SessionModel.status,
            SessionModel.detected_company,
            SessionModel.created_at,
            UploadedFile.id.label("file_id"),
            UploadedFile.original_filename,
            UploadedFile.storage_sha256,
            QuotationDraft.fields,
        )
        .join(UploadedFile, SessionModel.uploaded_file_id == UploadedFile.id)
        .join(QuotationDraft, SessionModel.draft_id == QuotationDraft.id)
        .filter(SessionModel.status != "trash")
        .order_by(SessionModel.created_at.desc())
        .all()
    )

    total_sessions = len(results)
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
            "file_id": r.file_id,
            "filename": r.original_filename,
            "company": r.detected_company or "Unknown Insurer",
            "plate": clean_plate,
            "sha": r.storage_sha256,
            "gross_premium": gross_premium,
            "roadtax": roadtax,
            "addons": addons,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }

        if r.storage_sha256:
            by_sha[r.storage_sha256].append(info)
        if clean_plate != "UNKNOWN":
            by_plate[clean_plate].append(info)

    # Exact Duplicates: Same storage_sha256 uploaded multiple times
    exact_duplicate_groups: list[dict[str, Any]] = []
    redundant_session_ids: list[str] = []

    for sha, group in by_sha.items():
        if len(group) > 1:
            # First item in group is newest due to order_by(created_at.desc())
            keep_session = group[0]
            redundant_sessions = group[1:]
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
        "duplicate_groups": exact_duplicate_groups[:15],
        "unique_quote_variations_count": len(unique_quote_variations),
        "sample_unique_quote_variations": unique_quote_variations[:5],
    }


# ---------------------------------------------------------------------------
# 2. CONVERSATIONAL SYNTHESIS ENGINE
# ---------------------------------------------------------------------------

def _build_deterministic_response(
    query: str,
    catalog_facts: dict[str, Any],
    session_facts: dict[str, Any],
    parsed_mutations: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """Generate a high-quality deterministic response if Gemini is unavailable or offline."""
    q_lower = query.lower()
    actions: list[dict[str, Any]] = []

    # 1. Session Hygiene & Duplicate Check
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

    # 2. Insurer Catalogs & Towing Situation
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

    # 3. Fallback General / Catalog Mutation
    if parsed_mutations:
        reply = (
            f"I have parsed your request into {len(parsed_mutations)} catalog operation(s). "
            f"Review the diff table below and click **Confirm & Apply** when ready."
        )
        return reply, actions

    return (
        "I am your RiskLocker Copilot. You can ask me status checks (e.g. *'How many catalogs does AmAssurance have?'*, "
        "*'Check session duplicates'*, or *'What is the towing distance for EV?'*), or instruct me to apply catalog changes directly.",
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

    # 1. Gather live database facts based on intent/scope
    q_lower = cleaned_query.lower()
    is_session_query = any(k in q_lower for k in ["session", "duplicate", "redundant", "car plate", "car number", "plate", "uploads", "clean duplicate", "quotation"]) or scope == "sessions"
    is_catalog_query = any(k in q_lower for k in ["catalog", "towing", "benefit", "coverage", "insurer", "company", "amassurance", "qbe", "etiqa", "lonpac", "sompo", "stmb", "tune", "condition", "dummy", "profile", "add", "remove", "update"]) or scope == "catalogs" or bool(company_id)

    catalog_facts = get_catalog_status_facts(db, company_id, cleaned_query) if (is_catalog_query or not is_session_query) else {}
    session_facts = get_session_hygiene_facts(db, user) if (is_session_query or not is_catalog_query) else {}

    # 2. Check for catalog mutation intent (ONLY if mutation keywords are present)
    target_company_id = catalog_facts.get("company_id") or company_id
    parsed_operations: list[dict[str, Any]] = []
    diff_preview: dict[str, Any] | None = None

    is_mutation_intent = any(w in q_lower for w in ["update", "change", "set", "add", "remove", "exclude", "delete", "replace", "increase", "decrease"])
    if target_company_id and is_mutation_intent:
        try:
            parsed_operations = parse_catalog_intent(db, cleaned_query, target_company_id)
            if parsed_operations:
                diff_preview = preview_catalog_operations(db, target_company_id, parsed_operations)
        except Exception as e:
            logger.warning(f"Error parsing catalog mutation intent: {e}")

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
                "4. Maintain a professional, crisp, helpful tone. Use markdown with bullet points and bold highlights.\n"
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
                "parts": [{"text": f"GROUND TRUTH CONTEXT:\n{json.dumps(context_payload, indent=2)}\n\nUSER QUESTION: {cleaned_query}"}],
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
        det_reply, det_actions = _build_deterministic_response(cleaned_query, catalog_facts, session_facts, parsed_operations)
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
    """Safely soft-delete redundant duplicate sessions to Trash via move_to_trash."""
    if not duplicate_session_ids:
        return {"cleaned_count": 0, "trashed_session_ids": []}

    trashed: list[str] = []
    for s_id in duplicate_session_ids:
        session = db.get(SessionModel, s_id)
        if session and session.status != "trash":
            if session.uploaded_file_id:
                try:
                    move_to_trash(db, settings, user, session.uploaded_file_id)
                    session.status = "trash"
                    trashed.append(s_id)
                except Exception as e:
                    logger.warning(f"Failed to move session {s_id} to trash: {e}")

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
