# Frontend Engineering Rules (`frontend/AGENTS.md`)

> Scoped automatically to Next.js 15.5 / React / TypeScript / Tailwind / UI code under `frontend/`.

## Hard Engineering Invariants

1. **No Client Business Logic Duplication**:
   - Never hardcode JPJ road tax tables (e.g., `840` vs `880`), STMB/Lonpac towing rules, or total-payable rounding overrides in React components or providers. Display backend-calculated `Decimal` outputs.
2. **File & Component Modularity (`<600` Lines)**:
   - Never let pages or components grow into 1,000–4,000L monoliths (`review-phase`, `tenure-timeline-ledger`, `builder/benefits`). Extract pure presentational slices, custom hooks, and API services.
   - Never mutate React state or call formatters blindly across text inputs inside `useMemo` (e.g., `formatCoverPeriod` must ONLY run on period/date keys, never customer NRIC/names).
3. **UI Design System Lock (`docs/architecture/DESIGN-SYSTEM.md`)**:
   - Benchmark real product layouts via **Mobbin** (`mobbin_mobbin` when paid plan active, or `browser`/screenshots otherwise), verify accessible primitives via **`risklocker-ui-shadcn` MCP** (`.agents/plugins/risklocker-ui/`) + existing `frontend/src/components/ui/`, and lock strictly to Risklocker semantic `--rl-*` CSS tokens (`#f5f5f7`, `#ffffff`, `#1b1717`, `#ed1c24`, `8px`/`6px` radius, no pills, no random hex colors, Phosphor icons where specified, accessible Radix dialogs/tooltips).
   - **Ban native browser popups (`window.alert`, `window.confirm`, `window.prompt`).** Use accessible `Dialog` and `useToast()` components.
   - **Ban `localStorage` as primary business persistence.** All catalogs, presets, and drafts must round-trip through verified backend APIs.
4. **PDF Preview & Download Parity**:
   - Never generate official downloads via client `jsPDF` PNG raster screenshots or stale static `<svg>` mockups. Use the backend Playwright Chromium PDF endpoint (`/generate` / artifact download) and exact Design 2 HTML/React component parity.
5. **Security & Route Guards**:
   - Ensure `frontend/src/middleware.ts` protects every authenticated operational route (`/sessions`, `/comparison`, `/ledger`, `/builder`, `/extraction`, `/ai-context`, `/settings`). Zero hardcoded customer/bank PII in canvas fallbacks.
6. **Validation**:
   - Fast Track: `npx tsc --noEmit` inside `frontend/`. Deep Track: `npx tsc --noEmit` + `npm run build` + Playwright DOM/console/network verification.

