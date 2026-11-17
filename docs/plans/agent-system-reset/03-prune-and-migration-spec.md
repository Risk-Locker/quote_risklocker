# Prune and Migration Spec

Every action is reversible through git. Nothing is deleted outside this list. Execute one milestone at a time (see `00-master-plan.md`).

## 1. Rules (`.agents/rules/`)

| File | Size | Action | Where the content goes |
| :-- | :-- | :-- | :-- |
| `00-suggestive-evaluation-gate.md` | 1.1 KB | Delete | One line in the core: "Before adding a dependency, compare 2 options and choose the smaller" |
| `01-company-chain-of-command.md` | 0.8 KB | Delete | Duplicate of `AGENTS.md` invariants 1 and 6 |
| `02-anti-slop-and-modularity.md` | 2.9 KB | Delete | Invariant 6. Size limit becomes one number: 600 lines per file for new code. Naming advice already lives in `clean-code-and-refactoring` skill |
| `03-enterprise-ui-simplicity.md` | 2.1 KB | Keep, trim to 1.2 KB | Stays `model_decision`. Remove the states checklist (the `baseline-ui` skill has it) |
| `04-skill-vault-and-local-scope.md` | 1.5 KB | Delete | Three lines go into .agents/skills/README.md: repo-local installs only, use `skills-manager.py` |
| `05-live-reality-and-freshness.md` | 2.4 KB | Delete | Invariant 8, and the edge matrix stays in its skill |
| `06-serialized-milestones-and-authentic-verification.md` | 10.1 KB | Delete | Task classes in the core, milestone sizes in profiles, gauntlet becomes `gate.py full`, spec audit moves to docs/domain/AI-LIMITS.md and `BUSINESS-RULES.md` |
| `OVH_SSH.local.md` | 0.8 KB | Change trigger to `manual` | No content change |

Result: always-on rules go from about 28 KB to about 3 KB (core) plus 1.2 KB (UI rule, loaded on demand).

Other always-on files:
- `.agents/plugins/risklocker-ui/rules/AGENTS.md` (0.9 KB): merge its 4 lines into Rule 03. Delete the plugin rule file.
- `.agents/plugins/ui-21st-dev/rules/AGENTS.md` (0.7 KB): check if the plugin is used. If not, delete the folder.
- Per-folder `AGENTS.md`: remove sentences that repeat the core. Target 1.5 KB each.

## 2. Role subagents (`.agents/agents/`, 9 files, 38 KB)

Rule 01 says no roleplay. The nine numbered "company roles" are roleplay. Proposal:

| Keep (renamed, trimmed to 2 KB each) | Merge from |
| :-- | :-- |
| `planner` | `01-orchestrator-pm`, `03-mentor-architect` |
| `backend` | `06-backend-ledger-lead`, `08-ai-extraction-lead` |
| `frontend` | `05-principal-designer`, `07-frontend-ux-lead` |
| `verifier` | `04-security-auditor`, `09-qa-and-janitor-gate` |

`02-falcon-scout` is replaced by the built-in `research` subagent. Role files keep `model: inherit`.

## 3. Hooks (`.agents/hooks/`)

| File | Action |
| :-- | :-- |
| `daily_radar.py` | Keep. `deploy.yml` line 90 runs it |
| `freeze_and_path_guard.py` (33 KB), `static_security_tripwire.py`, `session_start_guard.py`, `brain_stop_guard.py` | All disabled in `hooks.json`. Delete the four scripts and their `hooks.json` entries. Keep `hooks.json` as `{}` |
| `.agents/logs/tripwire-alerts.archive.log` (407 KB) | Delete. Keep `.gitignore` entry |
| `.agents/proposals/*` | Close out the four radar audit files, then delete. Keep `README.md` |
| `STALE_SPLIT_RE` in `daily_radar.py` | Remove the check that polices `STATE.md` wording, so docs no longer need to avoid certain characters |

Before deleting: `rg "freeze_and_path_guard|session_start_guard|brain_stop_guard|static_security_tripwire"` across the repo, CI files and `commands/`. Fix every hit.

## 4. Skills (21 active, 96 in the vault)

Use `commands/skills-manager.py unmount <name>` (exists) so nothing is deleted.

| Group | Skills | Action |
| :-- | :-- | :-- |
| Keep active (10) | `edge-case-and-scenario-matrix`, `malaysian-motor-insurance`, `design2-pdf-parity`, `postgres-ledger-migrations`, `python-testing`, `test-driven-development`, `systematic-debugging`, `shadcn`, `playwright`, `security-best-practices` | Trim the largest to 4 KB |
| Unmount to vault (11) | `emil-design-eng` (28 KB), `forms-inputs-checkout` (26 KB), `design-systems-frontend-architecture` (22 KB), `better-layout`, `baseline-ui`, `agent-browser`, `writing-plans`, `requesting-code-review`, `verification-before-completion`, `system-design-and-architecture`, `clean-code-and-refactoring` | Mount when a task needs them |
| Rewrite descriptions | All active | Name the exact trigger, for example "Use when editing `backend/app/services/*comparison*`" so a weak model does not load it by accident |

After the change, run `skills-manager.py index`.

## 5. Docs diet

| File | Now | Target | How |
| :-- | :-- | :-- | :-- |
| `docs/core/STATE.md` | 42.8 KB | 6 KB or less | Rotate entries older than 14 days to `docs/history/MEMORY-2026-11.md`. Keep one line per milestone, maximum 160 characters |
| `docs/core/START-HERE.md` | 23.3 KB | 8 KB or less | Keep the routing table. Move the long prose to the topic docs |
| New docs/domain/AI-LIMITS.md | n/a | 1 KB | One table: model IDs, RPM, TPM, RPD, with the source file named. Replace every copy in rules |

Check `commands/verify-brain.py` for hard-coded size or link expectations before rotating. Update it in the same milestone so the CI step does not fail.

## 6. commands/gate.py (new, about 120 lines)

Wraps existing scripts. It must print a table of 12 lines or fewer so a model reads little.

| Mode | Runs | Notes |
| :-- | :-- | :-- |
| `quick` | `pytest -q` on tests matching changed backend paths (from `git diff --name-only`), `tsc --noEmit` if `frontend/` changed, `npm run lint` if `frontend/` changed | Under 2 minutes target |
| `full` | `commands/verify-deploy-gate.ps1` (already runs 10 steps: pytest, tsc, build, migrations, code map, brain, radar and others) plus `security-audit.py` compared with a stored baseline | Fails only on new findings. The audit currently reports 98 critical, so absolute zero is not a usable gate |

Output example:
```
GATE quick  PASS
 pytest   42 passed  (tests/unit/test_x.py ...)
 tsc      skipped (no frontend change)
 lint     skipped
```
Add tests/unit/test_gate_selection.py that checks changed-path to test mapping with a fake `git diff` list.

## 7. Rollback

Each milestone is one commit. Roll back with `git revert <commit>`. R1 keeps the old rules in git history only, so the first step of R1 is a tag: `git tag agents-legacy-2026-11-17`.

