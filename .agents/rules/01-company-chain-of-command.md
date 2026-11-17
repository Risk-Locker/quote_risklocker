---
trigger: always_on
description: Direct execution, search-before-naming grounding, and zero hardcoding discipline.
---
# Rule 01: Direct Execution & Anti-Hallucination Discipline

1. **Direct, Fast Execution:**
   - Match ceremony to task size (`QUICK` `<= 3` files = direct read -> edit -> 1 test -> done; `STANDARD` = TDD + targeted gate; `HEAVY` = milestone plan + full verification).
   - Adapt execution capacity to your active model profile (`.agents/profiles/deep.md` for **Gemini 4 Argon / Hydrogen**, `.agents/profiles/balanced.md` for **Claude Sonnet / Opus 5.5**, `.agents/profiles/flash.md` for **Gemini 3.8 Flash**).
2. **Search-Before-Naming:**
   - Verify every database column, API route, schema attribute, and component prop in code before referencing or editing it. Never guess identifiers from memory.
3. **Zero Hardcoding & Clean Garbage Collection:**
   - Keep underwriter rules, company names, towing limits, and rate schedules in PostgreSQL tables/seeds, never in hardcoded `if/elif` branches.
   - Delete temporary scratch scripts immediately after verification.
