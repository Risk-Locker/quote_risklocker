# Frontend Architecture Audit: Component Modularity, State Purity & Route Consolidation

> **Textbook Purpose**: Imagine opening one React file and seeing **3,974 lines of mixed JSX, CSS, API calls, modal state, and spreadsheet math** inside a single function. Nobody — not an intern, not a senior engineer, not an AI — can safely modify a 4,000-line file without breaking something nearby. Here is the exact diagnosis of every structural frontend flaw and the clean modular blueprint to replace it.

---

## 1. Giant Monolith Census (`>1,000` Lines)

Verified directly in the repository tree:

| File Path | Line Count | Why It Fails Modularity | Target Feature-Slice Decomposition (`<=250` Lines / File) |
| :--- | :--- | :--- | :--- |
| [`tenure-timeline-ledger.tsx`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/tenures/tenure-timeline-ledger.tsx) | `3,974L` (`~4.0k`) | Mixes monthly inbox filtering, inline table cell editors, stage popovers, financial toggles, CSV export, search, pagination, and bulk actions in 1 file | `features/ledger/`: `useLedgerQuery.ts`, `LedgerFiltersBar.tsx`, `LedgerMonthGroup.tsx`, `TenureRow.tsx`, `TenureStageSelector.tsx`, `TenureBulkActions.tsx` |
| [`builder/benefits/page.tsx`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/app/builder/benefits/page.tsx) | `3,661L` | Combines 4 competing benefit systems (`OurSpecial`, `Catalog`, `CompanyProfile`, `GlobalProfile`) + AI chat sidebar + Excel/Word matrix triggers | `features/benefits-studio/`: `ConceptRegistryTab.tsx`, `CompanyRulesMatrix.tsx`, `ConditionRulesEditor.tsx`, `useBenefitsStudio.ts` |
| [`review-phase.tsx`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/session-workspace/review-phase.tsx) | `~3,000L` | Contains raw HTML-to-PNG `jsPDF` screenshot generator, clipboard serializer, road-tax recalculations, form validation, EV detection, and modal orchestration | `features/workspace/review/`: `useReviewForm.ts`, `ReviewWorkspaceShell.tsx`, `ExportActionsBar.tsx`, `LivePreviewPane.tsx` |
| [`benefit-templates/page.tsx`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/app/builder/templates/benefit-templates/page.tsx) | `~2,507L` | Visual preset designer, factory defaults, `localStorage` offline hack, `window.prompt()` handler, and preview renderer in one component | `features/template-studio/benefit-cards/`: `PresetList.tsx`, `StyleControlsPanel.tsx`, `PresetPreviewCanvas.tsx` |
| [`builder/global-benefits/page.tsx`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/app/builder/global-benefits/page.tsx) | `2,079L` | Massive icon/asset mapping matrix mixed with upload handlers and clone dialogs | Merge into `features/benefits-studio/IconAssetMapper.tsx` |
| [`comparison-matrix.tsx`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/comparison/comparison-matrix.tsx) | `2,003L` | Hosts side-by-side matrix table, WhatsApp teaser drawer, quote upload drops, PDF generation triggers, and ranking state | Already partially split (`components/`, `hooks/`) — finish extracting `MatrixToolbar.tsx`, `MatrixComparisonTable.tsx`, `useComparisonMutations.ts` |
| [`shared.tsx`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/template-canvas/shared.tsx) & [`design2-canvas.tsx`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/template-canvas/design2-canvas.tsx) | `2,004L` + `900L` | Client re-implementation of Python HTML renderers with duplicated hardcoded defaults (`CHENG TECK KIOING`, `Hong Leong Bank`) | Retire custom canvas duplication in favor of unified backend HTML snapshot + thin TypeScript schema inspector |
| [`upload-workspace.tsx`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/upload/upload-workspace.tsx) | `1,704L` | Combines IndexedDB/staged upload queue (`staged-uploads-storage.ts`), mode switching, polling, and comparison batch linking | `features/upload/`: `DropzoneQueue.tsx`, `UploadJobTracker.tsx`, `ModeSelector.tsx` |
| [`global-ai-copilot.tsx`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/global-ai-copilot.tsx) | `1,329L` | Global floating drawer holding chat, catalog diff preview, prompt confirmation, and markdown parsing | `features/copilot/`: `CopilotDrawer.tsx`, `ActionDiffCard.tsx`, `useCopilotStream.ts` |

---

## 2. Severe Anti-Patterns in React State & Lifecycle

