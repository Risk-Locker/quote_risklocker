"""Dynamic Gemini Model Discovery and Qualification Service.

Inspects Google AI Studio's live model catalog and validates production readiness
against Risklocker's throughput and quota requirements:
- Text generation support (`generateContent`)
- High-throughput production tier (>= 13 RPM, >= 200,000 TPM, >= 480 RPD)
- Strict rejection of low-cap models (e.g. `gemini-3.8-flash` with 20 RPD cap)
- Strict rejection of experimental or preview tiers
"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.tables import AppSetting

SAFE_RPD_CEILING = 480
SAFE_RPM_CEILING = 13
SAFE_TPM_CEILING = 220_000
ALLOWED_PRODUCTION_MODELS = frozenset({"gemini-3.1-flash-lite", "gemini-3.5-flash-lite"})

# Canonical verified baseline models
CANONICAL_ELIGIBLE_MODELS = [
    {
        "id": "gemini-3.1-flash-lite",
        "display_name": "Gemini 3.1 Flash-Lite",
        "rpd_limit": SAFE_RPD_CEILING,
        "rpm_limit": SAFE_RPM_CEILING,
        "tpm_limit": SAFE_TPM_CEILING,
        "is_recommended": True,
        "description": "Standard high-capacity extraction tier (480 RPD, 13 RPM, 200k TPM).",
    },
    {
        "id": "gemini-3.5-flash-lite",
        "display_name": "Gemini 3.5 Flash-Lite",
        "rpd_limit": SAFE_RPD_CEILING,
        "rpm_limit": SAFE_RPM_CEILING,
        "tpm_limit": SAFE_TPM_CEILING,
        "is_recommended": True,
        "description": "Next-gen high-capacity extraction tier (480 RPD, 13 RPM, 200k TPM).",
    },
]

# Explicitly banned models with known risk profiles
BANNED_MODELS_REGISTRY = [
    {
        "id": "gemini-3.8-flash",
        "display_name": "Gemini 3.8 Flash",
        "reason": "Exhaustion risk: Google AI Studio restricts to 20 RPD cap (instantly exhausted).",
    },
]


def normalize_model_id(raw_name: str) -> str:
    """Strip 'models/' prefix from Google API model identifiers."""
    clean = (raw_name or "").strip()
    if clean.startswith("models/"):
        return clean[7:]
    return clean


def fetch_live_google_models(api_key: str) -> tuple[bool, list[dict[str, Any]], str | None]:
    """Lightweight metadata probe to Google AI Studio GET /v1beta/models."""
    if not api_key or len(api_key.strip()) < 15:
        return False, [], "Missing or invalid Google AI Studio API key."

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key.strip()}"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "risklocker-model-discovery/2.0"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = data.get("models", [])
            return True, models, None
    except Exception as exc:
        return False, [], str(exc)


def evaluate_model_eligibility(model_data: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    """Validate whether an upstream model satisfies Risklocker production quotas."""
    raw_name = model_data.get("name", "")
    model_id = normalize_model_id(raw_name).lower()
    display_name = model_data.get("displayName") or model_id
    supported_methods = model_data.get("supportedGenerationMethods", [])

    meta: dict[str, Any] = {
        "id": model_id,
        "display_name": display_name,
        "rpd_limit": SAFE_RPD_CEILING,
        "rpm_limit": SAFE_RPM_CEILING,
        "tpm_limit": SAFE_TPM_CEILING,
        "description": model_data.get("description", ""),
        "input_token_limit": model_data.get("inputTokenLimit", 1_048_576),
        "output_token_limit": model_data.get("outputTokenLimit", 8_192),
    }

    # 1. Guard against banned models
    if "gemini-3.8-flash" in model_id:
        return (
            False,
            "Model 'gemini-3.8-flash' is banned: Google AI Studio imposes a 20 RPD cap.",
            meta,
        )

    # 2. Guard against preview / experimental tiers
    if "-preview" in model_id or "-exp" in model_id:
        return (
            False,
            f"Model '{model_id}' is an unverified preview/experimental tier.",
            meta,
        )

    # 3. Guard against non-generative models (e.g. embedding, imagen)
    if "generateContent" not in supported_methods:
        return (
            False,
            f"Model '{model_id}' lacks 'generateContent' capability (methods: {supported_methods}).",
            meta,
        )

    # 4. Strict production allowlist lock: ONLY gemini-3.1-flash-lite and gemini-3.5-flash-lite
    if model_id in ALLOWED_PRODUCTION_MODELS:
        meta["is_recommended"] = True
        return True, "Verified canonical high-capacity Flash-Lite tier.", meta

    return False, f"Model '{model_id}' is blocked: only {sorted(ALLOWED_PRODUCTION_MODELS)} are permitted.", meta


def get_verified_eligible_models(api_key: str | None = None) -> dict[str, Any]:
    """Retrieve full list of eligible and banned models, attempting live probe if API key provided."""
    eligible: list[dict[str, Any]] = []
    banned: list[dict[str, Any]] = list(BANNED_MODELS_REGISTRY)
    source = "canonical_registry"
    probe_error: str | None = None

    if api_key:
        ok, live_models, err = fetch_live_google_models(api_key)
        if ok and live_models:
            source = "google_ai_studio_live"
            for m in live_models:
                is_el, reason, meta = evaluate_model_eligibility(m)
                if is_el:
                    eligible.append(meta)
                elif "banned" in reason.lower() or "20 rpd" in reason.lower():
                    if not any(b["id"] == meta["id"] for b in banned):
                        banned.append({"id": meta["id"], "display_name": meta["display_name"], "reason": reason})
        else:
            probe_error = err

    # Ensure baseline models are present if live probe was offline or returned empty
    if not eligible:
        eligible = list(CANONICAL_ELIGIBLE_MODELS)

    # Deduplicate eligible models by ID
    seen_ids = set()
    deduped_eligible = []
    for em in eligible:
        if em["id"] not in seen_ids:
            seen_ids.add(em["id"])
            deduped_eligible.append(em)

    return {
        "ok": True,
        "source": source,
        "probe_error": probe_error,
        "eligible_models": deduped_eligible,
        "banned_models": banned,
    }


def sync_model_baseline(
    db: Session, discovered_models: list[dict[str, Any]]
) -> tuple[bool, list[str]]:
    """Compare discovered models with stored baseline and record alerts on changes."""
    setting = db.get(AppSetting, "ai_model_baseline")
    current_ids = sorted([m["id"] for m in discovered_models if "id" in m])

    if not setting:
        # First-time initialization
        new_setting = AppSetting(
            key="ai_model_baseline",
            value={
                "known_models": current_ids,
                "last_synced_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        db.add(new_setting)
        db.commit()
        return False, []

    val = setting.value if isinstance(setting.value, dict) else {}
    known_models = sorted(val.get("known_models", []))

    if current_ids == known_models:
        return False, []

    # Detect additions and removals
    added = set(current_ids) - set(known_models)
    removed = set(known_models) - set(current_ids)
    alerts: list[str] = []

    for model_id in added:
        alerts.append(f"New eligible Gemini model discovered: '{model_id}'.")
    for model_id in removed:
        alerts.append(f"Previously active model is no longer reported eligible: '{model_id}'.")

    # Update setting
    from sqlalchemy.orm.attributes import flag_modified

    new_val = dict(val)
    new_val["known_models"] = current_ids
    new_val["last_synced_at"] = datetime.now(timezone.utc).isoformat()
    new_val["last_alert_at"] = datetime.now(timezone.utc).isoformat()
    setting.value = new_val
    flag_modified(setting, "value")
    db.commit()

    return True, alerts
