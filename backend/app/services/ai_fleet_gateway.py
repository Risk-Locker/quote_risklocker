"""Unified 2D Gemini Fleet Gateway (`Keys × Models`) with Postgres-backed Lane Locking & Event Telemetry."""

from __future__ import annotations

import collections
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
import logging
import os
import sys
import threading
import time
from typing import Any, Callable, Sequence

import httpx
from sqlalchemy import delete, desc, func, select

from app.core.config import get_settings, resolve_active_gemini_model
from app.core.errors import AIExtractionUnavailableException
from app.extraction.model_discovery_service import ALLOWED_PRODUCTION_MODELS, SAFE_RPD_CEILING, SAFE_RPM_CEILING, SAFE_TPM_CEILING
from app.models.tables import AIFleetEvent, AIFleetLane, GeminiApiCallLog, Job, new_id
from app.services.gemini_account_service import (
    PARALLEL_MODELS,
    PT_TZ,
    get_current_pt_cycle_date,
    get_key_pool,
    persist_call_log,
)

logger = logging.getLogger(__name__)

STALE_IN_FLIGHT_SECONDS = 120.0
EVENT_RETENTION_DAYS = 7


@dataclass(frozen=True)
class ModelQuotaConfig:
    model: str
    rpm_limit: int = SAFE_RPM_CEILING
    tpm_limit: int = SAFE_TPM_CEILING
    rpd_limit: int = SAFE_RPD_CEILING
    min_key_spacing_sec: float = 1.8


MODEL_QUOTA_CONFIGS: dict[str, ModelQuotaConfig] = {
    "gemini-3.1-flash-lite": ModelQuotaConfig(model="gemini-3.1-flash-lite"),
    "gemini-3.5-flash-lite": ModelQuotaConfig(model="gemini-3.5-flash-lite"),
}


class QuotaExhaustedError(AIExtractionUnavailableException):
    """Raised when Gemini lanes are temporarily saturated or exhausted for the PT daily cycle."""

    def __init__(
        self,
        reason: str,
        *,
        is_daily_exhausted: bool,
        wait_seconds: float,
        resume_at_utc: datetime | None = None,
        status_code: int = 429,
    ) -> None:
        super().__init__(reason=reason, status_code=status_code, detail=reason)
        self.is_daily_exhausted = is_daily_exhausted
        self.wait_seconds = wait_seconds
        self.resume_at_utc = resume_at_utc


def compute_next_pt_midnight_utc(now_utc: datetime | None = None) -> datetime:
    """Return exact next 00:00:10 America/Los_Angeles converted to UTC."""
    ref = now_utc or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    now_pt = ref.astimezone(PT_TZ)
    next_midnight_pt = (now_pt + timedelta(days=1)).replace(hour=0, minute=0, second=10, microsecond=0)
    return next_midnight_pt.astimezone(timezone.utc)


DEFAULT_COPILOT_QUOTA_POLICY: dict[str, Any] = {
    "enabled": True,
    "shared_copilot_rpd_pct": 20,
    "shared_interactive_reserve_pct": 10,
    "staff_daily_turns": 40,
    "staff_daily_tokens": 80_000,
    "admin_daily_turns": 150,
    "admin_daily_tokens": 250_000,
    "max_tool_hops": 4,
    "max_input_tokens_per_turn": 12_000,
}


