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

6. **On-Demand Context & Session Token Telemetry:**
   - Report token telemetry (`commands/chat-token-telemetry.py`) ONLY when explicitly requested by the user, during performance troubleshooting, or when active context exceeds 250k tokens to advise on fresh-chat handover (`Ctrl+L`). Avoid dumping repetitive telemetry tables on normal chat responses.

7. **Seamless Fresh-Chat Handover Protocol ($\ge 250\text{k}$ tokens or Milestone Completion):**
   - High conversation context (>250k tokens) and long multi-step sessions (>500 steps) increase latency and trigger automatic IDE context compaction pauses.
   - At the completion of any milestone, or whenever active context exceeds 250k–300k tokens, the agent MUST provide a structured handover prompt:
     - Verified milestone recap with concrete empirical evidence (test counts, endpoints, TypeScript status).
     - Working memory synchronization in `docs/core/STATE.md` and `docs/plans/`.
     - The exact copy-paste command for a fresh chat (`Ctrl+L` -> `Run docs/plans/...`) so the user can continue with zero context bloat.

## 2. Directory Structure & Runtime Reality

- `backend/app/api/`: Thin HTTP routers (validate input, call service, return JSON).
- `backend/app/services/`: Business workflows and database coordination.
- `backend/app/domain/`: Pure domain calculation engines (Decimal math, zero HTTP).
- `backend/app/models/`: SQLAlchemy ORM database tables.
- `frontend/src/`: Next.js 15 React components, styled cleanly with `--rl-*` design tokens.
- `migrations/`: Historical PostgreSQL schema evolution (never touch during runtime).

## 3. Pre-Commit Verification & Autonomous Forensics Gate

Never claim work is complete, passing, or production-ready based solely on an offline unit test (`pytest`). Unit tests verify isolated in-memory logic ("complimentary bread"), but do NOT prove a real web system works.

Before declaring ANY task or milestone complete, agents MUST autonomously execute the **Multi-Domain Lifecycle Forensics Protocol**:

1. **Domain & Module Enumeration (Discovery):**
   - Identify all architectural layers touched: `Database Models` -> `Pure Domain Engines` -> `Application Services` -> `FastAPI Routers` -> `Background Workers` -> `Frontend React UI` -> `PDF Vector Rendering` -> `Storage / External Integrations`.
   - Never skip layers. Enumerate all use cases (happy path, boundary failures, concurrency).

2. **Single Source of Truth & Database Invariants:**
   - Confirm zero client-side financial/tax math in React UI (sole authority: backend `Decimal` domain services).
   - Confirm database monetary columns use `Numeric(12, 2)`, NEVER `float` or plain text `varchar`.
   - Confirm zero mutating HTTP `GET` endpoints (`GET` must never execute `db.commit()` or `db.flush()`).
   - Confirm zero hardcoded underwriter terms, towing limits, or rules in application `if/elif` branches (rules belong in PostgreSQL tables/seeds).

3. **Authentic Live Operational Traversal:**
   - **Live Backend API**: Verify endpoints against running backend (`http://127.0.0.1:8100`) via real HTTP calls asserting real cookies, CSRF tokens, and zero unhandled 500 errors.
   - **Live Browser Visual & Console**: Automate real browser sessions (`http://127.0.0.1:3000`) asserting **zero `console.error`**, **zero unhandled rejections**, **zero red error toasts**, and responsive stability across `1024px`, `1280px`, `1920px` at `80%`, `100%`, `120%` zoom.
   - **Real Worker & Storage Pipeline**: Verify background workers execute real durable jobs, upload real vector PDFs to Supabase Storage (never ephemeral `/tmp` fallbacks), and enforce cancellation tokens.

4. **Specification Invariant Audit (`USER-CHRONICLE-IDEA-SPEC.md`):**
   - Verify Design 2 24-card matrix boundary enforcement and dynamic in-place Towing upgrade + duplicate suppression.
   - Verify single Bilingual Agency template with interactive quotation page toggle.
   - Verify exact calendar betterment age math (`relativedelta.years`, 9y 11m 29d = 9 completed years).
   - Verify strict Google AI Studio free tier caps (13 RPM, 200k TPM, 480 RPD) locked strictly to `gemini-3.1-flash-lite` and `gemini-3.5-flash-lite`, with zero calls to `gemini-3.8-flash` or preview models.
   - Verify real Living Eye pacer sentinel delays executed in the worker loop.
   - Verify token weighing does not use naive byte heuristics.
   - Verify dedicated sandbox / practice isolation (`is_sandbox`).

5. **Tooling & Harness Checks:**
   - Pytest passes: `.\.venv\Scripts\pytest.exe tests/`
   - Frontend compiles cleanly: `cd frontend; npx tsc --noEmit`
   - Knowledge Base verified: `.\.venv\Scripts\python.exe commands/verify-brain.py`

