"""Free Gemini Multimodal PDF Extraction Service with RAG Grounding and API Key Rotation."""

from __future__ import annotations

import base64
import json
import logging
import re
import threading
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


import time
from datetime import datetime, timezone


class GeminiKeyPool:
    """Thread-safe round-robin API key pool with automatic failover and quota tracking."""

    def __init__(self, keys: tuple[str, ...]):
        self._keys = list(keys)
        self._index = 0
        self._lock = threading.Lock()
        self._request_timestamps: list[float] = []

    def record_request(self) -> None:
        with self._lock:
            now = time.time()
            self._request_timestamps.append(now)
            cutoff = now - 86400
            self._request_timestamps = [t for t in self._request_timestamps if t >= cutoff]

    def get_quota_stats(self) -> dict[str, Any]:
        with self._lock:
            now = time.time()
            rpm_used = sum(1 for t in self._request_timestamps if t >= now - 60)
            today_utc_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
            rpd_used = sum(1 for t in self._request_timestamps if t >= today_utc_start)

            keys_count = max(len(self._keys), 1)
            rpm_limit = keys_count * 15
            rpd_limit = keys_count * 1500

            rpd_remaining = max(0, rpd_limit - rpd_used)
            rpm_remaining = max(0, rpm_limit - rpm_used)

            return {
                "keys_count": len(self._keys),
                "rpm_limit": rpm_limit,
                "rpm_used": rpm_used,
                "rpm_remaining": rpm_remaining,
                "rpd_limit": rpd_limit,
                "rpd_used": rpd_used,
                "rpd_remaining": rpd_remaining,
                "percent_rpd_remaining": round((rpd_remaining / rpd_limit) * 100, 1) if rpd_limit > 0 else 0,
            }

    def get_next_key(self) -> str | None:
        with self._lock:
            if not self._keys:
                return None
            key = self._keys[self._index % len(self._keys)]
            self._index = (self._index + 1) % len(self._keys)
            return key

    def get_all_keys(self) -> list[str]:
        with self._lock:
            return list(self._keys)


_key_pool: GeminiKeyPool | None = None


def get_key_pool() -> GeminiKeyPool:
    global _key_pool
    settings = get_settings()
    if _key_pool is None or _key_pool.get_all_keys() != list(settings.gemini_api_keys):
        existing_timestamps = _key_pool._request_timestamps if _key_pool else []
        _key_pool = GeminiKeyPool(settings.gemini_api_keys)
        _key_pool._request_timestamps = existing_timestamps
    return _key_pool


