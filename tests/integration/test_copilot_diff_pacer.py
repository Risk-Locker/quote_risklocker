"""Integration tests for Copilot catalog diff tools and PacerSentinel wiring (Task 4.2)."""

import sys
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.api.routers.copilot import router as copilot_router
from app.api.deps import current_user
from app.core.errors import register_error_handlers
from app.db.session import get_db
from app.models.tables import (
    Base,
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    CatalogOffering,
    InsuranceCompany,
    Role,
    User,
    new_id,
)


@pytest.fixture
def copilot_test_env():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    session = TestingSessionLocal()

    admin_user = User(
        id=new_id(),
        email="admin@risklocker.local",
        name="Admin User",
        password_hash="mock",
        role=Role.ADMIN.value,
    )
    session.add(admin_user)

    qbe = InsuranceCompany(id=new_id(), name="QBE Insurance", slug="qbe", status="active")
    allianz = InsuranceCompany(id=new_id(), name="Allianz General", slug="allianz", status="active")
    session.add_all([qbe, allianz])
    session.flush()

    c_towing = BenefitConcept(id=new_id(), concept_key="towing", label="Emergency Towing Assistance")
    session.add(c_towing)
    session.flush()

    cat_qbe = BenefitCatalog(id=new_id(), company_id=qbe.id, name="QBE Motor", revision=1)
    session.add(cat_qbe)
    session.flush()
    rev_qbe = BenefitCatalogRevision(id=new_id(), catalog_id=cat_qbe.id, revision_number=1, state="published", content_hash="hash_qbe")
    session.add(rev_qbe)
    session.flush()

    off_qbe = CatalogOffering(
        id=new_id(),
        catalog_revision_id=rev_qbe.id,
        offering_key="qbe:towing",
        concept_id=c_towing.id,
        offering_kind="core",
        role="included",
        display_value="Unlimited",
        sort_order=1,
        status="active",
    )
    session.add(off_qbe)

    cat_allianz = BenefitCatalog(id=new_id(), company_id=allianz.id, name="Allianz Motor", revision=1)
    session.add(cat_allianz)
    session.flush()
    rev_allianz = BenefitCatalogRevision(id=new_id(), catalog_id=cat_allianz.id, revision_number=1, state="draft", content_hash="hash_allianz")
    session.add(rev_allianz)
    session.commit()

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(copilot_router)

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[current_user] = lambda: admin_user

    client = TestClient(app)
    try:
        yield client, session, admin_user, qbe, allianz, rev_allianz
    finally:
        session.close()


def test_copilot_chat_detects_catalog_diff_intent(copilot_test_env):
    from app.services.copilot_chat_service import chat_with_copilot

    _, session, admin_user, qbe, allianz, _ = copilot_test_env

    result = chat_with_copilot(
        db=session,
        user=admin_user,
        message="Compare QBE and Allianz catalogs and show me what to clone",
    )
    assert "reply" in result
    actions = result.get("actions", [])
    diff_action = next((a for a in actions if a.get("type") == "catalog_diff"), None)
    assert diff_action is not None
    assert "plan" in diff_action
    plan = diff_action["plan"]
    assert plan["source_company"]["slug"] == "qbe"
    assert plan["target_company"]["slug"] == "allianz"
    assert len(plan["actions"]) >= 1


def test_copilot_apply_diff_plan_endpoint(copilot_test_env):
    client, session, _, qbe, allianz, rev_allianz = copilot_test_env
    from app.services.catalog_diff_service import generate_clone_diff_plan

    plan = generate_clone_diff_plan(session, qbe.id, allianz.id)

    resp = client.post("/copilot/catalog/apply-diff-plan", json={"plan": plan})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["applied_actions_count"] >= 1

    # Verify offering added to Allianz
    offerings = session.query(CatalogOffering).filter_by(catalog_revision_id=rev_allianz.id).all()
    assert any("towing" in off.offering_key for off in offerings)
