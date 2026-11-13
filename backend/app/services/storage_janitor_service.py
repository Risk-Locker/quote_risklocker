"""Storage Janitor Service.

Safely prunes superseded and duplicate quotation PDF files from local disk and remote S3/Supabase storage,
reclaiming storage bytes while guaranteeing strict protection of:
- Active renewal sessions (is_tenure_active is True)
- Bound Cover Notes (tenure.covernote_session_id)
- Business assets (business_assets)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import (
    BusinessAsset,
    InsuranceTenure,
    Session as SessionModel,
    TenureComparisonEntry,
    UploadedFile,
)

logger = logging.getLogger(__name__)


def delete_file_safely(file_path: str | None, object_key: str | None = None, storage_client: Any | None = None) -> bool:
    """Safely delete physical file on disk and/or remote object storage."""
    deleted_any = False

    # 1. Remote S3 / Supabase storage
    if storage_client and object_key:
        try:
            if hasattr(storage_client, "delete_pdf"):
                storage_client.delete_pdf(object_key)
                deleted_any = True
            elif hasattr(storage_client, "delete_object"):
                storage_client.delete_object(object_key)
                deleted_any = True
        except Exception as e:
            logger.warning("Failed to delete remote storage key %s: %s", object_key, e)

    # 2. Local disk file
    if file_path:
        try:
            p = Path(file_path)
            if p.exists() and p.is_file():
                p.unlink()
                deleted_any = True
        except Exception as e:
            logger.warning("Failed to delete local file %s: %s", file_path, e)

    return deleted_any


def prune_superseded_quotations(
    db: Session,
    tenure_id: str | None = None,
    dry_run: bool = False,
    storage_client: Any | None = None,
) -> dict[str, Any]:
    """Scan and prune superseded quotation files, reclaiming storage space.

    Guarantees asset protection:
    - Never prunes files referenced by active sessions.
    - Never prunes files referenced by bound Cover Notes.
    - Never prunes files referenced by BusinessAsset records.
    """
    now = datetime.now(timezone.utc)

    # 1. Query candidate superseded/inactive sessions
    query = select(SessionModel).where(
        (SessionModel.is_tenure_active.is_(False))
        | (SessionModel.duplicate_resolution.in_(["superseded", "superseded_pruned"]))
        | (SessionModel.status.in_(["trash", "archived"]))
    )
    if tenure_id:
        query = query.where(SessionModel.tenure_id == tenure_id)

    candidate_sessions = list(db.scalars(query).all())
    if not candidate_sessions:
        return {
            "dry_run": dry_run,
            "tenure_id": tenure_id,
            "pruned_files_count": 0,
            "reclaimed_bytes": 0,
            "pruned_file_ids": [],
            "pruned_sessions_count": 0,
        }

    candidate_file_ids = {s.uploaded_file_id for s in candidate_sessions if s.uploaded_file_id}
    if not candidate_file_ids:
        return {
            "dry_run": dry_run,
            "tenure_id": tenure_id,
            "pruned_files_count": 0,
            "reclaimed_bytes": 0,
            "pruned_file_ids": [],
            "pruned_sessions_count": len(candidate_sessions),
        }

    # 2. Query all active sessions to build protected file IDs (E-06)
    active_sessions = list(
        db.scalars(
            select(SessionModel).where(
                SessionModel.uploaded_file_id.in_(candidate_file_ids),
                SessionModel.is_tenure_active.is_(True),
                SessionModel.status != "trash",
            )
        ).all()
    )
    protected_file_ids = {s.uploaded_file_id for s in active_sessions if s.uploaded_file_id}

    # 3. Query all bound Cover Notes to protect their files
    bound_tenures = list(
        db.scalars(
            select(InsuranceTenure).where(
                InsuranceTenure.covernote_session_id.is_not(None)
            )
        ).all()
    )
    bound_session_ids = {t.covernote_session_id for t in bound_tenures if t.covernote_session_id}
    if bound_session_ids:
        cn_sessions = list(
            db.scalars(
                select(SessionModel).where(SessionModel.id.in_(bound_session_ids))
            ).all()
        )
        for cns in cn_sessions:
            if cns.uploaded_file_id:
                protected_file_ids.add(cns.uploaded_file_id)

    # 4. Query BusinessAsset paths to protect assets
    asset_paths = set(
        db.scalars(select(BusinessAsset.storage_path)).all()
    )

    # 5. Filter files eligible for pruning
    eligible_ids = candidate_file_ids - protected_file_ids
    if not eligible_ids:
        return {
            "dry_run": dry_run,
            "tenure_id": tenure_id,
            "pruned_files_count": 0,
            "reclaimed_bytes": 0,
            "pruned_file_ids": [],
            "pruned_sessions_count": 0,
        }

    files_to_prune = list(
        db.scalars(
            select(UploadedFile).where(
                UploadedFile.id.in_(eligible_ids),
                UploadedFile.storage_status != "deleted",
            )
        ).all()
    )

    prunable_files: list[UploadedFile] = []
    for f in files_to_prune:
        if f.storage_path and f.storage_path in asset_paths:
            continue
        prunable_files.append(f)

    pruned_file_ids: list[str] = []
    reclaimed_bytes = 0

    if dry_run:
        for f in prunable_files:
            pruned_file_ids.append(f.id)
            reclaimed_bytes += f.size_bytes or 0
    else:
        for f in prunable_files:
            delete_file_safely(
                file_path=f.storage_path,
                object_key=f.storage_path,
                storage_client=storage_client,
            )
            f.status = "pruned"
            f.storage_status = "deleted"
            f.storage_deleted_at = now
            f.deleted_at = now
            pruned_file_ids.append(f.id)
            reclaimed_bytes += f.size_bytes or 0

        # Mark sessions as superseded_pruned and cleanup comparison entries
        pruned_file_set = set(pruned_file_ids)
        for s in candidate_sessions:
            if s.uploaded_file_id in pruned_file_set:
                s.is_tenure_active = False
                s.status = "trash"
                s.duplicate_resolution = "superseded_pruned"
                if s.tenure_id:
                    comp_entries = list(
                        db.scalars(
                            select(TenureComparisonEntry).where(
                                TenureComparisonEntry.tenure_id == s.tenure_id,
                                TenureComparisonEntry.session_id == s.id,
                            )
                        ).all()
                    )
                    for ce in comp_entries:
                        db.delete(ce)

        db.commit()

    return {
        "dry_run": dry_run,
        "tenure_id": tenure_id,
        "pruned_files_count": len(pruned_file_ids),
        "reclaimed_bytes": reclaimed_bytes,
        "pruned_file_ids": pruned_file_ids,
        "pruned_sessions_count": len([s for s in candidate_sessions if s.uploaded_file_id in set(pruned_file_ids)]),
    }

