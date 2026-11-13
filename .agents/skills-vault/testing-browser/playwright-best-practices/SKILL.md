---
name: playwright-best-practices
description: Author deterministic Playwright E2E specs and visual/zoom verification scripts enforcing user-facing locators, console/5xx zero-error assertions, PDF download parity checks, and clean isolated browser contexts.
---

# Playwright E2E & Visual Verification Best Practices

Use this skill for `@playwright/test` specs (e.g., `frontend/tests/*.spec.ts` or `/.qc-tmp/*.js`), `commands/qa-crawl-page.mjs` audits, and Deep Track UI release checks (`09-qa-and-janitor-gate`).

## 1. Zero-Flake Locator & Assertion Discipline

1. **User-Facing Locators Only:** Prefer `page.getByRole()`, `page.getByLabel()`, `page.getByText()`, or explicit `data-testid` over fragile CSS/Tailwind class chains (`div > div:nth-child(3)`).
2. **Web-First Auto-Waiting Assertions:** Use `await expect(locator).toBeVisible()` / `toHaveText()` rather than manual `page.waitForTimeout(2000)`.
3. **Mandatory Console, PageError & Network Failure Traps:**
   - Every E2E test and crawl script MUST attach listeners for `page.on("console", ...)` (`type === "error"`), `page.on("pageerror", ...)`, and `page.on("response", ...)` (`status >= 500` or unexpected `4xx`), failing hard if any runtime error occurs!
4. **Full Responsive & Browser Zoom Audit (`1024px–1920px`, `80%–120%` Zoom):**
   - Assert `document.documentElement.scrollWidth <= window.innerWidth` across `1024x768`, `1280x800`, and `1920x1080` AND scaled zoom views (`references/e2e-and-visual-audit.md`) — catching table crunches (`benefits-manager-panel`) and sticky-header overlap before users do.
5. **Artifacts Stay Inside `/.qc-tmp/`:** Never dump trace zips or screenshots at repo root or OS `%TEMP%`.

## 2. Standard E2E Assertion Checklist

| Check Area | Required Assertion | Failure Trigger |
| :--- | :--- | :--- |
| **Runtime Stability** | Attach `console` (`error`) + `pageerror` traps before `goto` | Any uncaught React/JS console error fails test immediately |
| **Network Integrity** | Listen to `response` across API mutations & initial loads | Unexpected HTTP `5xx` or unhandled `4xx` fails test immediately |
| **Layout & Zoom** | Measure `scrollWidth <= innerWidth` across `80%/100%/120%` | Horizontal overflow or sticky header clipping fails visual check |
| **PDF Downloads** | Verify `download.path()` starts cleanly with `%PDF-` bytes | Empty response, HTML error fallback, or silent browser failure |
| **Keyboard Flow** | Verify `Tab` / `Escape` closes drawers and returns trigger focus | Trapped focus loss or missing accessible `role` fails a11y |

## 3. E2E & Visual Audit Templates

- Run Playwright E2E suites cleanly via `npx --prefix frontend playwright test` (keep traces/screenshots inside `/.qc-tmp/`).
- Run single-page layout & zoom audits via `commands/qa-crawl-page.mjs` and inspect captured PNGs visually with `read_file`.
- Isolate test state cleanly (fresh browser context per spec, mock or seed hermetic sessions cleanly, never mutate shared production DB state).
- Load `references/e2e-and-visual-audit.md` for copy-paste Playwright console/network guards, zoom sweep loops, and real Chromium PDF download header checks.
