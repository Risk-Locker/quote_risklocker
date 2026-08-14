"""Behavior contracts for the local three-process development runtime."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_full_runtime_starts_api_frontend_and_one_worker():
    source = (ROOT / "commands/start-full.ps1").read_text(encoding="utf-8")

    assert "start-backend.ps1" in source
    assert "start-frontend.ps1" in source
    assert "start-worker.ps1" in source
    assert source.count('"`"$workerScript`""') == 1
    assert "backend, worker, and frontend" in source


def test_runtime_stop_targets_the_background_worker():
    source = (ROOT / "commands/stop-app.ps1").read_text(encoding="utf-8")

    assert "run-worker.py" in source


def test_worker_launcher_uses_the_project_environment_and_in_repo_logs():
    path = ROOT / "commands/start-worker.ps1"
    assert path.exists()
    source = path.read_text(encoding="utf-8")

    assert '.\\.venv\\Scripts\\python.exe' in source
    assert "commands/run-worker.py" in source
    assert ".qc-tmp" in source
