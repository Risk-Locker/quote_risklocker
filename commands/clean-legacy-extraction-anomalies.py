"""Clean legacy extraction anomalies and fake vehicle plates from the database."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.db.session import SessionLocal
from app.models.tables import QuotationDraft, Session as SessionModel, TrackedVehicle, VehicleOwnership
from app.services.vehicle_tracking_service import is_valid_malaysian_plate, normalize_plate


def clean_legacy_anomalies() -> dict[str, int]:
    db = SessionLocal()
    cleaned_drafts = 0
    deleted_vehicles = 0
    deleted_ownerships = 0

    try:
        # 1. Clean invalid vehicle plates in TrackedVehicle
        tracked_vehicles = db.query(TrackedVehicle).all()
        for tv in tracked_vehicles:
            if not is_valid_malaysian_plate(tv.vehicle_no):
                # Unlink sessions
                db.query(SessionModel).filter(SessionModel.tracked_vehicle_id == tv.id).update(
                    {"tracked_vehicle_id": None}, synchronize_session=False
                )
                # Delete ownerships
                own_count = db.query(VehicleOwnership).filter(VehicleOwnership.vehicle_id == tv.id).delete(
                    synchronize_session=False
                )
                deleted_ownerships += own_count
                db.delete(tv)
                deleted_vehicles += 1

        # 2. Clean invalid vehicle_no in QuotationDraft fields
        drafts = db.query(QuotationDraft).all()
        for d in drafts:
            if not d.fields or "vehicle_no" not in d.fields:
                continue

            v_entry = d.fields.get("vehicle_no")
            val = v_entry.get("value") if isinstance(v_entry, dict) else v_entry
            if val and not is_valid_malaysian_plate(str(val)):
                # Remove or blank the invalid plate
                new_fields = dict(d.fields)
                if isinstance(v_entry, dict):
                    new_fields["vehicle_no"] = {**v_entry, "value": ""}
                else:
                    new_fields["vehicle_no"] = ""
                d.fields = new_fields
                cleaned_drafts += 1

        db.commit()
        print(
            f"Successfully cleaned: {deleted_vehicles} invalid vehicles, "
            f"{deleted_ownerships} ownership records, {cleaned_drafts} draft fields."
        )
        return {
            "deleted_vehicles": deleted_vehicles,
            "deleted_ownerships": deleted_ownerships,
            "cleaned_drafts": cleaned_drafts,
        }
    except Exception as e:
        db.rollback()
        print(f"Error during legacy cleanup: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    clean_legacy_anomalies()
