"""Hermetic tests for CompanyBenefitProfile versioning system and global cascade architecture.

Tests:
1. Pydantic schemas and aliases validation.
2. Profile lifecycle in business_setup_service (auto-fallback, create, clone, update, activate, delete).
3. Archived profile immutability (configs, conditions, profiles cannot be modified or deleted).
4. Review seeding cascade exclusion (seed_base_benefits omits disabled concepts).
5. Render context cascade exclusion (resolve_benefit_cards suppresses disabled concepts from available_cards while preserving current selections).
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault("APP_ENV", "test")

from app.api.schemas import (
    BenefitCatalogSaveRequest,
    BenefitProfileCloneRequest,
    BenefitProfileCreateRequest,
    BenefitProfileUpdateRequest,
    CatalogOfferingSaveRequest,
    CompanyBenefitConfigsUpdateRequest,
    CompanyBenefitProfileCloneRequest,
    CompanyBenefitProfileCreateRequest,
    CompanyBenefitProfileUpdateRequest,
    PackageCloneRequest,
    PackageSaveRequest,
)
from app.core.errors import AppError
from app.models.tables import (
    Base,
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    BenefitProfile,
    CatalogOffering,
    CompanyBenefitCondition,
    CompanyBenefitConfig,
    CompanyBenefitProfile,
    DraftBenefitSelection,
    InsuranceCompany,
    QuotationDraft,
)
from app.rendering.render_context import resolve_benefit_cards
from app.services.business_setup_service import (
    activate_benefit_profile,
    activate_company_profile,
    clone_benefit_profile,
    clone_company_profile,
    create_benefit_profile,
    create_company_profile,
    delete_benefit_profile,
    delete_company_condition,
    delete_company_profile,
    get_active_benefit_profile,
    get_active_company_profile,
    get_company_benefit_configs,
    list_benefit_profiles,
    list_company_conditions,
    list_company_profiles,
    save_company_condition,
    update_benefit_profile,
    update_company_benefit_configs,
    update_company_profile,
)
from app.services.catalog_review_service import seed_base_benefits


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


def make_user(role="admin"):
    return SimpleNamespace(id=str(uuid4()), role=role)


def test_profile_schemas_validation():
    # 1. Create request
    create_req = CompanyBenefitProfileCreateRequest(name="Q4 2026 Revisions", notes="Testing notes")
    assert create_req.name == "Q4 2026 Revisions"
    assert create_req.notes == "Testing notes"

    # 2. Clone request
    clone_req = CompanyBenefitProfileCloneRequest(name="Cloned Profile", notes="Cloned notes")
    assert clone_req.name == "Cloned Profile"

    # 3. Update request
    update_req = CompanyBenefitProfileUpdateRequest(name="Updated Name")
    assert update_req.name == "Updated Name"

    # 4. Config update request supporting both configs and items aliases & ignoring extra metadata fields
    by_configs = CompanyBenefitConfigsUpdateRequest(configs=[{
        "concept_id": "c1",
        "is_enabled": True,
        "id": "existing-id-123",
        "company_id": "comp-123",
        "profile_id": "prof-123",
        "created_at": "2026-09-14T00:00:00Z",
        "concept": {"id": "c1", "label": "Roadside"},
    }])
    assert len(by_configs.items) == 1
    assert by_configs.items[0].concept_id == "c1"
    assert by_configs.items[0].is_enabled is True

    by_items = CompanyBenefitConfigsUpdateRequest(items=[{
        "concept_id": "c2",
        "is_enabled": False,
        "baseline_description": "Custom text",
        "extra_client_data": 42,
    }])
    assert len(by_items.items) == 1
    assert by_items.items[0].is_enabled is False
    assert by_items.items[0].baseline_description == "Custom text"


def test_get_active_benefit_profile_auto_provisions(db_session: Session):
    # Initial call auto-provisions baseline profile
    prof = get_active_benefit_profile(db_session)
    assert prof is not None
    assert prof.is_active is True
    assert prof.status == "active"
    assert prof.version_number == 1
    assert "Main Unified Baseline" in prof.name

    # Subsequent call returns the existing active profile
    prof2 = get_active_benefit_profile(db_session)
    assert prof2.id == prof.id

    # Backwards-compatible alias also returns the unified active profile
    legacy_prof = get_active_company_profile(db_session, "dummy-company-id")
    assert legacy_prof.id == prof.id


def test_profile_lifecycle_crud_and_atomic_activation(db_session: Session):
    user = make_user("admin")
    company_a = InsuranceCompany(
        id=str(uuid4()),
        name="Allianz General",
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    company_b = InsuranceCompany(
        id=str(uuid4()),
        name="Zurich General",
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add_all([company_a, company_b])
    db_session.commit()

    # Create concepts for condition testing
    conc_dpp = BenefitConcept(id=str(uuid4()), concept_key="dpp", label="DPP", description="DPP", status="active")
    conc_tow = BenefitConcept(id=str(uuid4()), concept_key="towing", label="Towing", description="Towing", status="active")
    conc_ws = BenefitConcept(id=str(uuid4()), concept_key="windscreen", label="Windscreen", description="Windscreen", status="active")
    conc_flood = BenefitConcept(id=str(uuid4()), concept_key="flood", label="Flood", description="Flood", status="active")
    db_session.add_all([conc_dpp, conc_tow, conc_ws, conc_flood])
    db_session.commit()

    # 1. Baseline profile auto-provisioned
    base_prof = get_active_benefit_profile(db_session)
    assert base_prof.is_active is True

    # Add configs and condition for Company A
    update_company_benefit_configs(
        db_session,
        user,
        company_a.id,
        items=[
            {"concept_id": conc_tow.id, "is_enabled": True, "baseline_description": "Allianz Towing"},
            {"concept_id": conc_ws.id, "is_enabled": True, "baseline_description": "Allianz Windscreen"},
        ],
        profile_id=base_prof.id,
    )
    save_company_condition(
        db_session,
        user,
        company_a.id,
        payload={
            "name": "Allianz DPP Towing",
            "trigger_concept_id": conc_dpp.id,
            "target_concept_id": conc_tow.id,
            "replacement_description": "Allianz Unlimited Towing",
        },
        profile_id=base_prof.id,
    )

    # Add configs and condition for Company B
    update_company_benefit_configs(
        db_session,
        user,
        company_b.id,
        items=[
            {"concept_id": conc_tow.id, "is_enabled": True, "baseline_description": "Zurich Towing"},
            {"concept_id": conc_flood.id, "is_enabled": True, "baseline_description": "Zurich Flood"},
        ],
        profile_id=base_prof.id,
    )
    save_company_condition(
        db_session,
        user,
        company_b.id,
        payload={
            "name": "Zurich DPP Towing",
            "trigger_concept_id": conc_dpp.id,
            "target_concept_id": conc_tow.id,
            "replacement_description": "Zurich Unlimited Towing",
        },
        profile_id=base_prof.id,
    )

    # Verify global counts in profile list
    prof_list = list_benefit_profiles(db_session, user)
    assert len(prof_list) == 1
    assert prof_list[0]["configs_count"] == 4
    assert prof_list[0]["conditions_count"] == 2

    # 2. Deep Clone profile into new draft version (spans ALL companies!)
    cloned = clone_benefit_profile(
        db_session,
        user,
        base_prof.id,
        payload={"name": "Global Baseline (v2)", "notes": "Cloned for test"},
    )
    assert cloned["name"] == "Global Baseline (v2)"
    assert cloned["version_number"] == 2
    assert cloned["is_active"] is False
    assert cloned["status"] == "draft"

    # Verify cloned profile has deep copies for Company A
    a_cloned_configs = get_company_benefit_configs(db_session, user, company_a.id, profile_id=cloned["id"])
    assert len(a_cloned_configs) == 2
    a_cloned_conditions = list_company_conditions(db_session, user, company_a.id, profile_id=cloned["id"])
    assert len(a_cloned_conditions) == 1
    assert a_cloned_conditions[0]["replacement_description"] == "Allianz Unlimited Towing"

    # Verify cloned profile has deep copies for Company B
    b_cloned_configs = get_company_benefit_configs(db_session, user, company_b.id, profile_id=cloned["id"])
    assert len(b_cloned_configs) == 2
    b_cloned_conditions = list_company_conditions(db_session, user, company_b.id, profile_id=cloned["id"])
    assert len(b_cloned_conditions) == 1
    assert b_cloned_conditions[0]["replacement_description"] == "Zurich Unlimited Towing"

    # 3. Update cloned draft metadata
    updated = update_benefit_profile(
        db_session,
        user,
        cloned["id"],
        payload={"name": "Global Baseline v2 (Reviewed)", "notes": "Ready for live"},
    )
    assert updated["name"] == "Global Baseline v2 (Reviewed)"

    # Modify a config in cloned draft for Company A (disable windscreen)
    update_company_benefit_configs(
        db_session,
        user,
        company_a.id,
        items=[{"concept_id": conc_ws.id, "is_enabled": False}],
        profile_id=cloned["id"],
    )
    v2_a_configs = {c["concept_id"]: c["is_enabled"] for c in get_company_benefit_configs(db_session, user, company_a.id, profile_id=cloned["id"])}
    assert v2_a_configs[conc_ws.id] is False

    # Baseline profile windscreen remains True for Company A (isolation check)
    base_a_configs = {c["concept_id"]: c["is_enabled"] for c in get_company_benefit_configs(db_session, user, company_a.id, profile_id=base_prof.id)}
    assert base_a_configs[conc_ws.id] is True

    # 4. Atomic activation of v2
    activated = activate_benefit_profile(db_session, user, cloned["id"])
    assert activated["is_active"] is True
    assert activated["status"] == "active"

    # Check that previous baseline is deactivated and archived
    db_session.refresh(base_prof)
    assert base_prof.is_active is False
    assert base_prof.status == "archived"

    # Check that get_active_benefit_profile now returns v2
    active_now = get_active_benefit_profile(db_session)
    assert active_now.id == cloned["id"]

    # 5. Test draft deletion
    draft_v3 = create_benefit_profile(db_session, user, {"name": "Draft v3", "notes": "Temporary"})
    assert draft_v3["status"] == "draft"
    delete_benefit_profile(db_session, user, draft_v3["id"])
    assert db_session.scalar(select(BenefitProfile).where(BenefitProfile.id == draft_v3["id"])) is None


def test_archived_profile_immutability(db_session: Session):
    user = make_user("admin")
    company = InsuranceCompany(
        id=str(uuid4()),
        name="Zurich",
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(company)
    db_session.commit()

    base_prof = get_active_company_profile(db_session, company.id)

    # Clone and activate v2 to make baseline archived
    cloned = clone_company_profile(db_session, user, company.id, base_prof.id, payload={"name": "Zurich v2"})
    activate_company_profile(db_session, user, company.id, cloned["id"])

    db_session.refresh(base_prof)
    assert base_prof.status == "archived"

    # 1. Modifying archived profile name or notes raises AppError 400
    with pytest.raises(AppError) as exc:
        update_company_profile(db_session, user, company.id, base_prof.id, {"name": "Hacked"})
    assert "Cannot modify an archived profile" in str(exc.value)

    # 2. Deleting archived profile raises AppError 400
    with pytest.raises(AppError) as exc:
        delete_company_profile(db_session, user, company.id, base_prof.id)
    assert "Cannot delete an archived profile" in str(exc.value)

    # 3. Updating configs in archived profile raises AppError 400
    with pytest.raises(AppError) as exc:
        update_company_benefit_configs(db_session, user, company.id, items=[{"concept_id": "towing", "is_enabled": False}], profile_id=base_prof.id)
    assert "Cannot modify an archived profile" in str(exc.value)

    # 4. Adding condition to archived profile raises AppError 400
    with pytest.raises(AppError) as exc:
        save_company_condition(db_session, user, company.id, payload={"name": "Rule", "trigger_concept_id": "a", "target_concept_id": "b", "replacement_description": "c"}, profile_id=base_prof.id)
    assert "Cannot modify an archived profile" in str(exc.value)


def test_seed_base_benefits_cascade_exclusion(db_session: Session):
    user = make_user("staff")
    company = InsuranceCompany(
        id=str(uuid4()),
        name="AmAssurance",
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(company)

    active_prof = get_active_company_profile(db_session, company.id)

    # Create concepts for offerings
    conc_tow = BenefitConcept(id=str(uuid4()), concept_key="towing", label="Towing Assistance", status="active", description="Towing")
    conc_flood = BenefitConcept(id=str(uuid4()), concept_key="flood_perils", label="Flood", status="active", description="Flood")
    db_session.add_all([conc_tow, conc_flood])

    # Disable 'flood_perils' concept in active profile
    cfg_flood = CompanyBenefitConfig(
        id=str(uuid4()),
        company_id=company.id,
        profile_id=active_prof.id,
        concept_id=conc_flood.id,
        is_enabled=False,
    )
    cfg_tow = CompanyBenefitConfig(
        id=str(uuid4()),
        company_id=company.id,
        profile_id=active_prof.id,
        concept_id=conc_tow.id,
        is_enabled=True,
    )
    db_session.add_all([cfg_flood, cfg_tow])

    # Create catalog revision with both concepts
    cat = BenefitCatalog(id=str(uuid4()), company_id=company.id, name="Motor Cat", status="published", revision=1)
    db_session.add(cat)
    cat_rev = BenefitCatalogRevision(id=str(uuid4()), catalog_id=cat.id, revision_number=1, state="published", content_hash="hash")
    db_session.add(cat_rev)

    off_tow = CatalogOffering(
        id=str(uuid4()),
        catalog_revision_id=cat_rev.id,
        concept_id=conc_tow.id,
        offering_key="tow-off",
        offering_kind="base",
        status="active",
        sort_order=1,
    )
    off_flood = CatalogOffering(
        id=str(uuid4()),
        catalog_revision_id=cat_rev.id,
        concept_id=conc_flood.id,
        offering_key="flood-off",
        offering_kind="base",
        status="active",
        sort_order=2,
    )
    db_session.add_all([off_tow, off_flood])

    draft = QuotationDraft(
        id=str(uuid4()),
        uploaded_file_id=str(uuid4()),
        owner_id=user.id,
        company_id=company.id,
        catalog_revision_id=cat_rev.id,
        status="review",
        revision=1,
        fields={},
        scalar_decisions={},
        warnings=[],
    )
    db_session.add(draft)
    db_session.commit()

    # Seed base benefits
    created_count = seed_base_benefits(db_session, draft, cat_rev)
    assert created_count == 1

    selections = list(db_session.scalars(select(DraftBenefitSelection).where(DraftBenefitSelection.draft_id == draft.id)))
    seeded_concept_ids = [s.concept_id for s in selections]

    # 'towing' was seeded because is_enabled=True
    assert conc_tow.id in seeded_concept_ids
    # 'flood_perils' was excluded from seeding by active profile cascade!
    assert conc_flood.id not in seeded_concept_ids


def test_render_context_available_cards_suppression_and_customer_extra_preservation():
    def row(**kwargs):
        return SimpleNamespace(**kwargs)

    conc_towing = row(id="towing", concept_key="towing", label="Towing Assistance", status="active", description="Standard towing", default_asset_id=None, display_overrides={})
    conc_windscreen = row(id="windscreen", concept_key="windscreen", label="Windscreen Damage", status="active", description="Windscreen", default_asset_id=None, display_overrides={})
    conc_flood = row(id="special_perils", concept_key="special_perils", label="Special Perils", status="active", description="Flood", default_asset_id=None, display_overrides={})

    off_towing = row(id="off-tow", concept_id="towing", offering_key="tow-std", status="active", offering_kind="base", sort_order=1, typed_value=None, label_override=None, description_override=None, presentation_facet_ids=[])
    off_windscreen_addon = row(id="off-ws", concept_id="windscreen", offering_key="ws-opt", status="active", offering_kind="optional", sort_order=2, typed_value={"display_text": "RM 1,000"}, label_override=None, description_override=None, presentation_facet_ids=[])
    off_flood_addon = row(id="off-flood", concept_id="special_perils", offering_key="flood-opt", status="active", offering_kind="optional", sort_order=3, typed_value={"display_text": "Full Sum Insured"}, label_override=None, description_override=None, presentation_facet_ids=[])

    # Current selection: towing included
    sel_towing = row(
        id="sel-tow",
        selection_key="tow",
        catalog_offering_id=off_towing.id,
        concept_id=conc_towing.id,
        item_kind="catalog",
        state="current",
        cost_status="included",
        label_override=None,
        typed_value_override=None,
        sort_order=1,
    )

    # Customer quotation already has windscreen purchased/reviewed as extra
    sel_windscreen_purchased = row(
        id="sel-ws",
        selection_key="ws",
        catalog_offering_id=off_windscreen_addon.id,
        concept_id=conc_windscreen.id,
        item_kind="catalog",
        state="current",
        cost_status="paid",
        label_override=None,
        typed_value_override=None,
        sort_order=2,
    )

    # Company configs: special_perils AND windscreen are disabled in profile!
    company_configs = [
        row(concept_id="towing", is_enabled=True, baseline_description=None),
        row(concept_id="special_perils", is_enabled=False, baseline_description=None),
        row(concept_id="windscreen", is_enabled=False, baseline_description=None),
    ]

    res = resolve_benefit_cards(
        selections=[sel_towing, sel_windscreen_purchased],
        offerings=[off_towing, off_windscreen_addon, off_flood_addon],
        concepts=[conc_towing, conc_windscreen, conc_flood],
        relations=[],
        facets=[],
        company_configs=company_configs,
    )

    # 1. Available add-ons: flood was optional and disabled by profile -> suppressed!
    available_keys = [c["concept_key"] for c in res["available_addons"]]
    assert "special_perils" not in available_keys

    # 2. Current cards: windscreen was purchased by customer -> PRESERVED!
    current_keys = [c["concept_key"] for c in res["current_benefits"]]
    assert "windscreen" in current_keys
    assert "towing" in current_keys


def test_catalog_mutation_schemas_extra_fields_and_kinds():
    # 1. CatalogOfferingSaveRequest ignores client metadata (concept, revision_id, etc.)
    off_req = CatalogOfferingSaveRequest(
        base_revision=1,
        concept_id="c1",
        offering_kind="base",
        id="off-123",
        catalog_revision_id="rev-456",
        concept={"id": "c1", "label": "Test Concept"},
        extra_client_data="ignored",
    )
    assert off_req.id == "off-123"
    assert off_req.concept_id == "c1"

    # 2. PackageSaveRequest supports comprehensive, tpft, tpo, and addon_bundle
    pkg_comp = PackageSaveRequest(base_revision=1, name="Comp Package", package_kind="comprehensive")
    assert pkg_comp.package_kind == "comprehensive"

    pkg_tpft = PackageSaveRequest(base_revision=1, name="TPFT Package", package_kind="tpft", extra_field="ok")
    assert pkg_tpft.package_kind == "tpft"

    pkg_tpo = PackageSaveRequest(base_revision=1, name="TPO Package", package_kind="tpo")
    assert pkg_tpo.package_kind == "tpo"

    pkg_bundle = PackageSaveRequest(base_revision=1, name="Bundle Package", package_kind="addon_bundle")
    assert pkg_bundle.package_kind == "addon_bundle"

    # 3. PackageCloneRequest supports tpft and tpo
    clone_tpft = PackageCloneRequest(base_revision=1, package_key="tpft_key", name="TPFT Clone", package_kind="tpft")
    assert clone_tpft.package_kind == "tpft"

    # 4. BenefitCatalogSaveRequest ignores extra client properties
    cat_req = BenefitCatalogSaveRequest(
        company_id="comp-1",
        name="Private Car EV",
        engine_type="ev",
        client_timestamp="2026-09-14",
    )
    assert cat_req.engine_type == "ev"

