"""RL-DISABLED automatic PDF expiry — disabled 2026-08-13; v7 uses manual reference-aware deletion."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.storage.supabase import SupabaseStorage


def purge_expired_pdfs(db: Session, storage: SupabaseStorage, *, limit: int = 200) -> dict:
    return {"processed": 0, "deleted": 0, "failures": [], "disabled": True}
