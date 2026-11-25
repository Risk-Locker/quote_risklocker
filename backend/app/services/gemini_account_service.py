"""Thread-safe multi-account Gemini manager for Key Pooling and Rotation."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Sequence

import httpx

from app.core.config import get_settings, resolve_active_gemini_model

logger = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo("Asia/Kuala_Lumpur")
    PT_TZ = ZoneInfo("America/Los_Angeles")
except Exception:
    LOCAL_TZ = timezone.utc
    PT_TZ = timezone.utc


def get_current_local_date() -> str:
    """Return calendar date YYYY-MM-DD in Asia/Kuala_Lumpur (UTC+8)."""
    return datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")


def get_pt_cycle_date_for_time(dt: datetime) -> str:
    """Return Google AI Studio quota cycle calendar date YYYY-MM-DD in Pacific Time.

    Google AI Studio resets daily quota at 12:00 AM Pacific Time (4:00 PM MYT in winter / 3:00 PM MYT in summer).
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(PT_TZ).strftime("%Y-%m-%d")


def get_current_pt_cycle_date() -> str:
    """Return current active Google AI Studio quota cycle date YYYY-MM-DD."""
    return datetime.now(PT_TZ).strftime("%Y-%m-%d")


def persist_call_log(
    account_id: str,
    api_key_masked: str | None,
    model: str,
    endpoint_slot: str | None,
    status_code: int,
    is_success: bool,
    prompt_tokens: int = 0,
    candidate_tokens: int = 0,
    total_tokens: int = 0,
    latency_ms: int = 0,
    error_message: str | None = None,
    db: Any = None,
) -> None:
    """Atomically record call metrics into gemini_api_call_logs table."""
    import os, sys
    if os.getenv("APP_ENV") == "test" or "pytest" in sys.modules:
        return

    today_str = get_current_pt_cycle_date()

    def _do_insert(session: Any):
        from app.models.tables import GeminiApiCallLog
        entry = GeminiApiCallLog(
            account_id=account_id or "unknown",
            api_key_masked=api_key_masked or None,
            model=model or "unknown",
            endpoint_slot=endpoint_slot or None,
            status_code=status_code,
            is_success=is_success,
            prompt_tokens=prompt_tokens or 0,
            candidate_tokens=candidate_tokens or 0,
            total_tokens=total_tokens or 0,
            latency_ms=latency_ms or 0,
            error_message=error_message[:1000] if error_message else None,
            local_date=today_str,
        )
        session.add(entry)
        session.commit()

    if db is not None:
        try:
            _do_insert(db)
        except Exception as exc:
            logger.debug("Could not insert Gemini call log with session: %s", exc)
    else:
        try:
            from app.db.session import SessionLocal
            with SessionLocal() as session:
                _do_insert(session)
        except Exception as exc:
            logger.debug("Could not insert Gemini call log with SessionLocal: %s", exc)



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
    last_dispatched_at: float = 0.0

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
    is_paused: bool = False

    @property
    def masked_key(self) -> str:
        if not self.key:
            return ""
        if len(self.key) <= 10:
            return self.key[:2] + "..." + self.key[-2:]
        return self.key[:6] + "..." + self.key[-4:]


PARALLEL_MODELS: tuple[str, ...] = ("gemini-3.1-flash-lite", "gemini-3.5-flash-lite")


