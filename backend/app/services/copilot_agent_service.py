"""Enterprise Agentic AI Copilot Orchestrator (ReAct Loop + Function Calling + Compaction + Verified Links)."""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Generator
from urllib.parse import quote

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.tables import (
    CopilotArtifact,
    CopilotMessage,
    CopilotThread,
    GeminiApiCallLog,
    User,
    new_id,
)
from app.services.ai_fleet_gateway import (
    QuotaExhaustedError,
    get_copilot_quota_policy,
    get_fleet_gateway,
)
from app.services.copilot_excel_service import export_sql_to_excel
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
- **Plate matching**: Always normalize spaces/case with `REPLACE(UPPER(vehicle_no), ' ', '') ILIKE '%88%'` (or `LIKE` in SQLite).
- **Multi-year ambiguity**: If the user asks about a car/plate without specifying a year and multiple `policy_year` tenures exist, briefly analyze ALL years on record (e.g., 2025 vs 2026) using `get_comparison_matrix_detail` or SQL, highlight the key YoY difference, and naturally ask which year they want to inspect further or act on.
- **Zero-Token Excel**: When the user asks for an Excel report, workbook, or full list export, write ONE clean SQL query and call `export_sql_to_excel`. Never attempt to print hundreds of rows in chat text.
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
    """Return current user's today Copilot turn/token usage and fleet availability."""
    policy = get_copilot_quota_policy(db)
    is_admin = user.role in ("super_admin", "admin", "dev")
    turns_limit = policy["admin_daily_turns"] if is_admin else policy["staff_daily_turns"]
    tokens_limit = policy["admin_daily_tokens"] if is_admin else policy["staff_daily_tokens"]

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


def serialize_thread(t: CopilotThread) -> dict[str, Any]:
    return {
        "id": str(t.id),
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


def _collect_verified_links(rows: list[dict[str, Any]], max_links: int = 8) -> list[dict[str, str]]:
    """Build verified UI navigation chips strictly from real IDs observed in SQL/tool outputs."""
    links: list[dict[str, str]] = []
    seen_hrefs: set[str] = set()

    def _add(kind: str, label: str, href: str) -> None:
        if len(links) >= max_links or href in seen_hrefs:
            return
        seen_hrefs.add(href)
        links.append({"kind": kind, "label": label[:64], "href": href})

    for row in rows:
        tenure_id = row.get("tenure_id")
        session_id = row.get("session_id")
        covernote_sid = row.get("covernote_session_id")
        plate = str(row.get("vehicle_no") or "").strip()
        year = row.get("policy_year")
        customer = str(row.get("customer_name") or row.get("canonical_name") or "").strip()

        yr_suffix = f" ({year})" if year else ""
        tag = plate or customer or "Record"

        if tenure_id:
            comp_href = f"/comparison?tenure_id={tenure_id}"
            _add("comparison", f"Compare {tag}{yr_suffix}", comp_href)
            if plate:
                ledger_href = f"/ledger?search={quote(plate)}&highlight={tenure_id}"
            else:
                ledger_href = f"/ledger?highlight={tenure_id}"
            _add("ledger", f"Ledger: {tag}{yr_suffix}", ledger_href)
        elif plate:
            _add("ledger", f"Ledger: {plate}", f"/ledger?search={quote(plate)}")

        eff_sid = session_id or covernote_sid
        if eff_sid:
            _add("session", f"Workspace: {tag}{yr_suffix}", f"/sessions/{eff_sid}/review")

        if customer and not tenure_id and not eff_sid:
            _add("client", f"Client: {customer}", f"/client-records?search={quote(customer)}")

    return links


def _tool_declarations(*, include_web_research: bool) -> list[dict[str, Any]]:
    decls: list[dict[str, Any]] = [
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

            yield {"type": "thread", "thread": serialize_thread(thread)}

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

        # Step 2: Autonomous ReAct Loop (outside long DB transaction!)
        pool = get_key_pool()
        has_keys = bool(pool.get_all_keys())
        tools_spec = _tool_declarations(include_web_research=enable_web_research)
        final_markdown = ""
        model_reply_telemetry: list[dict[str, Any]] = []

        if has_keys:
            for hop in range(max_hops + 1):
                if cancel_event.is_set():
                    yield {"type": "error", "code": "cancelled", "message": "Request stopped."}
                    return

                # Allow final synthesis hop without tools if we already hit max_hops
                use_tools = hop < max_hops
                payload: dict[str, Any] = {
                    "system_instruction": {"parts": [{"text": _SCHEMA_SYSTEM_PROMPT}]},
                    "contents": contents,
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1200},
                }
                if use_tools:
                    payload["tools"] = tools_spec

                est_tok = min(max_input_tok, max(400, len(json.dumps(payload, default=str)) // 4))
                if est_tok > max_input_tok:
                    break

                hop_telemetry: list[dict[str, Any]] = []
                try:
                    raw_resp = gw.execute_gemini_request(
                        payload=payload,
                        estimated_tokens=est_tok,
                        timeout_seconds=22.0,
                        max_attempts=2,
                        max_wait_seconds=12.0,
                        purpose="copilot_agent",
                        actor_user_id=user_id,
                        priority=10,
                        telemetry_log=hop_telemetry,
                        allow_quota_raise=True,
                        parse_fn=lambda d: d if (d.get("candidates") or []) else None,
                    )
                except QuotaExhaustedError as qerr:
                    logger.info("Copilot quota exhausted/paused: %s", qerr)
                    raw_resp = None
                    if not final_markdown:
                        final_markdown, _ = _deterministic_offline_fallback_with_session(
                            session_factory, cleaned_query, observed_rows
                        )
                    break

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
                        if fn_name == "run_readonly_sql":
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
            with session_factory() as fb_db:
                final_markdown, _ = _deterministic_offline_fallback(fb_db, cleaned_query, observed_rows)

        verified_links = _collect_verified_links(observed_rows)
        if verified_links:
            yield {"type": "links", "links": verified_links}
        if action_cards:
            yield {"type": "actions", "actions": action_cards}

        # Stream answer progressively in natural chunks for responsive UX
        chunk_size = 90
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
                "thread": serialize_thread(thread),
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
