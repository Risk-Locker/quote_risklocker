---
trigger: always_on
---
# Rule 04: Single Skill Vault & Repo-Local Default Scope

1. **One Physical Ecosystem (`.agents/`):**
   - Active startup skills live in `.agents/skills/<name>/SKILL.md` (`<= 50` soft active ceiling; uncapped Gemini 3.8 Flash High rigor mode).
   - Cold dormant skills live in `.agents/skills-vault/<category>/<name>/SKILL.md` at zero idle boot token cost and mount/unmount in seconds via `commands/skills-manager.py`.
2. **Strict Repo-Local Default (Zero Global Pollution):**
   - When installing or adding any skill, ALWAYS target this repository exclusively (using `commands/skills-manager.py install ...`).
   - **Never** install globally (`-g`, `--global`, `graphify install`, or writing into `~/.gemini/`, `~/.claude/`, `~/.codex/`, `~/.copilot/`, `~/.agents/`) unless the owner explicitly says `"install globally"` in that exact request.
   - Strip third-party vendor debris (`node_modules/`, `.venv/`, `.git/`, `.cache/`, stray `.claude/` or `.cursor/` drops) so every installed skill stays clean inside `.agents/`.
3. **Sacred Root Symmetry:**
   - Root `AGENTS.md` (plus `backend/AGENTS.md`, `frontend/AGENTS.md`, `migrations/AGENTS.md`) is the sole committed root instruction contract. Never commit vendor-specific root files (`CLAUDE.md`, `GEMINI.md`, `MINIMAX.md`).
   - Legacy workstation adapters (`.claude/`, `.cursor/`) remain opt-in (`commands/sync-agent-bridges.py --ide ...`), gitignored, and zero-copy via NTFS junctions.
