"""Run the bounded Risklocker Postgres job worker."""

from __future__ import annotations

import argparse
import os
import socket
import sys
import time
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings
from app.db.session import SessionLocal, verify_database_connection, verify_schema_version
from app.workers.extraction_worker import run_one_job
from app.services.worker_health import heartbeat_worker


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one bounded Risklocker extraction/render worker.")
    parser.add_argument("--once", action="store_true", help="Claim at most one job and exit.")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()
    if args.poll_seconds < 0.25 or args.poll_seconds > 60:
        parser.error("--poll-seconds must be between 0.25 and 60")

    settings = get_settings()
    verify_database_connection()
    verify_schema_version()
    worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"
    print(f"Risklocker worker {worker_id} started.", flush=True)
    while True:
        with SessionLocal() as db:
            heartbeat_worker(
                db,
                worker_id=worker_id,
                process_id=os.getpid(),
                state="polling",
                release_id=os.getenv("RELEASE_ID"),
            )
            job = run_one_job(db, settings, worker_id=worker_id)
            heartbeat_worker(
                db,
                worker_id=worker_id,
                process_id=os.getpid(),
                state="idle",
                release_id=os.getenv("RELEASE_ID"),
            )
        if args.once:
            return 0
        if job is None:
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