GEMINI_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "customer_name": {
            "type": "string",
            "description": "Full name of the policyholder/insured customer (e.g. found under 'The Insured / Pihak Diinsuranskan', 'Insured Name', 'Participant'). NEVER extract the Agent's Name, Agency, or Broker (e.g. ignore 'Nama Ejen', 'No. Akaun', 'RISKLOCKER').",
        },
        "insurance_company": {
            "type": "string",
            "description": "The underwriting insurance company name (e.g. QBE, Etiqa, AmAssurance, Lonpac, Allianz, Zurich, Liberty, MSIG, Tokio Marine, Berjaya Sompo, RHB).",
        },
        "product_name": {
            "type": "string",
            "description": "Insurance product or scheme title (e.g. 'Private Car Protector', 'Private Car Comprehensive', 'Motor Takaful').",
        },
        "detected_package_name": {
            "type": "string",
            "description": "If this is a packaged insurer (like AmAssurance), specify the package/tier name found in the document (e.g. 'Lite', 'Plus', 'Standard', 'Premier', 'Comprehensive'). Otherwise empty string.",
        },
        "vehicle_no": {
            "type": "string",
            "description": "Vehicle registration / plate number (e.g. 'JUM2709', 'WYY1234', 'VAA8888').",
        },
        "car_brand": {
            "type": "string",
            "description": "Vehicle make/manufacturer (e.g. 'PERODUA', 'PROTON', 'HONDA', 'TOYOTA', 'MAZDA', 'MERCEDES-BENZ', 'BMW').",
        },
        "car_model": {
            "type": "string",
            "description": "Complete vehicle model, variant, transmission, and body type text (e.g. 'PERODUA ATIVA AV MY21 D55L 4D WAGON 1 SP AUTOMATIC CONSTANTLY VARIABLE (CVT) / 4D WAGON').",
        },
        "vehicle_year": {
            "type": "string",
            "description": "Year of manufacture (e.g. '2021', '2023').",
        },
        "engine_cc": {
            "type": "string",
            "description": "Engine capacity in CC (e.g. '998 CC' or '1500').",
        },
        "chassis_no": {
            "type": "string",
            "description": "Vehicle chassis / VIN number.",
        },
        "engine_no": {
            "type": "string",
            "description": "Vehicle engine / motor number.",
        },
        "coverage_type": {
            "type": "string",
            "description": "Scope of coverage. Must be normalized to 'Comprehensive', 'Third Party Fire & Theft', or 'Third Party'. NEVER return 'Jenis Perlindungan' (which is just the Malay word for Cover Type).",
        },
        "excess_amount": {
            "type": "string",
            "description": "Excess amount or policy excess in RM (e.g. '0.00', '1,000.00', '500.00', '400.00'). Look for 'Excess', 'Lebihan', '*Excess Amount', 'Excess Amount', 'Policy Excess', 'Excess all claims', 'Ekses Polisi'. ALWAYS output '0.00' if excess is stated as 0 or 0.00.",
        },
        "coverage_amount": {
            "type": "string",
            "description": "Sum insured / agreed value / market value (e.g. '53,000.00').",
        },
        "cover_start_date": {
            "type": "string",
            "description": "Coverage period start date in DD/MM/YYYY or DD-MM-YYYY format.",
        },
        "cover_end_date": {
            "type": "string",
            "description": "Coverage period expiry / end date in DD/MM/YYYY or DD-MM-YYYY format.",
        },
        "ncd_percent": {
            "type": "string",
            "description": "No Claim Discount percentage number without percent sign (e.g. '25.00' or '55'). Check 'NCD', 'NCB', 'No Claim Bonus', 'No Claim Discount', 'DTT'.",
        },
        "basic_premium": {
            "type": "string",
            "description": "Basic insurance premium before NCD discount (e.g. '2,756.15' or '1,381.94'). Look for 'Basic Premium', 'Premium Asas', 'Premium'.",
        },
        "ncd_amount": {
            "type": "string",
            "description": "No Claim Discount amount deducted in RM (e.g. '1,515.88' or '345.50'). Look for 'NCD', 'DTT', 'No Claim Discount'.",
        },
        "gross_premium": {
            "type": "string",
            "description": "Gross premium after NCD deduction plus extra add-on riders (e.g. '2,335.57' or '1,036.44'). Look for 'Gross Premium', 'Premium Kasar', 'Gross Contribution'.",
        },
        "premium": {
            "type": "string",
            "description": "Total Insurance Premium payable to the insurer (e.g. '2,522.42' or '1,036.44'). Look for 'Total Premium', 'Jumlah Premium', 'Total Contribution', 'Premium Payable', 'Gross Premium'. If both basic premium and total premium are present, output the final Total Premium payable to the insurer.",
        },
        "total_optional_cover_amount": {
            "type": "string",
            "description": "Total Optional Cover Amount or Extra Benefit cost sum in RM (e.g. '845.35' or '20.00').",
        },
        "service_tax": {
            "type": "string",
            "description": "SST / Service tax amount (e.g. '186.85' or '84.52'). Look for 'Service Tax', 'Cukai Perkhidmatan', 'SST'.",
        },
        "stamp_duty": {
            "type": "string",
            "description": "Stamp duty amount (e.g. '10.00' or '0.00'). Look for 'Stamp Duty', 'Duti Setem'.",
        },
        "total_amount": {
            "type": "string",
            "description": "Final total quotation amount payable (e.g. '2,522.42' or '1,150.97').",
        },
        "roadtax": {
            "type": "string",
            "description": "Road tax amount if specified.",
        },
        "service_fee": {
            "type": "string",
            "description": "Runner / service fee if specified.",
        },
        "valid_until": {
            "type": "string",
            "description": "Quotation validity expiry date or duration (e.g. '18-03-2026', '15/09/2026', or '30 Days'). Look for 'This quotation will expire on DD-MM-YYYY', 'Quotation will expire on...', 'Validity', 'Valid Until', 'Sah Sehingga', 'Tarikh Tamat', 'Tarikh Luput'.",
        },
        "detected_benefits": {
            "type": "array",
            "description": "List of all benefits, add-ons, extra covers, and riders explicitly present in this quotation (e.g. Windscreen Damage RM 4,000 cost RM 600, Private Car 365 Plan 2 cost RM 166, Legal Liability Of Passengers RM 7.50, Legal Liability To Passengers RM 71.85, All Drivers RM 20, 24-hr Towing, Special Perils, Workmanship Warranty, etc.).",
            "items": {
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": "The standard name or description of the benefit / add-on.",
                    },
                    "concept_key": {
                        "type": "string",
                        "description": "Matched concept key from the concepts library (e.g. 'windscreen', 'towing', 'special-perils', 'legal-liability-to-passengers', 'legal-liability-of-passengers', 'all-drivers', 'private-car-365', 'motor-pa-plus', 'oto-360', 'repair-workmanship-warranty').",
                    },
                    "value": {
                        "type": "string",
                        "description": "The coverage value, limit amount, or description (e.g. 'RM 4,000.00', 'Unlimited Towing', 'Included', 'Plan 2').",
                    },
                    "coverage_limit": {
                        "type": "string",
                        "description": "Sum covered / coverage limit if any (e.g. 'RM 4,000.00', 'RM 10,000', '200 km').",
                    },
                    "premium_cost": {
                        "type": "string",
                        "description": "Additional premium cost in RM for this add-on (e.g. '600.00', '166.00', '7.50', '71.85', '20.00'). Empty string if included/FOC.",
                    },
                    "is_optional_cover": {
                        "type": "boolean",
                        "description": "True if this is an optional paid add-on / rider from the Optional Cover List or Extra Benefit table, False if included base cover.",
                    },
                    "raw_text": {
                        "type": "string",
                        "description": "The verbatim excerpt found in the quotation table or endorsement.",
                    },
                },
                "required": ["label", "value"],
            },
        },
        "detected_packs": {
            "type": "array",
            "description": "Purchased benefit packs / bundled add-on plans explicitly present in the quotation (e.g. a cost summary line 'DPA pack A -> 288.05 RM', 'Driver Protection Plan B', 'Key Replacement -> 43 RM'). Include ONLY packs that were actually purchased/selected (they appear in the cost summary or a selected-benefits table with a price or checkmark). Do NOT list generic marketing or unselected options. Tolerate small wording variations in the description text.",
            "items": {
                "type": "object",
                "properties": {
                    "package_name": {
                        "type": "string",
                        "description": "The pack/bundle name (e.g. 'Driver Protection Pack', 'DPA Pack', 'Key Replacement').",
                    },
                    "plan_name": {
                        "type": "string",
                        "description": "The plan level if present (e.g. 'Plan A', 'A', 'Plan B', 'B'). Empty string if the pack has no level.",
                    },
                    "raw_text": {
                        "type": "string",
                        "description": "The verbatim line from the cost summary or benefits table (e.g. 'DPA pack A 288.05 RM').",
                    },
                },
                "required": ["package_name"],
            },
        },
    },
    "required": [
        "customer_name",
        "insurance_company",
        "vehicle_no",
        "coverage_type",
        "coverage_amount",
        "total_amount",
    ],
}


