---
trigger: always_on
description: Clean code craft, naming precision, single-responsibility slicing (<300L Python / <600L React), zero parallel *_v2 slop, and anti-rationalization enforcement.
---
# Rule 02: Clean Architecture, Naming Craft & Anti-Slop Gate

## 1. "Reads Like Butter" Code Standards
- **Exact Intent-Revealing Naming:** Use `verbNoun()` (`calculateRoadTax`, `resolveInsurerAlias`, `buildComparisonMatrix`), semantic booleans (`is_verified`, `has_active_covernote`, `can_generate_pdf`), and domain nouns — ban vague `data`, `info`, `item`, `temp`, `handleSomething`, `helper_v2`.
- **Flat Guard-Clause Flow (`Depth <= 3`):** Validate preconditions early and `return`/`raise` cleanly instead of nesting 5 `if/else` pyramids.
- **Pure Core, Imperative Shell:** Keep tax/NCD/betterment/ledger math in pure functions accepting typed primitives/`Decimal` (zero DB/HTTP side effects), orchestrated cleanly by thin routers/services.
- **Explicit State Machines Over Boolean Soup:** Replace scattered `is_locked && !is_draft && has_override` flags with explicit enums/states and valid transition tables.
- **Modular Slicing Ceilings:** Python services `<= 300` lines per logical unit (`<= 600` max file budget); React UI components/hooks `<= 300–600` lines. Never create parallel `*_v2.py`, `helpers_extra.ts`, or copy-paste utilities already exported by `lib/api.ts`, `lib/utils.ts`, or shared backend services.
- **Zero Dead Code:** Remove unused imports, unreachable branches, and orphaned components instead of leaving commented ghosts. Mark intentional temporary blocks inline: `// RL-DISABLED <feature> — disabled <date>; restore when <reason>`.

## 2. Anti-Rationalization Reality Table

| Agent Excuse / Thought | Non-Negotiable Reality |
| :--- | :--- |
| *"This bugfix is tiny, skip writing the failing test first."* | Skip TDD = skip proof. Write minimal failing assertion first on all Deep Track fixes (`test-driven-development`). |
| *"Compute road tax / totals in React quickly too so UI updates fast."* | Dual-truth math is P0 defect `F-06`. Backend `Decimal` API is the sole mathematical authority. |
| *"One quick fallback PII string (`CHENG...` / mock bank) helps preview render."* | Hardcoding PII is P0 compliance violation `F-11`. Always use tenant settings or neutral empty placeholders. |
| *"Testing against SQLite needs mocking, let me hit live Supabase once."* | Prohibited (`AGENTS.md` Hermetic Invariant). All `pytest` runs use isolated in-memory SQLite + mocks. |
| *"File is already 3,000 lines; adding 80 more lines doesn't hurt."* | Extract a cohesive slice/hook now — never deepen monolith debt. |
| *"I didn't test the empty/null/concurrency/leap-year case because it's rare."* | Rare edge cases break production insurance ledgers. Clear `edge-case-and-scenario-matrix` before coding. |
