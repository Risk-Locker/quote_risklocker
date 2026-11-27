"""Zero-dependency strict AST/lexer SQL Guard and Read-Only Semantic View executor for AI Copilot."""

from __future__ import annotations

import hashlib
import re
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

ALLOWED_AI_VIEWS: frozenset[str] = frozenset(
    {
        "ai_v_motor_ledger",
        "ai_v_comparison_quotes",
        "ai_v_vehicles_plates",
        "ai_v_clients_fleet",
        "ai_v_sessions",
        "ai_v_insurer_catalogs",
    }
)

FORBIDDEN_SQL_KEYWORDS: frozenset[str] = frozenset(
    {
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "GRANT",
        "REVOKE",
        "COPY",
        "EXECUTE",
        "CALL",
        "DO",
        "SET",
        "RESET",
        "VACUUM",
        "ANALYZE",
        "LOCK",
        "LISTEN",
        "NOTIFY",
        "PREPARE",
        "DEALLOCATE",
        "MERGE",
        "INTO",
        "RECURSIVE",
        "RETURNING",
        "PG_READ_FILE",
        "PG_READ_BINARY_FILE",
        "PG_LS_DIR",
        "PG_SLEEP",
        "PG_STAT_ACTIVITY",
        "PG_CATALOG",
        "INFORMATION_SCHEMA",
        "DBLINK",
        "LO_IMPORT",
        "LO_EXPORT",
        "USERS",
        "AUTH_SESSIONS",
        "AUTH_LOGIN_CODES",
        "APP_SETTINGS",
        "STORAGE_CONNECTIONS",
        "RATE_LIMIT_BUCKETS",
    }
)

