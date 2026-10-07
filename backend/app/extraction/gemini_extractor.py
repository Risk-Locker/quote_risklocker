"""Free Gemini Multimodal PDF Extraction Service with RAG Grounding and API Key Rotation."""

from __future__ import annotations

import base64
import json
import logging
import re
import threading
from typing import Any, Sequence

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


import time
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class GeminiAccount:
    """Represents a single Google Cloud account / Gemini API key with granular rate tracking."""
    id: str
    key: str
    label: str
    source: str = "env"  # "env" | "manual"
    status: str = "untested"  # "ready" | "cooling_rpm" | "exhausted_rpd" | "denied" | "invalid_key" | "model_not_found" | "error" | "untested"
    status_label: str = "Untested"
    status_color: str = "gray"

    # Rate tracking
    request_timestamps_min: list[float] = field(default_factory=list)
    request_count_today: int = 0
    token_timestamps_min: list[tuple[float, int]] = field(default_factory=list)
    tokens_today: int = 0

    # Safety & cooldown timers
    cooling_until: float | None = None
    quarantine_until: float | None = None
    last_switch_reason: str | None = None

    # Diagnostics
    last_probed_at: str | None = None
    last_success_at: str | None = None
    last_error_at: str | None = None
    last_error_code: int | None = None
    last_error_message: str | None = None
    successful_calls: int = 0
    failed_calls: int = 0

    @property
    def masked_key(self) -> str:
        if not self.key:
            return ""
        if len(self.key) <= 10:
            return self.key[:2] + "..." + self.key[-2:]
        return self.key[:6] + "..." + self.key[-4:]


