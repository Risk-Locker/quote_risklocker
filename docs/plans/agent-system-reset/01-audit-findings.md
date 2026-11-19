# Agent System Audit (2026-11-17)

Method: file sizes measured with PowerShell, rule text read in full, hooks and CI inspected, rule trigger types checked against the Antigravity rules guide. Nothing was changed.

## 1. What is loaded and what it costs

| Layer | Files | Size | Loaded when |
| :-- | :-- | :-- | :-- |
| Always-on rules (`.agents/rules` 00,01,02,04,05,06 + OVH local) | 7 | 19.5 KB | Every turn |
| Root `AGENTS.md` + plugin `AGENTS.md` | 3 | 8.5 KB | Every turn |
| Per-folder `AGENTS.md` (backend, frontend, migrations) | 3 | 6.1 KB | When working in that folder |
| Skills (21 active, descriptions always, body on trigger) | 21 | 163 KB (SKILL.md only) | Description always; body on demand |
| Role subagents (legacy agents dir) | 9 | 38 KB | Listed every turn |
| Hooks | 5 scripts | 64 KB | All four lifecycle hooks are `enabled: false`; only `daily_radar.py` is used (by CI) |
| Logs and proposals | 8 | 410 KB | Never useful to a model (400 KB is one archive log) |
| Skills vault (dormant) | 96 | 767 KB | Never, unless mounted |
| `docs/core/STATE.md` | 1 | 42.8 KB (63 lines, very long lines) | When the agent reads it |
| `docs/core/START-HERE.md` | 1 | 23.3 KB | When the agent reads it |

Always-on text is about 28 KB, roughly 7K tokens. That is a minority of a 100K budget, so rule size alone does not explain the hallucination. The bigger costs are in the next sections.

## 2. Findings

### F1. No task-size tiering in the always-on rules
Rule 06 section 2 says "every verification pass MUST" run a 5-stage forensics loop: live API gauntlet, 4 RBAC personas, browser at 3 viewports times 3 zooms, spec audit, 10-point matrix. It has no exemption for small tasks. A one-line fix therefore triggers the full ceremony. Fast Track exists only inside the `01-orchestrator-pm` subagent, which is not loaded in a normal chat. This is the main cause of "5 minutes for one simple task".

### F2. The same rule is written two or three times
| Rule | Where it repeats |
| :-- | :-- |
| Verification gauntlet | `AGENTS.md` section 3, Rule 06 section 2 |
| 10-point edge matrix | Rule 05 section 3, Rule 06 stage 5, `edge-case-and-scenario-matrix` skill |
| Fresh-chat handover and 250K threshold | `AGENTS.md` principles 6 and 7, Rule 06 section 4 |
| Token telemetry "on demand only" | `AGENTS.md`, Rule 05, Rule 06 |
| Zero hardcoding | `AGENTS.md` section 1, Rule 01 |

Repeats waste tokens, and they drift apart. A weak model that sees two slightly different versions picks one at random.

### F3. Direct contradictions
| Conflict | Evidence |
| :-- | :-- |
| 300 vs 600 line limit | Rule 02 says "<= 300 (<= 600 max)" in one bullet and "<300 / <600" in its header. `AGENTS.md` says 300 for React. The security audit flags at 600 |
| "No bureaucratic roleplay" vs 9 numbered role agents | Rule 01 vs `.agents/agents/01..09` |
| "Never cite model IDs from memory" vs hardcoded model IDs | Rule 05 vs `AGENTS.md` and Rule 06 (`gemini-3.1-flash-lite`, 13 RPM, 200k TPM, 480 RPD written into the rules) |
| "Skip nothing, run all layers" vs "tiny bugfix" | Rule 06 vs Rule 02 reality table |
| `STATE.md` under 80 lines | It is 63 lines but 42.8 KB. The line cap is met and the intent (small file) is not |

### F4. Stale and broken references
- `freeze_and_path_guard.py` cites "AGENTS.md section 4 workspace containment". `AGENTS.md` ends at section 3.
- Rule 04 says "uncapped Gemini 3.8 Flash High rigor mode". The system is tuned to one model.
- `STATE.md` content is policed by a regex in `daily_radar.py` (`STALE_SPLIT_RE`). The roadmap had to warn agents not to write certain characters. A doc style rule enforced by a hook regex is a fragile design.
- All four hooks are disabled but still shipped. `session_start_guard.py` and `brain_stop_guard.py` assume freeze locks and an 80-line cap that no longer drive behaviour.

### F5. Process is described in prose, so a model has to remember it
The gate steps (`pytest`, `tsc`, `lint`, `build`, `verify-brain`, code map, radar, security audit) exist as separate commands. A model has to remember all of them and run them in order. A single command that runs them and prints a short table would remove that dependence on model memory. Flash needs this most.

### F6. Skills are too heavy and overlap
- `emil-design-eng` 28 KB, `forms-inputs-checkout` 26 KB, `design-systems-frontend-architecture` 22 KB. One wrong trigger puts about 7K tokens into context.
- Overlap with global skills: `baseline-ui` vs `better-ui`, `playwright` vs `agent-browser`, `writing-plans` vs `executing-plans`, `shadcn` vs `building-components`.
- Generic descriptions ("Use when designing forms...") mean a weak model triggers them on unrelated tasks.

### F7. Context hygiene numbers assume a large-context model
The 250K-token handover threshold is useless for Flash. The owner reports it behaves like a 100K model.

### F8. Machine-local rule is always on
`OVH_SSH.local.md` (a root login to a production IP) is loaded every turn. It is gitignored, so it is not leaked. It should be manual-trigger so it is only read when the user asks about the server.

### F9. No measurement
There is no benchmark that shows whether a rule change helped. Every rule is added on belief.

## 3. What is good and should stay

- The business invariants (backend `Decimal` is the only source of math, no mutating GET, `Numeric(12,2)`, rules in the database, hermetic tests). They are correct and cheap to state.
- `edge-case-and-scenario-matrix`, `malaysian-motor-insurance`, `design2-pdf-parity`, `postgres-ledger-migrations`, `python-testing`, `test-driven-development`, `systematic-debugging`. These carry domain knowledge or a real method.
- Per-folder `AGENTS.md` files.
- `daily_radar.py` (CI depends on it), `verify-brain.py`, `security-audit.py`, `update-code-map.py`.


