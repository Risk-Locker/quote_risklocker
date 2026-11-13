"""Hermetic unit tests for .agents/hooks/freeze_and_path_guard.py."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".agents" / "hooks"))

import freeze_and_path_guard as guard


def test_write_to_locked_prefix_is_denied(monkeypatch):
    monkeypatch.setattr(
        guard,
        "load_freeze_config",
        lambda: (True, ["backend/app/", "frontend/src/", "migrations/", "tests/"], ["docs/", ".agents/", "commands/"]),
    )
    for locked in ["backend/app/main.py", "frontend/src/app/page.tsx", "migrations/001_initial.sql", "tests/test_x.py"]:
        payload = {
            "toolCall": {
                "name": "write_file",
                "args": {"Path": str(ROOT / locked), "Content": "test"},
            }
        }
        res = guard.evaluate_payload(payload)
        assert res["decision"] == "deny", f"Expected deny for {locked}, got {res}"
        assert "Code freeze active" in res["reason"]


def test_write_to_allowed_prefix_is_allowed(monkeypatch):
    monkeypatch.setattr(
        guard,
        "load_freeze_config",
        lambda: (True, ["backend/app/", "frontend/src/", "migrations/", "tests/"], ["docs/", ".agents/", "commands/", ".qc-tmp/"]),
    )
    for allowed in ["docs/core/STATE.md", ".agents/memory/digest.json", "commands/new-command.py", ".qc-tmp/test.txt"]:
        payload = {
            "toolCall": {
                "name": "write_file",
                "args": {"Path": str(ROOT / allowed), "Content": "test"},
            }
        }
        res = guard.evaluate_payload(payload)
        assert res["decision"] == "allow", f"Expected allow for {allowed}, got {res}"


def test_write_outside_repo_is_denied():
    payload = {
        "toolCall": {
            "name": "write_file",
            "args": {"Path": "C:/Windows/System32/drivers/etc/hosts", "Content": "malicious"},
        }
    }
    res = guard.evaluate_payload(payload)
    assert res["decision"] == "deny"
    assert "AGENTS.md §4 violation" in res["reason"]


def test_artifact_dir_writes_are_allowed(tmp_path):
    brain_artifact = tmp_path / "brain" / "conv-123" / "plan.md"
    payload = {
        "artifactDirectoryPath": str(tmp_path / "brain" / "conv-123"),
        "toolCall": {
            "name": "write_file",
            "args": {"Path": str(brain_artifact), "Content": "# Plan"},
        },
    }
    res = guard.evaluate_payload(payload)
    assert res["decision"] == "allow"


def test_destructive_shell_commands_force_ask():
    destructive_cmds = [
        "git push origin main --force",
        "git reset --hard HEAD~1",
        "DROP TABLE users",
        "TRUNCATE TABLE schema_migrations",
    ]
    for cmd in destructive_cmds:
        payload = {"toolCall": {"name": "run_command", "args": {"CommandLine": cmd}}}
        res = guard.evaluate_payload(payload)
        assert res["decision"] == "force_ask", f"Expected force_ask for '{cmd}', got {res}"
        assert "Destructive" in res["reason"]


def test_global_skill_installation_forces_ask():
    global_cmds = [
        "npx skills install foo",
        "skills add bar",
        "graphify install",
    ]
    for cmd in global_cmds:
        payload = {"toolCall": {"name": "run_command", "args": {"CommandLine": cmd}}}
        res = guard.evaluate_payload(payload)
        assert res["decision"] == "force_ask", f"Expected force_ask for '{cmd}', got {res}"
        assert "Rule 04" in res["reason"]


def test_shell_write_to_locked_directory_is_denied(monkeypatch):
    monkeypatch.setattr(
        guard,
        "load_freeze_config",
        lambda: (True, ["backend/app/", "frontend/src/", "migrations/", "tests/"], ["docs/", ".agents/"]),
    )
    cmds = [
        "echo test > backend/app/main.py",
        "rm -rf migrations/001.sql",
        "Set-Content -Path tests/test_new.py -Value 'data'",
        "cd backend/app && touch bad.py",
    ]
    for cmd in cmds:
        payload = {"toolCall": {"name": "run_command", "args": {"CommandLine": cmd}}}
        res = guard.evaluate_payload(payload)
        assert res["decision"] == "deny", f"Expected deny for '{cmd}', got {res}"
        assert "Code freeze active" in res["reason"]


def test_normal_read_only_shell_commands_are_allowed(monkeypatch):
    monkeypatch.setattr(
        guard,
        "load_freeze_config",
        lambda: (True, ["backend/app/", "frontend/src/", "migrations/", "tests/"], ["docs/", ".agents/"]),
    )
    read_cmds = [
        "git status",
        ".\\.venv\\Scripts\\python.exe -m pytest -q",
        "npm.cmd run lint",
        "cat docs/core/STATE.md",
    ]
    for cmd in read_cmds:
        payload = {"toolCall": {"name": "run_command", "args": {"CommandLine": cmd}}}
        res = guard.evaluate_payload(payload)
        assert res["decision"] == "allow", f"Expected allow for '{cmd}', got {res}"

