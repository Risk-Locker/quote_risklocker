---
trigger: model_decision
description: Repo-local skill vault management (.agents/skills vs .agents/skills-vault) when installing or mounting skills.
---
# Rule 04: Single Skill Vault & Repo-Local Scope

1. **Active vs Cold Vault:**
   - Active domain/workflow skills live in `.agents/skills/<name>/SKILL.md`.
   - Cold dormant skills live in `.agents/skills-vault/<category>/<name>/SKILL.md` at zero idle token cost and mount/unmount via `python commands/skills-manager.py`.
2. **Repo-Local Only:**
   - Always install or modify skills inside this repository (`commands/skills-manager.py`), never globally unless explicitly instructed by the owner.
