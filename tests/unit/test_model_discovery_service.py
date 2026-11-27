"""Unit tests for Model Discovery & Qualification Service (Milestone 3)."""

from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from app.models.tables import AppSetting, Notification, User, new_id


def test_evaluate_model_eligibility_accepts_flash_lite():
    from app.extraction.model_discovery_service import evaluate_model_eligibility

    model_31 = {
        "name": "models/gemini-3.1-flash-lite",
        "displayName": "Gemini 3.1 Flash-Lite",
        "description": "High-speed multimodal model with high free tier throughput.",
        "supportedGenerationMethods": ["generateContent", "countTokens"],
        "inputTokenLimit": 1048576,
        "outputTokenLimit": 8192,
    }
    eligible, reason, meta = evaluate_model_eligibility(model_31)
    assert eligible is True
    assert meta["id"] == "gemini-3.1-flash-lite"
    assert meta["rpd_limit"] == 480
    assert meta["rpm_limit"] == 13
    assert meta["tpm_limit"] == 220_000

    model_35 = {
        "name": "models/gemini-3.5-flash-lite",
        "displayName": "Gemini 3.5 Flash-Lite",
        "description": "Next-gen Flash-Lite tier with 480 RPD cap.",
        "supportedGenerationMethods": ["generateContent"],
        "inputTokenLimit": 1048576,
        "outputTokenLimit": 8192,
    }
    eligible, reason, meta = evaluate_model_eligibility(model_35)
    assert eligible is True
    assert meta["id"] == "gemini-3.5-flash-lite"


def test_evaluate_model_eligibility_rejects_banned_and_preview():
    from app.extraction.model_discovery_service import evaluate_model_eligibility

    # 1. Banned gemini-3.8-flash (low 20 RPD cap)
    model_38 = {
        "name": "models/gemini-3.8-flash",
        "displayName": "Gemini 3.8 Flash",
        "supportedGenerationMethods": ["generateContent"],
    }
    eligible, reason, meta = evaluate_model_eligibility(model_38)
    assert eligible is False
    assert "20 RPD" in reason or "banned" in reason.lower()

    # 2. Preview / Experimental model
    model_preview = {
        "name": "models/gemini-3.5-flash-preview",
        "displayName": "Gemini 3.5 Flash Preview",
        "supportedGenerationMethods": ["generateContent"],
    }
    eligible, reason, _ = evaluate_model_eligibility(model_preview)
    assert eligible is False
    assert "preview" in reason.lower() or "experimental" in reason.lower()

    # 3. Embedding model (no generateContent)
    model_embed = {
        "name": "models/text-embedding-004",
        "displayName": "Text Embedding 004",
        "supportedGenerationMethods": ["embedContent"],
    }
    eligible, reason, _ = evaluate_model_eligibility(model_embed)
    assert eligible is False
    assert "generateContent" in reason


def test_sync_model_baseline_detects_changes(db_session: Session):
    from app.extraction.model_discovery_service import sync_model_baseline

    initial_models = [
        {"id": "gemini-3.1-flash-lite", "display_name": "Gemini 3.1 Flash-Lite"}
    ]
    # First sync sets the baseline
    has_changed, alerts = sync_model_baseline(db_session, initial_models)
    assert has_changed is False
    assert len(alerts) == 0

    setting = db_session.get(AppSetting, "ai_model_baseline")
    assert setting is not None
    assert setting.value.get("known_models") == ["gemini-3.1-flash-lite"]

    # Second sync introduces a newly released eligible model
    new_models = [
        {"id": "gemini-3.1-flash-lite", "display_name": "Gemini 3.1 Flash-Lite"},
        {"id": "gemini-3.5-flash-lite", "display_name": "Gemini 3.5 Flash-Lite"},
    ]
    has_changed, alerts = sync_model_baseline(db_session, new_models)
    assert has_changed is True
    assert len(alerts) == 1
    assert "gemini-3.5-flash-lite" in alerts[0]

    # Verify baseline updated
    db_session.refresh(setting)
    assert "gemini-3.5-flash-lite" in setting.value.get("known_models")


def test_get_verified_eligible_models_offline_fallback():
    from app.extraction.model_discovery_service import get_verified_eligible_models

    res = get_verified_eligible_models(api_key=None)
    assert res["ok"] is True
    eligible_ids = [m["id"] for m in res["eligible_models"]]
    assert "gemini-3.1-flash-lite" in eligible_ids
    assert "gemini-3.5-flash-lite" in eligible_ids

    banned_ids = [m["id"] for m in res["banned_models"]]
    assert "gemini-3.8-flash" in banned_ids
