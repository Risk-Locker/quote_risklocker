"""Plan and apply non-destructive legacy-to-v7 compatibility backfill."""

from __future__ import annotations

import re
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.services.compatibility_service import adapt_legacy_special, adapt_legacy_template


def _value(record: Any, name: str, default=None):
    return record.get(name, default) if isinstance(record, dict) else getattr(record, name, default)


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def stable_key(namespace: str, legacy_id: str) -> str:
    return sha256(f"risklocker-v7:{namespace}:{legacy_id}".encode("utf-8")).hexdigest()[:32]


def stable_uuid(namespace: str, legacy_id: str) -> str:
    digest = sha256(f"risklocker-v7:{namespace}:{legacy_id}".encode("utf-8")).hexdigest()[:32]
    return str(UUID(digest))


def build_backfill_plan(
    *,
    companies: list[Any],
    specials: list[Any],
    templates: list[Any],
    legacy_draft_ids: list[str] | None = None,
    legacy_version_ids: list[str] | None = None,
) -> dict:
    actions: list[dict] = []
    warnings: list[dict] = []

    aliases: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for company in companies:
        company_id = str(_value(company, "id"))
        candidates = [_value(company, "name", ""), *(_value(company, "detection_phrases", []) or [])]
        for alias in candidates:
            normalized = normalize_key(str(alias))
            if normalized:
                aliases[normalized].append((company_id, str(alias).strip()))
    for normalized, owners in sorted(aliases.items()):
        company_ids = sorted({owner[0] for owner in owners})
        if len(company_ids) > 1:
            warnings.append(
                {"kind": "duplicate_company_alias", "normalized_alias": normalized, "company_ids": company_ids}
            )
            continue
        actions.append(
            {
                "operation": "upsert",
                "entity": "company_alias",
                "stable_key": stable_key("company-alias", f"{company_ids[0]}:{normalized}"),
                "company_id": company_ids[0],
                "alias": owners[0][1],
                "normalized_alias": normalized,
            }
        )

    if specials:
        actions.append(
            {
                "operation": "upsert",
                "entity": "compatibility_catalog",
                "stable_key": stable_key("compatibility-catalog", "global-legacy-specials"),
                "company_id": None,
                "state": "compatibility",
                "verified": False,
            }
        )
    for parent in sorted(specials, key=lambda item: str(_value(item, "id"))):
        variants = list(_value(parent, "variants", []) or [])
        adapted = adapt_legacy_special(parent, variants)
        by_label: dict[str, list[str]] = defaultdict(list)
        for item in variants:
            by_label[normalize_key(str(_value(item, "label", "")))].append(str(_value(item, "id")))
        for label, ids in sorted(by_label.items()):
            if label and len(ids) > 1:
                warnings.append(
                    {
                        "kind": "duplicate_legacy_variant_label",
                        "legacy_special_id": str(_value(parent, "id")),
                        "normalized_label": label,
                        "variant_ids": sorted(ids),
                    }
                )
        actions.append(
            {
                "operation": "upsert",
                "entity": "compatibility_offering",
                "stable_key": stable_key("legacy-special", str(_value(parent, "id"))),
                "legacy_id": str(_value(parent, "id")),
                "company_id": None,
                "verified": False,
                "payload": adapted,
            }
        )

    for template in sorted(templates, key=lambda item: str(_value(item, "id"))):
        adapted = adapt_legacy_template(template)
        actions.append(
            {
                "operation": "upsert",
                "entity": "compatibility_template_revision",
                "stable_key": stable_key("legacy-template", str(_value(template, "id"))),
                "legacy_id": str(_value(template, "id")),
                "company_id": None,
                "legacy_company_id": adapted["legacy_company_id"],
                "payload": adapted,
            }
        )

    for draft_id in sorted(legacy_draft_ids or []):
        actions.append({"operation": "preserve", "entity": "legacy_draft", "legacy_id": draft_id})
    for version_id in sorted(legacy_version_ids or []):
        actions.append({"operation": "preserve", "entity": "generated_version", "legacy_id": version_id})

    actions.sort(key=lambda item: (item["operation"], item["entity"], item.get("stable_key") or item.get("legacy_id", "")))
    return {
        "schema_version": 1,
        "mode": "non_destructive_compatibility",
        "actions": actions,
        "warnings": sorted(warnings, key=lambda item: (item["kind"], str(item))),
        "summary": {
            "action_count": len(actions),
            "warning_count": len(warnings),
            "delete_count": 0,
            "guessed_company_count": 0,
            "legacy_drafts_preserved": len(legacy_draft_ids or []),
            "generated_versions_preserved": len(legacy_version_ids or []),
        },
    }


def report_path(workspace: Path, requested: Path) -> Path:
    workspace = workspace.resolve()
    qc_root = (workspace / ".qc-tmp").resolve()
    resolved = (workspace / requested).resolve() if not requested.is_absolute() else requested.resolve()
    try:
        resolved.relative_to(qc_root)
    except ValueError as exc:
        raise ValueError("Backfill reports must stay inside the repository .qc-tmp directory.") from exc
    return resolved