def build_rag_system_prompt(
    db_companies: list[dict] | None = None,
    db_benefit_concepts: list[dict] | None = None,
    db_aliases: dict | None = None,
    db_packs: list[dict] | None = None,
    prompt_override: str | None = None,
) -> str:
    """Build grounded insurance domain prompt with live active database context.

    When ``prompt_override`` is provided it replaces the fixed instruction
    block; the live grounding sections (companies, concepts, packs) are always
    appended so the model still has authoritative database context.
    """
    company_hints: list[str] = []
    for c in (db_companies or []):
        name = c.get("name", "")
        if not name:
            continue
        aliases = [a for a in (c.get("aliases") or []) if a and a != name]
        if aliases:
            company_hints.append(f"{name} (aliases: {', '.join(aliases)})")
        else:
            company_hints.append(name)
    companies_str = "; ".join(company_hints) or "QBE, Etiqa, AmAssurance, Lonpac, Allianz, Zurich, Liberty"
    
    concepts_list = []
    for c in (db_benefit_concepts or []):
        key = c.get("key", "")
        name = c.get("name", "")
        if name:
            concepts_list.append(f"- {name} (concept_key: '{key}')")
    concepts_str = "\n".join(concepts_list) if concepts_list else "- Windscreen Coverage ('wndscrn')\n- Towing Service ('towing')\n- Special Perils ('spcl_peril')\n- All Drivers ('all_driver')\n- Legal Liability ('llp')"

    packs_list = []
    for pack in (db_packs or []):
        name = pack.get("name", "")
        plans = pack.get("plans", [])
        if name:
            plan_names = ", ".join(str(p.get("name", "")) for p in plans if p.get("name"))
            packs_list.append(f"- {name}" + (f" (plans: {plan_names})" if plan_names else ""))
    packs_str = "\n".join(packs_list) if packs_list else ""

    grounding = f"""
### LIVE DATABASE GROUNDING CONTEXT (always authoritative):
- Active insurance companies: {companies_str}
- Benefit concepts library:
{concepts_str}
- Known benefit packs and plan levels:
{packs_str}
Return strictly structured JSON adhering to the provided schema.
"""

    if prompt_override and prompt_override.strip():
        return f"""{prompt_override.strip()}

{grounding}"""

    return f"""You are the RiskLocker High-Precision Malaysian Motor Insurance Quotation Extractor.
Extract structured quotation data from the provided insurance document with 100% accuracy.

### CRITICAL GROUNDING RULES:
1. **CUSTOMER NAME (The Insured)**:
   - Extract the customer/policyholder name (e.g. under 'The Insured / Pihak Diinsuranskan', 'Insured Name', 'Participant').
   - NEVER extract the Agent's Name, Broker Name, Agency Name, or Account Number (e.g. IGNORE 'Account No. / Agent\'s Name', 'Nama Ejen', '02103586', 'RISKLOCKER SDN.BHD.').
2. **COVERAGE TYPE**:
   - MUST be normalized to 'Comprehensive', 'Third Party Fire & Theft', or 'Third Party'.
   - NEVER output 'Jenis Perlindungan' (which is simply the Malay translation of 'Cover Type').
3. **VEHICLE MAKE & MODEL**:
   - Extract the COMPLETE vehicle make, model, variant, and transmission (e.g. 'PERODUA ATIVA AV MY21 D55L 4D WAGON 1 SP AUTOMATIC (CVT)'). Do NOT truncate to a single word.
4. **NCD / NCB**:
   - Look for 'NCD', 'NCB', 'No Claim Bonus', 'No Claim Discount', 'NCB (25.00%)'. Output the percentage value (e.g. '25.00').
5. **INSURANCE COMPANY**:
   - Match one of the active insurance companies: {companies_str}.
6. **PACKAGE DETECTION (For Packaged Insurers like AmAssurance)**:
   - Check if any specific package/tier is mentioned anywhere in the document (e.g. 'Lite', 'Plus', 'Standard', 'Comprehensive', 'Premier').
7. **BENEFIT CONCEPTS LIBRARY**:
   Match detected benefits against the official library where applicable:
{concepts_str}
8. **BENEFIT PACKS / BUNDLED ADD-ON PLANS**:
   - Detect purchased packs from the cost summary and selected-benefits table (e.g. 'DPA pack A -> 288.05 RM', 'Driver Protection Plan B', 'Key Replacement -> 43 RM').
   - Only report packs that were actually purchased/selected (they carry a price or a selection marker). Never report unselected marketing options.
   - Tolerate small wording variations in the description text and match the plan level (A/B/C/D) when present.
   - Known packs and their plan levels:
{packs_str}
9. **EXCESS AMOUNT, VALIDITY & OPTIONAL COVER BREAKDOWN**:
   - Extract `excess_amount` if stated (e.g. 'Excess / Lebihan 0.00' -> '0.00', '*Excess Amount : RM 1,000.00' -> '1,000.00', 'Policy Excess: RM 500.00', 'Ekses Polisi'). Output '0.00' if excess is 0 or zero.
   - Extract `valid_until` date (e.g. 'This quotation will expire on 18-03-2026' -> '18-03-2026', 'Valid Until 05-07-2026', 'Tarikh Luput').
   - Extract `total_optional_cover_amount` (e.g. 'Total Optional Cover Amount : RM 845.35' or 'Extra Benefit / Manfaat Tambahan : RM 20.00').
   - In `detected_benefits`, extract EVERY item in the Optional Cover List or Extra Benefit section with its name (`label`, e.g. 'ALL DRIVERS', 'Windscreen', 'Legal Liability to Passengers'), coverage limit (`coverage_limit`), cost (`premium_cost`, e.g. '20.00', '150.00', '7.50'), and mark `is_optional_cover: true`.
Return strictly structured JSON adhering to the provided schema.
"""


