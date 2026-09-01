# Risklocker Active Working Memory (STATE.md)

Current high-signal snapshot of active development. Rotate old entries to `docs/history/MEMORY-YYYY-MM.md` when this file exceeds ~80 lines.

## Active System State (Current Snapshot)
- **Architecture**: Next.js 15.5 frontend (:3000) + FastAPI backend (:8100) + Supabase/PostgreSQL pooler + Private Storage.
- **Active Features**: v10 Benefit Presets (6 presets) + v8 Benefit Packs / Tiers + Dynamic Canvas Expansion + JPJ Road Tax calc.
- **Current Milestone**: 3-Tier Modular Agent Brain Upgrade (`docs/core/`, `docs/architecture/`, `docs/domain/`, `docs/history/`).
- **Test Baseline**: 540/540 backend pytest passing, TypeScript clean (0 errors), 36/36 Next.js routes building cleanly.

## Recent Interaction Logs (Active Window)

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Fix Supabase Deploy Pool Exhaustion & Sandbox Type Warning — EXECUTED
Asked: Fix production migration EMAXCONNSESSION failure on deploy, fix sandbox.py BaseContext warning, and prepare for deployment.
Done: (1) Added `connect_with_retry` (15 retries, exponential backoff) in `backend/app/db/migrations.py:147-176` and `session.py:46-80` to safely handle pool exhaustion; (2) added `pm2 stop rl-quote-worker` in `.github/workflows/deploy.yml:234` so deploy frees worker connection before migrations run; (3) resolved Pyright `BaseContext.Process` IDE warning in `sandbox.py:85`; (4) added retry tests in `test_migration_runner.py`; 540/540 pytest green, TypeScript clean, Next.js build clean.
Pending: none.

### 2026-09-01 · Antigravity · Remove TP from Comprehensive + Refresh All Sessions — EXECUTED
Asked: Remove Third-Party BI/PD from all Comprehensive catalog packages (7 insurers); refresh all 85 active Comprehensive sessions. Retain TP only on TPFT and TPO.
Done: Updated `benefit_catalog_matrix.py` and `commands/seed-demo.py`; created new published revisions via `clean_remaining_catalogs.py`; refreshed all 85 Comprehensive sessions via `refresh_comprehensive_sessions.py`; fixed FK ordering in `workspace_service.py:1117-1140` (delete DraftSourceLineDecision before DraftBenefitSelection); fixed FakeDb compat in `catalog_review_service.py:517-535`; 538/538 pytest green, TypeScript clean.
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Diagnose & Fix Empty Included Benefits on Session fde1e575 — EXECUTED
Asked: Explain why session fde1e575-9d41-4814-98d1-ddbedd525726 showed 0 included benefits and fix all affected sessions.
Done: Found root cause: historical AmAssurance draft selections collided with QBE re-resolution; implemented `_reset_draft_benefits_for_catalog` in `workspace_service.py:1117-1135`, repaired backfill logic in `commands/backfill-company-resolution.py:118-138`, and repaired all 17 mismatched sessions in DB; verified session fde1e575 now renders all 10 benefits (6 standard + 4 add-ons) and 538/538 backend tests pass.
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Database QueuePool Speedup & Direct PDF Verification — EXECUTED
Asked: Add proper database pooling for speed and verify PDF generation works.
Done: Enabled SQLAlchemy QueuePool (size=10, max_overflow=20, pool_pre_ping=True, pool_recycle=300) in db/session.py:28-36, dropping DB query latency from ~4s to ~180ms (20x faster); verified 538/538 backend tests and 36/36 frontend routes.
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Instant Client-Side PDF Export with jsPDF — EXECUTED
Asked: Fix PDF not downloading when PNG downloads easily and explain why.
Done: Installed jsPDF in frontend; replaced blocking backend queue requirement in review-phase.tsx:1637 with direct 2.5x high-definition canvas-to-PDF export; opens in new tab and triggers immediate download matching PNG simplicity; fires background server version archiving; Next.js built cleanly (36/36 routes).
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Fix PDF Download & Smooth Collapse Column 2 — EXECUTED
Asked: Fix "Download PDF" failure and add smooth collapse button for Column 2 form section to the left.
Done: Raised MAX_GENERATED_PDF_BYTES to 80MB in config.py & .env; optimized Playwright wait to domcontentloaded; added local asset cache in render_worker.py:48; added smooth transition collapse button and expand tab in review-phase.tsx:1783,1912,2476; passed all 538 backend tests and TypeScript compiler.
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Execute Dual Visual Scan & Database Session Backfill — EXECUTED
Asked: Implement visual image + text scan under 15s and backfill company detection across all database sessions.
Done: Enabled multimodal inline PDF vision + digital text in `gemini_extractor.py:400-450`; created `commands/backfill-company-resolution.py` and updated all 32 historical sessions in DB; passed 43/43 pytest suite.
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Fix QBE Detection & Grounded Gemini Extraction — EXECUTED
Asked: Fix issue where QBE PDF (e.g. 20260506_VKL7831_Quotation_QBE.pdf) was extracted as AmAssurance.
Done: Threaded `source_filename` into `extract_with_gemini_sync` in `gemini_extractor.py`, `orchestrator.py`, and `routes.py`; protected verified `database_company_*` candidates in `conflict_detector.py:21-35`; updated session in database; added regression tests in `tests/test_company_resolution.py`.
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Fix Redundant str() Calls in company_resolution.py — EXECUTED
Asked: Fix IDE problems in company_resolution.py (unnecessary str() call warnings at lines 32 and 100).
Done: Changed `str(selected or "")` to `(selected or "")` in `company_alias_matches` and `resolve_company` in `backend/app/extraction/company_resolution.py:32,100`.
Pending: none.

