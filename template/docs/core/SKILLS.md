# AI Skill Routing (Universal)

This registry guides AI agent capabilities across ANY tech stack, framework, or project domain. Load a skill only when the current task matches its purpose. Skills guide work but never override `AGENTS.md`, `docs/domain/BUSINESS-RULES.md`, tests, or user decisions.

---

## 1. Skill Discovery & Adoption Protocol

When a task requires a specialized capability (e.g. Flutter mobile animations, Rust memory safety, complex SQL tuning, Playwright browser testing, Electron IPC, or design systems):
1. **Search for installable skills**: Use `find-skills` or the environment's skill manager to discover relevant skills.
2. **Install the skill** into the project's agent directory (e.g., `.agents/skills/<skill_name>/` or `.gemini/skills/`).
3. **Register the skill** in the table below with its trigger criteria.

---

## 2. Core Universal Skills Registry

| Skill / Capability | Use when |
| :--- | :--- |
| `systematic-debugging` | ANY bug, crash, 500 error, test failure, or unexpected behavior — investigate root cause before editing code. |
| `test-driven-development` | Implementing any new feature, API route, service logic, or bugfix — write failing tests first. |
| `brainstorming` | ANY creative work, UI redesign, or feature architecture change before implementation. |
| `writing-plans` | Multi-step features, large refactors, or schema changes — produce a structured, bite-sized plan first. |
| `frontend-design` | Building UI components, layouts, responsive design, typography, and interactive aesthetics. |
| `security-best-practices` | Implementing authentication, authorization, session management, input validation, CSRF, and data security. |

---

## 3. Project-Specific Installed Skills (Auto-Updated on Discovery)

*(Add new rows as project-specific skills are installed for this repository)*

| Skill | Technology / Domain | Use when |
| :--- | :--- | :--- |
| — | — | — |

---

## 4. Verification Gate

- Run project test suite.
- Run project linter / typechecker.
- Run `python commands/verify-brain.py` to confirm documentation and registry integrity.
- Run `python commands/update-code-map.py --write` (and `--check`) when structure changes.
