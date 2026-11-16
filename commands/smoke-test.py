"""Run one real upload, review, generate, download flow and clean it up."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import fitz  # noqa: E402
import httpx  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.security import csrf_token_for_session  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.enums import AccountStatus, Role  # noqa: E402
from app.models.tables import (  # noqa: E402
    AuditEvent,
    AuthSession,
    Batch,
    CorrectionMemory,
    ExtractionRecord,
    GeneratedPdfVersion,
    QuotationDraft,
    UploadedFile,
    User,
)
from app.storage.supabase import StorageError, SupabaseStorage  # noqa: E402
from app.services.auth_service import create_session  # noqa: E402


def create_smoke_pdf(path: Path) -> None:
    lines = [
        "MOTOR TAKAFUL QUOTATION SLIP",
        "Etiqa General Takaful Berhad",
        "Applicant : SMOKE TEST CUSTOMER",
        "Period of Cover : 16/05/2026 until 15/05/2027",
        "Vehicle Registration Number : TST9000",
        "Vehicle Make : PERODUA",
        "Vehicle Model : ATIVA 1.0L TURBO AV",
        "Year of Manufactured : 2023",
        "Sum Covered : RM 57000.00 (Market Value)",
        "Cover Type : Comprehensive",
        "NCD (55.00%) RM 891.50",
        "Gross Contribution RM 1067.06",
        "Total Contribution Payable RM 1242.62",
    ]
    document = fitz.open()
    page = document.new_page()
    y = 60
    for line in lines:
        page.insert_text((55, y), line, fontsize=10)
        y += 24
    document.save(path)
    document.close()


def cleanup(owner_id: str) -> None:
    settings = get_settings()
    storage = SupabaseStorage(settings)
    with SessionLocal() as db:
        uploads = list(db.scalars(select(UploadedFile).where(UploadedFile.owner_id == owner_id)).all())
        upload_ids = [item.id for item in uploads]
        drafts = list(db.scalars(select(QuotationDraft).where(QuotationDraft.owner_id == owner_id)).all())
        draft_ids = [item.id for item in drafts]
        versions = list(
            db.scalars(select(GeneratedPdfVersion).where(GeneratedPdfVersion.draft_id.in_(draft_ids))).all()
        ) if draft_ids else []
        for record in [*uploads, *versions]:
            if record.storage_provider == "supabase":
                try:
                    storage.delete_pdf(record.storage_path)
                except StorageError:
                    pass
        if draft_ids:
            db.execute(delete(CorrectionMemory).where(CorrectionMemory.draft_id.in_(draft_ids)))
            db.execute(delete(GeneratedPdfVersion).where(GeneratedPdfVersion.draft_id.in_(draft_ids)))
            db.execute(delete(QuotationDraft).where(QuotationDraft.id.in_(draft_ids)))
        if upload_ids:
            db.execute(delete(ExtractionRecord).where(ExtractionRecord.uploaded_file_id.in_(upload_ids)))
            db.execute(delete(UploadedFile).where(UploadedFile.id.in_(upload_ids)))
        db.execute(delete(Batch).where(Batch.owner_id == owner_id))
        db.execute(delete(AuthSession).where(AuthSession.user_id == owner_id))
        db.execute(delete(AuditEvent).where(AuditEvent.actor_id == owner_id))
        db.execute(delete(User).where(User.id == owner_id))
        db.commit()


def run(base_url: str) -> None:
    email = f"smoke-{uuid4().hex}@risklocker.com"
    settings = get_settings()
    with SessionLocal() as db:
        user = User(
            email=email,
            role=Role.ADMIN.value,
            status=AccountStatus.ACTIVE.value,
        )
        db.add(user)
        db.flush()
        _, session_token = create_session(db, settings, user, user_agent="risklocker-smoke-test")
        db.commit()
        db.refresh(user)
        owner_id = user.id

    try:
        csrf_token = csrf_token_for_session(session_token, settings.auth_hash_secret)
        with httpx.Client(base_url=base_url.rstrip("/"), timeout=180) as client:
            client.cookies.set(settings.session_cookie_name, session_token)
            client.cookies.set("risklocker_csrf", csrf_token)
            client.headers["X-CSRF-Token"] = csrf_token

            with tempfile.TemporaryDirectory(prefix="risklocker-smoke-") as directory:
                pdf_path = Path(directory) / "20260330_TST9000_Quotation_Etiqa.pdf"
                create_smoke_pdf(pdf_path)
                with pdf_path.open("rb") as handle:
                    upload = client.post(
                        "/api/batches/upload",
                        files={"files": (pdf_path.name, handle, "application/pdf")},
                        data={"enhanced_reading": "false"},
                    )
                upload.raise_for_status()
            batch = upload.json()["batch"]
            if not batch["files"]:
                raise RuntimeError(f"Smoke upload failed: {batch.get('failed_files')}")
            draft_id = batch["files"][0]["draft_id"]

            detail = client.get(f"/api/drafts/{draft_id}")
            detail.raise_for_status()
            draft = detail.json()["draft"]
            template = next(
                (item for item in draft["available_templates"] if item.get("is_default")),
                draft["available_templates"][0],
            )
            package = template["packages"][0]["name"]
            reviewed_fields = {
                key: "" if field.get("value") is None else str(field.get("value"))
                for key, field in draft["fields"].items()
            }
            save = client.patch(
                f"/api/drafts/{draft_id}",
                json={
                    "fields": reviewed_fields,
                    "template_id": template["id"],
                    "selected_package": package,
                    "benefits_selected": "[]",
                    "add_ons_selected": "[]",
                },
            )
            save.raise_for_status()

            generate = client.post(f"/api/drafts/{draft_id}/generate", json={})
            generate.raise_for_status()
            version = generate.json()["version"]
            content = client.get(f"/api/generated-versions/{version['id']}/content")
            content.raise_for_status()
            if not content.content.startswith(b"%PDF"):
                raise RuntimeError("Generated content is not a PDF.")
            print(
                "Smoke flow passed: upload -> extraction -> review -> generate -> authenticated PDF download "
                f"({len(content.content)} bytes)."
            )
    finally:
        cleanup(owner_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8100")
    arguments = parser.parse_args()
    run(arguments.base_url)
