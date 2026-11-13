---
name: parallel-variant-tournament
description: Push Gemini 3.8 Flash (High) to maximum accuracy via parallel branch swarm variants, adversarial fuzz/SAST scoring, minimal-LOC pruning, and reference cross-checks.
---

# Parallel Variant Tournament (`Max-Force Gemini 3.8 Flash`)

Single-pass generation leaves bugs behind. Use **parallel Test-Time Compute** via `swarm` (`model: "gemini-3.8-flash-high"`, `workspace: "branch"`) on every core engine, security fix, database migration, or high-complexity refactor — regardless of token spend.

## 0. Freeze Pre-Flight Gate
Inspect `.agents/.freeze.lock` before spawning any write-enabled branch worker. If `enabled: true`, halt implementation branches touching locked paths (`backend/app/`, `frontend/src/`, `migrations/`, `tests/`) and emit `.agents/proposals/` designs only.

## 1. Grounding & Shared Red-First Test Anchor (BEFORE Forking Branches)
1. **Reference Grounding (`02-falcon-scout`):** Verify upstream idioms via `search_web` and request Chief of Staff MCP lookups (`context7_context7` pinned to Risklocker versions + `github` `search_code`) — extract proven invariants cleanly without cargo-culting bloat.
2. **Lock the Target Test Oracle (`09-qa-and-janitor-gate`, `workspace: "inherit"`):** BEFORE spawning implementation branches, `09` authors the failing Red-First regression test + 10-dimension boundary/fuzz assertions on the shared baseline so all competing branches are judged against an identical, immutable oracle.

## 2. Competing Implementation Swarm (`swarm`, `workspace: "branch"`)
Fork ONLY implementation variants from the shared Red-First baseline commit (`model: "gemini-3.8-flash-high"`):

| Swarm Worker | Branch Focus | Optimization Target |
| :--- | :--- | :--- |
| `variant-minimal` | Pure functional core + lookup tables | **Minimum LOC**, flat guard clauses (`<= 3` depth), zero clever tricks |
| `variant-hardened` | Defensive state machine + DB lock safety | **Maximum edge-case, concurrency & failure-recovery armor** |
| *(Optional `variant-domain`)* | Clean DDD / modular slice architecture | Alternative modular split for complex multi-file workflows |

## 3. Hard Lexicographic Tournament Scoring Gates (`03` + `04`)
`09-qa-and-janitor-gate` runs `pytest` + `commands/security-audit.py --strict --with-external --json` against each surviving branch and hands verbatim outputs to read-only **`03-mentor-architect`** and **`04-security-auditor`** to score strictly in order:

1. **Gate 1 — 100% Correctness (Pass/Fail Disqualifier):** Must pass `100%` of `09`'s Red-First + boundary/fuzz tests (`0` failures, zero mocked-away assertions).
2. **Gate 2 — 0 Security Blockers (Pass/Fail Disqualifier):** Must score `0` `CRITICAL`/`HIGH` findings in `commands/security-audit.py --strict --with-external --json` (`04-security-auditor` veto) and `0` tripwire alerts.
3. **Rank 1 — Minimal Footprint & Complexity (Winner Picker):** Lowest net `delta-LOC` within budget (`<= 300L` Python / `<= 600L` TS), lowest max nesting depth (`<= 3`), zero dead code or duplicated client math.
4. **Rank 2 — Query Efficiency Tie-Breaker:** Fewest indexed SQL queries on critical paths (zero `.all()` scans; explicit row locking where required).

### Required `03`/`04` Scorecard Block
| Branch | Gate 1 (Tests) | Gate 2 (`04` SAST) | Net `delta-LOC` | Max Depth | SQL Queries | Verdict |
| :--- | :--- | :--- | ---: | ---: | ---: | :--- |
| `variant-minimal` | `PASS/FAIL` | `PASS/BLOCKED` | `+N/-M` | `<=3` | `K` | `WINNER / PRUNE` |
| `variant-hardened` | `PASS/FAIL` | `PASS/BLOCKED` | `+N/-M` | `<=3` | `K` | `WINNER / PRUNE` |

## 4. Winner Landing, Pruning & Branch Cleanup
1. Merge ONLY the winning cleanest variant (or minimal synthesis approved by `03`) into the active branch.
2. Prune dead helpers and run one simplification pass via `clean-code-and-refactoring`.
3. Cleanly terminate swarm workers (`swarm kill`) and delete losing temporary worktrees/branches per `finishing-a-development-branch`, then run full `04` read-only veto + `09` `verify-deploy-gate.ps1` (`10/10`).
