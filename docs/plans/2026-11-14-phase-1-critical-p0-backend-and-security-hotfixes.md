# Phase 1: Critical P0 Backend & Security Hotfixes Implementation Plan

> **For agentic workers:** Enforces `AGENTS.md`, Rule 02 (Anti-Slop & Clean Architecture), and Rule 06 (Serialized Milestones & Authentic Verification). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate all open P0 vulnerabilities and calculation defects (F-01 through F-06):
1. **F-01 (P0 Storage)**: Enforce durable Supabase storage in `render_worker.py` for production environments (raise `JobProcessingError` if storage is unavailable/omitted in production, preventing silent degradation to ephemeral local `.qc-tmp/`). Pass initialized `storage` client in `main.py` and `extraction_worker.py:run_one_job`.
2. **F-02 (P0 RBAC)**: Add strict `@require_role([Role.SUPER_ADMIN, Role.ADMIN, Role.DEV])` protection to `POST /admin/settings/runner-fee` in `backend/app/api/routers/system.py` so non-admin staff users receive HTTP 403 Forbidden.
3. **F-03 (P0 AppSec)**: Replace Python `eval()` in `road_tax_engine._eval_formula` with a safe AST mathematical evaluator that disallows `**` exponentiation, CPU DoS vectors, and division-by-zero crashes.
4. **F-04 (P0 Route Guard)**: Extend Next.js `middleware.ts` route matcher to cover `/comparison/:path*`, `/ledger/:path*`, `/insights/:path*`, and `/ai-context/:path*`.
5. **F-05 (P0 Comparison Logic)**: Fix STMB PA Plus Towing regex in `towing_evaluator.py` to stop naive `"4" in text` from falsely classifying any quote with digit '4' as "Unlimited", and fix fallback towing for unknown insurers.
6. **F-06 (P0 Road Tax Monotonicity)**: Fix JPJ 2501-3000cc rate schedule discontinuity in `road_tax_engine.py` (West MY Private Car base rate: 840 -> 880; Labuan Private Car: 420 -> 440) and synchronize `policy-fields-card.tsx` from 840 to 880.

---

### Task 1: F-01 Durable Storage Enforcement & Worker Storage Injection

**Files:**
- Modify: `backend/app/workers/render_worker.py:195-218`
- Modify: `backend/app/workers/extraction_worker.py:787-815`
- Modify: `backend/app/main.py:75-90`
- Test: `tests/security/test_p0_open_exploits.py::test_f01_render_worker_requires_durable_storage`

- [x] **Step 1: Inspect failing test status in `test_p0_open_exploits.py`**
  Remove `@pytest.mark.xfail(strict=True)` for `test_f01` to establish a true failing assertion.
- [x] **Step 2: Update `render_worker.py` to reject `storage=None` in production**
  If `storage is None` and `app_env == "production"`, raise `JobProcessingError("generated_storage_required", "Durable PDF storage is required in production.")`.
- [x] **Step 3: Wire default `SupabaseStorage(settings)` in `extraction_worker.py:run_one_job`**
  Ensure background worker slots instantiate and pass durable `storage` when not explicitly supplied.
- [x] **Step 4: Verify `test_f01_render_worker_requires_durable_storage` passes 100%**

---

### Task 2: F-02 RBAC Protection on Runner Fee Mutation

**Files:**
- Modify: `backend/app/api/routers/system.py:823-826`
- Test: `tests/security/test_p0_open_exploits.py::test_f02_runner_fee_set_rejects_staff_user`

- [x] **Step 1: Inspect failing test status for F-02**
  Remove `@pytest.mark.xfail(strict=True)` for `test_f02`.
- [x] **Step 2: Add `require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)` in `runner_fee_set`**
  Ensure HTTP 403 is returned if a staff user attempts to POST to `/admin/settings/runner-fee`.
- [x] **Step 3: Verify `test_f02_runner_fee_set_rejects_staff_user` passes 100%**

---

### Task 3: F-03 Safe AST Formula Evaluator (Eliminating `eval()`)

**Files:**
- Modify: `backend/app/services/road_tax_engine.py:18-35`
- Test: `tests/security/test_p0_open_exploits.py::test_f03_road_tax_engine_eval_rejects_exponentiation`
- Test: `tests/unit/test_road_tax_ast_evaluator.py`

