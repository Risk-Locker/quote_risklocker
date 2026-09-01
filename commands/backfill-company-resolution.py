"""Batch re-evaluate and backfill company detection across all database sessions.

Usage (from repo root):
    python commands/backfill-company-resolution.py --dry-run
    python commands/backfill-company-resolution.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import select  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.extraction.company_resolution import build_companies_payload, resolve_company  # noqa: E402
from app.models.tables import (  # noqa: E402
    CompanyAlias,
    DraftBenefitSelection,
    DraftSourceLineDecision,
    ExtractionBenefitLine,
    ExtractionRecord,
    InsuranceCompany,
    QuotationDraft,
    Session,
    UploadedFile,
    new_id,
)
from app.services.catalog_review_service import auto_apply_extracted_benefits, initialize_catalog_review  # noqa: E402


def run_backfill(apply: bool = False) -> None:
    print(f"Running company resolution backfill (Mode: {'APPLY' if apply else 'DRY RUN'})...\n")

    # Step 1: Pre-load companies and session metadata in a single short-lived connection
    with SessionLocal() as db:
        companies = db.query(InsuranceCompany).all()
        alias_rows = db.query(CompanyAlias).all()
        db_companies = build_companies_payload(companies, alias_rows)

        session_rows = (
            db.query(Session.id, UploadedFile.id, QuotationDraft.id, UploadedFile.original_filename, Session.detected_company, QuotationDraft.company_id, QuotationDraft.fields)
            .join(UploadedFile, UploadedFile.id == Session.uploaded_file_id)
            .join(QuotationDraft, QuotationDraft.id == Session.draft_id)
            .order_by(Session.created_at.desc())
            .all()
        )

    print(f"Loaded {len(session_rows)} sessions to analyze.\n")

    updated_count = 0
    unchanged_count = 0
    unresolved_count = 0

    to_update: list[tuple[str, str, str, str, str]] = []

    for sess_id, file_id, draft_id, orig_fn, curr_name, curr_comp_id, fields in session_rows:
        resolved = resolve_company(orig_fn or "", db_companies)

        if resolved.get("status") != "matched" and fields:
            draft_val = str((fields.get("insurance_company") or {}).get("value") or "").strip()
            if draft_val:
                resolved = resolve_company(draft_val, db_companies)

        if resolved.get("status") == "matched":
            target_id = resolved["company_id"]
            target_name = resolved["display_name"]
            if (curr_comp_id != target_id) or (curr_name != target_name):
                to_update.append((str(sess_id), str(file_id), str(draft_id), target_id, target_name))
                print(f"[UPDATE CANDIDATE] Session {sess_id}:")
                print(f"  Filename: {orig_fn}")
                print(f"  Old: {curr_name} ({curr_comp_id}) -> New: {target_name} ({target_id})\n")
                updated_count += 1
            else:
                unchanged_count += 1
        else:
            unresolved_count += 1
            if curr_comp_id is None:
                print(f"[UNRESOLVED] Session {sess_id}: {orig_fn}")

    print(f"Summary: {updated_count} to update, {unchanged_count} unchanged, {unresolved_count} unresolved.\n")

    if not apply:
        print("[DRY RUN COMPLETE] Run with --apply to commit changes to database.")
        return

    # Step 2: Apply updates one-by-one with isolated transaction per session
    print("Applying updates to database...")
    committed = 0
    failed = 0

    for sess_id, file_id, draft_id, target_id, target_name in to_update:
        with SessionLocal() as db:
            try:
                sess = db.query(Session).filter(Session.id == sess_id).first()
                f = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
                draft = db.query(QuotationDraft).filter(QuotationDraft.id == draft_id).first()
                rec = db.query(ExtractionRecord).filter(ExtractionRecord.uploaded_file_id == file_id).first()

                if sess:
                    sess.detected_company = target_name
                if f:
                    f.insurance_company_id = target_id
                if draft:
                    draft.company_id = target_id
                    dfields = dict(draft.fields or {})
                    dfields["insurance_company"] = {"value": target_name, "status": "ready", "message": ""}
                    draft.fields = dfields
                if rec:
                    rec.company_resolution = {"status": "matched", "company_id": target_id, "display_name": target_name}
                    cands = dict(rec.candidates or {})
                    cands["insurance_company"] = [
                        {
                            "page": 1,
                            "field": "insurance_company",
                            "score": 0.99,
                            "value": target_name,
                            "evidence": f.original_filename if f else "",
                            "warnings": [],
                            "source_method": "database_company_filename",
                        }
                    ]
                    rec.candidates = cands

                if draft:
                    try:
                        # Purge stale selections and decisions from previous company
                        db.query(DraftSourceLineDecision).filter(DraftSourceLineDecision.draft_id == draft.id).delete()
                        db.query(DraftBenefitSelection).filter(DraftBenefitSelection.draft_id == draft.id).delete()
                        db.flush()

                        initialize_catalog_review(db, draft)

                        if rec:
                            lines = db.scalars(select(ExtractionBenefitLine).where(ExtractionBenefitLine.extraction_record_id == rec.id)).all()
                            for line in lines:
                                db.add(DraftSourceLineDecision(
                                    id=new_id(),
                                    draft_id=draft.id,
                                    source_line_id=line.id,
                                    disposition="unresolved",
                                ))
                            db.flush()
                            auto_apply_extracted_benefits(db, draft)
                    except Exception as cat_err:
                        print(f"  Notice: catalog sync for {sess_id}: {cat_err}")

                db.commit()
                committed += 1
                print(f"[COMMITTED] Session {sess_id} updated to {target_name}.")
            except Exception as e:
                db.rollback()
                failed += 1
                print(f"[ERROR] Failed to update session {sess_id}: {e}")

    print(f"\n[DONE] Successfully committed {committed} sessions ({failed} failed).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill company resolution on database sessions")
    parser.add_argument("--apply", action="store_true", help="Apply updates to database")
    parser.add_argument("--dry-run", action="store_true", help="Preview updates without committing")
    args = parser.parse_args()

    run_backfill(apply=args.apply)
