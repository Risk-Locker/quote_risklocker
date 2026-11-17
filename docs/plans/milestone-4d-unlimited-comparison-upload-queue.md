# Milestone 4d: Unlimited Staged and Queued Comparison Uploads

> **Status:** Ready to Execute (`v30.4`), part of `docs/plans/2026-11-17-combined-master-roadmap-edit-persistence-kurnia-3c-upload.md`
> **Skills:** `system-design-and-architecture`, `edge-case-and-scenario-matrix`, `test-driven-development`, `python-testing`
> **Model Profile:** `.agents/profiles/deep.md` (Gemini 4 Argon)

## 1. Verified Starting Point & Code-Audit Fixes

- Frontend cap: `maxBulkLimit = mode === "comparison" ? 30 : (limits?.max_bulk_upload_files || 30)` (`frontend/src/components/upload/upload-workspace.tsx:277`); dropzone hidden at the cap (`:1572`); copy says `"Up to 30"` (`:1596-1636`).
- Backend: `POST /api/uploads` queues one file per request, no per-tenure cap. Per-file safety limits stay intact (`20 MB`, `100` pages, `200,000` estimated tokens per PDF; `RATE_LIMIT_UPLOAD_ATTEMPTS = 500` per hour in `backend/app/core/config.py:305-306`).
- **Route Ordering Fix (`sessions.py:449`):** `backend/app/api/routers/sessions.py:449` currently defines `@router.get("/jobs/{job_id}")` and `@router.get("/uploads/jobs/{job_id}")`. The new batch status endpoint `@router.get("/jobs/status")` and `@router.get("/uploads/jobs/status")` MUST be registered **above** line `449` so FastAPI does not capture `"status"` as `job_id="status"`.
- **Durable DB Status Polling:** `GET /api/jobs/status?ids=...` must query the PostgreSQL `Job` table (`select(Job).where(Job.id.in_(job_ids), Job.owner_id == user.id)`) as the primary source of truthâ€”enriched with live `FairShareJobQueue` position when queued in memoryâ€”so 100+ queued jobs remain visible and resumable across browser reloads or worker restarts.

## 2. Design

1. **Setting, Not Constant (`comparison_upload_limit`):**
   - Add `AppSetting` key `comparison_upload_limit` (JSON `{"max_files": null | int}`, default `null` = unlimited), exposed by `GET /api/settings/limits` (`backend/app/api/routers/system.py`) and configurable in `backend/app/services/admin_service.py` and `/builder/uploads`.
   - Frontend `upload-workspace.tsx` reads `limits?.comparison_upload_limit` (`null` -> `Infinity` / unlimited in comparison mode); zero hardcoded `30`.
2. **Enqueue-All & Server-Side Pacing:**
   - Staging in comparison mode accepts 100+ PDFs without dropping files.
   - Clicking `"Process"` uploads files with bounded HTTP concurrency (e.g. 3 concurrent `POST /api/uploads` requests), stores each returned `(session_id, job_id)` in `staged-uploads-storage.ts`, and lets the backend worker + `PacerSentinel` process the queue at the fleet's rate without holding a 15-minute per-file browser loop.
3. **Batch Durable Status Polling (`GET /api/jobs/status`):**
   - Register `@router.get("/jobs/status")` and `@router.get("/uploads/jobs/status")` **before** `@router.get("/jobs/{job_id}")` in `backend/app/api/routers/sessions.py`.
   - Accept comma-separated `ids` (capped at `200` IDs per request; `422` if `> 200`), filter strictly by `Job.owner_id == _user.id`, and return per-job `state`, `progress`, `error_message`, `session_id`, and `queue_position`.
4. **Rate-Limit Pause & Resume:**
   - If `POST /api/uploads` returns `429` (`RATE_LIMIT_UPLOAD_ATTEMPTS`), pause client enqueueing, display `"N of M queued; resuming after window reset"`, and resume automatically when `Retry-After` elapses.
5. **Modular Extraction (`upload-workspace.tsx`):**
   - Extract the batch queue status poller hook (`useUploadQueuePoller.ts`) so `upload-workspace.tsx` stays clean and maintainable.

## 3. Files

- **Allowed:** `backend/app/api/routers/sessions.py`, `backend/app/api/routers/system.py`, `backend/app/services/admin_service.py`, `frontend/src/components/upload/upload-workspace.tsx`, `frontend/src/components/upload/` (`useUploadQueuePoller.ts`) (new), `frontend/src/lib/staged-uploads-storage.ts`, `frontend/src/app/builder/uploads/page.tsx`.
- **Forbidden:** Extraction worker internals, `PacerSentinel`, Gemini model IDs.

## 4. Hermetic & Live Tests

- `GET /api/settings/limits` returns `comparison_upload_limit: null` by default and honors `AppSetting` overrides.
- `GET /api/jobs/status?ids=...` resolves before `/jobs/{job_id}`, returns `422` for `> 200` IDs, filters out jobs owned by other users, and returns durable states (`queued`, `running`, `done`, `failed`) from the `Job` table.
- Frontend staging & polling: stage 100+ PDFs in comparison mode -> all staged without truncation; reload mid-queue resumes polling from persisted `job_id`s with zero `console.error`.