### Bug FE-01 [P0]: Direct State Mutation Inside `useMemo`!
- **Exact File & Lines**: [`review-phase.tsx:1390-1402`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/session-workspace/review-phase.tsx#L1390-L1402).
- **What the code actually does**:
  ```tsx
  if (vtype.startsWith("EV") || evCat) {
    vtype = vtype.startsWith("EV") ? vtype : (evCat || "EVSaloonCar");
    formValues["vehicle_type"] = vtype; // <-- DIRECTLY MUTATES React state object inside useMemo!
    fields["vehicle_type"] = vtype;
  } else if (...) {
    formValues["vehicle_type"] = "NonSaloonCar";
  ```
- **Why this breaks React**: In React, `state` (`formValues`) must be strictly immutable (`setFormValues(...)`). Mutating `formValues["vehicle_type"] = ...` inside `useMemo` causes silent desynchronization between what the DOM renders, what React's reconciler thinks changed, and what gets flushed to `PATCH /workspace`! In React StrictMode / concurrent renders, this creates ghost edits that appear on screen without ever setting `mutation.dirty = true`.
- **Exact Cure**: Compute derived EV/Non-Saloon classification in a pure helper (`const derivedVehicleType = ...`) — NEVER mutate `formValues` during render/memo. Only suggest a correction banner ("Detected EV — switch type to EVSaloonCar?") or write explicitly inside an event handler via `setFormValues`.

### Bug FE-02 [P0]: Side-Effect Database Writes on Page Mount (`/comparison`)
- **Exact File & Lines**: [`comparison/page.tsx:19-45`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/app/comparison/page.tsx#L19-L45).
- **What happens**: Navigating to `/comparison` without a `?tenure_id=` parameter executes `useEffect` -> `POST /tenures` with `"New Quotation Intake"` and `vehicle_no: "UNPLATED"`.
- **Why this is catastrophic**: Simply bookmarking `/comparison`, refreshing before redirect completes, or preloading the link creates orphaned `UNPLATED` rows in PostgreSQL and triggers unique constraint failures on [`TrackedVehicle.vehicle_no`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/models/tables.py#L415).
- **Cure**: Make `/comparison` show an empty-state Comparison Picker (Recent Active Comparisons + **"New Blank Comparison"** explicit button) when `tenure_id` is absent. Never auto-POST on mount.

### Bug FE-03 [P1]: Duplicated Client-Side Calculation Engines Out of Sync With Backend
- **Road tax implemented in 3 places**:
  1. [`provider.tsx:90-120`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/session-workspace/provider.tsx#L90-L120) (uses **`880`** for `2501–3000cc`)
  2. [`policy-fields-card.tsx:231-253`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/session-workspace/review-components/policy-fields-card.tsx#L231-L253) (uses **`840`** for `2501–3000cc`)
  3. [`road_tax_engine.py:41-42`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/road_tax_engine.py#L41-L42) (uses **`840`**)
- **Benefit 24-card engine implemented in 2 places**: [`unified-addon-engine.ts`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/lib/unified-addon-engine.ts) (`674L`) manually mirrored against [`unified_addon_engine.py`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/rendering/unified_addon_engine.py) (`724L`).
- **Cure**: Delete ALL client-side Malaysian JPJ road-tax math tables and `CANONICAL_24_CATALOG` mirrors. Request authoritative calculations from `POST /api/road-tax/calculate` (debounced) and read workspace card arrays directly from backend `GET /api/sessions/{id}/workspace`!

### Bug FE-04 [P2]: Unsafe `localStorage` Caches & `api/[...path]/route.ts` Error Swallowing
- **Browser storage drift**: [`benefit-templates/page.tsx:265, 438-457`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/app/builder/templates/benefit-templates/page.tsx#L265) saves/reads custom benefit card presets from `localStorage` (`risklocker_cached_benefit_presets`, `risklocker_benefit_card_presets`) on network errors. That creates invisible "it works on my laptop only" split-brain presets that vanish on another staff computer or fail during backend PDF generation!
- **Proxy 503 Masking**: [`frontend/src/app/api/[...path]/route.ts:55-60`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/app/api/[...path]/route.ts#L55-L60) wraps the entire proxy fetch in `catch {}` -> `HTTP 503`, making proxy config errors indistinguishable from backend downtime or request body stream timeouts. Log structured failure diagnostics server-side (never exposing stack traces/secrets to client) with distinct `502 Bad Gateway` vs `504 Gateway Timeout`.

---

## 3. Route Consolidation & Dead Code Elimination Plan

| Legacy / Duplicate Path | Status Today | Consolidated Enterprise Route |
| :--- | :--- | :--- |
| `/insights`, `/insights?tab=...` | 34-line client redirect (`insights/page.tsx`) | Redirect HTTP 308 in Next config / remove dead route cleanly -> `/ledger` |
| `/admin`, `/admin/benefits`, `/admin/checks`, `/admin/companies`, `/admin/storage`, `/admin/templates`, `/admin/templates/[id]/builder` | 7 stub redirect pages (`4L–5L` each) | Consolidate to clean `/settings/*` and `/studio/*` via permanent `redirects()` in `next.config` (zero React page files needed) |
| `/settings/extraction/*` (4 redirect stubs) | Duplicate stub pages (`5L` each) | Move into `/studio/extraction/*` or keep canonical `/extraction/*` without stub directories |
| `/builder/our-specials`, `/builder/templates`, `/builder/templates/benefits` | 3 redirect stub pages (`5L–13L`) | Permanent Next.js `redirects()`, delete stub `page.tsx` files |
| `/upload`, `/upload/single`, `/upload/fleet`, `/upload/marketing-comparison` | 4 identical 20-line wrappers | Single `/upload?mode=single|fleet|comparison` page with URL tab state |

### Target Modular Directory Map (`frontend/src/`)
```text
frontend/src/
├── app/                     # Thin Next.js App Router entrypoints ONLY (<80 lines each)
├── components/ui/           # Reusable pure Radix/Tailwind design-system primitives
├── components/layout/       # AppShell, role-filtered navigation, header quota meter
├── features/
│   ├── auth/                # Login, session guard hooks
│   ├── workspace/           # Review form, pricing breakdown, benefit tabs, HTML iframe preview
│   ├── comparison/          # Multi-insurer comparison matrix, rankings, WhatsApp formatter
│   ├── ledger/              # Renewal timeline, stage workflow, financial journal drawer
│   ├── studio/              # Unified benefit rules studio, template builder, asset library
│   └── copilot/             # Floating assistant drawer + structured confirmation diffs
└── lib/                     # Thin API client, auth helpers, MyKad/date formatting utilities (ZERO business pricing!)
```