- [x] **Step 1: Inspect failing test status for F-03**
  Remove `@pytest.mark.xfail(strict=True)` for `test_f03`.
- [x] **Step 2: Implement AST expression evaluator in `road_tax_engine.py`**
  Parse with `ast.parse(formula, mode='eval')` supporting only binary ops (`+`, `-`, `*`, `/`), unary ops (`+`, `-`), numbers, and variable `cc`. Strictly reject `ast.Pow`, function calls, attributes, and handle division by zero cleanly.
- [x] **Step 3: Verify `test_f03_road_tax_engine_eval_rejects_exponentiation` and new AST unit tests pass 100%**

---

### Task 4: F-04 Next.js Middleware Matcher Route Coverage

**Files:**
- Modify: `frontend/src/middleware.ts:32-44`
- Test: `tests/security/test_p0_open_exploits.py::test_f04_frontend_middleware_matcher_covers_all_protected_routes`

- [x] **Step 1: Inspect failing test status for F-04**
  Remove `@pytest.mark.xfail(strict=True)` for `test_f04`.
- [x] **Step 2: Add `/comparison/:path*`, `/ledger/:path*`, `/insights/:path*`, `/ai-context/:path*` to `middleware.ts`**
- [x] **Step 3: Verify `test_f04_frontend_middleware_matcher_covers_all_protected_routes` passes 100%**

---

### Task 5: F-05 STMB PA Plus Towing Regex & Fallback Hardening

**Files:**
- Modify: `backend/app/services/marketing_comparison/towing_evaluator.py:221-243,285-295`
- Create: `tests/unit/test_towing_regex_hardening.py`

- [x] **Step 1: Write failing test in `tests/unit/test_towing_regex_hardening.py`**
  Assert that STMB quotes with `"2024"`, `"RM 400"`, `"Plate 4"` and `motor pa plus` without Plan 4 do NOT resolve to `"Unlimited"`. Assert that Plan 4 resolves to `"Unlimited"`, Plan 3 to `"300 km"`, Plan 2 to `"200 km"`, Plan 1 to `"100 km"`, and unlisted unknown insurer defaults to standard towing (`RM 200` or `50 km`), not `"Unlimited"`.
- [x] **Step 2: Update regex patterns in `towing_evaluator.py`**
  Use `re.search` with word boundaries `r"\b(?:plan|pelan)\s*4\b|\bunlimited\b|\bpa\s*plus\s*4\b"`, etc. Replace fallback `"Unlimited"` at line 295 with standard towing.
- [x] **Step 3: Verify `test_towing_regex_hardening.py` passes 100%**

---

### Task 6: F-06 JPJ Road Tax Monotonicity & Schedule Parity

**Files:**
- Modify: `backend/app/services/road_tax_engine.py:42,153`
- Modify: `frontend/src/components/session-workspace/review-components/policy-fields-card.tsx:251`
- Create: `tests/unit/test_road_tax_monotonicity.py`

- [x] **Step 1: Write failing test asserting road tax continuity and monotonicity across 2500cc/2501cc**
  Assert:
  - West MY Private Car at 2500cc is RM 880.00
  - West MY Private Car at 2501cc is RM 882.50 (monotonically greater than 880.00)
  - Labuan Private Car at 2500cc is RM 440.00
  - Labuan Private Car at 2501cc is RM 441.25 (monotonically greater than 440.00)
- [x] **Step 2: Fix base rates in `road_tax_engine.py` (840 -> 880, 420 -> 440) and `policy-fields-card.tsx` (840 -> 880)**
- [x] **Step 3: Verify `test_road_tax_monotonicity.py` passes 100%**

---

### Task 7: Full Regression, Pre-Commit Verification & State Sync

- [x] **Step 1: Run full pytest suite across `tests/security/` and `tests/unit/`**
- [x] **Step 2: Run frontend TypeScript compile check (`tsc --noEmit`)**
- [x] **Step 3: Run `commands/verify-brain.py`**
- [x] **Step 4: Update `docs/core/STATE.md` with verified Phase 1 deliverables**