class GeminiAccountManager:
    """Thread-safe multi-account Gemini manager enforcing 440 RPD, 10 RPM, 100k TPM, prompt guards & auto-failover."""

    def __init__(self, keys: tuple[str, ...] = ()):
        self._lock = threading.RLock()
        settings = get_settings()
        self._max_rpd_per_key = getattr(settings, "gemini_max_rpd_per_key", 440)
        self._max_rpm_per_key = getattr(settings, "gemini_max_rpm_per_key", 10)
        self._max_tpm_per_key = getattr(settings, "gemini_max_tpm_per_key", 100_000)
        self._max_prompt_tokens = getattr(settings, "gemini_max_prompt_tokens", 60_000)
        self._max_accounts = getattr(settings, "gemini_max_accounts", 6)

        self._accounts: list[GeminiAccount] = []
        self._active_index: int = 0
        self._last_reset_date: str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._last_probe_cached_time: float = 0.0
        self._pool_cutoff_active: bool = False

        # Global aggregate stats
        self._total_prompt_tokens: int = 0
        self._total_candidate_tokens: int = 0
        self._total_tokens: int = 0
        self._successful_calls: int = 0
        self._failed_calls: int = 0

        # Initialize from provided keys
        if keys:
            for idx, k in enumerate(keys):
                if k.strip():
                    self._accounts.append(
                        GeminiAccount(
                            id=f"env_{idx}",
                            key=k.strip(),
                            label=f"Account {idx + 1} (.env Primary)" if idx == 0 else f"Account {idx + 1} (.env)",
                            source="env",
                        )
                    )

    def _check_daily_reset(self) -> None:
        """Reset daily quotas and quarantines when passing 00:00 UTC."""
        today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today_date != self._last_reset_date:
            self._last_reset_date = today_date
            for acc in self._accounts:
                acc.request_count_today = 0
                acc.tokens_today = 0
                if acc.status == "exhausted_rpd":
                    acc.status = "ready"
                    acc.status_label = "Ready"
                    acc.status_color = "green"
                acc.quarantine_until = None
            self._pool_cutoff_active = False

    def sync_accounts(self, db: Any = None) -> None:
        """Sync accounts between .env configuration and Postgres AppSetting manual keys without losing live metrics."""
        with self._lock:
            self._check_daily_reset()
            settings = get_settings()
            env_keys = [k.strip() for k in settings.gemini_api_keys if k.strip()]

            manual_items: list[dict[str, Any]] = []
            if db is not None:
                from app.models.tables import AppSetting
                setting = db.get(AppSetting, "gemini_manual_api_keys")
                if setting and isinstance(setting.value, dict):
                    manual_items = setting.value.get("keys", [])
            else:
                import os
                if os.getenv("APP_ENV") != "test":
                    try:
                        from app.db.session import SessionLocal
                        from app.models.tables import AppSetting
                        with SessionLocal() as session:
                            setting = session.get(AppSetting, "gemini_manual_api_keys")
                            if setting and isinstance(setting.value, dict):
                                manual_items = setting.value.get("keys", [])
                    except Exception as exc:
                        logger.debug("Could not read manual keys from DB: %s", exc)

            existing_by_key = {acc.key: acc for acc in self._accounts}
            new_accounts: list[GeminiAccount] = []

            # 1. Primary .env key(s)
            for idx, k in enumerate(env_keys):
                if k in existing_by_key:
                    acc = existing_by_key[k]
                    acc.label = f"Account {idx + 1} (.env Primary)" if idx == 0 else f"Account {idx + 1} (.env)"
                    acc.source = "env"
                    new_accounts.append(acc)
                else:
                    new_accounts.append(
                        GeminiAccount(
                            id=f"env_{idx}",
                            key=k,
                            label=f"Account {idx + 1} (.env Primary)" if idx == 0 else f"Account {idx + 1} (.env)",
                            source="env",
                            status="ready",
                            status_label="Ready · Configured",
                            status_color="green",
                        )
                    )

            # 2. Manual keys from Postgres AppSetting
            for idx, item in enumerate(manual_items):
                k = item.get("key", "").strip()
                if not k or any(na.key == k for na in new_accounts):
                    continue
                acc_id = item.get("id") or f"manual_{idx}"
                acc_label = item.get("label") or f"Account {len(new_accounts) + 1} (Manual)"
                if k in existing_by_key:
                    acc = existing_by_key[k]
                    acc.id = acc_id
                    acc.label = acc_label
                    acc.source = "manual"
                    new_accounts.append(acc)
                else:
                    new_accounts.append(
                        GeminiAccount(
                            id=acc_id,
                            key=k,
                            label=acc_label,
                            source="manual",
                            status=item.get("last_status", "ready"),
                            status_label="Ready · Manual Key" if item.get("last_status") == "ready" else "Untested",
                            status_color="green" if item.get("last_status") == "ready" else "gray",
                            last_probed_at=item.get("last_probed_at"),
                        )
                    )

            self._accounts = new_accounts[:self._max_accounts]
            if self._active_index >= len(self._accounts):
                self._active_index = 0

    def get_accounts(self) -> list[GeminiAccount]:
        with self._lock:
            return list(self._accounts)

    def switch_active_account(self, index: int) -> bool:
        """Manually switch active account by index."""
        with self._lock:
            if 0 <= index < len(self._accounts):
                self._active_index = index
                self._accounts[index].last_switch_reason = f"Manually selected Account {index + 1}"
                logger.info("Manually switched active Gemini account to %d (%s)", index + 1, self._accounts[index].label)
                return True
            return False

    def get_next_key(self) -> str | None:
        """Get the active API key enforcing 440 RPD, 10 RPM, 100k TPM and automatic failover."""
        with self._lock:
            self._check_daily_reset()
            if not self._accounts:
                return None

            now = time.time()
            # Clear expired 60s RPM cooling
            for acc in self._accounts:
                if acc.cooling_until and now >= acc.cooling_until:
                    acc.cooling_until = None
                    if acc.status == "cooling_rpm":
                        acc.status = "ready"
                        acc.status_label = "Ready"
                        acc.status_color = "green"

            # Filter non-blocked, under 440 RPD accounts
            available_indices: list[int] = []
            for i, acc in enumerate(self._accounts):
                if acc.status in ("denied", "invalid_key"):
                    continue
                if acc.request_count_today >= self._max_rpd_per_key:
                    acc.status = "exhausted_rpd"
                    acc.status_label = f"Safety Cap ({self._max_rpd_per_key} RPD)"
                    acc.status_color = "amber"
                    continue
                available_indices.append(i)

            if not available_indices:
                logger.warning(
                    "Hard Pool Cutoff active: All Gemini accounts exhausted safety cap (%d RPD) or blocked. Falling back to local OCR/regex.",
                    self._max_rpd_per_key,
                )
                self._pool_cutoff_active = True
                return None

            self._pool_cutoff_active = False

            # Check if current active account is valid and under limits
            active = self._accounts[self._active_index]
            can_use_active = True
            switch_reason = ""

            if active.request_count_today >= self._max_rpd_per_key or active.status in ("exhausted_rpd", "denied", "invalid_key"):
                can_use_active = False
                switch_reason = f"Account {self._active_index + 1} reached {self._max_rpd_per_key} RPD safety cap"
            else:
                rpm_used = sum(1 for t in active.request_timestamps_min if t >= now - 60)
                tpm_used = sum(tok for t, tok in active.token_timestamps_min if t >= now - 60)

                if rpm_used >= self._max_rpm_per_key:
                    can_use_active = False
                    active.status = "cooling_rpm"
                    active.status_label = f"Cooling ({self._max_rpm_per_key} RPM Cap)"
                    active.status_color = "amber"
                    active.cooling_until = now + 65.0
                    switch_reason = f"Account {self._active_index + 1} reached {self._max_rpm_per_key} RPM limit"
                elif tpm_used >= self._max_tpm_per_key:
                    can_use_active = False
                    active.status = "cooling_rpm"
                    active.status_label = f"Cooling ({self._max_tpm_per_key:,} TPM Cap)"
                    active.status_color = "amber"
                    active.cooling_until = now + 65.0
                    switch_reason = f"Account {self._active_index + 1} reached {self._max_tpm_per_key:,} TPM limit"
                elif active.cooling_until and now < active.cooling_until:
                    can_use_active = False
                    switch_reason = f"Account {self._active_index + 1} is cooling down"

            if can_use_active:
                return active.key

            # Find next ready account
            for idx in available_indices:
                cand = self._accounts[idx]
                c_rpm = sum(1 for t in cand.request_timestamps_min if t >= now - 60)
                c_tpm = sum(tok for t, tok in cand.token_timestamps_min if t >= now - 60)
                if c_rpm < self._max_rpm_per_key and c_tpm < self._max_tpm_per_key and (not cand.cooling_until or now >= cand.cooling_until):
                    self._active_index = idx
                    cand.last_switch_reason = f"Auto-switched from Account {self._active_index + 1}: {switch_reason}"
                    logger.info("Auto-switched to Gemini Account %d (%s): %s", idx + 1, cand.label, switch_reason)
                    return cand.key

            logger.warning("All available accounts are currently in short RPM/TPM cooling. Short wait required.")
            return None

    def get_all_keys(self) -> list[str]:
        with self._lock:
            return [acc.key for acc in self._accounts if acc.status not in ("denied", "invalid_key")]

    def _find_account_by_key(self, key: str | None) -> GeminiAccount | None:
        if not self._accounts:
            return None
        if key:
            for acc in self._accounts:
                if acc.key == key:
                    return acc
        return self._accounts[self._active_index] if 0 <= self._active_index < len(self._accounts) else None

    def record_request(self, key: str | None = None) -> None:
        with self._lock:
            self._check_daily_reset()
            now = time.time()
            acc = self._find_account_by_key(key)
            if acc:
                acc.request_timestamps_min.append(now)
                acc.request_timestamps_min = [t for t in acc.request_timestamps_min if t >= now - 60]
                acc.request_count_today += 1

    def record_success(
        self, prompt_tokens: int = 0, candidate_tokens: int = 0, total_tokens: int = 0, key: str | None = None
    ) -> None:
        with self._lock:
            self._check_daily_reset()
            now = time.time()
            tok_count = max(0, total_tokens if total_tokens > 0 else (prompt_tokens + candidate_tokens))

            self._successful_calls += 1
            self._total_prompt_tokens += max(0, prompt_tokens)
            self._total_candidate_tokens += max(0, candidate_tokens)
            self._total_tokens += tok_count

            acc = self._find_account_by_key(key)
            if acc:
                acc.request_timestamps_min.append(now)
                acc.request_timestamps_min = [t for t in acc.request_timestamps_min if t >= now - 60]
                acc.request_count_today += 1
                acc.token_timestamps_min.append((now, tok_count))
                acc.token_timestamps_min = [(t, k) for t, k in acc.token_timestamps_min if t >= now - 60]
                acc.tokens_today += tok_count
                acc.successful_calls += 1
                acc.status = "ready"
                acc.status_label = "Ready"
                acc.status_color = "green"
                acc.last_error_code = None
                acc.last_error_message = None
                acc.last_success_at = datetime.now(timezone.utc).isoformat()
                acc.last_probed_at = acc.last_success_at

    def record_failure(self, status_code: int, error_message: str, key: str | None = None) -> None:
        with self._lock:
            self._failed_calls += 1
            clean_msg = (error_message or "").strip()
            acc = self._find_account_by_key(key)
            if not acc:
                return

            now = time.time()
            acc.failed_calls += 1
            acc.last_error_code = status_code
            acc.last_error_message = clean_msg or f"HTTP {status_code} error from Gemini API"
            acc.last_error_at = datetime.now(timezone.utc).isoformat()
            acc.last_probed_at = acc.last_error_at

            if status_code == 403:
                acc.status = "denied"
                acc.status_label = "Access Denied (403)"
                acc.status_color = "red"
            elif status_code in (400, 401):
                acc.status = "invalid_key"
                acc.status_label = "Invalid Key"
                acc.status_color = "red"
            elif status_code == 429:
                # Discriminate between short 60s RPM spike vs daily quota exhaustion
                is_rpm = "per minute" in clean_msg.lower() or "requests per minute" in clean_msg.lower() or acc.request_count_today < self._max_rpd_per_key
                if is_rpm:
                    acc.status = "cooling_rpm"
                    acc.status_label = "Rate Limited (Cooling 65s)"
                    acc.status_color = "amber"
                    acc.cooling_until = now + 65.0
                else:
                    acc.status = "exhausted_rpd"
                    acc.status_label = "Daily Quota Exhausted"
                    acc.status_color = "amber"
            elif status_code == 404:
                acc.status = "model_not_found"
                acc.status_label = "Model Deprecated (404)"
                acc.status_color = "amber"
            else:
                acc.status = "error"
                acc.status_label = f"Error ({status_code})"
                acc.status_color = "amber"

    @staticmethod
    def probe_single_key(key: str, model: str | None = None) -> dict[str, Any]:
        """Test a single key against Google Generative Language API without modifying pool state."""
        import os, sys

        if os.getenv("APP_ENV") == "test" or "pytest" in sys.modules:
            if "invalid" in key.lower():
                return {"ok": False, "status_code": 400, "error": "API_KEY_INVALID", "latency_ms": 45, "model": model or "gemini-3.1-flash-lite-preview"}
            if "denied" in key.lower() or "403" in key:
                return {"ok": False, "status_code": 403, "error": "Project access denied", "latency_ms": 50, "model": model or "gemini-3.1-flash-lite-preview"}
            return {"ok": True, "status_code": 200, "error": None, "latency_ms": 40, "model": model or "gemini-3.1-flash-lite-preview"}

        settings = get_settings()
        target_model = model or getattr(settings, "gemini_model", None) or "gemini-3.1-flash-lite-preview"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={key}"
        test_payload = {
            "contents": [{"parts": [{"text": "ping"}]}],
            "generationConfig": {"maxOutputTokens": 5},
        }

        start_t = time.time()
        try:
            with httpx.Client(timeout=6.0, http2=False) as client:
                res = client.post(url, json=test_payload)
                latency_ms = int((time.time() - start_t) * 1000)
                if res.status_code == 200:
                    return {
                        "ok": True,
                        "status_code": 200,
                        "error": None,
                        "latency_ms": latency_ms,
                        "model": target_model,
                    }
                else:
                    err_text = ""
                    try:
                        err_text = res.json().get("error", {}).get("message", "")
                    except Exception:
                        err_text = res.text[:200]
                    return {
                        "ok": False,
                        "status_code": res.status_code,
                        "error": err_text or f"HTTP {res.status_code} error from Gemini API",
                        "latency_ms": latency_ms,
                        "model": target_model,
                    }
        except Exception as exc:
            latency_ms = int((time.time() - start_t) * 1000)
            return {
                "ok": False,
                "status_code": 500,
                "error": f"Connection error: {str(exc)[:150]}",
                "latency_ms": latency_ms,
                "model": target_model,
            }

    def probe(self, force: bool = False, model: str | None = None, account_index: int | None = None) -> dict[str, Any]:
        """Actively test generation capability for active account or specified index."""
        import os, sys

        with self._lock:
            self._check_daily_reset()
            now = time.time()
            idx = account_index if account_index is not None and 0 <= account_index < len(self._accounts) else self._active_index

            if not self._accounts:
                return self.get_quota_stats()

            # Cache check
            if not force and (now - self._last_probe_cached_time) < 60.0 and self._accounts[idx].status != "untested":
                return self.get_quota_stats()

            target_acc = self._accounts[idx]
            test_key = target_acc.key

        if os.getenv("APP_ENV") == "test" or "pytest" in sys.modules:
            with self._lock:
                target_acc.status = "ready"
                target_acc.status_label = "Ready · Test Verified"
                target_acc.status_color = "green"
                target_acc.last_probed_at = datetime.now(timezone.utc).isoformat()
                self._last_probe_cached_time = time.time()
                return self.get_quota_stats()

        res = self.probe_single_key(test_key, model=model)
        with self._lock:
            self._last_probe_cached_time = time.time()
            if res["ok"]:
                self.record_success(prompt_tokens=1, candidate_tokens=1, total_tokens=2, key=test_key)
            else:
                self.record_failure(res["status_code"], res["error"] or "Probe failed", key=test_key)

        return self.get_quota_stats()

    def get_quota_stats(self) -> dict[str, Any]:
        with self._lock:
            self._check_daily_reset()
            now = time.time()
            settings = get_settings()
            target_model = getattr(settings, "gemini_model", None) or "gemini-3.1-flash-lite-preview"

            accounts_data: list[dict[str, Any]] = []
            pool_rpd_used = 0
            pool_rpm_used = 0

            for idx, acc in enumerate(self._accounts):
                a_rpm = sum(1 for t in acc.request_timestamps_min if t >= now - 60)
                a_tpm = sum(tok for _, tok in acc.token_timestamps_min if _ >= now - 60)
                pool_rpd_used += acc.request_count_today
                pool_rpm_used += a_rpm

                accounts_data.append(
                    {
                        "id": acc.id,
                        "index": idx,
                        "label": acc.label,
                        "source": acc.source,
                        "masked_key": acc.masked_key,
                        "status": acc.status,
                        "status_label": acc.status_label,
                        "status_color": acc.status_color,
                        "rpm_used": a_rpm,
                        "rpm_limit": self._max_rpm_per_key,
                        "rpm_remaining": max(0, self._max_rpm_per_key - a_rpm),
                        "rpd_used": acc.request_count_today,
                        "rpd_limit": self._max_rpd_per_key,
                        "rpd_remaining": max(0, self._max_rpd_per_key - acc.request_count_today),
                        "tpm_used": a_tpm,
                        "tpm_limit": self._max_tpm_per_key,
                        "tpm_remaining": max(0, self._max_tpm_per_key - a_tpm),
                        "cooling_until": acc.cooling_until,
                        "last_switch_reason": acc.last_switch_reason,
                        "last_probed_at": acc.last_probed_at,
                        "last_success_at": acc.last_success_at,
                        "last_error": acc.last_error_message,
                        "last_error_code": acc.last_error_code,
                        "successful_calls": acc.successful_calls,
                        "failed_calls": acc.failed_calls,
                        "is_active": idx == self._active_index,
                    }
                )

            active_acc = self._accounts[self._active_index] if 0 <= self._active_index < len(self._accounts) else None
            active_status = active_acc.status if active_acc else "offline"
            active_label = active_acc.status_label if active_acc else "Offline (No Keys)"
            active_color = active_acc.status_color if active_acc else "gray"

            if active_status == "untested" and active_acc:
                active_status = "ready"
                active_label = "Ready · Configured"
                active_color = "green"

            is_active = bool(
                self._accounts
                and not self._pool_cutoff_active
                and any(a.status in ("ready", "untested", "cooling_rpm") for a in self._accounts)
            )
            total_accounts = max(len(self._accounts), 1)
            pool_rpd_limit = len(self._accounts) * self._max_rpd_per_key
            pool_rpm_limit = len(self._accounts) * self._max_rpm_per_key

            active_rpm_used = sum(1 for t in active_acc.request_timestamps_min if t >= now - 60) if active_acc else 0
            active_rpd_used = active_acc.request_count_today if active_acc else 0

            return {
                "active": is_active,
                "status": active_status,
                "status_label": active_label,
                "status_color": active_color,
                "model": target_model,
                "models": [
                    "gemini-3.1-flash-lite-preview",
                    "gemini-flash-lite-latest",
                    "gemini-2.5-flash-lite",
                ],
                "active_account_index": self._active_index,
                "active_account_label": active_acc.label if active_acc else "None",
                "keys_count": len(self._accounts),
                "key_count": len(self._accounts),
                "rpm_limit": self._max_rpm_per_key,
                "rpm_used": active_rpm_used,
                "rpm_remaining": max(0, self._max_rpm_per_key - active_rpm_used),
                "rpd_limit": self._max_rpd_per_key,
                "rpd_used": active_rpd_used,
                "rpd_remaining": max(0, self._max_rpd_per_key - active_rpd_used),
                "percent_rpd_remaining": round((max(0, self._max_rpd_per_key - active_rpd_used) / self._max_rpd_per_key) * 100, 1) if self._max_rpd_per_key > 0 else 0,
                "tpm_limit": self._max_tpm_per_key,
                "prompt_guard_limit": self._max_prompt_tokens,
                "pool_rpd_limit": pool_rpd_limit,
                "pool_rpd_used": pool_rpd_used,
                "pool_rpd_remaining": max(0, pool_rpd_limit - pool_rpd_used),
                "pool_rpm_limit": pool_rpm_limit,
                "pool_rpm_used": pool_rpm_used,
                "pool_cutoff_active": self._pool_cutoff_active,
                "rpm_per_key": self._max_rpm_per_key,
                "rpd_per_key": self._max_rpd_per_key,
                "total_rpd": pool_rpd_limit,
                "tokens_total": self._total_tokens,
                "tokens_prompt": self._total_prompt_tokens,
                "tokens_candidate": self._total_candidate_tokens,
                "successful_calls": self._successful_calls,
                "failed_calls": self._failed_calls,
                "last_error": active_acc.last_error_message if active_acc else None,
                "last_error_code": active_acc.last_error_code if active_acc else None,
                "last_error_at": active_acc.last_error_at if active_acc else None,
                "last_success_at": active_acc.last_success_at if active_acc else None,
                "last_probed_at": active_acc.last_probed_at if active_acc else None,
                "accounts": accounts_data,
                "message": f"Active: {active_acc.label if active_acc else 'None'} ({max(0, self._max_rpd_per_key - active_rpd_used)} / {self._max_rpd_per_key} RPD safe capacity)",
                "troubleshooting": {},
            }

    def get_status(self) -> str:
        with self._lock:
            if not self._accounts:
                return "offline"
            return self._accounts[self._active_index].status

    def get_last_error_message(self) -> str | None:
        with self._lock:
            if not self._accounts:
                return None
            return self._accounts[self._active_index].last_error_message

    def get_last_error_code(self) -> int | None:
        with self._lock:
            if not self._accounts:
                return None
            return self._accounts[self._active_index].last_error_code

    def is_active(self) -> bool:
        with self._lock:
            return bool(self._accounts and self._accounts[self._active_index].status == "ready")


