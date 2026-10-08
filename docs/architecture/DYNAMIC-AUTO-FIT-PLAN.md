# Dynamic Auto-Fit & Multi-Line Benefit Title Implementation Plan

## 1. Executive Summary & Problem Context

In motor quotation rendering (verified on live session draft `252f65a5-7d01-412c-b96a-e03e63fa6bcc`, reference `RL260000308`, Tesla Model Y RWD, AmGeneral Insurance Berhad, using template `Bilingual Agency Motor v3`):
1. **Benefit Titles Truncated / Cut Off**:
   - In Purchased Extras (Row 2, Column 3), the title `"Waiver of Compulsory Excess for Unnamed Drivers"` is cut off into `"Waiver of Compulsory Excess for Unnamed"`, omitting `"Drivers"`.
   - Other long benefit titles are similarly constrained to a single line.
2. **Row 4 Cards Clipped at Bottom**:
   - In Recommended Add-On Upgrades (Section 3), there are 11 cards. In a 3-column grid, this spans 4 rows (3 + 3 + 3 + 2).
   - The bottom half and bottom borders of Row 4 cards (`Legal Liability of Passengers` and `EV Charger Liability`) are clipped / faded out.
3. **The "False Gap" at Page Bottom**:
   - Below Row 4, there is a visible ~88px empty white space between the cards and the footer (`*Terms & Conditions Apply | Quotation Validity: 01-11-2025`).
   - The user understandably asks: *If there is still empty space below, why are Row 4 cards clipped, and why did the layout not compress or fit properly?*

---

## 2. Root Cause Analysis

