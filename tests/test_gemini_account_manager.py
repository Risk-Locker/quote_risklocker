"""Hermetic unit tests for GeminiAccountManager, safety limits, rotation, and settings API."""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_PROVIDER": "supabase_postgres",
        "DATABASE_URL": "postgresql://postgres:password@db.test.supabase.co:5432/postgres",
        "AUTH_HASH_SECRET": "test-auth-hash-secret-that-is-long-enough",
        "STORAGE_DRIVER": "supabase",
        "SUPABASE_URL": "https://project-ref.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
        "GEMINI_API_KEY": "AIzaSyPrimaryEnvKey12345678901234567890",
        "GEMINI_MODEL": "gemini-3.1-flash-lite-preview",
        "GEMINI_MAX_RPD_PER_KEY": "440",
        "GEMINI_MAX_RPM_PER_KEY": "10",
        "GEMINI_MAX_TPM_PER_KEY": "100000",
        "GEMINI_MAX_PROMPT_TOKENS": "60000",
    }
)

from app.api import routes
from app.api.deps import current_user, settings_dep
from app.core.errors import register_error_handlers
from app.db.session import get_db
from app.extraction.gemini_extractor import (
    GeminiAccount,
    GeminiAccountManager,
    estimate_and_guard_payload,
    get_key_pool,
)
from app.models.tables import AppSetting, User


def _test_settings():
    return SimpleNamespace(
        app_env="test",
        cors_origins=("http://localhost:3000",),
        session_cookie_name="risklocker_session",
        session_cookie_secure=False,
        session_idle_hours=8,
        session_max_days=30,
        auth_hash_secret="test-auth-hash-secret-that-is-long-enough",
        max_upload_files=1,
        max_upload_bytes=1024 * 1024,
        max_source_pdf_bytes=20 * 1024 * 1024,
        trash_retention_days=14,
        gemini_api_keys=("AIzaSyPrimaryEnvKey12345678901234567890",),
        gemini_model="gemini-3.1-flash-lite-preview",
        gemini_max_rpd_per_key=440,
        gemini_max_rpm_per_key=10,
        gemini_max_tpm_per_key=100_000,
        gemini_max_prompt_tokens=60_000,
        gemini_max_accounts=6,
    )


def _admin_user() -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=str(uuid4()),
        email="admin@risklocker.com",
        password_hash="",
        role="admin",
        status="active",
        created_at=now,
        updated_at=now,
    )


class MemoryDb:
    def __init__(self):
        self.store: dict[str, Any] = {}

    def get(self, model: Any, key: Any) -> Any:
        if model is AppSetting:
            return self.store.get(key)
        return None

    def add(self, obj: Any) -> None:
        if isinstance(obj, AppSetting):
            self.store[obj.key] = obj

    def commit(self) -> None:
        pass

    def refresh(self, _obj: Any) -> None:
        pass


def _http_client(*, user: User | None = None, db: MemoryDb | None = None) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(routes.router)
    memory_db = db or MemoryDb()
    app.dependency_overrides[get_db] = lambda: memory_db
    app.dependency_overrides[settings_dep] = _test_settings
    if user:
        app.dependency_overrides[current_user] = lambda: user
    return TestClient(app)


def test_gemini_account_manager_init():
    keys = ("AIzaSyPrimaryEnvKey12345678901234567890",)
    mgr = GeminiAccountManager(keys)
    accounts = mgr.get_accounts()
    assert len(accounts) == 1
    assert accounts[0].source == "env"
    assert accounts[0].masked_key.startswith("AIzaSy")
    assert accounts[0].masked_key.endswith("7890")
    assert mgr.get_next_key() == "AIzaSyPrimaryEnvKey12345678901234567890"


def test_gemini_auto_failover_on_rpm_cap():
    mgr = GeminiAccountManager(
        (
            "AIzaSyKeyOne1111111111111111111111111111",
            "AIzaSyKeyTwo2222222222222222222222222222",
        )
    )
    # Record 10 calls for Account 1 within 60s
    for _ in range(10):
        mgr.record_request("AIzaSyKeyOne1111111111111111111111111111")

    # Account 1 reached 10 RPM -> next call must auto-switch to Account 2
    next_key = mgr.get_next_key()
    assert next_key == "AIzaSyKeyTwo2222222222222222222222222222"
    assert mgr.get_accounts()[0].status == "cooling_rpm"
    assert "10 RPM" in (mgr.get_accounts()[1].last_switch_reason or "")