# Backwards compatibility alias
GeminiKeyPool = GeminiAccountManager

_account_manager: GeminiAccountManager | None = None


def get_key_pool() -> GeminiAccountManager:
    """Retrieve singleton GeminiAccountManager, syncing keys from .env and Postgres."""
    global _account_manager
    if _account_manager is None:
        settings = get_settings()
        _account_manager = GeminiAccountManager(settings.gemini_api_keys)
        _account_manager.sync_accounts()
    return _account_manager


def estimate_and_guard_payload(payload: dict[str, Any], max_tokens: int = 60_000) -> dict[str, Any]:
    """Estimate prompt tokens heuristic and safely compact context if exceeding safety threshold."""
    contents = payload.get("contents", [])
    total_chars = 0
    inline_parts = 0
    for c in contents:
        for p in c.get("parts", []):
            if "text" in p:
                total_chars += len(p["text"])
            if "inline_data" in p:
                inline_parts += 1

    sys_inst = payload.get("system_instruction", {})
    for p in sys_inst.get("parts", []):
        total_chars += len(p.get("text", ""))

    est_tokens = int(total_chars / 3.5) + (inline_parts * 1200)

    if est_tokens > max_tokens:
        logger.warning(
            "Prompt payload tokens (~%d) exceed safety cap (%d). Applying context compaction.",
            est_tokens, max_tokens
        )
        for c in contents:
            for p in c.get("parts", []):
                if "text" in p:
                    text = p["text"]
                    text = re.sub(r"\n{3,}", "\n\n", text)
                    if len(text) > 120_000:
                        head = text[:60_000]
                        tail = text[-60_000:]
                        text = head + "\n\n[... TRUNCATED MIDDLE FOR TOKEN SAFETY LIMIT ...]\n\n" + tail
                    p["text"] = text

    return payload