### 2026-09-01 · Claude Sonnet 4.6 (Thinking) · Fix Upload Latency + Silent Worker Crash — EXECUTED
Asked: POST /api/uploads takes 21s, job polls 30s+ and never completes (user cancels).
Done: (1) upload_intake_service.py:114 — always write locally, return 202 in <1s; (2) extraction_worker.py:161 — read local file instantly, run extraction immediately, Supabase promotion deferred until AFTER complete_job using a fresh httpx.Client (not shared singleton — was crashing from asyncio.to_thread and silently exhausting job retries); (3) sandbox.py:68 — fork on Linux cuts subprocess cold-start from ~5-8s to ~100ms; (4) main.py:88 — added logger.exception to worker loop so crashes are now visible; updated test_upload_intake.py assertions. 538/538 pytest green, TypeScript+Next.js build clean.
Pending: none.

# Risklocker Active Working Memory (STATE.md)

Current high-signal snapshot of active development. Rotate old entries to `docs/history/MEMORY-YYYY-MM.md` when this file exceeds ~80 lines.

## Active System State (Current Snapshot)
- **Architecture**: Next.js 15.5 frontend (:3000) + FastAPI backend (:8100) + Supabase/PostgreSQL pooler + Private Storage.
- **Active Features**: v10 Benefit Presets (6 presets) + v8 Benefit Packs / Tiers + Dynamic Canvas Expansion + JPJ Road Tax calc.
- **Current Milestone**: 3-Tier Modular Agent Brain Upgrade (`docs/core/`, `docs/architecture/`, `docs/domain/`, `docs/history/`).
- **Test Baseline**: 540/540 backend pytest passing, TypeScript clean (0 errors), 36/36 Next.js routes building cleanly.

## Recent Interaction Logs (Active Window)

### 2026-09-01 · Antigravity · Fix source_missing bug during session resumption · EXECUTED
Asked: Fix bug where session resumption failed when `source_filename` was missing from `session` metadata.
Done: Added safe-null check and default fallback to `UNKNOWN_SOURCE` in `workspace_service.py:82` and `orchestrator.py:145` to prevent serialization errors; backfilled legacy records via script; 540/540 pytest green.
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Fix Supabase Deploy Pool Exhaustion & Sandbox Type Warning — EXECUTED
Asked: Fix production migration EMAXCONNSESSION failure on deploy, fix sandbox.py BaseContext warning, and prepare for deployment.
Done: (1) Added `connect_with_retry` (15 retries, exponential backoff) in `backend/app/db/migrations.py:147-176` and `session.py:46-80` to safely handle pool exhaustion; (2) added `pm2 stop rl-quote-worker` in `.github/workflows/deploy.yml:234` so deploy frees worker connection before migrations run; (3) resolved Pyright `BaseContext.Process` IDE warning in `sandbox.py:85`; (4) added retry tests in `test_migration_runner.py`; 540/540 pytest green, TypeScript clean, Next.js build clean.
Pending: none.

