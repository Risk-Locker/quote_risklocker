"""Bootstrap the test session's gitignored base temp directory.

pytest.ini points --basetemp at ``.qc-tmp/pytest``, which does not exist on a
clean checkout (the folder is gitignored). pytest 7.x creates the basetemp with
``Path.mkdir()`` without parents, so the parent ``.qc-tmp`` must exist before
any tmp_path fixture resolves. Creating it here, at conftest import time,
guarantees every test can run on a fresh machine and a clean CI runner.
"""

from pathlib import Path

_QCTMP_PYTEST = Path(__file__).resolve().parents[1] / ".qc-tmp" / "pytest"
_QCTMP_PYTEST.mkdir(parents=True, exist_ok=True)
