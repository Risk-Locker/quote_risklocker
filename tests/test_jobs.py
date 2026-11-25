"""Durable Postgres job queue contracts."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.errors import AppError
from app.models.tables import Job
from app.services.job_service import (
    cancel_job,
    claim_next_job,
    claim_query,
    complete_job,
    enqueue_job,
    fail_job,
    heartbeat_job,
    serialize_job,
)


class FakeDb:
    def __init__(self, scalar_values=None):
        self.scalar_values = list(scalar_values or [])
        self.added = []
        self.commits = 0
        self.flushes = 0

    def scalar(self, _statement):
        return self.scalar_values.pop(0) if self.scalar_values else None

    def add(self, item):
        self.added.append(item)

    def flush(self):
        self.flushes += 1

    def commit(self):
        self.commits += 1

    def refresh(self, _item):
        return None


def make_job(**overrides) -> Job:
    now = datetime.now(timezone.utc)
    values = {
        "id": "job-1",
        "job_type": "extract_pdf",
        "idempotency_key": "key-1",
        "state": "queued",
        "priority": 100,
        "payload": {"private": "not serialized", "session_id": "session-1"},
        "result": {},
        "safe_error": {},
        "progress": 0,
        "attempt": 0,
        "max_attempts": 3,
        "available_at": now,
        "lease_owner": None,
        "lease_expires_at": None,
        "heartbeat_at": None,
        "phase": "queued",
        "phase_started_at": now,
        "phase_timestamps": {"queued": now.isoformat()},
        "cancelled_at": None,
        "completed_at": None,
        "owner_id": "user-1",
        "session_id": "session-1",
        "uploaded_file_id": "file-1",
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return Job(**values)


def test_claim_query_uses_skip_locked_and_recovers_expired_leases():
    sql = str(
        claim_query(datetime.now(timezone.utc)).compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    ).upper()

    assert "FOR UPDATE SKIP LOCKED" in sql
    assert "JOBS.STATE = 'QUEUED'" in sql
    assert "JOBS.LEASE_EXPIRES_AT" in sql
    assert "JOBS.ATTEMPT < JOBS.MAX_ATTEMPTS" in sql


def test_enqueue_is_idempotent_and_does_not_duplicate_existing_job():
    existing = make_job()
    db = FakeDb([existing])

    job, created = enqueue_job(
        db,
        job_type="extract_pdf",
        idempotency_key="key-1",
        owner_id="user-1",
        session_id="session-1",
        uploaded_file_id="file-1",
        payload={"session_id": "session-1"},
    )

    assert job is existing
    assert created is False
    assert db.added == []
    assert db.commits == 0


def test_enqueue_creates_queued_job_with_bounded_attempts():
    db = FakeDb([None])

    job, created = enqueue_job(
        db,
        job_type="extract_pdf",
        idempotency_key="key-2",
        owner_id="user-1",
        session_id="session-2",
        uploaded_file_id="file-2",
        payload={"enhanced_reading": False},
        max_attempts=4,
    )

    assert created is True
    assert job.state == "queued"
    assert job.attempt == 0
    assert job.max_attempts == 4
    assert db.added == [job]
    assert db.commits == 1


def test_claim_sets_lease_heartbeat_and_attempt_atomically():
    job = make_job()
    db = FakeDb([job])

    claimed = claim_next_job(db, worker_id="worker-a", lease_seconds=120)

    assert claimed is job
    assert job.state == "processing"
    assert job.attempt == 1
    assert job.lease_owner == "worker-a"
    assert job.lease_expires_at > job.heartbeat_at
    assert db.commits == 1


def test_heartbeat_requires_the_current_lease_owner():
    job = make_job(state="processing", lease_owner="worker-a")
    db = FakeDb()

    heartbeat_job(db, job, worker_id="worker-a", progress=55, phase="extracting", lease_seconds=60)
    assert job.progress == 55
    assert job.phase == "extracting"
    assert "extracting" in job.phase_timestamps
    assert db.commits == 1

    with pytest.raises(AppError, match="lease"):
        heartbeat_job(FakeDb(), job, worker_id="worker-b", progress=60, lease_seconds=60)


def test_failure_requeues_until_attempt_limit_then_becomes_terminal():
    retry = make_job(state="processing", lease_owner="worker-a", attempt=1, max_attempts=2)
    db = FakeDb()

    fail_job(db, retry, worker_id="worker-a", code="extract_failed", message="This PDF could not be read.")
    assert retry.state == "queued"
    assert retry.safe_error == {"code": "extract_failed", "message": "This PDF could not be read."}
    assert retry.available_at > datetime.now(timezone.utc)
    assert retry.lease_owner is None

    terminal = make_job(state="processing", lease_owner="worker-a", attempt=2, max_attempts=2)
    fail_job(FakeDb(), terminal, worker_id="worker-a", code="extract_failed", message="This PDF could not be read.")
    assert terminal.state == "failed"
    assert terminal.completed_at is not None


def test_complete_and_cancel_are_terminal_and_serialization_is_safe():
    completed = make_job(state="processing", lease_owner="worker-a", attempt=1)
    complete_job(FakeDb(), completed, worker_id="worker-a", result={"draft_id": "draft-1"})
    assert completed.state == "completed"
    assert completed.progress == 100
    assert completed.lease_owner is None

    queued = make_job()
    cancel_job(FakeDb(), queued)
    assert queued.state == "cancelled"
    assert queued.cancelled_at is not None

    payload = serialize_job(completed)
    assert payload["state"] == "completed"
    assert payload["attempt"] == 1
    assert payload["progress"] == 100
    assert payload["result"] == {"draft_id": "draft-1"}
    assert payload["phase"] == "completed"
    assert payload["heartbeat_at"] is not None
    assert payload["elapsed_seconds"] >= 0
    assert payload["phase_timestamps"]["completed"]
    assert "payload" not in payload
    assert "lease_owner" not in payload


def test_terminal_or_foreign_leased_jobs_reject_state_changes():
    with pytest.raises(AppError, match="cannot be cancelled"):
        cancel_job(FakeDb(), make_job(state="completed"))
    with pytest.raises(AppError, match="lease"):
        complete_job(FakeDb(), make_job(state="processing", lease_owner="worker-a"), "worker-b", {})


def test_cancel_job_detaches_session_and_remains_serializable():
    from types import SimpleNamespace

    mock_session = SimpleNamespace(id="session-1", draft_id="draft-1", uploaded_file_id="file-1")
    mock_draft = SimpleNamespace(id="draft-1", revision=1)
    mock_file = SimpleNamespace(id="file-1", batch_id="batch-1")
    mock_batch = SimpleNamespace(id="batch-1", files=[])

    deleted_items = []

    class MockDb:
        def __init__(self):
            self.commits = 0
            self.flushes = 0

        def get(self, model, ident):
            name = getattr(model, "__name__", str(model))
            if "Session" in name and ident == "session-1":
                return mock_session
            if "QuotationDraft" in name and ident == "draft-1":
                return mock_draft
            if "UploadedFile" in name and ident == "file-1":
                return mock_file
            if "Batch" in name and ident == "batch-1":
                return mock_batch
            return None

        def delete(self, obj):
            deleted_items.append(obj)

        def flush(self):
            self.flushes += 1

        def commit(self):
            self.commits += 1

    job = make_job(session_id="session-1", uploaded_file_id="file-1")
    db = MockDb()

    cancel_job(db, job)

    assert job.state == "cancelled"
    assert job.session_id is None
    assert job.uploaded_file_id is None
    assert mock_session in deleted_items
    assert mock_draft in deleted_items
    assert mock_file in deleted_items
    assert mock_batch in deleted_items

    serialized = serialize_job(job)
    assert serialized["state"] == "cancelled"
    assert serialized["cancelled_at"] is not None


def _sqlite_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.models.tables import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def test_sql_fair_share_interleaving_and_fast_lane_priority():
    from app.models.tables import User, new_id

    db = _sqlite_session()
    try:
        u_a = User(id=new_id(), email="a@risklocker.test", role="staff")
        u_b = User(id=new_id(), email="b@risklocker.test", role="staff")
        u_c = User(id=new_id(), email="c@risklocker.test", role="staff")
        db.add_all([u_a, u_b, u_c])
        db.commit()

        base_t = datetime.now(timezone.utc) - timedelta(minutes=5)
        for i in range(3):
            db.add(make_job(id=new_id(), idempotency_key=f"a-{i}", owner_id=u_a.id, session_id=None, uploaded_file_id=None, priority=100, available_at=base_t + timedelta(seconds=i), created_at=base_t + timedelta(seconds=i)))
        for i in range(2):
            db.add(make_job(id=new_id(), idempotency_key=f"b-{i}", owner_id=u_b.id, session_id=None, uploaded_file_id=None, priority=100, available_at=base_t + timedelta(seconds=10 + i), created_at=base_t + timedelta(seconds=10 + i)))
        # Fast-lane interactive job (priority=10) arrives last, must claim first
        db.add(make_job(id=new_id(), idempotency_key="c-fast", owner_id=u_c.id, session_id=None, uploaded_file_id=None, priority=10, available_at=base_t + timedelta(seconds=30), created_at=base_t + timedelta(seconds=30)))
        db.commit()

        claimed_owners = []
        while True:
            c = claim_next_job(db, worker_id="w-1", lease_seconds=120)
            if c is None:
                break
            claimed_owners.append(c.owner_id)

        assert claimed_owners[0] == u_c.id
        # Next two bulk jobs must interleave u_a and u_b (not u_a, u_a, u_a before u_b)
        assert set(claimed_owners[1:3]) == {u_a.id, u_b.id}
        assert len(claimed_owners) == 6
    finally:
        db.close()


def test_requeue_job_for_quota_preserves_attempts_and_resumes_on_key_add():
    from app.models.tables import User, new_id
    from app.services.job_service import requeue_job_for_quota, resume_paused_quota_jobs

    db = _sqlite_session()
    try:
        u = User(id=new_id(), email="quota@risklocker.test", role="staff")
        db.add(u)
        db.commit()

        j = make_job(id=new_id(), idempotency_key="q-1", owner_id=u.id, session_id=None, uploaded_file_id=None, attempt=0, max_attempts=3)
        db.add(j)
        db.commit()

        claimed = claim_next_job(db, worker_id="w-1", lease_seconds=120)
        assert claimed is not None and claimed.attempt == 1

        future_reset = datetime.now(timezone.utc) + timedelta(hours=6)
        requeue_job_for_quota(
            db,
            claimed,
            worker_id="w-1",
            resume_at=future_reset,
            pause_daily=True,
            reason="All lanes reached 480 RPD",
        )
        assert claimed.attempt == 0
        assert claimed.state == "paused_quota"
        assert claim_next_job(db, worker_id="w-1", lease_seconds=120) is None

        woken = resume_paused_quota_jobs(db, reason="Added backup key")
        assert woken == 1
        reclaimed = claim_next_job(db, worker_id="w-1", lease_seconds=120)
        assert reclaimed is not None and reclaimed.id == claimed.id
    finally:
        db.close()


def test_upload_run_lifecycle_and_retry_failed_only():
    from app.models.tables import User, new_id
    from app.services.upload_run_service import (
        create_upload_run,
        get_upload_run_detail,
        list_upload_runs,
        pause_upload_run,
        resume_upload_run,
        retry_failed_upload_run,
    )

    db = _sqlite_session()
    try:
        user = User(id=new_id(), email="batch@risklocker.test", role="staff")
        db.add(user)
        db.commit()

        run = create_upload_run(db, owner_id=user.id, title="Lunch Batch 120", mode="bulk", total_files=3)
        j_done = make_job(id=new_id(), idempotency_key="r-done", owner_id=user.id, upload_run_id=run.id, state="completed", progress=100, session_id=None, uploaded_file_id=None)
        j_fail = make_job(id=new_id(), idempotency_key="r-fail", owner_id=user.id, upload_run_id=run.id, state="failed", attempt=3, safe_error={"message": "Timeout"}, session_id=None, uploaded_file_id=None)
        j_q = make_job(id=new_id(), idempotency_key="r-q", owner_id=user.id, upload_run_id=run.id, state="queued", session_id=None, uploaded_file_id=None)
        db.add_all([j_done, j_fail, j_q])
        db.commit()

        paused = pause_upload_run(db, run_id=run.id, user=user)
        assert paused["paused_count"] == 1
        db.refresh(j_q)
        assert j_q.state == "paused_user"

        resumed = resume_upload_run(db, run_id=run.id, user=user)
        assert resumed["resumed_count"] == 1
        db.refresh(j_q)
        assert j_q.state == "queued"

        retried = retry_failed_upload_run(db, run_id=run.id, user=user)
        assert retried["retried_count"] == 1
        db.refresh(j_fail)
        db.refresh(j_done)
        assert j_fail.state == "queued" and j_fail.attempt == 0
        assert j_done.state == "completed"

        listed = list_upload_runs(db, user=user)
        assert listed["total"] == 1
        detail = get_upload_run_detail(db, run_id=run.id, user=user)
        assert len(detail["items"]) == 3
    finally:
        db.close()