### Cause A: Rigid 1-Line Title Clamp (`target_row_h < 64px`)
- **Backend**: [backend/app/rendering/benefit_grid_renderer.py:392-402](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/rendering/benefit_grid_renderer.py#L392-L402)
  ```python
  elif target_row_h > 0 and target_row_h < 64.0:
      title_wrap_css = "overflow:hidden;display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;word-break:break-word;white-space:normal;"
  ```
- **Frontend Canvas**: [frontend/src/components/template-canvas/shared.tsx:1232-1234](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/template-canvas/shared.tsx#L1232-L1234)
  ```typescript
  const cardTitleClamp = (element as any).textWrap === "truncate"
    ? 1
    : ((element as any).textWrap === "multi" ? 3 : (cardRowH > 0 && cardRowH < 50 ? 1 : 2));
  ```
- **Diagnostic**: When a quotation has a high load of benefits (3 FOC + 6 Extras + 11 Addons = 7 total rows), the calculated row height is ~52px–60px. Because `target_row_h < 64.0`, the backend unconditionally forces `-webkit-line-clamp: 1` on every card title, discarding any second line of text. In a 65–74px card, a 2-line title at 8.5–9.5px font-size only consumes ~20px of vertical space, leaving plenty of room for icon and description.

### Cause B: Fixed Grid Container Height Clamps 4th Row
- In [frontend/src/components/template-canvas/shared.tsx:766](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/template-canvas/shared.tsx#L766), the grid wrapper is:
  ```html
  <div class="relative h-full w-full overflow-hidden">
  ```
- In the template configuration, `available_addons_grid` was authored with a fixed bounding box of `h: 268px`.
- 3 rows at 74px + gaps = `231px`. That leaves only `37px` for Row 4.
- Because Row 4 needs ~74px, the bottom 37px of Row 4 is cut off by `overflow: hidden`.

### Cause C: Non-v4 Hardcoded 84px Row Height Triggers Emergency `scale(0.93)`
- In [backend/app/rendering/benefit_grid_renderer.py:658-668](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/rendering/benefit_grid_renderer.py#L658-L668), non-v4 templates hardcode:
  ```python
  addon_row_height = max(84.0, ...)
  ```
- With 7 rows at 84px + headers (97px) + table (318px), total page content reached **1,205px** (exceeding the 1,123px A4 height).
- In [backend/app/rendering/template_renderer.py:851-854](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/rendering/template_renderer.py#L851-L854), an emergency scale was triggered:
  ```css
  transform: scale(0.93195); transform-origin: top center;
  ```
- When the 1,205px layout was shrunk down to 93.2%, the bottom content was pulled upward by **~82px**, creating a false void between the content and the footer, while Row 4 was already truncated inside its container before the scaling occurred.

---

## 3. Mathematical Specification for Proportional Auto-Fit

On a standard A4 portrait canvas (794px × 1123px):
1. **Safe Bottom Boundary**:
   $$\text{safe\_bottom} = \text{footer\_y} (1072\text{px}) - 14\text{px} = 1058\text{px}$$
2. **Top Content Anchor**:
   $$y_{\text{top}} = \text{card\_bottom} + 10\text{px} \approx 412\text{px} \text{ to } 426\text{px}$$
3. **Available Height**:
   $$H_{\text{avail}} = \text{safe\_bottom} - y_{\text{top}} \approx 632\text{px} \text{ to } 646\text{px}$$
4. **Header & Section Overheads**:
   $$H_{\text{headers}} = N_{\text{sections}} \times (24\text{px} + 3\text{px}) + (N_{\text{sections}} - 1) \times 8\text{px} = 3 \times 27 + 16 = 97\text{px}$$
   $$H_{\text{gaps}} = \sum (\text{rows}_i - 1) \times 4.5\text{px} = (0 + 1 + 3) \times 4.5 = 18\text{px}$$
5. **Pure Card Height & Proportional Row Height**:
   $$H_{\text{pure}} = H_{\text{avail}} - H_{\text{headers}} - H_{\text{gaps}} = 632\text{px} - 115\text{px} = 517\text{px}$$
   $$\text{target\_row\_h} = \frac{H_{\text{pure}}}{\text{total\_rows}} = \frac{517\text{px}}{7} = 73.8\text{px}$$
6. **Result**:
   - Section 1 (FOC, 1 row): $1 \times 73.8\text{px} = 73.8\text{px}$
   - Section 2 (Extras, 2 rows): $2 \times 73.8\text{px} + 4.5\text{px} = 152.1\text{px}$
   - Section 3 (Addons, 4 rows): $4 \times 73.8\text{px} + 3 \times 4.5\text{px} = 308.7\text{px}$
   - Section 3 ends at: $y = 749.3 + 308.7 = 1058.0\text{px}$ (exact boundary).
   - Footer remains at $1072\text{px}$.
   - **`scale(1.0)`**: Zero scaling, zero clipping, zero footer shift.

---

## 4. Multi-Phase Implementation Plan & Recommended Models

### Phase 1: Multi-Line Title Wrap & Dynamic Typography
- **Recommended AI Model**: `Gemini 3.8 Flash` (fast styling, regex rules, CSS tokens).
- **Files to Modify**:
  - [backend/app/rendering/benefit_grid_renderer.py:388-408](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/rendering/benefit_grid_renderer.py#L388-L408)
  - [frontend/src/components/template-canvas/shared.tsx:1227-1279](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/template-canvas/shared.tsx#L1227-L1279)
- **Tasks**:
  1. Replace `< 64.0` clamp with a minimum clamp threshold of `< 38.0` (only single-line if card height is under 38px).
  2. For `target_row_h >= 38.0`, allow `-webkit-line-clamp: 2` (or 3 for `textWrap="multi"`).
  3. Dynamic Title Font Size:
     - Label length > 28 chars: reduce font size to `8.5px` (line-height 1.15, taking ~20px for 2 lines).
     - Label length 18–28 chars: font size `9.0px`.
     - Label length <= 18 chars: font size `9.5px`–`10.0px`.
  4. Ensure title margin is set to `2px` so 2-line titles never push the icon or description out of the card.

---

### Phase 2: Backend Dynamic Proportional Row Height & Zero-Scale Unification
- **Recommended AI Model**: `Gemini 3.1 Pro` (deep backend layout and rendering engine refactoring).
- **Files to Modify**:
  - [backend/app/rendering/benefit_grid_renderer.py:620-705](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/rendering/benefit_grid_renderer.py#L620-L705)
  - [backend/app/rendering/template_renderer.py:840-860](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/rendering/template_renderer.py#L840-L860)
- **Tasks**:
  1. Unify row height calculation across both v3 and v4 templates:
     - Compute `raw_row_h = pure_cards_h / float(total_rows)`.
     - Bound `target_row_h = min(74.0, max(46.0, raw_row_h))` (or `uniformHeight` if explicitly configured).
  2. Eliminate the hardcoded `addon_row_height = max(84.0, ...)` that blew up v3 content height to 1205px.
  3. Set `e["h"] = rows * target_row_h + max(0, rows - 1) * card_gap` on all three grids (`current_benefits`, `extras_grid`, `available_addons_grid`).
  4. Pass `target_row_h` as the card row height style so cards and rows in equal-height mode match the container.
  5. Prevent artificial `footer_shift` when `bottom2 <= safe_bottom`.

---

### Phase 3: Frontend Canvas Container Height & Preview Parity
- **Recommended AI Model**: `Gemini 3.1 Pro` (TypeScript React canvas layout and review phase synchronization).
- **Files to Modify**:
  - [frontend/src/components/template-canvas/shared.tsx:1860-2030](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/template-canvas/shared.tsx#L1860-L2030)
  - [frontend/src/components/session-workspace/review-phase.tsx:670-710](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/session-workspace/review-phase.tsx#L670-L710)
- **Tasks**:
  1. In `balanceBenefitGridElements`, update `h2` calculation to use proportional `targetRowH` so the container height matches the grid cards.
  2. Ensure `effectiveCardRowH` inside the equal-height grid respects `targetRowH` without overflowing the outer article or section.
  3. Verify that the Review Phase canvas preview renders identical card dimensions to the backend PDF engine.

---

### Phase 4: Dynamic 4-Column Auto-Balance for High Addon Density
- **Recommended AI Model**: `Gemini 3.1 Pro` (adaptive column packing algorithm).
- **Files to Modify**:
  - [backend/app/rendering/benefit_grid_renderer.py:610-625](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/rendering/benefit_grid_renderer.py#L610-L625)
  - [frontend/src/components/template-canvas/shared.tsx:1855-1865](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/template-canvas/shared.tsx#L1855-L1865)
- **Tasks**:
  1. In Section 3 (`available_addons`), when `n2 >= 9` (e.g. 11 items):
     - Support adaptive 4-column packing: 11 cards pack into 3 rows (4 + 4 + 3) instead of 4 rows.
     - Saves ~75px of vertical space, completely eliminating the 4th row overflow risk.
  2. If the user retains 3 columns, the dynamic compression from Phase 2 safely compresses 4 rows to fit within the `safe_bottom` boundary.

---

### Phase 5: Verification & Pre-Deploy Gate
- **Recommended AI Model**: `Gemini 3.1 Pro` (hermetic test suite execution and gatekeeper).
- **Tasks**:
  1. Run backend tests: `python -m pytest -q tests/test_template_renderer.py tests/test_dynamic_grid_renderer.py`.
  2. Run frontend type check: `npx tsc --noEmit`.
  3. Run frontend production build: `npm run build`.
  4. Verify rendered output HTML for draft `252f65a5-7d01-412c-b96a-e03e63fa6bcc`:
     - Scale factor must equal `1.0` (no shrink).
     - Full titles rendered with `-webkit-line-clamp: 2`.
     - Zero clipping on Row 4 cards.
  5. Run pre-deploy verification gate: `.\commands\verify-deploy-gate.ps1`.
