"""Shared Staff record-access contract."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.auth.rbac import can_view_owner_record
from app.services.review_service import list_trash
from app.services.session_service import list_sessions


class Rows:
    def all(self):
        return []


class CaptureDb:
    def __init__(self):
        self.scalar_statements = []
        self.scalars_statements = []

    def scalar(self, statement):
        self.scalar_statements.append(statement)
        return 0

    def scalars(self, statement):
        self.scalars_statements.append(statement)
        return Rows()


def user(role: str, user_id: str = "staff-a"):
    return SimpleNamespace(role=role, id=user_id)


def test_authenticated_business_roles_share_record_access():
    for role in ("staff", "admin", "super_admin"):
        assert can_view_owner_record(SimpleNamespace(), user(role), "another-owner") is True
    assert can_view_owner_record(SimpleNamespace(), user("unknown"), "another-owner") is False


def test_session_listing_has_no_owner_predicate_for_staff():
    db = CaptureDb()

    list_sessions(db, "staff-a")

    statements = [str(statement) for statement in db.scalar_statements + db.scalars_statements]
    assert statements
    assert all("WHERE sessions.owner_id" not in statement for statement in statements)


def test_staff_trash_listing_has_no_owner_predicate():
    db = CaptureDb()

    list_trash(db, user("staff"))

    statement = str(db.scalars_statements[0])
    assert "uploaded_files.owner_id" not in statement.split("WHERE", 1)[-1]
