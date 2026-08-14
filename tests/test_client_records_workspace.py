from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.models.tables import AuditEvent, Base, ClientRecord, RecordSavedView, User  # noqa: E402
from app.services.client_record_service import (  # noqa: E402
    list_records_page,
    list_saved_views,
    save_view,
    set_records_archived,
)


def database():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_records_are_paginated_filtered_archived_and_audited():
    engine = database()
    with Session(engine) as db:
        user = User(id=str(uuid4()), email="staff@example.test", password_hash="x", role="staff", status="active")
        db.add(user)
        for index in range(5):
            db.add(ClientRecord(
                id=str(uuid4()), insurer_no=f"QBE-{index}", insurance_company="QBE" if index < 3 else "Etiqa",
                vehicle_no=f"JXS{index}", customer_name=f"Customer {index}", raw_values={},
            ))
        db.commit()

        first = list_records_page(db, company="QBE", state="active", page=1, page_size=2)
        assert first["total"] == 3
        assert len(first["items"]) == 2
        assert first["companies"] == ["Etiqa", "QBE"]

        changed = set_records_archived(db, user, [first["items"][0].id], archived=True)
        assert len(changed) == 1
        assert list_records_page(db, company="QBE", state="archived", page=1, page_size=10)["total"] == 1
        assert db.query(AuditEvent).filter(AuditEvent.action == "records.archive").count() == 1


def test_saved_record_views_are_revisioned_and_shared():
    engine = database()
    with Session(engine) as db:
        owner = User(id=str(uuid4()), email="owner@example.test", password_hash="x", role="staff", status="active")
        colleague = User(id=str(uuid4()), email="staff@example.test", password_hash="x", role="staff", status="active")
        db.add_all([owner, colleague])
        db.commit()
        view = save_view(db, owner, {"name": "QBE active", "filters": {"company": "QBE", "state": "active"}, "is_shared": True})
        assert view.revision == 1
        assert [item.id for item in list_saved_views(db, colleague)] == [view.id]
        updated = save_view(db, owner, {"id": view.id, "base_revision": 1, "name": view.name, "filters": {"company": "QBE", "state": "archived"}, "is_shared": True})
        assert updated.revision == 2
        assert db.query(RecordSavedView).count() == 1
