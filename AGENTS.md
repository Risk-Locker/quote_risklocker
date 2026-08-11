# Agent Brain System (Universal)

This file plus the whole `docs/` folder is a portable agent brain. Copy `AGENTS.md` and `docs/` into any project, adapt the "Project-Specific" section and the docs files, and the system works as-is. The rules below are binding for every AI agent working in this repository.

## 1. Reading Order (always)

1. Read this file first.
2. Read `docs/START-HERE.md` — it routes every request to the smallest relevant context.
3. Read only the topic docs the routing table points to. The docs tell you exactly which folder, file, and line range to touch.
4. Read code only after the docs located it. Never scan or grep the whole repo to build context; that is a waste and a failure of this system.

## 2. Logbook Duty (mandatory, every interaction)

- `docs/MEMORY.md` is the project logbook and current snapshot.
- After EVERY interaction — including "hi", a question, or a rejected idea — append one ultra-short log entry: `date · model · what was asked (1-2 lines, gist only) · what was done (1-2 lines, files changed with file:line) · pending items (if any)`. Max ~4 lines. No bullet points. Never paste prompts or code blocks.
- Updating MEMORY.md is your responsibility. It never waits for git commit or push. Do it before finishing the interaction.
- Record file additions, file deletions, and byproducts in the same log.

## 3. Documentation Duty (mandatory)

- Docs are the map. Every durable fact must live in a doc with file:line references so future agents never need to hunt.
- BEFORE executing a plan: record the plan and affected files in MEMORY.md, and update any topic doc whose behavior will change.
- AFTER executing: update every affected doc — MEMORY.md (log entry), topic docs (behavior/routes/schema/env), `docs/STRUCTURE.md` (file add/delete), `docs/SETUP.md` (infrastructure), `docs/SKILLS.md` (skills used or added), and regenerate `docs/generated/CODEBASE-MAP.md` with `python commands/update-code-map.py --write` when structure changes.
- Undocumented work is unacceptable, even for one-line changes.

## 4. Temporary Files Convention

- NEVER create files outside the repository (e.g., `%TEMP%`, `C:\Users\...`). No exceptions.
- Anything temporary goes in a gitignored folder INSIDE the project. This project uses `/.qc-tmp/`.
- If a new temporary folder is needed: append one line to `.gitignore` (e.g., `/.new-tmp/`), then create it. Never remove, edit, or comment out existing `.gitignore` lines — only append.

## 5. Code Change Rules

- When code is deleted or commented out, mark it inline: `// RL-DISABLED <feature> — disabled <date>; restore when <condition>` so future agents know why and when to bring it back.
- Match existing code style. No gratuitous comments; no refactors bundled into unrelated work.
- Commit only when the user explicitly asks. Documentation updates never depend on committing.

## 6. Interaction Rules

- Read `docs/INSTRUCTIONS.md` — it defines how the owner talks and how to interpret him.
- NEVER take the owner's words literally. References, sarcasm, analogies, and examples are references to intent, not literal requirements. Do not invent or hunt for things the owner did not actually ask for.
- Ask questions before big or ambiguous work. For design/UX changes, analyze first, research options, present 6-8 concrete options, get approval, then execute.

## 7. Skills

- Load a skill only when the task matches its description (`docs/SKILLS.md` registry). Read the selected skill completely before using it.
- When a capability is missing, use the `find-skills` skill before proposing anything new, then record the result in `docs/SKILLS.md`.

## 8. Verification

- Never declare done without: backend `python -m pytest -q` (green), frontend `npx tsc --noEmit` and `npm run build` (green), and `python commands/update-code-map.py --check` when structure changed.
- E2E/QA scripts live in `/.qc-tmp/` (see OPERATIONS.md for the runbook).

## 9. Project-Specific (adapt when copying to another project)

- Stack: Next.js 15.5 frontend (`frontend/`), FastAPI backend (`backend/`), Supabase/Postgres (`migrations/`), private Supabase Storage for PDFs.
- Dev servers: backend :8100, frontend :3000, started with `commands/start-backend.ps1` and `commands/start-frontend.ps1` (port file `.qc-tmp\backend-port.txt`).
- Dev login: admin@risklocker.local / admin123.
- Default motor template id `4a16bc96-7ca1-44db-be1b-c0a462e71e2f` — contains ONLY 5 image, 24 text, 11 variable, 4 group elements (no specials); E2E group tests must add text elements first.
- Non-negotiable business rules (full list in BUSINESS-RULES.md): Supabase/Postgres only for app data; private Supabase Storage for persistent PDFs; never expose backend secrets to the frontend; never silently guess uncertain extracted values; deterministic PDF generation from reviewed drafts; no hardcoded fees; preserve Upload -> Check Values -> Generate PDF.
