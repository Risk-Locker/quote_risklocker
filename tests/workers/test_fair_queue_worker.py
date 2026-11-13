"""Hermetic unit tests for Task 3: Multi-User "Elevator" Fair-Share Job Queue."""

import pytest
from app.workers.fair_queue_worker import FairShareJobQueue, QueueItem


def test_elevator_fair_share_interleaving():
    """Simulates User C with 30 PDFs and User A with 2 PDFs.

    Asserts User A completes both items within the first 5 dispatch turns,
    avoiding starvation behind User C's 30 items.
    """
    queue = FairShareJobQueue()

    # 1. User C queues 30 fleet insurance renewal PDFs
    c_jobs = []
    for i in range(30):
        item = queue.enqueue(user_id="user_c_fleet", document_id=f"fleet_pdf_{i}")
        c_jobs.append(item.job_id)

    # 2. User A arrives with 2 urgent customer counter PDFs
    a_jobs = []
    for i in range(2):
        item = queue.enqueue(user_id="user_a_agent", document_id=f"urgent_pdf_{i}")
        a_jobs.append(item.job_id)

    # 3. User B arrives with 1 PDF
    b_item = queue.enqueue(user_id="user_b_staff", document_id="single_pdf_0")

    assert queue.total_pending == 33
    assert queue.active_users_count == 3

    # Dispatch sequence verification:
    # Round 1: C[0], A[0], B[0]
    p1 = queue.pop_next_job()
    assert p1.user_id == "user_c_fleet"
    assert p1.document_id == "fleet_pdf_0"

    p2 = queue.pop_next_job()
    assert p2.user_id == "user_a_agent"
    assert p2.document_id == "urgent_pdf_0"

    p3 = queue.pop_next_job()
    assert p3.user_id == "user_b_staff"
    assert p3.document_id == "single_pdf_0"

    # User B is now finished; active users is 2 (C and A)
    assert queue.active_users_count == 2

    # Round 2: C[1], A[1]
    p4 = queue.pop_next_job()
    assert p4.user_id == "user_c_fleet"
    assert p4.document_id == "fleet_pdf_1"

    p5 = queue.pop_next_job()
    assert p5.user_id == "user_a_agent"
    assert p5.document_id == "urgent_pdf_1"

    # User A is now finished with both PDFs at turn 5!
    assert queue.active_users_count == 1

    # Remaining 28 items are all User C
    remaining_popped = []
    while True:
        job = queue.pop_next_job()
        if not job:
            break
        assert job.user_id == "user_c_fleet"
        remaining_popped.append(job.document_id)

    assert len(remaining_popped) == 28
    assert queue.total_pending == 0


def test_accurate_fair_share_queue_position_calculation():
    """Verify queue position returns accurate interleaved position for user banner."""
    queue = FairShareJobQueue()

    # User C enqueues 10 items
    for i in range(10):
        queue.enqueue(user_id="user_c", document_id=f"doc_c_{i}")

    # User A enqueues 2 items
    item_a1 = queue.enqueue(user_id="user_a", document_id="doc_a_1")
    item_a2 = queue.enqueue(user_id="user_a", document_id="doc_a_2")

    # In naive FIFO, item_a1 would be position 11.
    # In Fair-Share Elevator, item_a1 is position 2!
    pos_a1 = queue.get_queue_position(user_id="user_a", job_id=item_a1.job_id)
    assert pos_a1["position"] == 2
    assert pos_a1["other_users_count"] == 1
    assert pos_a1["total_pending_jobs"] == 12

    # item_a2 will be processed in round 2 -> position 4 (C[0], A[0], C[1], A[1])
    pos_a2 = queue.get_queue_position(user_id="user_a", job_id=item_a2.job_id)
    assert pos_a2["position"] == 4
    assert pos_a2["items_ahead_for_user"] == 1


def test_empty_queue_and_invalid_job_handling():
    """Empty queue safely returns None and negative position for missing jobs."""
    queue = FairShareJobQueue()
    assert queue.pop_next_job() is None
    assert queue.total_pending == 0

    pos = queue.get_queue_position("unknown_user", "unknown_job")
    assert pos["position"] == -1

