"""Static regression contract for the canonical one-file frontend flow."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_upload_page_uses_one_file_durable_job_api():
    source = (ROOT / "frontend/src/app/upload/page.tsx").read_text(encoding="utf-8")
    assert 'api<UploadResult>("/uploads"' in source
    assert '"Idempotency-Key"' in source
    assert 'api<{ job: JobStatus }>(`/jobs/${result.job_id}`' in source
    assert 'type="file"' in source
    assert "multiple" not in source
    assert 'form.append("file", file)' in source
    assert "/batches/upload" not in source


def test_legacy_batch_page_has_no_generate_all_action():
    source = (ROOT / "frontend/src/app/batches/[id]/page.tsx").read_text(encoding="utf-8")
    assert "generate-selected" not in source
    assert "Generate All" not in source
    assert "Review / Edit" in source
