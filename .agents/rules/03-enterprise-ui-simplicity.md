---
trigger: model_decision
description: Risklocker --rl-* fintech design tokens, shadcn/ui primitives, zero client math, and Design 2 PDF parity when editing frontend UI.
---
# Rule 03: Enterprise UI Simplicity & Visual Parity

1. **Visual Authority (`docs/architecture/DESIGN-SYSTEM.md`):**
   - Use `--rl-*` CSS tokens (`#f5f5f7` page gray, `#ffffff` cards, `#1b1717` primary ink, `#ed1c24` Risklocker red, `8px` card radius, `6px` chip radius). Reject generic Tailwind blue (`#3b82f6`), pill chips, and native `window.alert`/`confirm`/`prompt`.
2. **Component Reuse First:**
   - Check `frontend/src/components/ui/` and the `risklocker-ui-shadcn` MCP tools before creating any new dialog, popover, select, badge, tabs, or toast primitive.
3. **Design 2 WYSIWYG Parity:**
   - Keep live React canvas (`frontend/src/components/template-canvas/`) and backend PDF rendering (`backend/app/rendering/`) 1:1 synchronized.
