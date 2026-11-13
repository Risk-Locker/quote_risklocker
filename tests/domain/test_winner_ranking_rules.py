"""Unit tests for the STMB vs Amgen RM 40 Towing-Advantage Ranking Rule."""

from __future__ import annotations

from decimal import Decimal
import pytest

from app.domain.motor.winner_ranking_rules import apply_towing_advantage_rule


class MockEntry:
    def __init__(self, company_name: str, total_payable: Decimal | float, towing: str, rank: int = 1, is_recommended: bool = False):
        self.company_name = company_name
        self.total_payable = Decimal(str(total_payable))
        self.towing_km = towing
        self.towing_limit = towing
        self.rank = rank
        self.manual_rank = None
        self.is_recommended = is_recommended
        self.is_hidden = False
        self.recommendation_reason = ""


def test_amgen_wins_when_difference_is_exactly_40():
    stmb = MockEntry("Syarikat Takaful Malaysia Am Berhad", 1200.00, "50km")
    amgen = MockEntry("AmAssurance", 1240.00, "365km")
    entries = [stmb, amgen]

    result = apply_towing_advantage_rule(entries)
    assert result[0].company_name == "AmAssurance"
    assert result[0].is_recommended is True
    assert "365km Towing" in result[0].recommendation_reason
    assert result[1].company_name == "Syarikat Takaful Malaysia Am Berhad"


def test_amgen_wins_when_difference_is_under_40():
    stmb = MockEntry("STMB", 1200.00, "100km")
    amgen = MockEntry("Amgen", 1225.50, "365km")
    entries = [stmb, amgen]

    result = apply_towing_advantage_rule(entries)
    assert result[0].company_name == "Amgen"
    assert result[0].is_recommended is True


def test_stmb_wins_when_difference_exceeds_40():
    stmb = MockEntry("STMB", 1200.00, "50km")
    amgen = MockEntry("AmAssurance", 1240.05, "365km")  # 5 cents over RM 40
    entries = [stmb, amgen]

    result = apply_towing_advantage_rule(entries)
    assert result[0].company_name == "STMB"
    assert result[1].company_name == "AmAssurance"


def test_rule_does_not_apply_if_amgen_lacks_365km():
    stmb = MockEntry("STMB", 1200.00, "50km")
    amgen = MockEntry("AmAssurance", 1215.00, "100km")  # Only 100km, not 365km
    entries = [stmb, amgen]

    result = apply_towing_advantage_rule(entries)
    assert result[0].company_name == "STMB"

