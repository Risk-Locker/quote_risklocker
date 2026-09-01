# Risklocker Active Working Memory (STATE.md)

Current high-signal snapshot of active development. Rotate old entries to `docs/history/MEMORY-YYYY-MM.md` when this file exceeds ~80 lines.

## Active System State (Current Snapshot)
- **Architecture**: Next.js 15.5 frontend (:3000) + FastAPI backend (:8100) + Supabase/PostgreSQL pooler + Private Storage.
- **Active Features**: Package Icon Container in Review Workspace + Redesigned Benefit Aliases UI + Bilingual Agency Motor Default Template (r8 A4) + Multi-Tier Cache.
- **Current Milestone**: Branch v11 Performance & Architecture Upgrades.
- **Test Baseline**: 541/541 backend pytest passing, TypeScript clean (0 errors), 36/36 Next.js routes building cleanly.

## Recent Interaction Logs (Active Window)

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

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Explain 401, 422 Workspace, and Chrome runtime.lastError Errors — INVESTIGATED
Asked: Explain the meaning and causes of `/api/auth/me` 401, `/drafts/.../workspace` 422, and Chrome `runtime.lastError` in the browser console.
Done: Explained 401 (standard unauthenticated session check), 422 (workspace patch validation/reference violation during auto-save attempts), and `runtime.lastError` (external Chrome extension background script disconnect).
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Propose Malware Scanning Alternatives & Optimization Paths — INVESTIGATED
Asked: Propose fast alternatives to the 24s ClamAV scan for internal staff usage.
Done: Formulated 3 optimization paths: (1) Pure built-in pikepdf/fitz structural inspection (<30ms); (2) ClamAV memory-resident daemon `clamdscan` (<50ms); (3) Asynchronous worker-level scanning so uploads return 202 in <50ms.
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Analyze Server Upload Latency vs Local Execution — INVESTIGATED
Asked: Explain why PDF upload on VPS took 24.4s before elevator progress started compared to ~9s locally.
Done: Analyzed PM2 logs showing `POST /api/uploads` took 24,447ms before returning 202 while the actual background job took only 7s; identified ClamAV cold scanning, network transmission, and Supabase storage upload sync in older deployments as root causes.
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Push Production Milestone to origin v11 and origin main — EXECUTED
Asked: Commit and push verified v11 enhancements to origin v11 and merge cleanly to origin main.
Done: Committed full hardened suite (541/541 pytest green, 36/36 Next.js build clean), pushed commit `eb3debc` to `origin v11` and fast-forward merged to `origin main`.
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Fix Intermittent 422 FK Violation & Idempotent Benefit Operations — EXECUTED
Asked: Diagnose and eliminate intermittent 422 ("This record references a value that does not exist") during draft workspace saves/benefit customization.
Done: Hardened `backend/app/services/workspace_service.py:1328-1540` with `_safe_concept_id`, `_safe_source_line_id`, in-place idempotent updates for `create_custom_benefit` keys (`addon:*`, `default:*`, `concept:*`), and extended `_resolve_selection`; verified 541/541 pytest green, 36/36 Next.js build clean.
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Replace PRO Box with Duotone Package Icon in Review Workspace — EXECUTED
Asked: Replace the hardcoded blue "PRO" badge on the Detected Insurance Package banner with Option 1.
Done: Updated `frontend/src/components/session-workspace/review-phase.tsx:2327` to replace the "PRO" box with a rounded white/blue container featuring a duotone `PackageIcon`; verified 541/541 pytest green, 36/36 Next.js build clean.
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Redesign Extraction Benefit Aliases Page & Design System Alignment — EXECUTED
Asked: Fix styling issues on `/extraction/benefit-aliases` and bring it to modern Risklocker design system standards.
Done: Refactored `frontend/src/app/extraction/benefit-aliases/page.tsx:1-300` with `Card`, `Badge`, scope indicators (`Global`, `Company`, `Product`, `Package`), search filters, delete confirmation dialog, and toast notifications; verified 36/36 Next.js routes building cleanly.
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Fix OutputTemplateConfig Import in Workspace Service — EXECUTED
Asked: Fix backend `NameError: name 'OutputTemplateConfig' is not defined` during quotation session workspace initialization.
Done: Added `OutputTemplateConfig` to model imports in `backend/app/services/workspace_service.py:44`; verified 541/541 pytest green, 36/36 Next.js build clean.
Pending: none.

### 2026-09-01 · Antigravity (Gemini 3.7 Flash) · Resolve Workspace 409 Conflict Race & Browser Extension Error Analysis — EXECUTED
Asked: Diagnose `runtime.lastError` and `409 (Conflict)` errors on `/api/drafts/.../workspace`.
Done: (1) Diagnosed `runtime.lastError` as client-side Chrome Extension background script disconnects; (2) fixed 409 Conflict race condition by removing redundant eager `selectTemplateDirectly` auto-save on mount in `review-phase.tsx:948` and enforcing lazy `serverSnapshotRef` resolution in `provider.tsx:527`; verified 541/541 pytest green, 36/36 Next.js build clean.
Pending: none.
