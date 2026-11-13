# Step 4 Evaluation & Architecture Verdict: External Agent Frameworks & Option 2 Autonomous Enterprise Factory

> **Code Freeze Compliant**: Authored under `v30.1` production freeze ([`f8c410a`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/docs/change/00-git-checkpoint-log.md)). Zero application source code, `.agents/`, or `.gitignore` files were modified during this evaluation. All external GitHub ecosystems were verified via live search on `2026-11-11` alongside direct local disk inspection.

---

## 1. Executive Summary (Plain-English Guide for a First-Year Student)

Imagine trying to ask a brilliant junior intern—or a smaller 120B/Flash AI model—to modify a fintech insurance system with 74 database migrations and strict accounting rules without giving them a map:
- Without structure, the weak model **guesses** database columns, picks **random hex colors**, omits permission checks (`require_role()`), breaks leap-year date math, and leaves broken leftovers everywhere (`~20/100` quality).
- Even a strong model (like Claude Opus or Gemini Pro) gets **10x more accurate** when handed exact contracts, AST call graphs, and mechanical verification gates instead of re-discovering 100+ files from scratch every chat.

This document evaluates **10 leading open-source agent ecosystems** from GitHub against **what already exists locally** in `quote_risklocker` so we **keep only proven engineering mechanisms**, **adapt what fits Windows + Risklocker**, and **reject heavy bloat**.

---

## 2. Strategic Question: `docs/` vs `.agents/` vs Root Bridges

A common rookie mistake is dumping everything—business specs, coding prompts, server IPs, and gigabytes of markdown—into one folder or one rule file. Why does that fail?
1. Antigravity enforces a strict **`24 KB` per rule file** and **`20,000` token aggregate budget** across always-on rules (`agy-customizations/docs/rules.md`), and Cursor/Claude/Codex likewise degrade when flooded with unfocused context.
2. In this repo, `.gitignore` line 26 ignores `.agents` completely, while legacy `.agents/rules/OVH_SSH.md` (quarantined to gitignored `.agents/rules/OVH_SSH.local.md`) stored a live VPS IP and local key path!

### Chosen Separation Architecture (**Option 2 — Autonomous Enterprise Factory**)

| Layer | Directory / File | Exact Responsibility | Git Tracking |
| :--- | :--- | :--- | :--- |
| **Root Router & Bridges** | `AGENTS.md` (`<150` lines), `CLAUDE.md`, `.cursor/rules/*.mdc`, `.github/copilot-instructions.md` | Model- and IDE-agnostic entry bootloader. Read natively by Claude Code, OpenAI Codex CLI, Cursor, VS Code Copilot, JetBrains Junie, Windsurf, and Antigravity. | **Tracked** (generated from canonical templates — never manually drifted) |
| **Scoped Subtree Rules** | `backend/AGENTS.md`, `frontend/AGENTS.md`, `migrations/AGENTS.md` | Directory-scoped rules loaded **only** when working inside Python, Next.js UI, or SQL migrations so 120B/Flash models never drown in unrelated instructions. | **Tracked** |
| **Product Knowledge Textbook** | `docs/` (`core/`, `domain/`, `architecture/`, `change/`, `research/`, `generated/`) | **What Risklocker IS**: DB ERDs, JPJ/insurer rules, `DESIGN-SYSTEM.md` UI tokens, API contracts, `CODEBASE-MAP.md`, `Graphify` `GRAPH_REPORT.md`, sprint state. Separate from `.agents/` so humans and *every* AI share one source of truth. | **Tracked** |
| **Workforce Operating System** | `.agents/` (`manifest.yaml`, `agents/`, `skills/`, `hooks/`, `hooks.json`, `rules/`, `proposals/`, `logs/`) | **How AI Workers Operate**: 9 focused roles, open-standard `SKILL.md` playbooks synced cleanly to `.claude`/`.cursor`/`.codex`, deterministic `hooks.json` tripwires, daily conditional radar, and compressed session digests. | **Tracked** via append-only `.gitignore` overrides — **with local secrets (`OVH_SSH.local.md`) & auth profiles strictly ignored** |
| **Runtime Quarantine & Auth Browser** | `/.qc-tmp/` (including `/.qc-tmp/research-browser-profile/`) | Scratch screenshots, Playwright scripts, and persistent local Chrome login profile for authenticated research sites — quarantined inside repo root and 100% gitignored. | **Gitignored** (`/.qc-tmp/`) |

