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

## Large-File Guardrails
- Never read a whole file over 300 lines.
- Big files (>600 lines) such as `frontend/src/app/builder/benefits/page.tsx` and `frontend/src/components/session-workspace/review-components/benefit-cards.tsx`: edit only the touched region.
- Never re-read a file that was already read in the same session unless it was modified.
- Never dump raw command output into chat; filter with `Select-Object -First 40` or `Select-Object -Last 40`.
- Prefer `Select-String` (PowerShell) or `rg -n` over directory-wide file reads.

## Examples
- Find a symbol: `Select-String -Path "backend/app" -Pattern "def get_runner_fee" -Recurse | Select-Object -First 20`
- Find a React component: `Select-String -Path "frontend/src" -Pattern "BenefitCards" -Recurse | Select-Object -First 20`
- Check TypeScript: `cd frontend; npx tsc --noEmit`
- Run a single pytest file: `.\.venv\Scripts\python.exe -m pytest tests/test_v7_domain.py -q`

## Output Discipline
- Do not summarize code you did not change.
- Cite exact file paths and observed test counts only.
- If any check was skipped or failed, state it explicitly.
