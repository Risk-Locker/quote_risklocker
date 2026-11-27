"""Enterprise Agentic AI Copilot Orchestrator (ReAct Loop + Function Calling + Compaction + Verified Links)."""

from __future__ import annotations

import json
import logging
import queue
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Generator
from urllib.parse import quote

from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.tables import (
    ClientRecord,
    CopilotArtifact,
    CopilotMessage,
    CopilotThread,
    CustomerAccount,
    GeminiApiCallLog,
    InsuranceCompany,
    InsuranceTenure,
    TenureComparisonEntry,
    TrackedVehicle,
    User,
    VehiclePlateHistory,
    new_id,
)
from app.services.ai_fleet_gateway import (
    QuotaExhaustedError,
    get_copilot_quota_policy,
    get_fleet_gateway,
)
from app.services.copilot_excel_service import export_rows_to_excel, export_sql_to_excel
from app.services.copilot_orchestrator import get_copilot_orchestrator
from app.services.copilot_sql_guard import SQLGuardError, execute_readonly_sql
from app.services.gemini_account_service import get_current_pt_cycle_date, get_key_pool

logger = logging.getLogger(__name__)

# Per-user active stream cancellation events (max 1 concurrent turn per user)
_STREAM_LOCK = threading.Lock()
_ACTIVE_USER_STREAMS: dict[str, threading.Event] = {}

_SCHEMA_SYSTEM_PROMPT = """You are the **RiskLocker Insurance Intelligence Copilot** — a realistic, sharp, executive-grade Malaysian motor insurance AI analyst & assistant.

You have full live awareness of the agency's entire PostgreSQL database through read-only tools.

### 1. AVAILABLE READ-ONLY SEMANTIC VIEWS (SQL)
1. `ai_v_motor_ledger`: Every active motor renewal/policy tenure.
   Columns: `tenure_id`, `tracked_vehicle_id`, `vehicle_no`, `customer_id`, `customer_name`, `car_brand`, `car_model`, `engine_cc`, `manufacture_year`, `chassis_no`, `coverage_start_date`, `coverage_end_date`, `expiry_month` (YYYY-MM), `policy_year` (int), `stage` ('Quotations','Pending','Hit','Miss', etc.), `status`, `business_type`, `winning_company`, `winning_quotation_ref`, `won_premium`, `road_tax`, `runner_fee`, `include_road_tax`, `include_runner_fee`, `ncd_percentage`, `motor_discount_pct`, `quotation_discount`, `pic_name`, `pic_type`, `agency_group`, `sub_agent_name`, `loss_reason_category`, `miss_reason`, `policy_number`, `covernote_session_id`, `is_projected`, `is_hidden`, `client_payment_received`, `agency_payment_done`, `key_in_ucd`, `print_roadtax`, `comment`, `created_at`, `updated_at`.
2. `ai_v_comparison_quotes`: Every insurer quote row inside comparison tables.
   Columns: `entry_id`, `tenure_id`, `session_id`, `vehicle_no`, `customer_name`, `car_brand`, `car_model`, `coverage_start_date`, `coverage_end_date`, `expiry_month`, `policy_year`, `tenure_stage`, `company_name`, `sum_insured`, `valuation_type`, `motor_premium`, `road_tax`, `runner_fee`, `total_payable`, `discount`, `towing_limit`, `towing_km`, `agreed_value`, `waiver_betterment`, `betterment_rate`, `betterment_display`, `excess`, `rate_percentage`, `windscreen_sum_insured`, `special_perils`, `llp`, `llop`, `llp_llop`, `personal_accident`, `rank`, `manual_rank`, `is_recommended`, `is_manual`, `notes`, `uploaded_at`.
3. `ai_v_vehicles_plates`: Vehicles, current plates & historical plates (`vehicle_plate_history`).
   Columns: `tracked_vehicle_id`, `vehicle_no`, `historical_plate_no`, `plate_effective_from`, `plate_effective_to`, `car_brand`, `car_model`, `engine_cc`, `manufacture_year`, `chassis_no`, `customer_id`, `customer_name`, `entity_type`, `is_fleet`.
4. `ai_v_clients_fleet`: Customer accounts & fleet sizes (NRIC/ID already masked as `masked_id_number`).
   Columns: `customer_id`, `canonical_name`, `entity_type`, `id_type`, `masked_id_number`, `phone`, `email`, `is_fleet`, `vehicle_count`, `tenure_count`, `active_hit_count`, `created_at`.
5. `ai_v_sessions`: Uploaded quotation/covernote sessions & drafts.
   Columns: `session_id`, `draft_id`, `tenure_id`, `tracked_vehicle_id`, `customer_id`, `document_type`, `detected_company`, `quotation_ref`, `quotation_status`, `status`, `policy_number`, `coverage_start_date`, `coverage_end_date`, `filename`, `created_at`.
6. `ai_v_insurer_catalogs`: Published insurer benefit rules & defaults.
   Columns: `company_name`, `catalog_name`, `engine_type`, `concept_key`, `concept_label`, `offering_kind`, `role`, `display_value`, `description_override`, `concept_description`.

### 2. DOMAIN RULES & BEHAVIOUR
- **100% Accuracy & Completeness**: Never print partial 10-row samples when the user asks for the full table or all items — output every row returned by the tool, or clearly refuse / export Excel if >100 rows. Never guess, fabricate, or omit rows; if any tool output was capped or truncated, explicitly state exact bounds and never present partial data as complete. Only mark a vehicle `"In Motor Renewal Ledger"` when `in_motor_ledger` is `true` (active, non-projected, non-hidden tenure).
- **Bulk plate existence checks**: Whenever the user pastes 3 or more vehicle plates to check existence, ALWAYS call `bulk_check_plates` ONCE with `use_user_message=True` so zero plates are dropped from the user's message.
- **Plate matching in SQL**: Always normalize spaces/case with `REPLACE(UPPER(vehicle_no), ' ', '') ILIKE '%88%'` (or `LIKE` in SQLite).
- **Accurate counts & active ledger defaults**: On `ai_v_motor_ledger`, ALWAYS filter `is_projected = FALSE AND is_hidden = FALSE` unless the user explicitly asks for projected or hidden records. On `ai_v_vehicles_plates`, ALWAYS use `COUNT(DISTINCT tracked_vehicle_id)` because historical plate joins produce multiple rows per vehicle.
- **Deterministic IDs & sorting**: Always include `tenure_id`, `entry_id`, `session_id`, `customer_id`, `policy_year`, and an explicit `ORDER BY` in SQL queries so clickable navigation links and counts are exact.
- **Multi-year ambiguity**: If the user asks about a car/plate without specifying a year and multiple `policy_year` tenures exist, briefly analyze ALL years on record (e.g., 2025 vs 2026) using `get_comparison_matrix_detail` or SQL, highlight the key YoY difference, and naturally ask which year they want to inspect further or act on.
- **Malaysian Motor Domain Rules**: Cover Notes and Quotations are strictly isolated; never calculate totals or road tax mentally — use `calculate_road_tax_tool` (ICE CC vs 2026 EV kW) and `get_comparison_matrix_detail` (authoritative Decimal totals and 10-year betterment caps).
- **Zero-Token Excel**: When the user asks for an Excel report, workbook, or full list export, write ONE clean SQL query and call `export_sql_to_excel`.
- **Zero Invented Facts/Links**: Only state exact numbers, plates, customer names, and RM values observed in tool results. Do NOT fabricate UUIDs or URLs; verified clickable navigation buttons are automatically attached from your tool results, so mention entities cleanly by plate/name/year in prose and tables.
- **Formatting**: Respond naturally like Gemini — concise, structured GitHub Markdown with bold RM amounts, crisp comparison tables when helpful, and proactive next-step suggestions.
"""


def _register_user_stream(user_id: str) -> threading.Event:
    ev = threading.Event()
    with _STREAM_LOCK:
        prev = _ACTIVE_USER_STREAMS.get(user_id)
        if prev is not None:
            prev.set()
        _ACTIVE_USER_STREAMS[user_id] = ev
    return ev


def _clear_user_stream(user_id: str, ev: threading.Event) -> None:
    with _STREAM_LOCK:
        if _ACTIVE_USER_STREAMS.get(user_id) is ev:
            _ACTIVE_USER_STREAMS.pop(user_id, None)


def get_user_copilot_quota(db: Session, user: User) -> dict[str, Any]:
    """Return current user's today Copilot turn/token usage, policy caps, and live barrel availability."""
    policy = get_copilot_quota_policy(db)
    is_admin = user.role in ("super_admin", "admin", "dev")
    turns_limit = policy["admin_daily_turns"] if is_admin else policy["staff_daily_turns"]
    tokens_limit = policy["admin_daily_tokens"] if is_admin else policy["staff_daily_tokens"]
    max_tokens_per_turn = policy["max_tokens_per_turn"] if is_admin else policy["staff_max_tokens_per_turn"]

    now_utc = datetime.now(timezone.utc)
    start_of_day = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    turns_used = int(
        db.scalar(
            select(func.count(CopilotMessage.id))
            .join(CopilotThread, CopilotThread.id == CopilotMessage.thread_id)
            .where(
                CopilotThread.user_id == user.id,
                CopilotMessage.role == "user",
                CopilotMessage.created_at >= start_of_day,
            )
        )
        or 0
    )

    today_pt = get_current_pt_cycle_date()
    tokens_used = int(
        db.scalar(
            select(func.coalesce(func.sum(GeminiApiCallLog.total_tokens), 0)).where(
                GeminiApiCallLog.local_date == today_pt,
                GeminiApiCallLog.actor_user_id == user.id,
                GeminiApiCallLog.purpose.like("copilot%"),
            )
        )
        or 0
    )

    gw = get_fleet_gateway()
    barrels = gw.get_copilot_barrel_snapshot(db)
    dedicated_keys = len({b["account_id"] for b in barrels if b.get("scope") == "copilot_only"})

    is_exhausted = (not policy["enabled"]) or (turns_used >= turns_limit) or (tokens_used >= tokens_limit)
    return {
        "enabled": policy["enabled"],
        "turns_used": turns_used,
        "turns_limit": turns_limit,
        "turns_remaining": max(0, turns_limit - turns_used),
        "tokens_used": tokens_used,
        "tokens_limit": tokens_limit,
        "tokens_remaining": max(0, tokens_limit - tokens_used),
        "is_exhausted": is_exhausted,
        "pt_cycle_date": today_pt,
        "warn_turn_tokens": int(policy.get("warn_turn_tokens", 15_000)),
        "max_tokens_per_turn": int(max_tokens_per_turn),
        "max_input_tokens_per_turn": int(policy.get("max_input_tokens_per_turn", 200_000)),
        "barrels": barrels,
        "dedicated_copilot_keys_count": dedicated_keys,
    }


