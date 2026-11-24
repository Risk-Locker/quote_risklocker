---
name: deep-refactor-architect
description: "Deep Tier-3 refactor architecture skill enforcing 100% file reads, full caller graphs, trade-off analysis, and surgical migration blueprints."
---

# Deep Refactor Architect (`deep-refactor-architect`)

Use this skill for Tier 3 architecture analysis and enterprise refactoring plans. Never write a shallow bullet plan from file line counts alone.

## 1. Complete Target Context (Mandatory Before Designing)
1. Read **100% of every file** slated for decomposition or rewrite (issue parallel 800-line `read_file` calls or dispatch read-only `research` subagents across modules).
2. Map **every inbound and outbound dependency**:
   - Search all callers/importers across `backend/app/`, `frontend/src/`, and `tests/`.
   - Check `tests/test_frontend_workspace_contract.py` and domain contract tests for required or forbidden literals/op names before moving code between files.
   - Trace DB transactions (`db.flush`/`db.commit`), state hooks, optimistic updates, and side effects across file boundaries.

## 2. Systemic Diagnosis
Document for each module:
- Current responsibilities & hidden coupling (which hooks/services/components share mutable state or implicit assumptions).
- Dead code, duplicated handlers, mixed UI tokens vs `--rl-*`, and unsafe error swallowing.
- Database/schema/transaction invariants that modularization must preserve (`uq_draft_benefit_selection_concept`, `Numeric(12,2)`, Design 2 parity).

## 3. Compare Concrete Architectural Alternatives
For every major structural split, compare at least **2 real designs** (e.g., extracted headless hooks vs pure domain reducers vs facade modules) across:
- State ownership & re-render boundaries,
- Bundle/testability impact (how unit tests isolate pure logic vs React shell),
- Blast radius & rollback safety.

## 4. Precalculated File-by-File Execution Blueprint
Output a concrete migration plan listing:
- Exact new files/modules to extract and their exported interfaces/types,
- Step-by-step ordered extraction slices (so every intermediate slice builds cleanly with `tsc`, `pytest`, and `build` green),
- Contract-test and E2E verification criteria per slice.