_SQLITE_SEMANTIC_VIEW_DDL: tuple[str, ...] = (
    """
    CREATE VIEW IF NOT EXISTS ai_v_motor_ledger AS
    SELECT
        t.id AS tenure_id,
        t.tracked_vehicle_id,
        COALESCE(NULLIF(TRIM(t.vehicle_no), ''), v.vehicle_no) AS vehicle_no,
        t.customer_id,
        t.customer_name,
        v.car_brand,
        v.car_model,
        v.engine_cc,
        v.manufacture_year,
        v.chassis_no,
        t.coverage_start_date,
        t.coverage_end_date,
        t.expiry_month,
        CAST(strftime('%Y', t.coverage_start_date) AS INTEGER) AS policy_year,
        t.stage,
        t.status,
        t.business_type,
        ic.name AS winning_company,
        t.winning_quotation_ref,
        t.won_premium,
        t.road_tax,
        t.runner_fee,
        t.include_road_tax,
        t.include_runner_fee,
        t.ncd_percentage,
        t.motor_discount_pct,
        t.quotation_discount,
        pic.name AS pic_name,
        pic.type AS pic_type,
        pic.agency_group,
        t.sub_agent_name,
        t.loss_reason_category,
        t.miss_reason,
        t.policy_number,
        t.covernote_session_id,
        t.is_projected,
        t.is_hidden,
        t.client_payment_received,
        t.agency_payment_done,
        t.key_in_ucd,
        t.print_roadtax,
        t.comment,
        t.created_at,
        t.updated_at
    FROM insurance_tenures t
    LEFT JOIN tracked_vehicles v ON v.id = t.tracked_vehicle_id
    LEFT JOIN person_in_charge pic ON pic.id = t.pic_id
    LEFT JOIN insurance_companies ic ON ic.id = t.winning_company_id
    WHERE t.deleted_at IS NULL
      AND t.is_discarded = 0
    """,
    """
    CREATE VIEW IF NOT EXISTS ai_v_comparison_quotes AS
    SELECT
        e.id AS entry_id,
        e.tenure_id,
        e.session_id,
        COALESCE(NULLIF(TRIM(t.vehicle_no), ''), v.vehicle_no) AS vehicle_no,
        t.customer_name,
        v.car_brand,
        v.car_model,
        t.coverage_start_date,
        t.coverage_end_date,
        t.expiry_month,
        CAST(strftime('%Y', t.coverage_start_date) AS INTEGER) AS policy_year,
        t.stage AS tenure_stage,
        e.company_name,
        e.sum_insured,
        e.valuation_type,
        e.motor_premium,
        e.road_tax,
        e.runner_fee,
        e.total_payable,
        e.discount,
        e.towing_limit,
        e.towing_km,
        e.agreed_value,
        e.waiver_betterment,
        e.betterment_rate,
        e.betterment_display,
        e.excess,
        e.rate_percentage,
        e.windscreen_sum_insured,
        e.special_perils,
        e.llp,
        e.llop,
        e.llp_llop,
        e.personal_accident,
        e.rank,
        e.manual_rank,
        e.is_recommended,
        e.is_manual,
        e.notes,
        e.uploaded_at
    FROM tenure_comparison_entries e
    JOIN insurance_tenures t ON t.id = e.tenure_id
    LEFT JOIN tracked_vehicles v ON v.id = t.tracked_vehicle_id
    WHERE t.deleted_at IS NULL
      AND t.is_discarded = 0
      AND e.is_hidden = 0
    """,
    """
    CREATE VIEW IF NOT EXISTS ai_v_vehicles_plates AS
    SELECT
        v.id AS tracked_vehicle_id,
        v.vehicle_no,
        ph.plate_no AS historical_plate_no,
        ph.effective_from AS plate_effective_from,
        ph.effective_to AS plate_effective_to,
        v.car_brand,
        v.car_model,
        v.engine_cc,
        v.manufacture_year,
        v.chassis_no,
        v.customer_id,
        ca.canonical_name AS customer_name,
        ca.entity_type,
        COALESCE(ca.is_fleet, 0) AS is_fleet
    FROM tracked_vehicles v
    LEFT JOIN customer_accounts ca ON ca.id = v.customer_id
    LEFT JOIN vehicle_plate_history ph ON ph.tracked_vehicle_id = v.id
    """,
    """
    CREATE VIEW IF NOT EXISTS ai_v_clients_fleet AS
    SELECT
        ca.id AS customer_id,
        ca.canonical_name,
        ca.entity_type,
        ca.id_type,
        CASE
            WHEN ca.id_number IS NULL OR LENGTH(ca.id_number) <= 4 THEN '****'
            ELSE '******-**-' || SUBSTR(ca.id_number, LENGTH(ca.id_number) - 3, 4)
        END AS masked_id_number,
        ca.phone,
        ca.email,
        ca.is_fleet,
        COUNT(DISTINCT tv.id) AS vehicle_count,
        COUNT(DISTINCT CASE WHEN t.deleted_at IS NULL AND t.is_discarded = 0 THEN t.id END) AS tenure_count,
        COUNT(DISTINCT CASE WHEN t.deleted_at IS NULL AND t.is_discarded = 0 AND t.stage = 'Hit' THEN t.id END) AS active_hit_count,
        ca.created_at
    FROM customer_accounts ca
    LEFT JOIN tracked_vehicles tv ON tv.customer_id = ca.id
    LEFT JOIN insurance_tenures t ON t.customer_id = ca.id
    GROUP BY ca.id, ca.canonical_name, ca.entity_type, ca.id_type, ca.id_number, ca.phone, ca.email, ca.is_fleet, ca.created_at
    """,
    """
    CREATE VIEW IF NOT EXISTS ai_v_sessions AS
    SELECT
        s.id AS session_id,
        s.draft_id,
        s.tenure_id,
        s.tracked_vehicle_id,
        s.customer_id,
        s.document_type,
        s.detected_company,
        s.quotation_ref,
        s.quotation_status,
        s.status,
        s.policy_number,
        s.coverage_start_date,
        s.coverage_end_date,
        uf.original_filename AS filename,
        s.created_at
    FROM sessions s
    JOIN quotation_drafts d ON d.id = s.draft_id
    JOIN uploaded_files uf ON uf.id = s.uploaded_file_id
    WHERE d.deleted_at IS NULL
      AND uf.deleted_at IS NULL
      AND s.is_test = 0
    """,
    """
    CREATE VIEW IF NOT EXISTS ai_v_insurer_catalogs AS
    SELECT
        ic.name AS company_name,
        bc.name AS catalog_name,
        bc.engine_type,
        con.concept_key,
        con.label AS concept_label,
        co.offering_kind,
        co.role,
        co.display_value,
        co.description_override,
        con.description AS concept_description
    FROM benefit_catalogs bc
    JOIN insurance_companies ic ON ic.id = bc.company_id
    JOIN benefit_catalog_revisions bcr ON bcr.catalog_id = bc.id
    JOIN catalog_offerings co ON co.catalog_revision_id = bcr.id
    JOIN benefit_concepts con ON con.id = co.concept_id
    WHERE bcr.state = 'published'
      AND bcr.is_archived = 0
      AND co.status = 'active'
    """,
)

_RO_ENGINE_CACHE: dict[str, Any] = {}


class SQLGuardError(ValueError):
    """Raised when an AI-generated SQL query violates read-only or semantic-view constraints."""


