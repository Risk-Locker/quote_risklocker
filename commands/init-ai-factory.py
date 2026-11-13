"""Bootstrap the portable Agent Harness (.agents/) and Project Knowledge Base (docs/) into any repository.

Standardized Vocabulary (understood zero-shot across Claude, Gemini, GPT/Codex, DeepSeek, MiniMax):
  - Agent Harness (`AGENTS.md` + `.agents/`): Subagents, Active/Cold Agent Skills, Rules, Hooks, Memory.
  - Project Knowledge Base (`docs/`): Progressive-disclosure index (`START-HERE.md`), Working Memory (`STATE.md`).

Usage:
  python commands/init-ai-factory.py --target C:\\path\\to\\new-project --project-name MySaaS [--dry-run]
"""

from __future__ import annotations

import argparse
import datetime
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_LOCK = ROOT / ".agents" / "skills-lock.json"

PORTABLE_FILES = [
    ".agents/manifest.yaml",
    ".agents/hooks.json",
    ".agents/hooks/session_start_guard.py",
    ".agents/hooks/freeze_and_path_guard.py",
    ".agents/hooks/static_security_tripwire.py",
    ".agents/hooks/brain_stop_guard.py",
    ".agents/hooks/daily_radar.py",
    ".agents/guides/authenticated-research-runbook.md",
    ".agents/proposals/README.md",
    ".agents/skills-vault/README.md",
    ".agents/rules/00-suggestive-evaluation-gate.md",
    ".agents/rules/01-company-chain-of-command.md",
    ".agents/rules/02-anti-slop-and-modularity.md",
    ".agents/rules/03-enterprise-ui-simplicity.md",
    ".agents/rules/04-skill-vault-and-local-scope.md",
    ".agents/rules/05-live-reality-and-freshness.md",
    "commands/sync-agent-bridges.py",
    "commands/skills-manager.py",
    "commands/verify-brain.py",
    "commands/update-code-map.py",
    "commands/security-audit.py",
    "commands/clean-repo-debris.ps1",
]

PORTABLE_PLUGIN_DIRS = [
    "risklocker-ui",
    "ui-21st-dev",
]


def load_universal_skills() -> tuple[dict[str, dict], int]:
    """Read universal skills dynamically from .agents/skills-lock.json (active + cold vault)."""
    if SOURCE_LOCK.exists():
        try:
            data = json.loads(SOURCE_LOCK.read_text(encoding="utf-8"))
            soft_limit = int(data.get("active_soft_limit", 50))
            universal = {
                name: info
                for name, info in sorted((data.get("skills") or {}).items())
                if info.get("scope") == "universal"
            }
            return universal, soft_limit
        except (json.JSONDecodeError, ValueError):
            pass

    # Fallback scan if lockfile is absent: treat everything in .agents/skills/ without project domains as universal
    universal: dict[str, dict] = {}
    skills_dir = ROOT / ".agents" / "skills"
    if skills_dir.exists():
        for d in sorted(skills_dir.iterdir()):
            if d.is_dir() and (d / "SKILL.md").exists():
                universal[d.name] = {
                    "location": "active",
                    "path": d.relative_to(ROOT).as_posix(),
                    "category": "general",
                    "scope": "universal",
                    "source": "local-repo",
                }
    return universal, 50


def render_root_agents_stub(project_name: str) -> str:
    return f"""# {project_name} Project Instructions & Agent Harness (`AGENTS.md`)

1. Read `AGENTS.md` and `docs/core/START-HERE.md` (**Project Knowledge Base**) before inspecting source code.
2. Obey Dual-Track Execution: Fast Track (`<15s` CSS/copy polish -> single-file check) vs Deep Track (`implementation_plan.md` with model assignment + Subagent Security/QA gates).
3. Install all Agent Skills repo-locally inside `.agents/skills/` (Active) or `.agents/skills-vault/` (Cold Archive) via `commands/skills-manager.py`; never install globally (`-g`, `~/.gemini`, `~/.claude`, `~/.codex`, `~/.copilot`) unless explicitly ordered.
4. Keep `docs/core/STATE.md` (Working Memory) under 80 lines; keep temporary artifacts strictly inside `/.qc-tmp/`.
5. Run `python commands/verify-brain.py` and `python commands/skills-manager.py doctor --check` after updates.

## Project-Specific Domain Rules (`TODO`)
- Define database/stack invariants in `docs/domain/BUSINESS-RULES.md`.
- Define visual design tokens in `docs/architecture/DESIGN-SYSTEM.md`.
"""