def _derive_thread_title(query: str, links: list[dict[str, Any]] | None = None) -> str:
    """Create a crisp readable session title without wasting an extra LLM call."""
    cleaned = re.sub(r"\s+", " ", (query or "").strip())
    plate_match = re.search(r"\b([A-Z]{1,3}\s?\d{1,4}\s?[A-Z]?)\b", cleaned.upper())
    prefix = ""
    if plate_match:
        prefix = f"{plate_match.group(1)} · "
    elif links:
        first_label = str(links[0].get("label") or "").split(":")[-1].strip()
        if first_label and len(first_label) <= 24:
            prefix = f"{first_label} · "
    snippet = cleaned[:58].rstrip(" .,;:")
    if len(cleaned) > 58:
        snippet += "..."
    title = f"{prefix}{snippet}" if prefix and prefix.strip(" ·") not in snippet.upper() else snippet
    return title[:100] or "New Chat"


def serialize_thread(t: CopilotThread, owner: User | None = None) -> dict[str, Any]:
    return {
        "id": str(t.id),
        "user_id": str(t.user_id),
        "owner_name": (owner.name or owner.email) if owner else None,
        "owner_email": owner.email if owner else None,
        "owner_role": owner.role if owner else None,
        "title": t.title,
        "is_pinned": bool(t.is_pinned),
        "anchor_type": t.anchor_type,
        "anchor_id": t.anchor_id,
        "anchor_label": t.anchor_label,
        "total_tokens": int(t.total_tokens or 0),
        "has_summary": bool(t.compacted_summary),
        "last_message_at": t.last_message_at.isoformat() if t.last_message_at else None,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def serialize_artifact(a: CopilotArtifact) -> dict[str, Any]:
    return {
        "id": str(a.id),
        "thread_id": str(a.thread_id),
        "message_id": str(a.message_id) if a.message_id else None,
        "kind": a.kind,
        "filename": a.filename,
        "mime_type": a.mime_type,
        "row_count": int(a.row_count or 0),
        "size_bytes": int(a.size_bytes or 0),
        "preview": a.preview_json or {},
        "download_url": f"/api/copilot/artifacts/{a.id}/download",
        "expires_at": a.expires_at.isoformat() if a.expires_at else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def serialize_message(m: CopilotMessage, artifacts: list[CopilotArtifact] | None = None) -> dict[str, Any]:
    return {
        "id": str(m.id),
        "thread_id": str(m.thread_id),
        "role": m.role,
        "content_markdown": m.content_markdown,
        "tool_trace": m.tool_trace_json or [],
        "verified_links": m.verified_links_json or [],
        "action_cards": m.action_cards_json or [],
        "artifacts": [serialize_artifact(a) for a in (artifacts or [])],
        "prompt_tokens": int(m.prompt_tokens or 0),
        "candidate_tokens": int(m.candidate_tokens or 0),
        "total_tokens": int(m.total_tokens or 0),
        "model_used": m.model_used,
        "feedback": m.feedback,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def _norm_plate(raw: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (raw or "").upper())


_PLATE_EXTRACT_RE = re.compile(
    r"(?<![A-Z0-9/])((?:T/)?(?:(?:PUTRAJAYA|MALAYSIA|PATRIOT|RIMAU|PERFECT|PROTON|NAZA|SUKOM|G1M|1M4U|BAMBEE|EV)\s?\d{1,4}|[A-Z]{1,3}\s?\d{1,4}[A-Z]?))(?![A-Z0-9/])"
)
_NON_PLATE_PREFIX_RE = re.compile(r"^(?:RM|NO|IC|TEL|HP|KM|CC|KW|KG|FY)\d+[A-Z]?$")
_PROSE_LABEL_RE = re.compile(r"^(?:M[12]|V\d{1,2}|Q[1-4]|A4|H[1-6])$")
_ANALYTICAL_INTENT_RE = re.compile(
    r"\b(?:whatsapp|draft|road\s*tax|calculate|betterment|towing|windscreen|special\s*perils|yoy|compare\s+insurer|best\s+quote|recommend|sum\s+insured|why|explain|analy[sz]e|duplicate\s+upload|clean\s*up)\b",
    re.IGNORECASE,
)
_BULK_EXISTENCE_INTENT_RE = re.compile(
    r"\b(?:exist|ledger|found|missing|not\s+found|check|verify|table|list|status|have|got|record|system|database|in\s+the)\b",
    re.IGNORECASE,
)


def _extract_bulk_plates_from_message(text: str) -> tuple[list[dict[str, str]], int]:
    """Extract ordered, deduplicated Malaysian vehicle plates and optional pasted customer names."""
    upper_text = (text or "").upper()
    raw_matches = list(_PLATE_EXTRACT_RE.finditer(upper_text))
    kept: list[tuple[re.Match[str], str, str]] = []
    seen_norms: set[str] = set()
    dup_count = 0

    for m in raw_matches:
        disp = re.sub(r"\s+", " ", m.group(1).strip())
        np = _norm_plate(disp)
        if not np:
            continue
        after_slice = text[m.end() :]
        has_pair_sep = bool(re.match(r"^\s*[-–—:\t]\s*", after_slice))
        if not has_pair_sep and (_NON_PLATE_PREFIX_RE.match(np) or _PROSE_LABEL_RE.match(np)):
            continue
        if np in seen_norms:
            dup_count += 1
            continue
        seen_norms.add(np)
        kept.append((m, disp, np))

    entries: list[dict[str, str]] = []
    for idx, (m, disp, np) in enumerate(kept):
        pasted_name = ""
        after_slice = text[m.end() :]
        sep_m = re.match(r"^\s*[-–—:\t]\s*", after_slice)
        if sep_m:
            start_pos = m.end() + sep_m.end()
            next_plate_pos = kept[idx + 1][0].start() if idx + 1 < len(kept) else len(text)
            nl_pos = text.find("\n", start_pos)
            end_pos = min(next_plate_pos, nl_pos) if nl_pos != -1 else next_plate_pos
            cand_name = text[start_pos:end_pos]
            # Trim trailing conversational tail if this was the final pasted item inline
            if idx == len(kept) - 1:
                cand_name = re.split(
                    r"\s+(?:also|please|can\s+you|tell\s+me|check\s+if|in\s+the\s+motor)\b",
                    cand_name,
                    maxsplit=1,
                    flags=re.IGNORECASE,
                )[0]
            cand_name = re.sub(r"\s+", " ", cand_name.strip(" \t\r\n\"',;|"))
            if cand_name:
                pasted_name = cand_name[:180]
        entries.append({"plate": disp, "norm": np, "pasted_name": pasted_name})
    return entries, dup_count


def _is_pure_bulk_plate_check(
    query: str,
    extracted: list[dict[str, str]],
    *,
    enable_web_research: bool = False,
) -> bool:
    """Detect pure plate existence / ledger verification batches eligible for deterministic 0-token execution."""
    if enable_web_research or len(extracted) < 5:
        return False

    # Strip the contiguous pasted plate-list span to inspect surrounding user instructions cleanly
    upper_text = (query or "").upper()
    first_pos: int | None = None
    last_pos: int = 0
    for item in extracted:
        np = item["norm"]
        m = _PLATE_EXTRACT_RE.search(upper_text, last_pos)
        while m and _norm_plate(m.group(1)) != np:
            m = _PLATE_EXTRACT_RE.search(upper_text, m.end())
        if m:
            if first_pos is None:
                first_pos = m.start()
            last_pos = m.end()
            if item.get("pasted_name"):
                p_idx = upper_text.find(item["pasted_name"].upper(), last_pos)
                if p_idx != -1 and p_idx - last_pos <= 40:
                    last_pos = p_idx + len(item["pasted_name"])

    if first_pos is not None:
        prose_only = re.sub(r"\s+", " ", f"{query[:first_pos]} {query[last_pos:]}").strip()
    else:
        prose_only = re.sub(r"\s+", " ", query or "").strip()

    if _ANALYTICAL_INTENT_RE.search(prose_only):
        return False
    if _BULK_EXISTENCE_INTENT_RE.search(prose_only):
        return True
    return len(extracted) >= 8 and len(prose_only) < 280


def _execute_bulk_check_plates_full(
    db: Session,
    raw_plates: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Cross-check up to 5,000 plates across Active Motor Ledger, TrackedVehicle, PlateHistory, Projected/Hidden Tenures, and ClientRecord."""
    raw_items: list[tuple[str, str]] = []
    if isinstance(raw_plates, list):
        for item in raw_plates:
            if isinstance(item, dict):
                p_txt = str(item.get("plate") or "").strip()
                p_name = str(item.get("pasted_name") or "").strip()
                if p_txt:
                    raw_items.append((p_txt, p_name))
            else:
                p_txt = str(item or "").strip()
                if p_txt:
                    raw_items.append((p_txt, ""))
    elif isinstance(raw_plates, str):
        for chunk in re.split(r"[\n,;]+", raw_plates):
            c = chunk.strip()
            if c:
                raw_items.append((c, ""))

    seen_norm: dict[str, dict[str, str]] = {}
    for p_txt, p_name in raw_items:
        np = _norm_plate(p_txt)
        if np and np not in seen_norm:
            seen_norm[np] = {"label": p_txt.upper(), "pasted_name": p_name}
            if len(seen_norm) >= 5000:
                break

    if not seen_norm:
        return (
            {
                "total_checked": 0,
                "in_ledger_count": 0,
                "other_record_only_count": 0,
                "found_count": 0,
                "missing_count": 0,
                "missing_plates": [],
                "other_record_only_plates": [],
                "matched_via_history": [],
                "matched_tenure_ids": [],
                "sample_matches": [],
            },
            [],
            [],
        )

    target_set = set(seen_norm.keys())

    # 1. TrackedVehicle current plates + CustomerAccount
    tv_map: dict[str, dict[str, Any]] = {}
    tv_by_id: dict[str, dict[str, Any]] = {}
    tv_rows = db.execute(
        select(
            TrackedVehicle.id,
            TrackedVehicle.vehicle_no,
            TrackedVehicle.customer_id,
            CustomerAccount.canonical_name,
        ).outerjoin(CustomerAccount, CustomerAccount.id == TrackedVehicle.customer_id)
    ).all()
    for tv_id, vno, cid, cname in tv_rows:
        info = {
            "tracked_vehicle_id": str(tv_id),
            "vehicle_no": vno or "",
            "customer_id": str(cid) if cid else None,
            "customer_name": cname or None,
        }
        tv_by_id[str(tv_id)] = info
        np = _norm_plate(vno)
        if np in target_set and np not in tv_map:
            tv_map[np] = info

    # 2. VehiclePlateHistory historical plates
    hist_map: dict[str, dict[str, Any]] = {}
    hist_rows = db.execute(
        select(VehiclePlateHistory.plate_no, VehiclePlateHistory.tracked_vehicle_id)
    ).all()
    for h_plate, tv_id in hist_rows:
        np = _norm_plate(h_plate)
        if np in target_set and np not in hist_map:
            tv_info = tv_by_id.get(str(tv_id), {})
            hist_map[np] = {
                "historical_plate_no": h_plate,
                "current_plate_no": tv_info.get("vehicle_no"),
                "tracked_vehicle_id": str(tv_id),
                "customer_id": tv_info.get("customer_id"),
                "customer_name": tv_info.get("customer_name"),
            }

    needed_tv_ids = {
        h["tracked_vehicle_id"] for h in hist_map.values() if h.get("tracked_vehicle_id")
    } | {
        tv["tracked_vehicle_id"] for tv in tv_map.values() if tv.get("tracked_vehicle_id")
    }

    # 3. Active visible Motor Renewal Ledger tenures (exact same visibility rules as ledger_query_service)
    active_ledger_by_plate: dict[str, dict[str, Any]] = {}
    active_years_by_plate: dict[str, list[int]] = {}
    active_ledger_by_tv: dict[str, dict[str, Any]] = {}
    active_years_by_tv: dict[str, list[int]] = {}
    matched_tid_set: set[str] = set()

    t_rows = db.execute(
        select(
            InsuranceTenure.id,
            InsuranceTenure.vehicle_no,
            InsuranceTenure.customer_name,
            InsuranceTenure.stage,
            InsuranceTenure.coverage_start_date,
            InsuranceTenure.coverage_end_date,
            InsuranceTenure.tracked_vehicle_id,
            InsuranceTenure.customer_id,
            InsuranceCompany.name,
        )
        .outerjoin(InsuranceCompany, InsuranceCompany.id == InsuranceTenure.winning_company_id)
        .where(
            InsuranceTenure.deleted_at.is_(None),
            InsuranceTenure.is_discarded == False,
            InsuranceTenure.is_projected == False,
            InsuranceTenure.is_hidden == False,
        )
        .order_by(InsuranceTenure.coverage_start_date.desc())
    ).all()
    for tid, vno, cname, stage, start_dt, end_dt, tv_id, cid, win_comp in t_rows:
        np = _norm_plate(vno)
        tv_key = str(tv_id) if tv_id else None
        if np not in target_set and (not tv_key or tv_key not in needed_tv_ids):
            continue
        p_year = start_dt.year if start_dt else None
        entry = {
            "tenure_id": str(tid),
            "vehicle_no": vno or "",
            "customer_name": cname or None,
            "stage": stage or "Quotations",
            "policy_year": p_year,
            "expiry_date": end_dt.strftime("%Y-%m-%d") if end_dt else None,
            "tracked_vehicle_id": tv_key,
            "customer_id": str(cid) if cid else None,
            "winning_company": win_comp or None,
        }
        matched_tid_set.add(str(tid))
        if np in target_set:
            if np not in active_ledger_by_plate:
                active_ledger_by_plate[np] = entry
            if p_year is not None:
                yrs = active_years_by_plate.setdefault(np, [])
                if p_year not in yrs:
                    yrs.append(p_year)
        if tv_key:
            if tv_key not in active_ledger_by_tv:
                active_ledger_by_tv[tv_key] = entry
            if p_year is not None:
                yrs = active_years_by_tv.setdefault(tv_key, [])
                if p_year not in yrs:
                    yrs.append(p_year)

    # 4. Projected or Hidden tenures (NEVER treated as active ledger rows)
    inactive_by_plate: dict[str, dict[str, Any]] = {}
    inactive_by_tv: dict[str, dict[str, Any]] = {}
    in_rows = db.execute(
        select(
            InsuranceTenure.id,
            InsuranceTenure.vehicle_no,
            InsuranceTenure.customer_name,
            InsuranceTenure.coverage_start_date,
            InsuranceTenure.is_projected,
            InsuranceTenure.is_hidden,
            InsuranceTenure.tracked_vehicle_id,
        )
        .where(
            InsuranceTenure.deleted_at.is_(None),
            InsuranceTenure.is_discarded == False,
            or_(InsuranceTenure.is_projected == True, InsuranceTenure.is_hidden == True),
        )
        .order_by(InsuranceTenure.is_projected.asc(), InsuranceTenure.coverage_start_date.desc())
    ).all()
    for tid, vno, cname, start_dt, is_proj, is_hid, tv_id in in_rows:
        np = _norm_plate(vno)
        tv_key = str(tv_id) if tv_id else None
        if np not in target_set and (not tv_key or tv_key not in needed_tv_ids):
            continue
        p_year = start_dt.year if start_dt else None
        reason_lbl = "Hidden in Ledger" if is_hid else "Projected Renewal Only"
        if p_year:
            reason_lbl = f"{reason_lbl} ({p_year})"
        info = {
            "tenure_id": str(tid),
            "vehicle_no": vno or "",
            "customer_name": cname or None,
            "policy_year": p_year,
            "reason": reason_lbl,
        }
        if np in target_set and np not in inactive_by_plate:
            inactive_by_plate[np] = info
        if tv_key and tv_key not in inactive_by_tv:
            inactive_by_tv[tv_key] = info

    # 5. Comparison quote counts per active matched tenure_id (chunked by 500)
    quote_counts: dict[str, int] = {}
    tid_list = list(matched_tid_set)
    for i in range(0, len(tid_list), 500):
        chunk = tid_list[i : i + 500]
        c_rows = db.execute(
            select(TenureComparisonEntry.tenure_id, func.count(TenureComparisonEntry.id))
            .where(
                TenureComparisonEntry.tenure_id.in_(chunk),
                TenureComparisonEntry.is_hidden == False,
            )
            .group_by(TenureComparisonEntry.tenure_id)
        ).all()
        for tid, cnt in c_rows:
            quote_counts[str(tid)] = int(cnt or 0)

    # 6. Non-deleted ClientRecord rows
    client_rec_map: dict[str, dict[str, Any]] = {}
    cr_rows = db.execute(
        select(
            ClientRecord.id,
            ClientRecord.vehicle_no,
            ClientRecord.customer_name,
            ClientRecord.insurance_company,
            ClientRecord.session_id,
        ).where(ClientRecord.deleted_at.is_(None))
    ).all()
    for cr_id, vno, cname, comp, sid in cr_rows:
        np = _norm_plate(vno)
        if np in target_set and np not in client_rec_map:
            client_rec_map[np] = {
                "client_record_id": str(cr_id),
                "vehicle_no": vno or "",
                "customer_name": cname or None,
                "insurance_company": comp,
                "session_id": str(sid) if sid else None,
            }

    missing_plates: list[str] = []
    other_record_only_plates: list[dict[str, Any]] = []
    matched_via_history: list[dict[str, Any]] = []
    matched_tenure_ids: list[str] = []
    sample_matches: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []
    matched_observed_rows: list[dict[str, Any]] = []
    in_ledger_count = 0
    found_count = 0

    for idx, (np, meta) in enumerate(seen_norm.items(), start=1):
        orig_label = meta["label"]
        pasted_name = meta.get("pasted_name", "")
        tv_hit = tv_map.get(np)
        hist_hit = hist_map.get(np)
        cr_hit = client_rec_map.get(np)

        hist_tv_id = (hist_hit or {}).get("tracked_vehicle_id")
        tv_id_eff = (tv_hit or {}).get("tracked_vehicle_id") or hist_tv_id

        ten_hit = active_ledger_by_plate.get(np) or (active_ledger_by_tv.get(hist_tv_id) if hist_tv_id else None)
        all_years = (
            active_years_by_plate.get(np)
            or (active_years_by_tv.get(hist_tv_id) if hist_tv_id else None)
            or ([ten_hit["policy_year"]] if ten_hit and ten_hit.get("policy_year") else [])
        )
        inact_hit = inactive_by_plate.get(np) or (inactive_by_tv.get(tv_id_eff) if tv_id_eff else None)

        if not (tv_hit or hist_hit or ten_hit or inact_hit or cr_hit):
            missing_plates.append(orig_label)
            all_rows.append(
                {
                    "index": idx,
                    "queried_plate": orig_label,
                    "vehicle_no": orig_label,
                    "pasted_name": pasted_name,
                    "customer_name": pasted_name or None,
                    "ledger_status": "Not Found",
                    "in_motor_ledger": False,
                    "other_reason": None,
                    "tenure_id": None,
                    "policy_year": None,
                    "all_policy_years": [],
                    "stage": None,
                    "expiry_date": None,
                    "winning_company": None,
                    "comparison_quote_count": 0,
                    "session_id": None,
                    "customer_id": None,
                    "sources": [],
                }
            )
            continue

        found_count += 1
        sources: list[str] = []
        if tv_hit:
            sources.append("tracked_vehicles")
        if hist_hit:
            sources.append("plate_history")
            matched_via_history.append(
                {
                    "queried_plate": orig_label,
                    "current_plate": hist_hit.get("current_plate_no"),
                    "customer_name": (ten_hit or {}).get("customer_name") or hist_hit.get("customer_name"),
                }
            )
        if ten_hit:
            sources.append("motor_ledger")
            in_ledger_count += 1
            matched_tenure_ids.append(ten_hit["tenure_id"])
        if inact_hit and not ten_hit:
            sources.append("inactive_tenure")
        if cr_hit:
            sources.append("client_records")

        best_plate = (
            (ten_hit or {}).get("vehicle_no")
            or (tv_hit or {}).get("vehicle_no")
            or (cr_hit or {}).get("vehicle_no")
            or (hist_hit or {}).get("current_plate_no")
            or (inact_hit or {}).get("vehicle_no")
            or orig_label
        )
        best_cust = (
            (ten_hit or {}).get("customer_name")
            or (tv_hit or {}).get("customer_name")
            or (cr_hit or {}).get("customer_name")
            or (hist_hit or {}).get("customer_name")
            or (inact_hit or {}).get("customer_name")
            or pasted_name
            or None
        )
        other_reason: str | None = None
        if not ten_hit:
            if inact_hit:
                other_reason = str(inact_hit["reason"])
            elif cr_hit and tv_hit:
                other_reason = "Client & Vehicle Registry Only"
            elif cr_hit:
                other_reason = "Client Records Only"
            elif hist_hit:
                other_reason = f"Plate History Only ({hist_hit.get('current_plate_no') or 'old plate'})"
            else:
                other_reason = "Vehicle Registry Only"
            other_record_only_plates.append(
                {
                    "queried_plate": orig_label,
                    "customer_name": best_cust,
                    "reason": other_reason,
                }
            )

        q_count = quote_counts.get(ten_hit["tenure_id"], 0) if ten_hit else 0
        row_summary = {
            "index": idx,
            "queried_plate": orig_label,
            "vehicle_no": best_plate,
            "pasted_name": pasted_name,
            "customer_name": best_cust,
            "ledger_status": "In Ledger" if ten_hit else "Other Record Only",
            "in_motor_ledger": bool(ten_hit),
            "other_reason": other_reason,
            "tenure_id": (ten_hit or {}).get("tenure_id"),
            "policy_year": (ten_hit or {}).get("policy_year"),
            "all_policy_years": all_years,
            "stage": (ten_hit or {}).get("stage"),
            "expiry_date": (ten_hit or {}).get("expiry_date"),
            "winning_company": (ten_hit or {}).get("winning_company"),
            "comparison_quote_count": q_count,
            "session_id": (cr_hit or {}).get("session_id"),
            "customer_id": (ten_hit or {}).get("customer_id")
            or (tv_hit or {}).get("customer_id")
            or (hist_hit or {}).get("customer_id"),
            "sources": sources,
        }
        all_rows.append(row_summary)
        matched_observed_rows.append(row_summary)
        if len(sample_matches) < 150:
            sample_matches.append(row_summary)

    return (
        {
            "total_checked": len(seen_norm),
            "in_ledger_count": in_ledger_count,
            "other_record_only_count": len(other_record_only_plates),
            "found_count": found_count,
            "missing_count": len(missing_plates),
            "missing_plates": missing_plates,
            "other_record_only_plates": other_record_only_plates[:150],
            "matched_via_history": matched_via_history[:100],
            "matched_tenure_ids": matched_tenure_ids[:200],
            "sample_matches": sample_matches,
        },
        all_rows,
        matched_observed_rows,
    )


def _execute_bulk_check_plates(db: Session, raw_plates: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Cross-check up to 5,000 vehicle plates across active ledger, vehicle registry, plate history, and client records."""
    summary, _all_rows, matched_rows = _execute_bulk_check_plates_full(db, raw_plates)
    return summary, matched_rows


def _escape_md_cell(val: Any) -> str:
    txt = re.sub(r"\s+", " ", str(val if val is not None else "—")).strip()
    return (txt or "—").replace("|", r"\|")


def _render_deterministic_bulk_report(
    summary: dict[str, Any],
    all_rows: list[dict[str, Any]],
    *,
    duplicate_count: int = 0,
) -> str:
    """Render a 100% complete, DB-verified Markdown report and full table for pasted plate batches."""
    total = int(summary.get("total_checked") or 0)
    in_ledger = int(summary.get("in_ledger_count") or 0)
    other_cnt = int(summary.get("other_record_only_count") or 0)
    missing_cnt = int(summary.get("missing_count") or 0)

    lines: list[str] = [
        f"Checked **{total:,}** unique vehicle registration plate(s) directly against the Motor Renewal Ledger and client/vehicle records (100% DB verified):",
        "",
        f"- **In Motor Renewal Ledger (Active):** {in_ledger:,}",
        f"- **Other Record Only (Not in Active Ledger):** {other_cnt:,}",
        f"- **Not Found Anywhere:** {missing_cnt:,}",
    ]
    if duplicate_count > 0:
        lines.append(f"- **Duplicate entries deduplicated from input:** {duplicate_count:,}")

    not_found_rows = [r for r in all_rows if r["ledger_status"] == "Not Found"]
    if not_found_rows:
        lines.extend(["", f"### Plates Not Found ({len(not_found_rows):,})"])
        for r in not_found_rows:
            p_name = f" — {r['pasted_name']}" if r.get("pasted_name") else ""
            lines.append(f"- **{r['queried_plate']}**{p_name}")

    other_rows = [r for r in all_rows if r["ledger_status"] == "Other Record Only"]
    if other_rows:
        lines.extend(["", f"### Other Record Only — Not in Active Ledger ({len(other_rows):,})"])
        for r in other_rows:
            c_txt = f" ({r['customer_name']})" if r.get("customer_name") else ""
            lines.append(f"- **{r['queried_plate']}**{c_txt} — {r.get('other_reason') or 'Non-ledger record'}")

    hist_rows = summary.get("matched_via_history") or []
    if hist_rows:
        lines.extend(["", f"### Matched via Historical Plate ({len(hist_rows):,})"])
        for h in hist_rows:
            lines.append(
                f"- **{h.get('queried_plate')}** → Current plate **{h.get('current_plate') or '—'}** ({h.get('customer_name') or '—'})"
            )

    lines.extend(
        [
            "",
            f"### Complete Vehicle Status Table ({len(all_rows):,} rows)",
            "",
            "| # | Vehicle No | Customer Name | Ledger Status | Year | Stage | Comparison | Links |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )

    for r in all_rows:
        vno_disp = r.get("vehicle_no") or r.get("queried_plate") or "—"
        if r.get("queried_plate") and _norm_plate(r["queried_plate"]) != _norm_plate(vno_disp):
            vno_disp = f"{r['queried_plate']} → {vno_disp}"
        cust_disp = r.get("customer_name") or r.get("pasted_name") or "—"
        status_disp = r["ledger_status"]

        yrs = r.get("all_policy_years") or []
        if yrs:
            yr_disp = ", ".join(str(y) for y in yrs)
        elif r.get("policy_year"):
            yr_disp = str(r["policy_year"])
        else:
            yr_disp = "—"

        stage_disp = r.get("stage") or (r.get("other_reason") or "—")

        q_cnt = int(r.get("comparison_quote_count") or 0)
        if r["in_motor_ledger"]:
            comp_disp = f"{q_cnt} quote{'s' if q_cnt == 1 else ''}" if q_cnt > 0 else "0 quotes"
            if r.get("winning_company"):
                comp_disp = f"{comp_disp} ({r['winning_company']})"
        else:
            comp_disp = "—"

        cell_links: list[str] = []
        tid = r.get("tenure_id")
        if tid:
            yr_param = str(r["policy_year"]) if r.get("policy_year") else "all"
            ledger_url = (
                f"/ledger?tenure_ids={tid}&select=true&highlight_tenure={tid}"
                f"&year={yr_param}&category=all"
            )
            cell_links.append(f"[Ledger]({ledger_url})")
            cell_links.append(f"[Compare](/comparison?tenure_id={tid})")
        else:
            if r.get("session_id"):
                cell_links.append(f"[Workspace](/sessions/{r['session_id']})")
            if r["ledger_status"] == "Other Record Only" and (r.get("customer_name") or r.get("vehicle_no")):
                q_term = quote(str(r.get("vehicle_no") or r.get("customer_name") or ""))
                c_url = f"/client-records?search={q_term}"
                if r.get("customer_id"):
                    c_url += f"&highlight_client={r['customer_id']}"
                cell_links.append(f"[Client]({c_url})")

        links_disp = " · ".join(cell_links) if cell_links else "—"
        lines.append(
            "| "
            + " | ".join(
                [
                    str(r.get("index") or ""),
                    _escape_md_cell(vno_disp),
                    _escape_md_cell(cust_disp),
                    _escape_md_cell(status_disp),
                    _escape_md_cell(yr_disp),
                    _escape_md_cell(stage_disp),
                    _escape_md_cell(comp_disp),
                    links_disp,
                ]
            )
            + " |"
        )

    return "\n".join(lines)


def _collect_verified_links(
    rows: list[dict[str, Any]],
    final_markdown: str = "",
    max_links: int = 8,
    *,
    prefer_all_ledger_rows: bool = False,
) -> list[dict[str, str]]:
    """Build verified UI navigation chips strictly from real IDs relevant to the final answer."""
    if not rows:
        return []

    norm_answer = re.sub(r"[^A-Z0-9]", "", (final_markdown or "").upper())
    low_answer = (final_markdown or "").lower()

    # Filter to rows mentioned in the final answer when possible so missing-only reports don't attach random vehicles
    relevant_rows: list[dict[str, Any]] = []
    if prefer_all_ledger_rows:
        relevant_rows = [r for r in rows if r.get("tenure_id") or r.get("session_id") or r.get("customer_id") or r.get("vehicle_no")]
    elif final_markdown.strip():
        for r in rows:
            vno = _norm_plate(str(r.get("vehicle_no") or ""))
            qno = _norm_plate(str(r.get("queried_plate") or ""))
            cname = str(r.get("customer_name") or r.get("canonical_name") or "").strip().lower()
            plate_hit = (len(vno) >= 3 and vno in norm_answer) or (len(qno) >= 3 and qno in norm_answer)
            cust_hit = len(cname) >= 4 and cname in low_answer
            if plate_hit or cust_hit:
                relevant_rows.append(r)
    else:
        relevant_rows = rows

    if not relevant_rows:
        return []

    links: list[dict[str, str]] = []
    seen_hrefs: set[str] = set()

    def _add(kind: str, label: str, href: str) -> None:
        if len(links) >= max_links or href in seen_hrefs:
            return
        seen_hrefs.add(href)
        links.append({"kind": kind, "label": label[:72], "href": href})

    # Emit primary batch selection link when 2+ distinct tenures are relevant
    distinct_tids: list[str] = []
    for r in relevant_rows:
        tid = str(r.get("tenure_id") or "").strip()
        if tid and tid not in distinct_tids:
            distinct_tids.append(tid)
    if len(distinct_tids) >= 2:
        capped = distinct_tids[:100]
        joined = ",".join(capped)
        batch_label = (
            f"Select & Highlight {len(distinct_tids)} Vehicles in Ledger"
            if len(distinct_tids) <= 100
            else f"Select First 100 of {len(distinct_tids)} Vehicles in Ledger"
        )
        _add(
            "ledger_batch",
            batch_label,
            f"/ledger?tenure_ids={joined}&select=true&highlight=all&year=all&category=all",
        )

    for row in relevant_rows:
        tenure_id = str(row.get("tenure_id") or "").strip()
        entry_id = str(row.get("entry_id") or "").strip()
        session_id = str(row.get("session_id") or "").strip()
        covernote_sid = str(row.get("covernote_session_id") or "").strip()
        customer_id = str(row.get("customer_id") or "").strip()
        plate = str(row.get("vehicle_no") or "").strip()
        year = row.get("policy_year")
        customer = str(row.get("customer_name") or row.get("canonical_name") or "").strip()

        yr_suffix = f" ({year})" if year else ""
        tag = plate or customer or "Record"

        if tenure_id:
            comp_href = f"/comparison?tenure_id={tenure_id}"
            if entry_id:
                comp_href += f"&highlight_entry={entry_id}"
            _add("comparison", f"Compare {tag}{yr_suffix}", comp_href)

            yr_param = str(year) if year else "all"
            if plate:
                ledger_href = f"/ledger?tenure_ids={tenure_id}&select=true&highlight_tenure={tenure_id}&year={yr_param}&category=all&search={quote(plate)}"
            else:
                ledger_href = f"/ledger?tenure_ids={tenure_id}&select=true&highlight_tenure={tenure_id}&year={yr_param}&category=all"
            _add("ledger", f"Ledger: {tag}{yr_suffix}", ledger_href)
        elif plate and not row.get("other_reason"):
            _add("ledger", f"Ledger: {plate}", f"/ledger?search={quote(plate)}&year=all&category=all")

        eff_sid = session_id or covernote_sid
        if eff_sid:
            _add("session", f"Workspace: {tag}{yr_suffix}", f"/sessions/{eff_sid}")

        if customer and not tenure_id and not eff_sid:
            c_href = f"/client-records?search={quote(customer)}"
            if customer_id:
                c_href += f"&highlight_client={customer_id}"
            _add("client", f"Client: {customer}", c_href)

    return links


def _tool_declarations(*, include_web_research: bool) -> list[dict[str, Any]]:
    decls: list[dict[str, Any]] = [
        {
            "name": "bulk_check_plates",
            "description": (
                "Check existence of 3 to 5,000 vehicle registration plates in ONE fast pass across "
                "active motor_ledger tenures, tracked_vehicles, vehicle_plate_history, and client_records. "
                "Set use_user_message=True whenever checking plates pasted in the user's message so zero plates are dropped."
            ),
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "plates": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"},
                        "description": "List of vehicle registration plates to check.",
                    },
                    "use_user_message": {
                        "type": "BOOLEAN",
                        "description": "Set true to extract and verify all plates directly from the user's message.",
                    },
                    "reason": {"type": "STRING", "description": "Short 4-8 word summary of this bulk check."},
                },
                "required": ["reason"],
            },
        },
        {
            "name": "run_readonly_sql",
            "description": (
                "Execute a read-only PostgreSQL SELECT/WITH query over the 6 ai_v_* semantic views "
                "(ai_v_motor_ledger, ai_v_comparison_quotes, ai_v_vehicles_plates, ai_v_clients_fleet, "
                "ai_v_sessions, ai_v_insurer_catalogs). Returns up to 50 rows."
            ),
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "sql": {"type": "STRING", "description": "Single read-only SELECT or WITH query over ai_v_* views."},
                    "reason": {"type": "STRING", "description": "Short 4-8 word label of what this query checks."},
                },
                "required": ["sql", "reason"],
            },
        },
        {
            "name": "export_sql_to_excel",
            "description": (
                "Generate a formatted Excel (.xlsx) workbook directly from a read-only SQL query over ai_v_* views "
                "(up to 25,000 rows, zero token bloat). Use whenever the user asks for an Excel/spreadsheet/full export."
            ),
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "sql": {"type": "STRING", "description": "Single SELECT/WITH query over ai_v_* views."},
                    "filename": {"type": "STRING", "description": "Descriptive .xlsx filename (e.g. 'stmb_2026_quotes.xlsx')."},
                    "sheet_name": {"type": "STRING", "description": "Short Excel worksheet tab name."},
                    "reason": {"type": "STRING", "description": "Short 4-8 word summary of the export."},
                },
                "required": ["sql", "filename", "reason"],
            },
        },
        {
            "name": "get_comparison_matrix_detail",
            "description": (
                "Run RiskLocker's exact Decimal comparison & ranking engine for a specific tenure_id. "
                "Returns all insurer quotes, winner recommendation, towing km, betterment waiver, and YoY delta vs previous policy."
            ),
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "tenure_id": {"type": "STRING", "description": "UUID of the insurance_tenures record."},
                },
                "required": ["tenure_id"],
            },
        },
        {
            "name": "calculate_road_tax_tool",
            "description": "Compute official Malaysian JPJ road tax (ICE CC or EV kW or Commercial kg).",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "capacity": {"type": "STRING", "description": "Engine capacity e.g. '1500 CC', '150 kW', '5000 KG'."},
                    "vehicle_type": {"type": "STRING", "description": "Car, MPV, SUV, Motorcycle, Lorry, EVSaloonCar, EVSUV."},
                    "jurisdiction": {"type": "STRING", "description": "West Malaysia, Sabah, or Sarawak."},
                    "owner_type": {"type": "STRING", "description": "Individual or Company."},
                },
                "required": ["capacity"],
            },
        },
        {
            "name": "inspect_duplicate_sessions_or_catalog",
            "description": (
                "Inspect duplicate session uploads (for 1-click cleanup card) or compare/inspect insurer benefit catalogs."
            ),
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "intent": {"type": "STRING", "description": "'duplicates' or 'catalog'."},
                    "company_name": {"type": "STRING", "description": "Optional insurer name (e.g. 'AmAssurance', 'STMB')."},
                },
                "required": ["intent"],
            },
        },
    ]
    if include_web_research:
        decls.append(
            {
                "name": "web_research",
                "description": "Search the live web via Gemini Google Search for external Malaysian JPJ/insurance/vehicle facts.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {"type": "STRING", "description": "Targeted factual search query."},
                    },
                    "required": ["query"],
                },
            }
        )
    return [{"function_declarations": decls}]


