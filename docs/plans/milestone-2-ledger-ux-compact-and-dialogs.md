# Milestone 2: `/ledger` Compact Layout, Sticky Pan Rail & Native Dialog Purge (`F-06a`)

- **Status:** `VERIFIED`
- **Parent Plan:** `docs/plans/2026-11-17-ux-saving-ledger-and-sandbox-audit-plan.md` (revised roadmap §3)
- **Branch:** `v30.4`
- **Prerequisite:** Milestone 1 (`milestone-1-save-sync-and-api-repairs.md`) — re-verified 2026-11-17 (pytest, `tsc --noEmit`, code review of F-01..F-04b).
- **Estimated Scope:** `<= 450` net LOC, frontend only (`frontend/src/components/tenures/`).

> [!NOTE]
> **Plan revision (2026-11-17):** The original M2 bundled `/ledger` *and* `/comparison` chrome work. `comparison-matrix.tsx` alone is 2,441 lines with 19 native `alert()`/`confirm()` calls, so the combined scope breaks the Rule 06 `300–500` LOC budget. M2 now covers `/ledger` only. The `/comparison` chrome compression moves to a new **M3**; the old M3 (classifier + sandbox dry-run) becomes **M4** and the old M4 (RBAC + responsive gauntlet) becomes **M5**.
>
> The older `milestone-2-frontend-deslop-and-component-deduplication.md` (Clean Code roadmap) is **superseded** where it overlaps M1: M1 already removed client total math from `provider.tsx`/`useReviewWorkspaceState.ts` and deliberately *retains* failed ops (its "purge failed op" item contradicts M1 and must not be executed). Its remaining items (`benefit-cards.tsx` dead `AddonCard`, `policy-fields-card.tsx` helper extraction) carry over to a later de-slop slice.

## 1. Scope & Allowed Blast Radius

### Included
1. **True Compact mode (`<= 960px` total row width):**
   - Single source of column visibility in new `ledger-columns.ts` (`resolveLedgerColumns(density, hiddenColumns)`), used by both `LedgerTable.tsx` header and `TenureRow.tsx` cells so header/body can never drift.
   - Compact auto-hides `Ledger Created` and `PIC & Milestones` (secondary metadata stays in Detailed/Comfortable mode and the timeline drawer).
   - Compact widths: checkbox 48 + vehicle 200 + coverage 128 + stage 240 + quotes 190 + actions 104 ≈ **910px**.
2. **Declutter rows:**
   - Remove the always-on `Cli Unpaid` / `Agc Due` badges; show a single subtle `Client paid` / `Agency paid` chip only when the flag is `true` (information kept, noise removed).
   - Remove the duplicate `Confirm Hit ✓` button in the quotes column (`TenureStageSelector` already owns the HIT action).
   - Remove repeated coverage dates in the quotes column (already shown in the Coverage column).
   - Consolidate row actions into one column: `Compare`, `Logs`, `Edit` (the duplicate inline pencil + separate `Details` button both opened the same edit modal).
3. **Viewport-sticky horizontal pan rail:** replace the non-sticky `Left/Right` strip above `<thead>` with `LedgerScrollRail.tsx` — a `sticky bottom-0` rail with left/right buttons and a mirrored scrollbar, rendered only when `scrollWidth > clientWidth`. Card switches `overflow-hidden` → `overflow-clip` so `position: sticky` resolves against the viewport.
4. **Monolith slicing:** `TenureRow.tsx` (818L) → composer + `row-cells/` slices (`VehicleCustomerCell`, `CoveragePeriodCell`, `QuotesActivityCell`, `PicCell`, `RowActionsCell`), each `< 300` lines.
5. **Native dialog purge in `/ledger`:** `useLedgerState.ts` bulk delete / bulk confirm-hit `confirm()` → Radix `ConfirmDialog` (`pendingBulkAction` state); `edit-vehicle-deal-modal.tsx` and `TenureBulkActions.tsx` `alert()` → `useToast()`.

### Forbidden (out of scope for M2)
- `comparison-matrix.tsx` and all `/comparison` files (M3).
- Backend routers/services/models (no API or schema change in M2).
- `candidate_finder.py`, sandbox dry-run (M4), RBAC sweep (M5).

## 2. 10-Point Edge-Case & Scenario Matrix
1. **Empty / null:** Rows with no quotes, no cover note, no PIC, blank plate (`Chassis:`/`Engine:`/`No Plate`) still render; empty table keeps a correct `colSpan` from `resolveLedgerColumns`.
2. **Decimal / money display:** Quote chips display backend `total_payable` strings as-is (no client rounding/`toFixed(0)` truncation); no client math added.
3. **Dates:** Coverage dates rendered only in the Coverage column via existing `formatDateSafe`; no new date arithmetic.
4. **Concurrency / double-submit:** Bulk confirm dialog buttons disabled while `deletingBulk`/`confirmingBulk`; dialog closes only after the request settles.
5. **RBAC / CSRF:** No new endpoints; existing `api()` CSRF headers unchanged.
6. **Malformed data:** Long customer names / insurer names truncate with `title` tooltips; unknown stage falls back to neutral config.
7. **Partial failure:** Bulk action failure keeps selection and shows an error toast; dialog closes and table reloads.
8. **Responsive zoom & keyboard:** Compact fits 1280px at 100% without horizontal scroll; when overflow occurs (1024px / 120% zoom / Comfortable), the sticky rail stays visible at the viewport bottom; all icon-only actions carry `aria-label` + `title`; dialogs trap focus and close on `Esc`.
9. **Legacy rows:** Missing `created_by_email`, `expiry_month`, `sourced_quotes` handled with existing fallbacks.
10. **Scale:** Rail uses one `ResizeObserver` + passive scroll sync (no per-row listeners); no extra network calls.

## 3. Verification
- `cd frontend; npx tsc --noEmit` and `npx next lint` on touched files.
- Production build `npx next build` (isolated `NEXT_DIST_DIR` so the running dev server is not disturbed).
- `.\.venv\Scripts\pytest.exe tests/` (regression guard; M2 is frontend-only).
- Live browser: `/ledger` at 1024 / 1280 / 1920 widths, Compact vs Comfortable, sticky rail visibility, bulk dialog open/cancel, zero `console.error`.
- `.\.venv\Scripts\python.exe commands/verify-brain.py`.