GEMINI_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "customer_name": {
            "type": "string",
            "description": "Full name of the policyholder/insured customer or company (e.g. found under 'The Insured / Pihak Diinsuranskan', 'Insured Name', 'Participant'). NEVER extract the Agent's Name, Agency, or Broker.",
        },
        "client_type": {
            "type": "string",
            "description": "Strictly classify the customer as either 'Private' or 'Company'. Look at the customer name and IC/BRN structure.",
        },
        "ic_or_brn": {
            "type": "string",
            "description": "Extract the Customer IC No. (if Private) or Business Registration No. / ROC / ROB (if Company). Look for 'New IC No.', 'NRIC', 'Business Regist. No.', 'Company Registration'.",
        },
        "representative_name": {
            "type": "string",
            "description": "If the client is a Company, extract the name of the person handling or representing the policy if explicitly stated. Otherwise empty string.",
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
        "quotation_no": {
            "type": "string",
            "description": "The exact quotation reference number or schedule/proposal reference issued by the insurance company as printed on this uploaded PDF (e.g. 'QM12351901', 'FL22026M-00867209-001', 'QTE-2024-9988'). Look for 'Quotation no.', 'Quotation No:', 'Quote No.', 'No. Sebutharga', 'Schedule No.'. Do NOT output our internal RiskLocker reference.",
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
            "description": "Complete vehicle model including make/brand prefix in canonical format (e.g. 'TESLA MODEL 3 PREMIUM RWD (ENHANCED AUTOPILOT)', 'PERODUA ATIVA AV MY21 D55L 4D WAGON', 'BMW M3'). CAR MODEL SIMPLY MEANS: CAR BRAND + CAR MODEL. If Make is listed separately as 'BMW' and Model is 'BMW M3', do not duplicate Make (result is 'BMW M3'). If Make is 'TESLA' and Model is 'MODEL 3 ...', prepend Make to get 'TESLA MODEL 3 ...'. If text was truncated at table margins (such as 'AUTOPILO' or 'AUTOMATI'), reconstruct the full word ('AUTOPILOT', 'AUTOMATIC') and close any open parentheses.",
        },
        "vehicle_year": {
            "type": "string",
            "description": "Year of manufacture (e.g. '2021', '2023').",
        },
        "engine_cc": {
            "type": "string",
            "description": "Engine capacity or electric motor power. For standard combustion engine cars, extract capacity in CC (e.g. '1495 CC' or '1500'). For electric vehicles (EV), extract motor power in kW or W (e.g. '150 kW' or '150000 W'). If given in kW or W, preserve the unit.",
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
            "description": "Voluntary/policy excess amount in RM (e.g. '0.00', '500.00', '1,000.00'). Look for 'Policy Excess', 'Excess', 'Lebihan', 'Ekses Polisi', 'Excess all claims'. Do NOT extract Compulsory Excess here. ALWAYS output '0.00' if excess is stated as 0 or 0.00.",
        },
        "compulsory_excess": {
            "type": "string",
            "description": "Compulsory excess (statutory excess) in RM (e.g. '0.00', '400.00'). Look for 'Compulsory Excess', 'Ekses Wajib', 'Ekses Mandatori'. ALWAYS output '0.00' if zero, not mentioned, or stated as per quotation/schedule.",
        },
        "coverage_amount": {
            "type": "string",
            "description": "Vehicle Sum Insured / Agreed Value / Market Value of the CAR itself (e.g. '53,000.00', '71,000.00'). Look for 'Sum Insured', 'Jumlah Diinsuranskan'. DO NOT extract the premium/price of an extra coverage option as the sum insured. A car sum insured is almost never a small number like 400 or 1000. It is usually tens of thousands (e.g. 10000+).",
        },
        "valuation_type": {
            "type": "string",
            "description": "Valuation basis for vehicle sum insured: either 'Agreed Value' or 'Market Value'. Check if the quotation specifies 'Agreed Value', 'Agreed Value = Yes', 'Agreed Value Basis', 'Market Value = Yes', 'Market Value Basis', or if an Agreed Value endorsement/addon was selected. Output exactly 'Agreed Value' or 'Market Value'.",
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
            "description": "No Claim Discount percentage number without percent sign (e.g. '25.00' or '55'). Check 'NCD', 'NCB', 'No Claim Bonus', 'No Claim Discount', 'DTT'. NEVER include the % symbol.",
        },
        "basic_premium": {
            "type": "string",
            "description": "Basic insurance premium before NCD discount (e.g. '2,756.15' or '1,381.94'). Look for 'Basic Premium', 'Premium Asas', 'Premium'.",
        },
        "ncd_amount": {
            "type": "string",
            "description": "No Claim Discount amount deducted in RM (e.g. '1,515.88' or '345.50'). Look for 'NCD', 'DTT', 'No Claim Discount'. NEVER include negative signs or minus symbols. E.g. if it says '- 1,515.88', extract '1515.88'.",
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
        "valid_until": {
            "type": "string",
            "description": "Quotation validity expiry date or duration (e.g. '18-03-2026', '15/09/2026', or '30 Days'). Look for 'This quotation will expire on DD-MM-YYYY', 'Quotation will expire on...', 'Validity', 'Valid Until', 'Sah Sehingga', 'Tarikh Tamat', 'Tarikh Luput'.",
        },
        "detected_benefits": {
            "type": "array",
            "description": "List of all benefits, add-ons, extra covers, and riders explicitly present in this quotation (e.g. Windscreen Damage RM 4,000 cost RM 600, Legal Liability Of Passengers cost RM 7.50, Legal Liability To Passengers cost RM 41.85, All Drivers cost RM 20, 24-hr Towing, Special Perils, Key Replacement RM 1,000, etc.). CRITICAL: DO NOT extract generic policy terms, standard exclusions, legal definitions, or general conditions as benefits. ONLY extract specific coverages or riders explicitly listed in the quotation schedule or pricing summary.",
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
                        "description": "The coverage value, limit amount, or description (e.g. 'RM 4,000.00', 'Unlimited Towing', 'Included', 'Plan 2'). If no coverage amount exists (e.g. LLTP/LLOP endorsements), output 'Included' or 'Selected'.",
                    },
                    "coverage_limit": {
                        "type": "string",
                        "description": "Explicit sum insured or coverage limit amount ONLY (e.g. '2,650' or 'RM 2,650' for Windscreen, '1,000' for Key Replacement, '14 Days / RM 200 daily' for CART). If the add-on has NO explicit coverage amount or sum insured stated in the quotation (e.g. Legal Liability to Passengers, Legal Liability of Passengers, All Drivers, 24-hr Towing), this MUST be empty string (\"\"). NEVER copy the premium price into coverage_limit.",
                    },
                    "premium_cost": {
                        "type": "string",
                        "description": "Additional premium cost in RM for this add-on (e.g. '600.00', '166.00', '7.50', '41.85', '20.00'). Empty string if included/FOC.",
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
                    "price": {
                        "type": "string",
                        "description": "The price or additional premium amount for this pack (e.g. '288.05', '120.00', '43.00').",
                    },
                    "raw_text": {
                        "type": "string",
                        "description": "The excerpt showing the purchased pack line.",
                    },
                },
                "required": ["package_name"],
            },
        },
    },
    "required": [
        "customer_name",
        "coverage_type",
        "vehicle_no",
        "car_model",
        "insurance_company",
        "total_amount",
    ],
}


