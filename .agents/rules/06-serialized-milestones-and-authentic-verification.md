---
trigger: always_on
---
# Rule 06: Serialized Milestone Planning, Authentic Live Verification & Living Knowledge Base

## 1. Serialized Milestone Architecture (Anti-Monolith Planning)

When an architectural plan or feature request requires significant changes (e.g. >500 lines of code, cross-layer changes touching database, backend APIs, frontend UI, testing, or cleanup):

1. **Master Roadmap + Serialized Milestone Slices:**
   - The agent MUST NOT generate a single massive, monolithic execution plan and attempt to run it all at once in one chat turn.
   - The agent MUST decompose the scope into an overarching **Master Roadmap** divided into numbered **Serialized Milestones** (`M1`, `M2`, `M3`, etc.).
   - Each milestone is strictly bounded:
     - Net change budget: `<= 300–500` lines of code.
     - Cohesive scope: touches only 1–2 related subsystems (e.g. `M1: Storage & RBAC fixes`, `M2: Actuarial math engine`, `M3: UI canvas parity`).
     - Clear blast radius: explicitly list files allowed to change and forbidden to change.
     - Discrete plan file: Each milestone is saved to `docs/plans/milestone-<N>-<name>.md` so it can be reviewed and executed independently.

2. **Auto-Paced Execution & Human Checkpoint:**
   - The agent executes **one milestone at a time**.
   - Upon finishing a milestone, the agent MUST NOT blindly jump into the next milestone. It must:
     1. Run full authentic verification for that milestone.
     2. Update the Project Knowledge Base and regression tests.
     3. Present a concise verification report with concrete evidence (test outputs, screenshots, response payloads).
     4. Stop and guide the human partner: *"Milestone 1 is verified. Would you like to proceed with Milestone 2 here, or open a fresh chat (`Ctrl+L`) and type `Run docs/plans/milestone-2.md`?"*

---

## 2. Autonomous Multi-Domain Lifecycle Forensics Gate

Offline unit tests with in-memory SQLite and mocks are necessary, but **NEVER sufficient** on their own to prove a feature works in production ("complimentary bread"). Every verification pass MUST autonomously execute this 5-stage forensics loop without waiting for the user to prompt it:

### Stage 1: Full-Stack Domain & Module Discovery
Before asserting anything works or is ready, the agent must enumerate all domains and modules across the entire stack:
- `Database Models`: PostgreSQL tables, migration parity, column constraints, `Numeric` types.
- `Pure Domain Engines`: Actuarial calculators, Decimal math, NCD tiers, Betterment calendar logic, zero HTTP.
- `Application Services`: Business coordination, idempotency keys, customer deduplication, workspace patches.
- `FastAPI Routers`: Input schemas, RBAC guards, HTTP verb purity (strict read-only `GET`).
- `Background Workers`: Durable job polling, PacerSentinel delays, abort/cancellation tokens, Supabase Storage uploads.
- `Frontend Views & Canvas`: Next.js 15 App Router, React 19 client components, Design 2 live canvas parity.
- `External APIs & Pacing`: Google AI Studio rate limits (13 RPM, 200k TPM, 480 RPD), token weighing.

### Stage 2: Single Source of Truth & Invariant Verification
- **Zero Client-Side Math**: Verify React components NEVER calculate road tax, betterment, totals, or discounts independently. The backend `Decimal` API is the sole mathematical authority.
- **Monetary Precision**: Confirm monetary columns in PostgreSQL and Python models use `Numeric(12, 2)` / `Decimal`, NEVER IEEE-754 `float` or plain text `varchar`.
- **Zero Mutating `GET`s**: Verify `GET` endpoints never call `db.commit()` or `db.flush()`. All mutations require `POST`, `PUT`, `PATCH`, or `DELETE`.
- **Zero Hardcoded Underwriter Rules**: Verify underwriter catalogs, towing limits, and excess schedules exist in database tables/seeds, NEVER hardcoded in Python `if/elif` branches or React components.

### Stage 3: Authentic Real-World Live Verification
1. **Live Local API Gauntlet (Real HTTP Requests):**
   - Test endpoints against the live running backend (`http://127.0.0.1:8100` via `httpx` or dedicated verification scripts).
   - Assert real cookie handling, real CSRF protection (`X-CSRF-Token` & cookie binding), payload validation, and response serialization.
   - Ensure zero 500 Internal Server Errors and verify error responses follow the standard `{ "error": { "code": "...", "message": "..." } }` contract.

2. **Multi-Role Profile Traversal (RBAC Integrity):**
   - For every role-restricted route, feature, or UI action, verify behavior across all 4 personas:
     - `Super Admin`: Full authority.
     - `Admin`: Tenant administration.
     - `Staff`: Quotation drafting and customer management.
     - `Unauthenticated / Guest`: Redirection to `/login` or clean 401/403.
   - Assert forbidden actions return clean 403 Forbidden with zero PII, zero internal stack traces, and zero data leakage.

