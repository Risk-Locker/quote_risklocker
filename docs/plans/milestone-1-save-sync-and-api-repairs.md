# Milestone 1: Save, Sync & API Repairs (`F-01`, `F-02`, `F-03`, `F-04a`, `F-04b`)

- **Status:** `VERIFIED`
- **Parent Plan:** `docs/plans/2026-11-17-ux-saving-ledger-and-sandbox-audit-plan.md`
- **Branch:** `v30.4`
- **Estimated Scope:** `<= 450` net LOC across backend identity sync, router/schema parity, and frontend workspace/ledger/comparison save paths.

## 1. Scope & Allowed Blast Radius

### Included Fixes
1. **`F-01` (CRITICAL â€” Cross-Vehicle / Sandbox Overwrite in Tenure Identity Sync):**
   - File: `backend/app/services/tenure_identity_sync_service.py` (`_propagate_to_session_drafts`, `_update_single_draft_fields`)
   - Fix: Restrict vehicle specs propagation (`vehicle_no`, `car_brand`, `car_model`, `engine_cc`, `chassis_no`, `engine_no`, `manufacture_year`, `vehicle_type`, `powertrain`) strictly to sessions linked by `tenure_id == tenure.id` or `tracked_vehicle_id == tv.id`. Restrict coverage dates, road tax, runner fee, NCD, and payable totals strictly to `session.tenure_id == tenure.id`. Sibling sessions sharing ONLY `customer_id == cust.id` receive ONLY customer identity updates (`customer_name`, `ic_or_brn`). Exclude `is_test=True` sandbox sessions from production propagation.
2. **`F-02` (Ledger Row Inline / Stage Save `405`):**
   - Files: `frontend/src/components/tenures/useLedgerState.ts`, `backend/app/api/routers/tenures.py`, `backend/app/api/schemas.py`
   - Fix: Route `patchTenureField` to `PATCH /tenures/${tenureId}/ledger-fields` instead of `PATCH /tenures/${tenureId}` and ensure backend schema supports all inline/modal fields sent by the ledger UI cleanly.
3. **`F-03` (Comparison Fixed Costs / NCD Modal `405` & Client `Math.round`):**
   - Files: `frontend/src/components/comparison/comparison-matrix.tsx`, `frontend/src/components/comparison/hooks/useNcdHistory.ts`
   - Fix: Change `method: "PATCH"` -> `method: "POST"` on `/comparison/${tenureId}/fixed-costs`; remove client `Math.round(gq.total_payable)` in `comparison-matrix.tsx`.
4. **`F-04a` (EV `kW` / Lorry `KG` Coerced to `CC` on Blur):**
   - File: `frontend/src/components/session-workspace/review-components/policy-fields-card.tsx`
   - Fix: Skip appending `" CC"` when `isCurrentEV` or lorry weight (`KG`) / EV unit (`kW`) applies.
5. **`F-04b` (Staged Workspace Saving UX, Failed-Op Retention, Accessible Leave Guard, Single Source of Truth Math & Atomic Generate):**
   - Files: `frontend/src/components/session-workspace/provider.tsx`, `frontend/src/components/session-workspace/review-phase.tsx`, `frontend/src/components/session-workspace/review-components/useReviewWorkspaceState.ts`, `frontend/src/components/session-workspace/review-components/useReviewCatalogAndTemplate.ts`, `frontend/src/components/session-workspace/review-components/ReviewHeaderCard.tsx`, `frontend/src/components/session-workspace/review-components/UnsavedChangesBar.tsx`, `frontend/src/components/session-workspace/review-components/useQuotationExports.ts`, `backend/app/rendering/render_context.py`, `backend/app/services/workspace_snapshot_service.py`, `backend/app/services/generation_service.py`.
   - Fix: Replace silent 800ms auto-`PATCH` with staged unsaved draft state + sticky Save/Discard bar showing dirty edit count/fields; retain failed queued operations in state so `dirty` stays `true` until acknowledged/saved; replace blocking `window.confirm()` route-leave guard with an accessible Radix/shadcn confirm dialog; drop client-side total/rounding math in favor of authoritative backend `Decimal` response on save; enforce atomic pre-flight save before quotation PDF/PNG export.

### Forbidden Files (Out of Scope for M1)
- Do NOT touch M2 `/ledger` layout/scroll/toolbar overhaul (`LedgerTable.tsx`, `LedgerFiltersBar.tsx`, `TenureRow.tsx` visual layout) beyond verifying field names.
- Do NOT touch M3/M4 files (`candidate_finder.py`, `covernote_classifier.py`, sandbox ledger views, comparison layout).

## 2. Mandatory 10-Point Edge-Case & Scenario Matrix
1. **Empty / Null / Whitespace Inputs:** Blank `engine_cc`, `customer_name`, or `roadtax` updates must clear or fall back cleanly without appending `" CC"` to `""` or throwing `NaN` in JS/Python.
2. **Decimal / Bounds Precision:** Backend `Decimal` totals stay `2dp` without JS `Math.round()` integer truncation; `roadtax = 0` or negative/invalid strings reject cleanly at schema validation.
3. **Dates & Boundaries:** Coverage dates (`coverage_start_date` / `coverage_end_date`) propagate strictly within matching `tenure_id`, preserving multi-year historical tenures and Feb-29 boundaries untouched.
4. **Concurrency / Double-Submit & Failed Save Retention:** Rapid `[Save & Sync]` or `[Generate Quotation]` deduplicates in-flight saves; network/4xx/5xx save failures restore failed queued ops to pending queue so `dirty` stays `true` and no changes are silently dropped.
5. **RBAC / IDOR / CSRF / Sandbox Isolation:** Sandbox (`is_test=True`) sessions never overwrite or inherit updates from production `CustomerAccount`/`InsuranceTenure` propagation, and all state-changing routes use `PATCH`/`POST` with CSRF headers cleanly.
6. **Malformed Inputs / Units:** EV `"150 kW"` / `"150"` on EV powertrain or Commercial `"7500 KG"` never turns into `"150 CC"` / `"7500 CC"`.
7. **Timeout / Partial Failure Rollback:** Save failure leaves local staged draft intact, displays explicit error status/message, and blocks stale quotation export until save succeeds.
8. **Responsive Zoom & Accessible Navigation Guard:** Sticky Unsaved Changes Bar wraps cleanly at `1024pxâ€“1920px` (`80%â€“120%` zoom), uses `--rl-*` tokens, and route-leave guard uses keyboard-accessible Dialog (`Esc`, focus trap) instead of native `window.confirm()`.
9. **Legacy Unmigrated Rows:** Sessions where `tracked_vehicle_id` is `None` still fall back to `tenure_id == tenure.id` without leaking into sibling vehicles sharing `customer_id`.
10. **Indexed SQL Scaling:** `_propagate_to_session_drafts` queries strictly indexed `tenure_id` / `tracked_vehicle_id` / `customer_id` columns without full-table scans.

## 3. Permanent Verification & Regression Plan
- **Hermetic Pytest:** Add tests in `tests/unit/test_milestone1_save_sync_repairs.py` covering multi-vehicle same-customer sync isolation, sandbox (`is_test=True`) isolation, multi-year same-vehicle date isolation, `PATCH /tenures/{id}/ledger-fields` full payload coverage, and `POST /comparison/{id}/fixed-costs`.
- **Checks:** Full `.\.venv\Scripts\pytest.exe tests/`, `cd frontend && npx tsc --noEmit`, `.\.venv\Scripts\python.exe commands/verify-brain.py`, plus live API & browser UI checks against running dev servers if available.