def apply_backfill_plan(db, plan: dict) -> dict:
    """Apply only deterministic INSERTs; legacy preserve actions remain report-only."""

    statements = 0
    inserted_or_present = 0
    try:
        for action in plan.get("actions", []):
            if action.get("operation") != "upsert":
                continue
            entity = action.get("entity")
            if entity == "company_alias":
                result = db.execute(
                    text(
                        "INSERT INTO company_aliases(id, company_id, alias, normalized_alias, alias_kind, status) "
                        "VALUES (:id, :company_id, :alias, :normalized_alias, 'compatibility', 'active') "
                        "ON CONFLICT DO NOTHING"
                    ),
                    {
                        "id": stable_uuid("company-alias", action["stable_key"]),
                        "company_id": action["company_id"],
                        "alias": action["alias"],
                        "normalized_alias": action["normalized_alias"],
                    },
                )
            elif entity == "compatibility_catalog":
                catalog_id = stable_uuid("compatibility-catalog", action["stable_key"])
                result = db.execute(
                    text(
                        "INSERT INTO benefit_catalogs(id, company_id, name, revision, status) "
                        "VALUES (:id, NULL, 'Legacy Our Specials', 1, 'compatibility') ON CONFLICT DO NOTHING"
                    ),
                    {"id": catalog_id},
                )
                db.execute(
                    text(
                        "INSERT INTO benefit_catalog_revisions(id, catalog_id, revision_number, state, source_document_ids, content_hash) "
                        "VALUES (:id, :catalog_id, 1, 'compatibility', '[]'::jsonb, :content_hash) ON CONFLICT DO NOTHING"
                    ),
                    {
                        "id": stable_uuid("compatibility-catalog-revision", action["stable_key"]),
                        "catalog_id": catalog_id,
                        "content_hash": sha256(b"legacy-our-specials-compatibility").hexdigest(),
                    },
                )
                statements += 1
                inserted_or_present += 1
            elif entity == "compatibility_template_revision":
                payload = action["payload"]
                page_id = stable_uuid("compatibility-page-profile", action["legacy_id"])
                result = db.execute(
                    text(
                        "INSERT INTO template_page_profiles(id, profile_key, name, width, height, unit, safe_margins, bleed, background_behavior, status) "
                        "VALUES (:id, :key, :name, :width, :height, 'px', '{}'::jsonb, '{}'::jsonb, 'clip', 'compatibility') "
                        "ON CONFLICT DO NOTHING"
                    ),
                    {
                        "id": page_id,
                        "key": f"legacy-{action['legacy_id']}",
                        "name": f"Legacy profile: {payload['name']}",
                        "width": (payload.get("config", {}).get("canvas", {}) or {}).get("width", 794),
                        "height": (payload.get("config", {}).get("canvas", {}) or {}).get("height", 1123),
                    },
                )
                db.execute(
                    text(
                        "INSERT INTO template_revisions(id, template_id, revision_number, state, page_profile_id, config, config_hash) "
                        "VALUES (:id, :template_id, 0, 'compatibility', :page_id, CAST(:config AS jsonb), :config_hash) "
                        "ON CONFLICT DO NOTHING"
                    ),
                    {
                        "id": stable_uuid("legacy-template-revision", action["legacy_id"]),
                        "template_id": action["legacy_id"],
                        "page_id": page_id,
                        "config": __import__("json").dumps(payload.get("config", {}), sort_keys=True),
                        "config_hash": sha256(__import__("json").dumps(payload.get("config", {}), sort_keys=True).encode()).hexdigest(),
                    },
                )
                statements += 1
                inserted_or_present += 1
            elif entity == "compatibility_offering":
                payload = action["payload"]
                catalog_revision_id = stable_uuid("compatibility-catalog-revision", stable_key("compatibility-catalog", "global-legacy-specials"))
                concept_id = stable_uuid("legacy-concept", action["legacy_id"])
                result = db.execute(
                    text(
                        "INSERT INTO benefit_concepts(id, concept_key, label, value_schema, display_template, status) "
                        "VALUES (:concept_id, :concept_key, :label, '{}'::jsonb, '{label}', 'compatibility') ON CONFLICT DO NOTHING"
                    ),
                    {"concept_id": concept_id, "concept_key": f"legacy-{action['legacy_id']}", "label": payload["label"]},
                )
                db.execute(
                    text(
                        "INSERT INTO catalog_offerings(id, catalog_revision_id, offering_key, concept_id, offering_kind, label_override, typed_value, source_citation, source_aliases, presentation_facet_ids, status) "
                        "VALUES (:id, :catalog_revision_id, :key, :concept_id, 'optional', :label, CAST(:typed_value AS jsonb), '{}'::jsonb, '[]'::jsonb, '[]'::jsonb, 'compatibility') "
                        "ON CONFLICT DO NOTHING"
                    ),
                    {
                        "id": stable_uuid("legacy-offering", action["legacy_id"]),
                        "catalog_revision_id": catalog_revision_id,
                        "key": f"legacy-{action['legacy_id']}",
                        "concept_id": concept_id,
                        "label": payload["label"],
                        "typed_value": __import__("json").dumps({"legacy_variants": payload["variants"]}, sort_keys=True),
                    },
                )
                statements += 1
                inserted_or_present += 1
            else:
                continue
            statements += 1
            inserted_or_present += 1 if getattr(result, "rowcount", 0) >= 0 else 0
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"statements": statements, "inserted_or_present": inserted_or_present}
