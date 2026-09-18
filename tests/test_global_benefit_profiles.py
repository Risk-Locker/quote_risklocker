"""Hermetic tests for GlobalBenefitProfile, Category Exclusivity, Health Monitoring, and Auto-Matching."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault("APP_ENV", "test")

from app.core.errors import AppError
from app.models.tables import (
    Base,
    BenefitConcept,
    BusinessAsset,
    GlobalBenefitProfile,
    GlobalBenefitProfileAsset,
    new_id,
    utcnow,
)
from app.rendering.render_context import resolve_benefit_cards
from app.services.global_benefit_profile_service import (
    activate_global_benefit_profile,
    auto_assign_category_assets,
    clone_global_benefit_profile,
    create_global_benefit_profile,
    delete_global_benefit_profile,
    get_active_visual_profile_asset_map,
    get_global_benefit_profile_detail,
    list_global_benefit_profiles,
    save_global_benefit_profile_assets,
)


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


def make_user(role="admin") -> Any:
    return SimpleNamespace(id=str(uuid4()), role=role)


def make_asset(
    *,
    key: str,
    label: str,
    filename: str,
    category: str = "General",
    status: str = "active",
) -> BusinessAsset:
    return BusinessAsset(
        id=new_id(),
        asset_key=key,
        label=label,
        original_filename=filename,
        asset_kind="benefit_art",
        category=category,
        content_type="image/png",
        content_hash=f"hash-{key}",
        storage_path=f"assets/{filename}",
        size_bytes=1024,
        derivative_manifest={},
        status=status,
        created_at=utcnow(),
        updated_at=utcnow(),
    )


def test_global_benefit_profile_crud_and_activation(db_session: Session):
    user = make_user()

    # Seed concepts
    c1 = BenefitConcept(
        id=new_id(),
        concept_key="towing",
        label="Towing Assistance",
        sort_order=1,
        status="active",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    c2 = BenefitConcept(
        id=new_id(),
        concept_key="windscreen",
        label="Windscreen Damage",
        sort_order=2,
        status="active",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db_session.add_all([c1, c2])

    # Seed assets in category 'Minimal Line Art'
    a1 = make_asset(
        key="asset-towing-1",
        label="Towing Line Art",
        filename="towing.png",
        category="Minimal Line Art",
    )
    a2 = make_asset(
        key="asset-windscreen-1",
        label="Windscreen Line Art",
        filename="windscreen.png",
        category="Minimal Line Art",
    )
    db_session.add_all([a1, a2])
    db_session.commit()

    # 1. Create Profile
    created = create_global_benefit_profile(
        db_session,
        user,
        {
            "name": "Minimal Line Art v1",
            "asset_category": "Minimal Line Art",
            "description": "Clean monochromatic icons",
        },
    )
    prof_id = created["profile"]["id"]
    assert created["profile"]["name"] == "Minimal Line Art v1"
    assert created["profile"]["asset_category"] == "Minimal Line Art"
    assert not created["profile"]["is_active"]

    # 2. Save Asset Mappings
    saved_detail = save_global_benefit_profile_assets(
        db_session,
        user,
        prof_id,
        [
            {"concept_id": c1.id, "asset_id": a1.id},
            {"concept_id": c2.id, "asset_id": a2.id},
        ],
    )
    assert saved_detail["profile"]["mapped_concepts"] == 2
    assert saved_detail["profile"]["missing_assets_count"] == 0

    # 3. Clone Profile
    cloned = clone_global_benefit_profile(
        db_session,
        user,
        prof_id,
        {"name": "Minimal Line Art v2"},
    )
    clone_id = cloned["profile"]["id"]
    assert cloned["profile"]["name"] == "Minimal Line Art v2"
    assert cloned["profile"]["mapped_concepts"] == 2

    # 4. Activate Profile
    activated = activate_global_benefit_profile(db_session, user, clone_id)
    assert activated["profile"]["is_active"] is True

    # Check active asset map
    active_map = get_active_visual_profile_asset_map(db_session)
    assert active_map[c1.id] == a1.id
    assert active_map[c2.id] == a2.id

    # 5. Attempting to delete active profile must fail
    with pytest.raises(AppError, match="Cannot delete the currently active visual profile"):
        delete_global_benefit_profile(db_session, user, clone_id)

    # 6. Delete draft original profile succeeds
    delete_global_benefit_profile(db_session, user, prof_id)
    profiles = list_global_benefit_profiles(db_session, user)
    assert len(profiles) == 1
    assert profiles[0]["id"] == clone_id


def test_category_exclusivity_invariant(db_session: Session):
    user = make_user()

    c1 = BenefitConcept(
        id=new_id(),
        concept_key="towing",
        label="Towing",
        sort_order=1,
        status="active",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db_session.add(c1)

    # Asset A in "Category A"
    asset_a = make_asset(
        key="cat-a-icon",
        label="Icon A",
        filename="icon_a.png",
        category="Category A",
    )
    # Asset B in "Category B"
    asset_b = make_asset(
        key="cat-b-icon",
        label="Icon B",
        filename="icon_b.png",
        category="Category B",
    )
    db_session.add_all([asset_a, asset_b])
    db_session.commit()

    # Profile bound to "Category A"
    prof = create_global_benefit_profile(
        db_session,
        user,
        {"name": "Profile Cat A", "asset_category": "Category A"},
    )
    prof_id = prof["profile"]["id"]

    # Trying to assign Asset B (which belongs to Category B) must be rejected with 422
    with pytest.raises(AppError, match="Category Exclusivity Violation"):
        save_global_benefit_profile_assets(
            db_session,
            user,
            prof_id,
            [{"concept_id": c1.id, "asset_id": asset_b.id}],
        )

    # Assigning Asset A succeeds
    saved = save_global_benefit_profile_assets(
        db_session,
        user,
        prof_id,
        [{"concept_id": c1.id, "asset_id": asset_a.id}],
    )
    assert saved["profile"]["mapped_concepts"] == 1


def test_missing_image_health_monitoring(db_session: Session):
    user = make_user()

    c1 = BenefitConcept(
        id=new_id(),
        concept_key="flood",
        label="Special Perils / Flood",
        sort_order=1,
        status="active",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db_session.add(c1)

    asset = make_asset(
        key="flood-icon",
        label="Flood Icon",
        filename="flood.png",
        category="3D Isometric Clay",
    )
    db_session.add(asset)
    db_session.commit()

    prof = create_global_benefit_profile(
        db_session,
        user,
        {"name": "3D Clay Profile", "asset_category": "3D Isometric Clay"},
    )
    prof_id = prof["profile"]["id"]

    save_global_benefit_profile_assets(
        db_session,
        user,
        prof_id,
        [{"concept_id": c1.id, "asset_id": asset.id}],
    )

    # Check initially healthy
    detail = get_global_benefit_profile_detail(db_session, user, prof_id)
    assert detail["profile"]["missing_assets_count"] == 0
    concept_item = detail["concepts"][0]
    assert concept_item["is_missing"] is False
    assert concept_item["assigned_asset"] is not None

    # Simulate asset deletion / retirement
    asset.status = "retired"
    db_session.commit()

    # Re-fetch: profile must monitor and report missing asset non-destructively
    detail_after = get_global_benefit_profile_detail(db_session, user, prof_id)
    assert detail_after["profile"]["missing_assets_count"] == 1
    assert detail_after["concepts"][0]["is_missing"] is True
    assert detail_after["concepts"][0]["assigned_asset"] is None

    # Profiles list summary also flags missing
    profiles_summary = list_global_benefit_profiles(db_session, user)
    assert profiles_summary[0]["missing_count"] == 1
    assert profiles_summary[0]["is_complete"] is False


def test_fuzzy_auto_assign_category_assets(db_session: Session):
    user = make_user()

    c1 = BenefitConcept(
        id=new_id(),
        concept_key="towing",
        label="Emergency Roadside Towing Assistance",
        sort_order=1,
        status="active",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    c2 = BenefitConcept(
        id=new_id(),
        concept_key="windscreen",
        label="Windscreen Damage Protection",
        sort_order=2,
        status="active",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    c3 = BenefitConcept(
        id=new_id(),
        concept_key="key_replacement",
        label="Car Key Replacement",
        sort_order=3,
        status="active",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db_session.add_all([c1, c2, c3])

    # Assets in folder
    a1 = make_asset(
        key="a1",
        label="Towing",
        filename="towing_truck.png",
        category="AutoMatch Category",
    )
    a2 = make_asset(
        key="a2",
        label="Windscreen",
        filename="windscreen_shield.png",
        category="AutoMatch Category",
    )
    a3 = make_asset(
        key="a3",
        label="Unrelated Logo",
        filename="logo_random.png",
        category="AutoMatch Category",
    )
    db_session.add_all([a1, a2, a3])
    db_session.commit()

    prof = create_global_benefit_profile(
        db_session,
        user,
        {"name": "Auto Profile", "asset_category": "AutoMatch Category"},
    )
    prof_id = prof["profile"]["id"]

    res = auto_assign_category_assets(db_session, user, prof_id)
    assert res["total_concepts"] == 3
    assert res["total_category_assets"] == 3
    assert res["matched_count"] >= 2

    # Check towing match
    towing_match = next(m for m in res["matches"] if m["concept_id"] == c1.id)
    assert towing_match["status"] == "matched"
    assert towing_match["matched_asset"]["id"] == a1.id
    assert towing_match["confidence"] >= 0.70

    # Check windscreen match
    windscreen_match = next(m for m in res["matches"] if m["concept_id"] == c2.id)
    assert windscreen_match["status"] == "matched"
    assert windscreen_match["matched_asset"]["id"] == a2.id


def test_render_context_visual_profile_overlay():
    # Verify resolve_benefit_cards applies visual_profile_assets
    offering = SimpleNamespace(
        id="offering-1",
        concept_id="concept-1",
        optional_price=None,
        cost_status="foc",
        role="standard",
        offering_kind="default",
        presentation_facet_ids=[],
        description_override=None,
        typed_value={"type": "standard"},
        status="active",
    )
    concept = SimpleNamespace(
        id="concept-1",
        concept_key="towing",
        label="Towing",
        default_asset_id="default-asset-id",
        description="Standard towing",
        status="active",
    )
    selection = SimpleNamespace(
        id="sel-1",
        catalog_offering_id="offering-1",
        item_kind="catalog",
        package_plan_id=None,
        concept_id="concept-1",
        selection_key="concept-1",
        sort_order=1,
        state="current",
        cost_status="foc",
        price=None,
        typed_value_override=None,
        description_override=None,
        evidence_snapshot=None,
        source_kind="manual",
    )

    # 1. Without visual profile asset overlay -> uses default_asset_id
    cards_default = resolve_benefit_cards(
        selections=[selection],
        offerings=[offering],
        concepts=[concept],
        relations=[],
        facets=[],
    )
    assert cards_default["current_benefits"][0]["asset_id"] == "default-asset-id"

    # 2. With visual profile asset overlay -> uses mapped asset_id
    cards_overlay = resolve_benefit_cards(
        selections=[selection],
        offerings=[offering],
        concepts=[concept],
        relations=[],
        facets=[],
        visual_profile_assets={"concept-1": "profile-visual-asset-id"},
    )
    assert cards_overlay["current_benefits"][0]["asset_id"] == "profile-visual-asset-id"
