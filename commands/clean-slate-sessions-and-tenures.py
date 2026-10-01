"""Clean slate script to safely purge all legacy test sessions, drafts, jobs,
uploaded test PDFs, client records, and placeholder tenures while strictly
preserving master templates, insurer catalogs, user accounts, and business assets.
"""

import sys
from pathlib import Path

# Add backend directory to sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
sys.path.insert(0, str(backend_dir))

from sqlalchemy import delete
from app.db.session import SessionLocal
from app.models.tables import (
    Batch,
    ClientRecord,
    CustomerAccount,
    DraftBenefitSelection,
    DraftSourceLineDecision,
    ExtractionRecord,
    GeneratedPdfVersion,
    InsuranceTenure,
    Job,
    QuotationActivity,
    QuotationDraft,
    RenderSnapshot,
    Session,
    TenureComparisonEntry,
    TrackedVehicle,
    TrashRecord,
    UploadedFile,
    VehicleOwnership,
)


def run_clean_slate():
    db = SessionLocal()
    try:
        print("[CLEAN SLATE] Starting safe purge of legacy sessions, drafts, and tenures...")

        # 1. Comparison entries & snapshots
        res_comp = db.execute(delete(TenureComparisonEntry))
        res_snap = db.execute(delete(RenderSnapshot))
        print(f"  - Purged {res_comp.rowcount} tenure comparison entries")
        print(f"  - Purged {res_snap.rowcount} render snapshots")

        # 2. Draft decisions & selections
        res_dec = db.execute(delete(DraftSourceLineDecision))
        res_sel = db.execute(delete(DraftBenefitSelection))
        print(f"  - Purged {res_dec.rowcount} draft decisions")
        print(f"  - Purged {res_sel.rowcount} draft benefit selections")

        # 3. Sessions & Activities
        res_act = db.execute(delete(QuotationActivity))
        res_sess = db.execute(delete(Session))
        print(f"  - Purged {res_act.rowcount} quotation activities")
        print(f"  - Purged {res_sess.rowcount} sessions")

        # 4. Drafts & Generated PDFs
        res_gen = db.execute(delete(GeneratedPdfVersion))
        res_draft = db.execute(delete(QuotationDraft))
        print(f"  - Purged {res_gen.rowcount} generated PDF versions")
        print(f"  - Purged {res_draft.rowcount} quotation drafts")

        # 5. Extraction records & Jobs
        res_ext = db.execute(delete(ExtractionRecord))
        res_job = db.execute(delete(Job))
        print(f"  - Purged {res_ext.rowcount} extraction records")
        print(f"  - Purged {res_job.rowcount} background extraction jobs")

        # 6. Uploaded files & Batches & Trash
        res_file = db.execute(delete(UploadedFile))
        res_batch = db.execute(delete(Batch))
        res_trash = db.execute(delete(TrashRecord))
        print(f"  - Purged {res_file.rowcount} uploaded files")
        print(f"  - Purged {res_batch.rowcount} upload batches")
        print(f"  - Purged {res_trash.rowcount} trash records")

        # 7. Tenures & Ownerships
        res_ten = db.execute(delete(InsuranceTenure))
        res_own = db.execute(delete(VehicleOwnership))
        print(f"  - Purged {res_ten.rowcount} insurance tenures")
        print(f"  - Purged {res_own.rowcount} vehicle ownership records")

        # 8. Tracked Vehicles & Clients
        res_veh = db.execute(delete(TrackedVehicle))
        res_cli = db.execute(delete(ClientRecord))
        res_acc = db.execute(delete(CustomerAccount))
        print(f"  - Purged {res_veh.rowcount} tracked vehicles")
        print(f"  - Purged {res_cli.rowcount} legacy client records")
        print(f"  - Purged {res_acc.rowcount} customer accounts")

        db.commit()
        print("\n[SUCCESS] Clean slate completed successfully. Database is now clean and production-ready!")
    except Exception as exc:
        db.rollback()
        print(f"\n[ERROR] Clean slate failed: {exc}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_clean_slate()
