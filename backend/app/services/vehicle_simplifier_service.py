"""Vehicle Brand & Model Simplifier Service.

Combines AI (Gemini) and deterministic rule heuristics to distill overly long,
noisy automotive schedule strings (e.g. 'MERCEDES-BENZ S 400 L HYBRID (CKD) MY14 W222 4D SEDAN 7 SP AUTOMATIC')
into concise, human-understandable combined names (e.g. 'Mercedes-Benz S 400 L Hybrid').
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.core.config import get_settings
from app.extraction.gemini_extractor import get_key_pool

logger = logging.getLogger(__name__)

# Known internal chassis / platform codes to strip from public vehicle display names
KNOWN_CHASSIS_CODES = re.compile(
    r"\b(W222|W221|W223|W205|W206|W204|W213|W212|W214|G20|G30|G01|G05|F30|F10|F20|F48|E90|E46|E60|E39|FC1|FE1|D55L|D20N|D68T)\b",
    re.IGNORECASE,
)

# Common body types to strip from consumer vehicle names
BODY_TYPE_PATTERNS = re.compile(
    r"\b(?:\d+D\s+)?(SEDAN|HATCHBACK|SALOON|COUPE|STATION\s*WAGON|WAGON|CAB(?:IN)?|DOUBLE\s*CAB(?:IN)?|PICKUP|PICK-UP|SUV|MPV|VAN|LORRY|TRUCK)\b",
    re.IGNORECASE,
)

# Transmission descriptions to strip
TRANSMISSION_PATTERNS = re.compile(
    r"\b(?:\d+\s*(?:SP|SPEED)\s+)?(AUTOMATIC|AUTO|MANUAL|7G-DCT|9G-TRONIC|STEPTRONIC|TIPTRONIC|DSG|CVT)\b",
    re.IGNORECASE,
)

# CKD / CBU / Model year badges
REGISTRATION_PATTERNS = re.compile(
    r"\((?:CKD|CBU|AT|MT|A|M)\)|\b(?:CKD|CBU)\b|\bMY\d{2,4}\b",
    re.IGNORECASE,
)

# Acronyms that should stay uppercase in title formatting
PRESERVE_UPPERCASE = {
    "BMW", "BYD", "MG", "GWM", "EV", "HEV", "PHEV", "AWD", "4WD", "4X4", "2WD",
    "CKD", "CBU", "AV", "X", "RS", "GT", "TRD", "GLI", "SE", "V", "E", "G", "J",
    "TGDI", "TSI", "TDI", "VTEC", "M", "AMG", "S", "L", "TC-P", "TC", "VTI",
    "CX", "CR", "HR", "BR", "MX", "GLS", "GLX", "AT", "MT",
}

# Proper brand name capitalizations
CANONICAL_BRANDS = {
    "MERCEDES-BENZ": "Mercedes-Benz",
    "MERCEDES BENZ": "Mercedes-Benz",
    "MERCEDES": "Mercedes-Benz",
    "BMW": "BMW",
    "HONDA": "Honda",
    "TOYOTA": "Toyota",
    "PROTON": "Proton",
    "PERODUA": "Perodua",
    "MAZDA": "Mazda",
    "NISSAN": "Nissan",
    "HYUNDAI": "Hyundai",
    "KIA": "Kia",
    "VOLVO": "Volvo",
    "VOLKSWAGEN": "Volkswagen",
    "AUDI": "Audi",
    "PORSCHE": "Porsche",
    "LEXUS": "Lexus",
    "SUBARU": "Subaru",
    "MITSUBISHI": "Mitsubishi",
    "SUZUKI": "Suzuki",
    "PEUGEOT": "Peugeot",
    "RENAULT": "Renault",
    "FORD": "Ford",
    "LAND ROVER": "Land Rover",
    "JAGUAR": "Jaguar",
    "MINI": "MINI",
    "CHERY": "Chery",
    "BYD": "BYD",
    "TESLA": "Tesla",
    "ISUZU": "Isuzu",
    "BLUESHARK": "Blueshark",
}


def clean_vehicle_tokens_deterministic(raw_brand: str | None, raw_model: str | None) -> tuple[str, str, str]:
    """Clean vehicle brand and model deterministically using domain regex rules."""
    brand_str = (raw_brand or "").strip()
    model_str = (raw_model or "").strip()

    # Determine canonical brand
    clean_brand = ""
    brand_upper = brand_str.upper()
    for k, v in CANONICAL_BRANDS.items():
        if brand_upper == k or brand_upper.startswith(k + " "):
            clean_brand = v
            break
    if not clean_brand and brand_str:
        clean_brand = brand_str.title()

    # Work on model string
    text = model_str
    if not text and brand_str:
        return clean_brand, clean_brand, clean_brand

    # Strip CKD, CBU, MY14, etc.
    text = REGISTRATION_PATTERNS.sub(" ", text)

    # Strip known chassis codes (e.g. W222, G20)
    text = KNOWN_CHASSIS_CODES.sub(" ", text)

    # Strip transmission noise (e.g. 7 SP AUTOMATIC)
    text = TRANSMISSION_PATTERNS.sub(" ", text)

    # Strip body styles (e.g. 4D SEDAN)
    text = BODY_TYPE_PATTERNS.sub(" ", text)

    # Clean residual door indicators (e.g. '4D', '5D')
    text = re.sub(r"\b\d+D\b", " ", text, flags=re.IGNORECASE)

    # Clean remaining speed/gear indicators (e.g. '7 SP', '6 SPEED')
    text = re.sub(r"\b\d+\s*(?:SP|SPEED)\b", " ", text, flags=re.IGNORECASE)

    # Clean leftover empty or single parenthesis: '()', '( )'
    text = re.sub(r"\(\s*\)", " ", text)
    text = re.sub(r"[\(\)]", " ", text)

    # Remove isolated or boundary punctuation, but preserve hyphens within model tokens (e.g. TC-P, CX-5)
    text = re.sub(r"(?<!\w)-|-(?!\w)", " ", text)
    text = re.sub(r"[\s_:/]+", " ", text).strip()

    # Split into words and deduplicate adjacent identical tokens
    tokens = text.split()
    deduped: list[str] = []
    for tok in tokens:
        if not deduped or deduped[-1].upper() != tok.upper():
            deduped.append(tok)

    # If model starts with brand, separate or strip brand
    if clean_brand and deduped:
        brand_tokens = [b.upper() for b in re.split(r"[\s\-]+", clean_brand) if b]
        matches = 0
        for i, bt in enumerate(brand_tokens):
            if i < len(deduped) and deduped[i].upper() == bt:
                matches += 1
            else:
                break
        if matches > 0 and matches == len(brand_tokens):
            deduped = deduped[matches:]
        elif matches > 0 and len(deduped) > matches:
            # Partial brand match (e.g. 'MERCEDES' matching 'MERCEDES')
            deduped = deduped[matches:]

    # Format tokens with casing intelligence
    formatted_tokens: list[str] = []
    for tok in deduped:
        tok_up = tok.upper()
        if tok_up in PRESERVE_UPPERCASE or (len(tok_up) <= 3 and tok_up.isupper() and not tok_up.isdigit()):
            formatted_tokens.append(tok_up)
        elif "-" in tok:
            sub = [p.upper() if p.upper() in PRESERVE_UPPERCASE else p.capitalize() for p in tok.split("-")]
            formatted_tokens.append("-".join(sub))
        elif re.search(r"\d+(?:\.\d+)?kw$", tok, re.IGNORECASE):
            formatted_tokens.append(re.sub(r"(?i)kw$", "kW", tok))
        else:
            formatted_tokens.append(tok.capitalize())

    clean_model = " ".join(formatted_tokens).strip()

    # If brand was not provided, detect from model
    if not clean_brand:
        for k, v in CANONICAL_BRANDS.items():
            if clean_model.upper().startswith(k + " ") or clean_model.upper() == k:
                clean_brand = v
                clean_model = clean_model[len(k):].strip()
                break

    if not clean_brand and clean_model:
        first_word = clean_model.split()[0]
        clean_brand = first_word.title()
        clean_model = " ".join(clean_model.split()[1:]).strip() or clean_brand

    # Combined name
    if clean_brand and clean_model and not clean_model.upper().startswith(clean_brand.upper()):
        combined = f"{clean_brand} {clean_model}".strip()
    else:
        combined = clean_model or clean_brand

    return clean_brand, clean_model or clean_brand, combined


def simplify_vehicle_name_with_ai(
    raw_brand: str | None,
    raw_model: str | None,
    *,
    timeout_seconds: float = 4.0,
) -> tuple[str, str, str]:
    """Run an AI job (Gemini) to distill vehicle brand and model, falling back to deterministic rules."""
    # Deterministic fallback ready immediately
    det_brand, det_model, det_combined = clean_vehicle_tokens_deterministic(raw_brand, raw_model)

    raw_input = f"{raw_brand or ''} {raw_model or ''}".strip()
    if not raw_input or len(raw_input) < 4:
        return det_brand, det_model, det_combined

    pool = get_key_pool()
    all_keys = pool.get_all_keys()
    if not all_keys:
        return det_brand, det_model, det_combined

    settings = get_settings()
    configured_model = settings.gemini_model or "gemini-3.1-flash-lite-preview"
    prompt = (
        "You are an expert Malaysian automotive naming normalizer.\n"
        "Given this raw automotive insurance schedule vehicle string:\n"
        f"\"{raw_input}\"\n\n"
        "Simplify and normalize it into a concise, professional, easy-to-understand combined vehicle name.\n"
        "Rules:\n"
        "1. Include ONLY Brand, Core Model series, and Key Trim/Engine/Hybrid badge.\n"
        "   Examples: 'Mercedes-Benz S 400 L Hybrid', 'Honda Civic 1.5 TC-P', 'BMW 330i M Sport', 'Perodua Myvi 1.5 AV', 'Toyota Hilux Double Cab 2.8'.\n"
        "2. Strip out all registration noise:\n"
        "   - CKD, CBU\n"
        "   - Internal chassis codes (W222, W205, G20, F30, FC1, etc.)\n"
        "   - Model year codes (MY14, MY20)\n"
        "   - Body style descriptors (4D SEDAN, 5D HATCHBACK, SALOON, SUV, etc.)\n"
        "   - Transmission details (7 SP AUTOMATIC, 6 SPEED AUTO, A/T, CVT)\n"
        "3. Output strictly valid JSON with no markdown formatting:\n"
        "{\"simplified_brand\": \"...\", \"simplified_model\": \"...\", \"combined_name\": \"...\"}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": 128,
            "responseMimeType": "application/json",
        },
    }

    for api_key in all_keys[:2]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{configured_model}:generateContent?key={api_key}"
        try:
            pool.record_request()
            with httpx.Client(timeout=timeout_seconds) as client:
                res = client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates") or []
                    if candidates:
                        text_part = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        clean_json = re.sub(r"^```json\s*|\s*```$", "", text_part.strip(), flags=re.MULTILINE)
                        parsed = json.loads(clean_json)
                        sb = (parsed.get("simplified_brand") or "").strip()
                        sm = (parsed.get("simplified_model") or "").strip()
                        comb = (parsed.get("combined_name") or "").strip()
                        if comb:
                            return sb or det_brand, sm or det_model, comb
        except Exception as exc:
            logger.warning("Gemini vehicle model simplification note: %s (using deterministic rules)", exc)
            continue

    return det_brand, det_model, det_combined
