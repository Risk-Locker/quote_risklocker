"""Native PDF extraction with optional PyMuPDF/pdfplumber."""

from __future__ import annotations

from pathlib import Path

from app.extraction.types import ExtractionBundle


def extract_native(path: Path) -> ExtractionBundle:
    page_text: list[dict] = []
    words: list[dict] = []
    blocks: list[dict] = []
    tables: list[dict] = []
    images: list[dict] = []
    methods: list[str] = []
    warnings: list[str] = []

    try:
        import fitz  # type: ignore

        with fitz.open(path) as document:
            for page_index, page in enumerate(document, start=1):
                text = page.get_text("text") or ""
                page_text.append({"page": page_index, "text": text, "width": page.rect.width, "height": page.rect.height})
                for block in page.get_text("blocks") or []:
                    blocks.append({"page": page_index, "bbox": block[:4], "text": block[4] if len(block) > 4 else ""})
                for image_index, image in enumerate(page.get_images(full=True), start=1):
                    images.append({"page": page_index, "index": image_index, "xref": image[0]})
                for w in page.get_text("words") or []:
                    words.append({
                        "page": page_index,
                        "text": w[4],
                        "x0": w[0],
                        "top": w[1],
                        "x1": w[2],
                        "bottom": w[3],
                    })
        methods.append("PyMuPDF native text")
    except Exception as exc:
        warnings.append(f"Native PyMuPDF unavailable: {exc.__class__.__name__}")

    # Fallback to pdfplumber ONLY if PyMuPDF failed to extract text or words
    if not page_text or not words:
        try:
            import pdfplumber  # type: ignore

            with pdfplumber.open(str(path)) as pdf:
                for page_index, page in enumerate(pdf.pages, start=1):
                    extracted_words = page.extract_words() or []
                    words.extend({"page": page_index, **word} for word in extracted_words)
                    for table_index, table in enumerate(page.extract_tables() or [], start=1):
                        tables.append({"page": page_index, "index": table_index, "rows": table})
                    if page_index > len(page_text):
                        page_text.append({"page": page_index, "text": page.extract_text() or "", "width": page.width, "height": page.height})
            methods.append("pdfplumber layout text")
        except Exception as exc:
            warnings.append(f"pdfplumber unavailable: {exc.__class__.__name__}")

    raw_text = "\n".join(page.get("text", "") for page in sorted(page_text, key=lambda item: item.get("page", 0))).strip()
    if not raw_text:
        warnings.append("No selectable PDF text found. Enhanced reading may be needed.")

    return ExtractionBundle(raw_text=raw_text, page_text=page_text, words=words, blocks=blocks, tables=tables, images=images, method_summary=methods, warnings=warnings)

