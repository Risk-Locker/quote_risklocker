# Milestone 3c: Connected Box 1 ↔ Box 2 In-Place Towing Engine, Design 2 WYSIWYG Parity & `/builder/benefits` Cleanup

> **Status:** Ready to Execute Next (`v30.4`)  
> **Skills Required:** `malaysian-motor-insurance`, `design2-pdf-parity`, `system-design-and-architecture`, `edge-case-and-scenario-matrix`, `test-driven-development`, `python-testing`

## 1. Objective & Empirical Root Causes to Resolve
Eliminate split-brain divergence between Workspace Box 1 (`Current Benefits`), Design 2 Live Canvas / A4 PDF Free Added Coverage, Comparison Matrix Towing, and `/builder/benefits` catalogs (~380 LOC):
1. **Commercial Catalog Pinning (`backend/app/services/catalog_review_service.py`):**
   - Pass resolved `vehicle_type` / `is_commercial_heavy_vehicle(...)` when pinning company catalogs so Commercial Goods / Heavy Vehicles (e.g. `266e1ac8` `VRS7732` `SANY`) automatically pin to Commercial catalogs and seed `legal-defense-costs` + `repair-workmanship-warranty` directly into Box 1 instead of Private Car `towing`.
2. **Design 2 WYSIWYG Free Added Coverage (`backend/app/rendering/unified_addon_engine.py`, `frontend/src/lib/unified-addon-engine.ts`):**
   - Ensure `extract_free_coverage_items()` / `extractFreeCoverageItems()` render active Box 1 `current_benefits` truthfully — zero silent deletions of visible Box 1 cards and zero phantom catalog fallback injections when Box 1 is explicitly populated.
   - Harden `detect_towing_upgrade()` fallback to parse `value` / `typed_value` (e.g. `"Plan 4"`, `"Plan 3"`) cleanly across both Python and TypeScript.
3. **Database `CompanyBenefitCondition` Single Source of Truth (`backend/app/services/marketing_comparison/benefits_extractor.py`, `backend/app/rendering/render_context.py`, DB seed hygiene):**
   - Query active `BenefitProfile` conditions plus legacy `profile_id IS NULL` conditions cleanly in `benefits_extractor.py` with indexed `IN (company_ids)` filters (solving `3b759922` `Motor PA Plus — Plan 4` parity across Box 1 UI, PDF, and Comparison).
   - Audit & resolve contradictory Takaful Plan 1/2/3/wildcard conditions in DB hygiene migration/seed helper.
   - Ticking/unticking `Motor PA Plus — Plan 4` keeps ONLY `Motor PA Plus` in Box 2 and updates Box 1 Towing title & description in-place (`Emergency Towing Assistance (RM 200.00)` ↔ `Unlimited Towing Assistance`).
4. **`/builder/benefits` Deep Link & Copy Clarity (`frontend/src/app/builder/benefits/page.tsx`, `components/benefits-step-navigator.tsx`):**
   - Auto-select `"catalogs"` tab when `?product=&catalog=` URL parameters are supplied (e.g. links from Studio/session cards).
   - Clarify Global Insurer Conditional Rules vs Product Catalog scope labels.

## 2. Verification Plan
- TDD hermetic tests covering `266e1ac8` Commercial catalog pinning + Box 1 ↔ PDF WYSIWYG match (`Legal Defense Costs` + `Panel Workmanship Warranty`), `3b759922` `Motor PA Plus — Plan 4` in-place Towing swap across `render_context.py`, `unified_addon_engine.py`, `unified-addon-engine.ts`, and `benefits_extractor.py`, plus Takaful Plan condition conflict resolution.
- Full `pytest tests/`, `npx tsc --noEmit`, `npm run lint`, `npm run build`, `verify-brain.py`, and Playwright live checks on Workspace Box 1 ↔ Canvas ↔ PDF & `/builder/benefits?product=...&catalog=...`.
