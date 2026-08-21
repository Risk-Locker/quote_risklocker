"""Owner DOCX intake remains an unverified reference, never catalog truth."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
DOCX_CANDIDATES = [
    ROOT / "tests" / "fixtures" / "RiskLocker_Malaysia_Motor_Comprehensive_Packages_Benefits_Addons_2026.docx",
    ROOT / "fix" / "RiskLocker_Malaysia_Motor_Comprehensive_Packages_Benefits_Addons_2026.docx",
    ROOT / "Malaysia_Motor_Insurance_Quick_Benefits_Addons_2026.docx",
]
DOCX = next((p for p in DOCX_CANDIDATES if p.is_file()), DOCX_CANDIDATES[0])
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.models.tables import SourceDocument
from app.services.reference_intake import build_docx_reference, register_docx_reference


class FakeDb:
    def __init__(self, existing=None):
        self.existing = existing
        self.added = []
        self.commits = 0

    def scalar(self, _statement):
        return self.existing

    def add(self, item):
        self.added.append(item)

    def commit(self):
        self.commits += 1


def test_owner_docx_is_extracted_as_unverified_reference_only():
    reference = build_docx_reference(DOCX)

    assert reference["checksum"] and len(reference["checksum"]) == 64
    assert reference["verification_status"] == "unverified"
    assert reference["metadata_json"]["workspace_state"] == "draft_reference"
    assert reference["metadata_json"]["publication_allowed"] is False
    assert reference["metadata_json"]["source_filename"] == DOCX.name
    assert reference["metadata_json"]["text_item_count"] > 20
    assert len(reference["reference_text"]) > 1_000
    assert "QBE" in reference["reference_text"]
    assert "benefit_concepts" not in reference
    assert "catalog_offerings" not in reference


def test_registering_reference_is_idempotent_by_checksum():
    db = FakeDb()
    document, created = register_docx_reference(db, DOCX)

    assert created is True
    assert isinstance(document, SourceDocument)
    assert document.verification_status == "unverified"
    assert document.reviewed_by is None
    assert document.reviewed_at is None
    assert db.commits == 1

    retry_db = FakeDb(existing=document)
    same, created = register_docx_reference(retry_db, DOCX)
    assert same is document
    assert created is False
    assert retry_db.added == []
    assert retry_db.commits == 0


def test_non_docx_or_malformed_container_is_rejected(tmp_path):
    wrong = tmp_path / "reference.txt"
    wrong.write_text("not docx", encoding="utf-8")
    try:
        build_docx_reference(wrong)
    except ValueError as exc:
        assert "DOCX" in str(exc)
    else:
        raise AssertionError("Expected a DOCX validation error")

    malformed = tmp_path / "reference.docx"
    malformed.write_bytes(b"not a zip")
    try:
        build_docx_reference(malformed)
    except ValueError as exc:
        assert "malformed" in str(exc).lower()
    else:
        raise AssertionError("Expected a malformed DOCX error")
