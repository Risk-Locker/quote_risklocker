# Milestone 2: Pricing Precision & Excel-Style Staff Freedom

> **Spec Document:** `docs/superpowers/plans/2026-11-12-milestone-2-pricing-precision-and-staff-freedom.md`  
> **Status:** Completed & Verified (100% CI Parity)  
> **Prerequisite:** Milestone 1 Completed

**Goal:** Implement Bank Negara Malaysia (BNM) 5-cent cash rounding mechanism with an exact cents UI toggle, add explicit enable/disable checkboxes for Road Tax and Runner Fee (supporting Lorries, commercial fleets, and self-renewing clients), unlock all input fields across the app so staff edits are permanently respected, and provide a 30-second "Fast-Quote" manual fallback modal.

---

## Global Constraints

- **Pure Decimal Currency:** All rounding and delta math uses Python `decimal.Decimal` (zero `float`).
- **User Edits Are Sacred:** Automated calculation hooks must never revert, overwrite, or snap back user-entered values.
- **BNM Cash Rounding Standard:**
  - Cents ending in 1 or 2 $\to$ round down to 0
  - Cents ending in 3 or 4 $\to$ round up to 5
  - Cents ending in 6 or 7 $\to$ round down to 5
  - Cents ending in 8 or 9 $\to$ round up to 10

---

## Tasks

### Task 1: BNM 5-Cent Currency Rounding Engine - [COMPLETED]
- Created: `backend/app/domain/motor/currency_rounding.py`
  - Function: `apply_bnm_cash_rounding(amount: Decimal) -> Decimal`
  - Function: `format_currency_with_precision(amount: Decimal, mode: Literal["exact", "rounded_5cent"]) -> str`
- Tested: `tests/domain/test_currency_rounding.py` (32 hermetic unit tests covering cent endings 0 through 9, roll-over boundaries, negative handling).

### Task 2: Comparison Matrix Cents & Rounding Toggle - [COMPLETED]
- Modified: `frontend/src/components/comparison/comparison-matrix.tsx` & `UnderwriterQuoteCard.tsx`
  - Added UI Toggle Switch: `[ Exact Cents (.15) | BNM 5¢ Rounded (.15) ]`
  - Respected user preference in `localStorage.getItem("rl_rounding_mode")`.
  - Applied dynamically across sum insured, motor premium, and net total payable columns.

### Task 3: Road Tax & Runner Fee Enable/Disable Checkboxes - [COMPLETED]
- Modified: `backend/app/models/tables.py` (Added `include_road_tax` and `include_runner_fee` columns; `migrations/075_add_include_road_tax_and_runner_fee.sql`).
- Modified: `frontend/src/components/comparison/comparison-matrix.tsx` & `CustomerVehicleLedgerPane.tsx`
  - Added explicit checkboxes `[x] Include Road Tax` and `[x] Include Runner Fee`.
  - Unchecking immediately zeroes out the cost in calculations, recomputes total payable, and labels the card as `(Excl. Roadtax & Runner fee)` or partial.
- Tested: `tests/integration/test_milestone_2_pricing_and_fixed_costs.py`.

### Task 4: Unlock All Form Inputs & Permanent Edit Respect - [COMPLETED]
- Audited & Modified: `frontend/src/components/session-workspace/review-phase.tsx`, `policy-fields-card.tsx`, and `comparison-matrix.tsx`.
  - Removed aggressive automatic `useEffect`/`onBlur` re-computation hooks that clobbered `roadtax` and fixed costs when staff had entered custom or zero values.
  - Form edits are locked in draft state and preserved across tab switches and comparisons.

### Task 5: 30-Second "Fast-Quote" Manual Fallback Modal - [COMPLETED]
- Created: `frontend/src/components/comparison/components/FastQuoteModal.tsx`
  - Clean modal: Underwriter quick-picker presets, Sum Insured, Motor Premium, Towing presets, and live calculation preview banner.
  - Linked to matrix "+ Fast Quote (30s)" amber button in `comparison-matrix.tsx`.
