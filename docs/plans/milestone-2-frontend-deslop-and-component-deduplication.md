# Milestone 2: Frontend De-Slop, Dead Code Purge & Zero Client-Side Math

> [!WARNING]
> **Status: `SUPERSEDED` (2026-11-17).** Items 2 and 4 were overtaken by `milestone-1-save-sync-and-api-repairs.md`: client total math was removed from `provider.tsx`/`useReviewWorkspaceState.ts`, and failed queue operations are now deliberately **retained** (do NOT re-introduce the "purge failed op" behaviour below). Items 1 and 3 (`benefit-cards.tsx` dead `AddonCard`, `policy-fields-card.tsx` helper extraction) remain open for a later de-slop slice. Active Milestone 2 is `milestone-2-ledger-ux-compact-and-dialogs.md`.

> **Serialized Milestone 2 of 3 (`Rule 06`)**
> **Net Change Budget:** ~-650 lines (dead code removal & deduplication)
> **Allowed to Change:**
> - `frontend/src/components/session-workspace/review-components/benefit-cards.tsx`
> - `frontend/src/components/session-workspace/review-components/useReviewWorkspaceState.ts`
> - `frontend/src/components/session-workspace/review-components/policy-fields-card.tsx` (plus new helper slice `vehicle-catalog-sync.ts`)
> - `frontend/src/components/session-workspace/provider.tsx`
> - `frontend/src/components/comparison/manual-quote-modal.tsx`
> **Forbidden to Change:**
> - Backend Python services and database models
> - `design2-canvas.tsx` visual geometry

## 1. Non-Breaking Guarantees

1. **`benefit-cards.tsx` Deduplication (`1,548L -> <500L`):**
   - Deletes the 526-line dead `AddonCard` component (0 imports across `frontend/src/`).
   - Extracts `useBenefitCardEditor` hook shared by `IncludedCard` and `MatrixAddonCard`, keeping all props, styles, and queue operations 100% identical.
   - Removes blocking `window.confirm` on card delete (relying on the existing `Undo` button in `BenefitsManagerPanel`).
2. **`useReviewWorkspaceState.ts` Single Calculation Helper:**
   - Replaces 5 copy-pasted total calculation blocks with one pure helper `calculateWorkspaceDisplayTotals` that computes $\text{Net Premium} + \text{Road Tax} + \text{Runner Fee}$ without double-counting `workspace.extras`.
3. **`policy-fields-card.tsx` Helper Extraction (`833L -> <450L`):**
   - Moves vehicle/product classification functions and catalog auto-pinning logic to `vehicle-catalog-sync.ts` while re-exporting them from `policy-fields-card.tsx` so zero existing imports break.
4. **`provider.tsx` Queue Error Recovery:**
   - Restores `workingSnapshot` from `serverSnapshotRef.current` + remaining valid operations when a failed patch operation is purged, preventing phantom unsaved UI state.

## 2. Verification Gate for Milestone 2
- `cd frontend; npx tsc --noEmit`
- `.\.venv\Scripts\python.exe commands/security-audit.py` (confirm `NATIVE_DIALOG` and `MONOLITH_TS` reductions)