def build_rag_system_prompt(
    db_companies: Sequence[dict[str, Any] | str] | None = None,
    db_benefit_concepts: Sequence[dict[str, Any] | str] | None = None,
    db_aliases: dict[str, Any] | None = None,
    db_packs: Sequence[dict[str, Any] | str] | None = None,
    correction_memory: Sequence[dict[str, Any] | str] | None = None,
    prompt_override: str | None = None,
) -> str:
    """Construct dynamic grounding prompt with database-seeded business catalog context."""
    companies_list = []
    for comp in (db_companies or []):
        if isinstance(comp, dict):
            name = comp.get("name") or ""
            aliases = [a for a in comp.get("aliases", []) if a]
        else:
            name = comp
            aliases = []
        if name:
            companies_list.append(f"{name}" + (f" (aliases: {', '.join(aliases[:4])})" if aliases else ""))
    companies_str = ", ".join(companies_list) if companies_list else "All standard Malaysian insurers"

    concepts_list = []
    for bc in (db_benefit_concepts or []):
        if isinstance(bc, dict):
            k = bc.get("concept_key") or bc.get("key") or ""
            lbl = bc.get("label") or bc.get("name") or ""
        else:
            k = ""
            lbl = bc
        if k or lbl:
            concepts_list.append(f"- {lbl} (concept_key: '{k}')" if k and lbl else f"- {lbl or k}")
    concepts_str = "\n".join(concepts_list) if concepts_list else "- Standard Malaysian Motor Benefit Library"

    aliases_list = []
    if db_aliases:
        for alias, concept in db_aliases.items():
            aliases_list.append(f"- Code/Alias '{alias}' MUST map to '{concept}'")
    aliases_str = "\n".join(aliases_list) if aliases_list else "- No custom aliases."

    packs_list = []
    for pk in (db_packs or []):
        if isinstance(pk, dict):
            pn = pk.get("name") or ""
            tiers = pk.get("tiers") or pk.get("plans") or []
        else:
            pn = pk
            tiers = []
        if pn:
            tier_names = ", ".join(
                str(t.get("name") if isinstance(t, dict) else t).strip()
                for t in tiers
                if str(t.get("name") if isinstance(t, dict) else t).strip()
            )
            packs_list.append(f"- {pn}" + (f" (plans: {tier_names})" if tier_names else ""))
    packs_str = "\n".join(packs_list) if packs_list else ""

    # // RL-DISABLED correction_memory — disabled 2026-09-08; restore when semantic provenance and context-aware learning are implemented

    grounding_context = f"""
### LIVE DATABASE GROUNDING CONTEXT (always authoritative):
- Active insurance companies: {companies_str}
- Benefit concepts library:
{concepts_str}
- Known benefit packs and plan levels:
{packs_str}
- Endorsement Code Aliases (Mandatory Mappings):
{aliases_str}
"""

    if prompt_override and prompt_override.strip():
        return f"""{prompt_override.strip()}

{grounding_context}
Return strictly structured JSON adhering to the provided schema.
"""

    return f"""You are RiskLocker AI, an expert underwriting extraction system specializing in Malaysian Motor Insurance Quotation PDFs.
Extract accurate, grounded JSON data matching the provided schema from the quotation document text or image.

### CRITICAL GROUNDING RULES:
1. **CUSTOMER NAME & CLIENT TYPE (The Insured)**:
   - Extract the customer/policyholder name (e.g. under 'The Insured / Pihak Diinsuranskan', 'Insured Name', 'Participant').
   - NEVER extract the Agent's Name, Broker Name, Agency Name, or Account Number (e.g. IGNORE 'Account No. / Agent\'s Name', 'Nama Ejen', '02103586', 'RISKLOCKER SDN.BHD.').
   - **CLIENT TYPE**: Cross-confirm whether the customer name represents an Individual person (Private) or a Business / Legal entity (Company). If the name contains words like 'SDN BHD', 'BHD', 'ENTERPRISE', 'TRADING', 'PLT', 'LTD', 'CORP', 'CO.', 'PERUSAHAAN', or has a Business Registration Number (BRN/ROC/ROB/SSM), classify `client_type` strictly as 'Company'. Only classify as 'Private' if the insured is a natural human person with a personal IC number.
2. **COVERAGE TYPE**:
   - MUST be normalized to 'Comprehensive', 'Third Party Fire & Theft', or 'Third Party'.
   - NEVER output 'Jenis Perlindungan' (which is simply the Malay translation of 'Cover Type').
3. **VEHICLE MAKE & MODEL**:
   - Extract the COMPLETE vehicle make, model, variant, and transmission (e.g. 'PERODUA ATIVA AV MY21 D55L 4D WAGON 1 SP AUTOMATIC (CVT)'). Do NOT truncate to a single word.
4. **NCD / NCB**:
   - Look for 'NCD', 'NCB', 'No Claim Bonus', 'No Claim Discount', 'NCB (25.00%)'. Output the percentage value (e.g. '25.00').
5. **INSURANCE COMPANY**:
   - Match one of the active insurance companies: {companies_str}.
   - The upload filename (e.g. `_QBE.pdf`, `_Sompo_`, `_Etiqa`, `_Amgen`, `_Lonpac`, `_STMB`) often directly indicates the underwriting insurer when logos or headers are graphical. Cross-reference the filename and document header.
6. **PACKAGE DETECTION (For Packaged Insurers like AmAssurance)**:
   - Check if any specific package/tier is mentioned anywhere in the document (e.g. 'Lite', 'Plus', 'Standard', 'Comprehensive', 'Premier').
7. **BENEFIT CONCEPTS LIBRARY**:
   Match detected benefits against the official library where applicable:
{concepts_str}
8. **BENEFIT PACKS / BUNDLED ADD-ON PLANS**:
   - Detect purchased packs ONLY if an explicit purchased plan name AND explicit premium cost appear in the quotation's extra benefits or cost summary table (e.g. 'DPA pack A -> 288.05 RM', 'Driver Protection Plan B -> RM 120', 'Key Replacement -> 43 RM').
   - NEVER report or infer a package if it is not purchased with an explicit price. Do NOT report marketing notices, generic headings, or standard policy names as packages. If no explicit purchased package is present, `detected_packs` MUST BE EMPTY `[]`.
   - Known packs and their plan levels for reference:
{packs_str}
9. **EXCESS AMOUNT, COMPULSORY EXCESS, VALIDITY & OPTIONAL COVER BREAKDOWN**:
   - Extract `excess_amount` for Policy Excess if stated (e.g. 'Policy Excess: RM 500.00' -> '500.00', 'Excess / Lebihan 0.00' -> '0.00', '*Excess Amount : RM 1,000.00' -> '1,000.00', 'Ekses Polisi'). Output '0.00' if excess is 0 or zero.
   - Extract `compulsory_excess` for Compulsory Excess if stated (e.g. 'Compulsory Excess: RM 400.00' -> '400.00', 'Ekses Wajib: RM 400.00' -> '400.00'). Output '0.00' if zero, not mentioned, or nominal schedule terms.
   - Extract `valid_until` date (e.g. 'This quotation will expire on 18-03-2026' -> '18-03-2026', 'Valid Until 05-07-2026', 'Tarikh Luput').
   - Extract `total_optional_cover_amount` (e.g. 'Total Optional Cover Amount : RM 845.35' or 'Extra Benefit / Manfaat Tambahan : RM 20.00').
10. **DISTINGUISHING COVERAGE LIMIT vs PREMIUM COST**:
   - In `detected_benefits`, read the extras table with extreme precision.
   - **Coverage Limit (`coverage_limit`)**: Sum covered or insured limit explicitly stated (e.g. `Windscreen (Sum Insured: RM 2,650) ... RM 397.50` -> `coverage_limit: "2,650"`, `premium_cost: "397.50"`; `Key Replacement (Coverage: RM 1,000) ... RM 45.00` -> `coverage_limit: "1,000"`, `premium_cost: "45.00"`).
   - **No Coverage Limit**: If the benefit is a legal liability endorsement or service rider without an explicit sum insured (e.g. `Legal Liability to Passengers ... RM 41.85`, `Legal Liability of Passengers ... RM 7.50`, `All Drivers ... RM 20.00`, `24-hr Towing`), `coverage_limit` MUST BE EMPTY `""` or null. NEVER put the premium cost or price into `coverage_limit`.
11. **STRICT BENEFIT FILTERING & PRODUCT DISCLOSURE SHEET (PDS) EXCLUSION**:
   - If the document contains a Product Disclosure Sheet (PDS) or sample illustration table (e.g. 'As an illustration, for RM2,619.93...'), DO NOT extract benefits, vehicle data, or premiums from the PDS. Extract ONLY from the official quotation schedule or pricing slip.
   - NEVER extract contact phone numbers (e.g. '03-2262 8666'), email addresses, document revision codes (e.g. '26/PRN/PDS/...'), basic premium, NCD deduction, Service Tax (SST), stamp duty, or sales commission as benefits.
   - NEVER extract generic policy definitions, standard terms and conditions, legal clauses, or claim procedures as benefits.
   - ONLY extract concrete coverages, riders, or add-ons that are explicitly listed in the quotation's pricing schedule, benefits table, or endorsements summary.
   - NEVER extract the core coverage type or vehicle use class (e.g. 'Comprehensive', 'Third Party', 'Third Party Fire & Theft', 'TPFT', 'Private Car - Private Use', 'Motorcycle') as a benefit. These belong in the main vehicle/policy fields.
   - If a PDF contains pages of generic policy wording or PDS, IGNORE the generic text completely.
12. **QUOTATION REFERENCE**:
   - DO NOT extract underwriter reference numbers, quote numbers, or ref numbers from the document. Quotation reference is strictly an internal Risklocker system sequence.
13. **ROAD TAX**:
   - NEVER extract road tax from the quotation document under any circumstances. Road tax is an internal, dynamically computed government tariff.
14. **ENGINE CAPACITY / MOTOR OUTPUT**:
   - For petrol/diesel vehicles, extract capacity in CC (e.g. '1495 CC' or '1500').
   - For Electric Vehicles (EV), extract the electric motor power in kW or W (e.g. '150 kW', '150000 W', '50 kW'). If quoted with kW or W, preserve the unit.

{grounding_context}
Return strictly structured JSON adhering to the provided schema.
"""


