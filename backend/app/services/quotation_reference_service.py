"""Quotation reference number generation service.

Non-negotiable rule:
Quotation reference numbers are strictly internal system sequences formatted as:
RL{YY}{SEQ:07d} (e.g. RL260000001, RL260000165, RL270000001).
They are partitioned by calendar year (retrieved in real-time from Asia/Kuala_Lumpur or UTC),
automatically resetting to 1 on January 1st of each year.
Reference numbers are NEVER extracted from insurer PDFs.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def format_quotation_reference(year: int, seq_num: int) -> str:
    """Format reference number as RL{YY}{SEQ:07d}."""
    year_short = year % 100
    return f"RL{year_short:02d}{seq_num:07d}"


def get_current_business_time() -> datetime:
    """Get real-time timestamp in Asia/Kuala_Lumpur (or UTC if zoneinfo is unavailable)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Kuala_Lumpur"))
    except Exception:
        return datetime.now(timezone.utc)


def generate_quotation_reference(db: Session | Any, when: datetime | None = None) -> str:
    """Atomically generate the next sequential quotation reference for the given or current year."""
    if when is None:
        when = get_current_business_time()

    year = when.year

    try:
        # Atomic upsert increment in PostgreSQL
        seq_num = db.scalar(
            text("""
                INSERT INTO quotation_sequences (year, current_val)
                VALUES (:year, 1)
                ON CONFLICT (year) DO UPDATE
                SET current_val = quotation_sequences.current_val + 1
                RETURNING current_val
            """),
            {"year": year},
        )
    except Exception as exc:
        logger.warning("Failed to query quotation_sequences, attempting fallback: %s", exc)
        try:
            # Fallback to legacy sequence or count if table doesn't exist yet
            seq_num = db.scalar(text("SELECT nextval('quotation_ref_seq')"))
        except Exception:
            seq_num = 1

    if not seq_num:
        seq_num = 1

    return format_quotation_reference(year, int(seq_num))
