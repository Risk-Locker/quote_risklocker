"""Clean legacy seeded test records and dummy client artifacts.

Usage:
    python commands/clean-legacy-test-data.py           # Dry-run report
    python commands/clean-legacy-test-data.py --apply   # Commit cleanup to database
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import delete, select, text
from app.db.session import SessionLocal
from app.models.tables import ClientRecord, Session as SessionModel, User, UploadedFile


def audit_and_clean(apply_changes: bool = False) -> None:
    db = SessionLocal()
    try:
        print("=== Auditing Seeded / Legacy Test Data ===")
        
        # 1. Inspect ClientRecord table
        legacy_records = db.scalars(select(ClientRecord)).all()
        print(f"\n1. Legacy Client Records Found: {len(legacy_records)}")
        for r in legacy_records:
            print(f"   - ID: {r.id} | Insurer No: {r.insurer_no} | Plate: {r.vehicle_no} | Customer: {r.customer_name} | Deleted: {r.deleted_at is not None}")

        # 2. Inspect Users table
        test_users = db.scalars(
            select(User).where(User.email.in_(["admin@test.local", "test@test.local", "demo@risklocker.local"]))
        ).all()
        print(f"\n2. Test / Seeded Users Found: {len(test_users)}")
        for u in test_users:
            print(f"   - User ID: {u.id} | Email: {u.email} | Name: {u.name} | Role: {u.role}")

        # 3. Inspect Sessions without files or drafts
        orphans = db.scalars(
            select(SessionModel).where(
                (SessionModel.uploaded_file_id.is_(None)) | (SessionModel.draft_id.is_(None))
            )
        ).all()
        print(f"\n3. Orphan / Incomplete Sessions Found: {len(orphans)}")
        for o in orphans:
            print(f"   - Session ID: {o.id} | Status: {o.status} | FileID: {o.uploaded_file_id} | DraftID: {o.draft_id}")

        if not apply_changes:
            print("\n[DRY RUN] No database changes committed. Run with '--apply' to purge these items.")
            return

        print("\n--- Applying Cleanup ---")
        # Delete legacy client records
        if legacy_records:
            record_ids = [r.id for r in legacy_records]
            db.execute(delete(ClientRecord).where(ClientRecord.id.in_(record_ids)))
            print(f"[OK] Purged {len(legacy_records)} legacy client records.")

        # Deactivate test users
        if test_users:
            for u in test_users:
                u.status = "inactive"
            print(f"[OK] Deactivated {len(test_users)} test users (status=inactive).")

        # Soft-delete or purge orphan sessions
        if orphans:
            for o in orphans:
                o.status = "trash"
            print(f"[OK] Moved {len(orphans)} orphan sessions to trash.")

        db.commit()
        print("\n[OK] Cleanup successfully completed and committed to database!")

    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] Cleanup failed: {e}")
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Clean legacy test data and dummy records")
    parser.add_argument("--apply", action="store_true", help="Execute deletion and commit changes")
    args = parser.parse_args()
    audit_and_clean(apply_changes=args.apply)


if __name__ == "__main__":
    main()
