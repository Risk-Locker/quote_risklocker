# Quotation Workspace Stabilization & Concurrency Hardening Implementation Plan

> **Goal:** Eliminate the "Benefit cost must be included, paid, FOC, or unknown" error on windscreen/add-on removal, enable instant cross-screen sync for vehicle name without duplication (`HONDA CRF250`), fix instant road tax/runner fee toggles, prevent rapid-click concurrency jamming, and stop package dropdown reselection.

**Architecture:** Layered fix adhering to Amazon-grade clean boundaries:
1. **Domain & Backend Ledger (`backend/app/domain/benefits.py`, `backend/app/services/workspace_patch_service.py`):**
   - Safe cost status normalization in `CostStatus` and `workspace_patch_service.py` (`optional` -> `paid`, `free` -> `foc`) with zero 422 crash.
   - Comprehensive bidirectional sync on workspace save: propagate `car_model`, `car_brand`, `include_road_tax`, and `include_runner_fee` directly to `InsuranceTenure`, `TrackedVehicle`, and sibling sessions under the same tenure.
   - Vehicle name deduplication in `draft_mapper.py` and tenure display components so `HONDA` + `HONDA CRF250` never renders as `HONDA HONDA CRF250`.
2. **Quotation Workspace Queue & State (`frontend/src/components/session-workspace/`):**
   - Queue unjamming in `provider.tsx`: strip failed operations on error instead of permanently blocking the queue.
   - Correct `cost_status: "paid"` sent on benefit card untick and remove in `benefits-manager-panel.tsx` and `benefit-cards.tsx`.
   - Remove the motorcycle windscreen exclusion in `useBenefitOperations.ts` so users can always see, edit, and remove windscreen.
   - Remove the false "Mandatory Lock" on windscreen cards in `benefit-cards.tsx` and expose full custom limit and visibility controls.
   - Wire `include_road_tax` and `include_runner_fee` to `update_display_options` and trigger instant client-side total recalculation.
   - Prevent package reselection in `TemplateConfigCard.tsx` and `useReviewCatalogAndTemplate.ts` during async catalog operations.

---

## 10-Point Edge-Case Matrix

1. **Empty/Null Inputs:** `cost_status` null/empty/whitespace defaults safely to `paid` or `unknown`.
2. **Decimal Precision:** Financial totals and fee adjustments recalculate using exact decimal string values.
3. **Leap Dates / Timezones:** Preserved unchanged.
4. **Concurrency / Rapid Clicks:** `provider.tsx` queues and dispatches without stale revision 409 loops; failed operations are purged so the workspace never gets jammed.
5. **RBAC & Cross-Tenant:** Workspace permissions and user tracking intact.
6. **Vehicle Category & Brand Deduplication:** Vehicle names like `HONDA CRF250` remain unified without repeating brand prefixes (`HONDA HONDA CRF250`).
7. **Motorcycle Windscreen Access:** Windscreen coverage cards are visible, editable, and removable regardless of whether vehicle category is Motorcycle or Car.
8. **Instant Toggles:** Road tax and runner fee toggles immediately reflect in total payable and preview without requiring manual refresh.
9. **Display Options Sync:** `include_road_tax` and `include_runner_fee` synced to `InsuranceTenure` so Marketing Comparison and Quotation Workspace always match.
10. **SQL Performance:** Indexed queries; zero unindexed full-table scans.

---

## Serialized Milestones

- **Milestone 1 (Backend Core & Domain Resilience):**
  - Implement `normalize_cost_status()` in `backend/app/domain/benefits.py` and update `workspace_patch_service.py` to gracefully accept `optional`, `free`, `paid`, `included`, `foc`, `unknown`.
  - Add bidirectional sync in `workspace_patch_service.py` for `car_model`, `car_brand`, `engine_cc`, `vehicle_year`, `include_road_tax`, and `include_runner_fee` to `InsuranceTenure` and `TrackedVehicle`.
  - Fix vehicle name deduplication in `backend/app/extraction/draft_mapper.py`.
  - Unit tests in `tests/unit/test_workspace_patch_cost_status.py`.

- **Milestone 2 (Frontend Benefit Card & Windscreen Controls):**
  - Fix `benefits-manager-panel.tsx` and `benefit-cards.tsx` to send valid `cost_status: "paid"` when moving to `available_addon`.
  - Remove motorcycle windscreen suppression from `useBenefitOperations.ts` so users can always see, edit, and remove windscreen.
  - Remove the hardcoded "Mandatory" lock badge on windscreen in `benefit-cards.tsx` and unlock custom limit and visibility controls.

- **Milestone 3 (Instant Toggles, Concurrency Queue & Package Selection):**
  - Wire `include_road_tax` and `include_runner_fee` in `policy-fields-card.tsx` and `useReviewWorkspaceState.ts` to `update_display_options` with instant total recalculation.
  - Harden `provider.tsx`: purge failed operations on error so the workspace queue never becomes permanently jammed; improve saving timer/state feedback.
  - Fix package selection in `TemplateConfigCard.tsx` and `useReviewCatalogAndTemplate.ts` to prevent dropdown resets.
  - Fix vehicle brand deduplication in `TenureRow.tsx`, `TenureBulkActions.tsx`, and `CustomerVehicleLedgerPane.tsx`.

- **Milestone 4 (Authentic Multi-Domain Forensics & Verification):**
  - Run hermetic pytest suite.
  - Verify TypeScript compilation (`npx tsc --noEmit`).
  - Verify live workspace behavior and document in state.
