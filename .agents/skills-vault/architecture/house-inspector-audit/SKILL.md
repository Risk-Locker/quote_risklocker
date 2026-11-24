---
name: house-inspector-audit
description: "Exhaustive subsystem-by-subsystem code, UI wiring, DB commit, security, and parity audit checklist with strict verified vs unchecked honesty."
---

# House-Inspector System Audit (`house-inspector-audit`)

Use this skill whenever the owner asks to audit the system, check if anything is broken, or inspect codebase quality and consistency (Tier 3). Read complete files with zero artificial truncation and never report a subsystem as clean unless every route, button, and transaction in that slice was actually inspected.

## 1. Automated Executable Checks First
1. Run `.venv\Scripts\python.exe commands/audit-wiring.py` — detects mutating routes missing `db.commit()`, in-place JSON writes missing `flag_modified`, missing RBAC, dead frontend `api(...)` calls, and silent `catch { console.error }` handlers.
2. Run `.venv\Scripts\python.exe commands/security-audit.py` — checks SQLi, SSRF, PII leaks, auth bypasses, deprecated Gemini models, and monolith file counts.
3. Run runtime gates when auditing release readiness:
   - `.venv\Scripts\python.exe -m pytest -q`
   - `cd frontend; npx tsc --noEmit; npm run lint; npm run build`

## 2. Subsystem-by-Subsystem Inspection Checklist
Inspect each relevant area deeply (read whole files via parallel 800-line `read_file` slices or dispatch read-only `research` subagents) and mark EVERY row explicitly:
- **Backend API & Transactions (`backend/app/api/routers/*.py`):** Verify every mutating `POST`/`PUT`/`PATCH`/`DELETE` calls `db.commit()` (or delegates to a committing service), calls `flag_modified` on JSON mutations, enforces `require_role` + CSRF, and performs zero writes in `GET` handlers.
- **Core Domain & Financial Math (`backend/app/domain/`, `backend/app/services/`):** Verify pure `Decimal` arithmetic (`Numeric(12,2)`), DB-driven insurer/towing/betterment/road-tax rules, and zero client-duplicated pricing math.
- **Database Schema & Migrations (`migrations/`, `backend/app/models/tables.py`):** Verify `CHECK` constraints, FK `ON DELETE` cascades, partial unique indexes, and explicit SQLAlchemy `db.flush()` ordering before replacement inserts.
- **Frontend Wiring & Zero Dead UI (`frontend/src/`):** Verify every button, toggle, modal, and notice banner points to an active backend endpoint, displays loading feedback, handles errors via `useToast()` or inline alerts (never silent `catch { console.error }`), and reuses `frontend/src/components/ui/` + `--rl-*` tokens.
- **PDF & Canvas Parity (`design2-pdf-parity` / `design2-canvas.tsx`, `template_renderer_design2.py`):** Verify 1:1 layout, typography, benefit visibility, and financial totals parity.
- **Auth, RBAC, CSRF & PII Privacy (`backend/app/auth/`, `frontend/src/middleware.ts`):** Verify explicit role guards on all mutations, session cookie CSRF checks, middleware protection across all operational routes, and zero hardcoded PII in fallbacks or test outputs.
- **Tests & CI Hygiene (`tests/`, `.github/workflows/deploy.yml`):** Verify real DB persistence and HTTP route coverage, consolidated domain test files, and zero stale hotfix/string-scraping bloat.

## 3. Mandatory Honesty Report Format
Present a concise table covering every subsystem above:
`Subsystem | Status ([VERIFIED OK] / [DEFECT FOUND] / [NOT YET CHECKED]) | Scope Checked | Exact Findings (file:line)`

- **Strict Honesty Rule:** Never extrapolate from partial file reads or grep hits. If context or time prevented inspecting any module or endpoint, explicitly mark it `[NOT YET CHECKED]`, list what remains, and ask whether to continue — NEVER report `"all okay"` or `"0 issues"` on partial coverage.
