---
trigger: always_on
---
# Rule 01: Engineering Execution & Discipline

1. **Direct, Cohesive Engineering:**
   - Execute tasks cleanly and directly without multi-layered bureaucratic roleplay.
   - When touching backend Python code, respect domain boundaries and Decimal precision.
   - When touching frontend React UI, keep components modular and never duplicate calculation formulas.

2. **Zero Hardcoding Invariant:**
   - Underwriter rules, towing limits, product catalogs, and rate schedules belong in the Database (PostgreSQL / models / seed data), never hardcoded in Python `if/elif` branches or React components.

3. **Clean As You Go (Garbage Collection):**
   - No temporary milestone test files in `tests/` root.
   - Delete scratch scripts and verify end-to-end before declaring tasks complete.
