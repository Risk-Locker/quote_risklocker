"""Run one Supabase PDF retention cycle."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services.storage_retention import purge_expired_pdfs  # noqa: E402
from app.storage.supabase import SupabaseStorage  # noqa: E402


if __name__ == "__main__":
    settings = get_settings()
    with SessionLocal() as db:
        result = purge_expired_pdfs(db, SupabaseStorage(settings))
    print(result)
    raise SystemExit(1 if result["failures"] else 0)
