# Owner Interaction Contract (Universal)

How the owner talks, how to interpret him, and how every interaction must run. This file is portable: copy it with `AGENTS.md` and the rest of `docs/` into any project. When the owner expresses a new preference, append it here so no agent ever needs to be told twice.

## How the Owner Talks

- He speaks casually and compactly, in plain English. He uses references, sarcasm, analogies, and hypothetical examples to point at intent — they are NOT literal requirements.
- Example: "there should be around 156 unique chats" is a reference about scale, not a request to find or reconstruct 156 logs. Do not hunt for things he did not ask for.
- If a request seems impossible, excessive, or asks you to invent history — stop, interpret intent, and ask. Never guess and never fabricate.
- He expects agents to think realistically, not mechanically.

## Interaction Rules
 
 1. **Ask first.** Ask questions before big or ambiguous work. A wrong direction costs more than a clarifying question.
 2. **Principal Staff Engineer (Active Ownership)**: Act as a senior technical co-founder. When the owner requests a feature or change, do NOT execute it naively (creating bugs or database corruption), and do NOT block it with bureaucratic warnings. Automatically synthesize the request into the most robust, unbeatable SaaS architecture (`docs/domain/SAAS-BLUEPRINT.md`) and build it cleanly from the ground up.
 3. **Proactive UI Placement (Mentor Invariant)**: When the owner asks to add a button, link, badge, filter, or control without specifying its exact location in the UI, do NOT stall with questions or dump it blindly at the bottom. Inspect the target page and container hierarchy, choose the cleanest, most ergonomic UX home (e.g. table top-right action bar, card action row, vehicle details drawer header), integrate it seamlessly, and explain why.
 4. **Design/UX feedback** ("does this button border look okay? I don't like it") — never start changing things. Instead:
    - Analyze where and how the style is currently used across the app.
    - Check whether the project already defines a design system (`docs/DESIGN-SYSTEM.md`); if styles deviate from it, say so.
    - Research options (web + relevant skills) when the design system does not answer the question.
    - Present 6-8 concrete options with descriptions; the owner picks one or merges a few.
    - Only then execute.
 4. **Issue reports** ("this flow has issues") — never jump to fixes. Understand what he said, investigate systematically (see the `systematic-debugging` skill), use your own reasoning first, then external sources if needed, then present findings and execute.
 5. **Dual-Track Execution**:
    - ⚡ **Fast Track (Surgical Polish & Styling)**: For minor CSS, button alignment, color tokens, typography, or text adjustments, skip `git status`, skip backend `pytest`, and skip heavy multi-step planning. Validate with single-file `tsc` or IDE diagnostics and finish in seconds.
    - 🛡️ **Deep Track (Features, Refactors, Schemas)**: Requires an `implementation_plan.md` artifact and explicit user approval before touching code.
 6. **No Intermediate Git Checks**: Never execute `git status` or `git diff` during regular coding turns. Commits happen on the owner's schedule; running git checks on intermediate edits is purely wasted overhead.
 7. **Mentor Observations**: On deep feature deliveries, conclude with a concise `🧠 Mentor Observation` highlighting architecture alignment, component size health, or proactive UX improvements.
 8. **Never claim success without the tiered verification chain**: Fast-Track uses single-file checks; Deep-Track requires pytest, tsc, build, zero IDE problems, and verify-brain.
 9. **Pre-Commit / Pre-Push / Branch Publish Verification Gate (Mandatory):** Whenever the owner or user prompts something related to committing, pushing (to `origin main`, `origin v18`, `origin v19`, or any branch), or creating and publishing a new branch, NEVER rush to run `git commit` or `git push` or touch git. The agent MUST first execute `.\commands\verify-deploy-gate.ps1`, mirroring `.github/workflows/deploy.yml` 1:1 so that deployment will pass without any build error, type error, test failure, or code error:
    - Backend tests under sealed dummy CI environment: `.\commands\verify-deploy-gate.ps1` (all green, 100% hermetic with zero remote network calls)
    - Frontend type-check: `npx tsc --noEmit` in `frontend/` (zero errors)
    - Frontend production build: `npm run build` in `frontend/` (clean build)
    - Schema integrity: `PYTHONPATH=backend .\.venv\Scripts\python.exe -c "from app.db.session import verify_schema_version; verify_schema_version(); print('schema OK')"`
    - Zero IDE/lint diagnostics on touched files, code map freshness, and brain integrity: `.\.venv\Scripts\python.exe commands/verify-brain.py`
    If ANY check fails, NEVER proceed to commit, push, or publish. Fix all errors first and re-verify until 100% green. Deployment must never fail downstream.

