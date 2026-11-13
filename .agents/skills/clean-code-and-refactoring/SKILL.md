---
name: clean-code-and-refactoring
description: Craft clean, readable, modular code ("reads like butter"): intent-revealing names, flat guard clauses (depth <=3), pure-core/imperative-shell, monolith slicing (<300L Python / <600L React), zero parallel *_v2 slop, and dead-code cleanup.
---

# Clean Code, Naming Craft & Modularity Skill

Write and refactor code so any engineer opening a file understands it in 10 seconds with zero guesswork (`Rule 02`).

## 1. Core Cleanliness Standards

1. **Intent-Revealing Naming (`VerbNoun`, Semantic Booleans, Domain Nouns):**
   - Functions: `calculatePeninsularRoadTax()`, `normalizeMalaysianPlate()`, `buildUnifiedAddonSlots()`. Ban `handleData()`, `processItem()`, `doCheck()`, `tempHelper()`.
   - Booleans: `is_published`, `has_active_covernote`, `can_generate_pdf`, `requires_manual_check` (`is_/has_/can_/should_/requires_`).
   - Collections: plural domain nouns (`selected_coverages`, `unmatched_benefit_keys`) — never `list1`, `data_rows`.
2. **Flat Control Flow & Early Returns (`Nesting Depth <= 3`):**
   - Validate preconditions and fail fast with guard clauses (`if not plate: raise ValidationError(...)`, `if quote.is_locked: return ...`). Never nest 4–6 levels of `if / for / if / try`.
3. **Cohesive Unit Sizing:**
   - Function length target: `<= 40–60` lines with ONE clear responsibility.
   - Python modules: target `<= 300` lines per logical module (`<= 600` hard cap before extraction).
   - React TSX components/hooks: target `<= 250–400` lines (`<= 600` hard cap).
4. **Zero Parallel `_v2` / Duplicate Helper Slop:**
   - Extend/fix the canonical module in place (`lib/api.ts`, `lib/utils.ts`, `benefit_evaluation_engine.py`). Never copy-paste a second formatter or spawn `helpers_v2.ts`.
5. **Typed Errors, Zero Silent Swallows:**
   - Catch specific exceptions (`HTTPException`, `SQLAlchemyError`, `ValueError`), log safe masked context, and propagate or transition explicitly to `Check Needed`. Ban bare `except Exception: pass` or defaulting silently to `"etiqa"`.
6. **Dead Code Hygiene:**
   - Remove unused imports, unreachable branches, and orphaned files cleanly. Annotate intentionally disabled blocks with `// RL-DISABLED <feature> — disabled YYYY-MM-DD; restore when <reason>`.

## 2. Slicing Recipe (Breaking Monoliths Without Breaking Imports)

Load `references/naming-slicing-patterns.md` when decomposing existing large files (`review-phase.tsx`, `benefits-manager-panel.tsx`, `comparison-matrix.tsx`, `workspace_service.py`) into clean cohesive modules.

