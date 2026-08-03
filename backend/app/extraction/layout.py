"""Optional document layout helpers."""

from __future__ import annotations

import logging


logger = logging.getLogger(__name__)


def words_to_lines(words: list[dict], tolerance: float = 2.5) -> list[dict]:
    lines: list[dict] = []
    for word in sorted(words, key=lambda item: (int(item.get("page", 1)), float(item.get("top", 0)), float(item.get("x0", 0)))):
        page = int(word.get("page", 1))
        top = float(word.get("top", 0))
        target = None
        for line in lines:
            if line["page"] == page and abs(float(line["top"]) - top) <= tolerance:
                target = line
                break
        if not target:
            target = {"page": page, "top": top, "bottom": float(word.get("bottom", top)), "words": []}
            lines.append(target)
        target["words"].append(word)
        target["top"] = min(float(target["top"]), top)
        target["bottom"] = max(float(target["bottom"]), float(word.get("bottom", top)))

    regions: list[dict] = []
    for line in lines:
        line_words = sorted(line["words"], key=lambda item: float(item.get("x0", 0)))
        if not line_words:
            continue
        regions.append(
            {
                "type": "text_line",
                "page": line["page"],
                "text": " ".join(str(word.get("text", "")) for word in line_words).strip(),
                "x0": min(float(word.get("x0", 0)) for word in line_words),
                "x1": max(float(word.get("x1", 0)) for word in line_words),
                "top": line["top"],
                "bottom": line["bottom"],
            }
        )
    return regions


def detect_layout(words: list[dict] | None = None) -> tuple[list[dict], list[str]]:
    regions = words_to_lines(words or [])
    warnings: list[str] = []
    try:
        import cv2  # type: ignore  # noqa: F401

        warnings.append("OpenCV available for visual checks")
    except Exception as exc:
        logger.warning("OpenCV is not available: %s", exc)
        warnings.append("Visual checks unavailable on this machine.")
    return regions, warnings
