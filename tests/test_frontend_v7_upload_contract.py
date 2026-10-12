"""Static regression contract for the canonical one-file frontend flow."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_upload_page_uses_one_file_durable_job_api():
    page_source = (ROOT / "frontend/src/app/upload/page.tsx").read_text(encoding="utf-8")
    workspace_source = (ROOT / "frontend/src/components/upload/upload-workspace.tsx").read_text(encoding="utf-8")
    source = f"{page_source}\n{workspace_source}"
    assert 'api<UploadResult>("/uploads"' in source
    assert '"Idempotency-Key"' in source
    assert 'api<{ job: JobStatus }>(`/jobs/${result.job_id}`' in source
    assert 'type="file"' in source
    assert 'form.append("file", file)' in source
    assert "/batches/upload" not in source


def test_legacy_batch_and_review_routes_are_retired():
    assert not (ROOT / "frontend/src/app/batches").exists()
    assert not (ROOT / "frontend/src/app/review").exists()
