# Radix & shadcn Enterprise Recipes (Risklocker `--rl-*`)

## 1. Safe Destructive Confirmation Pattern (No `window.confirm`)

```tsx
// Always wire async guard + disabled loading label + Esc recovery
<ConfirmDialog
  open={pendingTarget !== null}
  onOpenChange={(open) => { if (!open && !isDeleting) setPendingTarget(null); }}
  title="Delete comparison column"
  description={`Remove ${pendingTarget?.insurerLabel ?? "this quote"} from the comparison table?`}
  confirmLabel={isDeleting ? "Removing..." : "Remove column"}
  confirmVariant="destructive"
  disabled={isDeleting}
  onConfirm={handleConfirmedDelete}
/>
```

## 2. Table / Row Dropdown Actions Without Event Bubbling Bugs

```tsx
// Stop propagation on row-click tables & keep accessible label for icon-only trigger
<DropdownMenu>
  <DropdownMenuTrigger asChild>
    <button
      type="button"
      aria-label={`Actions for ${row.plateNumber}`}
      onClick={(e) => e.stopPropagation()}
      className="rounded-[6px] p-1.5 text-[#1b1717] hover:bg-[#f5f5f7] focus-visible:outline-2 focus-visible:outline-[#1b1717]"
    >
      <DotsThreeVertical size={18} />
    </button>
  </DropdownMenuTrigger>
  <DropdownMenuPortal>
    <DropdownMenuContent align="end" className="z-50 min-w-[180px] rounded-[8px] border bg-white p-1 shadow-md">
      {/* items */}
    </DropdownMenuContent>
  </DropdownMenuPortal>
</DropdownMenu>
```

## 3. Component Mapping Checklist
- [ ] Dialog close restores focus to trigger button automatically (Radix default preserved — no manual `.blur()` hacks).
- [ ] All form controls carry explicit `<label htmlFor>` or `aria-label` + visible inline validation text.
- [ ] Async submit buttons guard against double-click re-submission while `isPending === true`.

