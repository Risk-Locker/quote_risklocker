# Milestone 3c: Connected Box 1 â†” Box 2 In-Place Towing Engine, Design 2 WYSIWYG Parity & `/builder/benefits` Cleanup

> **Status:** Ready to Execute (`v30.4`), part of `docs/plans/2026-11-17-combined-master-roadmap-edit-persistence-kurnia-3c-upload.md`
> **Skills:** `malaysian-motor-insurance`, `design2-pdf-parity`, `system-design-and-architecture`, `edge-case-and-scenario-matrix`, `test-driven-development`, `python-testing`
> **Model Profile:** `.agents/profiles/deep.md` (Gemini 4 Argon)

## 1. Objective & Empirical Root Causes

Eliminate split-brain divergence between Workspace Box 1 (`Current Benefits`), Design 2 Live Canvas / A4 PDF Free Added Coverage, Comparison Matrix Towing, and `/builder/benefits` catalogs (~380 LOC):

1. **Commercial Catalog Pinning (`backend/app/services/catalog_review_service.py`):**
   - Pass resolved `vehicle_type` / `is_commercial_heavy_vehicle(...)` when pinning company catalogs so Commercial Goods / Heavy Vehicles automatically pin to Commercial catalogs and seed `legal-defense-costs` + `repair-workmanship-warranty` directly into Box 1 instead of Private Car `towing`.
2. **Design 2 WYSIWYG Free Added Coverage (`backend/app/rendering/unified_addon_engine.py`, `frontend/src/lib/unified-addon-engine.ts`):**
   - Ensure `extract_free_coverage_items()` / `extractFreeCoverageItems()` render active Box 1 `current_benefits` truthfullyâ€”zero silent deletions of visible Box 1 cards and zero phantom catalog fallback injections when Box 1 is explicitly populated.
   - Harden `detect_towing_upgrade()` fallback to parse `value` / `typed_value` (e.g. `"Plan 4"`, `"Plan 3"`) cleanly across both Python and TypeScript.
3. **Database `CompanyBenefitCondition` Single Source of Truth (`backend/app/services/marketing_comparison/benefits_extractor.py`, `backend/app/rendering/render_context.py`):**
   - Query active `BenefitProfile` conditions plus legacy `profile_id IS NULL` conditions cleanly in `benefits_extractor.py` with indexed `IN (company_ids)` filters so ticking `Motor PA Plus â€” Plan 4` keeps ONLY `Motor PA Plus` in Box 2 and updates Box 1 Towing title & description in-place (`Emergency Towing Assistance (RM 200.00)` â†” `Unlimited Towing Assistance`) across Box 1 UI, Design 2 PDF, and Comparison Matrix.
   - Resolve contradictory Takaful Plan 1/2/3/wildcard conditions in seed/reconciliation helpers.
4. **`/builder/benefits` Deep Link & Copy Clarity (`frontend/src/app/builder/benefits/page.tsx`, `components/benefits-step-navigator.tsx`):**
   - Auto-select `"catalogs"` tab when `?product=&catalog=` URL parameters are supplied.
   - Clarify Global Insurer Conditional Rules vs Product Catalog scope labels.

## 2. Files

- **Allowed:** `backend/app/services/catalog_review_service.py`, `backend/app/rendering/unified_addon_engine.py`, `backend/app/rendering/render_context.py`, `backend/app/services/marketing_comparison/benefits_extractor.py`, `frontend/src/lib/unified-addon-engine.ts`, `frontend/src/app/builder/benefits/page.tsx`, `frontend/src/app/builder/benefits/components/benefits-step-navigator.tsx`, `tests/unit/` (`test_m3c_box1_design2_towing_parity.py`) (new).
- **Forbidden:** Upload workspace, ledger routes, raw ad-hoc mutations on live tenures.

## 3. Edge Cases Covered

- Commercial heavy vehicle with explicit `vehicle_type="Commercial"` vs capacity token `16000 KG`; Box 1 explicitly emptied by staff (`[]`) vs uninitialized (`None`); `Motor PA Plus` ticked with `"Plan 1"` (no unlimited towing upgrade) vs `"Plan 4"` (upgrades Box 1 towing in-place to `"Unlimited"`, suppresses duplicate unselected towing card in Box 2); URL query params `?product=foo&catalog=bar` on `/builder/benefits` cold load.

## 4. Verification Plan (Hermetic Synthetic Fixtures + Live Check)

- Write hermetic tests in `tests/unit/` (`test_m3c_box1_design2_towing_parity.py`) using synthetic SQLite fixtures (never depending on live DB UUIDs) for:
  1. Commercial catalog pinning seeding `legal-defense-costs` + `repair-workmanship-warranty` into Box 1,
  2. Box 1 â†” Design 2 Python & TS `extract_free_coverage_items` 1:1 parity,
  3. `Motor PA Plus â€” Plan 4` in-place Towing upgrade across `render_context.py`, `unified_addon_engine.py`, `unified-addon-engine.ts`, and `benefits_extractor.py`.
- Run `pytest tests/`, `npx tsc --noEmit`, `verify-brain.py`, and live browser check on Workspace Box 1 â†” Design 2 Canvas & `/builder/benefits?product=...&catalog=...`.

