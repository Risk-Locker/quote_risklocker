# Project Instructions & Engineering Contract (`AGENTS.md`)

> Multi-Tier Engineering Contract for **Gemini 4 Argon**, **Gemini 4 Hydrogen**, **Claude Sonnet/Opus 5.5**, and **Gemini 3.8 Flash**.
> Layered architecture: **Database -> Domain (`Decimal`) -> Services -> API -> UI**.

## 1. Fast Execution & Anti-Hallucination Gate (Read First)

1. **Search-Before-Naming (Zero Hallucination):**
   - Never guess or invent table columns, API routes, Pydantic fields, React props, or helper names from memory.
   - Run a targeted search (`Select-String` / `grep`) and read the exact line range (`path:line`) before describing or editing code. If a symbol does not exist, state `"not found"`—never fabricate it.

2. **Task-Size Routing (Stop Spending 5 Minutes on a 30-Second Task):**
   | Task Class | Scope Test | Required Execution & Verification |
   | :--- | :--- | :--- |
   | **`QUICK`** | `<= 3` files; copy/UI tweak, isolated bugfix; zero schema/math/RBAC changes | **Direct Fast Path:** Read target lines -> Edit -> Run the 1 relevant test or `npx tsc --noEmit` -> Done. **No plan file, no 5-stage ceremony, no doc sweep.** |
   | **`STANDARD`** | `4–10` files or 1 cohesive subsystem | Short inline plan -> Failing test first -> Cohesive edit -> Targeted `pytest` + `npx tsc --noEmit` + `verify-brain.py` -> 1-line `docs/core/STATE.md` update. |
   | **`HEAVY`** | DB migration, `Decimal` pricing math, RBAC/CSRF, or multi-subsystem roadmap | Plan in `docs/plans/` -> 10-point edge matrix (`.agents/skills/edge-case-and-scenario-matrix/SKILL.md`) -> Full verification gate + live API/browser check. |

3. **Model-Tier Power Profiles (`.agents/profiles/`):**
   | Model Tier | Active Models | Milestone Budget & Execution Mode | Context Handover |
   | :--- | :--- | :--- | :--- |
   | **`deep`** (`.agents/profiles/deep.md`) | **Gemini 4 Argon**, **Gemini 4 Hydrogen**, **Orchestrator** | **Full Heavy Power:** Up to `1,200–1,500 LOC` per milestone. Can execute multiple serialized milestones in one go when requested, using parallel tool batches/subagents. Pause only on ambiguity or destructive live-DB ops. | `350k–450k` tokens |
   | **`balanced`** (`.agents/profiles/balanced.md`) | **Claude Sonnet 5.5**, **Claude Opus 5.5**, **GPT-OSS** | **Surgical Precision:** Up to `800–1,000 LOC` across 1–2 subsystems. Parallel read batches, minimal token waste, strict verification per milestone. | `200k–250k` tokens |
   | **`flash`** (`.agents/profiles/flash.md`) | **Gemini 3.8 Flash** | **100K-Safe Economy:** Assume `100k` effective context ceiling. Read in `<= 200`-line chunks (never load whole `>600` line files at once). Capped to `QUICK` and bounded `STANDARD` slices (`<= 350 LOC`). Zero unrequested subagents. | `~80k` tokens or `~40` tool calls |

## 2. Core Operating Invariants (Non-Negotiable)

1. **Zero Hardcoding in Application Code:**
   - Business rules, insurer catalogs, towing limits, NCD rates, and excess schedules belong in **PostgreSQL tables/seeds**, never hardcoded in Python `if/elif` branches or React components.
2. **Single Source of Truth (Zero Dual-Truth Math):**
   - Financial, road tax, betterment, and discount math is authoritative **ONLY in backend `Decimal` services**. Monetary DB columns use `Numeric(12, 2)`. React UI never calculates totals or taxes independently.
3. **HTTP Verb & Security Purity:**
   - HTTP `GET` routes must be strictly read-only (never call `db.commit()` or `db.flush()`).
   - Mutating routes (`POST`/`PUT`/`PATCH`/`DELETE`) must enforce `require_role(...)` and CSRF validation.
4. **Cohesive Coding & Garbage Collection:**
   - Keep new modules `<= 600` lines (`<= 300` target for services). Do not create parallel `*_v2` files.
   - Place permanent tests in `tests/unit/`, `tests/integration/`, or `frontend/e2e/` (never root `tests/test_milestone_*`). All `pytest` runs must be 100% hermetic (in-memory SQLite + mocks).

## 3. Directory Structure & Verification Gate (`STANDARD` & `HEAVY`)

- `backend/app/api/` (thin routers) -> `backend/app/services/` (workflows) -> `backend/app/domain/` (pure `Decimal` math) -> `backend/app/models/` (ORM tables) -> `frontend/src/` (Next.js 15 `--rl-*` UI) -> `migrations/` (`075+` SQL).
- **Pre-Commit Checks (`STANDARD` / `HEAVY`):**
  1. Backend hermetic tests: `.\.venv\Scripts\pytest.exe tests/`
  2. Frontend type-check: `cd frontend; npx tsc --noEmit`
  3. Knowledge Base integrity: `.\.venv\Scripts\python.exe commands/verify-brain.py`
  4. For `HEAVY` / UI changes: verify live backend (`http://127.0.0.1:8100`) and live browser (`http://127.0.0.1:3000`, zero `console.error`, zero red error toasts) per `.agents/rules/06-serialized-milestones-and-authentic-verification.md`.
