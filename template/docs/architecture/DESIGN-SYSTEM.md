# Design System & UI Guidelines

## 1. Visual Principles & Aesthetics

- **Theme & Mode**: Clean, high-contrast, modern UI (Dark mode preferred/supported).
- **Typography**: Primary font family (e.g. `Inter`, `Geist`, `Roboto`), monospace for code.
- **Spacing & Layout**: Standard 4px/8px grid system (`gap-2`, `gap-4`, `p-6`).

## 2. Color Palette & Tokens

| Token | CSS Variable / Class | Value / Hex | Usage |
| :--- | :--- | :--- | :--- |
| `Background` | `bg-background` | `#0f172a` / `#ffffff` | Primary app canvas background |
| `Surface / Card` | `bg-card` | `#1e293b` / `#f8fafc` | Card containers and elevated panels |
| `Primary` | `bg-primary` | `#3b82f6` | Key action buttons, active tabs |
| `Border` | `border-border` | `#334155` / `#e2e8f0` | Subtle structural dividers |
| `Muted Text` | `text-muted` | `#94a3b8` / `#64748b` | Secondary labels, timestamps, hints |

## 3. Component Standards

- **Buttons**: Clear hover transitions, focus ring, loading states with spinners.
- **Form Inputs**: Explicit labels, placeholder text, inline validation error messages.
- **Modals & Dialogs**: Accessible focus traps, backdrop blur, `Esc` key dismissal.
- **Tables**: Sticky headers, responsive scrolling, clear sort indicators.
