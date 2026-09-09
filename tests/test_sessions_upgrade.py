from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.models.tables import (
    Session as SessionModel,
    UploadedFile,
    QuotationDraft,
    User,
)
from app.services.session_service import serialize_session, get_session_filter_options
from app.services.auth_service import serialize_user


def test_serialize_session_defaults_and_authorship():
    owner = User(
        id="user-nina",
        name="Nina",
        email="nina@risklocker.local",
        role="staff",
    )
    editor = User(
        id="user-alex",
        name="Alex",
        email="alex@risklocker.local",
        role="staff",
    )
    uploaded = UploadedFile(
        id="up-1",
        batch_id="batch-1",
        owner_id="user-nina",
        original_filename="Quotation_Civic.pdf",
    )
    draft = QuotationDraft(
        id="draft-1",
        uploaded_file_id="up-1",
        owner_id="user-nina",
        status="ready",
        fields={
            "customer_name": {"value": "Tan Sri Ahmad"},
            "vehicle_no": {"value": "JJC9250"},
            "car_model": {"value": "Honda Civic"},
            "total_amount": {"value": "2,145.50"},
            "quotation_reference": {"value": "RL260000148"},
        },
    )
    session = SessionModel(
        id="sess-1",
        owner_id="user-nina",
        uploaded_file_id="up-1",
        draft_id="draft-1",
        detected_company="Allianz",
        quotation_ref="RL260000148",
        created_at=datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc),
        last_edited_by_id="user-alex",
        last_edited_at=datetime(2026, 9, 4, 14, 23, 45, tzinfo=timezone.utc),
    )
    session.owner = owner
    session.last_edited_by = editor
    session.uploaded_file = uploaded
    session.draft = draft

    # Serialize session cleanly
    data = serialize_session(session)

    assert data["id"] == "sess-1"
    assert data["quotation_ref"] == "RL260000148"
    assert data["created_by"] == "Nina"
    assert data["created_by_email"] == "nina@risklocker.local"
    assert data["last_edited_by"] == "Alex"
    assert data["last_edited_by_email"] == "alex@risklocker.local"
    assert data["last_edited_at"] == "2026-09-04T14:23:45+00:00"
    assert data["is_edited"] is True
    assert data["insured_name"] == "Tan Sri Ahmad"
    assert data["vehicle_plate"] == "JJC9250"
    assert data["total_premium"] == "2,145.50"


def test_serialize_session_unedited():
    owner = User(
        id="user-nina",
        name=None,
        email="nina@risklocker.local",
        role="staff",
    )
    uploaded = UploadedFile(
        id="up-2",
        batch_id="batch-1",
        owner_id="user-nina",
        original_filename="Quotation_Raw.pdf",
    )
    draft = QuotationDraft(
        id="draft-2",
        uploaded_file_id="up-2",
        owner_id="user-nina",
        status="check_needed",
        fields={
            "customer_name": {"value": "John Doe"},
            "vehicle_no": {"value": "WUN762"},
        },
    )
    session = SessionModel(
        id="sess-2",
        owner_id="user-nina",
        uploaded_file_id="up-2",
        draft_id="draft-2",
        detected_company="Kurnia",
        quotation_ref="RL260000149",
        created_at=datetime(2026, 9, 4, 12, 30, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 9, 4, 12, 30, 0, tzinfo=timezone.utc),
        last_edited_by_id=None,
        last_edited_at=None,
    )
    session.owner = owner
    session.last_edited_by = None
    session.uploaded_file = uploaded
    session.draft = draft

    # Name fallback from email prefix
    data = serialize_session(session)

    assert data["created_by"] == "Nina"
    assert data["last_edited_by"] is None
    assert data["last_edited_at"] is None
    assert data["is_edited"] is False


def test_serialize_user_includes_name():
    user_with_name = User(
        id="u1",
        name="Alex Tan",
        email="alex@risklocker.local",
        role="staff",
        status="active",
    )
    data = serialize_user(user_with_name)
    assert data["name"] == "Alex Tan"
    assert data["email"] == "alex@risklocker.local"

    user_without_name = User(
        id="u2",
        name=None,
        email="admin@risklocker.local",
        role="admin",
        status="active",
    )
    data2 = serialize_user(user_without_name)
    assert data2["name"] == "Admin"


def test_apply_workspace_patch_stamps_session_editor():
    from tests.test_workspace_service import FakeDb, objects, user
    from app.services.workspace_service import apply_workspace_patch

    db = FakeDb(objects())
    alex = user("staff")
    alex.id = "user-alex"
    apply_workspace_patch(
        db,
        alex,
        "draft-1",
        base_revision=3,
        operations=[{"op": "scalar_decision", "field": "customer_name", "decision": "edit", "value": "Correct Name"}],
    )
    session = db.get(SessionModel, "session-1")
    assert session is not None
    assert session.last_edited_by_id == "user-alex"
    assert session.last_edited_at is not None
