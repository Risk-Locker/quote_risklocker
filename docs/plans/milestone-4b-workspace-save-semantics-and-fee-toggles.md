# Milestone 4b: Workspace Save Semantics, Learn 422 and Fee Toggles

> **Status:** Ready to Execute (`v30.4`), part of `docs/plans/2026-11-17-combined-master-roadmap-edit-persistence-kurnia-3c-upload.md`
> **Skills:** `systematic-debugging`, `test-driven-development`, `edge-case-and-scenario-matrix`, `shadcn`
> **Model Profile:** `.agents/profiles/deep.md` (Gemini 4 Argon)

## 1. Objective

Make workspace editing accurate and frustration-free: touching a field or toggling a benefit and returning it to its saved state clears the `"Unsaved"` indicator (`dirty === false`), individual edits can be undone from the Unsaved bar, `/api/business/dictionaries/learn` never fires `422`, and Road Tax / Runner Fee toggles persist across workspace saves, comparison loads, and commercial vehicle rescans.

## 2. Hardened Design (with Proven P7 Root Causes)

1. **Snapshot-Diffed Dirty State (`provider.tsx`):**
   - In `frontend/src/components/session-workspace/provider.tsx`, compare incoming `queueOperation` values against the baseline server snapshot value for that path (normalized for strings/booleans/numbers).
   - When an edited field or benefit `include`/`exclude` toggle returns to its saved server snapshot state, remove the pending operation from the map so `dirty` and `dirtyPaths` immediately drop back to clean (`false` / `[]`).
2. **Per-Edit Undo (`UnsavedChangesBar.tsx` & `provider.tsx`):**
   - Expose `revertOperation(path: string)` on the workspace context so the user can revert any individual dirty path from the Unsaved Changes popover list while keeping other edits intact (`"Discard all"` remains available).
3. **Explicit Save Default + Opt-In Auto-Save:**
   - Keep explicit Save as the default (`autoSaveEnabled = false` in `localStorage` unless toggled on by the user) so multi-field edits never trigger mid-typing cross-sync.
4. **Fix `/api/business/dictionaries/learn` `422` (`useReviewWorkspaceState.ts` & `admin_service.py`):**
   - Restrict `LEARNABLE` in `frontend/src/components/session-workspace/review-components/useReviewWorkspaceState.ts:21` strictly to `car_brand` -> `"car_brand"` and `car_model` -> `"car_model"`, matching `LEARNABLE_FIELDS` in `backend/app/services/admin_service.py:576`.
   - Never call `/business/dictionaries/contains` or `/business/dictionaries/learn` for non-learnable fields. Surface any genuine error as a dismissible notice instead of silently swallowing it.
5. **Fix Road Tax & Runner Fee Toggle Persistence (`P7` Verified Causes):**
   - **Cause A (`marketing_comparison_service.py:320-325` and `:2411`):** `get_marketing_comparison` and `rescan_comparison` currently force `tenure.include_road_tax = False` and `tenure.include_runner_fee = False` whenever `is_commercial_heavy_vehicle(...)` is true, overwriting explicit user toggles! Fix: only apply `default_fee_inclusions` when a tenure is first created (`tenure.include_road_tax is None`), NEVER overwriting an existing boolean on `GET` or `rescan`.
   - **Cause B (`workspace_patch_service.py:1235-1252`):** Ensure `update_display_options` (`include_road_tax`, `include_runner_fee`) and field decisions (`decideField("include_road_tax", ...)`) resolve deterministically with `display_options` taking precedence when toggled in `policy-fields-card.tsx`, and synchronize `tenure.include_road_tax` / `tenure.include_runner_fee` plus `entry.include_road_tax` / `entry.include_runner_fee` on save.

## 3. Files

- **Allowed:** `frontend/src/components/session-workspace/provider.tsx`, `frontend/src/components/session-workspace/review-components/useReviewWorkspaceState.ts`, `frontend/src/components/session-workspace/review-components/UnsavedChangesBar.tsx`, `frontend/src/components/session-workspace/review-components/policy-fields-card.tsx`, `backend/app/services/workspace_patch_service.py`, `backend/app/services/marketing_comparison_service.py`, `backend/app/services/admin_service.py`.
- **Forbidden:** Design 2 PDF renderers, upload workspace.

## 4. Hermetic & Live Tests

- Unit/component test: edit field -> `dirty === true` -> edit back to initial value -> `dirty === false`; toggle benefit twice -> `dirty === false`; `revertOperation(pathA)` reverts only `pathA`.
- Backend test: `/api/business/dictionaries/learn` with `car_brand` / `car_model` returns `200`; unsupported fields are never sent by `useReviewWorkspaceState.ts`.
- Integration + Playwright test: toggle Road Tax and Runner Fee off/on for both private and heavy commercial vehicles, Save, reload workspace and comparison page -> state persists and `total_payable` updates from backend `Decimal` math with zero `console.error`.

