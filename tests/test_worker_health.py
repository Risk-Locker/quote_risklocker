"""Worker heartbeat readiness contract."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.models.tables import WorkerHeartbeat
from app.services.worker_health import WORKER_STALE_SECONDS, worker_readiness


class Db:
    def __init__(self, record=None):
        self.record = record

    def scalar(self, _statement):
        return self.record


def test_worker_readiness_requires_a_recent_heartbeat():
    now = datetime.now(timezone.utc)
    assert worker_readiness(Db(), now=now)["ready"] is False
    current = WorkerHeartbeat(worker_id="worker-1", process_id=42, state="idle", started_at=now, heartbeat_at=now)
    assert worker_readiness(Db(current), now=now)["ready"] is True
    current.heartbeat_at = now - timedelta(seconds=WORKER_STALE_SECONDS + 1)
    result = worker_readiness(Db(current), now=now)
    assert result["ready"] is False
    assert result["reason"] == "Worker heartbeat is stale."
