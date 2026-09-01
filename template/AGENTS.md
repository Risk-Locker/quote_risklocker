# Agent Brain System (Universal)

This file plus the whole `docs/` folder is a portable agent brain. When copied into ANY project (e.g. ERP system, mobile app, desktop app, web app, microservices, or a simple 3-file script), this system gives AI agents a structured operating system, deterministic context routing, zero context rot, and strict quality verification.

---

## 0. Project Auto-Adoption / Bootstrap Protocol

When the user asks to **"update the agents to docs folder properly"**, **"adopt this project"**, or **"initialize the brain"**, the agent must execute this one-time discovery sequence without asking unnecessary questions:
1. **Scan the repository**: Identify project type, programming languages, runtimes, package managers, frameworks, and directory structure.
2. **Populate `docs/domain/PROJECT-CONTEXT.md`**: Summarize the product purpose, target users, and key feature scope based on existing code, comments, and READMEs.
3. **Populate `docs/architecture/`**:
   - `STRUCTURE.md`: Map the top-level directory ownership.
   - `ARCHITECTURE.md`: Document system boundaries, subsystems, and data flows.
   - `SETUP.md` & `OPERATIONS.md`: Extract run scripts, dev commands, and environment variables from configs.
   - `TESTING.md`: Extract test commands and testing frameworks used in the project.
   - `DESIGN-SYSTEM.md` & `API-CONTRACT.md`: Document UI patterns or API contracts if applicable (or note if headless/CLI).
4. **Populate `docs/domain/BUSINESS-RULES.md`**: Record critical safety invariants, validation rules, or compliance constraints found in the codebase.
5. **Generate Codebase Map**: Run `python commands/update-code-map.py --write` to scan all symbols across the codebase into `docs/generated/CODEBASE-MAP.md`.
6. **Initialize `docs/core/STATE.md`**: Write the initial active working memory snapshot (<40 lines).
7. **Update Section 9 below**: Fill in the detected stack, dev commands, and non-negotiable rules.
8. **Verify**: Run `python commands/verify-brain.py` to ensure 100% link and registry validity.

---

## 1. Reading Order (always)

1. Read this file first.
2. Read `docs/core/START-HERE.md` — it routes every request to the smallest relevant context.
3. Read only the topic docs the routing table points to. The docs tell you exactly which folder, file, and line range to touch.
4. Read code only after the docs located it. Never scan or grep the whole repo to build context; that is a waste and a failure of this system.

---

## 2. Working Memory & Logbook Duty (mandatory, every interaction)

- `docs/core/STATE.md` is the active working memory (<80 lines) containing the current sprint state and recent logs.
- `docs/history/MEMORY-YYYY-MM.md` holds cold episodic log archives (e.g. `docs/history/MEMORY-2026-08.md`).
- After EVERY interaction — including "hi", a question, or a rejected idea — append one ultra-short log entry to `docs/core/STATE.md`: `date · model · what was asked (1-2 lines, gist only) · what was done (1-2 lines, files changed with file:line) · pending items (if any)`. Max ~4 lines. No bullet points. Never paste prompts or code blocks.
- When `docs/core/STATE.md` exceeds ~80 lines, rotate older entries into `docs/history/MEMORY-YYYY-MM.md`.
- Updating `docs/core/STATE.md` is your responsibility. It never waits for git commit or push. Do it before finishing the interaction.

---

## 3. Documentation Duty (mandatory)

- Docs are the map. Every durable fact must live in a doc with file:line references so future agents never need to hunt.
- BEFORE executing a plan: record the plan and affected files in `docs/core/STATE.md`, and update any topic doc whose behavior will change.
- AFTER executing: update every affected doc — `docs/core/STATE.md` (log entry), topic docs (behavior/routes/schema/env), `docs/architecture/STRUCTURE.md` (file add/delete), `docs/architecture/SETUP.md` (infrastructure), `docs/core/SKILLS.md` (skills used or added), and regenerate `docs/generated/CODEBASE-MAP.md` with `python commands/update-code-map.py --write` when structure changes.
- Run `python commands/verify-brain.py` to ensure doc links and registries stay valid.
- Undocumented work is unacceptable, even for one-line changes.

---

## 4. Temporary Files Convention

- NEVER create files outside the repository (e.g., `%TEMP%`, `C:\Users\...`). No exceptions.
- Anything temporary goes in a gitignored folder INSIDE the project (e.g., `/.tmp/`, `/.qc-tmp/`, or `/.scratch/`).
- If a new temporary folder is needed: append one line to `.gitignore` (e.g., `/.tmp/`), then create it. Never remove, edit, or comment out existing `.gitignore` lines — only append.

---

## 5. Code Change Rules

- When code is deleted or commented out, mark it inline: `// DISABLED <feature> — disabled <date>; restore when <condition>` so future agents know why and when to bring it back.
- Match existing code style. No gratuitous comments; no refactors bundled into unrelated work.
- Commit only when the user explicitly asks. Documentation updates never depend on committing.

---

## 6. Interaction Rules

- Read `docs/core/INSTRUCTIONS.md` — it defines how the owner talks and how to interpret him.
- NEVER take the owner's words literally. References, sarcasm, analogies, and examples are references to intent, not literal requirements. Do not invent or hunt for things the owner did not actually ask for.
- Ask questions before big or ambiguous work. For design/UX changes, analyze first, research options, present 6-8 concrete options, get approval, then execute.

---

## 7. Skills & Capabilities

- Load a skill only when the task matches its description (`docs/core/SKILLS.md` registry). Read the selected skill completely before using it.
- When a capability is missing, search for installable skills or plugins, then record the result in `docs/core/SKILLS.md`.

---

## 8. Verification Gate

- Never declare done without running the project verification chain:
  1. Automated test suite (e.g. `pytest`, `npm test`, `cargo test`, `go test`, `flutter test`) -> must pass with 0 errors.
  2. Static typecheck / linter (e.g. `npx tsc --noEmit`, `mypy`, `ruff`, `cargo check`, `eslint`) -> must pass cleanly.
  3. Brain verification: `python commands/verify-brain.py` -> green.
  4. Code map check: `python commands/update-code-map.py --check` when structure changed.

---

## 9. Project-Specific (Auto-populated during project adoption)

- **Project Name**: [Auto-populated on adoption]
- **Project Type / Domain**: [e.g. Web App, Mobile App, Desktop App, ERP, API Service, CLI, Full-Stack Monorepo]
- **Stack & Technologies**: [e.g. React / Next.js, Node.js, Python FastAPI, Flutter, Electron, Rust, Go, PostgreSQL, etc.]
- **Development Commands**: [e.g. npm run dev, cargo run, flutter run, python main.py]
- **Verification Commands**: [e.g. npm test, pytest, npx tsc --noEmit]
- **Non-Negotiable Business Rules** (see `docs/domain/BUSINESS-RULES.md`):
  - Rule 1: [Auto-populated or specified by owner]
  - Rule 2: [Auto-populated or specified by owner]
