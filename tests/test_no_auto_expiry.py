"""New v7 source and generated objects have no automatic expiry."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services import pdf_service, upload_service


def test_new_source_and_generated_pdf_paths_assign_no_expiry_timestamp():
    upload_source = inspect.getsource(upload_service._persist_upload)
    generation_source = inspect.getsource(pdf_service.generate_pdf)

    assert "storage_expires_at=None" in upload_source
    assert "storage_expires_at=None" in generation_source
    assert "settings.pdf_retention_days" not in upload_source
    assert "settings.pdf_retention_days" not in generation_source
