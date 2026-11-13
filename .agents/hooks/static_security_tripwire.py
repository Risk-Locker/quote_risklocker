"""PostToolUse & CLI static security/anti-slop tripwire on edited source files.

Imports canonical AST/regex security detectors from `commands/security-audit.py` so hook
and pre-deploy SAST rules never drift apart, plus guards SQL migrations for destructive DDL.
Always outputs `{}` to stdout in hook mode while logging findings to
`.agents/logs/tripwire-alerts.log` (and exiting non-zero in `--check-file` CLI mode).
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALERT_LOG = ROOT / ".agents" / "logs" / "tripwire-alerts.log"
AUDIT_SCRIPT = ROOT / "commands" / "security-audit.py"

WRITE_TOOLS = {
    "write_file",
    "edit_file",
    "replace_file_content",
    "multi_replace_file_content",
    "write_to_file",
    "create_file",
    "patch_file",
    "rename_file",
    "move_file",
    "multi_edit",
    "notebookedit",
}
PATH_ARG_KEYS = (
    "Path",
    "TargetFile",
    "path",
    "file_path",
    "AbsolutePath",
    "target_file",
    "DestinationPath",
    "destination",
    "source",
    "SourcePath",
    "old_path",
    "new_path",
    "OldPath",
    "NewPath",
    "TargetPath",
    "target",
)
LIST_PATH_KEYS = ("paths", "files", "targets", "edits")
DESTRUCTIVE_SQL_RE = re.compile(r"\b(?:DROP\s+(?:DATABASE|SCHEMA|TABLE)|TRUNCATE\s+TABLE)\b", re.IGNORECASE)
TEST_SEVERE_RULES = frozenset(
    {
        "PY_SYNTAX",
        "SQLI_DYNAMIC",
        "NO_EVAL",
        "NO_EXEC",
        "NO_EVAL_ALIAS",
        "NO_DUNDER_IMPORT",
        "NO_GETATTR_EXEC",
        "NO_OS_EXEC",
        "UNSAFE_DESERIALIZATION",
        "UNSAFE_YAML",
        "SHELL_TRUE",
        "PII_OR_SECRET",
        "DEPRECATED_GEMINI",
    }
)


def _load_security_audit_module():
    spec = importlib.util.spec_from_file_location("risklocker_security_audit", str(AUDIT_SCRIPT))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {AUDIT_SCRIPT}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["risklocker_security_audit"] = mod
    spec.loader.exec_module(mod)
    return mod


def _extract_all_paths(args: dict, *, _depth: int = 0) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()

    def _add(val: object) -> None:
        if isinstance(val, str):
            trimmed = val.strip()
            if trimmed and trimmed not in seen:
                seen.add(trimmed)
                paths.append(trimmed)

    for key in PATH_ARG_KEYS:
        _add(args.get(key))

    if _depth < 2:
        for lkey in LIST_PATH_KEYS:
            seq = args.get(lkey)
            if isinstance(seq, (list, tuple)):
                for item in seq:
                    if isinstance(item, str):
                        _add(item)
                    elif isinstance(item, dict):
                        for nested in _extract_all_paths(item, _depth=_depth + 1):
                            _add(nested)
    return paths


def _log_tripwire_alerts(findings: list[str]) -> None:
    if not findings:
        return
    ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with ALERT_LOG.open("a", encoding="utf-8") as fh:
        for item in findings:
            fh.write(f"{stamp} {item}\n")
    sys.stderr.write("TRIPWIRE ALERTS:\n" + "\n".join(findings) + "\n")


def scan_file(target: Path) -> list[str]:
    if not target.exists() or not target.is_file():
        return []
    try:
        rel = target.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return []

    audit = _load_security_audit_module()
    text = target.read_text(encoding="utf-8", errors="ignore")
    findings: list[str] = []

    if rel.startswith("backend/app/") and rel.endswith(".py"):
        for f in audit.scan_python_source(rel, text, None):
            findings.append(f"[{f.rule_id}] {f.location} — {f.message}")
    elif rel.startswith((".agents/hooks/", "commands/")) and rel.endswith(".py"):
        for f in audit.scan_python_source(rel, text, None):
            if f.rule_id != "MONOLITH_PY":
                findings.append(f"[{f.rule_id}] {f.location} — {f.message}")
    elif rel.startswith("frontend/src/") and rel.endswith((".ts", ".tsx", ".js", ".jsx")):
        for f in audit.scan_typescript_source(rel, text):
            findings.append(f"[{f.rule_id}] {f.location} — {f.message}")
    elif rel.startswith("migrations/") and rel.endswith(".sql"):
        for idx, line in enumerate(text.splitlines(), 1):
            if DESTRUCTIVE_SQL_RE.search(line):
                findings.append(f"[DESTRUCTIVE_MIGRATION] {rel}:{idx} — Destructive DROP/TRUNCATE SQL requires explicit owner sign-off.")
            if audit.PII_SECRET_RE.search(line):
                findings.append(f"[PII_OR_SECRET] {rel}:{idx} — Hardcoded PII/secret literal in SQL migration.")
            if audit.NRIC_RE.search(line):
                findings.append(f"[PII_OR_SECRET] {rel}:{idx} — Hardcoded Malaysian NRIC literal in SQL migration.")
    elif rel.startswith("tests/") and rel.endswith(".py"):
        for f in audit.scan_python_source(rel, text, None):
            if f.rule_id in TEST_SEVERE_RULES:
                findings.append(f"[{f.rule_id}] {f.location} — {f.message}")
    elif rel.startswith(("commands/", ".github/workflows/", ".agents/", "tests/")) and rel.endswith((".py", ".yml", ".yaml", ".ps1", ".json")):
        for idx, line in enumerate(text.splitlines(), 1):
            if audit.PII_SECRET_RE.search(line):
                findings.append(f"[PII_OR_SECRET] {rel}:{idx} — Secret or PII literal detected.")
            if audit.NRIC_RE.search(line):
                findings.append(f"[PII_OR_SECRET] {rel}:{idx} — Hardcoded Malaysian NRIC literal detected.")
            if audit.DEPRECATED_GEMINI_RE.search(line):
                findings.append(f"[DEPRECATED_GEMINI] {rel}:{idx} — Deprecated or shutdown Gemini model string detected.")

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Static security and anti-slop tripwire.")
    parser.add_argument("--check-file", type=str, help="Inspect a single file explicitly (exits 1 if findings exist).")
    args, _ = parser.parse_known_args()

    if args.check_file:
        target = Path(args.check_file)
        if not target.is_absolute():
            target = ROOT / target
        try:
            findings = scan_file(target)
        except Exception as exc:
            err = f"[TRIPWIRE_LOAD_ERROR] {args.check_file} — {exc}"
            sys.stderr.write(err + "\n")
            return 1
        for item in findings:
            print(item)
        return 1 if findings else 0

    try:
        raw = sys.stdin.read().strip()
        payload = json.loads(raw) if raw else {}
    except Exception as exc:
        _log_tripwire_alerts([f"[TRIPWIRE_PAYLOAD_ERROR] stdin — Malformed PostToolUse JSON payload: {exc}"])
        sys.stdout.write("{}\n")
        return 0

    if not isinstance(payload, dict):
        _log_tripwire_alerts(["[TRIPWIRE_PAYLOAD_ERROR] stdin — PostToolUse payload must be a JSON object."])
        sys.stdout.write("{}\n")
        return 0

    tool_call = payload.get("toolCall") or {}
    if isinstance(tool_call, dict) and str(tool_call.get("name", "")).lower() in WRITE_TOOLS:
        tool_args = tool_call.get("args") or {}
        if isinstance(tool_args, dict):
            for raw_path in _extract_all_paths(tool_args):
                target = Path(raw_path)
                if not target.is_absolute():
                    target = ROOT / target
                try:
                    findings = scan_file(target)
                except Exception as exc:
                    findings = [f"[TRIPWIRE_LOAD_ERROR] {raw_path} — Failed to run static security scan: {exc}"]
                _log_tripwire_alerts(findings)

    sys.stdout.write("{}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
