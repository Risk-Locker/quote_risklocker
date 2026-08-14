# Risklocker Design System

## Direction

Quiet, confident internal dashboard for repeated daily use. Apple-inspired calm — smooth transitions, stable layout, clear hierarchy. Red, black, and white palette with subtle gray backgrounds. No blue, no pill shapes, no bouncing.

## Foundations

- Fonts: Manrope (headings), Inter (body), JetBrains Mono (data/IDs). Loaded via `next/font/google` in `frontend/src/app/layout.tsx`.
- Base text is 16 px; supporting text is 14 px; labels are 13 px; table headers are 12 px uppercase.
- All design tokens live in `frontend/src/app/globals.css` as CSS custom properties (`--rl-*`) wired into `tailwind.config.ts` as `rl.*` colors.
- Use the component library at `frontend/src/components/ui/` (Button, Input, Textarea, Select, Card, Badge, Spinner, Dialog, Tabs, Tooltip, Toast).
- Cards and panels use an 8 px radius. Chips/badges use 6 px. Do not use pill (full-round) shapes anywhere.
- Page backgrounds use Apple gray `#f5f5f7`; surfaces are white with a soft card shadow.
- Color palette is red, black, white and their tonal gradients. No blue.

## Design Tokens

| Token | Value |
|---|---|
| `--rl-bg` | `#f5f5f7` (page background) |
| `--rl-surface` | `#ffffff` (cards, panels) |
| `--rl-text` | `#454545` (body) |
| `--rl-text-strong` | `#1b1717` (headings, emphasis) |
| `--rl-text-muted` | `#6e6e73` (secondary, labels) |
| `--rl-border` | `#e5e5ea` |
| `--rl-black` | `#1b1717` |
| `--rl-red` | `#ed1c24` |
| `--rl-red-hover` | `#c4171e` |
| `--rl-red-light` | `rgba(237, 28, 36, 0.08)` |
| `--rl-success` | `#2f7d32` |
| `--rl-success-light` | `rgba(47, 125, 50, 0.08)` |
| `--rl-warning` | `#8a5a00` |
| `--rl-warning-light` | `rgba(138, 90, 0, 0.08)` |
| `--rl-radius` | `8px` |
| `--rl-radius-sm` | `6px` |
| `--rl-shadow` | `0 1px 3px rgba(0,0,0,0.04), 0 8px 24px rgba(0,0,0,0.04)` |
| `--rl-shadow-lift` | `0 4px 12px rgba(0,0,0,0.08), 0 12px 32px rgba(0,0,0,0.06)` |
| `--rl-duration-instant` | `200ms` |
| `--rl-duration-fast` | `300ms` |
| `--rl-duration-normal` | `500ms` |

## Interaction and Accessibility

- Use Phosphor icons (`@phosphor-icons/react`) for all UI icons. No Lucide, no Shadcn. Icons use `weight="bold"` for actions, `weight="regular"` for decorations, `weight="fill"` for active states.
- Radix primitives provide accessible dialogs, tooltips, and toasts with custom styling.
- Framer Motion provides smooth layout transitions, toast animations, and micro-interactions.
- Every interactive control must have default, hover, focus-visible, active, disabled, and loading behavior. Buttons scale to 0.98 on active. Cards lift slightly on hover.
- Keyboard navigation and visible focus are required. Target WCAG 2.2 AA.
- Focus ring is red-tinted (`rgba(237, 28, 36, 0.35)`) with a 2 px offset.
- Error messages use red-light background boxes or toast notifications.
- Success feedback uses toast notifications (top-right, auto-dismiss 4 s).

## Component Library

All components live in `frontend/src/components/ui/`.

- **Button** — `variant="primary"|"secondary"|"ghost"|"danger"`, `loading`, `icon`, `size="sm"|"md"`. Primary is black, secondary is white with border, danger is red.
- **Input / Textarea / Select** — consistent 40 px min-height, 14 px text, 6 px radius, border hover, focus border to black.
- **Card** — white surface, border, shadow, optional hover lift. Use for all panel-like containers.
- **Badge** — inline chip with variants `default|success|warning|danger|info`, 6 px radius.
- **StatusBadge** — pre-styled badge for draft/record statuses (Ready, Check Needed, Cannot Read, etc.).
- **Toast** — `useToast()` hook returning `toast(message, variant?)`. Variants: `success|error|warning|info`. Slides in from top-right.
- **Dialog** — confirmation modal with overlay, title, description, action buttons.
- **Tooltip** — hover tooltip using Radix. Dark background, 6 px radius.
- **Tabs** — Radix-based tab bar with a 6 px rectangular active state.
- **Spinner** — animated spinner for loading states.

## Workflow Screens

- Preserve Upload -> Check Values -> Generate PDF.
- **Shell:** Fixed 56 px glass header with Risklocker horizontal logo, user email, sign-out button. Fixed 220 px sidebar with distinct Phosphor icons per route, active state in a 6 px black rectangle. Main area scrolls independently.
- **Login:** Centered card on gray background, logo above form, minimal fields.
- **Review:** Sticky toolbar, two-column layout (PDF iframe left, extracted text + fields right). DraftFieldTable component reused.
- **Template Builder:** Compact command bar, hierarchy-only Layers panel on the left, fit-to-view fixed-page canvas in the center, contextual Properties inspector on the right, and zoom/page/guides controls in the bottom status bar. Renderable rectangles and semantic layer groups are separate node types.
- **Builder navigation:** Templates, Benefits, and Asset Library only. Benefits is company-first. Company-detection aliases live under Settings → Extraction.
- **Builder / Settings sub-navigation:** Compact rectangular links with a border or surface active state; never capsule tabs.

## Loading and Progress

- Loading state belongs to the operation or region that is waiting. Use skeletons for initial content, a button busy state for mutations, and named phase/progress/elapsed status for upload, extraction, preview, and generation.
- Do not fabricate delay, show a global request capsule, or flash progress for background polling. After two seconds, long operations show their current phase, elapsed time, and a recovery action when stalled.

## Staff Language

Use `Review / Edit`, `Please check this value.`, `Enhanced reading`, and `PDF Expired`. Use the approved statuses from [BUSINESS-RULES.md](BUSINESS-RULES.md). Do not reveal technical implementation terms to Staff.

## Component Definition Standards

- Use semantic tokens (`--rl-*`), never raw hex values, in component guidance and implementation.
- Every component defines states for default, hover, focus-visible, active, disabled, loading, and error.
- Component behavior specifies responsive and edge-case handling; interactive components document keyboard, pointer, and touch behavior.
- Accessibility acceptance criteria must be testable in implementation (WCAG 2.2 AA minimum).
- Do not introduce one-off spacing or typography exceptions; do not use ambiguous labels or non-descriptive actions.
- Do not ship a component without explicit state rules; prefer system consistency over local visual exceptions.
