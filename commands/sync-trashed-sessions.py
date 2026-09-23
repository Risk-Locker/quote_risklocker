"""Synchronize sessions whose underlying uploaded files are already deleted to status='trash'."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.db.session import SessionLocal
from app.models.tables import Session as SessionModel, UploadedFile


def sync_trashed_sessions() -> int:
    db = SessionLocal()
    try:
        orphan_sessions = (
            db.query(SessionModel)
            .join(UploadedFile, SessionModel.uploaded_file_id == UploadedFile.id)
            .filter(UploadedFile.deleted_at.is_not(None), SessionModel.status != "trash")
            .all()
        )
        count = len(orphan_sessions)
        if count > 0:
            for s in orphan_sessions:
                s.status = "trash"
            db.commit()
            print(f"Successfully synchronized {count} session(s) to status='trash'.")
        else:
            print("All sessions with deleted uploaded files are already marked status='trash'.")
        return count
    finally:
        db.close()


if __name__ == "__main__":
    sync_trashed_sessions()
