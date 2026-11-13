# Design 2 Geometry, Sheet 2 Pagination & Parity Spec

## 1. Exact Shared File Pairs (Update Both Together or Fail Parity)

| Concern | Backend Rendering File | Frontend Live Canvas / Lib |
| :--- | :--- | :--- |
| Main A4 Quotation Layout | `backend/app/rendering/template_renderer_design2.py` | `frontend/src/components/template-canvas/design2-canvas.tsx` |
| 24 Dual-Tone SVG Icons | `backend/app/rendering/design2_icons.py` | `frontend/src/components/template-canvas/design2-icons.tsx` |
| Float-to-Top 24-Slot Engine | `backend/app/rendering/unified_addon_engine.py` | `frontend/src/lib/unified-addon-engine.ts` |
| Sheet 2 Benefit & Endorsements Schedule | `backend/app/rendering/benefit_schedule_renderer.py` | Previewed via Sheet 2 pagination spec (`875`/`840` budget) |

## 2. Visual Invariants Never To Break
- **Logo Cropping:** Non-destructive bounding-box transparent/white margin trim on insurer logos (e.g., Takaful Malaysia, Lonpac) so marks fill clean header frames instead of shrinking to 30% padding.
- **Capacity Display:** Print `Engine Capacity/发动机排量 : ` appending **strictly** `cc` for ICE or `kW` for EV, NEVER both.
- **Zero Raster Screenshots (`jsPDF`):** Clicking "Download PDF" in Review or Preview MUST download the server-generated Chromium `%PDF` binary, never canvas PNG screenshots.
- **Zero Mid-Card Page Splits:** `benefit_schedule_renderer.py` tracks accumulated pixel heights cleanly across Sheet 2 A4 breaks so no benefit card or endorsement block slices across pages.

