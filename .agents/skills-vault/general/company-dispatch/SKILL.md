---
name: company-dispatch
description: Orchestrate the 9-role Risklocker engineering company across Antigravity native subagents (.agents/agents/01..09.md), Dual-Track routing, live freshness verification, and 10-point scenario gates during Deep Track work.
---

# Company Dispatch Runbook (`.agents/manifest.yaml`)

Use this skill whenever handling **Deep Track** work (features, schema migrations, API contracts, calculation/tax/benefit logic, AI extraction pipelines, refactors, security fixes). **Skip heavy ceremony on Fast Track (`<15s`)** pure CSS/copy/token tweaks.

## 1. Pre-Flight Before Dispatching
1. Inspect `.agents/.freeze.lock`. If `enabled: true`, block all edits inside `backend/app/`, `frontend/src/`, `migrations/`, and `tests/`.
2. Check `.agents/manifest.yaml`: every role runs on `inherit` (`invoke_subagent`) or explicit `"gemini-3.8-flash-high"` (`swarm`) with uncapped verification depth.
3. Ground first (`Rule 05`): confirm active models (`swarm models`), package versions, `docs/generated/GRAPH_REPORT.md` AST neighborhoods, `docs/generated/CODEBASE-MAP.md`, and relevant `docs/change/` dossiers.
4. Enforce `domain-interrogation-and-reality-gate` (40-factor checklist + Build-vs-Buy honesty table incl. OSS/`Rule 00`) and `edge-case-and-scenario-matrix` (all 10 dimensions mapped to tests before coding).

## 2. Separation of Duties & Antigravity Execution Ownership
- **CEO -> Chief of Staff -> Management Flow:** The user (`CEO`) talks only to Antigravity's Default Agent (or optional `01-orchestrator-pm`, `mainAgent: true`). Specialists `02`–`09` (`mainAgent: false`, `subagent: true`) execute strictly via delegation (`invoke_subagent` / `swarm`).
- **Role Boundaries:** Governance roles (`01`–`05`) NEVER hold `write_file`, `edit_file`, or `run_command` tools (`inherit` workspace, read/search only). Execution & SAST command runs (`pytest`, Playwright, `security-audit.py --strict --with-external --json`) live on `09-qa-and-janitor-gate` (or Chief of Staff), while `04-security-auditor` holds **strict read-only unilateral veto power** over code + verbatim SAST output.
- **Chief of Staff MCP & Media Toolkit:** Antigravity's Default Agent (`Chief of Staff`) directly invokes connected MCP servers (`context7_context7`, `github`, `mobbin_mobbin`, `risklocker-ui-shadcn`, `chrome-devtools-mcp`), the `browser` subagent, `image-generator` subagent, `generative_ui` skill, `ask_question`, `swarm`, and `schedule` whenever specialists request external lookups or visual artifacts.
- **Proactive Slash Commands:** Suggest `/grill-me`, `/plan`, `/teamwork`, `/boost`, `/browser`, or `/learn` when a prompt matches those workflows.

## 3. Canonical Deep Track Execution Pipeline (Matches `manifest.yaml`)
1. **Route (`01-orchestrator-pm`):** Classify Deep Track vs Fast Track and surface ambiguous requirement branches via `ask_question`.
2. **Grounding (`02-falcon-scout` + Chief of Staff MCPs):** Verify live deprecations (`ai.google.dev` via `search_web`) and package/OSS idioms (`context7_context7` + `github` MCP).
3. **Interrogate Domain (`domain-interrogation-and-reality-gate`):** Complete all 40 factors + 4-bucket Build-vs-Buy table (`references/40-factor-audit-checklist.md`).
4. **Architect & Design (`edge-case-and-scenario-matrix` + `03-mentor-architect` [+ `05-principal-designer` if UI]):** Lock clean boundaries, 6-point plan checklist, 10-point guard-to-test matrix, and `--rl-*` component placement.
5. **Owner Plan Gate:** Present `implementation_plan.md` and wait for explicit owner approval before writing production code.
6. **Red-First Anchor (`09-qa-and-janitor-gate`, `inherit`):** Author/confirm failing regression + boundary fuzz test BEFORE forking implementation branches.
7. **Parallel Variant Tournament (`parallel-variant-tournament`):** Dispatch competing `swarm` branch workers (`model: "gemini-3.8-flash-high"`, `workspace: "branch"`), verify via `09` + `03` + `04` lexicographic scoring gates, and merge/prune only the simplest bug-free winner.
8. **Independent Security Veto (`09` executes -> `04` judges):** `09` executes `commands/security-audit.py --strict --with-external --json` (zero tampering); `04-security-auditor` audits diff + verbatim JSON output read-only and returns `PASS | BLOCKED`.
9. **Final Release Gauntlet (`09-qa-and-janitor-gate`):** Run `pytest`, `tsc --noEmit`, `npm run build`, Playwright `1024px–1920px` + `80%–120%` zoom checks, `.qc-tmp/` debris cleanup, `STATE.md` (`<= 80L`), `update-code-map.py --write`, `verify-brain.py`, `daily_radar.py --offline --dry-run --strict`, and `verify-deploy-gate.ps1` (`10/10`).

## 4. Mandatory Verification Output Contract
Every delegated agent MUST return: `verdict`, `files_touched`, `invariants_verified`, `commands_executed_and_verbatim_output`, and `residual_risks`. Never pass "looks good" summaries upward.
