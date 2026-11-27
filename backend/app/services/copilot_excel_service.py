"""Zero-Token Excel Export Service for AI Copilot (streams SQL rows directly to openpyxl)."""

from __future__ import annotations

import hashlib
import re
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from app.core.workspace import QC_TEMP_ROOT
from app.models.tables import AuditEvent, CopilotArtifact, User, new_id
from app.services.copilot_sql_guard import execute_readonly_sql

COPILOT_EXPORTS_DIR = (QC_TEMP_ROOT / "copilot_exports").resolve()
COPILOT_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

_MONEY_COL_TOKENS = (
    "premium",
    "road_tax",
    "runner_fee",
    "total_payable",
    "sum_insured",
    "discount",
    "excess",
    "windscreen_sum_insured",
)


def _safe_filename(raw_name: str | None) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", (raw_name or "risklocker_export").strip()).strip("._")
    if not base:
        base = "risklocker_export"
    if not base.lower().endswith(".xlsx"):
        base = f"{base}.xlsx"
    return base[:120]


def _safe_sheet_name(raw_name: str | None) -> str:
    cleaned = re.sub(r"[\[\]:*?/\\]+", " ", (raw_name or "Report").strip())
    return (cleaned[:31] or "Report").strip()


def _sanitize_excel_cell(value: Any) -> Any:
    """Prevent CSV/Excel formula injection on untrusted string cells."""
    if value is None:
        return ""
    if isinstance(value, str):
        stripped = value.lstrip()
        if stripped and stripped[0] in ("=", "+", "-", "@"):
            return f"'{value}"
        return value
    return value


def _is_money_column(col_name: str) -> bool:
    low = col_name.lower()
    if low.endswith("_pct") or low.endswith("_percentage") or low.endswith("_rate"):
        return False
    return any(tok in low for tok in _MONEY_COL_TOKENS)


