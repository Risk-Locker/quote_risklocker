"""Tests for Lightweight AI Grounding Assistant and Targeted DB Retrieval."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.models.tables import BenefitConcept, InsuranceCompany
from app.services.grounding_assistant import _extract_potential_plates, answer_grounding_query


def test_extract_potential_plates():
    plates = _extract_potential_plates("Tell me about vehicle VG9XXX and WYY1234 please")
    assert "VG9XXX" in plates
    assert "WYY1234" in plates

    single_plate = _extract_potential_plates("What is the status of VAA8888?")
    assert "VAA8888" in single_plate


def test_answer_grounding_query_empty():
    mock_db = MagicMock()
    result = answer_grounding_query(mock_db, "")
    assert "Please ask a question" in result["reply"]
    assert result["tokens_used"] == 0


def test_answer_grounding_query_summary():
    mock_db = MagicMock()
    # Mock companies
    mock_companies = [
        InsuranceCompany(id="comp-1", name="QBE", slug="qbe"),
        InsuranceCompany(id="comp-2", name="Etiqa", slug="etiqa"),
    ]
    mock_concepts = [
        BenefitConcept(id="con-1", concept_key="wndscrn", label="Windscreen Coverage"),
    ]
    mock_db.scalars.return_value.all.side_effect = [
        mock_companies,  # for InsuranceCompany
        mock_concepts,   # for BenefitConcept
    ]
    mock_db.scalar.return_value = 5  # for count queries

    result = answer_grounding_query(mock_db, "How much info you gathered so far?")
    assert "reply" in result
    assert len(result["reply"]) > 0
    assert "sources" in result
    assert any("Grounding" in s or "System" in s for s in result["sources"])
