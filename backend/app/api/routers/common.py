"""Shared API router utilities and helpers."""

from __future__ import annotations

from fastapi import Response
from app.services.pdf_content import parse_byte_range


def _pdf_response(data: bytes, filename: str, range_header: str | None, download: bool) -> Response:
    selected_range = parse_byte_range(range_header, len(data))
    disposition = "attachment" if download else "inline"
    safe_filename = filename.replace('"', "_").replace("\r", "_").replace("\n", "_")
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'{disposition}; filename="{safe_filename}"',
        "Cache-Control": "private, no-store",
    }
    if selected_range:
        start, end = selected_range
        headers["Content-Range"] = f"bytes {start}-{end}/{len(data)}"
        return Response(data[start : end + 1], status_code=206, media_type="application/pdf", headers=headers)
    return Response(data, media_type="application/pdf", headers=headers)
