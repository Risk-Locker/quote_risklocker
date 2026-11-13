# Project Instructions & Engineering Contract (`AGENTS.md`)

> Lean, pragmatic engineering contract for Gemini 3.8 Flash and IDE agents.
> Follows Amazon-grade layered architecture: **Database -> Services -> API -> UI**.
> Write code like a senior human engineer: cohesive blocks, zero hardcoding, zero slop.

## 1. Core Operating Principles (Non-Negotiable)

1. **Zero Hardcoding in Application Code:**
   - Business rules, company names, towing limits, NCD rates, and excess defaults belong in the **Database (PostgreSQL / models / seeds)**, NEVER hardcoded in Python `if/elif` branches or React components.
   - If an underwriter changes terms, it must only require a database row update, zero code deployments.

2. **Single Source of Truth (Zero Dual-Truth Math):**
   - Financial, road tax, and discount calculations are authoritative **ONLY in backend `Decimal` services**.
   - The frontend React UI renders data received from the API. It NEVER duplicates road tax formulas or calculates totals independently.

3. **Human-Grade Cohesive Coding (No Frankenstein Micro-Patching):**
   - When modifying a component or function, rewrite the cohesive block cleanly. Do not apply 20 tiny string patches that leave orphaned variables and broken event listeners.
   - Keep files modular: Python services `<= 300` lines, React components `<= 300` lines.
   - Delete dead code and unused imports immediately.

4. **Strict Garbage Collection (Clean as You Go):**
   - NEVER dump temporary test files (`test_v6_*`, `test_v7_*`, `test_milestone_*`) in the root `tests/` directory.
   - Integrate permanent tests into canonical test folders:
     - `tests/unit/` (domain calculations, Decimal engines)
     - `tests/integration/` (FastAPI endpoints, database workflows)
     - `frontend/e2e/` (real Playwright browser tests)
   - Delete all scratch scripts and temporary test files immediately after verification.

5. **Authentic Verification (No Self-Grading Illusions):**
   - A mocked in-memory SQLite test does NOT prove a web UI works.
   - For UI changes, verify live interactive behavior (input focus, blur, state persistence).

## 2. Directory Structure & Runtime Reality

- `backend/app/api/`: Thin HTTP routers (validate input, call service, return JSON).
- `backend/app/services/`: Business workflows and database coordination.
- `backend/app/domain/`: Pure domain calculation engines (Decimal math, zero HTTP).
- `backend/app/models/`: SQLAlchemy ORM database tables.
- `frontend/src/`: Next.js 15 React components, styled cleanly with `--rl-*` design tokens.
- `migrations/`: Historical PostgreSQL schema evolution (never touch during runtime).

## 3. Pre-Commit Verification

Before completing tasks, ensure:
- Pytest passes: `.\.venv\Scripts\pytest.exe tests/`
- Frontend compiles cleanly: `cd frontend; npx tsc --noEmit`
- Knowledge Base verified: `.\.venv\Scripts\python.exe commands/verify-brain.py`
