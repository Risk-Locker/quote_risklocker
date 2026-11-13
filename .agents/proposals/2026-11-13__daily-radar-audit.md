# Daily Self-Audit Proposal — 2026-11-13

> Generated `2026-11-13T09:00:07+08:00` by `.agents/hooks/daily_radar.py`. **Requires Owner Approval — zero auto-edits applied.**

## Internal Harness & Hygiene Signals
- 979 static security/anti-slop tripwire alert(s) logged in `.agents/logs/tripwire-alerts.log`.
- Rule `.agents/rules/06-serialized-milestones-and-authentic-verification.md` missing Antigravity `trigger:` frontmatter.

## Freeze-Deferred Runtime Deprecation Signals
- Deprecated/shutdown Gemini model IDs detected in runtime app code (19 occurrences): `backend/app/api/routers/copilot.py:483` (`gemini-3.1-flash-lite-preview`), `backend/app/api/routers/copilot.py:483` (`gemini-3.1-flash-lite-preview`), `backend/app/api/routers/sessions.py:1132` (`gemini-3.5-flash`), `backend/app/api/routers/sessions.py:1132` (`gemini-3.5-flash`), `backend/app/api/routers/system.py:886` (`gemini-3.1-flash-lite-preview`), `backend/app/api/routers/system.py:946` (`gemini-3.1-flash-lite-preview`) (+13 more — see `.agents/proposals/2026-11-11__backend-gemini-model-deprecation-audit.md`)

## Upstream Ecosystem Changes Detected
- None detected since baseline.

## Recommended Next Step
- Review signals above; apply via an approved plan or dismiss cleanly.
