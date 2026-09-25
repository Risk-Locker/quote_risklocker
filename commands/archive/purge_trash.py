"""Purge expired trash records.

This script is intentionally conservative; it only deletes records whose purge_after
date has already passed.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.tables import UploadedFile


if __name__ == "__main__":
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        records = list(db.scalars(select(UploadedFile).where(UploadedFile.deleted_at.is_not(None), UploadedFile.purge_after <= now)).all())
        for record in records:
            db.delete(record)
        db.commit()
        print(f"Purged {len(records)} expired records.")
