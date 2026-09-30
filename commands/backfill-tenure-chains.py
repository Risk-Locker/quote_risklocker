"""Backfill multi-year tenure chains (2024 - 2029) for all tracked vehicles."""

import sys
from pathlib import Path

# Add backend directory to sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.tables import TrackedVehicle, InsuranceTenure
from app.services.insurance_tenure_service import ensure_vehicle_tenure_chain

def run_backfill():
    db = SessionLocal()
    try:
        vehicles = list(db.scalars(select(TrackedVehicle)).all())
        print(f"Discovered {len(vehicles)} tracked vehicles in database.")

        total_created = 0
        for veh in vehicles:
            # Find the best anchor tenure for this vehicle
            anchor = db.scalar(
                select(InsuranceTenure)
                .where(InsuranceTenure.tracked_vehicle_id == veh.id)
                .order_by(InsuranceTenure.created_at.asc())
                .limit(1)
            )
            if not anchor:
                continue

            created = ensure_vehicle_tenure_chain(db, anchor, target_years=(2024, 2025, 2026, 2027, 2028, 2029))
            total_created += len(created)

        db.commit()
        print(f"Successfully backfilled {total_created} multi-year tenure templates across 2024-2029.")
    finally:
        db.close()

if __name__ == "__main__":
    run_backfill()
