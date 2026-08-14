"""Immutable v7 template publication and insurer-independent selection."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
os.environ.setdefault("APP_ENV", "test")

from app.core.errors import AppError  # noqa: E402
from app.models.tables import (  # noqa: E402
    AuditEvent,
    OutputTemplateConfig,
    TemplatePageProfile,
    TemplateRevision,
)
from app.services.template_revision_service import (  # noqa: E402
    list_page_profiles,
    list_published_templates,
    publish_template_revision,
)


def template_config(*, legacy: bool = False) -> dict:
    elements = [{
        "id": "current-grid",
        "type": "benefit-grid",
        "gridKind": "current_benefits",
        "x": 20,
        "y": 250,
        "w": 754,
        "h": 360,
        "packing": {"strategy": "balanced", "alignment": "center"},
        "cardStyle": "standard",
        "textDensity": "normal",
        "emptyState": "hide",
    }]
    if legacy:
        elements.append({
            "id": "legacy-specials",
            "type": "benefit-section",
            "x": 20,
            "y": 650,
            "w": 754,
            "h": 200,
        })
    return {
        "version": 7,
        "insurance_company_id": "must-not-be-published",
        "page_profile": {
            "profile_key": "a4",
            "name": "A4",
            "width": 794,
            "height": 1123,
            "unit": "px",
            "safe_margins": {"top": 24, "right": 24, "bottom": 24, "left": 24},
        },
        "canvas": {"width": 794, "height": 1123, "elements": elements},
    }


class Scalars:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return list(self.rows)


class FakeDb:
    def __init__(self, values):
        self.values = {(type(item), item.id): item for item in values}
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def get(self, model, object_id):
        return self.values.get((model, object_id))

    def scalars(self, statement):
        entity = statement.column_descriptions[0].get("entity") if statement.column_descriptions else None
        return Scalars(item for (model, _item_id), item in self.values.items() if model is entity)

    def scalar(self, statement):
        rows = self.scalars(statement).all()
        return rows[0] if rows else None

    def add(self, item):
        self.added.append(item)
        if getattr(item, "id", None):
            self.values[(type(item), item.id)] = item

    def flush(self):
        return None

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, _item):
        return None


def user(role: str = "staff"):
    return SimpleNamespace(id="staff-1", role=role)


def editable_template(**patch) -> OutputTemplateConfig:
    values = {
        "id": "template-1",
        "revision": 3,
        "name": "Insurer-independent Motor",
        "insurance_type": "Motor",
        "insurance_company_id": "legacy-company-only",
        "fixed_fields": template_config(),
        "status": "active",
    }
    values.update(patch)
    return OutputTemplateConfig(**values)


def test_publish_creates_exact_immutable_revision_and_canonical_page_profile():
    template = editable_template()
    db = FakeDb([template])

    published = publish_template_revision(db, user(), template.id, base_revision=3)

    assert published.state == "published"
    assert published.revision_number == 1
    assert published.published_by == "staff-1"
    assert published.published_at is not None
    assert published.config["template_name"] == template.name
    assert "insurance_company_id" not in published.config
    assert published.config["page_profile"]["profile_key"] == "a4"
    assert len(published.config_hash) == 64
    assert template.revision == 4
    assert any(isinstance(item, TemplatePageProfile) for item in db.added)
    assert any(isinstance(item, AuditEvent) and item.action == "template.publish" for item in db.added)
    assert db.commits == 1


def test_same_content_publish_is_idempotent_and_stale_base_fails_closed():
    template = editable_template()
    db = FakeDb([template])
    first = publish_template_revision(db, user(), template.id, base_revision=3)
    second = publish_template_revision(db, user(), template.id, base_revision=4)

    assert second.id == first.id
    assert template.revision == 4
    assert db.commits == 1

    with pytest.raises(AppError) as error:
        publish_template_revision(db, user(), template.id, base_revision=3)
    assert error.value.status_code == 409


def test_new_publication_rejects_legacy_manual_benefit_content():
    template = editable_template(fixed_fields=template_config(legacy=True))
    db = FakeDb([template])

    with pytest.raises(AppError, match="legacy manual") as error:
        publish_template_revision(db, user(), template.id, base_revision=3)

    assert error.value.status_code == 422
    assert not any(isinstance(item, TemplateRevision) for item in db.added)
    assert db.rollbacks == 1


def test_published_options_return_only_latest_revision_without_company_filtering():
    first = editable_template()
    second = editable_template(
        id="template-2",
        name="Long Master",
        insurance_company_id="another-legacy-company",
    )
    profile = TemplatePageProfile(
        id="profile-1",
        profile_key="a4",
        name="A4",
        width=794,
        height=1123,
        unit="px",
        safe_margins={},
        bleed={},
        status="active",
    )
    revisions = [
        TemplateRevision(id="r1", template_id=first.id, revision_number=1, state="published", page_profile_id=profile.id, config=template_config(), config_hash="1" * 64),
        TemplateRevision(id="r2", template_id=first.id, revision_number=2, state="published", page_profile_id=profile.id, config=template_config(), config_hash="2" * 64),
        TemplateRevision(id="r3", template_id=second.id, revision_number=1, state="retired", page_profile_id=profile.id, config=template_config(), config_hash="3" * 64),
    ]
    db = FakeDb([first, second, profile, *revisions])

    options = list_published_templates(db, user())

    assert options == [{
        "template_id": first.id,
        "template_revision_id": "r2",
        "name": first.name,
        "revision_number": 2,
        "config_hash": "2" * 64,
        "page_profile": {
            "id": profile.id,
            "profile_key": "a4",
            "name": "A4",
            "width": 794.0,
            "height": 1123.0,
            "unit": "px",
            "safe_margins": {},
            "background_behavior": "clip",
        },
    }]
    assert list_page_profiles(db, user())[0]["profile_key"] == "a4"


def test_non_business_role_cannot_publish_or_list_templates():
    db = FakeDb([editable_template()])
    with pytest.raises(AppError) as error:
        publish_template_revision(db, user("dev"), "template-1", base_revision=3)
    assert error.value.status_code == 403
    with pytest.raises(AppError) as error:
        list_published_templates(db, user("dev"))
    assert error.value.status_code == 403