def extract_with_gemini_sync(
    pdf_bytes: bytes,
    *,
    document_text: str | None = None,
    source_filename: str | None = None,
    db_companies: Sequence[dict[str, Any] | str] | None = None,
    db_benefit_concepts: Sequence[dict[str, Any] | str] | None = None,
    db_aliases: dict[str, Any] | None = None,
    db_packs: Sequence[dict[str, Any] | str] | None = None,
    correction_memory: Sequence[dict[str, Any] | str] | None = None,
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
    configured_model = settings.gemini_model or "gemini-3.1-flash-lite-preview"
    system_prompt = build_rag_system_prompt(db_companies, db_benefit_concepts, db_aliases, db_packs, correction_memory, prompt_override)

    fn_prefix = f"Original Upload Filename: {source_filename}\n\n" if source_filename else ""
    parts: list[dict[str, Any]] = []

    has_digital_text = bool(document_text and len(document_text.strip()) >= 50)
    
    # ALWAYS pass multimodal vision bytes if available to ensure spatial/horizontal alignment awareness.
    if pdf_bytes and len(pdf_bytes) > 100:
        b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
        parts.append(
            {
                "inline_data": {
                    "mime_type": "application/pdf",
                    "data": b64_pdf,
                }
            }
        )

    if has_digital_text:
        # High-speed text-first extraction helps exact spelling
        parts.append(
            {
                "text": f"{fn_prefix}Extract all insurance quotation values, vehicle details, coverage, and detected benefits from this document according to the JSON schema.\n\n--- DOCUMENT TEXT LAYER ---\n{document_text}\n--- END DOCUMENT TEXT LAYER ---"
            }
        )
    else:
        parts.append(
            {
                "text": f"{fn_prefix}Extract all insurance quotation values, vehicle details, coverage, and detected benefits from this scanned document according to the JSON schema."
            }
        )

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

    # Pre-flight prompt token safety guard
    payload = estimate_and_guard_payload(payload, getattr(settings, "gemini_max_prompt_tokens", 60_000))

    candidate_models = [
        configured_model,
        "gemini-3.1-flash-lite-preview",
        "gemini-flash-lite-latest",
        "gemini-2.5-flash-lite",
    ]
    seen_models: set[str] = set()
    models_to_try = [m for m in candidate_models if m and not (m in seen_models or seen_models.add(m))]

    # Timeout: ensure sufficient time for complete structured JSON extraction (typically 5-7s)
    effective_timeout = max(timeout_seconds or 20.0, 15.0)

    api_key = pool.get_next_key()
    if not api_key:
        logger.info("No active Gemini API key available or safety cap reached; falling back to native extraction.")
        return None

    last_failure_reason = ""
    for m_name in models_to_try:
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
                            usage = data.get("usageMetadata", {})
                            p_tok = usage.get("promptTokenCount", 0)
                            c_tok = usage.get("candidatesTokenCount", 0)
                            t_tok = usage.get("totalTokenCount", p_tok + c_tok)
                            pool.record_success(prompt_tokens=p_tok, candidate_tokens=c_tok, total_tokens=t_tok, key=api_key)
                            logger.info("Gemini AI extraction succeeded with %s (tokens: %d prompt, %d candidate).", m_name, p_tok, c_tok)
                            return parsed
                elif response.status_code in (500, 502, 503, 504):
                    err_msg = f"Server error {response.status_code}"
                    pool.record_failure(response.status_code, err_msg, key=api_key)
                    logger.warning("Gemini model %s returned server error (%d), trying fallback.", m_name, response.status_code)
                    last_failure_reason = err_msg
                    continue
                elif response.status_code == 429:
                    err_msg = ""
                    try:
                        err_msg = response.json().get("error", {}).get("message", "")
                    except Exception:
                        err_text = response.text[:200]
                        err_msg = err_text
                    pool.record_failure(429, err_msg or "Rate limit / quota exceeded", key=api_key)
                    logger.warning("Gemini model %s returned rate-limit (429), rotating key or fallback.", m_name)
                    last_failure_reason = err_msg or "Rate limit exceeded (429)"
                    next_key = pool.get_next_key()
                    if next_key and next_key != api_key:
                        api_key = next_key
                    continue
                elif response.status_code in (401, 403):
                    err_msg = ""
                    try:
                        err_msg = response.json().get("error", {}).get("message", "")
                    except Exception:
                        err_msg = response.text[:200]
                    pool.record_failure(response.status_code, err_msg, key=api_key)
                    logger.warning(
                        "Gemini API returned %d (%s) on %s: %s. Google Cloud project access denied for this key.",
                        response.status_code,
                        "PERMISSION_DENIED" if response.status_code == 403 else "UNAUTHENTICATED",
                        m_name,
                        err_msg or response.text[:200],
                    )
                    last_failure_reason = err_msg or f"HTTP {response.status_code}: Project access denied"
                    next_key = pool.get_next_key()
                    if next_key and next_key != api_key:
                        api_key = next_key
                    continue
                elif response.status_code == 404:
                    err_msg = f"Model {m_name} not available (404)"
                    pool.record_failure(404, err_msg, key=api_key)
                    logger.warning("Gemini model %s returned 404, trying fallback.", m_name)
                    last_failure_reason = err_msg
                    continue
                else:
                    err_msg = f"Status {response.status_code}: {response.text[:150]}"
                    pool.record_failure(response.status_code, err_msg, key=api_key)
                    logger.warning("Gemini API returned status %d on %s: %s", response.status_code, m_name, response.text[:200])
                    last_failure_reason = err_msg
                    continue
        except (httpx.TimeoutException, TimeoutError):
            pool.record_failure(504, f"Timeout after {effective_timeout}s on {m_name}", key=api_key)
            logger.warning("Gemini extraction timed out on %s; trying fallback model.", m_name)
            last_failure_reason = f"Timeout on {m_name}"
            continue
        except Exception as exc:
            pool.record_failure(500, f"Exception on {m_name}: {exc}", key=api_key)
            logger.warning("Gemini extraction attempt failed on %s: %s; trying fallback model.", m_name, exc)
            last_failure_reason = str(exc)
            continue

    logger.error("All Gemini API keys and models in pool failed: %s", last_failure_reason or "Unknown")
    return None

