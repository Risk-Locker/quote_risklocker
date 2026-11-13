---
name: web-design-guidelines
description: Review UI code for WCAG 2.2 AA accessibility, contrast, keyboard navigation, responsive layout at 80%-120% zoom, and Web Interface Guidelines compliance; optionally fetch latest Vercel checklist when online.
---

# Web Design, Accessibility (WCAG 2.2) & Interface Audit

Use this skill when reviewing React/Next.js screens or components for accessibility, responsive layout resilience, copy clarity, and interaction craft.

## 1. Audit Execution Sequence

1. **Optional Live Upstream Check (`search_web` when online):** Check `https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md` for updates if verifying external web-interface conventions (`Rule 05`).
2. **Inspect Target Components & Styles:** Check semantics, focus management, contrast, layout flexibility, and form feedback.
3. **Report Findings Precisely (`file:line`):** Cite exact `path:line`, violated rule, impact at desktop/zoom, and concrete fix.

## 2. Non-Negotiable UI & WCAG 2.2 AA Checklist

### Semantics & Keyboard Mechanics
- **Native Elements:** Use `<button type="button">` for actions, `<a href>` for navigation — never clickable `<div onClick>` without `role`, `tabIndex`, and `Enter`/`Space` handlers.
- **Accessible Labels:** Every icon-only button has `aria-label` or visually hidden text; every form input connects via `<label htmlFor>` (placeholder text is NEVER a label replacement); images carry meaningful `alt` (or `alt=""` if purely decorative).
- **Focus & Escape Flows:** Visible `:focus-visible` outline (`>= 2px`), logical DOM `Tab` order, Radix `Dialog`/drawers trap focus cleanly inside and return focus to trigger on `Escape`/close.

### Visual Hierarchy, Contrast & Motion Safety
- **Contrast Floors:** Body/table text `>= 4.5:1` (`#1b1717` on `#ffffff`/`#f5f5f7` passes cleanly), large headings & borders/UI states `>= 3.0:1`; never rely solely on color red/green without icon or text label (`✔` / `Check Needed`).
- **Tabular Numerals (`tabular-nums`):** Apply `tabular-nums` on all currency columns (`MYR`), road tax, percentages, dates, and NRIC tables so columns align vertically.
- **Reduced Motion:** Honor `@media (prefers-reduced-motion: reduce)` (`apple-design`); ban infinite blinking/bouncing loops on work screens.

### Responsive & Zoom Resilience (`1024px–1920px`, `80%–120%` Zoom)
- Avoid hardcoded fixed pixel widths inside multi-column grids (`minmax(0, 1fr)` / flexible grids instead of overflowing fixed spans).
- Long strings (`insurer names`, `remarks`, `URLs`) use `min-w-0` + `truncate` or controlled line wrapping so adjacent action buttons are never pushed off-screen.
- Verify sticky table headers stay aligned during vertical scroll and `0` horizontal body overflow occurs (`scrollWidth <= innerWidth`).

## 3. High-Impact Risklocker A11y Checks
- **Comparison Grid (`tabular-nums`):** Ensure every currency cell, percentage, sum insured, and action column preserves crisp alignment across `80%`–`120%` zoom without wrapping prices mid-number (`whitespace-nowrap`).
- **Form Errors & Inline Hints:** Connect error messages via `aria-describedby` and `aria-invalid="true"` cleanly rather than ephemeral toast-only validation.
- **No Color-Only Status:** Always pair status color (`Check Needed`, `Confirmed`, `Expired`) with an explicit badge text label or crisp icon.