def _compact_comparison_summary(comp_data: dict[str, Any]) -> dict[str, Any]:
    entries = []
    for e in comp_data.get("entries") or []:
        if e.get("is_hidden"):
            continue
        entries.append(
            {
                "entry_id": e.get("id"),
                "company_name": e.get("company_name"),
                "sum_insured": e.get("sum_insured"),
                "valuation_type": e.get("valuation_type"),
                "motor_premium": e.get("motor_premium"),
                "road_tax": e.get("road_tax"),
                "runner_fee": e.get("runner_fee"),
                "total_payable": e.get("total_payable"),
                "discount": e.get("discount"),
                "towing_limit": e.get("towing_limit"),
                "towing_km": e.get("towing_km"),
                "waiver_betterment": e.get("waiver_betterment"),
                "betterment_display": e.get("betterment_display"),
                "windscreen_sum_insured": e.get("windscreen_sum_insured"),
                "special_perils": e.get("special_perils"),
                "rank": e.get("manual_rank") or e.get("rank"),
                "is_recommended": e.get("is_recommended"),
                "session_id": e.get("session_id"),
            }
        )
    tenure = comp_data.get("tenure") or {}
    return {
        "tenure_id": tenure.get("id"),
        "vehicle_no": tenure.get("vehicle_no"),
        "customer_name": tenure.get("customer_name"),
        "coverage_start_date": tenure.get("coverage_start_date"),
        "coverage_end_date": tenure.get("coverage_end_date"),
        "stage": tenure.get("stage"),
        "ncd_percentage": tenure.get("ncd_percentage"),
        "entries": entries,
        "yoy_insight": comp_data.get("yoy_insight"),
    }