class GeminiAccountManager:
    """Thread-safe multi-account Gemini manager supporting up to 8+ parallel model endpoints (2N x 13 RPM, 200k TPM, 480 RPD)."""

    def __init__(self, keys: Sequence[str] = ()):
        self._lock = threading.RLock()
        settings = get_settings()
        self._max_rpd_per_key = getattr(settings, "gemini_max_rpd_per_key", 480)
        self._max_rpm_per_key = getattr(settings, "gemini_max_rpm_per_key", 13)
        self._max_tpm_per_key = getattr(settings, "gemini_max_tpm_per_key", 200_000)
        self._max_prompt_tokens = getattr(settings, "gemini_max_prompt_tokens", 60_000)
        self._max_accounts = getattr(settings, "gemini_max_accounts", 8)

        self._accounts: list[GeminiAccount] = []
        self._active_index: int = 0
        self._last_reset_date: str = get_current_pt_cycle_date()
        self._last_probe_cached_time: float = 0.0
        self._pool_cutoff_active: bool = False
        self._parallel_slots: dict[str, dict[str, Any]] = {}

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
        self._init_parallel_slots()

    def _check_daily_reset(self) -> None:
        """Reset daily quotas and quarantines when passing 12:00 AM Pacific Time (4 PM MYT winter / 3 PM MYT summer)."""
        current_cycle = get_current_pt_cycle_date()
        if current_cycle != self._last_reset_date:
            self._last_reset_date = current_cycle
            for acc in self._accounts:
                acc.request_count_today = 0
                acc.tokens_today = 0
                if acc.status == "exhausted_rpd":
                    acc.status = "ready"
                    acc.status_label = "Ready"
                    acc.status_color = "green"
                acc.quarantine_until = None
            for slot in self._parallel_slots.values():
                slot["request_count_today"] = 0
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

            paused_ids: set[str] = set()
            if db is not None:
                from app.models.tables import AppSetting

                p_set = db.get(AppSetting, "gemini_paused_keys")
                if p_set and isinstance(p_set.value, dict):
                    paused_ids = set(p_set.value.get("paused_ids", []))
                m_set = db.get(AppSetting, "gemini_model_config")
                if m_set and isinstance(m_set.value, dict):
                    par = m_set.value.get("parallel_models")
                    if par:
                        self._parallel_models = tuple(m for m in par if m in PARALLEL_MODELS)
                    pri = m_set.value.get("primary_model")
                    if pri and pri in PARALLEL_MODELS:
                        self._primary_model = pri

            existing_by_key = {acc.key: acc for acc in self._accounts}
            new_accounts: list[GeminiAccount] = []

            # 1. Primary .env key(s)
            for idx, k in enumerate(env_keys):
                acc_id = f"env_{idx}"
                is_p = acc_id in paused_ids
                if k in existing_by_key:
                    acc = existing_by_key[k]
                    acc.label = f"Account {idx + 1} (.env Primary)" if idx == 0 else f"Account {idx + 1} (.env)"
                    acc.source = "env"
                    acc.is_paused = is_p
                    new_accounts.append(acc)
                else:
                    new_accounts.append(
                        GeminiAccount(
                            id=acc_id,
                            key=k,
                            label=f"Account {idx + 1} (.env Primary)" if idx == 0 else f"Account {idx + 1} (.env)",
                            source="env",
                            status="ready",
                            status_label="Ready · Configured",
                            status_color="green",
                            is_paused=is_p,
                        )
                    )

            # 2. Manual keys from Postgres AppSetting
            for idx, item in enumerate(manual_items):
                k = item.get("key", "").strip()
                if not k or any(na.key == k for na in new_accounts):
                    continue
                acc_id = item.get("id") or f"manual_{idx}"
                acc_label = item.get("label") or f"Account {len(new_accounts) + 1} (Manual)"
                is_p = (acc_id in paused_ids) or bool(item.get("is_paused", False))
                if k in existing_by_key:
                    acc = existing_by_key[k]
                    acc.id = acc_id
                    acc.label = acc_label
                    acc.source = "manual"
                    acc.is_paused = is_p
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
                            is_paused=is_p,
                        )
                    )

            # 3. Synchronize honest daily usage counts from Postgres gemini_api_call_logs
            import os, sys
            usage_by_slot: dict[str, int] = {}
            if os.getenv("APP_ENV") != "test" and "pytest" not in sys.modules:
                today_str = get_current_pt_cycle_date()
                usage_by_account: dict[str, int] = {}
                try:
                    from sqlalchemy import text
                    if db is not None:
                        rows = db.execute(
                            text("SELECT account_id, COUNT(*) FROM gemini_api_call_logs WHERE local_date = :dt GROUP BY account_id"),
                            {"dt": today_str}
                        ).fetchall()
                        usage_by_account = {str(r[0]): int(r[1]) for r in rows}
                        slot_rows = db.execute(
                            text("SELECT endpoint_slot, COUNT(*) FROM gemini_api_call_logs WHERE local_date = :dt GROUP BY endpoint_slot"),
                            {"dt": today_str}
                        ).fetchall()
                        usage_by_slot = {str(r[0]): int(r[1]) for r in slot_rows}
                    else:
                        from app.db.session import SessionLocal
                        with SessionLocal() as session:
                            rows = session.execute(
                                text("SELECT account_id, COUNT(*) FROM gemini_api_call_logs WHERE local_date = :dt GROUP BY account_id"),
                                {"dt": today_str}
                            ).fetchall()
                            usage_by_account = {str(r[0]): int(r[1]) for r in rows}
                            slot_rows = session.execute(
                                text("SELECT endpoint_slot, COUNT(*) FROM gemini_api_call_logs WHERE local_date = :dt GROUP BY endpoint_slot"),
                                {"dt": today_str}
                            ).fetchall()
                            usage_by_slot = {str(r[0]): int(r[1]) for r in slot_rows}
                except Exception as exc:
                    logger.debug("Could not sync gemini usage from DB: %s", exc)

                for acc in new_accounts:
                    db_cnt = usage_by_account.get(acc.id, 0)
                    acc.request_count_today = max(acc.request_count_today, db_cnt)

            self._accounts = new_accounts[:self._max_accounts]
            if self._active_index >= len(self._accounts):
                self._active_index = 0
            self._init_parallel_slots()
            if usage_by_slot:
                for s_id, s_data in self._parallel_slots.items():
                    s_data["request_count_today"] = max(s_data.get("request_count_today", 0), usage_by_slot.get(s_id, 0))

    def _init_parallel_slots(self) -> None:
        """Initialize or sync 2 models x N keys parallel slots with independent per-model quota limits (500 RPD / 15 RPM raw; 460 RPD / 12 RPM / 220k TPM buffered)."""
        new_slots: dict[str, dict[str, Any]] = {}
        active_models = getattr(self, "_parallel_models", PARALLEL_MODELS) or PARALLEL_MODELS
        n_models = max(len(active_models), 1)
        # Google AI Studio quotas are per model per key:
        slot_rpm = self._max_rpm_per_key
        slot_tpm = self._max_tpm_per_key
        slot_rpd = self._max_rpd_per_key

        for acc_idx, acc in enumerate(self._accounts):
            for mod_idx, mod_name in enumerate(active_models):
                slot_id = f"{acc.id}::{mod_name}"
                existing = self._parallel_slots.get(slot_id)
                new_slots[slot_id] = {
                    "slot_id": slot_id,
                    "slot_index": acc_idx * n_models + mod_idx,
                    "account_id": acc.id,
                    "account_index": acc_idx,
                    "account_label": acc.label,
                    "key": acc.key,
                    "masked_key": acc.masked_key,
                    "model": mod_name,
                    "rpm_limit": slot_rpm,
                    "tpm_limit": slot_tpm,
                    "rpd_limit": slot_rpd,
                    "request_count_today": existing.get("request_count_today", 0) if existing else 0,
                    "request_timestamps_min": existing["request_timestamps_min"] if existing else [],
                    "token_timestamps_min": existing["token_timestamps_min"] if existing else [],
                    "cooling_until": existing.get("cooling_until") if existing else None,
                    "successful_calls": existing.get("successful_calls", 0) if existing else 0,
                    "failed_calls": existing.get("failed_calls", 0) if existing else 0,
                    "last_error": existing.get("last_error") if existing else None,
                    "last_dispatched_at": existing.get("last_dispatched_at", 0.0) if existing else 0.0,
                }
        self._parallel_slots = new_slots

    def get_fleet_endpoints(self) -> list[dict[str, Any]]:
        """Return the current parallel model endpoints with live minute rates."""
        with self._lock:
            if not self._parallel_slots:
                self._init_parallel_slots()
            now = time.time()
            endpoints = []
            for slot in sorted(self._parallel_slots.values(), key=lambda s: s["slot_index"]):
                slot_rpm_used = sum(1 for t in slot["request_timestamps_min"] if t >= now - 60)
                slot_tpm_used = sum(tok for t, tok in slot["token_timestamps_min"] if t >= now - 60)
                is_cooling = bool(slot["cooling_until"] and now < slot["cooling_until"])
                acc = next((a for a in self._accounts if a.key == slot["key"]), None)
                is_paused = bool(acc and acc.is_paused)

                if is_paused:
                    is_ready = False
                    status_label = "Off · Paused"
                    status_color = "gray"
                elif is_cooling:
                    is_ready = False
                    status_label = "Cooling (60s)"
                    status_color = "amber"
                elif slot_rpm_used >= slot["rpm_limit"] or slot.get("request_count_today", 0) >= slot["rpd_limit"]:
                    is_ready = False
                    status_label = "At Limit"
                    status_color = "amber"
                else:
                    is_ready = True
                    status_label = "Ready"
                    status_color = "green"

                endpoints.append({
                    "slot_id": slot["slot_id"],
                    "slot_index": slot["slot_index"],
                    "account_label": slot["account_label"],
                    "masked_key": slot["masked_key"],
                    "model": slot["model"],
                    "rpm_used": slot_rpm_used,
                    "rpm_limit": slot["rpm_limit"],
                    "rpm_remaining": max(0, slot["rpm_limit"] - slot_rpm_used),
                    "tpm_used": slot_tpm_used,
                    "tpm_limit": slot["tpm_limit"],
                    "tpm_remaining": max(0, slot["tpm_limit"] - slot_tpm_used),
                    "rpd_used": slot.get("request_count_today", 0),
                    "rpd_limit": slot["rpd_limit"],
                    "rpd_remaining": max(0, slot["rpd_limit"] - slot.get("request_count_today", 0)),
                    "cooling_until": slot["cooling_until"],
                    "is_paused": is_paused,
                    "is_ready": is_ready,
                    "status_label": status_label,
                    "status_color": status_color,
                })
            return endpoints

    def acquire_parallel_slot(
        self,
        batch_item_index: int | None = None,
        requested_model: str | None = None,
        exclude_slot_ids: set[str] | None = None,
    ) -> tuple[str, str, str] | None:
        """Acquire a parallel endpoint slot (api_key, model_name, slot_id) honoring 13 RPM / 200k TPM / 480 RPD per model slot."""
        if requested_model is not None and requested_model not in PARALLEL_MODELS:
            raise ValueError(f"Forbidden model tier: {requested_model}. Allowed models: {PARALLEL_MODELS}")

        with self._lock:
            self._check_daily_reset()
            now = time.time()
            if not self._parallel_slots:
                self._init_parallel_slots()
            if not self._parallel_slots:
                return None

            slots_list = sorted(self._parallel_slots.values(), key=lambda s: s["slot_index"])
            if requested_model is not None:
                slots_list = [s for s in slots_list if s["model"] == requested_model]
            if exclude_slot_ids:
                non_excluded = [s for s in slots_list if s["slot_id"] not in exclude_slot_ids]
                if non_excluded:
                    slots_list = non_excluded
            n_slots = len(slots_list)
            if n_slots == 0:
                return None

            # Clean expired cooling
            for slot in slots_list:
                if slot["cooling_until"] and now >= slot["cooling_until"]:
                    slot["cooling_until"] = None

            # Strict S = 2N round-robin equilibrium via PacerSentinel
            from app.extraction.pacer_sentinel import get_pacer_sentinel, SAFE_RPM_CEILING, SAFE_TPM_CEILING, SAFE_RPD_CEILING

            sentinel = get_pacer_sentinel(n_slots)
            if batch_item_index is not None:
                pref_idx = abs(batch_item_index) % n_slots
            else:
                pref_idx = sentinel.next_slot_index()

            ordered = [slots_list[pref_idx]] + [s for i, s in enumerate(slots_list) if i != pref_idx]

            MIN_KEY_SPACING = 1.8
            best_candidate = None

            for slot in ordered:
                acc = next((a for a in self._accounts if a.key == slot["key"]), None)
                if not acc or acc.is_paused or acc.status in ("denied", "invalid_key"):
                    continue
                # Key daily quota: supports len(PARALLEL_MODELS) * max_rpd_per_key across its models
                if acc.request_count_today >= len(PARALLEL_MODELS) * self._max_rpd_per_key:
                    continue
                # Slot daily quota: 480 RPD (buffered) for its specific model
                effective_rpd = min(slot.get("rpd_limit", SAFE_RPD_CEILING), SAFE_RPD_CEILING)
                if slot.get("request_count_today", 0) >= effective_rpd:
                    continue
                if slot["cooling_until"] and now < slot["cooling_until"]:
                    continue

                slot["request_timestamps_min"] = [t for t in slot["request_timestamps_min"] if t >= now - 60]
                slot["token_timestamps_min"] = [(t, tok) for t, tok in slot["token_timestamps_min"] if t >= now - 60]

                s_rpm = len(slot["request_timestamps_min"])
                s_tpm = sum(tok for _, tok in slot["token_timestamps_min"])
                effective_rpm = min(slot.get("rpm_limit", SAFE_RPM_CEILING), SAFE_RPM_CEILING)
                effective_tpm = min(slot.get("tpm_limit", SAFE_TPM_CEILING), SAFE_TPM_CEILING)

                if s_rpm < effective_rpm and s_tpm < effective_tpm:
                    time_since_last = now - getattr(acc, "last_dispatched_at", 0.0)
                    if time_since_last >= MIN_KEY_SPACING:
                        acc.last_dispatched_at = now
                        slot["last_dispatched_at"] = now
                        slot["request_timestamps_min"].append(now)
                        acc.request_timestamps_min.append(now)
                        acc.request_timestamps_min = [t for t in acc.request_timestamps_min if t >= now - 60]
                        acc.request_count_today += 1
                        slot["request_count_today"] = slot.get("request_count_today", 0) + 1
                        return slot["key"], slot["model"], slot["slot_id"]
                    if best_candidate is None:
                        best_candidate = (slot, acc)

            if best_candidate is not None:
                slot, acc = best_candidate
                acc.last_dispatched_at = now
                slot["last_dispatched_at"] = now
                slot["request_timestamps_min"].append(now)
                acc.request_timestamps_min.append(now)
                acc.request_timestamps_min = [t for t in acc.request_timestamps_min if t >= now - 60]
                acc.request_count_today += 1
                slot["request_count_today"] = slot.get("request_count_today", 0) + 1
                return slot["key"], slot["model"], slot["slot_id"]

            return None

    def record_slot_success(
        self,
        slot_id: str,
        prompt_tokens: int = 0,
        candidate_tokens: int = 0,
        total_tokens: int = 0,
        latency_ms: int = 0,
        endpoint_slot_override: str | None = None,
    ) -> None:
        with self._lock:
            now = time.time()
            slot = self._parallel_slots.get(slot_id)
            tok_count = max(0, total_tokens if total_tokens > 0 else (prompt_tokens + candidate_tokens))
            if slot:
                slot["successful_calls"] += 1
                slot["token_timestamps_min"].append((now, tok_count))
                slot["token_timestamps_min"] = [(t, k) for t, k in slot["token_timestamps_min"] if t >= now - 60]
                slot["cooling_until"] = None
                slot["last_error"] = None
            self.record_success(prompt_tokens=prompt_tokens, candidate_tokens=candidate_tokens, total_tokens=total_tokens, key=slot["key"] if slot else None)

            # Atomically persist call log to Postgres
            if slot:
                acc = next((a for a in self._accounts if a.key == slot["key"]), None)
                acc_id = acc.id if acc else slot.get("account_id", "unknown")
                persist_call_log(
                    account_id=acc_id,
                    api_key_masked=slot.get("masked_key"),
                    model=slot.get("model", "unknown"),
                    endpoint_slot=endpoint_slot_override or slot_id,
                    status_code=200,
                    is_success=True,
                    prompt_tokens=prompt_tokens,
                    candidate_tokens=candidate_tokens,
                    total_tokens=tok_count,
                    latency_ms=latency_ms,
                )

    def record_slot_failure(
        self,
        slot_id: str,
        status_code: int | str,
        error_message: str | int = "",
        latency_ms: int = 0,
        endpoint_slot_override: str | None = None,
        cool_slot: bool = True,
    ) -> None:
        # Defensive parameter auto-normalization if arguments were inverted by caller
        if isinstance(status_code, str) and (isinstance(error_message, int) or (isinstance(error_message, str) and error_message.isdigit())):
            status_code, error_message = int(error_message), status_code
        try:
            status_code = int(status_code)
        except Exception:
            status_code = 500
        clean_msg = str(error_message or "")

        with self._lock:
            now = time.time()
            slot = self._parallel_slots.get(slot_id)
            if slot:
                slot["failed_calls"] += 1
                slot["last_error"] = clean_msg
                if status_code == 429 and cool_slot:
                    slot["cooling_until"] = now + 65.0
            if cool_slot or status_code != 429:
                self.record_failure(status_code, clean_msg, key=slot["key"] if slot else None)

            # Atomically persist call log to Postgres
            if slot:
                acc = next((a for a in self._accounts if a.key == slot["key"]), None)
                acc_id = acc.id if acc else slot.get("account_id", "unknown")
                persist_call_log(
                    account_id=acc_id,
                    api_key_masked=slot.get("masked_key"),
                    model=slot.get("model", "unknown"),
                    endpoint_slot=endpoint_slot_override or slot_id,
                    status_code=status_code,
                    is_success=False,
                    error_message=clean_msg,
                    latency_ms=latency_ms,
                )

    def persist_account_call_log(
        self,
        *,
        key: str | None,
        model: str,
        endpoint_slot: str,
        status_code: int,
        is_success: bool,
        prompt_tokens: int = 0,
        candidate_tokens: int = 0,
        total_tokens: int = 0,
        latency_ms: int = 0,
        error_message: str | None = None,
    ) -> None:
        """Persist a direct/spillover/probe call log entry for an account."""
        with self._lock:
            acc = self._find_account_by_key(key)
            acc_id = acc.id if acc else "unknown"
            masked = acc.masked_key if acc else None
        persist_call_log(
            account_id=acc_id,
            api_key_masked=masked,
            model=model,
            endpoint_slot=endpoint_slot,
            status_code=status_code,
            is_success=is_success,
            prompt_tokens=prompt_tokens,
            candidate_tokens=candidate_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            error_message=error_message,
        )

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

    def set_account_paused(self, account_id: str, paused: bool = True) -> bool:
        """Pause or unpause an account without modifying or deleting its credentials."""
        with self._lock:
            for acc in self._accounts:
                if acc.id == account_id:
                    acc.is_paused = paused
                    logger.info("Account %s (%s) paused state set to %s", acc.id, acc.label, paused)
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
                active.request_timestamps_min.append(now)
                active.request_timestamps_min = [t for t in active.request_timestamps_min if t >= now - 60]
                active.request_count_today += 1
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
                    cand.request_timestamps_min.append(now)
                    cand.request_timestamps_min = [t for t in cand.request_timestamps_min if t >= now - 60]
                    cand.request_count_today += 1
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
            elif status_code == 504:
                acc.status = "timeout"
                acc.status_label = "Timeout (504)"
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
            active_m = resolve_active_gemini_model(model)
            if "invalid" in key.lower():
                return {"ok": False, "status_code": 400, "error": "API_KEY_INVALID", "latency_ms": 45, "model": active_m}
            if "denied" in key.lower() or "403" in key:
                return {"ok": False, "status_code": 403, "error": "Project access denied", "latency_ms": 50, "model": active_m}
            return {"ok": True, "status_code": 200, "error": None, "latency_ms": 40, "model": active_m}

        settings = get_settings()
        target_model = resolve_active_gemini_model(model or getattr(settings, "gemini_model", None))
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={key}"
        test_payload = {
            "contents": [{"parts": [{"text": "ping"}]}],
            "generationConfig": {"maxOutputTokens": 5},
        }

        start_t = time.time()
        try:
            with httpx.Client(timeout=httpx.Timeout(25.0, connect=10.0), http2=False) as client:
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
        except httpx.TimeoutException:
            latency_ms = int((time.time() - start_t) * 1000)
            return {
                "ok": False,
                "status_code": 504,
                "error": "Gemini API request timed out (>25s)",
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

        self.record_request(test_key)
        res = self.probe_single_key(test_key, model=model)
        with self._lock:
            self._last_probe_cached_time = time.time()
            if res["ok"]:
                self.record_success(prompt_tokens=1, candidate_tokens=1, total_tokens=2, key=test_key)
            else:
                self.record_failure(res["status_code"], res["error"] or "Probe failed", key=test_key)

        self.persist_account_call_log(
            key=test_key,
            model=res.get("model") or model or "unknown",
            endpoint_slot=f"probe::{target_acc.id}::{res.get('model') or model or 'default'}",
            status_code=int(res.get("status_code") or (200 if res.get("ok") else 500)),
            is_success=bool(res.get("ok")),
            prompt_tokens=1 if res.get("ok") else 0,
            candidate_tokens=1 if res.get("ok") else 0,
            total_tokens=2 if res.get("ok") else 0,
            latency_ms=int(res.get("latency_ms") or 0),
            error_message=res.get("error"),
        )

        return self.get_quota_stats()

    def probe_model(self, *, model: str, account_index: int | None = None) -> dict[str, Any]:
        """Probe a specific Gemini model across active accounts (or a single account) and persist logs."""
        target_model = resolve_active_gemini_model(model)
        with self._lock:
            self._check_daily_reset()
            if account_index is not None and 0 <= account_index < len(self._accounts):
                targets = [self._accounts[account_index]]
            else:
                targets = [a for a in self._accounts if not a.is_paused]
                if not targets and self._accounts:
                    targets = [self._accounts[0]]
            snapshot = [(a.id, a.label, a.masked_key, a.key) for a in targets]

        results: list[dict[str, Any]] = []
        for acc_id, acc_label, masked, key in snapshot:
            self.record_request(key)
            res = self.probe_single_key(key, model=target_model)
            with self._lock:
                self._last_probe_cached_time = time.time()
                acc_obj = self._find_account_by_key(key)
                if acc_obj:
                    acc_obj.last_probed_at = datetime.now(timezone.utc).isoformat()
                if res["ok"]:
                    self.record_success(prompt_tokens=1, candidate_tokens=1, total_tokens=2, key=key)
                elif int(res.get("status_code") or 0) in (400, 401, 403):
                    self.record_failure(res["status_code"], res["error"] or "Probe failed", key=key)

            self.persist_account_call_log(
                key=key,
                model=target_model,
                endpoint_slot=f"probe::{acc_id}::{target_model}",
                status_code=int(res.get("status_code") or (200 if res.get("ok") else 500)),
                is_success=bool(res.get("ok")),
                prompt_tokens=1 if res.get("ok") else 0,
                candidate_tokens=1 if res.get("ok") else 0,
                total_tokens=2 if res.get("ok") else 0,
                latency_ms=int(res.get("latency_ms") or 0),
                error_message=res.get("error"),
            )
            results.append(
                {
                    "account_id": acc_id,
                    "label": acc_label,
                    "masked_key": masked,
                    "model": target_model,
                    "ok": bool(res.get("ok")),
                    "status_code": int(res.get("status_code") or 500),
                    "latency_ms": int(res.get("latency_ms") or 0),
                    "error": res.get("error"),
                }
            )

        any_ok = any(r["ok"] for r in results)
        all_ok = bool(results) and all(r["ok"] for r in results)
        return {
            "model": target_model,
            "overall_ok": any_ok,
            "all_ok": all_ok,
            "tested_count": len(results),
            "results": results,
        }

    def get_quota_stats(self) -> dict[str, Any]:
        with self._lock:
            self._check_daily_reset()
            now = time.time()
            settings = get_settings()
            target_model = resolve_active_gemini_model(getattr(settings, "gemini_model", None))

            today_str = get_current_pt_cycle_date()
            db_counts_by_account: dict[str, int] = {}
            db_pool_rpd_used = None
            import os, sys
            if os.getenv("APP_ENV") != "test" and "pytest" not in sys.modules:
                try:
                    from sqlalchemy import text
                    from app.db.session import SessionLocal
                    with SessionLocal() as session:
                        rows = session.execute(
                            text("SELECT account_id, COUNT(*) FROM gemini_api_call_logs WHERE local_date = :dt GROUP BY account_id"),
                            {"dt": today_str}
                        ).fetchall()
                        for acc_id_val, cnt_val in rows:
                            db_counts_by_account[str(acc_id_val)] = int(cnt_val)
                        total_cnt = session.execute(
                            text("SELECT COUNT(*) FROM gemini_api_call_logs WHERE local_date = :dt"),
                            {"dt": today_str}
                        ).scalar()
                        if total_cnt is not None:
                            db_pool_rpd_used = int(total_cnt)
                except Exception as exc:
                    logger.debug("Could not query DB for Gemini stats: %s", exc)

            accounts_data: list[dict[str, Any]] = []
            pool_rpd_used = 0
            pool_rpm_used = 0

            for idx, acc in enumerate(self._accounts):
                a_rpm = sum(1 for t in acc.request_timestamps_min if t >= now - 60)
                a_tpm = sum(tok for _, tok in acc.token_timestamps_min if _ >= now - 60)
                db_acc_used = db_counts_by_account.get(acc.id, 0)
                effective_rpd_used = max(acc.request_count_today, db_acc_used)
                pool_rpd_used += effective_rpd_used
                pool_rpm_used += a_rpm

                acc_rpd_limit = len(PARALLEL_MODELS) * self._max_rpd_per_key
                acc_rpm_limit = len(PARALLEL_MODELS) * self._max_rpm_per_key
                acc_tpm_limit = len(PARALLEL_MODELS) * self._max_tpm_per_key

                acc_is_active = not acc.is_paused and acc.status not in ("denied", "invalid_key")
                acc_label = "Off · Paused" if acc.is_paused else ("Active" if acc.status in ("ready", "untested") else acc.status_label)
                acc_color = "gray" if acc.is_paused else ("green" if acc.status in ("ready", "untested") else acc.status_color)

                accounts_data.append(
                    {
                        "id": acc.id,
                        "index": idx,
                        "label": acc.label,
                        "source": acc.source,
                        "masked_key": acc.masked_key,
                        "status": "paused" if acc.is_paused else acc.status,
                        "status_label": acc_label,
                        "status_color": acc_color,
                        "rpm_used": a_rpm,
                        "rpm_limit": acc_rpm_limit,
                        "rpm_remaining": max(0, acc_rpm_limit - a_rpm),
                        "rpd_used": effective_rpd_used,
                        "rpd_limit": acc_rpd_limit,
                        "rpd_remaining": max(0, acc_rpd_limit - effective_rpd_used),
                        "tpm_used": a_tpm,
                        "tpm_limit": acc_tpm_limit,
                        "tpm_remaining": max(0, acc_tpm_limit - a_tpm),
                        "cooling_until": acc.cooling_until,
                        "last_switch_reason": acc.last_switch_reason,
                        "last_probed_at": acc.last_probed_at,
                        "last_success_at": acc.last_success_at,
                        "last_error": acc.last_error_message,
                        "last_error_code": acc.last_error_code,
                        "successful_calls": acc.successful_calls,
                        "failed_calls": acc.failed_calls,
                        "is_active": acc_is_active,
                        "is_paused": acc.is_paused,
                    }
                )

            if db_pool_rpd_used is not None and db_pool_rpd_used > pool_rpd_used:
                pool_rpd_used = db_pool_rpd_used

            fleet_endpoints = self.get_fleet_endpoints()
            active_accounts = [a for a in self._accounts if not a.is_paused and a.status not in ("denied", "invalid_key")]
            active_keys_count = len(active_accounts)
            total_keys_count = len(self._accounts)
            models_count = len(PARALLEL_MODELS)
            total_endpoints = total_keys_count * models_count
            active_endpoints_count = active_keys_count * models_count

            # Active limits scale dynamically with active (unpaused) keys
            pool_rpd_limit = active_endpoints_count * self._max_rpd_per_key
            pool_rpm_limit = active_endpoints_count * self._max_rpm_per_key
            pool_tpm_limit = active_endpoints_count * self._max_tpm_per_key
            raw_rpd_capacity = active_endpoints_count * 500
            raw_rpm_capacity = active_endpoints_count * 15
            tokens_budget = 43_000

            if not self._accounts:
                overall_status = "offline"
                overall_label = "Offline (No Keys)"
                overall_color = "gray"
                is_active = False
            elif active_keys_count == 0:
                overall_status = "paused"
                overall_label = "Fleet Offline (All Keys Paused)"
                overall_color = "gray"
                is_active = False
            elif self._pool_cutoff_active:
                overall_status = "cutoff"
                overall_label = "Fleet Quota Exceeded (Safety Cutoff)"
                overall_color = "red"
                is_active = False
            elif active_keys_count == total_keys_count:
                overall_status = "ready"
                overall_label = "Fleet Online · All Keys Active"
                overall_color = "green"
                is_active = True
            else:
                overall_status = "ready"
                overall_label = f"{active_endpoints_count}/{total_endpoints} Endpoints Active ({active_keys_count} Keys Active)"
                overall_color = "green"
                is_active = True

            active_acc = self._accounts[self._active_index] if 0 <= self._active_index < len(self._accounts) else None
            active_rpm_used = sum(1 for t in active_acc.request_timestamps_min if t >= now - 60) if active_acc else 0
            active_rpd_used = active_acc.request_count_today if active_acc else 0
            rpd_rem = 0 if self._pool_cutoff_active else max(0, pool_rpd_limit - pool_rpd_used)

            return {
                "active": is_active,
                "status": overall_status,
                "status_label": overall_label,
                "status_color": overall_color,
                "local_date": today_str,
                "pt_cycle_date": today_str,
                "quota_cycle_window": "Pacific Time (Resets 12:00 AM PT / 4:00 PM MYT)",
                "model": getattr(self, "_primary_model", target_model),
                "models": list(getattr(self, "_parallel_models", PARALLEL_MODELS) or PARALLEL_MODELS),
                "available_models": list(PARALLEL_MODELS),
                "active_parallel_models": list(getattr(self, "_parallel_models", PARALLEL_MODELS) or PARALLEL_MODELS),
                "active_account_index": self._active_index,
                "active_account_label": active_acc.label if active_acc else "None",
                "keys_count": total_keys_count,
                "key_count": total_keys_count,
                "active_keys_count": active_keys_count,
                "fleet_endpoints_count": len(fleet_endpoints),
                "active_endpoints_count": active_endpoints_count,
                "tokens_budget_per_request": tokens_budget,
                "fleet_summary": {
                    "keys_count": total_keys_count,
                    "active_keys_count": active_keys_count,
                    "models_per_key": models_count,
                    "total_parallel_endpoints": total_endpoints,
                    "active_parallel_endpoints": active_endpoints_count,
                    "fleet_rpd_limit": pool_rpd_limit,
                    "fleet_rpm_limit": pool_rpm_limit,
                    "fleet_tpm_limit": pool_tpm_limit,
                    "raw_rpd_capacity": raw_rpd_capacity,
                    "raw_rpm_capacity": raw_rpm_capacity,
                    "tokens_per_request_budget": tokens_budget,
                },
                "endpoints": fleet_endpoints,
                "parallel_slots": fleet_endpoints,
                "rpm_limit": pool_rpm_limit,
                "rpm_used": pool_rpm_used,
                "rpm_remaining": max(0, pool_rpm_limit - pool_rpm_used),
                "rpd_limit": pool_rpd_limit,
                "rpd_used": pool_rpd_used,
                "rpd_remaining": rpd_rem,
                "percent_rpd_remaining": 0.0 if self._pool_cutoff_active else round((max(0, pool_rpd_limit - pool_rpd_used) / max(pool_rpd_limit, 1)) * 100, 1),
                "tpm_limit": pool_tpm_limit,
                "prompt_guard_limit": self._max_prompt_tokens,
                "pool_rpd_limit": pool_rpd_limit,
                "pool_rpd_used": pool_rpd_used,
                "pool_rpd_remaining": rpd_rem,
                "pool_rpm_limit": pool_rpm_limit,
                "pool_rpm_used": pool_rpm_used,
                "pool_cutoff_active": self._pool_cutoff_active,
                "rpm_per_key": self._max_rpm_per_key,
                "rpd_per_key": self._max_rpd_per_key,
                "tpm_per_key": self._max_tpm_per_key,
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

    def get_health(self) -> dict[str, Any]:
        """Return comprehensive health and quota metrics for the Gemini key pool."""
        return self.get_quota_stats()

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


def get_historical_analytics(db: Any, time_range: str = "today") -> dict[str, Any]:
    """Aggregate historical Gemini call metrics matching Google AI Studio rate limit dashboard."""
    from datetime import datetime, timedelta, timezone
    from collections import defaultdict
    from sqlalchemy import select, func
    from app.models.tables import GeminiApiCallLog
    from app.extraction.pacer_sentinel import SAFE_RPM_CEILING, SAFE_TPM_CEILING, SAFE_RPD_CEILING

    now = datetime.now(timezone.utc)
    if time_range == "today":
        today_str = get_current_pt_cycle_date()
        base_filter = GeminiApiCallLog.local_date == today_str
    elif time_range == "last-1-day":
        cutoff = now - timedelta(days=1)
        base_filter = GeminiApiCallLog.created_at >= cutoff
    elif time_range == "last-7-days":
        cutoff = now - timedelta(days=7)
        base_filter = GeminiApiCallLog.created_at >= cutoff
    elif time_range == "last-28-days":
        cutoff = now - timedelta(days=28)
        base_filter = GeminiApiCallLog.created_at >= cutoff
    else:
        today_str = get_current_pt_cycle_date()
        base_filter = GeminiApiCallLog.local_date == today_str

    # 1. Overall totals via single aggregation query
    summary_stmt = select(
        func.count(GeminiApiCallLog.id),
        func.coalesce(func.sum(GeminiApiCallLog.total_tokens), 0),
    ).where(base_filter)
    summary_res = db.execute(summary_stmt).first()
    total_calls = int(summary_res[0]) if summary_res and summary_res[0] is not None else 0
    total_tokens = int(summary_res[1]) if summary_res and summary_res[1] is not None else 0

    if total_calls == 0:
        return {
            "time_range": time_range,
            "summary": {
                "total_calls": 0,
                "total_tokens": 0,
                "models_active": 0,
            },
            "table": [],
        }

    # 2. Group totals per (account_id, model)
    group_stmt = (
        select(
            GeminiApiCallLog.account_id,
            GeminiApiCallLog.model,
            func.count(GeminiApiCallLog.id).label("call_count"),
            func.coalesce(func.sum(GeminiApiCallLog.total_tokens), 0).label("group_tokens"),
            func.max(GeminiApiCallLog.api_key_masked).label("masked_key"),
        )
        .where(base_filter)
        .group_by(GeminiApiCallLog.account_id, GeminiApiCallLog.model)
    )
    group_rows = db.execute(group_stmt).all()

    # 3. Peak RPM/TPM via database minute-bucket grouping (zero RAM scans, zero O(N^2) loops)
    is_sqlite = False
    try:
        bind = getattr(db, "bind", None)
        if bind is None and hasattr(db, "get_bind"):
            bind = db.get_bind()
        if bind and getattr(bind.dialect, "name", "") == "sqlite":
            is_sqlite = True
    except Exception:
        pass

    if is_sqlite:
        minute_bucket = func.strftime("%Y-%m-%d %H:%M", GeminiApiCallLog.created_at)
    else:
        minute_bucket = func.to_char(GeminiApiCallLog.created_at, "YYYY-MM-DD HH24:MI")

    minute_stmt = (
        select(
            GeminiApiCallLog.account_id,
            GeminiApiCallLog.model,
            func.count(GeminiApiCallLog.id).label("minute_calls"),
            func.coalesce(func.sum(GeminiApiCallLog.total_tokens), 0).label("minute_tokens"),
        )
        .where(base_filter)
        .group_by(GeminiApiCallLog.account_id, GeminiApiCallLog.model, minute_bucket)
    )
    minute_rows = db.execute(minute_stmt).all()

    peak_metrics: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"rpm": 0, "tpm": 0})
    for row in minute_rows:
        key = (str(row[0]), str(row[1]))
        calls = int(row[2] or 0)
        tokens = int(row[3] or 0)
        if calls > peak_metrics[key]["rpm"]:
            peak_metrics[key]["rpm"] = calls
        if tokens > peak_metrics[key]["tpm"]:
            peak_metrics[key]["tpm"] = tokens

    table_rows: list[dict[str, Any]] = []
    for row in group_rows:
        acc_id = str(row[0])
        model_name = str(row[1])
        call_count = int(row[2] or 0)
        group_tokens = int(row[3] or 0)
        masked_key = str(row[4] or "")

        key = (acc_id, model_name)
        peak_rpm = peak_metrics[key]["rpm"]
        peak_tpm = peak_metrics[key]["tpm"]

        table_rows.append({
            "account_id": acc_id,
            "masked_key": masked_key,
            "model": model_name,
            "category": "Text-out models",
            "call_count": call_count,
            "total_tokens": group_tokens,
            "peak_rpm": peak_rpm,
            "rpm_limit": SAFE_RPM_CEILING,
            "peak_tpm": peak_tpm,
            "tpm_limit": SAFE_TPM_CEILING,
            "rpd_limit": SAFE_RPD_CEILING,
            "status": "Healthy",
        })

    return {
        "time_range": time_range,
        "summary": {
            "total_calls": total_calls,
            "total_tokens": total_tokens,
            "models_active": len(table_rows),
        },
        "table": table_rows,
    }


