import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.file_validation import display_filename, validate_upload_bytes
from app.services.document_security import quarantined_pdf
from app.storage.supabase import StorageError, SupabaseStorage


def storage_settings():
    return SimpleNamespace(
        supabase_url="https://project.supabase.co",
        supabase_service_role_key="backend-only-key",
        supabase_storage_bucket="risklocker-pdfs",
        max_upload_bytes=1024 * 1024,
    )


def test_upload_filename_is_display_only_and_sanitized():
    assert display_filename("../../secret.pdf") == "secret.pdf"
    assert display_filename("bad:name?.pdf") == "bad_name_.pdf"


def test_upload_accepts_only_valid_pdf_bytes():
    with pytest.raises(ValueError, match="File type does not match"):
        validate_upload_bytes("quote.pdf", "application/pdf", b"not a pdf")
    with pytest.raises(ValueError, match="Upload a PDF"):
        validate_upload_bytes("quote.png", "image/png", b"\x89PNG")
    assert validate_upload_bytes("quote.pdf", "application/pdf", b"%PDF-1.7\n") == ".pdf"


def test_upload_limit_is_enforced():
    with pytest.raises(ValueError, match="1MB or smaller"):
        validate_upload_bytes("quote.pdf", "application/pdf", b"%PDF" + b"0" * (1024 * 1024), max_bytes=1024 * 1024)


def test_supabase_object_key_blocks_traversal():
    assert SupabaseStorage._validate_object_key("source/2026/07/batch/file.pdf") == "source/2026/07/batch/file.pdf"
    with pytest.raises(StorageError, match="Invalid object key"):
        SupabaseStorage._validate_object_key("../outside.pdf")


def test_supabase_storage_uses_private_backend_requests():
    uploaded = b"%PDF-1.7\nverified"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer backend-only-key"
        assert "backend-only-key" not in str(request.url)
        if request.method == "GET" and "/bucket/" in request.url.path:
            return httpx.Response(200, json={"id": "risklocker-pdfs", "public": False})
        if request.method == "POST":
            assert request.url.path.endswith("/source/2026/07/batch/file.pdf")
            return httpx.Response(200, json={"Key": "source/2026/07/batch/file.pdf"}, headers={"etag": "test-etag"})
        if request.method == "GET":
            return httpx.Response(200, content=uploaded)
        if request.method == "DELETE":
            return httpx.Response(200, json=[])
        return httpx.Response(500)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    storage = SupabaseStorage(storage_settings(), client=client)
    storage.ensure_bucket()
    stored = storage.upload_pdf("source/2026/07/batch/file.pdf", uploaded)
    assert stored.sha256
    assert stored.etag == "test-etag"
    assert storage.download_bytes(stored.object_key) == uploaded
    storage.delete_pdf(stored.object_key)
    client.close()


def test_quarantine_rejects_active_pdf_content(monkeypatch, tmp_path):
    monkeypatch.setattr("app.services.document_security._defender_command", lambda _: None)
    settings = SimpleNamespace(require_malware_scanner=False)
    dangerous = b"%PDF-1.4\n/JavaScript\n%%EOF"
    with pytest.raises(ValueError, match="prohibited JavaScript"):
        with quarantined_pdf(dangerous, settings):
            pass
