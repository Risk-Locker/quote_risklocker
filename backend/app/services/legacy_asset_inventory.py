"""Conservative reference inventory used before any legacy asset cleanup."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import select

from app.services.template_assets import _local_asset_id


def _references(token: str, surfaces: list[dict[str, Any]]) -> list[dict[str, str]]:
    if not token:
        return []
    matches: list[dict[str, str]] = []
    for surface in surfaces:
        serialized = json.dumps(surface.get("payload"), sort_keys=True, default=str)
        if token in serialized:
            matches.append({"entity": str(surface["entity"]), "id": str(surface["id"])})
    return matches


def build_reference_inventory(
    local_paths: Iterable[Path],
    uploaded_records: Iterable[Any],
    surfaces: list[dict[str, Any]],
) -> dict[str, Any]:
    referenced: list[dict[str, Any]] = []
    unreferenced: list[dict[str, Any]] = []
    for path in sorted(local_paths, key=lambda item: item.name.casefold()):
        asset_id = _local_asset_id(path)
        refs = _references(asset_id, surfaces)
        item = {"id": asset_id, "filename": path.name, "references": refs}
        (referenced if refs else unreferenced).append(item)

    uploaded = []
    for record in uploaded_records:
        uploaded.append(
            {
                "id": str(record.id),
                "label": record.label,
                "filename": record.filename,
                "status": record.status,
                "storage_path": record.storage_path,
                "references": _references(str(record.id), surfaces),
            }
        )
    return {
        "local_referenced": referenced,
        "local_unreferenced": unreferenced,
        "uploaded_records": uploaded,
    }


def collect_database_surfaces(db) -> list[dict[str, Any]]:
    from app.models.tables import (
        AppSetting,
        GeneratedPdfVersion,
        Job,
        OurSpecialVariant,
        OutputTemplateConfig,
        QuotationDraft,
        RenderSnapshot,
        TemplateRevision,
    )

    surfaces: list[dict[str, Any]] = []

    def add(entity: str, row_id: object, payload: object) -> None:
        surfaces.append({"entity": entity, "id": str(row_id), "payload": payload})

    for row in db.scalars(select(OutputTemplateConfig)).all():
        add("output_template_config", row.id, row.fixed_fields)
    for row in db.scalars(select(TemplateRevision)).all():
        add("template_revision", row.id, row.config)
    for row in db.scalars(select(QuotationDraft)).all():
        add("quotation_draft", row.id, row.layout_override)
    for row in db.scalars(select(GeneratedPdfVersion)).all():
        add("generated_pdf_version", row.id, [row.draft_snapshot, row.template_snapshot, row.render_context_snapshot])
    for row in db.scalars(select(RenderSnapshot)).all():
        add("render_snapshot", row.id, [row.context, row.asset_hashes])
    for row in db.scalars(select(OurSpecialVariant)).all():
        add("our_special_variant", row.id, row.icon_asset_id)
    for row in db.scalars(select(AppSetting)).all():
        add("app_setting", row.key, row.value)
    for row in db.scalars(select(Job)).all():
        add("job", row.id, [row.payload, row.result])
    return surfaces
