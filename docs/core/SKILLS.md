# Agent Skills Registry, Repo Plugins & Cold Archive Contract

Load an **Agent Skill** cleanly via `using-superpowers` (`1%` threshold; **Fast Track** single-file CSS/copy tweaks skip heavy ceremony). Read the target `SKILL.md` completely before executing. Skills never override `AGENTS.md`, `docs/domain/BUSINESS-RULES.md`, tests, or owner decisions.

---

## 1. Two-Tier Storage & Repo Plugins Inside `.agents/`

Every repository skill and repo-scoped UI plugin lives inside **`.agents/`** (`commands/skills-manager.py`, `.agents/skills-lock.json`, `.agents/plugins/`):

| Layer | Location | Purpose | Prompt Token Impact |
| :--- | :--- | :--- | :--- |
| **Active Agent Skills** | `.agents/skills/<name>/` | Deep multi-file active skills auto-discovered at startup (`<= 50` soft cap under Max-Force Gemini 3.8 Flash High mode; live count in `docs/generated/SKILLS-INDEX.md`) | Compact metadata |
| **Cold Skill Archive** | `.agents/skills-vault/<category>/<name>/` | Dormant packs (marketing/scroll UI, standalone Playwright CLI; live count in `docs/generated/SKILLS-INDEX.md`) ready to `mount` | **0 boot tokens** until mounted |
| **Repo-Local UI Plugins** | `.agents/plugins/{risklocker-ui,ui-21st-dev}/` | Zero-key `shadcn@latest mcp` registry (enabled) + opt-in `21st.dev` (disabled) | Scoped to UI plugin toggles |
| **Live Inventory** | [`docs/generated/SKILLS-INDEX.md`](../generated/SKILLS-INDEX.md) | Auto-generated complete Active + Cold catalog, token estimate & scope | Auto-synced (`skills-manager.py index`) |

## 2. Category Routing Map (Active Skills + Cold Vault — see `SKILLS-INDEX.md`)

- **Governance, Freshness & Dispatch:** `using-superpowers`, `company-dispatch`, `dispatching-parallel-agents`, `live-reality-and-deprecation-gate`, `requesting-code-review`, `receiving-code-review`, `finishing-a-development-branch`
- **Architecture, Clean Code, Reality & Planning:** `brainstorming`, `writing-plans`, `system-design-and-architecture`, `domain-interrogation-and-reality-gate`, `parallel-variant-tournament`, `clean-code-and-refactoring`, `postgres-ledger-migrations`
- **Backend Testing, Debugging, Security & Domain:** `systematic-debugging`, `test-driven-development`, `python-testing`, `edge-case-and-scenario-matrix`, `verification-before-completion`, `security-best-practices`, `security-threat-model`, `malaysian-motor-insurance`
- **Enterprise UI, Mobbin + `shadcn` & PDF Parity:** `enterprise-product-ui`, `apple-design`, `frontend-design`, `shadcn`, `web-design-guidelines`, `design2-pdf-parity`
- **Browser & E2E Verification:** `webapp-testing`, `playwright`, `playwright-best-practices`, `agent-browser`
- **Cold Vault (`.agents/skills-vault/`, 0 Boot Tokens — `mount` on demand):** `design-taste-frontend`, `gsap-framer-scroll-animation`, `playwright-cli`, `playwright-explore-website`, `playwright-automation-fill-in-form`

## 3. Repo-Local Default Rule & Daily Commands

- **Repo-Local Default (Mandatory):** Never install skills globally (`-g`, `--global`, `~/.gemini`, `~/.claude`, `~/.codex`, `~/.copilot`, `~/.agents`) unless the owner explicitly orders a global install. Always install into this repo using `commands/skills-manager.py`:
  - Add local or `npx` skill to Active: `.\.venv\Scripts\python.exe commands/skills-manager.py install <path_or_pkg> [--from-npx] --scope universal`
  - Add directly to Cold Vault (`0` boot tokens): `... install <path_or_pkg> --cold --category <cat>`
  - Mount / unmount packs for a sprint: `.\.venv\Scripts\python.exe commands/skills-manager.py mount <name_or_cat>` / `unmount <name_or_cat>`
  - Audit stray folders, broken links & lockfile freshness: `.\.venv\Scripts\python.exe commands/skills-manager.py doctor`
  - Opt-in workstation NTFS junctions (if using legacy Claude/Cursor): `.\.venv\Scripts\python.exe commands/sync-agent-bridges.py --write --ide claude,cursor`