def bootstrap(target: Path, project_name: str, *, dry_run: bool) -> list[str]:
    actions: list[str] = []

    for rel in PORTABLE_FILES:
        src = ROOT / rel
        dst = target / rel
        if src.exists():
            actions.append(f"COPY {rel}")
            if not dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

    agents_src = ROOT / ".agents" / "agents"
    if agents_src.exists():
        for role_file in sorted(agents_src.glob("*.md")):
            rel = role_file.relative_to(ROOT).as_posix()
            actions.append(f"COPY {rel}")
            if not dry_run:
                dst = target / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(role_file, dst)

    plugins_src = ROOT / ".agents" / "plugins"
    for p_name in PORTABLE_PLUGIN_DIRS:
        p_src = plugins_src / p_name
        if p_src.exists():
            rel_dir = p_src.relative_to(ROOT).as_posix()
            actions.append(f"COPY_PLUGIN {rel_dir}/")
            if not dry_run:
                p_dst = target / rel_dir
                if p_dst.exists():
                    shutil.rmtree(p_dst)
                shutil.copytree(p_src, p_dst, ignore=shutil.ignore_patterns("__pycache__", "node_modules", ".git", ".env*"))

    universal_skills, soft_limit = load_universal_skills()
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    target_lock_skills: dict[str, dict] = {}

    for skill_name, info in universal_skills.items():
        rel_src = str(info.get("path") or f".agents/skills/{skill_name}")
        s_src = ROOT / rel_src
        if s_src.exists():
            actions.append(f"COPY_SKILL {rel_src}/ [{info.get('location', 'active')}]")
            if not dry_run:
                s_dst = target / rel_src
                if s_dst.exists():
                    shutil.rmtree(s_dst)
                shutil.copytree(s_src, s_dst, ignore=shutil.ignore_patterns("__pycache__", "node_modules", ".git", ".cache"))
            entry = dict(info)
            entry["updated_at"] = now
            target_lock_skills[skill_name] = entry

    actions.append(f"WRITE .agents/skills-lock.json ({len(target_lock_skills)} universal skills)")
    if not dry_run:
        t_lock = target / ".agents" / "skills-lock.json"
        t_lock.parent.mkdir(parents=True, exist_ok=True)
        t_lock.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "active_soft_limit": soft_limit,
                    "skills": target_lock_skills,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    skeleton_docs = {
        "AGENTS.md": render_root_agents_stub(project_name),
        "docs/core/STATE.md": f"# Working Memory (`{project_name}`)\n\n- Initialized portable Agent Harness (`.agents/`) & Project Knowledge Base (`docs/`).\n",
        "docs/core/SKILLS.md": f"# Agent Skills Registry & Cold Archive (`{project_name}`)\n\nAll Agent Skills live in `.agents/skills/` (Active) or `.agents/skills-vault/` (Cold Archive).\nRun `python commands/skills-manager.py list` or inspect `docs/generated/SKILLS-INDEX.md`.\n",
        "docs/core/START-HERE.md": f"# Project Knowledge Base Index (`{project_name}`)\n\n| Doc | Purpose |\n| :--- | :--- |\n| `docs/core/STATE.md` | Working memory (<80 lines) |\n| `docs/core/SKILLS.md` | Agent Skills archive & repo-local install contract |\n| `docs/domain/BUSINESS-RULES.md` | Non-negotiable domain rules |\n| `docs/architecture/DESIGN-SYSTEM.md` | UI tokens and layout standards |\n",
        "docs/domain/BUSINESS-RULES.md": f"# {project_name} Business Rules\n\n- TODO: Specify authoritative business & compliance invariants.\n",
        "docs/architecture/DESIGN-SYSTEM.md": f"# {project_name} Design System\n\n- TODO: Specify color tokens, typography scale, spacing & accessibility standards.\n",
        ".agents/logs/self-audit-history.md": f"# Self-Audit History ({project_name})\n",
    }
    for rel, content in skeleton_docs.items():
        dst = target / rel
        if not dst.exists():
            actions.append(f"CREATE {rel}")
            if not dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(content, encoding="utf-8")

    return actions


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize portable Agent Harness and Project Knowledge Base in another repository.")
    parser.add_argument("--target", required=True, help="Target repository directory.")
    parser.add_argument("--project-name", default="EnterpriseApp", help="Project display name.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned actions without writing files.")
    args = parser.parse_args()

    target = Path(args.target).resolve()
    if not args.dry_run:
        target.mkdir(parents=True, exist_ok=True)
    actions = bootstrap(target, args.project_name, dry_run=bool(args.dry_run))
    for act in actions:
        print(act)
    print(f"\n[{'DRY-RUN' if args.dry_run else 'OK'}] {len(actions)} factory setup actions targeting {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
