"""Text normalization and slugification utilities."""

from __future__ import annotations

import re


def slugify(value: str) -> str:
    """Create a URL/key-safe lowercase alphanumeric slug separated by hyphens."""
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def normalize_phrase(value: str) -> str:
    """Normalize text into lowercase single-space words for indexing and matching."""
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()
