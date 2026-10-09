"""Migrate historical uploaded Cover Notes / Policy Schedules.

Finds all sessions where the uploaded file is a Cover Note,
marks session.document_type = 'covernote', removes their TenureComparisonEntry
records from comparison tables, and binds them to the vehicle tenure as official issued policies.
"""

import os
import sys
import re
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath("backend"))

from sqlalchemy import or_
from sqlalchemy.orm import selectinload
from app.db.session import SessionLocal
from app.models.tables import Session, UploadedFile, InsuranceTenure, TenureComparisonEntry, InsuranceCompany, ExtractionRecord
from app.extraction.candidate_finder import detect_is_covernote


def run_migration():
    db = SessionLocal()
    try:
        # 1. Directly target candidates matching cover/policy/schedule/nota in filename
        candidate_sessions = (
            db.query(Session)
            .join(UploadedFile, Session.uploaded_file_id == UploadedFile.id)
            .options(
                selectinload(Session.uploaded_file).selectinload(UploadedFile.extraction_record),
                selectinload(Session.draft),
            )
            .filter(
                UploadedFile.deleted_at.is_(None),
                or_(
                    UploadedFile.original_filename.ilike("%cover%"),
                    UploadedFile.original_filename.ilike("%policy%"),
                    UploadedFile.original_filename.ilike("%schedule%"),
                    UploadedFile.original_filename.ilike("%nota%"),
                    UploadedFile.original_filename.ilike("%jadual%"),
                    Session.document_type == "covernote",
                ),
            )
            .all()
        )

        migrated_count = 0
        cleaned_entries = 0
        tenures_updated = 0

        print(f"Inspecting {len(candidate_sessions)} candidate sessions...", flush=True)

        for s in candidate_sessions:
            fn = s.uploaded_file.original_filename if s.uploaded_file else ""
            raw_text = ""
            if s.uploaded_file and s.uploaded_file.extraction_record:
                raw_text = s.uploaded_file.extraction_record.raw_text or ""

            is_cn = detect_is_covernote(text=raw_text, filename=fn)
            if not is_cn:
                continue

            # Mark session as covernote
            if s.document_type != "covernote":
                s.document_type = "covernote"
                migrated_count += 1
                print(f"  -> Marked {fn} as covernote (session {s.id})", flush=True)

            # Delete any comparison entries created for this cover note session
            entries = db.query(TenureComparisonEntry).filter(TenureComparisonEntry.session_id == s.id).all()
            for e in entries:
                print(f"     Deleted comparison entry for {e.company_name} (tenure {e.tenure_id})", flush=True)
                db.delete(e)
                cleaned_entries += 1

            # Bind to tenure
            if s.tenure_id:
                t = db.get(InsuranceTenure, s.tenure_id)
                if t:
                    if t.covernote_session_id != s.id:
                        t.covernote_session_id = s.id
                        tenures_updated += 1
                        print(f"     Linked covernote to tenure {t.id} (Vehicle: {t.vehicle_no})", flush=True)

                    # Sync policy dates
                    if s.coverage_start_date:
                        t.coverage_start_date = s.coverage_start_date
                    if s.coverage_end_date:
                        t.coverage_end_date = s.coverage_end_date
                        t.expiry_month = s.coverage_end_date.strftime("%Y-%m")

                    # Extract total payable
                    if s.draft and isinstance(s.draft.fields, dict):
                        f = s.draft.fields
                        tot_val = (f.get("total_amount") or {}).get("value") or (f.get("total_payable") or {}).get("value")
                        if tot_val:
                            try:
                                t.won_premium = float(str(tot_val).replace(",", "").replace("RM", "").strip())
                            except (ValueError, TypeError):
                                pass

                    # Resolve winning company
                    if s.detected_company and not t.winning_company_id:
                        comp = db.query(InsuranceCompany).filter(InsuranceCompany.name.ilike(f"%{s.detected_company.strip()}%")).first()
                        if comp:
                            t.winning_company_id = comp.id

                    # Advance stage to Issue Policy if not already hit
                    if t.stage in ("Quotations", "Material to Client", None, "draft"):
                        t.stage = "Issue Policy"
                        stage_hist = dict(t.stage_history or {})
                        stage_hist["Issue Policy"] = datetime.now(timezone.utc).isoformat()
                        t.stage_history = stage_hist
                        t.stage_updated_at = datetime.now(timezone.utc)

        db.commit()
        print("\n=== Cover Note Migration Summary ===", flush=True)
        print(f"Sessions classified as covernote: {migrated_count}", flush=True)
        print(f"Redundant comparison entries deleted: {cleaned_entries}", flush=True)
        print(f"Tenures bound to official cover notes: {tenures_updated}", flush=True)
        print("Migration completed successfully!", flush=True)

    finally:
        db.close()


if __name__ == "__main__":
    run_migration()