def probe_google_live_model_catalog(key: str) -> tuple[bool, list[str], str | None]:
    """Lightweight GET /v1beta/models probe to verify model presence without token cost."""
    import urllib.request
    import json

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "risklocker-quota-radar/2.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            model_names = [m.get("name", "").replace("models/", "") for m in data.get("models", [])]
            return True, model_names, None
    except Exception as exc:
        return False, [], str(exc)


def get_ai_quota_radar_snapshot(*, probe_live: bool = False, db: Any = None) -> dict[str, Any]:
    """Generate comprehensive snapshot of live Gemini key pool, parallel models, and quotas."""
    import json
    from datetime import datetime, timezone
    from pathlib import Path
    from app.extraction.pacer_sentinel import SAFE_RPD_CEILING

    pool = get_key_pool()
    if db is not None:
        pool.sync_accounts(db=db)
    else:
        from app.db.session import SessionLocal
        with SessionLocal() as session:
            pool.sync_accounts(db=session)

    if probe_live:
        pool.probe(force=True)

    stats = pool.get_quota_stats()
    accounts = stats.get("accounts", [])
    endpoints = stats.get("endpoints", [])
    today_str = get_current_pt_cycle_date()

    report: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "local_date": today_str,
        "overall_status": stats.get("status_label", "Unknown"),
        "active_model": stats.get("model", "gemini-3.1-flash-lite"),
        "parallel_models": list(stats.get("parallel_models", PARALLEL_MODELS)),
        "key_count": len(accounts),
        "total_endpoints": len(endpoints),
        "total_rpd_used": stats.get("rpd_used", 0),
        "total_rpd_limit": stats.get("rpd_limit", len(accounts) * len(PARALLEL_MODELS) * SAFE_RPD_CEILING),
        "accounts": accounts,
        "endpoints": endpoints,
        "google_catalog_verified": False,
        "alerts": [],
    }

    # Verify live Google catalog
    primary_keys = pool.get_all_keys()
    if primary_keys:
        ok, available_models, err = probe_google_live_model_catalog(primary_keys[0])
        if ok:
            report["google_catalog_verified"] = True
            for expected_model in PARALLEL_MODELS:
                is_present = any(expected_model in m for m in available_models)
                if not is_present:
                    report["alerts"].append(
                        f"[CRITICAL MODEL SHIFT] Google AI Studio does NOT list '{expected_model}' in live catalog! Possible upstream retirement!"
                    )
        else:
            report["alerts"].append(
                f"[LIVE PROBE WARNING] Failed to reach Google live models endpoint: {err}"
            )
    else:
        report["alerts"].append(
            "[CRITICAL] Zero Gemini API keys configured! System fail-closed blocks unverified uploads."
        )

    # Check for quota warnings
    for acc in accounts:
        used = acc.get("rpd_used", 0)
        limit = acc.get("rpd_limit", SAFE_RPD_CEILING * len(PARALLEL_MODELS))
        pct = (used / limit * 100) if limit > 0 else 0
        if pct >= 90:
            report["alerts"].append(
                f"[CRITICAL] Account {acc.get('label')} has reached {used}/{limit} RPD ({pct:.1f}%). Near suspension threshold!"
            )
        elif pct >= 75:
            report["alerts"].append(
                f"[WARNING] Account {acc.get('label')} usage at {used}/{limit} RPD ({pct:.1f}%)."
            )

        if acc.get("status") in {"denied", "rate_limited", "cooling"}:
            report["alerts"].append(
                f"[ALERT] Account {acc.get('label')} status is '{acc.get('status_label')}' (Error: {acc.get('last_error')})"
            )

    try:
        root_dir = Path(__file__).resolve().parent.parent.parent.parent
        memory_dir = root_dir / ".agents" / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        report_file = memory_dir / "ai-radar-latest.json"
        report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    except Exception:
        pass

    return report


