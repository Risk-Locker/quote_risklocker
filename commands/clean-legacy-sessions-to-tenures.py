"""Clean legacy duplicate sessions and populate Insurance Tenure entities.

Usage:
    python commands/clean-legacy-sessions-to-tenures.py           # Dry-run preview
    python commands/clean-legacy-sessions-to-tenures.py --write   # Commit changes
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.db.session import SessionLocal
from app.models.tables import InsuranceTenure, Session as SessionModel, TrackedVehicle
from app.services.insurance_tenure_service import (
    compute_quotation_content_hash,
    resolve_or_create_tenure,
)
from app.services.vehicle_tracking_service import normalize_plate


def clean_legacy_sessions(write: bool = False) -> None:
    db = SessionLocal()
    mode_label = "EXECUTION (COMMITTING CHANGES)" if write else "DRY RUN (NO CHANGES WRITTEN)"
    print(f"=== Legacy Session Cleanup & Tenure Migration: {mode_label} ===")

    try:
        # 1. Fetch all active non-trashed sessions
        sessions = (
            db.query(SessionModel)
            .filter(SessionModel.status != "trash")
            .order_by(SessionModel.created_at.desc())
            .all()
        )
        print(f"Loaded {len(sessions)} active sessions.")

        # 2. Group sessions by (plate_number, company)
        groups: dict[tuple[str, str], list[SessionModel]] = defaultdict(list)

        for s in sessions:
            draft = s.draft
            fields = draft.fields if draft else {}
            raw_plate = (
                fields.get("vehicle_no", {}).get("value")
                or fields.get("vehicle_number", {}).get("value")
                or (s.tracked_vehicle.vehicle_no if s.tracked_vehicle else "")
                or ""
            )
            norm_p = normalize_plate(raw_plate)
            comp = (s.detected_company or "unknown").strip().lower()

            # Fallback key if plate is missing
            key = (norm_p or f"NO_PLATE_{s.id[:8]}", comp)
            groups[key].append(s)

        kept_count = 0
        trashed_count = 0
        tenure_map: dict[str, InsuranceTenure] = {}

        for (plate, comp), group in groups.items():
            if len(group) == 1:
                best = group[0]
                duplicates = []
            else:
                # Rank: prioritize session with generated RL quotation reference, then latest created_at
                def _score(item: SessionModel) -> tuple[int, datetime]:
                    has_rl = 1 if (item.quotation_ref and str(item.quotation_ref).startswith("RL")) else 0
                    dt = item.created_at or datetime.min.replace(tzinfo=timezone.utc)
                    return (has_rl, dt)

                sorted_group = sorted(group, key=_score, reverse=True)
                best = sorted_group[0]
                duplicates = sorted_group[1:]

            kept_count += 1
            for dup in duplicates:
                trashed_count += 1
                dup.status = "trash"
                dup.is_tenure_active = False

            # Resolve / link tenure for the retained session
            draft = best.draft
            fields = draft.fields if draft else {}
            customer = str(fields.get("customer_name", {}).get("value") or "").strip()
            c_start = fields.get("cover_start_date", {}).get("value") or fields.get("issue_date", {}).get("value")
            c_end = fields.get("cover_end_date", {}).get("value") or fields.get("valid_until", {}).get("value")

            if plate and not plate.startswith("NO_PLATE"):
                tenure = resolve_or_create_tenure(
                    db,
                    vehicle_no=plate,
                    customer_name=customer,
                    start_date=c_start,
                    end_date=c_end,
                    tracked_vehicle_id=best.tracked_vehicle_id,
                )
                best.tenure_id = tenure.id
                best.tenure_version = 1
                best.is_tenure_active = True
                best.content_hash = compute_quotation_content_hash(fields, draft.selections if hasattr(draft, "selections") else None)
                tenure_map[tenure.id] = tenure

        print(f"\n--- Cleanup Summary ---")
        print(f"Total groups processed: {len(groups)}")
        print(f"Retained active sessions: {kept_count}")
        print(f"Redundant sessions moved to trash: {trashed_count}")
        print(f"Insurance tenures resolved/created: {len(tenure_map)}")

        if write:
            db.commit()
            print("\nSuccessfully committed changes to database.")
        else:
            db.rollback()
            print("\nDry-run completed. Rolled back all changes (safe).")

    except Exception as e:
        db.rollback()
        print(f"\nERROR during cleanup: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean legacy sessions to tenures")
    parser.add_argument("--write", action="store_true", help="Commit changes to database")
    args = parser.parse_args()

    clean_legacy_sessions(write=args.write)
