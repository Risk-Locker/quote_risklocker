# Milestone 1: Sandbox / Test Session Isolation & Redesigned `/sessions` Command Center

> **Serialized Milestone 1 of 6 (`Rule 06`)**  
> **Master Roadmap:** [2026-11-17-principal-fintech-audit-and-master-roadmap.md](2026-11-17-principal-fintech-audit-and-master-roadmap.md)  
> **Net Change Budget:** `~380` lines  
> **Allowed to Change:**
> - `backend/app/workers/extraction_worker.py`
> - `backend/app/services/upload_intake_service.py`
> - `backend/app/services/session_service.py`
> - `backend/app/api/routers/sessions.py`
> - `frontend/src/app/sessions/page.tsx`
> - Unit test suite in `tests/unit/`
> **Forbidden to Change:**
> - Actuarial calculation engines (`road_tax_engine.py`, `ncd_evaluator.py`, `towing_evaluator.py`)
> - Design 2 PDF renderers (scheduled for Milestone 5)

---

## 1. Root Cause Analysis

1. **Test Sessions Polluting Production Ledger (`extraction_worker.py:520-793` & `upload_intake_service.py:165`):**
   - `upload_intake_service.py` calls `generate_quotation_reference(db)` even when `is_test=True`, consuming official `RL{YY}{SEQ:07d}` production sequence numbers.
   - `extraction_worker.py` never checks `if session.is_test:`. It unconditionally executes `resolve_or_create_customer()`, `get_or_create_vehicle_tracking()`, and `resolve_or_create_tenure()` — writing test uploads directly into the live Monthly Renewal Ledger (`/ledger`), live Customer Records, and live Vehicle Tracking.
2. **Sessions Page (`/sessions`) Sorting, Filtering & N+1 Defects (`session_service.py:89-256` & `sessions/page.tsx:121-165`):**
   - `list_sessions()` defaults to `sort_by="vehicle"`, sorting **alphabetically by vehicle plate (`A..Z`)** instead of **`created_at DESC` (newest uploaded first)**.
   - `list_sessions()` filters `or_(SessionModel.is_test.is_(True), and_(SessionModel.tenure_id.is_not(None), ...))`, which **hides 35 live single-quote sessions** where `tenure_id IS NULL`.
   - `serialize_session()` executes 2 synchronous `db.get()` queries (`TemplateRevision` and `OutputTemplateConfig`) per row inside the serialization loop.
   - `frontend/src/app/sessions/page.tsx` hardcodes `limit=100` with zero pagination, no date grouping (`Today`, `Yesterday`, `Earlier`), and no way to purge test sessions from the Test Sandbox Dump.

---

## 2. 10-Dimension Edge-Case & Scenario Matrix (`Rule 05`)

| # | Dimension | How It Is Handled & Verified |
| :- | :--- | :--- |
| 1 | **Null, Empty & Unicode Inputs** | `HANDLED`: Unplated/blank PDFs (`vehicle_no=""`), Chinese/Malay customer names, and missing dates render clean fallback badges (`Unplated`, `Unassigned Client`) in `/sessions`. Tested in `test_sandbox_isolation_and_sessions.py`. |
| 2 | **`Decimal` Bounds & Precision** | `HANDLED`: `total_premium` display formats exact backend `Decimal` strings without client float math. |
| 3 | **Timezones & Leap Calendars** | `HANDLED`: Date grouping (`Today`, `Yesterday`, `Earlier this Week`, `Older`) evaluates in `Asia/Kuala_Lumpur` (`UTC+8`). |
| 4 | **Concurrency, Races & Idempotency** | `HANDLED`: `DELETE /sessions/test-sandbox/purge` locks target test rows (`with_for_update(skip_locked=True)`) and skips any session with an active running `Job`. |
| 5 | **Auth, RBAC, IDOR & CSRF** | `HANDLED`: All `/sessions` endpoints require authenticated staff/admin session cookies + CSRF validation on `POST`/`DELETE`. |
| 6 | **Malformed Files, OCR & Prompt Injection** | `HANDLED`: Failed extraction jobs appear in `/sessions` with a clear `Cannot Read` / `Failed` status badge and a 1-click `[Re-detect]` recovery button. |
| 7 | **Timeouts, Quota & Partial-Failure Rollback** | `HANDLED`: Test session purge cleans up DB metadata and storage references transactionally. |
| 8 | **UI States, Accessibility & Browser Zoom** | `HANDLED`: `/sessions` uses `--rl-*` tokens (`#f5f5f7`, `#ffffff`, `#1b1717`, `#ed1c24`, `8px` card radius, `6px` badge radius), keyboard focus rings, Radix `Dialog` confirmation (zero `window.confirm`), and verified across `1024px`, `1280px`, `1920px` at `80%–120%` zoom. |
| 9 | **Legacy DB Rows & Schema Drift** | `HANDLED`: Existing 35 live sessions with `tenure_id=None` and existing 22 `is_test=True` sessions load cleanly without migration breakage. |
| 10 | **Scale, Pagination & Memory Limits** | `HANDLED`: Eager-loads template metadata in `list_sessions()` (eliminating 200 N+1 queries) and adds server-side pagination (`page`, `limit=50`) for `648+` sessions. |
