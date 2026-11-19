# Project rules (lean)

Stack: FastAPI + PostgreSQL (backend/app), Next.js 15 (frontend/src), SQL migrations in migrations/.

## Token discipline (most important)
- Never read a whole file over 300 lines. Use Select-String/grep to find the symbol, then read at most ~120 lines around it.
- Do not re-read a file already read this session. Do not dump command output; filter with `Select-Object -First 40`.
- No subagents, swarms, plans, or doc sweeps unless the user asks. Do the task directly.
- Big files (>600 lines) like benefits/page.tsx, benefit-cards.tsx: edit the touched part only.

## Correctness
- Search for a name before using it. If it does not exist, say "not found".
- Money math lives only in backend `Decimal` services (Numeric(12,2)); React never computes totals or taxes.
- GET routes are read-only. POST/PUT/PATCH/DELETE keep require_role + CSRF.
- Business data (insurers, rates, limits) comes from DB tables, not hardcoded branches.
- UI: reuse frontend/src/components/ui/ and --rl-* tokens.

## Verify
- Run only the relevant test or `cd frontend; npx tsc --noEmit`. Report result in 1-2 lines.
- **Strict readiness gate:** NEVER say "all okay", "perfect", "0 issues", or "deploy will work" unless you have actually run and observed the full CI/test suite (`pytest -q`, `npx tsc --noEmit`, `npm run lint`, `npm run build`) pass with 0 failures in the current state. If any check was skipped or failed, state that explicitly.

## Output
- Be brief: no preamble or recap; state changes and test result only.
