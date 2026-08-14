"""Safe intake of owner-provided DOCX material as unpublished evidence."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from sqlalchemy import select

from app.models.tables import SourceDocument


WORD_NAMESPACE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _document_text(data: bytes, path: Path) -> tuple[str, int]:
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if "word/document.xml" not in names or "[Content_Types].xml" not in names:
                raise ValueError("The DOCX container is malformed or incomplete.")
            if archive.getinfo("word/document.xml").file_size > 20 * 1024 * 1024:
                raise ValueError("The DOCX document content is too large.")
            xml = archive.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError, OSError) as exc:
        raise ValueError("The DOCX container is malformed or unreadable.") from exc
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise ValueError("The DOCX document XML is malformed.") from exc

    items: list[str] = []
    for paragraph in root.iter(f"{WORD_NAMESPACE}p"):
        fragments = [node.text or "" for node in paragraph.iter(f"{WORD_NAMESPACE}t")]
        value = "".join(fragments).strip()
        if value:
            items.append(value)
    if not items:
        raise ValueError("The DOCX document contains no readable text.")
    return "\n".join(items), len(items)


def build_docx_reference(path: Path) -> dict:
    if path.suffix.casefold() != ".docx":
        raise ValueError("Upload a DOCX reference document.")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ValueError("The DOCX reference document could not be read.") from exc
    if not data or len(data) > 20 * 1024 * 1024:
        raise ValueError("The DOCX reference document size is invalid.")
    text, item_count = _document_text(data, path)
    return {
        "issuer": "Owner-supplied insurance reference compilation",
        "title": path.stem.replace("_", " "),
        "reference_url": None,
        "reference_text": text,
        "effective_from": None,
        "effective_to": None,
        "checksum": hashlib.sha256(data).hexdigest(),
        "verification_status": "unverified",
        "reviewed_by": None,
        "reviewed_at": None,
        "metadata_json": {
            "source_filename": path.name,
            "source_format": "docx",
            "text_item_count": item_count,
            "workspace_state": "draft_reference",
            "publication_allowed": False,
            "verification_required": "primary_insurer_source",
        },
    }


def register_docx_reference(db, path: Path) -> tuple[SourceDocument, bool]:
    reference = build_docx_reference(path)
    existing = db.scalar(select(SourceDocument).where(SourceDocument.checksum == reference["checksum"]))
    if existing is not None:
        return existing, False
    document = SourceDocument(**reference)
    db.add(document)
    db.commit()
    return document, True