def _strip_comments_and_tokenize(sql: str) -> tuple[str, list[tuple[str, str]]]:
    """Strip SQL comments safely while preserving string literals, and return (clean_sql, tokens)."""
    n = len(sql)
    i = 0
    out_chars: list[str] = []
    tokens: list[tuple[str, str]] = []

    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""

        # Line comment -- ...
        if ch == "-" and nxt == "-":
            i += 2
            while i < n and sql[i] != "\n":
                i += 1
            out_chars.append(" ")
            continue

        # Block comment /* ... */
        if ch == "/" and nxt == "*":
            depth = 1
            i += 2
            while i < n and depth > 0:
                if sql[i] == "/" and i + 1 < n and sql[i + 1] == "*":
                    depth += 1
                    i += 2
                elif sql[i] == "*" and i + 1 < n and sql[i + 1] == "/":
                    depth -= 1
                    i += 2
                else:
                    i += 1
            if depth > 0:
                raise SQLGuardError("Unterminated block comment in SQL query.")
            out_chars.append(" ")
            continue

        # Single-quoted string literal '...'
        if ch == "'":
            start = i
            i += 1
            while i < n:
                if sql[i] == "'":
                    if i + 1 < n and sql[i + 1] == "'":
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            else:
                raise SQLGuardError("Unterminated string literal in SQL query.")
            lit = sql[start:i]
            out_chars.append(lit)
            tokens.append(("STRING", lit))
            continue

        # Dollar-quoted strings $$...$$ are forbidden (PL/pgSQL smuggling vector)
        if ch == "$":
            raise SQLGuardError("Dollar-quoted strings or positional parameters ($) are not allowed.")

        # Double-quoted identifier "..."
        if ch == '"':
            start = i
            i += 1
            while i < n:
                if sql[i] == '"':
                    if i + 1 < n and sql[i + 1] == '"':
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            else:
                raise SQLGuardError("Unterminated quoted identifier in SQL query.")
            ident = sql[start:i]
            out_chars.append(ident)
            tokens.append(("IDENT", ident[1:-1].replace('""', '"')))
            continue

        # Semicolon check outside literals
        if ch == ";":
            rest = sql[i + 1 :].strip()
            if rest:
                raise SQLGuardError("Multiple SQL statements are not allowed.")
            i += 1
            continue

        # Punctuation / operators
        if ch in "(),.*+-/<>=!|":
            out_chars.append(ch)
            tokens.append(("PUNCT", ch))
            i += 1
            continue

        if ch.isspace():
            out_chars.append(ch)
            i += 1
            continue

        # Word / number token
        if ch.isalnum() or ch == "_":
            start = i
            while i < n and (sql[i].isalnum() or sql[i] in "_"):
                i += 1
            word = sql[start:i]
            out_chars.append(word)
            kind = "NUMBER" if word.isdigit() else "WORD"
            tokens.append((kind, word))
            continue

        raise SQLGuardError(f"Unsupported character in SQL query: {ch!r}")

    clean_sql = "".join(out_chars).strip()
    return clean_sql, tokens


def _extract_cte_names(tokens: list[tuple[str, str]]) -> set[str]:
    """Collect CTE names declared in top-level WITH clauses."""
    ctes: set[str] = set()
    if not tokens or tokens[0][1].upper() != "WITH":
        return ctes

    i = 1
    n = len(tokens)
    while i < n:
        kind, val = tokens[i]
        if kind in ("WORD", "IDENT"):
            cte_name = val.lower()
            # Peek ahead for optional column list (...) then AS (
            j = i + 1
            if j < n and tokens[j] == ("PUNCT", "("):
                depth = 1
                j += 1
                while j < n and depth > 0:
                    if tokens[j] == ("PUNCT", "("):
                        depth += 1
                    elif tokens[j] == ("PUNCT", ")"):
                        depth -= 1
                    j += 1
            if j < n and tokens[j][0] == "WORD" and tokens[j][1].upper() == "AS":
                ctes.add(cte_name)
                j += 1
                if j < n and tokens[j] == ("PUNCT", "("):
                    depth = 1
                    j += 1
                    while j < n and depth > 0:
                        if tokens[j] == ("PUNCT", "("):
                            depth += 1
                        elif tokens[j] == ("PUNCT", ")"):
                            depth -= 1
                        j += 1
                    i = j
                    if i < n and tokens[i] == ("PUNCT", ","):
                        i += 1
                        continue
                    break
        i += 1
    return ctes


