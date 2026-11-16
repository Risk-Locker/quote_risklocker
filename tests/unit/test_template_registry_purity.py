"""Unit tests for Milestone 1: Template Registry Purity and Admin API Filtering."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.master_template_service import master_template_specs
from app.models.tables import Base, OutputTemplateConfig, TemplateRevision, User, Role, new_id
from app.api.routers.templates import admin_templates


@pytest.fixture
def sqlite_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    session = TestingSessionLocal()
    yield session
    session.close()


def test_master_template_specs_active_returns_canonical():
    """Verify master_template_specs(active_only=True) returns only non-deprecated canonical templates."""
    active = master_template_specs(active_only=True)
    assert len(active) == 1
    assert active[0]["key"] == "agency_bilingual_v4"
    assert active[0]["is_deprecated"] is False


def test_admin_templates_sort_prefers_design2(sqlite_db):
    """Verify admin templates sorting places Design 2 first as primary default and excludes archived rows."""
    user = User(
        id=new_id(),
        email="admin@risklocker.local",
        name="Admin",
        password_hash="mock",
        role=Role.ADMIN.value,
    )
    sqlite_db.add(user)

    # Active Design 1 (Bilingual v4)
    t1 = OutputTemplateConfig(
        id="72af8553-b1ec-439c-ad71-5402d4f467a3",
        name="Bilingual Agency Motor v4",
        status="active",
        insurance_type="Motor",
        fixed_fields={"is_default": False, "v7_master_key": "agency_bilingual_v4"}
    )
    # Active Design 2
    t2 = OutputTemplateConfig(
        id="b78e2024-0002-4000-8000-000000000002",
        name="Design 2 (Modern 4-Column Grid)",
        status="active",
        insurance_type="Motor",
        fixed_fields={"is_default": True, "layout_engine": "design2", "v7_master_key": "motor_modern_design_2"}
    )
    # Archived / Deleted legacy ghost template
    t3 = OutputTemplateConfig(
        id="3832df1d-f56e-4ce2-bc08-e9477dd7380c",
        name="Bilingual Agency Motor v3",
        status="archived",
        insurance_type="Motor",
        fixed_fields={"is_default": False, "v7_master_key": "agency_bilingual_v3"}
    )

    sqlite_db.add_all([t1, t2, t3])
    sqlite_db.commit()

    res = admin_templates(db=sqlite_db, user=user)
    tmpls = res["templates"]
    
    # Exactly 2 active templates returned (t3 archived must be excluded)
    assert len(tmpls) == 2
    
    # Design 2 MUST be first
    assert tmpls[0]["id"] == "b78e2024-0002-4000-8000-000000000002"
    assert tmpls[0]["is_default"] is True
    assert "Design 2" in tmpls[0]["name"]
    
    # Bilingual v4 is second
    assert tmpls[1]["id"] == "72af8553-b1ec-439c-ad71-5402d4f467a3"