def normalize_copilot_quota_policy(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Clamp and normalize copilot quota governance policy with safe defaults."""
    src = raw if isinstance(raw, dict) else {}
    return {
        "enabled": bool(src.get("enabled", True)),
        "shared_copilot_rpd_pct": max(5, min(80, int(src.get("shared_copilot_rpd_pct", 20) or 20))),
        "shared_interactive_reserve_pct": max(0, min(40, int(src.get("shared_interactive_reserve_pct", 10) or 10))),
        "staff_daily_turns": max(5, min(500, int(src.get("staff_daily_turns", 40) or 40))),
        "staff_daily_tokens": max(5_000, min(2_000_000, int(src.get("staff_daily_tokens", 80_000) or 80_000))),
        "admin_daily_turns": max(10, min(1_000, int(src.get("admin_daily_turns", 150) or 150))),
        "admin_daily_tokens": max(10_000, min(5_000_000, int(src.get("admin_daily_tokens", 250_000) or 250_000))),
        "max_tool_hops": max(1, min(8, int(src.get("max_tool_hops", 4) or 4))),
        "max_input_tokens_per_turn": max(2_000, min(40_000, int(src.get("max_input_tokens_per_turn", 12_000) or 12_000))),
    }


def get_copilot_quota_policy(db: Any = None) -> dict[str, Any]:
    """Read copilot quota governance policy from AppSetting or return safe defaults."""
    from app.models.tables import AppSetting

    if db is not None:
        try:
            row = db.get(AppSetting, "copilot_quota_policy")
            if row and isinstance(row.value, dict):
                return normalize_copilot_quota_policy(row.value)
        except Exception:
            pass
        return dict(DEFAULT_COPILOT_QUOTA_POLICY)
    if _is_test_runtime():
        return dict(DEFAULT_COPILOT_QUOTA_POLICY)
    try:
        from app.db.session import SessionLocal

        with SessionLocal() as sess:
            row = sess.get(AppSetting, "copilot_quota_policy")
            if row and isinstance(row.value, dict):
                return normalize_copilot_quota_policy(row.value)
    except Exception:
        pass
    return dict(DEFAULT_COPILOT_QUOTA_POLICY)


@dataclass
class LaneReservation:
    reservation_id: str
    lane_id: str
    account_id: str
    account_label: str
    masked_key: str
    api_key: str
    model: str
    estimated_tokens: int
    purpose: str = "extraction"
    actor_user_id: str | None = None


@dataclass
class _MemoryLaneState:
    lane_id: str
    account_id: str
    api_key_masked: str | None
    model: str
    rpm_limit: int
    tpm_limit: int
    rpd_limit: int
    in_flight_count: int = 0
    in_flight_meta: dict[str, Any] = field(default_factory=dict)
    recent_calls_json: list[float] = field(default_factory=list)
    recent_tokens_json: list[list[Any]] = field(default_factory=list)
    rpd_used: int = 0
    copilot_rpd_used: int = 0
    pt_cycle_date: str = field(default_factory=get_current_pt_cycle_date)
    last_dispatched_at: float = 0.0
    cooling_until: float | None = None
    global_pause_until: float | None = None
    interactive_yield_until: float | None = None
    status: str = "ready"
    last_error: str | None = None
    last_latency_ms: int = 0


def estimate_payload_tokens(payload: dict[str, Any]) -> int:
    """Rough safe pre-flight token estimator for JSON + inline PDF/PNG payloads."""
    try:
        serialized = json.dumps(payload, default=str)
        # Base64 PDF/PNG bytes overstate text tokens (~0.25 tok/char); 258 tok per media part + 0.25/text char
        parts_tokens = 0
        text_chars = 0
        for msg in payload.get("contents") or []:
            for part in msg.get("parts") or []:
                if "inline_data" in part:
                    data_len = len(str((part["inline_data"] or {}).get("data") or ""))
                    # Approx 1 page per 120KB b64 (~1800 tok) or minimum 258 tok per image
                    parts_tokens += max(258, min(16_000, data_len // 75))
                elif "text" in part:
                    text_chars += len(str(part["text"] or ""))
        sys_parts = ((payload.get("system_instruction") or {}).get("parts") or [])
        for sp in sys_parts:
            text_chars += len(str(sp.get("text") or ""))
        est = parts_tokens + max(64, int(text_chars * 0.28))
        return max(256, min(est, max(len(serialized) // 4, 256)))
    except Exception:
        return 4_000


def _is_test_runtime() -> bool:
    return os.getenv("APP_ENV") == "test" or "pytest" in sys.modules


def _is_daily_quota_message(msg: str) -> bool:
    low = (msg or "").lower()
    return any(
        tok in low
        for tok in (
            "per day",
            "requests per day",
            "daily",
            "rpd",
            "quota exceeded for metric: generativelanguage.googleapis.com/generate_requests_per_model_per_day",
        )
    )


class GeminiFleetGateway:
    """Single-authority 2D (`Account × Model`) Gemini scheduler, pacer, and telemetry ledger."""

    def __init__(self, *, session_factory: Any = None, force_memory: bool = False) -> None:
        self._lock = threading.RLock()
        self._session_factory = session_factory
        self._force_memory = force_memory
        self._rr_seq: int = 0
        self._recent_latencies: collections.deque[float] = collections.deque(maxlen=20)
        self._mem_lanes: dict[str, _MemoryLaneState] = {}
        self._mem_events: collections.deque[dict[str, Any]] = collections.deque(maxlen=500)
        self._last_prune_ts: float = 0.0
        self._last_pace_event_ts: float = 0.0
        self._copilot_policy_override: dict[str, Any] | None = None

    def _use_db(self, db: Any = None) -> bool:
        if db is not None:
            return True
        if self._force_memory:
            return False
        if self._session_factory is not None:
            return True
        return not _is_test_runtime()

    def _open_db(self) -> Any:
        if self._session_factory is not None:
            return self._session_factory()
        from app.db.session import SessionLocal

        return SessionLocal()

    def _get_model_config(self, model: str) -> ModelQuotaConfig:
        cfg = MODEL_QUOTA_CONFIGS.get(model)
        if cfg is not None:
            return cfg
        return ModelQuotaConfig(model=model)

    def _active_accounts_and_models(self, db: Any = None) -> tuple[list[Any], list[str], dict[str, Any]]:
        pool = get_key_pool()
        # Only pass db to sync_accounts when explicitly provided or in DB runtime
        if db is not None:
            pool.sync_accounts(db=db)
        else:
            pool.sync_accounts()

        accounts = pool.get_accounts()
        active_models = [
            m
            for m in (getattr(pool, "_parallel_models", PARALLEL_MODELS) or PARALLEL_MODELS)
            if m in ALLOWED_PRODUCTION_MODELS
        ]
        if not active_models:
            active_models = list(PARALLEL_MODELS)

        acc_by_id = {acc.id: acc for acc in accounts}
        return accounts, active_models, acc_by_id

    def _prune_stale_inflight(self, in_flight_meta: dict[str, Any], now: float) -> tuple[dict[str, Any], int]:
        cleaned: dict[str, Any] = {}
        for rid, meta in (in_flight_meta or {}).items():
            if not isinstance(meta, dict):
                continue
            started_ts = float(meta.get("ts") or 0.0)
            if now - started_ts <= STALE_IN_FLIGHT_SECONDS:
                cleaned[rid] = meta
        return cleaned, len(cleaned)

    def _prune_60s_windows(
        self,
        recent_calls: list[Any],
        recent_tokens: list[Any],
        now: float,
    ) -> tuple[list[float], list[list[Any]]]:
        cutoff = now - 60.0
        calls = [float(t) for t in (recent_calls or []) if float(t) >= cutoff]
        tokens: list[list[Any]] = []
        for entry in (recent_tokens or []):
            if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                ts = float(entry[0])
                tok = int(entry[1] or 0)
                if ts >= cutoff:
                    tokens.append([ts, tok])
        return calls, tokens

    def _sync_db_lanes_locked(self, db: Any, accounts: list[Any], active_models: list[str], now: float) -> list[AIFleetLane]:
        today_pt = get_current_pt_cycle_date()
        desired_ids: list[str] = []
        lane_specs: dict[str, tuple[Any, str, ModelQuotaConfig]] = {}
        settings = get_settings()

        for acc in accounts:
            for model in active_models:
                lid = f"{acc.id}::{model}"
                desired_ids.append(lid)
                cfg = self._get_model_config(model)
                effective_cfg = ModelQuotaConfig(
                    model=model,
                    rpm_limit=min(cfg.rpm_limit, getattr(settings, "gemini_max_rpm_per_key", SAFE_RPM_CEILING)),
                    tpm_limit=min(cfg.tpm_limit, getattr(settings, "gemini_max_tpm_per_key", SAFE_TPM_CEILING)),
                    rpd_limit=min(cfg.rpd_limit, getattr(settings, "gemini_max_rpd_per_key", SAFE_RPD_CEILING)),
                    min_key_spacing_sec=cfg.min_key_spacing_sec,
                )
                lane_specs[lid] = (acc, model, effective_cfg)

        if not desired_ids:
            return []

        bind = getattr(db, "bind", None) or (db.get_bind() if hasattr(db, "get_bind") else None)
        dialect_name = getattr(getattr(bind, "dialect", None), "name", "")
        stmt = select(AIFleetLane).where(AIFleetLane.lane_id.in_(desired_ids))
        if dialect_name == "postgresql":
            stmt = stmt.with_for_update()
        existing_rows = {row.lane_id: row for row in db.scalars(stmt).all()}

        missing_ids = [lid for lid in desired_ids if lid not in existing_rows]
        slot_counts: dict[str, int] = {}
        if missing_ids and not _is_test_runtime():
            try:
                rows = db.execute(
                    select(GeminiApiCallLog.endpoint_slot, func.count(GeminiApiCallLog.id))
                    .where(
                        GeminiApiCallLog.local_date == today_pt,
                        GeminiApiCallLog.endpoint_slot.in_(missing_ids),
                    )
                    .group_by(GeminiApiCallLog.endpoint_slot)
                ).all()
                slot_counts = {str(r[0]): int(r[1] or 0) for r in rows}
            except Exception:
                slot_counts = {}

        lanes_out: list[AIFleetLane] = []
        for lid in desired_ids:
            acc, model, cfg = lane_specs[lid]
            lane = existing_rows.get(lid)
            if lane is None:
                lane = AIFleetLane(
                    lane_id=lid,
                    account_id=acc.id,
                    api_key_masked=acc.masked_key,
                    model=model,
                    rpm_limit=cfg.rpm_limit,
                    tpm_limit=cfg.tpm_limit,
                    rpd_limit=cfg.rpd_limit,
                    in_flight_count=0,
                    in_flight_meta={},
                    recent_calls_json=[],
                    recent_tokens_json=[],
                    rpd_used=slot_counts.get(lid, 0),
                    pt_cycle_date=today_pt,
                    last_dispatched_at=0.0,
                    cooling_until=None,
                    global_pause_until=None,
                    status="paused" if acc.is_paused else "ready",
                    last_error=None,
                    last_latency_ms=0,
                )
                db.add(lane)
            else:
                lane.api_key_masked = acc.masked_key
                lane.rpm_limit = cfg.rpm_limit
                lane.tpm_limit = cfg.tpm_limit
                lane.rpd_limit = cfg.rpd_limit
                if lane.pt_cycle_date != today_pt:
                    lane.pt_cycle_date = today_pt
                    lane.rpd_used = 0
                    lane.copilot_rpd_used = 0
                    lane.cooling_until = None
                    lane.interactive_yield_until = None
                    if lane.status in ("exhausted_rpd", "cooling_429", "cooling_err"):
                        lane.status = "ready"
                        lane.last_error = None
                cleaned_meta, active_inf = self._prune_stale_inflight(lane.in_flight_meta, now)
                lane.in_flight_meta = cleaned_meta
                lane.in_flight_count = active_inf
                calls, tokens = self._prune_60s_windows(lane.recent_calls_json, lane.recent_tokens_json, now)
                lane.recent_calls_json = calls
                lane.recent_tokens_json = tokens
                if lane.cooling_until and now >= lane.cooling_until:
                    lane.cooling_until = None
                    if lane.status in ("cooling_429", "cooling_err", "quarantined_auth"):
                        lane.status = "ready"
                if lane.global_pause_until and now >= lane.global_pause_until:
                    lane.global_pause_until = None
                if acc.is_paused:
                    lane.status = "paused"
                elif acc.status in ("denied", "invalid_key"):
                    lane.status = "quarantined_auth"
                elif lane.rpd_used >= lane.rpd_limit:
                    lane.status = "exhausted_rpd"
                elif lane.status == "paused" and not acc.is_paused:
                    lane.status = "ready"
            lanes_out.append(lane)
        db.flush()
        return lanes_out

    def _sync_mem_lanes_locked(self, accounts: list[Any], active_models: list[str], now: float) -> list[_MemoryLaneState]:
        today_pt = get_current_pt_cycle_date()
        settings = get_settings()
        lanes_out: list[_MemoryLaneState] = []
        for acc in accounts:
            for model in active_models:
                lid = f"{acc.id}::{model}"
                cfg = self._get_model_config(model)
                rpm_lim = min(cfg.rpm_limit, getattr(settings, "gemini_max_rpm_per_key", SAFE_RPM_CEILING))
                tpm_lim = min(cfg.tpm_limit, getattr(settings, "gemini_max_tpm_per_key", SAFE_TPM_CEILING))
                rpd_lim = min(cfg.rpd_limit, getattr(settings, "gemini_max_rpd_per_key", SAFE_RPD_CEILING))
                lane = self._mem_lanes.get(lid)
                if lane is None:
                    lane = _MemoryLaneState(
                        lane_id=lid,
                        account_id=acc.id,
                        api_key_masked=acc.masked_key,
                        model=model,
                        rpm_limit=rpm_lim,
                        tpm_limit=tpm_lim,
                        rpd_limit=rpd_lim,
                        pt_cycle_date=today_pt,
                        status="paused" if acc.is_paused else "ready",
                    )
                    self._mem_lanes[lid] = lane
                else:
                    lane.api_key_masked = acc.masked_key
                    lane.rpm_limit = rpm_lim
                    lane.tpm_limit = tpm_lim
                    lane.rpd_limit = rpd_lim
                    if lane.pt_cycle_date != today_pt:
                        lane.pt_cycle_date = today_pt
                        lane.rpd_used = 0
                        lane.copilot_rpd_used = 0
                        lane.cooling_until = None
                        lane.interactive_yield_until = None
                        if lane.status in ("exhausted_rpd", "cooling_429", "cooling_err"):
                            lane.status = "ready"
                            lane.last_error = None
                    cleaned_meta, active_inf = self._prune_stale_inflight(lane.in_flight_meta, now)
                    lane.in_flight_meta = cleaned_meta
                    lane.in_flight_count = active_inf
                    calls, tokens = self._prune_60s_windows(lane.recent_calls_json, lane.recent_tokens_json, now)
                    lane.recent_calls_json = calls
                    lane.recent_tokens_json = tokens
                    if lane.cooling_until and now >= lane.cooling_until:
                        lane.cooling_until = None
                        if lane.status in ("cooling_429", "cooling_err", "quarantined_auth"):
                            lane.status = "ready"
                    if lane.global_pause_until and now >= lane.global_pause_until:
                        lane.global_pause_until = None
                    if acc.is_paused:
                        lane.status = "paused"
                    elif acc.status in ("denied", "invalid_key"):
                        lane.status = "quarantined_auth"
                    elif lane.rpd_used >= lane.rpd_limit:
                        lane.status = "exhausted_rpd"
                    elif lane.status == "paused" and not acc.is_paused:
                        lane.status = "ready"
                lanes_out.append(lane)
        return lanes_out

    def _adaptive_cadence_seconds(self, *, priority: int, queued_count: int) -> float:
        avg_lat = (sum(self._recent_latencies) / len(self._recent_latencies)) if self._recent_latencies else 0.0
        if avg_lat > 4.0:
            return 6.0
        if priority <= 20:
            return 0.8
        if queued_count > 20:
            return 3.5
        return 2.0

    def _emit_event_on_session(
        self,
        db: Any,
        *,
        level: str,
        event_type: str,
        message: str,
        lane_id: str | None = None,
        account_id: str | None = None,
        model: str | None = None,
        job_id: str | None = None,
        upload_run_id: str | None = None,
        filename: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        ev = AIFleetEvent(
            id=new_id(),
            level=level[:20],
            event_type=event_type[:50],
            lane_id=lane_id,
            account_id=account_id,
            model=model,
            job_id=job_id,
            upload_run_id=upload_run_id,
            filename=filename[:255] if filename else None,
            message=message,
            detail=detail or {},
        )
        db.add(ev)
        now = time.time()
        if now - self._last_prune_ts > 3600.0:
            self._last_prune_ts = now
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(days=EVENT_RETENTION_DAYS)
                db.execute(delete(AIFleetEvent).where(AIFleetEvent.created_at < cutoff))
            except Exception:
                pass

    def record_fleet_event(
        self,
        *,
        level: str,
        event_type: str,
        message: str,
        lane_id: str | None = None,
        account_id: str | None = None,
        model: str | None = None,
        job_id: str | None = None,
        upload_run_id: str | None = None,
        filename: str | None = None,
        detail: dict[str, Any] | None = None,
        db: Any = None,
    ) -> None:
        if self._use_db(db):
            owns_db = db is None
            sess = db if db is not None else self._open_db()
            try:
                self._emit_event_on_session(
                    sess,
                    level=level,
                    event_type=event_type,
                    message=message,
                    lane_id=lane_id,
                    account_id=account_id,
                    model=model,
                    job_id=job_id,
                    upload_run_id=upload_run_id,
                    filename=filename,
                    detail=detail,
                )
                if owns_db:
                    sess.commit()
            except Exception as exc:
                logger.debug("Could not persist fleet event: %s", exc)
                if owns_db:
                    sess.rollback()
            finally:
                if owns_db:
                    sess.close()
        else:
            with self._lock:
                self._mem_events.appendleft(
                    {
                        "id": new_id(),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "level": level,
                        "event_type": event_type,
                        "lane_id": lane_id,
                        "account_id": account_id,
                        "model": model,
                        "job_id": job_id,
                        "upload_run_id": upload_run_id,
                        "filename": filename,
                        "message": message,
                        "detail": detail or {},
                    }
                )

    def _select_lane_from_list(
        self,
        lanes: Sequence[Any],
        acc_by_id: dict[str, Any],
        *,
        now: float,
        estimated_tokens: int,
        requested_model: str | None,
        exclude_lane_ids: set[str] | None,
        batch_item_index: int | None,
        priority: int,
        queued_count: int,
        purpose: str = "extraction",
        policy: dict[str, Any] | None = None,
    ) -> tuple[Any | None, float, bool]:
        """Pure scheduler over locked lane objects. Returns (chosen_lane, wait_seconds, is_daily_exhausted)."""
        is_copilot = (purpose or "extraction").startswith("copilot")
        eff_policy = normalize_copilot_quota_policy(policy if policy is not None else self._copilot_policy_override)
        if is_copilot and not eff_policy["enabled"]:
            return None, float("inf"), True

        candidates = list(lanes)
        if requested_model is not None:
            candidates = [l for l in candidates if l.model == requested_model]
        if exclude_lane_ids:
            filtered = [l for l in candidates if l.lane_id not in exclude_lane_ids]
            candidates = filtered

        # Workload scope filtering + shared RPD ring-fencing across N accounts
        shared_total_rpd = 0
        shared_used_total = 0
        shared_copilot_used = 0
        has_dedicated_copilot = False
        for l in lanes:
            acc = acc_by_id.get(l.account_id)
            if not acc or acc.is_paused or acc.status in ("denied", "invalid_key"):
                continue
            scope = getattr(acc, "workload_scope", "all") or "all"
            if scope == "copilot_only":
                has_dedicated_copilot = True
            elif scope == "all":
                shared_total_rpd += int(l.rpd_limit or SAFE_RPD_CEILING)
                shared_used_total += int(l.rpd_used or 0) + int(l.in_flight_count or 0)
                shared_copilot_used += int(getattr(l, "copilot_rpd_used", 0) or 0)

        shared_copilot_cap = max(1, int(shared_total_rpd * eff_policy["shared_copilot_rpd_pct"] / 100)) if shared_total_rpd > 0 else 0
        shared_reserve_floor = int(shared_total_rpd * eff_policy["shared_interactive_reserve_pct"] / 100) if (shared_total_rpd > 0 and not has_dedicated_copilot) else 0
        shared_remaining_rpd = max(0, shared_total_rpd - shared_used_total)

        eligible_account_lanes: list[Any] = []
        for l in candidates:
            acc = acc_by_id.get(l.account_id)
            if not acc or acc.is_paused or acc.status in ("denied", "invalid_key"):
                continue
            if l.status == "quarantined_auth" and l.cooling_until and now < l.cooling_until:
                continue
            scope = getattr(acc, "workload_scope", "all") or "all"
            if is_copilot and scope == "extraction_only":
                continue
            if not is_copilot and scope == "copilot_only":
                continue
            eligible_account_lanes.append(l)

        if not eligible_account_lanes:
            return None, float("inf"), True

        rpd_available: list[Any] = []
        for l in eligible_account_lanes:
            if (int(l.rpd_used or 0) + int(l.in_flight_count or 0)) >= int(l.rpd_limit or SAFE_RPD_CEILING):
                continue
            acc = acc_by_id.get(l.account_id)
            scope = getattr(acc, "workload_scope", "all") if acc else "all"
            if is_copilot and scope == "all" and shared_copilot_used >= shared_copilot_cap:
                continue
            if (not is_copilot) and priority >= 80 and scope == "all" and shared_reserve_floor > 0 and shared_remaining_rpd <= shared_reserve_floor:
                continue
            rpd_available.append(l)

        if not rpd_available:
            return None, float("inf"), True

        # Order round-robin across RPD-capable lanes, preferring dedicated lanes first
        n = len(rpd_available)
        if batch_item_index is not None:
            start_idx = abs(int(batch_item_index)) % n
        else:
            start_idx = self._rr_seq % n
            self._rr_seq += 1
        rr_ordered = rpd_available[start_idx:] + rpd_available[:start_idx]
        if is_copilot:
            ordered = [l for l in rr_ordered if (getattr(acc_by_id.get(l.account_id), "workload_scope", "all") == "copilot_only")] + [
                l for l in rr_ordered if (getattr(acc_by_id.get(l.account_id), "workload_scope", "all") != "copilot_only")
            ]
        else:
            ordered = [l for l in rr_ordered if (getattr(acc_by_id.get(l.account_id), "workload_scope", "all") == "extraction_only")] + [
                l for l in rr_ordered if (getattr(acc_by_id.get(l.account_id), "workload_scope", "all") != "extraction_only")
            ]

        # Compute max last_dispatched_at per account and per workload scope
        account_last_dispatch: dict[str, float] = {}
        scope_last_dispatch: dict[str, float] = {}
        global_pause_until = 0.0
        shared_interactive_yield = 0.0
        for l in lanes:
            ld = float(l.last_dispatched_at or 0.0)
            l_acc = acc_by_id.get(l.account_id)
            l_scope = getattr(l_acc, "workload_scope", "all") if l_acc else "all"
            if ld > scope_last_dispatch.get(l_scope, 0.0):
                scope_last_dispatch[l_scope] = ld
            prev_acc = account_last_dispatch.get(l.account_id, 0.0)
            if ld > prev_acc:
                account_last_dispatch[l.account_id] = ld
            gp = float(l.global_pause_until or 0.0)
            if gp > global_pause_until:
                global_pause_until = gp
            iy = float(getattr(l, "interactive_yield_until", 0.0) or 0.0)
            if iy > shared_interactive_yield:
                shared_interactive_yield = iy

        cadence_sec = self._adaptive_cadence_seconds(priority=priority, queued_count=queued_count)
        effective_cadence = min(cadence_sec, 3.5 if queued_count > 20 else cadence_sec)
        if len(rpd_available) >= 2 and cadence_sec <= 3.5:
            effective_cadence = max(0.35, cadence_sec / max(1, min(len(rpd_available), 4)))

        min_wait = float("inf")
        for l in ordered:
            cfg = self._get_model_config(l.model)
            acc = acc_by_id.get(l.account_id)
            scope = getattr(acc, "workload_scope", "all") if acc else "all"
            wait_reasons: list[float] = []

            if global_pause_until > now:
                wait_reasons.append(global_pause_until - now)

            if l.cooling_until and now < l.cooling_until:
                wait_reasons.append(l.cooling_until - now)

            # Bulk background batches yield politely on shared lanes when interactive Copilot is active
            if (not is_copilot) and priority >= 80 and scope == "all" and shared_interactive_yield > now:
                wait_reasons.append(min(2.5, shared_interactive_yield - now))

            cadence_ready_at = scope_last_dispatch.get(scope, 0.0) + effective_cadence
            if cadence_ready_at > now:
                wait_reasons.append(cadence_ready_at - now)

            # STRICT 1.8s same-key gap across all sibling models sharing API key (zero cheating!)
            acc_last = account_last_dispatch.get(l.account_id, 0.0)
            key_ready_at = acc_last + cfg.min_key_spacing_sec
            if key_ready_at > now:
                wait_reasons.append(key_ready_at - now)

            # 60s RPM sliding window (includes in_flight_count)
            recent_calls = [float(t) for t in (l.recent_calls_json or [])]
            active_rpm = len(recent_calls) + int(l.in_flight_count or 0)
            if active_rpm >= int(l.rpm_limit or SAFE_RPM_CEILING):
                if recent_calls:
                    wait_reasons.append(max(0.25, (min(recent_calls) + 60.05) - now))
                else:
                    wait_reasons.append(2.0)

            # 60s TPM sliding window
            recent_tok_sum = sum(int(e[1] or 0) for e in (l.recent_tokens_json or []) if isinstance(e, (list, tuple)) and len(e) >= 2)
            if recent_tok_sum + estimated_tokens > int(l.tpm_limit or SAFE_TPM_CEILING):
                if l.recent_tokens_json:
                    oldest_tok_ts = min(float(e[0]) for e in l.recent_tokens_json if isinstance(e, (list, tuple)) and len(e) >= 1)
                    wait_reasons.append(max(0.25, (oldest_tok_ts + 60.05) - now))
                else:
                    wait_reasons.append(2.0)

            if not wait_reasons:
                return l, 0.0, False

            lane_wait = max(wait_reasons)
            if lane_wait < min_wait:
                min_wait = lane_wait

        if min_wait == float("inf"):
            min_wait = 2.0
        return None, max(0.1, min_wait), False

    def reserve_lane(
        self,
        *,
        estimated_tokens: int = 8_000,
        requested_model: str | None = None,
        exclude_lane_ids: set[str] | None = None,
        batch_item_index: int | None = None,
        purpose: str = "extraction",
        filename: str | None = None,
        job_id: str | None = None,
        upload_run_id: str | None = None,
        actor_user_id: str | None = None,
        priority: int = 100,
        db: Any = None,
    ) -> tuple[LaneReservation | None, float, bool]:
        """Atomically reserve a 2D lane slot. Never sleeps inside DB transaction or lock."""
        if requested_model is not None and requested_model not in ALLOWED_PRODUCTION_MODELS:
            raise ValueError(f"Forbidden model tier: {requested_model}. Allowed models: {sorted(ALLOWED_PRODUCTION_MODELS)}")

        now = time.time()
        is_copilot = (purpose or "extraction").startswith("copilot")
        if self._use_db(db):
            owns_db = db is None
            sess = db if db is not None else self._open_db()
            try:
                with self._lock:
                    accounts, active_models, acc_by_id = self._active_accounts_and_models(sess)
                    lanes = self._sync_db_lanes_locked(sess, accounts, active_models, now)
                    policy = get_copilot_quota_policy(sess)
                    queued_count = 1
                    try:
                        queued_count = int(
                            sess.scalar(
                                select(func.count(Job.id)).where(
                                    Job.job_type == "extract_pdf",
                                    Job.state.in_(["queued", "processing"]),
                                )
                            )
                            or 1
                        )
                    except Exception:
                        queued_count = 1

                    chosen, wait_sec, is_daily = self._select_lane_from_list(
                        lanes,
                        acc_by_id,
                        now=now,
                        estimated_tokens=estimated_tokens,
                        requested_model=requested_model,
                        exclude_lane_ids=exclude_lane_ids,
                        batch_item_index=batch_item_index,
                        priority=priority,
                        queued_count=queued_count,
                        purpose=purpose,
                        policy=policy,
                    )
                    if is_copilot and chosen is None and not is_daily:
                        # Ask shared bulk workers to politely yield 2.5s so interactive chat gets priority next tick
                        for fl in lanes:
                            if getattr(acc_by_id.get(fl.account_id), "workload_scope", "all") == "all":
                                fl.interactive_yield_until = max(float(fl.interactive_yield_until or 0.0), now + 2.5)
                    if chosen is None:
                        if owns_db:
                            sess.commit()
                        return None, wait_sec, is_daily

                    acc = acc_by_id[chosen.account_id]
                    res_id = new_id()
                    meta = dict(chosen.in_flight_meta or {})
                    meta[res_id] = {
                        "ts": now,
                        "purpose": purpose,
                        "filename": filename,
                        "job_id": job_id,
                        "upload_run_id": upload_run_id,
                        "actor_user_id": actor_user_id,
                        "estimated_tokens": estimated_tokens,
                    }
                    chosen.in_flight_meta = meta
                    chosen.in_flight_count = len(meta)
                    chosen.last_dispatched_at = now
                    if is_copilot:
                        chosen.interactive_yield_until = now + 2.5
                    chosen.status = "in_flight"
                    from sqlalchemy.orm.attributes import flag_modified

                    flag_modified(chosen, "in_flight_meta")
                    self._emit_event_on_session(
                        sess,
                        level="info",
                        event_type="assigned",
                        lane_id=chosen.lane_id,
                        account_id=chosen.account_id,
                        model=chosen.model,
                        job_id=job_id,
                        upload_run_id=upload_run_id,
                        filename=filename,
                        message=f"Assigned {filename or purpose} to {chosen.lane_id} (~{estimated_tokens:,} tok)",
                        detail={"reservation_id": res_id, "purpose": purpose, "estimated_tokens": estimated_tokens, "actor_user_id": actor_user_id},
                    )
                    if owns_db:
                        sess.commit()
                    return (
                        LaneReservation(
                            reservation_id=res_id,
                            lane_id=chosen.lane_id,
                            account_id=acc.id,
                            account_label=acc.label,
                            masked_key=acc.masked_key,
                            api_key=acc.key,
                            model=chosen.model,
                            estimated_tokens=estimated_tokens,
                            purpose=purpose,
                            actor_user_id=actor_user_id,
                        ),
                        0.0,
                        False,
                    )
            except Exception:
                if owns_db:
                    sess.rollback()
                raise
            finally:
                if owns_db:
                    sess.close()
        else:
            with self._lock:
                accounts, active_models, acc_by_id = self._active_accounts_and_models(None)
                lanes = self._sync_mem_lanes_locked(accounts, active_models, now)
                chosen, wait_sec, is_daily = self._select_lane_from_list(
                    lanes,
                    acc_by_id,
                    now=now,
                    estimated_tokens=estimated_tokens,
                    requested_model=requested_model,
                    exclude_lane_ids=exclude_lane_ids,
                    batch_item_index=batch_item_index,
                    priority=priority,
                    queued_count=1,
                    purpose=purpose,
                )
                if is_copilot and chosen is None and not is_daily:
                    for fl in lanes:
                        if getattr(acc_by_id.get(fl.account_id), "workload_scope", "all") == "all":
                            fl.interactive_yield_until = max(float(fl.interactive_yield_until or 0.0), now + 2.5)
                if chosen is None:
                    return None, wait_sec, is_daily
                acc = acc_by_id[chosen.account_id]
                res_id = new_id()
                chosen.in_flight_meta[res_id] = {
                    "ts": now,
                    "purpose": purpose,
                    "filename": filename,
                    "job_id": job_id,
                    "upload_run_id": upload_run_id,
                    "actor_user_id": actor_user_id,
                    "estimated_tokens": estimated_tokens,
                }
                chosen.in_flight_count = len(chosen.in_flight_meta)
                chosen.last_dispatched_at = now
                if is_copilot:
                    chosen.interactive_yield_until = now + 2.5
                chosen.status = "in_flight"
                self._mem_events.appendleft(
                    {
                        "id": new_id(),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "level": "info",
                        "event_type": "assigned",
                        "lane_id": chosen.lane_id,
                        "account_id": chosen.account_id,
                        "model": chosen.model,
                        "job_id": job_id,
                        "upload_run_id": upload_run_id,
                        "filename": filename,
                        "message": f"Assigned {filename or purpose} to {chosen.lane_id}",
                        "detail": {"reservation_id": res_id, "purpose": purpose, "actor_user_id": actor_user_id},
                    }
                )
                return (
                    LaneReservation(
                        reservation_id=res_id,
                        lane_id=chosen.lane_id,
                        account_id=acc.id,
                        account_label=acc.label,
                        masked_key=acc.masked_key,
                        api_key=acc.key,
                        model=chosen.model,
                        estimated_tokens=estimated_tokens,
                        purpose=purpose,
                        actor_user_id=actor_user_id,
                    ),
                    0.0,
                    False,
                )

    def commit_lane(
        self,
        reservation: LaneReservation,
        *,
        prompt_tokens: int = 0,
        candidate_tokens: int = 0,
        total_tokens: int = 0,
        latency_ms: int = 0,
        purpose: str = "extraction",
        filename: str | None = None,
        job_id: str | None = None,
        upload_run_id: str | None = None,
        actor_user_id: str | None = None,
        endpoint_slot_override: str | None = None,
        db: Any = None,
    ) -> None:
        now = time.time()
        eff_purpose = purpose or reservation.purpose or "extraction"
        eff_actor = actor_user_id or reservation.actor_user_id
        is_copilot = eff_purpose.startswith("copilot")
        tok_count = max(0, total_tokens if total_tokens > 0 else (prompt_tokens + candidate_tokens))
        if latency_ms > 0:
            self._recent_latencies.append(latency_ms / 1000.0)

        pool = get_key_pool()
        pool.record_success(prompt_tokens=prompt_tokens, candidate_tokens=candidate_tokens, total_tokens=tok_count, key=reservation.api_key)

        if self._use_db(db):
            owns_db = db is None
            sess = db if db is not None else self._open_db()
            try:
                with self._lock:
                    lane = sess.get(AIFleetLane, reservation.lane_id)
                    if lane is not None:
                        meta = dict(lane.in_flight_meta or {})
                        meta.pop(reservation.reservation_id, None)
                        lane.in_flight_meta = meta
                        lane.in_flight_count = len(meta)
                        calls, tokens = self._prune_60s_windows(lane.recent_calls_json, lane.recent_tokens_json, now)
                        calls.append(now)
                        tokens.append([now, tok_count])
                        lane.recent_calls_json = calls
                        lane.recent_tokens_json = tokens
                        lane.rpd_used = int(lane.rpd_used or 0) + 1
                        if is_copilot:
                            lane.copilot_rpd_used = int(getattr(lane, "copilot_rpd_used", 0) or 0) + 1
                        lane.cooling_until = None
                        lane.last_error = None
                        lane.last_latency_ms = int(latency_ms or 0)
                        lane.status = "exhausted_rpd" if lane.rpd_used >= lane.rpd_limit else ("in_flight" if lane.in_flight_count > 0 else "ready")
                        from sqlalchemy.orm.attributes import flag_modified

                        flag_modified(lane, "in_flight_meta")
                        flag_modified(lane, "recent_calls_json")
                        flag_modified(lane, "recent_tokens_json")

                    self._emit_event_on_session(
                        sess,
                        level="info",
                        event_type="success",
                        lane_id=reservation.lane_id,
                        account_id=reservation.account_id,
                        model=reservation.model,
                        job_id=job_id,
                        upload_run_id=upload_run_id,
                        filename=filename,
                        message=f"{reservation.lane_id} finished {filename or eff_purpose} in {latency_ms}ms ({tok_count:,} tok)",
                        detail={"latency_ms": latency_ms, "total_tokens": tok_count, "purpose": eff_purpose},
                    )
                    if owns_db:
                        sess.commit()
            except Exception as exc:
                logger.debug("commit_lane DB update note: %s", exc)
                if owns_db:
                    sess.rollback()
            finally:
                if owns_db:
                    sess.close()
        else:
            with self._lock:
                lane = self._mem_lanes.get(reservation.lane_id)
                if lane is not None:
                    lane.in_flight_meta.pop(reservation.reservation_id, None)
                    lane.in_flight_count = len(lane.in_flight_meta)
                    calls, tokens = self._prune_60s_windows(lane.recent_calls_json, lane.recent_tokens_json, now)
                    calls.append(now)
                    tokens.append([now, tok_count])
                    lane.recent_calls_json = calls
                    lane.recent_tokens_json = tokens
                    lane.rpd_used += 1
                    if is_copilot:
                        lane.copilot_rpd_used += 1
                    lane.cooling_until = None
                    lane.last_error = None
                    lane.last_latency_ms = int(latency_ms or 0)
                    lane.status = "exhausted_rpd" if lane.rpd_used >= lane.rpd_limit else ("in_flight" if lane.in_flight_count > 0 else "ready")
                self._mem_events.appendleft(
                    {
                        "id": new_id(),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "level": "info",
                        "event_type": "success",
                        "lane_id": reservation.lane_id,
                        "account_id": reservation.account_id,
                        "model": reservation.model,
                        "job_id": job_id,
                        "upload_run_id": upload_run_id,
                        "filename": filename,
                        "message": f"{reservation.lane_id} finished {filename or eff_purpose} in {latency_ms}ms",
                        "detail": {"latency_ms": latency_ms, "total_tokens": tok_count, "purpose": eff_purpose},
                    }
                )

        persist_call_log(
            account_id=reservation.account_id,
            api_key_masked=reservation.masked_key,
            model=reservation.model,
            endpoint_slot=endpoint_slot_override or reservation.lane_id,
            status_code=200,
            is_success=True,
            prompt_tokens=prompt_tokens,
            candidate_tokens=candidate_tokens,
            total_tokens=tok_count,
            latency_ms=latency_ms,
            purpose=eff_purpose,
            actor_user_id=eff_actor,
        )

    def release_lane(
        self,
        reservation: LaneReservation,
        *,
        status_code: int,
        error_message: str,
        latency_ms: int = 0,
        purpose: str = "extraction",
        filename: str | None = None,
        job_id: str | None = None,
        upload_run_id: str | None = None,
        actor_user_id: str | None = None,
        cool_slot: bool = True,
        endpoint_slot_override: str | None = None,
        db: Any = None,
    ) -> None:
        now = time.time()
        eff_purpose = purpose or reservation.purpose or "extraction"
        eff_actor = actor_user_id or reservation.actor_user_id
        clean_msg = str(error_message or f"HTTP {status_code}")
        is_auth_err = status_code in (401, 403) or "unauthenticated" in clean_msg.lower() or "permission_denied" in clean_msg.lower()
        is_429 = status_code == 429
        is_daily = is_429 and _is_daily_quota_message(clean_msg)

        pool = get_key_pool()
        if cool_slot or not is_429:
            pool.record_failure(status_code, clean_msg, key=reservation.api_key)

        ev_level = "error" if is_auth_err else ("warn" if is_429 else "warn")
        ev_type = "quarantine_auth" if is_auth_err else ("cooldown_429" if is_429 else "cooldown_err")

        if self._use_db(db):
            owns_db = db is None
            sess = db if db is not None else self._open_db()
            try:
                with self._lock:
                    lane = sess.get(AIFleetLane, reservation.lane_id)
                    if lane is not None:
                        meta = dict(lane.in_flight_meta or {})
                        meta.pop(reservation.reservation_id, None)
                        lane.in_flight_meta = meta
                        lane.in_flight_count = len(meta)
                        lane.last_error = clean_msg[:500]
                        lane.last_latency_ms = int(latency_ms or 0)
                        from sqlalchemy.orm.attributes import flag_modified

                        flag_modified(lane, "in_flight_meta")

                        if is_auth_err:
                            # Quarantine ALL sibling model lanes sharing the same API key for 1 hour
                            sibling_lanes = sess.scalars(
                                select(AIFleetLane).where(AIFleetLane.account_id == reservation.account_id)
                            ).all()
                            for sib in sibling_lanes:
                                sib.status = "quarantined_auth"
                                sib.cooling_until = now + 3600.0
                                sib.last_error = clean_msg[:500]
                        elif is_429 and cool_slot:
                            calls, _ = self._prune_60s_windows(lane.recent_calls_json, lane.recent_tokens_json, now)
                            calls.append(now)
                            lane.recent_calls_json = calls
                            flag_modified(lane, "recent_calls_json")
                            if is_daily or int(lane.rpd_used or 0) >= int(lane.rpd_limit or SAFE_RPD_CEILING):
                                lane.status = "exhausted_rpd"
                                lane.rpd_used = max(int(lane.rpd_used or 0), int(lane.rpd_limit or SAFE_RPD_CEILING))
                            else:
                                lane.status = "cooling_429"
                                lane.cooling_until = now + 65.0
                                # Apply 6.0s fleet-wide breathing pause so concurrent workers don't pile on
                                all_lanes = sess.scalars(select(AIFleetLane)).all()
                                for fl in all_lanes:
                                    fl.global_pause_until = max(float(fl.global_pause_until or 0.0), now + 6.0)
                        elif cool_slot:
                            lane.status = "cooling_err"
                            lane.cooling_until = now + 15.0
                        else:
                            lane.status = "in_flight" if lane.in_flight_count > 0 else "ready"

                    self._emit_event_on_session(
                        sess,
                        level=ev_level,
                        event_type=ev_type,
                        lane_id=reservation.lane_id,
                        account_id=reservation.account_id,
                        model=reservation.model,
                        job_id=job_id,
                        upload_run_id=upload_run_id,
                        filename=filename,
                        message=f"{reservation.lane_id} HTTP {status_code} ({ev_type}): {clean_msg[:180]}",
                        detail={"status_code": status_code, "purpose": purpose, "is_daily": is_daily},
                    )
                    if owns_db:
                        sess.commit()
            except Exception as exc:
                logger.debug("release_lane DB update note: %s", exc)
                if owns_db:
                    sess.rollback()
            finally:
                if owns_db:
                    sess.close()
        else:
            with self._lock:
                lane = self._mem_lanes.get(reservation.lane_id)
                if lane is not None:
                    lane.in_flight_meta.pop(reservation.reservation_id, None)
                    lane.in_flight_count = len(lane.in_flight_meta)
                    lane.last_error = clean_msg[:500]
                    lane.last_latency_ms = int(latency_ms or 0)
                    if is_auth_err:
                        for sib in self._mem_lanes.values():
                            if sib.account_id == reservation.account_id:
                                sib.status = "quarantined_auth"
                                sib.cooling_until = now + 3600.0
                                sib.last_error = clean_msg[:500]
                    elif is_429 and cool_slot:
                        calls, _ = self._prune_60s_windows(lane.recent_calls_json, lane.recent_tokens_json, now)
                        calls.append(now)
                        lane.recent_calls_json = calls
                        if is_daily or lane.rpd_used >= lane.rpd_limit:
                            lane.status = "exhausted_rpd"
                            lane.rpd_used = max(lane.rpd_used, lane.rpd_limit)
                        else:
                            lane.status = "cooling_429"
                            lane.cooling_until = now + 65.0
                            for fl in self._mem_lanes.values():
                                fl.global_pause_until = max(float(fl.global_pause_until or 0.0), now + 6.0)
                    elif cool_slot:
                        lane.status = "cooling_err"
                        lane.cooling_until = now + 15.0
                    else:
                        lane.status = "in_flight" if lane.in_flight_count > 0 else "ready"
                self._mem_events.appendleft(
                    {
                        "id": new_id(),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "level": ev_level,
                        "event_type": ev_type,
                        "lane_id": reservation.lane_id,
                        "account_id": reservation.account_id,
                        "model": reservation.model,
                        "job_id": job_id,
                        "upload_run_id": upload_run_id,
                        "filename": filename,
                        "message": f"{reservation.lane_id} HTTP {status_code} ({ev_type}): {clean_msg[:180]}",
                        "detail": {"status_code": status_code, "is_daily": is_daily},
                    }
                )

        persist_call_log(
            account_id=reservation.account_id,
            api_key_masked=reservation.masked_key,
            model=reservation.model,
            endpoint_slot=endpoint_slot_override or reservation.lane_id,
            status_code=status_code,
            is_success=False,
            latency_ms=latency_ms,
            error_message=clean_msg,
            purpose=eff_purpose,
            actor_user_id=eff_actor,
        )

    def execute_gemini_request(
        self,
        *,
        payload: dict[str, Any] | None = None,
        payload_builder: Callable[[str], dict[str, Any]] | None = None,
        estimated_tokens: int | None = None,
        requested_model: str | None = None,
        exclude_slot_ids: set[str] | None = None,
        batch_item_index: int | None = None,
        timeout_seconds: float = 35.0,
        max_attempts: int = 4,
        max_wait_seconds: float = 90.0,
        purpose: str = "extraction",
        filename: str | None = None,
        job_id: str | None = None,
        upload_run_id: str | None = None,
        actor_user_id: str | None = None,
        priority: int = 100,
        telemetry_log: list[dict[str, Any]] | None = None,
        allow_quota_raise: bool = True,
        cool_slot_on_429: bool = True,
        endpoint_slot_override_prefix: str | None = None,
        parse_fn: Callable[[dict[str, Any]], Any] | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        http_post_fn: Callable[[str, dict[str, Any], float], httpx.Response] | None = None,
    ) -> Any:
        """Execute a Gemini generateContent call through the 2D Fleet Gateway with pacing & spillover."""
        if payload is None and payload_builder is None:
            raise ValueError("Either payload or payload_builder is required.")

        base_payload = payload if payload is not None else payload_builder(resolve_active_gemini_model(requested_model))  # type: ignore[misc]
        est_tok = estimated_tokens if estimated_tokens is not None else estimate_payload_tokens(base_payload)
        excluded = set(exclude_slot_ids or ())
        deadline = time.monotonic() + max(0.0, max_wait_seconds)
        effective_timeout = max(timeout_seconds, 10.0)

        attempts_used = 0
        while attempts_used < max_attempts:
            res: LaneReservation | None = None
            wait_sec = 0.0
            is_daily = False

            while True:
                res, wait_sec, is_daily = self.reserve_lane(
                    estimated_tokens=est_tok,
                    requested_model=requested_model,
                    exclude_lane_ids=excluded,
                    batch_item_index=batch_item_index if attempts_used == 0 else None,
                    purpose=purpose,
                    filename=filename,
                    job_id=job_id,
                    upload_run_id=upload_run_id,
                    actor_user_id=actor_user_id,
                    priority=priority,
                )
                if res is not None:
                    break
                if is_daily:
                    resume_at = compute_next_pt_midnight_utc()
                    msg = "All active Gemini lanes reached daily RPD quota; waiting until Pacific Time midnight reset."
                    if allow_quota_raise:
                        raise QuotaExhaustedError(
                            msg,
                            is_daily_exhausted=True,
                            wait_seconds=float("inf"),
                            resume_at_utc=resume_at,
                        )
                    return None

                remaining = deadline - time.monotonic()
                if remaining <= 0.1 or wait_sec > remaining:
                    msg = f"Gemini lanes temporarily busy (~{wait_sec:.1f}s wait exceeds remaining budget {max(0.0, remaining):.1f}s)."
                    if allow_quota_raise:
                        raise QuotaExhaustedError(
                            msg,
                            is_daily_exhausted=False,
                            wait_seconds=wait_sec,
                            resume_at_utc=datetime.now(timezone.utc) + timedelta(seconds=min(wait_sec, 120.0)),
                        )
                    return None

                sleep_dur = min(wait_sec + 0.05, remaining)
                now_ts = time.time()
                if sleep_dur >= 1.5 and (now_ts - self._last_pace_event_ts) >= 5.0:
                    self._last_pace_event_ts = now_ts
                    self.record_fleet_event(
                        level="info",
                        event_type="pacing_wait",
                        job_id=job_id,
                        upload_run_id=upload_run_id,
                        filename=filename,
                        message=f"Pacing wait {sleep_dur:.1f}s before dispatching {filename or purpose}",
                        detail={"wait_seconds": round(sleep_dur, 2), "purpose": purpose},
                    )
                sleep_fn(sleep_dur)

            attempts_used += 1
            req_payload = payload if payload is not None else payload_builder(res.model)  # type: ignore[misc]
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{res.model}:generateContent?key={res.api_key}"
            slot_override = f"{endpoint_slot_override_prefix}::{res.lane_id}" if endpoint_slot_override_prefix else None

            start_t = time.perf_counter()
            try:
                if http_post_fn is not None:
                    response = http_post_fn(url, req_payload, effective_timeout)
                else:
                    with httpx.Client(timeout=effective_timeout, http2=False) as client:
                        response = client.post(url, json=req_payload)
                latency_ms = int((time.perf_counter() - start_t) * 1000)

                if response.status_code == 200:
                    data = response.json()
                    parsed = parse_fn(data) if parse_fn is not None else data
                    if parsed is None:
                        self.release_lane(
                            res,
                            status_code=500,
                            error_message="Empty or unparseable Gemini response",
                            latency_ms=latency_ms,
                            purpose=purpose,
                            filename=filename,
                            job_id=job_id,
                            upload_run_id=upload_run_id,
                            cool_slot=False,
                            endpoint_slot_override=slot_override,
                        )
                        excluded.add(res.lane_id)
                        continue
                    usage = data.get("usageMetadata", {}) if isinstance(data, dict) else {}
                    p_tok = int(usage.get("promptTokenCount", 0) or 0)
                    c_tok = int(usage.get("candidatesTokenCount", 0) or 0)
                    t_tok = int(usage.get("totalTokenCount", p_tok + c_tok) or 0)
                    self.commit_lane(
                        res,
                        prompt_tokens=p_tok,
                        candidate_tokens=c_tok,
                        total_tokens=t_tok,
                        latency_ms=latency_ms,
                        purpose=purpose,
                        filename=filename,
                        job_id=job_id,
                        upload_run_id=upload_run_id,
                        endpoint_slot_override=slot_override,
                    )
                    if telemetry_log is not None:
                        telemetry_log.append(
                            {
                                "stage": purpose,
                                "model": res.model,
                                "slot_id": res.lane_id,
                                "status_code": 200,
                                "is_success": True,
                                "prompt_tokens": p_tok,
                                "candidate_tokens": c_tok,
                                "total_tokens": t_tok,
                                "latency_ms": latency_ms,
                            }
                        )
                    return parsed

                err_msg = ""
                try:
                    err_msg = response.json().get("error", {}).get("message", "")
                except Exception:
                    err_msg = response.text[:250]
                if not err_msg:
                    err_msg = f"HTTP {response.status_code}"

                should_cool = cool_slot_on_429 if response.status_code == 429 else True
                self.release_lane(
                    res,
                    status_code=response.status_code,
                    error_message=err_msg,
                    latency_ms=latency_ms,
                    purpose=purpose,
                    filename=filename,
                    job_id=job_id,
                    upload_run_id=upload_run_id,
                    cool_slot=should_cool,
                    endpoint_slot_override=slot_override,
                )
                if telemetry_log is not None:
                    telemetry_log.append(
                        {
                            "stage": purpose,
                            "model": res.model,
                            "slot_id": res.lane_id,
                            "status_code": response.status_code,
                            "is_success": False,
                            "latency_ms": latency_ms,
                            "error": err_msg[:200],
                        }
                    )
                excluded.add(res.lane_id)
                # Clear model lock if requested model failed so spillover can use sibling model
                if requested_model is not None and response.status_code in (404, 429):
                    requested_model = None
            except (httpx.TimeoutException, TimeoutError) as exc:
                latency_ms = int((time.perf_counter() - start_t) * 1000)
                self.release_lane(
                    res,
                    status_code=504,
                    error_message=f"Timeout after {effective_timeout}s: {exc}",
                    latency_ms=latency_ms,
                    purpose=purpose,
                    filename=filename,
                    job_id=job_id,
                    upload_run_id=upload_run_id,
                    cool_slot=True,
                    endpoint_slot_override=slot_override,
                )
                if telemetry_log is not None:
                    telemetry_log.append(
                        {
                            "stage": purpose,
                            "model": res.model,
                            "slot_id": res.lane_id,
                            "status_code": 504,
                            "is_success": False,
                            "latency_ms": latency_ms,
                            "error": str(exc)[:200],
                        }
                    )
                excluded.add(res.lane_id)
            except Exception as exc:
                latency_ms = int((time.perf_counter() - start_t) * 1000)
                self.release_lane(
                    res,
                    status_code=500,
                    error_message=str(exc)[:250],
                    latency_ms=latency_ms,
                    purpose=purpose,
                    filename=filename,
                    job_id=job_id,
                    upload_run_id=upload_run_id,
                    cool_slot=True,
                    endpoint_slot_override=slot_override,
                )
                if telemetry_log is not None:
                    telemetry_log.append(
                        {
                            "stage": purpose,
                            "model": res.model,
                            "slot_id": res.lane_id,
                            "status_code": 500,
                            "is_success": False,
                            "latency_ms": latency_ms,
                            "error": str(exc)[:200],
                        }
                    )
                excluded.add(res.lane_id)

        return None

    def get_fleet_telemetry(
        self,
        db: Any = None,
        *,
        upload_run_id: str | None = None,
        limit: int = 150,
        level: str | None = None,
    ) -> dict[str, Any]:
        """Strictly read-only live fleet telemetry (lanes, active assignments, queue ETA, and logs)."""
        now = time.time()
        now_utc = datetime.now(timezone.utc)
        next_reset_utc = compute_next_pt_midnight_utc(now_utc)
        seconds_until_reset = max(0, int((next_reset_utc - now_utc).total_seconds()))

        pool = get_key_pool()
        accounts = pool.get_accounts()
        acc_by_id = {a.id: a for a in accounts}

        lanes_data: list[dict[str, Any]] = []
        events_data: list[dict[str, Any]] = []
        queue_summary = {
            "queued": 0,
            "processing": 0,
            "paused_quota": 0,
            "paused_user": 0,
            "completed": 0,
            "failed": 0,
        }

        if db is not None:
            raw_lanes = db.scalars(select(AIFleetLane).order_by(AIFleetLane.lane_id.asc())).all()
            for lane in raw_lanes:
                acc = acc_by_id.get(lane.account_id)
                cleaned_meta, active_inf = self._prune_stale_inflight(lane.in_flight_meta, now)
                calls, tokens = self._prune_60s_windows(lane.recent_calls_json, lane.recent_tokens_json, now)
                rpm_used = len(calls) + active_inf
                tpm_used = sum(int(e[1] or 0) for e in tokens)
                cooling_rem = max(0.0, float(lane.cooling_until) - now) if lane.cooling_until and now < lane.cooling_until else 0.0
                eff_status = lane.status
                if acc and acc.is_paused:
                    eff_status = "paused"
                elif cooling_rem > 0 and eff_status == "ready":
                    eff_status = "cooling_429"
                elif cooling_rem == 0 and eff_status in ("cooling_429", "cooling_err", "quarantined_auth"):
                    eff_status = "ready"
                if active_inf > 0 and eff_status == "ready":
                    eff_status = "in_flight"

                active_files = [
                    {
                        "filename": m.get("filename"),
                        "purpose": m.get("purpose"),
                        "job_id": m.get("job_id"),
                        "upload_run_id": m.get("upload_run_id"),
                        "elapsed_sec": round(max(0.0, now - float(m.get("ts") or now)), 1),
                    }
                    for m in cleaned_meta.values()
                ]
                lanes_data.append(
                    {
                        "lane_id": lane.lane_id,
                        "account_id": lane.account_id,
                        "account_label": acc.label if acc else lane.account_id,
                        "workload_scope": getattr(acc, "workload_scope", "all") if acc else "all",
                        "api_key_masked": lane.api_key_masked,
                        "model": lane.model,
                        "status": eff_status,
                        "rpm_used": rpm_used,
                        "rpm_limit": lane.rpm_limit,
                        "tpm_used": tpm_used,
                        "tpm_limit": lane.tpm_limit,
                        "rpd_used": lane.rpd_used,
                        "copilot_rpd_used": int(getattr(lane, "copilot_rpd_used", 0) or 0),
                        "rpd_limit": lane.rpd_limit,
                        "in_flight_count": active_inf,
                        "active_assignments": active_files,
                        "cooling_remaining_seconds": round(cooling_rem, 1),
                        "last_latency_ms": lane.last_latency_ms,
                        "last_error": lane.last_error,
                    }
                )

            job_stmt = select(Job.state, func.count(Job.id)).where(Job.job_type == "extract_pdf")
            if upload_run_id:
                job_stmt = job_stmt.where(Job.upload_run_id == upload_run_id)
            for st, cnt in db.execute(job_stmt.group_by(Job.state)).all():
                if st in queue_summary:
                    queue_summary[str(st)] = int(cnt or 0)

            ev_stmt = select(AIFleetEvent).order_by(desc(AIFleetEvent.created_at))
            if upload_run_id:
                ev_stmt = ev_stmt.where(AIFleetEvent.upload_run_id == upload_run_id)
            if level and level != "all":
                ev_stmt = ev_stmt.where(AIFleetEvent.level == level)
            ev_stmt = ev_stmt.limit(max(1, min(limit, 300)))
            for ev in db.scalars(ev_stmt).all():
                events_data.append(
                    {
                        "id": ev.id,
                        "created_at": ev.created_at.isoformat() if ev.created_at else None,
                        "level": ev.level,
                        "event_type": ev.event_type,
                        "lane_id": ev.lane_id,
                        "account_id": ev.account_id,
                        "model": ev.model,
                        "job_id": ev.job_id,
                        "upload_run_id": ev.upload_run_id,
                        "filename": ev.filename,
                        "message": ev.message,
                        "detail": ev.detail or {},
                    }
                )
        else:
            with self._lock:
                for lane in self._mem_lanes.values():
                    acc = acc_by_id.get(lane.account_id)
                    cleaned_meta, active_inf = self._prune_stale_inflight(lane.in_flight_meta, now)
                    calls, tokens = self._prune_60s_windows(lane.recent_calls_json, lane.recent_tokens_json, now)
                    cooling_rem = max(0.0, float(lane.cooling_until) - now) if lane.cooling_until and now < lane.cooling_until else 0.0
                    lanes_data.append(
                        {
                            "lane_id": lane.lane_id,
                            "account_id": lane.account_id,
                            "account_label": acc.label if acc else lane.account_id,
                            "workload_scope": getattr(acc, "workload_scope", "all") if acc else "all",
                            "api_key_masked": lane.api_key_masked,
                            "model": lane.model,
                            "status": lane.status,
                            "rpm_used": len(calls) + active_inf,
                            "rpm_limit": lane.rpm_limit,
                            "tpm_used": sum(int(e[1] or 0) for e in tokens),
                            "tpm_limit": lane.tpm_limit,
                            "rpd_used": lane.rpd_used,
                            "copilot_rpd_used": lane.copilot_rpd_used,
                            "rpd_limit": lane.rpd_limit,
                            "in_flight_count": active_inf,
                            "active_assignments": list(cleaned_meta.values()),
                            "cooling_remaining_seconds": round(cooling_rem, 1),
                            "last_latency_ms": lane.last_latency_ms,
                            "last_error": lane.last_error,
                        }
                    )
                events_data = list(self._mem_events)[:limit]

        ready_lanes = [l for l in lanes_data if l["status"] in ("ready", "in_flight")]
        remaining_active = queue_summary["queued"] + queue_summary["processing"]
        cadence_mode = "Interactive (2.0s)" if remaining_active <= 20 else "Batch Calm (3.5s)"
        avg_lat = (sum(self._recent_latencies) / len(self._recent_latencies)) if self._recent_latencies else 2.5
        if avg_lat > 4.0:
            cadence_mode = "Congestion Backoff (6.0s)"

        # Wave ETA estimate: active lanes * ~8 calls/min realistic sustained throughput (Proof-First bulk ~1.2 calls/PDF)
        effective_lanes = max(1, len(ready_lanes))
        calls_per_min = effective_lanes * 8.0
        est_seconds = int((remaining_active * 1.2 / calls_per_min) * 60.0) if remaining_active > 0 else 0

        return {
            "lanes": lanes_data,
            "active_lanes_count": len(ready_lanes),
            "total_lanes_count": len(lanes_data),
            "queue_summary": queue_summary,
            "estimated_remaining_seconds": est_seconds,
            "cadence_mode": cadence_mode,
            "avg_latency_ms": int(avg_lat * 1000) if self._recent_latencies else 0,
            "next_pt_reset_utc": next_reset_utc.isoformat(),
            "seconds_until_pt_reset": seconds_until_reset,
            "events": events_data,
            "governance": self.get_copilot_governance_summary(db) if db is not None else None,
        }

    def get_copilot_governance_summary(self, db: Any) -> dict[str, Any]:
        """Compute dynamic N-key workload split, Copilot RPD ring-fence, and per-user daily usage."""
        from app.models.tables import CopilotArtifact, CopilotMessage, CopilotThread, User

        policy = get_copilot_quota_policy(db)
        pool = get_key_pool()
        pool.sync_accounts(db=db)
        accounts = [a for a in pool.get_accounts() if not a.is_paused and a.status not in ("denied", "invalid_key")]
        models_count = max(1, len(getattr(pool, "_parallel_models", PARALLEL_MODELS) or PARALLEL_MODELS))
        rpd_per_lane = int(getattr(pool, "_max_rpd_per_key", SAFE_RPD_CEILING) or SAFE_RPD_CEILING)

        shared_accounts = [a for a in accounts if (a.workload_scope or "all") == "all"]
        ded_copilot_accounts = [a for a in accounts if a.workload_scope == "copilot_only"]
        ded_extraction_accounts = [a for a in accounts if a.workload_scope == "extraction_only"]

        shared_total_rpd = len(shared_accounts) * models_count * rpd_per_lane
        dedicated_copilot_rpd = len(ded_copilot_accounts) * models_count * rpd_per_lane
        dedicated_extraction_rpd = len(ded_extraction_accounts) * models_count * rpd_per_lane
        total_fleet_rpd = shared_total_rpd + dedicated_copilot_rpd + dedicated_extraction_rpd

        shared_copilot_cap = int(shared_total_rpd * policy["shared_copilot_rpd_pct"] / 100) if shared_total_rpd > 0 else 0
        shared_reserve_rpd = (
            int(shared_total_rpd * policy["shared_interactive_reserve_pct"] / 100)
            if (shared_total_rpd > 0 and not ded_copilot_accounts)
            else 0
        )
        copilot_rpd_limit = dedicated_copilot_rpd + shared_copilot_cap
        extraction_rpd_limit = dedicated_extraction_rpd + max(0, shared_total_rpd - shared_copilot_cap)

        today_pt = get_current_pt_cycle_date()
        copilot_rpd_used = 0
        extraction_rpd_used = 0
        copilot_tokens_today = 0
        extraction_tokens_today = 0

        purpose_rows = db.execute(
            select(
                GeminiApiCallLog.purpose,
                func.count(GeminiApiCallLog.id),
                func.coalesce(func.sum(GeminiApiCallLog.total_tokens), 0),
            )
            .where(GeminiApiCallLog.local_date == today_pt)
            .group_by(GeminiApiCallLog.purpose)
        ).all()
        for purp, cnt, tok in purpose_rows:
            p_str = str(purp or "extraction")
            if p_str.startswith("copilot"):
                copilot_rpd_used += int(cnt or 0)
                copilot_tokens_today += int(tok or 0)
            else:
                extraction_rpd_used += int(cnt or 0)
                extraction_tokens_today += int(tok or 0)

        # Per-user Copilot turns, LLM calls, tokens, and Excel exports today
        call_rows = db.execute(
            select(
                GeminiApiCallLog.actor_user_id,
                func.count(GeminiApiCallLog.id),
                func.coalesce(func.sum(GeminiApiCallLog.total_tokens), 0),
            )
            .where(
                GeminiApiCallLog.local_date == today_pt,
                GeminiApiCallLog.actor_user_id.is_not(None),
                GeminiApiCallLog.purpose.like("copilot%"),
            )
            .group_by(GeminiApiCallLog.actor_user_id)
        ).all()
        user_stats_map: dict[str, dict[str, int]] = {}
        for uid, cnt, tok in call_rows:
            user_stats_map[str(uid)] = {
                "llm_calls_today": int(cnt or 0),
                "tokens_today": int(tok or 0),
                "turns_today": 0,
                "excel_exports_today": 0,
            }

        now_utc = datetime.now(timezone.utc)
        start_of_day = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        turn_rows = db.execute(
            select(CopilotThread.user_id, func.count(CopilotMessage.id))
            .join(CopilotThread, CopilotThread.id == CopilotMessage.thread_id)
            .where(CopilotMessage.role == "user", CopilotMessage.created_at >= start_of_day)
            .group_by(CopilotThread.user_id)
        ).all()
        for uid, cnt in turn_rows:
            entry = user_stats_map.setdefault(
                str(uid), {"llm_calls_today": 0, "tokens_today": 0, "turns_today": 0, "excel_exports_today": 0}
            )
            entry["turns_today"] = int(cnt or 0)

        art_rows = db.execute(
            select(CopilotArtifact.owner_id, func.count(CopilotArtifact.id))
            .where(CopilotArtifact.kind == "xlsx", CopilotArtifact.created_at >= start_of_day)
            .group_by(CopilotArtifact.owner_id)
        ).all()
        for uid, cnt in art_rows:
            entry = user_stats_map.setdefault(
                str(uid), {"llm_calls_today": 0, "tokens_today": 0, "turns_today": 0, "excel_exports_today": 0}
            )
            entry["excel_exports_today"] = int(cnt or 0)

        users_by_id: dict[str, User] = {}
        if user_stats_map:
            for u in db.scalars(select(User).where(User.id.in_(list(user_stats_map.keys())))).all():
                users_by_id[str(u.id)] = u

        per_user_today: list[dict[str, Any]] = []
        for uid, st in user_stats_map.items():
            u = users_by_id.get(uid)
            role = u.role if u else "staff"
            is_admin = role in ("super_admin", "admin", "dev")
            per_user_today.append(
                {
                    "user_id": uid,
                    "name": (u.name or u.email) if u else uid[:8],
                    "email": u.email if u else "",
                    "role": role,
                    "turns_today": st["turns_today"],
                    "llm_calls_today": st["llm_calls_today"],
                    "tokens_today": st["tokens_today"],
                    "excel_exports_today": st["excel_exports_today"],
                    "daily_turn_limit": policy["admin_daily_turns"] if is_admin else policy["staff_daily_turns"],
                    "daily_token_limit": policy["admin_daily_tokens"] if is_admin else policy["staff_daily_tokens"],
                }
            )
        per_user_today.sort(key=lambda item: (-item["tokens_today"], -item["turns_today"]))

        return {
            "policy": policy,
            "pt_cycle_date": today_pt,
            "active_keys_count": len(accounts),
            "shared_keys_count": len(shared_accounts),
            "dedicated_copilot_keys_count": len(ded_copilot_accounts),
            "dedicated_extraction_keys_count": len(ded_extraction_accounts),
            "total_fleet_rpd": total_fleet_rpd,
            "copilot_rpd_limit": copilot_rpd_limit,
            "copilot_rpd_used": copilot_rpd_used,
            "copilot_rpd_remaining": max(0, copilot_rpd_limit - copilot_rpd_used),
            "copilot_tokens_today": copilot_tokens_today,
            "extraction_rpd_limit": extraction_rpd_limit,
            "extraction_rpd_used": extraction_rpd_used,
            "extraction_tokens_today": extraction_tokens_today,
            "shared_reserve_rpd": shared_reserve_rpd,
            "per_user_today": per_user_today,
        }


_GLOBAL_GATEWAY: GeminiFleetGateway | None = None
_GATEWAY_LOCK = threading.Lock()


def get_fleet_gateway() -> GeminiFleetGateway:
    global _GLOBAL_GATEWAY
    if _GLOBAL_GATEWAY is None:
        with _GATEWAY_LOCK:
            if _GLOBAL_GATEWAY is None:
                _GLOBAL_GATEWAY = GeminiFleetGateway()
    return _GLOBAL_GATEWAY
