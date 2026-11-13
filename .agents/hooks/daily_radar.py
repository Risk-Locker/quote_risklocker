"""Conditional daily self-improvement radar (internal hygiene + freshness + curated upstream audit).

Follows the Zero-Noise Gate:
  - Logs one concise `NOOP` line to `.agents/logs/self-audit-history.md` when nothing requires action.
  - Emits a structured human-review proposal in `.agents/proposals/YYYY-MM-DD__daily-radar-audit.md`
    ONLY when a new security/framework change, brain failure, bridge drift, stale model/tier rule,
    stub regression, native Antigravity schema error, or tripwire alert occurs.
  - Supports `--strict` to exit 1 when active harness/hygiene findings (`harness_signals_count > 0`) exist.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RADAR_STATE = ROOT / ".agents" / "memory" / "radar-state.json"
AUDIT_HISTORY = ROOT / ".agents" / "logs" / "self-audit-history.md"
TRIPWIRE_LOG = ROOT / ".agents" / "logs" / "tripwire-alerts.log"
PROPOSALS_DIR = ROOT / ".agents" / "proposals"
STATE_MD = ROOT / "docs" / "core" / "STATE.md"
FREEZE_LOCK = ROOT / ".agents" / ".freeze.lock"

PYPI_WATCH = ["fastapi", "pydantic", "playwright", "graphifyy", "sqlalchemy"]
NPM_WATCH = ["next", "react", "tailwindcss"]

# Verified deprecated / shutdown Gemini endpoints (Rule 05 / F-14)
DEPRECATED_GEMINI_RE = re.compile(
    r"\b("
    r"gemini-" r"3\.1-flash-lite(?:-preview)?|"
    r"gemini-" r"3\.5-flash(?!-lite)|"
    r"gemini-2\.[05]-[A-Za-z0-9_.-]+|"
    r"gemini-1\.[05]-[A-Za-z0-9_.-]+"
    r")\b"
)
# Active-harness stale model/tier/cap strings (only exempt explicit ban/rule reference files)
STALE_PRO_LABEL_RE = re.compile(r"Gemini 3\.1 Pro", re.IGNORECASE)
STALE_SPLIT_RE = re.compile(r"(?:pro\s+model\s+tier|`pro`\s+for\s+backend|`flash`\s+for\s+UI|<= ?35\b|\b(?:6/6|8/8)\s+(?:checks?|gates?|verify-deploy-gate))", re.IGNORECASE)
ALLOWED_PRO_WARNING_PATHS = {
    ".agents/rules/05-live-reality-and-freshness.md",
    ".agents/agents/01-orchestrator-pm.md",
    ".agents/hooks/daily_radar.py",
}
ALLOWED_GEMINI_BAN_DOC_PATHS = {
    ".agents/agents/01-orchestrator-pm.md",
    ".agents/agents/08-ai-extraction-lead.md",
    ".agents/skills/live-reality-and-deprecation-gate/SKILL.md",
    ".agents/skills/live-reality-and-deprecation-gate/references/verification-checklist.md",
    ".agents/hooks/daily_radar.py",
    "backend/AGENTS.md",
}


def fetch_json(url: str, timeout: float = 5.0) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": "risklocker-daily-radar/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8", errors="ignore"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    return None


def _read_freeze_enabled() -> bool:
    if not FREEZE_LOCK.exists():
        return False
    text = FREEZE_LOCK.read_text(encoding="utf-8", errors="ignore").lower()
    return "enabled: true" in text or '"enabled": true' in text


def _parse_yaml_header(md_path: Path) -> dict[str, str]:
    text = md_path.read_text(encoding="utf-8-sig", errors="replace")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    meta: dict[str, str] = {}
    for ln in lines[1:]:
        if ln.strip() == "---":
            break
        m = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", ln)
        if m:
            meta[m.group(1).strip()] = m.group(2).strip().strip("\"'")
    return meta


def check_harness_freshness() -> tuple[list[str], list[str]]:
    """Return (harness_findings, freeze_deferred_code_findings)."""
    harness_findings: list[str] = []
    frozen_code_findings: list[str] = []

    # 1. Native Antigravity Agent Frontmatter (.agents/agents/*.md)
    agents_dir = ROOT / ".agents" / "agents"
    if agents_dir.exists():
        for agent_file in sorted(agents_dir.glob("*.md")):
            meta = _parse_yaml_header(agent_file)
            missing = [k for k in ("name", "description", "mainAgent", "subagent", "tools") if k not in meta]
            if missing:
                harness_findings.append(
                    f"Agent `{agent_file.relative_to(ROOT).as_posix()}` missing native Antigravity frontmatter key(s): {', '.join(missing)}."
                )

    # 2. Native Antigravity Rule Trigger Frontmatter (.agents/rules/*.md)
    rules_dir = ROOT / ".agents" / "rules"
    if rules_dir.exists():
        for rule_file in sorted(rules_dir.glob("*.md")):
            if rule_file.name.endswith(".local.md"):
                continue
            meta = _parse_yaml_header(rule_file)
            if "trigger" not in meta:
                harness_findings.append(
                    f"Rule `{rule_file.relative_to(ROOT).as_posix()}` missing Antigravity `trigger:` frontmatter."
                )

    # 3. Active Skill Stub Regression (< 25 lines)
    skills_dir = ROOT / ".agents" / "skills"
    if skills_dir.exists():
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            non_empty = [ln for ln in skill_md.read_text(encoding="utf-8-sig", errors="replace").splitlines() if ln.strip()]
            if len(non_empty) < 25:
                harness_findings.append(
                    f"Active skill `{skill_md.relative_to(ROOT).as_posix()}` has only {len(non_empty)} non-empty lines (stub regression <25L)."
                )

    # 4. Repo-Local Plugin JSON Validity (.agents/plugins/*)
    plugins_dir = ROOT / ".agents" / "plugins"
    if plugins_dir.exists():
        for plugin_dir in sorted(plugins_dir.iterdir()):
            if not plugin_dir.is_dir():
                continue
            p_json = plugin_dir / "plugin.json"
            if not p_json.exists():
                harness_findings.append(f"Plugin `{plugin_dir.relative_to(ROOT).as_posix()}` missing required `plugin.json`.")
                continue
            for cfg in (p_json, plugin_dir / "mcp_config.json", plugin_dir / "hooks.json"):
                if cfg.exists():
                    try:
                        json.loads(cfg.read_text(encoding="utf-8-sig"))
                    except json.JSONDecodeError as exc:
                        harness_findings.append(f"Invalid JSON in `{cfg.relative_to(ROOT).as_posix()}`: {exc.msg} (line {exc.lineno}).")

    # 5. Stale/Unverified Model Labels, Deprecated Gemini IDs & Superseded Harness Caps across Active Harness + Skills + Core Docs
    scan_paths: list[Path] = [
        ROOT / "AGENTS.md",
        ROOT / "backend" / "AGENTS.md",
        ROOT / "frontend" / "AGENTS.md",
        ROOT / "migrations" / "AGENTS.md",
        ROOT / ".agents" / "manifest.yaml",
        ROOT / ".agents" / "hooks.json",
        ROOT / ".agents" / "skills-vault" / "README.md",
        ROOT / ".github" / "copilot-instructions.md",
    ]
    scan_paths.extend(sorted(agents_dir.glob("*.md")) if agents_dir.exists() else [])
    scan_paths.extend(sorted(rules_dir.glob("*.md")) if rules_dir.exists() else [])
    scan_paths.extend(sorted((ROOT / ".agents" / "hooks").glob("*.py")) if (ROOT / ".agents" / "hooks").exists() else [])
    scan_paths.extend(sorted(skills_dir.glob("*/SKILL.md")) if skills_dir.exists() else [])
    scan_paths.extend(sorted(skills_dir.glob("*/references/*.md")) if skills_dir.exists() else [])
    scan_paths.extend(sorted((ROOT / "commands").glob("*.py")) if (ROOT / "commands").exists() else [])
    scan_paths.extend(sorted((ROOT / "commands").glob("*.ps1")) if (ROOT / "commands").exists() else [])
    scan_paths.extend(sorted((ROOT / "docs" / "core").glob("*.md")) if (ROOT / "docs" / "core").exists() else [])
    scan_paths.extend(sorted((ROOT / "docs" / "architecture").glob("*.md")) if (ROOT / "docs" / "architecture").exists() else [])

    for p in scan_paths:
        if not p.exists() or p.name.endswith(".local.md"):
            continue
        text = p.read_text(encoding="utf-8-sig", errors="replace")
        rel = p.relative_to(ROOT).as_posix()
        if rel not in ALLOWED_PRO_WARNING_PATHS:
            if STALE_PRO_LABEL_RE.search(text):
                harness_findings.append(
                    f"Unverified/stale model label `Gemini 3.1 Pro` present in `{rel}` (Rule 05 violation)."
                )
            m_split = STALE_SPLIT_RE.search(text)
            if m_split:
                harness_findings.append(
                    f"Superseded harness directive `{m_split.group(0)}` present in `{rel}` (expected Max-Force Flash, 50-skill cap, 10/10 gate)."
                )
        if rel not in ALLOWED_GEMINI_BAN_DOC_PATHS:
            m_gem = DEPRECATED_GEMINI_RE.search(text)
            if m_gem:
                harness_findings.append(
                    f"Deprecated Gemini model ID `{m_gem.group(1)}` present in active harness/doc `{rel}` (Rule 05 violation)."
                )

    # 6. Deprecated Gemini Model ID Scan across frozen runtime app (backend/app/ & frontend/src/)
    runtime_hits: list[str] = []
    backend_app = ROOT / "backend" / "app"
    if backend_app.exists():
        for py_file in sorted(backend_app.rglob("*.py")):
            lines = py_file.read_text(encoding="utf-8-sig", errors="replace").splitlines()
            for idx, ln in enumerate(lines, start=1):
                for m in DEPRECATED_GEMINI_RE.finditer(ln):
                    runtime_hits.append(f"`{py_file.relative_to(ROOT).as_posix()}:{idx}` (`{m.group(1)}`)")
    frontend_src = ROOT / "frontend" / "src"
    if frontend_src.exists():
        for ts_file in sorted(frontend_src.rglob("*")):
            if not ts_file.is_file() or ts_file.suffix not in {".ts", ".tsx", ".js", ".jsx"}:
                continue
            lines = ts_file.read_text(encoding="utf-8-sig", errors="replace").splitlines()
            for idx, ln in enumerate(lines, start=1):
                for m in DEPRECATED_GEMINI_RE.finditer(ln):
                    runtime_hits.append(f"`{ts_file.relative_to(ROOT).as_posix()}:{idx}` (`{m.group(1)}`)")
    if runtime_hits:
        freeze_tag = " [Freeze-Deferred under .freeze.lock]" if _read_freeze_enabled() else ""
        frozen_code_findings.append(
            f"Deprecated/shutdown Gemini model IDs detected in runtime app code ({len(runtime_hits)} occurrences){freeze_tag}: "
            + ", ".join(runtime_hits[:6])
            + (f" (+{len(runtime_hits) - 6} more — see `.agents/proposals/2026-11-11__backend-gemini-model-deprecation-audit.md`)" if len(runtime_hits) > 6 else "")
        )

    return harness_findings, frozen_code_findings


def check_internal_health() -> tuple[list[str], list[str]]:
    findings: list[str] = []

    if STATE_MD.exists():
        lines = len(STATE_MD.read_text(encoding="utf-8-sig").splitlines())
        if lines > 80:
            findings.append(f"`docs/core/STATE.md` has {lines} lines (>80 target); rotate old rows to `docs/history/`.")

    for script, label in [
        ("commands/verify-brain.py", "Brain integrity"),
        ("commands/sync-agent-bridges.py --check", "Cross-IDE bridges"),
        ("commands/skills-manager.py doctor --check", "Skill Vault hygiene"),
    ]:
        parts = script.split()
        proc = subprocess.run([sys.executable, *parts], cwd=str(ROOT), capture_output=True, text=True)
        if proc.returncode != 0:
            detail = (proc.stdout + "\n" + proc.stderr).strip().splitlines()[-1:] or ["failed"]
            findings.append(f"{label} failed (`{script}`): {detail[0]}")

    if TRIPWIRE_LOG.exists():
        raw_alerts = [ln.strip() for ln in TRIPWIRE_LOG.read_text(encoding="utf-8", errors="ignore").splitlines() if ln.strip()]
        if raw_alerts:
            findings.append(f"{len(raw_alerts)} static security/anti-slop tripwire alert(s) logged in `.agents/logs/tripwire-alerts.log`.")

    harness_findings, frozen_code_findings = check_harness_freshness()
    findings.extend(harness_findings)
    return findings, frozen_code_findings


def check_external_releases(prev_versions: dict[str, str], *, offline: bool) -> tuple[dict[str, str], list[str]]:
    current = dict(prev_versions)
    changes: list[str] = []
    if offline:
        return current, changes

    for pkg in PYPI_WATCH:
        data = fetch_json(f"https://pypi.org/pypi/{pkg}/json")
        ver = str(((data or {}).get("info") or {}).get("version") or "")
        if ver:
            key = f"pypi:{pkg}"
            old = prev_versions.get(key)
            if old and old != ver:
                changes.append(f"PyPI `{pkg}` released `{ver}` (previously seen `{old}`). Review changelog before upgrading.")
            current[key] = ver

    for pkg in NPM_WATCH:
        data = fetch_json(f"https://registry.npmjs.org/{pkg}/latest")
        ver = str((data or {}).get("version") or "")
        if ver:
            key = f"npm:{pkg}"
            old = prev_versions.get(key)
            if old and old != ver:
                changes.append(f"npm `{pkg}` latest is `{ver}` (previously seen `{old}`). Check release notes for deprecations.")
            current[key] = ver

    return current, changes


def run_radar(*, offline: bool, dry_run: bool) -> dict:
    now = datetime.datetime.now().astimezone()
    stamp_iso = now.isoformat(timespec="seconds")
    date_slug = now.strftime("%Y-%m-%d")

    prev_state: dict = {}
    if RADAR_STATE.exists():
        try:
            prev_state = json.loads(RADAR_STATE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            prev_state = {}

    prev_versions = dict(prev_state.get("seen_versions") or {})
    internal_findings, frozen_code_findings = check_internal_health()
    new_versions, external_changes = check_external_releases(prev_versions, offline=offline)

    all_signals = internal_findings + frozen_code_findings + external_changes
    is_baseline_seed = not prev_versions and not all_signals

    if not all_signals:
        status = "NOOP"
        history_line = f"- `{stamp_iso}` · `NOOP` · System healthy; zero internal friction, stale models, or upstream changes ({'offline' if offline else 'online'})."
        proposal_path: str | None = None
    else:
        status = "PROPOSAL_CREATED"
        PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
        p_file = PROPOSALS_DIR / f"{date_slug}__daily-radar-audit.md"
        proposal_path = p_file.relative_to(ROOT).as_posix()
        history_line = f"- `{stamp_iso}` · `PROPOSAL` · {len(all_signals)} finding(s) queued in `{proposal_path}`."
        if not dry_run:
            lines = [
                f"# Daily Self-Audit Proposal — {date_slug}",
                "",
                f"> Generated `{stamp_iso}` by `.agents/hooks/daily_radar.py`. **Requires Owner Approval — zero auto-edits applied.**",
                "",
                "## Internal Harness & Hygiene Signals",
                *([f"- {item}" for item in internal_findings] or ["- None (Brain, Bridges, Native Agents/Rules, Plugins, Skills, Tripwires all clean)."]),
                "",
                "## Freeze-Deferred Runtime Deprecation Signals",
                *([f"- {item}" for item in frozen_code_findings] or ["- None detected in backend application code."]),
                "",
                "## Upstream Ecosystem Changes Detected",
                *([f"- {item}" for item in external_changes] or ["- None detected since baseline."]),
                "",
                "## Recommended Next Step",
                "- Review signals above; apply via an approved plan or dismiss cleanly.",
                "",
            ]
            p_file.write_text("\n".join(lines), encoding="utf-8")

    if not dry_run:
        RADAR_STATE.parent.mkdir(parents=True, exist_ok=True)
        RADAR_STATE.write_text(
            json.dumps(
                {
                    "last_run": stamp_iso,
                    "last_status": status,
                    "seen_versions": new_versions,
                    "baseline_initialized": not is_baseline_seed or bool(new_versions),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        AUDIT_HISTORY.parent.mkdir(parents=True, exist_ok=True)
        with AUDIT_HISTORY.open("a", encoding="utf-8") as fh:
            fh.write(history_line + "\n")

    return {
        "status": status,
        "timestamp": stamp_iso,
        "offline": offline,
        "dry_run": dry_run,
        "harness_signals_count": len(internal_findings),
        "frozen_code_signals_count": len(frozen_code_findings),
        "external_signals_count": len(external_changes),
        "signals_count": len(all_signals),
        "proposal": proposal_path,
        "preview_findings": all_signals,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Risklocker conditional daily self-improvement radar.")
    parser.add_argument("--offline", action="store_true", help="Skip external PyPI/npm network queries.")
    parser.add_argument("--dry-run", action="store_true", help="Evaluate without writing radar-state, logs, or proposals.")
    parser.add_argument("--strict", action="store_true", help="Exit 1 if any harness/hygiene issues (harness_signals_count > 0) exist.")
    args = parser.parse_args()
    result = run_radar(offline=bool(args.offline), dry_run=bool(args.dry_run))
    print(json.dumps(result, indent=2))
    if args.strict and result["harness_signals_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
