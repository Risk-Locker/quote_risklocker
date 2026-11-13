---
name: system-design-and-architecture
description: Design scalable modular systems with strict router-service-domain boundaries, single-source-of-truth pricing math, explicit state machines, transactional ACID locks, idempotent APIs, and fail-closed storage before implementing features or refactors.
---

# System Design & Architecture Skill

Think like a Principal Systems Architect before writing a single line of implementation code. Trace downstream impact across `docs/generated/GRAPH_REPORT.md` (`6,348` AST nodes), `docs/domain/SAAS-BLUEPRINT.md`, and `docs/domain/BUSINESS-RULES.md`.

## 1. Non-Negotiable Architecture Principles

1. **Pure Core, Imperative Shell:**
   - Isolate deterministic calculations (`road_tax_engine.py`, `ncd_evaluator.py`, `towing_evaluator.py`, `unified_addon_engine.py`) as pure functions over typed primitives / `Decimal`. Zero SQL sessions, zero HTTP clients, zero filesystem I/O inside calculation engines.
   - Orchestrate DB transactions (`SELECT ... FOR UPDATE`), storage uploads, and HTTP orchestration strictly in focused service layers (`backend/app/services/`), keeping HTTP routers (`backend/app/api/`) thin validation + RBAC gates.
2. **Single Source of Truth (Zero Dual-Truth Logic):**
   - Backend `Decimal` engines + Supabase catalog tables are authoritative. Never duplicate road tax formulas, total payable rounding, or benefit sorting logic inconsistently in React or fallback constants.
3. **Compare 2–3 Modular Options Before Committing (`Rule 00`):**
   - Evaluate candidate architectures across: (a) 5-year maintainability & schema clarity, (b) transactional consistency under concurrency, (c) operational simplicity & zero bloated dependencies, (d) clean rollback path on partial failure.
4. **Explicit State Machines Over Implicit Booleans:**
   - Replace overlapping flags (`is_ready`, `is_locked`, `client_paid`, `has_covernote`) with explicit finite states (`Enum` + PostgreSQL check constraints) and validated transition guards.
5. **Fail-Closed External Boundaries:**
   - Never silently write sensitive customer artifacts to local temp directories (`storage=None` fail-open bypass) or fall back to `"etiqa"` on exception. Surface explicit typed domain errors.

## 2. Architecture Anti-Patterns Rejected at Design Review

| Anti-Pattern Found in Legacy Modules | Target Production Architecture |
| :--- | :--- |
| Multi-purpose `services/*.py` god modules (`>800` lines) | Split cohesive domain modules (`<=350` lines) with clear interfaces |
| `_rows()` full-table Python scan in request handlers | Indexed SQL `WHERE` / `JOIN` + keyset/bounded `LIMIT` pagination |
| Floating-point tariff constants in React + Python mismatch | Backend `Decimal` service + DB catalog as sole source of truth |
| Silent local temp fallback when `storage=None` (`F-01`) | Fail-closed domain error + rollback cleanly before response |

## 3. Architecture Pre-Flight Checklist (Mandatory Before Coding)

- [ ] Read `docs/generated/GRAPH_REPORT.md` + target module's `docs/change/` dossier to inspect every caller/dependent.
- [ ] Verify DB concurrency safety: read `references/api-idempotency-and-concurrency.md` for `Idempotency-Key`, row locks (`FOR UPDATE`), optimistic version columns, and HTTP `GET` read-only enforcement.
- [ ] Verify module boundary rules: read `references/clean-architecture-boundaries.md` for layer dependency direction, slice sizes, and DTO typing.
- [ ] Pair with `edge-case-and-scenario-matrix` before finalizing `implementation_plan.md`.
