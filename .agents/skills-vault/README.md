# `.agents/skills-vault/` — Cold Local Skill Library (100+ Scale Tier)

> **Purpose:** Store dozens or hundreds of repo-local skills inside the repository **without burning prompt boot tokens** on every AI turn.

- **Active skills (`.agents/skills/`):** Always discovered at session startup (`<= 50` soft active cap under Max-Force Gemini 3.8 Flash High mode; live counts in `docs/generated/SKILLS-INDEX.md`).
- **Cold vault (`.agents/skills-vault/<category>/<name>/`):** Dormant local skills costing **0 boot tokens** until mounted.

## Category Taxonomy
- `frontend/` — UI frameworks, Tailwind, component libraries, accessibility
- `backend-db/` — FastAPI, Postgres, Redis, queuing, storage, migrations
- `testing-browser/` — Playwright suites, E2E harnesses, load/perf tools
- `security/` — AppSec, auth, RBAC, secrets scanning, compliance
- `design/` — Design tokens, PDF parity, Figma, typography
- `domain/` — Project-specific business/industry rulebooks
- `vendor/` — Third-party SaaS/API SDK packs (Sentry, Stripe, Supabase, etc.)
- `general/` — Cross-cutting workflows, research, refactoring, planning

## Quick Commands
- Inspect inventory & token budget: `.\.venv\Scripts\python.exe commands/skills-manager.py list`
- Install repo-locally (Active or Cold): `.\.venv\Scripts\python.exe commands/skills-manager.py install <path> --cold --category vendor`
- Mount for a sprint: `.\.venv\Scripts\python.exe commands/skills-manager.py mount <name_or_category>`
- Unmount back to vault: `.\.venv\Scripts\python.exe commands/skills-manager.py unmount <name_or_category>`
- Audit hygiene & rebuild index: `.\.venv\Scripts\python.exe commands/skills-manager.py doctor`

