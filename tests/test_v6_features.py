"""Regression tests for v6 features: template groups, copy guard, road-tax date defaults, session layout override."""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_PROVIDER": "supabase_postgres",
        "DATABASE_URL": "postgresql://postgres:password@db.test.supabase.co:5432/postgres",
        "AUTH_HASH_SECRET": "test-auth-hash-secret-that-is-long-enough",
        "STORAGE_DRIVER": "supabase",
        "SUPABASE_URL": "https://project-ref.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
    }
)

from app.core.errors import AppError
from app.models.tables import OutputTemplateConfig, TemplateGroup
from app.services import admin_service, review_service, road_tax_service


def _admin_user() -> object:
    user = MagicMock()
    user.role = "admin"
    user.id = "u-admin"
    return user


def _fake_db() -> MagicMock:
    db = MagicMock()
    db.get.return_value = None
    db.scalars.return_value.all.return_value = []
    return db


def test_road_tax_missing_dates_default_to_today_and_one_year():
    db = _fake_db()
    rule = road_tax_service.upsert_rule(
        db,
        {"vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "West Malaysia", "min_cc": 100, "base_rate": 20},
    )
    assert rule.effective_from == date.today()
    assert rule.effective_to == date.today() + timedelta(days=365)


def test_road_tax_explicit_dates_are_kept():
    db = _fake_db()
    rule = road_tax_service.upsert_rule(
        db,
        {
            "vehicle_type": "Car", "owner_type": "Individual", "jurisdiction": "West Malaysia",
            "min_cc": 100, "base_rate": 20,
            "effective_from": "2025-01-01", "effective_to": "2025-12-31",
        },
    )
    assert rule.effective_from == date(2025, 1, 1)
    assert rule.effective_to == date(2025, 12, 31)


def test_copy_template_clones_editable_template_as_an_independent_draft():
    db = _fake_db()
    editable = OutputTemplateConfig(name="Editable", fixed_fields={"canvas": {"elements": []}, "locked": False, "is_default": False})
    db.get.return_value = editable
    copy = admin_service.copy_template(db, _admin_user(), "template-id")
    assert copy.name == "Copy of Editable"
    assert copy.fixed_fields["locked"] is False
    assert copy.fixed_fields["is_default"] is False


def test_copy_template_allows_locked_default_and_inherits_group():
    db = _fake_db()
    locked = OutputTemplateConfig(
        name="Locked Default",
        insurance_company_id="company-1",
        group_id="group-1",
        fixed_fields={"canvas": {"elements": []}, "locked": True},
    )
    db.get.return_value = locked
    copy = admin_service.copy_template(db, _admin_user(), "template-id")
    assert copy.name == "Copy of Locked Default"
    assert copy.group_id == "group-1"
    assert copy.insurance_company_id == "company-1"


def test_template_group_requires_name():
    db = _fake_db()
    with pytest.raises(AppError) as exc:
        admin_service.upsert_template_group(db, _admin_user(), {})
    assert exc.value.status_code == 400


def test_template_group_create_and_rename():
    db = _fake_db()
    group = admin_service.upsert_template_group(db, _admin_user(), {"name": "  QBE  ", "company_id": "company-1"})
    assert group.name == "QBE"
    assert group.company_id == "company-1"
    group.id = "group-1"
    db.get.return_value = group
    updated = admin_service.upsert_template_group(db, _admin_user(), {"id": "group-1", "name": "QBE Motor", "company_id": None})
    assert updated.name == "QBE Motor"
    assert updated.company_id is None


def test_template_group_delete_unassigns_templates():
    db = _fake_db()
    group = TemplateGroup(id="group-1", name="QBE")
    assigned = OutputTemplateConfig(name="T1", group_id="group-1", fixed_fields={"canvas": {"elements": []}})
    db.get.return_value = group
    db.scalars.return_value.all.return_value = [assigned]
    admin_service.delete_template_group(db, _admin_user(), "group-1")
    assert assigned.group_id is None
    db.delete.assert_called_once_with(group)


def test_upsert_template_seeds_editable_config():
    db = _fake_db()
    db.get.return_value = None
    template = admin_service.upsert_template(db, _admin_user(), {"name": "New Editable"})
    config = template.fixed_fields
    assert config.get("locked") is False
    assert config.get("is_default") is False
    assert config["version"] == 7
    assert config["page_profile"]["profile_key"] == "a4"
    assert config["canvas"]["elements"] == []


def test_make_template_master_promotes_and_demotes():
    db = _fake_db()
    current_master = OutputTemplateConfig(name="Old Master", fixed_fields={"canvas": {"elements": []}, "is_default": True, "locked": True})
    new_master = OutputTemplateConfig(name="New Master", fixed_fields={"canvas": {"elements": []}, "is_default": False, "locked": False})
    db.get.side_effect = lambda model, object_id: new_master if object_id == "new" else current_master
    db.scalars.return_value.all.return_value = [current_master, new_master]
    result = admin_service.make_template_master(db, _admin_user(), "new")
    assert result.fixed_fields["is_default"] is True
    assert result.fixed_fields["locked"] is True
    assert current_master.fixed_fields["is_default"] is False
    assert current_master.fixed_fields["locked"] is False


def test_runner_fee_default_returns_20_when_unset():
    db = _fake_db()
    assert admin_service.get_runner_fee_default(db) == 20.0


def test_upsert_special_rejects_unknown_category():
    db = _fake_db()
    db.get.return_value = None
    with pytest.raises(AppError) as exc:
        admin_service.upsert_special(db, _admin_user(), {"label": "Bad", "category": "FOCD"})
    assert exc.value.status_code == 400


def test_upsert_special_accepts_foc_and_addon():
    db = _fake_db()
    db.get.return_value = None
    special = admin_service.upsert_special(db, _admin_user(), {"label": "Towing", "category": "Add-on"})
    assert special.category == "Add-on"


def test_update_draft_fields_stores_layout_override(monkeypatch):
    draft = MagicMock()
    draft.id = "draft-1"
    draft.fields = {}
    draft.uploaded_file = MagicMock()
    draft.uploaded_file.template_id = None
    draft.uploaded_file.insurance_company_id = None
    db = _fake_db()
    monkeypatch.setattr(review_service, "get_accessible_draft", lambda _db, _user, _id: draft)
    review_service.update_draft_fields(
        db,
        _admin_user(),
        "draft-1",
        {},
        template_id=None,
        layout_override={"canvas": {"width": 794, "height": 1123, "elements": []}},
    )
    assert draft.layout_override == {"canvas": {"width": 794, "height": 1123, "elements": []}}
