"""Stop lifecycle guard verifying Project Knowledge Base integrity (verify-brain.py) and STATE.md <= 80 lines."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE_FILE = ROOT / "docs" / "core" / "STATE.md"
VERIFY_BRAIN = ROOT / "commands" / "verify-brain.py"

SKIP_REASONS = {"USER_CANCELED", "MAX_INVOCATIONS", "MAX_FORCED_INVOCATIONS", "MAX_TOKEN_BUDGET_EXCEEDED", "ERROR"}


def run_check() -> dict:
    if STATE_FILE.exists():
        lines = STATE_FILE.read_text(encoding="utf-8-sig").splitlines()
        if len(lines) > 80:
            return {
                "decision": "continue",
                "reason": f"docs/core/STATE.md is {len(lines)} lines (>80 target). Rotate older entries into docs/history/MEMORY-YYYY-MM.md.",
            }

    if VERIFY_BRAIN.exists():
        proc = subprocess.run(
            [sys.executable, str(VERIFY_BRAIN)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            detail = (proc.stdout + "\n" + proc.stderr).strip()[-600:]
            return {
                "decision": "continue",
                "reason": f"commands/verify-brain.py failed. Fix docs registration/links before ending:\n{detail}",
            }

    return {}


def main() -> int:
    try:
        raw = sys.stdin.read().strip()
        payload = json.loads(raw) if raw else {}
    except Exception:
        payload = {}

    reason = str(payload.get("terminationReason", "")).upper()
    if reason in SKIP_REASONS:
        sys.stdout.write("{}\n")
        return 0

    result = run_check()
    sys.stdout.write(json.dumps(result) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

