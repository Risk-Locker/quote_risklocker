---
trigger: model_decision
description: Risklocker --rl-* fintech design tokens, shadcn MCP + browser UI workflow, Radix accessibility, zero client math, Design 2 PDF parity, and live browser QA across desktop and zoom levels.
---
# Rule 03: Enterprise UI Simplicity, Component Pipeline & Visual Parity

1. **Visual Authority:** Follow [`docs/architecture/DESIGN-SYSTEM.md`](../../docs/architecture/DESIGN-SYSTEM.md) (`--rl-*` CSS tokens: `#f5f5f7` page gray, `#ffffff` cards, `#1b1717` ink/primary, `#ed1c24` Risklocker red, `8px` card radius, `6px` chip radius). Zero random blue hues, zero pill badges, zero arbitrary inline hex literals.
2. **Design & Component Pipeline (`shadcn` MCP + UI Audit -> `--rl-*`):**
   - For new screens or layout fixes, verify accessible component primitives/props via **`shadcn` MCP** (`risklocker-ui` plugin), compose existing `frontend/src/components/ui/` wrappers, and adapt strictly into Risklocker `--rl-*` tokens — never guess markup from memory. Use Mobbin MCP when a paid Mobbin Pro plan is active, or `browser` / `chrome-devtools-mcp` / web references otherwise.
3. **The Halvi / Landing-Page Filter:** Never apply consumer portfolio/landing-page gimmicks (flashy GSAP scroll hijacking, gradient hero banners, gratuitous decorative widgets) onto financial comparison matrices, renewal ledgers, or staff review screens.
4. **Interactive & State Coverage Discipline:**
   - Every control handles `default`, `hover`, `focus-visible` (2px offset ring), `active`, `disabled`, `loading`, `empty`, `error`, and `overflow`.
   - Zero `window.alert()`, `window.confirm()`, or `window.prompt()` calls — use accessible Radix `Dialog` and `useToast()`.
   - Preserve exact 1:1 visual parity between live canvas preview (`design2-canvas.tsx`) and Playwright Chromium A4 PDFs (`template_renderer_design2.py`).
5. **Mandatory Browser Self-Audit:** Verify changed views in `chrome-devtools-mcp` / Playwright across `1024px`, `1280px`, `1920px` and `80%`/`100%`/`120%` zoom with zero horizontal scrollbars and zero React/network console errors.
