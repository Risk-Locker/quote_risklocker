# AI Skill Routing

Load a skill only when the current task matches its description below. Read the selected skill completely before using it. Skills guide work but never override `AGENTS.md`, `docs/BUSINESS-RULES.md`, tests, or user decisions.

## Installed Skills (`.agents/skills/`)

The `.agents/` folder is gitignored (see `.gitignore`) — skills live only in local installs. On a fresh clone, reinstall via the opencode skill manager before relying on them.

| Skill | Use when |
| --- | --- |
| `agent-browser` | Browser automation: navigate, fill forms, click, screenshots, scrape, test web apps, Electron apps, QA/dogfooding runs. |
| `brainstorming` | ANY creative work — features, components, behavior changes — before implementation (explores intent/requirements/design). |
| `customize-opencode` | Editing opencode's own config: opencode.json/.jsonc, `.opencode/`, agents, subagents, skills, plugins, MCP servers, permissions. |
| `fastapi` | Working on FastAPI APIs, Pydantic models, dependencies, SSE streaming, serving frontends. |
| `find-skills` | "How do I do X?", "find a skill for X" — discovering new installable skills. Mandatory before proposing a new skill. |
| `frontend-design` | Building new UI or reshaping existing UI; aesthetic direction, typography, non-templated visual choices. |
| `playwright-automation-fill-in-form` | Automating form filling with Playwright MCP. |
| `playwright-best-practices` | Writing Playwright tests, fixing flaky tests, POM, CI/CD, mocking, auth/OAuth, uploads/downloads, multi-tab, mobile, annotations. |
| `playwright-cli` | Browser interaction and Playwright test work via CLI. |
| `playwright-explore-website` | Website exploration for testing (Playwright MCP). |
| `python-testing` | Writing/reviewing Python tests, flaky tests, regression coverage, nox multi-version, free-threaded Python. |
| `security-best-practices` | Explicit security review requests for python/js/ts/go code. |
| `shadcn` | shadcn/ui projects: add/search/fix/debug components, registries, presets, `components.json`. |
| `systematic-debugging` | ANY bug, test failure, or unexpected behavior — root-cause investigation before fixes (mandatory per AGENTS.md). |
| `test-driven-development` | Implementing any feature or bugfix — write failing tests first. |
| `using-superpowers` | Conversation start — establishes skill discovery and invocation. |
| `vercel-composition-patterns` | React composition: compound components, prop proliferation cleanup, component-library APIs. |
| `vercel-react-best-practices` | React/Next.js performance: data fetching, bundle optimization, rendering patterns. |
| `web-design-guidelines` | "Review my UI", accessibility audit, UX review against Web Interface Guidelines. |
| `webapp-testing` | Interacting with and testing local web apps via Playwright; frontend verification, UI debugging, screenshots. |
| `writing-plans` | Multi-step tasks with a spec — before touching code, write the plan. |

## Skill Discovery Loop

1. When a capability is missing, load the `find-skills` skill and search.
2. Install the skill (opencode skill manager); `.agents/` and `.skill-sources/` stay gitignored.
3. Record the result here (add a row to the table) — that is part of the documentation duty.

## Verification

- Backend: `.venv\Scripts\python.exe -m pytest -q` (from repo root).
- Frontend: `npx tsc --noEmit` and `npm run build` in `frontend/`.
- Structure changed: `python commands/update-code-map.py --write`, then `--check` before finishing.
- E2E/QA scripts: `/.qc-tmp/` (see `docs/OPERATIONS.md` runbook).
