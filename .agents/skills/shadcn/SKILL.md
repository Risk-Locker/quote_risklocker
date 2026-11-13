---
name: shadcn
description: Build and debug accessible Radix UI and Tailwind components mapped cleanly into Risklocker --rl-* design tokens, using existing ui/ primitives and the risklocker-ui-shadcn MCP server before creating custom widgets.
---

# Radix & shadcn Component Engineering Skill

Use this skill whenever adding, extending, or fixing UI primitives (Dialogs, Sheets/Drawers, Dropdowns, Select, Tabs, Popovers, Tooltips, Forms, Data Tables) inside `frontend/src/`.

## 1. Mandatory Lookup Sequence (Reuse Before Building)

1. **Inspect Repo Primitives First:** Read `frontend/src/components/ui/` (`badge.tsx`, `button.tsx`, `card.tsx`, `confirm-dialog.tsx`, `dialog.tsx`, `input.tsx`, `select.tsx`, `spinner.tsx`, `tabs.tsx`, `textarea.tsx`, `toast.tsx`, `tooltip.tsx`) — never build duplicate dialogs/spinners/buttons from raw divs.
2. **Query Official `risklocker-ui-shadcn` MCP (`risklocker-ui` plugin):** Look up accessible ARIA roles, keyboard focus trapping, portal props, and component structure directly from the live shadcn registry (`npx -y shadcn@latest mcp`) rather than guessing Radix markup from memory.
3. **Adapt Into `--rl-*` Tokens (`docs/architecture/DESIGN-SYSTEM.md`):**
   - Strip default cool grays, generic blues (`#3b82f6`), or excessive shadow blur.
   - Lock to `#f5f5f7` (`--rl-bg`), `#ffffff` (`--rl-surface`), `#1b1717` (`--rl-black`), `#ed1c24` (`--rl-red`), `8px` card radius, `6px` chip/input radius.
   - Preserve existing `@phosphor-icons/react` / `lucide-react` conventions matching the host module.

## 2. Non-Negotiable Radix & Interactive Guarantees

- **Zero Native Browser Dialogs:** Replace `window.alert()`, `window.confirm()`, and `window.prompt()` unconditionally with Radix `Dialog` / `ConfirmDialog` + `useToast()`.
- **Slot & `asChild` Discipline:** Never nest interactive `<button>` inside `<button>` or `<a>`. Use Radix `asChild` + `forwardRef` cleanly so keyboard activation and `focus-visible` rings remain intact.
- **Controlled State Ownership:** Keep `open` / `onOpenChange` and `value` / `onValueChange` explicitly controlled for forms and confirmation modals, resetting validation state cleanly on close.
- **Portals & Overflow Clips:** Render `SelectContent`, `DropdownMenuContent`, `PopoverContent`, and `TooltipContent` inside `<Portal>` with consistent semantic `z-index` tokens so sticky table headers never clip dropdowns.
- **Keyboard & Zoom Survival:** Verify `Tab`, `Shift+Tab`, `Escape`, `Enter`, and Arrow navigation plus zero text collision at `1024px`–`1920px` and `80%`–`120%` browser zoom.

## 3. Risklocker UI Component Mapping Quick Table

| Need | Reuse Repo Primitive / Pattern | Key Accessible Requirement |
| :--- | :--- | :--- |
| Destructive Confirm | `frontend/src/components/ui/confirm-dialog.tsx` | Controlled `open`, disabled Confirm while loading |
| Tabular Navigation | `frontend/src/components/ui/tabs.tsx` | Arrow navigation + unambiguous active border/ink |
| Select / Filter Dropdown | `frontend/src/components/ui/select.tsx` | `<SelectPortal>` prevents clipping inside tables |
| Async Mutation Toast | `frontend/src/components/ui/toast.tsx` | Clear error text + `aria-live="polite"` |

## 4. Worked Patterns

Load `references/radix-and-registry-recipes.md` for controlled confirmation modal, async loading submit button, and accessible table action menu patterns.
