"""Repository-local temporary workspace helpers for private processing data."""

from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
QC_TEMP_ROOT = REPOSITORY_ROOT / ".qc-tmp"


QC_TEMP_ROOT.mkdir(parents=True, exist_ok=True)


def resolve_qc_path(relative_or_absolute: str | Path) -> Path:
    """Resolve a path reliably against QC_TEMP_ROOT, CWD, and REPOSITORY_ROOT."""
    p = Path(relative_or_absolute)
    if p.is_absolute() and p.exists():
        return p
    if p.exists():
        return p.resolve()
    cand_repo = (REPOSITORY_ROOT / p).resolve()
    if cand_repo.exists():
        return cand_repo
    cleaned_rel = str(relative_or_absolute).replace("\\", "/").lstrip("/")
    if cleaned_rel.startswith(".qc-tmp/"):
        cleaned_rel = cleaned_rel[len(".qc-tmp/"):]
    cand_qc = (QC_TEMP_ROOT / cleaned_rel).resolve()
    if cand_qc.exists():
        return cand_qc
    cand_backend_qc = (REPOSITORY_ROOT / "backend" / ".qc-tmp" / cleaned_rel).resolve()
    if cand_backend_qc.exists():
        return cand_backend_qc
    return cand_qc


@contextmanager
def qc_temp_directory(prefix: str) -> Generator[Path, None, None]:
    """Create an automatically cleaned directory only under ``/.qc-tmp``."""

    QC_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=prefix, dir=QC_TEMP_ROOT) as directory:
        yield Path(directory)
