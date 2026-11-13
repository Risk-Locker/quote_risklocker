---
name: enterprise-product-ui
description: Enforce quiet, restrained, token-locked Enterprise Fintech UI (DESIGN-SYSTEM.md) using the Mobbin + shadcn MCP + --rl-* pipeline across dashboards, comparisons, ledgers, drawers, and dialogs while rejecting marketing hype.
---

# Enterprise Product UI Skill (`Mobbin + shadcn MCP + --rl-*`)

This skill governs **high-density financial and insurance operations workspaces** (`comparison`, `insights`, `sessions/[id]`, `builder`, `upload`). Never apply consumer landing-page/portfolio hype (`design-taste-frontend`, parked in `.agents/skills-vault/`) to internal fintech productivity screens.

## 1. Mandatory Design Pre-Flight (`1-Line Design Read`)

Before modifying or designing any React UI, emit:
> `"Design Read: <workflow view> for <internal ops staff / admin>, high information density, locked to Risklocker --rl-* Apple-calm palette."`

## 2. Production Component Pipeline (Real Patterns -> Local Primitives -> `--rl-*`)

1. **Benchmark Structural Flow (`shadcn` MCP + Browser Research / Optional Mobbin):** Inspect accessible component primitives via `risklocker-ui-shadcn` MCP and compose existing `frontend/src/components/ui/` wrappers (`Dialog`, `ConfirmDialog`, `Tabs`, `Select`, `Tooltip`, `Badge`, `Toast`). Use `mobbin_mobbin` (`redesign-screen`) when a paid Mobbin Pro plan is connected, or `browser` / `chrome-devtools-mcp` / user-supplied screenshots otherwise — NEVER import foreign brand colors.
2. **Fetch Accessible Anatomy (`shadcn` MCP + `ui/`):** Inspect accessible component primitives via `risklocker-ui-shadcn` MCP and compose existing `frontend/src/components/ui/` wrappers (`Dialog`, `ConfirmDialog`, `Tabs`, `Select`, `Tooltip`, `Badge`, `Toast`).
3. **Lock Strictly to `--rl-*` Tokens (`docs/architecture/DESIGN-SYSTEM.md`):**
   - Surfaces & Ink: `#f5f5f7` (`--rl-bg`), `#ffffff` (`--rl-surface`), `#1b1717` (`--rl-black`), `#ed1c24` (`--rl-red`), semantic emerald/amber/slate status tints.
   - Radii: `8px` cards/panels/modals, `6px` buttons/inputs/chips (**zero pill badges** for action buttons or dense grid chips).
4. **The Halvi / Marketing Filter:**
   - Reject parallax heroes, bouncy/gamified confetti, heavy glassmorphic glow cards, scroll-jacking, and gratuitous decorative KPI widgets on operational workspaces.
   - If subtle drawer/sheet motion helps spatial continuity (`apple-design`), keep springs critically damped (`damping: 1.0`, zero bounce) and honor `prefers-reduced-motion`.

## 3. Quick Token & Layout Guardrails (`05-principal-designer` / `07-frontend-ux-lead`)

| Screen / Element | Enterprise Fintech Rule | Avoid |
| :--- | :--- | :--- |
| **Action Buttons & Grid Chips** | `6px` radius, crisp borders, `tabular-nums` for `MYR` & `%` | Pill buttons (`rounded-full`) inside operational grids |
| **Loading / Empty / Error States** | Inline skeleton, calm factual empty message, typed retry CTA | Spinning decorative overlays or `window.alert()` popups |
| **Confirmations & Destructive Actions** | Controlled Radix `ConfirmDialog` (`ui/confirm-dialog.tsx`) | Native `window.confirm()` or silent instant deletes |
| **Responsive & Browser Zoom** | Test `1024px`, `1280px`, `1920px` + `80%/100%/120%` zoom (`0` X-scroll) | Fixed `px` multi-column widths that clip long insurer names |

## 4. Reference Pipeline & Component Slice Discipline

See `references/mobbin-shadcn-risklocker-pipeline.md` for toolbar/drawer placement anatomy, full 9-state & zoom checklist (`1024px–1920px` at `80%/100%/120%`), and `<600`-line slice limits.
