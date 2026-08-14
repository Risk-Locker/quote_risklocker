"""Repository-local temporary workspace helpers for private processing data."""

from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
QC_TEMP_ROOT = REPOSITORY_ROOT / ".qc-tmp"


@contextmanager
def qc_temp_directory(prefix: str) -> Iterator[Path]:
    """Create an automatically cleaned directory only under ``/.qc-tmp``."""

    QC_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=prefix, dir=QC_TEMP_ROOT) as directory:
        yield Path(directory)
