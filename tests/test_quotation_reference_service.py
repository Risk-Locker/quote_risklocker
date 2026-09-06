"""Unit and contract tests for yearly sequential quotation reference numbers."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from typing import Any

from app.services.quotation_reference_service import (
    format_quotation_reference,
    generate_quotation_reference,
)


class FakeDb:
    def __init__(self, scalar_map: dict | None = None):
        self.scalar_map = scalar_map or {}
        self.executed_statements = []

    def scalar(self, statement, params=None):
        self.executed_statements.append((statement, params))
        year = (params or {}).get("year")
        if year in self.scalar_map:
            val = self.scalar_map[year]
            self.scalar_map[year] = val + 1
            return val
        return 1


def test_format_quotation_reference_exact_patterns():
    # 2026, session 1 -> RL260000001
    assert format_quotation_reference(2026, 1) == "RL260000001"
    # 2026, session 147 -> RL260000147
    assert format_quotation_reference(2026, 147) == "RL260000147"
    # 2026, session 165 -> RL260000165
    assert format_quotation_reference(2026, 165) == "RL260000165"
    # 2027, session 1 -> RL270000001 (year rollover resets sequence)
    assert format_quotation_reference(2027, 1) == "RL270000001"
    # 2030, session 42 -> RL300000042
    assert format_quotation_reference(2030, 42) == "RL300000042"


def test_generate_quotation_reference_increments_per_year():
    db: Any = FakeDb(scalar_map={2026: 1, 2027: 1})

    dt_2026 = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)
    dt_2027 = datetime(2027, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    # In 2026: session 1
    ref1 = generate_quotation_reference(db, when=dt_2026)
    assert ref1 == "RL260000001"

    # In 2026: session 2
    ref2 = generate_quotation_reference(db, when=dt_2026)
    assert ref2 == "RL260000002"

    # In 2027: rollover to session 1
    ref_2027 = generate_quotation_reference(db, when=dt_2027)
    assert ref_2027 == "RL270000001"


def test_generate_quotation_reference_uses_current_time_if_none():
    db: Any = FakeDb(scalar_map={2026: 100})
    ref = generate_quotation_reference(db, when=None)
    # Must start with RL followed by 2-digit year (e.g. RL26) and 7 digits
    assert ref.startswith("RL")
    assert len(ref) == 11
    assert ref[4:].isdigit()


def test_candidate_finder_does_not_extract_quotation_reference():
    from app.extraction.candidate_finder import find_candidates
    sample_text = "Quotation Ref: MPA-25-49-00274660\nQuotation No. QB413363-8-001\nVehicle No: WYY1234\nCustomer: John Doe"
    candidates = find_candidates(sample_text, [{"page": 1, "text": sample_text}])
    assert "quotation_reference" not in candidates
    assert "quotation_ref" not in candidates


def test_gemini_schema_excludes_quotation_reference():
    from app.extraction.gemini_extractor import GEMINI_EXTRACTION_SCHEMA
    props = GEMINI_EXTRACTION_SCHEMA["properties"]
    assert "quotation_reference" not in props
    assert "quotation_ref" not in props


def test_field_summary_preserves_session_quotation_reference():
    from app.models.tables import QuotationDraft
    from app.services.workspace_service import _field_summary

    draft = QuotationDraft(
        id="d1",
        revision=1,
        fields={"customer_name": {"value": "Alice", "status": "ready"}},
    )
    summary = _field_summary(draft, session_ref="RL260000147")
    assert summary["quotation_reference"]["value"] == "RL260000147"

