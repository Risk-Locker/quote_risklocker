"""Enhanced reading is functional and temporary data stays in-repository."""

from __future__ import annotations

import sys
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.workspace import qc_temp_directory
from app.extraction import ocr
from app.extraction import orchestrator
from app.extraction.types import ExtractionBundle


def test_qc_temp_directory_is_inside_repository_and_is_removed_after_use():
    with qc_temp_directory("unit-") as directory:
        resolved = directory.resolve()
        assert resolved.is_relative_to((ROOT / ".qc-tmp").resolve())
        (directory / "private.txt").write_text("private", encoding="utf-8")
        retained_path = directory
    assert not retained_path.exists()


def test_tesseract_enhanced_reading_returns_page_text(monkeypatch, tmp_path):
    pdf = tmp_path / "scan.pdf"
    document = fitz.open()
    document.new_page()
    document.new_page()
    document.save(pdf)
    document.close()

    monkeypatch.setattr(ocr, "available_engines", lambda: {"paddleocr": False, "tesseract": True, "ocrmypdf": False})
    seen: list[int] = []

    def fake_page(_page, page_number):
        seen.append(page_number)
        return f"OCR text from page {page_number}"

    monkeypatch.setattr(ocr, "_tesseract_page_text", fake_page)
    text, methods, warnings = ocr.run_enhanced_reading(pdf)

    assert seen == [1, 2]
    assert text == "OCR text from page 1\n\nOCR text from page 2"
    assert methods == ["Tesseract OCR (2 pages)"]
    assert warnings == []


def test_ocr_failure_is_actionable_and_does_not_claim_success(monkeypatch, tmp_path):
    pdf = tmp_path / "scan.pdf"
    document = fitz.open()
    document.new_page()
    document.save(pdf)
    document.close()

    monkeypatch.setattr(ocr, "available_engines", lambda: {"paddleocr": False, "tesseract": True, "ocrmypdf": False})
    monkeypatch.setattr(ocr, "_tesseract_page_text", lambda *_args: (_ for _ in ()).throw(RuntimeError("engine crash")))

    text, methods, warnings = ocr.run_enhanced_reading(pdf)

    assert text == ""
    assert methods == []
    assert warnings == ["Enhanced reading failed. Review this document manually or retry."]


def test_ocr_text_reaches_structured_benefit_line_extraction(monkeypatch, tmp_path):
    source = tmp_path / "scanned-quotation.pdf"
    source.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(orchestrator, "extract_native", lambda _path: ExtractionBundle(
        raw_text="", page_text=[{"page": 1, "text": ""}], method_summary=["PyMuPDF native text"],
    ))
    monkeypatch.setattr(
        orchestrator,
        "run_enhanced_reading",
        lambda _path: ("SELECTED BENEFITS\nTowing 999 km", ["Tesseract OCR (1 pages)"], []),
    )

    result = orchestrator.ExtractionOrchestrator().extract_file(source, enhanced_reading=True)

    assert result["full_record"]["ocr_page_text"] == [{"page": 1, "text": "SELECTED BENEFITS\nTowing 999 km", "source_method": "ocr"}]
    assert any(line["raw_label"] == "Towing 999 km" and line["inclusion_state"] == "selected" for line in result["full_record"]["benefit_lines"])
