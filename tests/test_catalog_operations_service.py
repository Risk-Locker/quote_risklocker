"""Hermetic unit tests for AI catalog operations service and diagnostic constraint handling."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import (
    Base,
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    BenefitPackage,
    BenefitPackagePlan,
    BenefitPackagePlanItem,
    BenefitProfile,
    CatalogOffering,
    CompanyBenefitConfig,
    InsuranceCompany,
    InsuranceProduct,
    Segment,
    User,
    VehicleCategory,
    new_id,
    utcnow,
)
from app.services.catalog_operations_service import (
    apply_catalog_operations,
    parse_catalog_intent,
    preview_catalog_operations,
)
from app.services.business_setup_service import get_active_benefit_profile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def db_session():
    """In-memory SQLite session hermetic fixture."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


from types import SimpleNamespace


@pytest.fixture
def mock_business_user():
    return SimpleNamespace(
        id=new_id(),
        email="admin@risklocker.local",
        name="Business Admin",
        role="admin",
    )


@pytest.fixture
def test_setup_data(db_session: Session) -> dict:
    # 1. Active profile
    profile = get_active_benefit_profile(db_session)

    # 2. Company
    company = InsuranceCompany(
        id=new_id(),
        name="AmAssurance Test",
        slug="amassurance-test",
        category="Motor",
        revision=1,
    )
    db_session.add(company)

    # 3. Product & Segment & Vehicle
    segment = Segment(id=new_id(), segment_key="private", name="Private Use")
    vehicle = VehicleCategory(id=new_id(), category_key="car", name="Motor Car")
    product = InsuranceProduct(id=new_id(), company_id=company.id, product_key="motor-car", name="Motor Car")
    db_session.add_all([segment, vehicle, product])

    # 4. Benefit Concepts: Towing & Windscreen
    towing = BenefitConcept(id=new_id(), concept_key="towing", label="24/7 Roadside Towing")
    windscreen = BenefitConcept(id=new_id(), concept_key="windscreen", label="Windscreen Damage")
    db_session.add_all([towing, windscreen])
    db_session.flush()

    # 5. Catalog & Revision
    catalog = BenefitCatalog(
        id=new_id(),
        company_id=company.id,
        product_id=product.id,
        segment_id=segment.id,
        vehicle_category_id=vehicle.id,
        name="AmAssurance Test Motor Car Comprehensive ICE",
        status="published",
        revision=1,
    )
    db_session.add(catalog)
    db_session.flush()

    rev = BenefitCatalogRevision(
        id=new_id(),
        catalog_id=catalog.id,
        revision_number=1,
        state="published",
        content_hash="hash-12345",
    )
    db_session.add(rev)
    db_session.flush()

    # 6. Package & Plans (Auto365 Plus & Premier)
    pkg = BenefitPackage(
        id=new_id(),
        catalog_revision_id=rev.id,
        package_key="auto365",
        name="auto365 Comprehensive",
        package_kind="comprehensive",
    )
    db_session.add(pkg)
    db_session.flush()

    plan_plus = BenefitPackagePlan(id=new_id(), package_id=pkg.id, plan_key="plus", name="auto365 Plus")
    plan_premier = BenefitPackagePlan(id=new_id(), package_id=pkg.id, plan_key="premier", name="auto365 Premier")
    db_session.add_all([plan_plus, plan_premier])
    db_session.flush()

    # 7. Offerings & Plan Items
    off_towing = CatalogOffering(
        id=new_id(),
        catalog_revision_id=rev.id,
        offering_key="towing-base",
        concept_id=towing.id,
        offering_kind="base",
        applies_to_type="package",
        applies_to_id=pkg.id,
        role="included",
        display_value="50 km",
    )
    db_session.add(off_towing)
    db_session.flush()

    item_plus = BenefitPackagePlanItem(
        id=new_id(),
        plan_id=plan_plus.id,
        offering_id=off_towing.id,
        typed_value_override={"type": "text", "value": "100 km", "formatted": "100 km"},
    )
    item_premier = BenefitPackagePlanItem(
        id=new_id(),
        plan_id=plan_premier.id,
        offering_id=off_towing.id,
        typed_value_override={"type": "text", "value": "365 km", "formatted": "365 km"},
    )
    db_session.add_all([item_plus, item_premier])
    db_session.commit()

    return {
        "company": company,
        "catalog": catalog,
        "profile": profile,
        "towing": towing,
        "windscreen": windscreen,
        "plan_plus": plan_plus,
        "plan_premier": plan_premier,
    }