def _write_workbook_and_artifact(
    db: Session,
    *,
    user: User,
    thread_id: str,
    message_id: str | None,
    columns: list[str],
    rows: list[dict[str, Any]],
    filename: str,
    sheet_name: str,
    truncated: bool,
    elapsed_ms: int,
    sql_fingerprint: str,
) -> tuple[CopilotArtifact, dict[str, Any]]:
    """Render rows to a styled openpyxl .xlsx artifact and record audit metadata."""
    COPILOT_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = _safe_sheet_name(sheet_name)

    header_fill = PatternFill(start_color="111111", end_color="111111", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    body_font = Font(name="Calibri", size=10, color="111827")
    total_fill = PatternFill(start_color="F3F4F6", end_color="F3F4F6", fill_type="solid")
    total_font = Font(name="Calibri", size=10, bold=True, color="111111")

    money_cols = {idx for idx, c in enumerate(columns) if _is_money_column(c)}
    numeric_sums: dict[str, Decimal] = {c: Decimal("0.00") for idx, c in enumerate(columns) if idx in money_cols}

    # Header row
    for col_idx, col_name in enumerate(columns, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col_name.replace("_", " ").title())
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 24
    ws.freeze_panes = "A2"

    # Data rows
    for r_idx, row_dict in enumerate(rows, start=2):
        for c_idx, col_name in enumerate(columns, start=1):
            raw_val = row_dict.get(col_name)
            if (c_idx - 1) in money_cols and isinstance(raw_val, (int, float, Decimal)):
                dec_val = Decimal(str(raw_val)).quantize(Decimal("0.01"))
                numeric_sums[col_name] += dec_val
                cell = ws.cell(row=r_idx, column=c_idx, value=float(dec_val))
                cell.number_format = "#,##0.00"
                cell.alignment = Alignment(horizontal="right", vertical="center")
            else:
                cell = ws.cell(row=r_idx, column=c_idx, value=_sanitize_excel_cell(raw_val))
                cell.alignment = Alignment(horizontal="left", vertical="center")
            cell.font = body_font

    # Totals row if money columns exist and rows > 0
    last_data_row = len(rows) + 1
    if rows and money_cols:
        total_row_idx = last_data_row + 1
        for c_idx, col_name in enumerate(columns, start=1):
            cell = ws.cell(row=total_row_idx, column=c_idx)
            cell.fill = total_fill
            cell.font = total_font
            if c_idx == 1:
                cell.value = "TOTAL"
            elif (c_idx - 1) in money_cols:
                col_letter = get_column_letter(c_idx)
                cell.value = f"=SUM({col_letter}2:{col_letter}{last_data_row})"
                cell.number_format = "#,##0.00"
                cell.alignment = Alignment(horizontal="right", vertical="center")

    if columns and rows:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(columns))}{last_data_row}"

    # Auto-fit column widths cleanly
    for c_idx, col_name in enumerate(columns, start=1):
        max_len = len(col_name) + 3
        for r_dict in rows[:200]:
            val_str = str(r_dict.get(col_name) or "")
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[get_column_letter(c_idx)].width = max(12, min(42, max_len + 3))

    artifact_id = new_id()
    safe_name = _safe_filename(filename)
    file_path = (COPILOT_EXPORTS_DIR / f"{artifact_id}.xlsx").resolve()
    if not file_path.is_relative_to(COPILOT_EXPORTS_DIR):
        raise ValueError("Invalid artifact output path.")
    wb.save(str(file_path))
    size_bytes = file_path.stat().st_size

    totals_serialized = {k: float(v) for k, v in numeric_sums.items()}
    preview_payload = {
        "columns": columns,
        "rows": rows[:25],
        "totals": totals_serialized,
        "truncated": truncated,
        "elapsed_ms": elapsed_ms,
    }

    artifact = CopilotArtifact(
        id=artifact_id,
        thread_id=thread_id,
        message_id=message_id,
        owner_id=user.id,
        kind="xlsx",
        filename=safe_name,
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        row_count=len(rows),
        size_bytes=size_bytes,
        storage_path=str(file_path),
        preview_json=preview_payload,
        sql_fingerprint=sql_fingerprint,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(artifact)
    db.add(
        AuditEvent(
            actor_id=user.id,
            action="copilot.excel_export",
            entity_type="copilot_artifacts",
            entity_id=artifact_id,
            details={
                "filename": safe_name,
                "row_count": len(rows),
                "size_bytes": size_bytes,
                "sql_fingerprint": sql_fingerprint,
            },
        )
    )
    db.flush()

    llm_metadata = {
        "status": "ok",
        "artifact_id": artifact_id,
        "filename": safe_name,
        "row_count": len(rows),
        "size_bytes": size_bytes,
        "columns": columns,
        "totals": totals_serialized,
        "sample_rows": rows[:3],
        "download_url": f"/api/copilot/artifacts/{artifact_id}/download",
    }
    return artifact, llm_metadata


def export_rows_to_excel(
    db: Session,
    *,
    user: User,
    thread_id: str,
    message_id: str | None,
    columns: list[str],
    rows: list[dict[str, Any]],
    filename: str = "risklocker_bulk_check.xlsx",
    sheet_name: str = "Bulk Check",
) -> tuple[CopilotArtifact, dict[str, Any]]:
    """Export pre-computed tabular rows directly to a styled .xlsx artifact with zero LLM tokens."""
    t0 = time.perf_counter()
    fp = hashlib.sha256(f"{filename}:{len(rows)}:{','.join(columns)}".encode("utf-8")).hexdigest()[:16]
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    return _write_workbook_and_artifact(
        db,
        user=user,
        thread_id=thread_id,
        message_id=message_id,
        columns=columns,
        rows=rows,
        filename=filename,
        sheet_name=sheet_name,
        truncated=False,
        elapsed_ms=elapsed_ms,
        sql_fingerprint=fp,
    )


def export_sql_to_excel(
    db: Session,
    *,
    user: User,
    thread_id: str,
    message_id: str | None,
    sql: str,
    filename: str = "risklocker_report.xlsx",
    sheet_name: str = "Report",
    max_rows: int = 25_000,
) -> tuple[CopilotArtifact, dict[str, Any]]:
    """Execute read-only SQL and stream results directly to .xlsx without passing rows through LLM."""
    result = execute_readonly_sql(db, sql, max_rows=max_rows, timeout_ms=10_000)
    return _write_workbook_and_artifact(
        db,
        user=user,
        thread_id=thread_id,
        message_id=message_id,
        columns=result["columns"],
        rows=result["rows"],
        filename=filename,
        sheet_name=sheet_name,
        truncated=bool(result["truncated"]),
        elapsed_ms=int(result["elapsed_ms"]),
        sql_fingerprint=str(result["sql_fingerprint"]),
    )


def resolve_artifact_file_path(artifact: CopilotArtifact) -> Path | None:
    """Safely resolve an artifact file on disk inside COPILOT_EXPORTS_DIR."""
    if not artifact.storage_path:
        return None
    p = Path(artifact.storage_path).resolve()
    if not p.is_relative_to(COPILOT_EXPORTS_DIR):
        return None
    if not p.exists() or not p.is_file():
        return None
    return p
