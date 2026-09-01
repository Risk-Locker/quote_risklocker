"""Quarantine and inspect PDFs before persistent storage or extraction."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from uuid import uuid4

import fitz
import pikepdf

from app.core.config import Settings
from app.core.workspace import QC_TEMP_ROOT, qc_temp_directory


MAX_PDF_PAGES = 100
FORBIDDEN_PDF_MARKERS = {
    b"/JavaScript": "JavaScript",
    b"/Launch": "launch action",
    b"/EmbeddedFiles": "embedded file",
    b"/FileAttachment": "file attachment",
    b"/XFA": "XFA form",
}


def _defender_command(path: Path) -> tuple[list[str], str] | None:
    executable = shutil.which("MpCmdRun.exe")
    if not executable:
        platform_root = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Microsoft" / "Windows Defender" / "Platform"
        candidates = sorted(platform_root.glob("*/MpCmdRun.exe"), reverse=True) if platform_root.exists() else []
        executable = str(candidates[0]) if candidates else None
    if executable:
        return [executable, "-Scan", "-ScanType", "3", "-File", str(path), "-DisableRemediation"], "Microsoft Defender"
    clamdscan = shutil.which("clamdscan")
    if clamdscan:
        return [clamdscan, "--no-summary", str(path)], "ClamAV"
    clamscan = shutil.which("clamscan")
    if clamscan:
        return [clamscan, "--no-summary", str(path)], "ClamAV"
    return None


def scanner_status(settings: Settings | None = None) -> tuple[bool, str]:
    placeholder = QC_TEMP_ROOT / "risklocker-scanner-check.pdf"
    command = _defender_command(placeholder)
    if command:
        return True, f"{command[1]} is available."
    if settings is not None and not getattr(settings, "require_malware_scanner", True):
        return True, "Built-in structural inspection (pikepdf + PyMuPDF) active."
    return False, "Install or enable Microsoft Defender/ClamAV for required PDF scanning."


def _scan_malware(path: Path, required: bool) -> dict:
    command = _defender_command(path)
    if not command:
        if required:
            raise ValueError("A malware scanner is required before PDFs can be uploaded.")
        return {"engine": "builtin_structural", "result": "clean", "signature_version": "pikepdf+PyMuPDF"}
    args, engine = command
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("The malware scan could not be completed.") from exc
    if result.returncode != 0:
        raise ValueError("The PDF did not pass the malware scan.")
    signature = None
    match = re.search(r"Version:\s*([^\r\n]+)", f"{result.stdout}\n{result.stderr}", re.IGNORECASE)
    if match:
        signature = match.group(1).strip()[:120]
    return {"engine": engine, "result": "clean", "signature_version": signature}


def _inspect_pdf(path: Path, max_pages: int = MAX_PDF_PAGES) -> dict:
    raw = path.read_bytes()
    for marker, description in FORBIDDEN_PDF_MARKERS.items():
        if marker.lower() in raw.lower():
            raise ValueError(f"PDF contains a prohibited {description}.")
    try:
        with pikepdf.open(path) as pdf:
            if len(pdf.attachments):
                raise ValueError("PDFs containing embedded files are not accepted.")
            root = pdf.Root
            if "/OpenAction" in root or "/AA" in root:
                raise ValueError("PDFs containing automatic actions are not accepted.")

            # Check document-level JavaScript
            names = root.get("/Names")
            if names is not None and "/JavaScript" in names:
                js_tree = names.get("/JavaScript")
                if js_tree is not None and (
                    ("/Names" in js_tree and len(js_tree["/Names"]) > 0)
                    or ("/Kids" in js_tree and len(js_tree["/Kids"]) > 0)
                ):
                    raise ValueError("PDF contains a prohibited JavaScript.")

            acro_form = root.get("/AcroForm")
            if acro_form is not None:
                if "/XFA" in acro_form:
                    raise ValueError("PDFs containing XFA forms are not accepted.")
                fields = acro_form.get("/Fields", [])
                for field in fields:
                    if isinstance(field, pikepdf.Dictionary):
                        action = field.get("/A")
                        if isinstance(action, pikepdf.Dictionary) and action.get("/S") == "/JavaScript":
                            raise ValueError("PDF contains a prohibited JavaScript.")
                        if "/AA" in field:
                            raise ValueError("PDFs containing automatic actions are not accepted.")

            for page in pdf.pages:
                if "/AA" in page:
                    raise ValueError("PDFs containing automatic actions are not accepted.")
                annots = page.get("/Annots")
                if annots is not None and isinstance(annots, pikepdf.Array):
                    for annot in annots:
                        if isinstance(annot, pikepdf.Dictionary):
                            a = annot.get("/A")
                            if isinstance(a, pikepdf.Dictionary) and a.get("/S") == "/JavaScript":
                                raise ValueError("PDF contains a prohibited JavaScript.")
                            if "/AA" in annot:
                                raise ValueError("PDFs containing automatic actions are not accepted.")
    except pikepdf.PasswordError as exc:
        raise ValueError("Encrypted or password-protected PDFs are not accepted.") from exc
    except pikepdf.PdfError as exc:
        raise ValueError("The PDF is malformed or unreadable.") from exc

    try:
        document = fitz.open(path)
    except Exception as exc:
        raise ValueError("The PDF is malformed or unreadable.") from exc
    try:
        if document.needs_pass:
            raise ValueError("Encrypted or password-protected PDFs are not accepted.")
        if document.page_count < 1:
            raise ValueError("The PDF has no readable pages.")
        if document.page_count > max_pages:
            raise ValueError(f"PDFs may contain up to {max_pages} pages.")
        embedded_count = len(document.embfile_names()) if hasattr(document, "embfile_names") else 0
        if embedded_count:
            raise ValueError("PDFs containing embedded files are not accepted.")
        for page in document:
            rect = page.rect
            if rect.width <= 0 or rect.height <= 0 or rect.width > 20000 or rect.height > 20000:
                raise ValueError("The PDF contains an invalid page size.")
        return {"pages": document.page_count, "structure": "clean", "structure_engine": "pikepdf+PyMuPDF"}
    finally:
        document.close()


@contextmanager
def quarantined_pdf(data: bytes, settings: Settings) -> Iterator[tuple[Path, dict]]:
    with qc_temp_directory("quarantine-") as directory:
        path = directory / f"{uuid4()}.pdf"
        path.write_bytes(data)
        structure = _inspect_pdf(path, settings.max_pdf_pages)
        malware = _scan_malware(path, settings.require_malware_scanner)
        scan = {
            **structure,
            **malware,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            yield path, scan
        finally:
            if path.exists():
                path.unlink()
