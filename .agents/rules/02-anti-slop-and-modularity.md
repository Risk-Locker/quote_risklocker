---
trigger: always_on
description: Clean code craft, pure Decimal core, unified 600-line ceiling for new modules, and zero *_v2 slop.
---
# Rule 02: Clean Architecture & Anti-Slop Gate

1. **Intent-Revealing Code & Guard Clauses:**
   - Use clear domain names (`calculateRoadTax`, `resolveSpecialPerils`, `is_manual`) and flat guard clauses (`depth <= 3`).
2. **Pure Core, Imperative Shell:**
   - Keep tax, NCD, betterment, and ledger math in pure backend `Decimal` functions (zero client-side math in React; zero `float` on monetary columns).
3. **Modular File Budget & Legacy Pragmatism:**
   - Keep **new** Python and React modules `<= 600` lines (`<= 300` target for services).
   - When fixing a targeted bug inside a legacy file (`> 600` lines), apply the clean cohesive fix or extract only the touched helper—do not derail a bugfix into an unrequested 2,000-line rewrite unless slicing is part of the milestone.
   - Never create parallel `*_v2.py` or `helpers_extra.ts` duplicates. Remove unused imports and dead code you touch.
