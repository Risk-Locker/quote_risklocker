---
trigger: always_on
---
# Rule 05: Live Reality Grounding, Model Freshness & Exhaustive Edge-Case Gate

1. **Zero Stale-Memory Assumptions (`Live First, Docs Synced`):**
   - NEVER cite, hardcode, or recommend AI model IDs (`gemini-*`, `claude-*`, `gpt-*`), SDK flags, framework APIs, or deprecation timelines from training memory or old `STATE.md` entries.
   - Before writing AI provider code, upgrading packages, or choosing agent model tiers:
     1. Check runtime reality (`swarm` `models`, `backend/app/core/config.py`, `frontend/package.json`, `.venv`).
     2. Verify live upstream status & deprecations via `search_web` against official docs (`ai.google.dev`, Next.js, FastAPI, Pydantic, Tailwind, Playwright) and **Context7** (`context7_context7`: `resolve-library-id` / `query-docs` pinned to installed package versions; cross-check `ai.google.dev` for Gemini model IDs).
   - Whenever a live check reveals stale model strings, broken workflows, deprecated commands, or wrong claims in `AGENTS.md`, `.agents/`, `commands/`, or `docs/`, **update the affected docs/harness immediately** (or log a freeze-safe remediation file under `.agents/proposals/` + `digest.json` if inside frozen `backend/app/`, `frontend/src/`, `migrations/`, `tests/`).

2. **Model Attribution Accuracy:**
   - Never fabricate or echo retired/non-existent model labels (e.g., `"Gemini 3.1 Pro"`) when logging `STATE.md` or agent configs. Use `"inherit"` in `.agents/agents/*.md` and explicit verified runtime IDs (`"gemini-3.8-flash-high"`) in `swarm` configs and logs.

3. **Exhaustive Edge-Case & Scenario Gate (Before Any Deep-Track Implementation):**
   - Before writing implementation code for any new feature or bugfix, complete the 10-point **Edge-Case & Failure-Mode Matrix** (`.agents/skills/edge-case-and-scenario-matrix/SKILL.md`) covering: empty/null/whitespace inputs, `Decimal` rounding & negative/zero bounds, timezone/Feb-29 leap boundaries, concurrency/double-submit/deadlocks, cross-tenant RBAC/IDOR/CSRF, malformed PDF/OCR/Unicode inputs, timeout/partial-failure rollback, responsive zoom (`80%–120%` & `1024px`) + keyboard states, legacy unmigrated rows, and indexed SQL scaling.

