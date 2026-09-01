"""Strict HTML-to-PDF rendering through the pinned Playwright Chromium."""

from __future__ import annotations

from pathlib import Path


class PdfRendererUnavailable(RuntimeError):
    """Retryable renderer dependency or process failure."""


class PdfOutputInvalid(RuntimeError):
    """Renderer returned an invalid or empty PDF."""


def html_to_pdf(
    html: str,
    output_path: Path,
    *,
    width: float = 794,
    height: float = 1123,
    timeout_ms: int = 30_000,
) -> tuple[Path, list[str]]:
    if width <= 0 or height <= 0:
        raise ValueError("PDF page dimensions must be positive.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PdfRendererUnavailable("The production PDF renderer is not installed.") from exc

    browser = None
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": max(1, round(width)), "height": max(1, round(height))},
                device_scale_factor=1,
            )
            page.set_default_timeout(timeout_ms)
            page.set_content(html, wait_until="domcontentloaded", timeout=timeout_ms)
            page.emulate_media(media="print")
            page.pdf(
                path=str(output_path),
                width=f"{width}px",
                height=f"{height}px",
                print_background=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                prefer_css_page_size=True,
                tagged=True,
            )
    except Exception as exc:
        output_path.unlink(missing_ok=True)
        raise PdfRendererUnavailable("The PDF renderer is temporarily unavailable.") from exc
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass

    try:
        data = output_path.read_bytes()
    except OSError as exc:
        raise PdfOutputInvalid("The renderer did not produce an output file.") from exc
    if len(data) < 100 or not data.startswith(b"%PDF-") or b"%%EOF" not in data[-2_048:]:
        output_path.unlink(missing_ok=True)
        raise PdfOutputInvalid("The renderer produced an invalid PDF.")
    return output_path, []