def test_parse_catalog_intent_towing_and_windscreen(db_session: Session, test_setup_data: dict):
    company = test_setup_data["company"]

    # Towing tiers query
    query = "AmAssurance PLUS and Premier towing to 200km and 365km"
    ops = parse_catalog_intent(db_session, query, company.id)
    assert len(ops) >= 2
    plus_op = next((o for o in ops if o.get("tier_filter") == "plus"), None)
    premier_op = next((o for o in ops if o.get("tier_filter") == "premier"), None)
    assert plus_op is not None
    assert plus_op["value"] == "200 km"
    assert premier_op is not None
    assert premier_op["value"] == "365 km"

    # Description query
    query_desc = "change description of towing to '24/7 Unlimited Roadside Towing Assistance'"
    ops_desc = parse_catalog_intent(db_session, query_desc, company.id)
    assert len(ops_desc) >= 1
    assert ops_desc[0]["action"] == "update_description"
    assert "Unlimited" in ops_desc[0]["description"]


def test_preview_and_apply_catalog_operations_with_profile_versioning(
    db_session: Session,
    mock_business_user: User,
    test_setup_data: dict,
):
    company = test_setup_data["company"]
    profile = test_setup_data["profile"]

    # 1. Preview
    operations = [
        {
            "action": "update_plan_item",
            "concept_key": "towing",
            "tier_filter": "plus",
            "vehicle_category": "car",
            "powertrain": "all",
            "value": "200 km",
        },
        {
            "action": "update_description",
            "concept_key": "towing",
            "description": "AmAssurance Premier Towing Upgrade",
        },
    ]

    preview = preview_catalog_operations(db_session, company.id, operations, profile.id)
    assert preview["target_company_id"] == company.id
    assert len(preview["mutations"]) >= 2
    plan_mut = next((m for m in preview["mutations"] if m["category"] == "plan_item"), None)
    desc_mut = next((m for m in preview["mutations"] if m["category"] == "config"), None)
    assert plan_mut is not None
    assert plan_mut["new_value"] == "200 km"
    assert desc_mut is not None
    assert desc_mut["new_value"] == "AmAssurance Premier Towing Upgrade"

    # 2. Apply with auto-cloning to new profile version
    apply_payload = {
        "mutations": preview["mutations"],
        "target_profile_action": "clone_new",
        "new_profile_name": "v3 - Auto365 Towing Update",
    }
    result = apply_catalog_operations(db_session, mock_business_user, company.id, apply_payload)

    assert result["applied_count"] >= 2
    new_profile = result["active_profile"]
    assert new_profile["version_number"] > profile.version_number
    assert "v3" in new_profile["name"] or "Auto365" in new_profile["name"]

    # Verify that plan item was updated
    plan_plus = test_setup_data["plan_plus"]
    towing = test_setup_data["towing"]
    updated_item = db_session.scalar(
        select(BenefitPackagePlanItem)
        .join(CatalogOffering, CatalogOffering.id == BenefitPackagePlanItem.offering_id)
        .where(
            BenefitPackagePlanItem.plan_id == plan_plus.id,
            CatalogOffering.concept_id == towing.id,
        )
    )
    assert updated_item is not None
    assert updated_item.typed_value_override["value"] == "200 km"

    # Verify that company config baseline description was updated under new profile
    cfg = db_session.scalar(
        select(CompanyBenefitConfig).where(
            CompanyBenefitConfig.company_id == company.id,
            CompanyBenefitConfig.profile_id == new_profile["id"],
            CompanyBenefitConfig.concept_id == towing.id,
        )
    )
    assert cfg is not None
    assert cfg.baseline_description == "AmAssurance Premier Towing Upgrade"