def validate_readonly_sql(sql: str, *, max_rows: int = 50) -> str:
    """Validate that SQL is a single read-only SELECT/WITH over ALLOWED_AI_VIEWS and enforce row cap."""
    raw = (sql or "").strip()
    if not raw:
        raise SQLGuardError("SQL query cannot be empty.")
    if len(raw) > 8_000:
        raise SQLGuardError("SQL query exceeds 8,000 character limit.")

    clean_sql, tokens = _strip_comments_and_tokenize(raw)
    if not tokens:
        raise SQLGuardError("SQL query contains no executable tokens.")

    first_word = tokens[0][1].upper() if tokens[0][0] == "WORD" else ""
    if first_word not in {"SELECT", "WITH"}:
        raise SQLGuardError("Only read-only SELECT or WITH queries are permitted.")

    for kind, val in tokens:
        if kind in {"WORD", "IDENT"}:
            upper = val.upper()
            if upper in FORBIDDEN_SQL_KEYWORDS:
                raise SQLGuardError(f"Forbidden SQL keyword or restricted table: {upper}")

    cte_names = _extract_cte_names(tokens)

    # Validate every table reference following FROM or JOIN
    n = len(tokens)
    for i, (kind, val) in enumerate(tokens):
        if kind != "WORD":
            continue
        kw = val.upper()
        if kw not in {"FROM", "JOIN"}:
            continue

        # Look ahead for source token(s)
        j = i + 1
        if j >= n:
            raise SQLGuardError(f"Incomplete {kw} clause.")
        # Derived subquery: FROM (SELECT ...) -> inner SELECT's own FROM/JOIN will be validated too
        if tokens[j] == ("PUNCT", "("):
            continue

        # Support optional schema prefix `public.ai_v_...`
        first_tok = tokens[j]
        if first_tok[0] not in {"WORD", "IDENT"}:
            raise SQLGuardError(f"Invalid table reference after {kw}.")
        table_name = first_tok[1].lower()
        if j + 2 < n and tokens[j + 1] == ("PUNCT", ".") and tokens[j + 2][0] in {"WORD", "IDENT"}:
            schema_name = table_name
            if schema_name != "public":
                raise SQLGuardError(f"Access to schema '{schema_name}' is not allowed.")
            table_name = tokens[j + 2][1].lower()

        if table_name not in ALLOWED_AI_VIEWS and table_name not in cte_names:
            raise SQLGuardError(
                f"Table or view '{table_name}' is not in the allowed AI semantic views: {sorted(ALLOWED_AI_VIEWS)}"
            )

    safe_limit = max(1, min(int(max_rows), 25_000))
    return f"SELECT * FROM ({clean_sql}) AS _ai_q LIMIT {safe_limit}"


def ensure_semantic_views(db: Session) -> None:
    """Ensure SQLite test databases have the 6 ai_v_* semantic views defined."""
    bind = getattr(db, "bind", None) or (db.get_bind() if hasattr(db, "get_bind") else None)
    dialect_name = getattr(getattr(bind, "dialect", None), "name", "")
    if dialect_name != "sqlite":
        return
    for ddl in _SQLITE_SEMANTIC_VIEW_DDL:
        db.execute(text(ddl))


def _serialize_cell(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (int, float, bool, str)):
        return value
    return str(value)


def _get_readonly_pg_engine(url: str):
    eng = _RO_ENGINE_CACHE.get(url)
    if eng is None:
        eng = create_engine(url, poolclass=NullPool, pool_pre_ping=True)
        _RO_ENGINE_CACHE[url] = eng
    return eng


def execute_readonly_sql(
    db: Session,
    sql: str,
    *,
    max_rows: int = 50,
    timeout_ms: int = 5_000,
) -> dict[str, Any]:
    """Validate and execute a strictly read-only SQL query over the 6 ai_v_* semantic views."""
    safe_sql = validate_readonly_sql(sql, max_rows=max_rows)
    fingerprint = hashlib.sha256(safe_sql.encode("utf-8")).hexdigest()[:16]
    settings = get_settings()
    ro_url = getattr(settings, "ai_readonly_database_url", "") or ""

    bind = getattr(db, "bind", None) or (db.get_bind() if hasattr(db, "get_bind") else None)
    dialect_name = getattr(getattr(bind, "dialect", None), "name", "")

    t0 = time.perf_counter()
    if dialect_name == "postgresql" and ro_url:
        eng = _get_readonly_pg_engine(ro_url)
        with eng.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            conn.execute(text("SELECT set_config('statement_timeout', :timeout_ms, true)"), {"timeout_ms": str(int(timeout_ms))})
            result = conn.exec_driver_sql(safe_sql)
            columns = list(result.keys())
            raw_rows = result.fetchall()
            conn.rollback()
    elif dialect_name == "postgresql":
        with db.begin_nested():
            db.execute(text("SET TRANSACTION READ ONLY"))
            db.execute(text("SELECT set_config('statement_timeout', :timeout_ms, true)"), {"timeout_ms": str(int(timeout_ms))})
            result = db.execute(text(safe_sql))
            columns = list(result.keys())
            raw_rows = result.fetchall()
    else:
        ensure_semantic_views(db)
        result = db.execute(text(safe_sql))
        columns = list(result.keys())
        raw_rows = result.fetchall()

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    rows: list[dict[str, Any]] = [
        {col: _serialize_cell(row[idx]) for idx, col in enumerate(columns)}
        for row in raw_rows
    ]
    return {
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "truncated": len(rows) >= max_rows,
        "elapsed_ms": elapsed_ms,
        "executed_sql": safe_sql,
        "sql_fingerprint": fingerprint,
    }
