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

## 2. Authentic Real-World Live Verification Gate

Offline unit tests with in-memory SQLite and mocks are necessary, but **NEVER sufficient** on their own to prove a feature works in production. Every milestone must pass **Authentic Verification**:

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

