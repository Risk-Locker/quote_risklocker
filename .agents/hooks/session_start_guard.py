"""SessionStart lifecycle hook injecting concise workspace freeze/alert state on turn 1.

Follows Antigravity SessionStart JSON contract (`.agents/hooks.json`):
Outputs `{}` when idle/clear or `{"injectSteps": [{"systemMessage": {"systemMessage": "..."}}]}`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK_FILE = ROOT / ".agents" / ".freeze.lock"
PROPOSALS_DIR = ROOT / ".agents" / "proposals"
TRIPWIRE_LOG = ROOT / ".agents" / "logs" / "tripwire-alerts.log"
DOCS_STATE = ROOT / "docs" / "core" / "STATE.md"


def build_status_parts() -> list[str]:
    parts: list[str] = []

    if LOCK_FILE.exists():
        try:
            lock_data = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
            if lock_data.get("enabled", True):
                locked = ", ".join(lock_data.get("locked_prefixes", []))
                parts.append(f"ACTIVE CODE FREEZE (.freeze.lock locks: {locked})")
        except Exception:
            parts.append("ACTIVE CODE FREEZE (.freeze.lock enabled)")

    if PROPOSALS_DIR.exists():
        pending = [p.name for p in sorted(PROPOSALS_DIR.glob("*.md")) if p.name.upper() != "README.MD"]
        if pending:
            parts.append(f"{len(pending)} pending audit proposal(s) in .agents/proposals/ ({pending[0]})")

    if TRIPWIRE_LOG.exists():
        alerts = [ln for ln in TRIPWIRE_LOG.read_text(encoding="utf-8", errors="ignore").splitlines() if ln.strip()]
        if alerts:
            parts.append(f"{len(alerts)} tripwire alert(s) logged in .agents/logs/tripwire-alerts.log")

    if DOCS_STATE.exists():
        lines = len(DOCS_STATE.read_text(encoding="utf-8-sig", errors="replace").splitlines())
        if lines > 80:
            parts.append(f"docs/core/STATE.md at {lines} lines (>80 cap; rotate to docs/history/)")

    return parts


def main() -> int:
    try:
        _ = sys.stdin.read()
    except Exception:
        pass

    parts = build_status_parts()
    if not parts:
        sys.stdout.write("{}\n")
        return 0

    summary = (
        "[Risklocker Session Context] "
        + " | ".join(parts)
        + ". Read AGENTS.md + docs/core/START-HERE.md; keep CEO -> Default Agent -> PM (01) -> Specialist Leads workflow active."
    )
    payload = {
        "injectSteps": [
            {
                "systemMessage": {
                    "systemMessage": summary,
                }
            }
        ]
    }
    sys.stdout.write(json.dumps(payload) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

