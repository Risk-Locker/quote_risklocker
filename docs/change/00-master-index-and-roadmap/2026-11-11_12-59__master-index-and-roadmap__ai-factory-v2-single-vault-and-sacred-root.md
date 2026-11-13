# AI Factory v2.0 Architecture Record: Sacred Root (`AGENTS.md`), 100+-Scale Single Skill Vault & Repo-Local Guardrails

> **Timestamp:** `2026-11-11 12:59` (`v30.1` Code Freeze [`f8c410a`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/docs/change/00-git-checkpoint-log.md) intact — zero production source files modified).

---

## 1. Problems Identified in Factory v1

1. **Root File Asymmetry (`CLAUDE.md` vs Universal `AGENTS.md`):**
   - Verified ecosystem status as of Sept–Nov 2026: Antigravity, Codex CLI, OpenCode V2, Cursor, Windsurf, JetBrains, Gemini CLI (via `.gemini/settings.json`), and **Claude Code `v2.1.277+`** all read `AGENTS.md` natively (while OpenCode ignores `CLAUDE.md`). Tracking `CLAUDE.md` in the root directory without `GEMINI.md` or `MINIMAX.md` created vendor asymmetry and invited root clutter.
2. **Disk Triplication & Dangling Links:**
   - Copying `.agents/skills/*` into `.claude/skills/*` and `.cursor/skills/*` multiplied directories `3x` on disk (300+ folders once 100 skills are installed), while legacy dangling NTFS junctions (`ai-image-generation`, `image-edit`) remained orphaned inside `.claude/skills/`.
3. **Token Bloat at `100+` Skills:**
   - Auto-loading 120+ skills into `.agents/skills/*/SKILL.md` inflates every prompt by ~6,000–12,000 metadata tokens, degrading weaker `120B`/Flash/MiniMax models.
4. **Silent Global Pollution & Hardcoded Catalog Lists:**
   - External installers (`npx skills add -g`, `graphify install`) can leak into `~/.copilot/`, `~/.claude/`, `~/.gemini/`, `~/.agents/`. Meanwhile [`docs/core/SKILLS.md`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/docs/core/SKILLS.md) and [`commands/init-ai-factory.py`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/commands/init-ai-factory.py) relied on manually edited tables and hardcoded lists.

---

## 2. Implemented Factory v2.0 Architecture

| Pillar | Exact Files Changed / Added | Design Behavior |
| :--- | :--- | :--- |
| **Sacred Root Symmetry** | Removed root `CLAUDE.md`, `.cursor/`, copied `.claude/` mirrors & dangling links; refactored [`commands/sync-agent-bridges.py`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/commands/sync-agent-bridges.py); appended [`.gitignore`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/.gitignore#L68-L80) | Root contains **only** `AGENTS.md` (`backend/`, `frontend/`, `migrations/` hold scoped rules; `.github/copilot-instructions.md` lives inside `.github/`). Opt-in `--ide claude,cursor,legacy-claude` creates gitignored **single directory NTFS Junctions** (zero copies). |
| **Two-Tier Single Skill Vault (`100+` Scale)** | Created [`.agents/skills-vault/README.md`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/.agents/skills-vault/README.md), [`.agents/skills-lock.json`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/.agents/skills-lock.json), [`commands/skills-manager.py`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/commands/skills-manager.py), auto-generated [`docs/generated/SKILLS-INDEX.md`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/docs/generated/SKILLS-INDEX.md) | `.agents/skills/` holds active mounted skills (`<= 35` soft cap, ~1,008 boot tokens across 21 skills); `.agents/skills-vault/<category>/` archives dormant skills at **0 boot tokens** with 1-second `mount`/`unmount` commands and auto-sanitization of `node_modules/`/`.git/`/`.cache/`. |
| **Repo-Local Skill Guardrails** | Created [`.agents/rules/04-skill-vault-and-local-scope.md`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/.agents/rules/04-skill-vault-and-local-scope.md); updated [`AGENTS.md`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/AGENTS.md), [`freeze_and_path_guard.py`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/.agents/hooks/freeze_and_path_guard.py), [`daily_radar.py`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/.agents/hooks/daily_radar.py) | `PreToolUse` hook returns `force_ask` on global skill flags (`-g`/`--global`), `graphify install`, or home-folder shell writes (`~/.gemini`, `~/.claude`, `~/.codex`, `~/.copilot`, `~/.agents`). `daily_radar.py` runs `skills-manager.py doctor --check` daily. |
| **Dynamic Portable Bootstrap** | Updated [`commands/init-ai-factory.py`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/commands/init-ai-factory.py) & [`docs/core/SKILLS.md`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/docs/core/SKILLS.md) | Reads `scope == "universal"` dynamically from `.agents/skills-lock.json` across both Active and Cold Vault tiers; `SKILLS.md` stays a durable 40-line routing contract while `SKILLS-INDEX.md` stays auto-generated. |

---

## 3. Daily Operator Commands (Quick Reference)

- Inspect active skills, vault packs & boot token budget: `.\.venv\Scripts\python.exe commands/skills-manager.py list`
- Install new skill pack locally (Active or Cold Vault): `.\.venv\Scripts\python.exe commands/skills-manager.py install <path_or_pkg> [--from-npx] [--cold] --category <cat>`
- Mount / unmount by skill name or category: `.\.venv\Scripts\python.exe commands/skills-manager.py mount <target>` / `unmount <target>`
- Run full hygiene & lockfile/index repair: `.\.venv\Scripts\python.exe commands/skills-manager.py doctor`
- Enable optional gitignored local junctions for Cursor or older Claude Code: `.\.venv\Scripts\python.exe commands/sync-agent-bridges.py --write --ide claude,cursor`

