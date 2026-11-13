---
name: design2-pdf-parity
description: Maintain 1:1 mathematical, typographic, and visual parity between Design 2 React live canvas (design2-canvas.tsx) and Playwright Chromium A4 PDF output (backend/app/rendering/template_renderer_design2.py + benefit_schedule_renderer.py).
---

# Design 2 & Deterministic PDF Parity Skill

## 1. Core Invariants (`docs/domain/BUSINESS-RULES.md`)

- **One Authoritative Output Path:** Official customer PDFs are **always** generated deterministically server-side via Playwright Chromium (`backend/app/rendering/` + `backend/app/workers/render_worker.py`) using reviewed snapshot data + published pinned template revision — **never** via client browser `jsPDF` PNG screenshots (`review-phase.tsx` bug) and never falling back silently to stale static `<svg>` mockups (`preview-phase.tsx`).
- **Storage Enforcement (`F-01`):** Production `render_worker.py` MUST use the configured Supabase Storage provider cleanly (`backend/app/storage/supabase.py`), never failing open to `/.qc-tmp/stateless_generated/` when `storage=None`.
- **Browser Pool & Query Efficiency:** Reuse a pooled Chromium browser/page context rather than cold-launching Chromium per PDF request (`pdf_generator.py`), and look up `RenderSnapshot` rows by indexed query rather than `_rows()` full-table RAM scans.

## 2. Design 2 Visual & Data Contract (`references/design2-geometry-and-parity.md`)

- **No Hardcoded PII Fallbacks (`F-11`):** Never ship sample customer names, MyKad numbers, car plates, phones, or bank account numbers inside `template_renderer_design2.py`, `template_renderer.py`, `design2-canvas.tsx`, or template builder defaults.
- **4-Tier Benefit Card Hierarchy:** `(1) Title` -> `(2) Coverage Amount` -> `(3) Short Description` -> `(4) Cost : MYR XX.XX` (add-ons show cost; pure defaults omit costing badge). Preserve clean dual-tone `#1D1D1B + #E52320` 24-concept SVGs (`design2_icons.py` / `design2-icons.tsx`), structural `#64748B` hairlines, value-only `#334155` underlines, unified `#F8F9FC` Free Coverage + Bank panel, `108px` footer with white dividers, and `875`/`840` Sheet 2 A4 pagination budgets.
- **Selected Float-to-Top Ordering:** Both `backend/app/rendering/unified_addon_engine.py` and `frontend/src/lib/unified-addon-engine.ts` float selected/FOC active coverages (`✔`) to the top before unselected available add-ons (`☐`), staying 100% synchronized.
- **Engine Capacity Unit Suffix:** Display strictly `cc` for ICE vehicles or `kW` for EVs on `Engine Capacity/发动机排量 : ` — never append `cc` onto EV kilowatts.

## 3. Quick-Check Anti-Pattern Matrix

| Drift Risk | Deterministic Prevention Rule |
| :--- | :--- |
| Browser `jsPDF` PNG capture or static SVG fallback | Official downloads always stream Playwright Chromium server PDF |
| Dual pagination or rounded totals diverging in React | Share exact catalog/snapshot fields + `ROUND_HALF_UP` backend sums |
| Missing `storage` falling back to temp local directory | Fail-closed when Supabase storage fails; never dump customer PDFs to disk |
| Cold-starting Chromium per request / RAM `_rows()` scan | Pool Chromium context cleanly and query `RenderSnapshot` by primary key |

## 4. Verification Requirement

1. Render sample Design 2 quotes (ICE, EV, Lonpac, STMB/Takaful, Etiqa) cleanly via Chromium (`backend/app/rendering/`).
2. Inspect Sheet 1 + Sheet 2 crops side-by-side against `design2-canvas.tsx` in Playwright (`1024px–1920px` + `80%–120%` zoom).
3. Verify `%PDF-` binary validity, non-zero page count, zero overflowing benefit descriptions (`875`/`840` pagination budgets), and exact totals to the sen (`ROUND_HALF_UP`).
4. Verify no legacy sample PII (`Mohd`, dummy NRICs, fake plate numbers, bank accounts) appears anywhere inside fallback props (`references/design2-geometry-and-parity.md`).
