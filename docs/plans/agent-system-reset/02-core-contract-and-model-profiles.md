# Core Contract and Model Profiles (draft text)

This file contains the proposed replacement text. Nothing here is active until milestone R1 is approved and executed.

## 1. How model-specific rules work

Antigravity rules have trigger types `always_on`, `model_decision`, `glob` and `manual`. There is no per-model trigger. The design therefore uses two layers:

1. One small `always_on` core (target 3 KB or less). It is written so Gemini 3.8 Flash can follow it safely, because Flash is the weakest reader. Every model gets it.
2. Three profile files in .agents/profiles/. The core tells the agent: "Find your model name in the session, read the matching profile (one file read). If unsure, use `flash`."

Model to profile map:

| Model | Profile | Why |
| :-- | :-- | :-- |
| Gemini 3.8 Flash (any effort) | `flash` | Cheap, small effective context, hallucinates under load |
| Claude Sonnet 5.5, Claude Opus 5.5, GPT-OSS | `balanced` | Reliable, token-frugal, moderate fan-out |
| Gemini 4 Argon, Gemini 4 Hydrogen, Orchestrator (Argon) | `deep` | Heavy autonomous work, parallel agents, large milestones |

The `deep` profile for Hydrogen and Argon is based on the owner's description. Milestone R5 measures it before the numbers are trusted.

Quota data seen on 2026-11-17 (from the `swarm models` tool): Argon 100% with a weekly reset, Hydrogen and Flash 43% and Claude 56% with hourly-scale resets. The `deep` profile therefore routes long autonomous runs to Argon first.

## 2. Draft `AGENTS.md` (replaces the current 6.9 KB root file)

```markdown
# Risklocker Agent Contract

Stack: FastAPI + PostgreSQL (`backend/`), Next.js 15 + React 19 (`frontend/`). Flow: DB -> services -> API -> UI.

## Start of every task
1. Find your model name in the session. Read `.agents/profiles/<flash|balanced|deep>.md`. Unsure: read `flash`.
2. Classify the task (table below).
3. Read the code you will change before you describe or edit it. Cite `path:line`. Never state a function, column or endpoint from memory. If search finds nothing, say "not found".

## Task size
| Class | Test | What to do |
| :-- | :-- | :-- |
| QUICK | 3 files or fewer, no schema, money, auth or PDF | Read, edit, run the one relevant test. No plan file. No docs sweep |
| STANDARD | 4-10 files or one subsystem | Plan in chat (10 lines), failing test first, `python commands/gate.py quick`, one line in `docs/core/STATE.md` |
| HEAVY | Schema, money math, auth, cross-layer, or more than 10 files | Plan file in `docs/plans/`, 10-point edge matrix (`edge-case-and-scenario-matrix` skill), milestones sized per profile, `gate.py full`, live browser check, stop for owner review |

## Invariants (never break)
1. Business rules (rates, limits, insurer terms) live in the database, not in `if` branches or React.
2. Money and tax math is backend `Decimal` only. The frontend renders what the API returns. Money columns are `Numeric(12,2)`.
3. `GET` never writes (no commit or flush).
4. Every write route has `require_role` and CSRF.
5. Tests are hermetic (in-memory SQLite and mocks). Never write to the live database from a test or script.
6. No parallel `*_v2` files. Delete dead code you create. Check `frontend/src/components/ui/` before adding a primitive.
7. UI follows `docs/architecture/DESIGN-SYSTEM.md` (`--rl-*` tokens). UI changes need a live check in the browser, not only a type check.
8. Model IDs and rate limits come from `backend/app/core/config.py` and docs/domain/AI-LIMITS.md. Never from memory.

## Stop and ask
- The request has two reasonable readings.
- The change is destructive (data delete, force push, migration on live data).
- You would need to touch files outside the stated scope.
- Two attempts to fix the same failure did not work. Report what you tried. Do not loop.

## Gate
`python commands/gate.py quick` after STANDARD work. `python commands/gate.py full` before commit on HEAVY work. Do not claim "done" without pasting the gate summary.

## Context
Follow the limits in your profile. At the limit, write the handover (what is done, what is next, exact files) and ask the owner to start a fresh chat.
```

Target size: under 3 KB. Everything else in the old Rule 00 to 06 is either moved into a profile, moved into a skill, or dropped (see `03-prune-and-migration-spec.md`).

## 3. Draft .agents/profiles/flash.md

