# Milestone 6: Design 2 Quotation Typography & Exact Font Pairing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` and `systematic-debugging` to execute this plan cleanly. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align Design 2 typography across both backend Chromium PDF rendering (`template_renderer_design2.py`, `benefit_schedule_renderer.py`) and frontend live canvas (`design2-canvas.tsx`) with the designer's exact font hierarchy:
- Primary English Body: `Helvetica, Arial, sans-serif`
- Headings & Bold Callouts: `Helvetica-Bold, Helvetica, Arial, sans-serif` (weight 700)
- Light/Secondary Text: `Helvetica-Light, Helvetica, Arial, sans-serif` (weight 300)
- Notes & Small Annotations: `Calibri, Calibri-Italic, Arial, sans-serif` (italic)
- Chinese Body & Bilingual Text: `'Source Han Sans CN', 'SourceHanSansCN-Normal', 'PingFang SC', 'Microsoft YaHei', sans-serif`
- Chinese Headings / Emphasis: `'Source Han Sans SC', 'SourceHanSansSC-Medium', 'PingFang SC', sans-serif`
- Bold Chinese Legacy / Notes: `'SourceHanSansOLD-Bold', SimSun, STSong, serif`

**Architecture:**
1. Define a centralized CSS font-family stack in `@font-face` and CSS variables:
   - `--rl-font-heading`: `'Helvetica Neue', Helvetica, Arial, 'Source Han Sans SC', sans-serif`
   - `--rl-font-body`: `'Helvetica Neue', Helvetica, Arial, 'Source Han Sans CN', sans-serif`
   - `--rl-font-notes`: `'Calibri', Arial, sans-serif`
   - `--rl-font-chinese`: `'Source Han Sans SC', 'Source Han Sans CN', 'PingFang SC', 'Microsoft YaHei', sans-serif`
2. Update `backend/app/rendering/template_renderer_design2.py` and `benefit_schedule_renderer.py`:
   - Replace legacy `'Be Vietnam Pro'` with the canonical Helvetica + Source Han Sans + Calibri stack.
   - Ensure `@media print` loads webfonts or standard local font fallbacks for Chromium headless Playwright rendering.
3. Update `frontend/src/components/template-canvas/design2-canvas.tsx`:
   - Update canvas font family declarations to maintain 1:1 mathematical and typographic parity with Playwright PDF output.

**Tech Stack:** CSS, Python, HTML5, React 19, TypeScript.

---

### Task 1: Update Backend PDF Template Renderers

**Files:**
- Modify: `backend/app/rendering/template_renderer_design2.py:315-330`
- Modify: `backend/app/rendering/benefit_schedule_renderer.py:590-670`

- [x] **Step 1: Write unit test asserting font stack in rendered HTML**
- [x] **Step 2: Update CSS font-family rules in `template_renderer_design2.py`**
- [x] **Step 3: Update CSS font-family rules in `benefit_schedule_renderer.py`**
- [x] **Step 4: Verify test passes**

---

### Task 2: Update Frontend Design 2 Live Canvas

**Files:**
- Modify: `frontend/src/components/template-canvas/design2-canvas.tsx:380-400`
- Modify: `frontend/src/components/template-canvas/design2-canvas.tsx:765-780`

- [x] **Step 5: Update canvas typography styles**
- [x] **Step 6: Verify TypeScript compilation (`npx tsc --noEmit`)**
- [x] **Step 7: Commit Milestone 6 changes**

