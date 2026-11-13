# Risklocker UI Plugin Guardrails

1. Check `frontend/src/components/ui/` first before creating any new button, dialog, input, select, badge, tabs, toast, or tooltip component.
2. Use the `risklocker-ui-shadcn` MCP tools to inspect official accessible Radix/shadcn component primitives and patterns without API keys.
3. Translate any imported primitive strictly into `docs/architecture/DESIGN-SYSTEM.md` `--rl-*` CSS tokens (`#f5f5f7`, `#ffffff`, `#1b1717`, `#ed1c24`, `8px` card radius, `6px` chip radius). Reject generic Tailwind blue (`#3b82f6`), pill chips, and unstyled native `window.alert`/`confirm`/`prompt`.
4. Pair component selection with **Mobbin** (`mobbin_mobbin`, when a paid Mobbin Pro plan is connected) or `browser` / reference research for workflow hierarchy changes, while preserving `@phosphor-icons/react` and Design 2 PDF parity.

