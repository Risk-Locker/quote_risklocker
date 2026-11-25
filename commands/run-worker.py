"""Run the bounded Risklocker Postgres job worker."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import os
import socket
import sys
import threading
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


def _run_slot_loop(slot_idx: int, settings, *, poll_seconds: float, job_types: list[str] | None, once: bool, stop_event: threading.Event) -> None:
    worker_id = f"{socket.gethostname()}:{os.getpid()}:w{slot_idx}:{uuid4().hex[:6]}"
    print(f"Risklocker worker slot {worker_id} started (job_types={job_types or 'all'}).", flush=True)
    while not stop_event.is_set():
        job = None
        try:
            with SessionLocal() as db:
                heartbeat_worker(
                    db,
                    worker_id=worker_id,
                    process_id=os.getpid(),
                    state="polling",
                    release_id=os.getenv("RELEASE_ID"),
                )
                job = run_one_job(db, settings, worker_id=worker_id, job_types=job_types)
                heartbeat_worker(
                    db,
                    worker_id=worker_id,
                    process_id=os.getpid(),
                    state="idle",
                    release_id=os.getenv("RELEASE_ID"),
                )
        except Exception as exc:
            print(f"Worker slot {worker_id} iteration error: {exc}", flush=True)
            time.sleep(2.0)
        if once:
            return
        if job is None:
            stop_event.wait(poll_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run bounded Risklocker extraction/render worker slots.")
    parser.add_argument("--once", action="store_true", help="Claim at most one job and exit.")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--concurrency", type=int, default=int(os.getenv("WORKER_CONCURRENCY", "3") or "3"))
    parser.add_argument("--job-types", type=str, default=os.getenv("WORKER_JOB_TYPES", ""))
    args = parser.parse_args()
    if args.poll_seconds < 0.25 or args.poll_seconds > 60:
        parser.error("--poll-seconds must be between 0.25 and 60")

    concurrency = max(1, min(int(args.concurrency), 4))
    raw_types = [t.strip() for t in (args.job_types or "").split(",") if t.strip()]
    job_types = raw_types or None

    settings = get_settings()
    verify_database_connection()
    verify_schema_version()

    if args.once or concurrency == 1:
        _run_slot_loop(0, settings, poll_seconds=args.poll_seconds, job_types=job_types, once=args.once, stop_event=threading.Event())
        return 0

    stop_event = threading.Event()
    try:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futs = [
                pool.submit(_run_slot_loop, idx, settings, poll_seconds=args.poll_seconds, job_types=job_types, once=False, stop_event=stop_event)
                for idx in range(concurrency)
            ]
            for f in futs:
                f.result()
    except KeyboardInterrupt:
        stop_event.set()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
