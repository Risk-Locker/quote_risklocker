# Risklocker Active Working Memory (STATE.md)

Current high-signal snapshot of active development. Rotate old entries to `docs/history/MEMORY-YYYY-MM.md` when this file exceeds ~80 lines.

## Active System State (Current Snapshot)
- **Architecture**: Next.js 15.5 frontend (:3000) + FastAPI backend (:8100) + Supabase/PostgreSQL pooler + Private Storage.
- **Active Features**: Package Icon Container in Review Workspace + Redesigned Benefit Aliases UI + Bilingual Agency Motor Default Template (r8 A4) + Multi-Tier Cache + Embedded Worker.
- **Current Milestone**: Branch v12 Active Development.
- **Test Baseline**: 541/541 backend pytest passing, TypeScript clean (0 errors), 36/36 Next.js routes building cleanly.

## Recent Interaction Logs (Active Window)

### 2026-09-02 · Antigravity (Gemini 3.7 Flash) · Initialize Branch v12 from Latest v11 & Push to Remote — EXECUTED
Asked: Commit and push the current latest version from origin v11 to origin v12 and checkout to branch v12 for upcoming work.
Done: Synchronized local `v12` to latest `v11` (`9fdc8bc`), rotated older logs to `docs/history/MEMORY-2026-09.md`, updated `docs/core/STATE.md` to milestone `Branch v12`, and pushed branch `v12` to `origin/v12`.
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Enable Embedded Worker & Expand Rate Limits for Concurrent Staff — EXECUTED
Asked: Fix long job queue delays and allow concurrent multi-device staff uploads without rate-limit throttling.
Done: Updated `ecosystem.config.cjs:38-41` (`ENABLE_EMBEDDED_WORKER="1"`), `extraction_worker.py:170-195` (multi-candidate fallback for reading ephemeral source files), and `config.py:282-294` (increased rate limits to 500 uploads/hr, 500 gens/hr); verified 541/541 pytest green.
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Fix Reverse Proxy Host Detection in Next.js Middleware — EXECUTED
Asked: Fix browser cross-origin frame error ("Unsafe attempt to load URL https://localhost:3000/login from https://quote.risklocker.com/upload").
Done: Updated `frontend/src/middleware.ts:5-15` to detect `x-forwarded-host` and `x-forwarded-proto` headers behind Nginx reverse proxy; verified 36/36 Next.js build clean.
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Fix Malware Scan Subprocess Failure on VPS Without Clamd Daemon — EXECUTED
Asked: Fix 400 Bad Request error on upload endpoint caused by `clamdscan` executing when `clamav-daemon` is offline.
Done: Updated `document_security.py:59-75` to immediately bypass subprocess when `required=False` and automatically fallback from `clamdscan` (exit 2) to `clamscan` when `required=True`; verified 541/541 pytest green.
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Resolve IDE Type Diagnostics in Document Security & Tests — EXECUTED
Asked: Fix IDE diagnostic warnings and type errors in `document_security.py` and `test_hardening.py`.
Done: Updated `document_security.py:10-170` (fixed `acro_form.get` array typing, `@contextmanager` `Generator` return type) and `test_hardening.py:1-176` (added `Settings` type casting for `SimpleNamespace` mock objects and safe `new_page` attribute access); verified 541/541 pytest green, TypeScript clean.
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Optimize Upload Malware Scan & Prioritize ClamAV Daemon — EXECUTED
Asked: Eliminate the 24s upload scanner freeze by enabling built-in structural inspection and prioritizing `clamdscan`.
Done: Updated `document_security.py:32-75`, `config.py:249`, `system_checks.py:114`, and `test_hardening.py:126-150` to make `REQUIRE_MALWARE_SCANNER` configurable (defaulting to fast 15ms `pikepdf+PyMuPDF` structural inspection) and prioritize `clamdscan` over `clamscan`; verified 541/541 pytest green, TypeScript clean.
Pending: none.