def extract_with_gemini_sync(
    pdf_bytes: bytes,
    *,
    document_text: str | None = None,
    db_companies: list[dict] | None = None,
    db_benefit_concepts: list[dict] | None = None,
    db_aliases: dict | None = None,
    db_packs: list[dict] | None = None,
    prompt_override: str | None = None,
    timeout_seconds: float = 15.0,
) -> dict[str, Any] | None:
    """Extract quotation fields using Gemini AI with API key rotation."""
    pool = get_key_pool()
    all_keys = pool.get_all_keys()
    if not all_keys:
        logger.info("No GEMINI_API_KEY configured; skipping Gemini extraction.")
        return None

    settings = get_settings()
    model = settings.gemini_model or "gemini-3.6-flash"
    if model in {"gemini-2.0-flash", "gemini-2.5-flash"}:
        model = "gemini-3.6-flash"
    system_prompt = build_rag_system_prompt(db_companies, db_benefit_concepts, db_aliases, db_packs, prompt_override)

    if document_text and len(document_text.strip()) > 30:
        parts: list[dict[str, Any]] = [
            {
                "text": f"Extract all insurance quotation values, vehicle details, coverage, and detected benefits from this document according to the JSON schema:\n\n--- DOCUMENT TEXT ---\n{document_text}\n--- END DOCUMENT TEXT ---"
            }
        ]
    else:
        b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
        parts = [
            {
                "inline_data": {
                    "mime_type": "application/pdf",
                    "data": b64_pdf,
                }
            },
            {
                "text": "Extract all quotation information and benefits from this Malaysian motor insurance document according to the JSON schema."
            }
        ]

    payload = {
        "system_instruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": [
            {
                "role": "user",
                "parts": parts,
            }
        ],
        "generationConfig": {
            "response_mime_type": "application/json",
            "response_schema": GEMINI_EXTRACTION_SCHEMA,
            "temperature": 0.0,
        },
    }

    candidate_models = [
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.7-flash",
        model,
    ]
    seen_models: set[str] = set()
    models_to_try = [m for m in candidate_models if m and not (m in seen_models or seen_models.add(m))]
    failed_models: set[str] = set()

    # Attempt keys in pool with round-robin + multi-model fallback
    effective_timeout = min(timeout_seconds, 25.0)
    for attempt in range(len(all_keys)):
        api_key = pool.get_next_key()
        if not api_key:
            break

        for m_name in models_to_try:
            if m_name in failed_models:
                continue
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m_name}:generateContent?key={api_key}"
            try:
                with httpx.Client(timeout=effective_timeout, http2=False) as client:
                    response = client.post(url, json=payload)
                    if response.status_code == 200:
                        data = response.json()
                        candidates = data.get("candidates") or []
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts") or []
                            if parts:
                                raw_text = parts[0].get("text", "")
                                parsed = json.loads(raw_text)
                                pool.record_request()
                                logger.info("Gemini AI extraction succeeded with %s on attempt %d.", m_name, attempt + 1)
                                return parsed
                    elif response.status_code == 429:
                        logger.warning("Gemini key rate-limited (429) on %s, rotating to next key...", m_name)
                        break
                    elif response.status_code == 404:
                        logger.warning("Gemini model %s returned 404 (unavailable), skipping permanently...", m_name)
                        failed_models.add(m_name)
                        continue
                    elif response.status_code == 503:
                        logger.warning("Gemini model %s returned 503, trying fallback model...", m_name)
                        continue
                    else:
                        logger.warning("Gemini API returned status %d: %s", response.status_code, response.text[:200])
                        continue
            except Exception as exc:
                logger.warning("Gemini extraction attempt failed on %s: %s", m_name, exc)
                continue

    logger.error("All Gemini API keys and models in pool failed or exhausted.")
    return None
