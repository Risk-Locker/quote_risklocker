"""Extraction dataclasses shared across the pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CandidateValue:
    field: str
    value: str
    source_method: str
    score: float
    page: int | None = None
    evidence: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExtractionBundle:
    raw_text: str
    page_text: list[dict[str, Any]]
    words: list[dict[str, Any]] = field(default_factory=list)
    blocks: list[dict[str, Any]] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)
    images: list[dict[str, Any]] = field(default_factory=list)
    method_summary: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class FieldSelection:
    value: str | None
    status: str
    candidates: list[CandidateValue]
    warnings: list[str] = field(default_factory=list)

    def to_draft_field(self) -> dict[str, Any]:
        evidence = self.candidates[0].evidence if self.candidates else ""
        return {
            "value": self.value,
            "detected_value": self.value,
            "status": self.status,
            "message": "Please check this value." if self.status != "ready" else "",
            "warnings": self.warnings,
            "evidence": evidence,
        }
