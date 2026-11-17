"""Unit tests for Logical Underwriter Reranker, Reasoning Badges & Deep System Diagnostics."""

from __future__ import annotations

from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.domain.motor.winner_ranking_rules import (
    build_underwriter_ranking_explanation,
    evaluate_logical_value_rerank,
)
from app.models.tables import Base
from app.services.system_checks import get_deep_system_diagnostics


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_logical_value_reranker_promotes_superior_coverage_within_threshold():
    bare_cheapest = SimpleNamespace(
        id="e-etiqa",
        company_name="Etiqa",
        total_payable=1420.00,
        agreed_value=False,
        valuation_type="market_value",
        towing_km="200 km",
        towing_limit="200 km",
        excess=400.00,
        waiver_betterment=False,
        betterment_rate=20.0,
        special_perils="",
        manual_rank=None,
        is_hidden=False,
        rank=1,
        notes=None,
    )
    superior_qbe = SimpleNamespace(
        id="e-qbe",
        company_name="QBE",
        total_payable=1452.00,
        agreed_value=True,
        valuation_type="agreed_value",
        towing_km="Unlimited",
        towing_limit="Unlimited",
        excess=0.00,
        waiver_betterment=True,
        betterment_rate=0.0,
        special_perils="Included",
        manual_rank=None,
        is_hidden=False,
        rank=2,
        notes=None,
    )

    ranked = evaluate_logical_value_rerank([bare_cheapest, superior_qbe])
    assert ranked[0].company_name == "QBE"
    assert ranked[0].rank == 1
    assert "Ranked #1 (Best Value Logic)" in ranked[0].notes
    assert "Agreed Value" in ranked[0].notes

    assert ranked[1].company_name == "Etiqa"
    assert ranked[1].rank == 2
    assert "Ranked #2 (Lowest Price)" in ranked[1].notes


def test_deep_system_diagnostics_executes_all_probes_and_sitemap(db_session: Session):
    class DummySettings:
        gemini_model = "gemini-3.1-flash-lite"

    diag = get_deep_system_diagnostics(DummySettings(), db_session)
    assert "domain_logic_checks" in diag
    assert "sitemap_routes" in diag
    assert "database_summary" in diag
    assert len(diag["sitemap_routes"]) == 12

    by_name = {c["name"]: c for c in diag["domain_logic_checks"]}
    assert by_name["JPJ Road Tax Engine (ICE CC & 2026 ZEV EV kW)"]["status"] == "Ready"
    assert by_name["Exact Calendar Betterment & 7-Insurer Underwriting Engine"]["status"] == "Ready"
    assert by_name["Logical Underwriter Value Reranker & BNM 5¢ Rounding"]["status"] == "Ready"
    assert by_name["Design 2 8K Ultra-HD Brand & QR Asset Resolution"]["status"] == "Ready"
