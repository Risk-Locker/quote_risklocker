"""Lightweight AI Grounding Assistant Service with Targeted Low-Token Database Retrieval."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.extraction.gemini_extractor import get_key_pool
from app.models.tables import (
    BenefitConcept,
    ClientRecord,
    FieldAlias,
    InsuranceCompany,
    QuotationDraft,
    UploadedFile,
)

logger = logging.getLogger(__name__)


def _extract_potential_plates(query: str) -> list[str]:
    """Find potential Malaysian vehicle plate patterns or alphanumeric identifiers."""
    cleaned = re.sub(r"[^A-Za-z0-9\s]", " ", query.upper())
    tokens = cleaned.split()
    plates = []
    for token in tokens:
        # Standard Malaysian plate patterns like VG9XXX, WYY1234, VAA888, ABC1234, B1234A
        if re.match(r"^[A-Z]{1,3}\d{1,4}[A-Z]?$", token):
            plates.append(token)
        elif any(c.isdigit() for c in token) and any(c.isalpha() for c in token) and 3 <= len(token) <= 10:
            plates.append(token)
    return plates


def _field_val(fields: dict | None, key: str) -> str:
    """Safely extract scalar string value from draft field dict or nested value object."""
    if not fields or not isinstance(fields, dict):
        return ""
    item = fields.get(key)
    if isinstance(item, dict):
        return str(item.get("value") or "")
    return str(item or "")


def answer_grounding_query(
    db: Session,
    query: str,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Process a grounding query by retrieving targeted DB facts and calling Gemini with ultra-low token context."""
    user_query = query.strip()
    if not user_query:
        return {
            "reply": "Please ask a question about the grounding database, active insurers, benefit concepts, or vehicle records.",
            "sources": [],
            "tokens_used": 0,
        }

    facts_lines: list[str] = []
    sources: list[str] = []

    # 1. Check if asking about specific session
    if session_id:
        draft = db.scalar(
            select(QuotationDraft)
            .join(UploadedFile, UploadedFile.id == QuotationDraft.uploaded_file_id)
            .where((QuotationDraft.id == session_id) | (UploadedFile.id == session_id))
        )
        if draft:
            f = draft.fields or {}
            veh = _field_val(f, "vehicle_no") or "N/A"
            cust = _field_val(f, "customer_name") or "N/A"
            ins = _field_val(f, "insurance_company") or "N/A"
            prem = _field_val(f, "total_premium") or _field_val(f, "premium") or "N/A"
            facts_lines.append(
                f"Active Session: Vehicle={veh}, Insured={cust}, Insurer={ins}, "
                f"Premium=RM {prem}, Status={draft.status}"
            )
            sources.append("Active Session Draft")

    # 2. Check for vehicle plate or identifier query
    potential_plates = _extract_potential_plates(user_query)
    found_vehicle = False
    for plate in potential_plates:
        # Search ClientRecord
        client_matches = db.scalars(
            select(ClientRecord).where(ClientRecord.vehicle_no.ilike(f"%{plate}%")).limit(2)
        ).all()
        for cr in client_matches:
            found_vehicle = True
            facts_lines.append(
                f"Client Record for {cr.vehicle_no}: Insured={cr.customer_name or 'N/A'}, "
                f"Company={cr.insurance_company or 'N/A'}, Model={cr.car_model or 'N/A'}, "
                f"Coverage={cr.coverage_type or 'Comprehensive'}, Premium=RM {cr.total_premium or 'N/A'}, "
                f"NCD={cr.ncd_percent or cr.ncd or 'N/A'}%, Created={cr.created_at.strftime('%Y-%m-%d')}"
            )
            sources.append(f"Client Record ({cr.vehicle_no})")

        # Search QuotationDraft fields if not found in ClientRecord
        if not client_matches:
            drafts = db.scalars(select(QuotationDraft).limit(50)).all()
            for d in drafts:
                f = d.fields or {}
                v_no = _field_val(f, "vehicle_no")
                v_plate = v_no.replace(" ", "").upper()
                if v_plate and (plate in v_plate or v_plate in plate):
                    found_vehicle = True
                    cust = _field_val(f, "customer_name") or "N/A"
                    ins = _field_val(f, "insurance_company") or "N/A"
                    model = _field_val(f, "car_model") or "N/A"
                    prem = _field_val(f, "total_premium") or _field_val(f, "premium") or "N/A"
                    facts_lines.append(
                        f"Quotation Draft for {v_no}: Insured={cust}, "
                        f"Company={ins}, Model={model}, "
                        f"Total Premium=RM {prem}, Status={d.status}"
                    )
                    sources.append(f"Quotation Draft ({v_no})")
                    break

    # 3. Check for insurer / company mentions
    q_lower = user_query.lower()
    companies = db.scalars(select(InsuranceCompany).order_by(InsuranceCompany.name)).all()
    matched_companies = [
        c for c in companies
        if c.name.lower() in q_lower or (c.detection_phrases and any(p.lower() in q_lower for p in c.detection_phrases))
    ]
    if matched_companies:
        for mc in matched_companies:
            has_pack = "amassurance" in mc.name.lower()
            facts_lines.append(
                f"Insurance Company: {mc.name} (Slug: {mc.slug or 'N/A'}, Mode: {'4-Tier Package Chain' if has_pack else 'Single Add-on Mode'}, "
                f"Detection Phrases: {', '.join(mc.detection_phrases or [mc.name])})"
            )
            sources.append(f"Insurer Catalog ({mc.name})")

    # 4. Check for benefit concept mentions
    concepts = db.scalars(select(BenefitConcept).order_by(BenefitConcept.label)).all()
    matched_concepts = [
        b for b in concepts
        if b.label.lower() in q_lower or b.concept_key.lower() in q_lower
    ]
    if matched_concepts:
        for bc in matched_concepts[:3]:
            facts_lines.append(
                f"Benefit Concept: {bc.label} (Key: '{bc.concept_key}', Description: {bc.description or 'Standard Coverage'})"
            )
            sources.append(f"Benefit Concept ({bc.label})")

    # 5. General stats / summary if requested or if no specific record found
    summary_keywords = ["how much", "info", "gathered", "know", "summary", "stats", "overview", "what", "database", "catalog", "many"]
    if any(k in q_lower for k in summary_keywords) or not facts_lines:
        company_count = len(companies)
        concept_count = len(concepts)
        alias_count = db.scalar(select(func.count(FieldAlias.id))) or 0
        client_count = db.scalar(select(func.count(ClientRecord.id))) or 0
        session_count = db.scalar(select(func.count(QuotationDraft.id))) or 0
        company_names = ", ".join([c.name for c in companies])

        facts_lines.append(
            f"RiskLocker Grounding Summary: {company_count} active insurers ({company_names}), "
            f"{concept_count} standardized benefit concepts, {alias_count} field aliases, "
            f"{client_count} client records saved, {session_count} total quotation sessions processed."
        )
        sources.append("System Grounding Ledger")

    facts_text = "\n".join(facts_lines)
    system_instruction = (
        "You are the RiskLocker AI Grounding Assistant. "
        "Answer the user's question concisely in 1 to 3 direct sentences using ONLY the provided verified database facts. "
        "Be strictly factual, professional, and clear. If a vehicle plate was searched and not found, say it is not in the system records. "
        "Never invent or hallucinate data."
    )

    prompt = f"VERIFIED DATABASE FACTS:\n{facts_text}\n\nUSER QUESTION:\n{user_query}"

    pool = get_key_pool()
    all_keys = pool.get_all_keys()
    settings = get_settings()

    # If keys exist, call Gemini with tight token limits
    if all_keys:
        api_key = pool.get_next_key()
        model_name = getattr(settings, "gemini_model", None) or "gemini-3.6-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system_instruction}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 250,
            },
        }
        try:
            with httpx.Client(timeout=8.0) as client:
                res = client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates") or []
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts") or []
                        if parts:
                            reply = parts[0].get("text", "").strip()
                            pool.record_request()
                            # Rough token count estimate (prompt chars / 4)
                            est_tokens = len(prompt) // 4 + len(reply) // 4
                            return {
                                "reply": reply,
                                "sources": list(dict.fromkeys(sources)),
                                "tokens_used": est_tokens,
                            }
        except Exception as exc:
            logger.warning("Grounding assistant Gemini call failed: %s; falling back to deterministic response.", exc)

    # Deterministic fallback from real facts if offline or API unavailable
    if found_vehicle:
        reply = f"Here is the verified record from the database: {facts_lines[0]}"
    elif matched_companies:
        reply = f"The insurer {matched_companies[0].name} is active in the database with {len(matched_companies[0].detection_phrases or [])} alias detection phrases."
    else:
        reply = f"RiskLocker is grounded with {len(companies)} active insurance companies, {len(concepts)} benefit concepts, and {db.scalar(select(func.count(ClientRecord.id))) or 0} client records."

    return {
        "reply": reply,
        "sources": list(dict.fromkeys(sources)),
        "tokens_used": len(facts_text) // 4,
    }
