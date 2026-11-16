"""Unit tests for Catalog Diff & Cloning Engine (Milestone 4, Task 4.1)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.tables import (
    AuditEvent,
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
def diff_test_db():
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

    # 1. Source Company: QBE
    qbe = InsuranceCompany(id=new_id(), name="QBE Insurance", slug="qbe", status="active")
    # 2. Target Company: Allianz
    allianz = InsuranceCompany(id=new_id(), name="Allianz General", slug="allianz", status="active")
    session.add_all([qbe, allianz])
    session.flush()

    # 3. Benefit Concepts
    c_towing = BenefitConcept(id=new_id(), concept_key="towing", label="Emergency Towing Assistance")
    c_glass = BenefitConcept(id=new_id(), concept_key="windscreen", label="Windscreen Damage")
    c_flood = BenefitConcept(id=new_id(), concept_key="special_perils", label="Special Perils (Flood)")
    session.add_all([c_towing, c_glass, c_flood])
    session.flush()

    # 4. QBE Catalog & Offerings (3 benefits)
    cat_qbe = BenefitCatalog(id=new_id(), company_id=qbe.id, name="QBE Motor Comprehensive", revision=1)
    session.add(cat_qbe)
    session.flush()
    rev_qbe = BenefitCatalogRevision(id=new_id(), catalog_id=cat_qbe.id, revision_number=1, state="published", content_hash="hash_qbe")
    session.add(rev_qbe)
    session.flush()

    off_qbe_towing = CatalogOffering(
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
    off_qbe_glass = CatalogOffering(
        id=new_id(),
        catalog_revision_id=rev_qbe.id,
        offering_key="qbe:windscreen",
        concept_id=c_glass.id,
        offering_kind="addon",
        role="optional",
        display_value="RM 1,000",
        sort_order=2,
        status="active",
    )
    off_qbe_flood = CatalogOffering(
        id=new_id(),
        catalog_revision_id=rev_qbe.id,
        offering_key="qbe:flood",
        concept_id=c_flood.id,
        offering_kind="addon",
        role="optional",
        display_value="Included in Special Perils",
        sort_order=3,
        status="active",
    )
    session.add_all([off_qbe_towing, off_qbe_glass, off_qbe_flood])

    # 5. Allianz Catalog & Offerings (only 1 benefit: windscreen)
    cat_allianz = BenefitCatalog(id=new_id(), company_id=allianz.id, name="Allianz Motor Comprehensive", revision=1)
    session.add(cat_allianz)
    session.flush()
    rev_allianz = BenefitCatalogRevision(id=new_id(), catalog_id=cat_allianz.id, revision_number=1, state="draft", content_hash="hash_allianz")
    session.add(rev_allianz)
    session.flush()

    off_allianz_glass = CatalogOffering(
        id=new_id(),
        catalog_revision_id=rev_allianz.id,
        offering_key="allianz:windscreen",
        concept_id=c_glass.id,
        offering_kind="addon",
        role="optional",
        display_value="RM 1,000",
        sort_order=1,
        status="active",
    )
    session.add(off_allianz_glass)
    session.commit()

    try:
        yield session, admin_user, qbe, allianz, cat_allianz, rev_allianz
    finally:
        session.close()


def test_compare_underwriter_catalogs_identifies_diffs(diff_test_db):
    from app.services.catalog_diff_service import compare_underwriter_catalogs

    session, _, qbe, allianz, _, _ = diff_test_db

    diff = compare_underwriter_catalogs(session, qbe.id, allianz.id)
    assert diff["source_company"]["slug"] == "qbe"
    assert diff["target_company"]["slug"] == "allianz"

    # Common: windscreen
    assert len(diff["common_benefits"]) == 1
    assert diff["common_benefits"][0]["concept_key"] == "windscreen"

    # Missing in Allianz: towing, flood
    missing_keys = [m["concept_key"] for m in diff["missing_in_target"]]
    assert "towing" in missing_keys
    assert "special_perils" in missing_keys


def test_generate_clone_diff_plan_structures_actions(diff_test_db):
    from app.services.catalog_diff_service import generate_clone_diff_plan

    session, _, qbe, allianz, _, _ = diff_test_db

    plan = generate_clone_diff_plan(session, qbe.id, allianz.id)
    assert "plan_id" in plan
    assert plan["source_company"]["name"] == "QBE Insurance"
    assert plan["target_company"]["name"] == "Allianz General"

    actions = plan["actions"]
    assert len(actions) == 2  # towing and flood to add
    action_concepts = [a["concept_key"] for a in actions]
    assert "towing" in action_concepts
    assert "special_perils" in action_concepts
    for a in actions:
        assert a["action"] == "add"
        assert a["proposed_value"] is not None


def test_apply_catalog_diff_plan_transactional(diff_test_db):
    from app.services.catalog_diff_service import (
        apply_catalog_diff_plan,
        generate_clone_diff_plan,
    )

    session, admin_user, qbe, allianz, cat_allianz, rev_allianz = diff_test_db

    plan = generate_clone_diff_plan(session, qbe.id, allianz.id)
    result = apply_catalog_diff_plan(session, admin_user, plan)

    assert result["ok"] is True
    assert result["applied_actions_count"] == 2

    # Verify offerings were added to Allianz catalog
    allianz_offerings = session.query(CatalogOffering).filter_by(catalog_revision_id=rev_allianz.id).all()
    assert len(allianz_offerings) == 3  # original glass + 2 added (towing, flood)

    # Verify AuditEvent
    audits = session.query(AuditEvent).filter_by(action="catalog.diff.applied").all()
    assert len(audits) >= 1
    assert audits[0].actor_id == admin_user.id