def get_fleet_timeline_data(db: Any) -> dict[str, Any]:
    """Compile visual timeline and calendar analytics for Google AI Studio quota management."""
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select, func, desc, case
    from app.models.tables import GeminiApiCallLog

    now_utc = datetime.now(timezone.utc)
    now_pt = now_utc.astimezone(PT_TZ)
    current_pt_date = now_pt.strftime("%Y-%m-%d")

    # Calculate exact next midnight in Pacific Time
    next_midnight_pt = (now_pt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    seconds_until_reset = max(0, int((next_midnight_pt - now_pt).total_seconds()))
    hours = seconds_until_reset // 3600
    minutes = (seconds_until_reset % 3600) // 60
    next_reset_myt = next_midnight_pt.astimezone(LOCAL_TZ)
    reset_time_str = next_reset_myt.strftime("%I:%M %p")
    cycle_reset_display = f"Resets at {reset_time_str} MYT (in {hours}h {minutes}m)"

    current_cycle = {
        "pt_date": current_pt_date,
        "local_now_myt": now_utc.astimezone(LOCAL_TZ).strftime("%Y-%m-%d %I:%M:%S %p"),
        "next_reset_pt": next_midnight_pt.isoformat(),
        "next_reset_myt": next_reset_myt.isoformat(),
        "seconds_until_reset": seconds_until_reset,
        "cycle_reset_display": cycle_reset_display,
    }

    # 1. Recent raw timeline calls (up to 100)
    logs_stmt = (
        select(GeminiApiCallLog)
        .order_by(desc(GeminiApiCallLog.created_at))
        .limit(100)
    )
    raw_logs = db.execute(logs_stmt).scalars().all()

    timeline = []
    for log in raw_logs:
        slot_lower = (log.endpoint_slot or "").lower()
        purpose = "Quotation Extraction"
        if "probe" in slot_lower:
            purpose = "Model Health Probe"
        elif "grounding" in slot_lower:
            purpose = "Vehicle Grounding Search"
        elif "spillover" in slot_lower:
            purpose = "Quotation Extraction (Fallback)"
        elif log.error_message and "copilot" in log.error_message.lower():
            purpose = "Copilot Assistant"

        created_myt = log.created_at.astimezone(LOCAL_TZ) if log.created_at.tzinfo else log.created_at.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ)
        timeline.append(
            {
                "id": str(log.id),
                "timestamp": created_myt.strftime("%Y-%m-%d %H:%M:%S"),
                "iso_timestamp": log.created_at.isoformat() if log.created_at else None,
                "account_id": log.account_id,
                "api_key_masked": log.api_key_masked or "AIza••••••••",
                "model": log.model,
                "endpoint_slot": log.endpoint_slot,
                "purpose": purpose,
                "status_code": log.status_code,
                "is_success": log.is_success,
                "prompt_tokens": log.prompt_tokens,
                "candidate_tokens": log.candidate_tokens,
                "total_tokens": log.total_tokens,
                "latency_ms": log.latency_ms,
                "error_message": log.error_message,
                "local_date": log.local_date,
            }
        )

    # 2. Minute-level buckets for the past 60 minutes (dedicated query, not capped at 100 rows)
    minute_map: dict[str, dict[str, int]] = {}
    for i in range(59, -1, -1):
        m_time = (now_utc - timedelta(minutes=i)).astimezone(LOCAL_TZ)
        m_key = m_time.strftime("%H:%M")
        minute_map[m_key] = {
            "calls": 0,
            "errors": 0,
            "total_tokens": 0,
            "prompt_tokens": 0,
            "candidate_tokens": 0,
        }

    cutoff_60m = now_utc - timedelta(minutes=60)
    bucket_stmt = (
        select(GeminiApiCallLog)
        .where(GeminiApiCallLog.created_at >= cutoff_60m)
        .order_by(GeminiApiCallLog.created_at.asc())
    )
    bucket_logs = db.execute(bucket_stmt).scalars().all()
    minute_summary = {"calls": 0, "errors": 0, "tokens": 0}
    for log in bucket_logs:
        if not log.created_at:
            continue
        log_myt = (
            log.created_at.astimezone(LOCAL_TZ)
            if log.created_at.tzinfo
            else log.created_at.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ)
        )
        m_key = log_myt.strftime("%H:%M")
        if m_key in minute_map:
            minute_map[m_key]["calls"] += 1
            if not log.is_success:
                minute_map[m_key]["errors"] += 1
            minute_map[m_key]["total_tokens"] += log.total_tokens or 0
            minute_map[m_key]["prompt_tokens"] += log.prompt_tokens or 0
            minute_map[m_key]["candidate_tokens"] += log.candidate_tokens or 0
        minute_summary["calls"] += 1
        if not log.is_success:
            minute_summary["errors"] += 1
        minute_summary["tokens"] += log.total_tokens or 0

    minute_buckets = [
        {"minute": k, **v} for k, v in minute_map.items()
    ]

    # 3. Daily history breakdown by PT cycle date (past 14 cycles)
    daily_stmt = (
        select(
            GeminiApiCallLog.local_date,
            func.count(GeminiApiCallLog.id).label("calls"),
            func.coalesce(func.sum(GeminiApiCallLog.total_tokens), 0).label("tokens"),
            func.sum(case((GeminiApiCallLog.is_success == False, 1), else_=0)).label("errors"),
        )
        .group_by(GeminiApiCallLog.local_date)
        .order_by(desc(GeminiApiCallLog.local_date))
        .limit(14)
    )
    daily_rows = db.execute(daily_stmt).fetchall()
    daily_history = [
        {
            "date": str(r[0]),
            "calls": int(r[1]),
            "tokens": int(r[2]),
            "errors": int(r[3] or 0),
        }
        for r in daily_rows
    ]

    return {
        "current_cycle": current_cycle,
        "timeline": timeline,
        "minute_buckets": minute_buckets,
        "minute_summary": minute_summary,
        "daily_history": daily_history,
    }