def test_gemini_auto_failover_on_rpd_cap():
    mgr = GeminiAccountManager(
        (
            "AIzaSyKeyOne1111111111111111111111111111",
            "AIzaSyKeyTwo2222222222222222222222222222",
        )
    )
    # Set Account 1 requests today to 440
    mgr.get_accounts()[0].request_count_today = 440

    next_key = mgr.get_next_key()
    assert next_key == "AIzaSyKeyTwo2222222222222222222222222222"
    assert mgr.get_accounts()[0].status == "exhausted_rpd"


def test_gemini_hard_pool_cutoff():
    mgr = GeminiAccountManager(
        (
            "AIzaSyKeyOne1111111111111111111111111111",
            "AIzaSyKeyTwo2222222222222222222222222222",
        )
    )
    mgr.get_accounts()[0].request_count_today = 440
    mgr.get_accounts()[1].request_count_today = 440

    # Both capped at 440 -> hard pool cutoff -> returns None immediately
    next_key = mgr.get_next_key()
    assert next_key is None
    stats = mgr.get_quota_stats()
    assert stats["pool_cutoff_active"] is True
    assert stats["pool_rpd_remaining"] == 0


def test_gemini_429_rpm_cooling_vs_rpd_quarantine():
    mgr = GeminiAccountManager(("AIzaSyKeyOne1111111111111111111111111111",))
    key = "AIzaSyKeyOne1111111111111111111111111111"

    # Test 429 when under daily quota -> sets 65s cooling
    mgr.record_failure(429, "Quota exceeded for quota metric 'requests per minute'", key=key)
    acc = mgr.get_accounts()[0]
    assert acc.status == "cooling_rpm"
    assert acc.cooling_until is not None

    # Test 429 when at or over 440 daily requests -> sets daily exhausted
    acc.request_count_today = 440
    mgr.record_failure(429, "Daily quota limit reached", key=key)
    assert acc.status == "exhausted_rpd"


def test_gemini_prompt_token_compaction_guard():
    huge_text = "Policy terms and conditions\n\n\n\n" * 15_000
    payload = {
        "contents": [{"parts": [{"text": huge_text}]}],
        "system_instruction": {"parts": [{"text": "System prompt"}]},
    }
    guarded = estimate_and_guard_payload(payload, max_tokens=60_000)
    guarded_text = guarded["contents"][0]["parts"][0]["text"]
    assert len(guarded_text) < len(huge_text)
    assert "[... TRUNCATED MIDDLE FOR TOKEN SAFETY LIMIT ...]" in guarded_text


def test_settings_add_and_delete_manual_key():
    db = MemoryDb()
    client = _http_client(user=_admin_user(), db=db)

    # 1. Invalid key format check
    bad_res = client.post("/settings/gemini/keys", json={"key": "invalid_short_key"})
    assert bad_res.status_code == 400

    # 2. Add valid key
    valid_key = "AIzaSyManualAccount2TestKey123456789012"
    res = client.post(
        "/settings/gemini/keys",
        json={"key": valid_key, "label": "Account 2 Test"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "Account added to pool" in data["message"]
    key_id = data["account"]["id"]

    # Verify key is saved in AppSetting in DB
    setting = db.get(AppSetting, "gemini_manual_api_keys")
    assert setting is not None
    assert len(setting.value["keys"]) == 1
    assert setting.value["keys"][0]["key"] == valid_key

    # 3. Check /settings/limits reflects 2 accounts
    limits_res = client.get("/settings/limits")
    assert limits_res.status_code == 200
    gemini_data = limits_res.json()["gemini"]
    assert len(gemini_data["accounts"]) == 2

    # 4. Switch active account to Account 2
    switch_res = client.post("/settings/gemini/switch-account", json={"account_index": 1})
    assert switch_res.status_code == 200
    assert switch_res.json()["active_account_index"] == 1

    # 5. Delete manual key
    del_res = client.delete(f"/settings/gemini/keys/{key_id}")
    assert del_res.status_code == 200
    assert del_res.json()["ok"] is True
    assert len(db.get(AppSetting, "gemini_manual_api_keys").value["keys"]) == 0


def test_settings_add_aq_prefix_manual_key():
    """Verify modern Google AI Studio keys starting with 'AQ.' pass formatting validation and probe."""
    db = MemoryDb()
    client = _http_client(user=_admin_user(), db=db)

    aq_key = "AQ.Ab8ManualAccountTestKey123456789012"
    res = client.post(
        "/settings/gemini/keys",
        json={"key": aq_key, "label": "Account AQ Test"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "Account added to pool" in data["message"]
    assert data["account"]["masked_key"].startswith("AQ.Ab8")

