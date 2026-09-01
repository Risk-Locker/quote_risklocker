# Risklocker Active Working Memory (STATE.md)

Current high-signal snapshot of active development. Rotate old entries to `docs/history/MEMORY-YYYY-MM.md` when this file exceeds ~80 lines.

## Active System State (Current Snapshot)
- **Architecture**: Next.js 15.5 frontend (:3000) + FastAPI backend (:8100) + Supabase/PostgreSQL pooler + Private Storage.
- **Active Features**: v10 Benefit Presets (6 presets) + v8 Benefit Packs / Tiers + Dynamic Canvas Expansion + JPJ Road Tax calc.
- **Current Milestone**: 3-Tier Modular Agent Brain Upgrade (`docs/core/`, `docs/architecture/`, `docs/domain/`, `docs/history/`).
- **Test Baseline**: 538/538 backend pytest passing, TypeScript clean (0 errors), 36/36 Next.js routes building cleanly.

## Recent Interaction Logs (Active Window)

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

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Preview Panel Collapse, Ctrl-Wheel Zoom & Dialog Wrap Fix — EXECUTED
Asked: Add matching collapse panel button to right preview panel, remove redundant preview buttons, add Ctrl+Mouse Wheel zoom, and fix dialog text overflow.
Done: (1) Added `previewColCollapsed` state, smooth collapse transition, and expand handle tab in `review-phase.tsx:718,1893,2484,3068`; (2) streamlined preview header to compact Style preset, Expand canvas, and Collapse Panel buttons in `review-phase.tsx:2490-2580`; (3) implemented direct Ctrl+Mouse Wheel zoom in canvas container in `review-phase.tsx:2590-2600`; (4) added `[overflow-wrap:anywhere] break-words pr-8` in `dialog.tsx:36,47,51`; verified 538 backend tests and 36/36 Next.js build clean.
Pending: none.



