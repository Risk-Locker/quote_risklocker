---
name: domain-interrogation-and-reality-gate
description: Enforce a 40-factor domain completeness audit, multi-plan DB contingency design, and explicit Build-vs-Buy honesty gate before planning or writing core business logic.
---

# Domain Interrogation & Reality Gate

Use this skill **BEFORE** architecture sign-off and planning on any non-trivial feature, regulatory calculation, HR/payroll/tax/insurance engine, or external data pipeline. Never accept an underspecified prompt blindly, and never fabricate missing data sources.

## Role & Skill Boundary (Zero Overlap)
- **`domain-interrogation-and-reality-gate` (`01` / `02` / `03`, pre-plan):** Interrogates **requirements, data ownership, multi-plan DB schema/backfill/rollback, and Build-vs-Buy honesty** across [`references/40-factor-audit-checklist.md`](references/40-factor-audit-checklist.md).
- **`edge-case-and-scenario-matrix` (`03` / `06`–`09`, plan -> test):** Translates approved scope into **10 code-level guards and concrete Red-First test vectors**.

## 1. Mandatory 40-Factor Completeness Audit (`8 Axes x 5 Factors`)

Inspect all **40 numbered factors** (`#1`–`#40`) in [`references/40-factor-audit-checklist.md`](references/40-factor-audit-checklist.md) and output a grouped sign-off table in `implementation_plan.md` marking every factor `HANDLED`, `N/A` (with reason), or `BLOCKED`:
1. **Domain & Regulatory Truth (`#1–#5`)** — Official sources, jurisdictions, effective dates, `Decimal` rounding, fail-closed unknowns.
2. **Input Normalization & Format Scope (`#6–#10`)** — Units (`cc`/`kW`/`W`), plates/IDs, empty/extreme bounds, OCR noise, manual staff priority.
3. **Database Architecture & Multi-Plan Contingency (`#11–#15`)** — Normalized `NUMERIC(12,2)` schema, triggers/indexes, forward migration + idempotent backfill + verified rollback plan.
4. **Concurrency & Finite State Integrity (`#16–#20`)** — Explicit enums, read-only `GET`, row locks (`FOR UPDATE`), idempotency keys, worker lease safety.
5. **Security & Bug-Bounty Surface (`#21–#25`)** — RBAC, tenant/staff IDOR, CSRF, injection/SSRF ban, fail-closed private storage & PII safety.
6. **Observability & Failure Recovery (`#26–#30`)** — Timeouts, outage degradation, audit log, masked telemetry, dead-letter states.
7. **UX, Reporting & Export Parity (`#31–#35`)** — Zero client math, accessible dialogs, complete UI states, `80%–120%` zoom, Design 2 PDF parity.
8. **Scale, Cost & Lifecycle Governance (`#36–#40`)** — Indexed SQL, zero `N+1`, AI quota/live model checks, memory caps, retention/purge.

## 2. Mandatory 4-Bucket Build-vs-Buy & OSS Honesty Table (Zero Mumbling)

Every plan MUST classify external dependencies and non-trivial modules honestly — **never invent live APIs or fake regulatory accuracy**:

| Need | Classification | Honest Action Required |
| :--- | :--- | :--- |
| Deterministic math & versioned tables | **Build in Code/DB** | Encode pure `Decimal` engines + effective-dated Postgres tables. |
| Reusable library / workflow capability | **Adopt / Evaluate OSS Package (`Rule 00`)** | Dispatch `02-falcon-scout` (`Context7` / `github` / `PyPI`/`npm`) to compare 2–3 curated OSS packages for maintenance & minimal footprint before custom-building. |
| Authoritative public gazette / specs | **Verify Live First (`Rule 05`)** | Fetch official source via `search_web` / Context7, cite exact URL & date. |
| Proprietary / Paid live data (JPJ MyEG, insurer portals, credit/NRIC verification) | **Buy / License Required** | Tell the owner bluntly: *"AI cannot fabricate this feed; you must purchase/connect API X or supply signed tariff files; until then, field Y stays manual / `Check Needed`."* |

## 3. Clarification Rule (`ask_question`)

When business rules fork cleanly (e.g., effective-date cutoffs, fee ownership, overwrite vs versioned history, OSS vs minimal custom module), present concise multiple-choice questions via `ask_question` with a recommended enterprise default instead of guessing silently.