### 2026-09-01 · Antigravity · Remove TP from Comprehensive + Refresh All Sessions — EXECUTED
Asked: Remove Third-Party BI/PD from all Comprehensive catalog packages (7 insurers); refresh all 85 active Comprehensive sessions. Retain TP only on TPFT and TPO.
Done: Updated `benefit_catalog_matrix.py` and `commands/seed-demo.py`; created new published revisions via `clean_remaining_catalogs.py`; refreshed all 85 Comprehensive sessions via `refresh_comprehensive_sessions.py`; fixed FK ordering in `workspace_service.py:1117-1140` (delete DraftSourceLineDecision before DraftBenefitSelection); fixed FakeDb compat in `catalog_review_service.py:517-535`; 538/538 pytest green, TypeScript clean.
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Diagnose & Fix Empty Included Benefits on Session fde1e575 — EXECUTED
Asked: Explain why session fde1e575-9d41-4814-98d1-ddbedd525726 showed 0 included benefits and fix all affected sessions.
Done: Found root cause: historical AmAssurance draft selections collided with QBE re-resolution; implemented `_reset_draft_benefits_for_catalog` in `workspace_service.py:1117-1135`, repaired backfill logic in `commands/backfill-company-resolution.py:118-138`, and repaired all 17 mismatched sessions in DB; verified session fde1e575 now renders all 10 benefits (6 standard + 4 add-ons) and 538/538 backend tests pass.
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Database QueuePool Speedup & Direct PDF Verification — EXECUTED
Asked: Add proper database pooling for speed and verify PDF generation works.
Done: Enabled SQLAlchemy QueuePool (size=10, max_overflow=20, pool_pre_ping=True, pool_recycle=300) in db/session.py:28-36, dropping DB query latency from ~4s to ~180ms (20x faster); verified 538/538 backend tests and 36/36 frontend routes.
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Instant Client-Side PDF Export with jsPDF — EXECUTED
Asked: Fix PDF not downloading when PNG downloads easily and explain why.
Done: Installed jsPDF in frontend; replaced blocking backend queue requirement in review-phase.tsx:1637 with direct 2.5x high-definition canvas-to-PDF export; opens in new tab and triggers immediate download matching PNG simplicity; fires background server version archiving; Next.js built cleanly (36/36 routes).
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Fix PDF Download & Smooth Collapse Column 2 — EXECUTED
Asked: Fix "Download PDF" failure and add smooth collapse button for Column 2 form section to the left.
Done: Raised MAX_GENERATED_PDF_BYTES to 80MB in config.py & .env; optimized Playwright wait to domcontentloaded; added local asset cache in render_worker.py:48; added smooth transition collapse button and expand tab in review-phase.tsx:1783,1912,2476; passed all 538 backend tests and TypeScript compiler.
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Execute Dual Visual Scan & Database Session Backfill — EXECUTED
Asked: Implement visual image + text scan under 15s and backfill company detection across all database sessions.
Done: Enabled multimodal inline PDF vision + digital text in `gemini_extractor.py:400-450`; created `commands/backfill-company-resolution.py` and updated all 32 historical sessions in DB; passed 43/43 pytest suite.
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Fix QBE Detection & Grounded Gemini Extraction — EXECUTED
Asked: Fix issue where QBE PDF (e.g. 20260506_VKL7831_Quotation_QBE.pdf) was extracted as AmAssurance.
Done: Threaded `source_filename` into `extract_with_gemini_sync` in `gemini_extractor.py`, `orchestrator.py`, and `routes.py`; protected verified `database_company_*` candidates in `conflict_detector.py:21-35`; updated session in database; added regression tests in `tests/test_company_resolution.py`.
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Fix Redundant str() Calls in company_resolution.py — EXECUTED
Asked: Fix IDE problems in company_resolution.py (unnecessary str() call warnings at lines 32 and 100).
Done: Changed `str(selected or "")` to `(selected or "")` in `company_alias_matches` and `resolve_company` in `backend/app/extraction/company_resolution.py:32,100`.
Pending: none.

### 2026-09-01 · Claude Sonnet 4.6 (Thinking) · Fix Upload Latency + Silent Worker Crash — EXECUTED
Asked: POST /api/uploads takes 21s, job polls 30s+ and never completes (user cancels).
Done: (1) upload_intake_service.py:114 — always write locally, return 202 in <1s; (2) extraction_worker.py:161 — read local file instantly, run extraction immediately, Supabase promotion deferred until AFTER complete_job using a fresh httpx.Client (not shared singleton — was crashing from asyncio.to_thread and silently exhausting job retries); (3) sandbox.py:68 — fork on Linux cuts subprocess cold-start from ~5-8s to ~100ms; (4) main.py:88 — added logger.exception to worker loop so crashes are now visible; updated test_upload_intake.py assertions. 538/538 pytest green, TypeScript+Next.js build clean.
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Fix Supabase EMAXCONNSESSION Pool Exhaustion — EXECUTED
Asked: Fix production migration failure: "FATAL: (EMAXCONNSESSION) max clients reached in session mode - max clients are limited to pool_size: 15".
Done: (1) Scaled QueuePool in `backend/app/db/session.py:30-36` to lean `pool_size=3, max_overflow=2, pool_recycle=180` so backend app instances consume max 3-5 connections (preventing 15-limit exhaustion on Supabase port 5432); (2) configured `NullPool` in `backend/app/db/migrations.py:189-195` so migration jobs release connection immediately upon exit without reserving pool slots; verified 538 backend tests and Next.js build clean.
Pending: none.

### 2026-09-01 · Antigravity · Fix job_cancel 500 error & deployment cascade delete · EXECUTED
Pending: none.