def _maybe_compact_thread(
    db: Session,
    *,
    thread: CopilotThread,
    user: User,
    gateway: Any,
    compact_threshold_tokens: int = 6_000,
) -> None:
    """Summarize older completed turns into thread.compacted_summary once uncompacted history grows."""
    msgs = list(
        db.scalars(
            select(CopilotMessage)
            .where(CopilotMessage.thread_id == thread.id)
            .order_by(CopilotMessage.created_at.asc())
        ).all()
    )
    if len(msgs) <= 8:
        return

    start_idx = 0
    if thread.compacted_up_to_message_id:
        for idx, m in enumerate(msgs):
            if str(m.id) == str(thread.compacted_up_to_message_id):
                start_idx = idx + 1
                break

    uncompacted = msgs[start_idx:]
    if len(uncompacted) <= 6:
        return

    est_tokens = sum(max(20, len(m.content_markdown or "") // 4) for m in uncompacted)
    if est_tokens < compact_threshold_tokens:
        return

    # Keep the latest 4 messages (2 full turns) raw; compact the rest
    to_compact = uncompacted[:-4]
    if len(to_compact) < 2:
        return
    # End at an assistant boundary so user/assistant pairs never orphan
    while to_compact and to_compact[-1].role != "assistant":
        to_compact.pop()
    if not to_compact:
        return

    transcript_lines = []
    if thread.compacted_summary:
        transcript_lines.append(f"PREVIOUS SUMMARY:\n{thread.compacted_summary}\n")
    for m in to_compact:
        transcript_lines.append(f"{m.role.upper()}: {(m.content_markdown or '')[:1200]}")

    payload = {
        "system_instruction": {
            "parts": [
                {
                    "text": (
                        "Compress this conversation history into a dense, factual summary (max 220 words) preserving "
                        "all vehicle plates, customer names, tenure_ids, years, RM amounts, and user preferences."
                    )
                }
            ]
        },
        "contents": [{"role": "user", "parts": [{"text": "\n".join(transcript_lines)}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 350},
    }
    try:
        summary = gateway.execute_gemini_request(
            payload=payload,
            estimated_tokens=min(4_000, est_tokens),
            timeout_seconds=12.0,
            max_attempts=1,
            max_wait_seconds=6.0,
            purpose="copilot_compact",
            actor_user_id=user.id,
            priority=25,
            allow_quota_raise=False,
            parse_fn=lambda d: (
                (((d.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [{}])[0]
                .get("text", "")
                .strip()
                or None
            ),
        )
        if summary:
            thread.compacted_summary = summary[:3_000]
            thread.compacted_up_to_message_id = to_compact[-1].id
            db.commit()
    except Exception as exc:
        logger.debug("Copilot thread compaction skipped: %s", exc)


def _deterministic_offline_fallback(
    db: Session,
    query: str,
    observed_rows: list[dict[str, Any]],
) -> tuple[str, list[dict[str, str]]]:
    """Safe fallback when Gemini quota is paused/exhausted or offline."""
    plates = re.findall(r"\b[A-Z]{1,3}\s?\d{1,4}[A-Z]?\b", query.upper())
    collected = list(observed_rows)
    if not collected and plates:
        clean_p = plates[0].replace(" ", "")
        try:
            res = execute_readonly_sql(
                db,
                f"SELECT tenure_id, vehicle_no, customer_name, policy_year, stage, winning_company, won_premium "
                f"FROM ai_v_motor_ledger WHERE REPLACE(UPPER(vehicle_no), ' ', '') LIKE '%{clean_p}%' "
                f"ORDER BY coverage_start_date DESC",
                max_rows=20,
            )
            collected.extend(res["rows"])
        except Exception:
            pass

    links = _collect_verified_links(collected)
    if collected:
        lines = [
            f"⚠️ **Live AI reasoning is temporarily unavailable or paused**, so I pulled direct database records for you ({len(collected)} match(es)):",
            "",
        ]
        for r in collected[:10]:
            vno = r.get("vehicle_no") or "—"
            cust = r.get("customer_name") or "—"
            yr = r.get("policy_year") or ""
            stg = r.get("stage") or r.get("tenure_stage") or "—"
            prem = r.get("won_premium") or r.get("total_payable")
            prem_txt = f"RM {prem:,.2f}" if isinstance(prem, (int, float)) else "—"
            lines.append(f"- **{vno}** ({yr}) · {cust} · Stage: `{stg}` · {prem_txt}")
        return "\n".join(lines), links

    return (
        "⚠️ **AI Copilot is currently paused or reached its daily quota reserve.** "
        "Please ask an Admin to check `/settings/ai-engine`, or wait for the next Pacific Time quota reset.",
        links,
    )


def stream_agent_turn(
    *,
    session_factory: Callable[[], Session],
    user_id: str,
    thread_id: str,
    message_text: str,
    page_context: dict[str, Any] | None = None,
    enable_web_research: bool = False,
    gateway: Any = None,
) -> Generator[dict[str, Any], None, None]:
    """Run the autonomous ReAct Copilot loop, yielding SSE event dicts without holding DB connections during LLM I/O."""
    cleaned_query = (message_text or "").strip()
    if not cleaned_query:
        yield {"type": "error", "code": "empty_message", "message": "Message cannot be empty."}
        return

    gw = gateway or get_fleet_gateway()
    cancel_event = _register_user_stream(user_id)

    observed_rows: list[dict[str, Any]] = []
    tool_trace: list[dict[str, Any]] = []
    action_cards: list[dict[str, Any]] = []
    artifacts_out: list[CopilotArtifact] = []
    artifact_ids: list[str] = []
    total_prompt_tokens = 0
    total_candidate_tokens = 0
    total_tokens_turn = 0
    last_model_used: str | None = None
    user_msg_id: str = new_id()
    assistant_msg_id: str = new_id()

    try:
        # Step 1: Load user, thread, quota, and conversation context in a short DB session
        with session_factory() as db:
            user = db.get(User, user_id)
            if not user:
                yield {"type": "error", "code": "unauthorized", "message": "User session not found."}
                return

            thread = db.get(CopilotThread, thread_id)
            if not thread or thread.deleted_at is not None or str(thread.user_id) != str(user.id):
                yield {"type": "error", "code": "not_found", "message": "Copilot thread not found."}
                return

            policy = get_copilot_quota_policy(db)
            quota = get_user_copilot_quota(db, user)
            if not policy["enabled"]:
                yield {
                    "type": "error",
                    "code": "copilot_paused",
                    "message": "AI Copilot is currently paused by an administrator to preserve extraction capacity.",
                    "quota": quota,
                }
                return
            if quota["turns_used"] >= quota["turns_limit"] or quota["tokens_used"] >= quota["tokens_limit"]:
                yield {
                    "type": "error",
                    "code": "user_quota_exceeded",
                    "message": f"You have reached today's Copilot limit ({quota['turns_used']}/{quota['turns_limit']} chats).",
                    "quota": quota,
                }
                return

            # Persist user message immediately so thread history is durable
            now_dt = datetime.now(timezone.utc)
            u_msg = CopilotMessage(
                id=user_msg_id,
                thread_id=thread.id,
                role="user",
                content_markdown=cleaned_query,
            )
            db.add(u_msg)
            thread.last_message_at = now_dt
            if page_context and not thread.anchor_id:
                if page_context.get("anchor_id"):
                    thread.anchor_type = str(page_context.get("anchor_type") or "")[:40] or None
                    thread.anchor_id = str(page_context.get("anchor_id") or "")[:120] or None
                    thread.anchor_label = str(page_context.get("anchor_label") or "")[:255] or None
            db.commit()

            yield {"type": "thread", "thread": serialize_thread(thread, owner=user)}

            # Build conversation contents from compacted summary + recent messages
            contents: list[dict[str, Any]] = []
            if thread.compacted_summary:
                contents.append(
                    {
                        "role": "user",
                        "parts": [{"text": f"[CONVERSATION MEMORY SUMMARY]\n{thread.compacted_summary}"}],
                    }
                )
                contents.append({"role": "model", "parts": [{"text": "Understood, continuing with that context."}]})

            recent_msgs = list(
                db.scalars(
                    select(CopilotMessage)
                    .where(CopilotMessage.thread_id == thread.id)
                    .order_by(CopilotMessage.created_at.desc())
                    .limit(11)
                ).all()
            )
            recent_msgs.reverse()
            # Exclude the brand-new user message from history loop; we append it with active screen context below
            for rm in recent_msgs[:-1]:
                contents.append(
                    {
                        "role": "user" if rm.role == "user" else "model",
                        "parts": [{"text": (rm.content_markdown or "")[:3000]}],
                    }
                )

            ctx_banner = ""
            if page_context and any(page_context.get(k) for k in ("pathname", "anchor_id", "anchor_label")):
                ctx_banner = (
                    f"[ACTIVE SCREEN CONTEXT: pathname={page_context.get('pathname') or '/'}, "
                    f"anchor_type={page_context.get('anchor_type') or 'none'}, "
                    f"anchor_id={page_context.get('anchor_id') or 'none'}, "
                    f"anchor_label={page_context.get('anchor_label') or 'none'}]\n\n"
                )
            contents.append({"role": "user", "parts": [{"text": f"{ctx_banner}{cleaned_query}"}]})

            max_hops = int(policy["max_tool_hops"])
            max_input_tok = int(policy["max_input_tokens_per_turn"])
            is_admin_user = user.role in ("super_admin", "admin", "dev")
            turn_token_cap = int(
                policy.get("max_tokens_per_turn", 150_000)
                if is_admin_user
                else policy.get("staff_max_tokens_per_turn", 60_000)
            )

        # Step 2: Deterministic Zero-Token Bulk Fast-Path OR Autonomous ReAct Loop
        extracted_plates, dup_plate_count = _extract_bulk_plates_from_message(cleaned_query)
        final_markdown = ""
        model_reply_telemetry: list[dict[str, Any]] = []
        orchestrator = get_copilot_orchestrator()
        token_cap_reached = False
        prefer_all_ledger_rows = False

        if len(extracted_plates) > 5000:
            last_model_used = "direct-db-verified"
            final_markdown = (
                f"⚠️ **Batch size limit exceeded ({len(extracted_plates):,} unique plates detected).** "
                "Single-batch verification supports up to **5,000** unique plates to guarantee 100% completeness without truncation. "
                "Please split your paste into batches of 5,000 or fewer plates."
            )
        elif _is_pure_bulk_plate_check(
            cleaned_query,
            extracted_plates,
            enable_web_research=enable_web_research,
        ):
            step_id = new_id()[:8]
            step_label = f"Verify {len(extracted_plates):,} vehicle plates across ledger & records"
            yield {
                "type": "step",
                "step_id": step_id,
                "status": "running",
                "tool": "bulk_check_plates",
                "label": step_label,
            }
            t_tool0 = time.perf_counter()
            step_status = "done"
            step_rows: int | None = None
            with session_factory() as bulk_db:
                bulk_user = bulk_db.get(User, user_id)
                bulk_summary, all_bulk_rows, matched_rows = _execute_bulk_check_plates_full(
                    bulk_db, extracted_plates
                )
                observed_rows.extend(matched_rows)
                step_rows = int(bulk_summary.get("total_checked") or 0)
                prefer_all_ledger_rows = True
                last_model_used = "direct-db-verified"
                final_markdown = _render_deterministic_bulk_report(
                    bulk_summary,
                    all_bulk_rows,
                    duplicate_count=dup_plate_count,
                )

                low_q = cleaned_query.lower()
                wants_excel = bulk_summary["total_checked"] >= 50 or any(
                    kw in low_q for kw in ("excel", "xlsx", "export", "spreadsheet")
                )
                if wants_excel and bulk_user and all_bulk_rows:
                    try:
                        xl_cols = [
                            "#",
                            "vehicle_no",
                            "queried_plate",
                            "customer_name",
                            "ledger_status",
                            "policy_years",
                            "stage",
                            "expiry_date",
                            "winning_company",
                            "comparison_quotes",
                            "detail",
                        ]
                        xl_rows = [
                            {
                                "#": r.get("index"),
                                "vehicle_no": r.get("vehicle_no") or r.get("queried_plate"),
                                "queried_plate": r.get("queried_plate"),
                                "customer_name": r.get("customer_name") or "",
                                "ledger_status": r.get("ledger_status"),
                                "policy_years": ", ".join(str(y) for y in (r.get("all_policy_years") or []))
                                or (str(r["policy_year"]) if r.get("policy_year") else ""),
                                "stage": r.get("stage") or "",
                                "expiry_date": r.get("expiry_date") or "",
                                "winning_company": r.get("winning_company") or "",
                                "comparison_quotes": int(r.get("comparison_quote_count") or 0)
                                if r.get("in_motor_ledger")
                                else "",
                                "detail": r.get("other_reason") or "",
                            }
                            for r in all_bulk_rows
                        ]
                        art, _art_meta = export_rows_to_excel(
                            bulk_db,
                            user=bulk_user,
                            thread_id=thread_id,
                            message_id=None,
                            columns=xl_cols,
                            rows=xl_rows,
                            filename=f"bulk_plate_check_{bulk_summary['total_checked']}_vehicles.xlsx",
                            sheet_name="Vehicle Status",
                        )
                        bulk_db.commit()
                        artifact_ids.append(str(art.id))
                        artifacts_out.append(art)
                        yield {"type": "artifact", "artifact": serialize_artifact(art)}
                    except Exception as exc:
                        bulk_db.rollback()
                        logger.warning("Zero-token bulk Excel attachment skipped: %s", exc)

            elapsed_ms = int((time.perf_counter() - t_tool0) * 1000)
            trace_item = {
                "step_id": step_id,
                "status": step_status,
                "tool": "bulk_check_plates",
                "label": step_label,
                "sql": None,
                "row_count": step_rows,
                "elapsed_ms": elapsed_ms,
            }
            tool_trace.append(trace_item)
            yield {"type": "step", **trace_item}
        else:
            pool = get_key_pool()
            has_keys = bool(pool.get_all_keys())
            tools_spec = _tool_declarations(include_web_research=enable_web_research)

            if has_keys:
                for hop in range(max_hops + 1):
                    if cancel_event.is_set():
                        yield {"type": "error", "code": "cancelled", "message": "Request stopped."}
                        return

                    if total_tokens_turn >= turn_token_cap:
                        token_cap_reached = True
                        break

                    # Allow final synthesis hop without tools if we already hit max_hops
                    use_tools = hop < max_hops
                    remaining_turn_budget = max(2048, turn_token_cap - total_tokens_turn)
                    payload: dict[str, Any] = {
                        "system_instruction": {"parts": [{"text": _SCHEMA_SYSTEM_PROMPT}]},
                        "contents": contents,
                        "generationConfig": {"temperature": 0.2, "maxOutputTokens": min(8192, remaining_turn_budget)},
                    }
                    if use_tools:
                        payload["tools"] = tools_spec

                    raw_est_tok = max(400, len(json.dumps(payload, default=str)) // 4)
                    if raw_est_tok > max_input_tok or raw_est_tok > 220_000:
                        token_cap_reached = True
                        break
                    est_tok = raw_est_tok

                    hop_telemetry: list[dict[str, Any]] = []
                    status_q: queue.Queue[dict[str, Any]] = queue.Queue()
                    worker_result: dict[str, Any] = {}

                    def _run_orchestrated_hop() -> None:
                        try:
                            with orchestrator.acquire_turn_slot(
                                user_id=user_id,
                                estimated_tokens=est_tok,
                                cancel_event=cancel_event,
                                on_status=lambda st: status_q.put({"type": "queue_status", **st}),
                                max_wait_seconds=95.0,
                            ):
                                resp = gw.execute_gemini_request(
                                    payload=payload,
                                    estimated_tokens=est_tok,
                                    timeout_seconds=28.0,
                                    max_attempts=2,
                                    max_wait_seconds=95.0,
                                    purpose="copilot_agent",
                                    actor_user_id=user_id,
                                    priority=10,
                                    telemetry_log=hop_telemetry,
                                    allow_quota_raise=True,
                                    on_wait_cb=lambda st: status_q.put({"type": "queue_status", **st}),
                                    parse_fn=lambda d: d if (d.get("candidates") or []) else None,
                                )
                                worker_result["resp"] = resp
                        except BaseException as exc:
                            worker_result["exc"] = exc
                        finally:
                            status_q.put({"type": "_worker_done"})

                    t_hop = threading.Thread(target=_run_orchestrated_hop, daemon=True)
                    t_hop.start()
                    while True:
                        if cancel_event.is_set():
                            yield {"type": "error", "code": "cancelled", "message": "Request stopped."}
                            return
                        try:
                            evt = status_q.get(timeout=0.25)
                        except queue.Empty:
                            if not t_hop.is_alive():
                                break
                            continue
                        if evt.get("type") == "_worker_done":
                            break
                        yield evt
                    t_hop.join(timeout=1.0)

                    if "exc" in worker_result:
                        exc = worker_result["exc"]
                        if isinstance(exc, InterruptedError):
                            yield {"type": "error", "code": "cancelled", "message": "Request stopped."}
                            return
                        if isinstance(exc, QuotaExhaustedError):
                            logger.info("Copilot quota exhausted/paused: %s", exc)
                            raw_resp = None
                            if not final_markdown:
                                final_markdown, _ = _deterministic_offline_fallback_with_session(
                                    session_factory, cleaned_query, observed_rows
                                )
                            break
                        if isinstance(exc, TimeoutError):
                            raw_resp = None
                            if not final_markdown:
                                final_markdown = f"⚠️ **Queue wait timeout:** {exc}"
                            break
                        raise exc
                    raw_resp = worker_result.get("resp")

                    if hop_telemetry:
                        model_reply_telemetry.extend(hop_telemetry)
                        last_t = hop_telemetry[-1]
                        total_prompt_tokens += int(last_t.get("prompt_tokens", 0) or 0)
                        total_candidate_tokens += int(last_t.get("candidate_tokens", 0) or 0)
                        total_tokens_turn += int(last_t.get("total_tokens", 0) or 0)
                        last_model_used = last_t.get("model") or last_model_used

                    if not raw_resp:
                        break

                    candidates = raw_resp.get("candidates") or []
                    if not candidates:
                        break
                    model_content = candidates[0].get("content") or {}
                    parts = model_content.get("parts") or []
                    contents.append({"role": "model", "parts": parts})

                    function_calls = [p["functionCall"] for p in parts if isinstance(p, dict) and "functionCall" in p]
                    text_parts = [str(p.get("text") or "") for p in parts if isinstance(p, dict) and "text" in p]

                    if not function_calls:
                        final_markdown = "".join(text_parts).strip()
                        break

                    # Execute each tool call requested by Gemini inside a short-lived DB session
                    function_response_parts: list[dict[str, Any]] = []
                    for fc in function_calls:
                        if cancel_event.is_set():
                            yield {"type": "error", "code": "cancelled", "message": "Request stopped."}
                            return

                        fn_name = str(fc.get("name") or "")
                        fn_args = fc.get("args") if isinstance(fc.get("args"), dict) else {}
                        step_id = new_id()[:8]
                        step_label = str(fn_args.get("reason") or fn_name.replace("_", " ").title())

                        yield {
                            "type": "step",
                            "step_id": step_id,
                            "status": "running",
                            "tool": fn_name,
                            "label": step_label,
                        }

                        t_tool0 = time.perf_counter()
                        tool_out: dict[str, Any]
                        step_sql: str | None = None
                        step_rows: int | None = None
                        step_status = "done"

                        with session_factory() as tool_db:
                            tool_user = tool_db.get(User, user_id)
                            if fn_name == "bulk_check_plates":
                                arg_plates = fn_args.get("plates")
                                if extracted_plates and (
                                    bool(fn_args.get("use_user_message"))
                                    or len(extracted_plates) > (len(arg_plates) if isinstance(arg_plates, list) else 0)
                                ):
                                    raw_plates: Any = extracted_plates
                                else:
                                    raw_plates = arg_plates
                                try:
                                    bulk_out, matched_rows = _execute_bulk_check_plates(tool_db, raw_plates)
                                    observed_rows.extend(matched_rows)
                                    step_rows = int(bulk_out.get("total_checked") or 0)
                                    tool_out = bulk_out
                                except Exception as exc:
                                    step_status = "error"
                                    tool_out = {"error": str(exc)}

                            elif fn_name == "run_readonly_sql":
                                raw_sql = str(fn_args.get("sql") or "")
                                step_sql = raw_sql
                                try:
                                    sql_res = execute_readonly_sql(tool_db, raw_sql, max_rows=50)
                                    observed_rows.extend(sql_res["rows"])
                                    step_rows = sql_res["row_count"]
                                    tool_out = {
                                        "columns": sql_res["columns"],
                                        "rows": sql_res["rows"],
                                        "row_count": sql_res["row_count"],
                                        "truncated": sql_res["truncated"],
                                    }
                                except (SQLGuardError, Exception) as exc:
                                    step_status = "error"
                                    tool_out = {"error": str(exc), "hint": "Fix the SQL syntax or use only allowed ai_v_* views."}

                            elif fn_name == "export_sql_to_excel":
                                raw_sql = str(fn_args.get("sql") or "")
                                step_sql = raw_sql
                                fname = str(fn_args.get("filename") or "risklocker_export.xlsx")
                                sname = str(fn_args.get("sheet_name") or "Report")
                                try:
                                    if not tool_user:
                                        raise AppError("Unauthorized", 401)
                                    art, art_meta = export_sql_to_excel(
                                        tool_db,
                                        user=tool_user,
                                        thread_id=thread_id,
                                        message_id=None,
                                        sql=raw_sql,
                                        filename=fname,
                                        sheet_name=sname,
                                    )
                                    tool_db.commit()
                                    step_rows = int(art.row_count or 0)
                                    artifact_ids.append(str(art.id))
                                    artifacts_out.append(art)
                                    yield {"type": "artifact", "artifact": serialize_artifact(art)}
                                    tool_out = art_meta
                                except Exception as exc:
                                    tool_db.rollback()
                                    step_status = "error"
                                    tool_out = {"error": str(exc)}

                            elif fn_name == "get_comparison_matrix_detail":
                                tid = str(fn_args.get("tenure_id") or "").strip()
                                try:
                                    if not tool_user:
                                        raise AppError("Unauthorized", 401)
                                    from app.services.marketing_comparison_service import get_marketing_comparison

                                    comp_raw = get_marketing_comparison(tool_db, tid, tool_user, allow_commit=False)
                                    summary = _compact_comparison_summary(comp_raw)
                                    observed_rows.append(
                                        {
                                            "tenure_id": summary.get("tenure_id"),
                                            "vehicle_no": summary.get("vehicle_no"),
                                            "customer_name": summary.get("customer_name"),
                                        }
                                    )
                                    step_rows = len(summary.get("entries") or [])
                                    tool_out = summary
                                except Exception as exc:
                                    step_status = "error"
                                    tool_out = {"error": str(exc)}

                            elif fn_name == "calculate_road_tax_tool":
                                try:
                                    from app.services.road_tax_engine import calculate_road_tax_unified

                                    rt = calculate_road_tax_unified(
                                        capacity=str(fn_args.get("capacity") or "1500 CC"),
                                        vehicle_type=str(fn_args.get("vehicle_type") or "Car"),
                                        owner_type=str(fn_args.get("owner_type") or "Individual"),
                                        jurisdiction=str(fn_args.get("jurisdiction") or "West Malaysia"),
                                        db=tool_db,
                                    )
                                    tool_out = rt
                                except Exception as exc:
                                    step_status = "error"
                                    tool_out = {"error": str(exc)}

                            elif fn_name == "inspect_duplicate_sessions_or_catalog":
                                try:
                                    if not tool_user:
                                        raise AppError("Unauthorized", 401)
                                    from app.services.copilot_chat_service import (
                                        get_catalog_status_facts,
                                        get_session_hygiene_facts,
                                    )

                                    intent = str(fn_args.get("intent") or "duplicates").lower()
                                    cname = str(fn_args.get("company_name") or "").strip()
                                    if intent == "duplicates":
                                        sf = get_session_hygiene_facts(tool_db, tool_user)
                                        if sf.get("redundant_sessions_count", 0) > 0:
                                            action_cards.append(
                                                {
                                                    "type": "session_cleanup",
                                                    "title": f"Clean {sf['redundant_sessions_count']} Exact Duplicate Uploads",
                                                    "redundant_count": sf["redundant_sessions_count"],
                                                    "groups": sf.get("duplicate_groups", []),
                                                    "session_ids_to_trash": sf.get("redundant_session_ids", []),
                                                }
                                            )
                                        tool_out = {
                                            "total_active_sessions": sf.get("total_active_sessions"),
                                            "unique_car_plates": sf.get("unique_car_plates_count"),
                                            "redundant_sessions_count": sf.get("redundant_sessions_count"),
                                            "duplicate_sets": sf.get("exact_duplicate_sets_count"),
                                        }
                                    else:
                                        cf = get_catalog_status_facts(tool_db, None, cname or cleaned_query, None)
                                        tool_out = cf
                                except Exception as exc:
                                    step_status = "error"
                                    tool_out = {"error": str(exc)}

                            elif fn_name == "web_research" and enable_web_research:
                                q_str = str(fn_args.get("query") or cleaned_query)
                                web_tel: list[dict[str, Any]] = []
                                try:
                                    web_payload = {
                                        "contents": [{"role": "user", "parts": [{"text": f"Answer concisely with verified Malaysian automotive/insurance facts: {q_str}"}]}],
                                        "tools": [{"google_search": {}}],
                                        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 500},
                                    }
                                    web_txt = gw.execute_gemini_request(
                                        payload=web_payload,
                                        estimated_tokens=600,
                                        timeout_seconds=18.0,
                                        max_attempts=1,
                                        max_wait_seconds=10.0,
                                        purpose="copilot_web",
                                        actor_user_id=user_id,
                                        priority=15,
                                        telemetry_log=web_tel,
                                        allow_quota_raise=False,
                                        parse_fn=lambda d: (
                                            (((d.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [{}])[0]
                                            .get("text", "")
                                            .strip()
                                            or None
                                        ),
                                    )
                                    if web_tel:
                                        total_tokens_turn += int(web_tel[-1].get("total_tokens", 0) or 0)
                                    tool_out = {"answer": web_txt or "No web result returned."}
                                except Exception as exc:
                                    step_status = "error"
                                    tool_out = {"error": str(exc)}
                            else:
                                step_status = "error"
                                tool_out = {"error": f"Unknown or disabled tool: {fn_name}"}

                        elapsed_ms = int((time.perf_counter() - t_tool0) * 1000)
                        trace_item = {
                            "step_id": step_id,
                            "status": step_status,
                            "tool": fn_name,
                            "label": step_label,
                            "sql": step_sql,
                            "row_count": step_rows,
                            "elapsed_ms": elapsed_ms,
                        }
                        tool_trace.append(trace_item)
                        yield {"type": "step", **trace_item}

                        function_response_parts.append(
                            {
                                "functionResponse": {
                                    "name": fn_name,
                                    "response": tool_out,
                                }
                            }
                        )

                    contents.append({"role": "user", "parts": function_response_parts})

        if not final_markdown:
            if token_cap_reached and observed_rows:
                final_markdown = (
                    f"⚠️ **Per-turn token safety cap reached ({total_tokens_turn:,} / {turn_token_cap:,} tok).** "
                    "Showing verified records retrieved before the cap."
                )
            else:
                with session_factory() as fb_db:
                    final_markdown, _ = _deterministic_offline_fallback(fb_db, cleaned_query, observed_rows)
        elif token_cap_reached:
            final_markdown += (
                f"\n\n> **Note:** Stopped additional tool steps at per-turn token cap "
                f"({total_tokens_turn:,} / {turn_token_cap:,} tok)."
            )

        verified_links = _collect_verified_links(
            observed_rows,
            final_markdown=final_markdown,
            prefer_all_ledger_rows=prefer_all_ledger_rows,
        )
        if verified_links:
            yield {"type": "links", "links": verified_links}
        if action_cards:
            yield {"type": "actions", "actions": action_cards}

        # Stream answer progressively in natural chunks for responsive UX
        chunk_size = max(120, len(final_markdown) // 40)
        for i in range(0, len(final_markdown), chunk_size):
            if cancel_event.is_set():
                return
            yield {"type": "delta", "text": final_markdown[i : i + chunk_size]}

        # Step 3: Persist assistant message, link artifacts, update thread title/tokens, and auto-compact
        with session_factory() as db:
            thread = db.get(CopilotThread, thread_id)
            user_obj = db.get(User, user_id)
            if not thread or not user_obj:
                return

            a_msg = CopilotMessage(
                id=assistant_msg_id,
                thread_id=thread.id,
                role="assistant",
                content_markdown=final_markdown,
                tool_trace_json=tool_trace,
                verified_links_json=verified_links,
                action_cards_json=action_cards,
                prompt_tokens=total_prompt_tokens,
                candidate_tokens=total_candidate_tokens,
                total_tokens=total_tokens_turn,
                model_used=last_model_used,
            )
            db.add(a_msg)
            db.flush()

            attached_artifacts: list[CopilotArtifact] = []
            if artifact_ids:
                attached_artifacts = list(
                    db.scalars(select(CopilotArtifact).where(CopilotArtifact.id.in_(artifact_ids))).all()
                )
                for art in attached_artifacts:
                    art.message_id = a_msg.id

            if thread.title == "New Chat":
                thread.title = _derive_thread_title(cleaned_query, verified_links)
            thread.total_tokens = int(thread.total_tokens or 0) + total_tokens_turn
            thread.last_message_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(a_msg)
            db.refresh(thread)

            _maybe_compact_thread(db, thread=thread, user=user_obj, gateway=gw)
            updated_quota = get_user_copilot_quota(db, user_obj)

            yield {
                "type": "done",
                "thread": serialize_thread(thread, owner=user_obj),
                "message": serialize_message(a_msg, attached_artifacts),
                "quota": updated_quota,
            }
    finally:
        _clear_user_stream(user_id, cancel_event)


def _deterministic_offline_fallback_with_session(
    session_factory: Callable[[], Session],
    query: str,
    observed_rows: list[dict[str, Any]],
) -> tuple[str, list[dict[str, str]]]:
    with session_factory() as db:
        return _deterministic_offline_fallback(db, query, observed_rows)
