# Mobbin -> `shadcn` -> Risklocker `--rl-*` Placement & State Spec

## 1. Canonical Control Placement Rules (`03-mentor-architect` / `05-principal-designer`)
- **Workspace / Table Global Actions** (Upload, Export PDF, Copy WhatsApp, Filter, Add Vehicle): top-right action bar aligned cleanly beside title/search controls.
- **Row / Column Record Actions** (Edit, Confirm Hit, Mark Winner, Delete): right-aligned compact action cell or row menu, never floating unaligned badges.
- **Dense Secondary Metadata** (MyKad history, covernote extraction diffs, audit logs, insurer schedule breakdowns): slide-over Drawer or controlled `Dialog`, keeping main table scannable down to `1024px` without horizontal squishing (`benefits-manager-panel` fix).

## 2. Full 9-State & Multi-Zoom Audit Matrix
Verify every interactive panel renders cleanly across ALL states:
1. `default` (crisp data, aligned decimal columns, tabular-nums for RM amounts)
2. `hover` & `active` (subtle `--rl-*` surface shift, instant feedback)
3. `focus-visible` (high-contrast 2px ring visible on keyboard `Tab`)
4. `disabled` (non-clickable muted contrast with tooltip explaining why if locked)
5. `loading` (container-local skeleton matching target layout height — zero full-page jitter)
6. `empty` (actionable direct instruction + primary CTA button, zero dead whitespace)
7. `error` (plain actionable recovery copy + Retry button; zero raw Python tracebacks)
8. `overflow` (long plate, 40-char benefit name, multi-line remark truncating or wrapping cleanly without clipping sibling cells)
9. **Viewports & Zoom:** `1024px`, `1280px`, `1920px` tested at `80%`, `100%`, and `120%` browser zoom with `scrollWidth <= innerWidth`.

