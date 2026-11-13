# Enterprise UI/UX & Design Consistency Audit: Live Workspace & Sitewide Simplification

> **Textbook Purpose**: Great enterprise UI reduces human error under pressure. When an insurance advisor inspects a live quotation (such as session `4e7df9b1-395d-4c40-af05-bd1eb14b20c9` or Design 2 previews), the interface must never lie about numbers, scramble NRICs, clip benefit text, pop up ugly 1998 browser `alert()` boxes, or export a screenshot instead of a real PDF.

---

## 1. Live Quotation Workspace & Visual Bugs (`/sessions/[id]`)

### Issue UX-01 [P0]: NRIC & Arbitrary Text Fields Scrambled by Date Formatter!
- **Where it happens**: [`review-phase.tsx:192-208`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/session-workspace/review-phase.tsx#L192-L208).
- **Exact code flaw**:
  ```ts
  function displayValue(kind: FieldKind, value: string | null | undefined): string {
    if (kind === "money" || kind === "total") return formatMoney(value);
    if (kind === "date") return formatDate(value);
    if (kind === "percent") return value ? `${String(value).replace(/%/g, "")}%` : "";
    if (kind === "vehicle_type") return String(value || "Car");
    return formatCoverPeriod(String(value ?? "")); // <-- BUG: runs on ALL "text" fields!
  }
  ```
  Look at what `formatCoverPeriod` does on `:195-197`: `.replace(/(\d{4})-(\d{2})-(\d{2})/g, "$3-$2-$1")`. Any text field (`ic_or_brn`, `quotation_no`, `chassis_no`, remarks) containing `YYYY-MM-DD` digit runs — including 12-digit NRIC patterns or hyphenated dates embedded in prose/BRN IDs (e.g. `2024-05-12` or `1234-56-7890` if formatted with 4-2-2) — gets reversed silently when displayed!
- **Cure**: Restrict `formatCoverPeriod` strictly to explicit `"cover_period"` fields (`FieldKind === "cover_period"`). Plain `"text"`, `"nric"`, `"plate"`, and `"reference"` fields must return raw trimmed strings untouched.

### Issue UX-02 [P1]: Review "Download PDF" Exports a Giant Screenshot (`jsPDF` + `toPng`), Diverging From Preview/Backend
- **Where it happens**: [`review-phase.tsx:2121-2189`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/session-workspace/review-phase.tsx#L2121-L2189).
- **Why this fails**:
  1. Instead of using the real Playwright Chromium vector PDF from `/sessions/{id}/versions`, Review calls `toPng(live, { pixelRatio: 4 })` and drops a bitmap picture into `jsPDF`.
  2. Users cannot select/copy quotation reference numbers, plate numbers, or bank account numbers from the PDF! File size bloats from ~200 KB to several megabytes.
  3. Notice line `:2184-2188`: the frontend triggers server version archiving *in the background* AFTER already letting the user download the local screenshot (`ExecuteDownload -> Archive`), meaning the user holds an un-versioned raster PDF if the background archive fails (`POST /versions` throws 409 on blockers!).
- **Cure**: Unify Download PDF in both `ReviewPhase` and `PreviewPhase` onto one backend Playwright PDF action with an atomic "Save -> Preview/Render -> Download Versioned PDF" stepper.

### Issue UX-03 [P1]: Non-Design-2 Templates Preview a Fake Static `<svg>`!
- **Where it happens**: [`preview-phase.tsx:607-743`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/session-workspace/preview-phase.tsx#L607-L743).
- **What users experience**: Whenever a template is not Design 2, Preview ignores the custom layout built in Template Builder (`block_tree` / `canvas.elements`) and renders a hardcoded generic red-and-grey `<svg>` box with fixed `y={304 + idx * 56}` benefit cards (which silently clip off the bottom of an `1123px` page once >13 benefits exist!).
- **Cure**: Render non-Design-2 previews in an isolated `<iframe>` sourced directly from the server `RenderSnapshot` HTML endpoint (`render_snapshot_preview_html`), giving staff 100% WYSIWYG accuracy.

### Issue UX-04 [P1]: Hardcoded Customer, Vehicle & Bank PII Displayed on Missing Fields
- **Where it happens**:
  - [`template_renderer_design2.py:114-130, 152-157, 446-448`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/rendering/template_renderer_design2.py#L114-L130)
  - [`design2-canvas.tsx:267-282, 317-321, 585-587`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/template-canvas/design2-canvas.tsx#L267-L282)
  - [`template_renderer.py:782-787`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/rendering/template_renderer.py#L782-L787)
  - [`builder/templates/[id]/builder/page.tsx:95-117`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/app/builder/templates/[id]/builder/page.tsx#L95-L117)
- **How it hurts real customers**: If `customer_name`, `vehicle_no`, or `quotation_reference` fails to extract cleanly on a blank/partial session, the renderer silently falls back to real-looking customer PII (`"CHENG TECK KIOING"`, `"ANY 368"`, `"RL260000314"`, `"Tesla Model 3 Performance"`, `"RM 5,447.30"`), or defaults `free_items` to `"Drive-Less Save-More"` when no benefits exist! Even worse, bank details (`RISKLOCKER SDN.BHD.`, `Hong Leong Bank`, `12300318500`) are hardcoded directly into Python & TSX strings instead of an editable DB `agency_profiles` configuration.
- **Cure**: Replace all PII defaults with `""` / `"—"` (flagged clearly as missing in draft workspace) and seed anonymized sample fixtures solely in the Builder simulator.

### Issue UX-05 [P2]: Squished 3-Column Benefits Grid & Unbalanced Visual Hierarchy
- **Where it happens**: [`benefits-manager-panel.tsx:231-237`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/session-workspace/review-components/benefits-manager-panel.tsx#L231-L237).
- **Exact defect**: When `purchasedAddonCards.length > 0`, the grid flips from `lg:grid-cols-2` to `lg:grid-cols-3` inside an already split-pane workspace (`ReviewPhase` left column + right live preview!). At 1280–1440px laptop widths, three vertical columns leave ~210px per card column, squishing titles, badges, coverage inputs, and delete buttons into tight multi-line wrapping with nested scrollbars (`max-h-[380px] overflow-y-auto`).
- **Cure**: Use a clean **single-column stacked accordion** or crisp **tabular list with tabs** (`Included (FOC)` | `Purchased Extras` | `Optional Add-Ons (24 Matrix)`) inside the narrow Review pane so every control has generous breathing room (`>=40px` interactive targets).

### Issue UX-06 [P2]: Amateur Browser `window.confirm()`, `window.alert()`, `window.prompt()` & Hard Reloads
- **Where it happens**:
  - [`review-header.tsx:69-85`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/session-workspace/review-components/review-header.tsx#L69-L85): `window.confirm(...)`, `alert(...)`, and `window.location.reload()` (destroying unsaved UI scroll/state!).
  - [`benefit-templates/page.tsx:416`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/app/builder/templates/benefit-templates/page.tsx#L416): `window.prompt(...)` for naming custom presets.
- **Cure**: Replace 100% of native blocking browser dialogs with the existing design-system `<ConfirmDialog>`, `<Dialog>`, and `toast()` components, and replace `window.location.reload()` with clean React state revalidation (`await reload()`).

---

## 2. Sitewide Cognitive Load, Navigation & Design System Critique

### 2.1 Navigation Overload & Duplicate Entry Points
Look at [`app-shell.tsx`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/app-shell.tsx) and `frontend/src/app/`:
- The sidebar shows **restricted Admin/Builder links to `staff` users in a disabled/dimmed state** (`app-shell.tsx:232-233`: *"kept so staff can faintly see them in a disabled state"*). Seeing unclickable locked settings every day creates visual clutter and frustration — staff should only see Staff workflows!
- Duplicate/redundant routes (`/insights` redirecting to `/ledger` [`insights/page.tsx:14-16`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/app/insights/page.tsx#L14-L16); `/admin/*` redirecting to `/settings/*`; `/settings/extraction/*` redirecting to `/extraction/*`; 4 separate `/upload/*` subpages for 1 workflow) confuse mental models.

### 2.2 Total Payable Contradictions in Workspace UI
- [`policy-fields-card.tsx:960-985`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/session-workspace/review-components/policy-fields-card.tsx#L960-L985) displays `Net Premium + Road Tax + Runner Fee = Total Payable`, omitting **Purchased Optional Add-Ons (`extras`)** and **Agency Quotation Discount**, and showing stale extracted totals when add-ons are toggled until manual adjustment or Design 2 recalculation!
- Worse, `Check Needed` indicators confuse staff because `workspace_common.py:241-250` generates `scalar_check_needed` even for computed fields, while Preview & Generation allow proceeding without resolving them.

### 2.3 Enterprise Visual & Typography Remediation Standards

| Dimension | Current Problems | Target Enterprise Design Token Standard |
| :--- | :--- | :--- |
| **Typography Hierarchy** | Mix of `10px` badges, Chinese/English inline spans without baseline tokens, arbitrary inline pixels in `design2-canvas.tsx` | Clear scale (`12px` metadata minimum in app UI, `14px` inputs, `18px–24px` section headings), tabular numbers (`font-variant-numeric: tabular-nums`) on **all** RM amounts, NRICs, and plate metrics |
| **Status & Verification Clarity** | Ambiguous `Check Needed` lock badge + silent `"ready"` overrides | Strictly 3 explicit states with clear action CTA: **Verified (Green)**, **Needs Human Review (Amber + exact reason e.g. "Towing tier ambiguous")**, **Error/Blocker (Red — blocks final PDF)** |
| **PDF Preview & Workspace Split** | 3 nested scroll containers in Review + squished 3-col cards | 2 clean primary panels: Left `55%` Tabbed Review Form (`Policy & Vehicle` · `Pricing Breakdown` · `Benefits (24)`), Right `45%` Sticky Live Scaled A4 Preview with 1-click "Zoom / Multi-page Sheet 2" toggle |
| **Loading & Async States** | Blank spinner on `/comparison` while invisibly mutating DB via `POST /tenures` | Instant clean empty-state Intake launcher on `/comparison` ("Start New Comparison" CTA button, NEVER auto-POST on mount!) |