```markdown
# Profile: flash (Gemini 3.8 Flash)

You are cheap and fast but lose accuracy when context grows. These rules protect you.

## Limits
- Assume 100K usable context. After about 40 tool calls, or if you re-read the same file twice, write the handover and ask for a fresh chat.
- Final answers: 10 lines or fewer. Lead with the result.

## Reading
- Read in line ranges of 200 lines or fewer. Never open `STATE.md`, `START-HERE.md` or a file over 600 lines in full. Search first, then read the matching range.
- Before every edit, state in one sentence what you will change and the `path:line`. After the edit, re-read the changed range.

## Anti-hallucination
- Search before you name anything: function, column, endpoint, prop, setting. No hit means "not found". Ask. Do not invent.
- Anything you did not read or run this session is "unverified". Say so.
- Do not claim a test passed unless you ran it and saw the output.

## Scope
- QUICK and STANDARD only. For HEAVY work, stop and propose a split into milestones of 300 changed lines or fewer, one subsystem each, and recommend running the work on a `deep` or `balanced` model.
- No subagents, no swarm, no web search, unless the owner asks.
- One failed fix attempt: re-read the error. Second failure: stop and report.

## Output hygiene
- Do not rewrite docs or rules unless asked. Do not add files outside the task.
```

## 4. Draft .agents/profiles/balanced.md

```markdown
# Profile: balanced (Claude Sonnet / Opus, GPT-OSS)

## Limits
- Plan on 200K usable context. Hand over at about 150K or after about 150 tool calls.
- Final answers: short. Use a table only for comparisons.

## Working style
- Run independent reads and searches in one parallel batch.
- Read targeted ranges. Do not read whole files unless you must edit most of the file.
- STANDARD work: solo. HEAVY work: write the plan file and the edge matrix first, then build.
- Milestone size: up to 600 changed lines, one or two related subsystems.
- Use a read-only research subagent when a question needs more than 10 files read, so the main context stays small.
- Review role: for HEAVY changes by another model, read the diff and the tests and report concrete defects with `path:line`.

## Verification
- STANDARD: `gate.py quick`. HEAVY: `gate.py full` plus a live browser check for UI.
- Report evidence (test counts, endpoint results). Do not report intent.
```

## 5. Draft .agents/profiles/deep.md

```markdown
# Profile: deep (Gemini 4 Argon, Gemini 4 Hydrogen, Orchestrator)

You are the heavy model. Use the full capability. Do not self-limit to small steps.

## Limits
- Plan on 500K or more usable context. Hand over at about 400K or when a milestone ends.

## Scope you own
- HEAVY work end to end in one session: plan, build, self-review, `gate.py full`, live browser check.
- Milestone size: up to 1,200 changed lines, or one whole subsystem, when the slices are cohesive. Split only at a real boundary (database, then backend, then frontend).
- Whole-subsystem refactors, including slicing oversized files, belong to you.

## Parallel work
- For independent slices (backend, frontend, tests, docs), fan out with `invoke_subagent`, `swarm` or `run_workflow`. Give each worker its own file list and a definition of done.
- Use `gemini-3.8-flash` or `claude-sonnet` workers for read-only fan-out (search, inventory, log reading). Use yourself or Claude for code that touches money, auth or migrations.
- Verify worker claims by running the tests. Treat a worker's "done" as unverified.

## Routing
- Argon holds the weekly quota pool. Put long autonomous runs on Argon. Use Hydrogen xhigh for the hardest design or debugging problems.

## Checkpoints
- Stop for owner review at milestone end when the milestone touches money, schema, auth or live data. Otherwise continue to the next milestone and report once.

## Verification
- `gate.py full`, then the live browser check with the existing `commands/qa-live-browser-verification.mjs`. Report evidence.
```

## 6. Skills the core refers to (kept, trimmed)

| Skill | Keep | Change |
| :-- | :-- | :-- |
| `edge-case-and-scenario-matrix` | Yes | Becomes the single place for the 10-point matrix |
| `test-driven-development`, `systematic-debugging` | Yes | Trim to 4 KB each |
| `malaysian-motor-insurance`, `design2-pdf-parity`, `postgres-ledger-migrations`, `python-testing` | Yes | No change |
| `verification-before-completion` | Merge | Its content becomes the `gate.py` summary rule |
| `requesting-code-review`, `writing-plans` | Keep but optional | Used by `balanced` and `deep` only |

