"""High-DPI PyMuPDF Visual Crop Renderer for Multimodal Gemini Vision.

Renders targeted 300-400 DPI PNG image crops of quotation headers, footers,
schedule pages, and pricing/endorsement tables without injecting noisy OCR
text into Gemini Vision prompts.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_PRICING_ANCHOR_TOKENS = (
    "basic",
    "ncd",
    "ncb",
    "gross",
    "service tax",
    "sst",
    "stamp",
    "total",
    "payable",
    "contribution",
    "optional",
    "extra",
    "endorsement",
    "windscreen",
    "special peril",
    "peril",
    "towing",
    "betterment",
    "loading",
)


def _open_pdf_doc(pdf_bytes: bytes | None) -> Any | None:
    if not pdf_bytes or len(pdf_bytes) < 500 or not pdf_bytes.lstrip().startswith(b"%PDF"):
        return None
    try:
        import fitz

        return fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        logger.debug("Visual cropper could not open PDF bytes: %s", exc)
        return None


def _render_clip_png(page: Any, clip: Any | None, dpi: int) -> bytes | None:
    try:
        pix = page.get_pixmap(dpi=dpi, clip=clip, alpha=False)
        data = pix.tobytes("png")
        return data if data and len(data) > 100 else None
    except Exception as exc:
        logger.debug("Could not render PDF clip at %ddpi: %s", dpi, exc)
        return None


def render_header_footer_crops(
    pdf_bytes: bytes,
    dpi: int = 300,
) -> list[tuple[bytes, str]]:
    """Render Page 1 header logo strip and bottom footer brand strip at high DPI."""
    doc = _open_pdf_doc(pdf_bytes)
    if doc is None:
        return []
    crops: list[tuple[bytes, str]] = []
    try:
        if len(doc) < 1:
            return []
        import fitz

        page = doc[0]
        rect = page.rect
        w, h = float(rect.width), float(rect.height)
        if w <= 10 or h <= 10:
            return []

        header_rect = fitz.Rect(0, 0, w, h * 0.24)
        header_png = _render_clip_png(page, header_rect, dpi=dpi)
        if header_png:
            crops.append(
                (
                    header_png,
                    "Zoomed Page 1 Header Banner & Logo Crop (300 DPI): verify insurer emblem, brand name, and product tier.",
                )
            )

        footer_rect = fitz.Rect(0, h * 0.82, w, h)
        footer_png = _render_clip_png(page, footer_rect, dpi=dpi)
        if footer_png:
            crops.append(
                (
                    footer_png,
                    "Zoomed Page 1 Footer Strip Crop (300 DPI): verify official underwriter website domain and company registration.",
                )
            )
    finally:
        doc.close()
    return crops


def render_schedule_and_pricing_crops(
    pdf_bytes: bytes,
    *,
    dpi: int = 350,
    zoom_pricing_dpi: int = 400,
    include_pricing_zoom: bool = False,
) -> list[tuple[bytes, str]]:
    """Render high-DPI operative schedule images and optional 400-DPI pricing table zooms."""
    doc = _open_pdf_doc(pdf_bytes)
    if doc is None:
        return []
    crops: list[tuple[bytes, str]] = []
    try:
        import fitz

        max_pages = min(len(doc), 2)
        for p_idx in range(max_pages):
            page = doc[p_idx]
            page_no = p_idx + 1
            rect = page.rect
            w, h = float(rect.width), float(rect.height)
            if w <= 10 or h <= 10:
                continue

            full_png = _render_clip_png(page, None, dpi=dpi)
            if full_png:
                crops.append(
                    (
                        full_png,
                        f"Operative Page {page_no} High-Resolution Scan ({dpi} DPI): inspect printed and handwritten values carefully.",
                    )
                )

            if include_pricing_zoom:
                y_mins: list[float] = []
                y_maxs: list[float] = []
                try:
                    blocks = page.get_text("blocks") or []
                except Exception:
                    blocks = []
                for blk in blocks:
                    if len(blk) < 5:
                        continue
                    bx0, by0, bx1, by1, btext = blk[0], blk[1], blk[2], blk[3], str(blk[4] or "")
                    low = btext.lower()
                    if any(tok in low for tok in _PRICING_ANCHOR_TOKENS):
                        y_mins.append(float(by0))
                        y_maxs.append(float(by1))
                if y_mins and y_maxs:
                    top_y = max(0.0, min(y_mins) - 28.0)
                    bot_y = min(h, max(y_maxs) + 32.0)
                    if bot_y - top_y < h * 0.25:
                        top_y = max(0.0, top_y - h * 0.10)
                        bot_y = min(h, bot_y + h * 0.10)
                else:
                    top_y = h * 0.32
                    bot_y = h

                pricing_rect = fitz.Rect(0, top_y, w, bot_y)
                zoom_png = _render_clip_png(page, pricing_rect, dpi=zoom_pricing_dpi)
                if zoom_png:
                    crops.append(
                        (
                            zoom_png,
                            f"Page {page_no} Ultra-Sharp Pricing & Optional Riders Zoom ({zoom_pricing_dpi} DPI): read exact sen digits, Basic Premium, NCD, Riders, Gross, SST, Stamp Duty, and Final Insurer Payable.",
                        )
                    )
    finally:
        doc.close()
    return crops
