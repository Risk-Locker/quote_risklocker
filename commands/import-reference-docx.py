"""Register the owner-provided benefits DOCX as an unverified source record."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.db.session import SessionLocal
from app.services.reference_intake import build_docx_reference, register_docx_reference


DEFAULT_DOCX = ROOT / "Malaysia_Motor_Insurance_Quick_Benefits_Addons_2026.docx"


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run/register a DOCX as unverified catalog reference material.")
    parser.add_argument("--path", type=Path, default=DEFAULT_DOCX)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report-path", type=Path, default=Path(".qc-tmp/docx-reference-report.json"))
    args = parser.parse_args()
    path = args.path.resolve()
    report_path = (ROOT / args.report_path).resolve() if not args.report_path.is_absolute() else args.report_path.resolve()
    try:
        report_path.relative_to((ROOT / ".qc-tmp").resolve())
    except ValueError:
        parser.error("--report-path must be inside .qc-tmp")

    reference = build_docx_reference(path)
    report: dict = {
        "mode": "apply" if args.apply else "dry_run",
        "checksum": reference["checksum"],
        "verification_status": reference["verification_status"],
        "metadata": reference["metadata_json"],
        "text_length": len(reference["reference_text"]),
    }
    if args.apply:
        with SessionLocal() as db:
            document, created = register_docx_reference(db, path)
            report["result"] = {"source_document_id": document.id, "created": created}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {report_path.relative_to(ROOT)} ({report['mode']}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
