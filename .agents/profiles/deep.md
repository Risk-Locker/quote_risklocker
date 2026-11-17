# Profile: `deep` (Gemini 4 Argon, Gemini 4 Hydrogen, Orchestrator)

You are running on a frontier high-capacity reasoning model. Use your full architectural and execution capability without artificial micro-stops.

## 1. Execution Capacity & Multi-Milestone Power
- **Milestone Budget:** Up to `1,200–1,500` changed lines or an entire cohesive subsystem per milestone.
- **Continuous Multi-Milestone Execution:** When the owner asks to execute a multi-milestone roadmap "in one go", execute milestones sequentially (`M1 -> verify -> M2 -> verify -> ...`) within the same session, running targeted verification gates between slices and stopping only if:
  1. A requirement is genuinely ambiguous and affects data/financial schema, or
  2. A step requires a destructive action on live production data.
- **Parallel Tooling & Subagents:** Batch independent `read_file` / search calls in parallel. For large cross-layer tasks, you may dispatch focused subagents (`invoke_subagent`) or `swarm` workers with explicit file boundaries. Always verify subagent output with real test runs.

## 2. Grounding & Verification Discipline
- Even with large context capacity, always verify exact symbols, schemas, and line numbers before editing (`Search-Before-Naming`).
- For `QUICK` tasks (`<= 3` files), execute immediately in 1–2 turns without ceremony.
- For `HEAVY` tasks, run hermetic `pytest`, `npx tsc --noEmit`, `commands/verify-brain.py`, and live browser/API verification before declaring completion.
- **Context Handover:** Provide a fresh-chat handover (`Ctrl+L`) when active context exceeds `350k–450k` tokens or at the end of a full roadmap run.
