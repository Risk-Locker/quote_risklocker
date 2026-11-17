---
trigger: always_on
description: Model-tiered milestone execution (Argon/Hydrogen vs Claude vs 3.8 Flash), task-size verification gates, and Knowledge Base sync.
---
# Rule 06: Model-Tiered Milestones & Verification Gate

## 1. Model-Aware Milestone Execution

Match milestone sizing and checkpoint pacing to the active AI model profile (`.agents/profiles/`):

| Tier | Models | Milestone Budget | Execution Pacing | Handover Ceiling |
| :--- | :--- | :--- | :--- | :--- |
| **`deep`** | **Gemini 4 Argon**, **Gemini 4 Hydrogen**, **Orchestrator** | Up to `1,200–1,500 LOC` or full cohesive subsystem | Can run single milestones OR execute an approved multi-milestone roadmap sequentially in one go (`M1 -> verify -> M2 -> verify`) when requested. Pause only on ambiguity or destructive DB actions. | `350k–450k` tokens |
| **`balanced`** | **Claude Sonnet 5.5**, **Claude Opus 5.5**, **GPT-OSS** | Up to `800–1,000 LOC` (1–2 subsystems) | Execute 1 milestone (or tightly coupled pair) per turn, verify, and report evidence. | `200k–250k` tokens |
| **`flash`** | **Gemini 3.8 Flash** | `<= 300–400 LOC` (1 subsystem only) | Strict single-milestone execution. Read files in `<= 200`-line chunks. Stop and hand over after each milestone. | `~80k` tokens (`~40` tool calls) |

## 2. Task-Size Verification Matrix

Never run a 10-minute verification ceremony on a 5-line fix, and never skip live verification on a `HEAVY` feature:

1. **`QUICK` (`<= 3` files, isolated fix / UI copy, no schema/math/RBAC):**
   - Run the single relevant `pytest` file or `npx tsc --noEmit`. Done immediately.
2. **`STANDARD` (`4–10` files, single subsystem):**
   - Failing hermetic test first -> Targeted `pytest` -> `cd frontend; npx tsc --noEmit` -> `python commands/verify-brain.py` -> Append 1 concise line to `docs/core/STATE.md` (keep `< 80` lines).
3. **`HEAVY` (Schema migration, `Decimal` actuarial math, RBAC/CSRF, or cross-layer milestone):**
   - Complete the 10-point Edge-Case Matrix (`.agents/skills/edge-case-and-scenario-matrix/SKILL.md`) before coding.
   - **Invariant Checks:** Zero client-side math in React; `Numeric(12, 2)` money columns; zero mutating `GET` routes; `require_role` + CSRF on writes; exact calendar betterment age (`relativedelta.years`); Design 2 24-card boundary & in-place towing upgrade; `is_sandbox` isolation.
   - **Live Operational Check:** When touching API/UI flows, verify against live backend (`http://127.0.0.1:8100`) and browser (`http://127.0.0.1:3000`, zero `console.error`, zero red error toasts).
   - **Full Harness:** `.\.venv\Scripts\pytest.exe tests/`, `cd frontend; npx tsc --noEmit`, `python commands/verify-brain.py`, and `python commands/update-code-map.py --write` (when symbols/routes change).

## 3. On-Demand Telemetry & Handover
- Run `commands/chat-token-telemetry.py` ONLY when requested or approaching your profile's handover ceiling.
- At milestone completion or handover ceiling, provide a concise evidence recap and the exact copy-paste command for a fresh chat (`Ctrl+L` -> `Run docs/plans/...`).
