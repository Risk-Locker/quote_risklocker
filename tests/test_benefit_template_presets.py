"""Hermetic unit tests for Benefit Card Template Presets persistence and default selection."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault("APP_ENV", "test")

from app.core.errors import AppError
from app.models.tables import Base, BenefitCardPreset
from app.services.benefit_template_preset_service import (
    create_custom_benefit_card_preset,
    delete_custom_benefit_card_preset,
    get_benefit_card_preset,
    list_benefit_card_presets,
    reset_benefit_card_preset,
    save_benefit_card_preset,
    set_default_benefit_card_preset,
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


def test_list_benefit_card_presets_seeds_default_masonry_flow(db_session: Session):
    """Ensure listing presets seeds factory presets with Masonry Flow as default (44px, subtle lift, auto height)."""
    presets = list_benefit_card_presets(db_session)
    assert len(presets) == 7

    # First preset must be the default one
    default_preset = presets[0]
    assert default_preset.id == "masonry-flow"
    assert default_preset.is_default is True
    assert default_preset.config["iconSize"] == 44
    assert default_preset.config["elevation"] == "lift"
    assert default_preset.config["uniformHeight"] == 0

    # Ensure other presets have is_default=False
    for other in presets[1:]:
        assert other.is_default is False


def test_save_benefit_card_preset_persists_config_changes(db_session: Session):
    """Ensure saving changes updates and persists preset configuration in the database."""
    list_benefit_card_presets(db_session)  # ensure seeded

    updates = {
        "name": "Masonry Flow Custom",
        "iconSize": 50,
        "elevation": "flat",
        "uniformHeight": 52,
    }
    updated = save_benefit_card_preset(db_session, "masonry-flow", updates)
    assert updated.name == "Masonry Flow Custom"
    assert updated.config["iconSize"] == 50
    assert updated.config["elevation"] == "flat"
    assert updated.config["uniformHeight"] == 52

    # Re-fetch from clean query to guarantee DB persistence
    reloaded = get_benefit_card_preset(db_session, "masonry-flow")
    assert reloaded.config["iconSize"] == 50
    assert reloaded.config["elevation"] == "flat"


def test_set_default_benefit_card_preset_atomic_switch(db_session: Session):
    """Ensure switching the default preset atomically resets the old default and activates the new one."""
    list_benefit_card_presets(db_session)

    # Switch default to compact-minimal
    new_default = set_default_benefit_card_preset(db_session, "compact-minimal")
    assert new_default.is_default is True

    # Check that masonry-flow is no longer default
    old_default = get_benefit_card_preset(db_session, "masonry-flow")
    assert old_default.is_default is False

    # Check listing orders the new default first
    presets = list_benefit_card_presets(db_session)
    assert presets[0].id == "compact-minimal"
    assert presets[0].is_default is True


def test_create_and_delete_custom_preset(db_session: Session):
    """Ensure creating custom presets works and system presets cannot be deleted."""
    list_benefit_card_presets(db_session)

    payload = {
        "id": "my-custom-style",
        "name": "My Custom Card Style",
        "shortName": "Custom Style",
        "description": "A customized card style",
        "iconSize": 36,
        "elevation": "lift",
    }
    created = create_custom_benefit_card_preset(db_session, payload)
    assert created.id == "my-custom-style"
    assert created.is_custom is True
    assert created.config["iconSize"] == 36

    # System preset cannot be deleted
    with pytest.raises(AppError, match="System presets cannot be deleted"):
        delete_custom_benefit_card_preset(db_session, "masonry-flow")

    # Custom preset can be deleted
    delete_custom_benefit_card_preset(db_session, "my-custom-style")
    with pytest.raises(AppError, match="not found"):
        get_benefit_card_preset(db_session, "my-custom-style")


def test_reset_benefit_card_preset_restores_factory_defaults(db_session: Session):
    """Ensure resetting restores factory defaults while preserving is_default status."""
    list_benefit_card_presets(db_session)

    # Modify masonry-flow
    save_benefit_card_preset(db_session, "masonry-flow", {"iconSize": 28, "elevation": "flat"})
    modified = get_benefit_card_preset(db_session, "masonry-flow")
    assert modified.config["iconSize"] == 28

    # Reset
    reset = reset_benefit_card_preset(db_session, "masonry-flow")
    assert reset.config["iconSize"] == 44
    assert reset.config["elevation"] == "lift"
    assert reset.is_default is True
