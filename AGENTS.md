# Project Operating Contract (`AGENTS.md`)

Stack: FastAPI + PostgreSQL (`backend/app`), Next.js 15 (`frontend/src`), SQL migrations (`migrations/`).
Subtree rules load automatically for `backend/AGENTS.md`, `frontend/AGENTS.md`, and `migrations/AGENTS.md`.
Knowledge index: `docs/core/START-HERE.md` | Working memory: `docs/core/STATE.md` | Code map: `docs/generated/CODEBASE-MAP.md`.

## 1. Adaptive Depth Policy (Match Depth to the Task)
- **Subagent Policy:** **Default: 0 subagents** (single-agent execution for all coding, debugging, analysis, and planning). **Hard cap: max 1–2 subagents**, and **only** when the user explicitly requests or approves them first. Never launch automatic parallel subagent swarms or `run_workflow` sweeps.
- **Tier 1 — Direct Question / Micro-Fix** ("why is this happening?", "tell me shortly", small CSS/copy tweak):
  Answer directly and fast. Read only the relevant symbols/files; never spawn subagents or run repo sweeps.
- **Tier 2 — Standard Feature / Bugfix / Planning** (UI flow, API endpoint, DB migration, service bug):
  Locate exact targets first via `docs/generated/CODEBASE-MAP.md` or symbol/grep lookup, then read the exact end-to-end path (UI component -> API router -> service -> DB model/migration -> relevant test) with no blind directory sweeps or unrelated file dumps. Verify real persistence (fresh DB session) + relevant tests + `npx tsc --noEmit`.
- **Tier 3 — Scoped Audit / Refactor Plan** ("audit X", "check for broken things", "plan a refactor"):
  Run **single-agent by default** (never launch subagents unless explicitly requested/approved; hard max 1–2). Read only files relevant to the user's explicit scope, and ask the user before widening scope. Mount `.agents/skills-vault/architecture/house-inspector-audit/SKILL.md` or `.agents/skills-vault/architecture/deep-refactor-architect/SKILL.md` only if explicitly needed.
  Every audit MUST present an explicit subsystem checklist marking each area `[VERIFIED OK]`, `[DEFECT FOUND]`, or `[NOT YET CHECKED]`. **Never claim a full system check is complete while any checklist item remains unchecked** — if full coverage needs another pass, state exact progress and ask to continue.

## 2. Non-Negotiable Engineering Invariants
- **Verify Before Naming:** Search for symbols, routes, and columns before referencing them. If missing, say `"not found"`.
- **Zero Dead UI:** Never ship a button, toggle, or banner action without a verified, committing backend endpoint and visible UI error/loading feedback. Ban silent `catch (e) { console.error(e); }` on user actions.
- **Money & Tax Precision:** All monetary/tax/NCD/discount math lives strictly in backend `Decimal` services (`Numeric(12,2)`). React never computes totals or taxes.
- **API & Transaction Integrity:** `GET` routes are strictly read-only. Every mutating `POST`/`PUT`/`PATCH`/`DELETE` route enforces `require_role` + CSRF and MUST call `db.commit()` (plus `flag_modified(...)` on JSON/JSONB mutations) before returning.
- **DB-Driven Business Rules:** Insurer rates, limits, towing/betterment rules, and catalogs live in DB tables, not hardcoded branches.
- **Design System:** Reuse `frontend/src/components/ui/` and `--rl-*` CSS tokens. No `window.alert`/`confirm`/`prompt`.
- **Test Hygiene:** Add new tests into consolidated domain test files; never create one-off version/hotfix test files (`test_v31_hotfix_*.py`).

## 3. Git & Verification Discipline
- **Branches:** Version/numeric branch names only (`v31`, `v31.1`, `30.11`). Never create descriptive slug branches (`refactor/...`) and never merge/push to `main` without explicit owner confirmation.
- **Strict Readiness Gate:** Never say "all okay", "0 issues", or "deploy will work" unless you have actually run and observed the full verification suite (`pytest -q`, `npx tsc --noEmit`, `npm run lint`, `npm run build`, and CI checks) pass with 0 failures in the current state. Explicitly state anything skipped or not yet checked.
