"""Regression tests for categorized trash (templates, specials, variants, records)."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": "postgresql://postgres:password@db.test.supabase.co:5432/postgres",
        "AUTH_HASH_SECRET": "test-auth-hash-secret-that-is-long-enough",
        "SUPABASE_URL": "https://project-ref.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
    }
)

from app.core.errors import AppError  # noqa: E402
from typing import Any
from app.models.tables import OurSpecial, OurSpecialVariant, OutputTemplateConfig  # noqa: E402
from app.services import trash_service  # noqa: E402
from app.services.template_config import default_template_config  # noqa: E402


def _settings() -> Any:
    return SimpleNamespace(trash_retention_days=14)


def _user() -> Any:
    return SimpleNamespace(id=str(uuid4()), role="admin")


def _fake_db() -> Any:
    return FakeDb()


class FakeDb:
    def __init__(self):
        self._items: list = []
        self.added: list = []
        self.commits = 0

    def seed(self, *items):
        self._items.extend(items)

    def get(self, model, object_id):
        sid = str(object_id)
        return next((i for i in self._items if type(i) is model and str(i.id) == sid), None)

    def scalars(self, statement):
        try:
            cls = statement.column_descriptions[0]["type"]
        except Exception:
            cls = None
        return _ScalarResult(
            [
                i
                for i in self._items
                if (cls is None or isinstance(i, cls)) and getattr(i, "deleted_at", None) is not None
            ]
        )

    def add(self, value):
        self.added.append(value)
        self._items.append(value)

    def execute(self, _statement):
        return None

    def delete(self, value):
        if value in self._items:
            self._items.remove(value)

    def commit(self):
        self.commits += 1


class _ScalarResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)


def _template(name="Copy of Test", locked=False) -> OutputTemplateConfig:
    config = default_template_config("Motor", locked=locked)
    return OutputTemplateConfig(
        id=str(uuid4()),
        name=name,
        insurance_type="Motor",
        fixed_fields=config,
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _special(label="Towing") -> OurSpecial:
    return OurSpecial(
        id=str(uuid4()),
        label=label,
        category="FOC",
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _variant(special_id: str, label="V1") -> OurSpecialVariant:
    return OurSpecialVariant(
        id=str(uuid4()),
        special_id=special_id,
        label=label,
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def test_delete_template_rejects_locked_default():
    db = _fake_db()
    template = _template(locked=True)
    db.seed(template)

    with pytest.raises(AppError, match="cannot be deleted"):
        trash_service.delete_template(db, _settings(), _user(), template.id)


def test_delete_template_soft_deletes_editable_copy():
    db = _fake_db()
    template = _template()
    db.seed(template)

    trash_service.delete_template(db, _settings(), _user(), template.id)

    assert template.deleted_at is not None
    assert template.purge_after is None
    assert template.status == "inactive"
    assert db.commits == 1
    assert any(getattr(e, "entity_type", None) == "template" for e in db.added)


def test_restore_template_clears_deleted_at():
    db = _fake_db()
    template = _template()
    db.seed(template)
    trash_service.delete_template(db, _settings(), _user(), template.id)

    trash_service.restore_template(db, _user(), template.id)

    assert template.deleted_at is None
    assert template.purge_after is None
    assert template.status == "active"


def test_delete_special_soft_deletes_variants_too():
    db = _fake_db()
    special = _special()
    variant = _variant(special.id)
    special.variants = [variant]
    db.seed(special, variant)

    trash_service.delete_special(db, _settings(), _user(), special.id)

    assert special.deleted_at is not None
    assert variant.deleted_at is not None


def test_restore_special_restores_variants():
    db = _fake_db()
    special = _special()
    variant = _variant(special.id)
    special.variants = [variant]
    db.seed(special, variant)
    trash_service.delete_special(db, _settings(), _user(), special.id)

    trash_service.restore_special(db, _user(), special.id)

    assert special.deleted_at is None
    assert variant.deleted_at is None
    assert special.status == "active"
    assert variant.status == "active"


def test_delete_client_record_soft_deletes():
    from app.models.tables import ClientRecord

    db = _fake_db()
    record = ClientRecord(
        id=str(uuid4()),
        insurer_no="NO-001",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.seed(record)

    trash_service.delete_client_record(db, _settings(), _user(), record.id)
    assert record.deleted_at is not None

    trash_service.restore_client_record(db, _user(), record.id)
    assert record.deleted_at is None


def test_trash_list_categorized_shape():
    db = _fake_db()
    template = _template()
    special = _special()
    db.seed(template, special)

    data = trash_service.list_trash_categorized(db, _user(), 14)

    assert data["retention_policy"] == "manual_reference_aware_purge"
    assert set(data.keys()) == {"retention_policy", "sessions", "templates", "our_specials", "our_special_variants", "client_records", "assets"}
    assert data["templates"] == []  # nothing deleted yet
    trash_service.delete_template(db, _settings(), _user(), template.id)
    trash_service.delete_special(db, _settings(), _user(), special.id)
    data = trash_service.list_trash_categorized(db, _user(), 14)
    assert len(data["templates"]) == 1
    assert len(data["our_specials"]) == 1


def test_permanent_delete_template_removes_row():
    db = _fake_db()
    template = _template()
    db.seed(template)
    trash_service.delete_template(db, _settings(), _user(), template.id)

    trash_service.permanent_delete_template(db, _user(), template.id)

    assert db.get(type(template), template.id) is None


def test_permanent_delete_special_removes_variants():
    db = _fake_db()
    special = _special()
    variant = _variant(special.id)
    special.variants = [variant]
    db.seed(special, variant)
    trash_service.delete_special(db, _settings(), _user(), special.id)

    trash_service.permanent_delete_special(db, _user(), special.id)

    assert db.get(type(special), special.id) is None
    assert db.get(type(variant), variant.id) is None


def test_empty_all_trash_deletes_everything():
    from types import SimpleNamespace as _NS

    db = _fake_db()
    template = _template()
    special = _special()
    variant = _variant(special.id)
    special.variants = [variant]
    db.seed(template, special, variant)
    trash_service.delete_template(db, _settings(), _user(), template.id)
    trash_service.delete_special(db, _settings(), _user(), special.id)

    admin = _NS(id=str(uuid4()), role="admin")
    counts = trash_service.empty_all_trash(db, admin, _NS(delete_pdf=lambda _k: None))

    assert counts["templates"] == 1
    assert counts["our_specials"] == 1
    assert db.get(type(template), template.id) is None
    assert db.get(type(special), special.id) is None


def test_permanent_delete_session_cleans_render_snapshots_and_draft_dependencies():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models.tables import (
        Base,
        Batch,
        UploadedFile,
        QuotationDraft,
        Session as SessionModel,
        RenderSnapshot,
        QuotationActivity,
        User,
        new_id,
    )
    from types import SimpleNamespace as _NS

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    user = User(id=new_id(), email="admin@example.com", password_hash="hash", name="Admin", role="admin")
    db.add(user)
    db.flush()

    batch = Batch(id=new_id(), owner_id=user.id, name="Sample Batch")
    db.add(batch)
    db.flush()

    uploaded = UploadedFile(
        id=new_id(),
        batch_id=batch.id,
        owner_id=user.id,
        original_filename="sample.pdf",
        content_type="application/pdf",
        size_bytes=1000,
        storage_provider="local_ephemeral",
        storage_path="sample.pdf",
        deleted_at=datetime.now(timezone.utc),
    )
    db.add(uploaded)
    db.flush()

    draft = QuotationDraft(
        id=new_id(),
        owner_id=user.id,
        uploaded_file_id=uploaded.id,
        fields={"vehicle_no": {"value": "W 1234 A"}},
    )
    db.add(draft)
    db.flush()

    session = SessionModel(
        id=new_id(),
        owner_id=user.id,
        uploaded_file_id=uploaded.id,
        draft_id=draft.id,
        quotation_status="pending",
    )
    db.add(session)
    db.flush()

    # Add child dependent rows: RenderSnapshot, ExtractionRecord, ExtractionBenefitLine, DraftBenefitSelection, DraftSourceLineDecision, QuotationActivity
    from app.models.tables import (
        ExtractionRecord,
        ExtractionBenefitLine,
        DraftBenefitSelection,
        DraftSourceLineDecision,
    )

    snapshot = RenderSnapshot(
        id=new_id(),
        draft_id=draft.id,
        draft_revision=1,
        template_revision_id=new_id(),
        context_hash="hash123",
        context={},
        asset_hashes={},
        renderer_version="v7",
    )
    db.add(snapshot)

    ext_rec = ExtractionRecord(
        id=new_id(),
        uploaded_file_id=uploaded.id,
        raw_text="sample",
    )
    db.add(ext_rec)
    db.flush()

    line = ExtractionBenefitLine(
        id=new_id(),
        extraction_record_id=ext_rec.id,
        line_id="line1",
        raw_label="Towing",
        normalized_label="Towing",
    )
    db.add(line)
    db.flush()

    selection = DraftBenefitSelection(
        id=new_id(),
        draft_id=draft.id,
        selection_key="tow",
        item_kind="catalog",
        catalog_offering_id=new_id(),
    )
    db.add(selection)
    db.flush()

    decision = DraftSourceLineDecision(
        id=new_id(),
        draft_id=draft.id,
        source_line_id=line.id,
        disposition="mapped",
        selection_id=selection.id,
    )
    db.add(decision)

    activity = QuotationActivity(
        id=new_id(),
        session_id=session.id,
        vehicle_no="W 1234 A",
        customer_name="John Doe",
        action_type="quote_generated",
    )
    db.add(activity)
    db.commit()

    # Verify rows exist before deletion
    assert db.get(RenderSnapshot, snapshot.id) is not None
    assert db.get(DraftBenefitSelection, selection.id) is not None
    assert db.get(DraftSourceLineDecision, decision.id) is not None
    assert db.get(QuotationActivity, activity.id) is not None
    assert db.get(QuotationDraft, draft.id) is not None
    assert db.get(SessionModel, session.id) is not None

    # Perform permanent delete
    storage_mock = _NS(delete_pdf=lambda _path: None)
    trash_service.permanent_delete_session(db, user, uploaded.id, storage_mock)

    # Verify all dependent rows and parents are completely removed
    assert db.get(RenderSnapshot, snapshot.id) is None
    assert db.get(DraftBenefitSelection, selection.id) is None
    assert db.get(DraftSourceLineDecision, decision.id) is None
    assert db.get(QuotationActivity, activity.id) is None
    assert db.get(QuotationDraft, draft.id) is None
    assert db.get(SessionModel, session.id) is None
    assert db.get(UploadedFile, uploaded.id) is None
    db.close()

