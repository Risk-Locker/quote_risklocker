---
name: lean-context
description: Use before any code edit or investigation in a large file (>300 lines) or multi-file task, to keep reads and outputs small.
---
# Lean context procedure
1. Locate: `Select-String -Path <dir> -Pattern <symbol> -Recurse | Select -First 20`. Never open a file just to look around.
2. Read: only the matched region, `StartLine..EndLine` of at most ~120 lines. Read a second region only if the first proves insufficient.
3. Edit: one `edit_file` per contiguous block. Do not rewrite or re-paste whole files.
4. Verify: run only the one relevant test or `npx tsc --noEmit`; pipe through `Select -First 40`.
5. Reply in <=5 lines: what changed, file paths, test result. No recap of the code.
6. If the task needs broad reading of many files, stop and tell the user to switch to a cheaper model (Flash) for the exploration, or to start a fresh chat.