3. **Live Browser Visual & Interaction Inspection:**
   - Automate real browser sessions via Playwright, `commands/qa-crawl-page.mjs`, or `chrome-devtools-mcp` against `http://127.0.0.1:3000`.
   - Capture DOM snapshots and full-page screenshots (stored strictly inside gitignored `/.qc-tmp/shots/`).
   - Hard assertions:
     - Zero unhandled console errors (`console.error`).
     - Zero unhandled network rejections or 5xx responses.
     - Zero red error toast notifications rendered in the UI.
     - Visual alignment, optical typography, and `--rl-*` design tokens intact.
     - Responsive stability across `1024x768`, `1280x800`, and `1920x1080` viewports at `80%`, `100%`, and `120%` zoom.

4. **Real Worker & Storage Execution:**
   - Verify extraction and render workers execute real jobs against durable Postgres tables.
   - Verify Playwright Chromium vector PDFs are uploaded to private Supabase Storage, asserting zero fallback to local ephemeral `/tmp` in production.
   - Verify cancellation tokens abort worker execution when uploads are canceled.

### Stage 4: Specification Invariant Audit (`USER-CHRONICLE-IDEA-SPEC.md`)
Cross-check against the user's permanent serial idea specification:
- **Design 2 24-Card Boundary**: Fixed 24 cards matrix; dynamic in-place Towing card upgrade (`EMERGENCY` -> `UNLIMITED`); suppress duplicate unselected towing card in bottom matrix.
- **Single Bilingual Agency Template**: One template with interactive quotation page toggle (`[ Itemized | Lump Sum | None ]`).
- **Exact Calendar Betterment Age**: Full date math via `relativedelta.years` (where 9y 11m 29d = 9 completed years at 35% tariff scale).
- **Google AI Studio Quota Shields**: 13 RPM, 200k TPM, 480 RPD caps locked strictly to `gemini-3.1-flash-lite` and `gemini-3.5-flash-lite`. Zero calls to `gemini-3.8-flash` or preview models.
- **Living Eye Pacer**: Verify PacerSentinel delay is actually executed inside the extraction worker loop.
- **Accurate Token Weighing**: Reject naive `file.size / 65,000` byte heuristics.
- **Sandbox Isolation**: Isolated `is_sandbox: bool` ledger and records for testing/training.

### Stage 5: 10-Point Edge Case & Failure-Mode Analysis
Run before declaring any feature or bugfix ready:
- Empty/null/whitespace inputs
- Boundary numbers (0.00, negative, max limits)
- Leap dates (Feb 29) & timezone bounds
- Concurrency & double-click submission
- RBAC / IDOR / CSRF integrity
- Malformed inputs / OCR errors / prompt injection boundaries
- Network timeout & transaction rollback
- Responsive zoom & keyboard accessibility
- Legacy unmigrated rows
- Indexed SQL queries (zero `_rows()` full-table scans)

---

## 3. Living System Learning & Knowledge Base Synchronization

A system that does not update its working memory and use cases with each feature will quickly degrade and hallucinate. Every completed milestone MUST update the living system:

1. **Exhaustive Use Case Enumeration:**
   - When adding or changing a feature (e.g. a new button, calculation formula, or scanning step), the agent must explicitly enumerate:
     - The primary happy path.
     - Boundary edge cases (empty inputs, zeroes, negative values, large numbers, Unicode/malformed data).
     - Permission permutations (which roles see it, which roles are blocked).
     - Cross-device behaviors.

2. **Cascading Logic & Deprecation Audit:**
   - Actively audit and modify existing/legacy logic affected by the new feature.
   - Never leave orphan parallel functions (`*_v2`, obsolete fallback flags, or conflicting formulas).
   - If an older assumption is superseded, refactor all dependent modules in that milestone to align with the new single source of truth.

3. **Permanent Knowledge Base & Test Sync:**
   - Synchronize affected documentation in `docs/domain/BUSINESS-RULES.md`, `docs/domain/SAAS-BLUEPRINT.md`, and `docs/architecture/`.
   - Append a concise 1–2 line milestone entry to `docs/core/STATE.md` (keep `<80` lines).
   - Add permanent regression test cases to `tests/` covering the newly enumerated use cases so future sprints can never silently break them.

---

## 4. On-Demand Context Telemetry & Fresh-Chat Handover Protocol

1. **Context Telemetry (On-Demand Only):**
   - Run `commands/chat-token-telemetry.py` ONLY when requested by the user or when active context exceeds 250k tokens to guide a fresh chat handover (`Ctrl+L`). Avoid dumping repetitive telemetry tables on normal chat turns.

2. **Fresh-Chat Handover Protocol ($\ge 250\text{k}$ tokens or Milestone Completion):**
   - High conversation context (>250k tokens) and multi-step conversations (>500 steps) increase token processing latency and risk automatic platform compaction pauses.
   - Upon completing a milestone or when active context exceeds 250k tokens:
     1. Present a concise, evidence-backed verification report.
     2. Update `docs/core/STATE.md` and `docs/plans/`.
     3. Provide the user with the exact prompt to start a fresh chat (`Ctrl+L` -> `Run docs/plans/...`) so work continues at maximum speed with zero context loss.

