# Milestone 3: AI Rate-Limit Sharding & Multi-User "Elevator" Fair-Share Queue

> **Spec Document:** `docs/superpowers/plans/2026-11-12-milestone-3-ai-rate-limiting-and-elevator-queue.md`  
> **Status:** Completed & Verified (100% CI Parity)  
> **Prerequisite:** Milestone 2 Completed

**Goal:** Implement a strict Fail-Closed AI Gate (halting and alerting the user when AI tokens or quota are exhausted, ending silent corrupt regex degradation), build a deterministic round-robin sharded key/model allocator across verified active models with safe RPM/RPD caps, and author a Weighted Fair Queue ("Elevator" model) to interleave multi-user upload requests fairly without starvation.

---

## Global Constraints

- **Fail-Closed on AI Outage:** If Gemini returns 429, 401, timeout, or empty key pool, the system MUST halt with an explicit HTTP 429/503 user alert. Silent fallback to corrupt regex drafts is prohibited.
- **Safe Capacity Limits:** 12 RPM and 450 RPD per model (24 RPM / 900 RPD per API key). Total system throughput = $24N$ RPM across $N$ pooled keys.
- **Fair-Share Weighted Allocation:** Requests are queued per-user and processed in an interleaved round-robin cycle:
  $$\text{User A [1]} \to \text{User B [1]} \to \text{User C [1]} \to \text{User A [2]} \dots$$

---

## Tasks

### Task 1: Strict Fail-Closed AI Gate - [COMPLETED]
- Created: `AIExtractionUnavailableException` in `backend/app/core/errors.py` (exported via `backend/app/extraction/types.py`).
- Modified: `backend/app/extraction/orchestrator.py`
  - Replaced silent `except Exception as exc: warnings.append(...)` swallow.
  - Fail-closed mode raises typed `AIExtractionUnavailableException` when API keys are absent (503) or quota is exhausted (429), preventing corrupt regex draft generation.
  - Integrated with `backend/app/workers/extraction_worker.py` and `backend/app/extraction/sandbox.py`.
- Tested: `tests/extraction/test_fail_closed_ai_gate.py` (3 passing unit tests).

### Task 2: Round-Robin Sharded Key & Model Allocator - [COMPLETED]
- Created: `backend/app/extraction/ai_sharded_pool.py`
  - Maintains active slot registry: 2 verified active models (`gemini-3.5-flash-lite`, `gemini-3.8-flash`) per API key.
  - Slot capacity tracking: 12 RPM sliding-window rate-limiter and 450 RPD daily counter per slot (safe caps).
  - Deterministic round-robin dispatcher: `allocate_next_available_slot(document_id: str) -> AISlot`.
  - Automatic slot cooldown upon upstream 429s.
- Tested: `tests/extraction/test_ai_sharded_pool.py` (5 passing concurrency tests verifying 8-slot round-robin, RPM sliding window enforcement, cooling skip, and 16-thread safety).

### Task 3: Multi-User "Elevator" Fair-Share Job Queue - [COMPLETED]
- Created: `backend/app/workers/fair_queue_worker.py`
  - Queues uploads tagged with `user_id`, `document_id`, `created_at`.
  - Fair-Share Dispatcher: Pops 1 job per active user in a round-robin cycle, preventing single-user queue starvation.
  - Integrated with `backend/app/api/routers/sessions.py` (`upload_one` and `job_detail` queue position metrics).
- Tested: `tests/workers/test_fair_queue_worker.py` (3 passing tests simulating User C with 30 PDFs and User A with 2 PDFs; asserts User A finishes in slot 5 without waiting for User C's 30 items).

### Task 4: Real-Time Frontend Queue Progress Banner - [COMPLETED]
- Created: `frontend/src/components/upload/queue-progress-banner.tsx`
  - Follows `--rl-*` design tokens, Phosphor icons, micro-progress bar, and clear status copy:
    `"Processing item 2 of 5... (Position 1 in queue. 1 other staff member currently processing)"`.
- Integrated: `frontend/src/components/upload/upload-workspace.tsx` for both single-quote and bulk/comparison modes.