---

## 3. Live Audit of Existing Local Setup vs External Claims (What Was Actually Found)

Before pulling anything from GitHub, **Stage 1 (Inspect First)** uncovered critical mismatches between existing docs and disk reality:

1. **Duplicate/Drift in Installed Skills ([`.agents/skills/`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/.agents/skills) & [`SKILLS.md`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/docs/core/SKILLS.md)):**
   - Local `.agents/skills/using-superpowers/SKILL.md` is a shallow 4-bullet summary (`~20` lines), lacking upstream `obra/superpowers`'s **1% skill-invocation rule**, **Red Flags excuse-vs-reality table**, and **subagent recursion blocks**.
   - Global [`design-taste-frontend`](file:///C:/Users/mahmud/.gemini/config/skills/design-taste-frontend/SKILL.md) (based on `Leonxlnx/taste-skill`) is **already installed** on this machine—**but line 6 explicitly says:** *"Landing pages, portfolios, and redesigns. Not dashboards, not data tables, not multi-step product UI."* Using it unmodified for Risklocker's financial ledger and comparison matrices would apply landing-page bias to data-dense fintech screens. We must adapt its anti-slop discipline into an enterprise dashboard/table skill paired with [`DESIGN-SYSTEM.md`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/docs/architecture/DESIGN-SYSTEM.md).
   - [`SKILLS.md`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/docs/core/SKILLS.md) references skills (`fastapi`, `vercel-react-best-practices`, `customize-opencode`) not present in `.agents/skills/`, while omitting installed ones (`playwright-cli`, `playwright-explore-website`).
2. **Existing 5 Council Roles Are Solid Concepts Without Enforcement ([`.agents/agents/`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/.agents/agents)):**
   - Existing `principal-architect`, `mentor`, `anti-slop`, `qa-gauntlet`, and `janitor` files contain zero YAML frontmatter, zero structured return schemas, and no `Security Auditor`, `Falcon` Research Scout, or dedicated domain leads—and Antigravity does not auto-mount `.agents/agents/*.md` as tools unless bridged via a dispatch skill (`company-dispatch`).
3. **Existing Scripts (`commands/update-code-map.py`, `verify-brain.py`, `qa-crawl-page.mjs`, `verify-deploy-gate.ps1`):**
   - `update-code-map.py` extracts surface endpoints/classes but does **not** build multi-hop AST call-dependency graphs connecting frontend calls → API routers → SQLAlchemy services → Postgres tables/migrations.

---

## 4. Evaluate-First Matrix: 10 External Open-Source Repos & Benchmarks

Evaluated cleanly on **2026-11-11** via live web lookup against Windows + Risklocker engineering requirements:

| # | Repository / Reference | Real Core Mechanism (Verified) | Verdict | Exact What to KEEP / ADAPT vs REJECT |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **`obra/superpowers`** (`~315k★`) | Socratic spec refinement, 2–5 min step plans, 4-phase root-cause debugging, Red-Green TDD, **1% skill rule + Red Flags rationalization table**, no subagent self-spawn review loops. | **ADAPT CORE** | **Keep & Upgrade:** Replace watered-down local `using-superpowers` rules with strict 1% threshold + Red Flags table + micro-step plan format.<br>**Reject:** Turning trivial 5–10s CSS polish (**Fast Track**) into multi-step planning ceremonies. |
| **2** | **`addyosmani/agent-skills`** (`~113k★`) | Lifecycle phase skills (*Define → Plan → Build → Verify → Review → Ship*), **excuse-vs-reality anti-rationalization tables**, `interview-me`, `context-engineering`, `doubt-driven-development`, `source-driven-development`. | **ADAPT CORE** | **Keep:** Anti-rationalization checklists embedded into `.agents/rules/02-anti-slop-and-modularity.md` and skill gates; `source-driven-development` (verify live official docs before assuming APIs).<br>**Reject:** Copying redundant generic skills already covered by our verified stack. |
| **3** | **`affaan-m/ECC`** (*Everything Claude Code*, `~299k★`) | Decoupled **Agents / Deterministic Hooks / Rules / Continuous-Learning Instincts (`continuous-learning-v2`)** scoring observed behaviors globally or per project. | **ADAPT HOOKS & INSTINCTS** | **Keep:** Universal lifecycle hook architecture (`.agents/hooks.json` + Python hook scripts) and atomic project-scoped learning (`instincts.json` feeding proposals).<br>**Reject:** Claude-only bash scripts that assume Linux paths/shells; use cross-platform Python scripts in `.agents/hooks/`. |
| **4** | **`msitarzewski/agency-agents`** (`~80k+★`) | 200+ rigid Markdown+YAML role personas (*Identity, Core Mission, Critical Domain Rules, Technical Deliverables, Workflow, Success Metrics*). | **ADAPT TEMPLATE ONLY** | **Keep:** Standard YAML + 6-section rubric format for our **9 Risklocker roles** in `.agents/agents/`.<br>**Reject:** Importing 150–200 bloated generic personas into context. |
| **5** | **`thedotmack/claude-mem`** | Persistent cross-session context compression via background Bun HTTP worker + SQLite FTS5 + folder timelines (`CLAUDE.md`). | **ADAPT PATTERN (LIGHTWEIGHT)** | **Keep:** Compressed milestone digest pattern (`.agents/memory/digest.json` + `STATE.md` rolling summaries) so model/IDE swaps preserve architecture decisions.<br>**Reject:** Installing heavy Bun/node-gyp native SQLite background daemons on Windows (documented Windows console-popup & build-toolchain friction). |
| **6** | **`Leonxlnx/taste-skill`** (`design-taste-frontend`) | Visual anti-slop design rules, brief inference (*Design Read*), art direction & real browser checks. Also benchmarked UI simplicity vs **`codeandchill.store`** / SPA kits (`Halvi` reference). | **ADAPT WITH OVERRIDE** | **Keep:** Art-direction discipline, strict non-random tokens, and Playwright visual verification.<br>**Reject:** Letting landing-page / flashy GSAP hype infect operational fintech tables — wrap inside a new **`enterprise-product-ui`** skill locked to [`DESIGN-SYSTEM.md`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/docs/architecture/DESIGN-SYSTEM.md). |
| **7** | **`Graphify-Labs/graphify`** (`pip install graphifyy`) | Local **tree-sitter AST** parser across Python/TS/SQL/docs generating `GRAPH_REPORT.md`, `graph.json`, interactive `graph.html`, and zero-vector-DB MCP server (`python -m graphify.serve`), supporting `--platform windows`. | **ADAPT & INTEGRATE** | **Keep:** Install inside project `.venv` (via approved plan) to generate `docs/generated/GRAPH_REPORT.md` so 120B/Flash/Pro models trace exact call graphs across monoliths without guessing.<br>**Reject:** Replacing `commands/verify-brain.py`; run alongside it as deeper structural layer. |
| **8** | **`NousResearch/hermes-agent`** (`~262k★`) & **`deepseek-ai/deepseek-harness`** (`dsh`, `~275k★`) | Standalone modular plugin/harness architectures decoupling models, loops, tools, and memory (`Cordis` framework / gateway plugins). | **PATTERNS ONLY — REJECT INSTALL** | **Keep:** Declarative modular contract pattern in `.agents/manifest.yaml` (clean separation of model tier, tools, role, verification gate).<br>**Reject:** Embedding external TypeScript/Python agent runtimes inside `.agents/engines/` (creates competing apps inside the repo). |
| **9** | **`browser-use/browser-use`** (+ **Playwright MCP**) | Python/TS agentic browser control supporting **persistent Chrome `user_data_dir` & `storage_state` profiles**. | **ADAPT AUTH PROFILE PATTERN** | **Keep:** For **Falcon Scout**, use Playwright / `browser-use` pointing to gitignored **`/.qc-tmp/research-browser-profile/`** where **the human owner logs in once** (handling MFA/CAPTCHA legitimately).<br>**Reject:** Plaintext credentials in `.env.falcon` or automated anti-bot/CAPTCHA bypasses. |
| **10** | **`bmad-code-org/BMAD-METHOD`** | Spec-driven agile pipeline + **`bmad-shard-pro` document sharding** (`INDEX_GUIDED` / `SELECTIVE_LOAD`) so huge PRDs never overwhelm execution models. | **ADAPT SHARDING** | **Keep:** Apply `INDEX_GUIDED` micro-sharding across `docs/change/` and large blueprints (aligns with `START-HERE.md` line-range routing for smaller 120B/Flash models).<br>**Reject:** Heavy multi-sprint Scrum-ceremony roleplay for solo/small-team velocity. |

---

## 5. Final Architecture Specification for Option 2 (Pending Plan Approval)

1. **9-Role Balanced Team (Preserves All Council Veto Gates + Eliminates Self-Grading):**
   - `01-orchestrator-pm` (Deep Track dispatcher; **explicitly bypassed on Fast Track CSS/copy tweaks**)
   - `02-falcon-scout` (On-demand web/GitHub/changelog/auth-profile research + conditional daily radar)
   - `03-mentor-architect` (Zero-coding elder architect, AST/DB judge, owner-intent translator)
   - `04-security-auditor` (**Strict read-only `Write: false`** RBAC/AppSec/PDPA PII veto gate)
   - `05-principal-designer` (Enterprise UI simplicity, `DESIGN-SYSTEM.md` token lock, Halvi/hype filter)
   - `06-backend-ledger-lead` (FastAPI, Postgres triggers, `NUMERIC(12,2)` journals, Malaysian motor math)
   - `07-frontend-ux-lead` (Next.js modular slicing, `<600L` files, React live canvas, zero client tax formulas)
   - `08-ai-extraction-lead` (PDF/OCR/Gemini structured schemas, full-document parsing, calibrated confidence)
   - `09-qa-and-janitor-gate` (Red-First TDD, Playwright E2E, dead-code deletion, `/.qc-tmp/` purge, `6/6` CI gate)
2. **Cross-IDE Bridge Generator (`commands/sync-agent-bridges.py`):**
   - Generates clean pointer/adapter files (`CLAUDE.md`, `.cursor/rules/*.mdc`, `.github/copilot-instructions.md`, and skill mirrors if needed) from one source (`AGENTS.md` + `.agents/`) **without flaky Windows symlinks**.
3. **Deterministic Guardrail Hooks (`.agents/hooks.json` + Cross-Platform Python Scripts):**
   - Code-freeze / workspace-boundary lock (`PreToolUse`), static security/PII/banned-pattern scanner (`PostToolUse`), and brain/logbook sanity check (`Stop`).
4. **Conditional Daily Self-Improvement Automation (`Nov 11 → Nov 12`):**
   - Scheduled once daily locally (`.agents/hooks/daily_radar.py`): inspects recent friction/errors + curated official release feeds. Logs **`NOOP`** silently when clean; writes `.agents/proposals/YYYY-MM-DD__<topic>.md` for owner review **only** when genuinely valuable.

